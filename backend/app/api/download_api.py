from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
from typing import List
import zipfile
import uuid
from fastapi import BackgroundTasks
import tempfile
from app.utils.task_manager_memory import task_manager

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SRT_WAV_DIR = BASE_DIR / "srt_and_wav"
ZIP_DIR = BASE_DIR / "temp_zip"
ZIP_DIR.mkdir(parents=True, exist_ok=True)

@router.get("/api/download/all")
async def download_all_srt_and_wav(
    task_id: str = Query(None, description="任务ID"),
    file: str = Query(None, description="文件名/目录名"),
    background_tasks: BackgroundTasks = None
):
    pdf_name = None
    if task_id:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task["type"] == "pdf_upload":
            pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_upload":
            pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        else:
            raise HTTPException(status_code=400, detail="不支持的任务类型")
    elif file:
        pdf_name = file
    else:
        raise HTTPException(status_code=400, detail="请提供task_id或file参数")
    task_dir = SRT_WAV_DIR / pdf_name
    if not task_dir.exists() or not task_dir.is_dir():
        raise HTTPException(status_code=404, detail="任务音频目录不存在")
    wav_files = list(task_dir.glob("*.wav"))
    srt_files = list(task_dir.glob("*_merged.srt"))
    files_to_zip = wav_files + srt_files
    if not files_to_zip:
        raise HTTPException(status_code=404, detail="没有找到可打包的 .wav 和 *_merged.srt 文件")
    tmp_dir = tempfile.mkdtemp()
    zip_path = Path(tmp_dir) / f"{pdf_name}_srt_and_wav.zip"
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for file in files_to_zip:
            zipf.write(file, arcname=file.name)
    def delete_zip(file_path: Path):
        try:
            file_path.unlink()
        except Exception as e:
            print(f"[WARN] 删除ZIP失败：{file_path}，原因：{e}")
    background_tasks.add_task(delete_zip, zip_path)
    return FileResponse(
        path=zip_path,
        filename=f"{pdf_name}_srt_and_wav.zip",
        media_type="application/zip",
        background=background_tasks
    )

@router.get("/api/files/list", response_model=List[str])
async def list_all_files(
    task_id: str = Query(None, description="任务ID"),
    file: str = Query(None, description="文件名/目录名")
):
    pdf_name = None
    if task_id:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task["type"] == "pdf_upload":
            pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_upload":
            pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        else:
            raise HTTPException(status_code=400, detail="不支持的任务类型")
    elif file:
        pdf_name = file
    else:
        raise HTTPException(status_code=400, detail="请提供task_id或file参数")
    task_dir = SRT_WAV_DIR / pdf_name
    if not task_dir.exists() or not task_dir.is_dir():
        raise HTTPException(status_code=404, detail="目录不存在")
    file_list = [f.name for f in task_dir.iterdir() if f.is_file()]
    return file_list

@router.delete("/api/files/clear")
async def delete_all_files(
    task_id: str = Query(None, description="任务ID"),
    file: str = Query(None, description="文件名/目录名")
):
    pdf_name = None
    if task_id:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task["type"] == "pdf_upload":
            pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_upload":
            pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        else:
            raise HTTPException(status_code=400, detail="不支持的任务类型")
    elif file:
        pdf_name = file
    else:
        raise HTTPException(status_code=400, detail="请提供task_id或file参数")
    task_dir = SRT_WAV_DIR / pdf_name
    if not task_dir.exists() or not task_dir.is_dir():
        raise HTTPException(status_code=404, detail="目录不存在")
    deleted = []
    for f in task_dir.glob("*"):
        if f.is_file():
            try:
                f.unlink()
                deleted.append(f.name)
            except Exception as e:
                print(f"[WARN] 删除失败: {f.name}，原因：{e}")
    return {"deleted": deleted, "count": len(deleted)}

@router.delete("/api/files/delete/{filename}")
async def delete_single_file(
    filename: str,
    task_id: str = Query(None, description="任务ID"),
    file: str = Query(None, description="文件名/目录名")
):
    pdf_name = None
    if task_id:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task["type"] == "pdf_upload":
            pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_upload":
            pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        else:
            raise HTTPException(status_code=400, detail="不支持的任务类型")
    elif file:
        pdf_name = file
    else:
        raise HTTPException(status_code=400, detail="请提供task_id或file参数")
    target_file = SRT_WAV_DIR / pdf_name / filename
    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    try:
        target_file.unlink()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
    return {"deleted": filename}