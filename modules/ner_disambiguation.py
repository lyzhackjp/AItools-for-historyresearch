"""
NER同形异义词区分模块

提供日文历史实体中同形异义词的消歧功能。

功能特性：
- 基于上下文的消歧
- 词典匹配消歧
- 规则匹配消歧
- 置信度评估

主要实体类型：
- 江戸（城市/幕府）
- 薩摩（地名/藩名）
- 長州（地名/藩名）
- 会津（地名/藩名）
- 幕府（政府/时代）

使用示例：
```python
from modules.ner_disambiguation import EntityDisambiguator

disambiguator = EntityDisambiguator()
context = "江戸幕府が終焉を迎えた"
result = disambiguator.disambiguate("江戸", context)
print(result)  # {'type': 'organization', 'meaning': '德川幕府'}

作者：AI Assistant
日期：2026-03-29
版本：1.0
"""

import re
from typing import Dict, List, Optional, Any, Tuple


class EntityDisambiguator:
    """
    实体消歧器
    
    基于上下文信息，对同形异义词进行消歧。
    """
    
    AMBIGUOUS_ENTITIES = {
        '江戸': [
            {
                'type': 'location',
                'context_pattern': ['江戸幕府', '江戸城', '将軍駐在大'],
                'meaning': '东京的旧称、德川幕府所在地',
                'examples': ['江戸城', '江戸幕府', '大江戸']
            },
            {
                'type': 'organization',
                'context_pattern': ['幕府', '終焉', '建立'],
                'meaning': '德川幕府的简称',
                'examples': ['幕府終焉', '江戸幕府']
            }
        ],
        '薩摩': [
            {
                'type': 'location',
                'context_pattern': ['鹿兒島', '県', '半島'],
                'meaning': '鹿儿岛县的古称',
                'examples': ['薩摩半島', '薩摩国']
            },
            {
                'type': 'organization',
                'context_pattern': ['藩', '武士', '維新'],
                'meaning': '薩摩藩的简称',
                'examples': ['薩摩藩', '薩摩武士', '薩摩藩閥']
            }
        ],
        '長州': [
            {
                'type': 'location',
                'context_pattern': ['山口県', '県', '沿岸'],
                'meaning': '山口县的古称',
                'examples': ['長州海岸', '周防国']
            },
            {
                'type': 'organization',
                'context_pattern': ['藩', '維新', '戦争'],
                'meaning': '長州藩的简称',
                'examples': ['長州藩', '長州征伐', '薩長同盟']
            }
        ],
        '会津': [
            {
                'type': 'location',
                'context_pattern': ['福島', '県', '鶴ヶ城'],
                'meaning': '会津若松市及其周边地区',
                'examples': ['会津若松', '会津地方']
            },
            {
                'type': 'organization',
                'context_pattern': ['藩', '武士', '戊辰'],
                'meaning': '会津藩的简称',
                'examples': ['会津藩', '会津武士', '会津打仗']
            }
        ],
        '幕府': [
            {
                'type': 'organization',
                'context_pattern': ['建立', '終焉', '德川'],
                'meaning': '武士政权的政府机构',
                'examples': ['幕府建立', '幕府終焉', '德川幕府']
            },
            {
                'type': 'historical_period',
                'context_pattern': ['時代', '中期', '後期'],
                'meaning': '历史时代的统称',
                'examples': ['幕府中期', '鎌倉幕府', '室町幕府']
            }
        ],
        '平安': [
            {
                'type': 'location',
                'context_pattern': ['京', '都'],
                'meaning': '平安京的简称',
                'examples': ['平安京', '都平安']
            },
            {
                'type': 'historical_period',
                'context_pattern': ['時代', '前期', '後期'],
                'meaning': '日本历史时代',
                'examples': ['平安時代', '平安中期']
            }
        ],
        '明治': [
            {
                'type': 'historical_period',
                'context_pattern': ['時代', '維新', '年号'],
                'meaning': '日本年号',
                'examples': ['明治維新', '明治時代', '1868年明治']
            },
            {
                'type': 'location',
                'context_pattern': ['府', '東京'],
                'meaning': '明治天皇的名字',
                'examples': []
            }
        ],
        '天皇': [
            {
                'type': 'person',
                'context_pattern': ['陛下', '勅語', '詔勅'],
                'meaning': '日本皇帝',
                'examples': ['天皇陛下', '天皇の勅語']
            },
            {
                'type': 'concept',
                'context_pattern': ['制度', '制', '統治'],
                'meaning': '天皇制度',
                'examples': ['天皇制', '天皇政治']
            }
        ]
    }
    
    CONTEXT_KEYWORDS = {
        'organization': ['藩', '幕府', '政府', '省', '院', '会', '党'],
        'location': ['県', '府', '市', '町', '村', '国', '半島', '沿岸'],
        'person': ['氏', '人', '大臣', '藩主', '将軍', '公家'],
        'event': ['事件', '戦争', '維新', '革命', '運動'],
        'historical_period': ['時代', '前期', '中期', '後期']
    }
    
    def __init__(self):
        """初始化消歧器"""
        pass
    
    def disambiguate(self, entity: str, context: str) -> Dict[str, Any]:
        """
        对实体进行消歧
        
        Args:
            entity: 待消歧的实体
            context: 上下文文本
            
        Returns:
            Dict[str, Any]: 消歧结果
        """
        if entity not in self.AMBIGUOUS_ENTITIES:
            return {
                'entity': entity,
                'type': 'unknown',
                'meaning': '未识别的同形异义词',
                'confidence': 0.0
            }
        
        candidates = self.AMBIGUOUS_ENTITIES[entity]
        
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            score = self._calculate_match_score(entity, context, candidate)
            
            if score > best_score:
                best_score = score
                best_match = candidate
        
        if best_match and best_score > 0:
            return {
                'entity': entity,
                'type': best_match['type'],
                'meaning': best_match['meaning'],
                'confidence': best_score
            }
        
        return self._default_disambiguation(entity, context)
    
    def _calculate_match_score(self, entity: str, context: str, candidate: Dict[str, Any]) -> float:
        """计算匹配分数"""
        score = 0.0
        patterns = candidate.get('context_pattern', [])
        examples = candidate.get('examples', [])
        
        for pattern in patterns:
            if pattern in context:
                score += 0.3
        
        for example in examples:
            if example in context:
                score += 0.2
        
        type_keywords = self.CONTEXT_KEYWORDS.get(candidate['type'], [])
        for keyword in type_keywords:
            if keyword in context:
                score += 0.1
        
        return min(score, 1.0)
    
    def _default_disambiguation(self, entity: str, context: str) -> Dict[str, Any]:
        """默认消歧策略"""
        type_scores = {}
        
        for entity_type, keywords in self.CONTEXT_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in context)
            if score > 0:
                type_scores[entity_type] = score
        
        if not type_scores:
            return {
                'entity': entity,
                'type': 'unknown',
                'meaning': '无法消歧',
                'confidence': 0.0
            }
        
        best_type = max(type_scores.items(), key=lambda x: x[1])[0]
        
        return {
            'entity': entity,
            'type': best_type,
            'meaning': '基于上下文推断',
            'confidence': 0.5
        }
    
    def batch_disambiguate(self, entities: List[Dict[str, Any]], context: str) -> List[Dict[str, Any]]:
        """
        批量消歧
        
        Args:
            entities: 实体列表
            context: 上下文文本
            
        Returns:
            List[Dict[str, Any]]: 消歧后的实体列表
        """
        disambiguated = []
        
        for entity in entities:
            entity_text = entity.get('text', entity.get('entity', ''))
            
            if entity_text in self.AMBIGUOUS_ENTITIES:
                result = self.disambiguate(entity_text, context)
                entity.update(result)
            
            disambiguated.append(entity)
        
        return disambiguated


