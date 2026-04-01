"""
核心层

提供统一的基础服务：
- LLM管理器
- 缓存管理器
- 配置管理器
- 数据模型
"""

from .llm_manager import LLMManager
from .cache_manager import CacheManager
from .config_manager import ConfigManager
from .data_models import SearchResult, AnalysisResult, Report

__all__ = [
    "LLMManager",
    "CacheManager",
    "ConfigManager",
    "SearchResult",
    "AnalysisResult",
    "Report"
]
