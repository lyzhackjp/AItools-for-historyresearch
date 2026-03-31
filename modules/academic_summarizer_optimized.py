"""
学术摘要生成器 - 优化版

专为学术论文设计的智能摘要生成工具

优化内容 (v2.0.0):
- 优化摘要结构，符合学术规范
- 添加关键句提取功能
- 支持多语言摘要生成
- 支持多种摘要类型

核心功能：
- 智能摘要生成：基于论文内容自动生成结构化摘要
- 关键句提取：自动提取论文中的关键句子
- 多语言支持：支持中、英、日文摘要
- 多种摘要类型：结构化摘要、叙述性摘要、评论性摘要

支持的摘要类型：
- structured: 结构化摘要
- narrative: 叙述性摘要
- critical: 评论性摘要
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import math


class SummaryType(Enum):
    """摘要类型枚举"""
    STRUCTURED = 'structured'
    NARRATIVE = 'narrative'
    CRITICAL = 'critical'


class Language(Enum):
    """语言枚举"""
    CHINESE = 'zh'
    ENGLISH = 'en'
    JAPANESE = 'ja'


@dataclass
class KeySentence:
    """关键句数据类"""
    text: str
    position: int
    score: float
    category: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'text': self.text,
            'position': self.position,
            'score': self.score,
            'category': self.category
        }


@dataclass
class GeneratedSummary:
    """生成的摘要数据类"""
    title: str
    summary: str
    summary_type: str
    language: str
    key_sentences: List[KeySentence] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    word_count: int = 0
    char_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class KeySentenceExtractor:
    """关键句提取器"""
    
    SENTENCE_PATTERNS = {
        'zh': r'[^。！？]+[。！？]',
        'en': r'[^.!?]+[.!?]',
        'ja': r'[^。！？]+[。！？]'
    }
    
    IMPORTANCE_KEYWORDS = {
        'zh': [
            '本文', '本研究', '本研究旨在', '研究表明', '研究发现',
            '结论', '结果表明', '综上所述', '因此', '总之',
            '主要观点', '核心问题', '关键在于', '重要意义'
        ],
        'en': [
            'this paper', 'this study', 'we find', 'our results',
            'conclusion', 'in summary', 'therefore', 'thus',
            'significantly', 'importantly', 'key finding'
        ],
        'ja': [
            '本研究', '本稿', '結論', '要するに', 'したがって',
            '研究結果', '重要な点', '主な発見', '総じて'
        ]
    }
    
    def __init__(self, language: str = 'zh'):
        """
        初始化关键句提取器
        
        Args:
            language: 语言代码
        """
        self.language = language
        self.sentence_pattern = self.SENTENCE_PATTERNS.get(language, self.SENTENCE_PATTERNS['zh'])
        self.importance_keywords = self.IMPORTANCE_KEYWORDS.get(language, self.IMPORTANCE_KEYWORDS['zh'])
    
    def extract_sentences(self, text: str) -> List[str]:
        """
        分割文本为句子
        
        Args:
            text: 输入文本
            
        Returns:
            list: 句子列表
        """
        sentences = re.findall(self.sentence_pattern, text)
        return [s.strip() for s in sentences if s.strip()]
    
    def calculate_sentence_scores(self, sentences: List[str], 
                                  original_text: str) -> List[Tuple[int, float, str]]:
        """
        计算句子重要性得分
        
        Args:
            sentences: 句子列表
            original_text: 原始文本
            
        Returns:
            list: (位置, 得分, 类别) 元组列表
        """
        if not sentences:
            return []
        
        scores = []
        total_sentences = len(sentences)
        
        word_freq = self._calculate_word_frequency(original_text)
        
        for i, sentence in enumerate(sentences):
            position_score = self._position_score(i, total_sentences)
            keyword_score = self._keyword_score(sentence)
            length_score = self._length_score(sentence)
            frequency_score = self._frequency_score(sentence, word_freq)
            
            total_score = (
                position_score * 0.25 +
                keyword_score * 0.35 +
                length_score * 0.15 +
                frequency_score * 0.25
            )
            
            category = self._categorize_sentence(sentence)
            
            scores.append((i, total_score, category))
        
        return scores
    
    def _calculate_word_frequency(self, text: str) -> Dict[str, int]:
        """计算词频"""
        words = re.findall(r'\w+', text.lower())
        freq = {}
        for word in words:
            if len(word) > 1:
                freq[word] = freq.get(word, 0) + 1
        return freq
    
    def _position_score(self, position: int, total: int) -> float:
        """位置得分"""
        if total == 0:
            return 0
        
        if position < 3:
            return 1.0
        elif position < total * 0.2:
            return 0.8
        elif position > total * 0.8:
            return 0.7
        else:
            return 0.5
    
    def _keyword_score(self, sentence: str) -> float:
        """关键词得分"""
        score = 0.0
        for keyword in self.importance_keywords:
            if keyword in sentence.lower():
                score += 0.2
        return min(score, 1.0)
    
    def _length_score(self, sentence: str) -> float:
        """长度得分"""
        length = len(sentence)
        if 50 <= length <= 200:
            return 1.0
        elif 30 <= length < 50 or 200 < length <= 300:
            return 0.7
        else:
            return 0.4
    
    def _frequency_score(self, sentence: str, word_freq: Dict[str, int]) -> float:
        """词频得分"""
        words = re.findall(r'\w+', sentence.lower())
        if not words:
            return 0
        
        total_freq = sum(word_freq.get(word, 0) for word in words)
        return min(total_freq / (len(words) * 2), 1.0)
    
    def _categorize_sentence(self, sentence: str) -> str:
        """句子分类"""
        sentence_lower = sentence.lower()
        
        if any(kw in sentence_lower for kw in ['目的', 'aim', '目的', '本研究旨在']):
            return 'purpose'
        elif any(kw in sentence_lower for kw in ['方法', 'method', '方法']):
            return 'method'
        elif any(kw in sentence_lower for kw in ['结果', 'result', '結果', '发现']):
            return 'result'
        elif any(kw in sentence_lower for kw in ['结论', 'conclusion', '結論', '综上']):
            return 'conclusion'
        else:
            return 'content'
    
    def extract_key_sentences(self, text: str, 
                             max_sentences: int = 5) -> List[KeySentence]:
        """
        提取关键句
        
        Args:
            text: 输入文本
            max_sentences: 最大句子数
            
        Returns:
            list: 关键句列表
        """
        sentences = self.extract_sentences(text)
        if not sentences:
            return []
        
        scores = self.calculate_sentence_scores(sentences, text)
        scores.sort(key=lambda x: x[1], reverse=True)
        
        key_sentences = []
        for position, score, category in scores[:max_sentences]:
            key_sentences.append(KeySentence(
                text=sentences[position],
                position=position,
                score=score,
                category=category
            ))
        
        key_sentences.sort(key=lambda x: x.position)
        return key_sentences


class AcademicSummarizerOptimized:
    """学术摘要生成器 - 优化版"""
    
    LANGUAGE_PROMPTS = {
        'zh': {
            'system': """你是一位专业的学术编辑，擅长为学术论文撰写高质量摘要。

