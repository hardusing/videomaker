import os
import uuid
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
# from fastapi_limiter import FastAPILimiter
# import redis.asyncio as redis

from app.utils.ppt_parser import extract_notes

from app.api import pdf_api
from app.api import tts_api
from app.api import download_api
from app.api import notes_api
from app.api import image_notes_api
from app.api import video_api
from app.api import task_api
# ===================== 配置与数据结构 =====================
from dotenv import load_dotenv
load_dotenv()
print(os.getenv("DB_HOST"))
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "notes_output"
AUDIO_OUTPUT_DIR = "srt_and_wav"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True)

projects = []

class Project(BaseModel):
    id: str
    name: str
    file_path: str
    created_at: datetime

# ===================== 初始化 FastAPI =====================

app = FastAPI(title="视频制作 API")
# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 挂载 API 模块
app.include_router(pdf_api.router)
app.include_router(tts_api.router)
app.include_router(download_api.router)
app.include_router(notes_api.router)
app.include_router(image_notes_api.router)
app.include_router(video_api.router)
app.include_router(task_api.router)
# ✅ 挂载静态目录供前端访问音频和字幕
app.mount("/srt_and_wav", StaticFiles(directory=AUDIO_OUTPUT_DIR), name="audio")

@app.on_event("startup")
async def startup():
    # redis_client = redis.from_url("redis://localhost", encoding="utf-8", decode_responses=True)
    # await FastAPILimiter.init(redis_client)
    pass

# 示例：添加限流装饰器
@app.get("/")
# @app.get("/", dependencies=[RateLimiter(times=2, seconds=5)])
async def root():
    return {"message": "视频制作 API 服务正在运行"}

# ===================== 项目相关接口 =====================

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

    project = Project(
        id=project_id,
        name=file.filename,
        file_path=file_path,
        created_at=datetime.now()
    )
    projects.append(project)

    return {"message": "上传成功", "id": project_id}

@app.post("/api/v1/projects/{project_id}/extract")
def extract_notes_for_project(project_id: str):
    project = next((p for p in projects if p.id == project_id), None)
    if not project:
        return {"error": "项目不存在"}

    output_path = os.path.join(OUTPUT_DIR, project_id)
    notes = extract_notes(project.file_path, output_path)
    return {
        "message": "提取成功",
        "notes": notes
    }

