# VideoMaker Linux 部署指南

## 📋 部署概览

本指南将帮助你在Linux系统上部署VideoMaker后端服务，不使用Docker容器化部署。

## 🖥️ 系统要求

### 支持的Linux发行版
- **Ubuntu 18.04+** (推荐 20.04/22.04)
- **CentOS 7+** / **Rocky Linux 8+**
- **Debian 10+**
- **Red Hat Enterprise Linux 8+**

### 硬件要求
- **CPU**: 2核心以上 (推荐4核心+)
- **内存**: 最少4GB (推荐8GB+)
- **存储**: 最少20GB可用空间 (推荐50GB+)
- **网络**: 稳定的互联网连接

## 🔧 系统依赖安装

### Ubuntu/Debian 系统

```bash
# 更新系统包
sudo apt update && sudo apt upgrade -y

# 安装基础依赖
sudo apt install -y \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    curl \
    wget \
    gnupg \
    lsb-release \
    build-essential \
    pkg-config

# 安装Python 3.8+
sudo apt install -y python3 python3-pip python3-venv python3-dev

# 安装FFmpeg (视频处理)
sudo apt install -y ffmpeg

# 安装Tesseract OCR
sudo apt install -y tesseract-ocr tesseract-ocr-chi-sim

# 安装图像处理库
sudo apt install -y \
    libopencv-dev \
    python3-opencv \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev

# 安装Redis (可选)
sudo apt install -y redis-server

# 安装Nginx (反向代理)
sudo apt install -y nginx

# 安装系统监控工具
sudo apt install -y htop iotop nethogs
```

### CentOS/RHEL/Rocky Linux 系统

```bash
# 更新系统包
sudo dnf update -y

# 安装EPEL仓库
sudo dnf install -y epel-release

# 安装基础依赖
sudo dnf groupinstall -y "Development Tools"
sudo dnf install -y \
    python3 \
    python3-pip \
    python3-devel \
    curl \
    wget \
    git

# 安装FFmpeg
sudo dnf install -y --nogpgcheck https://download1.rpmfusion.org/free/el/rpmfusion-free-release-$(rpm -E %rhel).noarch.rpm
sudo dnf install -y ffmpeg ffmpeg-devel

# 安装Tesseract OCR
sudo dnf install -y tesseract tesseract-langpack-chi_sim

# 安装图像处理库
sudo dnf install -y \
    opencv-devel \
    python3-opencv \
    libjpeg-turbo-devel \
    libpng-devel \
    libtiff-devel

# 安装Redis
sudo dnf install -y redis

# 安装Nginx
sudo dnf install -y nginx
```

## 🚀 项目部署

### 1. 创建部署用户

```bash
# 创建专用用户
sudo useradd -m -s /bin/bash videomaker
sudo usermod -aG sudo videomaker  # 如需sudo权限

# 切换到部署用户
sudo su - videomaker
```

### 2. 部署项目文件

```bash
# 创建应用目录
mkdir -p /home/videomaker/apps
cd /home/videomaker/apps

# 方式1: 使用git克隆 (如果有git仓库)
git clone <your-repo-url> videomaker
cd videomaker/backend

# 方式2: 手动上传文件
# 将你的项目文件上传到 /home/videomaker/apps/videomaker/backend/
```

### 3. 创建Python虚拟环境

```bash
# 进入项目目录
cd /home/videomaker/apps/videomaker/backend

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 升级pip
pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt

# 验证安装
python -c "import fastapi, uvicorn, openai, cv2, ffmpeg; print('✅ 依赖安装成功')"
```

### 4. 环境配置

```bash
# 创建环境变量文件
cat > .env << EOF
# OpenAI API配置
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1

# 服务配置
DEBUG=False
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000

# Redis配置 (如果使用)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# 文件路径配置
UPLOAD_DIR=/home/videomaker/data/uploads
VIDEO_DIR=/home/videomaker/data/videos
ENCODED_VIDEO_DIR=/home/videomaker/data/encoded_videos
NOTES_OUTPUT_DIR=/home/videomaker/data/notes_output
EOF

# 创建数据目录
mkdir -p /home/videomaker/data/{uploads,videos,encoded_videos,notes_output,logs}

# 设置权限
chmod 600 .env
chmod -R 755 /home/videomaker/data
```

### 5. 创建启动脚本

