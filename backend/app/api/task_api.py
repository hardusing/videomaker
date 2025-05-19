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