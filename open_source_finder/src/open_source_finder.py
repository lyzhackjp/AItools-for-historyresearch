"""
开源模块搜索与优化整合器

在 GitHub 和 HuggingFace 上搜索相关的开源模块，
评估其质量和适用性，生成优化整合报告，并执行优化工作。

功能特性：
- GitHub 仓库搜索与爬取
- HuggingFace 模型搜索
- 仓库/模型质量评估与排序
- 优化整合报告生成
- 自动优化代码执行
"""

import requests
import json
import re
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class GitHubRepo:
    """GitHub 仓库信息"""
    name: str
    full_name: str
    description: str
    stars: int
    forks: int
    language: str
    url: str
    readme: str = ""
    topics: List[str] = field(default_factory=list)
    last_updated: str = ""
    issues: int = 0
    watchers: int = 0
    license: str = ""
    score: float = 0.0


@dataclass
class HuggingFaceModel:
    """HuggingFace 模型信息"""
    model_id: str
    author: str
    model_name: str
    description: str
    downloads: int
    likes: int
    tags: List[str] = field(default_factory=list)
    pipeline_tag: str = ""
    created_at: str = ""
    last_modified: str = ""
    private: bool = False
    datasets: List[str] = field(default_factory=list)
    paper_url: str = ""
    score: float = 0.0


@dataclass
class SearchResult:
    """搜索结果汇总"""
    github_repos: List[GitHubRepo] = field(default_factory=list)
    huggingface_models: List[HuggingFaceModel] = field(default_factory=list)
    search_keywords: List[str] = field(default_factory=list)
    total_github_results: int = 0
    total_huggingface_results: int = 0


@dataclass
class IntegrationReport:
    """优化整合报告"""
    summary: str
    github_recommendations: List[Dict[str, Any]] = field(default_factory=list)
    huggingface_recommendations: List[Dict[str, Any]] = field(default_factory=list)
    integration_suggestions: List[Dict[str, Any]] = field(default_factory=list)
    code_improvements: List[Dict[str, Any]] = field(default_factory=list)
    priority_actions: List[str] = field(default_factory=list)
    estimated_effort: Dict[str, str] = field(default_factory=dict)


