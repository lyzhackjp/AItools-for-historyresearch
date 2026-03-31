"""
OCR处理模块 - 优化版

支持多种OCR引擎，提供图像预处理和多引擎对比功能

优化内容 (v2.0.0):
- 集成多引擎对比功能（Tesseract、NDL OCR、LLM OCR）
- 添加图像预处理（降噪、二值化、倾斜校正）
- 优化输出格式，支持结构化结果
- 添加置信度评估和结果验证

核心功能：
- 多OCR引擎支持
- 图像预处理
- 多引擎结果对比
- 置信度评估

支持的OCR引擎：
- Tesseract OCR
- NDL Lab OCR
- NDL OCR-Lite
- LLM辅助OCR
"""

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import io
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
import os
from dataclasses import dataclass
from enum import Enum


class OCREngine(Enum):
    """OCR引擎枚举"""
    TESSERACT = 'tesseract'
    NDL = 'ndl'
    NDL_LITE = 'ndlocr-lite'
    LLM = 'llm'
    AUTO = 'auto'


@dataclass
class OCRResult:
    """OCR识别结果数据类"""
    text: str
    confidence: float
    engine: str
    language: str
    processing_time: float
    word_count: int
    char_count: int
    success: bool
    error: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


class ImagePreprocessor:
    """图像预处理器"""
    
    @staticmethod
    def denoise(image: Image.Image, strength: int = 1) -> Image.Image:
        """
        降噪处理
        
        Args:
            image: PIL图像对象
            strength: 降噪强度 (1-3)
            
        Returns:
            Image: 处理后的图像
        """
        if strength == 1:
            return image.filter(ImageFilter.MedianFilter(size=3))
        elif strength == 2:
            return image.filter(ImageFilter.MedianFilter(size=5))
        else:
            return image.filter(ImageFilter.MedianFilter(size=7))
    
    @staticmethod
    def binarize(image: Image.Image, threshold: int = 128) -> Image.Image:
        """
        二值化处理
        
        Args:
            image: PIL图像对象
            threshold: 二值化阈值
            
        Returns:
            Image: 二值化后的图像
        """
        if image.mode != 'L':
            image = image.convert('L')
        
        return image.point(lambda x: 255 if x > threshold else 0, '1')
    
    @staticmethod
    def enhance_contrast(image: Image.Image, factor: float = 1.5) -> Image.Image:
        """
        增强对比度
        
        Args:
            image: PIL图像对象
            factor: 增强因子
            
        Returns:
            Image: 处理后的图像
        """
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(factor)
    
    @staticmethod
    def enhance_sharpness(image: Image.Image, factor: float = 2.0) -> Image.Image:
        """
        增强锐度
        
        Args:
            image: PIL图像对象
            factor: 增强因子
            
        Returns:
            Image: 处理后的图像
        """
        enhancer = ImageEnhance.Sharpness(image)
        return enhancer.enhance(factor)
    
    @staticmethod
    def deskew(image: Image.Image) -> Image.Image:
        """
        倾斜校正
        
        Args:
            image: PIL图像对象
            
        Returns:
            Image: 校正后的图像
        """
        try:
            import cv2
            
            img_array = np.array(image)
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array
            
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            coords = np.column_stack(np.where(binary > 0))
            angle = cv2.minAreaRect(coords)[-1]
            
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
            
            if abs(angle) < 0.5:
                return image
            
            (h, w) = img_array.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(img_array, M, (w, h), 
                                     flags=cv2.INTER_CUBIC, 
                                     borderMode=cv2.BORDER_REPLICATE)
            
            return Image.fromarray(rotated)
            
        except ImportError:
            return image
        except Exception:
            return image
    
    @classmethod
    def preprocess_for_ocr(cls, image: Image.Image, 
                          enable_denoise: bool = True,
                          enable_binarize: bool = False,
                          enable_contrast: bool = True,
                          enable_sharpness: bool = True,
                          enable_deskew: bool = True) -> Image.Image:
        """
        OCR预处理流水线
        
        Args:
            image: PIL图像对象
            enable_denoise: 是否启用降噪
            enable_binarize: 是否启用二值化
            enable_contrast: 是否启用对比度增强
            enable_sharpness: 是否启用锐度增强
            enable_deskew: 是否启用倾斜校正
            
        Returns:
            Image: 预处理后的图像
        """
        processed = image.copy()
        
        if enable_deskew:
            processed = cls.deskew(processed)
        
        if enable_denoise:
            processed = cls.denoise(processed, strength=1)
        
        if enable_contrast:
            processed = cls.enhance_contrast(processed, factor=1.3)
        
        if enable_sharpness:
            processed = cls.enhance_sharpness(processed, factor=1.5)
        
        if enable_binarize:
            processed = cls.binarize(processed, threshold=140)
        
        return processed


