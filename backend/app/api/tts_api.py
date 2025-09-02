from fastapi.responses import JSONResponse, StreamingResponse
from fastapi import APIRouter, HTTPException, Query, Body, WebSocket, WebSocketDisconnect,BackgroundTasks
from pydantic import BaseModel, Field
from pathlib import Path
from app.utils.mysql_config_helper import get_config_value, set_config_value
import os
from app.tts.tts_engine import tts, find_txt_files
from app.utils.task_manager_memory import task_manager
from typing import Dict, List
import logging
import json

AUDIO_OUTPUT_DIR = "./srt_and_wav"
NOTES_DIR = "./notes_output"
router = APIRouter(prefix="/api/tts", tags=["TTS配置"])

# 性别与声音的映射
VOICE_MAPPING = {
    "male": "ja-JP-DaichiNeural",    # 日语男声
    "female": "ja-JP-MayuNeural",    # 日语女声
    "chinese_female": "zh-CN-XiaoxiaoNeural"    # 中文女声
}

tts_tasks: Dict[str, dict] = {}
tts_tasks_by_filename: Dict[str, dict] = {}

# 配置日志
logging.basicConfig(level=logging.INFO)

class ConfigItem(BaseModel):
    key: str
    value: str

class SingleTTSRequest(BaseModel):
    filename: str  # 例如 "lesson01.txt"

class GenerateAudioRequest(BaseModel):
    task_id: str = Field(None, description="任务ID")
    filename: str = Field(None, description="文件名/目录名")
    gender: str = Field("male", description="声音性别：male(日语男声) 或 female(日语女声) 或 chinese_female(中文女声)")
    
    class Config:
        schema_extra = {
            "example": {
                "task_id": "12345678-1234-5678-1234-567812345678",
                "gender": "chinese_female"
            }
        }

class GenerateAudioResponse(BaseModel):
    audio_files: List[str] = Field(..., description="生成的音频文件列表")
    subtitle_files: List[str] = Field(..., description="生成的字幕文件列表")
    results: List[dict] = Field(..., description="详细处理结果")
    
    class Config:
        schema_extra = {
            "example": {
                "audio_files": ["1.wav", "2.wav"],
                "subtitle_files": ["1_merged.srt", "2_merged.srt"],
                "results": [
                    {
                        "filename": "1.txt",
                        "audio_file": "1.wav",
                        "subtitle_file": "1_merged.srt",
                        "status": "success"
                    }
                ]
            }
        }

@router.get("/texts")
def list_txt_files(
    task_id: str = Query(None, description="任务ID"),
    filename: str = Query(None, description="文件名/目录名")
):
    notes_dir = Path(NOTES_DIR)
    subdir = None
    if task_id:
        task = task_manager.get_task(task_id)
        if not task:
            return []
        if task["type"] == "pdf_upload":
            subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            subdir = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_upload":
            subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        else:
            return []
    elif filename:
        subdir = filename
    if subdir:
        target_dir = notes_dir / subdir
        if target_dir.exists() and target_dir.is_dir():
            files = [f.name for f in target_dir.glob("*.txt")]
        else:
            files = []
    else:
        files = [f for f in os.listdir(notes_dir) if f.endswith(".txt")]
    return files

@router.post("/set-config")
def set_config(item: ConfigItem):
    set_config_value(item.key, item.value)
    return {"message": "配置已更新", "key": item.key, "value": item.value}

@router.get("/get-config/{key}")
def get_config(key: str):
    value = get_config_value(key, default="未设置")
    return {"key": key, "value": value}

@router.post("/set-voice")
def set_voice(voice: str = Body(..., embed=True)):
    # 使用男生声音 Daichi
    fixed_voice = "ja-JP-DaichiNeural"
    set_config_value("voice", fixed_voice)
    return {"message": "声音已设置为男生Daichi", "voice": fixed_voice}

