import os
from fastapi import APIRouter
from fastapi.responses import JSONResponse

AUDIO_OUTPUT_DIR = "srt_and_mav"  # 根据你的目录设定

router = APIRouter(prefix="/api/tts", tags=["字幕处理"])

@router.get("/check-breaktime/{srt_filename}")
def check_breaktime(srt_filename: str):
    if not srt_filename.endswith("_merged.srt"):
        return JSONResponse(status_code=400, content={"error": "文件名必须以 _merged.srt 结尾"})

    srt_path = os.path.join(AUDIO_OUTPUT_DIR, srt_filename)
    if not os.path.exists(srt_path):
        return JSONResponse(status_code=404, content={"error": "文件不存在"})

    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
            has_breaktime = "breaktime" in content.lower()
            return {
                "filename": srt_filename,
                "has_breaktime": has_breaktime,
                "message": "文件包含 breaktime" if has_breaktime else "文件不包含 breaktime"
            }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"读取文件时发生错误: {str(e)}"})