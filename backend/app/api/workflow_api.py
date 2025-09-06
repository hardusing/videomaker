from fastapi import APIRouter, UploadFile, File, HTTPException, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
from pathlib import Path
import logging
import asyncio
import time
from datetime import datetime
from pydantic import BaseModel, Field

# 导入现有的API函数
from .pdf_api import upload_ppt_convert_pdf
from .image_notes_api import add_black_border_for_pdf_images
from .notes_api import generate_folder_scripts
# 注意：不能直接导入generate_all_audio，因为它是FastAPI路由函数
# from .tts_api import generate_all_audio
from ..utils.task_manager import task_manager, TaskStatus

# 导入PDF处理相关模块
import fitz  # PyMuPDF
from PIL import Image

# 设置日志
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflow", tags=["工作流程"])

# 工作流状态管理
workflow_tasks: Dict[str, dict] = {}

# 目录配置
BASE_DIR = Path(__file__).resolve().parent.parent.parent
PDF_DIR = BASE_DIR / "pdf_uploads"
IMG_DIR = BASE_DIR / "converted_images"

async def convert_pdf_to_images_internal(pdf_filename: str):
    """内部PDF转图片函数，用于工作流 - 基于PDF文件名"""
    # 检查PDF文件是否存在
    pdf_path = PDF_DIR / pdf_filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"PDF文件不存在: {pdf_filename}")
    
    try:
        doc = fitz.open(str(pdf_path))
        stem = pdf_path.stem  # PDF名字（不含扩展名）
        
        # 创建对应子目录
        output_subdir = IMG_DIR / stem
        output_subdir.mkdir(parents=True, exist_ok=True)
        
        saved_files = []
        total_pages = len(doc)
        
        if total_pages == 0:
            raise HTTPException(status_code=400, detail="PDF文件为空")
        
        logger.info(f"开始转换PDF: {pdf_filename}，共{total_pages}页")
        
        for i, page in enumerate(doc, start=1):
            # 生成图片ID
            image_id = str(i)
            img_path = output_subdir / f"{image_id}.png"
            
            # 转换页面为图片
            pix = page.get_pixmap(dpi=200)
            pix.save(str(img_path))
            
            saved_files.append({
                "image_id": image_id,
                "image_path": f"{stem}/{image_id}.png"
            })
            
            logger.info(f"转换完成页面 {i}/{total_pages}")
        
        doc.close()
        
        # 验证转换结果
        if not saved_files:
            raise HTTPException(status_code=500, detail="PDF转图片失败：没有生成任何图片")
        
        logger.info(f"PDF转图片完成: {pdf_filename}，生成{len(saved_files)}张图片")
        
        return {
            "message": f"PDF转图片完成，共生成 {len(saved_files)} 张图片",
            "total_pages": total_pages,
            "images": saved_files,
            "output_directory": str(output_subdir),
            "pdf_name": stem
        }
        
    except Exception as e:
        logger.error(f"PDF转图片失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"PDF转图片失败: {str(e)}")

async def add_black_borders_internal(pdf_name: str):
    """内部添加黑边函数，用于工作流 - 基于PDF名字"""
    # 目录配置
    PROCESSED_IMG_DIR = BASE_DIR / "processed_images"
    PROCESSED_IMG_DIR.mkdir(parents=True, exist_ok=True)
    
    # 检查源图片目录是否存在
    target_dir = IMG_DIR / pdf_name
    if not target_dir or not target_dir.exists():
        raise HTTPException(status_code=404, detail=f"源图片目录不存在: {target_dir}")
    
    # 检查目录中是否有图片
    png_files = list(target_dir.rglob("*.png"))
    if not png_files:
        raise HTTPException(status_code=404, detail=f"目录中没有找到PNG图片: {target_dir}")
    
    logger.info(f"开始为{len(png_files)}张图片添加黑边: {pdf_name}")
    
    # 处理图片添加黑边
    processed = []
    dst_dir = PROCESSED_IMG_DIR / pdf_name
    dst_dir.mkdir(parents=True, exist_ok=True)
    
    for src_path in png_files:
        try:
            rel_path = src_path.relative_to(target_dir)
            dst_path = dst_dir / rel_path
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 添加黑边
            img = Image.open(src_path)
            width, height = img.size
            top = bottom = 100  # 黑边高度
            new_height = height + top + bottom
            new_img = Image.new("RGB", (width, new_height), (0, 0, 0))
            new_img.paste(img, (0, top))
            new_img.save(dst_path)
            
            processed.append(f"{pdf_name}/{str(rel_path)}")
            logger.info(f"添加黑边完成: {src_path.name}")
            
        except Exception as e:
            logger.error(f"处理图片失败 {src_path}: {str(e)}")
            continue
    
    if not processed:
        raise HTTPException(status_code=500, detail="添加黑边失败：没有成功处理任何图片")
    
    logger.info(f"黑边添加完成: {pdf_name}，成功处理{len(processed)}张图片")
    
    return {
        "message": f"图片已加黑边，共处理 {len(processed)} 张",
        "processed_images": processed,
        "output_directory": str(dst_dir),
        "pdf_name": pdf_name
    }

async def generate_audio_internal(folder_name: str, gender: str = "male"):
    """内部音频生成函数，用于工作流 - 基于文件夹名，完全独立不依赖任何API"""
    import os
    from pathlib import Path
    
    logger.info(f"[内部TTS] 开始为文件夹 {folder_name} 生成音频，性别: {gender}")
    
    # 配置声音映射
    VOICE_MAPPING = {
        "male": "ja-JP-DaichiNeural",
        "female": "ja-JP-MayuNeural", 
        "chinese_female": "zh-CN-XiaoxiaoNeural"
    }
    
    # 验证性别参数
    if gender not in VOICE_MAPPING:
        raise HTTPException(status_code=400, detail="性别参数必须是 'male'、'female' 或 'chinese_female'")
    
    voice = VOICE_MAPPING[gender]
    
    # 目录配置 - 使用绝对路径
    base_dir = Path(__file__).resolve().parent.parent.parent
    notes_dir = base_dir / "notes_output" / folder_name
    output_dir = base_dir / "srt_and_wav" / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"[内部TTS] 脚本目录: {notes_dir}")
    logger.info(f"[内部TTS] 输出目录: {output_dir}")
    
    # 检查脚本目录是否存在
    if not notes_dir.exists() or not notes_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"脚本目录不存在: {notes_dir}")
    
    # 获取所有文本文件
    txt_files = list(notes_dir.glob("*.txt"))
    if not txt_files:
        raise HTTPException(status_code=404, detail=f"目录中没有找到脚本文件: {notes_dir}")
    
    # 排除合并文件
    txt_files = [f for f in txt_files if not f.name.endswith("_combined_scripts.txt")]
    txt_files.sort()
    
    logger.info(f"[内部TTS] 找到 {len(txt_files)} 个脚本文件")
    
    results = []
    
    # 导入TTS相关函数
    try:
        from ..tts.azure_toolkit import controlable_text_to_speech_with_subtitle
        from ..tts.srt_processer import process_srt
        from ..utils.mysql_config_helper import get_config_value
    except ImportError as e:
        logger.error(f"[内部TTS] 无法导入TTS模块: {str(e)}")
        raise HTTPException(status_code=500, detail=f"无法导入TTS模块: {str(e)}")
    
    # 获取Azure配置
    try:
        speech_key = get_config_value("speech_key")
        service_region = get_config_value("service_region")
        logger.info(f"[内部TTS] Azure配置获取成功")
    except Exception as e:
        logger.error(f"[内部TTS] 获取Azure配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取Azure配置失败: {str(e)}")
    
    if not speech_key or not service_region:
        raise HTTPException(status_code=500, detail="Azure Speech服务配置不完整")
    
    # 自定义停顿配置
    custom_breaks = {
        "。": "800ms",
        "、": "200ms",
        "，": "200ms",
        "？": "500ms",
        "！": "500ms",
        "\n": "500ms",
    }
    
    for i, txt_file in enumerate(txt_files, 1):
        try:
            logger.info(f"[内部TTS] 处理文件 {i}/{len(txt_files)}: {txt_file.name}")
            
            # 读取脚本内容
            with open(txt_file, "r", encoding="utf-8") as f:
                script_content = f.read().strip()
            
            # 清理脚本内容：去掉页面标记
            script_content = clean_script_content(script_content)
            
            if not script_content:
                logger.warning(f"[内部TTS] 脚本文件为空: {txt_file.name}")
                continue
            
            # 生成音频文件名
            base_name = txt_file.stem
            audio_file = output_dir / f"{base_name}.wav"
            pre_srt_file = output_dir / f"{base_name}_pre.srt"
            srt_file = output_dir / f"{base_name}_merged.srt"
            
            logger.info(f"[内部TTS] 开始TTS合成: {base_name}")
            
            # 使用Azure TTS生成音频和字幕
            success = controlable_text_to_speech_with_subtitle(
                speech_key=speech_key,
                service_region=service_region,
                text=script_content,
                audio_path=str(audio_file),
                srt_path=str(pre_srt_file),
                voice=voice,
                rate="-10%",
                punctuation_breaks=custom_breaks,
            )
            
            if success:
                logger.info(f"[内部TTS] TTS合成成功: {base_name}")
                
                # 处理字幕文件
                if pre_srt_file.exists():
                    logger.info(f"[内部TTS] 处理字幕文件: {base_name}")
                    process_srt(str(pre_srt_file), str(srt_file))
                    # 删除临时字幕文件
                    pre_srt_file.unlink(missing_ok=True)
                
                results.append({
                    "filename": txt_file.name,
                    "audio_file": audio_file.name,
                    "subtitle_file": srt_file.name,
                    "status": "success"
                })
                logger.info(f"[内部TTS] 成功生成音频: {audio_file.name}")
            else:
                logger.error(f"[内部TTS] TTS合成失败: {base_name}")
                results.append({
                    "filename": txt_file.name,
                    "audio_file": None,
                    "subtitle_file": None,
                    "status": "failed",
                    "error": "TTS引擎生成失败"
                })
                
        except Exception as e:
            logger.error(f"[内部TTS] 处理文件失败 {txt_file.name}: {str(e)}")
            results.append({
                "filename": txt_file.name,
                "audio_file": None,
                "subtitle_file": None,
                "status": "failed",
                "error": str(e)
            })
    
    # 统计结果
    audio_files = [r["audio_file"] for r in results if r["status"] == "success" and r["audio_file"]]
    subtitle_files = [r["subtitle_file"] for r in results if r["status"] == "success" and r["subtitle_file"]]
    
    if not audio_files:
        raise HTTPException(status_code=500, detail="音频生成失败：没有成功生成任何音频文件")
    
    logger.info(f"[内部TTS] 音频生成完成: {folder_name}，成功生成{len(audio_files)}个音频文件")
    
    return {
        "audio_files": audio_files,
        "subtitle_files": subtitle_files,
        "results": results,
        "output_directory": str(output_dir)
    }

