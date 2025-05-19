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
async def list_all_txt_files():
    """
    返回 notes_output 目录下所有子目录及其 .txt 文件的相对路径列表
    """
    txt_files = [str(file.relative_to(NOTES_DIR)) for file in NOTES_DIR.rglob("*.txt")]
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

@router.post("/api/notes/rewrite")
async def rewrite_txt_file(
    filename: str = Form(..., description="目标 .txt 文件名"),
    prompt: str = Form("请将下列文字整理为简洁通顺的日文文稿", description="OpenAI 使用的提示词")
):
    """
    获取指定 txt 文件内容，去除 breaktime 行，调用 OpenAI 生成清洗版本
    保存为 _cleaned.txt 文件并返回
    """
    if not filename.endswith(".txt"):
        filename += ".txt"

    file_path = NOTES_DIR 
    # ⛳️ 打印调试信息
    print("🔍 请求的文件名:", filename)
    print("📁 尝试读取路径:", file_path.resolve())
    print("📂 文件是否存在:", file_path.exists())
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        # 原始文本读取
        original_text = file_path.read_text(encoding="utf-8")

        # 清洗：去掉空行和含 break 的行
        cleaned_input = "\n".join([
            line.strip() for line in original_text.splitlines()
            if line.strip() and "break" not in line.lower()
        ])

        # OpenAI 调用
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": cleaned_input}
            ]
        )

        new_content = response.choices[0].message.content.strip()

        # 保存新文件
        new_filename = file_path.stem + "_cleaned.txt"
        save_txt_to_notes_dir(new_filename, new_content)

        return {
            "original_file": filename,
            "new_file": new_filename,
            "content": new_content
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {e}")


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

@router.get("/api/notes/search")
async def search_txt_files(keyword: str = Query(..., description="用英文逗号分隔多个关键词")):
    """
    在 notes_output 目录下所有 .txt 文件中搜索关键词
    返回匹配的文件名和高亮 HTML 内容片段
    """
    if not keyword.strip():
        raise HTTPException(status_code=400, detail="关键词不能为空")

    keywords = [kw.strip() for kw in keyword.split(",") if kw.strip()]
    if not keywords:
        raise HTTPException(status_code=400, detail="没有有效关键词")

    matches = []
    for txt_file in NOTES_DIR.glob("*.txt"):
        try:
            content = txt_file.read_text(encoding="utf-8")

            # 找出第一个出现的关键词用于定位段落
            first_hit_index = -1
            for kw in keywords:
                index = content.find(kw)
                if index != -1 and (first_hit_index == -1 or index < first_hit_index):
                    first_hit_index = index

            if first_hit_index == -1:
                continue  # 没命中关键词

            snippet_start = max(0, first_hit_index - 20)
            snippet_end = min(len(content), first_hit_index + 100)
            snippet = content[snippet_start:snippet_end].replace("\n", " ")

            # 高亮所有关键词（大小写敏感，支持中文）
            for kw in keywords:
                snippet = snippet.replace(kw, f"<mark>{kw}</mark>")

            matches.append({
                "file": txt_file.name,
                "snippet": snippet
            })

        except Exception as e:
            matches.append({
                "file": txt_file.name,
                "error": f"读取失败: {str(e)}"
            })

    return {"count": len(matches), "results": matches}

