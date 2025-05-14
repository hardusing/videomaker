from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import JSONResponse
from pathlib import Path
from PIL import Image
import pytesseract
import openai

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
IMG_DIR = BASE_DIR / "converted_images"

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

@router.get("/api/image-notes/images")
async def list_all_images():
    """
    获取 converted_images 目录下所有图片文件名
    """
    image_files = list(IMG_DIR.glob("*.png")) + list(IMG_DIR.glob("*.jpg")) + list(IMG_DIR.glob("*.jpeg"))
    image_list = [f.name for f in image_files]
    return {"images": image_list}

@router.delete("/api/image-notes/image/{filename}")
async def delete_single_image(filename: str):
    """
    删除指定图片文件（仅限于 converted_images 目录）
    """
    if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
        raise HTTPException(status_code=400, detail="仅支持删除图片文件")

    file_path = IMG_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        file_path.unlink()
        return {"message": f"{filename} 删除成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败：{str(e)}")