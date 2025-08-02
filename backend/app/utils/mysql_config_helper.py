import pymysql
import os

conn_params = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "root",  # 已根据输入更新
    "database": "videomaker",
    "charset": "utf8mb4"
}

def get_config_value(key: str, default: str = "") -> str:
    conn = pymysql.connect(**conn_params)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT config_value FROM tts_config WHERE config_key = %s", (key,))
            row = cursor.fetchone()
            return row[0] if row else default
    finally:
        conn.close()

def set_config_value(key: str, value: str):
    conn = pymysql.connect(**conn_params)
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO tts_config (config_key, config_value)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
            """, (key, value))
        conn.commit()
    finally:
        conn.close()