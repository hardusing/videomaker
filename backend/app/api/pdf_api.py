# app/api/pdf_api.py

from fastapi import APIRouter, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pathlib import Path
import os
import fitz  # 来自 PyMuPDF
from pdf2image import convert_from_path
from typing import List, Dict, Any
from ..utils.task_manager import task_manager, TaskStatus
import json
import asyncio
from PIL import Image
import base64
import io
import uuid
from os.path import abspath
import comtypes.client

router = APIRouter(prefix="/api/pdf", tags=["PDF 操作"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "pdf_uploads"
PDF_DIR = BASE_DIR / "pdf_uploads"
IMG_DIR = BASE_DIR / "converted_images"

IMG_DIR.mkdir(parents=True, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

def pptx_to_pdf(pptx_path, pdf_path):
    powerpoint = comtypes.client.CreateObject("Powerpoint.Application")
    powerpoint.Visible = 1

    # 使用绝对路径
    pptx_path = abspath(pptx_path)
    pdf_path = abspath(pdf_path)

    deck = powerpoint.Presentations.Open(pptx_path)
    deck.SaveAs(pdf_path, FileFormat=32)  # 32 for PDF format
    deck.Close()
    powerpoint.Quit()

def convert_folder_pptx_to_pdf(folder_path):
    for filename in os.listdir(folder_path):
        if filename.endswith(".pptx"):
            pptx_path = os.path.join(folder_path, filename)
            print(pptx_path)
            pdf_path = os.path.join(folder_path, filename.replace(".pptx", ".pdf"))
            pptx_to_pdf(pptx_path, pdf_path)
            print(f"Converted {filename} to PDF.")

@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="只支持 PDF 文件")

    # 创建新任务
    task_id = task_manager.create_task(
        task_type="pdf_upload",
        initial_data={
            "original_filename": file.filename,
            "status": "uploading"
        }
    )

    try:
        # 保存文件
        save_path = Path(UPLOAD_DIR) / file.filename
        with open(save_path, "wb") as f:
            f.write(await file.read())

        # 更新任务状态
        task_manager.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            data={
                "original_filename": file.filename,
                "saved_path": str(save_path),
                "file_size": os.path.getsize(save_path)
            }
        )

        return {
            "message": "上传成功",
            "filename": file.filename,
            "task_id": task_id
        }
    except Exception as e:
        task_manager.update_task_status(task_id, TaskStatus.FAILED, str(e))
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

@router.get("/upload/list", response_model=List[Dict[str, str]])
async def list_uploaded_files():
    """获取上传目录下所有 PDF 文件名及其对应的 task_id"""
    if not UPLOAD_DIR.exists():
        raise HTTPException(status_code=404, detail="上传目录不存在")
    files = []
    for f in UPLOAD_DIR.glob("*.pdf"):
        task_id = task_manager.get_task_id_by_filename(f.name)
        files.append({"filename": f.name, "task_id": task_id})
    return files

@router.delete("/upload/delete/{filename}")
async def delete_uploaded_file(filename: str):
    """删除上传目录下指定的 PDF 文件"""
    file_path = UPLOAD_DIR / filename
    if not file_path.exists() or not file_path.suffix == ".pdf":
        raise HTTPException(status_code=404, detail="指定的 PDF 文件不存在")
    try:
        file_path.unlink()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
    return {"message": f"{filename} 已删除"}

@router.post("/convert/{task_id}")
async def convert_pdf_to_images(task_id: str):
    """使用 PyMuPDF 将 PDF 每页转为 PNG，并保存到以 PDF 文件名为名的子目录中，返回图片ID和缩略图"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task["type"] != "pdf_upload":
        raise HTTPException(status_code=400, detail="无效的任务类型，需要先上传 PDF")
    if task["status"] != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="PDF 上传任务未完成")

    pdf_filename = task["data"]["original_filename"]
    pdf_path = PDF_DIR / pdf_filename

    # 创建转换任务
    convert_task_id = task_manager.create_task(
        task_type="pdf_to_images",
        initial_data={
            "pdf_filename": pdf_filename,
            "status": "converting",
            "parent_task_id": task_id
        }
    )

    async def generate():
        try:
            doc = fitz.open(pdf_path)
            stem = pdf_path.stem
            output_subdir = IMG_DIR / stem
            output_subdir.mkdir(parents=True, exist_ok=True)
            saved_files = []
            total_pages = len(doc)
            for i, page in enumerate(doc, start=1):
                progress = int((i / total_pages) * 100)
                task_manager.update_task_progress(convert_task_id, progress)
                # 生成唯一图片ID
                image_id = str(i)
                img_path = output_subdir / f"{image_id}.png"
                pix = page.get_pixmap(dpi=200)
                pix.save(str(img_path))
                saved_files.append({
                    "image_id": image_id,
                    "image_path": f"{stem}/{image_id}.png"
                })
                # 生成缩略图
                image = Image.open(str(img_path))
                image.thumbnail((120, 120))
                buf = io.BytesIO()
                image.save(buf, format='PNG')
                thumb_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                # 实时写入主任务进度
                parent_task = task_manager.get_task(task_id)
                parent_data = parent_task.get("data", {})
                parent_data["pdf_to_images"] = {
                    "status": "processing",
                    "progress": progress,
                    "current_page": i,
                    "total_pages": total_pages,
                    "images": saved_files.copy()
                }
                task_manager.update_task(task_id, data=parent_data)
                # 返回数据
                yield json.dumps({
                    "image_id": image_id,
                    "image_path": f"{stem}/{image_id}.png",
                    "thumbnail": thumb_base64,
                    "progress": progress,
                    "current_page": i,
                    "total_pages": total_pages,
                    "task_id": convert_task_id
                }).encode() + b"\n"
            # 更新任务状态
            task_manager.update_task(
                convert_task_id,
                status=TaskStatus.COMPLETED,
                data={
                    "pdf_filename": pdf_filename,
                    "image_subdir": f"{stem}/",
                    "images": saved_files,
                    "total_pages": total_pages
                }
            )
            # 主任务写入完成状态
            parent_task = task_manager.get_task(task_id)
            parent_data = parent_task.get("data", {})
            parent_data["pdf_to_images"] = {
                "status": "completed",
                "progress": 100,
                "total_pages": total_pages,
                "images": saved_files
            }
            task_manager.update_task(task_id, data=parent_data)
            yield json.dumps({
                "task_id": convert_task_id,
                "status": "completed",
                "message": "转换完成",
                "total_images": len(saved_files)
            }).encode() + b"\n"
        except Exception as e:
            task_manager.update_task_status(convert_task_id, TaskStatus.FAILED, str(e))
            # 主任务写入失败状态
            parent_task = task_manager.get_task(task_id)
            parent_data = parent_task.get("data", {})
            parent_data["pdf_to_images"] = {
                "status": "failed",
                "progress": 0,
                "error": str(e)
            }
            task_manager.update_task(task_id, data=parent_data)
            yield json.dumps({
                "error": f"转换失败: {str(e)}",
                "status": "failed"
            }).encode() + b"\n"
    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson"
    )

@router.websocket("/ws/convert/{task_id}")
async def websocket_convert_pdf(websocket: WebSocket, task_id: str):
    """WebSocket 端点，用于实时传输转换进度和图片路径"""
    await websocket.accept()
    try:
        task = task_manager.get_task(task_id)
        if not task:
            await websocket.send_json({"error": "任务不存在"})
            return
        if task["type"] != "pdf_upload":
            await websocket.send_json({"error": "无效的任务类型，需要先上传 PDF"})
            return
        if task["status"] != TaskStatus.COMPLETED:
            await websocket.send_json({"error": "PDF 上传任务未完成"})
            return
        pdf_filename = task["data"]["original_filename"]
        pdf_path = PDF_DIR / pdf_filename
        # 创建转换任务
        convert_task_id = task_manager.create_task(
            task_type="pdf_to_images",
            initial_data={
                "pdf_filename": pdf_filename,
                "status": "converting",
                "parent_task_id": task_id
            }
        )
        try:
            doc = fitz.open(pdf_path)
            stem = pdf_path.stem
            # 创建对应子目录
            output_subdir = IMG_DIR / stem
            output_subdir.mkdir(parents=True, exist_ok=True)
            saved_files = []
            total_pages = len(doc)
            for i, page in enumerate(doc, start=1):
                # 更新进度
                progress = int((i / total_pages) * 100)
                task_manager.update_task_progress(convert_task_id, progress)
                pix = page.get_pixmap(dpi=200)
                img_path = output_subdir / f"{stem}_p{i}.png"
                pix.save(str(img_path))
                saved_files.append(f"{stem}/{img_path.name}")
                # 主任务写入进度
                parent_task = task_manager.get_task(task_id)
                parent_data = parent_task.get("data", {})
                parent_data["pdf_to_images"] = {
                    "status": "processing",
                    "progress": progress,
                    "current_page": i,
                    "total_pages": total_pages,
                    "images": saved_files.copy()
                }
                task_manager.update_task(task_id, data=parent_data)
                # 通过 WebSocket 发送进度和图片路径
                await websocket.send_json({
                    "task_id": convert_task_id,
                    "progress": progress,
                    "current_page": i,
                    "total_pages": total_pages,
                    "image_path": f"{stem}/{img_path.name}"
                })
                await asyncio.sleep(0.1)
            # 更新任务状态
            task_manager.update_task(
                convert_task_id,
                status=TaskStatus.COMPLETED,
                data={
                    "pdf_filename": pdf_filename,
                    "image_subdir": f"{stem}/",
                    "images": saved_files,
                    "total_pages": total_pages
                }
            )
            # 主任务写入完成状态
            parent_task = task_manager.get_task(task_id)
            parent_data = parent_task.get("data", {})
            parent_data["pdf_to_images"] = {
                "status": "completed",
                "progress": 100,
                "total_pages": total_pages,
                "images": saved_files
            }
            task_manager.update_task(task_id, data=parent_data)
            await websocket.send_json({
                "task_id": convert_task_id,
                "status": "completed",
                "message": "转换完成",
                "total_images": len(saved_files)
            })
        except Exception as e:
            task_manager.update_task_status(convert_task_id, TaskStatus.FAILED, str(e))
            # 主任务写入失败状态
            parent_task = task_manager.get_task(task_id)
            parent_data = parent_task.get("data", {})
            parent_data["pdf_to_images"] = {
                "status": "failed",
                "progress": 0,
                "error": str(e)
            }
            task_manager.update_task(task_id, data=parent_data)
            await websocket.send_json({
                "error": f"转换失败: {str(e)}",
                "status": "failed"
            })
    except WebSocketDisconnect:
        print("WebSocket 连接断开")
    except Exception as e:
        await websocket.send_json({"error": str(e)})
    finally:
        await websocket.close()

@router.post("/convert-ppt-to-pdf")
async def convert_ppt_to_pdf(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename.endswith(".pptx"):
        raise HTTPException(status_code=400, detail="只支持 PPTX 文件")

    # 创建新任务
    task_id = task_manager.create_task(
        task_type="ppt_to_pdf",
        initial_data={
            "original_filename": file.filename,
            "status": "uploading"
        }
    )

    try:
        # 保存文件
        save_path = Path(UPLOAD_DIR) / file.filename
        with open(save_path, "wb") as f:
            f.write(await file.read())

        # 转换为 PDF
        pdf_path = save_path.with_suffix(".pdf")
        pptx_to_pdf(str(save_path), str(pdf_path))

        # 删除 PPT 文件
        os.remove(save_path)

        # 更新任务状态
        task_manager.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            data={
                "original_filename": file.filename,
                "saved_path": str(save_path),
                "pdf_path": str(pdf_path),
                "file_size": os.path.getsize(save_path)
            }
        )

        return {
            "message": "转换成功",
            "filename": file.filename,
            "pdf_path": str(pdf_path),
            "task_id": task_id
        }
    except Exception as e:
        task_manager.update_task_status(task_id, TaskStatus.FAILED, str(e))
        raise HTTPException(status_code=500, detail=f"转换失败: {str(e)}")