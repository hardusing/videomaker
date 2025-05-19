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
    获取任务全流程进度
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    # 只返回data里的各阶段进度
    progress = {
        "pdf_upload": {"status": task.get("status"), "progress": 100 if task.get("status") == "completed" else 0},
    }
    data = task.get("data", {})
    # 合并各阶段
    for key in [
        "pdf_to_images", "add_black_border", "notes_generate", "tts", "video_upload", "video_transcode"
    ]:
        if key in data:
            progress[key] = data[key]
    # 视频文件列表
    if "videos" in data:
        progress["videos"] = data["videos"]
    return progress

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