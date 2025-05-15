from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from typing import List
import zipfile
import uuid
from fastapi import BackgroundTasks

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SRT_WAV_DIR = BASE_DIR / "srt_and_wav"
ZIP_DIR = BASE_DIR / "temp_zip"
ZIP_DIR.mkdir(parents=True, exist_ok=True)

@router.get("/api/download/all")
async def download_all_srt_and_wav(background_tasks: BackgroundTasks):
    """
    打包 srt_and_wav 目录下所有 .wav 和 *_merged.srt 文件，返回 zip 文件，并在下载后自动删除
    """

    zip_id = uuid.uuid4().hex[:8]
    zip_path = ZIP_DIR / f"all_files_{zip_id}.zip"

    # 筛选目标文件
    wav_files = list(SRT_WAV_DIR.glob("*.wav"))
    srt_files = list(SRT_WAV_DIR.glob("*_merged.srt"))
    files_to_zip = wav_files + srt_files

    if not files_to_zip:
        raise HTTPException(status_code=404, detail="没有找到可打包的 .wav 和 *_merged.srt 文件")

    with zipfile.ZipFile(zip_path, "w") as zipf:
        for file in files_to_zip:
            zipf.write(file, arcname=file.name)

    # 自动清理 zip 文件
    def delete_zip(file_path: Path):
        try:
            file_path.unlink()
        except Exception as e:
            print(f"[WARN] 删除ZIP失败：{file_path}，原因：{e}")

    background_tasks.add_task(delete_zip, zip_path)

    return FileResponse(
        path=zip_path,
        filename="srt_and_wav_all.zip",
        media_type="application/zip",
        background=background_tasks
    )

@router.get("/api/files/list", response_model=List[str])
async def list_all_files():
    """
    获取 srt_and_wav 目录下所有文件名（包含 .wav 和 .srt）
    """
    if not SRT_WAV_DIR.exists():
        raise HTTPException(status_code=404, detail="目录不存在")

    file_list = [f.name for f in SRT_WAV_DIR.iterdir() if f.is_file()]
    return file_list

@router.delete("/api/files/clear")
async def delete_all_files():
    """
    删除 srt_and_wav 目录下的所有文件
    """
    deleted = []
    for file in SRT_WAV_DIR.glob("*"):
        if file.is_file():
            try:
                file.unlink()
                deleted.append(file.name)
            except Exception as e:
                print(f"[WARN] 删除失败: {file.name}，原因：{e}")
    return {"deleted": deleted, "count": len(deleted)}

@router.delete("/api/files/delete/{filename}")
async def delete_single_file(filename: str):
    """
    删除 srt_and_wav 目录下指定文件
    """
    target_file = SRT_WAV_DIR / filename
    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    try:
        target_file.unlink()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
    return {"deleted": filename}