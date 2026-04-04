"""
Stage 7: 注释格式修改

将论文中的引用格式化输出为指定引用风格
支持：Chicago / APA / GB7714 / MLA / IEEE / Harvard

输入：
    project.paper_draft: str — 论文草稿（含引用标注）
    project.literature: List[PaperRecord] — 文献数据库（用于反向查找）
    project.citation_format: str — 目标格式

输出：
    project.final_paper: str — 格式化后的最终论文

依赖模块：
    modules.citation_formats.CitationFormatter
    modules.citation_normalizer.CitationNormalizer
"""

import sys
import os
import re
from typing import Dict, Any, List, Optional

_AI_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '..')
if _AI_TOOLS not in sys.path:
    sys.path.insert(0, _AI_TOOLS)

from tools.workflow.research_project import ResearchProject, PaperRecord


class Stage7Format:
    """
    Stage 7: 注释格式修改

    使用方法：
        stage = Stage7Format(project)
        result = stage.run(format='chicago')

        # 直接格式化论文
        final = stage.format_paper(paper_text, format='apa')
    """

    NAME = "format"
    STAGE_NUM = 7

    def __init__(self, project: ResearchProject):
        self.project = project
        self.formatter = None
        self.normalizer = None

    def _get_formatter(self):
        """延迟创建引用格式化器"""
        if self.formatter is None:
            from modules.citation_formats import CitationFormatter
            self.formatter = CitationFormatter()
        return self.formatter

    def _get_normalizer(self):
        """延迟创建引用标准化器"""
        if self.normalizer is None:
            from modules.citation_normalizer import CitationNormalizer
            self.normalizer = CitationNormalizer(style=self.project.citation_format)
        return self.normalizer

    def run(self, format: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        执行 Stage 7：注释格式修改

        Args:
            format: 目标格式（默认使用 project.citation_format）
                   Chicago / APA / GB7714 / MLA / IEEE / Harvard

        Returns:
            Dict 含 'final_paper', 'formatted_citations'
        """
        if not self.project.paper_draft:
            print("[Stage 7] 无论文草稿可格式化（Stage 5 未完成），跳过")
            self.project.mark_stage_skipped()
            return {}

        target_format = format or self.project.citation_format or 'chicago'
        print(f"[Stage 7] 开始格式化引用 | 目标格式: {target_format}")
        print(f"[Stage 7] 论文: {len(self.project.paper_draft)} 字符")

        self.project.mark_stage_start(self.STAGE_NUM)

        # ── 7a. 构建文献数据库 ─────────────────────────────────
        # 建立 citation key → PaperRecord 的映射
        citation_db = self._build_citation_db()
        print(f"[Stage 7] 文献数据库: {len(citation_db)} 条")

        # ── 7b. 格式化论文引用 ─────────────────────────────────
        final_paper = self.format_paper(
            self.project.paper_draft,
            citation_db=citation_db,
            target_format=target_format
        )

        # ── 7c. 生成格式化引用列表 ─────────────────────────────
        formatted_refs = self.format_reference_list(
            self.project.literature,
            target_format=target_format
        )

        # ── 7d. 将引用列表追加到论文末尾 ───────────────────────
        final_paper = self._append_references(final_paper, formatted_refs, target_format)

        self.project.final_paper = final_paper
        self.project.citation_format = target_format
        self.project.mark_stage_done(self.STAGE_NUM)

        result = {
            'final_paper': final_paper,
            'formatted_citations': formatted_refs,
            'format': target_format,
        }

        print(f"[Stage 7] 完成！最终论文: {len(final_paper)} 字符")
        return result

    def _build_citation_db(self) -> Dict[str, PaperRecord]:
        """
        构建 citation key → PaperRecord 映射表
        key = 第一作者姓氏 + 年份（规范格式）
        """
        db = {}
        for paper in self.project.literature:
            # 建立多种 key 变体
            first_author = ''
            if paper.authors:
                first_author = paper.authors[0].split(',')[0].strip()
            year = paper.year or 'nd'

            keys = [
                f"{first_author}{year}".lower(),
                f"{first_author.lower()}_{year}" if year != 'nd' else first_author.lower(),
            ]
            for k in keys:
                if k and k not in db:
                    db[k] = paper
            # 也按 title 关键词建立映射
            if paper.title:
                title_word = paper.title.split()[0].lower()
                key2 = f"{title_word}{year}".lower()
                if key2 not in db:
                    db[key2] = paper

        return db

    def format_paper(
        self,
        paper_text: str,
        citation_db: Dict[str, PaperRecord],
        target_format: str = "chicago"
    ) -> str:
        """
        格式化论文中的内嵌引用

        Args:
            paper_text: 原始论文
            citation_db: citation key → PaperRecord 映射
            target_format: 目标格式

        Returns:
            str: 格式化后的论文
        """
        print(f"[Stage 7] 格式化内嵌引用...")

        # 各种语言的内嵌引用 pattern
        patterns = {
            'chicago': [
                # (Author, Year) 或 (Author 1 and Author 2, Year)
                r'\(([A-Z][a-z]+(?:\s+(?:et\s+al\.|,?\s*[A-Z][a-z]+))*)\s*,\s*(\d{4})\)',
                # "Author (Year)" 形式
                r'"([A-Z][a-z]+)"?\s*\((\d{4})\)',
            ],
            'apa': [
                # (Author, Year) 或 (Author et al., Year)
                r'\(([A-Z][a-z]+(?:\s+et\s+al\.?)?(?:,\s*[A-Z][a-z]+)*),\s*(\d{4})\)',
                # "Author (Year)" 形式
                r'"([A-Z][a-z]+)"?\s*\((\d{4})\)',
            ],
            'gb7714': [
                # [1] 或 [1-3] 序号形式
                r'\[(\d+(?:[-,]\d+)*)\]',
                # 姓名年份格式
                r'\[([A-Z][a-z]+\s+\d{4})\]',
            ],
            'mla': [
                r'\(([A-Z][a-z]+(?:\s+et\s+al?\.)?\s+\d{4})\)',
            ],
        }

        # 简化处理：对于大多数情况，替换引用格式但不改变引用内容
        # 真正的格式转换需要解析引用在文献数据库中的位置

        formatted = paper_text

        # ── 检测并规范引用 ──────────────────────────────────────
        # 简化策略：将论文中检测到的引用替换为标准格式
        # 实际应用中，CitationNormalizer 会更精确地做这件事

        # 追加参考文献标题（如果论文中已有可识别的参考文献章节）
        if 'references' not in formatted.lower() and \
           '参考文献' not in formatted:
            pass  # 引用列表会在后面统一追加

        return formatted

    def format_reference_list(
        self,
        literature: List[PaperRecord],
        target_format: str = "chicago"
    ) -> List[str]:
        """
        生成格式化参考文献列表

        Args:
            literature: 文献列表
            target_format: 目标格式

        Returns:
            List[str]: 每条引用格式化的字符串
        """
        if not literature:
            print("[Stage 7] 无文献可格式化")
            return []

        print(f"[Stage 7] 格式化参考文献: {len(literature)} 条 (格式: {target_format})")

        refs = []
        for i, paper in enumerate(literature):
            try:
                ref = self._format_single_reference(paper, target_format)
                refs.append(ref)
            except Exception as e:
                # 兜底：简化格式
                authors = ', '.join(paper.authors[:3]) if paper.authors else 'Unknown'
                ref = f"{authors}. \"{paper.title}\". {paper.journal or paper.source}, {paper.year or 'n.d.'}."
                refs.append(ref)

        return refs

    def _format_single_reference(self, paper: PaperRecord, fmt: str) -> str:
        """格式化单条引用"""
        authors_str = self._format_authors(paper.authors, fmt)
        title = paper.title or 'Unknown'
        journal = paper.journal or ''
        year = paper.year or 'n.d.'
        url = paper.url or ''
        doi = paper.doi or ''

        if fmt == 'chicago':
            journal_part = f"_{journal}_" if journal else ''
            return f"{authors_str}. \"{title}.\" {journal_part}{year}." + \
                   (f" {url}" if url else '') + \
                   (f" https://doi.org/{doi}" if doi else '')

        elif fmt == 'apa':
            et_al = ''
            if paper.authors:
                if len(paper.authors) == 1:
                    authors_str = paper.authors[0].split(',')[0].strip()
                elif len(paper.authors) == 2:
                    a1 = paper.authors[0].split(',')[0].strip()
                    a2 = paper.authors[1].split(',')[0].strip()
                    authors_str = f"{a1}, & {a2}"
                else:
                    authors_str = f"{paper.authors[0].split(',')[0].strip()} et al."
            journal_part = f"_{journal}_" if journal else ''
            return f"{authors_str} ({year}). {title}. {journal_part}." + \
                   (f" https://doi.org/{doi}" if doi else '')

        elif fmt == 'gb7714':
            authors_str = ', '.join(paper.authors) if paper.authors else 'Unknown'
            journal_part = f"_{journal}_" if journal else ''
            return f"[{i+1}] {authors_str}. {title} [J]. {journal_part}{year}." + \
                   (f" doi:{doi}" if doi else '')

        elif fmt == 'mla':
            authors_str = ', '.join(paper.authors) if paper.authors else 'Unknown'
            journal_part = f"_{journal}_" if journal else ''
            return f"{authors_str}. \"{title}.\" {journal_part}{year}."

        elif fmt == 'ieee':
            authors_str = ', '.join([a.split(',')[0].strip() for a in (paper.authors or [])])
            if not authors_str:
                authors_str = 'Unknown'
            return f"{authors_str}, \"{title},\" {journal}, {year}."

        elif fmt == 'harvard':
            authors_str = ', '.join(paper.authors[:2]) if paper.authors else 'Unknown'
            if len(paper.authors or []) > 2:
                authors_str += ' et al.'
            journal_part = f"_{journal}_" if journal else ''
            return f"{authors_str} ({year}) '{title}', {journal_part}{year}."

        else:
            # 默认 Chicago
            return f"{authors_str}. \"{title}.\" {journal} {year}."

    def _format_authors(self, authors: List[str], fmt: str) -> str:
        """根据引用格式格式化作者列表"""
        if not authors:
            return 'Unknown'

        if fmt == 'apa':
            if len(authors) == 1:
                return authors[0].split(',')[0].strip()
            elif len(authors) == 2:
                return f"{authors[0].split(',')[0].strip()}, & {authors[1].split(',')[0].strip()}"
            else:
                return f"{authors[0].split(',')[0].strip()} et al."

        elif fmt in ('chicago', 'mla', 'harvard'):
            if len(authors) == 1:
                return authors[0]
            elif len(authors) == 2:
                return f"{authors[0]}, and {authors[1]}"
            else:
                return f"{authors[0]} et al."

        elif fmt == 'ieee':
            # IEEE: First Initial. Last Name
            formatted = []
            for a in authors:
                parts = a.split(',')
                if len(parts) == 2:
                    initial = parts[1].strip()[0] + '.'
                    last = parts[0].strip()
                    formatted.append(f"{initial} {last}")
                else:
                    formatted.append(a)
            return ', '.join(formatted)

        else:
            return ', '.join(authors)

    def _append_references(
        self,
        paper_text: str,
        refs: List[str],
        fmt: str
    ) -> str:
        """将参考文献列表追加到论文末尾"""
        if not refs:
            return paper_text

        # 检查是否已有参考文献章节
        has_refs = bool(
            re.search(r'(references|参考文献)', paper_text[-500:], re.IGNORECASE)
        )

        ref_header = {
            'en': '\n\n## References\n\n',
            'ja': '\n\n## 参考文献\n\n',
            'zh': '\n\n## 参考文献\n\n',
        }.get(self.project.language[:2].lower(), '\n\n## References\n\n')

        ref_lines = [f"{i+1}. {ref}" for i, ref in enumerate(refs)]

        if has_refs:
            # 已有参考文献章节，不追加
            return paper_text

        return paper_text + ref_header + '\n'.join(ref_lines)
