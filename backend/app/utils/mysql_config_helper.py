import pymysql
import time

PRIMARY_CONN = {
    "host": "mysql",  # docker-compose 中服务名
    "port": 3306,
    "user": "root",
    "password": "root",
    "database": "videomaker",
    "charset": "utf8mb4"
}
# 👉 备用数据库地址（服务器 IP）
FALLBACK_CONN = {
    "host": "192.168.100.81",
    "port": 3306,
    "user": "root",
    "password": "root",
    "database": "videomaker",
    "charset": "utf8mb4"
}
# 当前使用的连接配置（默认是主）
conn_params = PRIMARY_CONN.copy()
# 当前使用的连接配置（默认是主）
# 🔁 添加连接重试机制，自动切换备用地址
def wait_for_mysql(max_retries=5, delay=2):
    global conn_params
    for i in range(max_retries):
        try:
            conn = pymysql.connect(**conn_params)
            conn.close()
            print(f"✅ 第{i+1}次连接成功，MySQL 已就绪")
            return
        except Exception as e:
            print(f"⏳ 第{i+1}次连接 {conn_params['host']} 失败: {e}")
            time.sleep(delay)

    # ⛔ 主连接失败，尝试备用
    print("⚠️ 主数据库连接失败，尝试备用地址...")
    conn_params = FALLBACK_CONN.copy()
    for i in range(max_retries):
        try:
            conn = pymysql.connect(**conn_params)
            conn.close()
            print(f"✅ 使用备用地址第{i+1}次连接成功")
            return
        except Exception as e:
            print(f"⏳ 备用地址第{i+1}次连接失败: {e}")
            time.sleep(delay)

    raise RuntimeError("❌ 主/备用数据库连接都失败")

# ⏳ 应用启动时执行一次
wait_for_mysql()

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