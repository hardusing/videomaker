from fastapi import APIRouter, HTTPException, Body, Query, Form
from pathlib import Path
import openai
import os
from dotenv import load_dotenv
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
NOTES_DIR = BASE_DIR / "notes_output"

def save_txt_to_notes_dir(filename: str, content: str):
    """保存文本内容到 notes_output 目录"""
    file_path = NOTES_DIR / filename
    file_path.write_text(content, encoding="utf-8")

@router.get("/api/notes/all")
async def list_all_txt_files(
    task_id: str = Query(None, description="任务ID，可选"),
    filename: str = Query(None, description="目录名/文件名，可选")
):
    """
    返回指定任务或目录下的所有 .txt 文件的相对路径列表
    """
    target_dir = NOTES_DIR
    subdir = None
    if task_id:
        from app.utils.task_manager import task_manager
        task = task_manager.get_task(task_id)
        if not task:
            return {"files": []}
        if task["type"] == "pdf_upload":
            subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            subdir = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_upload":
            subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
    elif filename:
        subdir = filename
    if subdir:
        target_dir = target_dir / subdir
        if not target_dir.exists() or not target_dir.is_dir():
            return {"files": []}
        txt_files = [str(file.relative_to(NOTES_DIR)) for file in target_dir.rglob("*.txt")]
    else:
        txt_files = [str(file.relative_to(NOTES_DIR)) for file in NOTES_DIR.rglob("*.txt")]
    return {"files": txt_files}

@router.get("/api/notes/{filename}")
async def get_txt_file_content(
    filename: str = Query(..., description="文件名（不含目录）"),
    task_id: str = Query(None, description="任务ID，可选"),
    dir_name: str = Query(None, description="目录名，可选")
):
    """
    获取指定目录下的 .txt 文件内容，必须传task_id或dir_name
    """
    from app.utils.task_manager import task_manager
    subdir = None
    if task_id:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task["type"] == "pdf_upload":
            subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            subdir = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_upload":
            subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
    elif dir_name:
        subdir = dir_name
    else:
        raise HTTPException(status_code=400, detail="必须提供task_id或dir_name")
    file_path = NOTES_DIR / subdir / filename
    if not filename.endswith(".txt"):
        file_path = file_path.with_suffix(".txt")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    content = file_path.read_text(encoding="utf-8")
    return {"filename": str(file_path.relative_to(NOTES_DIR)), "content": content}

@router.post("/api/notes/rewrite")
async def rewrite_txt_file(
    filename: str = Form(..., description="目标 .txt 文件名"),
    task_id: str = Form(None, description="任务ID，可选"),
    dir_name: str = Form(None, description="目录名，可选"),
    prompt: str = Form("请将下列文字整理为简洁通顺的日文文稿", description="OpenAI 使用的提示词")
):
    """
    获取指定目录下的txt文件内容，去除 breaktime 行，调用 OpenAI 生成清洗版本，保存为 _cleaned.txt 文件并返回
    """
    from app.utils.task_manager import task_manager
    subdir = None
    if task_id:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task["type"] == "pdf_upload":
            subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            subdir = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_upload":
            subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
    elif dir_name:
        subdir = dir_name
    else:
        raise HTTPException(status_code=400, detail="必须提供task_id或dir_name")
    file_path = NOTES_DIR / subdir / filename
    if not filename.endswith(".txt"):
        file_path = file_path.with_suffix(".txt")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    try:
        original_text = file_path.read_text(encoding="utf-8")
        cleaned_input = "\n".join([
            line.strip() for line in original_text.splitlines()
            if line.strip() and "break" not in line.lower()
        ])
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": cleaned_input}
            ]
        )
        new_content = response.choices[0].message.content.strip()
        new_filename = file_path.with_name(file_path.stem + "_cleaned.txt")
        new_filename.write_text(new_content, encoding="utf-8")
        return {
            "original_file": str(file_path.relative_to(NOTES_DIR)),
            "new_file": str(new_filename.relative_to(NOTES_DIR)),
            "content": new_content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {e}")

@router.delete("/api/notes/{filename}")
async def delete_txt_file(
    filename: str = Query(..., description="文件名（不含目录）"),
    task_id: str = Query(None, description="任务ID，可选"),
    dir_name: str = Query(None, description="目录名，可选")
):
    """
    删除指定目录下的 .txt 文稿，必须传task_id或dir_name
    """
    from app.utils.task_manager import task_manager
    subdir = None
    if task_id:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task["type"] == "pdf_upload":
            subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            subdir = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_upload":
            subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
    elif dir_name:
        subdir = dir_name
    else:
        raise HTTPException(status_code=400, detail="必须提供task_id或dir_name")
    file_path = NOTES_DIR / subdir / filename
    if not filename.endswith(".txt"):
        file_path = file_path.with_suffix(".txt")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    try:
        file_path.unlink()
        return {"message": f"{file_path.relative_to(NOTES_DIR)} 删除成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败：{str(e)}")

@router.get("/api/notes/search")
async def search_txt_files(
    keyword: str = Query(..., description="用英文逗号分隔多个关键词"),
    task_id: str = Query(None, description="任务ID，可选"),
    dir_name: str = Query(None, description="目录名，可选")
):
    """
    在指定目录下所有 .txt 文件中搜索关键词，必须传task_id或dir_name
    """
    from app.utils.task_manager import task_manager
    subdir = None
    if task_id:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task["type"] == "pdf_upload":
            subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            subdir = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_upload":
            subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
    elif dir_name:
        subdir = dir_name
    else:
        raise HTTPException(status_code=400, detail="必须提供task_id或dir_name")
    target_dir = NOTES_DIR / subdir
    if not target_dir.exists() or not target_dir.is_dir():
        return {"count": 0, "results": []}
    if not keyword.strip():
        raise HTTPException(status_code=400, detail="关键词不能为空")
    keywords = [kw.strip() for kw in keyword.split(",") if kw.strip()]
    if not keywords:
        raise HTTPException(status_code=400, detail="没有有效关键词")
    matches = []
    for txt_file in target_dir.glob("*.txt"):
        try:
            content = txt_file.read_text(encoding="utf-8")
            first_hit_index = -1
            for kw in keywords:
                index = content.find(kw)
                if index != -1 and (first_hit_index == -1 or index < first_hit_index):
                    first_hit_index = index
            if first_hit_index == -1:
                continue
            snippet_start = max(0, first_hit_index - 20)
            snippet_end = min(len(content), first_hit_index + 100)
            snippet = content[snippet_start:snippet_end].replace("\n", " ")
            for kw in keywords:
                snippet = snippet.replace(kw, f"<mark>{kw}</mark>")
            matches.append({
                "file": str(txt_file.relative_to(NOTES_DIR)),
                "snippet": snippet
            })
        except Exception as e:
            matches.append({
                "file": str(txt_file.relative_to(NOTES_DIR)),
                "error": f"读取失败: {str(e)}"
            })
    return {"count": len(matches), "results": matches}