@router.post(
    "/generate",
    tags=["视频制作工作流程"],
    summary="步骤5: 生成所有音频",
    description="""
    将步骤4生成的脚本转换为音频文件。
    
    输入:
    - task_id: 从步骤1获得的任务ID (优先使用)
    - filename: 文件夹名称 (可选，与task_id二选一)
    - gender: 声音性别选择，可选值：
      * male: 日语男声 (默认)
      * female: 日语女声
      * chinese_female: 中文女声
    
    处理流程:
    1. 读取notes_output目录下的脚本文件
    2. 使用TTS引擎将文本转换为语音
    3. 生成对应的字幕文件
    
    返回:
    - 生成的音频和字幕文件列表
    - 详细的处理结果
    """,
    response_model=GenerateAudioResponse
)
async def generate_all_audio(
    task_id: str = Query(None, description="任务ID"),
    filename: str = Query(None, description="文件名/目录名"),
    gender: str = Query("male", description="声音性别：male(日语男声) 或 female(日语女声) 或 chinese_female(中文女声)")
):
    """
    生成所有音频和字幕，支持task_id和filename双入口。
    优先使用task_id，若没有则使用filename。
    新增gender参数控制男声或女声。
    """
    # 验证性别参数
    if gender not in VOICE_MAPPING:
        raise HTTPException(status_code=400, detail="性别参数必须是 'male'(日语男声)、'female'(日语女声) 或 'chinese_female'(中文女声)")
    
    # 设置对应的声音
    voice = VOICE_MAPPING[gender]
    
    logging.info(f"🚀 开始执行 generate_all_audio, task_id: {task_id}, filename: {filename}, gender: {gender}, voice: {voice}")
    
    notes_dir = Path(NOTES_DIR)
    subdir = None
    if task_id:
        logging.info(f"🔍 查找任务: {task_id}")
        task = task_manager.get_task(task_id)
        if not task:
            logging.error(f"❌ 任务不存在: {task_id}")
            raise HTTPException(status_code=404, detail="任务不存在")
        if task["type"] == "pdf_upload":
            subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            subdir = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_upload":
            subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        else:
            logging.error(f"❌ 不支持的任务类型: {task['type']}")
            raise HTTPException(status_code=400, detail="不支持的任务类型")
        logging.info(f"📁 找到子目录: {subdir}")
    elif filename:
        subdir = filename
        logging.info(f"📁 使用提供的目录名: {subdir}")
    
    if subdir:
        notes_dir = notes_dir / subdir
        output_dir = Path(AUDIO_OUTPUT_DIR) / subdir
        output_dir.mkdir(parents=True, exist_ok=True)
        logging.info(f"📂 创建输出目录: {output_dir}")
        if not notes_dir.exists() or not notes_dir.is_dir():
            logging.error(f"❌ 任务文稿目录不存在: {notes_dir}")
            raise HTTPException(status_code=404, detail="任务文稿目录不存在")
        raw_txt = [f for f in notes_dir.glob("*.txt")]
    else:
        output_dir = Path(AUDIO_OUTPUT_DIR)
        raw_txt = find_txt_files(NOTES_DIR)
    
    raw_txt.sort()
    logging.info(f"📝 找到 {len(raw_txt)} 个文本文件")
    
    results = []
    total = len(raw_txt)
    for idx, path in enumerate(raw_txt, 1):
        logging.info(f"🔄 开始处理第 {idx}/{total} 个文件: {path.name}")
        try:
            logging.info(f"🎵 开始生成音频: {path.name}, 使用声音: {voice}")
            tts(path, output_dir=str(output_dir), voice=voice)
            wav_name = path.stem + ".wav"
            srt_name = path.stem + "_merged.srt"
            audio_path = output_dir / wav_name
            srt_path = output_dir / srt_name
            
            result = {
                "filename": path.name,
                "audio_file": audio_path.name if audio_path.exists() else None,
                "subtitle_file": srt_path.name if srt_path.exists() else None,
                "status": "success"
            }
            results.append(result)
            logging.info(f"✅ 成功生成音频: {path.name}")
            
            # 构造进度信息
            progress_info = {
                "status": "processing" if idx < total else "completed",
                "progress": int(idx / total * 100),
                "current": idx,
                "total": total,
                "current_file": path.name,
                "results": results.copy()
            }
            # 实时写入 tts_tasks
            if task_id:
                tts_tasks[task_id] = progress_info
                logging.info(f"📊 更新任务进度: {task_id} - {int(idx / total * 100)}%")
            # 实时写入 tts_tasks_by_filename
            if filename:
                tts_tasks_by_filename[filename] = progress_info
                logging.info(f"📊 [by_filename] 当前进度: {progress_info}")
        except Exception as e:
            logging.error(f"❌ 处理文件失败: {path.name}, 错误: {str(e)}")
            result = {
                "filename": path.name,
                "audio_file": None,
                "subtitle_file": None,
                "status": "failed",
                "error": str(e)
            }
            results.append(result)
            # 构造失败进度
            progress_info = {
                "status": "failed",
                "error": str(e),
                "current": idx,
                "total": total,
                "current_file": path.name,
                "results": results.copy()
            }
            if task_id:
                tts_tasks[task_id] = progress_info
                logging.error(f"❌ 更新任务状态为失败: {task_id}")
            if filename:
                tts_tasks_by_filename[filename] = json.loads(json.dumps(progress_info))
                logging.error(f"❌ [by_filename] 当前进度: {progress_info}")
    # 处理完成后写入最终状态
    if task_id:
        tts_tasks[task_id] = {
            "status": "completed",
            "progress": 100,
            "total": total,
            "results": results
        }
        logging.info(f"🎉 任务完成: {task_id}")
    if filename:
        tts_tasks_by_filename[filename] = {
            "status": "completed",
            "progress": 100,
            "total": total,
            "results": results
        }
        logging.info(f"🎉 [by_filename] 任务完成: {filename}")
    files = os.listdir(output_dir)
    audio_files = [f for f in files if f.endswith(".wav")]
    srt_files = [f for f in files if f.endswith("_merged.srt")]
    logging.info(f"📊 最终统计 - 音频文件: {len(audio_files)}, 字幕文件: {len(srt_files)}")
    return {
        "audio_files": audio_files,
        "subtitle_files": srt_files,
        "results": results
    }

