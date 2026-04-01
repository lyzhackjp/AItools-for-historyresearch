"""
报告生成器

提供综合报告生成功能
整合到统一的生成层架构中
"""

import os
import sys
from typing import List, Dict, Any, Optional
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from intelligent_research_assistant.core.data_models import SearchResult, AnalysisResult, Report
from intelligent_research_assistant.core.llm_manager import LLMManager
from intelligent_research_assistant.core.cache_manager import CacheManager


class ReportGenerator:
    """
    报告生成器
    
    功能：
    - 综合报告生成
    - 多格式输出（Markdown, JSON, HTML）
    - 结构化内容组织
    - 自动摘要生成
    """
    
    def __init__(self):
        """初始化报告生成器"""
        self.llm = LLMManager.get_instance()
        self.cache = CacheManager()
    
    def generate(
        self,
        search_results: List[SearchResult],
        analysis_results: List[AnalysisResult],
        title: str = '综合分析报告',
        format: str = 'markdown',
        use_cache: bool = True
    ) -> Report:
        """
        生成综合报告
        
        Args:
            search_results: 搜索结果列表
            analysis_results: 分析结果列表
            title: 报告标题
            format: 报告格式 ('markdown', 'json', 'html')
            use_cache: 是否使用缓存
            
        Returns:
            Report: 生成的报告
        """
        cache_key = f"report:{title}:{len(search_results)}:{len(analysis_results)}"
        
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                print(f"[ReportGenerator] 使用缓存报告")
                return Report.from_dict(cached)
        
        print(f"[ReportGenerator] 生成报告: {title}")
        
        prompt = self._build_report_prompt(search_results, analysis_results, title)
        
        content = self.llm.call(
            prompt=prompt,
            system_prompt=self._get_system_prompt()
        )
        
        sections = self._extract_sections(content, format)
        
        report = Report(
            title=title,
            content=content,
            format=format,
            sections=sections,
            metadata={
                'search_results_count': len(search_results),
                'analysis_results_count': len(analysis_results),
                'generated_at': datetime.now().isoformat()
            }
        )
        
        if use_cache:
            self.cache.set(cache_key, report.to_dict())
        
        print(f"[ReportGenerator] 报告生成完成")
        
        return report
    
    def generate_summary_report(
        self,
        search_results: List[SearchResult],
        analysis_results: List[AnalysisResult],
        use_cache: bool = True
    ) -> Report:
        """
        生成摘要报告
        
        Args:
            search_results: 搜索结果列表
            analysis_results: 分析结果列表
            use_cache: 是否使用缓存
            
        Returns:
            Report: 摘要报告
        """
        return self.generate(
            search_results=search_results,
            analysis_results=analysis_results,
            title='摘要报告',
            format='markdown',
            use_cache=use_cache
        )
    
    def generate_detailed_report(
        self,
        search_results: List[SearchResult],
        analysis_results: List[AnalysisResult],
        use_cache: bool = True
    ) -> Report:
        """
        生成详细报告
        
        Args:
            search_results: 搜索结果列表
            analysis_results: 分析结果列表
            use_cache: 是否使用缓存
            
        Returns:
            Report: 详细报告
        """
        return self.generate(
            search_results=search_results,
            analysis_results=analysis_results,
            title='详细分析报告',
            format='markdown',
            use_cache=use_cache
        )
    
    def save_report(
        self,
        report: Report,
        filepath: str
    ):
        """
        保存报告到文件
        
        Args:
            report: 报告对象
            filepath: 文件路径
        """
        report.save(filepath)
        print(f"[ReportGenerator] 报告已保存: {filepath}")
    
    def _build_report_prompt(
        self,
        search_results: List[SearchResult],
        analysis_results: List[AnalysisResult],
        title: str
    ) -> str:
        """
        构建报告生成提示词
        
        Args:
            search_results: 搜索结果
            analysis_results: 分析结果
            title: 报告标题
            
        Returns:
            str: 提示词
        """
        search_summary = self._summarize_search_results(search_results)
        analysis_summary = self._summarize_analysis_results(analysis_results)
        
        prompt = f"""请根据以下搜索和分析结果生成一份综合报告：

# {title}

## 搜索结果概览
{search_summary}

## 分析结果概览
{analysis_summary}

请生成一份结构化的Markdown格式报告，包含以下部分：

1. **概述** - 整体情况概述
2. **主要发现** - 关键发现和洞察
3. **技术分析** - 技术要点和趋势
4. **建议** - 具体建议和行动计划
5. **结论** - 总结和展望

请确保报告内容专业、详实、具有可操作性。
"""
        
        return prompt
    
    def _summarize_search_results(self, results: List[SearchResult]) -> str:
        """总结搜索结果"""
        if not results:
            return "暂无搜索结果"
        
        summary_parts = []
        summary_parts.append(f"共搜索到 {len(results)} 个结果")
        
        sources = {}
        for r in results:
            sources[r.source] = sources.get(r.source, 0) + 1
        
        sources_str = ", ".join([f"{k}: {v}" for k, v in sources.items()])
        summary_parts.append(f"来源分布: {sources_str}")
        
        top_results = sorted(results, key=lambda x: x.score, reverse=True)[:5]
        summary_parts.append("\nTop 5 结果:")
        for i, r in enumerate(top_results, 1):
            summary_parts.append(f"{i}. {r.title} (评分: {r.score})")
        
        return "\n".join(summary_parts)
    
    def _summarize_analysis_results(self, results: List[AnalysisResult]) -> str:
        """总结分析结果"""
        if not results:
            return "暂无分析结果"
        
        summary_parts = []
        summary_parts.append(f"共分析 {len(results)} 个项目/论文")
        
        all_findings = []
        all_points = []
        
        for r in results:
            all_findings.extend(r.key_findings[:2])
            all_points.extend(r.technical_points[:2])
        
        if all_findings:
            summary_parts.append("\n关键发现:")
            for i, f in enumerate(all_findings[:5], 1):
                summary_parts.append(f"{i}. {f}")
        
        if all_points:
            summary_parts.append("\n技术要点:")
            for i, p in enumerate(all_points[:5], 1):
                summary_parts.append(f"{i}. {p}")
        
        return "\n".join(summary_parts)
    
    def _extract_sections(self, content: str, format: str) -> List[Dict[str, Any]]:
        """提取报告章节"""
        sections = []
        
        if format == 'markdown':
            lines = content.split('\n')
            current_section = None
            current_content = []
            
            for line in lines:
                if line.startswith('## '):
                    if current_section:
                        sections.append({
                            'title': current_section,
                            'content': '\n'.join(current_content)
                        })
                    
                    current_section = line[3:].strip()
                    current_content = []
                else:
                    current_content.append(line)
            
            if current_section:
                sections.append({
                    'title': current_section,
                    'content': '\n'.join(current_content)
                })
        
        return sections
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一位专业的技术报告撰写专家，擅长撰写结构清晰、内容详实的技术分析报告。

