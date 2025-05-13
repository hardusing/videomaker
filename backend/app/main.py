import os
import uuid
from datetime import datetime
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List

from app.utils.ppt_parser import extract_notes
from app.tts.tts_engine import tts, find_txt_files  # ✅ 你要确保这些文件已在对应目录下

from app.api import pdf_api
from app.api import srt
from app.api import tts_api
from app.api import download_api
# ===================== 配置与数据结构 =====================

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

app = FastAPI()
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
app.include_router(srt.router)
app.include_router(tts_api.router)
app.include_router(download_api.router)
# ✅ 挂载静态目录供前端访问音频和字幕
app.mount("/srt_and_wav", StaticFiles(directory=AUDIO_OUTPUT_DIR), name="audio")

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

# ===================== TTS 相关接口 =====================

@app.get("/api/tts/texts")
def list_txt_files():
    files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".txt")]
    return files

@app.post("/api/tts/generate")
def generate_all_audio():
    raw_txt = find_txt_files(OUTPUT_DIR)
    raw_txt.sort()

    for path in raw_txt:
        tts(path, output_dir=AUDIO_OUTPUT_DIR)

    files = os.listdir(AUDIO_OUTPUT_DIR)
    audio_files = [f for f in files if f.endswith(".wav")]
    srt_files = [f for f in files if f.endswith("_merged.srt")]

    return {
        "audio_files": audio_files,
        "subtitle_files": srt_files
    }