【摘要要求】
1. 准确概括论文的核心内容和贡献
2. 结构清晰，逻辑连贯
3. 语言精炼，符合学术规范
4. 字数控制在200-400字

【输出格式】
请以JSON格式输出：
{
    "title": "论文标题",
    "summary": "摘要内容",
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "main_findings": ["发现1", "发现2"],
    "methodology": "研究方法简述"
}""",
            'structured': """请为以下学术论文生成结构化摘要，包含：研究目的、研究方法、主要发现、结论。

【论文内容】
{content}

请按JSON格式输出：""",
            'narrative': """请为以下学术论文生成叙述性摘要，以连贯的段落形式呈现核心内容。

【论文内容】
{content}

请按JSON格式输出：""",
            'critical': """请为以下学术论文生成评论性摘要，包含内容概述和简要评价。

【论文内容】
{content}

请按JSON格式输出："""
        },
        'en': {
            'system': """You are a professional academic editor specializing in writing high-quality abstracts.

【Requirements】
1. Accurately summarize the core content and contributions
2. Clear structure and coherent logic
3. Concise language, following academic conventions
4. Word count: 150-300 words

【Output Format】
Please output in JSON format:
{
    "title": "Paper Title",
    "summary": "Abstract content",
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "main_findings": ["finding1", "finding2"],
    "methodology": "Brief methodology description"
}""",
            'structured': """Please generate a structured abstract for the following academic paper, including: Purpose, Methods, Key Findings, and Conclusions.