class OpenSourceFinder:
    """开源模块搜索与优化整合器"""

    def __init__(self, api_provider='qwen', test_mode=False, github_token: Optional[str] = None):
        """
        初始化开源模块搜索器

        Args:
            api_provider: LLM API 服务商 ('qwen', 'openai', 'zhipu')
            test_mode: 测试模式开关
            github_token: GitHub 个人访问令牌（可选，提高 API 限制）
        """
        self.api_provider = api_provider
        self.test_mode = test_mode
        self.github_token = github_token
        self.client = None
        self.llm_available = False

        if not test_mode:
            self._init_llm_client()

    def _init_llm_client(self):
        """初始化 LLM 客户端"""
        try:
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from modules.llm_client import LLMClient

            provider_map = {
                'qwen': 'dashscope',
                'openai': 'openai',
                'zhipu': 'zhipu',
                'deepseek': 'deepseek',
                'ollama': 'ollama'
            }
            provider = provider_map.get(self.api_provider, 'dashscope')
            config = {'provider': provider}
            self.client = LLMClient(config)
            self.llm_available = True
        except ImportError:
            print("警告: 无法导入 LLM 客户端，将使用基础评估模式")
            self.llm_available = False

    def search_all(self, module_name: str, context: str, keywords: List[str] = None) -> SearchResult:
        """
        在所有平台搜索相关开源模块

        Args:
            module_name: 模块名称（如 'ocr_processor', 'ner_processor'）
            context: 应用上下文（用于生成搜索关键词）
            keywords: 额外的搜索关键词

        Returns:
            SearchResult: 搜索结果汇总
        """
        if keywords is None:
            keywords = self._generate_keywords(module_name, context)

        print(f"搜索关键词: {keywords}")

        github_results = []
        hf_results = []

        for keyword in keywords[:3]:
            print(f"正在搜索: {keyword}")

            github_repos = self.search_github(keyword, limit=10)
            github_results.extend(github_repos)

            hf_models = self.search_huggingface(keyword, limit=10)
            hf_results.extend(hf_models)

            time.sleep(1)

        github_results = self._deduplicate_github(github_results)
        hf_results = self._deduplicate_huggingface(hf_results)

        return SearchResult(
            github_repos=github_results,
            huggingface_models=hf_results,
            search_keywords=keywords,
            total_github_results=len(github_results),
            total_huggingface_results=len(hf_results)
        )

    def search_github(self, query: str, limit: int = 10, language: str = "python") -> List[GitHubRepo]:
        """
        在 GitHub 上搜索仓库

        Args:
            query: 搜索关键词
            limit: 返回结果数量限制
            language: 编程语言过滤

        Returns:
            List[GitHubRepo]: GitHub 仓库列表
        """
        if self.test_mode:
            return self._get_test_github_results(query)

        url = "https://api.github.com/search/repositories"
        headers = {}
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'

        params = {
            'q': f'{query} language:{language}',
            'sort': 'stars',
            'order': 'desc',
            'per_page': min(limit, 100)
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            repos = []
            for item in data.get('items', [])[:limit]:
                readme = self._fetch_readme(item['full_name'])

                repo = GitHubRepo(
                    name=item.get('name', ''),
                    full_name=item.get('full_name', ''),
                    description=item.get('description', ''),
                    stars=item.get('stargazers_count', 0),
                    forks=item.get('forks_count', 0),
                    language=item.get('language', ''),
                    url=item.get('html_url', ''),
                    readme=readme,
                    topics=item.get('topics', []),
                    last_updated=item.get('updated_at', ''),
                    issues=item.get('open_issues_count', 0),
                    watchers=item.get('watchers_count', 0),
                    license=item.get('license', {}).get('name', '') if item.get('license') else ''
                )
                repo.score = self._calculate_github_score(repo)
                repos.append(repo)

            return repos

        except requests.exceptions.RequestException as e:
            print(f"GitHub 搜索失败: {e}")
            return []

    def _fetch_readme(self, full_name: str) -> str:
        """获取仓库的 README 内容"""
        headers = {}
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'

        url = f"https://api.github.com/repos/{full_name}/readme"

        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                import base64
                content = response.json().get('content', '')
                if content:
                    decoded = base64.b64decode(content).decode('utf-8', errors='ignore')
                    return decoded[:2000]
        except Exception:
            pass

        return ""

    def search_huggingface(self, query: str, limit: int = 10) -> List[HuggingFaceModel]:
        """
        在 HuggingFace 上搜索模型

        Args:
            query: 搜索关键词
            limit: 返回结果数量限制

        Returns:
            List[HuggingFaceModel]: HuggingFace 模型列表
        """
        if self.test_mode:
            return self._get_test_huggingface_results(query)

        url = "https://huggingface.co/api/models"
        headers = {"Accept": "application/json"}

        params = {
            'search': query,
            'sort': 'downloads',
            'direction': -1,
            'limit': limit,
            'full': 'true'
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            models = []
            for item in data[:limit]:
                model = HuggingFaceModel(
                    model_id=item.get('id', ''),
                    author=item.get('author', ''),
                    model_name=item.get('modelId', '').split('/')[-1],
                    description=item.get('description', ''),
                    downloads=item.get('downloads', 0),
                    likes=item.get('likes', 0),
                    tags=item.get('tags', []),
                    pipeline_tag=item.get('pipeline_tag', ''),
                    created_at=item.get('createdAt', ''),
                    last_modified=item.get('lastModified', ''),
                    private=item.get('private', False),
                    datasets=item.get('datasets', []),
                    paper_url=item.get('paper', '') or ''
                )
                model.score = self._calculate_huggingface_score(model)
                models.append(model)

            return models

        except requests.exceptions.RequestException as e:
            print(f"HuggingFace 搜索失败: {e}")
            return []

    def _calculate_github_score(self, repo: GitHubRepo) -> float:
        """
        计算 GitHub 仓库的综合评分

        评分维度：
        - Stars (权重: 40%)
        - Forks (权重: 20%)
        - 最近更新时间 (权重: 15%)
        - Issues 数量 (权重: 10%)
        - 主题匹配度 (权重: 15%)
        """
        stars_score = min(repo.stars / 1000, 1.0) * 40
        forks_score = min(repo.forks / 200, 1.0) * 20
        watchers_score = min(repo.watchers / 500, 1.0) * 15

        issues_score = 0
        if repo.issues > 0 and repo.issues < 100:
            issues_score = (1 - repo.issues / 100) * 10

        topic_score = 0
        if repo.topics:
            topic_score = min(len(repo.topics) / 5, 1.0) * 15

        total_score = stars_score + forks_score + watchers_score + issues_score + topic_score
        return round(total_score, 2)

    def _calculate_huggingface_score(self, model: HuggingFaceModel) -> float:
        """
        计算 HuggingFace 模型的综合评分

        评分维度：
        - Downloads (权重: 50%)
        - Likes (权重: 30%)
        - 主题匹配度 (权重: 20%)
        """
        downloads_score = min(model.downloads / 100000, 1.0) * 50
        likes_score = min(model.likes / 1000, 1.0) * 30

        tag_score = 0
        if model.tags:
            tag_score = min(len(model.tags) / 10, 1.0) * 20

        total_score = downloads_score + likes_score + tag_score
        return round(total_score, 2)

    def rank_and_filter(self, results: SearchResult, min_stars: int = 50, min_downloads: int = 1000) -> SearchResult:
        """
        对搜索结果进行排序和过滤

        Args:
            results: 搜索结果
            min_stars: GitHub 仓库最小 stars 数
            min_downloads: HuggingFace 模型最小下载数

        Returns:
            SearchResult: 过滤和排序后的结果
        """
        filtered_repos = [r for r in results.github_repos if r.stars >= min_stars]
        filtered_repos.sort(key=lambda x: x.score, reverse=True)

        filtered_models = [m for m in results.huggingface_models if m.downloads >= min_downloads]
        filtered_models.sort(key=lambda x: x.score, reverse=True)

        return SearchResult(
            github_repos=filtered_repos[:20],
            huggingface_models=filtered_models[:20],
            search_keywords=results.search_keywords,
            total_github_results=len(filtered_repos),
            total_huggingface_results=len(filtered_models)
        )

    def generate_integration_report(
        self,
        results: SearchResult,
        module_name: str,
        context: str
    ) -> IntegrationReport:
        """
        生成优化整合报告

        Args:
            results: 搜索结果
            module_name: 目标模块名称
            context: 应用上下文

        Returns:
            IntegrationReport: 优化整合报告
        """
        if not self.llm_available:
            return self._generate_basic_report(results, module_name, context)

        from .prompts import OPENSOURCE_ANALYSIS_SYSTEM_PROMPT, OPENSOURCE_ANALYSIS_USER_PROMPT

        github_context = self._format_github_results(results.github_repos[:10])
        huggingface_context = self._format_huggingface_results(results.huggingface_models[:10])

        prompt = OPENSOURCE_ANALYSIS_USER_PROMPT.format(
            module_name=module_name,
            context=context,
            github_results=github_context,
            huggingface_results=huggingface_context
        )

        try:
            response = self._call_llm(prompt, system_prompt=OPENSOURCE_ANALYSIS_SYSTEM_PROMPT)
            return self._parse_report_response(response, results)
        except Exception as e:
            print(f"LLM 分析失败: {e}")
            return self._generate_basic_report(results, module_name, context)

    def _call_llm(self, prompt: str, system_prompt: str = None) -> str:
        """调用 LLM 的统一接口"""
        if not self.client:
            raise Exception("LLM 客户端未初始化")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat(messages)
            return response if isinstance(response, str) else response.get('content', '')
        except Exception as e:
            print(f"LLM 调用失败: {e}")
            raise

    def _format_github_results(self, repos: List[GitHubRepo]) -> str:
        """格式化 GitHub 结果为文本"""
        if not repos:
            return "未找到相关仓库"

        lines = []
        for i, repo in enumerate(repos[:10], 1):
            lines.append(f"\n{i}. {repo.full_name}")
            lines.append(f"   ⭐ Stars: {repo.stars} | Fork: {repo.forks} | Language: {repo.language}")
            lines.append(f"   📝 {repo.description or '无描述'}")
            lines.append(f"   🔗 {repo.url}")
            if repo.topics:
                lines.append(f"   🏷️ Topics: {', '.join(repo.topics[:5])}")

        return "\n".join(lines)

    def _format_huggingface_results(self, models: List[HuggingFaceModel]) -> str:
        """格式化 HuggingFace 结果为文本"""
        if not models:
            return "未找到相关模型"

        lines = []
        for i, model in enumerate(models[:10], 1):
            lines.append(f"\n{i}. {model.model_name}")
            lines.append(f"   📥 Downloads: {model.downloads:,} | ❤️ Likes: {model.likes}")
            lines.append(f"   📝 {model.description or '无描述'}")
            lines.append(f"   🔗 https://huggingface.co/{model.model_id}")
            if model.pipeline_tag:
                lines.append(f"   🏷️ Pipeline: {model.pipeline_tag}")
            if model.tags:
                relevant_tags = [t for t in model.tags if t not in ['pytorch', 'tensorflow', 'jax']]
                if relevant_tags:
                    lines.append(f"   Tags: {', '.join(relevant_tags[:5])}")

        return "\n".join(lines)

    def _parse_report_response(self, response: str, results: SearchResult) -> IntegrationReport:
        """解析 LLM 生成的报告"""
        recommendations = self._extract_recommendations(response, 'github', results.github_repos)
        hf_recommendations = self._extract_recommendations(response, 'huggingface', results.huggingface_models)

        return IntegrationReport(
            summary=self._extract_summary(response),
            github_recommendations=recommendations,
            huggingface_recommendations=hf_recommendations,
            integration_suggestions=self._extract_integration_suggestions(response),
            code_improvements=self._extract_code_improvements(response),
            priority_actions=self._extract_priority_actions(response),
            estimated_effort=self._extract_effort_estimate(response)
        )

    def _extract_recommendations(self, text: str, source: str, items: list) -> List[Dict[str, Any]]:
        """从文本中提取推荐项"""
        recommendations = []
        pattern = rf'{source.upper() if source == "github" else "HF"}.*?(?:推荐|建议|最佳).*?(?={source.upper()}|##|\Z)'
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)

        for i, item in enumerate(items[:5]):
            rec = {
                'rank': i + 1,
                'name': getattr(item, 'full_name', '') or getattr(item, 'model_id', ''),
                'url': getattr(item, 'url', '') or f"https://huggingface.co/{getattr(item, 'model_id', '')}",
                'stars_downloads': getattr(item, 'stars', 0) or getattr(item, 'downloads', 0),
                'score': getattr(item, 'score', 0),
                'integration_difficulty': self._estimate_difficulty(item)
            }
            recommendations.append(rec)

        return recommendations

    def _extract_summary(self, text: str) -> str:
        """提取摘要"""
        summary_pattern = r'(?:摘要|总结|概述|概览)(.*?)(?=##|GitHub|HuggingFace|详细|$)'
        match = re.search(summary_pattern, text, re.DOTALL)
        return match.group(1).strip() if match else "基于搜索结果生成的分析报告"

    def _extract_integration_suggestions(self, text: str) -> List[Dict[str, Any]]:
        """提取整合建议"""
        suggestions = []
        patterns = [
            r'(?:整合|集成|接入).*?(?=\d+\.|##|$)',
            r'建议.*?(?:整合|集成|使用).*?(?=\d+\.|##|$)'
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                suggestions.append({
                    'suggestion': match.strip()[:200],
                    'priority': 'high' if '直接' in match or '立即' in match else 'medium'
                })

        return suggestions[:5]

    def _extract_code_improvements(self, text: str) -> List[Dict[str, Any]]:
        """提取代码改进建议"""
        improvements = []
        code_pattern = r'```[\w]*\n(.*?)```'
        matches = re.findall(code_pattern, text, re.DOTALL)

        for match in matches:
            improvements.append({
                'code': match.strip(),
                'description': '代码优化建议'
            })

        return improvements[:3]

    def _extract_priority_actions(self, text: str) -> List[str]:
        """提取优先级行动"""
        actions = []
        priority_pattern = r'(?:优先|首要|立即|快速).*?(?=\n|$)'
        matches = re.findall(priority_pattern, text, re.IGNORECASE)

        for match in matches:
            action = match.strip()
            if len(action) > 10:
                actions.append(action)

        return actions[:5] if actions else ['审查推荐的仓库和模型', '评估整合可行性', '制定实施计划']

    def _extract_effort_estimate(self, text: str) -> Dict[str, str]:
        """提取工作量估算"""
        effort = {}

        effort_patterns = [
            (r'(?:快速|短期|简单).*?(?:天|周)', 'short'),
            (r'(?:中期|中等).*?(?:周|月)', 'medium'),
            (r'(?:长期|复杂).*?(?:月|季度)', 'long')
        ]

        for pattern, level in effort_patterns:
            match = re.search(pattern, text)
            if match:
                effort[level] = match.group()

        if not effort:
            effort = {'short': '1-2周', 'medium': '1个月', 'long': '2-3个月'}

        return effort

    def _estimate_difficulty(self, item) -> str:
        """估算整合难度"""
        stars = getattr(item, 'stars', 0)
        downloads = getattr(item, 'downloads', 0)

        if stars > 5000 or downloads > 50000:
            return 'easy'
        elif stars > 1000 or downloads > 10000:
            return 'medium'
        else:
            return 'hard'

    def _generate_basic_report(self, results: SearchResult, module_name: str, context: str) -> IntegrationReport:
        """生成基础报告（当 LLM 不可用时）"""
        top_github = results.github_repos[:5] if results.github_repos else []
        top_huggingface = results.huggingface_models[:5] if results.huggingface_models else []

        github_recs = [
            {
                'rank': i + 1,
                'name': repo.full_name,
                'url': repo.url,
                'stars_downloads': repo.stars,
                'score': repo.score,
                'integration_difficulty': self._estimate_difficulty(repo)
            }
            for i, repo in enumerate(top_github)
        ]

        hf_recs = [
            {
                'rank': i + 1,
                'name': model.model_id,
                'url': f"https://huggingface.co/{model.model_id}",
                'stars_downloads': model.downloads,
                'score': model.score,
                'integration_difficulty': self._estimate_difficulty(model)
            }
            for i, model in enumerate(top_huggingface)
        ]

        return IntegrationReport(
            summary=f"基于{module_name}模块的{context}，搜索到{len(top_github)}个相关GitHub仓库和{len(top_huggingface)}个相关HuggingFace模型。",
            github_recommendations=github_recs,
            huggingface_recommendations=hf_recs,
            integration_suggestions=[
                {'suggestion': '优先评估高星仓库的代码质量', 'priority': 'high'},
                {'suggestion': '测试HuggingFace模型的推理性能', 'priority': 'high'}
            ],
            code_improvements=[],
            priority_actions=[
                '审查推荐的GitHub仓库',
                '测试HuggingFace模型',
                '评估代码兼容性',
                '制定整合计划'
            ],
            estimated_effort={'short': '1-2周', 'medium': '1个月', 'long': '2-3个月'}
        )

    def execute_optimization(
        self,
        report: IntegrationReport,
        target_module_path: str,
        apply_changes: bool = False
    ) -> Dict[str, Any]:
        """
        根据报告执行优化工作

        Args:
            report: 优化整合报告
            target_module_path: 目标模块文件路径
            apply_changes: 是否直接应用更改

        Returns:
            Dict: 执行结果
        """
        results = {
            'status': 'pending',
            'changes_proposed': [],
            'changes_applied': [],
            'errors': []
        }

        for rec in report.github_recommendations[:3]:
            results['changes_proposed'].append({
                'type': 'github_integration',
                'source': rec['name'],
                'url': rec['url'],
                'description': f"集成 {rec['name']} 的相关功能"
            })

        for rec in report.huggingface_recommendations[:3]:
            results['changes_proposed'].append({
                'type': 'model_replacement',
                'source': rec['name'],
                'url': rec['url'],
                'description': f"使用 {rec['name']} 替换或增强现有功能"
            })

        if apply_changes and target_module_path:
            try:
                with open(target_module_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                backup_path = target_module_path + '.backup'
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                results['backup_path'] = backup_path

                for suggestion in report.code_improvements:
                    if suggestion.get('code'):
                        results['changes_applied'].append({
                            'code': suggestion['code'],
                            'status': 'proposed_only'
                        })

                results['status'] = 'completed'

            except Exception as e:
                results['status'] = 'error'
                results['errors'].append(str(e))

        return results

    def _generate_keywords(self, module_name: str, context: str) -> List[str]:
        """生成搜索关键词"""
        keywords = [module_name]

        keyword_mappings = {
            'ocr': ['ocr', 'text recognition', 'handwriting recognition', 'tesseract', 'easyocr', 'paddleocr'],
            'ner': ['ner', 'named entity recognition', 'entity extraction', 'spacy', 'huggingface ner'],
            'pdf': ['pdf processing', 'pdf extraction', 'pdf parsing', 'pdfminer'],
            'document': ['document processing', 'document parsing', 'text extraction'],
            'llm': ['llm', 'language model', 'text generation', 'chatgpt', 'openai'],
            'embedding': ['embedding', 'text embedding', 'sentence transformer', 'similarity'],
            'chatbot': ['chatbot', 'conversation ai', 'dialogue system', 'chatgpt']
        }

        module_lower = module_name.lower()
        for key, kws in keyword_mappings.items():
            if key in module_lower:
                keywords.extend(kws)
                break
        else:
            keywords.append(context.split()[0] if context else 'python')

        return list(set(keywords))[:5]

    def _deduplicate_github(self, repos: List[GitHubRepo]) -> List[GitHubRepo]:
        """去重 GitHub 结果"""
        seen = set()
        unique = []
        for repo in repos:
            if repo.full_name not in seen:
                seen.add(repo.full_name)
                unique.append(repo)
        return unique

    def _deduplicate_huggingface(self, models: List[HuggingFaceModel]) -> List[HuggingFaceModel]:
        """去重 HuggingFace 结果"""
        seen = set()
        unique = []
        for model in models:
            if model.model_id not in seen:
                seen.add(model.model_id)
                unique.append(model)
        return unique

    def _get_test_github_results(self, query: str) -> List[GitHubRepo]:
        """获取测试用的 GitHub 结果"""
        return [
            GitHubRepo(
                name=f"example-{query}-repo",
                full_name=f"testuser/example-{query}",
                description=f"An example repository for {query} with high stars",
                stars=2500,
                forks=300,
                language="Python",
                url=f"https://github.com/testuser/example-{query}",
                topics=[query, 'machine-learning', 'nlp'],
                score=85.5
            ),
            GitHubRepo(
                name=f"awesome-{query}",
                full_name=f"awesome/awesome-{query}",
                description=f"Awesome list for {query}",
                stars=1500,
                forks=150,
                language="Python",
                url=f"https://github.com/awesome/awesome-{query}",
                topics=[query, 'awesome-list'],
                score=72.0
            )
        ]

    def _get_test_huggingface_results(self, query: str) -> List[HuggingFaceModel]:
        """获取测试用的 HuggingFace 结果"""
        return [
            HuggingFaceModel(
                model_id=f"testuser/{query}-model",
                author="testuser",
                model_name=f"{query}-model",
                description=f"A powerful model for {query}",
                downloads=50000,
                likes=200,
                tags=[query, 'transformer', 'nlp'],
                pipeline_tag='text-generation',
                score=88.0
            ),
            HuggingFaceModel(
                model_id=f"testorg/{query}-base",
                author="testorg",
                model_name=f"{query}-base",
                description=f"Base model for {query} tasks",
                downloads=30000,
                likes=150,
                tags=[query, 'base-model'],
                pipeline_tag='fill-mask',
                score=75.0
            )
        ]

    def save_report(self, report: IntegrationReport, filepath: str):
        """保存报告到文件"""
        report_dict = {
            'summary': report.summary,
            'github_recommendations': report.github_recommendations,
            'huggingface_recommendations': report.huggingface_recommendations,
            'integration_suggestions': report.integration_suggestions,
            'code_improvements': report.code_improvements,
            'priority_actions': report.priority_actions,
            'estimated_effort': report.estimated_effort,
            'generated_at': datetime.now().isoformat()
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=2)

    def save_search_results(self, results: SearchResult, filepath: str):
        """保存搜索结果到文件"""
        results_dict = {
            'search_keywords': results.search_keywords,
            'total_github_results': results.total_github_results,
            'total_huggingface_results': results.total_huggingface_results,
            'github_repos': [
                {
                    'name': r.name,
                    'full_name': r.full_name,
                    'description': r.description,
                    'stars': r.stars,
                    'forks': r.forks,
                    'language': r.language,
                    'url': r.url,
                    'topics': r.topics,
                    'score': r.score
                }
                for r in results.github_repos
            ],
            'huggingface_models': [
                {
                    'model_id': m.model_id,
                    'model_name': m.model_name,
                    'description': m.description,
                    'downloads': m.downloads,
                    'likes': m.likes,
                    'tags': m.tags,
                    'pipeline_tag': m.pipeline_tag,
                    'score': m.score
                }
                for m in results.huggingface_models
            ]
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results_dict, f, ensure_ascii=False, indent=2)