@router.websocket("/ws/generate")
async def ws_generate_all_audio(websocket: WebSocket):
    await websocket.accept()
    import asyncio
    try:
        await websocket.send_json({"status": "connected", "message": "WebSocket 连接成功"})
        last_status_by_filename = {}
        while True:
            if tts_tasks_by_filename:
                for filename, status in tts_tasks_by_filename.items():
                    status_str = json.dumps(status, sort_keys=True, ensure_ascii=False)
                    if last_status_by_filename.get(filename) != status_str:
                        import logging
                        logging.info(f"[WS] 检测到 {filename} 进度变化，推送: {status_str}")
                        await websocket.send_json({"type": "filename", "filename": filename, "progress": status})
                        last_status_by_filename[filename] = status_str
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"status": "error", "message": str(e)})
        await websocket.close()

async def generate_all_audio_with_ws(websocket, task_id, filename):
    import asyncio
    import logging
    notes_dir = Path(NOTES_DIR)
    subdir = None
    logging.info(f"[WS] 进入 generate_all_audio_with_ws, task_id={task_id}, filename={filename}")
    if task_id:
        logging.info(f"[WS] 查找任务: {task_id}")
        task = task_manager.get_task(task_id)
        if not task:
            logging.error(f"[WS] 任务不存在: {task_id}")
            await websocket.send_json({"error": "任务不存在"})
            return
        if task["type"] == "pdf_upload":
            subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            subdir = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_upload":
            subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        else:
            logging.error(f"[WS] 不支持的任务类型: {task['type']}")
            await websocket.send_json({"error": "不支持的任务类型"})
            return
        logging.info(f"[WS] 任务子目录: {subdir}")
    elif filename:
        subdir = filename
        logging.info(f"[WS] 使用 filename 作为子目录: {subdir}")

    if subdir:
        notes_dir = notes_dir / subdir
        output_dir = Path(AUDIO_OUTPUT_DIR) / subdir
        output_dir.mkdir(parents=True, exist_ok=True)
        logging.info(f"[WS] notes_dir: {notes_dir}, output_dir: {output_dir}")
        if not notes_dir.exists() or not notes_dir.is_dir():
            logging.error(f"[WS] 任务文稿目录不存在: {notes_dir}")
            await websocket.send_json({"error": "任务文稿目录不存在"})
            return
        raw_txt = [f for f in notes_dir.glob("*.txt")]
    else:
        output_dir = Path(AUDIO_OUTPUT_DIR)
        raw_txt = find_txt_files(NOTES_DIR)
        logging.info(f"[WS] 未指定子目录，查找所有 txt 文件")

    raw_txt.sort()
    logging.info(f"[WS] 共找到 {len(raw_txt)} 个 txt 文件待处理")
    results = []
    total = len(raw_txt)
    for idx, path in enumerate(raw_txt, 1):
        logging.info(f"[WS] 开始处理第 {idx}/{total} 个文件: {path.name}")
        try:
            logging.info(f"[WS] 调用 tts 处理: {path}")
            tts(path, output_dir=str(output_dir))
            wav_name = path.stem + ".wav"
            srt_name = path.stem + "_merged.srt"
            audio_path = output_dir / wav_name
            srt_path = output_dir / srt_name
            result = {
                "filename": path.name,
                "audio_file": audio_path.name if audio_path.exists() else None,
                "subtitle_file": srt_path.name if srt_path.exists() else None,
                "status": "success"
            }
            results.append(result)
            progress_info = {
                "status": "processing" if idx < total else "completed",
                "progress": int(idx / total * 100),
                "current": idx,
                "total": total,
                "current_file": path.name,
                "results": results.copy()
            }
            logging.info(f"[WS] 推送进度: {progress_info}")
            await websocket.send_json({"progress": progress_info})
        except Exception as e:
            logging.error(f"[WS] 处理文件失败: {path.name}, 错误: {str(e)}")
            result = {
                "filename": path.name,
                "audio_file": None,
                "subtitle_file": None,
                "status": "failed",
                "error": str(e)
            }
            results.append(result)
            progress_info = {
                "status": "failed",
                "error": str(e),
                "current": idx,
                "total": total,
                "current_file": path.name,
                "results": results.copy()
            }
            logging.info(f"[WS] 推送失败进度: {progress_info}")
            await websocket.send_json({"progress": progress_info})
            break
        await asyncio.sleep(0.1)
    # 最终完成状态
    logging.info(f"[WS] 所有文件处理完成，推送最终状态")
    await websocket.send_json({"progress": {
        "status": "completed",
        "progress": 100,
        "total": total,
        "results": results
    }})

