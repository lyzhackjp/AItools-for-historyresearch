import os
import fitz
from PIL import Image
import io
from typing import List, Dict, Any, Optional, Tuple
import json


class PDFProcessor:
    """PDF文档处理模块 - 支持PDF转图片和版面分析"""

    def __init__(self, output_dir: str = './output'):
        """
        初始化PDF处理器

        Args:
            output_dir: 输出目录路径
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def pdf_to_images(self, pdf_path: str, output_dir: Optional[str] = None,
                      dpi: int = 300, format: str = 'PNG') -> List[str]:
        """
        将PDF文档转换为图片

        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录（可选）
            dpi: 图片分辨率（默认300 DPI）
            format: 输出格式（PNG/JPEG）

        Returns:
            list: 生成的图片文件路径列表
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        output_path = output_dir or os.path.join(self.output_dir, 'images')
        os.makedirs(output_path, exist_ok=True)

        doc = fitz.open(pdf_path)
        image_paths = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)

            pix = page.get_pixmap(matrix=mat)

            output_file = os.path.join(output_path, f'page_{page_num + 1:04d}.{format.lower()}')
            pix.save(output_file)
            image_paths.append(output_file)

        doc.close()
        return image_paths

    def pdf_to_images_from_bytes(self, pdf_bytes: bytes, output_dir: Optional[str] = None,
                                  dpi: int = 300, format: str = 'PNG') -> List[bytes]:
        """
        将PDF字节流转换为图片字节流列表

        Args:
            pdf_bytes: PDF文件字节流
            output_dir: 输出目录（可选）
            dpi: 图片分辨率
            format: 输出格式

        Returns:
            list: 图片字节流列表
        """
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        image_bytes_list = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)

            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes(format.lower())
            image_bytes_list.append(img_bytes)

        doc.close()
        return image_bytes_list

    def analyze_layout(self, image_path: str) -> Dict[str, Any]:
        """
        分析图片版面，识别正文区域、页眉页脚等

        Args:
            image_path: 图片文件路径

        Returns:
            dict: 版面分析结果
        """
        img = Image.open(image_path)
        width, height = img.size

        result = {
            'image_path': image_path,
            'size': {'width': width, 'height': height},
            'header_region': None,
            'footer_region': None,
            'main_content_region': None,
            'margins': {'top': 0, 'bottom': 0, 'left': 0, 'right': 0}
        }

        header_height_ratio = 0.08
        footer_height_ratio = 0.08

        header_region = {
            'y_start': 0,
            'y_end': int(height * header_height_ratio),
            'x_start': 0,
            'x_end': width
        }

        footer_region = {
            'y_start': int(height * (1 - footer_height_ratio)),
            'y_end': height,
            'x_start': 0,
            'x_end': width
        }

        margin_ratio = 0.05
        main_content_region = {
            'y_start': int(height * header_height_ratio),
            'y_end': int(height * (1 - footer_height_ratio)),
            'x_start': int(width * margin_ratio),
            'x_end': int(width * (1 - margin_ratio))
        }

        result['header_region'] = header_region
        result['footer_region'] = footer_region
        result['main_content_region'] = main_content_region
        result['margins'] = {
            'top': int(height * header_height_ratio),
            'bottom': int(height * footer_height_ratio),
            'left': int(width * margin_ratio),
            'right': int(width * margin_ratio)
        }

        return result

    def extract_main_content(self, image_path: str, remove_header_footer: bool = True) -> str:
        """
        提取图片中的正文内容（去除页眉页脚）

        Args:
            image_path: 图片文件路径
            remove_header_footer: 是否去除页眉页脚

        Returns:
            str: 提取的正文区域描述信息
        """
        layout_info = self.analyze_layout(image_path)

        if not remove_header_footer:
            return f"全图区域: 0,0 到 {layout_info['size']['width']},{layout_info['size']['height']}"

        region = layout_info['main_content_region']
        return (f"正文区域: x从{region['x_start']}到{region['x_end']}, "
                f"y从{region['y_start']}到{region['y_end']}")

    def get_page_info(self, pdf_path: str) -> Dict[str, Any]:
        """
        获取PDF文档基本信息

        Args:
            pdf_path: PDF文件路径

        Returns:
            dict: PDF文档信息
        """
        doc = fitz.open(pdf_path)

        info = {
            'page_count': len(doc),
            'metadata': doc.metadata,
            'pages': []
        }

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_info = {
                'page_number': page_num + 1,
                'width': page.rect.width,
                'height': page.rect.height,
                'text_length': len(page.get_text())
            }
            info['pages'].append(page_info)

        doc.close()
        return info

    def extract_text_by_region(self, pdf_path: str, page_num: int,
                                region: Optional[Dict[str, int]] = None) -> str:
        """
        从PDF指定区域提取文本

        Args:
            pdf_path: PDF文件路径
            page_num: 页码（从1开始）
            region: 区域坐标 {'x0', 'y0', 'x1', 'y1'}

        Returns:
            str: 提取的文本
        """
        doc = fitz.open(pdf_path)
        page = doc[page_num - 1]

        if region:
            clip = fitz.Rect(region['x0'], region['y0'], region['x1'], region['y1'])
            text = page.get_text('text', clip=clip)
        else:
            text = page.get_text('text')

        doc.close()
        return text

    def batch_convert_to_images(self, pdf_paths: List[str],
                                 output_base_dir: Optional[str] = None) -> Dict[str, List[str]]:
        """
        批量将多个PDF转换为图片

        Args:
            pdf_paths: PDF文件路径列表
            output_base_dir: 输出基础目录

        Returns:
            dict: 每个PDF对应的图片路径列表
        """
        results = {}

        for pdf_path in pdf_paths:
            pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
            output_dir = os.path.join(output_base_dir or self.output_dir, pdf_name)

            try:
                image_paths = self.pdf_to_images(pdf_path, output_dir)
                results[pdf_path] = image_paths
            except Exception as e:
                results[pdf_path] = {'error': str(e)}

        return results


def create_pdf_processor(output_dir: str = './output') -> PDFProcessor:
    """
    工厂函数 - 创建PDF处理器实例

    Args:
        output_dir: 输出目录

    Returns:
        PDFProcessor: PDF处理器实例
    """
    return PDFProcessor(output_dir)
