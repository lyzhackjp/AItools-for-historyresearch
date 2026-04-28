from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Sequence

def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def normalize_page_numbers(page_numbers: Iterable[Any]) -> List[int]:
    normalized: List[int] = []
    for page in page_numbers or []:
        try:
            value = int(page)
        except (TypeError, ValueError):
            continue
        if value >= 1 and value not in normalized:
            normalized.append(value)
    return normalized


def pages_are_consecutive(page_numbers: Sequence[int]) -> bool:
    pages = normalize_page_numbers(page_numbers)
    if len(pages) <= 1:
        return True
    ordered = sorted(pages)
    return ordered == list(range(ordered[0], ordered[-1] + 1))


def page_label_uses_explicit_list(page_label: str) -> bool:
    label = str(page_label or "")
    return bool(re.search(r"\d+\s*[,，、]\s*\d+", label))


def page_label_uses_range(page_label: str) -> bool:
    label = str(page_label or "")
    return bool(re.search(r"\d+\s*[-—－~～]\s*\d+", label))


def split_citation_claims_for_pages(text: str, *, limit: int = 8) -> List[str]:
    cleaned = clean_text(text)
    if not cleaned:
        return []
    raw_parts = [
        clean_text(part)
        for part in re.split(r"(?<=[。！？!?；;])|(?<=[，、,])", cleaned)
        if clean_text(part)
    ]
    if not raw_parts:
        return [cleaned]

    claims: List[str] = []
    buffer = ""
    for part in raw_parts:
        if not buffer:
            buffer = part
            continue
        if len(buffer) < 18 or len(part) < 8:
            buffer = clean_text(buffer + part)
            continue
        claims.append(buffer)
        buffer = part
    if buffer:
        claims.append(buffer)

    deduped: List[str] = []
    for claim in claims:
        if len(claim) >= 6 and claim not in deduped:
            deduped.append(claim)
        if len(deduped) >= limit:
            break
    return deduped or [cleaned]


def classify_page_span(
    page_numbers: Sequence[int],
    *,
    page_label: str = "",
    citation_text: str = "",
    unit_type: str = "",
) -> Dict[str, Any]:
    pages = normalize_page_numbers(page_numbers)
    page_count = len(pages)
    explicit_list = page_label_uses_explicit_list(page_label)
    explicit_range = page_label_uses_range(page_label)
    consecutive = pages_are_consecutive(pages)
    claims = split_citation_claims_for_pages(citation_text)
    comma_like_count = len(re.findall(r"[，、,；;]", str(citation_text or "")))

    if page_count == 0:
        mode = "unmarked"
        reason = "no page numbers parsed"
    elif page_count == 1:
        mode = "single_page"
        reason = "single cited page"
    elif explicit_list or not consecutive:
        mode = "distributed_pages"
        reason = "explicit page list or non-consecutive pages"
    elif page_count == 2:
        mode = "continuous_range"
        reason = "two-page consecutive range"
    elif str(unit_type or "") == "direct_quote" and explicit_range:
        mode = "continuous_range"
        reason = "direct quote across consecutive range"
    elif len(claims) >= 2 or comma_like_count >= 2:
        mode = "distributed_pages"
        reason = "multi-page citation contains multiple claim-like clauses"
    else:
        mode = "range_context"
        reason = "multi-page range without clear claim split"

    return {
        "mode": mode,
        "reason": reason,
        "page_count": page_count,
        "pages": pages,
        "consecutive": consecutive,
        "explicit_list": explicit_list,
        "explicit_range": explicit_range,
        "claim_count": len(claims),
        "claim_candidates": claims,
    }
