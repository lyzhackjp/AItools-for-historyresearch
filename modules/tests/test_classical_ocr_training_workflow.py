# -*- coding: utf-8 -*-
"""
古典籍OCR训练数据准备工作流模块单元测试
"""

import os
import sys
import json
import unittest
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.classical_ocr_training_workflow import (
    ContentType, ProcessingStage, LayoutRegion, DateInfo, TrainingSample,
    ProcessingResult, KanjiNumberConverter, ONNXModelManager, LayoutDetector,
    AnnotationExtractor, ClassicalOCRTrainingWorkflow, create_default_config
)

class TestKanjiNumberConverter(unittest.TestCase):
    
    def test_simple_numbers(self):
        self.assertEqual(KanjiNumberConverter.to_number('一'), 1)
        self.assertEqual(KanjiNumberConverter.to_number('五'), 5)
        self.assertEqual(KanjiNumberConverter.to_number('十'), 10)
    
    def test_compound_numbers(self):
        self.assertEqual(KanjiNumberConverter.to_number('十一'), 11)
        self.assertEqual(KanjiNumberConverter.to_number('二十'), 20)
        self.assertEqual(KanjiNumberConverter.to_number('三十五'), 35)
    
    def test_special_numbers(self):
        self.assertEqual(KanjiNumberConverter.to_number('廿'), 20)
        self.assertEqual(KanjiNumberConverter.to_number('廿五'), 25)
    
    def test_arabic_numbers(self):
        self.assertEqual(KanjiNumberConverter.to_number('1'), 1)
        self.assertEqual(KanjiNumberConverter.to_number('10'), 10)
        self.assertEqual(KanjiNumberConverter.to_number('36'), 36)
    
    def test_invalid_input(self):
        self.assertEqual(KanjiNumberConverter.to_number('invalid'), 0)

class TestContentType(unittest.TestCase):
    
    def test_content_types(self):
        self.assertEqual(ContentType.PRINTED_DATE.value, "printed_date")
        self.assertEqual(ContentType.PRINTED_WEATHER.value, "printed_weather")
        self.assertEqual(ContentType.PRINTED_QUOTE.value, "printed_quote")
        self.assertEqual(ContentType.HANDWRITTEN.value, "handwritten")
        self.assertEqual(ContentType.UNKNOWN.value, "unknown")

class TestProcessingStage(unittest.TestCase):
    
    def test_stages_order(self):
        stages = list(ProcessingStage)
        self.assertEqual(stages[0], ProcessingStage.INITIALIZED)
        self.assertEqual(stages[-1], ProcessingStage.COMPLETED)

class TestDataClasses(unittest.TestCase):
    
    def test_layout_region(self):
        region = LayoutRegion(
            box=[10, 20, 100, 50],
            content_type="handwritten",
            confidence=0.95,
            text="测试文本",
            ocr_text="测试文本"
        )
        self.assertEqual(region.box, [10, 20, 100, 50])
        self.assertEqual(region.content_type, "handwritten")
        self.assertEqual(region.confidence, 0.95)
    
    def test_date_info(self):
        date_info = DateInfo(
            era="明治",
            era_year=36,
            year=1903,
            month=1,
            day=18,
            date_key="1903-01-18"
        )
        self.assertEqual(date_info.era, "明治")
        self.assertEqual(date_info.year, 1903)
        self.assertEqual(date_info.date_key, "1903-01-18")
    
    def test_training_sample(self):
        sample = TrainingSample(
            image_path="/path/to/image.png",
            annotation_text="测试标注",
            source_page=1,
            box=[10, 20, 100, 50],
            confidence=0.9
        )
        self.assertEqual(sample.image_path, "/path/to/image.png")
        self.assertEqual(sample.source_page, 1)
    
    def test_processing_result(self):
        result = ProcessingResult(
            stage="completed",
            success=True,
            message="处理完成"
        )
        self.assertTrue(result.success)
        self.assertEqual(result.stage, "completed")

class TestLayoutDetector(unittest.TestCase):
    
    def setUp(self):
        self.mock_model_manager = Mock(spec=ONNXModelManager)
        self.mock_model_manager._detector_input_size = 1024
        self.mock_model_manager._recognizer_input_size = (384, 32)
        self.mock_model_manager.is_detector_loaded.return_value = True
        self.mock_model_manager.is_recognizer_loaded.return_value = True
        self.mock_model_manager.charlist = list("abcdefghijklmnopqrstuvwxyz")
        
        self.detector = LayoutDetector(self.mock_model_manager)
    
    def test_classify_date_content(self):
        text = "明治三十六年一月十八日"
        box = [10, 20, 50, 200]
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        
        content_type = self.detector.classify_content(text, box, img)
        self.assertEqual(content_type, ContentType.PRINTED_DATE.value)
    
    def test_classify_weather_content(self):
        text = "晴"
        box = [10, 20, 50, 60]
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        
        content_type = self.detector.classify_content(text, box, img)
        self.assertEqual(content_type, ContentType.PRINTED_WEATHER.value)
    
    def test_classify_quote_content(self):
        text = "「これは引用です」"
        box = [10, 20, 100, 50]
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        
        content_type = self.detector.classify_content(text, box, img)
        self.assertEqual(content_type, ContentType.PRINTED_QUOTE.value)
    
    def test_classify_handwritten_content(self):
        text = "これは手書きのテキストです"
        box = [10, 20, 100, 50]
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        
        content_type = self.detector.classify_content(text, box, img)
        self.assertEqual(content_type, ContentType.HANDWRITTEN.value)
    
    def test_classify_empty_text(self):
        text = ""
        box = [10, 20, 100, 50]
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        
        content_type = self.detector.classify_content(text, box, img)
        self.assertEqual(content_type, ContentType.UNKNOWN.value)
    
    def test_parse_date_from_text(self):
        text = "明治三十六年一月十八日"
        date_info = self.detector.parse_date_from_text(text)
        
        self.assertIsNotNone(date_info)
        self.assertEqual(date_info.era, "明治")
        self.assertEqual(date_info.era_year, 36)
        self.assertEqual(date_info.year, 1903)
        self.assertEqual(date_info.month, 1)
        self.assertEqual(date_info.day, 18)
    
    def test_parse_date_without_era(self):
        text = "一月十八日"
        date_info = self.detector.parse_date_from_text(text, era_context="明治")
        
        self.assertIsNotNone(date_info)
        self.assertEqual(date_info.month, 1)
        self.assertEqual(date_info.day, 18)
    
    def test_parse_invalid_date(self):
        text = "これは日付ではありません"
        date_info = self.detector.parse_date_from_text(text)
        
        self.assertIsNone(date_info)

