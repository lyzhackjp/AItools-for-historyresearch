"""
Stage 1: 搜集材料

使用 HistoryFieldExplorer 搜集学术文献

依赖模块：
    modules.history_field_explorer.HistoryFieldExplorer
    intelligent_research_assistant.search.paper_finder.PaperFinder

实现功能：
- 多源搜索（CrossRef / arXiv / PapersWithCode）
- 去重与相关性过滤
- 论文元数据标准化
"""

import sys
import os
from typing import List, Dict, Any

# 确保 AItools 路径可用
_AI_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '..')
if _AI_TOOLS not in sys.path:
    sys.path.insert(0, _AI_TOOLS)

from tools.workflow.research_project import ResearchProject, PaperRecord


class Stage1Collect:
    """
    Stage 1: 搜集材料

    使用方法：
        stage = Stage1Collect(project)
        papers = stage.run(search_limit=60)
    """

    NAME = "collect"
    STAGE_NUM = 1

    def __init__(self, project: ResearchProject):
        self.project = project
        self.explorer = None

    def _create_explorer(self):
        """延迟创建 explorer（避免循环导入时初始化失败）"""
        if self.explorer is None:
            from modules.history_field_explorer import create_explorer
            self.explorer = create_explorer(
                language=self.project.language,
                test_mode=False
            )

    def run(self, search_limit: int = 60) -> List[PaperRecord]:
        """
        执行 Stage 1：搜集材料

        Args:
            search_limit: 各数据源返回上限（总计约 3x search_limit）

        Returns:
            List[PaperRecord]: 搜集到的文献列表
        """
        print(f"[Stage 1] 开始搜集材料: {self.project.topic}")
        print(f"[Stage 1] 语言: {self.project.language} | 搜索上限: {search_limit}")

        self._create_explorer()

        try:
            self.explorer.explore(
                self.project.topic,
                search_limit=search_limit
            )
        except Exception as e:
            print(f"[Stage 1] Exploration 失败: {e}")
            self.project.mark_stage_failed(self.STAGE_NUM, str(e))
            return []

        report = self.explorer.report

        # 收集论文（合并 classic_studies + frontier_research）
        paper_set = {}
        for lit_list in [report.classic_studies, report.frontier_research]:
            for lit in lit_list:
                pid = lit.get('id', '') or lit.get('title', '')[:80]
                if pid not in paper_set:
                    paper_set[pid] = PaperRecord(
                        id=pid,
                        title=lit.get('title', ''),
                        authors=self._normalize_authors(lit.get('author', '')),
                        year=str(lit.get('year', '')),
                        source=lit.get('source', 'unknown'),
                        url=lit.get('url', ''),
                        doi=lit.get('doi', ''),
                        abstract=lit.get('abstract', '') or lit.get('description', ''),
                        journal=lit.get('journal', ''),
                        score=float(lit.get('score', 0)),
                    )

        papers = list(paper_set.values())
        # 按 score 降序
        papers.sort(key=lambda p: p.score, reverse=True)

        self.project.literature = papers
        self.project.mark_stage_done(self.STAGE_NUM)

        print(f"[Stage 1] 完成！搜集到 {len(papers)} 篇文献")
        for p in papers[:3]:
            print(f"  - [{p.source}] {p.title[:60]} ({p.year})")

        return papers

    def _normalize_authors(self, author_field) -> List[str]:
        """将各种格式的 author 字段规范化为 list[str]"""
        if not author_field:
            return []
        if isinstance(author_field, list):
            return [str(a).strip() for a in author_field if a]
        if isinstance(author_field, str):
            # 尝试用逗号/分号分割
            authors = []
            for sep in [';', '，', ',']:
                if sep in author_field:
                    authors = [a.strip() for a in author_field.split(sep) if a.strip()]
                    break
            return authors if authors else [author_field.strip()]
        return [str(author_field)]
