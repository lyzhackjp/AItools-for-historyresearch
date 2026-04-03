"""
统一OCR处理器 - 支持NDL OCRlite和NDL古典籍OCR-Lite模型切换

支持两种OCR模式:
1. NDL OCRlite - 用于近代现代日本印刷体文献
2. NDL古典籍OCR-Lite - 用于古典草书字文献(江戸期以前的和古書、清代以前的漢籍)

使用方式:
    processor = UnifiedOCRProcessor()
    
    # 使用NDL OCRlite(近代现代文献)
    result = processor.process_image(image_path, model_type='ndlocr_lite')
    
    # 使用NDL古典籍OCR-Lite(古典籍文献)
    result = processor.process_image(image_path, model_type='ndlkotenocr_lite')
"""

import os
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class OCRModelType(Enum):
    """OCR模型类型枚举"""
    NDLOCR_LITE = "ndlocr_lite"
    NDLKOTENOCR_LITE = "ndlkotenocr_lite"


@dataclass
class UnifiedOCRConfig:
    """统一OCR配置类"""
    ndlocr_path: Optional[str] = None
    ndlkoten_path: Optional[str] = None
    use_gpu: bool = False
    enable_visualization: bool = False
    timeout: int = 300
    default_model: str = "ndlocr_lite"


class UnifiedOCRResult:
    """统一OCR处理结果类"""

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
        self.model_type: str = ""
        self.model_description: str = ""

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
            'visualization_paths': self.visualization_paths,
            'model_type': self.model_type,
            'model_description': self.model_description
        }

    def merge_all_text(self) -> str:
        """合并所有页面的文本"""
        return '\n\n'.join([page['text'] for page in self.pages if page.get('text')])


