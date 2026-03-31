# -*- coding: utf-8 -*-
"""
通用板式分析模块
支持多种文档类型的板式分析需求
可扩展的模块化设计
"""

import os
import sys
import json
import re
import fitz
import numpy as np
from PIL import Image
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional, Union, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from abc import ABC, abstractmethod
import logging

sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DocumentType(Enum):
    CLASSICAL_DIARY = "classical_diary"
    NEWSPAPER = "newspaper"
    BOOK = "book"
    MANUSCRIPT = "manuscript"
    OFFICIAL_DOCUMENT = "official_document"
    LETTER = "letter"
    UNKNOWN = "unknown"

class RegionType(Enum):
    TITLE = "title"
    BODY_TEXT = "body_text"
    HEADER = "header"
    FOOTER = "footer"
    MARGINALIA = "marginalia"
    DATE = "date"
    SIGNATURE = "signature"
    TABLE = "table"
    FIGURE = "figure"
    HANDWRITTEN = "handwritten"
    PRINTED = "printed"
    UNKNOWN = "unknown"

class TextOrientation(Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    MIXED = "mixed"

@dataclass
class LayoutRegion:
    box: List[int]
    region_type: str
    confidence: float
    text: str = ""
    orientation: str = "vertical"
    language: str = "ja"
    metadata: Dict = field(default_factory=dict)
    children: List['LayoutRegion'] = field(default_factory=list)

@dataclass
class PageLayout:
    page_number: int
    width: int
    height: int
    orientation: str
    regions: List[LayoutRegion]
    metadata: Dict = field(default_factory=dict)

@dataclass
class DocumentLayout:
    document_type: str
    pages: List[PageLayout]
    metadata: Dict = field(default_factory=dict)

class LayoutAnalyzerBase(ABC):
    
    @abstractmethod
    def analyze(self, image: np.ndarray) -> List[LayoutRegion]:
        pass
    
    @abstractmethod
    def get_supported_types(self) -> List[str]:
        pass

class ONNXLayoutAnalyzer(LayoutAnalyzerBase):
    
    def __init__(self, model_path: str, config_path: str, 
                 input_size: int = 1024, conf_threshold: float = 0.3):
        self.model_path = model_path
        self.config_path = config_path
        self.input_size = input_size
        self.conf_threshold = conf_threshold
        
        self.session = None
        self.classes = None
        self.input_name = None
        self.output_names = None
    
    def load_model(self) -> bool:
        try:
            import onnxruntime
            import yaml
            
            opt_session = onnxruntime.SessionOptions()
            opt_session.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_DISABLE_ALL
            
            self.session = onnxruntime.InferenceSession(
                self.model_path,
                providers=['CPUExecutionProvider']
            )
            
            self.input_name = self.session.get_inputs()[0].name
            self.output_names = [o.name for o in self.session.get_outputs()]
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.classes = config.get('names', {0: 'line_main'})
            
            logger.info(f"模型加载成功: {self.model_path}")
            return True
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            return False
    
    def preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, int, int]:
        max_wh = max(image.shape[0], image.shape[1])
        padded = np.zeros((max_wh, max_wh, 3), dtype=np.uint8)
        padded[:image.shape[0], :image.shape[1], :] = image.copy()
        
        pil_image = Image.fromarray(padded)
        orig_w, orig_h = pil_image.size
        
        pil_resized = pil_image.resize((self.input_size, self.input_size))
        resized = np.array(pil_resized)[:, :, ::-1]
        
        mean = np.array([103.53, 116.28, 123.675], dtype=np.float32)
        std = np.array([57.375, 57.12, 58.395], dtype=np.float32)
        normalized = (resized - mean) / std
        normalized = normalized.transpose(2, 0, 1)
        tensor = normalized[np.newaxis, :, :, :].astype(np.float32)
        
        return tensor, orig_w, orig_h
    
    def postprocess(self, outputs: Tuple, orig_w: int, orig_h: int) -> List[Dict]:
        bboxes, class_ids = outputs
        predictions = np.squeeze(bboxes)
        
        if len(predictions.shape) == 1:
            predictions = predictions.reshape(1, -1)
        
        scores = predictions[:, 4]
        mask = scores > self.conf_threshold
        predictions = predictions[mask]
        scores = scores[mask]
        
        if len(predictions) == 0:
            return []
        
        boxes = predictions[:, :4] / self.input_size
        boxes *= np.array([orig_w, orig_h, orig_w, orig_h])
        
        results = []
        for bbox, score in zip(boxes, scores):
            x1, y1, x2, y2 = bbox.astype(np.int32)
            delta = (y2 - y1) * 0.02
            results.append({
                'box': [max(0, int(x1)), max(0, int(y1 - delta)), int(x2), int(y2 + delta)],
                'confidence': float(score),
                'class_name': 'line_main'
            })
        
        return results
    
    def analyze(self, image: np.ndarray) -> List[LayoutRegion]:
        if self.session is None:
            if not self.load_model():
                return []
        
        tensor, orig_w, orig_h = self.preprocess(image)
        outputs = self.session.run(self.output_names, {self.input_name: tensor})
        detections = self.postprocess(outputs, orig_w, orig_h)
        
        regions = []
        for det in detections:
            x1, y1, x2, y2 = det['box']
            
            if y2 > image.shape[0] or x2 > image.shape[1]:
                continue
            
            line_img = image[y1:y2, x1:x2]
            orientation = "vertical" if (y2 - y1) > (x2 - x1) else "horizontal"
            
            region = LayoutRegion(
                box=det['box'],
                region_type=RegionType.UNKNOWN.value,
                confidence=det['confidence'],
                orientation=orientation
            )
            regions.append(region)
        
        return regions
    
    def get_supported_types(self) -> List[str]:
        return ['line_main']

