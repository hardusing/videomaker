# PPT转图片并识别文字处理脚本使用说明

## 功能概述

这个脚本整合了你项目中的PPT处理功能，可以完成以下完整流程：

1. **PPT转PDF**: 使用PowerPoint COM对象将PPT/PPTX转换为PDF
2. **PDF转图片**: 将PDF每页转换为高质量PNG图片
3. **添加黑边**: 为图片添加上下黑边，便于后续字幕处理
4. **OCR识别**: 使用Tesseract识别图片中的文字
5. **AI优化**: 必须使用OpenAI API优化识别的文字内容（已内置API密钥）

## 安装依赖

### 1. Python依赖包
```bash
pip install -r ppt_processor_requirements.txt
```

### 2. 系统依赖

#### Windows系统
1. **Microsoft Office**: 需要安装PowerPoint（用于PPT转PDF）
2. **Tesseract OCR**: 
   - 下载: https://github.com/UB-Mannheim/tesseract/wiki
   - 安装时选择"Additional language data"以支持中文识别
   - 添加到系统PATH环境变量

#### macOS系统
```bash
# 安装Tesseract和中文语言包
brew install tesseract tesseract-lang

# 注意：macOS上PPT转PDF功能可能需要其他方案
```

#### Ubuntu系统
```bash
# 安装Tesseract和中文语言包
sudo apt install tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng

# 注意：Linux上PPT转PDF功能需要LibreOffice或其他方案
```

## 使用方法

### 基本用法
```bash
# 处理PPT文件，使用默认设置（自动使用AI优化）
python ppt_to_text_processor.py presentation.pptx
```

### 高级用法
```bash
# 指定输出目录
python ppt_to_text_processor.py presentation.pptx --output-dir ./my_output

# 自定义AI优化提示词
python ppt_to_text_processor.py presentation.pptx --custom-prompt "请将文字整理为简洁的中文讲稿"

# 不添加黑边
python ppt_to_text_processor.py presentation.pptx --no-borders

# 设置更高的图片质量
python ppt_to_text_processor.py presentation.pptx --dpi 300
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `ppt_file` | PPT或PPTX文件路径 | 必需 |
| `--output-dir` | 输出目录 | `./output` |
| `--custom-prompt` | 自定义AI提示词 | 默认提示词 |
| `--no-borders` | 不添加黑边 | 添加黑边 |
| `--dpi` | 图片DPI质量 | 200 |

**注意**: AI文字优化功能已内置并默认启用，使用预设的API密钥。

## 输出结构

脚本会在指定的输出目录下创建以下结构：

```
output/
├── pdf/                          # PDF文件
│   └── presentation.pdf
├── images/                       # 原始图片
│   └── presentation/
│       ├── 1.png
│       ├── 2.png
│       └── ...
├── processed_images/             # 添加黑边后的图片
│   └── presentation/
│       ├── 1.png
│       ├── 2.png
│       └── ...
├── text_output/                  # 识别的文字
│   └── presentation/
│       ├── 1.txt
│       ├── 2.txt
│       └── ...
└── presentation_processing_report.json  # 处理报告
```

## 处理报告

每次处理完成后，会生成一个JSON格式的处理报告，包含：

```json
{
  "ppt_file": "presentation.pptx",
  "pdf_file": "presentation.pdf",
  "total_pages": 10,
  "success_count": 9,
  "failed_count": 1,
  "output_directories": {
    "pdf": "/path/to/output/pdf",
    "images": "/path/to/output/images/presentation",
    "processed_images": "/path/to/output/processed_images/presentation",
    "text_output": "/path/to/output/text_output/presentation"
  },
  "results": [
    {
      "image": "1.png",
      "text_file": "1.txt",
      "status": "success",
      "ocr_text": "原始OCR文字...",
      "final_text": "AI优化后文字..."
    }
  ]
}
```

## 常见问题

### 1. PowerPoint COM错误
- **问题**: `pywintypes.com_error: (-2147221164, '没有注册类', None, None)`
- **解决**: 确保安装了Microsoft Office PowerPoint

### 2. Tesseract未找到
- **问题**: `TesseractNotFoundError`
- **解决**: 
  - Windows: 确保Tesseract安装路径在系统PATH中
  - 或在代码中指定: `pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'`

### 3. 中文识别效果差
- **解决**: 
  - 确保安装了中文语言包 `chi_sim`
  - 可以调整DPI参数提高图片质量: `--dpi 300`

### 4. AI优化失败
- **检查**: 
  - 网络连接是否正常
  - API额度是否充足
  - 如果持续失败，脚本会使用原始OCR文字作为备选

## 与项目集成

这个脚本整合了你项目中以下模块的功能：

- `backend/app/api/pdf_api.py` - PPT转PDF功能
- `backend/app/api/workflow_api.py` - PDF转图片功能  
- `backend/app/api/image_notes_api.py` - 添加黑边和OCR识别功能

可以直接在项目根目录使用，或者将其集成到现有的API服务中。

## 性能优化建议

1. **批量处理**: 对于大量PPT文件，可以修改脚本支持批量处理
2. **并行处理**: OCR识别可以使用多线程并行处理
3. **缓存机制**: 可以添加缓存避免重复处理相同文件
4. **内存优化**: 处理大型PPT时注意内存使用

## 扩展功能

脚本设计为模块化，可以轻松扩展：

- 支持更多输入格式（PDF直接输入）
- 添加更多图片处理选项
- 集成其他OCR引擎
- 支持更多AI服务提供商
- 添加Web界面
