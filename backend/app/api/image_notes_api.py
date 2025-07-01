from fastapi import APIRouter, HTTPException, Form, Query, Depends, BackgroundTasks, Body
from fastapi.responses import JSONResponse, FileResponse
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from pathlib import Path
from PIL import Image
import pytesseract
import openai
import tempfile
import shutil
import os
from typing import List
from ..utils.task_manager import task_manager

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
IMG_DIR = BASE_DIR / "converted_images"
PROCESSED_IMG_DIR = BASE_DIR / "processed_images"

# OpenAI 密钥（可以换成环境变量读取）
openai.api_key = "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"

@router.post("/api/image-notes/generate-all")
async def generate_notes_for_all_images(
    prompt: str = Form("请将下列文字整理为简洁通顺的日文文稿"),
    task_id: str = Form(None, description="任务ID，可选")
):
    """
    遍历 converted_images 下所有图片，生成对应 txt 文件并保存在同目录，并可选写入任务进度
    """
    if not IMG_DIR.exists():
        raise HTTPException(status_code=404, detail="converted_images 目录不存在")

    image_files = list(IMG_DIR.glob("*.png")) + list(IMG_DIR.glob("*.jpg")) + list(IMG_DIR.glob("*.jpeg"))

    if not image_files:
        raise HTTPException(status_code=404, detail="未找到任何图片")

    result = []
    total = len(image_files)
    for idx, img_path in enumerate(image_files, 1):
        try:
            # OCR识别
            ocr_text = pytesseract.image_to_string(Image.open(img_path), lang='chi_sim+eng')
            
            # 使用 prompt + OCR内容 调用 AI
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": ocr_text}
                ]
            )
            generated_text = response.choices[0].message.content.strip()

            # 保存 txt 到同目录
            txt_path = img_path.with_suffix(".txt")
            txt_path.write_text(generated_text, encoding="utf-8")

            result.append({"image": img_path.name, "txt": txt_path.name, "status": "success"})
            status = "success"
            error = None
        except Exception as e:
            result.append({"image": img_path.name, "status": "failed", "error": str(e)})
            status = "failed"
            error = str(e)
        # 实时写入任务进度
        if task_id:
            task = task_manager.get_task(task_id)
            if task:
                task_data = task.get("data", {})
                task_data["notes_generate"] = {
                    "status": "processing" if idx < total else ("completed" if error is None else "failed"),
                    "progress": int(idx / total * 100),
                    "current": idx,
                    "total": total,
                    "current_image": img_path.name,
                    "results": result.copy(),
                    "error": error
                }
                task_manager.update_task(task_id, data=task_data)
    # 处理完成后写入最终状态
    if task_id:
        task = task_manager.get_task(task_id)
        if task:
            task_data = task.get("data", {})
            task_data["notes_generate"] = {
                "status": "completed" if all(r.get("status") == "success" for r in result) else "failed",
                "progress": 100,
                "total": total,
                "results": result
            }
            task_manager.update_task(task_id, data=task_data)
    return JSONResponse(content={"results": result})

