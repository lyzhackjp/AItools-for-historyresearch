"""
文献分析器

提供研究文献的深度分析功能
整合到统一的分析层架构中
"""

import os
import sys
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from intelligent_research_assistant.core.data_models import AnalysisResult
from intelligent_research_assistant.core.llm_manager import LLMManager
from intelligent_research_assistant.core.cache_manager import CacheManager


class LiteratureAnalyzer:
    """
    文献分析器
    
    功能：
    - 文献内容深度分析
    - 技术要点提取
    - 实现建议生成
    - 最佳实践总结
    """
    
    def __init__(self):
        """初始化文献分析器"""
        self.llm = LLMManager.get_instance()
        self.cache = CacheManager()
    
    def analyze(
        self,
        summary: str,
        key_findings: List[str] = None,
        context: str = '',
        use_cache: bool = True
    ) -> AnalysisResult:
        """
        分析文献内容
        
        Args:
            summary: 文献摘要
            key_findings: 关键发现列表
            context: 上下文信息
            use_cache: 是否使用缓存
            
        Returns:
            AnalysisResult: 分析结果
        """
        if key_findings is None:
            key_findings = []
        
        cache_key = f"literature_analysis:{hash(summary)}:{hash(tuple(key_findings))}"
        
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                print(f"[LiteratureAnalyzer] 使用缓存分析结果")
                return AnalysisResult.from_dict(cached)
        
        print(f"[LiteratureAnalyzer] 分析文献内容...")
        
        prompt = self._build_analysis_prompt(summary, key_findings, context)
        
        response = self.llm.call_json(
            prompt=prompt,
            system_prompt=self._get_system_prompt()
        )
        
        analysis_result = AnalysisResult(
            source_id='literature',
            analysis_type='literature',
            summary=response.get('summary', ''),
            key_findings=response.get('key_findings', []),
            technical_points=response.get('technical_points', []),
            recommendations=response.get('recommendations', []),
            confidence=response.get('confidence', 0.8),
            metadata={
                'context': context,
                'input_findings_count': len(key_findings),
                'summary_length': len(summary)
            }
        )
        
        if use_cache:
            self.cache.set(cache_key, analysis_result.to_dict())
        
        print(f"[LiteratureAnalyzer] 分析完成，置信度: {analysis_result.confidence}")
        
        return analysis_result
    
    def extract_technical_points(
        self,
        summary: str,
        use_cache: bool = True
    ) -> List[str]:
        """
        提取技术要点
        
        Args:
            summary: 文献摘要
            use_cache: 是否使用缓存
            
        Returns:
            List[str]: 技术要点列表
        """
        cache_key = f"technical_points:{hash(summary)}"
        
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        
        prompt = f"""请从以下文献摘要中提取关键技术要点：

{summary}

请以JSON格式返回，包含以下字段：
{{
    "technical_points": ["技术要点1", "技术要点2", "技术要点3"]
}}
"""
        
        response = self.llm.call_json(prompt)
        
        points = response.get('technical_points', [])
        
        if use_cache and points:
            self.cache.set(cache_key, points)
        
        return points
    
    def generate_implementation_suggestions(
        self,
        summary: str,
        technical_points: List[str],
        context: str = '',
        use_cache: bool = True
    ) -> List[str]:
        """
        生成实现建议
        
        Args:
            summary: 文献摘要
            technical_points: 技术要点
            context: 上下文信息
            use_cache: 是否使用缓存
            
        Returns:
            List[str]: 实现建议列表
        """
        cache_key = f"implementation_suggestions:{hash(summary)}:{hash(tuple(technical_points))}"
        
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        
        prompt = f"""基于以下文献内容和技术要点，生成实现建议：

文献摘要：
{summary}

技术要点：
{chr(10).join([f'- {p}' for p in technical_points])}

上下文：{context or '通用应用场景'}

请以JSON格式返回，包含以下字段：
{{
    "suggestions": ["实现建议1", "实现建议2", "实现建议3"]
}}
"""
        
        response = self.llm.call_json(prompt)
        
        suggestions = response.get('suggestions', [])
        
        if use_cache and suggestions:
            self.cache.set(cache_key, suggestions)
        
        return suggestions
    
    def _build_analysis_prompt(
        self,
        summary: str,
        key_findings: List[str],
        context: str
    ) -> str:
        """
        构建分析提示词
        
        Args:
            summary: 文献摘要
            key_findings: 关键发现
            context: 上下文
            
        Returns:
            str: 提示词
        """
        findings_text = "\n".join([f"- {f}" for f in key_findings]) if key_findings else "暂无关键发现"
        
        prompt = f"""请深入分析以下研究文献：

文献摘要：
{summary}

关键发现：
{findings_text}

上下文：{context or '通用研究背景'}

请提供全面的分析，包括：
1. 文献概述（2-3句话）
2. 关键发现（3-5个）
3. 技术要点（3-5个）
4. 实现建议（3-5个）

请以JSON格式返回分析结果，包含以下字段：
{{
    "summary": "文献概述",
    "key_findings": ["关键发现1", "关键发现2", "关键发现3"],
    "technical_points": ["技术要点1", "技术要点2", "技术要点3"],
    "recommendations": ["建议1", "建议2", "建议3"],
    "confidence": 0.85
}}
"""
        
        return prompt
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一位资深的学术研究专家，擅长分析研究文献的技术要点和实现方法。

