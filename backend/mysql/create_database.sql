-- 创建数据库
CREATE DATABASE IF NOT EXISTS videomaker CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 使用创建的数据库
USE videomaker;

-- 创建TTS配置表
CREATE TABLE IF NOT EXISTS tts_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(255) NOT NULL UNIQUE,
    config_value VARCHAR(512) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 创建项目表
CREATE TABLE IF NOT EXISTS projects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 创建任务表
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
);

-- 创建文件表
CREATE TABLE IF NOT EXISTS files (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT,
    file_type VARCHAR(50) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- 插入默认TTS配置
INSERT INTO tts_config (config_key, config_value) VALUES
('voice', 'zh-CN-YunxiNeural'),
('speech_key', 'your-speech-key-here'),
('service_region', 'eastasia'),
('speech_rate', '1.0'),
('voice_style', 'General');

-- 插入示例项目
INSERT INTO projects (name, description, status) VALUES
('示例项目', '用于测试系统的示例项目', 'active');

-- 显示创建的表
SHOW TABLES; 