class TestAnnotationExtractor(unittest.TestCase):
    
    @patch('fitz.open')
    def test_extract_dates_from_pdf(self, mock_fitz_open):
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "明治三十六年一月十八日\n明治三十六年一月十九日"
        mock_doc.__iter__ = Mock(return_value=iter([mock_page]))
        mock_doc.__len__ = Mock(return_value=1)
        mock_fitz_open.return_value = mock_doc
        
        dates = AnnotationExtractor.extract_dates_from_pdf("test.pdf", target_era_year=36)
        
        self.assertIsInstance(dates, dict)

class TestClassicalOCRTrainingWorkflow(unittest.TestCase):
    
    def setUp(self):
        self.test_config = {
            'rtmdet_model': 'path/to/rtmdet.onnx',
            'parseq_model': 'path/to/parseq.onnx',
            'rtmdet_config': 'path/to/ndl.yaml',
            'parseq_config': 'path/to/NDLmoji.yaml'
        }
    
    def test_workflow_initialization(self):
        with patch.object(ONNXModelManager, 'load_detector', return_value=True):
            with patch.object(ONNXModelManager, 'load_recognizer', return_value=True):
                workflow = ClassicalOCRTrainingWorkflow(self.test_config)
                
                self.assertEqual(workflow.current_stage, ProcessingStage.INITIALIZED)
                self.assertIsInstance(workflow.results, list)
    
    def test_validate_config(self):
        workflow = ClassicalOCRTrainingWorkflow(self.test_config)
        self.assertTrue(workflow._validate_config())
    
    def test_validate_config_missing_keys(self):
        incomplete_config = {'rtmdet_model': 'path/to/model'}
        workflow = ClassicalOCRTrainingWorkflow(incomplete_config)
        self.assertFalse(workflow._validate_config())
    
    def test_add_result(self):
        workflow = ClassicalOCRTrainingWorkflow(self.test_config)
        
        workflow._add_result(
            ProcessingStage.PDF_LOADED,
            True,
            "PDF加载成功"
        )
        
        self.assertEqual(len(workflow.results), 1)
        self.assertEqual(workflow.current_stage, ProcessingStage.PDF_LOADED)
    
    @patch('os.path.exists')
    def test_process_source_pdf_file_not_found(self, mock_exists):
        mock_exists.return_value = False
        
        workflow = ClassicalOCRTrainingWorkflow(self.test_config)
        result = workflow.process_source_pdf("nonexistent.pdf", "/tmp/output")
        
        self.assertFalse(result.success)
        self.assertEqual(result.stage, ProcessingStage.FAILED.value)

class TestCreateDefaultConfig(unittest.TestCase):
    
    def test_create_default_config(self):
        config = create_default_config("/test/base/dir")
        
        self.assertIn('rtmdet_model', config)
        self.assertIn('parseq_model', config)
        self.assertIn('rtmdet_config', config)
        self.assertIn('parseq_config', config)
        
        self.assertIn('rtmdet-s-1280x1280.onnx', config['rtmdet_model'])
        self.assertIn('parseq-ndl-32x384-tiny-10.onnx', config['parseq_model'])

class TestIntegration(unittest.TestCase):
    
    def test_full_workflow_data_flow(self):
        date_info = DateInfo(
            era="明治",
            era_year=36,
            year=1903,
            month=1,
            day=18,
            date_key="1903-01-18",
            source_page=1,
            ocr_text="明治三十六年一月十八日"
        )
        
        region = LayoutRegion(
            box=[10, 20, 100, 200],
            content_type=ContentType.PRINTED_DATE.value,
            confidence=0.95,
            text=date_info.ocr_text,
            ocr_text=date_info.ocr_text
        )
        
        sample = TrainingSample(
            image_path="/path/to/image.png",
            annotation_text=date_info.ocr_text,
            source_page=date_info.source_page,
            date_key=date_info.date_key,
            box=region.box,
            confidence=region.confidence,
            content_type=region.content_type
        )
        
        self.assertEqual(sample.date_key, date_info.date_key)
        self.assertEqual(sample.source_page, date_info.source_page)
        self.assertEqual(sample.content_type, ContentType.PRINTED_DATE.value)

def run_tests():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestKanjiNumberConverter))
    suite.addTests(loader.loadTestsFromTestCase(TestContentType))
    suite.addTests(loader.loadTestsFromTestCase(TestProcessingStage))
    suite.addTests(loader.loadTestsFromTestCase(TestDataClasses))
    suite.addTests(loader.loadTestsFromTestCase(TestLayoutDetector))
    suite.addTests(loader.loadTestsFromTestCase(TestAnnotationExtractor))
    suite.addTests(loader.loadTestsFromTestCase(TestClassicalOCRTrainingWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestCreateDefaultConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result

if __name__ == "__main__":
    run_tests()
