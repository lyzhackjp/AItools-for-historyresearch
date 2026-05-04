from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Sequence, Tuple

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

KANJI_DIGIT_VALUES = {
    "〇": 0,
    "零": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def _parse_east_asian_number(value: str) -> Optional[int]:
    token = unicodedata.normalize("NFKC", value or "").strip()
    if not token:
        return None
    if token.isdigit():
        return int(token)
    total = 0
    if "百" in token:
        left, _sep, right = token.partition("百")
        total += (KANJI_DIGIT_VALUES.get(left, 1) if left else 1) * 100
        token = right
    if "十" in token:
        left, _sep, right = token.partition("十")
        total += (KANJI_DIGIT_VALUES.get(left, 1) if left else 1) * 10
        if right:
            total += KANJI_DIGIT_VALUES.get(right, 0)
        return total or None
    if len(token) > 1 and all(char in KANJI_DIGIT_VALUES for char in token):
        number = 0
        for char in token:
            number = number * 10 + KANJI_DIGIT_VALUES[char]
        return number
    return KANJI_DIGIT_VALUES.get(token)


def _to_kanji_number(number: int) -> str:
    if number <= 0:
        return ""
    digits = "〇一二三四五六七八九"
    if number < 10:
        return digits[number]
    if number < 100:
        tens, ones = divmod(number, 10)
        left = "" if tens == 1 else digits[tens]
        return left + "十" + (digits[ones] if ones else "")
    hundreds, rest = divmod(number, 100)
    left = ("" if hundreds == 1 else digits[hundreds]) + "百"
    return left + (_to_kanji_number(rest) if rest else "")


def _term_number(value: str) -> Optional[int]:
    match = re.search(r"([0-9一二三四五六七八九十百〇零]+)", value or "")
    if not match:
        return None
    return _parse_east_asian_number(match.group(1))


def extract_volume_terms(text: str) -> List[str]:
    normalized = unicodedata.normalize("NFKC", clean_text(text or ""))
    terms: List[str] = []

    def add(value: str) -> None:
        cleaned = clean_text(value)
        if cleaned and cleaned not in terms:
            terms.append(cleaned)

    for match in re.finditer(r"第\s*([0-9一二三四五六七八九十百〇零]+)\s*([卷巻冊册])", normalized):
        raw_number, marker = match.groups()
        number = _parse_east_asian_number(raw_number)
        add(match.group(0))
        if number is None:
            continue
        kanji = _to_kanji_number(number)
        if marker in {"冊", "册"}:
            add(f"第{number}冊")
            add(f"第{number}册")
            continue
        for suffix in ("巻", "卷"):
            add(f"第{number}{suffix}")
            if kanji:
                add(f"第{kanji}{suffix}")
        if "日本外交文書" in normalized or "日本外交文书" in normalized:
            add(f"明治{number}年")
            if kanji:
                add(f"明治{kanji}年")

    fascicle_numbers: set[int] = set()
    for match in re.finditer(
        r"第\s*([0-9一二三四五六七八九十百〇零]+)\s*[卷巻]\s*第?\s*([0-9一二三四五六七八九十百〇零]+)\s*[冊册]",
        normalized,
    ):
        volume_number = _parse_east_asian_number(match.group(1))
        fascicle_number = _parse_east_asian_number(match.group(2))
        if volume_number is not None and fascicle_number is not None and volume_number != fascicle_number:
            fascicle_numbers.add(fascicle_number)
    if fascicle_numbers:
        filtered_terms: List[str] = []
        for term in terms:
            number = _term_number(term)
            if number in fascicle_numbers and any(marker in term for marker in ("巻", "卷")):
                continue
            if number in fascicle_numbers and term.startswith("明治") and term.endswith("年"):
                continue
            filtered_terms.append(term)
        terms = filtered_terms
    return terms[:8]


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


def _ordered_title_candidates(text: str, title_patterns: Sequence[str]) -> List[str]:
    candidates: List[str] = []
    for pattern in title_patterns:
        for match in re.finditer(pattern, text):
            cleaned = clean_text(match.group(1))
            if cleaned and cleaned not in candidates:
                candidates.append(cleaned)
    return candidates


def _parenthetical_original_title_candidates(text: str) -> List[str]:
    """Prefer original-language titles in bilingual Chinese footnotes.

    A common PDF citation style is: Chinese title（author/editor:『original title』）.
    The original title is usually the better NDL query seed than the Chinese
    translation, so we surface it before the generic first-title fallback.
    """

    patterns = (
        r"[（(][^（）()]{0,100}[：:]\s*[「『《](.+?)[」』》][^（）()]{0,100}[）)]",
        r"[（(]\s*[「『《](.+?)[」』》]\s*[）)]",
    )
    candidates: List[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            cleaned = clean_text(match.group(1))
            if cleaned and cleaned not in candidates:
                candidates.append(cleaned)
    return candidates


def extract_title(text: str, *, title_patterns: Sequence[str] = DEFAULT_TITLE_PATTERNS) -> str:
    title_candidates = _ordered_title_candidates(text, title_patterns)
    first_title = title_candidates[0] if title_candidates else ""
    for candidate in _parenthetical_original_title_candidates(text):
        if candidate != first_title:
            return candidate
    if first_title:
        return first_title
    return ""


def _title_alias_key(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "").lower()
    return re.sub(r"[\s　「」『』《》〈〉（）()［］\[\]、，,。．.・·:：；;]+", "", normalized)


def _build_ndl_keyword(footnote: ParsedFootnote) -> str:
    return (
        " ".join(
            part
            for part in [
                footnote.host_title,
                footnote.title,
                *extract_volume_terms(footnote.text),
                footnote.author,
            ]
            if part
        ).strip()
        or footnote.text[:120]
    )


def apply_footnote_title_aliases(footnotes: Sequence[ParsedFootnote]) -> None:
    """Propagate original-language title aliases across repeated citations.

    Many articles define a source once as ``Chinese title（author:『Japanese title』）``
    and then cite only the Chinese title later. This function keeps the parsed
    footnote text intact but updates later search titles to the original title.
    """

    aliases: Dict[str, str] = {}
    for footnote in footnotes:
        title_key = _title_alias_key(footnote.title)
        if title_key and title_key in aliases and footnote.title != aliases[title_key]:
            original_title = footnote.title
            footnote.title = aliases[title_key]
            footnote.ndl_keyword = _build_ndl_keyword(footnote)
            note = f"title_alias_resolved:{original_title}->{footnote.title}"
            if note not in footnote.notes:
                footnote.notes.append(note)

        title_candidates = _ordered_title_candidates(footnote.text, DEFAULT_TITLE_PATTERNS)
        if not footnote.title or not title_candidates:
            continue
        for candidate in title_candidates:
            if candidate == footnote.title:
                continue
            candidate_key = _title_alias_key(candidate)
            if candidate_key:
                aliases.setdefault(candidate_key, footnote.title)


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
    volume_terms = extract_volume_terms(normalized)
    ndl_keyword = " ".join(part for part in [host_title, title, *volume_terms, author] if part).strip() or normalized[:120]

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
    for term in volume_terms[:3]:
        note = f"volume_hint:{term}"
        if note not in parsed.notes:
            parsed.notes.append(note)
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
