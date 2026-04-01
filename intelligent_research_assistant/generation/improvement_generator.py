"""
改进建议生成器

提供模块功能改进建议生成功能
整合到统一的生成层架构中
"""

import os
import sys
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from intelligent_research_assistant.core.data_models import ImprovementSuggestion
from intelligent_research_assistant.core.llm_manager import LLMManager
from intelligent_research_assistant.core.cache_manager import CacheManager


class ImprovementGenerator:
    """
    改进建议生成器
    
    功能：
    - 模块功能改进建议
    - 短期/中期/长期建议分类
    - 代码示例生成
    - 优先级评估
    """
    
    def __init__(self):
        """初始化改进建议生成器"""
        self.llm = LLMManager.get_instance()
        self.cache = CacheManager()
    
    def generate(
        self,
        module_name: str,
        context: str,
        research_findings: Dict[str, Any] = None,
        literature_insights: Dict[str, Any] = None,
        use_cache: bool = True
    ) -> ImprovementSuggestion:
        """
        生成模块功能改进建议
        
        Args:
            module_name: 模块名称
            context: 应用上下文
            research_findings: 研究发现
            literature_insights: 文献洞察
            use_cache: 是否使用缓存
            
        Returns:
            ImprovementSuggestion: 改进建议
        """
        cache_key = f"improvement:{module_name}:{hash(context)}"
        
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                print(f"[ImprovementGenerator] 使用缓存建议: {module_name}")
                return ImprovementSuggestion.from_dict(cached)
        
        print(f"[ImprovementGenerator] 生成改进建议: {module_name}")
        
        prompt = self._build_improvement_prompt(
            module_name,
            context,
            research_findings,
            literature_insights
        )
        
        response = self.llm.call_json(
            prompt=prompt,
            system_prompt=self._get_system_prompt()
        )
        
        suggestion = ImprovementSuggestion(
            module_name=module_name,
            context=context,
            short_term=response.get('short_term', []),
            medium_term=response.get('medium_term', []),
            long_term=response.get('long_term', []),
            code_examples=response.get('code_examples', []),
            priority=response.get('priority', 'medium'),
            confidence=response.get('confidence', 0.8)
        )
        
        if use_cache:
            self.cache.set(cache_key, suggestion.to_dict())
        
        print(f"[ImprovementGenerator] 建议生成完成，优先级: {suggestion.priority}")
        
        return suggestion
    
    def generate_from_analysis(
        self,
        module_name: str,
        context: str,
        analysis_results: List[Any],
        use_cache: bool = True
    ) -> ImprovementSuggestion:
        """
        从分析结果生成改进建议
        
        Args:
            module_name: 模块名称
            context: 应用上下文
            analysis_results: 分析结果列表
            use_cache: 是否使用缓存
            
        Returns:
            ImprovementSuggestion: 改进建议
        """
        research_findings = self._extract_research_findings(analysis_results)
        literature_insights = self._extract_literature_insights(analysis_results)
        
        return self.generate(
            module_name=module_name,
            context=context,
            research_findings=research_findings,
            literature_insights=literature_insights,
            use_cache=use_cache
        )
    
    def _extract_research_findings(self, results: List[Any]) -> Dict[str, Any]:
        """从分析结果提取研究发现"""
        findings = {
            'summary': '',
            'key_findings': [],
            'trends': []
        }
        
        for result in results:
            if hasattr(result, 'summary'):
                findings['summary'] += result.summary + ' '
            
            if hasattr(result, 'key_findings'):
                findings['key_findings'].extend(result.key_findings)
            
            if hasattr(result, 'technical_points'):
                findings['trends'].extend(result.technical_points)
        
        return findings
    
    def _extract_literature_insights(self, results: List[Any]) -> Dict[str, Any]:
        """从分析结果提取文献洞察"""
        insights = {
            'technical_points': [],
            'implementation_suggestions': []
        }
        
        for result in results:
            if hasattr(result, 'technical_points'):
                insights['technical_points'].extend(result.technical_points)
            
            if hasattr(result, 'recommendations'):
                insights['implementation_suggestions'].extend(result.recommendations)
        
        return insights
    
    def _build_improvement_prompt(
        self,
        module_name: str,
        context: str,
        research_findings: Dict[str, Any],
        literature_insights: Dict[str, Any]
    ) -> str:
        """
        构建改进建议提示词
        
        Args:
            module_name: 模块名称
            context: 应用上下文
            research_findings: 研究发现
            literature_insights: 文献洞察
            
        Returns:
            str: 提示词
        """
        research_summary = research_findings.get('summary', '') if research_findings else ''
        key_findings = research_findings.get('key_findings', []) if research_findings else []
        trends = research_findings.get('trends', []) if research_findings else []
        
        tech_points = literature_insights.get('technical_points', []) if literature_insights else []
        impl_suggestions = literature_insights.get('implementation_suggestions', []) if literature_insights else []
        
        prompt = f"""请为以下模块生成功能改进建议：

模块名称：{module_name}
应用上下文：{context}

研究发现：
{research_summary}

关键发现：
{chr(10).join([f'- {f}' for f in key_findings[:5]]) if key_findings else '暂无'}

技术趋势：
{chr(10).join([f'- {t}' for t in trends[:5]]) if trends else '暂无'}

技术要点：
{chr(10).join([f'- {p}' for p in tech_points[:5]]) if tech_points else '暂无'}

实现建议：
{chr(10).join([f'- {s}' for s in impl_suggestions[:5]]) if impl_suggestions else '暂无'}

请生成详细的改进建议，包括：
1. 短期改进建议（1-3个月）
2. 中期改进建议（3-6个月）
3. 长期改进建议（6-12个月）
4. 代码示例（可选）
5. 优先级评估（high/medium/low）

请以JSON格式返回，包含以下字段：
{{
    "short_term": ["建议1", "建议2", "建议3"],
    "medium_term": ["建议1", "建议2", "建议3"],
    "long_term": ["建议1", "建议2", "建议3"],
    "code_examples": ["示例1", "示例2"],
    "priority": "high",
    "confidence": 0.85
}}
"""
        
        return prompt
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一位资深的软件架构师和技术顾问，擅长分析模块功能并提出切实可行的改进建议。

