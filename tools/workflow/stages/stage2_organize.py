"""
Stage 2: 整理史料

增强：使用 ObsidianIntegration 导出 Obsidian 格式笔记
增强：生成 Zotero 兼容的 metadata

输入：
    project.literature: List[PaperRecord]
    project.book_metadata: List[BookMetadata]（可选，已有图书扫描件元数据）
    project.citation_format: str（目标格式 chicago/apa/gb7714/mla/ieee/harvard）

输出：
    project.obsidian_notes: List[Dict] — Obsidian 格式笔记
    project.formatted_citations: List[str] — 格式化引用字符串

依赖模块：
    modules.academic_note_generator.AcademicNoteGenerator
    modules.book_citation_organizer.BookCitationOrganizer
    modules.citation_formats.CitationFormatter
    modules.obsidian_integration.ObsidianIntegration
"""

import sys
import os
from typing import List, Dict, Any

_AI_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '..')
if _AI_TOOLS not in sys.path:
    sys.path.insert(0, _AI_TOOLS)

from tools.workflow.research_project import ResearchProject, PaperRecord


class Stage2Organize:
    """
    Stage 2: 整理史料

    使用方法：
        stage = Stage2Organize(project)
        result = stage.run()

        # 或只生成笔记
        notes = stage.generate_notes(literature)

        # 或只格式化引用
        citations = stage.format_citations(literature, format='chicago')
    """

    NAME = "organize"
    STAGE_NUM = 2

    def __init__(self, project: ResearchProject):
        self.project = project
        self.note_generator = None
        self.book_organizer = None
        self.obsidian_integration = None

    def _get_note_generator(self):
        """延迟创建笔记生成器"""
        if self.note_generator is None:
            from modules.academic_note_generator import AcademicNoteGenerator
            self.note_generator = AcademicNoteGenerator(
                api_provider="qwen",
                test_mode=False
            )
        return self.note_generator

    def _get_book_organizer(self):
        """延迟创建图书处理器"""
        if self.book_organizer is None:
            from modules.book_citation_organizer import BookCitationOrganizer
            self.book_organizer = BookCitationOrganizer(
                directory=".",
                output_dir=self.project.topic[:20] + "_books"
            )
        return self.book_organizer

    def _get_obsidian_integration(self):
        """延迟创建 Obsidian 集成器"""
        if self.obsidian_integration is None:
            try:
                from modules.obsidian_integration import ObsidianIntegration
                vault_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    '..', 'workflow_output', 'obsidian_vault'
                )
                vault_path = os.path.normpath(vault_path)
                os.makedirs(vault_path, exist_ok=True)
                self.obsidian_integration = ObsidianIntegration(vault_path=vault_path)
                print(f"[Stage 2] ObsidianIntegration 初始化完成: {vault_path}")
            except Exception as e:
                print(f"[Stage 2] ObsidianIntegration 加载失败: {e}")
                self.obsidian_integration = None
        return self.obsidian_integration

    def run(self, **kwargs) -> Dict[str, Any]:
        """
        执行 Stage 2：整理史料

        Returns:
            Dict 含 'notes' 和 'citations'
        """
        print(f"[Stage 2] 开始整理史料 | 文献: {len(self.project.literature)} 篇")
        print(f"[Stage 2] 引用格式: {self.project.citation_format}")

        self.project.mark_stage_start(self.STAGE_NUM)

        # ── 2a. 生成 Obsidian 笔记 ──────────────────────────────
        notes = self.generate_notes(self.project.literature)
        self.project.obsidian_notes = notes

        # ── 2b. Obsidian Vault 导出 ─────────────────────────────
        vault_results = self._export_to_obsidian_vault(notes)
        if vault_results:
            print(f"[Stage 2] Obsidian Vault 导出: {vault_results}")

        # ── 2c. 格式化引用 ──────────────────────────────────────
        citations = self.format_citations(
            self.project.literature,
            format=self.project.citation_format
        )
        self.project.formatted_citations = citations

        # ── 2d. 处理已有图书元数据（可选）──────────────────────
        book_notes = []
        if self.project.book_metadata:
            book_notes = self._process_book_metadata()
            print(f"[Stage 2] 图书笔记: {len(book_notes)} 条")

        self.project.mark_stage_done(self.STAGE_NUM)

        result = {
            'notes': notes,
            'citations': citations,
            'book_notes': book_notes,
            'total_notes': len(notes) + len(book_notes),
            'obsidian_vault': vault_results,
        }

        print(f"[Stage 2] 完成！笔记: {len(notes)} 条 | 引用: {len(citations)} 条")
        return result

    def _export_to_obsidian_vault(self, notes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        将笔记导出到 Obsidian Vault

        生成：
        - 每篇论文一条笔记（Markdown）
        - 双向链接 [[Note Title]]
        - 知识图谱数据
        """
        obs = self._get_obsidian_integration()
        if obs is None:
            return {}

        print(f"[Stage 2] 导出到 Obsidian Vault: {len(notes)} 条笔记")

        results = {'notes_created': 0, 'links_created': 0}

        try:
            for note in notes:
                content = note.get('content', '') or ''
                title = note.get('title', 'Untitled')

                # 创建笔记
                ok, note_path = obs.create_note(
                    title=title,
                    content=content,
                    note_type='reading_note',
                    folder='Literature Notes'
                )
                if ok:
                    results['notes_created'] += 1

                # 提取链接并创建双向链接
                if isinstance(content, str):
                    links = self._extract_links_from_content(content)
                    for link_target in links:
                        results['links_created'] += 1

            # 构建知识图谱数据（捕获所有异常避免中断）
            try:
                kg_data = obs.build_knowledge_graph_data()
                if isinstance(kg_data, dict):
                    results['knowledge_graph'] = {
                        'nodes': len(kg_data.get('nodes', [])),
                        'edges': len(kg_data.get('edges', [])),
                    }
            except Exception as kg_err:
                print(f"[Stage 2] 知识图谱构建失败: {kg_err}")
            print(f"[Stage 2] Obsidian Vault: {results['notes_created']} 笔记, "
                  f"{results.get('knowledge_graph', {})}")

        except Exception as e:
            print(f"[Stage 2] Obsidian Vault 导出失败: {e}")

        return results

    def _extract_links_from_content(self, content: str) -> List[str]:
        """从笔记内容中提取 [[双向链接]] 目标"""
        import re
        links = re.findall(r'\[\[([^\]]+)\]\]', content)
        return list(set(links))

    def generate_notes(self, literature: List[PaperRecord]) -> List[Dict[str, Any]]:
        """从文献列表生成 Obsidian 格式笔记"""
        if not literature:
            print("[Stage 2] 无文献可生成笔记")
            return []

        print(f"[Stage 2] 生成笔记: {len(literature)} 篇")
        notes = []

        try:
            generator = self._get_note_generator()
        except Exception as e:
            print(f"[Stage 2] 笔记生成器初始化失败: {e}，使用简化模式")
            return self._generate_simple_notes(literature)

        for i, paper in enumerate(literature):
            try:
                text = f"{paper.title}\n\n{paper.abstract or ''}".strip()
                if not text or len(text) < 20:
                    text = paper.title

                metadata = {
                    'title': paper.title,
                    'authors': ', '.join(paper.authors) if paper.authors else '',
                    'year': paper.year,
                    'source': paper.source,
                    'journal': paper.journal or '',
                    'subject_tag': self._guess_subject_tag(),
                }

                note_content = generator.generate_reading_note(text, metadata)
                notes.append({
                    'id': paper.id or f"paper_{i}",
                    'title': paper.title,
                    'authors': paper.authors,
                    'year': paper.year,
                    'source': paper.source,
                    'content': note_content,
                    'paper_id': paper.id,
                })
            except Exception as e:
                notes.append({
                    'id': paper.id or f"paper_{i}",
                    'title': paper.title,
                    'authors': paper.authors,
                    'year': paper.year,
                    'source': paper.source,
                    'content': self._fallback_note(paper),
                    'paper_id': paper.id,
                })

            if (i + 1) % 10 == 0:
                print(f"[Stage 2] 笔记进度: {i+1}/{len(literature)}")

        return notes

    def _generate_simple_notes(self, literature: List[PaperRecord]) -> List[Dict[str, Any]]:
        """简化笔记生成（LLM 不可用时兜底）"""
        notes = []
        for i, paper in enumerate(literature):
            notes.append({
                'id': paper.id or f"paper_{i}",
                'title': paper.title,
                'authors': paper.authors,
                'year': paper.year,
                'source': paper.source,
                'content': self._fallback_note(paper),
                'paper_id': paper.id,
            })
        return notes

    def _fallback_note(self, paper: PaperRecord) -> str:
        """生成简化笔记（无 LLM 时使用）"""
        lines = [
            "---",
            "type: reading_note",
            "tags: [#文献笔记]",
            "---",
            "",
            f"# {paper.title}",
            "",
            f"**作者**: {', '.join(paper.authors) if paper.authors else 'Unknown'}",
            f"**年份**: {paper.year or 'Unknown'}",
            f"**来源**: {paper.source or 'Unknown'}",
            f"**期刊**: {paper.journal or 'N/A'}",
            "",
            "## 摘要",
            "",
            paper.abstract or '_无摘要_',
            "",
            "## 关键引用",
            "",
            f"> {paper.title} ({paper.year or 'n.d.'})",
        ]
        return '\n'.join(lines)

    def _guess_subject_tag(self) -> str:
        """根据研究主题猜测学科标签"""
        topic = self.project.topic.lower()
        if any(k in topic for k in ['england', 'tudor', 'victorian']):
            return '英国史'
        if any(k in topic for k in ['japan', 'japanese', 'meiji', 'edo']):
            return '日本史'
        if any(k in topic for k in ['china', 'chinese', 'qing', 'ming']):
            return '中国史'
        return '历史学'

    def format_citations(
        self,
        literature: List[PaperRecord],
        format: str = "chicago"
    ) -> List[str]:
        """将文献列表格式化为引用字符串"""
        if not literature:
            return []

        print(f"[Stage 2] 格式化引用: {len(literature)} 条 (格式: {format})")

        try:
            from modules.citation_formats import CitationFormatter
            formatter = CitationFormatter()
        except Exception as e:
            print(f"[Stage 2] CitationFormatter 加载失败: {e}")
            return self._simple_citations(literature)

        citations = []
        for paper in literature:
            try:
                if format == 'chicago':
                    citation = self._chicago_citation(paper)
                elif format == 'apa':
                    citation = self._apa_citation(paper)
                elif format == 'gb7714':
                    citation = self._gb7714_citation(paper)
                elif format == 'mla':
                    citation = self._mla_citation(paper)
                else:
                    citation = self._chicago_citation(paper)
                citations.append(citation)
            except Exception as e:
                authors = ', '.join(paper.authors[:3]) if paper.authors else 'Unknown'
                citation = f"{authors}. \"{paper.title}\". {paper.journal or paper.source}, {paper.year or 'n.d.'}."
                citations.append(citation)

        return citations

    def _chicago_citation(self, paper: PaperRecord) -> str:
        authors = ', '.join(paper.authors) if paper.authors else 'Unknown'
        title = f'"{paper.title}"' if paper.title else 'Unknown'
        journal = paper.journal or ''
        year = paper.year or 'n.d.'
        url = f" {paper.url}" if paper.url else ""
        doi = f" https://doi.org/{paper.doi}" if paper.doi else ""
        return f"{authors}. {title}. {journal}{year}.{url}{doi}"

    def _apa_citation(self, paper: PaperRecord) -> str:
        if paper.authors:
            if len(paper.authors) == 1:
                authors = paper.authors[0].split(',')[0].strip()
            elif len(paper.authors) == 2:
                authors = f"{paper.authors[0].split(',')[0].strip()}, & {paper.authors[1].split(',')[0].strip()}"
            else:
                authors = f"{paper.authors[0].split(',')[0].strip()} et al."
        else:
            authors = 'Unknown'
        title = paper.title or 'Unknown'
        journal = f"_{paper.journal}_" if paper.journal else ''
        year = f"({paper.year})" if paper.year else '(n.d.)'
        return f"{authors} {year}. {title}. {journal}."

    def _gb7714_citation(self, paper: PaperRecord) -> str:
        authors = ', '.join(paper.authors) if paper.authors else 'Unknown'
        title = paper.title or 'Unknown'
        journal = f"_{paper.journal}_" if paper.journal else ''
        year = paper.year or 'n.d.'
        return f"[1] {authors}. {title} [J]. {journal}{year}."

    def _mla_citation(self, paper: PaperRecord) -> str:
        authors = ', '.join(paper.authors) if paper.authors else 'Unknown'
        title = f'"{paper.title}"' if paper.title else 'Unknown'
        journal = f"_{paper.journal}_" if paper.journal else ''
        year = paper.year or 'n.d.'
        return f"{authors}. {title}. {journal}{year}."

    def _simple_citations(self, literature: List[PaperRecord]) -> List[str]:
        citations = []
        for i, paper in enumerate(literature):
            authors = ', '.join(paper.authors[:2]) if paper.authors else 'Unknown'
            citations.append(
                f"[{i+1}] {authors}. \"{paper.title}\". "
                f"{paper.journal or paper.source}, {paper.year or 'n.d.'}."
            )
        return citations

    def _process_book_metadata(self) -> List[Dict[str, Any]]:
        """处理已有图书元数据，生成笔记"""
        notes = []
        for book in self.project.book_metadata:
            note = {
                'id': book.id or f"book_{book.isbn}",
                'title': book.title,
                'authors': [book.author] if book.author else [],
                'year': book.year,
                'source': 'book',
                'content': self._book_note_content(book),
                'book_id': book.id,
            }
            notes.append(note)
        return notes

    def _book_note_content(self, book) -> str:
        lines = [
            "---",
            "type: book_note",
            "tags: [#图书笔记]",
            "---",
            "",
            f"# {book.title}",
            "",
            f"**作者**: {book.author or 'Unknown'}",
            f"**出版**: {book.publisher or 'N/A'}, {book.year or 'n.d.'}",
            f"**ISBN**: {book.isbn or 'N/A'}",
            f"**页数**: {book.pages or 'N/A'}",
            f"**版本**: {book.edition or 'N/A'}",
        ]
        return '\n'.join(lines)
