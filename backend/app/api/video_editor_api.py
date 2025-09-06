from fastapi import APIRouter, UploadFile, File, HTTPException, Form, BackgroundTasks
from fastapi.responses import FileResponse
from typing import List, Dict, Optional
from pathlib import Path
import shutil
import os
import json
import subprocess
import tempfile
import time
import logging
from datetime import datetime
import uuid
import ffmpeg
from pydantic import BaseModel

# 设置日志
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/video-editor", tags=["视频编辑器"])

# 目录配置
VIDEO_EDITOR_DIR = Path("./video_editor")
VIDEO_EDITOR_DIR.mkdir(parents=True, exist_ok=True)

class TimelineItem(BaseModel):
    id: str
    mediaId: str
    startTime: float
    duration: float
    type: str

class VideoGenerationRequest(BaseModel):
    title: str
    timeline: List[TimelineItem]

# 存储项目信息
projects: Dict[str, dict] = {}

def check_ffmpeg():
    """检查 ffmpeg 是否可用"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False

@router.post("/upload-media")
async def upload_media_files(
    project_id: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """上传媒体文件到项目"""
    try:
        # 创建项目目录
        project_dir = VIDEO_EDITOR_DIR / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建媒体文件夹
        media_dir = project_dir / "media"
        media_dir.mkdir(exist_ok=True)
        
        uploaded_files = []
        
        for file in files:
            # 检查文件类型
            file_ext = file.filename.lower().split('.')[-1]
            if file_ext not in ['png', 'jpg', 'jpeg', 'gif', 'wav', 'mp3', 'aac', 'srt', 'vtt']:
                continue
                
            # 生成唯一文件名
            file_id = str(uuid.uuid4())
            file_path = media_dir / f"{file_id}.{file_ext}"
            
            # 保存文件
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            
            # 获取文件信息
            file_size = file_path.stat().st_size
            file_type = get_file_type(file_ext)
            
            file_info = {
                "id": file_id,
                "original_name": file.filename,
                "file_path": str(file_path),
                "type": file_type,
                "size": file_size,
                "extension": file_ext,
                "uploaded_at": datetime.now().isoformat()
            }
            
            # 如果是音频文件，获取时长
            if file_type == "audio":
                try:
                    probe = ffmpeg.probe(str(file_path))
                    file_info["duration"] = float(probe["format"]["duration"])
                except:
                    file_info["duration"] = 0
            
            uploaded_files.append(file_info)
        
        # 更新项目信息
        if project_id not in projects:
            projects[project_id] = {
                "id": project_id,
                "created_at": datetime.now().isoformat(),
                "media_files": []
            }
        
        projects[project_id]["media_files"].extend(uploaded_files)
        
        return {
            "project_id": project_id,
            "uploaded_files": uploaded_files,
            "total_files": len(projects[project_id]["media_files"])
        }
        
    except Exception as e:
        logger.error(f"上传文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

def get_file_type(extension: str) -> str:
    """根据文件扩展名判断文件类型"""
    if extension in ['png', 'jpg', 'jpeg', 'gif']:
        return 'image'
    elif extension in ['wav', 'mp3', 'aac']:
        return 'audio'
    elif extension in ['srt', 'vtt']:
        return 'subtitle'
    return 'unknown'

@router.post("/generate-video")
async def generate_video(
    project_id: str = Form(...),
    title: str = Form(...),
    timeline: str = Form(...),  # JSON字符串
    background_tasks: BackgroundTasks = None
):
    """生成视频"""
    try:
        if not check_ffmpeg():
            raise HTTPException(
                status_code=500,
                detail="ffmpeg 未安装或不可用。请先安装 ffmpeg。"
            )
        
        # 解析时间轴数据
        timeline_data = json.loads(timeline)
        timeline_items = [TimelineItem(**item) for item in timeline_data]
        
        if not timeline_items:
            raise HTTPException(status_code=400, detail="时间轴为空")
        
        # 检查项目是否存在
        if project_id not in projects:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        project = projects[project_id]
        project_dir = VIDEO_EDITOR_DIR / project_id
        
        # 创建输出目录
        output_dir = project_dir / "output"
        output_dir.mkdir(exist_ok=True)
        
        # 生成视频文件名
        video_filename = f"{title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        output_path = output_dir / video_filename
        
        # 在后台生成视频
        if background_tasks:
            background_tasks.add_task(
                generate_video_background,
                project_id,
                project,
                timeline_items,
                output_path,
                title
            )
        else:
            # 同步生成（用于测试）
            await generate_video_background(
                project_id,
                project,
                timeline_items,
                output_path,
                title
            )
        
        return {
            "project_id": project_id,
            "video_title": title,
            "status": "processing",
            "output_file": video_filename,
            "timeline_items": len(timeline_items)
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="时间轴数据格式错误")
    except Exception as e:
        logger.error(f"生成视频失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成视频失败: {str(e)}")

async def generate_video_background(
    project_id: str,
    project: dict,
    timeline_items: List[TimelineItem],
    output_path: Path,
    title: str
):
    """后台生成视频的任务"""
    try:
        logger.info(f"开始生成视频: {title}")
        
        # 创建临时目录用于处理
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 按时间轴顺序处理媒体文件
            sorted_timeline = sorted(timeline_items, key=lambda x: x.startTime)
            
            # 准备ffmpeg输入流
            inputs = []
            filter_complex_parts = []
            
            # 处理每个时间轴项目
            for i, item in enumerate(sorted_timeline):
                # 找到对应的媒体文件
                media_file = None
                for mf in project["media_files"]:
                    if mf["id"] == item.mediaId:
                        media_file = mf
                        break
                
                if not media_file:
                    logger.warning(f"找不到媒体文件: {item.mediaId}")
                    continue
                
                file_path = Path(media_file["file_path"])
                if not file_path.exists():
                    logger.warning(f"文件不存在: {file_path}")
                    continue
                
                # 根据文件类型处理
                if media_file["type"] == "image":
                    # 图片：创建指定时长的视频片段
                    inputs.append(ffmpeg.input(str(file_path), loop=1, t=item.duration))
                    filter_complex_parts.append(f"[{i}:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setpts=PTS-STARTPTS[v{i}]")
                    
                elif media_file["type"] == "audio":
                    # 音频：直接使用
                    inputs.append(ffmpeg.input(str(file_path), ss=0, t=item.duration))
            
            if not inputs:
                raise Exception("没有有效的媒体文件")
            
            # 简化的视频生成逻辑
            logger.info(f"处理 {len(inputs)} 个输入文件")
            
            # 创建一个简单的视频生成方案
            if len(inputs) == 1:
                # 单个输入文件的处理
                input_stream = inputs[0]
                
                # 检查是否是图片
                media_file = project["media_files"][0]  # 假设只有一个文件
                if media_file["type"] == "image":
                    # 图片转视频：添加循环和时长
                    stream = ffmpeg.output(
                        input_stream,
                        str(output_path),
                        vcodec='libx264',
                        pix_fmt='yuv420p',
                        r=25,  # 帧率
                        t=timeline_items[0].duration  # 持续时间
                    )
                else:
                    # 音频或其他格式
                    stream = ffmpeg.output(input_stream, str(output_path))
            else:
                # 多个输入文件：使用简单的拼接
                logger.info("处理多个输入文件")
                
                # 分离视频和音频输入
                video_inputs = []
                audio_inputs = []
                
                for i, (input_stream, timeline_item) in enumerate(zip(inputs, sorted_timeline)):
                    media_file = None
                    for mf in project["media_files"]:
                        if mf["id"] == timeline_item.mediaId:
                            media_file = mf
                            break
                    
                    if media_file and media_file["type"] == "image":
                        video_inputs.append(input_stream)
                    elif media_file and media_file["type"] == "audio":
                        audio_inputs.append(input_stream)
                
                # 如果只有图片，创建图片轮播视频
                if video_inputs and not audio_inputs:
                    if len(video_inputs) == 1:
                        stream = ffmpeg.output(
                            video_inputs[0],
                            str(output_path),
                            vcodec='libx264',
                            pix_fmt='yuv420p',
                            r=25,
                            t=sorted_timeline[0].duration
                        )
                    else:
                        # 多张图片拼接
                        concat_stream = ffmpeg.concat(*video_inputs, v=1, a=0)
                        stream = ffmpeg.output(
                            concat_stream,
                            str(output_path),
                            vcodec='libx264',
                            pix_fmt='yuv420p'
                        )
                else:
                    # 创建黑屏视频作为默认
                    stream = ffmpeg.output(
                        ffmpeg.input('color=black:1280x720:d=10', f='lavfi'),
                        str(output_path),
                        vcodec='libx264',
                        pix_fmt='yuv420p',
                        t=10
                    )
            
            # 执行ffmpeg命令
            logger.info(f"执行ffmpeg命令，输出到: {output_path}")
            ffmpeg.run(stream, overwrite_output=True, quiet=False)
            
        logger.info(f"视频生成完成: {output_path}")
        
        # 更新项目状态
        projects[project_id]["last_video"] = {
            "title": title,
            "file_path": str(output_path),
            "generated_at": datetime.now().isoformat(),
            "status": "completed"
        }
        
    except Exception as e:
        logger.error(f"后台生成视频失败: {str(e)}")
        # 更新项目状态为失败
        projects[project_id]["last_video"] = {
            "title": title,
            "status": "failed",
            "error": str(e),
            "generated_at": datetime.now().isoformat()
        }

@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    """获取项目信息"""
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    return projects[project_id]

@router.get("/projects/{project_id}/media")
async def get_project_media(project_id: str):
    """获取项目的媒体文件列表"""
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    return {
        "project_id": project_id,
        "media_files": projects[project_id]["media_files"]
    }

@router.delete("/projects/{project_id}/media/{file_id}")
async def delete_media_file(project_id: str, file_id: str):
    """删除项目中的媒体文件"""
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    project = projects[project_id]
    media_files = project["media_files"]
    
    # 找到要删除的文件
    file_to_delete = None
    for i, mf in enumerate(media_files):
        if mf["id"] == file_id:
            file_to_delete = mf
            del media_files[i]
            break
    
    if not file_to_delete:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 删除物理文件
    try:
        file_path = Path(file_to_delete["file_path"])
        if file_path.exists():
            file_path.unlink()
    except Exception as e:
        logger.warning(f"删除物理文件失败: {str(e)}")
    
    return {"message": "文件删除成功", "deleted_file": file_to_delete["original_name"]}

@router.get("/projects/{project_id}/download/{video_filename}")
async def download_video(project_id: str, video_filename: str):
    """下载生成的视频"""
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    video_path = VIDEO_EDITOR_DIR / project_id / "output" / video_filename
    
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="视频文件不存在")
    
    return FileResponse(
        path=str(video_path),
        filename=video_filename,
        media_type='video/mp4'
    )

@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """删除整个项目"""
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 删除项目目录
    project_dir = VIDEO_EDITOR_DIR / project_id
    if project_dir.exists():
        shutil.rmtree(project_dir)
    
    # 删除项目记录
    del projects[project_id]
    
    return {"message": "项目删除成功"}

@router.get("/projects")
async def list_projects():
    """获取所有项目列表"""
    return {"projects": list(projects.values())}

@router.get("/projects/{project_id}/videos")
async def list_project_videos(project_id: str):
    """获取项目的所有生成视频"""
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    project_dir = VIDEO_EDITOR_DIR / project_id / "output"
    videos = []
    
    if project_dir.exists():
        for video_file in project_dir.glob("*.mp4"):
            file_stat = video_file.stat()
            videos.append({
                "filename": video_file.name,
                "size": file_stat.st_size,
                "created_at": datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                "download_url": f"/api/video-editor/projects/{project_id}/download/{video_file.name}"
            })
    
    # 添加项目状态信息
    project_info = projects[project_id]
    last_video = project_info.get("last_video", {})
    
    return {
        "project_id": project_id,
        "videos": videos,
        "last_generation": last_video,
        "total_videos": len(videos)
    }
