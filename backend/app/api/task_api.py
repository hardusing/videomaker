from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from ..utils.task_manager import task_manager

router = APIRouter(prefix="/api/tasks", tags=["任务管理"])

@router.get("/{task_id}")
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """获取任务状态"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task

@router.get("/")
async def list_tasks(task_type: str = None) -> Dict[str, Dict[str, Any]]:
    """列出所有任务"""
    return task_manager.list_tasks(task_type)

@router.get("/{task_id}/progress")
def get_task_progress(task_id: str):
    """
    获取任务全流程详细进度
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    data = task.get("data", {})
    # 收集所有阶段（data下所有key）
    progress = {}
    for key, value in data.items():
        progress[key] = value
    # 主任务状态
    progress["pdf_upload"] = {"status": task.get("status"), "progress": 100 if task.get("status") == "completed" else 0}
    # 自动补全常见阶段
    default_keys = [
        "pdf_to_images", "add_black_border", "notes_generate", "tts_generate", "tts_generate_selected", "video_upload", "video_transcode"
    ]
    for key in default_keys:
        if key not in progress:
            progress[key] = {"status": "pending", "progress": 0}
    # 视频文件列表
    if "videos" in data:
        progress["videos"] = data["videos"]
    # 汇总主任务元信息
    result = {
        "task_id": task.get("id"),
        "type": task.get("type"),
        "status": task.get("status"),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "error": task.get("error"),
        "progress": progress
    }
    return result

@router.delete("/{task_id}")
def delete_task_and_files(task_id: str):
    """
    删除任务及其相关的所有文件（PDF、图片、音频、视频等），并从Redis中移除任务。
    """
    import shutil, os
    from pathlib import Path
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    data = task.get("data", {})
    # 1. 删除PDF文件
    pdf_name = None
    if task["type"] == "pdf_upload":
        pdf_name = data.get("original_filename", "").rsplit(".", 1)[0]
        pdf_path = Path("pdf_uploads") / data.get("original_filename", "")
        if pdf_path.exists():
            try:
                pdf_path.unlink()
            except Exception:
                pass
    elif task["type"] == "pdf_to_images":
        pdf_name = data.get("pdf_filename", "").rsplit(".", 1)[0]
    elif task["type"] == "ppt_upload":
        pdf_name = data.get("original_filename", "").rsplit(".", 1)[0]
    # 2. 删除图片目录
    if pdf_name:
        for d in ["converted_images", "processed_images"]:
            img_dir = Path(d) / pdf_name
            if img_dir.exists():
                shutil.rmtree(img_dir, ignore_errors=True)
    # 3. 删除音频/字幕目录
    if pdf_name:
        audio_dir = Path("srt_and_wav") / pdf_name
        if audio_dir.exists():
            shutil.rmtree(audio_dir, ignore_errors=True)
    # 4. 删除视频目录
    if pdf_name:
        for d in ["videos", "encoded_videos"]:
            v_dir = Path(d) / pdf_name
            if v_dir.exists():
                shutil.rmtree(v_dir, ignore_errors=True)
    # 5. 删除 notes_output 目录下的文稿
    if pdf_name:
        notes_dir = Path("notes_output") / pdf_name
        if notes_dir.exists():
            shutil.rmtree(notes_dir, ignore_errors=True)
    # 6. 从Redis中删除任务
    import redis
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    r.delete(f"task:{task_id}")
    return {"message": f"任务 {task_id} 及相关文件已删除"}

@router.get("/files/all")
async def get_all_tasks_files() -> Dict[str, Dict[str, Any]]:
    """
    获取所有任务的文件信息
    返回格式: {
        "task_id1": {
            "pdf_file": "文件名.pdf",
            "ppt_file": "文件名.pptx",
            "image_files": [...],
            "audio_files": [...],
            "video_files": [...],
            "notes_file": "文件名.txt"
        },
        "task_id2": {...}
    }
    """
    all_tasks = task_manager.list_tasks()
    result = {}
    
    for task_id, task in all_tasks.items():
        data = task.get("data", {})
        files_info = {
            "pdf_file": None,
            "ppt_file": None,
            "image_files": [],
            "audio_files": [],
            "video_files": [],
            "notes_file": None
        }
        
        # 获取PDF文件名
        if task["type"] in ["pdf_upload", "pdf_to_images"]:
            files_info["pdf_file"] = data.get("original_filename") or data.get("pdf_filename")
        
        # 获取PPT文件名
        if task["type"] == "ppt_upload":
            files_info["ppt_file"] = data.get("original_filename")
        
        # 获取图片文件列表
        if "converted_images" in data:
            files_info["image_files"] = data["converted_images"]
        
        # 获取音频文件列表
        if "audio_files" in data:
            files_info["audio_files"] = data["audio_files"]
        
        # 获取视频文件列表
        if "videos" in data:
            files_info["video_files"] = data["videos"]
        
        # 获取文稿文件
        if "notes_file" in data:
            files_info["notes_file"] = data["notes_file"]
        
        result[task_id] = files_info
    
    return result

@router.get("/{task_id}/files")
async def get_task_files(task_id: str) -> Dict[str, Any]:
    """
    获取任务相关的所有文件名信息
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    data = task.get("data", {})
    files_info = {
        "pdf_file": None,
        "ppt_file": None,
        "image_files": [],
        "audio_files": [],
        "video_files": [],
        "notes_file": None
    }
    
    # 获取PDF文件名
    if task["type"] in ["pdf_upload", "pdf_to_images"]:
        files_info["pdf_file"] = data.get("original_filename") or data.get("pdf_filename")
    
    # 获取PPT文件名
    if task["type"] == "ppt_upload":
        files_info["ppt_file"] = data.get("original_filename")
    
    # 获取图片文件列表
    if "converted_images" in data:
        files_info["image_files"] = data["converted_images"]
    
    # 获取音频文件列表
    if "audio_files" in data:
        files_info["audio_files"] = data["audio_files"]
    
    # 获取视频文件列表
    if "videos" in data:
        files_info["video_files"] = data["videos"]
    
    # 获取文稿文件
    if "notes_file" in data:
        files_info["notes_file"] = data["notes_file"]
    
    return files_info

# ================== 各阶段API中写入进度的举例 ==================

# 1. PDF转图片结束时：
# task_data = task.get("data", {})
# task_data["pdf_to_images"] = {"status": "completed", "progress": 100}
# task_manager.update_task(task_id, data=task_data)

# 2. 加黑边结束时：
# task_data = task.get("data", {})
# task_data["add_black_border"] = {"status": "completed", "progress": 100}
# task_manager.update_task(task_id, data=task_data)

# 3. 文稿生成结束时：
# task_data = task.get("data", {})
# task_data["notes_generate"] = {"status": "completed", "progress": 100}
# task_manager.update_task(task_id, data=task_data)

# 4. TTS生成时可实时写入：
# task_data = task.get("data", {})
# task_data["tts"] = {"status": "processing", "progress": 当前百分比}
# task_manager.update_task(task_id, data=task_data)

# 5. 视频上传后：
# task_data = task.get("data", {})
# task_data["video_upload"] = {"status": "completed", "progress": 100}
# task_manager.update_task(task_id, data=task_data)

# 6. 视频转码时可实时写入：
# task_data = task.get("data", {})
# task_data["video_transcode"] = {"status": "processing", "progress": 当前百分比}
# task_manager.update_task(task_id, data=task_data) 