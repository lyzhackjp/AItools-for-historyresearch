from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import fitz

from .docx_parser import (
    build_footnote_citation_units,
    build_footnote_contexts,
    clean_text,
)
from .footnote_parser import apply_footnote_title_aliases
from .models import ParsedFootnote, ParsedParagraph


FootnoteParser = Callable[[str, str], ParsedFootnote]
QuoteExtractor = Callable[[str], List[str]]
OcrPageTextProvider = Callable[[int], str]

FOOTNOTE_MARKERS = [
    "①",
    "②",
    "③",
    "④",
    "⑤",
    "⑥",
    "⑦",
    "⑧",
    "⑨",
    "⑩",
    "⑪",
    "⑫",
    "⑬",
    "⑭",
    "⑮",
    "⑯",
    "⑰",
    "⑱",
    "⑲",
    "⑳",
]
FOOTNOTE_MARKER_PATTERN = re.compile(r"^(\*|[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]|[\ue000-\uf8ff][^\s　、，：:]{0,4})[\s　]*")


@dataclass
class PdfLine:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    avg_size: float
    max_size: float


def _span_size_average(spans: Sequence[Dict[str, Any]]) -> Tuple[float, float]:
    weighted_total = 0.0
    text_len = 0
    max_size = 0.0
    for span in spans:
        size = float(span.get("size") or 0)
        text = str(span.get("text") or "")
        length = max(len(text.strip()), 1)
        weighted_total += size * length
        text_len += length
        max_size = max(max_size, size)
    if text_len <= 0:
        return 0.0, max_size
    return weighted_total / text_len, max_size


def _extract_pdf_lines(page: fitz.Page) -> List[PdfLine]:
    lines: List[PdfLine] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = list(line.get("spans", []))
            text = "".join(str(span.get("text") or "") for span in spans).strip()
            if not text:
                continue
            avg_size, max_size = _span_size_average(spans)
            bbox = line.get("bbox") or block.get("bbox") or [0, 0, 0, 0]
            lines.append(
                PdfLine(
                    text=text,
                    x0=float(bbox[0]),
                    y0=float(bbox[1]),
                    x1=float(bbox[2]),
                    y1=float(bbox[3]),
                    avg_size=avg_size,
                    max_size=max_size,
                )
            )
    return sorted(lines, key=lambda item: (round(item.y0, 1), item.x0))


def _merge_same_row_lines(lines: Sequence[PdfLine], *, tolerance: float = 3.2) -> List[PdfLine]:
    rows: List[List[PdfLine]] = []
    for line in lines:
        if rows and abs(rows[-1][0].y0 - line.y0) <= tolerance:
            rows[-1].append(line)
        else:
            rows.append([line])
    merged: List[PdfLine] = []
    for row in rows:
        row = sorted(row, key=lambda item: item.x0)
        text = "".join(item.text for item in row)
        weighted = sum(item.avg_size * max(len(item.text), 1) for item in row)
        length = sum(max(len(item.text), 1) for item in row)
        merged.append(
            PdfLine(
                text=text.strip(),
                x0=min(item.x0 for item in row),
                y0=min(item.y0 for item in row),
                x1=max(item.x1 for item in row),
                y1=max(item.y1 for item in row),
                avg_size=weighted / max(length, 1),
                max_size=max(item.max_size for item in row),
            )
        )
    return merged


def _looks_like_footnote_start(text: str) -> bool:
    stripped = text.strip()
    return bool(FOOTNOTE_MARKER_PATTERN.match(stripped))


def _infer_footnote_top(lines: Sequence[PdfLine], page_height: float) -> float:
    candidates = [
        line.y0
        for line in lines
        if line.y0 > page_height * 0.55
        and line.avg_size <= 8.9
        and (line.x0 < 120 or _looks_like_footnote_start(line.text))
        and _looks_like_footnote_start(line.text)
    ]
    if candidates:
        return min(candidates) - 2

    small_bottom_lines = [
        line.y0
        for line in lines
        if line.y0 > page_height * 0.70 and line.avg_size <= 8.9 and line.x0 < 140
    ]
    if small_bottom_lines:
        return min(small_bottom_lines) - 2
    return page_height + 1


def _strip_running_header_footer(lines: Sequence[PdfLine], page_height: float) -> List[PdfLine]:
    body: List[PdfLine] = []
    for line in lines:
        text = line.text.strip()
        if line.y0 > page_height - 48 and re.fullmatch(r"\d{2,4}", text):
            continue
        if line.y0 < 44 and (re.fullmatch(r"\d{2,4}", text) or len(text) <= 24):
            continue
        body.append(line)
    return body


def _line_text(lines: Sequence[PdfLine]) -> str:
    chunks: List[str] = []
    previous_y: float | None = None
    for line in lines:
        text = line.text.strip()
        if not text:
            continue
        if previous_y is not None and line.y0 - previous_y > 18:
            chunks.append("\n")
        chunks.append(text)
        previous_y = line.y0
    return clean_text("".join(chunks))


