import os
import fitz  # PyMuPDF
from pptx.util import Pt
from datetime import datetime
from collections import Counter
import re

# 导入我们已经完成的PPT生成器
from .ppt_generator import create_ppt_from_template

def parse_pdf_for_slides(pdf_path: str) -> list:
    """
    通过两遍扫描法和视觉识别，根据字体样式和图形元素智能地从PDF中解析出PPT结构。
    """
    doc = fitz.open(pdf_path)
    
    # --- 视觉识别: 查找所有黑色背景框和带边框的框 ---
    code_rects_by_page = {}
    bordered_rects_by_page = {}

    for i, page in enumerate(doc):
        code_rects_by_page[i] = []
        bordered_rects_by_page[i] = []

        drawings = page.get_drawings()
        for d in drawings:
            rect = d.get("rect")
            if not rect: continue

            is_black_fill = d.get("fill") == (0.0, 0.0, 0.0)
            if is_black_fill:
                code_rects_by_page[i].append(rect)
                continue

            has_black_stroke = d.get("stroke") == (0.0, 0.0, 0.0)
            is_transparent_fill = d.get("fill") is None or d.get("fill_opacity") == 0
            if has_black_stroke and is_transparent_fill:
                 bordered_rects_by_page[i].append(rect)

    # --- 第一遍扫描: 侦察并确定主标题和小标题的样式 (通用逻辑) ---
    style_counter = Counter()
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if b['type'] == 0:
                for l in b["lines"]:
                    for s in l["spans"]:
                        if s["text"].strip():
                            style_key = (round(s["size"], 1), "bold" in s["font"].lower())
                            style_counter[style_key] += 1
    
    if not style_counter: return []
    bold_styles = [s for s in style_counter if s[1]]
    if not bold_styles: return []
    
    main_title_style = max(bold_styles, key=lambda s: s[0])
    subtitle_styles = [s for s in bold_styles if s[0] < main_title_style[0]]
    subtitle_style = max(subtitle_styles, key=style_counter.get) if subtitle_styles else None

    # --- 第二遍扫描: 根据样式和视觉区域，构建幻灯片 ---
    slides_content = []
    main_title_text = ""
    current_title = ""
    current_content_parts = []

    for i, page in enumerate(doc):
        page_code_rects = code_rects_by_page[i]
        page_bordered_rects = bordered_rects_by_page[i]
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if b['type'] == 0:
                block_rect = fitz.Rect(b["bbox"])
                
                is_in_code_box = any(block_rect.intersects(code_rect) for code_rect in page_code_rects)
                is_in_bordered_box = any(block_rect.intersects(bordered_rect) for bordered_rect in page_bordered_rects)

                if is_in_code_box:
                    for l in b["lines"]:
                        line_text = "".join([s["text"] for s in l["spans"]]).strip()
                        if line_text and current_title:
                            current_content_parts.append(f"```{line_text}```")
                    continue
                elif is_in_bordered_box:
                    for l in b["lines"]:
                        line_text = "".join([s["text"] for s in l["spans"]]).strip()
                        if line_text and current_title:
                            current_content_parts.append(f"[BOXED]{line_text}[/BOXED]")
                    continue
                else:
                    for l in b["lines"]:
                        line_text_parts = [s["text"].strip() for s in l["spans"] if s["text"].strip()]
                        if not line_text_parts: continue
                        
                        is_title_line = False
                        if subtitle_style:
                            for s in l["spans"]:
                                span_style = (round(s["size"], 1), "bold" in s["font"].lower())
                                if span_style == subtitle_style:
                                    is_title_line = True
                                    break
                        
                        main_title_span_style = (round(l["spans"][0]["size"],1), "bold" in l["spans"][0]["font"].lower())
                        line_text = " ".join(line_text_parts)

                        if main_title_span_style == main_title_style and not main_title_text:
                            main_title_text = line_text
                        elif is_title_line:
                            if current_title:
                                slides_content.append({"title": current_title, "content": "\n".join(current_content_parts)})
                            current_title = line_text
                            current_content_parts = []
                        else:
                            if current_title:
                                current_content_parts.append(line_text)

    if current_title:
        slides_content.append({"title": current_title, "content": "\n".join(current_content_parts)})

    if main_title_text:
        slides_content.insert(0, {"title": main_title_text, "content": "由PDF自动生成"})
    else:
        pdf_filename = os.path.basename(pdf_path).replace(".pdf", "")
        slides_content.insert(0, {"title": pdf_filename, "content": "由PDF自动生成"})
        
    return slides_content

if __name__ == '__main__':
    current_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(current_dir, '..', '..')
    
    pdf_file = os.path.join(backend_dir, 'pptx', 'CSSセレクタとカスケーディングルール.pdf')
    template_file = os.path.join(backend_dir, 'pptx', 'ppt模板.pptx')
    
    if not os.path.exists(pdf_file):
        print(f"错误: PDF文件未找到于 {pdf_file}")
    elif not os.path.exists(template_file):
        print(f"错误: 模板PPT未找到于 {template_file}")
    else:
        print(f"开始解析PDF: {os.path.basename(pdf_file)}...")
        slides_data = parse_pdf_for_slides(pdf_file)
        
        if slides_data:
            print(f"成功解析出 {len(slides_data)} 张幻灯片内容。")
            
            main_title = slides_data[0]['title']
            safe_filename = "".join([c for c in main_title if c not in r'\\/:*?"<>|']) + ".pptx"
            output_path = os.path.join(backend_dir, 'outputs', safe_filename)
            
            print(f"开始生成PPT: {safe_filename}...")
            create_ppt_from_template(template_file, output_path, slides_data)
            print("PPT生成完毕！") 