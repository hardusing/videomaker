from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
from typing import List
import zipfile
import uuid
from fastapi import BackgroundTasks
import tempfile
from app.utils.task_manager_memory import task_manager
import shutil

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SRT_WAV_DIR = BASE_DIR / "srt_and_wav"
IMG_DIR = BASE_DIR / "converted_images"
PROCESSED_IMG_DIR = BASE_DIR / "processed_images"
ZIP_DIR = BASE_DIR / "temp_zip"
ZIP_DIR.mkdir(parents=True, exist_ok=True)

@router.get("/api/download/all")
async def download_all_srt_and_wav(
    task_id: str = Query(None, description="任务ID"),
    file: str = Query(None, description="文件名/目录名"),
    dir_name: str = Query(None, description="目录名"),
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
    elif dir_name:
        pdf_name = dir_name
    else:
        raise HTTPException(status_code=400, detail="请提供task_id、file或dir_name参数")
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
    file: str = Query(None, description="文件名/目录名"),
    dir_name: str = Query(None, description="目录名")
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
    elif dir_name:
        pdf_name = dir_name
    else:
        raise HTTPException(status_code=400, detail="请提供task_id、file或dir_name参数")
    task_dir = SRT_WAV_DIR / pdf_name
    if not task_dir.exists() or not task_dir.is_dir():
        raise HTTPException(status_code=404, detail="目录不存在")
    file_list = [f.name for f in task_dir.iterdir() if f.is_file()]
    return file_list

@router.delete("/api/files/clear")
async def delete_all_files(
    task_id: str = Query(None, description="任务ID"),
    file: str = Query(None, description="文件名/目录名"),
    dir_name: str = Query(None, description="目录名")
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
    elif dir_name:
        pdf_name = dir_name
    else:
        raise HTTPException(status_code=400, detail="请提供task_id、file或dir_name参数")
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
    file: str = Query(None, description="文件名/目录名"),
    dir_name: str = Query(None, description="目录名")
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
    elif dir_name:
        pdf_name = dir_name
    else:
        raise HTTPException(status_code=400, detail="请提供task_id、file或dir_name参数")
    target_file = SRT_WAV_DIR / pdf_name / filename
    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    try:
        target_file.unlink()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
    return {"deleted": filename}

@router.get("/api/download/folder-images")
async def download_folder_images(
    folder_name: str = Query(..., description="converted_images目录下的文件夹名"),
    include_black_bordered: bool = Query(False, description="是否包含黑边图片"),
    background_tasks: BackgroundTasks = None
):
    """
    下载指定文件夹下的所有图片API
    
    参数:
    - folder_name: converted_images目录下的文件夹名
    - include_black_bordered: 是否包含黑边图片，默认False
    - background_tasks: 后台任务（用于清理临时文件）
    
    返回:
    - ZIP文件下载
    """
    # 确定图片目录
    img_dir = IMG_DIR / folder_name
    processed_img_dir = PROCESSED_IMG_DIR / folder_name
    
    # 检查目录是否存在
    if not img_dir.exists() or not img_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"图片目录不存在: {folder_name}")
    
    # 收集图片文件
    files_to_zip = []
    
    # 添加原始图片
    for img_file in img_dir.glob("*.png"):
        files_to_zip.append((img_file, f"original/{img_file.name}"))
    
    # 如果需要包含黑边图片且目录存在
    if include_black_bordered and processed_img_dir.exists():
        for img_file in processed_img_dir.glob("*.png"):
            files_to_zip.append((img_file, f"black_bordered/{img_file.name}"))
    
    if not files_to_zip:
        raise HTTPException(status_code=404, detail="没有找到可下载的图片文件")
    
    # 创建临时ZIP文件
    tmp_dir = tempfile.mkdtemp()
    zip_filename = f"{folder_name}_images.zip"
    zip_path = Path(tmp_dir) / zip_filename
    
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path, arcname in files_to_zip:
                if file_path.exists():
                    zipf.write(file_path, arcname=arcname)
        
        # 设置后台任务清理临时文件
        def cleanup_temp_files():
            try:
                shutil.rmtree(tmp_dir)
            except Exception as e:
                print(f"[WARN] 清理临时文件失败：{tmp_dir}，原因：{e}")
        
        background_tasks.add_task(cleanup_temp_files)
        
        return FileResponse(
            path=zip_path,
            filename=zip_filename,
            media_type="application/zip",
            background=background_tasks
        )
        
    except Exception as e:
        # 清理临时文件
        try:
            shutil.rmtree(tmp_dir)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"创建ZIP文件失败: {str(e)}")