class RegionClassifier:
    
    DATE_PATTERNS = [
        r'明治[一二三四五六七八九十]+年[一二三四五六七八九十]+月[一二三四五六七八九十]+日',
        r'大正[一二三四五六七八九十]+年[一二三四五六七八九十]+月[一二三四五六七八九十]+日',
        r'昭和[一二三四五六七八九十]+年[一二三四五六七八九十]+月[一二三四五六七八九十]+日',
        r'平成[一二三四五六七八九十]+年[一二三四五六七八九十]+月[一二三四五六七八九十]+日',
        r'\d{4}年\d{1,2}月\d{1,2}日',
        r'[一二三四五六七八九十]+月[一二三四五六七八九十]+日',
    ]
    
    TITLE_INDICATORS = ['目次', '目録', '序', '跋', '章', '編', '巻']
    HEADER_INDICATORS = ['頁', 'ページ', 'page']
    FOOTER_INDICATORS = ['注', '※', '＊']
    
    @classmethod
    def classify(cls, text: str, box: List[int], page_height: int, 
                page_width: int) -> str:
        if not text:
            return RegionType.UNKNOWN.value
        
        x1, y1, x2, y2 = box
        region_height = y2 - y1
        region_width = x2 - x1
        
        if y1 < page_height * 0.1:
            if len(text) < 50:
                return RegionType.HEADER.value
        
        if y2 > page_height * 0.9:
            if len(text) < 50:
                return RegionType.FOOTER.value
        
        for pattern in cls.DATE_PATTERNS:
            if re.search(pattern, text):
                return RegionType.DATE.value
        
        for indicator in cls.TITLE_INDICATORS:
            if indicator in text and len(text) < 30:
                return RegionType.TITLE.value
        
        if region_height > region_width * 2:
            return RegionType.BODY_TEXT.value
        elif region_width > region_height * 2:
            return RegionType.BODY_TEXT.value
        
        return RegionType.BODY_TEXT.value
    
    @classmethod
    def classify_content_type(cls, text: str) -> str:
        if not text:
            return RegionType.UNKNOWN.value
        
        date_patterns = [
            r'明治[一二三四五六七八九十]+年',
            r'大正[一二三四五六七八九十]+年',
            r'昭和[一二三四五六七八九十]+年',
            r'[一二三四五六七八九十]+月[一二三四五六七八九十]+日'
        ]
        
        for pattern in date_patterns:
            if re.search(pattern, text):
                return RegionType.DATE.value
        
        weather_keywords = ['晴', '曇', '雨', '雪', '風']
        for kw in weather_keywords:
            if kw in text and len(text) < 10:
                return "weather"
        
        quote_indicators = ['「', '」', '『', '』']
        for ind in quote_indicators:
            if ind in text:
                return "quote"
        
        return RegionType.HANDWRITTEN.value

