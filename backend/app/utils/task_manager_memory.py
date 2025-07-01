import json
from typing import Dict, Any, Optional
import uuid
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TaskStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskManagerMemory:
    def __init__(self):
        self.tasks = {}  # 内存存储
        logger.info("使用内存版TaskManager初始化成功")

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
        try:
            self.tasks[task_id] = task_data
            logger.info(f"创建任务成功: {task_id}, 类型: {task_type}")
            return task_id
        except Exception as e:
            logger.error(f"创建任务失败: {str(e)}")
            raise

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        try:
            logger.info(f"尝试获取任务: {task_id}")
            if task_id in self.tasks:
                logger.info(f"获取任务成功: {task_id}")
                return self.tasks[task_id]
            else:
                logger.warning(f"任务不存在: {task_id}")
                logger.info(f"当前存在的所有任务ID: {list(self.tasks.keys())}")
                return None
        except Exception as e:
            logger.error(f"获取任务失败: {task_id}, {str(e)}")
            return None

    def update_task(self, task_id: str, **kwargs) -> bool:
        if task_id not in self.tasks:
            logger.warning(f"更新任务失败: 任务不存在 {task_id}")
            return False
        try:
            self.tasks[task_id].update(kwargs)
            self.tasks[task_id]["updated_at"] = datetime.now().isoformat()
            logger.info(f"更新任务成功: {task_id}")
            return True
        except Exception as e:
            logger.error(f"更新任务失败: {task_id}, {str(e)}")
            return False

    def update_task_status(self, task_id: str, status: str, error: str = None) -> bool:
        return self.update_task(task_id, status=status, error=error)

    def update_task_progress(self, task_id: str, progress: int) -> bool:
        return self.update_task(task_id, progress=progress)

    def list_tasks(self, task_type: str = None) -> Dict[str, Dict[str, Any]]:
        try:
            logger.info(f"开始列出任务, 类型过滤: {task_type}")
            result = {}
            for task_id, task in self.tasks.items():
                if (not task_type) or (task["type"] == task_type):
                    result[task_id] = task
                    logger.debug(f"添加任务到结果: {task_id}, 类型: {task['type']}")
            logger.info(f"列出任务成功: 共{len(result)}个任务")
            return result
        except Exception as e:
            logger.error(f"列出任务失败: {str(e)}")
            return {}

    def get_task_id_by_filename(self, filename: str) -> str:
        """根据文件名获取对应的 task_id"""
        try:
            logger.info(f"开始根据文件名查找任务: {filename}")
            for task_id, task in self.tasks.items():
                logger.debug(f"检查任务: {task_id}, 类型: {task['type']}")
                if task["type"] == "pdf_upload" and task["data"].get("original_filename") == filename:
                    logger.info(f"找到匹配的任务: {task_id}")
                    return task_id
            logger.warning(f"未找到匹配的任务: {filename}")
            return None
        except Exception as e:
            logger.error(f"根据文件名获取任务ID失败: {str(e)}")
            return None

    def get_tasks_by_type(self, task_type: str) -> Dict[str, Dict[str, Any]]:
        """根据任务类型获取所有任务"""
        try:
            logger.info(f"开始获取任务类型为 {task_type} 的任务")
            result = {}
            for task_id, task in self.tasks.items():
                if task["type"] == task_type:
                    result[task_id] = task
                    logger.debug(f"找到匹配任务: {task_id}")
            logger.info(f"获取任务成功: 共{len(result)}个任务")
            return result
        except Exception as e:
            logger.error(f"获取任务失败: {str(e)}")
            return {}

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        try:
            logger.info(f"开始删除任务: {task_id}")
            if task_id in self.tasks:
                del self.tasks[task_id]
                logger.info(f"删除任务成功: {task_id}")
                return True
            else:
                logger.warning(f"任务不存在，无法删除: {task_id}")
                return False
        except Exception as e:
            logger.error(f"删除任务失败: {task_id}, {str(e)}")
            return False

# 创建全局任务管理器实例
task_manager = TaskManagerMemory() 