你的建议应该：
1. 具有可操作性和实用性
2. 考虑短期、中期、长期的实施路径
3. 结合最新的研究成果和技术趋势
4. 提供具体的代码示例（如适用）
5. 评估优先级和实施难度

请确保建议具有专业性和可实施性。"""
    
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
        return f"ImprovementGenerator(llm={self.llm.api_provider})"


def test_improvement_generator():
    """测试改进建议生成器"""
    print("\n=== 测试改进建议生成器 ===\n")
    
    generator = ImprovementGenerator()
    print(f"1. 初始化: {generator}")
    
    test_findings = {
        'summary': 'BERT模型在NLP任务中表现优异',
        'key_findings': [
            '预训练-微调范式效果显著',
            '双向编码器性能优于单向',
            '大规模数据集提升模型效果'
        ],
        'trends': [
            'Transformer架构成为主流',
            '预训练模型广泛应用',
            '多模态学习兴起'
        ]
    }
    
    test_insights = {
        'technical_points': [
            '使用预训练模型',
            'Fine-tuning技术',
            '数据增强方法'
        ],
        'implementation_suggestions': [
            '选择合适的预训练模型',
            '准备充足的标注数据',
            '优化超参数配置'
        ]
    }
    
    print(f"\n2. 生成改进建议...")
    
    suggestion = generator.generate(
        module_name='ner_recognizer',
        context='日文史料实体识别',
        research_findings=test_findings,
        literature_insights=test_insights
    )
    
    print(f"\n3. 改进建议:")
    print(f"   模块: {suggestion.module_name}")
    print(f"   上下文: {suggestion.context}")
    print(f"   优先级: {suggestion.priority}")
    print(f"   置信度: {suggestion.confidence}")
    
    print(f"\n   短期建议:")
    for i, s in enumerate(suggestion.short_term[:3], 1):
        print(f"     {i}. {s}")
    
    print(f"\n   中期建议:")
    for i, s in enumerate(suggestion.medium_term[:3], 1):
        print(f"     {i}. {s}")
    
    print(f"\n   长期建议:")
    for i, s in enumerate(suggestion.long_term[:3], 1):
        print(f"     {i}. {s}")
    
    stats = generator.get_stats()
    print(f"\n4. 统计信息:")
    print(f"   LLM调用次数: {stats['llm_stats']['call_count']}")
    
    print("\n✅ 测试完成")


if __name__ == '__main__':
    test_improvement_generator()
