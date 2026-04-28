from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence, Tuple
from xml.etree import ElementTree as ET

from .models import CitationCandidate, ParsedFootnote, ParsedParagraph
from .page_span import classify_page_span, split_citation_claims_for_pages


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DOCX_NAMESPACES = {"w": WORD_NS}

QuoteExtractor = Callable[[str], List[str]]
FootnoteParser = Callable[[str, str], ParsedFootnote]
TranslationPicker = Callable[..., str]
FootnoteEligibilityChecker = Callable[[ParsedFootnote], bool]


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def clean_text(text: str) -> str:
    import re

    return re.sub(r"\s+", " ", (text or "").strip())


def _trim_context(text: str, *, limit: int = 280) -> str:
    cleaned = clean_text(text).lstrip("，,。；;：:、 ")
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[-limit:].lstrip("，,。；;：:、 ")


def _quote_spans(text: str) -> List[Tuple[int, int, str]]:
    spans: List[Tuple[int, int, str]] = []
    quote_patterns = [
        r"“([^”]{2,})”",
        r"「([^」]{2,})」",
        r"『([^』]{2,})』",
        r"\"([^\"\n]{2,})\"",
    ]
    for pattern in quote_patterns:
        for match in re.finditer(pattern, text):
            spans.append((match.start(), match.end(), clean_text(match.group(1))))
    spans.sort(key=lambda item: (item[1], item[0]))
    return spans