```bash
# 创建生产环境启动脚本
cat > start_production.py << 'EOF'
#!/usr/bin/env python3
"""
VideoMaker 生产环境启动脚本
"""
import uvicorn
import os
import logging
from pathlib import Path

# 设置工作目录
os.chdir(Path(__file__).parent)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/videomaker/data/logs/app.log'),
        logging.StreamHandler()
    ]
)

def main():
    """启动生产环境服务器"""
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        workers=4,  # 根据CPU核心数调整
        access_log=True,
        log_level="info",
        reload=False  # 生产环境关闭热重载
    )

if __name__ == "__main__":
    main()
EOF

chmod +x start_production.py
```

## 🔄 系统服务配置

### 1. 创建Systemd服务

```bash
# 创建服务文件
sudo tee /etc/systemd/system/videomaker.service << EOF
[Unit]
Description=VideoMaker FastAPI Application
After=network.target

[Service]
Type=exec
User=videomaker
Group=videomaker
WorkingDirectory=/home/videomaker/apps/videomaker/backend
Environment=PATH=/home/videomaker/apps/videomaker/backend/venv/bin
ExecStart=/home/videomaker/apps/videomaker/backend/venv/bin/python start_production.py
ExecReload=/bin/kill -s HUP \$MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 重新加载systemd配置
sudo systemctl daemon-reload

# 启用服务
sudo systemctl enable videomaker

# 启动服务
sudo systemctl start videomaker

# 检查服务状态
sudo systemctl status videomaker
```

### 2. 服务管理命令

```bash
# 启动服务
sudo systemctl start videomaker

# 停止服务
sudo systemctl stop videomaker

# 重启服务
sudo systemctl restart videomaker

# 查看服务状态
sudo systemctl status videomaker

# 查看服务日志
sudo journalctl -u videomaker -f

# 查看应用日志
tail -f /home/videomaker/data/logs/app.log
```

## 🌐 Nginx反向代理配置

### 1. 配置Nginx

```bash
# 创建Nginx配置文件
sudo tee /etc/nginx/sites-available/videomaker << 'EOF'
server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名
    client_max_body_size 100M;
    
    # 静态文件代理
    location /static/ {
        alias /home/videomaker/apps/videomaker/backend/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # 上传文件代理
    location /uploads/ {
        alias /home/videomaker/data/uploads/;
        expires 1d;
    }
    
    # API代理
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # WebSocket代理
    location /api/videos/ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# 启用站点
sudo ln -s /etc/nginx/sites-available/videomaker /etc/nginx/sites-enabled/

# 删除默认站点
sudo rm -f /etc/nginx/sites-enabled/default

# 测试Nginx配置
sudo nginx -t

# 重启Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### 2. SSL配置 (使用Let's Encrypt)

```bash
# 安装Certbot
sudo apt install -y certbot python3-certbot-nginx  # Ubuntu/Debian
# 或
sudo dnf install -y certbot python3-certbot-nginx  # CentOS/RHEL

# 获取SSL证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo crontab -e
# 添加以下行：
# 0 12 * * * /usr/bin/certbot renew --quiet
```

## 🔥 防火墙配置

### Ubuntu/Debian (UFW)

```bash
# 启用UFW
sudo ufw enable

# 允许SSH
sudo ufw allow ssh

# 允许HTTP/HTTPS
sudo ufw allow 80
sudo ufw allow 443

# 查看状态
sudo ufw status
```

### CentOS/RHEL (firewalld)

```bash
# 启动firewalld
sudo systemctl start firewalld
sudo systemctl enable firewalld

# 允许HTTP/HTTPS
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https

# 重新加载配置
sudo firewall-cmd --reload

# 查看状态
sudo firewall-cmd --list-all
```

## 📊 监控和日志

### 1. 日志管理

```bash
# 创建日志轮转配置
sudo tee /etc/logrotate.d/videomaker << EOF
/home/videomaker/data/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 videomaker videomaker
    postrotate
        systemctl reload videomaker
    endscript
}
EOF
```

### 2. 监控脚本

```bash
# 创建监控脚本
cat > /home/videomaker/monitor.sh << 'EOF'
#!/bin/bash
# VideoMaker服务监控脚本

SERVICE_NAME="videomaker"
LOG_FILE="/home/videomaker/data/logs/monitor.log"

