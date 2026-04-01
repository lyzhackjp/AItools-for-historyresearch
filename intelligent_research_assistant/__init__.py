"""
智能研究助手模块

整合OpenSourceFinder和LearningModule的统一模块
提供开源项目搜索、学术文献分析、报告生成等一站式服务

功能特性：
- 多平台搜索（GitHub, arXiv, Papers With Code）
- 项目与论文深度分析
- 学术文献研究
- 智能报告生成
- 改进建议生成

使用方法：
    from intelligent_research_assistant import IntelligentResearchAssistant
    
    assistant = IntelligentResearchAssistant(api_provider='qwen')
    result = assistant.analyze_module_optimization(
        module_name='ocr_processor',
        context='日文史料OCR识别'
    )
"""

__version__ = "1.0.0"
__all__ = [
    "IntelligentResearchAssistant",
    "SearchResult",
    "AnalysisResult",
    "Report",
    "LLMManager",
    "CacheManager",
    "ConfigManager"
]

from .core.llm_manager import LLMManager
from .core.cache_manager import CacheManager
from .core.config_manager import ConfigManager
from .core.data_models import SearchResult, AnalysisResult, Report
from .intelligent_assistant import IntelligentResearchAssistant
