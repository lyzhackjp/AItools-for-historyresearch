from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

from .docx_parser import clean_text
from .models import ParsedFootnote, ParsedParagraph
from .page_span import classify_page_span
from .contained_sources import apply_contained_source_metadata, contained_source_host_titles


DEFAULT_QUOTE_PATTERNS = [
    r"“([^”]{6,})”",
    r"「([^」]{6,})」",
    r"『([^』]{6,})』",
    r'"([^"\n]{6,})"',
]

DEFAULT_TITLE_PATTERNS = [
    r"[「『《](.+?)[」』》]",
]

DEFAULT_PAGE_PATTERNS = [
    r"(\d+)\s*[-—－~～]\s*(\d+)\s*頁",
    r"第?\s*(\d+)\s*[-—－~～]\s*(\d+)\s*页",
    r"(\d+)\s*頁",
    r"第?\s*(\d+)\s*页",
]

DEFAULT_STOPWORD_PREFIXES = (
    "相关研究参见",
    "如",
    "参见",
    "原文为",
)


def safe_int(value: str) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_quotes(text: str, *, quote_patterns: Sequence[str] = DEFAULT_QUOTE_PATTERNS) -> List[str]:
    quotes: List[str] = []
    for pattern in quote_patterns:
        for match in re.findall(pattern, text):
            cleaned = clean_text(match)
            if cleaned and cleaned not in quotes:
                quotes.append(cleaned)
    return quotes


def extract_title(text: str, *, title_patterns: Sequence[str] = DEFAULT_TITLE_PATTERNS) -> str:
    for pattern in title_patterns:
        match = re.search(pattern, text)
        if match:
            return clean_text(match.group(1))
    return ""


def extract_author(text: str, *, title: str) -> str:
    if not title:
        return ""
    prefix = text.split(title, 1)[0]
    prefix = prefix.strip("「『《（( ，,。；;:：")
    prefix = re.sub(r"(著|编|編|编纂|編纂|研究会編|研究會編)\s*$", "", prefix)
    return clean_text(prefix)


def extract_publisher(text: str, *, title: str) -> Tuple[str, str]:
    search_area = text
    if title and title in text:
        search_area = text.split(title, 1)[1]
    match = re.search(r"([^\s、，,。；;:：]{1,20})\s*[：:]\s*([^、，,。；;]{1,40})", search_area)
    if not match:
        return "", ""
    return clean_text(match.group(1)), clean_text(match.group(2))


def extract_pages(text: str, *, page_patterns: Sequence[str] = DEFAULT_PAGE_PATTERNS) -> Tuple[str, List[int]]:
    list_match = re.search(r"第?\s*(\d+(?:\s*[,，、]\s*\d+)+)\s*[页頁]", text)
    if list_match:
        numbers = [safe_int(value) for value in re.findall(r"\d+", list_match.group(1))]
        pages = [value for value in numbers if value is not None]
        if pages:
            return list_match.group(0), pages

    for pattern in page_patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        numbers = [safe_int(value) for value in match.groups() if value is not None]
        numbers = [value for value in numbers if value is not None]
        if len(numbers) == 2:
            start, end = numbers
            if start <= end:
                return match.group(0), list(range(start, end + 1))
            return match.group(0), [start, end]
        if len(numbers) == 1:
            return match.group(0), [numbers[0]]
    return "", []


def detect_source_type(text: str) -> str:
    lowered = text.lower()
    if "jacar" in lowered or "ref." in lowered:
        return "archive"
    if "紀要" in text or "学报" in text or "期" in text:
        return "article"
    return "book"


def parse_footnote_text(
    note_id: str,
    text: str,
    *,
    title_patterns: Sequence[str] = DEFAULT_TITLE_PATTERNS,
    page_patterns: Sequence[str] = DEFAULT_PAGE_PATTERNS,
) -> ParsedFootnote:
    normalized = clean_text(text)
    title = extract_title(normalized, title_patterns=title_patterns)
    author = extract_author(normalized, title=title)
    publication_place, publisher = extract_publisher(normalized, title=title)
    year_match = re.search(r"(1[89]\d{2}|20\d{2})年", normalized)
    year = year_match.group(1) if year_match else ""
    page_label, page_numbers = extract_pages(normalized, page_patterns=page_patterns)
    page_span = classify_page_span(page_numbers, page_label=page_label)
    source_type = detect_source_type(normalized)
    host_titles = contained_source_host_titles(title, normalized)
    host_title = host_titles[0] if host_titles else ""
    ndl_keyword = " ".join(part for part in [host_title, title, author] if part).strip() or normalized[:120]

    parsed = ParsedFootnote(
        id=str(note_id),
        text=normalized,
        title=title,
        author=author,
        publisher=publisher,
        publication_place=publication_place,
        year=year,
        page_label=page_label,
        page_numbers=page_numbers,
        page_span_type=page_span["mode"],
        page_span_source=page_span["reason"],
        source_type=source_type,
        ndl_keyword=ndl_keyword,
        host_title=host_title,
        contained_title=title if host_title else "",
        source_relation="contained_in_host" if host_title else "",
    )
    apply_contained_source_metadata(parsed)
    if not title:
        parsed.notes.append("title_not_parsed")
    if not page_numbers:
        parsed.notes.append("page_not_parsed")
    return parsed


def pick_translation_text(
    paragraph: ParsedParagraph,
    *,
    include_unquoted: bool = False,
    footnote_id: Optional[str] = None,
) -> str:
    if footnote_id:
        context = (paragraph.footnote_contexts or {}).get(str(footnote_id))
        if context:
            return context

    explicit_quotes = list(paragraph.quotes or [])
    if explicit_quotes:
        if footnote_id and len(explicit_quotes) > 1 and len(paragraph.footnote_ids) > 1:
            try:
                footnote_index = list(paragraph.footnote_ids).index(str(footnote_id))
            except ValueError:
                footnote_index = -1
            if 0 <= footnote_index < len(explicit_quotes):
                return explicit_quotes[footnote_index]
        explicit_quotes = sorted(explicit_quotes, key=len, reverse=True)
        return explicit_quotes[0]
    if include_unquoted:
        return paragraph.text
    if "：" in paragraph.text:
        tail = paragraph.text.split("：", 1)[1]
        tail = clean_text(tail)
        if len(tail) >= 12:
            return tail[:220]
    return ""


def is_verifiable_footnote(
    footnote: ParsedFootnote,
    *,
    stopword_prefixes: Sequence[str] = DEFAULT_STOPWORD_PREFIXES,
) -> bool:
    if not footnote.page_numbers:
        return False
    stripped = footnote.text.lstrip()
    return not any(stripped.startswith(prefix) for prefix in stopword_prefixes)
