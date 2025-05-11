# VideoMaker 项目

这是一个基于PPT自动生成视频的项目，可以将PPT转换为带有语音和字幕的视频。

## 项目架构

项目采用前后端分离的架构：

### 后端 (Python FastAPI)
- 主要功能：
  - PPT文件上传和处理
  - 笔记提取
  - 文本转语音(TTS)
  - 字幕生成
- 目录结构：
  - `/backend/app`: 主要应用代码
  - `/backend/uploads`: 上传的PPT文件存储
  - `/backend/notes_output`: 提取的笔记输出
  - `/backend/srt_and_mav`: 生成的音频和字幕文件

### 前端 (React + TypeScript)
- 技术栈：
  - React 18
  - TypeScript
  - Ant Design
  - Redux Toolkit
  - React Router
  - Vite

## API 接口

### 项目相关
- `GET /api/v1/projects`: 获取所有项目列表
- `POST /api/v1/projects/upload`: 上传PPT文件
- `POST /api/v1/projects/{project_id}/extract`: 提取项目笔记

### TTS相关
- `GET /api/tts/texts`: 获取所有文本文件列表
- `POST /api/tts/generate`: 生成所有音频文件

## 如何启动

### 后端启动
1. 进入后端目录：
```bash
cd backend
```

2. 创建并激活虚拟环境：
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 启动服务器：
```bash
uvicorn app.main:app --reload
```

### 前端启动
1. 进入前端目录：
```bash
cd frontend
```

2. 安装依赖：
```bash
npm install
```

3. 启动开发服务器：
```bash
npm run dev
```

## 使用说明
1. 通过前端界面上传PPT文件
2. 系统会自动提取PPT中的笔记
3. 使用TTS功能将文本转换为语音
4. 生成的字幕和音频文件可以在前端界面查看和下载

## 注意事项
- 仅支持.pptx格式的PPT文件
- 确保系统有足够的存储空间用于文件处理
- 音频生成可能需要一定时间，请耐心等待