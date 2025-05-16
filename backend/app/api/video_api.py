from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from typing import List
from pathlib import Path
import shutil
import zipfile
import os

router = APIRouter(prefix="/api/videos", tags=["视频管理"])

VIDEO_DIR = Path("./videos")
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/upload-multiple")
async def upload_multiple_videos(files: List[UploadFile] = File(...)):
    """
    批量上传视频文件
    """
    saved_files = []
    for file in files:
        file_path = VIDEO_DIR / file.filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        saved_files.append(file.filename)
    return {"uploaded": saved_files}


@router.get("/")
async def get_all_videos():
    """
    获取所有视频文件名
    """
    if not VIDEO_DIR.exists():
        return []
    video_files = [f.name for f in VIDEO_DIR.iterdir() if f.is_file()]
    return {"videos": video_files}


@router.get("/download/{filename}")
async def download_video(filename: str):
    """
    下载单个视频文件
    """
    file_path = VIDEO_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="视频文件不存在")
    return FileResponse(path=file_path, filename=filename, media_type="application/octet-stream")


@router.post("/download-zip")
async def download_multiple_videos_as_zip(file_names: List[str]):
    """
    批量下载视频：将选定视频打包成 zip 返回
    """
    zip_path = VIDEO_DIR / "videos_download.zip"
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for name in file_names:
            file_path = VIDEO_DIR / name
            if file_path.exists():
                zipf.write(file_path, arcname=name)
    return FileResponse(path=zip_path, filename="videos_download.zip", media_type="application/zip")