@router.delete("/api/image-notes/image")
async def delete_images_by_task(
    task_id: str = Query(..., description="任务ID"),
    image_ids: List[str] = Body(..., embed=True, description="要删除的图片ID列表"),
    black_bordered: bool = Query(False, description="是否删除加黑边图片（默认为原图）")
):
    """
    根据task_id和image_id列表批量删除图片。
    支持删除converted_images或processed_images下的图片。
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task["type"] == "pdf_upload":
        pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
    elif task["type"] == "pdf_to_images":
        pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
    elif task["type"] == "ppt_upload":
        # PPT任务，使用转换后的PDF文件名
        pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
    elif task["type"] == "ppt_pdf_to_images":
        # PPT转图片任务
        pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
    else:
        raise HTTPException(status_code=400, detail="不支持的任务类型，仅支持 PDF 和 PPT 任务")
    base_dir = PROCESSED_IMG_DIR if black_bordered else IMG_DIR
    target_dir = base_dir / pdf_name
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail="图片目录不存在")
    deleted = []
    not_found = []
    for image_id in image_ids:
        img_path = target_dir / f"{image_id}.png"
        if img_path.exists():
            img_path.unlink()
            deleted.append(f"{pdf_name}/{image_id}.png")
        else:
            not_found.append(f"{pdf_name}/{image_id}.png")
    return {
        "deleted": deleted,
        "not_found": not_found,
        "message": f"成功删除 {len(deleted)} 张，未找到 {len(not_found)} 张"
    }

@router.get("/api/image-notes/download")
async def download_image_zip(
    task_id: str = Query(None, description="任务ID，推荐优先使用"),
    pdf_name: str = Query(None, description="PDF 文件名（不含扩展名，兼容老参数）"),
    background_tasks: BackgroundTasks = None
):
    """
    下载指定任务的converted_images目录下所有图片为zip。
    支持task_id或pdf_name。
    下载后临时zip会被后台任务清理。
    """
    if task_id:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        # 支持 pdf_upload/pdf_to_images/ppt_upload/ppt_pdf_to_images 四种类型
        if task["type"] == "pdf_upload":
            pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_upload":
            # PPT任务，使用转换后的PDF文件名
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_pdf_to_images":
            # PPT转图片任务
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        else:
            raise HTTPException(status_code=400, detail="不支持的任务类型，仅支持 PDF 和 PPT 任务")
    if not pdf_name:
        raise HTTPException(status_code=400, detail="请提供task_id或pdf_name")
    subdir = IMG_DIR / pdf_name
    if not subdir.exists() or not subdir.is_dir():
        raise HTTPException(status_code=404, detail="对应的 PDF 图片目录不存在")
    try:
        # 创建临时目录并压缩
        tmp_dir = tempfile.mkdtemp()
        zip_path = Path(tmp_dir) / f"{pdf_name}.zip"
        shutil.make_archive(str(zip_path.with_suffix("")), 'zip', root_dir=subdir)
        # 下载完毕后自动删除 zip 文件和临时目录
        background_tasks.add_task(shutil.rmtree, tmp_dir)
        return FileResponse(
            path=zip_path,
            filename=f"{pdf_name}.zip",
            media_type="application/zip"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"打包失败: {e}")

def add_black_borders(image_path: Path, output_path: Path, top=100, bottom=100):
    """为图片添加上下黑边"""
    img = Image.open(image_path)
    width, height = img.size
    new_height = height + top + bottom
    new_img = Image.new("RGB", (width, new_height), (0, 0, 0))
    new_img.paste(img, (0, top))
    new_img.save(output_path)

def process_directory(src_dir: Path, processed: list):
    """处理单个目录下的所有图片"""
    dst_dir = PROCESSED_IMG_DIR / src_dir.name
    for src_path in src_dir.rglob("*.png"):
        rel_path = src_path.relative_to(src_dir)
        dst_path = dst_dir / rel_path
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        add_black_borders(src_path, dst_path)
        processed.append(f"{src_dir.name}/{str(rel_path)}")

@router.get("/api/image-notes/add-black-border")
async def add_black_border_for_pdf_images(
    task_id: str = Query(None, description="任务ID，推荐优先使用"),
    pdf_name: str = Query(None, description="PDF 文件名，不含扩展名（兼容老参数）")
):
    """
    为图片添加上下黑边
    支持通过 task_id 或 pdf_name 指定目录
    支持 PDF 和 PPT 任务
    """
    processed = []
    target_dir = None
    if task_id:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        # 支持 pdf_upload/pdf_to_images/ppt_upload/ppt_pdf_to_images 四种类型
        if task["type"] == "pdf_upload":
            pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_upload":
            # PPT任务，使用转换后的PDF文件名
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_pdf_to_images":
            # PPT转图片任务
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        else:
            raise HTTPException(status_code=400, detail="不支持的任务类型，仅支持 PDF 和 PPT 任务")
        target_dir = IMG_DIR / pdf_name
    elif pdf_name:
        target_dir = IMG_DIR / pdf_name
    else:
        # 处理所有目录
        for subdir in IMG_DIR.iterdir():
            if subdir.is_dir():
                process_directory(subdir, processed)
        return {
            "message": f"图片已加黑边，共处理 {len(processed)} 张",
            "processed_images": processed
        }
    if not target_dir or not target_dir.exists():
        raise HTTPException(status_code=404, detail="源图片目录不存在")
    process_directory(target_dir, processed)
    return {
        "message": f"图片已加黑边，共处理 {len(processed)} 张",
        "processed_images": processed
    }

@router.get("/api/image-notes/images")
async def list_images(
    task_id: str = Query(None, description="任务ID，推荐优先使用"),
    pdf_name: str = Query(None, description="PDF 文件名（不含扩展名），兼容老参数")
):
    """
    获取 converted_images 目录下所有图片文件名；支持 task_id 或 pdf_name
    """
    image_list: List[str] = []
    target_dir = None
    if task_id:
        task = task_manager.get_task(task_id)
        if not task:
            return {"images": [], "message": "任务不存在"}
        if task["type"] == "pdf_upload":
            pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_upload":
            # PPT任务，使用转换后的PDF文件名
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_pdf_to_images":
            # PPT转图片任务
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        else:
            return {"images": [], "message": "不支持的任务类型，仅支持 PDF 和 PPT 任务"}
        target_dir = IMG_DIR / pdf_name
    elif pdf_name:
        target_dir = IMG_DIR / pdf_name
    if target_dir:
        if target_dir.exists() and target_dir.is_dir():
            image_list = [f"{target_dir.name}/{f.name}" for f in target_dir.glob("*.png")]
        else:
            return {"images": [], "message": f"未找到目录: {pdf_name}"}
    else:
        # 列出所有子目录中的图片
        for subdir in IMG_DIR.iterdir():
            if subdir.is_dir():
                for f in subdir.glob("*.png"):
                    image_list.append(f"{subdir.name}/{f.name}")
    return {"images": image_list}

@router.get("/api/image-notes/black-bordered-images")
async def list_black_bordered_images(
    task_id: str = Query(None, description="任务ID，推荐优先使用"),
    pdf_name: str = Query(None, description="PDF 文件名（不含扩展名），兼容老参数")
):
    """
    获取 processed_images 目录下所有加黑边图片文件名；支持 task_id 或 pdf_name
    """
    image_list: List[str] = []
    target_dir = None
    if task_id:
        task = task_manager.get_task(task_id)
        if not task:
            return {"images": [], "message": "任务不存在"}
        if task["type"] == "pdf_upload":
            pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_upload":
            # PPT任务，使用转换后的PDF文件名
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_pdf_to_images":
            # PPT转图片任务
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        else:
            return {"images": [], "message": "不支持的任务类型，仅支持 PDF 和 PPT 任务"}
        target_dir = PROCESSED_IMG_DIR / pdf_name
    elif pdf_name:
        target_dir = PROCESSED_IMG_DIR / pdf_name
    if target_dir:
        if target_dir.exists() and target_dir.is_dir():
            image_list = [f"{target_dir.name}/{f.name}" for f in target_dir.glob("*.png")]
        else:
            return {"images": [], "message": f"未找到目录: {pdf_name}"}
    else:
        # 列出所有子目录中的图片
        for subdir in PROCESSED_IMG_DIR.iterdir():
            if subdir.is_dir():
                for f in subdir.glob("*.png"):
                    image_list.append(f"{subdir.name}/{f.name}")
    return {"images": image_list}