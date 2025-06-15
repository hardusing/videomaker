# videomaker/backend/app/utils/ppt_generator.py
import os
import re
from pptx import Presentation
from pptx.util import Inches, Pt, Cm
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

def create_ppt_from_template(template_path: str, output_path: str, slides_data: list):
    """
    根据PPTX模板创建新的演示文稿，并应用自定义格式。
    会先清空模板中所有已存在的幻灯片，然后根据数据重新生成。

    :param template_path: 模板文件的路径
    :param output_path: 生成的PPTX文件的保存路径
    :param slides_data: 一个包含幻灯片数据的列表，每个元素是一个字典，
                        例如: [{'title': '标题', 'content': '内容'}, ...]
    """
    prs = Presentation(template_path)
    # 定义颜色
    title_color = RGBColor(9, 87, 161) # 精确颜色 #0957A1
    black_color = RGBColor(0, 0, 0) # 黑色

    # --- 清空模板中所有已存在的幻灯片 ---
    # 通过直接操作XML列表来移除所有幻灯片引用
    sldIdLst = prs.slides._sldIdLst
    for i in range(len(sldIdLst) - 1, -1, -1):
        sldId = sldIdLst[i]
        prs.part.drop_rel(sldId.rId)
        del sldIdLst[i]
    # ------------------------------------

    # 假设模板的布局：
    # 0: 标题幻灯片
    # 1: 标题和内容
    title_slide_layout = prs.slide_layouts[0]
    content_slide_layout = prs.slide_layouts[1]

    for i, slide_data in enumerate(slides_data):
        if i == 0 and 'title' in slide_data:
            # --- 生成第一页 (标题页) ---
            # 规则 1: 移除模板中的副标题占位符，确保页面上只有主标题。
            # 这样可以防止不可见的文本框影响主标题的居中。
            slide = prs.slides.add_slide(title_slide_layout)

            # 通常副标题是第二个占位符(placeholders[1])
            if len(slide.placeholders) > 1:
                subtitle_shape = slide.placeholders[1]
                sp_element = subtitle_shape._element
                sp_element.getparent().remove(sp_element)

            # 规则 2: 将主标题的形状调整为与整个幻灯片页面一样大。
            # 这是实现完美居中的关键步骤。
            title_shape = slide.shapes.title
            title_shape.left = 0
            title_shape.top = 0
            title_shape.width = prs.slide_width
            title_shape.height = prs.slide_height

            # 规则 3: 设置标题的格式。
            # - 垂直居中 (MSO_ANCHOR.MIDDLE)
            # - 水平居中 (PP_ALIGN.CENTER)
            # - 字体: 'Microsoft YaHei', 粗体, 40pt
            # - 颜色: #0957A1
            title_shape.text = slide_data.get('title', '默认标题')
            text_frame = title_shape.text_frame
            text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE # 垂直居中
            
            p_title = text_frame.paragraphs[0]
            p_title.alignment = PP_ALIGN.CENTER # 水平居中
            p_title.font.name = 'Microsoft YaHei'
            p_title.font.bold = True # 设置为粗体
            p_title.font.size = Pt(40)
            p_title.font.color.rgb = title_color

        else:
            # --- 生成内容页 ---
            slide = prs.slides.add_slide(content_slide_layout)
            
            # --- 规则 4 & 6: 内容页标题格式与布局 ---
            # - 使用用户指定的精确厘米值进行布局
            # - 位置: (X=2.01cm, Y=3.2cm), 高度: 2.19cm
            
            # --- 标题框位置与尺寸 ---
            title_shape = slide.shapes.title
            title_shape.left = Cm(2.01)
            title_shape.top = Cm(3.2)
            title_shape.width = prs.slide_width - (Cm(2.01) * 2) # 保持左右边距对称
            title_shape.height = Cm(2.19)

            p_title = title_shape.text_frame.paragraphs[0]
            p_title.text = slide_data.get('title', f'第 {i+1} 页')
            p_title.alignment = PP_ALIGN.LEFT # 左对齐
            p_title.font.name = 'Microsoft YaHei'
            p_title.font.bold = True # 设置为粗体
            p_title.font.size = Pt(20)
            p_title.font.color.rgb = title_color

            # --- 规则 5: 内容页正文格式 ---
            # - 使用 ```...``` 标记来区分代码和普通文本
            # - 普通文本: 'Microsoft YaHei', 16pt, 黑色
            # - 代码文本: 'Source Code Pro', 16pt, 黑色
            # - 行间距: 1.5
            # - 布局: 自动调整以适应精确的标题布局
            if len(slide.placeholders) > 1:
                body_shape = slide.placeholders[1]
                
                # --- 内容框位置与尺寸 ---
                body_shape.left = Cm(2.01)
                # (标题Top + 标题Height + 0.5cm 间距)
                body_shape.top = Cm(3.2 + 2.19 + 0.5)
                body_shape.width = prs.slide_width - (Cm(2.01) * 2)
                # (幻灯片高度 - 内容框Top - 底部边距)
                body_shape.height = prs.slide_height - body_shape.top - Cm(2.01)
                
                if body_shape:
                    tf = body_shape.text_frame
                    tf.clear()
                    # 清空后，默认会有一个空段落，我们从这个段落开始
                    p = tf.paragraphs[0]
                    first_run_in_frame = True # 标记是否是文本框的第一个run

                    content = slide_data.get('content', '')
                    # 使用正则表达式按 ```...``` 分割内容
                    parts = re.split(r'(```.*?```)', content, flags=re.DOTALL)

                    for part in parts:
                        if not part: continue

                        is_code = part.startswith('```') and part.endswith('```')
                        if is_code:
                            text = part[3:-3].strip('\n') # 移除标记和首尾换行
                            font_name = 'Source Code Pro'
                        else:
                            text = part
                            font_name = 'Microsoft YaHei'
                        
                        lines = text.split('\n')
                        for line_index, line_text in enumerate(lines):
                            # 如果不是文本框的第一个run，就新起一个段落
                            if not first_run_in_frame:
                                p = tf.add_paragraph()
                            
                            run = p.add_run()
                            run.text = line_text
                            run.font.name = font_name
                            run.font.size = Pt(16)
                            run.font.color.rgb = black_color
                            p.line_spacing = 1.5
                            
                            first_run_in_frame = False # 后续都不是第一个run了

    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    prs.save(output_path)
    print(f"演示文稿已保存至: {output_path}")

