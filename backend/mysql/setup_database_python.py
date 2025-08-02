#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
通过Python直接创建数据库和表
不需要安装MySQL命令行工具
"""

import os
import sys
import pymysql
import getpass

def create_database():
    print("正在设置视频制作系统数据库...")
    print()

    # 获取用户输入
    mysql_host = input("请输入MySQL主机地址 (默认: localhost): ") or "localhost"
    mysql_port = input("请输入MySQL端口 (默认: 3306): ") or "3306"
    mysql_user = input("请输入MySQL用户名 (默认: root): ") or "root"
    mysql_password = getpass.getpass("请输入MySQL密码 (默认: root): ") or "root"

    try:
        # 首先连接MySQL服务器（不指定数据库）
        conn = pymysql.connect(
            host=mysql_host,
            port=int(mysql_port),
            user=mysql_user,
            password=mysql_password,
            charset='utf8mb4'
        )
        
        cursor = conn.cursor()
        
        # 创建数据库
        print("\n正在创建数据库...")
        cursor.execute("CREATE DATABASE IF NOT EXISTS videomaker CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
        
        # 切换到新创建的数据库
        cursor.execute("USE videomaker")
        
        # 创建表
        print("正在创建表...")
        
        # 创建TTS配置表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tts_config (
            id INT AUTO_INCREMENT PRIMARY KEY,
            config_key VARCHAR(255) NOT NULL UNIQUE,
            config_value VARCHAR(512) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """)
        
        # 创建项目表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            status VARCHAR(50) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """)
        
        # 创建任务表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            project_id INT,
            task_type VARCHAR(50) NOT NULL,
            status VARCHAR(50) DEFAULT 'pending',
            task_data JSON,
            result_data JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
        """)
        
        # 创建文件表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INT AUTO_INCREMENT PRIMARY KEY,
            project_id INT,
            file_type VARCHAR(50) NOT NULL,
            file_path VARCHAR(512) NOT NULL,
            original_name VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
        """)
        
        # 插入默认TTS配置
        print("正在插入初始数据...")
        cursor.execute("INSERT IGNORE INTO tts_config (config_key, config_value) VALUES (%s, %s)", ('voice', 'zh-CN-YunxiNeural'))
        cursor.execute("INSERT IGNORE INTO tts_config (config_key, config_value) VALUES (%s, %s)", ('speech_key', 'your-speech-key-here'))
        cursor.execute("INSERT IGNORE INTO tts_config (config_key, config_value) VALUES (%s, %s)", ('service_region', 'eastasia'))
        cursor.execute("INSERT IGNORE INTO tts_config (config_key, config_value) VALUES (%s, %s)", ('speech_rate', '1.0'))
        cursor.execute("INSERT IGNORE INTO tts_config (config_key, config_value) VALUES (%s, %s)", ('voice_style', 'General'))
        
        # 插入示例项目
        cursor.execute("INSERT IGNORE INTO projects (name, description, status) VALUES (%s, %s, %s)", 
                      ('示例项目', '用于测试系统的示例项目', 'active'))
        
        conn.commit()
        
        # 更新配置文件
        print("\n正在更新配置文件...")
        config_path = os.path.join('..', 'app', 'utils', 'mysql_config_helper.py')
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config_lines = f.readlines()
        
        new_config = [
            'import pymysql\n',
            'import os\n',
            '\n',
            'conn_params = {\n',
            f'    "host": "{mysql_host}",\n',
            f'    "port": {mysql_port},\n',
            f'    "user": "{mysql_user}",\n',
            f'    "password": "{mysql_password}",  # 已根据输入更新\n',
            '    "database": "videomaker",\n',
            '    "charset": "utf8mb4"\n',
            '}\n',
            '\n'
        ]
        
        # 保留原来的函数部分
        function_part = []
        for line in config_lines:
            if line.startswith('def '):
                function_part = config_lines[config_lines.index(line):]
                break
        
        with open(config_path, 'w', encoding='utf-8') as f:
            f.writelines(new_config + function_part)
        
        print("数据库创建成功！配置文件已更新！")
        
    except pymysql.Error as e:
        print(f"\n错误: {e}")
        print("\n请确保:")
        print("1. MySQL服务已启动")
        print("2. 用户名和密码正确")
        print("3. 用户有创建数据库的权限")
        return False
    finally:
        if 'conn' in locals() and conn:
            conn.close()
    
    return True

if __name__ == "__main__":
    try:
        success = create_database()
        if success:
            print("\n数据库初始化完成!")
        else:
            print("\n数据库初始化失败，请检查错误信息并重试。")
    except Exception as e:
        print(f"\n发生错误: {e}")
    
    input("\n按Enter键退出...") 