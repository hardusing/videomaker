from fastapi.responses import JSONResponse
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
from app.utils.mysql_config_helper import get_config_value, set_config_value
import os
from app.tts.tts_engine import tts, find_txt_files

AUDIO_OUTPUT_DIR = "./srt_and_wav"
NOTES_DIR = "./notes_output"
router = APIRouter(prefix="/api/tts", tags=["TTS配置"])

class ConfigItem(BaseModel):
    key: str
    value: str

class SingleTTSRequest(BaseModel):
    filename: str  # 例如 "lesson01.txt"

print("📦 正在加载 tts_api.py")

@router.get("/texts")
def list_txt_files():
    """获取所有可用的文本文件列表"""
    files = [f for f in os.listdir(NOTES_DIR) if f.endswith(".txt")]
    return files

@router.post("/set-config")
def set_config(item: ConfigItem):
    set_config_value(item.key, item.value)
    return {"message": "配置已更新", "key": item.key, "value": item.value}

@router.get("/get-config/{key}")
def get_config(key: str):
    value = get_config_value(key, default="未设置")
    return {"key": key, "value": value}

@router.post("/generate")
def generate_all_audio():
    raw_txt = find_txt_files(NOTES_DIR)
    raw_txt.sort()

    for path in raw_txt:
        try:
            tts(path, output_dir=AUDIO_OUTPUT_DIR)
        except Exception as e:
            print(f"[错误] 处理文件 {path} 时出错: {e}")

    files = os.listdir(AUDIO_OUTPUT_DIR)
    audio_files = [f for f in files if f.endswith(".wav")]
    srt_files = [f for f in files if f.endswith("_merged.srt")]

    print("生成的音频文件：", audio_files)
    print("生成的预处理字幕文件：", srt_files)
    print("目标输出目录：", AUDIO_OUTPUT_DIR)

    return {
        "audio_files": audio_files,
        "subtitle_files": srt_files
    }

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

@router.post("/generate-one")
def generate_single_audio(data: SingleTTSRequest):
    txt_path = Path(NOTES_DIR) / data.filename

    if not txt_path.exists() or txt_path.suffix != ".txt":
        raise HTTPException(status_code=400, detail="指定的 TXT 文件不存在")

    try:
        tts(txt_path, output_dir=AUDIO_OUTPUT_DIR)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS 处理失败: {str(e)}")

    wav_name = txt_path.stem + ".wav"
    srt_name = txt_path.stem + "_merged.srt"

    audio_path = Path(AUDIO_OUTPUT_DIR) / wav_name
    srt_path = Path(AUDIO_OUTPUT_DIR) / srt_name

    return {
        "audio_file": audio_path.name if audio_path.exists() else None,
        "subtitle_file": srt_path.name if srt_path.exists() else None,
        "status": "success"
    }