你的分析应该：
1. 准确提取文献的核心技术要点
2. 提供切实可行的实现建议
3. 识别最佳实践和潜在局限性
4. 结合上下文提供有针对性的建议

请确保分析结果具有实用性和可操作性。"""
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            dict: 统计信息
        """
        llm_stats = self.llm.get_stats()
        cache_stats = self.cache.get_stats()
        
        return {
            'llm_stats': llm_stats,
            'cache_stats': cache_stats
        }
    
    def __repr__(self):
        return f"LiteratureAnalyzer(llm={self.llm.api_provider})"


def test_literature_analyzer():
    """测试文献分析器"""
    print("\n=== 测试文献分析器 ===\n")
    
    analyzer = LiteratureAnalyzer()
    print(f"1. 初始化: {analyzer}")
    
    test_summary = """
    BERT是一种预训练语言表示模型，通过在大规模文本语料上进行预训练，
    然后在下游任务上进行微调，取得了显著的性能提升。BERT采用了双向
    Transformer编码器，使用Masked Language Model和Next Sentence Prediction
    两种预训练任务。
    """
    
    test_findings = [
        "双向编码器能够更好地理解上下文",
        "预训练-微调范式效果显著",
        "MLM任务有效提升语言理解能力"
    ]
    
    print(f"\n2. 测试文献分析")
    
    analysis = analyzer.analyze(
        summary=test_summary,
        key_findings=test_findings,
        context='NLP预训练模型研究'
    )
    
    print(f"\n3. 分析结果:")
    print(f"   概述: {analysis.summary}")
    print(f"   关键发现: {analysis.key_findings[:2]}")
    print(f"   技术要点: {analysis.technical_points[:2]}")
    print(f"   建议: {analysis.recommendations[:2]}")
    print(f"   置信度: {analysis.confidence}")
    
    points = analyzer.extract_technical_points(test_summary)
    print(f"\n4. 技术要点: {points[:3]}")
    
    suggestions = analyzer.generate_implementation_suggestions(
        test_summary,
        points,
        context='NLP应用开发'
    )
    print(f"\n5. 实现建议: {suggestions[:3]}")
    
    stats = analyzer.get_stats()
    print(f"\n6. 统计信息:")
    print(f"   LLM调用次数: {stats['llm_stats']['call_count']}")
    
    print("\n✅ 测试完成")


if __name__ == '__main__':
    test_literature_analyzer()
