#!/usr/bin/env python3
"""
PPT转图片并识别文字的完整处理脚本
整合了PPT转PDF、PDF转图片、添加黑边、OCR识别等功能

使用方法:
python ppt_to_text_processor.py input.pptx [--output-dir output] [--api-key your_api_key]

功能:
1. 将PPT/PPTX转换为PDF
2. 将PDF每页转换为高质量PNG图片
3. 为图片添加上下黑边
4. 使用OCR识别图片中的文字
5. 可选：使用AI优化识别的文字内容
"""

import os
import sys
import argparse
import comtypes.client
from pathlib import Path
from PIL import Image
import fitz  # PyMuPDF
import pytesseract
import tempfile
import shutil
from typing import List, Optional
import json
import time

# AI处理 - 必须使用
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    print("错误: 未安装openai库，AI文本优化功能是必需的")
    print("请安装: pip install openai")
    exit(1)


class PPTToTextProcessor:
    """PPT转文字处理器"""
    
    def __init__(self, output_dir: str = None):
        self.output_dir = Path(output_dir) if output_dir else Path("./output")
        # 写死API密钥
        self.api_key = "sk-xdtZS13EcaCHxoRbL50JDdP85EUKEhXtg4IcBKSKgF4ObTvW"
        
        # 创建输出目录结构
        self.pdf_dir = self.output_dir / "pdf"
        self.images_dir = self.output_dir / "images"
        self.processed_images_dir = self.output_dir / "processed_images"
        self.text_dir = self.output_dir / "text_output"
        
        for dir_path in [self.pdf_dir, self.images_dir, self.processed_images_dir, self.text_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
            
        # 设置OpenAI API密钥
        openai.api_key = self.api_key
    
    def ppt_to_pdf(self, ppt_path: str, pdf_path: str) -> bool:
        """将PPT或PPTX文件转换为PDF"""
        print(f"正在转换PPT为PDF: {ppt_path} -> {pdf_path}")
        
        try:
            # 创建PowerPoint应用程序对象
            powerpoint = comtypes.client.CreateObject("Powerpoint.Application")
            powerpoint.Visible = 1
            
            # 使用绝对路径
            ppt_path = os.path.abspath(ppt_path)
            pdf_path = os.path.abspath(pdf_path)
            
            # 打开PPT文件
            deck = powerpoint.Presentations.Open(ppt_path)
            
            # 保存为PDF格式 (32 = PDF format)
            deck.SaveAs(pdf_path, FileFormat=32)
            
            # 关闭文件和应用程序
            deck.Close()
            powerpoint.Quit()
            
            print(f"✓ PPT转PDF成功: {pdf_path}")
            return True
            
        except Exception as e:
            # 确保PowerPoint进程被关闭
            try:
                powerpoint.Quit()
            except:
                pass
            print(f"✗ PPT转PDF失败: {str(e)}")
            return False
    
    def pdf_to_images(self, pdf_path: str, output_subdir: str, dpi: int = 200) -> List[str]:
        """将PDF转换为图片"""
        print(f"正在转换PDF为图片: {pdf_path}")
        
        try:
            # 打开PDF文件
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            if total_pages == 0:
                print("✗ PDF文件为空")
                return []
            
            # 创建输出子目录
            output_dir = self.images_dir / output_subdir
            output_dir.mkdir(parents=True, exist_ok=True)
            
            saved_files = []
            
            print(f"PDF共有 {total_pages} 页，开始转换...")
            
            for i, page in enumerate(doc, start=1):
                # 生成图片文件名
                img_filename = f"{i}.png"
                img_path = output_dir / img_filename
                
                # 转换页面为图片
                pix = page.get_pixmap(dpi=dpi)
                pix.save(str(img_path))
                
                saved_files.append(str(img_path))
                print(f"  ✓ 转换完成页面 {i}/{total_pages}: {img_filename}")
            
            doc.close()
            print(f"✓ PDF转图片完成，共生成 {len(saved_files)} 张图片")
            return saved_files
            
        except Exception as e:
            print(f"✗ PDF转图片失败: {str(e)}")
            return []
    
    def add_black_borders(self, image_path: str, output_path: str, top: int = 100, bottom: int = 100) -> bool:
        """为图片添加上下黑边"""
        try:
            img = Image.open(image_path)
            width, height = img.size
            
            # 计算新的高度
            new_height = height + top + bottom
            
            # 创建新的黑色背景图片
            new_img = Image.new("RGB", (width, new_height), (0, 0, 0))
            
            # 将原图片粘贴到新图片上（留出上边距）
            new_img.paste(img, (0, top))
            
            # 保存处理后的图片
            new_img.save(output_path)
            return True
            
        except Exception as e:
            print(f"✗ 添加黑边失败 {image_path}: {str(e)}")
            return False
    
    def process_images_add_borders(self, image_paths: List[str], output_subdir: str) -> List[str]:
        """批量为图片添加黑边"""
        print("正在为图片添加黑边...")
        
        # 创建处理后图片的输出目录
        output_dir = self.processed_images_dir / output_subdir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        processed_files = []
        
        for img_path in image_paths:
            img_path = Path(img_path)
            output_path = output_dir / img_path.name
            
            if self.add_black_borders(str(img_path), str(output_path)):
                processed_files.append(str(output_path))
                print(f"  ✓ 添加黑边完成: {img_path.name}")
            else:
                print(f"  ✗ 添加黑边失败: {img_path.name}")
        
        print(f"✓ 黑边处理完成，共处理 {len(processed_files)} 张图片")
        return processed_files
    
    def ocr_image(self, image_path: str, lang: str = 'chi_sim+eng') -> str:
        """使用OCR识别图片中的文字"""
        try:
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img, lang=lang)
            return text.strip()
        except Exception as e:
            print(f"✗ OCR识别失败 {image_path}: {str(e)}")
            return ""
    
    def optimize_text_with_ai(self, ocr_text: str, prompt: str = None) -> str:
        """使用AI优化OCR识别的文字"""
        if not prompt:
            prompt = "请将下列OCR识别的文字整理为简洁通顺的文稿，修正错别字和格式问题："
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": ocr_text}
                ],
                max_tokens=2000,
                temperature=0.3
            )
            
            optimized_text = response.choices[0].message.content.strip()
            return optimized_text
            
        except Exception as e:
            print(f"✗ AI文本优化失败: {str(e)}")
            print("  使用原始OCR文字作为备选")
            return ocr_text
    
    def process_images_to_text(self, image_paths: List[str], output_subdir: str, 
                             custom_prompt: str = None) -> List[dict]:
        """批量处理图片并识别文字"""
        print("正在进行OCR文字识别...")
        
        # 创建文本输出目录
        text_output_dir = self.text_dir / output_subdir
        text_output_dir.mkdir(parents=True, exist_ok=True)
        
        results = []
        
        for i, img_path in enumerate(image_paths, 1):
            img_path = Path(img_path)
            print(f"  正在处理 {i}/{len(image_paths)}: {img_path.name}")
            
            # OCR识别
            ocr_text = self.ocr_image(str(img_path))
            
            if not ocr_text:
                print(f"    ✗ 未识别到文字")
                results.append({
                    "image": img_path.name,
                    "status": "failed",
                    "error": "OCR未识别到文字"
                })
                continue
            
            # AI优化（必须使用）
            print(f"    正在使用AI优化文字...")
            final_text = self.optimize_text_with_ai(ocr_text, custom_prompt)
            
            # 保存文字到文件
            txt_filename = img_path.stem + ".txt"
            txt_path = text_output_dir / txt_filename
            
            try:
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(f"=== 图片: {img_path.name} ===\n\n")
                    f.write("=== 原始OCR文字 ===\n")
                    f.write(ocr_text)
                    f.write("\n\n=== AI优化后文字 ===\n")
                    f.write(final_text)
                
                results.append({
                    "image": img_path.name,
                    "text_file": txt_filename,
                    "status": "success",
                    "ocr_text": ocr_text,
                    "final_text": final_text
                })
                
                print(f"    ✓ 文字识别完成: {txt_filename}")
                
            except Exception as e:
                print(f"    ✗ 保存文字失败: {str(e)}")
                results.append({
                    "image": img_path.name,
                    "status": "failed",
                    "error": f"保存失败: {str(e)}"
                })
        
        print(f"✓ 文字识别完成，共处理 {len(results)} 张图片")
        return results
    
    def process_ppt_file(self, ppt_path: str, custom_prompt: str = None, add_borders: bool = True) -> dict:
        """处理单个PPT文件的完整流程"""
        ppt_path = Path(ppt_path)
        
        if not ppt_path.exists():
            return {"error": f"PPT文件不存在: {ppt_path}"}
        
        if not ppt_path.suffix.lower() in ['.ppt', '.pptx']:
            return {"error": f"不支持的文件格式: {ppt_path.suffix}"}
        
        print(f"\n{'='*60}")
        print(f"开始处理PPT文件: {ppt_path.name}")
        print(f"{'='*60}")
        
        # 文件名（不含扩展名）
        file_stem = ppt_path.stem
        
        # 步骤1: PPT转PDF
        pdf_path = self.pdf_dir / f"{file_stem}.pdf"
        if not self.ppt_to_pdf(str(ppt_path), str(pdf_path)):
            return {"error": "PPT转PDF失败"}
        
        # 步骤2: PDF转图片
        image_paths = self.pdf_to_images(str(pdf_path), file_stem)
        if not image_paths:
            return {"error": "PDF转图片失败"}
        
        # 步骤3: 添加黑边（可选）
        if add_borders:
            processed_image_paths = self.process_images_add_borders(image_paths, file_stem)
            final_image_paths = processed_image_paths
        else:
            final_image_paths = image_paths
        
        # 步骤4: OCR识别文字并AI优化
        text_results = self.process_images_to_text(
            final_image_paths, file_stem, custom_prompt
        )
        
        # 生成总结报告
        success_count = len([r for r in text_results if r["status"] == "success"])
        
        result = {
            "ppt_file": ppt_path.name,
            "pdf_file": pdf_path.name,
            "total_pages": len(image_paths),
            "success_count": success_count,
            "failed_count": len(text_results) - success_count,
            "output_directories": {
                "pdf": str(self.pdf_dir),
                "images": str(self.images_dir / file_stem),
                "processed_images": str(self.processed_images_dir / file_stem) if add_borders else None,
                "text_output": str(self.text_dir / file_stem)
            },
            "results": text_results
        }
        
        # 保存处理报告
        report_path = self.output_dir / f"{file_stem}_processing_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\n{'='*60}")
        print(f"处理完成!")
        print(f"总页数: {result['total_pages']}")
        print(f"成功: {result['success_count']}")
        print(f"失败: {result['failed_count']}")
        print(f"处理报告: {report_path}")
        print(f"{'='*60}\n")
        
        return result


