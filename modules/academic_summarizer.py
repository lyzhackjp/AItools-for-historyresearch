"""
学术内容智能摘要模块

智能生成学术文献摘要，提取核心研究问题和概念
支持批量处理和相关性评估

核心功能：
- 生成抽取式/生成式摘要
- 提取核心研究问题
- 批量抽取核心概念和研究方法
- 评估文献与研究主题的相关度
- 支持多种API提供商

API优先级：
1. 阿里通义千问 (dashscope)
2. MiniMax
3. Gemini/ChatGPT（备选）

测试模式：使用模拟数据，不调用真实API

依赖模块：
- llm_client.py
- data_structurer.py
"""

import re
import json
import os
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime

from modules.llm_client import create_llm_client
from modules.data_structurer import DataStructurer


class AcademicSummarizer:
    """学术内容智能摘要生成器"""
    
    DEFAULT_SYSTEM_PROMPT = """你是一位资深的学术研究助手，专精于学术文献的分析与摘要生成。

你的专长包括：
1. 快速把握学术论文的核心论点
2. 识别研究问题和创新点
3. 提取关键概念和方法论
4. 评估文献的学术价值
5. 判断文献与特定研究主题的相关性

请严格按照JSON格式输出分析结果。"""
    
    def __init__(self, api_provider: str = "qwen", test_mode: bool = True):
        """
        初始化学术摘要生成器
        
        Args:
            api_provider: API提供商 ('qwen', 'minimax', 'gemini', 'chatgpt')
            test_mode: 测试模式标志
        """
        self.api_provider = api_provider
        self.test_mode = test_mode
        self.llm_client = None
        self.data_structurer = DataStructurer()
        
        self.provider_mapping = {
            'qwen': 'dashscope',
            'minimax': 'minimax',
            'gemini': 'custom',
            'chatgpt': 'openai'
        }
    
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
    
    def generate_abstractive_summary(self, text: str, 
                                   max_length: int = 500,
                                   style: str = 'academic') -> str:
        """
        生成抽象式摘要
        
        Args:
            text: 学术文献文本
            max_length: 最大长度（字符数）
            style: 摘要风格 ('academic', 'simple', 'bullet_points')
            
        Returns:
            str: 生成的摘要
        """
        if self.test_mode:
            return self._generate_mock_abstract(text, max_length, style)
        
        self._init_llm_client()
        
        style_instructions = {
            'academic': '使用正式学术语言，客观陈述',
            'simple': '使用通俗易懂的语言，简明扼要',
            'bullet_points': '使用要点列表形式，每点一句话'
        }
        
        prompt = f"""请为以下学术文献生成{max_length}字左右的摘要。

摘要风格要求：{style_instructions.get(style, style_instructions['academic'])}

文献内容：
{text[:6000]}

请直接输出摘要内容，不要包含其他说明。"""
        
        return self._call_llm(prompt)
    
    def generate_extractive_summary(self, text: str, 
                                  max_sentences: int = 5) -> str:
        """
        生成抽取式摘要
        
        Args:
            text: 学术文献文本
            max_sentences: 最大句子数
            
        Returns:
            str: 抽取的摘要句子
        """
        sentences = self._split_into_sentences(text)
        
        if len(sentences) <= max_sentences:
            return text
        
        if self.test_mode:
            return self._extract_key_sentences_mock(sentences, max_sentences)
        
        scored_sentences = self._score_sentences_importance(sentences)
        
        top_sentences = sorted(
            scored_sentences.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:max_sentences]
        
        selected_indices = [idx for idx, score in top_sentences]
        selected_indices.sort()
        
        return ' '.join([sentences[i] for i in selected_indices])
    
    def extract_research_questions(self, text: str) -> List[Dict[str, Any]]:
        """
        提取核心研究问题
        
        Args:
            text: 学术文献文本
            
        Returns:
            list: 研究问题列表，每个问题包含类型、描述、章节位置
        """
        if self.test_mode:
            return self._extract_mock_research_questions(text)
        
        self._init_llm_client()
        
        prompt = f"""请从以下学术文献中提取核心研究问题。

文献内容：
{text[:6000]}

请以JSON数组格式输出，每个元素包含：
- "type": 问题类型 ("main_question", "sub_question", "methodology_question")
- "description": 问题描述
- "chapter": 出现的章节
- "importance": 重要性评级 (high/medium/low)

输出示例：
[
    {{
        "type": "main_question",
        "description": "近代日本政治思想如何形成？",
        "chapter": "引言",
        "importance": "high"
    }}
]"""
        
        response = self._call_llm(prompt)
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return self._parse_questions_from_text(response)
    
    def identify_core_concepts(self, text: str) -> Dict[str, List[str]]:
        """
        识别核心概念
        
        Args:
            text: 学术文献文本
            
        Returns:
            dict: 按类型分类的概念字典
        """
        if self.test_mode:
            return self._identify_mock_concepts(text)
        
        self._init_llm_client()
        
        prompt = f"""请从以下学术文献中提取核心概念，并按类型分类。

文献内容：
{text[:6000]}

请以JSON格式输出：
{{
    "theoretical_concepts": ["理论概念列表"],
    "methodological_concepts": ["方法论概念列表"],
    "historical_concepts": ["历史概念列表"],
    "technical_terms": ["技术术语列表"]
}}"""
        
        response = self._call_llm(prompt)
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                'theoretical_concepts': [],
                'methodological_concepts': [],
                'historical_concepts': [],
                'technical_terms': []
            }
    
    def extract_research_methods(self, text: str) -> List[Dict[str, str]]:
        """
        提取研究方法
        
        Args:
            text: 学术文献文本
            
        Returns:
            list: 研究方法列表
        """
        if self.test_mode:
            return self._extract_mock_methods(text)
        
        self._init_llm_client()
        
        prompt = f"""请从以下学术文献中提取使用的研究方法。

文献内容：
{text[:6000]}

请以JSON数组格式输出，每个元素包含：
- "method": 方法名称
- "description": 方法描述
- "application": 在文献中的应用

输出示例：
[
    {{
        "method": "文献分析法",
        "description": "通过分析既有研究成果",
        "application": "用于梳理学术史脉络"
    }}
]"""
        
        response = self._call_llm(prompt)
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return []
    
    def filter_relevant_literature(self, documents: List[Dict[str, Any]], 
                                  query: str,
                                  top_k: int = 10) -> List[Dict[str, Any]]:
        """
        评估文献与研究主题的相关度
        
        Args:
            documents: 文献列表，每项包含text和metadata
            query: 研究主题查询
            top_k: 返回的相关文献数量
            
        Returns:
            list: 按相关度排序的文献列表
        """
        scored_documents = []
        
        for doc in documents:
            text = doc.get('text', '')
            metadata = doc.get('metadata', {})
            
            relevance_score = self._calculate_relevance(text, query)
            
            scored_documents.append({
                'metadata': metadata,
                'relevance_score': relevance_score,
                'key_reasons': self._extract_relevance_reasons(text, query)
            })
        
        scored_documents.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return scored_documents[:top_k]
    
    def batch_process(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量处理多个文档
        
        Args:
            documents: 文档列表
            
        Returns:
            list: 处理结果列表
        """
        results = []
        
        for doc in documents:
            text = doc.get('text', '')
            metadata = doc.get('metadata', {})
            
            result = {
                'metadata': metadata,
                'abstractive_summary': self.generate_abstractive_summary(text),
                'extractive_summary': self.generate_extractive_summary(text),
                'research_questions': self.extract_research_questions(text),
                'core_concepts': self.identify_core_concepts(text),
                'research_methods': self.extract_research_methods(text)
            }
            
            results.append(result)
        
        return results
    
    def generate_full_analysis(self, text: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        生成完整的文献分析报告
        
        Args:
            text: 学术文献文本
            metadata: 文献元数据
            
        Returns:
            dict: 完整的分析结果
        """
        metadata = metadata or {}
        
        return {
            'metadata': metadata,
            'abstractive_summary': self.generate_abstractive_summary(text),
            'extractive_summary': self.generate_extractive_summary(text),
            'research_questions': self.extract_research_questions(text),
            'core_concepts': self.identify_core_concepts(text),
            'research_methods': self.extract_research_methods(text),
            'reading_difficulty': self._estimate_reading_difficulty(text),
            'estimated_reading_time': self._estimate_reading_time(text),
            'language': self._detect_language(text)
        }
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM API"""
        try:
            result = self.llm_client._call_llm(prompt, temperature=0.3)
            return result.get('content', '')
        except Exception as e:
            raise RuntimeError(f"LLM API调用失败: {str(e)}")
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """将文本分割成句子"""
        sentence_endings = r'[。！？；\n]+'
        sentences = re.split(sentence_endings, text)
        
        return [s.strip() for s in sentences if s.strip()]
    
    def _score_sentences_importance(self, sentences: List[str]) -> Dict[int, float]:
        """评分句子重要性"""
        scores = {}
        
        important_keywords = [
            '研究', '本文', '主要', '核心', '关键', '结论', 
            '提出', '认为', '分析', '证明', '发现', '表明',
            '讨论', '探讨', '论述', '论证', '观点', '理论'
        ]
        
        for i, sentence in enumerate(sentences):
            score = 0.0
            
            if i < 3:
                score += 0.5
            
            if i >= len(sentences) - 2:
                score += 0.3
            
            for keyword in important_keywords:
                if keyword in sentence:
                    score += 0.1
            
            if len(sentence) > 50:
                score += 0.1
            
            scores[i] = min(score, 1.0)
        
        return scores
    
    def _calculate_relevance(self, text: str, query: str) -> float:
        """计算文献与查询的相关度"""
        if self.test_mode:
            return self._mock_relevance_score(text, query)
        
        prompt = f"""请评估以下文献与研究主题的相关度。

研究主题：{query}

文献摘要/开头：
{text[:1000]}

请返回一个0-1之间的浮点数表示相关度（1表示高度相关），只返回数字，不要其他内容。"""
        
        try:
            response = self._call_llm(prompt)
            score = float(response.strip())
            return max(0.0, min(1.0, score))
        except:
            return 0.5
    
    def _extract_relevance_reasons(self, text: str, query: str) -> List[str]:
        """提取相关原因"""
        if self.test_mode:
            return [
                "包含研究主题关键词",
                "涉及相关理论框架",
                "使用方法与研究相关"
            ]
        
        prompt = f"""请分析以下文献与研究主题的相关原因。

研究主题：{query}

文献摘要：
{text[:1000]}

请输出2-3个简要的相关原因。"""
        
        try:
            response = self._call_llm(prompt)
            return [r.strip() for r in response.split('\n') if r.strip()]
        except:
            return []
    
    def _estimate_reading_difficulty(self, text: str) -> str:
        """估算阅读难度"""
        avg_sentence_length = sum(len(s) for s in self._split_into_sentences(text)) / max(len(text), 1)
        
        technical_terms = len(re.findall(r'《[^》]+》|［[^］]+］|\([^) ]+\)', text))
        
        if avg_sentence_length > 50 or technical_terms > 10:
            return 'difficult'
        elif avg_sentence_length > 30 or technical_terms > 5:
            return 'medium'
        else:
            return 'easy'
    
    def _estimate_reading_time(self, text: str) -> int:
        """估算阅读时间（分钟）"""
        char_count = len(text)
        
        reading_speed = 400
        
        return max(1, char_count // reading_speed)
    
    def _detect_language(self, text: str) -> str:
        """检测文本语言"""
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        japanese_chars = len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', text))
        total_chars = len(text)
        
        if total_chars == 0:
            return 'unknown'
        
        chinese_ratio = chinese_chars / total_chars
        japanese_ratio = japanese_chars / total_chars
        
        if chinese_ratio > 0.3:
            return 'chinese'
        elif japanese_ratio > 0.2:
            return 'japanese'
        elif japanese_ratio > 0.1 and chinese_ratio > 0.1:
            return 'mixed_cjk'
        else:
            return 'other'
    
    def _parse_questions_from_text(self, text: str) -> List[Dict[str, Any]]:
        """从文本中解析研究问题"""
        questions = []
        
        current_type = 'unknown'
        for line in text.split('\n'):
            line = line.strip()
            
            if 'main' in line.lower() or '主要' in line:
                current_type = 'main_question'
            elif 'sub' in line.lower() or '次要' in line:
                current_type = 'sub_question'
            elif 'method' in line.lower() or '方法' in line:
                current_type = 'methodology_question'
            
            if line and not line.startswith('{') and not line.startswith('['):
                questions.append({
                    'type': current_type,
                    'description': line,
                    'chapter': '未知',
                    'importance': 'medium'
                })
        
        return questions[:5]
    
    def _generate_mock_abstract(self, text: str, max_length: int, 
                               style: str) -> str:
        """生成模拟摘要"""
        if style == 'academic':
            return f"""本文研究了近代日本政治思想的形成与发展。研究的核心问题在于明治时代日本如何在吸收西方政治哲学的同时，构建具有自身特色的政治思想体系。

文章首先分析了丸山真男对国体论的系统批判，指出超国家主义的思想根源在于对传统政治概念的误读。其次，通过考察福泽谕吉的文明论思想，揭示了文明开化运动在日本现代化进程中的关键作用。

研究方法上，本文采用思想史与政治哲学相结合的分析框架，综合运用文献分析和比较研究等方法。研究表明，近代日本政治思想的形成是一个复杂的本土化过程。"""
        elif style == 'simple':
            return """这篇论文研究的是近代日本政治思想是怎么形成的。主要分析了丸山真男和福泽谕吉的思想贡献。"""
        else:
            return """- 核心问题：近代日本政治思想的形成
- 主要论点：国体论批判与文明论建构
- 研究方法：思想史分析"""
    
    def _extract_key_sentences_mock(self, sentences: List[str], 
                                   max_sentences: int) -> str:
        """模拟提取关键句子"""
        return '。'.join(sentences[:max_sentences]) + '。'
    
    def _extract_mock_research_questions(self, text: str) -> List[Dict[str, Any]]:
        """模拟提取研究问题"""
        return [
            {
                'type': 'main_question',
                'description': '近代日本政治思想如何形成与发展？',
                'chapter': '引言',
                'importance': 'high'
            },
            {
                'type': 'sub_question',
                'description': '丸山真男的国体论批判有何学术贡献？',
                'chapter': '第一章',
                'importance': 'high'
            },
            {
                'type': 'sub_question',
                'description': '福泽谕吉的文明论对日本现代化有何影响？',
                'chapter': '第二章',
                'importance': 'medium'
            }
        ]
    
    def _identify_mock_concepts(self, text: str) -> Dict[str, List[str]]:
        """模拟识别核心概念"""
        return {
            'theoretical_concepts': [
                '国体论', '超国家主义', '文明开化', '实学', '独立自尊'
            ],
            'methodological_concepts': [
                '思想史研究', '文献分析', '比较研究', '概念史'
            ],
            'historical_concepts': [
                '明治维新', '甲午战争', '大正民主', '战后改革'
            ],
            'technical_terms': [
                '政治哲学', '现代化', '西化', '民族主义'
            ]
        }
    
    def _extract_mock_methods(self, text: str) -> List[Dict[str, str]]:
        """模拟提取研究方法"""
        return [
            {
                'method': '文献分析法',
                'description': '系统梳理既有研究成果',
                'application': '用于建构学术史脉络'
            },
            {
                'method': '比较研究法',
                'description': '对比不同思想家的观点',
                'application': '分析思想演变轨迹'
            },
            {
                'method': '概念史方法',
                'description': '追溯核心概念的历史演变',
                'application': '揭示概念的深层结构'
            }
        ]
    
    def _mock_relevance_score(self, text: str, query: str) -> float:
        """模拟相关度评分"""
        query_keywords = query.lower().split()
        
        text_lower = text.lower()
        
        match_count = sum(1 for keyword in query_keywords if keyword in text_lower)
        
        score = min(0.9, 0.3 + match_count * 0.2)
        
        return score


def create_academic_summarizer(api_provider: str = "qwen",
                              test_mode: bool = True) -> AcademicSummarizer:
    """
    工厂函数：创建学术摘要生成器实例
    
    Args:
        api_provider: API提供商
        test_mode: 是否使用测试模式
        
    Returns:
        AcademicSummarizer: 配置好的生成器实例
    """
    return AcademicSummarizer(api_provider=api_provider, test_mode=test_mode)
