from fastapi import APIRouter, UploadFile, File, HTTPException, Query, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from typing import List, Dict
from pathlib import Path
import shutil
import zipfile
import os
import json
import subprocess
import tempfile
from app.utils.transcoding import encode_video, get_video_info
import shutil
from app.utils.task_manager import task_manager
print(shutil.which("ffmpeg"))
print("当前 PATH：")
for p in os.environ["PATH"].split(";"):
    print("-", p)

print("是否能找到 ffmpeg：", shutil.which("ffmpeg"))
router = APIRouter(prefix="/api/videos", tags=["视频管理"])

VIDEO_DIR = Path("./videos")
ENCODED_VIDEO_DIR = Path("./encoded_videos")
VIDEO_DIR.mkdir(parents=True, exist_ok=True)
ENCODED_VIDEO_DIR.mkdir(parents=True, exist_ok=True)

def check_ffmpeg():
    """检查 ffmpeg 是否可用"""
    try:
        # 使用 where 命令查找 ffmpeg 路径
        result = subprocess.run(['where', 'ffmpeg'], capture_output=True, text=True)
        if result.returncode == 0:
            ffmpeg_path = result.stdout.strip()
            print(f"找到 ffmpeg: {ffmpeg_path}")
            # 验证 ffmpeg 版本
            version_result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            if version_result.returncode == 0:
                print("ffmpeg 版本检查通过")
                return True
        return False
    except Exception as e:
        print(f"检查 ffmpeg 时出错: {str(e)}")
        return False

# 存储转码任务状态和WebSocket连接
transcoding_tasks: Dict[str, dict] = {}
active_connections: Dict[str, WebSocket] = {}

@router.websocket("/ws/transcode/{task}")
async def websocket_endpoint(websocket: WebSocket, task: str):
    """
    WebSocket 连接端点，用于实时推送转码进度
    """
    await websocket.accept()
    active_connections[task] = websocket
    
    try:
        # 如果任务已存在，立即发送当前状态
        if task in transcoding_tasks:
            await websocket.send_json(transcoding_tasks[task])
        
        # 保持连接直到客户端断开
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if task in active_connections:
            del active_connections[task]

async def send_progress(task: str, data: dict):
    """
    向WebSocket客户端发送进度更新
    """
    if task in active_connections:
        try:
            await active_connections[task].send_json(data)
        except:
            # 如果发送失败，移除连接
            if task in active_connections:
                del active_connections[task]

@router.post("/upload-multiple")
async def upload_multiple_videos(
    task_id: str = Query(None, description="任务ID"),
    filename: str = Query(None, description="文件名/目录名"),
    files: List[UploadFile] = File(...)
):
    """
    批量上传视频文件到指定任务的目录，支持task_id和filename双入口。
    优先使用task_id，若没有则使用filename。
    """
    pdf_name = None
    if task_id:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task["type"] == "pdf_upload":
            pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        else:
            raise HTTPException(status_code=400, detail="不支持的任务类型")
    elif filename:
        pdf_name = filename
    else:
        raise HTTPException(status_code=400, detail="请提供task_id或filename参数")
    # 以pdf_name为目录名
    task_dir = VIDEO_DIR / pdf_name
    task_dir.mkdir(parents=True, exist_ok=True)
    saved_files = []
    for file in files:
        file_path = task_dir / file.filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        saved_files.append(file.filename)
    # 绑定到任务
    if task_id:
        task_data = task.get("data", {})
        video_list = task_data.get("videos", [])
        video_list.extend(saved_files)
        task_data["videos"] = list(set(video_list))
        task_data["video_upload"] = {"status": "completed", "progress": 100, "files": saved_files}
        task_manager.update_task(task_id, data=task_data)
    return {
        "task_id": task_id,
        "uploaded": saved_files,
        "directory": str(task_dir)
    }


@router.get("/")
async def get_all_videos():
    """
    获取所有视频文件，按任务分类返回
    返回格式：
    {
        "tasks": {
            "task1": ["video1.mp4", "video2.mp4"],
            "task2": ["video3.mp4"]
        }
    }
    """
    if not VIDEO_DIR.exists():
        return {"tasks": {}}

    tasks = {}
    # 遍历所有任务目录
    for task_dir in VIDEO_DIR.iterdir():
        if task_dir.is_dir():
            # 获取该任务下的所有视频文件
            videos = []
            for f in task_dir.iterdir():
                if f.is_file() and f.suffix.lower() == '.mp4':
                    videos.append(f.name)
            if videos:  # 只添加有视频的任务
                tasks[task_dir.name] = videos

    return {"tasks": tasks}

