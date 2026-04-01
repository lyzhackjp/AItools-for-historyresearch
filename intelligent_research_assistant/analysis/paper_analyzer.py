"""
论文分析器

提供学术论文的深度分析功能
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


class PaperAnalyzer:
    """
    论文分析器
    
    功能：
    - 论文摘要深度分析
    - 研究方法识别
    - 创新点提取
    - 应用价值评估
    """
    
    def __init__(self):
        """初始化论文分析器"""
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
        分析论文
        
        Args:
            result: 搜索结果
            analysis_depth: 分析深度 ('shallow', 'medium', 'deep')
            use_cache: 是否使用缓存
            
        Returns:
            AnalysisResult: 分析结果
        """
        cache_key = f"paper_analysis:{result.id}:{analysis_depth}"
        
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                print(f"[PaperAnalyzer] 使用缓存分析结果: {result.title[:30]}")
                return AnalysisResult.from_dict(cached)
        
        print(f"[PaperAnalyzer] 分析论文: {result.title[:50]}...")
        
        paper_info = self._fetch_paper_info(result)
        
        prompt = self._build_analysis_prompt(result, paper_info, analysis_depth)
        
        response = self.llm.call_json(
            prompt=prompt,
            system_prompt=self._get_system_prompt()
        )
        
        analysis_result = AnalysisResult(
            source_id=result.id,
            analysis_type='paper',
            summary=response.get('summary', ''),
            key_findings=response.get('key_findings', []),
            technical_points=response.get('technical_points', []),
            recommendations=response.get('recommendations', []),
            confidence=response.get('confidence', 0.8),
            metadata={
                'analysis_depth': analysis_depth,
                'source_title': result.title,
                'source_url': result.url,
                'authors': result.metadata.get('authors', []),
                'published': result.metadata.get('published', ''),
                'has_abstract': bool(result.description),
                'has_pdf': 'pdf_path' in paper_info if paper_info else False
            }
        )
        
        if use_cache:
            self.cache.set(cache_key, analysis_result.to_dict())
        
        print(f"[PaperAnalyzer] 分析完成，置信度: {analysis_result.confidence}")
        
        return analysis_result
    
    def batch_analyze(
        self,
        results: List[SearchResult],
        analysis_depth: str = 'deep',
        delay: float = 1.0
    ) -> List[AnalysisResult]:
        """
        批量分析论文
        
        Args:
            results: 搜索结果列表
            analysis_depth: 分析深度
            delay: 分析间隔（秒）
            
        Returns:
            List[AnalysisResult]: 分析结果列表
        """
        analyses = []
        
        for i, result in enumerate(results, 1):
            print(f"\n[PaperAnalyzer] 批量分析 {i}/{len(results)}")
            
            try:
                analysis = self.analyze(result, analysis_depth)
                analyses.append(analysis)
                
                import time
                if i < len(results):
                    time.sleep(delay)
                    
            except Exception as e:
                print(f"[PaperAnalyzer] 分析失败: {e}")
                continue
        
        return analyses
    
    def _fetch_paper_info(self, result: SearchResult) -> Optional[Dict]:
        """
        获取论文信息
        
        Args:
            result: 搜索结果
            
        Returns:
            Optional[Dict]: 论文信息
        """
        if result.source == 'arxiv':
            return self.fetcher.fetch_arxiv_paper(result.url, download_pdf=False)
        
        elif result.source == 'paperswithcode':
            if result.metadata.get('arxiv_id'):
                arxiv_url = f"https://arxiv.org/abs/{result.metadata['arxiv_id']}"
                return self.fetcher.fetch_arxiv_paper(arxiv_url, download_pdf=False)
        
        return None
    
    def _build_analysis_prompt(
        self,
        result: SearchResult,
        paper_info: Optional[Dict],
        analysis_depth: str
    ) -> str:
        """
        构建分析提示词
        
        Args:
            result: 搜索结果
            paper_info: 论文信息
            analysis_depth: 分析深度
            
        Returns:
            str: 提示词
        """
        depth_instructions = {
            'shallow': '请进行简要分析，重点关注论文的基本信息和主要贡献。',
            'medium': '请进行中等深度分析，重点关注论文的研究方法和创新点。',
            'deep': '请进行深度分析，全面评估论文的学术价值、创新性和应用前景。'
        }
        
        authors = result.metadata.get('authors', [])
        authors_str = ', '.join(authors[:5]) if authors else 'Unknown'
        
        prompt = f"""请分析以下学术论文：

论文信息：
- 标题：{result.title}
- 作者：{authors_str}
- 发表时间：{result.metadata.get('published', 'Unknown')}
- 来源：{result.source}
- URL：{result.url}

"""

        if result.description:
            prompt += f"""
摘要：
{result.description}

"""
        
        if paper_info and paper_info.get('abstract'):
            prompt += f"""
详细摘要：
{paper_info['abstract'][:1500]}

"""
        
        prompt += f"""
{depth_instructions.get(analysis_depth, depth_instructions['deep'])}

请以JSON格式返回分析结果，包含以下字段：
{{
    "summary": "论文概述（2-3句话）",
    "key_findings": ["关键发现1", "关键发现2", "关键发现3"],
    "technical_points": ["技术贡献1", "技术贡献2", "技术贡献3"],
    "recommendations": ["建议1", "建议2", "建议3"],
    "confidence": 0.85
}}
"""
        
        return prompt
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一位资深的学术研究专家，擅长分析学术论文的研究价值、创新性和应用前景。

你的分析应该：
1. 准确理解论文的核心贡献
2. 评估研究方法的科学性和创新性
3. 识别论文的学术价值和实际应用价值
4. 提供有针对性的建议和评价

请确保分析结果具有学术性和专业性。"""
    
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
        return f"PaperAnalyzer(llm={self.llm.api_provider})"


def test_paper_analyzer():
    """测试论文分析器"""
    print("\n=== 测试论文分析器 ===\n")
    
    analyzer = PaperAnalyzer()
    print(f"1. 初始化: {analyzer}")
    
    test_result = SearchResult(
        id='arxiv-test-001',
        title='Attention Is All You Need',
        source='arxiv',
        url='https://arxiv.org/abs/1706.03762',
        description='The dominant sequence transduction models are based on complex recurrent or convolutional neural networks...',
        metadata={
            'authors': ['Ashish Vaswani', 'Noam Shazeer', 'Niki Parmar'],
            'published': '2017-06-12',
            'arxiv_id': '1706.03762'
        },
        tags=['transformer', 'attention', 'nlp']
    )
    
    print(f"\n2. 测试论文: {test_result.title}")
    
    analysis = analyzer.analyze(test_result, analysis_depth='shallow')
    
    print(f"\n3. 分析结果:")
    print(f"   概述: {analysis.summary}")
    print(f"   关键发现: {analysis.key_findings[:2]}")
    print(f"   技术贡献: {analysis.technical_points[:2]}")
    print(f"   置信度: {analysis.confidence}")
    
    stats = analyzer.get_stats()
    print(f"\n4. 统计信息:")
    print(f"   LLM调用次数: {stats['llm_stats']['call_count']}")
    
    print("\n✅ 测试完成")


if __name__ == '__main__':
    test_paper_analyzer()
