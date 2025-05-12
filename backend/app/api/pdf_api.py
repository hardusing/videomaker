# app/api/pdf_api.py

from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import os
# from pdf2image import convert_from_path

router = APIRouter(prefix="/api/pdf", tags=["PDF 操作"])

UPLOAD_DIR = "pdf_uploads"
IMAGE_DIR = "converted_images"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="只支持 PDF 文件")

    # 保存文件
    save_path = Path(UPLOAD_DIR) / file.filename
    with open(save_path, "wb") as f:
        f.write(await file.read())

    return {"message": "上传成功", "filename": file.filename}


# @router.post("/convert")
# def convert_pdf(filename: str):
#     pdf_path = Path(UPLOAD_DIR) / filename
#     if not pdf_path.exists():
#         raise HTTPException(status_code=404, detail="PDF 文件不存在")

#     # 转换 PDF 每页为图片
#     images = convert_from_path(str(pdf_path), dpi=200)
#     output_files = []

#     for i, img in enumerate(images):
#         image_filename = f"{pdf_path.stem}_page{i+1}.png"
#         image_path = Path(IMAGE_DIR) / image_filename
#         img.save(image_path, "PNG")
#         output_files.append(str(image_path))

#     return {
#         "message": "转换成功",
#         "images": output_files
#     }
