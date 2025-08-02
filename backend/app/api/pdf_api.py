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
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/pdf", tags=["PDF 操作"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "pdf_uploads"
PDF_DIR = BASE_DIR / "pdf_uploads"
IMG_DIR = BASE_DIR / "converted_images"

IMG_DIR.mkdir(parents=True, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 请求和响应模型
class PPTConvertResponse(BaseModel):
    message: str = Field(..., description="处理结果消息")
    task_id: str = Field(..., description="任务ID，用于后续步骤")
    original_filename: str = Field(..., description="原始PPT文件名")
    pdf_filename: str = Field(..., description="转换后的PDF文件名")
    ppt_size: int = Field(..., description="PPT文件大小(字节)")
    pdf_size: int = Field(..., description="PDF文件大小(字节)")
    
    class Config:
        schema_extra = {
            "example": {
                "message": "PPT上传并转换为PDF成功",
                "task_id": "12345678-1234-5678-1234-567812345678",
                "original_filename": "presentation.pptx",
                "pdf_filename": "presentation.pdf",
                "ppt_size": 1024000,
                "pdf_size": 512000
            }
        }

def ppt_to_pdf(ppt_path, pdf_path):
    """将PPT或PPTX文件转换为PDF"""
    try:
        powerpoint = comtypes.client.CreateObject("Powerpoint.Application")
        powerpoint.Visible = 1

        # 使用绝对路径
        ppt_path = abspath(ppt_path)
        pdf_path = abspath(pdf_path)

        deck = powerpoint.Presentations.Open(ppt_path)
        deck.SaveAs(pdf_path, FileFormat=32)  # 32 for PDF format
        deck.Close()
        powerpoint.Quit()
    except Exception as e:
        # 确保PowerPoint进程被关闭
        try:
            powerpoint.Quit()
        except:
            pass
        raise e

# 保持向后兼容
def pptx_to_pdf(pptx_path, pdf_path):
    """向后兼容的函数名"""
    return ppt_to_pdf(pptx_path, pdf_path)

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

@router.post(
    "/convert/{task_id}",
    tags=["视频制作工作流程"],
    summary="步骤2: 将PDF转换为图片",
    description="""
    将步骤1生成的PDF转换为图片序列。
    
    输入:
    - task_id: 从步骤1获得的任务ID
    
    处理流程:
    1. 加载PDF文件
    2. 将每页PDF转换为高质量PNG图像
    3. 保存到以PDF文件名为名的子目录中
    
    返回:
    - 图片转换进度和结果的流式响应
    - 每个转换后的图片路径和缩略图预览
    - 总页数和处理进度
    """,
    response_description="返回流式JSON响应，包含图片路径和转换进度"
)
async def convert_pdf_to_images(task_id: str):
    """使用 PyMuPDF 将 PDF 每页转为 PNG，并保存到以 PDF 文件名为名的子目录中，返回图片ID和缩略图"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 支持PDF上传任务和PPT上传任务
    if task["type"] not in ["pdf_upload", "ppt_upload"]:
        raise HTTPException(status_code=400, detail="无效的任务类型，需要先上传 PDF 或 PPT")
    if task["status"] != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="上传任务未完成")

    # 根据任务类型获取PDF文件路径
    if task["type"] == "pdf_upload":
        pdf_filename = task["data"]["original_filename"]
        pdf_path = PDF_DIR / pdf_filename
    elif task["type"] == "ppt_upload":
        # PPT任务，使用转换后的PDF文件
        task_data = task.get("data", {})
        if not task_data.get("conversion_completed", False):
            raise HTTPException(status_code=400, detail="PPT转PDF未完成")
        pdf_filename = task_data.get("pdf_filename", "")
        pdf_path = Path(task_data.get("pdf_path", ""))
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="PDF文件不存在")

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
            # === 新增：生成前清空旧图片 ===
            if output_subdir.exists():
                for f in output_subdir.glob("*"):
                    try:
                        f.unlink()
                    except Exception:
                        pass
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
        if task["type"] not in ["pdf_upload", "ppt_upload"]:
            await websocket.send_json({"error": "无效的任务类型，需要先上传 PDF 或 PPT"})
            return
        if task["status"] != TaskStatus.COMPLETED:
            await websocket.send_json({"error": "上传任务未完成"})
            return
        
        # 根据任务类型获取PDF文件路径
        if task["type"] == "pdf_upload":
            pdf_filename = task["data"]["original_filename"]
            pdf_path = PDF_DIR / pdf_filename
        elif task["type"] == "ppt_upload":
            # PPT任务，使用转换后的PDF文件
            task_data = task.get("data", {})
            if not task_data.get("conversion_completed", False):
                await websocket.send_json({"error": "PPT转PDF未完成"})
                return
            pdf_filename = task_data.get("pdf_filename", "")
            pdf_path = Path(task_data.get("pdf_path", ""))
            if not pdf_path.exists():
                await websocket.send_json({"error": "PDF文件不存在"})
                return
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

@router.post(
    "/upload-ppt-convert-pdf",
    tags=["视频制作工作流程"],
    summary="步骤1: 上传PPT并转换为PDF",
    description="""
    上传PPT文件并转换为PDF格式。
    
    输入:
    - file: 上传的PPT或PPTX文件
    
    处理流程:
    1. 上传PPT文件到服务器
    2. 使用PowerPoint COM对象将PPT转换为PDF
    3. 保存转换后的PDF文件
    
    返回:
    - task_id: 用于后续步骤的任务ID
    - pdf_filename: 转换后的PDF文件名
    - original_filename: 原始PPT文件名
    - ppt_size: PPT文件大小(字节)
    - pdf_size: PDF文件大小(字节)
    """,
    response_model=PPTConvertResponse
)
async def upload_ppt_convert_pdf(file: UploadFile = File(...)) -> Dict[str, Any]:
    """上传PPT文件并转换为PDF"""
    # 支持多种PPT格式
    if not (file.filename.endswith(".pptx") or file.filename.endswith(".ppt")):
        raise HTTPException(status_code=400, detail="只支持 PPT 和 PPTX 文件")

    # 创建新任务
    task_id = task_manager.create_task(
        task_type="ppt_upload",
        initial_data={
            "original_filename": file.filename,
            "status": "uploading"
        }
    )

    try:
        # 保存PPT文件
        ppt_save_path = Path(UPLOAD_DIR) / file.filename
        with open(ppt_save_path, "wb") as f:
            f.write(await file.read())

        # 更新任务状态为转换中
        task_manager.update_task(
            task_id,
            status=TaskStatus.PROCESSING,
            data={
                "original_filename": file.filename,
                "ppt_path": str(ppt_save_path),
                "status": "converting"
            }
        )

        # 转换为 PDF
        pdf_filename = file.filename.rsplit('.', 1)[0] + '.pdf'
        pdf_path = Path(UPLOAD_DIR) / pdf_filename
        
        try:
            ppt_to_pdf(str(ppt_save_path), str(pdf_path))
        except Exception as convert_error:
            # 转换失败，但保留PPT文件
            task_manager.update_task(
                task_id,
                status=TaskStatus.FAILED,
                data={
                    "original_filename": file.filename,
                    "ppt_path": str(ppt_save_path),
                    "error": f"PPT转换失败: {str(convert_error)}",
                    "file_size": os.path.getsize(ppt_save_path)
                }
            )
            raise HTTPException(status_code=500, detail=f"PPT转换失败: {str(convert_error)}")

        # 转换成功，保留PPT文件用于备份
        pdf_size = os.path.getsize(pdf_path) if pdf_path.exists() else 0
        ppt_size = os.path.getsize(ppt_save_path)

        # 更新任务状态为完成
        task_manager.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            data={
                "original_filename": file.filename,
                "ppt_path": str(ppt_save_path),
                "pdf_filename": pdf_filename,
                "pdf_path": str(pdf_path),
                "ppt_size": ppt_size,
                "pdf_size": pdf_size,
                "conversion_completed": True
            }
        )

        return {
            "message": "PPT上传并转换为PDF成功",
            "task_id": task_id,
            "original_filename": file.filename,
            "pdf_filename": pdf_filename,
            "ppt_size": ppt_size,
            "pdf_size": pdf_size
        }
    except Exception as e:
        task_manager.update_task_status(task_id, TaskStatus.FAILED, str(e))
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")

@router.get("/ppt-uploads/list")
async def list_ppt_uploads():
    """获取所有PPT上传任务列表"""
    tasks = task_manager.get_tasks_by_type("ppt_upload")
    result = []
    for task_id, task in tasks.items():
        task_data = task.get("data", {})
        result.append({
            "task_id": task_id,
            "original_filename": task_data.get("original_filename", ""),
            "pdf_filename": task_data.get("pdf_filename", ""),
            "status": task.get("status", ""),
            "ppt_size": task_data.get("ppt_size", 0),
            "pdf_size": task_data.get("pdf_size", 0),
            "conversion_completed": task_data.get("conversion_completed", False),
            "created_at": task.get("created_at", ""),
            "error": task_data.get("error", "")
        })
    return result

@router.delete("/ppt-uploads/delete/{task_id}")
async def delete_ppt_upload(task_id: str):
    """删除PPT上传任务及相关文件"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task["type"] != "ppt_upload":
        raise HTTPException(status_code=400, detail="不是PPT上传任务")
    
    task_data = task.get("data", {})
    files_deleted = []
    
    try:
        # 删除PPT文件
        if "ppt_path" in task_data:
            ppt_path = Path(task_data["ppt_path"])
            if ppt_path.exists():
                ppt_path.unlink()
                files_deleted.append(str(ppt_path))
        
        # 删除PDF文件
        if "pdf_path" in task_data:
            pdf_path = Path(task_data["pdf_path"])
            if pdf_path.exists():
                pdf_path.unlink()
                files_deleted.append(str(pdf_path))
        
        # 删除任务记录
        task_manager.delete_task(task_id)
        
        return {
            "message": "PPT上传任务及文件删除成功",
            "task_id": task_id,
            "deleted_files": files_deleted
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

@router.post("/convert-ppt-to-images/{task_id}")
async def convert_ppt_to_images(task_id: str):
    """将PPT任务中的PDF转换为图片"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task["type"] != "ppt_upload":
        raise HTTPException(status_code=400, detail="无效的任务类型，需要先上传PPT")
    if task["status"] != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="PPT上传任务未完成")
    
    task_data = task.get("data", {})
    if not task_data.get("conversion_completed", False):
        raise HTTPException(status_code=400, detail="PPT转PDF未完成")
    
    pdf_path = Path(task_data.get("pdf_path", ""))
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF文件不存在")

    # 创建转换任务
    convert_task_id = task_manager.create_task(
        task_type="ppt_pdf_to_images",
        initial_data={
            "pdf_filename": task_data.get("pdf_filename", ""),
            "original_ppt_filename": task_data.get("original_filename", ""),
            "status": "converting",
            "parent_task_id": task_id
        }
    )

    async def generate():
        try:
            doc = fitz.open(pdf_path)
            stem = pdf_path.stem
            output_subdir = IMG_DIR / stem
            # 清空旧图片
            if output_subdir.exists():
                for f in output_subdir.glob("*"):
                    try:
                        f.unlink()
                    except Exception:
                        pass
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
                parent_data["ppt_to_images"] = {
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
                    "pdf_filename": task_data.get("pdf_filename", ""),
                    "original_ppt_filename": task_data.get("original_filename", ""),
                    "image_subdir": f"{stem}/",
                    "images": saved_files,
                    "total_pages": total_pages
                }
            )
            
            # 主任务写入完成状态
            parent_task = task_manager.get_task(task_id)
            parent_data = parent_task.get("data", {})
            parent_data["ppt_to_images"] = {
                "status": "completed",
                "progress": 100,
                "total_pages": total_pages,
                "images": saved_files
            }
            task_manager.update_task(task_id, data=parent_data)
            
            yield json.dumps({
                "task_id": convert_task_id,
                "status": "completed",
                "message": "PPT图片转换完成",
                "total_images": len(saved_files)
            }).encode() + b"\n"
            
        except Exception as e:
            task_manager.update_task_status(convert_task_id, TaskStatus.FAILED, str(e))
            # 主任务写入失败状态
            parent_task = task_manager.get_task(task_id)
            parent_data = parent_task.get("data", {})
            parent_data["ppt_to_images"] = {
                "status": "failed",
                "progress": 0,
                "error": str(e)
            }
            task_manager.update_task(task_id, data=parent_data)
            yield json.dumps({
                "error": f"PPT图片转换失败: {str(e)}",
                "status": "failed"
            }).encode() + b"\n"
    
    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson"
    )