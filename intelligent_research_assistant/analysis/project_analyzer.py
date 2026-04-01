"""
项目分析器

提供GitHub项目的深度分析功能
整合到统一的分析层架构中
"""

import os
import sys
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from intelligent_research_assistant.core.data_models import SearchResult, AnalysisResult
from intelligent_research_assistant.core.llm_manager import LLMManager
from intelligent_research_assistant.core.cache_manager import CacheManager
from intelligent_research_assistant.search.document_fetcher import DocumentFetcher


class ProjectAnalyzer:
    """
    项目分析器
    
    功能：
    - 项目README深度分析
    - 技术栈识别
    - 代码质量评估
    - 社区活跃度分析
    """
    
    def __init__(self):
        """初始化项目分析器"""
        self.llm = LLMManager.get_instance()
        self.cache = CacheManager()
        self.fetcher = DocumentFetcher()
    
    def analyze(
        self,
        result: SearchResult,
        analysis_depth: str = 'deep',
        use_cache: bool = True
    ) -> AnalysisResult:
        """
        分析项目
        
        Args:
            result: 搜索结果
            analysis_depth: 分析深度 ('shallow', 'medium', 'deep')
            use_cache: 是否使用缓存
            
        Returns:
            AnalysisResult: 分析结果
        """
        cache_key = f"project_analysis:{result.id}:{analysis_depth}"
        
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                print(f"[ProjectAnalyzer] 使用缓存分析结果: {result.title[:30]}")
                return AnalysisResult.from_dict(cached)
        
        print(f"[ProjectAnalyzer] 分析项目: {result.title[:50]}...")
        
        readme_content = self._fetch_readme(result)
        
        prompt = self._build_analysis_prompt(result, readme_content, analysis_depth)
        
        response = self.llm.call_json(
            prompt=prompt,
            system_prompt=self._get_system_prompt()
        )
        
        analysis_result = AnalysisResult(
            source_id=result.id,
            analysis_type='project',
            summary=response.get('summary', ''),
            key_findings=response.get('key_findings', []),
            technical_points=response.get('technical_points', []),
            recommendations=response.get('recommendations', []),
            confidence=response.get('confidence', 0.8),
            metadata={
                'analysis_depth': analysis_depth,
                'source_title': result.title,
                'source_url': result.url,
                'has_readme': readme_content is not None,
                'readme_length': len(readme_content) if readme_content else 0
            }
        )
        
        if use_cache:
            self.cache.set(cache_key, analysis_result.to_dict())
        
        print(f"[ProjectAnalyzer] 分析完成，置信度: {analysis_result.confidence}")
        
        return analysis_result
    
    def batch_analyze(
        self,
        results: List[SearchResult],
        analysis_depth: str = 'deep',
        delay: float = 1.0
    ) -> List[AnalysisResult]:
        """
        批量分析项目
        
        Args:
            results: 搜索结果列表
            analysis_depth: 分析深度
            delay: 分析间隔（秒）
            
        Returns:
            List[AnalysisResult]: 分析结果列表
        """
        analyses = []
        
        for i, result in enumerate(results, 1):
            print(f"\n[ProjectAnalyzer] 批量分析 {i}/{len(results)}")
            
            try:
                analysis = self.analyze(result, analysis_depth)
                analyses.append(analysis)
                
                import time
                if i < len(results):
                    time.sleep(delay)
                    
            except Exception as e:
                print(f"[ProjectAnalyzer] 分析失败: {e}")
                continue
        
        return analyses
    
    def _fetch_readme(self, result: SearchResult) -> Optional[str]:
        """
        获取README内容
        
        Args:
            result: 搜索结果
            
        Returns:
            Optional[str]: README内容
        """
        if result.source != 'github':
            return None
        
        doc = self.fetcher.fetch_github_readme(result.url)
        
        if 'error' in doc:
            return None
        
        return doc.get('content', '')
    
    def _build_analysis_prompt(
        self,
        result: SearchResult,
        readme_content: Optional[str],
        analysis_depth: str
    ) -> str:
        """
        构建分析提示词
        
        Args:
            result: 搜索结果
            readme_content: README内容
            analysis_depth: 分析深度
            
        Returns:
            str: 提示词
        """
        depth_instructions = {
            'shallow': '请进行简要分析，重点关注项目的基本信息。',
            'medium': '请进行中等深度分析，重点关注项目的技术特点和主要功能。',
            'deep': '请进行深度分析，全面评估项目的技术价值、代码质量和应用前景。'
        }
        
        prompt = f"""请分析以下GitHub项目：

项目信息：
- 名称：{result.title}
- URL：{result.url}
- 描述：{result.description}
- Stars：{result.metadata.get('stars', 0)}
- Forks：{result.metadata.get('forks', 0)}
- 语言：{result.metadata.get('language', 'Unknown')}
- 标签：{', '.join(result.tags[:5])}

"""

        if readme_content:
            prompt += f"""
README内容（前2000字符）：
{readme_content[:2000]}

"""
        
        prompt += f"""
{depth_instructions.get(analysis_depth, depth_instructions['deep'])}

请以JSON格式返回分析结果，包含以下字段：
{{
    "summary": "项目概述（2-3句话）",
    "key_findings": ["关键发现1", "关键发现2", "关键发现3"],
    "technical_points": ["技术特点1", "技术特点2", "技术特点3"],
    "recommendations": ["建议1", "建议2", "建议3"],
    "confidence": 0.85
}}
"""
        
        return prompt
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一位资深的技术专家和项目分析师，擅长分析开源项目的技术价值、代码质量和应用前景。

你的分析应该：
1. 客观、专业、深入
2. 关注技术创新点和实际应用价值
3. 识别项目的优缺点
4. 提供有针对性的建议

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
        return f"ProjectAnalyzer(llm={self.llm.api_provider})"


def test_project_analyzer():
    """测试项目分析器"""
    print("\n=== 测试项目分析器 ===\n")
    
    analyzer = ProjectAnalyzer()
    print(f"1. 初始化: {analyzer}")
    
    test_result = SearchResult(
        id='github-test-001',
        title='Python Machine Learning Library',
        source='github',
        url='https://github.com/scikit-learn/scikit-learn',
        description='Machine learning library for Python',
        metadata={
            'stars': 50000,
            'forks': 20000,
            'language': 'Python'
        },
        tags=['machine-learning', 'python', 'data-science']
    )
    
    print(f"\n2. 测试项目: {test_result.title}")
    
    analysis = analyzer.analyze(test_result, analysis_depth='shallow')
    
    print(f"\n3. 分析结果:")
    print(f"   概述: {analysis.summary}")
    print(f"   关键发现: {analysis.key_findings[:2]}")
    print(f"   技术特点: {analysis.technical_points[:2]}")
    print(f"   置信度: {analysis.confidence}")
    
    stats = analyzer.get_stats()
    print(f"\n4. 统计信息:")
    print(f"   LLM调用次数: {stats['llm_stats']['call_count']}")
    
    print("\n✅ 测试完成")


if __name__ == '__main__':
    test_project_analyzer()
