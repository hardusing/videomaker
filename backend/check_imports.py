#!/usr/bin/env python3
"""
检查所有必要的导入是否可用
"""

import sys
import importlib

# 需要检查的核心模块
required_modules = [
    'fastapi',
    'uvicorn',
    'pydantic',
    'sqlalchemy',
    'redis',
    'celery',
    'PIL',  # pillow
    'cv2',  # opencv-python
    'PyPDF2',
    'fitz',  # PyMuPDF
    'pptx',  # python-pptx
    'openai',
    'azure.cognitiveservices.speech',
    'pytesseract',
    'ffmpeg',
    'jose',  # python-jose
    'passlib',
    'pymysql',
]

def check_imports():
    """检查所有必要的模块是否可以导入"""
    missing_modules = []
    
    for module_name in required_modules:
        try:
            importlib.import_module(module_name)
            print(f"✓ {module_name}")
        except ImportError as e:
            print(f"✗ {module_name} - {str(e)}")
            missing_modules.append(module_name)
    
    if missing_modules:
        print(f"\n缺少 {len(missing_modules)} 个模块:")
        for module in missing_modules:
            print(f"  - {module}")
        return False
    else:
        print("\n所有模块都已正确安装！")
        return True

def check_specific_imports():
    """检查特定的导入路径"""
    print("\n检查项目特定导入:")
    
    specific_imports = [
        'from app.utils.ppt_parser import extract_notes',
        'from app.utils.task_manager import task_manager',
        'from app.api import pdf_api',
        'from app.database import get_db',
    ]
    
    for import_stmt in specific_imports:
        try:
            exec(import_stmt)
            print(f"✓ {import_stmt}")
        except Exception as e:
            print(f"✗ {import_stmt} - {str(e)}")

if __name__ == "__main__":
    print("检查 Python 依赖...\n")
    success = check_imports()
    
    if success:
        check_specific_imports()
    
    sys.exit(0 if success else 1) 