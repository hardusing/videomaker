# 使用官方轻量级 Python 镜像作为基础
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 拷贝依赖文件并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝项目代码
COPY . .

# 暴露端口（FastAPI 默认是8000）
EXPOSE 8003
# 启动服务
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
