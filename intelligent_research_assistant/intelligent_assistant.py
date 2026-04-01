"""
智能研究助手 - 主助手类

整合所有模块功能，提供统一的对外接口
"""

import os
import sys
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from intelligent_research_assistant.core.data_models import (
    SearchResult, AnalysisResult, Report, ImprovementSuggestion
)
from intelligent_research_assistant.core.llm_manager import LLMManager
from intelligent_research_assistant.core.cache_manager import CacheManager
from intelligent_research_assistant.core.config_manager import ConfigManager

from intelligent_research_assistant.search.project_finder import ProjectFinder
from intelligent_research_assistant.search.paper_finder import PaperFinder
from intelligent_research_assistant.search.document_fetcher import DocumentFetcher

from intelligent_research_assistant.analysis.project_analyzer import ProjectAnalyzer
from intelligent_research_assistant.analysis.paper_analyzer import PaperAnalyzer
from intelligent_research_assistant.analysis.literature_analyzer import LiteratureAnalyzer

from intelligent_research_assistant.generation.report_generator import ReportGenerator
from intelligent_research_assistant.generation.improvement_generator import ImprovementGenerator


class IntelligentResearchAssistant:
    """
    智能研究助手
    
    整合OpenSourceFinder和LearningModule的统一模块
    提供开源项目搜索、学术文献分析、报告生成等一站式服务
    
    功能特性：
    - 多平台搜索（GitHub, arXiv, Papers With Code）
    - 项目与论文深度分析
    - 学术文献研究
    - 智能报告生成
    - 改进建议生成
    """
    
    def __init__(
        self,
        api_provider: str = 'qwen',
        model: str = None,
        test_mode: bool = False,
        cache_enabled: bool = True,
        cache_ttl_days: int = 7
    ):
        """
        初始化智能研究助手
        
        Args:
            api_provider: API提供商 ('qwen', 'openai', 'minimax', 'zhipu', 'deepseek', 'ollama')
            model: 模型名称（可选）
            test_mode: 测试模式
            cache_enabled: 是否启用缓存
            cache_ttl_days: 缓存有效期（天）
        """
        self.api_provider = api_provider
        self.test_mode = test_mode
        self.cache_enabled = cache_enabled
        
        print(f"[IntelligentResearchAssistant] 初始化...")
        print(f"  API提供商: {api_provider}")
        print(f"  测试模式: {test_mode}")
        print(f"  缓存启用: {cache_enabled}")
        
        self.llm = LLMManager.get_instance(
            api_provider=api_provider,
            model=model,
            test_mode=test_mode
        )
        
        self.cache = CacheManager(ttl_days=cache_ttl_days) if cache_enabled else None
        self.config = ConfigManager.get_instance()
        
        self.project_finder = ProjectFinder()
        self.paper_finder = PaperFinder()
        self.document_fetcher = DocumentFetcher()
        
        self.project_analyzer = ProjectAnalyzer()
        self.paper_analyzer = PaperAnalyzer()
        self.literature_analyzer = LiteratureAnalyzer()
        
        self.report_generator = ReportGenerator()
        self.improvement_generator = ImprovementGenerator()
        
        print(f"[IntelligentResearchAssistant] 初始化完成\n")
    
    def analyze_module_optimization(
        self,
        module_name: str,
        context: str,
        search_limit: int = 50,
        analysis_depth: str = 'deep'
    ) -> Dict[str, Any]:
        """
        模块优化分析
        
        搜索相关项目和论文，进行深度分析，生成改进建议
        
        Args:
            module_name: 模块名称
            context: 应用上下文
            search_limit: 搜索数量限制
            analysis_depth: 分析深度
            
        Returns:
            dict: 完整的分析结果
        """
        print(f"\n{'='*60}")
        print(f"模块优化分析: {module_name}")
        print(f"{'='*60}\n")
        
        print(f"[步骤1] 搜索相关项目...")
        projects = self.project_finder.search(
            query=f"{module_name} {context}",
            limit=search_limit // 2
        )
        
        print(f"\n[步骤2] 搜索相关论文...")
        papers = self.paper_finder.search(
            query=f"{module_name} {context}",
            limit=search_limit // 2
        )
        
        print(f"\n[步骤3] 分析项目...")
        project_analyses = self.project_analyzer.batch_analyze(
            projects[:10],
            analysis_depth=analysis_depth
        )
        
        print(f"\n[步骤4] 分析论文...")
        paper_analyses = self.paper_analyzer.batch_analyze(
            papers[:10],
            analysis_depth=analysis_depth
        )
        
        print(f"\n[步骤5] 生成综合报告...")
        report = self.report_generator.generate(
            search_results=projects + papers,
            analysis_results=project_analyses + paper_analyses,
            title=f'{module_name} 模块优化分析报告'
        )
        
        print(f"\n[步骤6] 生成改进建议...")
        all_analyses = project_analyses + paper_analyses
        suggestion = self.improvement_generator.generate_from_analysis(
            module_name=module_name,
            context=context,
            analysis_results=all_analyses
        )
        
        result = {
            'module_name': module_name,
            'context': context,
            'search_results': {
                'projects': [r.to_dict() for r in projects],
                'papers': [r.to_dict() for r in papers]
            },
            'analysis_results': {
                'projects': [a.to_dict() for a in project_analyses],
                'papers': [a.to_dict() for a in paper_analyses]
            },
            'report': report.to_dict(),
            'improvement_suggestion': suggestion.to_dict()
        }
        
        print(f"\n{'='*60}")
        print(f"分析完成")
        print(f"  项目数: {len(projects)}")
        print(f"  论文数: {len(papers)}")
        print(f"  报告长度: {len(report.content)} 字符")
        print(f"{'='*60}\n")
        
        return result
    
    def search_projects(
        self,
        query: str,
        platforms: List[str] = None,
        limit: int = 50
    ) -> List[SearchResult]:
        """
        搜索项目
        
        Args:
            query: 搜索查询
            platforms: 平台列表
            limit: 结果数量限制
            
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        return self.project_finder.search(query, platforms, limit)
    
    def search_papers(
        self,
        query: str,
        sources: List[str] = None,
        limit: int = 50
    ) -> List[SearchResult]:
        """
        搜索论文
        
        Args:
            query: 搜索查询
            sources: 数据源列表
            limit: 结果数量限制
            
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        return self.paper_finder.search(query, sources, limit)
    
    def analyze_project(
        self,
        result: SearchResult,
        analysis_depth: str = 'deep'
    ) -> AnalysisResult:
        """
        分析项目
        
        Args:
            result: 搜索结果
            analysis_depth: 分析深度
            
        Returns:
            AnalysisResult: 分析结果
        """
        return self.project_analyzer.analyze(result, analysis_depth)
    
    def analyze_paper(
        self,
        result: SearchResult,
        analysis_depth: str = 'deep'
    ) -> AnalysisResult:
        """
        分析论文
        
        Args:
            result: 搜索结果
            analysis_depth: 分析深度
            
        Returns:
            AnalysisResult: 分析结果
        """
        return self.paper_analyzer.analyze(result, analysis_depth)
    
    def analyze_literature(
        self,
        summary: str,
        key_findings: List[str] = None,
        context: str = ''
    ) -> AnalysisResult:
        """
        分析文献
        
        Args:
            summary: 文献摘要
            key_findings: 关键发现
            context: 上下文
            
        Returns:
            AnalysisResult: 分析结果
        """
        return self.literature_analyzer.analyze(summary, key_findings, context)
    
    def generate_report(
        self,
        search_results: List[SearchResult],
        analysis_results: List[AnalysisResult],
        title: str = '综合分析报告'
    ) -> Report:
        """
        生成报告
        
        Args:
            search_results: 搜索结果列表
            analysis_results: 分析结果列表
            title: 报告标题
            
        Returns:
            Report: 生成的报告
        """
        return self.report_generator.generate(search_results, analysis_results, title)
    
    def generate_improvements(
        self,
        module_name: str,
        context: str,
        research_findings: Dict[str, Any] = None,
        literature_insights: Dict[str, Any] = None
    ) -> ImprovementSuggestion:
        """
        生成改进建议
        
        Args:
            module_name: 模块名称
            context: 应用上下文
            research_findings: 研究发现
            literature_insights: 文献洞察
            
        Returns:
            ImprovementSuggestion: 改进建议
        """
        return self.improvement_generator.generate(
            module_name, context, research_findings, literature_insights
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            dict: 统计信息
        """
        return {
            'llm_stats': self.llm.get_stats(),
            'cache_stats': self.cache.get_stats() if self.cache else None,
            'config_stats': {
                'providers': len(self.config.list_providers()),
                'platforms': len(self.config.list_platforms())
            }
        }
    
    def __repr__(self):
        return f"IntelligentResearchAssistant(provider={self.api_provider}, test_mode={self.test_mode})"


def test_intelligent_assistant():
    """测试智能研究助手"""
    print("\n=== 测试智能研究助手 ===\n")
    
    assistant = IntelligentResearchAssistant(
        api_provider='qwen',
        test_mode=True
    )
    
    print(f"1. 初始化: {assistant}")
    
    print(f"\n2. 测试项目搜索...")
    projects = assistant.search_projects('machine learning', limit=3)
    print(f"   找到 {len(projects)} 个项目")
    
    print(f"\n3. 测试论文搜索...")
    papers = assistant.search_papers('deep learning', limit=3)
    print(f"   找到 {len(papers)} 篇论文")
    
    if projects:
        print(f"\n4. 测试项目分析...")
        analysis = assistant.analyze_project(projects[0], analysis_depth='shallow')
        print(f"   分析完成: {analysis.summary[:50]}...")
    
    print(f"\n5. 测试文献分析...")
    lit_analysis = assistant.analyze_literature(
        summary='这是一个关于深度学习的文献',
        key_findings=['发现1', '发现2'],
        context='AI研究'
    )
    print(f"   分析完成: {lit_analysis.summary[:50]}...")
    
    print(f"\n6. 测试改进建议生成...")
    suggestion = assistant.generate_improvements(
        module_name='test_module',
        context='测试上下文'
    )
    print(f"   建议生成完成，优先级: {suggestion.priority}")
    
    stats = assistant.get_stats()
    print(f"\n7. 统计信息:")
    print(f"   LLM调用次数: {stats['llm_stats']['call_count']}")
    
    print("\n✅ 测试完成")


if __name__ == '__main__':
    test_intelligent_assistant()