class EntityRelationResolver:
    """实体关系解析器"""
    
    RELATION_PATTERNS = {
        'located_in': ['にある', '位于', '在'],
        'participated_in': ['に参加', '参与', '参加'],
        'founded': ['を創設', '创建', '创立'],
        'ruled_by': ['に支配', '统治', '管辖']
    }
    
    def __init__(self):
        """初始化关系解析器"""
        pass
    
    def resolve_relations(self, text: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        解析实体间关系
        
        Args:
            text: 文本内容
            entities: 实体列表
            
        Returns:
            List[Dict[str, Any]]: 关系列表
        """
        relations = []
        
        for relation_type, patterns in self.RELATION_PATTERNS.items():
            for pattern in patterns:
                if pattern in text:
                    relations.append({
                        'type': relation_type,
                        'pattern': pattern,
                        'context': text
                    })
        
        return relations


if __name__ == '__main__':
    print("同形异义词消歧测试")
    print("=" * 60)
    
    disambiguator = EntityDisambiguator()
    
    test_cases = [
        ("江戸", "江戸幕府が終焉を迎えた"),
        ("江戸", "江戸の町並みが発達した"),
        ("薩摩", "薩摩藩武士が維新に参加した"),
        ("薩摩", "薩摩半島の風景が美しい"),
        ("長州", "長州藩が中心となった"),
        ("長州", "山口県長州地方"),
        ("天皇", "天皇陛下が勅語を発した"),
        ("天皇", "天皇制の歴史")
    ]
    
    print("\n消歧测试:")
    for entity, context in test_cases:
        result = disambiguator.disambiguate(entity, context)
        print(f"\n实体: {entity}")
        print(f"上下文: {context}")
        print(f"消歧结果: {result['type']} - {result['meaning']} (置信度: {result['confidence']:.2f})")
    
    print("\n批量消歧测试:")
    entities = [
        {'text': '江戸', 'category': 'unknown'},
        {'text': '薩摩', 'category': 'unknown'},
        {'text': '長州', 'category': 'unknown'}
    ]
    context = "江戸幕府と薩摩藩、長州藩が対立した"
    
    results = disambiguator.batch_disambiguate(entities, context)
    print(f"上下文: {context}")
    for result in results:
        print(f"  - {result['text']}: {result['type']} (置信度: {result['confidence']:.2f})")
    
    print("\n测试完成！")
