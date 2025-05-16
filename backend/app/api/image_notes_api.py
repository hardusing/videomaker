from fastapi import APIRouter, HTTPException, Form, Query, Depends, BackgroundTasks
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

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
IMG_DIR = BASE_DIR / "converted_images"
PROCESSED_IMG_DIR = BASE_DIR / "processed_images"

# OpenAI 密钥（可以换成环境变量读取）
openai.api_key = "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"

@router.post("/api/image-notes/generate-all")
async def generate_notes_for_all_images(
    prompt: str = Form("请将下列文字整理为简洁通顺的日文文稿")
):
    """
    遍历 converted_images 下所有图片，生成对应 txt 文件并保存在同目录
    """
    if not IMG_DIR.exists():
        raise HTTPException(status_code=404, detail="converted_images 目录不存在")

    image_files = list(IMG_DIR.glob("*.png")) + list(IMG_DIR.glob("*.jpg")) + list(IMG_DIR.glob("*.jpeg"))

    if not image_files:
        raise HTTPException(status_code=404, detail="未找到任何图片")

    result = []

    for img_path in image_files:
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
        
        except Exception as e:
            result.append({"image": img_path.name, "status": "failed", "error": str(e)})

    return JSONResponse(content={"results": result})

@router.delete("/api/image-notes/image/{filename:path}")  
async def delete_single_image(filename: str):
    """
    删除指定图片文件（支持子目录）
    """
    # 支持传入 lesson01/lesson01_p1.png
    file_path = (IMG_DIR / filename).resolve()

    # 防止路径穿越攻击（必须限制在 IMG_DIR 内部）
    if not str(file_path).startswith(str(IMG_DIR.resolve())):
        raise HTTPException(status_code=400, detail="非法路径")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    if not file_path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
        raise HTTPException(status_code=400, detail="仅支持删除图片文件")

    try:
        file_path.unlink()
        return {"message": f"{filename} 删除成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败：{str(e)}")
    
@router.get("/api/image-notes/download")
async def download_image_zip(
    pdf_name: str = Query(..., description="PDF 文件名（不含扩展名）"),
    background_tasks: BackgroundTasks = None
):
    """
    将指定子目录下的所有图片打包成 zip 并提供下载。
    下载后临时 zip 会被后台任务清理。
    """
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

@router.get("/api/image-notes/add-black-border")
async def add_black_border_for_pdf_images(pdf_name: str = Query(None, description="PDF 文件名，不含扩展名")):
    """
    为图片添加上下黑边
    如果提供 pdf_name，则只处理该目录下的图片
    否则处理 converted_images 下所有目录的图片
    """
    processed = []
    
    if pdf_name:
        # 处理指定目录
        src_dir = IMG_DIR / pdf_name
        if not src_dir.exists():
            raise HTTPException(status_code=404, detail="源图片目录不存在")
        process_directory(src_dir, processed)
    else:
        # 处理所有目录
        for subdir in IMG_DIR.iterdir():
            if subdir.is_dir():
                process_directory(subdir, processed)

    return {
        "message": f"图片已加黑边，共处理 {len(processed)} 张",
        "processed_images": processed
    }

def process_directory(src_dir: Path, processed: list):
    """处理单个目录下的所有图片"""
    dst_dir = PROCESSED_IMG_DIR / src_dir.name
    # 递归处理所有子目录
    for src_path in src_dir.rglob("*.png"):
        # 计算相对路径
        rel_path = src_path.relative_to(src_dir)
        # 创建对应的目标路径
        dst_path = dst_dir / rel_path
        # 确保目标目录存在
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 处理图片
        add_black_borders(src_path, dst_path)
        processed.append(f"{src_dir.name}/{str(rel_path)}")

@router.get("/api/image-notes/images")
async def list_images(pdf_name: str = Query(None, description="PDF 文件名（不含扩展名）")):
    """
    获取 converted_images 目录下所有图片文件名；
    如果提供 pdf_name，则只获取该子目录下的图片
    """
    image_list: List[str] = []

    if pdf_name:
        # 仅列出指定子目录下的图片
        subdir = IMG_DIR / pdf_name
        if subdir.exists() and subdir.is_dir():
            image_list = [f"{pdf_name}/{f.name}" for f in subdir.glob("*.png")]
        else:
            return {"images": [], "message": f"未找到目录: {pdf_name}"}
    else:
        # 列出所有子目录中的图片
        for subdir in IMG_DIR.iterdir():
            if subdir.is_dir():
                for f in subdir.glob("*.png"):
                    image_list.append(f"{subdir.name}/{f.name}")

    return {"images": image_list}