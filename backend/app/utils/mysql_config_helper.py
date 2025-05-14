# app/utils/mysql_config_helper.py

import pymysql
import os

conn_params = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "root"),
    "database": os.getenv("DB_NAME", "videomaker"),
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