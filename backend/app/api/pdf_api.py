# app/api/pdf_api.py

from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import os
import fitz  # 来自 PyMuPDF
from pdf2image import convert_from_path
from typing import List

router = APIRouter(prefix="/api/pdf", tags=["PDF 操作"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
PDF_DIR = BASE_DIR / "pdf_uploads"
IMG_DIR = BASE_DIR / "converted_images"

IMG_DIR.mkdir(parents=True, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="只支持 PDF 文件")

    # 保存文件
    save_path = Path(UPLOAD_DIR) / file.filename
    with open(save_path, "wb") as f:
        f.write(await file.read())

    return {"message": "上传成功", "filename": file.filename}

@router.get("/upload/list", response_model=List[str])
async def list_uploaded_files():
    """
    获取上传目录下所有 PDF 文件名
    """
    if not UPLOAD_DIR.exists():
        raise HTTPException(status_code=404, detail="上传目录不存在")
    files = [f.name for f in UPLOAD_DIR.glob("*.pdf")]
    return files

@router.delete("/upload/delete/{filename}")
async def delete_uploaded_file(filename: str):
    """
    删除上传目录下指定的 PDF 文件
    """
    file_path = UPLOAD_DIR / filename
    if not file_path.exists() or not file_path.suffix == ".pdf":
        raise HTTPException(status_code=404, detail="指定的 PDF 文件不存在")
    try:
        file_path.unlink()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
    return {"message": f"{filename} 已删除"}

@router.post("/convert/{pdf_filename}")
async def convert_pdf_to_images(pdf_filename: str):
    """
    使用 PyMuPDF 将 PDF 每页转为 PNG，无需 Poppler
    """
    if not pdf_filename.endswith(".pdf"):
        pdf_filename += ".pdf"

    pdf_path = PDF_DIR / pdf_filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF 文件不存在")

    try:
        doc = fitz.open(pdf_path)
        stem = pdf_path.stem
        saved_files = []

        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=200)  # 可调 dpi 清晰度
            img_path = IMG_DIR / f"{stem}_p{i}.png"
            pix.save(str(img_path))
            saved_files.append(img_path.name)

        return {
            "message": f"{pdf_filename} 转换成功，共 {len(saved_files)} 页",
            "images": saved_files
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"转换失败: {e}")