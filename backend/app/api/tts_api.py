from fastapi.responses import JSONResponse, StreamingResponse
from fastapi import APIRouter, HTTPException, Query, Body, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from pathlib import Path
from app.utils.mysql_config_helper import get_config_value, set_config_value
import os
from app.tts.tts_engine import tts, find_txt_files
from app.utils.task_manager import task_manager

AUDIO_OUTPUT_DIR = "./srt_and_wav"
NOTES_DIR = "./notes_output"
router = APIRouter(prefix="/api/tts", tags=["TTS配置"])

class ConfigItem(BaseModel):
    key: str
    value: str

class SingleTTSRequest(BaseModel):
    filename: str  # 例如 "lesson01.txt"

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
    set_config_value("voice", voice)
    return {"message": "voice已更新", "voice": voice}

@router.post("/generate")
def generate_all_audio(
    task_id: str = Query(None, description="任务ID"),
    filename: str = Query(None, description="文件名/目录名")
):
    notes_dir = Path(NOTES_DIR)
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
    if subdir:
        notes_dir = notes_dir / subdir
        output_dir = Path(AUDIO_OUTPUT_DIR) / subdir
        output_dir.mkdir(parents=True, exist_ok=True)
        if not notes_dir.exists() or not notes_dir.is_dir():
            raise HTTPException(status_code=404, detail="任务文稿目录不存在")
        raw_txt = [f for f in notes_dir.glob("*.txt")]
    else:
        output_dir = Path(AUDIO_OUTPUT_DIR)
        raw_txt = find_txt_files(NOTES_DIR)
    raw_txt.sort()
    for path in raw_txt:
        try:
            tts(path, output_dir=str(output_dir))
        except Exception as e:
            print(f"[错误] 处理文件 {path} 时出错: {e}")
    files = os.listdir(output_dir)
    audio_files = [f for f in files if f.endswith(".wav")]
    srt_files = [f for f in files if f.endswith("_merged.srt")]
    return {
        "audio_files": audio_files,
        "subtitle_files": srt_files
    }

@router.websocket("/ws/generate/{task_id}")
async def ws_generate_all_audio(websocket: WebSocket, task_id: str):
    await websocket.accept()
    try:
        task = task_manager.get_task(task_id)
        if not task:
            await websocket.send_json({"error": "任务不存在"})
            await websocket.close()
            return
        if task["type"] == "pdf_upload":
            pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
        elif task["type"] == "pdf_to_images":
            pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
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
        raw_txt = [f for f in notes_dir.glob("*.txt")]
        raw_txt.sort()
        total = len(raw_txt)
        if total == 0:
            await websocket.send_json({"error": "没有可处理的文件"})
            await websocket.close()
            return
        for idx, path in enumerate(raw_txt, 1):
            try:
                tts(path, output_dir=str(output_dir))
                wav_name = path.stem + ".wav"
                srt_name = path.stem + "_merged.srt"
                audio_path = output_dir / wav_name
                srt_path = output_dir / srt_name
                result = {
                    "filename": path.name,
                    "audio_file": audio_path.name if audio_path.exists() else None,
                    "subtitle_file": srt_path.name if srt_path.exists() else None,
                    "status": "success",
                    "progress": int(idx / total * 100)
                }
            except Exception as e:
                result = {
                    "filename": path.name,
                    "audio_file": None,
                    "subtitle_file": None,
                    "status": "failed",
                    "error": str(e),
                    "progress": int(idx / total * 100)
                }
            await websocket.send_json(result)
        await websocket.close()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"error": str(e)})
        await websocket.close()

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

# @router.post("/generate-one")
# def generate_single_audio(data: SingleTTSRequest):
#     txt_path = Path(NOTES_DIR) / data.filename

#     if not txt_path.exists() or txt_path.suffix != ".txt":
#         raise HTTPException(status_code=400, detail="指定的 TXT 文件不存在")

#     try:
#         tts(txt_path, output_dir=AUDIO_OUTPUT_DIR)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"TTS 处理失败: {str(e)}")

#     wav_name = txt_path.stem + ".wav"
#     srt_name = txt_path.stem + "_merged.srt"

#     audio_path = Path(AUDIO_OUTPUT_DIR) / wav_name
#     srt_path = Path(AUDIO_OUTPUT_DIR) / srt_name

#     return {
#         "audio_file": audio_path.name if audio_path.exists() else None,
#         "subtitle_file": srt_path.name if srt_path.exists() else None,
#         "status": "success"
#     }

@router.post("/generate-selected")
def generate_selected_audio(
    task_id: str = Query(..., description="任务ID"),
    filenames: list = Body(..., embed=True, description="要生成的txt文件名列表")
):
    """
    批量生成选中的txt文件的音频和字幕，流式返回进度和结果。
    """
    import json
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task["type"] == "pdf_upload":
        pdf_name = task["data"].get("original_filename", "").rsplit(".", 1)[0]
    elif task["type"] == "pdf_to_images":
        pdf_name = task["data"].get("pdf_filename", "").rsplit(".", 1)[0]
    else:
        raise HTTPException(status_code=400, detail="不支持的任务类型")
    notes_dir = Path(NOTES_DIR) / pdf_name
    output_dir = Path(AUDIO_OUTPUT_DIR) / pdf_name
    output_dir.mkdir(parents=True, exist_ok=True)
    if not notes_dir.exists() or not notes_dir.is_dir():
        raise HTTPException(status_code=404, detail="任务文稿目录不存在")
    selected_files = [notes_dir / f for f in filenames if (notes_dir / f).exists() and f.endswith('.txt')]
    total = len(selected_files)
    if total == 0:
        raise HTTPException(status_code=400, detail="没有可处理的文件")
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
            except Exception as e:
                result = {
                    "filename": txt_path.name,
                    "audio_file": None,
                    "subtitle_file": None,
                    "status": "failed",
                    "error": str(e),
                    "progress": int(idx / total * 100)
                }
            yield json.dumps(result).encode() + b"\n"
    return StreamingResponse(generate(), media_type="application/x-ndjson")

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
            except Exception as e:
                result = {
                    "filename": txt_path.name,
                    "audio_file": None,
                    "subtitle_file": None,
                    "status": "failed",
                    "error": str(e),
                    "progress": int(idx / total * 100)
                }
            await websocket.send_json(result)
        await websocket.close()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"error": str(e)})
        await websocket.close()

