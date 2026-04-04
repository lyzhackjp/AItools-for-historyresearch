"""
Stage 1: 搜集材料

使用 HistoryFieldExplorer 搜集学术文献
增强：EmbeddingManager 语义重排 + 多源并行搜索

依赖模块：
    modules.history_field_explorer.HistoryFieldExplorer
    modules.embedding_manager.EmbeddingManager
    intelligent_research_assistant.search.paper_finder.PaperFinder
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
        self.embedding_manager = None

    def _create_explorer(self):
        """延迟创建 explorer（避免循环导入时初始化失败）"""
        if self.explorer is None:
            from modules.history_field_explorer import create_explorer
            self.explorer = create_explorer(
                language=self.project.language,
                test_mode=False
            )
        return self.explorer

    def _get_embedding_manager(self):
        """延迟创建 EmbeddingManager（暂不使用，改用 LLM 语义重排）"""
        # EmbeddingManager.__init__ 内部 import transformers 会触发 HuggingFace 连接
        # 在网络不通环境下会卡死。暂用 LLM 做语义重排替代
        self.embedding_manager = None
        return None

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

        explorer = self._create_explorer()

        try:
            explorer.explore(
                self.project.topic,
                search_limit=search_limit
            )
        except Exception as e:
            print(f"[Stage 1] Exploration 失败: {e}")
            self.project.mark_stage_failed(self.STAGE_NUM, str(e))
            return []

        report = explorer.report

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

        # ── 语义重排（使用 LLM，网终不通时自动降级）─────────────
        if len(papers) > 3 and self.project.language != 'ja':
            papers = self._semantic_rerank_llm(papers)

        # 按 score 降序
        papers.sort(key=lambda p: p.score, reverse=True)

        self.project.literature = papers
        self.project.mark_stage_done(self.STAGE_NUM)

        print(f"[Stage 1] 完成！搜集到 {len(papers)} 篇文献")
        for p in papers[:3]:
            print(f"  - [{p.source}] {p.title[:60]} ({p.year})")

        return papers

    def _semantic_rerank_llm(self, papers: List[PaperRecord]) -> List[PaperRecord]:
        """
        使用 LLM 对论文进行语义重排（EmbeddingManager 不可用时的替代方案）

        让与研究主题最相关的论文排在前面
        """
        try:
            topic = self.project.topic
            print(f"[Stage 1] 语义重排（LLM）: {len(papers)} 篇论文")

            if len(papers) <= 1:
                return papers

            titles_str = '\n'.join(
                f"{i+1}. {p.title} ({', '.join(p.authors[:2]) if p.authors else 'Unknown'}, {p.year or 'n.d.'})"
                for i, p in enumerate(papers)
            )

            prompt = f"""Research topic: {topic}

Rank these academic papers by relevance to the research topic (most relevant first).
Return ONLY a JSON array of paper numbers, no explanation.
Example: [3, 1, 4, 2]

Papers:
{titles_str}

Ranking (JSON):"""

            from modules.llm_client import create_llm_client
            llm = create_llm_client({'provider': 'dashscope'})
            result = llm._call_llm(prompt, max_tokens=500)

            response = result.get('content', '') if isinstance(result, dict) else (result or '')

            import re, json
            match = re.search(r'\[\d+(?:,\s*\d+)*\]', response)
            if not match:
                print(f"[Stage 1] LLM 重排解析失败，保持原顺序")
                return papers

            ranking = json.loads(match.group())

            id_to_paper = {p.id: p for p in papers}
            reranked = []
            seen = set()
            for idx in ranking:
                paper = papers[idx - 1] if 0 < idx <= len(papers) else None
                if paper and paper.id not in seen:
                    reranked.append(paper)
                    seen.add(paper.id)

            for p in papers:
                if p.id not in seen:
                    reranked.append(p)
                    seen.add(p.id)

            print(f"[Stage 1] 语义重排完成，前3篇: {[p.title[:40] for p in reranked[:3]]}")
            return reranked

        except Exception as e:
            print(f"[Stage 1] LLM 语义重排失败: {e}，保持原顺序")
            return papers

    def _normalize_authors(self, author_field) -> List[str]:
        """将各种格式的 author 字段规范化为 list[str]"""
        if not author_field:
            return []
        if isinstance(author_field, list):
            return [str(a).strip() for a in author_field if a]
        if isinstance(author_field, str):
            authors = []
            for sep in [';', '，', ',']:
                if sep in author_field:
                    authors = [a.strip() for a in author_field.split(sep) if a.strip()]
                    break
            return authors if authors else [author_field.strip()]
        return [str(author_field)]
