# 视频制作系统后端服务

## 环境要求

- Python 3.8+
- MySQL 5.7+（如需数据库功能）
- Redis 6.0+（任务管理依赖）
- Tesseract-OCR（如需OCR功能）

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

如需导出当前所有依赖（推荐开发后执行）：
```bash
pip freeze > requirements.txt
```

4. 启动 Redis 服务（本地或容器均可）：
- 本地启动：
```bash
redis-server
```
- Docker 启动：
```bash
docker run -d --name myredis -p 6379:6379 redis
```

5. 配置环境变量：
创建 `.env` 文件并配置以下参数（如需数据库等功能）：
```env
# 数据库配置
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=root
DB_NAME=videomaker

# OpenAI配置（如果需要）
OPENAI_API_KEY=your_key
```

## 启动服务

6. 启动后端服务：
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

服务启动后，可以通过以下地址访问：
- API 文档：http://localhost:8000/docs
- 后端服务：http://localhost:8000

## 主要API说明

### PDF上传
```
POST /api/pdf/upload
```
返回：`task_id`，用于后续操作。

### PDF转图片（流式返回图片ID和缩略图）
```
POST /api/pdf/convert/{task_id}
```
每生成一张图片，流式返回：
- image_id：唯一图片ID
- image_path：图片相对路径
- thumbnail：base64缩略图（前端可直接预览）
- progress/current_page/total_pages/task_id

前端可用 fetch/流式读取，或 WebSocket 方式（见源码）。

### 任务状态查询
```
GET /api/tasks/{task_id}
```

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

1. **Redis连接失败**：
   - 请确保 Redis 服务已启动，且端口映射正确（如用 Docker，需 `-p 6379:6379`）。
   - 代码默认连接 `localhost:6379`，如有变动请在 `task_manager.py` 中调整。

2. **数据库连接错误**：
   - MySQL 服务是否运行
   - 数据库配置是否正确
   - 数据库和表是否已创建

3. **文件上传/转换错误**：
   - 相关目录具有写入权限
   - 磁盘空间充足

4. **依赖问题**：
   - 可用 `pip freeze > requirements.txt` 导出依赖
   - 安装依赖时如遇报错，建议升级 pip 或单独安装缺失包

## API 文档

启动服务后，访问 http://localhost:8000/docs 查看完整的 API 文档。
