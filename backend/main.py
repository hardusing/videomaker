import os
import uuid
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field
from typing import List, Optional
# from fastapi_limiter import FastAPILimiter
# import redis.asyncio as redis
import redis
import logging
import sys

from app.utils.ppt_parser import extract_notes
from app.utils.task_manager_memory import task_manager, TaskStatus

# ===================== 配置与数据结构 =====================
from dotenv import load_dotenv
# ✅ 1. 最先加载 .env 和日志配置
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# ✅ 2. 定义路径并创建目录
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "notes_output"
AUDIO_OUTPUT_DIR = "srt_and_wav"

for d in [UPLOAD_DIR, OUTPUT_DIR, AUDIO_OUTPUT_DIR]:
    os.makedirs(d, exist_ok=True)

# ✅ 3. 导入 API 模块
from app.api import pdf_api, tts_api, download_api, notes_api, image_notes_api, video_api, task_api, video_editor_api, workflow_api
from app.utils.task_manager_memory import task_manager  # 确保导入正确


# ✅ 4. 初始化 FastAPI
app = FastAPI(
    title="视频制作 API",
    description="""
    # VideoMaker API文档
    
    ## 🎬 视频制作工作流程
    
    按照以下5个步骤顺序调用API可完成从PPT到视频的完整转换：
    
    1. **上传PPT并转换为PDF** - 将PPT文件转换为PDF格式
    2. **PDF转换为图片** - 将PDF文件转换为图片序列
    3. **为图片添加黑色边框** - 为图片添加黑色边框以便于后续处理
    4. **生成文件夹脚本** - 基于图片内容生成讲解脚本
    5. **生成所有音频** - 将脚本转换为音频文件
    
    完成以上步骤后，可以继续调用视频合成API完成最终视频制作。
    
    每个API调用都会返回一个task_id，用于关联整个工作流程中的各个步骤。
    """,
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ 5. 挂载模块 & 静态文件目录
app.include_router(pdf_api.router)
app.include_router(tts_api.router)
app.include_router(download_api.router)
app.include_router(notes_api.router)
app.include_router(image_notes_api.router)
app.include_router(video_api.router)
app.include_router(task_api.router)
app.include_router(video_editor_api.router)
app.include_router(workflow_api.router)
app.mount("/srt_and_wav", StaticFiles(directory=AUDIO_OUTPUT_DIR), name="audio")
app.mount("/converted_images", StaticFiles(directory="converted_images"), name="converted_images")
app.mount("/processed_images", StaticFiles(directory="processed_images"), name="processed_images")

# ✅ 6. 项目模型初始化 (Redis已被内存版task_manager替代)
# r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
projects = []

class Project(BaseModel):
    id: str
    name: str
    file_path: str
    created_at: datetime

# 自定义OpenAPI文档
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # 定义工作流程标签，并设置为最优先显示
    openapi_schema["tags"] = [
        {
            "name": "视频制作工作流程",
            "description": "PPT转视频完整流程API，按顺序调用可完成从PPT到视频的转换",
            "x-display-order": 1,  # 最高优先级
        },
        {
            "name": "PDF 操作",
            "description": "PDF文件处理相关接口",
            "x-display-order": 2,
        },
        {
            "name": "TTS配置",
            "description": "文本转语音相关接口",
            "x-display-order": 3,
        },
        {
            "name": "笔记操作",
            "description": "笔记和文档处理接口",
            "x-display-order": 4,
        }
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# ✅ 7. API 路由
@app.get("/")
async def root():
    return {"message": "视频制作 API 服务正在运行"}

@app.get("/api/v1/projects")
def list_projects() -> List[Project]:
    return projects

@app.post("/api/v1/projects/upload")
async def upload_pptx(file: UploadFile = File(...)):
    if not file.filename.endswith(".pptx"):
        return {"error": "仅支持上传pptx文件"}
    project_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, project_id + "_" + file.filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    task_id = task_manager.create_task(
        task_type="ppt_upload",
        initial_data={
            "original_filename": file.filename,
            "project_id": project_id,
            "ppt_path": file_path,
            "status": "uploaded"
        }
    )
    # r.set(f"project_task:{project_id}", task_id)  # 不再需要Redis

    project = Project(
        id=project_id,
        name=file.filename,
        file_path=file_path,
        created_at=datetime.now()
    )
    projects.append(project)

    logging.info(f"✅ 上传 PPT: {file.filename} -> task_id: {task_id}")

    return {"message": "上传成功", "id": project_id, "task_id": task_id}

@app.post("/api/v1/projects/{project_id}/extract")
def extract_notes_for_project(project_id: str, task_id: str = None):
    project = next((p for p in projects if p.id == project_id), None)
    if not project:
        return {"error": "项目不存在"}

    if not task_id:
        task_id = next(
            (tid for tid, t in task_manager.list_tasks().items()
             if t["type"] == "ppt_upload" and t["data"].get("project_id") == project_id),
            None
        )
    if not task_id:
        return {"error": "未找到对应的task_id"}

    output_path = os.path.join(OUTPUT_DIR, task_id)
    notes = extract_notes(project.file_path, output_path)

    task_data = task_manager.get_task(task_id).get("data", {})
    task_data["notes_generate"] = {
        "status": "completed",
        "progress": 100,
        "notes_count": len(notes)
    }
    task_manager.update_task(task_id, data=task_data)

    logging.info(f"✅ 提取 notes 成功：{len(notes)} 条")

    return {
        "message": "提取成功",
        "notes": notes,
        "task_id": task_id
    }

# 可选：on_startup
@app.on_event("startup")
async def startup_event():
    logging.info("🚀 服务启动中... Redis、路径初始化完毕")