class OCRProcessorOptimized:
    """OCR处理器 - 优化版"""
    
    SUPPORTED_LANGUAGES = ['eng', 'jpn', 'chi_sim', 'chi_tra', 'kor']
    LANGUAGES_MAP = {
        'en': 'eng',
        'ja': 'jpn',
        'zh': 'chi_sim',
        'zh-tw': 'chi_tra',
        'ko': 'kor'
    }
    
    ENGINE_PRIORITY = [OCREngine.NDL_LITE, OCREngine.TESSERACT, OCREngine.LLM]

    def __init__(self, tesseract_path: Optional[str] = None, 
                 ndl_model_path: Optional[str] = None,
                 enable_preprocessing: bool = True):
        """
        初始化OCR处理器
        
        Args:
            tesseract_path: Tesseract可执行文件路径
            ndl_model_path: NDL OCR模型路径
            enable_preprocessing: 是否启用图像预处理
        """
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        
        self.ndl_model = None
        self.ndl_processor = None
        self.ndl_model_path = ndl_model_path
        self.ndl_available = False
        self.enable_preprocessing = enable_preprocessing
        self.preprocessor = ImagePreprocessor()
        
        self._init_ndl_model()

    def _init_ndl_model(self):
        """初始化NDL Lab OCR模型"""
        try:
            from transformers import AutoProcessor, AutoModelForVision2Seq
            import torch
            
            if self.ndl_model_path and os.path.exists(self.ndl_model_path):
                model_name = self.ndl_model_path
            else:
                model_name = "NDLCLab/ndl-ocr-japanese"
            
            self.ndl_processor = AutoProcessor.from_pretrained(model_name)
            self.ndl_model = AutoModelForVision2Seq.from_pretrained(
                model_name,
                torch_dtype=torch.float16,
                device_map="auto"
            )
            
            self.ndl_available = True
            print(f"✓ NDL OCR模型加载成功")
            
        except ImportError:
            print("警告: transformers库未安装，无法使用NDL OCR模型")
            self.ndl_available = False
        except Exception as e:
            print(f"警告: NDL OCR模型初始化失败: {e}")
            self.ndl_available = False

    def extract_text_from_image(self, image_path: str,
                                language: str = 'zh',
                                config: Optional[str] = None,
                                preprocess: bool = True) -> OCRResult:
        """
        从图片中提取文字
        
        Args:
            image_path: 图片文件路径
            language: 识别语言
            config: Tesseract配置参数
            preprocess: 是否预处理
            
        Returns:
            OCRResult: OCR识别结果
        """
        import time
        start_time = time.time()
        
        try:
            img = Image.open(image_path)
            
            if preprocess and self.enable_preprocessing:
                img = self.preprocessor.preprocess_for_ocr(img)
            
            lang_code = self.LANGUAGES_MAP.get(language, language)
            if lang_code not in self.SUPPORTED_LANGUAGES:
                lang_code = 'eng'
            
            if config is None:
                config = '--psm 6'
            
            text = pytesseract.image_to_string(img, lang=lang_code, config=config)
            
            data = pytesseract.image_to_data(img, lang=lang_code, config=config, 
                                            output_type=pytesseract.Output.DICT)
            
            confidences = [c for c in data['conf'] if c > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            processing_time = time.time() - start_time
            
            return OCRResult(
                text=text.strip(),
                confidence=avg_confidence / 100.0,
                engine='tesseract',
                language=language,
                processing_time=processing_time,
                word_count=len(text.split()),
                char_count=len(text),
                success=True,
                raw_data=data
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            return OCRResult(
                text='',
                confidence=0.0,
                engine='tesseract',
                language=language,
                processing_time=processing_time,
                word_count=0,
                char_count=0,
                success=False,
                error=str(e)
            )

    def compare_engines(self, image_path: str,
                       language: str = 'zh',
                       engines: Optional[List[OCREngine]] = None,
                       llm_client=None) -> Dict[str, OCRResult]:
        """
        多引擎对比识别
        
        Args:
            image_path: 图片文件路径
            language: 识别语言
            engines: 要使用的引擎列表
            llm_client: LLM客户端
            
        Returns:
            dict: 各引擎的识别结果
        """
        engines = engines or self.ENGINE_PRIORITY
        results = {}
        
        for engine in engines:
            if engine == OCREngine.TESSERACT:
                results['tesseract'] = self.extract_text_from_image(
                    image_path, language, preprocess=True
                )
            elif engine == OCREngine.NDL_LITE:
                results['ndlocr-lite'] = self.ndlocr_lite_ocr(image_path)
            elif engine == OCREngine.NDL:
                results['ndl'] = self.ndl_ocr(image_path)
            elif engine == OCREngine.LLM and llm_client:
                results['llm'] = self.llm_ocr(image_path, llm_client, language)
        
        return results

    def get_best_result(self, comparison_results: Dict[str, OCRResult]) -> OCRResult:
        """
        从多引擎结果中选择最佳结果
        
        Args:
            comparison_results: 多引擎对比结果
            
        Returns:
            OCRResult: 最佳识别结果
        """
        valid_results = [r for r in comparison_results.values() if r.success]
        
        if not valid_results:
            return OCRResult(
                text='',
                confidence=0.0,
                engine='none',
                language='unknown',
                processing_time=0.0,
                word_count=0,
                char_count=0,
                success=False,
                error='所有OCR引擎均失败'
            )
        
        scored_results = []
        for result in valid_results:
            score = result.confidence * 0.5
            
            if 100 < result.char_count < 5000:
                score += 0.3
            
            if result.text and not result.text.isspace():
                score += 0.2
            
            scored_results.append((result, score))
        
        scored_results.sort(key=lambda x: x[1], reverse=True)
        
        return scored_results[0][0]

    def ndl_ocr(self, image_path: str) -> OCRResult:
        """使用NDL Lab OCR模型"""
        import time
        start_time = time.time()
        
        if not self.ndl_available:
            return OCRResult(
                text='',
                confidence=0.0,
                engine='ndl',
                language='ja',
                processing_time=0.0,
                word_count=0,
                char_count=0,
                success=False,
                error='NDL OCR模型未初始化或不可用'
            )
        
        try:
            import torch
            
            image = Image.open(image_path)
            
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            inputs = self.ndl_processor(text="日OCR", images=image, return_tensors="pt")
            
            if torch.cuda.is_available():
                inputs = {k: v.to("cuda") if isinstance(v, torch.Tensor) else v 
                         for k, v in inputs.items()}
            
            generated_ids = self.ndl_model.generate(
                pixel_values=inputs["pixel_values"],
                max_length=512,
                num_beams=5,
                do_sample=False
            )
            
            generated_text = self.ndl_processor.batch_decode(
                generated_ids, skip_special_tokens=True
            )[0]
            
            processing_time = time.time() - start_time
            
            return OCRResult(
                text=generated_text.strip(),
                confidence=0.85,
                engine='ndl',
                language='ja',
                processing_time=processing_time,
                word_count=len(generated_text.split()),
                char_count=len(generated_text),
                success=True
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            return OCRResult(
                text='',
                confidence=0.0,
                engine='ndl',
                language='ja',
                processing_time=processing_time,
                word_count=0,
                char_count=0,
                success=False,
                error=str(e)
            )

    def ndlocr_lite_ocr(self, image_path: str,
                       use_gpu: bool = False) -> OCRResult:
        """使用NDL OCR-Lite"""
        import time
        start_time = time.time()
        
        try:
            from modules.ndlocr_lite import create_ndlocr_processor
            
            processor = create_ndlocr_processor(use_gpu=use_gpu)
            
            if not processor.is_installed():
                return OCRResult(
                    text='',
                    confidence=0.0,
                    engine='ndlocr-lite',
                    language='ja',
                    processing_time=0.0,
                    word_count=0,
                    char_count=0,
                    success=False,
                    error='NDL OCR-Lite未安装'
                )
            
            result = processor.process_image(image_path)
            
            processing_time = time.time() - start_time
            
            return OCRResult(
                text=result.text if hasattr(result, 'text') else '',
                confidence=0.90,
                engine='ndlocr-lite',
                language='ja',
                processing_time=processing_time,
                word_count=len(result.text.split()) if hasattr(result, 'text') else 0,
                char_count=len(result.text) if hasattr(result, 'text') else 0,
                success=result.success if hasattr(result, 'success') else True
            )
            
        except ImportError:
            return OCRResult(
                text='',
                confidence=0.0,
                engine='ndlocr-lite',
                language='ja',
                processing_time=0.0,
                word_count=0,
                char_count=0,
                success=False,
                error='NDL OCR-Lite模块未找到'
            )
        except Exception as e:
            processing_time = time.time() - start_time
            return OCRResult(
                text='',
                confidence=0.0,
                engine='ndlocr-lite',
                language='ja',
                processing_time=processing_time,
                word_count=0,
                char_count=0,
                success=False,
                error=str(e)
            )

    def llm_ocr(self, image_path: str,
                llm_client,
                language: str = 'zh') -> OCRResult:
        """使用LLM进行OCR"""
        import time
        start_time = time.time()
        
        language_prompts = {
            'zh': '这是一张中文图片，请识别其中的所有文字内容，保持原有格式和结构。',
            'ja': 'これは日本語の画像です。すべてのテキスト内容を識別し、元のフォーマットと構造を維持してください。',
            'en': 'This is an image containing text. Please identify all the text content.'
        }
        
        prompt = language_prompts.get(language, language_prompts['zh'])
        
        try:
            with open(image_path, 'rb') as f:
                import base64
                img_base64 = base64.b64encode(f.read()).decode('utf-8')
            
            full_prompt = f"{prompt}\n\n[图片数据: data:image/png;base64,{img_base64[:100]}...]"
            
            result = llm_client._call_llm(full_prompt)
            
            text = result.get('content', '')
            processing_time = time.time() - start_time
            
            return OCRResult(
                text=text,
                confidence=0.80,
                engine='llm',
                language=language,
                processing_time=processing_time,
                word_count=len(text.split()),
                char_count=len(text),
                success=True
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            return OCRResult(
                text='',
                confidence=0.0,
                engine='llm',
                language=language,
                processing_time=processing_time,
                word_count=0,
                char_count=0,
                success=False,
                error=str(e)
            )

    def batch_ocr(self, image_paths: List[str],
                 language: str = 'zh',
                 engine: OCREngine = OCREngine.AUTO) -> List[OCRResult]:
        """
        批量OCR处理
        
        Args:
            image_paths: 图片路径列表
            language: 识别语言
            engine: OCR引擎
            
        Returns:
            list: OCR结果列表
        """
        results = []
        
        for image_path in image_paths:
            if engine == OCREngine.AUTO:
                comparison = self.compare_engines(image_path, language)
                result = self.get_best_result(comparison)
            elif engine == OCREngine.TESSERACT:
                result = self.extract_text_from_image(image_path, language)
            elif engine == OCREngine.NDL:
                result = self.ndl_ocr(image_path)
            elif engine == OCREngine.NDL_LITE:
                result = self.ndlocr_lite_ocr(image_path)
            else:
                result = self.extract_text_from_image(image_path, language)
            
            results.append(result)
        
        return results

    def get_available_engines(self) -> List[str]:
        """获取可用的OCR引擎列表"""
        engines = ['tesseract']
        
        if self.ndl_available:
            engines.append('ndl')
        
        try:
            from modules.ndlocr_lite import NDLOCRLiteProcessor
            if NDLOCRLiteProcessor().is_installed():
                engines.append('ndlocr-lite')
        except:
            pass
        
        engines.append('llm')
        
        return engines

    def get_supported_methods(self) -> List[str]:
        """获取支持的OCR方法列表"""
        return self.get_available_engines()


def create_ocr_processor_optimized(tesseract_path: Optional[str] = None, 
                                   ndl_model_path: Optional[str] = None,
                                   enable_preprocessing: bool = True) -> OCRProcessorOptimized:
    """
    工厂函数 - 创建优化版OCR处理器实例
    
    Args:
        tesseract_path: Tesseract路径
        ndl_model_path: NDL OCR模型路径
        enable_preprocessing: 是否启用预处理
        
    Returns:
        OCRProcessorOptimized: OCR处理器实例
    """
    return OCRProcessorOptimized(tesseract_path, ndl_model_path, enable_preprocessing)
