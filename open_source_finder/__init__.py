"""
OpenSourceFinder 模块

在 GitHub 和 HuggingFace 上搜索相关的开源模块，
评估其质量和适用性，生成优化整合报告，并执行优化工作。

功能特性：
- GitHub 仓库搜索与爬取
- HuggingFace 模型搜索
- 仓库/模型质量评估与排序
- 优化整合报告生成
- 自动优化代码执行

使用方法：
    from open_source_finder import OpenSourceFinder

    finder = OpenSourceFinder(api_provider='qwen', test_mode=True)
    results = finder.search_all(module_name='ocr_processor', context='日文OCR识别')
    report = finder.generate_integration_report(results, 'ocr_processor', '日文OCR')
    finder.save_report(report, 'optimization_report.json')

注意：
    LearningModule 模块已独立为 learning_module 包，
    请使用：from learning_module import LearningModule
"""

from .src.open_source_finder import (
    OpenSourceFinder,
    GitHubRepo,
    HuggingFaceModel,
    SearchResult,
    IntegrationReport
)

__version__ = "1.0.0"
__all__ = [
    "OpenSourceFinder",
    "GitHubRepo",
    "HuggingFaceModel",
    "SearchResult",
    "IntegrationReport"
]
