"""
Stage 5: 撰写论文

使用 HistoryFieldExplorer.draft_paper() 生成研究论文

依赖模块：
    modules.history_field_explorer.HistoryFieldExplorer
"""

import sys
import os
from typing import Dict, Any

_AI_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '..')
if _AI_TOOLS not in sys.path:
    sys.path.insert(0, _AI_TOOLS)

from tools.workflow.research_project import ResearchProject


class Stage5Write:
    """
    Stage 5: 撰写论文

    使用方法：
        stage = Stage5Write(project)
        paper = stage.run(topic="Tudor England")
    """

    NAME = "write"
    STAGE_NUM = 5

    def __init__(self, project: ResearchProject, explorer=None):
        self.project = project
        self.explorer = explorer  # 接受 Stage1 共享的 explorer 实例

    def _get_or_create_explorer(self):
        """获取或创建 explorer（Stage 1 可能已创建）"""
        if self.explorer is None:
            from modules.history_field_explorer import create_explorer
            self.explorer = create_explorer(
                language=self.project.language,
                test_mode=False
            )
            # 复用 Stage 1 的 literature（如果有）
            if self.project.literature and self.explorer.report:
                print("[Stage 5] 复用 Stage 1 的 literature 数据")
        return self.explorer

    def run(self, topic: str = "", style: str = "academic_history") -> str:
        """
        执行 Stage 5：撰写论文

        Args:
            topic: 论文主题（默认使用 project.topic）
            style: 论文风格 academic_history / historiographical / source_analysis

        Returns:
            str: 论文全文（Markdown，含双语翻译）
        """
        topic = topic or self.project.topic
        print(f"[Stage 5] 开始撰写论文: {topic}")
        print(f"[Stage 5] 语言: {self.project.language} | 双语: {self.project.bilingual} | 风格: {style}")

        explorer = self._get_or_create_explorer()

        # 如果 report 没有 literature，重新探索
        if not explorer.report or not explorer.report.search_results_count:
            print("[Stage 5] Stage 1 数据未就绪，执行探索...")
            explorer.explore(topic, search_limit=40)

        result = explorer.draft_paper(
            topic=topic,
            language=self.project.language,
            bilingual=self.project.bilingual,
            style=style,
        )

        paper_text = result.get('full_text', '')
        self.project.paper_draft = paper_text
        self.project.mark_stage_done(self.STAGE_NUM)

        print(f"[Stage 5] 完成！论文长度: {len(paper_text)} 字符")
        return paper_text

    def save_paper(self, path: str = "") -> str:
        """保存论文到文件"""
        if not self.project.paper_draft:
            print("[Stage 5] 无论文草稿可保存")
            return ""

        import datetime
        if not path:
            ts = datetime.datetime.now().strftime('%Y-%m-%d')
            safe_topic = "".join(c if c.isalnum() else '_' for c in self.project.topic[:20])
            path = f"paper_{safe_topic}_{ts}.md"

        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.project.paper_draft)
        print(f"[Stage 5] 论文已保存: {path}")
        return path