def main():
    parser = argparse.ArgumentParser(
        description="PPT转图片并识别文字的完整处理脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python ppt_to_text_processor.py presentation.pptx
  python ppt_to_text_processor.py presentation.pptx --output-dir ./my_output
  python ppt_to_text_processor.py presentation.pptx --custom-prompt "请整理为中文文稿"
  python ppt_to_text_processor.py presentation.pptx --no-borders
        """
    )
    
    parser.add_argument("ppt_file", help="PPT或PPTX文件路径")
    parser.add_argument("--output-dir", default="./output", help="输出目录 (默认: ./output)")
    parser.add_argument("--custom-prompt", help="自定义AI优化提示词")
    parser.add_argument("--no-borders", action="store_true", help="不添加黑边")
    parser.add_argument("--dpi", type=int, default=200, help="图片DPI质量 (默认: 200)")
    
    args = parser.parse_args()
    
    # 检查必要的依赖
    try:
        import comtypes
        import fitz
        import pytesseract
        from PIL import Image
    except ImportError as e:
        print(f"错误: 缺少必要的依赖库: {e}")
        print("\n请安装以下依赖:")
        print("pip install comtypes PyMuPDF pytesseract Pillow")
        print("\n注意: 还需要安装Tesseract OCR:")
        print("- Windows: https://github.com/UB-Mannheim/tesseract/wiki")
        print("- macOS: brew install tesseract")
        print("- Ubuntu: sudo apt install tesseract-ocr")
        sys.exit(1)
    
    # 创建处理器（AI功能已内置）
    processor = PPTToTextProcessor(
        output_dir=args.output_dir
    )
    
    # 处理PPT文件
    start_time = time.time()
    
    result = processor.process_ppt_file(
        ppt_path=args.ppt_file,
        custom_prompt=args.custom_prompt,
        add_borders=not args.no_borders
    )
    
    end_time = time.time()
    
    if "error" in result:
        print(f"处理失败: {result['error']}")
        sys.exit(1)
    
    print(f"总耗时: {end_time - start_time:.2f} 秒")
    print("处理完成!")


if __name__ == "__main__":
    main()