def _text_layer_needs_ocr(lines: Sequence[PdfLine], page_text: str) -> bool:
    cleaned = clean_text(page_text)
    if not lines or len(cleaned) < 30:
        return True
    if cleaned.count("\ufffd") >= 3:
        return True
    if cleaned and cleaned.count("?") / max(len(cleaned), 1) > 0.25:
        return True
    return False


def _extract_marker_token(text: str) -> Tuple[str, str]:
    stripped = text.strip()
    match = FOOTNOTE_MARKER_PATTERN.match(stripped)
    if not match:
        return "", stripped
    marker = match.group(1)
    rest = stripped[match.end() :].strip()
    return marker, rest


def _parse_page_footnotes(
    page_number: int,
    lines: Sequence[PdfLine],
    *,
    parse_footnote: FootnoteParser,
) -> Tuple[List[ParsedFootnote], Dict[str, str]]:
    notes: List[ParsedFootnote] = []
    marker_to_id: Dict[str, str] = {}
    current_marker = ""
    current_chunks: List[str] = []

    def flush() -> None:
        nonlocal current_marker, current_chunks
        if not current_marker or not current_chunks:
            current_marker = ""
            current_chunks = []
            return
        note_id = f"p{page_number}n{len(notes) + 1}"
        marker_to_id[current_marker] = note_id
        note_text = clean_text("".join(current_chunks))
        notes.append(parse_footnote(note_id, note_text))
        current_marker = ""
        current_chunks = []

    for line in lines:
        marker, rest = _extract_marker_token(line.text)
        if marker:
            flush()
            current_marker = marker
            current_chunks = [rest or line.text.strip()]
        elif current_marker:
            current_chunks.append(line.text.strip())
    flush()
    return notes, marker_to_id


def _replace_markers_with_positions(
    body_text: str,
    marker_to_id: Dict[str, str],
) -> Tuple[str, List[str], Dict[str, int], Dict[str, int]]:
    marker_order = sorted(marker_to_id, key=len, reverse=True)
    if not marker_order:
        return body_text, [], {}, {}
    pattern = re.compile("|".join(re.escape(marker) for marker in marker_order))
    result: List[str] = []
    footnote_ids: List[str] = []
    footnote_positions: Dict[str, int] = {}
    reference_counts: Dict[str, int] = {}
    last = 0
    for match in pattern.finditer(body_text):
        marker = match.group(0)
        # Avoid turning leading bibliography footnote markers into body markers:
        # PDF pages are already split into body/footnote regions, so this mainly
        # removes inline superscripts in the body text.
        result.append(body_text[last : match.start()])
        note_id = marker_to_id.get(marker)
        if note_id:
            position = len("".join(result))
            footnote_ids.append(note_id)
            footnote_positions[note_id] = position
            reference_counts[note_id] = reference_counts.get(note_id, 0) + 1
        last = match.end()
    result.append(body_text[last:])
    return clean_text("".join(result)), footnote_ids, footnote_positions, reference_counts


def _parse_ocr_page_text(
    page_number: int,
    ocr_text: str,
    *,
    parse_footnote: FootnoteParser,
) -> Tuple[List[PdfLine], List[PdfLine], List[ParsedFootnote], Dict[str, str]]:
    raw_lines = [clean_text(line) for line in (ocr_text or "").splitlines()]
    raw_lines = [line for line in raw_lines if line]
    if not raw_lines:
        return [], [], [], {}

    split_index = len(raw_lines)
    lower_bound = max(0, int(len(raw_lines) * 0.45))
    for index, line in enumerate(raw_lines[lower_bound:], start=lower_bound):
        if _looks_like_footnote_start(line):
            split_index = index
            break

    body_lines = [
        PdfLine(text=line, x0=0, y0=index * 12, x1=0, y1=index * 12 + 10, avg_size=10, max_size=10)
        for index, line in enumerate(raw_lines[:split_index])
    ]
    footnote_lines = [
        PdfLine(text=line, x0=0, y0=index * 12, x1=0, y1=index * 12 + 10, avg_size=8, max_size=8)
        for index, line in enumerate(raw_lines[split_index:], start=split_index)
    ]
    page_footnotes, marker_to_id = _parse_page_footnotes(
        page_number,
        footnote_lines,
        parse_footnote=parse_footnote,
    )
    return body_lines, footnote_lines, page_footnotes, marker_to_id


def _page_quality_flags(
    *,
    line_count: int,
    footnotes_found: int,
    body_markers_found: int,
    marker_reference_counts: Dict[str, int],
    ocr_fallback_needed: bool,
    ocr_fallback_used: bool,
    parser_mode: str,
) -> List[str]:
    flags: List[str] = []
    if line_count == 0:
        flags.append("pdf_page_no_text_layer")
    if ocr_fallback_needed and not ocr_fallback_used:
        flags.append("pdf_page_ocr_fallback_needed_but_unavailable")
    if ocr_fallback_used:
        flags.append("pdf_page_ocr_fallback_used")
    if parser_mode == "ocr_text_fallback" and footnotes_found == 0:
        flags.append("pdf_ocr_fallback_no_footnote_layout")
    if footnotes_found and body_markers_found == 0:
        flags.append("pdf_page_footnotes_without_body_markers")
    if footnotes_found > body_markers_found:
        flags.append("pdf_page_footnotes_exceed_body_markers")
    if any(count > 1 for count in marker_reference_counts.values()):
        flags.append("pdf_page_duplicate_body_marker_reference")
    return flags


