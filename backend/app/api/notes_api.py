from fastapi import APIRouter, HTTPException, Body
from pathlib import Path

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
NOTES_DIR = BASE_DIR / "notes_output"

@router.get("/api/notes/all")
async def list_all_txt_files():
    """
    返回 notes_output 目录下所有 .txt 文件的文件名列表
    """
    txt_files = [file.name for file in NOTES_DIR.glob("*.txt")]
    return {"files": txt_files}

@router.get("/api/notes/{filename}")
async def get_txt_file_content(filename: str):
    """
    获取指定 .txt 文件的内容
    """
    if not filename.endswith(".txt"):
        filename += ".txt"

    file_path = NOTES_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    content = file_path.read_text(encoding="utf-8")
    return {"filename": filename, "content": content}

@router.post("/api/notes/save")
async def save_txt_file(data: dict = Body(...)):
    """
    保存修改后的 .txt 内容到原文件
    """
    filename = data.get("filename")
    content = data.get("content")
    if not filename or not content:
        raise HTTPException(status_code=400, detail="缺少 filename 或 content")
    if not filename.endswith(".txt"):
        filename += ".txt"
    file_path = NOTES_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    file_path.write_text(content, encoding="utf-8")
    return {"message": f"{filename} 保存成功"}

@router.delete("/api/notes/{filename}")
async def delete_txt_file(filename: str):
    """
    删除指定的 .txt 文稿
    """
    if not filename.endswith(".txt"):
        filename += ".txt"
    file_path = NOTES_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        file_path.unlink()
        return {"message": f"{filename} 删除成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败：{str(e)}")

