"""
LLM OCR处理器
使用通义千问 VL OCR 模型进行PDF OCR识别
支持数据清洗和优化处理
"""

import os
import json
import re
import base64
import time
import requests
import io
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

import fitz
from PIL import Image


@dataclass
class PageHeaderFooter:
    """页眉页脚信息"""
    header: str = ""
    footer: str = ""
    page_number: Optional[int] = None
    page_number_text: str = ""


@dataclass
class ProcessedPage:
    """处理后的页面数据"""
    pdf_page_number: int
    ocr_page_number: Optional[int] = None
    ocr_page_number_text: str = ""
    header: str = ""
    footer: str = ""
    header_is_new: bool = False
    footer_is_new: bool = False
    text: str = ""
    text_length: int = 0
    raw_text: str = ""


class QwenVLOCRProcessor:
    """通义千问 VL OCR 处理器"""

    WATERMARK_PATTERNS = [
        r'E\d{8,}\s*LI\s*YUAN\s*Z?\s*H?\s*E?\s*N?\s*\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}',
        r'E\d{8,}\s*LIYUAN\s*[A-Z]*\s*\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}',
        r'E\d{8,}\s*LI\s*YUAN\s*[A-Z\s]*\d{4}/\d{2}/\d{2}',
        r'E\d+\s+LI\s*YUAN.*\d{4}/\d{2}/\d{2}.*',
        r'E\d{8,}.*LI.*YUAN.*\d{4}.*',
    ]

    HEADER_PATTERNS = [
        r'^第[一二三四五六七八九十百千]+編.+',
        r'^第[一二三四五六七八九十百千]+章.+',
        r'^第[一二三四五六七八九十百千]+節.+',
        r'^[一二三四五六七八九十]+、.+',
    ]

    PAGE_NUMBER_PATTERNS = [
        r'[　\s]*([一二三四五六七八九十百]+)[　\s]*$',
        r'[　\s]*(\d+)[　\s]*$',
        r'^[　\s]*[-－—]*\s*([一二三四五六七八九十百]+)\s*[-－—]*[　\s]*$',
        r'^[　\s]*[-－—]*\s*(\d+)\s*[-－—]*[　\s]*$',
    ]

    KANJI_NUM_MAP = {
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '二十': 20, '三十': 30, '四十': 40, '五十': 50,
        '六十': 60, '七十': 70, '八十': 80, '九十': 90, '百': 100
    }

    def __init__(self, pdf_path: str, output_dir: str, api_key: str = None):
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.images_dir = os.path.join(output_dir, 'images')
        self.ocr_output_dir = os.path.join(output_dir, 'llm_ocr_output')
        self.final_output_dir = os.path.join(output_dir, 'final')
        
        if api_key is None:
            api_key = self._load_api_key_from_config()
        self.api_key = api_key
        self.model = 'qwen-vl-ocr-latest'
        
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.ocr_output_dir, exist_ok=True)
        os.makedirs(self.final_output_dir, exist_ok=True)
        
        self.previous_header: str = ""
        self.previous_footer: str = ""
        self.header_footer_history: List[Dict[str, Any]] = []

    def _load_api_key_from_config(self) -> str:
        """从配置文件加载API key"""
        project_root = Path(__file__).parent.parent
        config_path = os.path.join(project_root, 'config', 'api_key.txt')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
                for line in content.strip().split('\n'):
                    if 'qwen' in line.lower() or 'dashscope' in line.lower():
                        parts = line.split('=')
                        if len(parts) >= 2:
                            return parts[1].strip()
        
        config_json_path = os.path.join(project_root, 'config', 'api_config.json')
        if os.path.exists(config_json_path):
            try:
                with open(config_json_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if 'dashscope' in config and 'api_key' in config['dashscope']:
                        return config['dashscope']['api_key']
            except:
                pass
        
        return os.getenv('DASHSCOPE_API_KEY', '')

    def convert_pdf_to_images(self, start_page: int, end_page: int, dpi: int = 150) -> List[str]:
        """
        将PDF页面转换为图片
        
        Args:
            start_page: 起始页码（1-based）
            end_page: 结束页码（1-based）
            dpi: 图片分辨率
            
        Returns:
            List[str]: 生成的图片路径列表
        """
        print(f"\n[步骤1] 转换PDF为图片 (DPI={dpi})...")
        
        doc = fitz.open(self.pdf_path)
        image_paths = []
        
        for page_num in range(start_page - 1, end_page):
            page = doc[page_num]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            
            image_path = os.path.join(self.images_dir, f'page_{page_num + 1:04d}.png')
            pix.save(image_path)
            image_paths.append(image_path)
            print(f"  转换第 {page_num + 1} 页完成")
        
        doc.close()
        print(f"  共转换 {len(image_paths)} 页")
        
        return image_paths

    def image_to_base64(self, image_path: str, max_size_mb: float = 8.0) -> str:
        """
        将图片转换为base64编码，自动压缩以符合API限制
        
        Args:
            image_path: 图片路径
            max_size_mb: 最大文件大小（MB），默认8MB（API限制10MB）
            
        Returns:
            str: base64编码的图片
        """
        img = Image.open(image_path)
        
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        quality = 85
        while quality >= 20:
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=quality, optimize=True)
            size_mb = len(buffer.getvalue()) / (1024 * 1024)
            
            if size_mb <= max_size_mb:
                return base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            quality -= 10
        
        max_dimension = 2000
        while max_dimension >= 800:
            img_resized = img.copy()
            img_resized.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            img_resized.save(buffer, format='JPEG', quality=70, optimize=True)
            size_mb = len(buffer.getvalue()) / (1024 * 1024)
            
            if size_mb <= max_size_mb:
                return base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            max_dimension -= 200
        
        buffer = io.BytesIO()
        img.thumbnail((800, 800), Image.Resampling.LANCZOS)
        img.save(buffer, format='JPEG', quality=50, optimize=True)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    def call_qwen_vl_ocr(self, image_path: str, language: str = 'ja') -> str:
        """
        调用通义千问 VL OCR API (使用OpenAI兼容接口)
        
        Args:
            image_path: 图片路径
            language: 语言代码
            
        Returns:
            str: 识别的文本
        """
        from openai import OpenAI
        
        image_base64 = self.image_to_base64(image_path)
        image_url = f"data:image/jpeg;base64,{image_base64}"
        
        language_prompts = {
            'ja': 'この画像は日本語の歴史文書です。画像内のすべてのテキストを正確に認識し、元のレイアウトと構造を維持して出力してください。ヘッダー、フッター、ページ番号も含めてください。',
            'zh': '这是一张中文历史文献图片。请准确识别图片中的所有文字，保持原有的版面结构和格式输出。包括页眉、页脚和页码。',
            'en': 'This is a historical document image. Please accurately recognize all text in the image, maintaining the original layout and structure. Include headers, footers, and page numbers.'
        }
        
        prompt = language_prompts.get(language, language_prompts['ja'])
        
        try:
            client = OpenAI(
                api_key=self.api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            
            completion = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url}
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )
            
            return completion.choices[0].message.content
            
        except Exception as e:
            print(f"  OCR调用错误: {e}")
            return f"[OCR错误: {e}]"

    def process_all_pages(self, start_page: int, end_page: int) -> List[ProcessedPage]:
        """
        处理所有页面
        
        Args:
            start_page: 起始页码
            end_page: 结束页码
            
        Returns:
            List[ProcessedPage]: 处理后的页面列表
        """
        image_paths = self.convert_pdf_to_images(start_page, end_page)
        
        print(f"\n[步骤2] 执行LLM OCR识别...")
        results = []
        
        for i, image_path in enumerate(image_paths):
            page_num = start_page + i
            print(f"  正在识别第 {page_num} 页...")
            
            raw_text = self.call_qwen_vl_ocr(image_path, language='ja')
            
            txt_path = os.path.join(self.ocr_output_dir, f'page_{page_num:04d}.txt')
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(raw_text)
            
            processed_page = self.process_page(page_num, raw_text)
            results.append(processed_page)
            
            print(f"  第 {page_num} 页识别完成，字符数: {processed_page.text_length}")
            
            time.sleep(1)
        
        return results

    def remove_all_watermarks(self, text: str) -> str:
        """彻底移除所有水印变体"""
        cleaned = text
        
        for pattern in self.WATERMARK_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        cleaned = re.sub(r'E\d{8,}', '', cleaned)
        cleaned = re.sub(r'LI\s*YUAN\s*[A-Z]*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}', '', cleaned)
        
        cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)
        
        return cleaned.strip()

    def clean_text(self, text: str) -> str:
        """基础文本清洗"""
        if not text:
            return ""
        
        cleaned = text
        cleaned = re.sub(r'\r\n', '\n', cleaned)
        cleaned = re.sub(r'\r', '\n', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        cleaned = cleaned.replace('\u3000', ' ')
        cleaned = re.sub(r'^\s+|\s+$', '', cleaned, flags=re.MULTILINE)
        
        return cleaned.strip()

    def fix_ocr_errors(self, text: str) -> str:
        """修复常见OCR识别错误"""
        if not text:
            return ""
        
        fixes = [
            (r'視', '察'),
            (r'難', '難'),
            (r'既', '既'),
            (r'突', '突'),
            (r'者', '者'),
            (r'祐', '予'),
            (r'禍', '禍'),
            (r'禎', '徳'),
            (r'穀', '徳'),
        ]
        
        for pattern, replacement in fixes:
            text = re.sub(pattern, replacement, text)
        
        return text

    def clean_html_tags(self, text: str) -> str:
        """清理HTML标签和代码块标记"""
        if not text:
            return ""
        
        text = re.sub(r'```html\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = re.sub(r'<html[^>]*>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'</html>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<body[^>]*>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'</body>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<p[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        text = text.strip()
        
        return text

    def kanji_to_number(self, kanji: str) -> Optional[int]:
        """将汉字数字转换为阿拉伯数字"""
        kanji = kanji.strip()
        
        if kanji in self.KANJI_NUM_MAP:
            return self.KANJI_NUM_MAP[kanji]
        
        if '十' in kanji:
            match = re.match(r'([一二三四五六七八九])?十([一二三四五六七八九])?', kanji)
            if match:
                tens = self.KANJI_NUM_MAP.get(match.group(1), 0) if match.group(1) else 1
                ones = self.KANJI_NUM_MAP.get(match.group(2), 0) if match.group(2) else 0
                return tens * 10 + ones
        
        try:
            return int(kanji)
        except ValueError:
            return None

    def extract_page_number(self, text: str) -> Tuple[Optional[int], str, str]:
        """从文本中提取PDF页码"""
        lines = text.strip().split('\n')
        
        for pattern in self.PAGE_NUMBER_PATTERNS:
            for i in range(len(lines) - 1, max(-1, len(lines) - 5), -1):
                line = lines[i].strip()
                match = re.search(pattern, line, re.MULTILINE)
                if match:
                    page_text = match.group(1) if match.groups() else match.group(0)
                    page_num = self.kanji_to_number(page_text)
                    
                    if page_num is not None:
                        remaining_lines = lines[:i] + lines[i+1:]
                        remaining_text = '\n'.join(remaining_lines)
                        return page_num, page_text, remaining_text
        
        for i in range(len(lines)):
            line = lines[i].strip()
            for pattern in self.PAGE_NUMBER_PATTERNS:
                match = re.search(pattern, line, re.MULTILINE)
                if match:
                    page_text = match.group(1) if match.groups() else match.group(0)
                    page_num = self.kanji_to_number(page_text)
                    
                    if page_num is not None:
                        remaining_lines = lines[:i] + lines[i+1:]
                        remaining_text = '\n'.join(remaining_lines)
                        return page_num, page_text, remaining_text
        
        return None, "", text

    def detect_header_footer(self, text: str) -> Tuple[str, str, str]:
        """检测页眉和页脚"""
        lines = text.strip().split('\n')
        if not lines:
            return "", "", ""
        
        header = ""
        footer = ""
        body_start = 0
        body_end = len(lines)
        
        for i, line in enumerate(lines[:3]):
            line_stripped = line.strip()
            for pattern in self.HEADER_PATTERNS:
                if re.match(pattern, line_stripped):
                    header = line_stripped
                    body_start = i + 1
                    break
            if header:
                break
        
        for i in range(len(lines) - 1, max(body_start, len(lines) - 4), -1):
            line_stripped = lines[i].strip()
            if line_stripped and len(line_stripped) < 50:
                for pattern in self.HEADER_PATTERNS:
                    if re.match(pattern, line_stripped):
                        footer = line_stripped
                        body_end = i
                        break
                if footer:
                    break
        
        body = '\n'.join(lines[body_start:body_end])
        
        return header, footer, body

    def process_page(self, pdf_page_num: int, raw_text: str) -> ProcessedPage:
        """处理单个页面"""
        text_no_html = self.clean_html_tags(raw_text)
        text_no_watermark = self.remove_all_watermarks(text_no_html)
        text_cleaned = self.clean_text(text_no_watermark)
        text_fixed = self.fix_ocr_errors(text_cleaned)
        
        ocr_page_num, ocr_page_text, text_without_page = self.extract_page_number(text_fixed)
        
        header, footer, body = self.detect_header_footer(text_without_page)
        
        header_is_new = header != self.previous_header and header != ""
        footer_is_new = footer != self.previous_footer and footer != ""
        
        if header_is_new:
            self.previous_header = header
        if footer_is_new:
            self.previous_footer = footer
        
        return ProcessedPage(
            pdf_page_number=pdf_page_num,
            ocr_page_number=ocr_page_num,
            ocr_page_number_text=ocr_page_text,
            header=header,
            footer=footer,
            header_is_new=header_is_new,
            footer_is_new=footer_is_new,
            text=body,
            text_length=len(body),
            raw_text=raw_text
        )

    def export_json(self, pages: List[ProcessedPage], output_path: str):
        """导出JSON格式"""
        data = {
            'metadata': {
                'processing_date': datetime.now().isoformat(),
                'ocr_method': 'qwen-vl-ocr-latest',
                'total_pages': len(pages),
                'total_characters': sum(p.text_length for p in pages)
            },
            'header_footer_changes': [],
            'pages': []
        }
        
        for page in pages:
            if page.header_is_new or page.footer_is_new:
                data['header_footer_changes'].append({
                    'pdf_page': page.pdf_page_number,
                    'ocr_page': page.ocr_page_number,
                    'header': page.header if page.header_is_new else None,
                    'footer': page.footer if page.footer_is_new else None
                })
            
            page_data = {
                'pdf_page_number': page.pdf_page_number,
                'ocr_page_number': page.ocr_page_number,
                'ocr_page_number_text': page.ocr_page_number_text,
                'header': page.header,
                'footer': page.footer,
                'text': page.text,
                'text_length': page.text_length
            }
            data['pages'].append(page_data)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"JSON导出: {output_path}")

    def export_txt(self, pages: List[ProcessedPage], output_path: str):
        """导出TXT格式"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("伊藤博文伝 中-1 OCR识别结果 (LLM OCR版)\n")
            f.write(f"处理时间: {datetime.now().isoformat()}\n")
            f.write(f"OCR方法: qwen-vl-ocr-latest\n")
            f.write(f"总页数: {len(pages)}\n")
            f.write(f"总字符数: {sum(p.text_length for p in pages)}\n")
            f.write("=" * 60 + "\n\n")
            
            current_header = ""
            current_footer = ""
            
            for page in pages:
                if page.header and page.header != current_header:
                    f.write(f"【页眉变更】{page.header}\n")
                    f.write("-" * 40 + "\n\n")
                    current_header = page.header
                
                f.write(f"【PDF第{page.pdf_page_number}页")
                if page.ocr_page_number:
                    f.write(f" / 原书第{page.ocr_page_number_text}页")
                f.write("】\n")
                f.write("-" * 40 + "\n")
                
                if page.text:
                    f.write(page.text)
                    if not page.text.endswith('\n'):
                        f.write('\n')
                else:
                    f.write("[无内容]\n")
                
                f.write("\n" + "=" * 60 + "\n\n")
        
        print(f"TXT导出: {output_path}")

    def export_csv(self, pages: List[ProcessedPage], output_path: str):
        """导出CSV格式"""
        import csv
        
        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['PDF页码', '原书页码', '页眉', '页脚', '文本长度', '文本内容'])
            
            for page in pages:
                text = page.text.replace('\n', '\\n')
                writer.writerow([
                    page.pdf_page_number,
                    page.ocr_page_number_text if page.ocr_page_number_text else '',
                    page.header,
                    page.footer,
                    page.text_length,
                    text
                ])
        
        print(f"CSV导出: {output_path}")

    def run(self, start_page: int, end_page: int) -> Dict[str, Any]:
        """运行完整处理流程"""
        print("=" * 60)
        print("LLM OCR处理 (通义千问 VL OCR)")
        print("=" * 60)
        
        print("\n[步骤1] 加载并处理页面...")
        pages = self.process_all_pages(start_page, end_page)
        print(f"  处理了 {len(pages)} 页")
        
        print("\n[步骤2] 统计信息...")
        total_chars = sum(p.text_length for p in pages)
        pages_with_ocr_num = sum(1 for p in pages if p.ocr_page_number is not None)
        header_changes = sum(1 for p in pages if p.header_is_new)
        footer_changes = sum(1 for p in pages if p.footer_is_new)
        
        print(f"  总字符数: {total_chars}")
        print(f"  识别到原书页码: {pages_with_ocr_num} 页")
        print(f"  页眉变更次数: {header_changes}")
        print(f"  页脚变更次数: {footer_changes}")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        print("\n[步骤3] 导出结果...")
        self.export_json(pages, os.path.join(self.final_output_dir, f'llm_ocr_result_{timestamp}.json'))
        self.export_txt(pages, os.path.join(self.final_output_dir, f'llm_ocr_result_{timestamp}.txt'))
        self.export_csv(pages, os.path.join(self.final_output_dir, f'llm_ocr_result_{timestamp}.csv'))
        
        print("\n" + "=" * 60)
        print("LLM OCR处理完成!")
        print(f"输出目录: {self.final_output_dir}")
        print("=" * 60)
        
        return {
            'pages': pages,
            'statistics': {
                'total_pages': len(pages),
                'total_characters': total_chars,
                'pages_with_ocr_number': pages_with_ocr_num,
                'header_changes': header_changes,
                'footer_changes': footer_changes
            }
        }


def main():
    project_root = Path(__file__).parent.parent
    pdf_path = os.path.join(project_root, '伊藤博文伝 中-1.pdf')
    output_dir = os.path.join(project_root, 'data', 'output', 'ocr_results')
    
    processor = QwenVLOCRProcessor(pdf_path, output_dir)
    result = processor.run(start_page=41, end_page=60)
    
    return result


if __name__ == '__main__':
    main()
