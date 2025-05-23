from fastapi import APIRouter, HTTPException, Body, Query, Form, Path, UploadFile, File
from pathlib import Path
import openai
import os
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from app.utils.base64encoder import encode_image
from app.utils.pdf2imgs import pdf_to_jpg
from app.utils.prompt import read_file_as_text
from typing import List
import asyncio
import time
from app.utils.mysql_config_helper import get_config_value
from openai import OpenAI
import requests


load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

router = APIRouter(prefix="/api/notes", tags=["笔记操作"])
router.include_router(APIRouter(prefix="/api/script", tags=["脚本生成"]))

BASE_DIR = Path(__file__).resolve().parent.parent.parent
NOTES_DIR = BASE_DIR / "notes_output"
PROCESSED_IMAGES_DIR = Path("./processed_images")
PROCESSED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

MAX_BASE64_LENGTH = 3000  # 控制图片base64内容最大长度，防止token超限
OPENAI_RETRY = 3          # OpenAI API最大重试次数
OPENAI_RETRY_INTERVAL = 2 # 重试间隔秒数

def save_txt_to_notes_dir(filename: str, content: str):
    """保存文本内容到 notes_output 目录"""
    file_path = NOTES_DIR / filename
    file_path.write_text(content, encoding="utf-8")

@router.get("/all")
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

