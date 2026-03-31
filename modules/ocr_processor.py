import pytesseract
from PIL import Image
import io
from typing import Dict, Any, Optional, List
import numpy as np
import os


class OCRProcessor:
    """OCR处理接口 - 支持多种OCR引擎"""

    SUPPORTED_LANGUAGES = ['eng', 'jpn', 'chi_sim', 'chi_tra', 'kor']
    LANGUAGES_MAP = {
        'en': 'eng',
        'ja': 'jpn',
        'zh': 'chi_sim',
        'zh-tw': 'chi_tra',
        'ko': 'kor'
    }

    def __init__(self, tesseract_path: Optional[str] = None, ndl_model_path: Optional[str] = None):
        """
        初始化OCR处理器

        Args:
            tesseract_path: Tesseract可执行文件路径（可选）
            ndl_model_path: NDL OCR模型路径（可选）
        """
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        
        self.ndl_model = None
        self.ndl_processor = None
        self.ndl_model_path = ndl_model_path
        self.ndl_available = False
        
        self._init_ndl_model()

    def _init_ndl_model(self):
        """
        初始化NDL Lab OCR模型
        
        NDL (National Diet Library) Lab发布了基于Transformer的OCR模型
        主要用于日文文献的识别，GitHub: https://github.com/ndl-lab/ndl-ocr
        """
        try:
            from transformers import AutoProcessor, AutoModelForVision2Seq
            from PIL import Image
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
            print(f"NDL OCR模型加载成功")
            
        except ImportError:
            print("警告: transformers库未安装，无法使用NDL OCR模型")
            print("请运行: pip install transformers torch")
            self.ndl_available = False
        except Exception as e:
            print(f"警告: NDL OCR模型初始化失败: {e}")
            self.ndl_available = False

    def extract_text_from_image(self, image_path: str,
                                language: str = 'zh',
                                config: Optional[str] = None) -> Dict[str, Any]:
        """
        从图片中提取文字（使用Tesseract）

        Args:
            image_path: 图片文件路径
            language: 识别语言
            config: Tesseract配置参数

        Returns:
            dict: 包含识别结果和详细信息的字典
        """
        try:
            img = Image.open(image_path)

            lang_code = self.LANGUAGES_MAP.get(language, language)
            if lang_code not in self.SUPPORTED_LANGUAGES:
                lang_code = 'eng'

            if config is None:
                config = '--psm 6'

            text = pytesseract.image_to_string(img, lang=lang_code, config=config)

            data = pytesseract.image_to_data(img, lang=lang_code, config=config, output_type=pytesseract.Output.DICT)

            words = []
            for i, word in enumerate(data['text']):
                if word.strip():
                    words.append({
                        'word': word,
                        'confidence': data['conf'][i],
                        'bbox': {
                            'x': data['left'][i],
                            'y': data['top'][i],
                            'width': data['width'][i],
                            'height': data['height'][i]
                        }
                    })

            return {
                'success': True,
                'text': text.strip(),
                'words': words,
                'language': language,
                'config': config,
                'method': 'tesseract'
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'text': '',
                'words': [],
                'method': 'tesseract'
            }

    def extract_text_from_bytes(self, image_bytes: bytes,
                                language: str = 'zh',
                                config: Optional[str] = None) -> Dict[str, Any]:
        """
        从图片字节流中提取文字

        Args:
            image_bytes: 图片字节流
            language: 识别语言
            config: Tesseract配置参数

        Returns:
            dict: 包含识别结果的字典
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))

            lang_code = self.LANGUAGES_MAP.get(language, language)
            if lang_code not in self.SUPPORTED_LANGUAGES:
                lang_code = 'eng'

            if config is None:
                config = '--psm 6'

            text = pytesseract.image_to_string(img, lang=lang_code, config=config)

            return {
                'success': True,
                'text': text.strip(),
                'language': language,
                'method': 'tesseract'
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'text': '',
                'method': 'tesseract'
            }

    def extract_text_with_regions(self, image_path: str,
                                 regions: List[Dict[str, int]],
                                 language: str = 'zh') -> Dict[str, Any]:
        """
        从图片指定区域提取文字

        Args:
            image_path: 图片文件路径
            regions: 区域列表 [{'x': 0, 'y': 0, 'width': 100, 'height': 50}]
            language: 识别语言

        Returns:
            dict: 各区域的识别结果
        """
        img = Image.open(image_path)
        results = {}

        lang_code = self.LANGUAGES_MAP.get(language, language)

        for i, region in enumerate(regions):
            x = region.get('x', 0)
            y = region.get('y', 0)
            w = region.get('width', img.width)
            h = region.get('height', img.height)

            cropped_img = img.crop((x, y, x + w, y + h))

            text = pytesseract.image_to_string(cropped_img, lang=lang_code)
            results[f'region_{i}'] = text.strip()

        return results

    def batch_ocr(self, image_paths: List[str],
                 language: str = 'zh') -> List[Dict[str, Any]]:
        """
        批量OCR处理

        Args:
            image_paths: 图片文件路径列表
            language: 识别语言

        Returns:
            list: 每个图片的OCR结果
        """
        results = []

        for image_path in image_paths:
            result = self.extract_text_from_image(image_path, language)
            result['image_path'] = image_path
            results.append(result)

        return results

    def llm_ocr(self, image_path: str,
                llm_client,
                language: str = 'zh',
                prompt_template: Optional[str] = None) -> Dict[str, Any]:
        """
        使用大语言模型进行OCR识别

        Args:
            image_path: 图片文件路径
            llm_client: LLM客户端实例
            language: 图片语言
            prompt_template: 自定义提示词模板

        Returns:
            dict: LLM OCR结果
        """
        img = Image.open(image_path)

        with open(image_path, 'rb') as f:
            import base64
            img_base64 = base64.b64encode(f.read()).decode('utf-8')

        language_prompts = {
            'zh': '这是一张中文图片，请识别其中的所有文字内容，保持原有格式和结构。',
            'ja': 'これは日本語の画像です。すべてのテキスト内容を識別し、元のフォーマットと構造を維持してください。',
            'en': 'This is an image containing text. Please identify all the text content and maintain the original format and structure.'
        }

        prompt = prompt_template or language_prompts.get(language, language_prompts['zh'])

        full_prompt = f"{prompt}\n\n[图片数据: data:image/png;base64,{img_base64}]"

        try:
            result = llm_client._call_llm(full_prompt)
            return {
                'success': True,
                'text': result.get('content', ''),
                'method': 'llm',
                'language': language
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'text': '',
                'method': 'llm'
            }

    def ndl_ocr(self, image_path: str) -> Dict[str, Any]:
        """
        使用NDL Lab OCR模型进行文字识别
        
        NDL Lab的OCR模型基于Transformer架构，专门针对日文文献优化
        支持手写文字、历史文献等多种复杂场景
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            dict: 包含识别结果的字典
        """
        if not self.ndl_available:
            return {
                'success': False,
                'error': 'NDL OCR模型未初始化或不可用',
                'text': '',
                'method': 'ndl'
            }
        
        try:
            from transformers import AutoProcessor, AutoModelForVision2Seq
            from PIL import Image
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
            
            generated_text = self.ndl_processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            return {
                'success': True,
                'text': generated_text.strip(),
                'method': 'ndl',
                'model': 'NDL-Lab-OCR'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'text': '',
                'method': 'ndl'
            }

    def ndl_ocr_batch(self, image_paths: List[str]) -> List[Dict[str, Any]]:
        """
        批量使用NDL OCR模型进行文字识别
        
        Args:
            image_paths: 图片文件路径列表
            
        Returns:
            list: 每个图片的OCR结果
        """
        results = []
        
        for image_path in image_paths:
            result = self.ndl_ocr(image_path)
            result['image_path'] = image_path
            results.append(result)
        
        return results

    def extract_text_with_method(self, image_path: str,
                                 method: str = 'tesseract',
                                 language: str = 'zh',
                                 llm_client=None) -> Dict[str, Any]:
        """
        使用指定方法提取文字
        
        Args:
            image_path: 图片文件路径
            method: OCR方法 ('tesseract', 'ndl', 'llm')
            language: 识别语言
            llm_client: LLM客户端实例（当method='llm'时必需）
            
        Returns:
            dict: 识别结果
        """
        if method == 'tesseract':
            return self.extract_text_from_image(image_path, language)
        elif method == 'ndl':
            return self.ndl_ocr(image_path)
        elif method == 'llm':
            if llm_client is None:
                return {
                    'success': False,
                    'error': 'LLM客户端未提供',
                    'text': '',
                    'method': 'llm'
                }
            return self.llm_ocr(image_path, llm_client, language)
        else:
            return {
                'success': False,
                'error': f'不支持的OCR方法: {method}',
                'text': '',
                'method': method
            }

    def get_available_languages(self) -> List[str]:
        """获取支持的OCR语言列表"""
        return list(self.LANGUAGES_MAP.keys())
    
    def is_ndl_available(self) -> bool:
        """检查NDL OCR模型是否可用"""
        return self.ndl_available
    
    def get_supported_methods(self) -> List[str]:
        """获取支持的OCR方法列表"""
        methods = ['tesseract']
        if self.ndl_available:
            methods.append('ndl')
        methods.append('llm')
        try:
            from modules.ndlocr_lite import NDLOCRLiteProcessor
            ndl_lite = NDLOCRLiteProcessor()
            if ndl_lite.is_installed():
                methods.append('ndlocr-lite')
        except:
            pass
        return methods

    def ndlocr_lite_ocr(self, image_path: str,
                       use_gpu: bool = False,
                       enable_viz: bool = False) -> Dict[str, Any]:
        """
        使用NDL OCR-Lite进行文字识别
        
        NDL OCR-Lite是日本国立国会图书馆开发的轻量级OCR工具
        专门针对日文文献优化，支持批量处理
        
        Args:
            image_path: 图片文件路径
            use_gpu: 是否使用GPU加速
            enable_viz: 是否生成可视化结果
            
        Returns:
            dict: 识别结果
        """
        try:
            from modules.ndlocr_lite import create_ndlocr_processor, NDLOCRLiteResult
            from modules.ndlocr_result_processor import create_result_processor
            
            processor = create_ndlocr_processor(
                use_gpu=use_gpu,
                enable_viz=enable_viz
            )
            
            if not processor.is_installed():
                return {
                    'success': False,
                    'error': 'NDL OCR-Lite未安装\n' + processor.get_installation_guide(),
                    'method': 'ndlocr-lite',
                    'text': ''
                }
            
            result = processor.process_image(image_path)
            
            result_processor = create_result_processor()
            processed = result_processor.process_result(result)
            
            return {
                'success': result.success,
                'text': processed.get('processed_text', ''),
                'structured_data': processed.get('structured_data', {}),
                'pages': processed.get('pages', []),
                'statistics': processed.get('statistics', {}),
                'method': 'ndlocr-lite',
                'raw_result': result.to_dict(),
                'processed_result': processed,
                'output_dir': result.output_dir,
                'visualization_paths': result.visualization_paths
            }
            
        except ImportError:
            return {
                'success': False,
                'error': 'NDL OCR-Lite模块未找到，请确保已正确安装',
                'method': 'ndlocr-lite',
                'text': ''
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'NDL OCR-Lite处理失败: {str(e)}',
                'method': 'ndlocr-lite',
                'text': ''
            }

    def ndlocr_lite_batch(self, directory_path: str,
                          use_gpu: bool = False,
                          enable_viz: bool = False) -> Dict[str, Any]:
        """
        批量使用NDL OCR-Lite处理目录中的图片
        
        Args:
            directory_path: 包含图片的目录路径
            use_gpu: 是否使用GPU加速
            enable_viz: 是否生成可视化结果
            
        Returns:
            dict: 批量处理结果
        """
        try:
            from modules.ndlocr_lite import create_ndlocr_processor
            from modules.ndlocr_result_processor import create_result_processor
            
            processor = create_ndlocr_processor(
                use_gpu=use_gpu,
                enable_viz=enable_viz
            )
            
            if not processor.is_installed():
                return {
                    'success': False,
                    'error': 'NDL OCR-Lite未安装\n' + processor.get_installation_guide(),
                    'method': 'ndlocr-lite',
                    'text': ''
                }
            
            result = processor.process_directory(directory_path)
            
            result_processor = create_result_processor()
            processed = result_processor.process_result(result)
            
            return {
                'success': result.success,
                'text': processed.get('processed_text', ''),
                'structured_data': processed.get('structured_data', {}),
                'pages': processed.get('pages', []),
                'statistics': processed.get('statistics', {}),
                'method': 'ndlocr-lite',
                'total_pages': len(result.pages),
                'raw_result': result.to_dict(),
                'processed_result': processed,
                'output_dir': result.output_dir,
                'visualization_paths': result.visualization_paths
            }
            
        except ImportError:
            return {
                'success': False,
                'error': 'NDL OCR-Lite模块未找到',
                'method': 'ndlocr-lite',
                'text': ''
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'NDL OCR-Lite批量处理失败: {str(e)}',
                'method': 'ndlocr-lite',
                'text': ''
            }

    def is_ndlocr_lite_available(self) -> bool:
        """检查NDL OCR-Lite是否可用"""
        try:
            from modules.ndlocr_lite import NDLOCRLiteProcessor
            processor = NDLOCRLiteProcessor()
            return processor.is_installed()
        except:
            return False


def create_ocr_processor(tesseract_path: Optional[str] = None, 
                        ndl_model_path: Optional[str] = None) -> OCRProcessor:
    """
    工厂函数 - 创建OCR处理器实例
    
    Args:
        tesseract_path: Tesseract路径
        ndl_model_path: NDL OCR模型路径
        
    Returns:
        OCRProcessor: OCR处理器实例
    """
    return OCRProcessor(tesseract_path, ndl_model_path)
