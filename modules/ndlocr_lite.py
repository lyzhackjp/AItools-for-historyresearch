"""
NDL OCR-Lite 集成模块

日本国立国会图书馆实验室(NDL Lab)开发的OCR工具本地调用封装
支持对日文文献、历史文档的高精度文字识别

官方文档: https://github.com/ndl-lab/ndlocr-lite
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


@dataclass
class NDLOCRLiteConfig:
    """NDL OCR-Lite配置类"""
    ndlocr_path: Optional[str] = None
    use_gpu: bool = False
    enable_visualization: bool = False
    timeout: int = 300
    supported_formats: tuple = ('jpg', 'jpeg', 'png', 'tiff', 'tif', 'jp2', 'bmp')


class NDLOCRLiteResult:
    """NDL OCR-Lite处理结果类"""

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


class NDLOCRLiteProcessor:
    """
    NDL OCR-Lite 处理器

    用于调用本地安装的ndlocr-lite工具进行OCR识别
    支持单张图片和批量处理
    """

    def __init__(self, config: Optional[NDLOCRLiteConfig] = None):
        """
        初始化NDL OCR-Lite处理器

        Args:
            config: NDL OCR-Lite配置对象
        """
        self.config = config or NDLOCRLiteConfig()
        self._ndlocr_executable = None
        self._check_installation()

    def _check_installation(self):
        """检查ndlocr-lite是否已安装"""
        possible_paths = []

        if self.config.ndlocr_path:
            possible_paths.append(self.config.ndlocr_path)

        possible_paths.extend([
            os.path.join(os.getcwd(), 'ndlocr-lite', 'src', 'ocr.py'),
            os.path.join(os.path.expanduser('~'), 'ndlocr-lite', 'src', 'ocr.py'),
            os.path.join(os.path.expanduser('~'), 'Desktop', 'AItools-for-historyresearch', 'ndlocr-lite', 'src', 'ocr.py'),
            os.path.join(os.path.expanduser('~'), 'Documents', 'GitHub', 'AItools-for-Japanesehistory', 'ndlocr-lite', 'src', 'ocr.py'),
            os.path.join(os.getcwd(), '..', 'ndlocr-lite', 'src', 'ocr.py'),
            'ndlocr-lite',
            'ocr.py'
        ])

        for path in possible_paths:
            if os.path.exists(path):
                self._ndlocr_executable = path
                return

        try:
            result = subprocess.run(
                ['ndlocr-lite', '--help'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self._ndlocr_executable = 'ndlocr-lite'
                return
        except:
            pass

        self._ndlocr_executable = None

    def is_installed(self) -> bool:
        """检查是否已安装ndlocr-lite"""
        return self._ndlocr_executable is not None

    def get_installation_guide(self) -> str:
        """获取安装指南"""
        return """
NDL OCR-Lite 安装指南
========================

1. 克隆仓库:
   git clone https://github.com/ndl-lab/ndlocr-lite

2. 进入目录并安装依赖:
   cd ndlocr-lite
   pip install -r requirements.txt

3. 进入src目录:
   cd src

4. 测试安装:
   python3 ocr.py --help

5. 或使用uv安装(可选):
   uv tool install .