@router.post("/transcode")
async def transcode_video(
    task_id: str = Query(None, description="任务ID"),
    filename: str = Query(None, description="文件名/目录名"),
    background_tasks: BackgroundTasks = None
):
    """
    转码指定任务目录下的所有视频文件，支持task_id和filename双入口。
    优先使用task_id，若没有则使用filename。
    """
    # 检查 ffmpeg 是否可用
    if not check_ffmpeg():
        raise HTTPException(
            status_code=500,
            detail="ffmpeg 未安装或不可用。请先安装 ffmpeg 并确保其在系统路径中。"
        )
    pdf_name = None
    if task_id:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task["type"] == "pdf_upload":
            pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        else:
            raise HTTPException(status_code=400, detail="不支持的任务类型")
    elif filename:
        pdf_name = filename
    else:
        raise HTTPException(status_code=400, detail="请提供task_id或filename参数")
    task_dir = VIDEO_DIR / pdf_name
    if not task_dir.exists() or not task_dir.is_dir():
        raise HTTPException(status_code=404, detail="任务目录不存在")
    # 创建对应的输出目录
    output_dir = ENCODED_VIDEO_DIR / pdf_name
    output_dir.mkdir(parents=True, exist_ok=True)
    # 获取所有需要转码的视频
    videos_to_process = []
    for video_file in task_dir.glob("*.mp4"):
        if video_file.parent == task_dir:  # 只处理任务目录下的视频，不包括子目录
            output_path = output_dir / f"encoded_{video_file.name}"
            if not output_path.exists():  # 只处理未转码的视频
                videos_to_process.append((video_file, output_path))
    if not videos_to_process:
        return {"message": "没有需要转码的视频文件"}
    # 初始化任务状态
    transcoding_tasks[pdf_name] = {
        "status": "processing",
        "total": len(videos_to_process),
        "completed": 0,
        "results": []
    }
    # 发送初始状态
    await send_progress(pdf_name, transcoding_tasks[pdf_name])
    # 在后台处理转码
    async def process_videos():
        try:
            for index, (input_path, output_path) in enumerate(videos_to_process, 1):
                try:
                    if not input_path.exists():
                        raise FileNotFoundError(f"输入文件不存在: {input_path}")
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    info = get_video_info(str(input_path))
                    if info and encode_video(str(input_path), str(output_path)):
                        result = {
                            "input": input_path.name,
                            "output": output_path.name,
                            "status": "success",
                            "info": info
                        }
                    else:
                        result = {
                            "input": input_path.name,
                            "status": "failed",
                            "error": "转码失败"
                        }
                    transcoding_tasks[pdf_name]["results"].append(result)
                except Exception as e:
                    result = {
                        "input": input_path.name,
                        "status": "failed",
                        "error": str(e)
                    }
                    transcoding_tasks[pdf_name]["results"].append(result)
                finally:
                    transcoding_tasks[pdf_name]["completed"] += 1
                    await send_progress(pdf_name, transcoding_tasks[pdf_name])
            transcoding_tasks[pdf_name]["status"] = "completed"
            await send_progress(pdf_name, transcoding_tasks[pdf_name])
            # 更新任务状态
            if task_id:
                task_data = task.get("data", {})
                task_data["video_transcode"] = {
                    "status": "completed",
                    "progress": 100,
                    "results": transcoding_tasks[pdf_name]["results"]
                }
                task_manager.update_task(task_id, data=task_data)
        except Exception as e:
            transcoding_tasks[pdf_name]["status"] = "failed"
            transcoding_tasks[pdf_name]["error"] = str(e)
            await send_progress(pdf_name, transcoding_tasks[pdf_name])
            # 更新任务状态
            if task_id:
                task_data = task.get("data", {})
                task_data["video_transcode"] = {
                    "status": "failed",
                    "error": str(e)
                }
                task_manager.update_task(task_id, data=task_data)
    background_tasks.add_task(process_videos)
    return {
        "message": f"开始转码 {len(videos_to_process)} 个视频文件",
        "task": pdf_name,
        "output_directory": str(output_dir),
        "videos_to_process": [v[0].name for v in videos_to_process],
        "websocket_url": f"ws://localhost:8000/api/videos/ws/transcode/{pdf_name}"
    }

@router.get("/download")
async def download_encoded_videos(
    task_id: str = Query(None, description="任务ID"),
    filename: str = Query(None, description="文件名/目录名"),
    background_tasks: BackgroundTasks = None
):
    """
    下载指定任务目录下的所有转码后视频，打包为zip，支持task_id和filename双入口。
    优先使用task_id，若没有则使用filename。
    """
    pdf_name = None
    if task_id:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task["type"] == "pdf_upload":
            pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        else:
            raise HTTPException(status_code=400, detail="不支持的任务类型")
    elif filename:
        pdf_name = filename
    else:
        raise HTTPException(status_code=400, detail="请提供task_id或filename参数")
    task_dir = ENCODED_VIDEO_DIR / pdf_name
    if not task_dir.exists() or not task_dir.is_dir():
        raise HTTPException(status_code=404, detail="任务目录不存在")
    try:
        # 创建临时 zip 文件
        tmp_dir = tempfile.mkdtemp()
        zip_path = Path(tmp_dir) / f"{pdf_name}.zip"
        shutil.make_archive(str(zip_path.with_suffix("")), 'zip', root_dir=task_dir)
        # 下载完自动清理
        background_tasks.add_task(shutil.rmtree, tmp_dir)
        return FileResponse(
            path=zip_path,
            filename=f"{pdf_name}.zip",
            media_type="application/zip"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"打包失败: {e}")