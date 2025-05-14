# 视频制作系统后端服务

## 环境要求

- Python 3.8+
- MySQL 5.7+
- Redis 6.0+
- Tesseract-OCR

## 安装步骤

1. 克隆项目并进入后端目录：
```bash
cd backend
```

2. 创建并激活虚拟环境（推荐）：
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 配置环境变量：
创建 `.env` 文件并配置以下参数：
```env
# 数据库配置
DB_HOST=192.168.100.81
DB_PORT=3306
DB_USER=root
DB_PASSWORD=root
DB_NAME=videomaker

# OpenAI配置（如果需要）
OPENAI_API_KEY=your_key
```

## 启动服务

3. 启动后端服务：
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

服务启动后，可以通过以下地址访问：
- API 文档：http://localhost:8000/docs
- 后端服务：http://localhost:8000

## 目录结构

```
backend/
├── app/
│   ├── api/            # API 路由
│   ├── models/         # 数据模型
│   ├── schemas/        # Pydantic 模型
│   ├── services/       # 业务逻辑
│   └── utils/          # 工具函数
├── uploads/            # 上传文件目录
├── notes_output/       # 笔记输出目录
├── srt_and_wav/       # 字幕和音频文件目录
├── main.py            # 主程序入口
└── requirements.txt   # 依赖列表
```

## 常见问题

1. 如果遇到数据库连接错误，请检查：
   - MySQL 服务是否运行
   - 数据库配置是否正确
   - 数据库和表是否已创建

3. 如果遇到文件上传错误，请确保：
   - 相关目录具有写入权限
   - 磁盘空间充足

## API 文档

启动服务后，访问 http://localhost:8000/docs 查看完整的 API 文档。
