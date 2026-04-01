"""
项目搜寻器

提供GitHub和Papers With Code的项目搜索功能
整合到统一的搜索层架构中
"""

import os
import sys
import time
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from intelligent_research_assistant.core.data_models import SearchResult
from intelligent_research_assistant.core.llm_manager import LLMManager
from intelligent_research_assistant.core.cache_manager import CacheManager
from intelligent_research_assistant.core.config_manager import ConfigManager


class GitHubAdapter:
    """GitHub数据源适配器"""
    
    def __init__(self, token: Optional[str] = None):
        self.base_url = "https://api.github.com"
        self.token = token or os.getenv('GITHUB_TOKEN')
        self.headers = {}
        if self.token:
            self.headers['Authorization'] = f'token {self.token}'
    
    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """
        搜索GitHub项目
        
        Args:
            query: 搜索查询
            limit: 结果数量限制
            
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        results = []
        
        try:
            params = {
                'q': f'{query} language:python',
                'sort': 'stars',
                'order': 'desc',
                'per_page': min(limit, 100)
            }
            
            response = requests.get(
                f"{self.base_url}/search/repositories",
                headers=self.headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            for item in data.get('items', [])[:limit]:
                result = SearchResult(
                    id=f"github-{item.get('id', '')}",
                    title=item.get('name', ''),
                    source='github',
                    url=item.get('html_url', ''),
                    description=item.get('description', ''),
                    metadata={
                        'stars': item.get('stargazers_count', 0),
                        'forks': item.get('forks_count', 0),
                        'watchers': item.get('watchers_count', 0),
                        'issues': item.get('open_issues_count', 0),
                        'language': item.get('language', ''),
                        'license': item.get('license', {}).get('name', '') if item.get('license') else '',
                        'topics': item.get('topics', []),
                        'created_at': item.get('created_at', ''),
                        'updated_at': item.get('updated_at', '')
                    },
                    score=self._calculate_score(item),
                    tags=item.get('topics', [])
                )
                results.append(result)
                
        except Exception as e:
            print(f"[GitHubAdapter] 搜索失败: {e}")
        
        return results
    
    def _calculate_score(self, item: Dict) -> float:
        """计算项目评分"""
        stars = item.get('stargazers_count', 0)
        forks = item.get('forks_count', 0)
        watchers = item.get('watchers_count', 0)
        
        stars_score = min(stars / 10000, 1.0) * 40
        forks_score = min(forks / 2000, 1.0) * 35
        watchers_score = min(watchers / 5000, 1.0) * 25
        
        return round(stars_score + forks_score + watchers_score, 2)
    
    def get_readme(self, owner: str, repo: str) -> Optional[str]:
        """
        获取README内容
        
        Args:
            owner: 仓库所有者
            repo: 仓库名称
            
        Returns:
            Optional[str]: README内容
        """
        try:
            response = requests.get(
                f"{self.base_url}/repos/{owner}/{repo}/readme",
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            import base64
            content = base64.b64decode(data['content']).decode('utf-8')
            return content
            
        except Exception as e:
            print(f"[GitHubAdapter] 获取README失败: {e}")
            return None


class PapersWithCodeAdapter:
    """Papers With Code数据源适配器"""
    
    def __init__(self):
        self.base_url = "https://paperswithcode.com/api/v1"
    
    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """
        搜索Papers With Code项目
        
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
                    description=item.get('abstract', ''),
                    metadata={
                        'authors': item.get('authors', []),
                        'published': item.get('published', ''),
                        'conference': item.get('conference', ''),
                        'arxiv_id': item.get('arxiv_id', '')
                    },
                    score=75.0,
                    tags=item.get('tasks', [])
                )
                results.append(result)
                
        except Exception as e:
            print(f"[PapersWithCodeAdapter] 搜索失败: {e}")
        
        return results