【Paper Content】
{content}

Please output in JSON format:""",
            'narrative': """Please generate a narrative abstract for the following academic paper in a coherent paragraph format.

【Paper Content】
{content}

Please output in JSON format:""",
            'critical': """Please generate a critical abstract for the following academic paper, including content summary and brief evaluation.

【Paper Content】
{content}

Please output in JSON format:"""
        },
        'ja': {
            'system': """あなたは学術論文の要約を専門とするプロの編集者です。

【要約要件】
1. 論文の核心的内容と貢献を正確に要約する
2. 構造が明確で、論理が一貫している
3. 言語は簡潔で、学術規範に従う
4. 文字数：200〜400字

【出力形式】
JSON形式で出力してください：
{
    "title": "論文タイトル",
    "summary": "要約内容",
    "keywords": ["キーワード1", "キーワード2", "キーワード3"],
    "main_findings": ["発見1", "発見2"],
    "methodology": "研究方法の概要"
}""",
            'structured': """以下の学術論文の構造化要約を生成してください。研究目的、方法、主な発見、結論を含めてください。

【論文内容】
{content}

JSON形式で出力してください：""",
            'narrative': """以下の学術論文の叙述的要約を生成してください。一貫した段落形式で核心内容を提示してください。

【論文内容】
{content}

JSON形式で出力してください：""",
            'critical': """以下の学術論文の批評的要約を生成してください。内容の概要と簡潔な評価を含めてください。

【論文内容】
{content}