def clean_script_content(content: str) -> str:
    """清理脚本内容，去掉页面标记和多余的格式"""
    import re
    
    # 去掉开头的 "Page X:" 或 "页面 X:" 标记
    content = re.sub(r'^Page\s+\d+:\s*', '', content, flags=re.IGNORECASE | re.MULTILINE)
    content = re.sub(r'^页面\s*\d+:\s*', '', content, flags=re.MULTILINE)
    
    # 去掉开头的数字标记，如 "1." "2." 等
    content = re.sub(r'^\d+\.\s*', '', content, flags=re.MULTILINE)
    
    # 去掉多余的换行符，但保留段落间的空行
    content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
    
    # 去掉行首行尾的空白字符
    lines = [line.strip() for line in content.split('\n') if line.strip()]
    content = '\n'.join(lines)
    
    # 将换行符替换为空格，使其适合TTS
    content = content.replace('\n', ' ')
    
    # 去掉多余的空格
    content = re.sub(r'\s+', ' ', content)
    
    return content.strip()

class WorkflowRequest(BaseModel):
    api_key: str = Field(..., description="AI生成脚本所需的API密钥")
    prompt: Optional[str] = Field(None, description="自定义脚本生成提示词")
    gender: str = Field("male", description="TTS声音性别：male(日语男声)、female(日语女声)、chinese_female(中文女声)")
    
    class Config:
        schema_extra = {
            "example": {
                "api_key": "your_api_key_here",
                "prompt": "请为这张IT课程幻灯片生成详细的讲解脚本",
                "gender": "male"
            }
        }

