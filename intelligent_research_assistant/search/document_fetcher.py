"""
文档获取器

负责从各种平台下载和获取文档内容
支持GitHub README、arXiv论文PDF等
整合到统一的搜索层架构中
"""

import os
import sys
import re
import time
import base64
import requests
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from intelligent_research_assistant.core.data_models import SearchResult
from intelligent_research_assistant.core.cache_manager import CacheManager
from intelligent_research_assistant.core.config_manager import ConfigManager


class DocumentFetcher:
    """
    文档获取器
    
    功能：
    - 获取GitHub README
    - 获取arXiv论文PDF
    - 缓存支持
    - 本地存储管理
    """
    
    def __init__(self, storage_dir: str = None):
        """
        初始化文档获取器
        
        Args:
            storage_dir: 文档存储目录
        """
        self.cache = CacheManager()
        self.config = ConfigManager.get_instance()
        
        if storage_dir is None:
            storage_dir = os.path.join(
                os.path.dirname(__file__),
                '..',
                'storage',
                'documents'
            )
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        (self.storage_dir / 'readme').mkdir(exist_ok=True)
        (self.storage_dir / 'papers').mkdir(exist_ok=True)
        
        self.github_token = os.getenv('GITHUB_TOKEN')
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AI-History-Research-Tools/1.0',
            'Accept': 'application/json'
        })
        
        if self.github_token:
            self.session.headers.update({
                'Authorization': f'token {self.github_token}'
            })
    
    def fetch_github_readme(
        self,
        repo_url: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        获取GitHub项目的README文件
        
        Args:
            repo_url: GitHub仓库URL
            use_cache: 是否使用缓存
            
        Returns:
            dict: 包含README内容和元数据的字典
        """
        match = re.search(r'github\.com/([^/]+)/([^/]+)', repo_url)
        if not match:
            return {'error': 'Invalid GitHub URL', 'content': ''}
        
        owner, repo = match.groups()
        repo = repo.replace('.git', '').rstrip('/')
        
        cache_key = f"github_readme:{owner}/{repo}"
        
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                print(f"[DocumentFetcher] 使用缓存的README: {owner}/{repo}")
                return cached
        
        print(f"[DocumentFetcher] 获取README: {owner}/{repo}")
        
        api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        
        try:
            response = self.session.get(api_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            content = base64.b64decode(data['content']).decode('utf-8')
            
            readme_path = self.storage_dir / 'readme' / f"{owner}_{repo}_{datetime.now().strftime('%Y%m%d')}.md"
            
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            result = {
                'content': content,
                'path': str(readme_path),
                'size': data['size'],
                'sha': data['sha'],
                'url': data['html_url'],
                'owner': owner,
                'repo': repo,
                'cached': False
            }
            
            if use_cache:
                self.cache.set(cache_key, result, metadata={'source': 'github'})
            
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"[DocumentFetcher] 获取README失败: {e}")
            return {
                'error': str(e),
                'content': '',
                'path': ''
            }
    
    def fetch_arxiv_paper(
        self,
        arxiv_url: str,
        download_pdf: bool = True,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        获取arXiv论文信息和PDF
        
        Args:
            arxiv_url: arXiv论文URL
            download_pdf: 是否下载PDF文件
            use_cache: 是否使用缓存
            
        Returns:
            dict: 包含论文信息和PDF路径的字典
        """
        match = re.search(r'arxiv\.org/(abs|pdf)/(\d+\.\d+)', arxiv_url)
        if not match:
            return {'error': 'Invalid arXiv URL', 'content': ''}
        
        paper_id = match.group(2)
        
        cache_key = f"arxiv_paper:{paper_id}"
        
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                print(f"[DocumentFetcher] 使用缓存的论文: {paper_id}")
                return cached
        
        print(f"[DocumentFetcher] 获取论文: {paper_id}")
        
        api_url = f"http://export.arxiv.org/api/query?id_list={paper_id}"
        
        try:
            response = self.session.get(api_url, timeout=30)
            response.raise_for_status()
            
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            entry = root.find('atom:entry', ns)
            if entry is None:
                return {'error': 'Paper not found', 'content': ''}
            
            title = entry.find('atom:title', ns).text.strip()
            abstract = entry.find('atom:summary', ns).text.strip()
            
            authors = []
            for author in entry.findall('atom:author', ns):
                name = author.find('atom:name', ns).text
                authors.append(name)
            
            published = entry.find('atom:published', ns).text
            
            result = {
                'paper_id': paper_id,
                'title': title,
                'abstract': abstract,
                'authors': authors,
                'published': published,
                'url': f"https://arxiv.org/abs/{paper_id}",
                'pdf_url': f"http://arxiv.org/pdf/{paper_id}",
                'cached': False
            }
            
            if download_pdf:
                pdf_path = self._download_pdf(paper_id, result['pdf_url'])
                if pdf_path:
                    result['pdf_path'] = pdf_path
            
            if use_cache:
                self.cache.set(cache_key, result, metadata={'source': 'arxiv'})
            
            return result
            
        except Exception as e:
            print(f"[DocumentFetcher] 获取论文失败: {e}")
            return {
                'error': str(e),
                'content': ''
            }
    
    def _download_pdf(self, paper_id: str, pdf_url: str) -> Optional[str]:
        """
        下载PDF文件
        
        Args:
            paper_id: 论文ID
            pdf_url: PDF URL
            
        Returns:
            Optional[str]: PDF文件路径
        """
        try:
            print(f"[DocumentFetcher] 下载PDF: {paper_id}")
            
            response = self.session.get(pdf_url, timeout=60)
            response.raise_for_status()
            
            pdf_path = self.storage_dir / 'papers' / f"{paper_id}.pdf"
            
            with open(pdf_path, 'wb') as f:
                f.write(response.content)
            
            print(f"[DocumentFetcher] PDF已保存: {pdf_path}")
            return str(pdf_path)
            
        except Exception as e:
            print(f"[DocumentFetcher] 下载PDF失败: {e}")
            return None
    
    def fetch_document(
        self,
        result: SearchResult,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        根据搜索结果获取文档
        
        Args:
            result: 搜索结果
            use_cache: 是否使用缓存
            
        Returns:
            dict: 文档内容
        """
        if result.source == 'github':
            return self.fetch_github_readme(result.url, use_cache)
        
        elif result.source == 'arxiv':
            return self.fetch_arxiv_paper(result.url, download_pdf=True, use_cache=use_cache)
        
        elif result.source == 'paperswithcode':
            if result.metadata.get('arxiv_id'):
                arxiv_url = f"https://arxiv.org/abs/{result.metadata['arxiv_id']}"
                return self.fetch_arxiv_paper(arxiv_url, download_pdf=True, use_cache=use_cache)
            elif result.metadata.get('github_url'):
                return self.fetch_github_readme(result.metadata['github_url'], use_cache)
        
        return {
            'error': f"Unsupported source: {result.source}",
            'content': ''
        }
    
    def batch_fetch(
        self,
        results: List[SearchResult],
        delay: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        批量获取文档
        
        Args:
            results: 搜索结果列表
            delay: 请求间隔（秒）
            
        Returns:
            List[Dict]: 文档内容列表
        """
        documents = []
        
        for i, result in enumerate(results, 1):
            print(f"\n[DocumentFetcher] 批量获取 {i}/{len(results)}: {result.title[:50]}...")
            
            doc = self.fetch_document(result)
            documents.append(doc)
            
            if i < len(results):
                time.sleep(delay)
        
        return documents
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            dict: 统计信息
        """
        readme_files = list((self.storage_dir / 'readme').glob('*.md'))
        pdf_files = list((self.storage_dir / 'papers').glob('*.pdf'))
        
        total_size = sum(f.stat().st_size for f in readme_files + pdf_files)
        
        return {
            'storage_dir': str(self.storage_dir),
            'readme_count': len(readme_files),
            'pdf_count': len(pdf_files),
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'cache_stats': self.cache.get_stats()
        }
    
    def cleanup_old_files(self, days: int = 30):
        """
        清理旧文件
        
        Args:
            days: 保留天数
        """
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(days=days)
        count = 0
        
        for file_type in ['readme', 'papers']:
            for file_path in (self.storage_dir / file_type).glob('*'):
                if datetime.fromtimestamp(file_path.stat().st_mtime) < cutoff:
                    file_path.unlink()
                    count += 1
        
        print(f"[DocumentFetcher] 已清理 {count} 个旧文件")
    
    def __repr__(self):
        return f"DocumentFetcher(storage={self.storage_dir})"


def test_document_fetcher():
    """测试文档获取器"""
    print("\n=== 测试文档获取器 ===\n")
    
    fetcher = DocumentFetcher()
    print(f"1. 初始化: {fetcher}")
    
    readme = fetcher.fetch_github_readme(
        'https://github.com/python/cpython',
        use_cache=False
    )
    
    if 'error' not in readme:
        print(f"\n2. README获取成功:")
        print(f"   标题: {readme.get('repo', 'N/A')}")
        print(f"   大小: {readme.get('size', 0)} bytes")
        print(f"   内容预览: {readme.get('content', '')[:100]}...")
    else:
        print(f"\n2. README获取失败: {readme.get('error')}")
    
    paper = fetcher.fetch_arxiv_paper(
        'https://arxiv.org/abs/2301.07041',
        download_pdf=False,
        use_cache=False
    )
    
    if 'error' not in paper:
        print(f"\n3. 论文获取成功:")
        print(f"   标题: {paper.get('title', 'N/A')}")
        print(f"   作者: {', '.join(paper.get('authors', [])[:3])}")
        print(f"   摘要: {paper.get('abstract', '')[:100]}...")
    else:
        print(f"\n3. 论文获取失败: {paper.get('error')}")
    
    stats = fetcher.get_stats()
    print(f"\n4. 统计信息:")
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n✅ 测试完成")


if __name__ == '__main__':
    test_document_fetcher()
