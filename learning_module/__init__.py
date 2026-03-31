"""
学习模块 - Learning Module

该模块提供学术资源自动检索、文献分析和技术要点提取功能，
帮助其他模块进行功能改进和优化。

功能特性：
- 学术资源自动检索与信息提取
- 研究文献分析与技术要点提取
- 基于既有研究成果的模块功能改进建议生成

使用方法：
    from learning_module import LearningModule
    
    learner = LearningModule(api_provider='qwen')
    analysis = learner.analyze_and_suggest(module_name='ner_processor', context='日文史料处理')

注意：
    OpenSourceFinder 模块已独立为 open_source_finder 包，
    请使用：from open_source_finder import OpenSourceFinder
"""

from .src.research_analyzer import ResearchAnalyzer
from .src.literature_analyzer import LiteratureAnalyzer
from .src.improvement_generator import ImprovementGenerator

__version__ = "1.0.0"
__all__ = [
    "ResearchAnalyzer",
    "LiteratureAnalyzer",
    "ImprovementGenerator",
    "LearningModule"
]


class LearningModule:
    """学习模块主类，整合所有学习功能"""

    def __init__(self, api_provider='qwen', api_key=None, test_mode=False):
        """
        初始化学习模块

        Args:
            api_provider: API服务商 ('qwen', 'openai', 'zhipu')
            api_key: API密钥（可选，将从环境变量读取）
            test_mode: 测试模式开关
        """
        self.api_provider = api_provider
        self.test_mode = test_mode

        self.research_analyzer = ResearchAnalyzer(api_provider, test_mode)
        self.literature_analyzer = LiteratureAnalyzer(api_provider, test_mode)
        self.improvement_generator = ImprovementGenerator(api_provider, test_mode)

    def analyze_and_suggest(
        self,
        module_name: str,
        context: str,
        research_topic: str = None
    ) -> dict:
        """
        综合分析和生成改进建议

        Args:
            module_name: 模块名称
            context: 应用上下文
            research_topic: 研究主题（可选）

        Returns:
            dict: 包含研究和改进建议的字典
        """
        if research_topic is None:
            research_topic = module_name

        research_findings = self.research_analyzer.search_research(research_topic)

        literature_insights = self.literature_analyzer.analyze_literature(
            summary=research_findings.get('summary', ''),
            key_findings=research_findings.get('key_findings', [])
        )

        improvements = self.improvement_generator.generate_improvements(
            module_name=module_name,
            context=context,
            research_findings=research_findings,
            literature_insights=literature_insights
        )

        return {
            'research_findings': research_findings,
            'literature_insights': literature_insights,
            'improvements': improvements,
            'module_name': module_name,
            'context': context,
            'research_topic': research_topic
        }

    def suggest_prompt_optimization(
        self,
        current_prompt: str,
        task_type: str
    ) -> dict:
        """
        提示词优化建议

        Args:
            current_prompt: 当前提示词
            task_type: 任务类型

        Returns:
            dict: 优化建议
        """
        return self.improvement_generator.suggest_prompt_optimization(
            current_prompt=current_prompt,
            task_type=task_type
        )
