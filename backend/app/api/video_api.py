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
    task: str = Query(..., description="任务名称（PDF文件名）"),
    files: List[UploadFile] = File(...)
):
    """
    批量上传视频文件到指定任务的目录
    """
    # 创建任务目录
    task_dir = VIDEO_DIR / task
    task_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for file in files:
        file_path = task_dir / file.filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        saved_files.append(file.filename)
    
    return {
        "task": task,
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
    task: str = Query(..., description="任务名称（PDF文件名）"),
    background_tasks: BackgroundTasks = None
):
    """
    转码指定任务目录下的所有视频文件
    使用后台任务处理，避免阻塞
    转码后的视频保存在 encoded_videos 目录下，保持相同的目录结构
    通过 WebSocket 实时推送进度
    """
    # 检查 ffmpeg 是否可用
    if not check_ffmpeg():
        raise HTTPException(
            status_code=500,
            detail="ffmpeg 未安装或不可用。请先安装 ffmpeg 并确保其在系统路径中。"
        )

    task_dir = VIDEO_DIR / task
    if not task_dir.exists() or not task_dir.is_dir():
        raise HTTPException(status_code=404, detail="任务目录不存在")

    # 创建对应的输出目录
    output_dir = ENCODED_VIDEO_DIR / task
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
    transcoding_tasks[task] = {
        "status": "processing",
        "total": len(videos_to_process),
        "completed": 0,
        "results": []
    }
    
    # 发送初始状态
    await send_progress(task, transcoding_tasks[task])

    # 在后台处理转码
    async def process_videos():
        try:
            print(f"\n开始处理任务 {task} 的转码...")
            print(f"输入目录: {task_dir}")
            print(f"输入目录(原始字符串): {str(task_dir)}")
            print(f"输入目录(字节): {str(task_dir).encode()}")
            print(f"输出目录: {output_dir}")
            print(f"总共需要处理 {len(videos_to_process)} 个视频文件")
            
            for index, (input_path, output_path) in enumerate(videos_to_process, 1):
                try:
                    print(f"\n[{index}/{len(videos_to_process)}] 正在处理: {input_path.name}")
                    print(f"输入文件路径: {input_path}")
                    print(f"输入文件路径(原始字符串): {str(input_path)}")
                    print(f"输入文件路径(字节): {str(input_path).encode()}")
                    print(f"输入文件路径(绝对路径): {input_path.absolute()}")
                    print(f"输出文件路径: {output_path}")
                    
                    # 检查输入文件是否存在
                    if not input_path.exists():
                        print(f"文件不存在，尝试列出目录内容:")
                        try:
                            print(f"目录内容: {list(input_path.parent.iterdir())}")
                        except Exception as e:
                            print(f"列出目录内容失败: {str(e)}")
                        raise FileNotFoundError(f"输入文件不存在: {input_path}")
                    
                    # 确保输出目录存在
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # 获取视频信息
                    info = get_video_info(str(input_path))
                    if info:
                        print(f"视频信息: {info['width']}x{info['height']}, 时长: {info['duration']:.2f}秒")
                        
                        # 执行转码
                        print("开始转码...")
                        if encode_video(str(input_path), str(output_path)):
                            result = {
                                "input": input_path.name,
                                "output": output_path.name,
                                "status": "success",
                                "info": info
                            }
                            print(f"✓ 转码成功: {output_path.name}")
                        else:
                            result = {
                                "input": input_path.name,
                                "status": "failed",
                                "error": "转码失败"
                            }
                            print(f"✗ 转码失败: {input_path.name}")
                    transcoding_tasks[task]["results"].append(result)
                except FileNotFoundError as e:
                    result = {
                        "input": input_path.name,
                        "status": "failed",
                        "error": f"文件不存在: {str(e)}"
                    }
                    transcoding_tasks[task]["results"].append(result)
                    print(f"✗ 文件错误: {str(e)}")
                except Exception as e:
                    result = {
                        "input": input_path.name,
                        "status": "failed",
                        "error": str(e)
                    }
                    transcoding_tasks[task]["results"].append(result)
                    print(f"✗ 处理出错: {str(e)}")
                finally:
                    transcoding_tasks[task]["completed"] += 1
                    progress = (transcoding_tasks[task]["completed"] / transcoding_tasks[task]["total"]) * 100
                    print(f"总体进度: {progress:.1f}%")
                    # 发送进度更新
                    await send_progress(task, transcoding_tasks[task])

            # 更新任务状态
            transcoding_tasks[task]["status"] = "completed"
            print(f"\n任务 {task} 转码完成！")
            print(f"成功: {sum(1 for r in transcoding_tasks[task]['results'] if r['status'] == 'success')}")
            print(f"失败: {sum(1 for r in transcoding_tasks[task]['results'] if r['status'] == 'failed')}")
            await send_progress(task, transcoding_tasks[task])
        except Exception as e:
            transcoding_tasks[task]["status"] = "failed"
            transcoding_tasks[task]["error"] = str(e)
            print(f"\n任务 {task} 转码失败: {str(e)}")
            await send_progress(task, transcoding_tasks[task])

    # 添加后台任务
    background_tasks.add_task(process_videos)

    return {
        "message": f"开始转码 {len(videos_to_process)} 个视频文件",
        "task": task,
        "output_directory": str(output_dir),
        "videos_to_process": [v[0].name for v in videos_to_process],
        "websocket_url": f"ws://localhost:8000/api/videos/ws/transcode/{task}"
    }

@router.get("/download")
async def download_encoded_videos(
    task: str = Query(..., description="视频任务名称（子目录名）"),
    background_tasks: BackgroundTasks = None
):
    task_dir = ENCODED_VIDEO_DIR / task
    if not task_dir.exists() or not task_dir.is_dir():
        raise HTTPException(status_code=404, detail="任务目录不存在")

    try:
        # 创建临时 zip 文件
        tmp_dir = tempfile.mkdtemp()
        zip_path = Path(tmp_dir) / f"{task}.zip"
        shutil.make_archive(str(zip_path.with_suffix("")), 'zip', root_dir=task_dir)

        # 下载完自动清理
        background_tasks.add_task(shutil.rmtree, tmp_dir)

        return FileResponse(
            path=zip_path,
            filename=f"{task}.zip",
            media_type="application/zip"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"打包失败: {e}")