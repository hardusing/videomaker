from fastapi import APIRouter
from pydantic import BaseModel
from app.utils.mysql_config_helper import get_config_value, set_config_value
import os
from app.tts.tts_engine import tts, find_txt_files

AUDIO_OUTPUT_DIR = "./srt_and_wav"
NOTES_DIR = "./notes_output"
router = APIRouter(prefix="/api/tts", tags=["TTS配置"])

class ConfigItem(BaseModel):
    key: str
    value: str

@router.post("/set-config")
def set_config(item: ConfigItem):
    set_config_value(item.key, item.value)
    return {"message": "配置已更新", "key": item.key, "value": item.value}

@router.get("/get-config/{key}")
def get_config(key: str):
    value = get_config_value(key, default="未设置")
    return {"key": key, "value": value}

@router.post("/api/tts/generate")
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

    print("生成的音频文件：", audio_path)
    print("生成的预处理字幕文件：", srt_path)
    print("目标输出目录：", output_dir)

    return {
        "audio_files": audio_files,
        "subtitle_files": srt_files
    }