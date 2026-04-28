"""
引用格式生成器模块

生成各种学术期刊格式的引用字符串
专门针对图书引用进行优化

使用方法：
    from modules.citation_formats import CitationFormatter

    formatter = CitationFormatter()
    citations = formatter.format_book_citation(
        title="銀河英雄伝説",
        author="田中芳樹",
        publisher="東京創元社",
        year="1982",
        pages="300",
        edition="文庫版"
    )
    print(citations['chicago'])  # 田中芳樹. 銀河英雄伝説 [M]. 東京創元社, 1982.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional


class CitationFormatter:
    """引用格式生成器 - 专注图书引用"""

    # 图书引用模板
    BOOK_TEMPLATES = {
        'chicago': {
            'default': '{author}. {title} [M]. {publisher}, {year}.',
            'with_pages': '{author}. {title} [M]. {publisher}, {year}. pp. {pages}.',
            'with_edition': '{author}. {title} [M]. {publisher}, {year}. {edition}.',
            'with_pages_edition': '{author}. {title} [M]. {publisher}, {year}. {edition}. pp. {pages}.',
        },
        'apa': {
            'default': '{author} ({year}). {title}. {publisher}.',
            'with_pages': '{author} ({year}). {title}. {publisher}. {pages}p.',
            'with_edition': '{author} ({year}). {title} ({edition}). {publisher}.',
            'with_pages_edition': '{author} ({year}). {title} ({edition}). {publisher}. {pages}p.',
        },
        'gb7714': {
            'default': '[1] {author}. {title} [M]. {publisher}, {year}.',
            'with_pages': '[1] {author}. {title} [M]. {publisher}, {year}: {pages}.',
            'with_edition': '[2] {author}. {title} [M]. {publisher}, {year}.',
            'with_pages_edition': '[2] {author}. {title} [M]. {publisher}, {year}: {pages}.',
        },
        'mla': {
            'default': '{author}. {title} [M]. {publisher}, {year}.',
            'with_pages': '{author}. {title} [M]. {publisher}, {year}. Print.',
            'with_edition': '{author}. {title} [M]. {publisher}, {year}.',
            'with_pages_edition': '{author}. {title} [M]. {publisher}, {year}. Print.',
        },
        'ieee': {
            'default': '{author}, {title}. {publisher}, {year}.',
            'with_pages': '{author}, {title}. {publisher}, {year}, pp. {pages}.',
            'with_edition': '{author}, {title}. {publisher}, {year}.',
            'with_pages_edition': '{author}, {title}. {publisher}, {year}, pp. {pages}.',
        },
        'harvard': {
            'default': '{author} ({year}) {title}. {publisher}.',
            'with_pages': '{author} ({year}) {title}. {publisher}, pp. {pages}.',
            'with_edition': '{author} ({year}) {title}. {publisher}.',
            'with_pages_edition': '{author} ({year}) {title}. {publisher}, pp. {pages}.',
        },
    }

    # 日文作者姓名处理（姓氏+名字顺序）
    JAPANESE_NAME_PATTERNS = [
        # 田中芳樹 -> 田中芳樹
        r'^([^\s]+)\s+([^\s]+)$',
        # 不变
        r'^([^\s]+)$',
    ]

    def __init__(self, index_start: int = 1):
        """
        初始化引用格式生成器

        Args:
            index_start: GB/T7714格式的起始序号
        """
        self.index_start = index_start
        self.current_index = index_start

    def get_capabilities(self) -> Dict[str, Any]:
        """Return a machine-readable capability snapshot."""

        return {
            "module": "citation_formats",
            "layer": "writing_output",
            "backend": "script",
            "provider": "rule_templates",
            "model": None,
            "tasks": ["citation_format", "citation_batch_format", "book_citation_format"],
            "output_types": ["citation_formatting"],
            "supported_styles": sorted(self.BOOK_TEMPLATES.keys()),
            "supports": {
                "format_record": True,
                "format_batch": True,
                "book_templates": True,
                "external_ai_backend": False,
                "package_output": True,
            },
            "privacy": {
                "local_first": True,
                "secrets_required": False,
                "logs_raw_text": False,
            },
        }

    def _format_author(self, author: str, style: str = 'chicago') -> str:
        """
        格式化作者名

        Args:
            author: 原始作者名
            style: 引用风格

        Returns:
            格式化后的作者名
        """
        if not author or author == '未知':
            return '未知作者'

        # 移除多余空格
        author = ' '.join(author.split())

        if style == 'apa':
            # APA: Last, First -> 已经是这样就保持
            pass
        elif style == 'chicago':
            # Chicago: 田中芳樹 (保持原样)
            pass
        elif style == 'ieee':
            # IEEE: 田中芳樹 (保持原样)
            pass

        return author

    def _format_title(self, title: str, style: str = 'chicago') -> str:
        """
        格式化书名

        Args:
            title: 原始书名
            style: 引用风格

        Returns:
            格式化后的书名
        """
        if not title or title == '未知书名':
            return '未知书名'

        # 保持日文书名的《》或『』
        # 可能需要清理一些格式
        return title

    def format_book_citation(
        self,
        title: str,
        author: str,
        publisher: str = '',
        year: str = '',
        pages: str = '',
        edition: str = '',
        language: str = 'ja'
    ) -> Dict[str, str]:
        """
        生成图书的各种引用格式

        Args:
            title: 书名
            author: 作者
            publisher: 出版社
            year: 出版年
            pages: 页数
            edition: 版次
            language: 语言 (ja/en/zh)

        Returns:
            包含各种引用格式的字典
        """
        # 处理默认值
        if not year:
            year = 'n.d.'
        if not pages:
            pages = ''
        if not edition:
            edition = ''

        # 格式化作者（不同风格可能不同）
        author_chicago = self._format_author(author, 'chicago')
        author_apa = self._format_author(author, 'apa')
        author_gb = self._format_author(author, 'gb7714')
        author_mla = self._format_author(author, 'mla')
        author_ieee = self._format_author(author, 'ieee')
        author_harvard = self._format_author(author, 'harvard')

        citations = {}

        # 判断使用哪个模板变体
        has_pages = bool(pages and pages != '未知')
        has_edition = bool(edition and edition != '未知')

        if has_pages and has_edition:
            template_key = 'with_pages_edition'
        elif has_pages:
            template_key = 'with_pages'
        elif has_edition:
            template_key = 'with_edition'
        else:
            template_key = 'default'

        # Chicago
        citations['chicago'] = self.BOOK_TEMPLATES['chicago'][template_key].format(
            author=author_chicago,
            title=title,
            publisher=publisher or '未知出版社',
            year=year,
            pages=pages,
            edition=edition
        )

        # APA
        citations['apa'] = self.BOOK_TEMPLATES['apa'][template_key].format(
            author=author_apa,
            title=title,
            publisher=publisher or '未知出版社',
            year=year,
            pages=pages,
            edition=edition
        )

        # GB/T 7714
        gb_template = self.BOOK_TEMPLATES['gb7714'][template_key]
        # 替换序号
        gb_template = gb_template.replace('[1]', f'[{self.current_index}]')
        if self.current_index > 1:
            gb_template = gb_template.replace('[2]', f'[{self.current_index}]')
        citations['gb7714'] = gb_template.format(
            author=author_gb,
            title=title,
            publisher=publisher or '未知出版社',
            year=year,
            pages=pages,
            edition=edition
        )
        self.current_index += 1

        # MLA
        citations['mla'] = self.BOOK_TEMPLATES['mla'][template_key].format(
            author=author_mla,
            title=title,
            publisher=publisher or '未知出版社',
            year=year,
            pages=pages,
            edition=edition
        )

        # IEEE
        citations['ieee'] = self.BOOK_TEMPLATES['ieee'][template_key].format(
            author=author_ieee,
            title=title,
            publisher=publisher or '未知出版社',
            year=year,
            pages=pages,
            edition=edition
        )

        # Harvard
        citations['harvard'] = self.BOOK_TEMPLATES['harvard'][template_key].format(
            author=author_harvard,
            title=title,
            publisher=publisher or '未知出版社',
            year=year,
            pages=pages,
            edition=edition
        )

        return citations

    def format_record(
        self,
        record: Dict[str, Optional[str]],
        style: str = 'chicago',
        index: Optional[int] = None
    ) -> str:
        """
        Render a normalized citation record into a target style.

        Args:
            record: 统一 citation record
            style: 目标风格
            index: 可选编号，主要用于 GB/T 7714 和 IEEE

        Returns:
            str: 格式化后的引用字符串
        """
        record_type = (record.get('type') or 'article').lower()
        author = record.get('author') or record.get('authors') or 'Unknown'
        if isinstance(author, list):
            author = self.format_multi_author(author, style=style)

        title = record.get('title') or 'Untitled'
        publisher = record.get('publisher') or record.get('journal') or record.get('source') or 'Unknown'
        year = str(record.get('year') or 'n.d.')
        pages = str(record.get('pages') or '').strip()
        edition = str(record.get('edition') or '').strip()
        volume = str(record.get('volume') or '').strip()
        issue = str(record.get('issue') or '').strip()
        url = str(record.get('url') or '').strip()

        if record_type == 'book':
            citations = self.format_book_citation(
                title=title,
                author=author,
                publisher=publisher,
                year=year,
                pages=pages,
                edition=edition,
            )
            rendered = citations.get(style, citations.get('chicago', ''))
            if style in ('gb7714', 'ieee') and index is not None:
                rendered = re.sub(r'^\[\d+\]', f'[{index}]', rendered)
            return rendered

        if style == 'apa':
            return f"{author} ({year}). {title}. {publisher}, {volume}({issue}), {pages}.".replace(' ,', ',').replace('()', '')
        if style == 'mla':
            return f'{author}. "{title}." {publisher}, vol. {volume}, no. {issue}, {year}, pp. {pages}.'.replace('vol. ,', '').replace('no. ,', '')
        if style == 'gb7714':
            idx = index if index is not None else self.current_index
            return f'[{idx}] {author}. {title}[J]. {publisher}, {year}, {volume}({issue}): {pages}.'.replace(' ,', ',').replace('()', '')
        if style == 'ieee':
            idx = index if index is not None else self.current_index
            return f'[{idx}] {author}, "{title}," {publisher}, vol. {volume}, no. {issue}, pp. {pages}, {year}.'.replace('vol. ,', '').replace('no. ,', '')
        if style == 'harvard':
            return f"{author} ({year}) {title}. {publisher}, pp. {pages}.".replace(', pp. .', '.')
        return f'{author}. "{title}." {publisher}, {year}, {volume}({issue}): {pages}.'.replace(' ,', ',').replace('()', '')

    def format_batch(
        self,
        records: list,
        style: str = 'chicago'
    ) -> list:
        """
        Format a batch of normalized citation records.
        """
        rendered = []
        for offset, record in enumerate(records, start=self.index_start):
            rendered.append(self.format_record(record, style=style, index=offset))
        return rendered

    def format_record_package(
        self,
        record: Dict[str, Optional[str]],
        style: str = 'chicago',
        index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Render one citation record and return a package envelope."""

        quality_flags = self._record_quality_flags(record, style)
        try:
            rendered = self.format_record(record, style=style, index=index)
            success = bool(rendered)
        except Exception as exc:  # noqa: BLE001
            rendered = ""
            success = False
            quality_flags.append("format_record_failed")
            error = f"{type(exc).__name__}: {exc}"
        else:
            error = ""

        if success and not rendered.strip():
            quality_flags.append("empty_rendered_citation")

        record_type = (record.get("type") or "article") if isinstance(record, dict) else "unknown"
        return {
            "type": "citation_formatting",
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "backend": "script",
            "provider": "rule_templates",
            "model": None,
            "style": style,
            "confidence": self._package_confidence(success, quality_flags),
            "needs_review": (not success) or bool(quality_flags),
            "quality_flags": quality_flags,
            "record": dict(record) if isinstance(record, dict) else {},
            "rendered": rendered,
            "summary": {
                "record_count": 1,
                "rendered_count": 1 if rendered else 0,
                "style": style,
                "record_type": record_type,
            },
            "capabilities": self.get_capabilities(),
            "error": error,
        }

    def format_batch_package(
        self,
        records: List[Dict[str, Optional[str]]],
        style: str = 'chicago',
    ) -> Dict[str, Any]:
        """Render normalized citation records and return a package envelope."""

        quality_flags = []
        if not records:
            quality_flags.append("empty_records")

        rendered_records = []
        rendered = []
        for offset, record in enumerate(records, start=self.index_start):
            package = self.format_record_package(record, style=style, index=offset)
            rendered_records.append(package)
            if package.get("rendered"):
                rendered.append(package["rendered"])
            for flag in package.get("quality_flags", []):
                if flag not in quality_flags:
                    quality_flags.append(flag)

        success = bool(rendered) or not records
        return {
            "type": "citation_formatting",
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "backend": "script",
            "provider": "rule_templates",
            "model": None,
            "style": style,
            "confidence": self._package_confidence(success, quality_flags),
            "needs_review": (not success) or bool(quality_flags),
            "quality_flags": quality_flags,
            "records": rendered_records,
            "rendered": rendered,
            "summary": {
                "record_count": len(records),
                "rendered_count": len(rendered),
                "style": style,
                "records_needing_review": sum(1 for package in rendered_records if package.get("needs_review")),
            },
            "capabilities": self.get_capabilities(),
            "error": "" if success else "no citations rendered",
        }

    def format_multi_author(
        self,
        authors: list,
        style: str = 'chicago'
    ) -> str:
        """
        格式化多作者

        Args:
            authors: 作者列表
            style: 引用风格

        Returns:
            格式化后的多作者字符串
        """
        if not authors:
            return '未知作者'

        if len(authors) == 1:
            return authors[0]

        if style == 'chicago':
            # 田中芳樹, 銀河英雄伝説
            return ', '.join(authors[:-1]) + ', ' + authors[-1]
        elif style == 'apa':
            # 田中芳樹, & 銀河英雄伝説
            return ', '.join(authors[:-1]) + ', & ' + authors[-1]
        elif style == 'ieee':
            # 田中芳樹, 銀河英雄伝説
            return ', '.join(authors[:-1]) + ', ' + authors[-1]
        else:
            return ', '.join(authors)

    def reset_index(self):
        """重置GB/T序号"""
        self.current_index = self.index_start

    def _record_quality_flags(self, record: Dict[str, Optional[str]], style: str) -> List[str]:
        flags = []
        if style not in self.BOOK_TEMPLATES:
            flags.append("unsupported_style_fallback")
        if not isinstance(record, dict):
            return ["invalid_record"]
        if not record.get("title"):
            flags.append("missing_title")
        if not (record.get("author") or record.get("authors")):
            flags.append("missing_author")
        if not record.get("year"):
            flags.append("missing_year")
        return flags

    def _package_confidence(self, success: bool, quality_flags: List[str]) -> float:
        if not success:
            return 0.0
        score = 0.9
        score -= min(0.45, 0.12 * len(quality_flags))
        return round(max(0.0, min(1.0, score)), 2)


def format_japanese_book(
    title: str,
    author: str,
    publisher: str,
    year: str,
    pages: str = '',
    edition: str = ''
) -> Dict[str, str]:
    """
    便捷函数：格式化日文图书引用

    Args:
        title: 书名
        author: 作者
        publisher: 出版社
        year: 出版年
        pages: 页数
        edition: 版次

    Returns:
        各种引用格式字典
    """
    formatter = CitationFormatter()
    return formatter.format_book_citation(
        title=title,
        author=author,
        publisher=publisher,
        year=year,
        pages=pages,
        edition=edition,
        language='ja'
    )
