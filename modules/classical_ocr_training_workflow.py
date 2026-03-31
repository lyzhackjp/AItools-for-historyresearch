# -*- coding: utf-8 -*-
"""
古典籍OCR训练数据准备工作流模块
集成版面分析、日期匹配和训练数据生成功能
作为古典OCR训练资料准备阶段的核心步骤
"""

import os
import sys
import json
import re
import fitz
import numpy as np
from PIL import Image
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import io
import logging

def convert_to_serializable(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        return convert_to_serializable(obj.__dict__)
    return obj

sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ContentType(Enum):
    PRINTED_DATE = "printed_date"
    PRINTED_WEATHER = "printed_weather"
    PRINTED_QUOTE = "printed_quote"
    HANDWRITTEN = "handwritten"
    UNKNOWN = "unknown"

class ProcessingStage(Enum):
    INITIALIZED = "initialized"
    PDF_LOADED = "pdf_loaded"
    LAYOUT_ANALYZED = "layout_analyzed"
    DATES_EXTRACTED = "dates_extracted"
    CONTENT_CLASSIFIED = "content_classified"
    IMAGES_EXTRACTED = "images_extracted"
    ANNOTATIONS_MATCHED = "annotations_matched"
    TRAINING_DATA_GENERATED = "training_data_generated"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class LayoutRegion:
    box: List[int]
    content_type: str
    confidence: float
    text: str = ""
    ocr_text: str = ""
    is_vertical: bool = True
    image_path: str = ""
    metadata: Dict = field(default_factory=dict)

@dataclass
class DateInfo:
    era: str
    era_year: int
    year: int
    month: int
    day: int
    date_key: str
    source_page: int = 0
    line_index: int = 0
    context: str = ""
    ocr_text: str = ""

@dataclass
class TrainingSample:
    image_path: str
    annotation_text: str
    source_page: int
    date_key: str = ""
    box: List[int] = field(default_factory=list)
    confidence: float = 0.0
    content_type: str = "handwritten"
    metadata: Dict = field(default_factory=dict)

@dataclass
class ProcessingResult:
    stage: str
    success: bool
    message: str
    data: Dict = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

class KanjiNumberConverter:
    
    KANJI_NUM = {
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '廿': 20, '卅': 30
    }
    
    @classmethod
    def to_number(cls, s: str) -> int:
        if s.isdigit():
            return int(s)
        
        result = 0
        if '十' in s:
            parts = s.split('十')
            if parts[0]:
                result = cls.KANJI_NUM.get(parts[0], 0) * 10
            else:
                result = 10
            if len(parts) > 1 and parts[1]:
                result += cls.KANJI_NUM.get(parts[1], 0)
        elif '廿' in s:
            result = 20
            remaining = s.replace('廿', '')
            if remaining:
                result += cls.KANJI_NUM.get(remaining, 0)
        elif '卅' in s:
            result = 30
            remaining = s.replace('卅', '')
            if remaining:
                result += cls.KANJI_NUM.get(remaining, 0)
        else:
            result = cls.KANJI_NUM.get(s, 0)
        return result
    
    NUM_KANJI = {v: k for k, v in KANJI_NUM.items()}
    
    @classmethod
    def to_kanji(cls, num: int) -> str:
        if num <= 10:
            return cls.NUM_KANJI.get(num, str(num))
        elif num < 20:
            return '十' + cls.NUM_KANJI.get(num - 10, str(num - 10))
        elif num == 20:
            return '廿'
        elif num < 30:
            return '廿' + cls.NUM_KANJI.get(num - 20, str(num - 20))
        elif num == 30:
            return '卅'
        elif num < 40:
            return '卅' + cls.NUM_KANJI.get(num - 30, str(num - 30))
        else:
            tens = num // 10
            ones = num % 10
            result = cls.NUM_KANJI.get(tens, str(tens)) + '十'
            if ones > 0:
                result += cls.NUM_KANJI.get(ones, str(ones))
            return result

class ONNXModelManager:
    
    def __init__(self, rtmdet_path: str, parseq_path: str, 
                 rtmdet_config: str, parseq_config: str):
        self.rtmdet_path = rtmdet_path
        self.parseq_path = parseq_path
        self.rtmdet_config = rtmdet_config
        self.parseq_config = parseq_config
        
        self.detector = None
        self.recognizer = None
        self.charlist = None
        self.classes = None
        
        self._detector_input_size = 1024
        self._recognizer_input_size = (384, 32)
    
    def load_detector(self) -> bool:
        try:
            import onnxruntime
            import yaml
            
            opt_session = onnxruntime.SessionOptions()
            opt_session.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_DISABLE_ALL
            
            self.detector = onnxruntime.InferenceSession(
                self.rtmdet_path, 
                providers=['CPUExecutionProvider']
            )
            
            with open(self.rtmdet_config, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.classes = config.get('names', {0: 'line_main'})
            
            input_shape = self.detector.get_inputs()[0].shape
            if len(input_shape) >= 4:
                self._detector_input_size = input_shape[2]
            
            logger.info(f"检测模型加载成功，输入尺寸: {self._detector_input_size}")
            return True
        except Exception as e:
            logger.error(f"检测模型加载失败: {e}")
            return False
    
    def load_recognizer(self) -> bool:
        try:
            import onnxruntime
            import yaml
            
            opt_session = onnxruntime.SessionOptions()
            opt_session.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_DISABLE_ALL
            
            self.recognizer = onnxruntime.InferenceSession(
                self.parseq_path,
                providers=['CPUExecutionProvider']
            )
            
            with open(self.parseq_config, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.charlist = list(config.get('model', {}).get('charset_train', []))
            
            logger.info(f"识别模型加载成功，字符集大小: {len(self.charlist)}")
            return True
        except Exception as e:
            logger.error(f"识别模型加载失败: {e}")
            return False
    
    def is_detector_loaded(self) -> bool:
        return self.detector is not None
    
    def is_recognizer_loaded(self) -> bool:
        return self.recognizer is not None and self.charlist is not None

class LayoutDetector:
    
    DATE_PATTERNS = [
        r'明治([一二三四五六七八九十]+)年([一二三四五六七八九十]+)月([一二三四五六七八九十]+)日',
        r'大正([一二三四五六七八九十]+)年([一二三四五六七八九十]+)月([一二三四五六七八九十]+)日',
        r'昭和([一二三四五六七八九十]+)年([一二三四五六七八九十]+)月([一二三四五六七八九十]+)日',
        r'([一二三四五六七八九十]+)月([一二三四五六七八九十]+)日',
    ]
    
    WEATHER_KEYWORDS = ['晴', '曇', '雨', '雪', '風', '快晴', '薄曇', '小雨', '大雨']
    QUOTE_INDICATORS = ['「', '」', '『', '』', '"', '"']
    
    def __init__(self, model_manager: ONNXModelManager):
        self.model_manager = model_manager
    
    def preprocess_for_detection(self, img: np.ndarray) -> Tuple[np.ndarray, int, int]:
        max_wh = max(img.shape[0], img.shape[1])
        paddedimg = np.zeros((max_wh, max_wh, 3)).astype(np.uint8)
        paddedimg[:img.shape[0], :img.shape[1], :] = img.copy()
        
        pil_image = Image.fromarray(paddedimg)
        image_width, image_height = pil_image.size
        
        input_size = self.model_manager._detector_input_size
        pil_resized = pil_image.resize((input_size, input_size))
        resized = np.array(pil_resized)
        resized = resized[:, :, ::-1]
        
        mean = np.array([103.53, 116.28, 123.675], dtype=np.float32)
        std = np.array([57.375, 57.12, 58.395], dtype=np.float32)
        input_image = (resized - mean) / std
        input_image = input_image.transpose(2, 0, 1)
        input_tensor = input_image[np.newaxis, :, :, :].astype(np.float32)
        
        return input_tensor, image_width, image_height
    
    def detect_lines(self, img: np.ndarray, conf_threshold: float = 0.3) -> List[Dict]:
        if not self.model_manager.is_detector_loaded():
            if not self.model_manager.load_detector():
                return []
        
        input_tensor, img_w, img_h = self.preprocess_for_detection(img)
        
        input_name = self.model_manager.detector.get_inputs()[0].name
        output_names = [o.name for o in self.model_manager.detector.get_outputs()]
        
        outputs = self.model_manager.detector.run(output_names, {input_name: input_tensor})
        
        bboxes, class_ids = outputs
        predictions = np.squeeze(bboxes)
        
        if len(predictions.shape) == 1:
            predictions = predictions.reshape(1, -1)
        
        scores = predictions[:, 4]
        
        predictions = predictions[scores > conf_threshold, :]
        scores = scores[scores > conf_threshold]
        
        if len(predictions) == 0:
            return []
        
        boxes = predictions[:, :4]
        input_size = self.model_manager._detector_input_size
        boxes /= input_size
        boxes *= np.array([img_w, img_h, img_w, img_h])
        
        detections = []
        for bbox, score in zip(boxes, scores):
            x1, y1, x2, y2 = bbox.astype(np.int32)
            delta_h = (y2 - y1) * 0.02
            y1 = max(0, int(y1 - delta_h))
            y2 = int(y2 + delta_h)
            
            detections.append({
                'box': [x1, y1, x2, y2],
                'confidence': float(score),
                'class_name': 'line_main'
            })
        
        return detections
    
    def preprocess_for_recognition(self, img: np.ndarray) -> np.ndarray:
        pil_image = Image.fromarray(img)
        
        if pil_image.height > pil_image.width:
            pil_image = pil_image.transpose(Image.ROTATE_90)
        
        target_w, target_h = self.model_manager._recognizer_input_size
        pil_resized = pil_image.resize((target_w, target_h))
        resized = np.array(pil_resized)
        resized = resized[:, :, ::-1]
        
        input_image = resized / 255.0
        input_image = 2.0 * (input_image - 0.5)
        input_image = input_image.transpose(2, 0, 1)
        input_tensor = input_image[np.newaxis, :, :, :].astype(np.float32)
        
        return input_tensor
    
    def recognize_text(self, img: np.ndarray) -> str:
        if not self.model_manager.is_recognizer_loaded():
            if not self.model_manager.load_recognizer():
                return ""
        
        if img is None or img.size == 0:
            return ""
        
        input_tensor = self.preprocess_for_recognition(img)
        
        input_name = self.model_manager.recognizer.get_inputs()[0].name
        outputs = self.model_manager.recognizer.run(None, {input_name: input_tensor})[0]
        
        result = ""
        for idx in np.argmax(outputs, axis=2)[0]:
            if idx == 0:
                break
            if idx - 1 < len(self.model_manager.charlist):
                result += self.model_manager.charlist[idx - 1]
        
        return result
    
    def classify_content(self, text: str, box: List[int], img: np.ndarray) -> str:
        if not text:
            return ContentType.UNKNOWN.value
        
        for pattern in self.DATE_PATTERNS[:3]:
            if re.search(pattern, text):
                return ContentType.PRINTED_DATE.value
        
        if re.search(self.DATE_PATTERNS[3], text):
            x1, y1, x2, y2 = box
            region_height = y2 - y1
            region_width = x2 - x1
            
            if region_height > region_width * 2:
                return ContentType.PRINTED_DATE.value
        
        for keyword in self.WEATHER_KEYWORDS:
            if keyword in text and len(text) < 10:
                return ContentType.PRINTED_WEATHER.value
        
        for indicator in self.QUOTE_INDICATORS:
            if indicator in text:
                return ContentType.PRINTED_QUOTE.value
        
        return ContentType.HANDWRITTEN.value
    
    def parse_date_from_text(self, text: str, era_context: str = "明治") -> Optional[DateInfo]:
        normalized = text.replace('\n', '').replace(' ', '')
        
        era_match = re.search(r'(明治|大正|昭和)([一二三四五六七八九十]+)年', normalized)
        if era_match:
            era = era_match.group(1)
            era_year = KanjiNumberConverter.to_number(era_match.group(2))
            search_start = era_match.end()
        else:
            era = era_context
            era_year = 36
            search_start = 0
        
        remaining_text = normalized[search_start:]
        
        date_match = re.search(r'([一二三四五六七八九十]+)月([一二三四五六七八九十]+)日', remaining_text)
        if date_match:
            month = KanjiNumberConverter.to_number(date_match.group(1))
            day = KanjiNumberConverter.to_number(date_match.group(2))
            
            if 1 <= month <= 12 and 1 <= day <= 31:
                era_to_year = {'明治': 1868, '大正': 1912, '昭和': 1926}
                year = era_to_year.get(era, 1868) + era_year - 1
                
                return DateInfo(
                    era=era,
                    era_year=era_year,
                    year=year,
                    month=month,
                    day=day,
                    date_key=f"{year}-{month:02d}-{day:02d}",
                    context=text[:100]
                )
        
        return None

class AnnotationExtractor:
    
    @staticmethod
    def extract_dates_from_pdf(pdf_path: str, target_era_year: int = 36) -> Dict[str, DateInfo]:
        logger.info(f"从翻刻版PDF提取明治{target_era_year}年日期...")
        
        doc = fitz.open(pdf_path)
        dates = {}
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            
            normalized = text.replace('\n', '').replace(' ', '')
            
            era_matches = list(re.finditer(r'明治([一二三四五六七八九十]+)年', normalized))
            
            for era_match in era_matches:
                era_year_str = era_match.group(1)
                era_year = KanjiNumberConverter.to_number(era_year_str)
                
                if era_year != target_era_year:
                    continue
                
                year = 1868 + era_year - 1
                search_start = era_match.end()
                remaining_text = normalized[search_start:]
                
                for match in re.finditer(r'([一二三四五六七八九十]+)月([一二三四五六七八九十]+)日', remaining_text):
                    month = KanjiNumberConverter.to_number(match.group(1))
                    day = KanjiNumberConverter.to_number(match.group(2))
                    
                    if 1 <= month <= 12 and 1 <= day <= 31:
                        date_key = f"{year}-{month:02d}-{day:02d}"
                        
                        if date_key not in dates:
                            dates[date_key] = DateInfo(
                                era='明治',
                                era_year=era_year,
                                year=year,
                                month=month,
                                day=day,
                                date_key=date_key,
                                source_page=page_num + 1,
                                context=text[:500]
                            )
        
        doc.close()
        logger.info(f"解析到 {len(dates)} 个明治{target_era_year}年日期条目")
        return dates
    
    @staticmethod
    def extract_annotation_text(pdf_path: str, page_num: int, 
                               date_key: str, context_length: int = 200) -> str:
        doc = fitz.open(pdf_path)
        
        if page_num < 1 or page_num > len(doc):
            doc.close()
            return ""
        
        page = doc[page_num - 1]
        text = page.get_text()
        doc.close()
        
        return text[:context_length]

class ClassicalOCRTrainingWorkflow:
    
    def __init__(self, config: Dict[str, str], progress_callback: Optional[Callable] = None):
        self.config = config
        self.progress_callback = progress_callback
        
        self.model_manager = ONNXModelManager(
            rtmdet_path=config.get('rtmdet_model', ''),
            parseq_path=config.get('parseq_model', ''),
            rtmdet_config=config.get('rtmdet_config', ''),
            parseq_config=config.get('parseq_config', '')
        )
        
        self.layout_detector = LayoutDetector(self.model_manager)
        
        self.current_stage = ProcessingStage.INITIALIZED
        self.results: List[ProcessingResult] = []
        
        self._validate_config()
    
    def _validate_config(self) -> bool:
        required_keys = ['rtmdet_model', 'parseq_model', 'rtmdet_config', 'parseq_config']
        missing = [k for k in required_keys if not self.config.get(k)]
        
        if missing:
            logger.warning(f"配置缺少必要参数: {missing}")
            return False
        return True
    
    def _report_progress(self, stage: str, progress: float, message: str):
        if self.progress_callback:
            self.progress_callback(stage, progress, message)
        logger.info(f"[{stage}] {progress*100:.1f}% - {message}")
    
    def _add_result(self, stage: ProcessingStage, success: bool, 
                   message: str, data: Dict = None, errors: List[str] = None):
        result = ProcessingResult(
            stage=stage.value,
            success=success,
            message=message,
            data=data or {},
            errors=errors or []
        )
        self.results.append(result)
        self.current_stage = stage
    
    def process_source_pdf(self, pdf_path: str, output_dir: str,
                          start_page: int = 1, end_page: int = None,
                          target_era_year: int = 36,
                          target_image_size: Tuple[int, int] = (384, 32)) -> ProcessingResult:
        
        logger.info(f"开始处理原始史料PDF: {pdf_path}")
        self._report_progress("初始化", 0.0, "加载PDF文件")
        
        if not os.path.exists(pdf_path):
            return ProcessingResult(
                stage=ProcessingStage.FAILED.value,
                success=False,
                message=f"PDF文件不存在: {pdf_path}",
                errors=["文件路径无效"]
            )
        
        os.makedirs(output_dir, exist_ok=True)
        
        handwritten_dir = os.path.join(output_dir, "handwritten_images")
        analysis_dir = os.path.join(output_dir, "analysis")
        os.makedirs(handwritten_dir, exist_ok=True)
        os.makedirs(analysis_dir, exist_ok=True)
        
        self._add_result(ProcessingStage.PDF_LOADED, True, f"PDF加载成功: {pdf_path}")
        
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        if end_page is None:
            end_page = total_pages
        
        end_page = min(end_page, total_pages)
        pages_to_process = end_page - start_page + 1
        
        all_dates: Dict[str, DateInfo] = {}
        all_regions: Dict[int, List[LayoutRegion]] = {}
        training_samples: List[TrainingSample] = []
        
        self._report_progress("版面分析", 0.0, f"开始处理 {pages_to_process} 页")
        
        for idx, page_num in enumerate(range(start_page - 1, end_page)):
            progress = (idx + 1) / pages_to_process
            self._report_progress("版面分析", progress, f"处理第 {page_num + 1} 页")
            
            page = doc[page_num]
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            np_img = np.array(img)
            
            detections = self.layout_detector.detect_lines(np_img)
            
            page_regions: List[LayoutRegion] = []
            page_dates: List[DateInfo] = []
            
            page_handwritten_dir = os.path.join(handwritten_dir, f"page_{page_num + 1:04d}")
            os.makedirs(page_handwritten_dir, exist_ok=True)
            
            for det_idx, det in enumerate(detections):
                x1, y1, x2, y2 = det['box']
                
                if y2 > np_img.shape[0] or x2 > np_img.shape[1]:
                    continue
                if y1 < 0 or x1 < 0:
                    continue
                
                line_img = np_img[y1:y2, x1:x2]
                
                if line_img.size == 0:
                    continue
                
                ocr_text = self.layout_detector.recognize_text(line_img)
                
                content_type = self.layout_detector.classify_content(ocr_text, det['box'], line_img)
                
                region = LayoutRegion(
                    box=det['box'],
                    content_type=content_type,
                    confidence=det['confidence'],
                    text=ocr_text,
                    ocr_text=ocr_text,
                    is_vertical=(y2 - y1) > (x2 - x1)
                )
                
                page_regions.append(region)
                
                if content_type == ContentType.PRINTED_DATE.value:
                    date_info = self.layout_detector.parse_date_from_text(ocr_text)
                    if date_info:
                        date_info.source_page = page_num + 1
                        date_info.line_index = det_idx
                        date_info.ocr_text = ocr_text
                        page_dates.append(date_info)
                        
                        if date_info.date_key not in all_dates:
                            all_dates[date_info.date_key] = date_info
                
                if content_type == ContentType.HANDWRITTEN.value:
                    pil_img = Image.fromarray(line_img)
                    
                    if pil_img.height > pil_img.width:
                        pil_img = pil_img.transpose(Image.ROTATE_90)
                    
                    pil_img = pil_img.resize(target_image_size, Image.LANCZOS)
                    
                    img_path = os.path.join(page_handwritten_dir, f"line_{det_idx:04d}.png")
                    pil_img.save(img_path)
                    
                    region.image_path = img_path
                    
                    sample = TrainingSample(
                        image_path=img_path,
                        annotation_text=ocr_text,
                        source_page=page_num + 1,
                        box=det['box'],
                        confidence=det['confidence'],
                        content_type=content_type
                    )
                    training_samples.append(sample)
            
            all_regions[page_num + 1] = page_regions
            
            page_analysis = {
                "page_number": page_num + 1,
                "total_regions": len(page_regions),
                "dates": [asdict(d) for d in page_dates],
                "handwritten_count": sum(1 for r in page_regions if r.content_type == ContentType.HANDWRITTEN.value)
            }
            
            analysis_path = os.path.join(analysis_dir, f"page_{page_num + 1:04d}.json")
            with open(analysis_path, 'w', encoding='utf-8') as f:
                json.dump(convert_to_serializable(page_analysis), f, ensure_ascii=False, indent=2)
        
        doc.close()
        
        self._add_result(ProcessingStage.LAYOUT_ANALYZED, True, 
                        f"版面分析完成，共 {len(all_regions)} 页")
        self._add_result(ProcessingStage.DATES_EXTRACTED, True,
                        f"日期提取完成，共 {len(all_dates)} 个日期")
        self._add_result(ProcessingStage.IMAGES_EXTRACTED, True,
                        f"图像提取完成，共 {len(training_samples)} 个样本")
        
        training_data_path = os.path.join(output_dir, "training_samples.json")
        training_data = [asdict(s) for s in training_samples]
        with open(training_data_path, 'w', encoding='utf-8') as f:
            json.dump(convert_to_serializable(training_data), f, ensure_ascii=False, indent=2)
        
        self._add_result(ProcessingStage.TRAINING_DATA_GENERATED, True,
                        f"训练数据已保存: {training_data_path}")
        
        summary = {
            "pdf_path": pdf_path,
            "pages_processed": len(all_regions),
            "total_dates": len(all_dates),
            "total_training_samples": len(training_samples),
            "dates": {k: asdict(v) for k, v in all_dates.items()},
            "output_dir": output_dir
        }
        
        summary_path = os.path.join(output_dir, "workflow_summary.json")
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(convert_to_serializable(summary), f, ensure_ascii=False, indent=2)
        
        self._add_result(ProcessingStage.COMPLETED, True, "工作流完成")
        
        return ProcessingResult(
            stage=ProcessingStage.COMPLETED.value,
            success=True,
            message="原始史料PDF处理完成",
            data=summary
        )
    
    def match_with_annotation(self, source_dates: Dict[str, DateInfo],
                             annotation_pdf_path: str,
                             target_era_year: int = 36) -> ProcessingResult:
        
        logger.info("开始日期匹配...")
        self._report_progress("日期匹配", 0.0, "提取翻刻版日期")
        
        annotation_dates = AnnotationExtractor.extract_dates_from_pdf(
            annotation_pdf_path, target_era_year
        )
        
        matched_pairs = []
        
        for date_key, source_info in source_dates.items():
            if date_key in annotation_dates:
                annotation_info = annotation_dates[date_key]
                matched_pairs.append({
                    'date_key': date_key,
                    'source_page': source_info.source_page,
                    'annotation_page': annotation_info.source_page,
                    'source_ocr_text': source_info.ocr_text,
                    'annotation_context': annotation_info.context[:100]
                })
        
        self._add_result(ProcessingStage.ANNOTATIONS_MATCHED, True,
                        f"匹配完成，共 {len(matched_pairs)} 对")
        
        return ProcessingResult(
            stage=ProcessingStage.ANNOTATIONS_MATCHED.value,
            success=True,
            message=f"日期匹配完成，共 {len(matched_pairs)} 对",
            data={
                "matched_pairs": matched_pairs,
                "source_dates_count": len(source_dates),
                "annotation_dates_count": len(annotation_dates)
            }
        )
    
    def run_full_workflow(self, source_pdf: str, annotation_pdf: str,
                         output_dir: str, start_page: int = 1, 
                         end_page: int = None, target_era_year: int = 36) -> Dict:
        
        logger.info("="*60)
        logger.info("开始完整工作流")
        logger.info("="*60)
        
        workflow_start = datetime.now()
        
        source_result = self.process_source_pdf(
            source_pdf, output_dir, start_page, end_page, target_era_year
        )
        
        if not source_result.success:
            return {
                "success": False,
                "error": source_result.message,
                "results": [asdict(r) for r in self.results]
            }
        
        source_dates = source_result.data.get("dates", {})
        
        match_result = self.match_with_annotation(
            source_dates, annotation_pdf, target_era_year
        )
        
        workflow_end = datetime.now()
        
        final_result = {
            "success": True,
            "workflow_start": workflow_start.isoformat(),
            "workflow_end": workflow_end.isoformat(),
            "duration_seconds": (workflow_end - workflow_start).total_seconds(),
            "source_result": asdict(source_result),
            "match_result": asdict(match_result),
            "results": [asdict(r) for r in self.results],
            "output_dir": output_dir
        }
        
        final_path = os.path.join(output_dir, "final_workflow_result.json")
        with open(final_path, 'w', encoding='utf-8') as f:
            json.dump(convert_to_serializable(final_result), f, ensure_ascii=False, indent=2)
        
        logger.info("="*60)
        logger.info("工作流完成")
        logger.info(f"处理时间: {(workflow_end - workflow_start).total_seconds():.2f} 秒")
        logger.info("="*60)
        
        return final_result

def create_default_config(base_dir: str = None) -> Dict[str, str]:
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    return {
        'rtmdet_model': os.path.join(base_dir, 'external', 'ndlkotenocr-lite', 'src', 'model', 'rtmdet-s-1280x1280.onnx'),
        'parseq_model': os.path.join(base_dir, 'external', 'ndlkotenocr-lite', 'src', 'model', 'parseq-ndl-32x384-tiny-10.onnx'),
        'rtmdet_config': os.path.join(base_dir, 'external', 'ndlkotenocr-lite', 'src', 'config', 'ndl.yaml'),
        'parseq_config': os.path.join(base_dir, 'external', 'ndlkotenocr-lite', 'src', 'config', 'NDLmoji.yaml')
    }

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="古典籍OCR训练数据准备工作流")
    parser.add_argument('--source-pdf', type=str, required=True, help='原始史料PDF路径')
    parser.add_argument('--annotation-pdf', type=str, required=True, help='翻刻版PDF路径')
    parser.add_argument('--output', type=str, required=True, help='输出目录')
    parser.add_argument('--start-page', type=int, default=1, help='起始页码')
    parser.add_argument('--end-page', type=int, default=None, help='结束页码')
    parser.add_argument('--era-year', type=int, default=36, help='目标明治年份')
    
    args = parser.parse_args()
    
    config = create_default_config()
    
    workflow = ClassicalOCRTrainingWorkflow(config)
    
    result = workflow.run_full_workflow(
        source_pdf=args.source_pdf,
        annotation_pdf=args.annotation_pdf,
        output_dir=args.output,
        start_page=args.start_page,
        end_page=args.end_page,
        target_era_year=args.era_year
    )
    
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
