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
import time
import logging
from datetime import datetime
from app.utils.transcoding import encode_video, get_video_info
import shutil
from app.utils.task_manager_memory import task_manager

# 设置日志
logger = logging.getLogger(__name__)

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
        "current_file": "",
        "current_progress": 0,
        "results": [],
        "start_time": datetime.now().isoformat(),
        "statistics": {
            "total_input_size": 0,
            "total_output_size": 0,
            "successful_transcodes": 0,
            "failed_transcodes": 0
        }
    }
    
    # 发送初始状态
    await send_progress(pdf_name, transcoding_tasks[pdf_name])
    
    logger.info(f"开始转码任务: {pdf_name}, 共 {len(videos_to_process)} 个文件")
    
    # 在后台处理转码
    async def process_videos():
        try:
            batch_start_time = time.time()
            
            for index, (input_path, output_path) in enumerate(videos_to_process, 1):
                try:
                    # 更新当前处理的文件
                    transcoding_tasks[pdf_name]["current_file"] = input_path.name
                    transcoding_tasks[pdf_name]["current_progress"] = 0
                    await send_progress(pdf_name, transcoding_tasks[pdf_name])
                    
                    logger.info(f"[{index}/{len(videos_to_process)}] 开始转码: {input_path.name}")
                    
                    if not input_path.exists():
                        raise FileNotFoundError(f"输入文件不存在: {input_path}")
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # 获取输入文件信息用于统计
                    input_info = get_video_info(str(input_path))
                    if input_info:
                        transcoding_tasks[pdf_name]["statistics"]["total_input_size"] += input_info['file_size']
                    
                    # 执行转码
                    success, transcode_result = encode_video(str(input_path), str(output_path))
                    
                    if success and transcode_result:
                        # 转码成功
                        transcoding_tasks[pdf_name]["statistics"]["successful_transcodes"] += 1
                        transcoding_tasks[pdf_name]["statistics"]["total_output_size"] += transcode_result['output_info']['file_size']
                        
                        result = {
                            "input": input_path.name,
                            "output": output_path.name,
                            "status": "success",
                            "duration": transcode_result.get("encoding_duration", 0),
                            "input_info": transcode_result.get("input_info", {}),
                            "output_info": transcode_result.get("output_info", {}),
                            "changes": transcode_result.get("changes", {}),
                            "encoding_settings": transcode_result.get("encoding_settings", {}),
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        logger.info(f"✅ 转码成功: {input_path.name} -> {output_path.name}")
                        
                        # 打印转码结果统计
                        if "changes" in transcode_result:
                            changes = transcode_result["changes"]
                            logger.info(f"   文件大小变化: {changes.get('size_change_mb', 0):+.2f} MB ({changes.get('size_change_percent', 0):+.2f}%)")
                            logger.info(f"   压缩比: {changes.get('compression_ratio', 1):.3f}")
                    
                    else:
                        # 转码失败
                        transcoding_tasks[pdf_name]["statistics"]["failed_transcodes"] += 1
                        error_msg = "转码失败"
                        if isinstance(transcode_result, dict) and "error" in transcode_result:
                            error_msg = transcode_result["error"]
                        
                        result = {
                            "input": input_path.name,
                            "status": "failed",
                            "error": error_msg,
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        logger.error(f"❌ 转码失败: {input_path.name} - {error_msg}")
                    
                    transcoding_tasks[pdf_name]["results"].append(result)
                    
                except Exception as e:
                    # 处理异常
                    transcoding_tasks[pdf_name]["statistics"]["failed_transcodes"] += 1
                    error_msg = str(e)
                    
                    result = {
                        "input": input_path.name,
                        "status": "failed", 
                        "error": error_msg,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    transcoding_tasks[pdf_name]["results"].append(result)
                    logger.error(f"❌ 转码异常: {input_path.name} - {error_msg}")
                
                finally:
                    # 更新进度
                    transcoding_tasks[pdf_name]["completed"] += 1
                    transcoding_tasks[pdf_name]["current_progress"] = 100
                    await send_progress(pdf_name, transcoding_tasks[pdf_name])
            
            # 完成所有转码
            batch_end_time = time.time()
            batch_duration = batch_end_time - batch_start_time
            
            # 计算总体统计
            stats = transcoding_tasks[pdf_name]["statistics"]
            total_input_size_mb = round(stats["total_input_size"] / (1024 * 1024), 2)
            total_output_size_mb = round(stats["total_output_size"] / (1024 * 1024), 2)
            total_size_change_mb = total_output_size_mb - total_input_size_mb
            
            compression_ratio = round(stats["total_output_size"] / stats["total_input_size"], 3) if stats["total_input_size"] > 0 else 0
            success_rate = round((stats["successful_transcodes"] / len(videos_to_process)) * 100, 1)
            
            # 更新最终状态
            transcoding_tasks[pdf_name].update({
                "status": "completed",
                "end_time": datetime.now().isoformat(),
                "batch_duration": round(batch_duration, 2),
                "current_file": "",
                "current_progress": 100,
                "summary": {
                    "total_files": len(videos_to_process),
                    "successful": stats["successful_transcodes"],
                    "failed": stats["failed_transcodes"],
                    "success_rate": success_rate,
                    "total_duration": round(batch_duration, 2),
                    "total_input_size_mb": total_input_size_mb,
                    "total_output_size_mb": total_output_size_mb,
                    "total_size_change_mb": total_size_change_mb,
                    "compression_ratio": compression_ratio
                }
            })
            
            await send_progress(pdf_name, transcoding_tasks[pdf_name])
            
            # 打印批量转码总结
            logger.info("=" * 80)
            logger.info(f"批量转码完成 - {pdf_name}")
            logger.info("=" * 80)
            logger.info(f"总文件数: {len(videos_to_process)}")
            logger.info(f"成功转码: {stats['successful_transcodes']}")
            logger.info(f"失败转码: {stats['failed_transcodes']}")
            logger.info(f"成功率: {success_rate}%")
            logger.info(f"总耗时: {batch_duration:.2f} 秒")
            logger.info(f"总输入大小: {total_input_size_mb} MB")
            logger.info(f"总输出大小: {total_output_size_mb} MB")
            logger.info(f"总大小变化: {total_size_change_mb:+.2f} MB")
            logger.info(f"整体压缩比: {compression_ratio:.3f}")
            logger.info("=" * 80)
            
            # 更新任务状态
            if task_id:
                task_data = task.get("data", {})
                task_data["video_transcode"] = {
                    "status": "completed",
                    "progress": 100,
                    "results": transcoding_tasks[pdf_name]["results"],
                    "summary": transcoding_tasks[pdf_name]["summary"],
                    "statistics": transcoding_tasks[pdf_name]["statistics"]
                }
                task_manager.update_task(task_id, data=task_data)
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"批量转码失败: {pdf_name} - {error_msg}")
            
            transcoding_tasks[pdf_name].update({
                "status": "failed",
                "error": error_msg,
                "end_time": datetime.now().isoformat()
            })
            
            await send_progress(pdf_name, transcoding_tasks[pdf_name])
            
            # 更新任务状态
            if task_id:
                task_data = task.get("data", {})
                task_data["video_transcode"] = {
                    "status": "failed",
                    "error": error_msg
                }
                task_manager.update_task(task_id, data=task_data)
    
    background_tasks.add_task(process_videos)
    
    return {
        "message": f"开始转码 {len(videos_to_process)} 个视频文件",
        "task": pdf_name,
        "output_directory": str(output_dir),
        "videos_to_process": [v[0].name for v in videos_to_process],
        "websocket_url": f"ws://localhost:8000/api/videos/ws/transcode/{pdf_name}",
        "expected_results": {
            "total_files": len(videos_to_process),
            "estimated_time": "根据文件大小和复杂度而定",
            "output_format": "H.264/AAC MP4"
        }
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

def _resolve_task_directory(task_id: str = None, filename: str = None):
    """
    解析任务目录，支持task_id和filename双入口
    """
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
    
    return pdf_name

@router.get("/transcode-status")
async def get_transcode_status(
    task_id: str = Query(None, description="任务ID"),
    filename: str = Query(None, description="文件名/目录名")
):
    """
    获取指定任务的转码状态和详细统计信息
    支持task_id和filename双入口，优先使用task_id
    """
    pdf_name = _resolve_task_directory(task_id, filename)
    
    if pdf_name not in transcoding_tasks:
        raise HTTPException(status_code=404, detail="转码任务不存在")
    
    return transcoding_tasks[pdf_name]

@router.get("/transcode-results")
async def get_transcode_results(
    task_id: str = Query(None, description="任务ID"),
    filename: str = Query(None, description="文件名/目录名")
):
    """
    获取指定任务的详细转码结果，包括每个文件的转码前后对比
    支持task_id和filename双入口，优先使用task_id
    """
    pdf_name = _resolve_task_directory(task_id, filename)
    
    if pdf_name not in transcoding_tasks:
        raise HTTPException(status_code=404, detail="转码任务不存在")
    
    task_data = transcoding_tasks[pdf_name]
    
    # 如果任务还在进行中，只返回基本状态
    if task_data["status"] == "processing":
        return {
            "status": "processing",
            "task_name": pdf_name,
            "current_file": task_data.get("current_file", ""),
            "progress": f"{task_data['completed']}/{task_data['total']}",
            "percentage": round((task_data["completed"] / task_data["total"]) * 100, 1)
        }
    
    # 返回完整的结果
    return {
        "task_name": pdf_name,
        "status": task_data["status"],
        "summary": task_data.get("summary", {}),
        "statistics": task_data.get("statistics", {}),
        "results": task_data.get("results", []),
        "start_time": task_data.get("start_time"),
        "end_time": task_data.get("end_time"),
        "batch_duration": task_data.get("batch_duration")
    }

@router.get("/transcode-logs")
async def get_transcode_logs(
    task_id: str = Query(None, description="任务ID"),
    filename: str = Query(None, description="文件名/目录名")
):
    """
    获取转码日志文件内容
    支持task_id和filename双入口，优先使用task_id
    """
    pdf_name = _resolve_task_directory(task_id, filename)
    
    log_file = Path("transcoding.log")
    if not log_file.exists():
        raise HTTPException(status_code=404, detail="日志文件不存在")
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            logs = f.read()
        
        # 过滤出与指定任务相关的日志
        filtered_logs = []
        for line in logs.split('\n'):
            if pdf_name in line or '转码' in line:
                filtered_logs.append(line)
        
        return {
            "task_name": pdf_name,
            "logs": filtered_logs[-100:],  # 返回最后100行相关日志
            "total_lines": len(filtered_logs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取日志失败: {str(e)}")

@router.get("/download-results")
async def download_transcode_results(
    task_id: str = Query(None, description="任务ID"),
    filename: str = Query(None, description="文件名/目录名"),
    background_tasks: BackgroundTasks = None
):
    """
    下载转码结果的JSON报告文件
    支持task_id和filename双入口，优先使用task_id
    """
    pdf_name = _resolve_task_directory(task_id, filename)
    
    if pdf_name not in transcoding_tasks:
        raise HTTPException(status_code=404, detail="转码任务不存在")
    
    task_data = transcoding_tasks[pdf_name]
    
    # 创建临时文件
    tmp_dir = tempfile.mkdtemp()
    report_file = Path(tmp_dir) / f"{pdf_name}_transcode_report.json"
    
    # 生成详细报告
    report_data = {
        "task_name": pdf_name,
        "report_generated": datetime.now().isoformat(),
        "summary": task_data.get("summary", {}),
        "statistics": task_data.get("statistics", {}),
        "detailed_results": task_data.get("results", []),
        "metadata": {
            "start_time": task_data.get("start_time"),
            "end_time": task_data.get("end_time"),
            "batch_duration": task_data.get("batch_duration"),
            "total_files_processed": task_data.get("total", 0),
            "files_completed": task_data.get("completed", 0)
        }
    }
    
    # 写入文件
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    
    # 异步删除临时目录
    background_tasks.add_task(shutil.rmtree, tmp_dir)
    
    return FileResponse(
        path=report_file,
        filename=f"{pdf_name}_transcode_report.json",
        media_type="application/json"
    )

@router.delete("/transcode-tasks")
async def clear_transcode_task(
    task_id: str = Query(None, description="任务ID"),
    filename: str = Query(None, description="文件名/目录名")
):
    """
    清除指定的转码任务记录
    支持task_id和filename双入口，优先使用task_id
    """
    pdf_name = _resolve_task_directory(task_id, filename)
    
    if pdf_name not in transcoding_tasks:
        raise HTTPException(status_code=404, detail="转码任务不存在")
    
    # 只有完成或失败的任务才能被清除
    if transcoding_tasks[pdf_name]["status"] == "processing":
        raise HTTPException(status_code=400, detail="正在进行的任务不能被清除")
    
    del transcoding_tasks[pdf_name]
    return {"message": f"转码任务 {pdf_name} 已清除"}

@router.get("/all-transcode-tasks")
async def get_all_transcode_tasks():
    """
    获取所有转码任务的概览信息
    """
    tasks_overview = {}
    
    for task_name, task_data in transcoding_tasks.items():
        tasks_overview[task_name] = {
            "status": task_data["status"],
            "total_files": task_data.get("total", 0),
            "completed_files": task_data.get("completed", 0),
            "start_time": task_data.get("start_time"),
            "end_time": task_data.get("end_time"),
            "success_rate": task_data.get("summary", {}).get("success_rate", 0) if task_data["status"] == "completed" else None
        }
    
    return {
        "total_tasks": len(transcoding_tasks),
        "tasks": tasks_overview
    }

@router.post("/transcode-directory")
async def transcode_directory(
    directory_path: str = Query(..., description="要转码的目录路径（相对于videos目录）"),
    recursive: bool = Query(True, description="是否递归处理子目录"),
    background_tasks: BackgroundTasks = None
):
    """
    直接对指定目录进行转码，支持递归处理子目录下的所有视频文件
    """
    # 检查 ffmpeg 是否可用
    if not check_ffmpeg():
        raise HTTPException(
            status_code=500,
            detail="ffmpeg 未安装或不可用。请先安装 ffmpeg 并确保其在系统路径中。"
        )
    
    # 构建完整的输入和输出路径
    input_dir = VIDEO_DIR / directory_path
    output_dir = ENCODED_VIDEO_DIR / directory_path
    
    if not input_dir.exists() or not input_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"目录不存在: {directory_path}")
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 获取所有需要转码的视频文件
    videos_to_process = []
    
    if recursive:
        # 递归查找所有MP4文件
        video_files = list(input_dir.rglob("*.mp4"))
        logger.info(f"递归搜索 {directory_path} 目录，找到 {len(video_files)} 个视频文件")
    else:
        # 只处理当前目录下的MP4文件
        video_files = list(input_dir.glob("*.mp4"))
        logger.info(f"搜索 {directory_path} 目录，找到 {len(video_files)} 个视频文件")
    
    for video_file in video_files:
        # 计算相对路径
        relative_path = video_file.relative_to(input_dir)
        output_path = output_dir / relative_path.parent / f"encoded_{video_file.name}"
        
        # 只处理未转码的视频
        if not output_path.exists():
            videos_to_process.append((video_file, output_path))
    
    if not videos_to_process:
        return {"message": f"目录 {directory_path} 中没有需要转码的视频文件"}
    
    # 使用目录路径作为任务名称
    task_name = f"dir_{directory_path.replace('/', '_').replace(chr(92), '_')}"
    
    # 初始化任务状态
    transcoding_tasks[task_name] = {
        "status": "processing",
        "total": len(videos_to_process),
        "completed": 0,
        "current_file": "",
        "current_progress": 0,
        "results": [],
        "start_time": datetime.now().isoformat(),
        "directory_path": directory_path,
        "recursive": recursive,
        "statistics": {
            "total_input_size": 0,
            "total_output_size": 0,
            "successful_transcodes": 0,
            "failed_transcodes": 0
        }
    }
    
    # 发送初始状态
    await send_progress(task_name, transcoding_tasks[task_name])
    
    logger.info(f"开始目录转码任务: {directory_path}, 递归: {recursive}, 共 {len(videos_to_process)} 个文件")
    
    # 在后台处理转码
    async def process_directory_videos():
        try:
            batch_start_time = time.time()
            
            for index, (input_path, output_path) in enumerate(videos_to_process, 1):
                try:
                    # 更新当前处理的文件
                    relative_input = input_path.relative_to(input_dir)
                    transcoding_tasks[task_name]["current_file"] = str(relative_input)
                    transcoding_tasks[task_name]["current_progress"] = 0
                    await send_progress(task_name, transcoding_tasks[task_name])
                    
                    logger.info(f"[{index}/{len(videos_to_process)}] 开始转码: {relative_input}")
                    
                    if not input_path.exists():
                        raise FileNotFoundError(f"输入文件不存在: {input_path}")
                    
                    # 确保输出目录存在
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # 获取输入文件信息用于统计
                    input_info = get_video_info(str(input_path))
                    if input_info:
                        transcoding_tasks[task_name]["statistics"]["total_input_size"] += input_info['file_size']
                    
                    # 执行转码
                    success, transcode_result = encode_video(str(input_path), str(output_path))
                    
                    if success and transcode_result:
                        # 转码成功
                        transcoding_tasks[task_name]["statistics"]["successful_transcodes"] += 1
                        transcoding_tasks[task_name]["statistics"]["total_output_size"] += transcode_result['output_info']['file_size']
                        
                        result = {
                            "input": str(relative_input),
                            "output": str(output_path.relative_to(output_dir)),
                            "status": "success",
                            "duration": transcode_result.get("encoding_duration", 0),
                            "input_info": transcode_result.get("input_info", {}),
                            "output_info": transcode_result.get("output_info", {}),
                            "changes": transcode_result.get("changes", {}),
                            "encoding_settings": transcode_result.get("encoding_settings", {}),
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        logger.info(f"✅ 转码成功: {relative_input}")
                        
                        # 打印转码结果统计
                        if "changes" in transcode_result:
                            changes = transcode_result["changes"]
                            logger.info(f"   文件大小变化: {changes.get('size_change_mb', 0):+.2f} MB ({changes.get('size_change_percent', 0):+.2f}%)")
                            logger.info(f"   压缩比: {changes.get('compression_ratio', 1):.3f}")
                    
                    else:
                        # 转码失败
                        transcoding_tasks[task_name]["statistics"]["failed_transcodes"] += 1
                        error_msg = "转码失败"
                        if isinstance(transcode_result, dict) and "error" in transcode_result:
                            error_msg = transcode_result["error"]
                        
                        result = {
                            "input": str(relative_input),
                            "status": "failed",
                            "error": error_msg,
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        logger.error(f"❌ 转码失败: {relative_input} - {error_msg}")
                    
                    transcoding_tasks[task_name]["results"].append(result)
                    
                except Exception as e:
                    # 处理异常
                    transcoding_tasks[task_name]["statistics"]["failed_transcodes"] += 1
                    error_msg = str(e)
                    relative_input = input_path.relative_to(input_dir) if input_path.exists() else "unknown"
                    
                    result = {
                        "input": str(relative_input),
                        "status": "failed", 
                        "error": error_msg,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    transcoding_tasks[task_name]["results"].append(result)
                    logger.error(f"❌ 转码异常: {relative_input} - {error_msg}")
                
                finally:
                    # 更新进度
                    transcoding_tasks[task_name]["completed"] += 1
                    transcoding_tasks[task_name]["current_progress"] = 100
                    await send_progress(task_name, transcoding_tasks[task_name])
            
            # 完成所有转码
            batch_end_time = time.time()
            batch_duration = batch_end_time - batch_start_time
            
            # 计算总体统计
            stats = transcoding_tasks[task_name]["statistics"]
            total_input_size_mb = round(stats["total_input_size"] / (1024 * 1024), 2)
            total_output_size_mb = round(stats["total_output_size"] / (1024 * 1024), 2)
            total_size_change_mb = total_output_size_mb - total_input_size_mb
            
            compression_ratio = round(stats["total_output_size"] / stats["total_input_size"], 3) if stats["total_input_size"] > 0 else 0
            success_rate = round((stats["successful_transcodes"] / len(videos_to_process)) * 100, 1)
            
            # 更新最终状态
            transcoding_tasks[task_name].update({
                "status": "completed",
                "end_time": datetime.now().isoformat(),
                "batch_duration": round(batch_duration, 2),
                "current_file": "",
                "current_progress": 100,
                "summary": {
                    "total_files": len(videos_to_process),
                    "successful": stats["successful_transcodes"],
                    "failed": stats["failed_transcodes"],
                    "success_rate": success_rate,
                    "total_duration": round(batch_duration, 2),
                    "total_input_size_mb": total_input_size_mb,
                    "total_output_size_mb": total_output_size_mb,
                    "total_size_change_mb": total_size_change_mb,
                    "compression_ratio": compression_ratio
                }
            })
            
            await send_progress(task_name, transcoding_tasks[task_name])
            
            # 打印批量转码总结
            logger.info("=" * 80)
            logger.info(f"目录转码完成 - {directory_path}")
            logger.info("=" * 80)
            logger.info(f"处理模式: {'递归' if recursive else '非递归'}")
            logger.info(f"总文件数: {len(videos_to_process)}")
            logger.info(f"成功转码: {stats['successful_transcodes']}")
            logger.info(f"失败转码: {stats['failed_transcodes']}")
            logger.info(f"成功率: {success_rate}%")
            logger.info(f"总耗时: {batch_duration:.2f} 秒")
            logger.info(f"总输入大小: {total_input_size_mb} MB")
            logger.info(f"总输出大小: {total_output_size_mb} MB")
            logger.info(f"总大小变化: {total_size_change_mb:+.2f} MB")
            logger.info(f"整体压缩比: {compression_ratio:.3f}")
            logger.info("=" * 80)
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"目录转码失败: {directory_path} - {error_msg}")
            
            transcoding_tasks[task_name].update({
                "status": "failed",
                "error": error_msg,
                "end_time": datetime.now().isoformat()
            })
            
            await send_progress(task_name, transcoding_tasks[task_name])
    
    background_tasks.add_task(process_directory_videos)
    
    return {
        "message": f"开始目录转码 {len(videos_to_process)} 个视频文件",
        "task_name": task_name,
        "directory_path": directory_path,
        "recursive": recursive,
        "input_directory": str(input_dir),
        "output_directory": str(output_dir),
        "videos_to_process": [str(v[0].relative_to(input_dir)) for v in videos_to_process],
        "websocket_url": f"ws://localhost:8000/api/videos/ws/transcode/{task_name}",
        "expected_results": {
            "total_files": len(videos_to_process),
            "estimated_time": "根据文件大小和复杂度而定",
            "output_format": "H.264/AAC MP4"
        }
    }

@router.get("/list-video-directories")
async def list_video_directories():
    """
    列出videos目录下的所有子目录，用于目录转码选择
    """
    directories = []
    
    def scan_directory(path: Path, relative_path: str = ""):
        try:
            for item in path.iterdir():
                if item.is_dir():
                    dir_relative_path = f"{relative_path}/{item.name}" if relative_path else item.name
                    
                    # 统计该目录下的视频文件数量
                    mp4_count = len(list(item.glob("*.mp4")))
                    recursive_mp4_count = len(list(item.rglob("*.mp4")))
                    
                    directories.append({
                        "path": dir_relative_path,
                        "name": item.name,
                        "mp4_files": mp4_count,
                        "total_mp4_files": recursive_mp4_count,
                        "has_subdirs": any(sub.is_dir() for sub in item.iterdir())
                    })
                    
                    # 递归扫描子目录
                    scan_directory(item, dir_relative_path)
        except PermissionError:
            pass  # 忽略权限错误
    
    if VIDEO_DIR.exists():
        scan_directory(VIDEO_DIR)
    
    return {
        "total_directories": len(directories),
        "directories": sorted(directories, key=lambda x: x["path"])
    }
