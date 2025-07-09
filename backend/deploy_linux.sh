#!/bin/bash

# VideoMaker Linux 自动部署脚本
# 使用方法: chmod +x deploy_linux.sh && sudo ./deploy_linux.sh

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 检查是否为root用户
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "此脚本需要root权限运行，请使用 sudo ./deploy_linux.sh"
        exit 1
    fi
}

# 检测操作系统
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    else
        log_error "无法检测操作系统版本"
        exit 1
    fi
    log_info "检测到操作系统: $OS $VER"
}

# 安装系统依赖
install_dependencies() {
    log_step "安装系统依赖..."
    
    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        apt update && apt upgrade -y
        apt install -y \
            software-properties-common \
            apt-transport-https \
            ca-certificates \
            curl \
            wget \
            gnupg \
            build-essential \
            python3 \
            python3-pip \
            python3-venv \
            python3-dev \
            ffmpeg \
            tesseract-ocr \
            tesseract-ocr-chi-sim \
            libopencv-dev \
            python3-opencv \
            libjpeg-dev \
            libpng-dev \
            redis-server \
            nginx \
            git \
            htop \
            ufw
            
    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]] || [[ "$OS" == *"Rocky"* ]]; then
        dnf update -y
        dnf install -y epel-release
        dnf groupinstall -y "Development Tools"
        dnf install -y \
            python3 \
            python3-pip \
            python3-devel \
            curl \
            wget \
            git \
            tesseract \
            tesseract-langpack-chi_sim \
            opencv-devel \
            python3-opencv \
            redis \
            nginx
            
        # 安装FFmpeg (需要RPM Fusion)
        dnf install -y --nogpgcheck \
            https://download1.rpmfusion.org/free/el/rpmfusion-free-release-$(rpm -E %rhel).noarch.rpm
        dnf install -y ffmpeg ffmpeg-devel
    else
        log_error "不支持的操作系统: $OS"
        exit 1
    fi
    
    log_info "系统依赖安装完成"
}

# 创建应用用户
create_user() {
    log_step "创建应用用户..."
    
    if ! id "videomaker" &>/dev/null; then
        useradd -m -s /bin/bash videomaker
        log_info "用户 videomaker 创建成功"
    else
        log_warn "用户 videomaker 已存在"
    fi
}

# 部署应用
deploy_app() {
    log_step "部署应用..."
    
    # 切换到videomaker用户执行
    sudo -u videomaker bash << 'EOSUDO'
    
    # 创建应用目录
    mkdir -p /home/videomaker/apps
    mkdir -p /home/videomaker/data/{uploads,videos,encoded_videos,notes_output,logs}
    
    # 如果应用目录不存在，则提示用户手动上传
    if [[ ! -d "/home/videomaker/apps/videomaker" ]]; then
        echo "请将VideoMaker项目文件上传到 /home/videomaker/apps/videomaker/"
        echo "您可以使用scp、rsync或其他方式上传文件"
        exit 1
    fi
    
    cd /home/videomaker/apps/videomaker/backend
    
    # 创建虚拟环境
    python3 -m venv venv
    source venv/bin/activate
    
    # 升级pip
    pip install --upgrade pip
    
    # 安装依赖
    pip install -r requirements.txt
    
    # 创建环境配置文件
    if [[ ! -f ".env" ]]; then
        cat > .env << EOF
# OpenAI API配置
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1

# 服务配置
DEBUG=False
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# 文件路径配置
UPLOAD_DIR=/home/videomaker/data/uploads
VIDEO_DIR=/home/videomaker/data/videos
ENCODED_VIDEO_DIR=/home/videomaker/data/encoded_videos
NOTES_OUTPUT_DIR=/home/videomaker/data/notes_output
EOF
        chmod 600 .env
    fi
    
    # 创建生产启动脚本
    cat > start_production.py << 'EOF'
#!/usr/bin/env python3
import uvicorn
import os
import logging
from pathlib import Path

os.chdir(Path(__file__).parent)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/videomaker/data/logs/app.log'),
        logging.StreamHandler()
    ]
)

def main():
    workers_count = max(1, os.cpu_count())
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        workers=workers_count,
        access_log=True,
        log_level="info",
        reload=False
    )

if __name__ == "__main__":
    main()
EOF
    chmod +x start_production.py
    
EOSUDO

    log_info "应用部署完成"
}

# 配置系统服务
setup_service() {
    log_step "配置系统服务..."
    
    cat > /etc/systemd/system/videomaker.service << EOF
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

    systemctl daemon-reload
    systemctl enable videomaker
    
    log_info "系统服务配置完成"
}