class ProjectFinder:
    """
    项目搜寻器
    
    功能：
    - 多平台搜索（GitHub, Papers With Code）
    - 缓存支持
    - 结果排序和过滤
    """
    
    def __init__(self):
        """初始化项目搜寻器"""
        self.llm = LLMManager.get_instance()
        self.cache = CacheManager()
        self.config = ConfigManager.get_instance()
        
        self.adapters = {
            'github': GitHubAdapter(),
            'paperswithcode': PapersWithCodeAdapter()
        }
    
    def search(
        self,
        query: str,
        platforms: List[str] = None,
        limit: int = 50,
        use_cache: bool = True
    ) -> List[SearchResult]:
        """
        搜索项目
        
        Args:
            query: 搜索查询
            platforms: 平台列表
            limit: 结果数量限制
            use_cache: 是否使用缓存
            
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        if platforms is None:
            platforms = ['github', 'paperswithcode']
        
        cache_key = f"project_search:{query}:{','.join(sorted(platforms))}:{limit}"
        
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                print(f"[ProjectFinder] 使用缓存结果")
                return [SearchResult.from_dict(r) for r in cached]
        
        print(f"[ProjectFinder] 搜索项目: {query}")
        print(f"  平台: {', '.join(platforms)}")
        print(f"  限制: {limit}")
        
        all_results = []
        
        for platform in platforms:
            if platform in self.adapters:
                if not self.config.is_platform_enabled(platform):
                    print(f"  跳过禁用的平台: {platform}")
                    continue
                
                print(f"  正在搜索 {platform}...")
                
                try:
                    adapter = self.adapters[platform]
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
                metadata={'query': query, 'platforms': platforms}
            )
        
        print(f"\n[ProjectFinder] 搜索完成，共 {len(results)} 个结果")
        
        return results
    
    def search_by_keywords(
        self,
        keywords: List[str],
        platforms: List[str] = None,
        limit: int = 50
    ) -> List[SearchResult]:
        """
        通过关键词列表搜索
        
        Args:
            keywords: 关键词列表
            platforms: 平台列表
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
                platforms=platforms,
                limit=min(20, limit - len(all_results))
            )
            
            for result in results:
                if result.url not in seen_urls:
                    seen_urls.add(result.url)
                    all_results.append(result)
        
        all_results.sort(key=lambda x: x.score, reverse=True)
        return all_results[:limit]
    
    def get_project_readme(self, result: SearchResult) -> Optional[str]:
        """
        获取项目README
        
        Args:
            result: 搜索结果
            
        Returns:
            Optional[str]: README内容
        """
        if result.source != 'github':
            return None
        
        parts = result.url.rstrip('/').split('/')
        if len(parts) < 5:
            return None
        
        owner = parts[-2]
        repo = parts[-1]
        
        cache_key = f"github_readme:{owner}/{repo}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        adapter = self.adapters.get('github')
        if not isinstance(adapter, GitHubAdapter):
            return None
        
        readme = adapter.get_readme(owner, repo)
        
        if readme:
            self.cache.set(cache_key, readme)
        
        return readme
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            dict: 统计信息
        """
        return {
            'available_platforms': list(self.adapters.keys()),
            'enabled_platforms': [
                p for p in self.adapters.keys()
                if self.config.is_platform_enabled(p)
            ],
            'cache_stats': self.cache.get_stats()
        }
    
    def __repr__(self):
        return f"ProjectFinder(platforms={list(self.adapters.keys())})"


def test_project_finder():
    """测试项目搜寻器"""
    print("\n=== 测试项目搜寻器 ===\n")
    
    finder = ProjectFinder()
    print(f"1. 初始化: {finder}")
    
    results = finder.search(
        query='machine learning',
        platforms=['github'],
        limit=5,
        use_cache=False
    )
    
    print(f"\n2. 搜索结果 ({len(results)} 个):")
    for i, result in enumerate(results, 1):
        print(f"  [{i}] {result.title}")
        print(f"      URL: {result.url}")
        print(f"      Score: {result.score}")
        print(f"      Stars: {result.metadata.get('stars', 0)}")
    
    stats = finder.get_stats()
    print(f"\n3. 统计信息:")
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n✅ 测试完成")


if __name__ == '__main__':
    test_project_finder()
