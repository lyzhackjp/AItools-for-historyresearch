"""
NER模块集成版本

集成ner_processor.py和ner_processor_optimized.py的功能，
提供统一的API接口，同时保持向后兼容。

主要特性：
- 向后兼容：保留原有recognize_historical_entities接口
- 优化功能：集成词典验证、JSON解析增强、去重机制
- 配置驱动：通过use_optimized参数控制是否启用优化
- 性能提升：词典匹配加速、置信度评估

依赖模块：
- llm_client.py
- ner_processor_optimized.py

使用示例：
```python
from modules.ner_processor_integrated import NERProcessor

# 使用优化版本（默认）
processor = NERProcessor(test_mode=True)
entities = processor.recognize_entities("伊藤博文出生于1841年")

# 使用原始版本
processor = NERProcessor(test_mode=True, use_optimized=False)
entities = processor.recognize_historical_entities("伊藤博文出生于1841年")

# 过滤高置信度实体
high_conf = processor.filter_by_confidence(entities, 0.8)
```

作者：AI Assistant
日期：2026-03-29
版本：1.0
"""

import re
import json
import os
from typing import Dict, List, Optional, Any
from pathlib import Path
from collections import defaultdict
from datetime import datetime


class NERProcessor:
    """
    命名实体识别处理器 - 集成优化版本
    
    支持两种工作模式：
    1. 原始模式（use_optimized=False）：使用原有功能
    2. 优化模式（use_optimized=True）：集成词典验证和增强解析
    
    Attributes:
        api_provider: API提供商
        test_mode: 测试模式标志
        use_optimized: 是否使用优化版本
        optimized: 优化版本处理器
    """
    
    ENTITY_CATEGORIES = {
        'person': '历史人物',
        'location': '地理位置',
        'organization': '机构组织',
        'event': '历史事件',
        'date': '历史年代',
        'work': '著作文献',
        'concept': '思想概念',
        'custom': '自定义类型'
    }
    
    JAPAN_HISTORICAL_ENTITIES = {
        'eras': ['明治', '大正', '昭和', '平成', '奈良', '平安', '鎌倉', '室町', '戦国', '江戸'],
        'institutions': ['幕府', '朝廷', '国会', '貴族院', '衆议院', '内務省', '外務省', '大蔵省', '軍部'],
        'political_groups': ['薩摩藩', '長州藩', '土佐藩', '肥前藩', '公家', '武家', '華族', '平民']
    }
    
    def __init__(self, api_provider: str = "qwen", test_mode: bool = True, use_optimized: bool = True):
        """
        初始化NER处理器
        
        Args:
            api_provider: API提供商，可选值：'qwen', 'minimax', 'chatgpt'
            test_mode: 测试模式标志，True时不调用真实API
            use_optimized: 是否使用优化版本，默认True
        """
        self.api_provider = api_provider
        self.test_mode = test_mode
        self.use_optimized = use_optimized
        
        self.provider_mapping = {
            'qwen': 'dashscope',
            'minimax': 'minimax',
            'chatgpt': 'openai',
            'gemini': 'custom'
        }
        
        self.llm_client = None
        self.recognized_entities = []
        self.entity_cache = {}
        
        self._init_optimized()
    
    def _init_optimized(self):
        """初始化优化版本处理器"""
        if self.use_optimized:
            try:
                from modules.ner_processor_optimized import NERProcessorOptimized
                self.optimized = NERProcessorOptimized(
                    api_provider=self.api_provider,
                    test_mode=self.test_mode
                )
                self.historical_dict = self.optimized.historical_dict
            except ImportError:
                print("警告：无法导入优化版本，将使用原始版本")
                self.use_optimized = False
                self.optimized = None
                self.historical_dict = {}
        else:
            self.optimized = None
            self.historical_dict = {}
    
    def _init_llm_client(self):
        """初始化LLM客户端"""
        if self.test_mode:
            return None
            
        if self.llm_client is None:
            provider = self.provider_mapping.get(self.api_provider, 'dashscope')
            config = self._create_provider_config(provider)
            self.llm_client = create_llm_client(config)
    
    def _create_provider_config(self, provider: str) -> Dict[str, Any]:
        """创建provider配置字典"""
        configs = {
            'dashscope': {
                'provider': 'dashscope',
                'model': 'qwen-turbo',
                'api_key': os.getenv('DASHSCOPE_API_KEY'),
                'base_url': 'https://dashscope.aliyuncs.com/api/v1'
            },
            'minimax': {
                'provider': 'minimax',
                'model': 'abab6-chat',
                'api_key': os.getenv('MINIMAX_API_KEY'),
                'base_url': 'https://api.minimax.chat/v1'
            },
            'openai': {
                'provider': 'openai',
                'model': 'gpt-4',
                'api_key': os.getenv('OPENAI_API_KEY'),
                'base_url': None
            }
        }
        
        return configs.get(provider, configs['dashscope'])
    
    def recognize_entities(self, text: str, categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        统一识别接口（推荐使用）
        
        Args:
            text: 待识别的文本
            categories: 要识别的实体类型列表
            
        Returns:
            List[Dict]: 识别出的实体列表，每个元素包含实体、类型、置信度等信息
        """
        if self.use_optimized and self.optimized:
            return self.optimized.recognize_entities_optimized(text, categories)
        else:
            return self._recognize_original(text, categories)
    
    def _recognize_original(self, text: str, categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """原始识别方法"""
        if self.test_mode:
            return self._recognize_mock_entities(text, categories)
        
        self._init_llm_client()
        
        categories = categories or list(self.ENTITY_CATEGORIES.keys())
        categories_text = '\n'.join([f"- {k}: {v}" for k, v in self.ENTITY_CATEGORIES.items()])
        
        prompt = f"""请从以下日文/中文史料中识别并标注命名实体。

【实体类型】
{categories_text}

【特殊提示 - 日本史相关实体】
时代：{', '.join(self.JAPAN_HISTORICAL_ENTITIES['eras'])}
机构：{', '.join(self.JAPAN_HISTORICAL_ENTITIES['institutions'])}
政治集团：{', '.join(self.JAPAN_HISTORICAL_ENTITIES['political_groups'])}

【待处理文本】
{text[:5000]}

请以JSON数组格式输出，每个元素包含：
- "entity": 实体名称
- "category": 实体类型
- "start_pos": 在文本中的起始位置
- "end_pos": 在文本中的结束位置
- "confidence": 识别置信度 (0-1)"""
        
        response = self._call_llm(prompt)
        
        try:
            entities = json.loads(response)
            self.recognized_entities.extend(entities)
            return entities
        except json.JSONDecodeError:
            return self._parse_entities_from_text(response)
    
    def recognize_historical_entities(self, text: str, categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        兼容原有接口
        
        Args:
            text: 待识别的文本
            categories: 要识别的实体类型列表
            
        Returns:
            List[Dict]: 识别出的实体列表
        """
        return self._recognize_original(text, categories)
    
    def _recognize_mock_entities(self, text: str, categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """模拟实体识别（测试模式）"""
        mock_entities = [
            {'entity': '伊藤博文', 'category': 'person', 'confidence': 0.95, 'start_pos': 0, 'end_pos': 4},
            {'entity': '明治維新', 'category': 'event', 'confidence': 0.92, 'start_pos': 10, 'end_pos': 15},
        ]
        
        categories = categories or list(self.ENTITY_CATEGORIES.keys())
        
        filtered = [
            e for e in mock_entities 
            if e['category'] in categories
        ]
        
        return filtered
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM API"""
        try:
            result = self.llm_client._call_llm(prompt)
            return result.get('content', '')
        except Exception as e:
            print(f"LLM调用失败: {e}")
            return ''
    
    def _parse_entities_from_text(self, text: str) -> List[Dict[str, Any]]:
        """从文本中解析实体"""
        entities = []
        entity_patterns = [
            r'([\u4e00-\u9fff]{2,})(氏|人|大臣|藩主|將軍)',
            r'([\u4e00-\u9fff]{2,})(事件|革命|戦争|維新)',
            r'([\u4e00-\u9fff]{2,})(年|時代|世紀)',
        ]
        
        for pattern in entity_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                entities.append({
                    'entity': match.group(0),
                    'category': 'unknown',
                    'confidence': 0.5
                })
        
        return entities
    
    def classify_entities(self, entities: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        按类型分类实体
        
        Args:
            entities: 实体列表
            
        Returns:
            Dict[str, List[Dict]]: 按类型分类的实体字典
        """
        classified = defaultdict(list)
        
        for entity in entities:
            category = entity.get('category', 'unknown')
            classified[category].append(entity)
        
        return dict(classified)
    
    def filter_by_confidence(self, entities: List[Dict[str, Any]], min_confidence: float = 0.7) -> List[Dict[str, Any]]:
        """
        按置信度过滤实体
        
        Args:
            entities: 实体列表
            min_confidence: 最小置信度阈值
            
        Returns:
            List[Dict]: 过滤后的实体列表
        """
        if not entities:
            return []
        
        if 'confidence' in entities[0]:
            return [e for e in entities if e.get('confidence', 0) >= min_confidence]
        
        return entities
    
    def get_statistics(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        获取实体统计信息
        
        Args:
            entities: 实体列表
            
        Returns:
            Dict[str, Any]: 统计信息
        """
        total = len(entities)
        
        category_counts = defaultdict(int)
        for entity in entities:
            category = entity.get('category', 'unknown')
            category_counts[category] += 1
        
        avg_confidence = 0
        if entities and 'confidence' in entities[0]:
            confidences = [e.get('confidence', 0) for e in entities]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        return {
            'total_entities': total,
            'category_distribution': dict(category_counts),
            'average_confidence': avg_confidence,
            'timestamp': datetime.now().isoformat()
        }
    
    def batch_process(self, texts: List[str], categories: Optional[List[str]] = None) -> List[List[Dict[str, Any]]]:
        """
        批量处理多个文本
        
        Args:
            texts: 文本列表
            categories: 实体类型列表
            
        Returns:
            List[List[Dict]]: 每个文本的识别结果
        """
        results = []
        for text in texts:
            entities = self.recognize_entities(text, categories)
            results.append(entities)
        return results


def create_llm_client(config: Dict[str, Any]):
    """创建LLM客户端（兼容函数）"""
    from modules.llm_client import LLMClient
    return LLMClient(config)


if __name__ == '__main__':
    print("NER模块集成版本测试")
    print("=" * 60)
    
    processor = NERProcessor(test_mode=True, use_optimized=True)
    print(f"API Provider: {processor.api_provider}")
    print(f"Test Mode: {processor.test_mode}")
    print(f"Use Optimized: {processor.use_optimized}")
    print(f"Dictionary Loaded: {len(processor.historical_dict) > 0}")
    
    print("\n测试识别功能:")
    text = "伊藤博文出生于1841年，在明治維新时期发挥了重要作用。"
    entities = processor.recognize_entities(text)
    
    print(f"识别到 {len(entities)} 个实体:")
    for entity in entities:
        confidence = entity.get('confidence', 0)
        print(f"  - {entity.get('entity', entity.get('text', ''))} ({entity.get('category', '')}) - 置信度: {confidence:.2f}")
    
    print("\n测试统计功能:")
    stats = processor.get_statistics(entities)
    print(f"总实体数: {stats['total_entities']}")
    print(f"平均置信度: {stats['average_confidence']:.2f}")
    print(f"类型分布: {stats['category_distribution']}")
    
    print("\n测试过滤功能:")
    high_conf = processor.filter_by_confidence(entities, 0.8)
    print(f"高置信度实体 (>=0.8): {len(high_conf)} 个")