if __name__ == '__main__':
    # 使用示例
    # __file__ 是当前脚本的路径, 我们需要找到项目根目录然后定位到模板和输出目录
    
    # 获取当前脚本所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 定位到 backend 目录
    backend_dir = os.path.join(current_dir, '..', '..')
    
    template = os.path.join(backend_dir, 'pptx', 'ppt模板.pptx')
    output_dir_path = os.path.join(backend_dir, 'outputs') # 定义输出目录
    
    # 幻灯片内容
    slides_content = [
        {
            'title': '掌握 HTML 文档结构与常用标签',
            'content': 'Web 前端基础入门'
        },
        {
            'title': '什么是 HTML?',
            'content': 'HTML 全称超文本标记语言 (HyperText Markup Language)，是构建网页和网络应用的标准语言。\n它并非编程语言，而是一种标记语言，通过不同的"标签"来定义页面内容的结构和含义。'
        },
        {
            'title': 'HTML 文档基本结构',
            'content': '每个HTML文档都遵循一个标准结构，就像一本书有封面、目录和正文。\n这是一个最基础的HTML5文档示例：\n```<!DOCTYPE html>\n<html>\n<head>\n  <title>页面标题</title>\n</head>\n<body>\n  <h1>我的第一个标题</h1>\n  <p>我的第一个段落。</p>\n</body>\n</html>```'
        },
        {
            'title': '文档头部 <head>',
            'content': '<head> 元素包含了文档的"元数据"，这些信息不会直接显示在页面上，但对浏览器和搜索引擎至关重要。\n- ```<title>```: 定义浏览器标签页上显示的标题。\n- ```<meta charset="UTF-8">```: 指定文档使用的字符编码。\n- ```<link rel="stylesheet" href="styles.css">```: 链接外部CSS样式表。'
        },
        {
            'title': '文档主体 <body>',
            'content': '<body> 元素包含了用户在浏览器中看到的所有可见内容，是网页的"血肉"。\n所有的文本、图片、链接、表格、表单等元素都应放置在 ```<body>``` 标签内部。'
        },
        {
            'title': '常用标签：标题和段落',
            'content': '标题和段落是文本内容的基础。\n- 标题 (Headings): 使用 ```<h1>``` 到 ```<h6>``` 标签定义，h1最重要，h6最次要。\n- 段落 (Paragraphs): 使用 ```<p>``` 标签定义一个文本段落。\n```<h1>这是最重要的标题</h1>\n<p>这是一个段落。</p>```'
        },
        {
            'title': '常用标签：列表',
            'content': '列表用于组织和展示项目集合。\n- 无序列表 (Unordered List): 使用 ```<ul>``` 和 ```<li>```。\n```<ul>\n  <li>苹果</li>\n  <li>香蕉</li>\n</ul>```\n- 有序列表 (Ordered List): 使用 ```<ol>``` 和 ```<li>```。\n```<ol>\n  <li>第一步</li>\n  <li>第二步</li>\n</ol>```'
        },
        {
            'title': '常用标签：链接',
            'content': '链接 (Anchor) 是超文本的核心，使用 ```<a>``` 标签创建。\n- `href` 属性指定链接的目标地址。\n- 标签内的文本是用户可点击的部分。\n```<a href="https://www.google.com">点击这里访问谷歌</a>```'
        },
        {
            'title': '常用标签：图片',
            'content': '图片使用 ```<img>``` 标签嵌入到页面中。这是一个自闭合标签。\n- `src` 属性指定图片的来源地址。\n- `alt` 属性提供图片的替代文本，用于可访问性和图片加载失败的情况。\n```<img src="logo.png" alt="网站Logo">```'
        },
        {
            'title': '常用标签：文本格式化',
            'content': '除了标题和段落，还有一些标签用于给予文本特殊的语义或样式。\n- ```<strong>```: 表示重要的文本（通常显示为粗体）。\n- ```<em>```: 表示强调的文本（通常显示为斜体）。\n- ```<code>```: 表示一段计算机代码（常用于行内代码）。'
        },
        {
            'title': '常用标签：表格',
            'content': '表格用于展示结构化的二维数据。\n```<table>\n  <tr>\n    <th>姓名</th>\n    <th>年龄</th>\n  </tr>\n  <tr>\n    <td>张三</td>\n    <td>25</td>\n  </tr>\n</table>```'
        },
        {
            'title': '常用标签：表单',
            'content': '表单用于收集用户输入。\n```<form action="/submit">\n  <label for="username">用户名:</label><br>\n  <input type="text" id="username" name="username"><br>\n  <input type="submit" value="提交">\n</form>```'
        },
        {
            'title': '总结',
            'content': '今天我们学习了HTML的基本骨架和最常用的标签。\n- HTML定义了网页的结构和内容。\n- 标签是HTML的基石，大部分标签都是成对出现的。\n- 不断练习是掌握这些标签的最好方法。'
        }
    ]
    
    # --- 根据第一页标题自动生成文件名 ---
    # 获取标题文本
    first_page_title = slides_content[0].get('title', 'generated_presentation')
    # 移除windows文件名中的非法字符
    safe_filename = "".join([c for c in first_page_title if c not in r'\\/:*?"<>|']) + ".pptx"
    output_file_path = os.path.join(output_dir_path, safe_filename)
    # ------------------------------------
    
    # 检查模板文件是否存在
    if not os.path.exists(template):
        print(f"错误：模板文件未找到，路径: {template}")
    else:
        create_ppt_from_template(template, output_file_path, slides_content) 