class UnifiedOCRProcessor:
    """
    统一OCR处理器

    提供NDL OCRlite和NDL古典籍OCR-Lite的统一接口
    支持运行时模型切换
    """

    MODEL_INFO = {
        'ndlocr_lite': {
            'name': 'NDL OCRlite',
            'name_cn': 'NDL OCR(近代现代文献)',
            'description': '用于识别近代现代日本印刷体文献',
            'use_case': '近代文献、现代文献、新闻、杂志、书籍等印刷体文字',
            'github': 'https://github.com/ndl-lab/ndlocr-lite'
        },
        'ndlkotenocr_lite': {
            'name': 'NDL古典籍OCR-Lite',
            'name_cn': 'NDL古典籍OCR(古典籍文献)',
            'description': '用于识别古典籍资料(江戸期以前的和古書、清代以前的漢籍)',
            'use_case': '江戸期以前的古典籍、漢籍、草书字、和古書等',
            'github': 'https://github.com/ndl-lab/ndlkotenocr-lite'
        }
    }

    def __init__(self, config: Optional[UnifiedOCRConfig] = None):
        """
        初始化统一OCR处理器

        Args:
            config: 统一OCR配置对象
        """
        self.config = config or UnifiedOCRConfig()
        self.ndlocr_processor = None
        self.ndlkoten_processor = None
        self._init_processors()

    def _init_processors(self):
        """初始化各OCR处理器"""
        try:
            from modules.ndlocr_lite import NDLOCRLiteProcessor, NDLOCRLiteConfig
            ndlocr_config = NDLOCRLiteConfig(
                ndlocr_path=self.config.ndlocr_path,
                use_gpu=self.config.use_gpu,
                enable_visualization=self.config.enable_visualization,
                timeout=self.config.timeout
            )
            self.ndlocr_processor = NDLOCRLiteProcessor(ndlocr_config)
            print("[OK] NDL OCRlite 处理器初始化成功")
        except Exception as e:
            print(f"[WARN] NDL OCRlite 处理器初始化失败: {e}")
            self.ndlocr_processor = None

        try:
            from modules.ndlkotenocr_lite import NDLKotenOCRLiteProcessor, NDLKotenOCRLiteConfig
            ndlkoten_config = NDLKotenOCRLiteConfig(
                ndlkoten_path=self.config.ndlkoten_path,
                use_gpu=self.config.use_gpu,
                enable_visualization=self.config.enable_visualization,
                timeout=self.config.timeout
            )
            self.ndlkoten_processor = NDLKotenOCRLiteProcessor(ndlkoten_config)
            print("[OK] NDL古典籍OCR-Lite 处理器初始化成功")
        except Exception as e:
            print(f"[WARN] NDL古典籍OCR-Lite 处理器初始化失败: {e}")
            self.ndlkoten_processor = None

    def is_model_available(self, model_type: str = 'ndlocr_lite') -> bool:
        """
        检查指定模型是否可用

        Args:
            model_type: 模型类型

        Returns:
            bool: 模型是否可用
        """
        if model_type == 'ndlocr_lite':
            return self.ndlocr_processor is not None and self.ndlocr_processor.is_installed()
        elif model_type == 'ndlkotenocr_lite':
            return self.ndlkoten_processor is not None and self.ndlkoten_processor.is_installed()
        return False

    def get_available_models(self) -> List[Dict[str, Any]]:
        """
        获取所有可用的OCR模型

        Returns:
            list: 可用模型列表
        """
        available = []
        for model_type, info in self.MODEL_INFO.items():
            is_available = self.is_model_available(model_type)
            available.append({
                'type': model_type,
                'name': info['name'],
                'name_cn': info['name_cn'],
                'description': info['description'],
                'use_case': info['use_case'],
                'available': is_available
            })
        return available

    def get_model_info(self, model_type: str) -> Optional[Dict[str, Any]]:
        """
        获取指定模型的详细信息

        Args:
            model_type: 模型类型

        Returns:
            dict: 模型信息
        """
        info = self.MODEL_INFO.get(model_type)
        if info:
            info = info.copy()
            info['type'] = model_type
            info['available'] = self.is_model_available(model_type)
            return info
        return None

    def process_image(self, image_path: str,
                     model_type: Optional[str] = None,
                     output_dir: Optional[str] = None) -> UnifiedOCRResult:
        """
        处理单张图片

        Args:
            image_path: 图片文件路径
            model_type: OCR模型类型 ('ndlocr_lite' 或 'ndlkotenocr_lite')
            output_dir: 输出目录路径(可选)

        Returns:
            UnifiedOCRResult: 处理结果
        """
        if model_type is None:
            model_type = self.config.default_model

        result = UnifiedOCRResult()
        result.model_type = model_type

        model_info = self.get_model_info(model_type)
        if model_info:
            result.model_description = model_info['name_cn']

        if not self.is_model_available(model_type):
            result.error = f"{model_info['name'] if model_info else model_type} 未安装或不可用"
            return result

        try:
            if model_type == 'ndlocr_lite':
                ocr_result = self.ndlocr_processor.process_image(image_path, output_dir)
            elif model_type == 'ndlkotenocr_lite':
                ocr_result = self.ndlkoten_processor.process_image(image_path, output_dir)
            else:
                result.error = f"不支持的模型类型: {model_type}"
                return result

            result.success = ocr_result.success
            result.text = ocr_result.text
            result.xml_content = ocr_result.xml_content
            result.pages = ocr_result.pages
            result.structures = ocr_result.structures
            result.error = ocr_result.error
            result.processing_time = ocr_result.processing_time
            result.output_dir = ocr_result.output_dir
            result.visualization_paths = ocr_result.visualization_paths

        except Exception as e:
            result.error = f"处理异常: {str(e)}"

        return result

    def process_directory(self, directory_path: str,
                         model_type: Optional[str] = None,
                         output_dir: Optional[str] = None) -> UnifiedOCRResult:
        """
        批量处理目录中的所有图片

        Args:
            directory_path: 包含图片的目录路径
            model_type: OCR模型类型
            output_dir: 输出目录路径(可选)

        Returns:
            UnifiedOCRResult: 处理结果
        """
        if model_type is None:
            model_type = self.config.default_model

        result = UnifiedOCRResult()
        result.model_type = model_type

        model_info = self.get_model_info(model_type)
        if model_info:
            result.model_description = model_info['name_cn']

        if not self.is_model_available(model_type):
            result.error = f"{model_info['name'] if model_info else model_type} 未安装或不可用"
            return result

        try:
            if model_type == 'ndlocr_lite':
                ocr_result = self.ndlocr_processor.process_directory(directory_path, output_dir)
            elif model_type == 'ndlkotenocr_lite':
                ocr_result = self.ndlkoten_processor.process_directory(directory_path, output_dir)
            else:
                result.error = f"不支持的模型类型: {model_type}"
                return result

            result.success = ocr_result.success
            result.text = ocr_result.text
            result.xml_content = ocr_result.xml_content
            result.pages = ocr_result.pages
            result.structures = ocr_result.structures
            result.error = ocr_result.error
            result.processing_time = ocr_result.processing_time
            result.output_dir = ocr_result.output_dir
            result.visualization_paths = ocr_result.visualization_paths

        except Exception as e:
            result.error = f"批量处理异常: {str(e)}"

        return result

    def compare_models(self, image_path: str,
                      output_dir: Optional[str] = None) -> Dict[str, UnifiedOCRResult]:
        """
        使用两种模型处理同一张图片，对比结果

        Args:
            image_path: 图片文件路径
            output_dir: 输出目录路径(可选)

        Returns:
            dict: 两种模型的OCR结果
        """
        results = {}

        if self.is_model_available('ndlocr_lite'):
            results['ndlocr_lite'] = self.process_image(image_path, 'ndlocr_lite', output_dir)

        if self.is_model_available('ndlkotenocr_lite'):
            results['ndlkotenocr_lite'] = self.process_image(image_path, 'ndlkotenocr_lite', output_dir)

        return results