def _last_sentence_fragment(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    # Semicolons often divide clauses inside one historical claim; a footnote at
    # the end of that sentence usually supports the whole compound sentence.
    delimiters = "。！？.!?"
    end = len(cleaned)
    while end > 0 and cleaned[end - 1] in delimiters:
        end -= 1
    search_area = cleaned[:end]
    last_index = -1
    for delimiter in delimiters:
        last_index = max(last_index, search_area.rfind(delimiter))
    if last_index >= 0:
        return cleaned[last_index + 1 :]
    return cleaned


def _split_claims(text: str) -> List[str]:
    cleaned = clean_text(text)
    if not cleaned:
        return []
    sentence_parts = [
        clean_text(part)
        for part in re.split(r"(?<=[。！？；;.!?])", cleaned)
        if clean_text(part)
    ]
    if not sentence_parts:
        sentence_parts = [cleaned]
    claims: List[str] = []
    for sentence in sentence_parts:
        if len(sentence) <= 160:
            claims.append(sentence)
            continue
        clause_parts = [
            clean_text(part)
            for part in re.split(r"(?<=[，,、；;：:])", sentence)
            if clean_text(part)
        ]
        buffer = ""
        for clause in clause_parts or [sentence]:
            if not buffer:
                buffer = clause
                continue
            if len(buffer) + len(clause) <= 150:
                buffer += clause
            else:
                claims.append(buffer)
                buffer = clause
        if buffer:
            claims.append(buffer)
    deduped: List[str] = []
    for claim in claims:
        normalized = clean_text(claim)
        if len(normalized) >= 4 and normalized not in deduped:
            deduped.append(normalized)
    return deduped


def _leading_unfootnoted_context_until_next_marker(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    future_footnote_sentence = _last_sentence_fragment(cleaned)
    prefix = cleaned
    if future_footnote_sentence and cleaned.endswith(future_footnote_sentence):
        prefix = cleaned[: -len(future_footnote_sentence)]
    return _trim_context(prefix, limit=360)


def _select_citation_text(text: str) -> Tuple[str, str, float, List[str], str]:
    claims = _split_claims(text)
    cleaned = clean_text(text)
    if not cleaned:
        return "", "empty", 0.0, [], "no_context"
    if len(cleaned) < 12 and claims:
        expanded = claims[-1]
        return expanded, "nearest_sentence_expanded", 0.62, claims, "context shorter than 12 chars"
    if len(cleaned) > 180 and claims:
        preferred = next((claim for claim in reversed(claims) if 12 <= len(claim) <= 160), claims[-1])
        return preferred, "previous_clause", 0.58, claims, "long context split into claim candidates"
    if claims and cleaned in claims:
        return cleaned, "nearest_sentence", 0.82, claims, "nearest sentence before footnote"
    return cleaned, "paragraph_span", 0.48, claims, "paragraph span fallback"


def build_footnote_citation_units(raw_text: str, footnote_positions: Dict[str, int]) -> Dict[str, Dict[str, Any]]:
    units: Dict[str, Dict[str, Any]] = {}
    ordered_positions = [
        (note_id, int(position))
        for note_id, position in sorted(footnote_positions.items(), key=lambda item: int(item[1]))
    ]
    quote_spans = _quote_spans(raw_text)
    previous_position = 0

    for index, (note_id, position) in enumerate(ordered_positions):
        next_position = (
            ordered_positions[index + 1][1]
            if index + 1 < len(ordered_positions)
            else None
        )
        bounded_text = raw_text[previous_position:position]
        following_text = raw_text[position:next_position] if next_position is not None else ""
        following_unfootnoted_context = _leading_unfootnoted_context_until_next_marker(following_text)
        context = ""
        prefix_to_marker = raw_text[:position].rstrip()
        marker_is_attached_to_quote = prefix_to_marker.endswith(("”", "」", "』", '"'))
        if marker_is_attached_to_quote:
            bounded_quotes = [
                quote
                for start, end, quote in quote_spans
                if previous_position <= start and end <= position and position - end <= 3
            ]
            if bounded_quotes:
                context = bounded_quotes[-1]
                units[str(note_id)] = {
                    "text": context,
                    "unit_type": "direct_quote",
                    "confidence": 0.95,
                    "reason": "footnote marker is attached to a direct quote",
                    "claim_candidates": [context],
                    "following_unfootnoted_context": following_unfootnoted_context,
                }
                previous_position = position
                continue
        if not context:
            sentence = _last_sentence_fragment(bounded_text)
            if len(clean_text(sentence)) >= 12:
                context = sentence
        if not context:
            context = bounded_text
        selected_text, unit_type, confidence, claims, reason = _select_citation_text(_trim_context(context, limit=520))
        units[str(note_id)] = {
            "text": _trim_context(selected_text),
            "unit_type": unit_type,
            "confidence": confidence,
            "reason": reason,
            "claim_candidates": claims[:8],
            "following_unfootnoted_context": following_unfootnoted_context,
        }
        previous_position = position
    return units


def build_footnote_contexts(raw_text: str, footnote_positions: Dict[str, int]) -> Dict[str, str]:
    units = build_footnote_citation_units(raw_text, footnote_positions)
    return {note_id: str(unit.get("text") or "") for note_id, unit in units.items()}


def extract_paragraph_content_with_positions(
    node: ET.Element,
) -> Tuple[str, List[str], Dict[str, int], str]:
    texts: List[str] = []
    footnote_ids: List[str] = []
    footnote_positions: Dict[str, int] = {}
    raw_text = ""
    for element in node.iter():
        name = local_name(element.tag)
        if name == "t" and element.text:
            texts.append(element.text)
            raw_text += element.text
        elif name == "footnoteReference":
            note_id = element.attrib.get(f"{{{WORD_NS}}}id")
            if note_id:
                footnote_ids.append(note_id)
                footnote_positions[str(note_id)] = len(raw_text)
    return clean_text("".join(texts)), footnote_ids, footnote_positions, raw_text


def extract_paragraph_content(node: ET.Element) -> Tuple[str, List[str]]:
    text, footnote_ids, _positions, _raw_text = extract_paragraph_content_with_positions(node)
    return text, footnote_ids


def collect_text(node: ET.Element) -> str:
    return clean_text("".join(element.text or "" for element in node.iter() if local_name(element.tag) == "t"))


def parse_docx_document(
    file_path: str,
    *,
    extract_quotes: QuoteExtractor,
    parse_footnote: FootnoteParser,
) -> Dict[str, Any]:
    path = Path(file_path)
    document_title = ""
    paragraphs: List[ParsedParagraph] = []
    footnotes: List[ParsedFootnote] = []

    with zipfile.ZipFile(path, "r") as archive:
        document_xml = ET.fromstring(archive.read("word/document.xml"))
        paragraph_nodes = document_xml.findall(".//w:body/w:p", DOCX_NAMESPACES)
        running_index = 0
        for node in paragraph_nodes:
            text, footnote_ids, footnote_positions, raw_text = extract_paragraph_content_with_positions(node)
            if not text:
                continue
            running_index += 1
            quotes = extract_quotes(text)
            paragraphs.append(
                ParsedParagraph(
                    index=running_index,
                    text=text,
                    footnote_ids=footnote_ids,
                    quotes=quotes,
                    footnote_positions=footnote_positions,
                    footnote_contexts=build_footnote_contexts(raw_text, footnote_positions),
                    footnote_citation_units=build_footnote_citation_units(raw_text, footnote_positions),
                )
            )
            if not document_title:
                document_title = text

        if "word/footnotes.xml" in archive.namelist():
            footnotes_xml = ET.fromstring(archive.read("word/footnotes.xml"))
            for node in footnotes_xml.findall(".//w:footnote", DOCX_NAMESPACES):
                note_id = node.attrib.get(f"{{{WORD_NS}}}id")
                note_type = node.attrib.get(f"{{{WORD_NS}}}type")
                if note_type in {"separator", "continuationSeparator"}:
                    continue
                if not note_id:
                    continue
                text = collect_text(node)
                if not text:
                    continue
                footnotes.append(parse_footnote(note_id, text))

        if "docProps/core.xml" in archive.namelist():
            try:
                core_xml = ET.fromstring(archive.read("docProps/core.xml"))
                for element in core_xml.iter():
                    if local_name(element.tag) == "title" and element.text:
                        document_title = element.text.strip() or document_title
                        break
            except ET.ParseError:
                pass

    return {
        "document": {
            "title": document_title,
            "file_path": str(path.resolve()),
            "paragraph_count": len(paragraphs),
            "footnote_count": len(footnotes),
        },
        "paragraphs": paragraphs,
        "footnotes": footnotes,
    }


def build_citation_candidates(
    paragraphs: Sequence[ParsedParagraph],
    footnotes: Sequence[ParsedFootnote],
    *,
    pick_translation_text: TranslationPicker,
    is_verifiable_footnote: FootnoteEligibilityChecker,
) -> List[CitationCandidate]:
    footnote_map = {item.id: item for item in footnotes}
    results: List[CitationCandidate] = []

    for paragraph in paragraphs:
        if not paragraph.footnote_ids:
            continue

        eligible_footnotes = [
            footnote_map[footnote_id]
            for footnote_id in paragraph.footnote_ids
            if footnote_id in footnote_map and is_verifiable_footnote(footnote_map[footnote_id])
        ]
        if not eligible_footnotes:
            continue

        for footnote in eligible_footnotes:
            try:
                translation_text = pick_translation_text(paragraph, footnote_id=footnote.id)
            except TypeError:
                translation_text = pick_translation_text(paragraph)
            if not translation_text:
                continue
            results.append(
                candidate := CitationCandidate(
                    candidate_id=f"p{paragraph.index}-f{footnote.id}",
                    paragraph_index=paragraph.index,
                    paragraph_text=paragraph.text,
                    translation_text=translation_text,
                    footnote_id=footnote.id,
                    footnote=footnote,
                )
            )
            citation_unit = (paragraph.footnote_citation_units or {}).get(str(footnote.id))
            if citation_unit:
                citation_unit = dict(citation_unit)
                page_span = classify_page_span(
                    footnote.page_numbers,
                    page_label=footnote.page_label,
                    citation_text=str(citation_unit.get("text") or translation_text),
                    unit_type=str(citation_unit.get("unit_type") or ""),
                )
                following_context = str(citation_unit.get("following_unfootnoted_context") or "")
                if page_span["mode"] == "distributed_pages" and following_context:
                    expanded_text = clean_text(f"{translation_text}{following_context}")
                    if expanded_text:
                        candidate.translation_text = expanded_text
                        citation_unit["text"] = expanded_text
                        citation_unit["unit_type"] = "multi_page_distributed_span"
                        citation_unit["confidence"] = min(float(citation_unit.get("confidence") or 0.7), 0.74)
                        citation_unit["reason"] = (
                            f"{citation_unit.get('reason') or 'nearest citation unit'}; "
                            "expanded with following unfootnoted context for distributed multi-page citation"
                        )
                        citation_unit["claim_candidates"] = split_citation_claims_for_pages(expanded_text)
                        page_span = classify_page_span(
                            footnote.page_numbers,
                            page_label=footnote.page_label,
                            citation_text=expanded_text,
                            unit_type=str(citation_unit.get("unit_type") or ""),
                        )
                candidate.artifacts["citation_unit"] = citation_unit
                candidate.artifacts["page_span"] = page_span

    return results
