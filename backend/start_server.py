#!/usr/bin/env python3
"""
videomaker 后端服务启动脚本
"""
import uvicorn
import sys
import os
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """启动FastAPI服务器"""
    try:
        logger.info("🚀 正在启动videomaker后端服务...")
        logger.info("📍 服务地址: http://localhost:8000")
        logger.info("📚 API文档: http://localhost:8000/docs")
        logger.info("🔄 WebSocket测试: http://localhost:8000/test-websocket")
        logger.info("👆 按Ctrl+C停止服务")
        logger.info("=" * 50)
        
        # 启动uvicorn服务器
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            access_log=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("👋 服务已停止")
    except Exception as e:
        logger.error(f"❌ 服务启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 