class WorkflowResponse(BaseModel):
    message: str = Field(..., description="工作流启动消息")
    workflow_id: str = Field(..., description="工作流ID，用于查询进度")
    task_id: str = Field(..., description="主任务ID")
    original_filename: str = Field(..., description="原始PPT文件名")
    steps: Dict[str, str] = Field(..., description="工作流步骤说明")
    
    class Config:
        schema_extra = {
            "example": {
                "message": "PPT到视频工作流已启动",
                "workflow_id": "workflow_12345678",
                "task_id": "12345678-1234-5678-1234-567812345678",
                "original_filename": "presentation.pptx",
                "steps": {
                    "step1": "PPT转PDF",
                    "step2": "PDF转图片", 
                    "step3": "添加黑边",
                    "step4": "生成脚本",
                    "step5": "生成音频"
                }
            }
        }

class WorkflowStatusResponse(BaseModel):
    workflow_id: str = Field(..., description="工作流ID")
    status: str = Field(..., description="当前状态：running, completed, failed")
    current_step: int = Field(..., description="当前步骤(1-5)")
    current_step_name: str = Field(..., description="当前步骤名称")
    progress: int = Field(..., description="总体进度百分比")
    step_progress: int = Field(..., description="当前步骤进度百分比")
    message: str = Field(..., description="状态消息")
    error: Optional[str] = Field(None, description="错误信息")
    results: Optional[Dict[str, Any]] = Field(None, description="最终结果")