class TextRecognizer:
    
    def __init__(self, model_path: str, config_path: str,
                 input_size: Tuple[int, int] = (384, 32)):
        self.model_path = model_path
        self.config_path = config_path
        self.input_size = input_size
        
        self.session = None
        self.charlist = None
    
    def load_model(self) -> bool:
        try:
            import onnxruntime
            import yaml
            
            opt_session = onnxruntime.SessionOptions()
            self.session = onnxruntime.InferenceSession(
                self.model_path,
                providers=['CPUExecutionProvider']
            )
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.charlist = list(config.get('model', {}).get('charset_train', []))
            
            logger.info(f"识别模型加载成功: {self.model_path}")
            return True
        except Exception as e:
            logger.error(f"识别模型加载失败: {e}")
            return False
    
    def preprocess(self, image: np.ndarray) -> np.ndarray:
        pil_image = Image.fromarray(image)
        
        if pil_image.height > pil_image.width:
            pil_image = pil_image.transpose(Image.ROTATE_90)
        
        pil_resized = pil_image.resize(self.input_size)
        resized = np.array(pil_resized)[:, :, ::-1]
        
        normalized = resized / 255.0
        normalized = 2.0 * (normalized - 0.5)
        normalized = normalized.transpose(2, 0, 1)
        tensor = normalized[np.newaxis, :, :, :].astype(np.float32)
        
        return tensor
    
    def recognize(self, image: np.ndarray) -> str:
        if self.session is None:
            if not self.load_model():
                return ""
        
        if image is None or image.size == 0:
            return ""
        
        tensor = self.preprocess(image)
        input_name = self.session.get_inputs()[0].name
        outputs = self.session.run(None, {input_name: tensor})[0]
        
        result = ""
        for idx in np.argmax(outputs, axis=2)[0]:
            if idx == 0:
                break
            if idx - 1 < len(self.charlist):
                result += self.charlist[idx - 1]
        
        return result

class DocumentTypeDetector:
    
    DIARY_INDICATORS = ['日記', '日誌', '記録', '明治', '大正', '昭和']
    NEWSPAPER_INDICATORS = ['新聞', '報知', '朝日', '毎日', '読売', '号']
    OFFICIAL_INDICATORS = ['令', '達', '伺', '届', '報告', '申請']
    LETTER_INDICATORS = ['拝啓', '敬具', '様', '殿', '貴殿']
    
    @classmethod
    def detect(cls, text_samples: List[str]) -> str:
        all_text = ' '.join(text_samples)
        
        diary_score = sum(1 for ind in cls.DIARY_INDICATORS if ind in all_text)
        newspaper_score = sum(1 for ind in cls.NEWSPAPER_INDICATORS if ind in all_text)
        official_score = sum(1 for ind in cls.OFFICIAL_INDICATORS if ind in all_text)
        letter_score = sum(1 for ind in cls.LETTER_INDICATORS if ind in all_text)
        
        scores = {
            DocumentType.CLASSICAL_DIARY.value: diary_score,
            DocumentType.NEWSPAPER.value: newspaper_score,
            DocumentType.OFFICIAL_DOCUMENT.value: official_score,
            DocumentType.LETTER.value: letter_score
        }
        
        max_score = max(scores.values())
        if max_score == 0:
            return DocumentType.UNKNOWN.value
        
        return max(scores, key=scores.get)