你的报告应该：
1. 结构清晰，层次分明
2. 内容专业，数据准确
3. 分析深入，见解独到
4. 建议具体，可操作性强

请使用Markdown格式撰写报告，确保报告的专业性和可读性。"""
    
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
        return f"ReportGenerator(llm={self.llm.api_provider})"


def test_report_generator():
    """测试报告生成器"""
    print("\n=== 测试报告生成器 ===\n")
    
    generator = ReportGenerator()
    print(f"1. 初始化: {generator}")
    
    test_search_results = [
        SearchResult(
            id='test-001',
            title='Python ML Library',
            source='github',
            url='https://github.com/test/ml',
            description='Machine learning library',
            score=95.0
        ),
        SearchResult(
            id='test-002',
            title='Deep Learning Paper',
            source='arxiv',
            url='https://arxiv.org/abs/1234.5678',
            description='Deep learning research',
            score=90.0
        )
    ]
    
    test_analysis_results = [
        AnalysisResult(
            source_id='test-001',
            analysis_type='project',
            summary='优秀的机器学习库',
            key_findings=['发现1', '发现2'],
            technical_points=['技术点1', '技术点2'],
            recommendations=['建议1', '建议2'],
            confidence=0.9
        )
    ]
    
    print(f"\n2. 生成报告...")
    
    report = generator.generate(
        search_results=test_search_results,
        analysis_results=test_analysis_results,
        title='测试报告'
    )
    
    print(f"\n3. 报告信息:")
    print(f"   标题: {report.title}")
    print(f"   格式: {report.format}")
    print(f"   章节数: {len(report.sections)}")
    print(f"   内容长度: {len(report.content)} 字符")
    
    print(f"\n4. 报告预览:")
    print(report.content[:300] + "...")
    
    stats = generator.get_stats()
    print(f"\n5. 统计信息:")
    print(f"   LLM调用次数: {stats['llm_stats']['call_count']}")
    
    print("\n✅ 测试完成")


if __name__ == '__main__':
    test_report_generator()