@router.post(
    "/ppt-to-video",
    summary="PPT到视频完整工作流",
    description="""
    一次性执行PPT到视频制作的完整工作流程：
    
    步骤1: 上传PPT并转换为PDF
    步骤2: PDF转换为图片
    步骤3: 为图片添加黑色边框
    步骤4: 生成讲解脚本
    步骤5: 生成音频和字幕
    
    工作流在后台异步执行，返回workflow_id用于查询进度。
    """,
    response_model=WorkflowResponse
)
async def create_ppt_to_video_workflow(
    file: UploadFile = File(..., description="PPT或PPTX文件"),
    api_key: str = Form(..., description="AI生成脚本所需的API密钥"),
    prompt: str = Form(None, description="自定义脚本生成提示词"),
    gender: str = Form("male", description="TTS声音性别：male、female、chinese_female"),
    background_tasks: BackgroundTasks = None
):
    """创建PPT到视频的完整工作流"""
    
    # 验证文件格式
    if not (file.filename.endswith(".pptx") or file.filename.endswith(".ppt")):
        raise HTTPException(status_code=400, detail="只支持 PPT 和 PPTX 文件")
    
    # 验证性别参数
    if gender not in ["male", "female", "chinese_female"]:
        raise HTTPException(status_code=400, detail="性别参数必须是 'male'、'female' 或 'chinese_female'")
    
    # 生成工作流ID
    workflow_id = f"workflow_{int(time.time())}"
    
    # 初始化工作流状态
    workflow_tasks[workflow_id] = {
        "status": "initializing",
        "current_step": 0,
        "current_step_name": "初始化",
        "progress": 0,
        "step_progress": 0,
        "message": "工作流初始化中...",
        "created_at": datetime.now().isoformat(),
        "file_name": file.filename,
        "api_key": api_key,
        "prompt": prompt,
        "gender": gender,
        "results": {}
    }
    
    logger.info(f"创建工作流: {workflow_id}, 文件: {file.filename}")
    
    # 在后台执行工作流
    if background_tasks:
        background_tasks.add_task(execute_workflow, workflow_id, file, api_key, prompt, gender)
    else:
        # 同步执行（用于测试）
        asyncio.create_task(execute_workflow(workflow_id, file, api_key, prompt, gender))
    
    return {
        "message": "PPT到视频工作流已启动",
        "workflow_id": workflow_id,
        "task_id": "",  # 将在执行过程中更新
        "original_filename": file.filename,
        "steps": {
            "step1": "PPT转PDF",
            "step2": "PDF转图片", 
            "step3": "添加黑边",
            "step4": "生成脚本",
            "step5": "生成音频"
        }
    }

