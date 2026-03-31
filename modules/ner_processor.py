"""
命名实体识别模块

从日文史料中识别和分类历史专有名词
支持多种实体类型和批量处理

核心功能：
- 识别历史专有名词
- 按类型分类实体（人名、地名、机构、年代等）
- 提取实体间的关联关系
- 批量处理文献进行NER标注
- 支持日文、简体中文、繁体中文

实体分类：
- 历史人物
- 幕府机构
- 地理位置
- 历史年代
- 重要事件

API优先级：
1. 阿里通义千问 (dashscope)
2. MiniMax
3. Gemini/ChatGPT（备选）

测试模式：使用模拟数据，不调用真实API

依赖模块：
- llm_client.py
- ocr_processor.py
"""

import re
import json
import os
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from collections import defaultdict
from datetime import datetime


class NERProcessor:
    """命名实体识别处理器"""
    
    ENTITY_CATEGORIES = {
        'person': '历史人物 (Historical Figure)',
        'location': '地理位置 (Location)',
        'organization': '机构组织 (Organization)',
        'event': '历史事件 (Event)',
        'date': '历史年代 (Date/Period)',
        'work': '著作文献 (Work/Literature)',
        'concept': '思想概念 (Concept/Idea)',
        'custom': '自定义类型 (Custom)'
    }
    
    JAPAN_HISTORICAL_ENTITIES = {
        'eras': ['明治', '大正', '昭和', '平成', '奈良', '平安', '鎌倉', '室町', '戦国', '江戸'],
        'institutions': ['幕府', '朝廷', '国会', '貴族院', '衆议院', '内務省', '外務省', '大蔵省', '軍部'],
        'political_groups': ['薩摩藩', '長州藩', '土佐藩', '肥前藩', '公家', '武家', '華族', '平民']
    }
    
    def __init__(self, api_provider: str = "qwen", test_mode: bool = True):
        """
        初始化NER处理器
        
        Args:
            api_provider: API提供商
            test_mode: 测试模式标志
        """
        self.api_provider = api_provider
        self.test_mode = test_mode
        self.llm_client = None
        
        self.provider_mapping = {
            'qwen': 'dashscope',
            'minimax': 'minimax',
            'gemini': 'custom',
            'chatgpt': 'openai'
        }
        
        self.recognized_entities = []
        self.entity_cache = {}
    
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
    
    def recognize_historical_entities(self, text: str,
                                    categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        识别历史专有名词
        
        Args:
            text: 待识别的文本
            categories: 要识别的实体类型列表
            
        Returns:
            list: 识别出的实体列表，每个元素包含实体、类型、位置等信息
        """
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
- "confidence": 识别置信度 (0-1)
- "notes": 补充说明（可选）

输出示例：
[
    {{
        "entity": "明治維新",
        "category": "event",
        "start_pos": 15,
        "end_pos": 19,
        "confidence": 0.95,
        "notes": "日本近代重要历史事件"
    }}
]"""
        
        response = self._call_llm(prompt)
        
        try:
            entities = json.loads(response)
            self.recognized_entities.extend(entities)
            return entities
        except json.JSONDecodeError:
            return self._parse_entities_from_text(response)
    
    def classify_entities(self, entities: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        按类型分类实体
        
        Args:
            entities: 实体列表
            
        Returns:
            dict: 按类型分类的实体字典
        """
        classified = defaultdict(list)
        
        for entity in entities:
            category = entity.get('category', 'unknown')
            classified[category].append(entity)
        
        return dict(classified)
    
    def extract_entity_relationships(self, text: str,
                                   entities: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        提取实体间的关联关系
        
        Args:
            text: 原始文本
            entities: 识别出的实体列表
            
        Returns:
            list: 关系列表
        """
        if self.test_mode:
            return self._extract_mock_relationships(text, entities)
        
        self._init_llm_client()
        
        entity_names = [e['entity'] for e in entities[:20]]
        
        prompt = f"""请分析以下文本中实体之间的关系。

【文本】
{text[:3000]}

【已识别实体】
{', '.join(entity_names)}

请识别实体间的关系，以JSON数组格式输出：
[
    {{
        "source": "实体A",
        "target": "实体B",
        "relation": "关系类型",
        "description": "关系描述"
    }}
]

关系类型可包括：
- 属于/包含关系
- 对立/敌对关系
- 影响/导致关系
- 同时期关系
- 人物-机构关系
- 地点-事件关系"""
        
        response = self._call_llm(prompt)
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return []
    
    def batch_process_documents(self, documents: List[Dict[str, Any]],
                              categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        批量处理多个文档进行NER标注
        
        Args:
            documents: 文档列表，每项包含text和metadata
            categories: 要识别的实体类型
            
        Returns:
            list: 处理结果列表
        """
        results = []
        
        for doc in documents:
            text = doc.get('text', '')
            metadata = doc.get('metadata', {})
            
            entities = self.recognize_historical_entities(text, categories)
            classified = self.classify_entities(entities)
            relationships = self.extract_entity_relationships(text, entities)
            
            results.append({
                'metadata': metadata,
                'entities': entities,
                'classified_entities': classified,
                'relationships': relationships,
                'entity_count': len(entities)
            })
        
        return results
    
    def get_entity_statistics(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        获取实体统计信息
        
        Args:
            entities: 实体列表
            
        Returns:
            dict: 统计信息
        """
        total = len(entities)
        
        category_counts = defaultdict(int)
        for entity in entities:
            category_counts[entity.get('category', 'unknown')] += 1
        
        confidence_sum = 0
        for entity in entities:
            confidence_sum += entity.get('confidence', 0)
        avg_confidence = confidence_sum / total if total > 0 else 0
        
        return {
            'total_entities': total,
            'category_distribution': dict(category_counts),
            'average_confidence': avg_confidence,
            'most_common_category': max(category_counts.items(), key=lambda x: x[1])[0] if category_counts else None
        }
    
    def filter_entities_by_confidence(self, entities: List[Dict[str, Any]],
                                     threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        按置信度过滤实体
        
        Args:
            entities: 实体列表
            threshold: 置信度阈值
            
        Returns:
            list: 过滤后的实体
        """
        return [e for e in entities if e.get('confidence', 0) >= threshold]
    
    def search_entities(self, query: str, 
                       entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        在实体列表中搜索
        
        Args:
            query: 搜索关键词
            entities: 实体列表
            
        Returns:
            list: 匹配的实体
        """
        query_lower = query.lower()
        
        results = []
        for entity in entities:
            entity_name = entity.get('entity', '').lower()
            notes = entity.get('notes', '').lower()
            
            if query_lower in entity_name or query_lower in notes:
                results.append(entity)
        
        return results
    
    def export_entities_for_obsidian(self, entities: List[Dict[str, Any]],
                                    output_format: str = 'json') -> str:
        """
        导出实体为Obsidian格式
        
        Args:
            entities: 实体列表
            output_format: 输出格式 ('json' 或 'markdown')
            
        Returns:
            str: 格式化后的字符串
        """
        if output_format == 'markdown':
            return self._export_as_markdown(entities)
        else:
            return json.dumps(entities, ensure_ascii=False, indent=2)
    
    def create_entity_network(self, entities: List[Dict[str, Any]],
                            relationships: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        创建实体网络图
        
        Args:
            entities: 实体列表
            relationships: 关系列表
            
        Returns:
            dict: 网络图数据
        """
        nodes = []
        edges = []
        
        for entity in entities:
            nodes.append({
                'id': entity.get('entity'),
                'label': entity.get('entity'),
                'category': entity.get('category'),
                'confidence': entity.get('confidence')
            })
        
        for rel in relationships:
            edges.append({
                'source': rel.get('source'),
                'target': rel.get('target'),
                'relation': rel.get('relation'),
                'label': rel.get('relation')
            })
        
        return {
            'nodes': nodes,
            'edges': edges,
            'stats': {
                'total_nodes': len(nodes),
                'total_edges': len(edges)
            }
        }
    
    def recognize_person_entities(self, text: str) -> List[Dict[str, Any]]:
        """专门识别历史人物"""
        return self.recognize_historical_entities(text, ['person'])
    
    def recognize_location_entities(self, text: str) -> List[Dict[str, Any]]:
        """专门识别地理位置"""
        return self.recognize_historical_entities(text, ['location'])
    
    def recognize_event_entities(self, text: str) -> List[Dict[str, Any]]:
        """专门识别历史事件"""
        return self.recognize_historical_entities(text, ['event'])
    
    def recognize_organization_entities(self, text: str) -> List[Dict[str, Any]]:
        """专门识别机构组织"""
        return self.recognize_historical_entities(text, ['organization'])
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM API"""
        try:
            full_prompt = f"你是一位专精于日本历史的名实体识别专家。\n\n{prompt}"
            result = self.llm_client._call_llm(full_prompt, temperature=0.1)
            return result.get('content', '')
        except Exception as e:
            raise RuntimeError(f"LLM API调用失败: {str(e)}")
    
    def _recognize_mock_entities(self, text: str,
                                categories: Optional[List[str]]) -> List[Dict[str, Any]]:
        """模拟实体识别"""
        mock_entities = [
            {
                'entity': '明治維新',
                'category': 'event',
                'start_pos': 10,
                'end_pos': 14,
                'confidence': 0.95,
                'notes': '日本近代重要历史事件'
            },
            {
                'entity': '福沢諭吉',
                'category': 'person',
                'start_pos': 50,
                'end_pos': 55,
                'confidence': 0.92,
                'notes': '明治时期启蒙思想家'
            },
            {
                'entity': '東京',
                'category': 'location',
                'start_pos': 80,
                'end_pos': 82,
                'confidence': 0.98,
                'notes': '日本首都'
            },
            {
                'entity': '幕府',
                'category': 'organization',
                'start_pos': 120,
                'end_pos': 122,
                'confidence': 0.94,
                'notes': '德川幕府'
            },
            {
                'entity': '国体論',
                'category': 'concept',
                'start_pos': 160,
                'end_pos': 163,
                'confidence': 0.88,
                'notes': '日本政治思想核心概念'
            },
            {
                'entity': '丸山真男',
                'category': 'person',
                'start_pos': 200,
                'end_pos': 204,
                'confidence': 0.96,
                'notes': '战后政治思想史学家'
            },
            {
                'entity': '昭和',
                'category': 'date',
                'start_pos': 240,
                'end_pos': 242,
                'confidence': 0.97,
                'notes': '日本年号'
            },
            {
                'entity': '文明開化',
                'category': 'event',
                'start_pos': 280,
                'end_pos': 285,
                'confidence': 0.91,
                'notes': '明治时期社会变革运动'
            },
            {
                'entity': '内務省',
                'category': 'organization',
                'start_pos': 320,
                'end_pos': 323,
                'confidence': 0.93,
                'notes': '日本政府机构'
            },
            {
                'entity': '『文明論概略』',
                'category': 'work',
                'start_pos': 360,
                'end_pos': 366,
                'confidence': 0.95,
                'notes': '福沢諭吉著作'
            }
        ]
        
        if categories:
            mock_entities = [e for e in mock_entities if e['category'] in categories]
        
        return mock_entities
    
    def _extract_mock_relationships(self, text: str,
                                  entities: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """模拟关系提取"""
        return [
            {
                'source': '福沢諭吉',
                'target': '文明開化',
                'relation': '推动',
                'description': '福沢谕吉是文明开化运动的重要推动者'
            },
            {
                'source': '明治維新',
                'target': '幕府',
                'relation': '推翻',
                'description': '明治维新推翻了德川幕府的统治'
            },
            {
                'source': '丸山真男',
                'target': '国体論',
                'relation': '批判',
                'description': '丸山真男对国体论进行了深刻的学术批判'
            },
            {
                'source': '福沢諭吉',
                'target': '『文明論概略』',
                'relation': '著作',
                'description': '《文明论概略》是福沢谕吉的代表性著作'
            }
        ]
    
    def _parse_entities_from_text(self, text: str) -> List[Dict[str, Any]]:
        """从文本中解析实体"""
        entities = []
        
        current_category = 'unknown'
        for line in text.split('\n'):
            line = line.strip()
            
            if not line:
                continue
            
            if ':' in line:
                parts = line.split(':', 1)
                key = parts[0].strip().lower()
                value = parts[1].strip()
                
                if 'person' in key or '人物' in key:
                    current_category = 'person'
                    entities.append({
                        'entity': value,
                        'category': current_category,
                        'confidence': 0.8
                    })
                elif 'location' in key or '地点' in key:
                    current_category = 'location'
                    entities.append({
                        'entity': value,
                        'category': current_category,
                        'confidence': 0.8
                    })
        
        return entities[:10]
    
    def _export_as_markdown(self, entities: List[Dict[str, Any]]) -> str:
        """导出为Markdown格式"""
        lines = [
            "# 命名实体识别结果",
            "",
            f"**识别时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**实体总数**: {len(entities)}",
            ""
        ]
        
        classified = self.classify_entities(entities)
        
        for category, ents in classified.items():
            lines.append(f"## {self.ENTITY_CATEGORIES.get(category, category)}")
            lines.append("")
            
            for entity in ents:
                lines.append(f"- **{entity['entity']}**")
                if entity.get('notes'):
                    lines.append(f"  - 说明：{entity['notes']}")
                if entity.get('confidence'):
                    lines.append(f"  - 置信度：{entity['confidence']:.2f}")
            
            lines.append("")
        
        return '\n'.join(lines)


def create_ner_processor(api_provider: str = "qwen",
                        test_mode: bool = True) -> NERProcessor:
    """
    工厂函数：创建NER处理器实例
    
    Args:
        api_provider: API提供商
        test_mode: 是否使用测试模式
        
    Returns:
        NERProcessor: 配置好的处理器实例
    """
    return NERProcessor(api_provider=api_provider, test_mode=test_mode)


from modules.llm_client import create_llm_client