# 检查服务状态
check_service() {
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo "$(date): $SERVICE_NAME is running" >> $LOG_FILE
        return 0
    else
        echo "$(date): $SERVICE_NAME is not running, attempting restart..." >> $LOG_FILE
        sudo systemctl restart $SERVICE_NAME
        sleep 10
        if systemctl is-active --quiet $SERVICE_NAME; then
            echo "$(date): $SERVICE_NAME restarted successfully" >> $LOG_FILE
        else
            echo "$(date): Failed to restart $SERVICE_NAME" >> $LOG_FILE
        fi
    fi
}

# 检查API响应
check_api() {
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/)
    if [ "$response" = "200" ]; then
        echo "$(date): API responding correctly" >> $LOG_FILE
    else
        echo "$(date): API not responding (HTTP $response)" >> $LOG_FILE
    fi
}

check_service
check_api
EOF

chmod +x /home/videomaker/monitor.sh

# 添加到crontab (每5分钟检查一次)
(crontab -l 2>/dev/null; echo "*/5 * * * * /home/videomaker/monitor.sh") | crontab -
```

## 🔧 性能优化

### 1. 系统优化

```bash
# 增加文件描述符限制
sudo tee -a /etc/security/limits.conf << EOF
videomaker soft nofile 65536
videomaker hard nofile 65536
EOF

# 优化内核参数
sudo tee -a /etc/sysctl.conf << EOF
# 网络优化
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 1200

# 内存优化
vm.swappiness = 10
vm.overcommit_memory = 1
EOF

sudo sysctl -p
```

### 2. Python应用优化

```bash
# 修改启动脚本，根据服务器配置调整workers数量
# CPU核心数 x 2 + 1
workers_count=$(($(nproc) * 2 + 1))

# 更新start_production.py中的workers参数
sed -i "s/workers=4/workers=$workers_count/" start_production.py
```

## 🧪 部署验证

### 1. 服务健康检查

```bash
# 检查服务状态
curl -I http://localhost:8000
curl http://localhost:8000

# 检查API文档
curl -I http://localhost:8000/docs

# 检查特定API
curl http://localhost:8000/api/videos/all-folders
```

### 2. 性能测试

```bash
# 安装ab测试工具
sudo apt install -y apache2-utils  # Ubuntu/Debian
sudo dnf install -y httpd-tools    # CentOS/RHEL

# 简单性能测试
ab -n 1000 -c 10 http://localhost:8000/
```

## 🚀 部署检查清单

部署完成后请确认：

- [ ] 所有系统依赖已安装
- [ ] Python虚拟环境创建成功
- [ ] 项目依赖安装完成
- [ ] 环境变量配置正确
- [ ] 服务可以正常启动
- [ ] Nginx反向代理配置正确
- [ ] 防火墙规则已设置
- [ ] SSL证书已配置 (如果需要)
- [ ] 监控脚本已设置
- [ ] 日志轮转已配置
- [ ] API响应正常

## 🔍 故障排除

### 常见问题

1. **服务启动失败**
   ```bash
   # 查看详细错误
   sudo journalctl -u videomaker -n 50
   
   # 检查文件权限
   ls -la /home/videomaker/apps/videomaker/backend/
   ```

2. **依赖安装失败**
   ```bash
   # 更新pip
   pip install --upgrade pip
   
   # 分别安装问题依赖
   pip install 依赖名 --verbose
   ```

3. **FFmpeg问题**
   ```bash
   # 验证FFmpeg安装
   ffmpeg -version
   which ffmpeg
   ```

4. **权限问题**
   ```bash
   # 检查文件所有者
   sudo chown -R videomaker:videomaker /home/videomaker/
   
   # 设置正确权限
   chmod -R 755 /home/videomaker/apps/
   ```

## 📋 维护命令

```bash
# 更新项目代码
cd /home/videomaker/apps/videomaker/backend
git pull
sudo systemctl restart videomaker

# 更新Python依赖
source venv/bin/activate
pip install -r requirements.txt --upgrade
sudo systemctl restart videomaker

# 备份数据
tar -czf /home/videomaker/backup-$(date +%Y%m%d).tar.gz /home/videomaker/data/

# 清理日志
find /home/videomaker/data/logs/ -name "*.log" -mtime +30 -delete
```

---

**🎉 恭喜！你的VideoMaker系统已成功部署到Linux服务器！**

访问 `http://your-server-ip` 或 `https://your-domain.com` 开始使用。

---
*最后更新: 2024年7月9日* 