# 配置Nginx
setup_nginx() {
    log_step "配置Nginx..."
    
    cat > /etc/nginx/sites-available/videomaker << 'EOF'
server {
    listen 80;
    server_name _;
    client_max_body_size 100M;
    
    location /static/ {
        alias /home/videomaker/apps/videomaker/backend/static/;
        expires 30d;
    }
    
    location /uploads/ {
        alias /home/videomaker/data/uploads/;
        expires 1d;
    }
    
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
    if [[ -d "/etc/nginx/sites-available" ]]; then
        ln -sf /etc/nginx/sites-available/videomaker /etc/nginx/sites-enabled/
        rm -f /etc/nginx/sites-enabled/default
    else
        # CentOS/RHEL
        cp /etc/nginx/sites-available/videomaker /etc/nginx/conf.d/videomaker.conf
    fi
    
    # 测试配置
    nginx -t
    systemctl enable nginx
    systemctl restart nginx
    
    log_info "Nginx配置完成"
}

# 配置防火墙
setup_firewall() {
    log_step "配置防火墙..."
    
    if command -v ufw >/dev/null 2>&1; then
        # Ubuntu/Debian
        ufw --force enable
        ufw allow ssh
        ufw allow 80
        ufw allow 443
    elif command -v firewall-cmd >/dev/null 2>&1; then
        # CentOS/RHEL
        systemctl start firewalld
        systemctl enable firewalld
        firewall-cmd --permanent --add-service=http
        firewall-cmd --permanent --add-service=https
        firewall-cmd --permanent --add-service=ssh
        firewall-cmd --reload
    fi
    
    log_info "防火墙配置完成"
}

# 配置日志轮转
setup_logrotate() {
    log_step "配置日志轮转..."
    
    cat > /etc/logrotate.d/videomaker << EOF
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

    log_info "日志轮转配置完成"
}

# 启动服务
start_services() {
    log_step "启动服务..."
    
    systemctl start redis-server || systemctl start redis
    systemctl start videomaker
    systemctl start nginx
    
    log_info "服务启动完成"
}

# 验证部署
verify_deployment() {
    log_step "验证部署..."
    
    sleep 5
    
    # 检查服务状态
    if systemctl is-active --quiet videomaker; then
        log_info "✅ VideoMaker服务运行正常"
    else
        log_error "❌ VideoMaker服务启动失败"
        return 1
    fi
    
    # 检查API响应
    if curl -f -s http://localhost:8000/ > /dev/null; then
        log_info "✅ API响应正常"
    else
        log_warn "⚠️  API响应异常，请检查日志"
    fi
    
    # 检查Nginx
    if systemctl is-active --quiet nginx; then
        log_info "✅ Nginx运行正常"
    else
        log_error "❌ Nginx启动失败"
    fi
}

# 显示部署结果
show_result() {
    echo ""
    echo -e "${GREEN}🎉 VideoMaker部署完成！${NC}"
    echo ""
    echo -e "${BLUE}访问地址:${NC}"
    echo "  HTTP: http://$(hostname -I | awk '{print $1}')"
    echo "  本地: http://localhost"
    echo ""
    echo -e "${BLUE}API文档:${NC}"
    echo "  http://$(hostname -I | awk '{print $1}')/docs"
    echo ""
    echo -e "${BLUE}管理命令:${NC}"
    echo "  启动服务: sudo systemctl start videomaker"
    echo "  停止服务: sudo systemctl stop videomaker"
    echo "  查看状态: sudo systemctl status videomaker"
    echo "  查看日志: sudo journalctl -u videomaker -f"
    echo ""
    echo -e "${YELLOW}注意事项:${NC}"
    echo "1. 请修改 /home/videomaker/apps/videomaker/backend/.env 中的配置"
    echo "2. 特别是 OPENAI_API_KEY 配置"
    echo "3. 如需域名访问，请修改 /etc/nginx/sites-available/videomaker"
    echo "4. 考虑配置SSL证书以支持HTTPS"
    echo ""
}

# 主函数
main() {
    log_info "开始VideoMaker Linux部署..."
    
    check_root
    detect_os
    install_dependencies
    create_user
    
    # 检查项目文件是否存在
    if [[ ! -d "/home/videomaker/apps/videomaker" ]]; then
        log_warn "项目文件不存在，请先将VideoMaker项目上传到服务器"
        echo ""
        echo "上传步骤："
        echo "1. 在服务器上创建目录: mkdir -p /home/videomaker/apps"
        echo "2. 上传项目文件到: /home/videomaker/apps/videomaker/"
        echo "3. 设置权限: chown -R videomaker:videomaker /home/videomaker/apps/"
        echo "4. 重新运行此脚本"
        exit 1
    fi
    
    deploy_app
    setup_service
    setup_nginx
    setup_firewall
    setup_logrotate
    start_services
    verify_deployment
    show_result
    
    log_info "部署完成！"
}

# 执行主函数
main "$@" 