async def execute_workflow(workflow_id: str, file: UploadFile, api_key: str, prompt: str, gender: str):
    """执行完整的工作流程"""
    try:
        # 更新状态为运行中
        update_workflow_status(workflow_id, "running", 1, "PPT转PDF", 0, "开始上传PPT并转换为PDF...")
        
        # 步骤1: 上传PPT并转换为PDF
        logger.info(f"[{workflow_id}] 开始步骤1: PPT转PDF")
        
        # 重置文件指针到开始位置
        await file.seek(0)
        
        step1_result = await upload_ppt_convert_pdf(file)
        task_id = step1_result["task_id"]
        
        # 更新工作流状态
        workflow_tasks[workflow_id]["task_id"] = task_id
        workflow_tasks[workflow_id]["results"]["step1"] = step1_result
        
        update_workflow_status(workflow_id, "running", 1, "PPT转PDF", 100, "PPT转PDF完成")
        logger.info(f"[{workflow_id}] 步骤1完成: {step1_result}")
        
        # 步骤2: PDF转图片
        update_workflow_status(workflow_id, "running", 2, "PDF转图片", 0, "开始将PDF转换为图片...")
        logger.info(f"[{workflow_id}] 开始步骤2: PDF转图片")
        
        # 获取PDF文件名
        pdf_filename = step1_result["pdf_filename"]
        
        # 调用内部转换函数（基于PDF文件名）
        step2_result = await convert_pdf_to_images_internal(pdf_filename)
        workflow_tasks[workflow_id]["results"]["step2"] = step2_result
        update_workflow_status(workflow_id, "running", 2, "PDF转图片", 100, f"PDF转图片完成，生成{step2_result['total_pages']}张图片")
        logger.info(f"[{workflow_id}] 步骤2完成: 生成{step2_result['total_pages']}张图片")
        
        # 验证步骤2是否成功
        if not step2_result.get("images") or step2_result.get("total_pages", 0) == 0:
            raise HTTPException(status_code=500, detail="步骤2失败：PDF转图片未成功生成图片")
        
        # 步骤3: 添加黑边
        update_workflow_status(workflow_id, "running", 3, "添加黑边", 0, "开始为图片添加黑色边框...")
        logger.info(f"[{workflow_id}] 开始步骤3: 添加黑边")
        
        # 获取PDF名字（不含扩展名）
        pdf_name = step2_result["pdf_name"]
        
        # 调用内部黑边函数（基于PDF名字）
        step3_result = await add_black_borders_internal(pdf_name)
        workflow_tasks[workflow_id]["results"]["step3"] = step3_result
        update_workflow_status(workflow_id, "running", 3, "添加黑边", 100, f"图片黑边添加完成，处理{len(step3_result['processed_images'])}张图片")
        logger.info(f"[{workflow_id}] 步骤3完成: 处理{len(step3_result['processed_images'])}张图片")
        
        # 验证步骤3是否成功
        if not step3_result.get("processed_images"):
            raise HTTPException(status_code=500, detail="步骤3失败：添加黑边未成功处理任何图片")
        
        # 步骤4: 生成脚本
        update_workflow_status(workflow_id, "running", 4, "生成脚本", 0, "开始生成讲解脚本...")
        logger.info(f"[{workflow_id}] 开始步骤4: 生成脚本")
        
        # 获取文件夹名称（使用步骤3成功处理的PDF名字）
        folder_name = pdf_name
        
        # 使用processed_images目录（步骤3的输出）
        step4_result = await generate_folder_scripts(
            folder_name=folder_name,
            api_key=api_key,
            prompt=prompt
        )
        workflow_tasks[workflow_id]["results"]["step4"] = step4_result
        
        # 验证步骤4是否成功
        if not step4_result.get("processed_images") or step4_result.get("processed_images", 0) == 0:
            raise HTTPException(status_code=500, detail="步骤4失败：脚本生成未成功处理任何图片")
        
        update_workflow_status(workflow_id, "running", 4, "生成脚本", 100, f"讲解脚本生成完成，处理{step4_result['processed_images']}张图片")
        logger.info(f"[{workflow_id}] 步骤4完成: 生成了{step4_result['processed_images']}个脚本")
        
        # 步骤5: 生成音频
        update_workflow_status(workflow_id, "running", 5, "生成音频", 0, "开始生成音频和字幕...")
        logger.info(f"[{workflow_id}] 开始步骤5: 生成音频")
        
        # 使用内部音频生成函数（基于文件夹名）
        step5_result = await generate_audio_internal(
            folder_name=folder_name,
            gender=gender
        )
        workflow_tasks[workflow_id]["results"]["step5"] = step5_result
        
        # 验证步骤5是否成功
        if not step5_result.get("audio_files") or len(step5_result.get("audio_files", [])) == 0:
            raise HTTPException(status_code=500, detail="步骤5失败：音频生成未成功生成任何音频文件")
        
        update_workflow_status(workflow_id, "completed", 5, "生成音频", 100, f"工作流完成！生成{len(step5_result['audio_files'])}个音频文件")
        logger.info(f"[{workflow_id}] 步骤5完成: 生成了{len(step5_result['audio_files'])}个音频文件")
        
        # 最终完成状态
        workflow_tasks[workflow_id]["completed_at"] = datetime.now().isoformat()
        workflow_tasks[workflow_id]["final_results"] = {
            "ppt_file": file.filename,
            "pdf_file": step1_result["pdf_filename"],
            "images_processed": step3_result["processed_images"],
            "scripts_generated": step4_result["processed_images"],
            "audio_files": step5_result["audio_files"],
            "subtitle_files": step5_result["subtitle_files"],
            "output_directory": step4_result["output_directory"],
            "combined_script_file": step4_result["combined_script_file"]
        }
        
        logger.info(f"[{workflow_id}] 工作流完成！")
        
    except Exception as e:
        error_msg = f"工作流执行失败: {str(e)}"
        logger.error(f"[{workflow_id}] {error_msg}")
        
        update_workflow_status(
            workflow_id, 
            "failed", 
            workflow_tasks[workflow_id]["current_step"], 
            workflow_tasks[workflow_id]["current_step_name"], 
            0, 
            error_msg,
            str(e)
        )

