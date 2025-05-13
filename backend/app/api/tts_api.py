from fastapi import APIRouter
from pydantic import BaseModel
from app.utils.mysql_config_helper import get_config_value, set_config_value

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