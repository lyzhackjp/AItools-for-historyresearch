"""
人物传记OCR处理管道 - 使用Qwen VL OCR
针对竖排日文文献进行优化
"""
import os
import sys
import json
import time
import base64
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass

# 导入基础模块
from .pdf_image_converter import convert_pdf_to_images
from .biographical_ner import BiographicalNER, PersonEntity


@dataclass
class OCRConfig:
    """OCR配置"""
    api_key: str = ""
    model: str = "qwen-vl-ocr"  # 或 "qwen-vl-plus"
    use_proxy: bool = False
    proxy_url: Optional[str] = None


class QwenVLOCRProcessor:
    """Qwen VL OCR 处理器"""

    API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

    def __init__(self, config: OCRConfig):
        self.config = config

    def image_to_base64(self, image_path: str) -> str:
        """将图片转为base64"""
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')

    def process_image(self, image_path: str) -> Dict[str, Any]:
        """
        处理单张图片

        Args:
            image_path: 图片路径

        Returns:
            OCR结果字典
        """
        try:
            # 读取图片
            with open(image_path, 'rb') as f:
                image_base64 = base64.b64encode(f.read()).decode('utf-8')

            # 构建请求
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.config.model,
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "image": f"data:image/jpeg;base64,{image_base64}"
                                },
                                {
                                    "text": "这是日本历史文献的页面图片。请仔细识别图片中的所有文字，注意这是竖排日文（从右到左阅读）。请按原样输出所有识别出的文字，不要省略任何内容。"
                                }
                            ]
                        }
                    ]
                },
                "parameters": {
                    "temperature": 0.1,
                    "max_tokens": 4000
                }
            }

            # 发送请求
            resp = requests.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=120
            )

            if resp.status_code == 200:
                result = resp.json()
                # 解析结果
                if 'output' in result and 'choices' in result['output']:
                    text = result['output']['choices'][0]['message']['content']
                    return {
                        'success': True,
                        'text': text,
                        'image_path': image_path
                    }

            return {
                'success': False,
                'error': f"API错误: {resp.status_code} - {resp.text[:200]}",
                'image_path': image_path
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'image_path': image_path
            }

    def process_images(
        self,
        image_paths: List[str],
        progress_callback: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """
        批量处理图片

        Args:
            image_paths: 图片路径列表
            progress_callback: 进度回调

        Returns:
            OCR结果列表
        """
        results = []

        for i, img_path in enumerate(image_paths):
            result = self.process_image(img_path)
            results.append(result)

            if progress_callback:
                progress_callback(i + 1, len(image_paths), f"OCR: {os.path.basename(img_path)}")

            # 避免API限流
            if i < len(image_paths) - 1:
                time.sleep(0.5)

        return results


class BiographyOCRPipeline:
    """人物传记OCR管道"""

    def __init__(
        self,
        pdf_path: str,
        output_dir: str,
        api_key: str,
        dpi: int = 200,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None
    ):
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.dpi = dpi
        self.start_page = start_page
        self.end_page = end_page

        self.ocr_config = OCRConfig(api_key=api_key)
        self.ocr_processor = QwenVLOCRProcessor(self.ocr_config)
        self.ner = BiographicalNER()
        self.persons: List[PersonEntity] = []

    def run(
        self,
        max_pages: Optional[int] = None,
        progress_callback: Optional[Callable] = None
    ) -> bool:
        """
        运行管道

        Args:
            max_pages: 最大处理页数（用于测试）
            progress_callback: 进度回调

        Returns:
            是否成功
        """
        try:
            # Step 1: PDF转图片
            if progress_callback:
                progress_callback(0, 100, "PDF转图片...")

            images_dir = os.path.join(self.output_dir, 'images')
            image_paths = convert_pdf_to_images(
                self.pdf_path,
                images_dir,
                dpi=self.dpi,
                start_page=self.start_page,
                end_page=self.end_page
            )

            if not image_paths:
                print("PDF转图片失败")
                return False

            # 限制处理页数
            if max_pages:
                image_paths = image_paths[:max_pages]

            if progress_callback:
                progress_callback(10, 100, f"图片转换完成: {len(image_paths)}张")

            # Step 2: OCR识别
            if progress_callback:
                progress_callback(20, 100, "开始OCR识别...")

            ocr_results = self.ocr_processor.process_images(
                image_paths,
                progress_callback=lambda c, t, p: progress_callback(20 + int(c/t*60), 100, p)
            )

            # Step 3: NER提取
            if progress_callback:
                progress_callback(80, 100, "提取人物实体...")

            all_persons = []
            for page_num, ocr_result in enumerate(ocr_results, 1):
                if not ocr_result.get('success'):
                    continue

                text = ocr_result.get('text', '')
                if not text:
                    continue

                # 提取人物
                person = self.ner.extract_person_from_block(text, page_num, 0)
                if person and (person.name or person.work_experiences):
                    all_persons.append(person)

            self.persons = all_persons

            # Step 4: 排序
            self.ner.sort_work_experiences_by_date()

            # Step 5: 导出CSV
            if progress_callback:
                progress_callback(95, 100, "导出CSV...")

            self.export_to_csv(os.path.join(self.output_dir, 'biography_data.csv'))

            if progress_callback:
                progress_callback(100, 100, f"完成! 共{len(self.persons)}人")

            return True

        except Exception as e:
            print(f"管道执行失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def export_to_csv(self, csv_path: str) -> None:
        """导出为CSV"""
        import csv

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # 表头
            writer.writerow([
                '姓名', '本籍', '学历',
                '工作经历1_单位', '工作经历1_时间', '工作经历1_描述',
                '工作经历2_单位', '工作经历2_时间', '工作经历2_描述',
                '工作经历3_单位', '工作经历3_时间', '工作经历3_描述',
                '页码', '块索引', '原始文本'
            ])

            # 数据
            for person in self.persons:
                experiences = person.work_experiences[:3]

                row = [
                    person.name or '',
                    person.hometown or '',
                    person.education or '',
                ]

                for i in range(3):
                    if i < len(experiences):
                        exp = experiences[i]
                        row.extend([
                            exp.get('unit', ''),
                            exp.get('date_range', ''),
                            exp.get('description', ''),
                        ])
                    else:
                        row.extend(['', '', ''])

                row.extend([
                    person.page_number or '',
                    person.block_index or '',
                    (person.original_text[:100] or '') if person.original_text else '',
                ])

                writer.writerow(row)

        print(f"CSV已导出: {csv_path}")


def run_biography_ocr(
    pdf_path: str,
    output_dir: str,
    api_key: str,
    dpi: int = 200,
    start_page: Optional[int] = None,
    end_page: Optional[int] = None,
    max_pages: Optional[int] = None,
    progress_callback: Optional[Callable] = None
) -> bool:
    """
    运行人物传记OCR的便捷函数
    """
    pipeline = BiographyOCRPipeline(
        pdf_path=pdf_path,
        output_dir=output_dir,
        api_key=api_key,
        dpi=dpi,
        start_page=start_page,
        end_page=end_page
    )

    return pipeline.run(max_pages=max_pages, progress_callback=progress_callback)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="人物传记OCR管道")
    parser.add_argument('pdf_path', help="PDF文件路径")
    parser.add_argument('output_dir', help="输出目录")
    parser.add_argument('--api-key', required=True, help="API密钥")
    parser.add_argument('--dpi', type=int, default=200, help="图片DPI")
    parser.add_argument('--start-page', type=int, help="起始页")
    parser.add_argument('--end-page', type=int, help="结束页")
    parser.add_argument('--max-pages', type=int, help="最大处理页数(测试用)")

    args = parser.parse_args()

    def progress(current, total, desc):
        print(f"[{current}/{total}] {desc}")

    run_biography_ocr(
        args.pdf_path,
        args.output_dir,
        args.api_key,
        dpi=args.dpi,
        start_page=args.start_page,
        end_page=args.end_page,
        max_pages=args.max_pages,
        progress_callback=progress
    )