@router.get("/check-breaktime/all")
def check_all_merged_srt():
    if not os.path.exists(AUDIO_OUTPUT_DIR):
        return JSONResponse(status_code=500, content={"error": "字幕目录不存在"})

    results = []
    try:
        for filename in os.listdir(AUDIO_OUTPUT_DIR):
            if filename.endswith("_merged.srt"):
                srt_path = os.path.join(AUDIO_OUTPUT_DIR, filename)
                try:
                    with open(srt_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        has_breaktime = "breaktime" in content.lower()
                        results.append({
                            "filename": filename,
                            "has_breaktime": has_breaktime,
                            "message": "包含 breaktime" if has_breaktime else "不包含 breaktime"
                        })
                except Exception as e:
                    results.append({
                        "filename": filename,
                        "error": f"读取失败: {str(e)}"
                    })

        return {"results": results}
    
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"发生错误: {str(e)}"})


@router.post("/generate-selected")
def generate_selected_audio(
    task_id: str = Query(None, description="任务ID"),
    filename: str = Query(None, description="文件名/目录名"),
    filenames: list = Body(..., embed=True, description="要生成的txt文件名列表")
):
    """
    批量生成选中的txt文件的音频和字幕，流式返回进度和结果。
    支持task_id和filename双入口。
    优先使用task_id，若没有则使用filename。
    """
    import json
    subdir = None
    if task_id:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task["type"] == "pdf_upload":
            subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            subdir = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_upload":
            subdir = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        else:
            raise HTTPException(status_code=400, detail="不支持的任务类型")
    elif filename:
        subdir = filename
    else:
        raise HTTPException(status_code=400, detail="请提供task_id或filename参数")
    notes_dir = Path(NOTES_DIR) / subdir
    output_dir = Path(AUDIO_OUTPUT_DIR) / subdir
    output_dir.mkdir(parents=True, exist_ok=True)
    if not notes_dir.exists() or not notes_dir.is_dir():
        raise HTTPException(status_code=404, detail="任务文稿目录不存在")
    selected_files = [notes_dir / f for f in filenames if (notes_dir / f).exists() and f.endswith('.txt')]
    total = len(selected_files)
    if total == 0:
        raise HTTPException(status_code=400, detail="没有可处理的文件")
    results = []
    def generate():
        for idx, txt_path in enumerate(selected_files, 1):
            try:
                tts(txt_path, output_dir=str(output_dir))
                wav_name = txt_path.stem + ".wav"
                srt_name = txt_path.stem + "_merged.srt"
                audio_path = output_dir / wav_name
                srt_path = output_dir / srt_name
                result = {
                    "filename": txt_path.name,
                    "audio_file": audio_path.name if audio_path.exists() else None,
                    "subtitle_file": srt_path.name if srt_path.exists() else None,
                    "status": "success",
                    "progress": int(idx / total * 100)
                }
                # 实时写入全局进度
                if task_id:
                    tts_tasks[task_id] = {
                        "status": "processing" if idx < total else "completed",
                        "progress": int(idx / total * 100),
                        "current": idx,
                        "total": total,
                        "current_file": txt_path.name,
                        "results": results.copy()
                    }
                    logging.info("当前 tts_tasks 状态：%s", tts_tasks)
                    # 同时更新 tts_tasks_by_filename
                    if filename:
                        tts_tasks_by_filename[filename] = tts_tasks[task_id]
                        logging.info("当前 tts_tasks_by_filename 状态：%s", tts_tasks_by_filename)
                logging.info(f"✅ 成功生成音频: {txt_path.name}")
            except Exception as e:
                result = {
                    "filename": txt_path.name,
                    "audio_file": None,
                    "subtitle_file": None,
                    "status": "failed",
                    "error": str(e),
                    "progress": int(idx / total * 100)
                }
                # 实时写入全局进度
                if task_id:
                    tts_tasks[task_id] = {
                        "status": "failed",
                        "error": str(e)
                    }
                    logging.info("当前 tts_tasks 状态：%s", tts_tasks)
            results.append(result)
            yield json.dumps(result).encode() + b"\n"
        # 更新任务状态
        if task_id:
            task_data = task.get("data", {})
            task_data["tts_generate_selected"] = {
                "status": "completed",
                "progress": 100,
                "results": results
            }
            task_manager.update_task(task_id, data=task_data)
    return StreamingResponse(generate(), media_type="application/x-ndjson")

