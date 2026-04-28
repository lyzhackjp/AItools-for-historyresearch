"""
NDL古典籍OCR-Lite 集成模块

日本国立国会图书馆实验室(NDL Lab)开发的古典籍OCR工具本地调用封装
支持对江戸期以前的和古書、清代以前的漢籍等古典籍资料的高精度文字识别

官方文档: https://github.com/ndl-lab/ndlkotenocr-lite

特点:
- CPU环境下高速运行，无需GPU
- 专门针对古典草书字、日文汉字、平假名、片假名等
- 支持レイアウト認識、字符串認識、讀み順整序
"""

import os
import subprocess
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
import tempfile
import json
from datetime import datetime


@dataclass
class NDLKotenOCRLiteConfig:
    """NDL古典籍OCR-Lite配置类"""
    ndlkoten_path: Optional[str] = None
    use_gpu: bool = False
    enable_visualization: bool = False
    timeout: int = 300
    supported_formats: tuple = ('jpg', 'jpeg', 'png', 'tiff', 'tif', 'jp2', 'bmp')


class NDLKotenOCRLiteResult:
    """NDL古典籍OCR-Lite处理结果类"""

    def __init__(self):
        self.success: bool = False
        self.text: str = ""
        self.xml_content: str = ""
        self.pages: List[Dict[str, Any]] = []
        self.structures: List[Dict[str, Any]] = []
        self.error: Optional[str] = None
        self.processing_time: float = 0.0
        self.output_dir: Optional[str] = None
        self.visualization_paths: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'success': self.success,
            'text': self.text,
            'xml_content': self.xml_content,
            'pages': self.pages,
            'structures': self.structures,
            'error': self.error,
            'processing_time': self.processing_time,
            'output_dir': self.output_dir,
            'visualization_paths': self.visualization_paths
        }

    def merge_all_text(self) -> str:
        """合并所有页面的文本"""
        return '\n\n'.join([page['text'] for page in self.pages if page.get('text')])

    def to_package(self, source_path: Optional[str] = None) -> Dict[str, Any]:
        """Return a workflow-ready OCR package."""
        text = self.merge_all_text() or self.text
        quality_flags: List[str] = []
        if not self.success:
            quality_flags.append("ocr_failed")
        if not text.strip():
            quality_flags.append("no_text")
        if not self.pages:
            quality_flags.append("no_pages")
        if self.error:
            quality_flags.append("has_error")
        confidence = 0.72 if self.success and text.strip() else 0.2
        if quality_flags:
            confidence = min(confidence, 0.62)
        return {
            "type": "ocr_result",
            "source_path": source_path,
            "success": self.success,
            "text": text,
            "xml_content": self.xml_content,
            "pages": self.pages,
            "structures": self.structures,
            "artifacts": [
                {"type": "visualization", "path": path}
                for path in self.visualization_paths
            ],
            "output_dir": self.output_dir,
            "backend": "local_engine",
            "provider": "ndlkotenocr_lite",
            "model": "ndlkotenocr-lite",
            "processing_time": self.processing_time,
            "confidence": round(confidence, 2),
            "needs_review": bool(quality_flags),
            "quality_flags": quality_flags,
            "error": self.error,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }


class NDLKotenOCRLiteProcessor:
    """
    NDL古典籍OCR-Lite 处理器

    用于调用本地安装的ndlkotenocr-lite工具进行OCR识别
    专门处理古典籍资料(江戸期以前的和古書、清代以前的漢籍)
    支持单张图片和批量处理
    """

    def __init__(self, config: Optional[NDLKotenOCRLiteConfig] = None):
        """
        初始化NDL古典籍OCR-Lite处理器

        Args:
            config: NDL古典籍OCR-Lite配置对象
        """
        self.config = config or NDLKotenOCRLiteConfig()
        self._ndlkoten_executable = None
        self._model_dir = None
        self._config_dir = None
        self._check_installation()

    def _check_installation(self):
        """检查ndlkotenocr-lite是否已安装"""
        possible_paths = []

        if self.config.ndlkoten_path:
            possible_paths.append(self.config.ndlkoten_path)

        possible_paths.extend([
            os.path.join(os.getcwd(), 'external', 'ndlkotenocr-lite', 'src', 'ocr.py'),
            os.path.join(os.path.expanduser('~'), 'ndlkotenocr-lite', 'src', 'ocr.py'),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'external', 'ndlkotenocr-lite', 'src', 'ocr.py'),
            'ndlkotenocr-lite',
            'ocr.py'
        ])

        for path in possible_paths:
            if os.path.exists(path):
                self._ndlkoten_executable = path
                src_dir = os.path.dirname(path)
                self._model_dir = os.path.join(os.path.dirname(src_dir), 'model')
                self._config_dir = os.path.join(src_dir, 'config')
                return

        try:
            result = subprocess.run(
                ['ndlkotenocr-lite', '--help'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self._ndlkoten_executable = 'ndlkotenocr-lite'
                return
        except:
            pass

        self._ndlkoten_executable = None

    def is_installed(self) -> bool:
        """检查是否已安装ndlkotenocr-lite"""
        return self._ndlkoten_executable is not None

    def get_capabilities(self) -> Dict[str, Any]:
        """Return local NDL Koten OCR capability metadata."""
        return {
            "module": "ndlkotenocr_lite",
            "backend": "local_engine",
            "provider": "ndlkotenocr_lite",
            "model": "ndlkotenocr-lite",
            "available": self.is_installed(),
            "capabilities": [
                "image_ocr",
                "directory_ocr",
                "xml_output",
                "visualization_output",
                "classical_japanese_ocr",
            ],
            "supported_formats": list(self.config.supported_formats),
            "fallback_order": ["local_engine:ndlkotenocr_lite", "local_engine:ndlocr_lite", "llm_ocr"],
        }

    def get_installation_guide(self) -> str:
        """获取安装指南"""
        return """
NDL古典籍OCR-Lite 安装指南
========================

1. 克隆仓库:
   git clone https://github.com/ndl-lab/ndlkotenocr-lite

2. 进入目录并安装依赖:
   cd ndlkotenocr-lite
   pip install -r requirements.txt

3. 进入src目录:
   cd src

4. 测试安装:
   python3 ocr.py --help

5. 或使用uv安装(可选):
   uv tool install .

系统要求:
- Python 3.10+
- Windows 10+ / macOS Sequoia / Linux Ubuntu 22.04+
- 推荐8GB+内存
- CPU环境下可高速运行(无需GPU)

特点:
- 专门针对古典籍资料优化
- 支持江戸期以前的和古書、清代以前的漢籍
- CPU环境下高速运行
- 比NDL古典籍OCR ver.3精度稍低约2%
"""

    def _validate_image(self, image_path: str) -> bool:
        """验证图片文件是否有效"""
        if not os.path.exists(image_path):
            return False

        ext = os.path.splitext(image_path)[1].lower().lstrip('.')
        return ext in self.config.supported_formats

    def _build_command(self, source: str, output_dir: str) -> List[str]:
        """
        构建ndlkotenocr-lite命令

        Args:
            source: 图片路径或目录路径
            output_dir: 输出目录

        Returns:
            list: 命令列表
        """
        import sys

        python_cmd = sys.executable

        is_dir = os.path.isdir(source)

        if is_dir:
            cmd = [python_cmd, self._ndlkoten_executable, '--sourcedir', source]
        else:
            cmd = [python_cmd, self._ndlkoten_executable, '--sourceimg', source]

        cmd.extend(['--output', output_dir])

        if self.config.enable_visualization:
            cmd.append('--viz')
            cmd.append('True')

        if self._model_dir and os.path.exists(self._model_dir):
            det_weights = os.path.join(self._model_dir, 'rtmdet-s-1280x1280.onnx')
            rec_weights = os.path.join(self._model_dir, 'parseq-ndl-32x384-tiny-10.onnx')

            if os.path.exists(det_weights):
                cmd.extend(['--det-weights', det_weights])
            if os.path.exists(rec_weights):
                cmd.extend(['--rec-weights', rec_weights])

        if self._config_dir and os.path.exists(self._config_dir):
            det_classes = os.path.join(self._config_dir, 'ndl.yaml')
            rec_classes = os.path.join(self._config_dir, 'NDLmoji.yaml')

            if os.path.exists(det_classes):
                cmd.extend(['--det-classes', det_classes])
            if os.path.exists(rec_classes):
                cmd.extend(['--rec-classes', rec_classes])

        if self.config.use_gpu:
            cmd.extend(['--device', 'cuda'])

        return cmd

    def process_image(self, image_path: str, output_dir: Optional[str] = None) -> NDLKotenOCRLiteResult:
        """
        处理单张图片

        Args:
            image_path: 图片文件路径
            output_dir: 输出目录路径(可选)

        Returns:
            NDLKotenOCRLiteResult: 处理结果
        """
        import time
        start_time = time.time()

        result = NDLKotenOCRLiteResult()

        if not self.is_installed():
            result.error = f"ndlkotenocr-lite未安装或无法找到\n{self.get_installation_guide()}"
            return result

        if not self._validate_image(image_path):
            result.error = f"不支持的图片格式或文件不存在: {image_path}\n支持的格式: {', '.join(self.config.supported_formats)}"
            return result

        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix='ndlkoten_')

        os.makedirs(output_dir, exist_ok=True)
        result.output_dir = output_dir

        try:
            cmd = self._build_command(image_path, output_dir)

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
                cwd=os.path.dirname(self._ndlkoten_executable) if self._ndlkoten_executable else None
            )

            if process.returncode != 0:
                result.error = f"古典籍OCR处理失败: {process.stderr}"
                return result

            result = self._parse_output(output_dir, result)

            result.success = True
            result.processing_time = time.time() - start_time

        except subprocess.TimeoutExpired:
            result.error = f"处理超时(>{self.config.timeout}秒)"
        except Exception as e:
            result.error = f"处理异常: {str(e)}"

        return result

    def process_image_package(self, image_path: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """Process one image and return a workflow package."""
        result = self.process_image(image_path, output_dir=output_dir)
        package = result.to_package(source_path=image_path)
        package["capabilities"] = self.get_capabilities()
        return package

    def process_directory(self, directory_path: str, output_dir: Optional[str] = None) -> NDLKotenOCRLiteResult:
        """
        批量处理目录中的所有图片

        Args:
            directory_path: 包含图片的目录路径
            output_dir: 输出目录路径(可选)

        Returns:
            NDLKotenOCRLiteResult: 处理结果
        """
        import time
        start_time = time.time()

        result = NDLKotenOCRLiteResult()

        if not self.is_installed():
            result.error = f"ndlkotenocr-lite未安装或无法找到\n{self.get_installation_guide()}"
            return result

        if not os.path.isdir(directory_path):
            result.error = f"目录不存在: {directory_path}"
            return result

        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix='ndlkoten_batch_')

        os.makedirs(output_dir, exist_ok=True)
        result.output_dir = output_dir

        try:
            cmd = self._build_command(directory_path, output_dir)

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout * 10,
                cwd=os.path.dirname(self._ndlkoten_executable) if self._ndlkoten_executable else None
            )

            if process.returncode != 0:
                result.error = f"批量处理失败: {process.stderr}"
                return result

            result = self._parse_output(output_dir, result)

            result.success = True
            result.processing_time = time.time() - start_time

        except subprocess.TimeoutExpired:
            result.error = f"处理超时(>{self.config.timeout * 10}秒)"
        except Exception as e:
            result.error = f"处理异常: {str(e)}"

        return result

    def process_directory_package(self, directory_path: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """Process a directory and return a workflow package."""
        result = self.process_directory(directory_path, output_dir=output_dir)
        package = result.to_package(source_path=directory_path)
        package["type"] = "ocr_batch"
        package["capabilities"] = self.get_capabilities()
        package["page_count"] = len(result.pages)
        return package

    def _parse_output(self, output_dir: str, result: NDLKotenOCRLiteResult) -> NDLKotenOCRLiteResult:
        """
        解析ndlkotenocr-lite的输出结果

        Args:
            output_dir: 输出目录
            result: 结果对象

        Returns:
            NDLKotenOCRLiteResult: 解析后的结果
        """
        all_text_parts = []
        all_xml_parts = []

        for filename in os.listdir(output_dir):
            file_path = os.path.join(output_dir, filename)

            if filename.endswith('.txt') and '_tei' not in filename:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text_content = f.read()
                        all_text_parts.append(text_content)

                        page_info = {
                            'filename': filename,
                            'text': text_content,
                            'path': file_path
                        }
                        result.pages.append(page_info)
                except Exception as e:
                    print(f"读取文本文件失败 {filename}: {e}")

            elif filename.endswith('.xml') and '_tei' not in filename:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        xml_content = f.read()
                        all_xml_parts.append(xml_content)

                        structure_info = self._parse_xml_structure(xml_content)
                        structure_info['filename'] = filename
                        structure_info['path'] = file_path
                        result.structures.append(structure_info)
                except Exception as e:
                    print(f"解析XML文件失败 {filename}: {e}")

            elif filename.endswith(('.png', '.jpg', '.jpeg')) and 'viz_' in filename:
                result.visualization_paths.append(file_path)

        result.text = '\n\n'.join(all_text_parts)
        result.xml_content = '\n'.join(all_xml_parts)

        return result

    def _parse_xml_structure(self, xml_content: str) -> Dict[str, Any]:
        """
        解析XML格式的结构化输出

        Args:
            xml_content: XML内容

        Returns:
            dict: 结构化数据
        """
        structure = {
            'blocks': [],
            'lines': [],
            'words': []
        }

        try:
            root = ET.fromstring(xml_content)

            for page in root.findall('.//PAGE'):
                for block in page.findall('.//BLOCK'):
                    block_info = {
                        'id': block.get('id'),
                        'type': block.get('type'),
                        'bbox': self._parse_bbox(block.get('bbox', '')),
                        'lines': []
                    }

                    for line in block.findall('.//LINE'):
                        line_info = {
                            'text': line.text if line.text else '',
                            'bbox': self._parse_bbox(line.get('bbox', '')),
                            'isVertical': line.get('isVertical', 'true'),
                            'confidence': float(line.get('CONF', 0))
                        }

                        block_info['lines'].append(line_info)
                        structure['lines'].append(line_info)

                        if line.text:
                            structure['words'].append({
                                'text': line.text,
                                'bbox': line_info['bbox']
                            })

                    structure['blocks'].append(block_info)

        except Exception as e:
            print(f"解析XML结构失败: {e}")

        return structure

    def _parse_bbox(self, bbox_str: str) -> List[float]:
        """
        解析边界框字符串

        Args:
            bbox_str: 边界框字符串 "xmin,ymin,xmax,ymax"

        Returns:
            list: [xmin, ymin, xmax, ymax]
        """
        if not bbox_str:
            return [0, 0, 0, 0]

        try:
            parts = bbox_str.split(',')
            return [float(p.strip()) for p in parts]
        except:
            return [0, 0, 0, 0]

    def _get_xml_namespaces(self) -> Dict[str, str]:
        """获取XML命名空间"""
        return {
            'w': 'http://schema.omni水平线/wiki/Download?file=wiki%2Fwiki%2Fshared%2FBiblioNLD.xlsx#',
            'ocrd': 'http://schema.omni水平线/wiki/Download?file=wiki%2Fwiki%2Fshared%2FBiblioNLD.xlsx#'
        }