class UniversalLayoutAnalyzer:
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        self.layout_analyzer = ONNXLayoutAnalyzer(
            model_path=config.get('rtmdet_model', ''),
            config_path=config.get('rtmdet_config', ''),
            input_size=config.get('detector_input_size', 1024),
            conf_threshold=config.get('conf_threshold', 0.3)
        )
        
        self.text_recognizer = TextRecognizer(
            model_path=config.get('parseq_model', ''),
            config_path=config.get('parseq_config', ''),
            input_size=config.get('recognizer_input_size', (384, 32))
        )
        
        self._models_loaded = False
    
    def load_models(self) -> bool:
        layout_loaded = self.layout_analyzer.load_model()
        text_loaded = self.text_recognizer.load_model()
        self._models_loaded = layout_loaded and text_loaded
        return self._models_loaded
    
    def analyze_page(self, image: np.ndarray, page_num: int = 1) -> PageLayout:
        if not self._models_loaded:
            self.load_models()
        
        height, width = image.shape[:2]
        
        regions = self.layout_analyzer.analyze(image)
        
        for region in regions:
            x1, y1, x2, y2 = region.box
            
            if y2 > height or x2 > width:
                continue
            
            line_img = image[y1:y2, x1:x2]
            if line_img.size == 0:
                continue
            
            text = self.text_recognizer.recognize(line_img)
            region.text = text
            
            region.region_type = RegionClassifier.classify(
                text, region.box, height, width
            )
        
        orientation = self._detect_page_orientation(regions)
        
        return PageLayout(
            page_number=page_num,
            width=width,
            height=height,
            orientation=orientation,
            regions=regions
        )
    
    def _detect_page_orientation(self, regions: List[LayoutRegion]) -> str:
        if not regions:
            return TextOrientation.VERTICAL.value
        
        vertical_count = sum(1 for r in regions if r.orientation == "vertical")
        horizontal_count = len(regions) - vertical_count
        
        if vertical_count > horizontal_count * 2:
            return TextOrientation.VERTICAL.value
        elif horizontal_count > vertical_count * 2:
            return TextOrientation.HORIZONTAL.value
        else:
            return TextOrientation.MIXED.value
    
    def analyze_document(self, pdf_path: str, start_page: int = 1,
                        end_page: int = None) -> DocumentLayout:
        
        logger.info(f"开始分析文档: {pdf_path}")
        
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        if end_page is None:
            end_page = total_pages
        end_page = min(end_page, total_pages)
        
        pages = []
        text_samples = []
        
        for page_num in range(start_page - 1, end_page):
            page = doc[page_num]
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            np_img = np.array(img)
            
            page_layout = self.analyze_page(np_img, page_num + 1)
            pages.append(page_layout)
            
            text_samples.extend([r.text for r in page_layout.regions if r.text])
        
        doc.close()
        
        document_type = DocumentTypeDetector.detect(text_samples)
        
        return DocumentLayout(
            document_type=document_type,
            pages=pages,
            metadata={
                'source_path': pdf_path,
                'total_pages': len(pages),
                'analysis_date': datetime.now().isoformat()
            }
        )
    
    def extract_regions_by_type(self, document: DocumentLayout,
                                region_type: str) -> List[LayoutRegion]:
        results = []
        for page in document.pages:
            for region in page.regions:
                if region.region_type == region_type:
                    results.append(region)
        return results
    
    def export_results(self, document: DocumentLayout, 
                      output_path: str, format: str = 'json') -> str:
        if format == 'json':
            data = {
                'document_type': document.document_type,
                'metadata': document.metadata,
                'pages': [
                    {
                        'page_number': p.page_number,
                        'width': p.width,
                        'height': p.height,
                        'orientation': p.orientation,
                        'regions': [asdict(r) for r in p.regions]
                    }
                    for p in document.pages
                ]
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        
        return output_path

def create_layout_config(base_dir: str = None) -> Dict[str, Any]:
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    return {
        'rtmdet_model': os.path.join(base_dir, 'external', 'ndlkotenocr-lite', 'src', 'model', 'rtmdet-s-1280x1280.onnx'),
        'parseq_model': os.path.join(base_dir, 'external', 'ndlkotenocr-lite', 'src', 'model', 'parseq-ndl-32x384-tiny-10.onnx'),
        'rtmdet_config': os.path.join(base_dir, 'external', 'ndlkotenocr-lite', 'src', 'config', 'ndl.yaml'),
        'parseq_config': os.path.join(base_dir, 'external', 'ndlkotenocr-lite', 'src', 'config', 'NDLmoji.yaml'),
        'detector_input_size': 1024,
        'recognizer_input_size': (384, 32),
        'conf_threshold': 0.3
    }

import io

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="通用板式分析模块")
    parser.add_argument('--pdf', type=str, required=True, help='PDF文件路径')
    parser.add_argument('--output', type=str, required=True, help='输出文件路径')
    parser.add_argument('--start-page', type=int, default=1, help='起始页码')
    parser.add_argument('--end-page', type=int, default=None, help='结束页码')
    parser.add_argument('--format', type=str, default='json', choices=['json'], help='输出格式')
    
    args = parser.parse_args()
    
    config = create_layout_config()
    analyzer = UniversalLayoutAnalyzer(config)
    
    document = analyzer.analyze_document(
        pdf_path=args.pdf,
        start_page=args.start_page,
        end_page=args.end_page
    )
    
    analyzer.export_results(document, args.output, args.format)
    
    print(f"文档类型: {document.document_type}")
    print(f"分析页数: {len(document.pages)}")
    print(f"结果已保存至: {args.output}")

if __name__ == "__main__":
    main()
