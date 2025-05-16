CREATE DATABASE IF NOT EXISTS videomaker CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE videomaker;

CREATE TABLE IF NOT EXISTS tts_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(255) NOT NULL,
    config_value VARCHAR(512) NOT NULL
);

INSERT INTO tts_config (id, config_key, config_value) VALUES
(1, 'voice', 'ja-JP-MayuNeural'),
(4, 'speech_key', 'your-real-key'),
(5, 'service_region', 'japaneast');