@router.post("/set-gender")
def set_gender(gender: str = Body(..., embed=True)):
    """
    设置TTS性别
    gender: "male"(日语男声)、"female"(日语女声) 或 "chinese_female"(中文女声)
    """
    if gender not in VOICE_MAPPING:
        raise HTTPException(status_code=400, detail="性别参数必须是 'male'(日语男声)、'female'(日语女声) 或 'chinese_female'(中文女声)")
    
    voice = VOICE_MAPPING[gender]
    set_config_value("voice", voice)
    
    gender_names = {
        "male": "日语男声",
        "female": "日语女声", 
        "chinese_female": "中文女声"
    }
    gender_name = gender_names.get(gender, "未知")
    return {
        "message": f"声音已设置为{gender_name}",
        "gender": gender,
        "voice": voice
    }

@router.get("/get-gender")
def get_gender():
    """
    获取当前TTS性别设置
    """
    current_voice = get_config_value("voice", "ja-JP-DaichiNeural")
    
    # 根据voice反向查找gender
    gender = "male"  # 默认
    for g, v in VOICE_MAPPING.items():
        if v == current_voice:
            gender = g
            break
    
    gender_names = {
        "male": "日语男声",
        "female": "日语女声", 
        "chinese_female": "中文女声"
    }
    gender_name = gender_names.get(gender, "未知")
    return {
        "gender": gender,
        "voice": current_voice,
        "gender_name": gender_name
    }