@router.get("/{filename}")
async def get_txt_file_content(
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

@router.post("/rewrite")
async def rewrite_txt_file(
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

@router.delete("/{filename}")
async def delete_txt_file(
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

@router.get("/search")
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

async def generate_script_for_image(image_path, notes_subdir, semaphore):
    async with semaphore:
        print(f"[LOG] 开始处理图片: {image_path}")
        encoded_image = encode_image(str(image_path))
        print(f"[LOG] 图片base64编码长度: {len(encoded_image)}")
        if len(encoded_image) > MAX_BASE64_LENGTH:
            print(f"[WARN] 图片base64过长，已截断: {len(encoded_image)} -> {MAX_BASE64_LENGTH}")
            encoded_image = encoded_image[:MAX_BASE64_LENGTH]
        prompt = [
            {"role": "system", "content": "你是一个专业的讲稿生成助手，请根据图片内容生成简洁通顺的中文讲稿。"},
            {"role": "user", "content": f"图片内容的base64编码：{encoded_image}"}
        ]
        for attempt in range(1, OPENAI_RETRY + 1):
            try:
                openai_key = get_config_value('openai_key')
                print(f"[LOG] 使用OpenAI Key: {openai_key[:6]}...{openai_key[-4:]}")
                client = OpenAI(api_key=openai_key)
                print(f"[LOG] 调用OpenAI API（第{attempt}次），图片: {image_path}")
                response = await asyncio.to_thread(
                    client.chat.completions.create,
                    model="gpt-3.5-turbo",
                    messages=prompt
                )
                script_content = response.choices[0].message.content.strip()
                txt_path = notes_subdir / f"{Path(image_path).stem}.txt"
                txt_path.write_text(script_content, encoding="utf-8")
                print(f"[LOG] 文稿生成并保存成功: {txt_path}")
                print(f"[LOG] 文稿内容预览: {script_content[:50]}...")
                return {
                    "image_path": str(image_path),
                    "txt_path": str(txt_path.relative_to(NOTES_DIR)),
                    "content": script_content
                }
            except Exception as e:
                import traceback
                print(f"[ERROR] OpenAI API 调用失败（第{attempt}次），图片: {image_path}，错误: {e}")
                print(traceback.format_exc())
                if attempt < OPENAI_RETRY:
                    print(f"[LOG] {OPENAI_RETRY_INTERVAL}秒后重试...")
                    time.sleep(OPENAI_RETRY_INTERVAL)
                else:
                    print(f"[ERROR] 最终失败，跳过该图片: {image_path}")
                    return {
                        "image_path": str(image_path),
                        "txt_path": None,
                        "content": None,
                        "error": str(e)
                    }

@router.post("/generate-script")
async def generate_script(
    task_id: str = Query(None, description="任务ID，可选"),
    filename: str = Query(None, description="目录名/文件名，可选"),
    files: List[UploadFile] = File(None, description="多个文件，可选")
) -> JSONResponse:
    print(f"[LOG] 接收到请求: task_id={task_id}, filename={filename}, files数量={len(files) if files else 0}")
    if not task_id and not filename and not files:
        print("[ERROR] 参数缺失，必须提供 task_id、filename 或 files")
        raise HTTPException(status_code=400, detail="必须提供 task_id、filename 或 files")

    try:
        scripts = []
        semaphore = asyncio.Semaphore(3)  # 控制最大并发数
        if task_id or filename:
            subdir = None
            if task_id:
                from app.utils.task_manager import task_manager
                task = task_manager.get_task(task_id)
                print(f"[LOG] 通过task_id获取到任务: {task}")
                if not task:
                    print("[ERROR] 任务不存在")
                    raise HTTPException(status_code=404, detail="任务不存在")
                if task["type"] == "pdf_upload":
                    subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
                elif task["type"] == "pdf_to_images":
                    subdir = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
                elif task["type"] == "ppt_upload":
                    subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
            elif filename:
                subdir = filename

            target_dir = PROCESSED_IMAGES_DIR / subdir
            print(f"[LOG] 目标图片目录: {target_dir}")
            if not target_dir.exists() or not target_dir.is_dir():
                print("[ERROR] 目录不存在")
                raise HTTPException(status_code=404, detail="目录不存在")

            notes_subdir = NOTES_DIR / subdir
            notes_subdir.mkdir(parents=True, exist_ok=True)
            print(f"[LOG] notes_output 目录已创建: {notes_subdir}")

            image_paths = []
            for ext in ["*.jpg", "*.jpeg", "*.png"]:
                image_paths.extend(target_dir.glob(ext))
            print(f"[LOG] 待处理图片数量: {len(image_paths)}")
            tasks = [
                generate_script_for_image(image_path, notes_subdir, semaphore)
                for image_path in image_paths
            ]
            scripts = await asyncio.gather(*tasks)
        else:
            for file in files:
                print(f"[LOG] 处理上传文件: {file.filename}")
                if not file.filename.endswith(".pdf"):
                    print(f"[ERROR] 文件类型不支持: {file.filename}")
                    raise HTTPException(status_code=400, detail="只支持 PDF 文件")

                save_path = PROCESSED_IMAGES_DIR / file.filename
                with open(save_path, "wb") as f:
                    f.write(await file.read())
                print(f"[LOG] PDF已保存: {save_path}")

                subdir = Path(file.filename).stem
                notes_subdir = NOTES_DIR / subdir
                notes_subdir.mkdir(parents=True, exist_ok=True)
                print(f"[LOG] notes_output 目录已创建: {notes_subdir}")

                image_paths = pdf_to_jpg(str(save_path), str(PROCESSED_IMAGES_DIR), max_size=768, dpi=300)
                print(f"[LOG] PDF {file.filename} 转换图片数量: {len(image_paths)}")
                tasks = [
                    generate_script_for_image(image_path, notes_subdir, semaphore)
                    for image_path in image_paths
                ]
                scripts += await asyncio.gather(*tasks)

        print(f"[LOG] 全部处理完成，成功生成文稿数: {len([s for s in scripts if s.get('content')])}")
        return JSONResponse(content={"message": "文稿生成成功", "scripts": scripts})
    except Exception as e:
        print(f"[FATAL] 文稿生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"文稿生成失败: {str(e)}")

@router.post("/generate-pages-script")
async def generate_pages_script(
    task_id: str = Query(None, description="任务ID，可选"),
    filename: str = Query(None, description="目录名/文件名，可选"),
    files: List[UploadFile] = File(None, description="多个文件，可选"),
    api_key: str = Form(..., description="API Key，可自定义"),
    prompt: str = Form(None, description="自定义prompt，可选")
):
    print(f"[LOG] 接收到请求: task_id={task_id}, filename={filename}, files数量={len(files) if files else 0}")
    if not task_id and not filename and not files:
        print("[ERROR] 参数缺失，必须提供 task_id、filename 或 files")
        raise HTTPException(status_code=400, detail="必须提供 task_id、filename 或 files")

    scripts = []
    recent_scripts = []
    output_file = None  # 最终稿件txt文件路径
    if task_id or filename:
        subdir = None
        if task_id:
            from app.utils.task_manager import task_manager
            task = task_manager.get_task(task_id)
            print(f"[LOG] 通过task_id获取到任务: {task}")
            if not task:
                print("[ERROR] 任务不存在")
                raise HTTPException(status_code=404, detail="任务不存在")
            if task["type"] == "pdf_upload":
                subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
            elif task["type"] == "pdf_to_images":
                subdir = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
            elif task["type"] == "ppt_upload":
                subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif filename:
            subdir = filename
        target_dir = PROCESSED_IMAGES_DIR / subdir
        print(f"[LOG] 目标图片目录: {target_dir}")
        if not target_dir.exists() or not target_dir.is_dir():
            print("[ERROR] 目录不存在")
            raise HTTPException(status_code=404, detail="目录不存在")
        slides_imgs = []
        for ext in ["*.jpg", "*.jpeg", "*.png"]:
            slides_imgs.extend(target_dir.glob(ext))
        print(f"[LOG] 待处理图片数量: {len(slides_imgs)}")
        base_prompt = prompt or read_file_as_text("课程讲稿生成prompt")
        url = "https://www.dmxapi.com/v1/chat/completions"
        output_dir = Path("./notes_output") / subdir
        output_dir.mkdir(parents=True, exist_ok=True)
        for i, slide in enumerate(slides_imgs, 1):
            print(f"[LOG] 开始处理图片: {slide}")
            time.sleep(5)
            encoded_slide = encode_image(slide)
            print(f"[LOG] 图片base64编码长度: {len(encoded_slide)}")
            previous_scripts = "\n".join(
                [f"Page {i-j}:\n{script}" for j, script in enumerate(reversed(recent_scripts), 1)]
            )
            full_prompt = (
                f"{base_prompt}\n\n[Scripts of Previous pages]\n{previous_scripts}"
                if recent_scripts else base_prompt
            )
            payload = {
                "model": "claude-3-5-sonnet-20241022",
                "messages": [
                    {"role": "system", "content": "You are an experienced lecture for IT skill training, now you are in charge of writing scripts for various IT courses."},
                    {"role": "user", "content": [
                        {"type": "text", "text": full_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_slide}"}},
                    ]},
                ],
                "temperature": 0.4,
                "user": "DMXAPI",
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "DMXAPI/1.0.0 (https://www.dmxapi.com/)",
            }
            try:
                response = requests.post(url, headers=headers, json=payload)
                print(f"[LOG] API响应状态: {response.status_code}")
                if response.status_code == 200:
                    result = response.json()
                    script = result["choices"][0]["message"]["content"]
                else:
                    script = f"API调用失败: {response.status_code} {response.text}"
            except Exception as e:
                print(f"[ERROR] API异常: {e}")
                script = f"API异常: {e}"
            script_with_page = f"Page {i}:\n{script}"
            scripts.append(script_with_page)
            recent_scripts.append(script)
            if len(recent_scripts) > 6:
                recent_scripts.pop(0)
            # 自动保存每页为单独txt
            page_txt = output_dir / f"{i}.txt"
            with open(page_txt, "w", encoding="utf-8") as f:
                f.write(script)
            print(f"[LOG] 单页脚本已保存到: {page_txt}")
        # 自动保存总稿件
        # output_file = output_dir / f"{subdir}_scripts.txt"
        # with open(output_file, "w", encoding="utf-8") as f:
        #     f.write("\n\n".join(scripts))
        # print(f"[LOG] 脚本已保存到: {output_file}")
    else:
        for file in files:
            print(f"[LOG] 处理上传文件: {file.filename}")
            if not file.filename.endswith(".pdf"):
                print(f"[ERROR] 文件类型不支持: {file.filename}")
                raise HTTPException(status_code=400, detail="只支持 PDF 文件")
            save_path = Path("./pdf_uploads") / file.filename
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(await file.read())
            print(f"[LOG] PDF已保存: {save_path}")
            slides_imgs = pdf_to_jpg(str(save_path), "./temp", max_size=768, dpi=300)
            print(f"[LOG] PDF {file.filename} 转换图片数量: {len(slides_imgs)}")
            base_prompt = prompt or read_file_as_text("课程讲稿生成prompt")
            url = "https://www.dmxapi.com/v1/chat/completions"
            output_dir = Path("./notes_output") / Path(file.filename).stem
            output_dir.mkdir(parents=True, exist_ok=True)
            for i, slide in enumerate(slides_imgs, 1):
                print(f"[LOG] 开始处理图片: {slide}")
                time.sleep(5)
                encoded_slide = encode_image(slide)
                print(f"[LOG] 图片base64编码长度: {len(encoded_slide)}")
                previous_scripts = "\n".join(
                    [f"Page {i-j}:\n{script}" for j, script in enumerate(reversed(recent_scripts), 1)]
                )
                full_prompt = (
                    f"{base_prompt}\n\n[Scripts of Previous pages]\n{previous_scripts}"
                    if recent_scripts else base_prompt
                )
                payload = {
                    "model": "claude-3-5-sonnet-20241022",
                    "messages": [
                        {"role": "system", "content": "You are an experienced lecture for IT skill training, now you are in charge of writing scripts for various IT courses."},
                        {"role": "user", "content": [
                            {"type": "text", "text": full_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_slide}"}},
                        ]},
                    ],
                    "temperature": 0.4,
                    "user": "DMXAPI",
                }
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "DMXAPI/1.0.0 (https://www.dmxapi.com/)",
                }
                try:
                    response = requests.post(url, headers=headers, json=payload)
                    print(f"[LOG] API响应状态: {response.status_code}")
                    if response.status_code == 200:
                        result = response.json()
                        script = result["choices"][0]["message"]["content"]
                    else:
                        script = f"API调用失败: {response.status_code} {response.text}"
                except Exception as e:
                    print(f"[ERROR] API异常: {e}")
                    script = f"API异常: {e}"
                script_with_page = f"Page {i}:\n{script}"
                scripts.append(script_with_page)
                recent_scripts.append(script)
                if len(recent_scripts) > 6:
                    recent_scripts.pop(0)
                # 自动保存每页为单独txt
                page_txt = output_dir / f"{i}.txt"
                with open(page_txt, "w", encoding="utf-8") as f:
                    f.write(script)
                print(f"[LOG] 单页脚本已保存到: {page_txt}")
            # 自动保存总稿件
            # output_file = output_dir / f"{Path(file.filename).stem}_scripts.txt"
            # with open(output_file, "w", encoding="utf-8") as f:
            #     f.write("\n\n".join(scripts))
            # print(f"[LOG] 脚本已保存到: {output_file}")
    print(f"[LOG] 全部处理完成，成功生成文稿数: {len(scripts)}")
    return {
        "message": "生成成功",
        "scripts": scripts,
        "txt_file": str(output_file) if output_file else None
    }

@router.post("/split-script")
async def split_script(
    task_id: str = Query(None, description="任务ID，可选"),
    dir_name: str = Query(None, description="目录名，可选")
):
    """
    读取指定目录下的txt文件，根据Page标记拆分成多个txt文件
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

    # 构建目录路径
    target_dir = NOTES_DIR / subdir
    print(f"[LOG] 目标目录: {target_dir}")
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"目录不存在: {target_dir}")

    try:
        # 获取目录下的所有txt文件
        txt_files = list(target_dir.glob("*.txt"))
        print(f"[LOG] 目录下找到 {len(txt_files)} 个txt文件")
        
        if not txt_files:
            raise HTTPException(status_code=404, detail="目录下没有txt文件")
            
        # 使用第一个txt文件
        source_file = txt_files[0]
        print(f"[LOG] 将处理文件: {source_file}")
        
        # 读取源文件内容
        content = source_file.read_text(encoding="utf-8")
        print(f"[LOG] 成功读取文件，内容长度: {len(content)}")
        
        # 按Page标记分割内容
        pages = []
        current_page = []
        for line in content.splitlines():
            if line.strip().startswith("Page "):
                if current_page:
                    pages.append("\n".join(current_page))
                current_page = []
            else:
                current_page.append(line)
        if current_page:
            pages.append("\n".join(current_page))
            
        print(f"[LOG] 分割得到 {len(pages)} 个页面")
        
        if len(pages) <= 1:
            raise HTTPException(status_code=400, detail="文件内容不足以拆分")
        
        # 为每个页面创建单独的文件
        new_files = []
        for i, page_content in enumerate(pages, 1):
            # 创建新文件
            page_file = source_file.parent / f"{i}.txt"
            # 写入内容（不包含Page标记）
            page_file.write_text(page_content.strip(), encoding="utf-8")
            new_files.append(str(page_file.relative_to(NOTES_DIR)))
            print(f"[LOG] 页面 {i} 已保存到: {page_file}")
        
        # 获取目录下的所有txt文件
        all_txt_files = [str(f.relative_to(NOTES_DIR)) for f in target_dir.glob("*.txt")]
        print(f"[LOG] 目录下共有 {len(all_txt_files)} 个txt文件")
        
        return {
            "message": "文件拆分成功",
            "source_file": str(source_file.relative_to(NOTES_DIR)),
            "new_files": new_files,
            "all_files": all_txt_files
        }
        
    except Exception as e:
        print(f"[ERROR] 文件拆分失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文件拆分失败: {str(e)}")