系统要求:
- Python 3.10+
- Windows 11 / macOS / Linux
- 推荐8GB+内存
"""

    def _validate_image(self, image_path: str) -> bool:
        """验证图片文件是否有效"""
        if not os.path.exists(image_path):
            return False

        ext = os.path.splitext(image_path)[1].lower().lstrip('.')
        return ext in self.config.supported_formats

    def _build_command(self, source: str, output_dir: str) -> List[str]:
        """
        构建ndlocr-lite命令

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
            cmd = [python_cmd, self._ndlocr_executable, '--sourcedir', source]
        else:
            cmd = [python_cmd, self._ndlocr_executable, '--sourceimg', source]

        cmd.extend(['--output', output_dir])

        if self.config.enable_visualization:
            cmd.append('--viz')
            cmd.append('True')

        if self.config.use_gpu:
            cmd.extend(['--device', 'cuda'])

        return cmd

    def process_image(self, image_path: str, output_dir: Optional[str] = None) -> NDLOCRLiteResult:
        """
        处理单张图片

        Args:
            image_path: 图片文件路径
            output_dir: 输出目录路径(可选)

        Returns:
            NDLOCRLiteResult: 处理结果
        """
        import time
        start_time = time.time()

        result = NDLOCRLiteResult()

        if not self.is_installed():
            result.error = f"ndlocr-lite未安装或无法找到\n{self.get_installation_guide()}"
            return result

        if not self._validate_image(image_path):
            result.error = f"不支持的图片格式或文件不存在: {image_path}\n支持的格式: {', '.join(self.config.supported_formats)}"
            return result

        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix='ndlocr_')

        os.makedirs(output_dir, exist_ok=True)
        result.output_dir = output_dir

        try:
            cmd = self._build_command(image_path, output_dir)

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
                cwd=os.path.dirname(self._ndlocr_executable) if self._ndlocr_executable else None
            )

            if process.returncode != 0:
                result.error = f"OCR处理失败: {process.stderr}"
                return result

            result = self._parse_output(output_dir, result)

            result.success = True
            result.processing_time = time.time() - start_time

        except subprocess.TimeoutExpired:
            result.error = f"处理超时(>{self.config.timeout}秒)"
        except Exception as e:
            result.error = f"处理异常: {str(e)}"

        return result

    def process_directory(self, directory_path: str, output_dir: Optional[str] = None) -> NDLOCRLiteResult:
        """
        批量处理目录中的所有图片

        Args:
            directory_path: 包含图片的目录路径
            output_dir: 输出目录路径(可选)

        Returns:
            NDLOCRLiteResult: 处理结果
        """
        import time
        start_time = time.time()

        result = NDLOCRLiteResult()

        if not self.is_installed():
            result.error = f"ndlocr-lite未安装或无法找到\n{self.get_installation_guide()}"
            return result

        if not os.path.isdir(directory_path):
            result.error = f"目录不存在: {directory_path}"
            return result

        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix='ndlocr_batch_')

        os.makedirs(output_dir, exist_ok=True)
        result.output_dir = output_dir

        try:
            cmd = self._build_command(directory_path, output_dir)

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout * 10,
                cwd=os.path.dirname(self._ndlocr_executable) if self._ndlocr_executable else None
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

    def _parse_output(self, output_dir: str, result: NDLOCRLiteResult) -> NDLOCRLiteResult:
        """
        解析ndlocr-lite的输出结果

        Args:
            output_dir: 输出目录
            result: 结果对象

        Returns:
            NDLOCRLiteResult: 解析后的结果
        """
        all_text_parts = []
        all_xml_parts = []

        for filename in os.listdir(output_dir):
            file_path = os.path.join(output_dir, filename)

            if filename.endswith('.txt'):
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

            elif filename.endswith('.xml'):
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

            elif filename.endswith(('.png', '.jpg', '.jpeg')) and '_viz' in filename:
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

            for block in root.findall('.//w:block', self._get_xml_namespaces()):
                block_info = {
                    'id': block.get('id'),
                    'type': block.get('type'),
                    'bbox': self._parse_bbox(block.get('bbox', '')),
                    'lines': []
                }

                for line in block.findall('.//w:line', self._get_xml_namespaces()):
                    line_info = {
                        'text': line.text if line.text else '',
                        'bbox': self._parse_bbox(line.get('bbox', '')),
                        'words': []
                    }

                    for word in line.findall('.//w:word', self._get_xml_namespaces()):
                        word_info = {
                            'text': word.text if word.text else '',
                            'bbox': self._parse_bbox(word.get('bbox', ''))
                        }
                        line_info['words'].append(word_info)
                        structure['words'].append(word_info)

                    block_info['lines'].append(line_info)
                    structure['lines'].append(line_info)

                structure['blocks'].append(block_info)

        except Exception as e:
            structure['parse_error'] = str(e)

        return structure

    def _get_xml_namespaces(self) -> Dict[str, str]:
        """获取XML命名空间"""
        return {
            'w': 'http://ocr.ndl.go.jp schema/1.0'
        }

    def _parse_bbox(self, bbox_str: str) -> Dict[str, float]:
        """
        解析边界框坐标

        Args:
            bbox_str: 边界框字符串 (x1,y1,x2,y2)

        Returns:
            dict: 边界框坐标
        """
        if not bbox_str:
            return {}

        try:
            parts = [float(p) for p in bbox_str.split(',')]
            if len(parts) == 4:
                return {
                    'x1': parts[0],
                    'y1': parts[1],
                    'x2': parts[2],
                    'y2': parts[3],
                    'width': parts[2] - parts[0],
                    'height': parts[3] - parts[1]
                }
        except:
            pass

        return {}

    def get_status(self) -> Dict[str, Any]:
        """获取处理器状态信息"""
        return {
            'installed': self.is_installed(),
            'executable_path': self._ndlocr_executable,
            'gpu_enabled': self.config.use_gpu,
            'visualization_enabled': self.config.enable_visualization,
            'supported_formats': list(self.config.supported_formats)
        }


def create_ndlocr_processor(
    ndlocr_path: Optional[str] = None,
    use_gpu: bool = False,
    enable_viz: bool = False,
    timeout: int = 300
) -> NDLOCRLiteProcessor:
    """
    工厂函数 - 创建NDL OCR-Lite处理器实例

    Args:
        ndlocr_path: ndlocr-lite安装路径
        use_gpu: 是否启用GPU加速
        enable_viz: 是否启用可视化输出
        timeout: 处理超时时间(秒)

    Returns:
        NDLOCRLiteProcessor: NDL OCR-Lite处理器实例
    """
    config = NDLOCRLiteConfig(
        ndlocr_path=ndlocr_path,
        use_gpu=use_gpu,
        enable_visualization=enable_viz,
        timeout=timeout
    )
    return NDLOCRLiteProcessor(config)
