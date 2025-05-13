import os
from fastapi import APIRouter
from fastapi.responses import JSONResponse

AUDIO_OUTPUT_DIR = "srt_and_wav"  # 根据你的目录设定

router = APIRouter(prefix="/api/tts", tags=["字幕处理"])

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