@router.websocket("/ws/generate-selected/{task_id}")
async def ws_generate_selected_audio(websocket: WebSocket, task_id: str):
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        filenames = data.get("filenames", [])
        if not isinstance(filenames, list) or not filenames:
            await websocket.send_json({"error": "请提供要生成的txt文件名列表"})
            await websocket.close()
            return
        task = task_manager.get_task(task_id)
        if not task:
            await websocket.send_json({"error": "任务不存在"})
            await websocket.close()
            return
        if task["type"] == "pdf_upload":
            pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "ppt_upload":
            pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        else:
            await websocket.send_json({"error": "不支持的任务类型"})
            await websocket.close()
            return
        notes_dir = Path(NOTES_DIR) / pdf_name
        output_dir = Path(AUDIO_OUTPUT_DIR) / pdf_name
        output_dir.mkdir(parents=True, exist_ok=True)
        if not notes_dir.exists() or not notes_dir.is_dir():
            await websocket.send_json({"error": "任务文稿目录不存在"})
            await websocket.close()
            return
        selected_files = [notes_dir / f for f in filenames if (notes_dir / f).exists() and f.endswith('.txt')]
        total = len(selected_files)
        if total == 0:
            await websocket.send_json({"error": "没有可处理的文件"})
            await websocket.close()
            return
        results = []
        for idx, txt_path in enumerate(selected_files, 1):
            try:
                tts(txt_path, output_dir=str(output_dir))
                wav_name = txt_path.stem + ".wav"
                srt_name = txt_path.stem + "_merged.srt"
                audio_path = output_dir / wav_name
                srt_path = output_dir / srt_name
                result = {
                    "filename": txt_path.name,
                    "audio_file": audio_path.name if audio_path.exists() else None,
                    "subtitle_file": srt_path.name if srt_path.exists() else None,
                    "status": "success",
                    "progress": int(idx / total * 100)
                }
                # 实时写入全局进度
                if task_id:
                    tts_tasks[task_id] = {
                        "status": "processing" if idx < total else "completed",
                        "progress": int(idx / total * 100),
                        "current": idx,
                        "total": total,
                        "current_file": txt_path.name,
                        "results": results.copy()
                    }
                    logging.info("当前 tts_tasks 状态：%s", tts_tasks)
                    # 同时更新 tts_tasks_by_filename
                    if pdf_name:
                        tts_tasks_by_filename[pdf_name] = tts_tasks[task_id]
                        logging.info("当前 tts_tasks_by_filename 状态：%s", tts_tasks_by_filename)
                logging.info(f"✅ 成功生成音频: {txt_path.name}")
            except Exception as e:
                result = {
                    "filename": txt_path.name,
                    "audio_file": None,
                    "subtitle_file": None,
                    "status": "failed",
                    "error": str(e),
                    "progress": int(idx / total * 100)
                }
                # 实时写入全局进度
                if task_id:
                    tts_tasks[task_id] = {
                        "status": "failed",
                        "error": str(e)
                    }
                    logging.info("当前 tts_tasks 状态：%s", tts_tasks)
            results.append(result)
            logging.info(f"📤 推送中: {result}")
            await websocket.send_json(result)
        # 更新任务状态
        task_data = task.get("data", {})
        task_data["tts_generate_selected"] = {
            "status": "completed",
            "progress": 100,
            "results": results
        }
        task_manager.update_task(task_id, data=task_data)
        await websocket.close()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"error": str(e)})
        await websocket.close()

