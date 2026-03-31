"""
Learning Module - 源代码包

包含学习模块的核心组件：
- ResearchAnalyzer: 学术资源检索分析器
- LiteratureAnalyzer: 文献分析器
- ImprovementGenerator: 改进建议生成器
"""

from .research_analyzer import ResearchAnalyzer
from .literature_analyzer import LiteratureAnalyzer
from .improvement_generator import ImprovementGenerator

__all__ = [
    "ResearchAnalyzer",
    "LiteratureAnalyzer",
    "ImprovementGenerator"
]
