#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF OCR 工作流程
使用 ndlocr-lite 对PDF文件进行OCR识别并输出为Markdown
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import sys
import json
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import subprocess

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入必要的模块
from modules.pdf_processor import PDFProcessor
from modules.ndlocr_result_processor import NDLOCRResultProcessor


class OCRWorkflow:
    """PDF OCR 完整工作流程"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.ndlocr_path = self.project_root / "ndlocr-lite" / "src" / "ocr.py"
        self.temp_dir = self.project_root / "temp_ocr_images"
        self.output_dir = self.project_root / "ocr_output"

        # 创建必要的目录
        self.temp_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)

    def check_ndlocr_available(self) -> bool:
        """检查 ndlocr-lite 是否可用"""
        if not self.ndlocr_path.exists():
            print(f"错误: ndlocr-lite 未找到: {self.ndlocr_path}")
            return False
        print(f"[OK] ndlocr-lite path: {self.ndlocr_path}")
        return True

    def pdf_to_images(self, pdf_path: str) -> List[str]:
        """将PDF转换为图片"""
        print(f"\n==> Converting PDF to images: {pdf_path}")

        pdf_processor = PDFProcessor(str(self.temp_dir))
        image_paths = pdf_processor.pdf_to_images(
            pdf_path,
            dpi=300,
            format='PNG'
        )

        print(f"[OK] Generated {len(image_paths)} images")
        return image_paths

    def process_images_with_ndlocr(self, image_paths: List[str]) -> List[Dict[str, Any]]:
        """使用 ndlocr-lite 处理图片"""
        print(f"\n==> Running ndlocr-lite OCR...")

        results = []

        # 检查是否可以使用Python直接调用
        try:
            # 尝试导入nldocr
            sys.path.insert(0, str(self.ndlocr_path.parent))
            # 由于OCR处理需要时间，我们先使用命令行方式
        except Exception as e:
            print(f"导入错误: {e}")

        # 使用命令行方式调用 ndlocr-lite
        for i, img_path in enumerate(image_paths):
            print(f"  处理第 {i+1}/{len(image_paths)} 张图片...")

            # 创建此图片的输出目录
            img_output_dir = self.temp_dir / f"ocr_result_{i+1:04d}"
            img_output_dir.mkdir(exist_ok=True)

            # 调用 ndlocr-lite
            cmd = [
                sys.executable,
                str(self.ndlocr_path),
                "--sourceimg", img_path,
                "--output", str(img_output_dir)
            ]

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5分钟超时
                )

                if result.returncode == 0:
                    # 读取生成的XML结果
                    xml_files = list(img_output_dir.glob("*.xml"))
                    if xml_files:
                        with open(xml_files[0], 'r', encoding='utf-8') as f:
                            xml_content = f.read()

                        # 解析XML提取文本
                        text = self._extract_text_from_xml(xml_content)
                        results.append({
                            'page': i + 1,
                            'image_path': img_path,
                            'text': text,
                            'xml_content': xml_content,
                            'success': True
                        })
                    else:
                        results.append({
                            'page': i + 1,
                            'image_path': img_path,
                            'text': '',
                            'success': False,
                            'error': '未生成XML文件'
                        })
                else:
                    results.append({
                        'page': i + 1,
                        'image_path': img_path,
                        'text': '',
                        'success': False,
                        'error': result.stderr
                    })

            except subprocess.TimeoutExpired:
                results.append({
                    'page': i + 1,
                    'image_path': img_path,
                    'text': '',
                    'success': False,
                    'error': '处理超时'
                })
            except Exception as e:
                results.append({
                    'page': i + 1,
                    'image_path': img_path,
                    'text': '',
                    'success': False,
                    'error': str(e)
                })

        success_count = sum(1 for r in results if r['success'])
        print(f"[OK] OCR completed: {success_count}/{len(results)} pages successful")

        return results

    def _extract_text_from_xml(self, xml_content: str) -> str:
        """从NDL OCR的XML结果中提取文本"""
        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(xml_content)
            texts = []

            # 遍历所有文本元素
            for elem in root.iter():
                if elem.text and elem.text.strip():
                    texts.append(elem.text.strip())

            return '\n'.join(texts)
        except Exception as e:
            print(f"XML解析错误: {e}")
            # 尝试简单提取
            text = re.sub(r'<[^>]+>', '', xml_content)
            return text.strip()

    def clean_text(self, text: str) -> str:
        """清洗OCR识别后的文本"""
        print("\n==> Cleaning text...")

        # 初始化结果处理器
        processor = NDLOCRResultProcessor()
        cleaned = processor.clean_text(text)

        # 额外的清洗步骤
        # 1. 去除多余空白
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        cleaned = re.sub(r' {2,}', ' ', cleaned)

        # 2. 去除常见OCR噪声
        cleaned = re.sub(r'[▪▫•●○◆◇□■△▲▼★☆♠♣♥♦]', '', cleaned)

        # 3. 修复常见的OCR错误
        cleaned = cleaned.replace('｜', '|')
        cleaned = cleaned.replace('━', '-')
        cleaned = cleaned.replace('——', '--')

        # 4. 规范化引号
        cleaned = cleaned.replace('"', '"').replace('"', '"')
        cleaned = cleaned.replace(''', "'").replace(''', "'")

        # 5. 去除页码标记
        cleaned = re.sub(r'\n\s*[-−–—]\s*\d+\s*[-−–—]\s*\n', '\n', cleaned)

        print("[OK] Text cleaning completed")
        return cleaned

    def generate_markdown(self, ocr_results: List[Dict[str, Any]], cleaned_full_text: str) -> str:
        """生成Markdown格式的输出"""
        print("\n==> Generating Markdown...")

        md_content = []
        md_content.append("# 伊藤博文伝 中-1 OCR识别结果\n")
        md_content.append("---")
        md_content.append(f"\n**原始文件**: 伊藤博文伝 中-1.pdf\n")
        md_content.append(f"**处理日期**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        md_content.append(f"**OCR引擎**: NDL OCR-Lite\n")
        md_content.append(f"**处理页数**: {len(ocr_results)}\n")
        md_content.append("\n---\n")

        # 添加清洗后的完整文本
        md_content.append("\n## 完整识别文本\n")
        md_content.append(cleaned_full_text)

        # 添加每页的详细信息作为附录
        md_content.append("\n\n---\n\n## 逐页识别结果\n")

        for result in ocr_results:
            page_num = result.get('page', '?')
            md_content.append(f"\n### 第 {page_num} 页\n")

            if result.get('success'):
                text = result.get('text', '')
                if text:
                    md_content.append(text[:1000])  # 每页限制显示1000字符
                    if len(text) > 1000:
                        md_content.append("\n*(内容过长，已截断)*\n")
                else:
                    md_content.append("*未识别到文本*\n")
            else:
                md_content.append(f"*识别失败: {result.get('error', '未知错误')}*\n")

        md_content.append("\n---\n")
        md_content.append("*本文档由AItools-for-historyresearch自动生成*\n")

        print("[OK] Markdown generated")
        return '\n'.join(md_content)

    def run(self, pdf_path: str, output_markdown_path: str) -> bool:
        """执行完整的OCR工作流程"""
        print("=" * 60)
        print("PDF OCR 工作流程")
        print("=" * 60)

        # 步骤1: 检查环境
        if not self.check_ndlocr_available():
            return False

        # 步骤2: PDF转图片
        image_paths = self.pdf_to_images(pdf_path)

        # 步骤3: OCR识别
        ocr_results = self.process_images_with_ndlocr(image_paths)

        # 步骤4: 合并所有文本
        full_text = '\n\n'.join([
            r.get('text', '') for r in ocr_results if r.get('success')
        ])

        # 步骤5: 文本清洗
        cleaned_text = self.clean_text(full_text)

        # 步骤6: 生成Markdown
        markdown_content = self.generate_markdown(ocr_results, cleaned_text)

        # 步骤7: 保存结果
        output_path = Path(output_markdown_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        print(f"\n[OK] Done! Output saved to: {output_path}")

        # 清理临时文件
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        print("[OK] Temporary files cleaned")

        return True


def main():
    """主函数"""
    # 配置路径
    pdf_path = r"c:\Users\lyzha\Desktop\AItools-for-historyresearch\伊藤博文伝 中-1.pdf"
    output_path = r"c:\Users\lyzha\Desktop\AItools-for-historyresearch\COMPREHENSIVE_TECHNICAL_GUIDE.md"

    # 获取项目根目录
    project_root = Path(__file__).parent

    # 创建工作流并执行
    workflow = OCRWorkflow(str(project_root))

    success = workflow.run(pdf_path, output_path)

    if success:
        print("\n*** OCR processing completed successfully!")
    else:
        print("\n[ERROR] OCR processing failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
