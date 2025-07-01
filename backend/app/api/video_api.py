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
from app.utils.task_manager_memory import task_manager
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
    tasks = {}
    encoded = {}

    # 原始视频
    if VIDEO_DIR.exists():
        for td in VIDEO_DIR.iterdir():
            if td.is_dir():
                vids = [f.name for f in td.iterdir() if f.suffix.lower()=='.mp4']
                if vids:
                    tasks[td.name] = vids

    # 已转码视频
    if ENCODED_VIDEO_DIR.exists():
        for td in ENCODED_VIDEO_DIR.iterdir():
            if td.is_dir():
                vids = [f.name for f in td.iterdir() if f.is_file() and f.suffix.lower()=='.mp4']
                if vids:
                    encoded[td.name] = vids

    return {"tasks": tasks, "encoded": encoded}

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
    files: str    = Query(None, description="用逗号分隔的已选文件列表"),
    background_tasks: BackgroundTasks = None
):
    """
    下载指定任务目录下的已转码视频，打包为 ZIP。
    支持 task_id 或 filename 两种入口，优先使用 task_id。
    前端传入的文件名可以是 "file.mp4" 或 "encoded_file.mp4"。
    """

    # 1. 确定目录名 pdf_name
    if task_id:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        # 根据业务类型取原始名称
        if task["type"] in ("pdf_upload", "pdf_to_images"):
            key = "original_filename" if task["type"]=="pdf_upload" else "pdf_filename"
            pdf_name = task["data"].get(key, "").rsplit(".", 1)[0]
        else:
            raise HTTPException(status_code=400, detail="不支持的任务类型")
    elif filename:
        pdf_name = filename
    else:
        raise HTTPException(status_code=400, detail="请提供 task_id 或 filename 参数")

    # 2. 校验输出目录
    task_dir = ENCODED_VIDEO_DIR / pdf_name
    if not task_dir.exists() or not task_dir.is_dir():
        raise HTTPException(status_code=404, detail="转码输出目录不存在")

    # 3. 解析用户选中的文件列表（files 参数）
    if files:
        selected = [f for f in files.split(",") if f]
    else:
        # 不传 files 就下载全部
        selected = [p.name for p in task_dir.iterdir() if p.is_file()]

    # 4. 创建临时目录和 ZIP
    tmp_dir = tempfile.mkdtemp()
    zip_path = Path(tmp_dir) / f"{pdf_name}.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name in selected:
            # 兼容前端传入带/不带前缀的情况
            if name.startswith("encoded_"):
                real_name = name
                arc_name  = name[len("encoded_"):]
            else:
                real_name = f"encoded_{name}"
                arc_name  = name

            src = task_dir / real_name
            if not src.exists():
                # 找不到文件就跳过
                continue
            # 打包时把文件写为原始名称（去掉 encoded_ 前缀）
            zf.write(src, arcname=arc_name)

    # 5. 异步删除临时目录
    background_tasks.add_task(shutil.rmtree, tmp_dir)

    # 6. 返回 ZIP 文件
    return FileResponse(
        path=zip_path,
        filename=f"{pdf_name}.zip",
        media_type="application/zip"
    )

@router.get("/download-file")
async def download_file(
    filename: str = Query(..., description="任务目录名"),
    file: str     = Query(..., description="原始文件名，例如 0519(1).mp4 或 encoded_0519(1).mp4")
):
    # 如果前端传的是原始名，就加前缀；如果已经带了，就直接用
    if file.startswith("encoded_"):
        encoded_name = file
        download_as   = file[len("encoded_"):]  # 去掉前缀后做下载名
    else:
        encoded_name = f"encoded_{file}"
        download_as   = file

    file_path = ENCODED_VIDEO_DIR / filename / encoded_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(404, detail=f"{encoded_name} 不存在")

    return FileResponse(
        path=file_path,
        media_type="application/octet-stream",
        filename=download_as    # 浏览器保存成没有前缀的原始文件名
    )

@router.get("/all-folders")
async def get_all_folders():
    """
    获取所有已转码视频的任务文件夹（即 encoded_videos 下所有子目录名）。
    """
    if not ENCODED_VIDEO_DIR.exists():
        return {"folders": []}
    folders = [
        f.name for f in ENCODED_VIDEO_DIR.iterdir()
        if f.is_dir()
    ]
    return {"folders": folders}