def parse_pdf_paper(
    file_path: str,
    *,
    extract_quotes: QuoteExtractor,
    parse_footnote: FootnoteParser,
    ocr_page_text_provider: Optional[OcrPageTextProvider] = None,
) -> Dict[str, Any]:
    path = Path(file_path)
    document_title = ""
    paragraphs: List[ParsedParagraph] = []
    footnotes: List[ParsedFootnote] = []
    page_debug: List[Dict[str, Any]] = []
    quality_flags: List[str] = []

    with fitz.open(path) as document:
        for zero_based_index, page in enumerate(document):
            page_number = zero_based_index + 1
            page_height = float(page.rect.height)
            lines = _merge_same_row_lines(_extract_pdf_lines(page))
            text_layer_text = _line_text(lines)
            ocr_fallback_needed = _text_layer_needs_ocr(lines, text_layer_text)
            ocr_fallback_used = False
            parser_mode = "text_layer"
            footnote_top = _infer_footnote_top(lines, page_height)
            body_lines = _strip_running_header_footer(
                [line for line in lines if line.y0 < footnote_top],
                page_height,
            )
            footnote_lines = [line for line in lines if line.y0 >= footnote_top and line.y0 < page_height - 45]
            page_footnotes, marker_to_id = _parse_page_footnotes(
                page_number,
                footnote_lines,
                parse_footnote=parse_footnote,
            )
            if ocr_fallback_needed and ocr_page_text_provider is not None:
                ocr_text = ""
                try:
                    ocr_text = ocr_page_text_provider(page_number)
                except Exception:
                    ocr_text = ""
                if clean_text(ocr_text):
                    (
                        body_lines,
                        footnote_lines,
                        page_footnotes,
                        marker_to_id,
                    ) = _parse_ocr_page_text(
                        page_number,
                        ocr_text,
                        parse_footnote=parse_footnote,
                    )
                    ocr_fallback_used = True
                    parser_mode = "ocr_text_fallback"
            footnotes.extend(page_footnotes)
            body_text = _line_text(body_lines)
            (
                paragraph_text,
                footnote_ids,
                footnote_positions,
                marker_reference_counts,
            ) = _replace_markers_with_positions(
                body_text,
                marker_to_id,
            )
            if paragraph_text:
                quotes = extract_quotes(paragraph_text)
                raw_text = paragraph_text
                paragraphs.append(
                    ParsedParagraph(
                        index=len(paragraphs) + 1,
                        text=paragraph_text,
                        footnote_ids=footnote_ids,
                        quotes=quotes,
                        footnote_positions=footnote_positions,
                        footnote_contexts=build_footnote_contexts(raw_text, footnote_positions),
                        footnote_citation_units=build_footnote_citation_units(raw_text, footnote_positions),
                    )
                )
                if not document_title:
                    title_candidate = paragraph_text[:120]
                    document_title = clean_text(re.split(r"[。！？]", title_candidate)[0])
            page_flags = _page_quality_flags(
                line_count=len(lines),
                footnotes_found=len(page_footnotes),
                body_markers_found=len(footnote_ids),
                marker_reference_counts=marker_reference_counts,
                ocr_fallback_needed=ocr_fallback_needed,
                ocr_fallback_used=ocr_fallback_used,
                parser_mode=parser_mode,
            )
            for flag in page_flags:
                if flag not in quality_flags:
                    quality_flags.append(flag)
            page_debug.append(
                {
                    "page_number": page_number,
                    "parser_mode": parser_mode,
                    "line_count": len(lines),
                    "body_line_count": len(body_lines),
                    "footnote_line_count": len(footnote_lines),
                    "footnote_top": round(footnote_top, 2),
                    "footnotes_found": len(page_footnotes),
                    "body_markers_found": len(footnote_ids),
                    "unique_body_markers_found": len(set(footnote_ids)),
                    "duplicate_body_marker_ids": [
                        note_id for note_id, count in marker_reference_counts.items() if count > 1
                    ],
                    "ocr_fallback_needed": ocr_fallback_needed,
                    "ocr_fallback_used": ocr_fallback_used,
                    "quality_flags": page_flags,
                }
            )

    apply_footnote_title_aliases(footnotes)

    return {
        "document": {
            "title": document_title,
            "file_path": str(path.resolve()),
            "input_format": "pdf",
            "paragraph_count": len(paragraphs),
            "footnote_count": len(footnotes),
        },
        "paragraphs": paragraphs,
        "footnotes": footnotes,
        "pdf_parse_debug": page_debug,
        "quality_flags": quality_flags,
    }
