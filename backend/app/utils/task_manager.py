import redis
import json
from typing import Dict, Any, Optional
import uuid
from datetime import datetime

class TaskStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# 连接 Redis（如有需要可调整 host/port/db）
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

class TaskManager:
    def create_task(self, task_type: str, initial_data: Dict[str, Any] = None) -> str:
        task_id = str(uuid.uuid4())
        task_data = {
            "id": task_id,
            "type": task_type,
            "status": TaskStatus.PENDING,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "data": initial_data or {},
            "progress": 0,
            "error": None
        }
        r.set(f"task:{task_id}", json.dumps(task_data))
        return task_id

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        data = r.get(f"task:{task_id}")
        return json.loads(data) if data else None

    def update_task(self, task_id: str, **kwargs) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False
        task.update(kwargs)
        task["updated_at"] = datetime.now().isoformat()
        r.set(f"task:{task_id}", json.dumps(task))
        return True

    def update_task_status(self, task_id: str, status: str, error: str = None) -> bool:
        return self.update_task(task_id, status=status, error=error)

    def update_task_progress(self, task_id: str, progress: int) -> bool:
        return self.update_task(task_id, progress=progress)

    def list_tasks(self, task_type: str = None) -> Dict[str, Dict[str, Any]]:
        keys = r.keys("task:*")
        result = {}
        for key in keys:
            data = r.get(key)
            if data:
                task = json.loads(data)
                if (not task_type) or (task["type"] == task_type):
                    result[task["id"]] = task
        return result

# 创建全局任务管理器实例
task_manager = TaskManager() 