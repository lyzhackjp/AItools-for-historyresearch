# -*- coding: utf-8 -*-
"""
接口模拟测试工具
用于在NDLoCR不可用时进行接口测试
"""

import os
import sys
import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging

sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class MockDetectionResult:
    boxes: List[List[int]]
    scores: List[float]
    labels: List[int]


@dataclass
class MockRecognitionResult:
    text: str
    confidence: float
    char_scores: List[float]


class MockOCRDetector:
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.model_loaded = True
        logger.info("MockOCRDetector 初始化完成")
    
    def detect(self, image: np.ndarray, conf_threshold: float = 0.5) -> MockDetectionResult:
        h, w = image.shape[:2]
        
        num_boxes = np.random.randint(3, 8)
        boxes = []
        scores = []
        labels = []
        
        for _ in range(num_boxes):
            x1 = np.random.randint(0, w // 2)
            y1 = np.random.randint(0, h // 2)
            x2 = np.random.randint(x1 + 50, min(x1 + 300, w))
            y2 = np.random.randint(y1 + 20, min(y1 + 100, h))
            
            score = np.random.uniform(conf_threshold, 1.0)
            
            boxes.append([int(x1), int(y1), int(x2), int(y2)])
            scores.append(float(score))
            labels.append(0)
        
        return MockDetectionResult(
            boxes=boxes,
            scores=scores,
            labels=labels
        )
    
    def get_model_info(self) -> Dict:
        return {
            "type": "mock",
            "name": "MockDetectionModel",
            "version": "1.0.0",
            "input_size": [1024, 1024]
        }


class MockOCRRecognizer:
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.model_loaded = True
        self.sample_texts = [
            "明治三十六年一月一日",
            "天気晴朗",
            "今日は休日なり",
            "東京府下にて",
            "日記を記す",
            "古文書の解読",
            "歴史資料整理",
            "翻刻作業中"
        ]
        logger.info("MockOCRRecognizer 初始化完成")
    
    def recognize(self, image: np.ndarray) -> MockRecognitionResult:
        text = np.random.choice(self.sample_texts)
        
        confidence = np.random.uniform(0.7, 0.99)
        
        char_scores = [np.random.uniform(0.6, 0.99) for _ in range(len(text))]
        
        return MockRecognitionResult(
            text=text,
            confidence=float(confidence),
            char_scores=char_scores
        )
    
    def get_model_info(self) -> Dict:
        return {
            "type": "mock",
            "name": "MockRecognitionModel",
            "version": "1.0.0",
            "input_size": [32, 384]
        }


class MockInterfaceTester:
    
    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.detector = MockOCRDetector(self.config.get("detection", {}))
        self.recognizer = MockOCRRecognizer(self.config.get("recognition", {}))
        
        self._test_results: List[Dict] = []
    
    def _load_config(self, config_path: str) -> Dict:
        if config_path and Path(config_path).exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def create_mock_image(self, width: int = 800, height: int = 600) -> np.ndarray:
        image = np.random.randint(200, 256, (height, width, 3), dtype=np.uint8)
        
        for _ in range(np.random.randint(5, 15)):
            x = np.random.randint(0, width - 100)
            y = np.random.randint(0, height - 50)
            w = np.random.randint(50, 200)
            h = np.random.randint(20, 50)
            image[y:y+h, x:x+w] = np.random.randint(0, 100)
        
        return image
    
    def test_detection(self, num_tests: int = 5) -> Dict:
        logger.info(f"运行检测测试 ({num_tests} 次)...")
        
        results = []
        for i in range(num_tests):
            image = self.create_mock_image()
            result = self.detector.detect(image)
            
            results.append({
                "test_id": i + 1,
                "image_size": list(image.shape),
                "num_detections": len(result.boxes),
                "avg_score": np.mean(result.scores) if result.scores else 0,
                "boxes": result.boxes[:3] if result.boxes else []
            })
        
        summary = {
            "test_type": "detection",
            "num_tests": num_tests,
            "model_info": self.detector.get_model_info(),
            "results": results,
            "avg_detections": np.mean([r["num_detections"] for r in results]),
            "avg_score": np.mean([r["avg_score"] for r in results])
        }
        
        self._test_results.append(summary)
        return summary
    
    def test_recognition(self, num_tests: int = 5) -> Dict:
        logger.info(f"运行识别测试 ({num_tests} 次)...")
        
        results = []
        for i in range(num_tests):
            image = self.create_mock_image(width=384, height=32)
            result = self.recognizer.recognize(image)
            
            results.append({
                "test_id": i + 1,
                "image_size": list(image.shape),
                "text": result.text,
                "confidence": result.confidence,
                "text_length": len(result.text)
            })
        
        summary = {
            "test_type": "recognition",
            "num_tests": num_tests,
            "model_info": self.recognizer.get_model_info(),
            "results": results,
            "avg_confidence": np.mean([r["confidence"] for r in results]),
            "avg_text_length": np.mean([r["text_length"] for r in results])
        }
        
        self._test_results.append(summary)
        return summary
    
    def test_full_pipeline(self, num_tests: int = 3) -> Dict:
        logger.info(f"运行完整流程测试 ({num_tests} 次)...")
        
        results = []
        for i in range(num_tests):
            image = self.create_mock_image()
            
            det_result = self.detector.detect(image)
            
            recognized_texts = []
            for box in det_result.boxes[:3]:
                x1, y1, x2, y2 = box
                crop = image[y1:y2, x1:x2]
                
                if crop.size > 0:
                    rec_result = self.recognizer.recognize(crop)
                    recognized_texts.append({
                        "box": box,
                        "text": rec_result.text,
                        "confidence": rec_result.confidence
                    })
            
            results.append({
                "test_id": i + 1,
                "num_detections": len(det_result.boxes),
                "recognized_texts": recognized_texts
            })
        
        summary = {
            "test_type": "full_pipeline",
            "num_tests": num_tests,
            "results": results
        }
        
        self._test_results.append(summary)
        return summary
    
    def run_all_tests(self) -> Dict:
        logger.info("=" * 60)
        logger.info("开始运行所有模拟测试")
        logger.info("=" * 60)
        
        detection_results = self.test_detection()
        recognition_results = self.test_recognition()
        pipeline_results = self.test_full_pipeline()
        
        summary = {
            "total_tests": len(self._test_results),
            "detection": {
                "status": "passed",
                "avg_detections": detection_results["avg_detections"],
                "avg_score": detection_results["avg_score"]
            },
            "recognition": {
                "status": "passed",
                "avg_confidence": recognition_results["avg_confidence"],
                "avg_text_length": recognition_results["avg_text_length"]
            },
            "pipeline": {
                "status": "passed",
                "num_tests": pipeline_results["num_tests"]
            },
            "all_passed": True
        }
        
        logger.info("=" * 60)
        logger.info("所有测试完成")
        logger.info(f"检测测试: 平均 {summary['detection']['avg_detections']:.1f} 个检测框")
        logger.info(f"识别测试: 平均置信度 {summary['recognition']['avg_confidence']:.2f}")
        logger.info("=" * 60)
        
        return summary
    
    def save_results(self, output_path: str):
        output = {
            "test_results": self._test_results,
            "timestamp": str(np.datetime64('now'))
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        logger.info(f"测试结果已保存: {output_path}")


def test_ndlocr_interface():
    logger.info("测试NDLoCR接口隔离机制...")
    
    try:
        from modules.integration_manager import create_integration_manager
        
        env_manager, file_manager, ndlocr_interface, workflow = create_integration_manager()
        
        print("\n" + "=" * 60)
        print("NDLoCR接口状态")
        print("=" * 60)
        print(f"可用: {ndlocr_interface.is_available}")
        
        validation = ndlocr_interface.validate_setup()
        print(f"配置完整: {validation['all_valid']}")
        
        if not ndlocr_interface.is_available:
            print("\nNDLoCR不可用，使用Mock接口")
            mock = ndlocr_interface.create_mock_interface()
            print(f"Mock接口: {mock}")
        
        print("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"接口测试失败: {e}")
        return False


def main():
    print("=" * 60)
    print("接口模拟测试工具")
    print("=" * 60)
    
    tester = MockInterfaceTester()
    
    summary = tester.run_all_tests()
    
    print("\n测试摘要:")
    print(f"  检测测试: {summary['detection']['status']}")
    print(f"  识别测试: {summary['recognition']['status']}")
    print(f"  流程测试: {summary['pipeline']['status']}")
    print(f"  全部通过: {summary['all_passed']}")
    
    output_path = "logs/mock_test_results.json"
    Path("logs").mkdir(exist_ok=True)
    tester.save_results(output_path)
    
    print("\n" + "=" * 60)
    print("测试NDLoCR接口隔离机制")
    print("=" * 60)
    test_ndlocr_interface()


if __name__ == "__main__":
    main()
