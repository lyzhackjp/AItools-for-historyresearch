"""
OpenSourceFinder - 源代码包

包含 OpenSourceFinder 的核心组件：
- OpenSourceFinder: 开源模块搜索与优化整合器
"""

from .open_source_finder import (
    OpenSourceFinder,
    GitHubRepo,
    HuggingFaceModel,
    SearchResult,
    IntegrationReport
)

__all__ = [
    "OpenSourceFinder",
    "GitHubRepo",
    "HuggingFaceModel",
    "SearchResult",
    "IntegrationReport"
]