def update_workflow_status(
    workflow_id: str, 
    status: str, 
    current_step: int, 
    step_name: str, 
    step_progress: int, 
    message: str,
    error: str = None
):
    """更新工作流状态"""
    if workflow_id not in workflow_tasks:
        return
    
    # 计算总体进度
    total_progress = ((current_step - 1) * 100 + step_progress) // 5
    
    workflow_tasks[workflow_id].update({
        "status": status,
        "current_step": current_step,
        "current_step_name": step_name,
        "progress": total_progress,
        "step_progress": step_progress,
        "message": message,
        "updated_at": datetime.now().isoformat()
    })
    
    if error:
        workflow_tasks[workflow_id]["error"] = error

@router.get(
    "/status/{workflow_id}",
    summary="查询工作流状态",
    description="根据workflow_id查询工作流的执行状态和进度",
    response_model=WorkflowStatusResponse
)
async def get_workflow_status(workflow_id: str):
    """查询工作流状态"""
    if workflow_id not in workflow_tasks:
        raise HTTPException(status_code=404, detail="工作流不存在")
    
    task_info = workflow_tasks[workflow_id]
    
    return {
        "workflow_id": workflow_id,
        "status": task_info["status"],
        "current_step": task_info["current_step"],
        "current_step_name": task_info["current_step_name"],
        "progress": task_info["progress"],
        "step_progress": task_info["step_progress"],
        "message": task_info["message"],
        "error": task_info.get("error"),
        "results": task_info.get("final_results")
    }

@router.get(
    "/list",
    summary="获取所有工作流",
    description="获取所有工作流的列表和状态"
)
async def list_workflows():
    """获取所有工作流列表"""
    workflows = []
    for workflow_id, task_info in workflow_tasks.items():
        workflows.append({
            "workflow_id": workflow_id,
            "status": task_info["status"],
            "file_name": task_info["file_name"],
            "current_step": task_info["current_step"],
            "progress": task_info["progress"],
            "created_at": task_info["created_at"],
            "message": task_info["message"]
        })
    
    return {"workflows": workflows}

@router.delete(
    "/{workflow_id}",
    summary="删除工作流记录",
    description="删除指定的工作流记录"
)
async def delete_workflow(workflow_id: str):
    """删除工作流记录"""
    if workflow_id not in workflow_tasks:
        raise HTTPException(status_code=404, detail="工作流不存在")
    
    del workflow_tasks[workflow_id]
    
    return {"message": f"工作流 {workflow_id} 已删除"}

@router.get(
    "/results/{workflow_id}",
    summary="获取工作流详细结果",
    description="获取工作流的详细执行结果"
)
async def get_workflow_results(workflow_id: str):
    """获取工作流详细结果"""
    if workflow_id not in workflow_tasks:
        raise HTTPException(status_code=404, detail="工作流不存在")
    
    task_info = workflow_tasks[workflow_id]
    
    if task_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="工作流尚未完成")
    
    return {
        "workflow_id": workflow_id,
        "status": task_info["status"],
        "file_name": task_info["file_name"],
        "created_at": task_info["created_at"],
        "completed_at": task_info.get("completed_at"),
        "results": task_info["results"],
        "final_results": task_info.get("final_results")
    }
