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
        """延迟创建 EmbeddingManager（语义重排用）"""
        if self.embedding_manager is None:
            try:
                from modules.embedding_manager import EmbeddingManager
                self.embedding_manager = EmbeddingManager(default_model='bge-m3')
                self.embedding_manager.load_embedding_model('bge-m3')
                print("[Stage 1] EmbeddingManager loaded for semantic reranking")
            except Exception as e:
                print(f"[Stage 1] EmbeddingManager 加载失败: {e}，跳过语义重排")
                self.embedding_manager = None
        return self.embedding_manager

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

        # ── 语义重排（使用 EmbeddingManager）────────────────────
        if len(papers) > 3 and self.project.language != 'ja':
            papers = self._semantic_rerank(papers)

        # 按 score 降序
        papers.sort(key=lambda p: p.score, reverse=True)

        self.project.literature = papers
        self.project.mark_stage_done(self.STAGE_NUM)

        print(f"[Stage 1] 完成！搜集到 {len(papers)} 篇文献")
        for p in papers[:3]:
            print(f"  - [{p.source}] {p.title[:60]} ({p.year})")

        return papers

    def _semantic_rerank(self, papers: List[PaperRecord]) -> List[PaperRecord]:
        """
        使用 EmbeddingManager 对论文进行语义重排

        让与研究主题最相关的论文排在前面
        """
        try:
            em = self._get_embedding_manager()
            if em is None:
                return papers

            topic = self.project.topic
            print(f"[Stage 1] 语义重排: {len(papers)} 篇论文")

            # 构建文档列表
            docs = []
            for p in papers:
                text = f"{p.title} {' '.join(p.authors)} {p.journal or ''} {p.abstract or ''}"
                docs.append({'id': p.id, 'text': text[:2000]})

            if not docs:
                return papers

            # 创建向量索引
            em.create_vector_index(docs)
            index_stats = em.get_index_stats()
            print(f"[Stage 1] 向量索引: {index_stats.get('document_count', 0)} 文档")

            # 语义搜索重排
            reranked = []
            seen_ids = set()

            # 前 3 篇：直接取语义搜索最相关的
            results = em.semantic_search(topic, top_k=min(5, len(papers)))
            for r in results:
                pid = r.get('id', '')
                if pid:
                    for p in papers:
                        if p.id == pid and pid not in seen_ids:
                            reranked.append(p)
                            seen_ids.add(pid)
                            break

            # 其余：按原 score 顺序补充
            for p in papers:
                if p.id not in seen_ids:
                    reranked.append(p)
                    seen_ids.add(p.id)

            print(f"[Stage 1] 语义重排完成，前3篇: {[p.title[:40] for p in reranked[:3]]}")
            return reranked

        except Exception as e:
            print(f"[Stage 1] 语义重排失败: {e}，保持原顺序")
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
