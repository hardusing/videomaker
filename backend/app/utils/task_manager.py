import redis
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

# 连接 Redis（如有需要可调整 host/port/db）
try:
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    # 测试连接
    r.ping()
    logger.info("Redis连接成功")
except redis.ConnectionError as e:
    logger.error(f"Redis连接失败: {str(e)}")
    raise

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
        try:
            r.set(f"task:{task_id}", json.dumps(task_data))
            logger.info(f"创建任务成功: {task_id}, 类型: {task_type}")
            return task_id
        except Exception as e:
            logger.error(f"创建任务失败: {str(e)}")
            raise

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        try:
            logger.info(f"尝试获取任务: {task_id}")
            data = r.get(f"task:{task_id}")
            if data:
                logger.info(f"获取任务成功: {task_id}")
                logger.debug(f"任务数据: {data}")
                return json.loads(data)
            else:
                logger.warning(f"任务不存在: {task_id}")
                # 打印所有存在的任务键
                all_keys = r.keys("task:*")
                logger.info(f"当前Redis中存在的所有任务键: {all_keys}")
                return None
        except json.JSONDecodeError as e:
            logger.error(f"任务数据格式错误: {task_id}, {str(e)}")
            return None
        except Exception as e:
            logger.error(f"获取任务失败: {task_id}, {str(e)}")
            return None

    def update_task(self, task_id: str, **kwargs) -> bool:
        task = self.get_task(task_id)
        if not task:
            logger.warning(f"更新任务失败: 任务不存在 {task_id}")
            return False
        try:
            task.update(kwargs)
            task["updated_at"] = datetime.now().isoformat()
            r.set(f"task:{task_id}", json.dumps(task))
            logger.info(f"更新任务成功: {task_id}")
            logger.debug(f"更新后的任务数据: {task}")
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
            keys = r.keys("task:*")
            logger.info(f"找到的任务键: {keys}")
            result = {}
            for key in keys:
                data = r.get(key)
                if data:
                    try:
                        task = json.loads(data)
                        if (not task_type) or (task["type"] == task_type):
                            result[task["id"]] = task
                            logger.debug(f"添加任务到结果: {task['id']}, 类型: {task['type']}")
                    except json.JSONDecodeError as e:
                        logger.error(f"任务数据格式错误: {key}, {str(e)}")
                        logger.debug(f"错误的数据内容: {data}")
                        continue
            logger.info(f"列出任务成功: 共{len(result)}个任务")
            logger.debug(f"任务列表: {result}")
            return result
        except Exception as e:
            logger.error(f"列出任务失败: {str(e)}")
            return {}

    def get_task_id_by_filename(self, filename: str) -> str:
        """根据文件名获取对应的 task_id"""
        try:
            logger.info(f"开始根据文件名查找任务: {filename}")
            keys = r.keys("task:*")
            logger.info(f"找到的任务键: {keys}")
            for key in keys:
                data = r.get(key)
                if data:
                    try:
                        task = json.loads(data)
                        logger.debug(f"检查任务: {task['id']}, 类型: {task['type']}")
                        if task["type"] == "pdf_upload" and task["data"].get("original_filename") == filename:
                            logger.info(f"找到匹配的任务: {task['id']}")
                            return task["id"]
                    except json.JSONDecodeError as e:
                        logger.error(f"任务数据格式错误: {key}, {str(e)}")
                        logger.debug(f"错误的数据内容: {data}")
                        continue
            logger.warning(f"未找到匹配的任务: {filename}")
            return None
        except Exception as e:
            logger.error(f"根据文件名获取任务ID失败: {str(e)}")
            return None

# 创建全局任务管理器实例
task_manager = TaskManager() 