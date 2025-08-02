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

1. **PowerShell执行策略限制**：
   如果在Windows系统上使用PowerShell激活虚拟环境时遇到以下错误：
   ```
   venv\Scripts\activate : File [...]\Activate.ps1 cannot be loaded because running scripts is disabled on this system.
   ```
   
   **解决方法**：
   以管理员身份运行PowerShell，并执行以下命令之一：
   ```powershell
   # 仅对当前用户更改执行策略（推荐）
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   
   # 或仅对当前会话更改执行策略
   Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
   ```
   执行后，重新尝试激活虚拟环境。

2. **本地MySQL数据库设置**：
   如果你需要连接本地MySQL数据库（而不是远程数据库），请按照以下步骤操作：
   
   1. 确保本地已安装MySQL服务并启动
   
   2. **方法一：使用Python脚本创建数据库（推荐，无需安装MySQL客户端）**：
      ```bash
      # 激活虚拟环境后执行
      cd backend/mysql
      python setup_database_python.py
      ```
      此脚本会直接通过Python创建数据库和表，并自动更新配置文件。
   
   3. **方法二：使用自动化脚本创建数据库**：
      ```bash
      # Windows系统
      cd backend/mysql
      .\setup_database.bat
      
      # Linux/Mac系统
      cd backend/mysql
      chmod +x setup_database.sh
      ./setup_database.sh
      ```
      这些脚本需要MySQL命令行工具，会自动创建数据库、表，并更新连接配置。
   
   4. **方法三：手动创建数据库和表**：
      ```bash
      # 进入mysql目录
      cd backend/mysql
      
      # 使用MySQL命令行工具执行初始化脚本
      mysql -u root -p < create_database.sql
      
      # 或者直接在MySQL客户端中执行create_database.sql的内容
      ```
      
   5. 如果你的MySQL用户名或密码不是`root`，请修改`app/utils/mysql_config_helper.py`中的连接参数
   
   6. 对于MySQL 8.0及以上版本，需要安装Python的cryptography包以支持caching_sha2_password认证方法：
      ```bash
      # 在虚拟环境中安装
      .\venv\Scripts\pip install cryptography  # Windows
      venv/bin/pip install cryptography        # Linux/Mac
      ```
      如果遇到"RuntimeError: 'cryptography' package is required for sha256_password or caching_sha2_password auth methods"错误，请执行上述命令安装cryptography包。
   
   **注意**：默认配置使用的是本地主机(localhost)，端口3306。

3. **Redis连接失败**：
   - 请确保 Redis 服务已启动，且端口映射正确（如用 Docker，需 `-p 6379:6379`）。
   - 代码默认连接 `localhost:6379`，如有变动请在 `task_manager.py` 中调整。

4. **数据库连接错误**：
   - MySQL 服务是否运行
   - 数据库配置是否正确
   - 数据库和表是否已创建

5. **文件上传/转换错误**：
   - 相关目录具有写入权限
   - 磁盘空间充足

6. **依赖问题**：
   - 可用 `pip freeze > requirements.txt` 导出依赖
   - 安装依赖时如遇报错，建议升级 pip 或单独安装缺失包

## API 文档

启动服务后，访问 http://localhost:8000/docs 查看完整的 API 文档。

# 后端服务启动指南

## 环境要求
- Python 3.8 或更高版本
- 安装依赖包：`pip install -r requirements.txt`

## 启动步骤
1. 进入 backend 目录：`cd backend`
2. 启动服务：`uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

## 访问服务
- 服务启动后，访问 `http://localhost:8000/docs` 查看 API 文档
- 默认端口为 8000，可在启动命令中修改

## 其他说明
- 服务支持热重载，修改代码后自动重启
- 如需修改端口，请调整启动命令中的 `--port` 参数
