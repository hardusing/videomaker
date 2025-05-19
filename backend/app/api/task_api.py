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