JSON形式で出力してください："""
        }
    }
    
    def __init__(self, llm_client=None, default_language: str = 'zh'):
        """
        初始化摘要生成器
        
        Args:
            llm_client: LLM客户端
            default_language: 默认语言
        """
        self.llm_client = llm_client
        self.default_language = default_language
        self.key_sentence_extractor = KeySentenceExtractor(default_language)
    
    def _init_llm_client(self):
        """初始化LLM客户端"""
        if self.llm_client is None:
            from modules.llm_client import create_llm_client
            self.llm_client = create_llm_client({'provider': 'dashscope'})
    
    def generate_summary(self, content: str,
                        summary_type: str = 'structured',
                        language: str = None,
                        extract_key_sentences: bool = True,
                        max_key_sentences: int = 5) -> GeneratedSummary:
        """
        生成学术摘要
        
        Args:
            content: 论文内容
            summary_type: 摘要类型
            language: 语言
            extract_key_sentences: 是否提取关键句
            max_key_sentences: 最大关键句数
            
        Returns:
            GeneratedSummary: 生成的摘要
        """
        self._init_llm_client()
        
        language = language or self.default_language
        prompts = self.LANGUAGE_PROMPTS.get(language, self.LANGUAGE_PROMPTS['zh'])
        
        self.key_sentence_extractor = KeySentenceExtractor(language)
        
        type_prompt = prompts.get(summary_type, prompts['structured'])
        user_prompt = type_prompt.format(content=content[:4000])
        
        try:
            response = self.llm_client._call_llm(
                user_prompt, 
                temperature=0.3,
                system_prompt=prompts['system']
            )
            
            result_text = response.get('content', '')
            
            try:
                summary_data = json.loads(self._extract_json(result_text))
            except json.JSONDecodeError:
                summary_data = {
                    'title': '摘要生成',
                    'summary': self._clean_response(result_text),
                    'keywords': [],
                    'main_findings': [],
                    'methodology': ''
                }
            
            key_sentences = []
            if extract_key_sentences:
                key_sentences = self.key_sentence_extractor.extract_key_sentences(
                    content, max_key_sentences
                )
            
            summary_text = summary_data.get('summary', '')
            
            return GeneratedSummary(
                title=summary_data.get('title', ''),
                summary=summary_text,
                summary_type=summary_type,
                language=language,
                key_sentences=key_sentences,
                keywords=summary_data.get('keywords', []),
                word_count=len(summary_text.split()),
                char_count=len(summary_text),
                metadata={
                    'main_findings': summary_data.get('main_findings', []),
                    'methodology': summary_data.get('methodology', '')
                }
            )
            
        except Exception as e:
            print(f"摘要生成失败: {e}")
            return GeneratedSummary(
                title='生成失败',
                summary=f"摘要生成失败: {str(e)}",
                summary_type=summary_type,
                language=language
            )
    
    def generate_multilingual_summary(self, content: str,
                                      languages: List[str] = None,
                                      summary_type: str = 'structured') -> Dict[str, GeneratedSummary]:
        """
        生成多语言摘要
        
        Args:
            content: 论文内容
            languages: 语言列表
            summary_type: 摘要类型
            
        Returns:
            dict: 各语言的摘要
        """
        languages = languages or ['zh', 'en']
        
        results = {}
        for lang in languages:
            results[lang] = self.generate_summary(
                content=content,
                summary_type=summary_type,
                language=lang
            )
        
        return results
    
    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON"""
        json_pattern = r'\{[^{}]*(?:\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            if 'summary' in match or 'title' in match:
                return match
        
        return text
    
    def _clean_response(self, response: str) -> str:
        """清理响应文本"""
        result = response.strip()
        
        prefixes = [
            "摘要：", "摘要:", "Abstract:", "要約：", "要約:",
            "```json", "```"
        ]
        for prefix in prefixes:
            if result.startswith(prefix):
                result = result[len(prefix):].strip()
        
        if result.endswith("```"):
            result = result[:-3].strip()
        
        return result.strip()
    
    def save_summary(self, summary: GeneratedSummary, output_path: str) -> str:
        """
        保存摘要到文件
        
        Args:
            summary: 摘要对象
            output_path: 输出路径
            
        Returns:
            str: 保存的文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        content = self._format_summary_markdown(summary)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(output_path)
    
    def _format_summary_markdown(self, summary: GeneratedSummary) -> str:
        """格式化摘要为Markdown"""
        lines = [
            f"# {summary.title}",
            "",
            f"> **摘要类型**: {summary.summary_type} | **语言**: {summary.language}",
            "",
            "## 摘要",
            "",
            summary.summary,
            ""
        ]
        
        if summary.keywords:
            lines.extend([
                "## 关键词",
                "",
                ", ".join(summary.keywords),
                ""
            ])
        
        if summary.key_sentences:
            lines.extend([
                "## 关键句",
                ""
            ])
            for ks in summary.key_sentences:
                lines.append(f"- [{ks.category}] {ks.text}")
            lines.append("")
        
        if summary.metadata.get('main_findings'):
            lines.extend([
                "## 主要发现",
                ""
            ])
            for finding in summary.metadata['main_findings']:
                lines.append(f"- {finding}")
            lines.append("")
        
        return '\n'.join(lines)
    
    def get_supported_languages(self) -> List[str]:
        """获取支持的语言列表"""
        return list(self.LANGUAGE_PROMPTS.keys())
    
    def get_supported_types(self) -> List[str]:
        """获取支持的摘要类型"""
        return ['structured', 'narrative', 'critical']


def create_academic_summarizer_optimized(
    llm_client=None,
    default_language: str = 'zh'
) -> AcademicSummarizerOptimized:
    """
    工厂函数 - 创建优化版学术摘要生成器
    
    Args:
        llm_client: LLM客户端
        default_language: 默认语言
        
    Returns:
        AcademicSummarizerOptimized: 摘要生成器实例
    """
    return AcademicSummarizerOptimized(llm_client, default_language)


if __name__ == "__main__":
    print("学术摘要生成器 - 优化版 v2.0.0")
    print("="*60)
    print("\n支持的语言: zh, en, ja")
    print("支持的摘要类型: structured, narrative, critical")
    print("\n使用方法:")
    print("```python")
    print("from modules.academic_summarizer_optimized import create_academic_summarizer_optimized")
    print("")
    print("# 创建生成器")
    print("summarizer = create_academic_summarizer_optimized()")
    print("")
    print("# 生成摘要")
    print("summary = summarizer.generate_summary(")
    print("    content='论文内容...',")
    print("    summary_type='structured',")
    print("    language='zh'")
    print(")")
    print("")
    print("# 生成多语言摘要")
    print("summaries = summarizer.generate_multilingual_summary(")
    print("    content='论文内容...',")
    print("    languages=['zh', 'en', 'ja']")
    print(")")
    print("")
    print("# 保存摘要")
    print("summarizer.save_summary(summary, 'output/summary.md')")
    print("```")
