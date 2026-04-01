"""
论文搜寻器

提供arXiv和Papers With Code的论文搜索功能
整合到统一的搜索层架构中
"""

import os
import sys
import time
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from intelligent_research_assistant.core.data_models import SearchResult
from intelligent_research_assistant.core.llm_manager import LLMManager
from intelligent_research_assistant.core.cache_manager import CacheManager
from intelligent_research_assistant.core.config_manager import ConfigManager


class ArxivAdapter:
    """arXiv数据源适配器"""
    
    def __init__(self):
        self.base_url = "http://export.arxiv.org/api/query"
    
    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """
        搜索arXiv论文
        
        Args:
            query: 搜索查询
            limit: 结果数量限制
            
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        results = []
        
        try:
            params = {
                'search_query': f'all:{query}',
                'start': 0,
                'max_results': min(limit, 100),
                'sortBy': 'relevance',
                'sortOrder': 'descending'
            }
            
            response = requests.get(
                self.base_url,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            
            ns = {
                'atom': 'http://www.w3.org/2005/Atom',
                'arxiv': 'http://arxiv.org/schemas/atom'
            }
            
            entries = root.findall('atom:entry', ns)
            
            for entry in entries[:limit]:
                title_elem = entry.find('atom:title', ns)
                title = title_elem.text.strip() if title_elem is not None else ''
                
                summary_elem = entry.find('atom:summary', ns)
                summary = summary_elem.text.strip() if summary_elem is not None else ''
                
                link_elem = entry.find('atom:id', ns)
                url = link_elem.text if link_elem is not None else ''
                
                published_elem = entry.find('atom:published', ns)
                published = published_elem.text if published_elem is not None else ''
                
                authors = []
                author_elems = entry.findall('atom:author', ns)
                for author_elem in author_elems:
                    name_elem = author_elem.find('atom:name', ns)
                    if name_elem is not None:
                        authors.append(name_elem.text)
                
                categories = []
                category_elems = entry.findall('atom:category', ns)
                for cat_elem in category_elems:
                    term = cat_elem.get('term')
                    if term:
                        categories.append(term)
                
                arxiv_id = url.split('/')[-1] if url else ''
                
                result = SearchResult(
                    id=f"arxiv-{arxiv_id}",
                    title=title,
                    source='arxiv',
                    url=url,
                    description=summary[:500] if summary else '',
                    metadata={
                        'authors': authors,
                        'published': published,
                        'categories': categories,
                        'arxiv_id': arxiv_id,
                        'pdf_url': f"http://arxiv.org/pdf/{arxiv_id}" if arxiv_id else ''
                    },
                    score=self._calculate_score(published),
                    tags=categories
                )
                results.append(result)
                
        except Exception as e:
            print(f"[ArxivAdapter] 搜索失败: {e}")
        
        return results
    
    def _calculate_score(self, published: str) -> float:
        """计算论文评分"""
        try:
            if published:
                pub_date = datetime.fromisoformat(published.replace('Z', '+00:00'))
                days_since = (datetime.now(pub_date.tzinfo) - pub_date).days
                
                if days_since < 30:
                    return 95.0
                elif days_since < 90:
                    return 85.0
                elif days_since < 180:
                    return 75.0
                elif days_since < 365:
                    return 65.0
                else:
                    return 55.0
        except:
            pass
        
        return 60.0
    
    def get_paper_by_id(self, arxiv_id: str) -> Optional[SearchResult]:
        """
        通过ID获取论文
        
        Args:
            arxiv_id: arXiv ID
            
        Returns:
            Optional[SearchResult]: 论文信息
        """
        try:
            params = {
                'search_query': f'id:{arxiv_id}',
                'max_results': 1
            }
            
            response = requests.get(
                self.base_url,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            entry = root.find('atom:entry', ns)
            if entry is None:
                return None
            
            title_elem = entry.find('atom:title', ns)
            title = title_elem.text.strip() if title_elem is not None else ''
            
            summary_elem = entry.find('atom:summary', ns)
            summary = summary_elem.text.strip() if summary_elem is not None else ''
            
            link_elem = entry.find('atom:id', ns)
            url = link_elem.text if link_elem is not None else ''
            
            published_elem = entry.find('atom:published', ns)
            published = published_elem.text if published_elem is not None else ''
            
            authors = []
            author_elems = entry.findall('atom:author', ns)
            for author_elem in author_elems:
                name_elem = author_elem.find('atom:name', ns)
                if name_elem is not None:
                    authors.append(name_elem.text)
            
            return SearchResult(
                id=f"arxiv-{arxiv_id}",
                title=title,
                source='arxiv',
                url=url,
                description=summary[:500] if summary else '',
                metadata={
                    'authors': authors,
                    'published': published,
                    'arxiv_id': arxiv_id,
                    'pdf_url': f"http://arxiv.org/pdf/{arxiv_id}"
                },
                score=self._calculate_score(published)
            )
            
        except Exception as e:
            print(f"[ArxivAdapter] 获取论文失败: {e}")
            return None


class PapersWithCodePaperAdapter:
    """Papers With Code论文适配器"""
    
    def __init__(self):
        self.base_url = "https://paperswithcode.com/api/v1"
    
    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """
        搜索Papers With Code论文
        
        Args:
            query: 搜索查询
            limit: 结果数量限制
            
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        results = []
        
        try:
            params = {
                'q': query,
                'page': 1,
                'items_per_page': min(limit, 50)
            }
            
            response = requests.get(
                f"{self.base_url}/papers/",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            for item in data.get('results', [])[:limit]:
                result = SearchResult(
                    id=f"pwc-{item.get('id', '')}",
                    title=item.get('title', ''),
                    source='paperswithcode',
                    url=item.get('url_abs', ''),
                    description=item.get('abstract', '')[:500] if item.get('abstract') else '',
                    metadata={
                        'authors': item.get('authors', []),
                        'published': item.get('published', ''),
                        'conference': item.get('conference', ''),
                        'arxiv_id': item.get('arxiv_id', ''),
                        'github_url': item.get('github', ''),
                        'pdf_url': item.get('url_pdf', '')
                    },
                    score=75.0,
                    tags=item.get('tasks', [])
                )
                results.append(result)
                
        except Exception as e:
            print(f"[PapersWithCodePaperAdapter] 搜索失败: {e}")
        
        return results


class PaperFinder:
    """
    论文搜寻器
    
    功能：
    - 多平台搜索（arXiv, Papers With Code）
    - 缓存支持
    - 结果排序和过滤
    """
    
    def __init__(self):
        """初始化论文搜寻器"""
        self.llm = LLMManager.get_instance()
        self.cache = CacheManager()
        self.config = ConfigManager.get_instance()
        
        self.adapters = {
            'arxiv': ArxivAdapter(),
            'paperswithcode': PapersWithCodePaperAdapter()
        }
    
    def search(
        self,
        query: str,
        sources: List[str] = None,
        limit: int = 50,
        use_cache: bool = True
    ) -> List[SearchResult]:
        """
        搜索论文
        
        Args:
            query: 搜索查询
            sources: 数据源列表
            limit: 结果数量限制
            use_cache: 是否使用缓存
            
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        if sources is None:
            sources = ['arxiv', 'paperswithcode']
        
        cache_key = f"paper_search:{query}:{','.join(sorted(sources))}:{limit}"
        
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                print(f"[PaperFinder] 使用缓存结果")
                return [SearchResult.from_dict(r) for r in cached]
        
        print(f"[PaperFinder] 搜索论文: {query}")
        print(f"  数据源: {', '.join(sources)}")
        print(f"  限制: {limit}")
        
        all_results = []
        
        for source in sources:
            if source in self.adapters:
                if not self.config.is_platform_enabled(source):
                    print(f"  跳过禁用的数据源: {source}")
                    continue
                
                print(f"  正在搜索 {source}...")
                
                try:
                    adapter = self.adapters[source]
                    results = adapter.search(query, limit)
                    all_results.extend(results)
                    print(f"    找到 {len(results)} 个结果")
                    
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"    搜索失败: {e}")
                    continue
        
        all_results.sort(key=lambda x: x.score, reverse=True)
        results = all_results[:limit]
        
        if use_cache and results:
            self.cache.set(
                cache_key,
                [r.to_dict() for r in results],
                metadata={'query': query, 'sources': sources}
            )
        
        print(f"\n[PaperFinder] 搜索完成，共 {len(results)} 个结果")
        
        return results
    
    def search_by_keywords(
        self,
        keywords: List[str],
        sources: List[str] = None,
        limit: int = 50
    ) -> List[SearchResult]:
        """
        通过关键词列表搜索
        
        Args:
            keywords: 关键词列表
            sources: 数据源列表
            limit: 结果数量限制
            
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        all_results = []
        seen_urls = set()
        
        for keyword in keywords:
            if len(all_results) >= limit:
                break
            
            results = self.search(
                query=keyword,
                sources=sources,
                limit=min(20, limit - len(all_results))
            )
            
            for result in results:
                if result.url not in seen_urls:
                    seen_urls.add(result.url)
                    all_results.append(result)
        
        all_results.sort(key=lambda x: x.score, reverse=True)
        return all_results[:limit]
    
    def get_paper_by_arxiv_id(self, arxiv_id: str) -> Optional[SearchResult]:
        """
        通过arXiv ID获取论文
        
        Args:
            arxiv_id: arXiv ID
            
        Returns:
            Optional[SearchResult]: 论文信息
        """
        cache_key = f"arxiv_paper:{arxiv_id}"
        cached = self.cache.get(cache_key)
        if cached:
            return SearchResult.from_dict(cached)
        
        adapter = self.adapters.get('arxiv')
        if not isinstance(adapter, ArxivAdapter):
            return None
        
        result = adapter.get_paper_by_id(arxiv_id)
        
        if result:
            self.cache.set(cache_key, result.to_dict())
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            dict: 统计信息
        """
        return {
            'available_sources': list(self.adapters.keys()),
            'enabled_sources': [
                s for s in self.adapters.keys()
                if self.config.is_platform_enabled(s)
            ],
            'cache_stats': self.cache.get_stats()
        }
    
    def __repr__(self):
        return f"PaperFinder(sources={list(self.adapters.keys())})"


def test_paper_finder():
    """测试论文搜寻器"""
    print("\n=== 测试论文搜寻器 ===\n")
    
    finder = PaperFinder()
    print(f"1. 初始化: {finder}")
    
    results = finder.search(
        query='machine learning',
        sources=['arxiv'],
        limit=5,
        use_cache=False
    )
    
    print(f"\n2. 搜索结果 ({len(results)} 个):")
    for i, result in enumerate(results, 1):
        print(f"  [{i}] {result.title[:60]}...")
        print(f"      URL: {result.url}")
        print(f"      Score: {result.score}")
        print(f"      Authors: {', '.join(result.metadata.get('authors', [])[:3])}")
    
    stats = finder.get_stats()
    print(f"\n3. 统计信息:")
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n✅ 测试完成")


if __name__ == '__main__':
    test_paper_finder()
