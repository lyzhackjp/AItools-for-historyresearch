from __future__ import annotations

import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


PAGE_MAPPING_CACHE_FILENAME = "page_mapping_cache.json"
PAGE_MAPPING_FAILURE_CACHE_FILENAME = "page_mapping_failure_cache.json"


def safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_page_mapping(mapping: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    anchor_scan = safe_int(mapping.get("anchor_scan_page"))
    anchor_book = safe_int(mapping.get("anchor_book_page"))
    if anchor_scan is None or anchor_book is None:
        return None
    pages_per_scan = safe_int(mapping.get("pages_per_scan")) or 2
    pages_per_scan = max(1, min(int(pages_per_scan), 16))
    normalized = {
        "anchor_scan_page": anchor_scan,
        "anchor_book_page": anchor_book,
        "pages_per_scan": pages_per_scan,
        "sample_scan_page": mapping.get("sample_scan_page"),
        "sample_title": mapping.get("sample_title"),
    }
    for optional_key in (
        "mapping_method",
        "confidence",
        "sample_toc_excerpt",
        "sample_body_excerpt",
        "ndl_id",
        "source_level_cache_key",
        "source_level_cache_alias",
        "source_level_cache_note",
    ):
        value = mapping.get(optional_key)
        if value is not None:
            normalized[optional_key] = value
    return normalized


def _normalize_for_page_mapping(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = re.sub(r"\s+", "", text)
    return re.sub(r"[^\w一-龥ぁ-んァ-ヶ]", "", text)


def _looks_like_toc(text: str) -> bool:
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    if any(marker in normalized for marker in ("目次", "目録", "Contents", "CONTENTS")):
        return True
    return False


_PAGE_DIGIT_VALUES = {
    "0": 0,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "〇": 0,
    "○": 0,
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
_PAGE_UNIT_VALUES = {"十": 10, "百": 100, "千": 1000}


def parse_toc_page_number_token(token: str) -> Optional[int]:
    normalized = unicodedata.normalize("NFKC", str(token or "")).strip()
    normalized = normalized.replace("O", "〇").replace("o", "〇")
    if not normalized:
        return None
    if normalized.isdigit():
        value = int(normalized)
        return value if value > 0 else None
    if all(char in _PAGE_DIGIT_VALUES for char in normalized):
        value = int("".join(str(_PAGE_DIGIT_VALUES[char]) for char in normalized))
        return value if value > 0 else None
    if not all(char in _PAGE_DIGIT_VALUES or char in _PAGE_UNIT_VALUES for char in normalized):
        return None

    total = 0
    current = 0
    for char in normalized:
        if char in _PAGE_DIGIT_VALUES:
            current = _PAGE_DIGIT_VALUES[char]
            continue
        unit = _PAGE_UNIT_VALUES[char]
        total += (current or 1) * unit
        current = 0
    value = total + current
    return value if value > 0 else None


def _iter_body_heading_candidates(text: str) -> List[str]:
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    candidates: List[str] = []
    patterns = [
        r"第[一二三四五六七八九十百0-9０-９]+[章節部編篇][^\n]{0,40}",
        r"(?:序|序章|序論|緒言|緒論|凡例|はしがき|まえがき|第一)[^\n]{0,30}",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, normalized):
            heading = match.group(0).strip(" 　\t\r\n、。・.,")
            if len(_normalize_for_page_mapping(heading)) >= 2 and heading not in candidates:
                candidates.append(heading)
    return candidates


def _toc_page_number_for_heading(toc_text: str, heading: str) -> Optional[int]:
    normalized_toc = _normalize_for_page_mapping(toc_text)
    signature = _normalize_for_page_mapping(heading)
    if not normalized_toc or not signature:
        return None

    signatures = [signature]
    for length in (24, 18, 14, 10, 8, 6, 4):
        if len(signature) >= length:
            signatures.append(signature[:length])
    for prefix in ("序", "緒言", "緒論", "凡例", "はしがき", "まえがき"):
        if signature.startswith(_normalize_for_page_mapping(prefix)):
            signatures.append(_normalize_for_page_mapping(prefix))

    seen_signatures: set[str] = set()
    for current_signature in signatures:
        if len(current_signature) < 2 or current_signature in seen_signatures:
            continue
        seen_signatures.add(current_signature)
        index = normalized_toc.find(current_signature)
        if index == -1:
            continue
        after_heading = normalized_toc[index + len(current_signature) : index + len(current_signature) + 80]
        number_match = re.search(r"([0-9０-９〇○零一二三四五六七八九十百千]{1,6})", after_heading)
        if not number_match:
            continue
        page_number = parse_toc_page_number_token(number_match.group(1))
        if page_number > 0:
            return page_number
    return None


def infer_page_mapping_from_front_matter_texts(
    page_texts: Dict[int, str],
) -> Optional[Dict[str, Any]]:
    """Infer book-page to NDL-scan-page mapping from TOC/body OCR samples.

    NDL scan pages often contain two facing book pages. Footnotes, however,
    usually cite the original book page. This helper anchors the conversion by
    finding a heading in the body and the same heading plus page number in the
    front matter.
    """

    normalized_texts: Dict[int, str] = {
        int(scan_page): str(text or "")
        for scan_page, text in sorted(page_texts.items())
        if safe_int(scan_page) is not None
    }
    if not normalized_texts:
        return None

    toc_pages: List[Tuple[int, str]] = [
        (scan_page, text)
        for scan_page, text in normalized_texts.items()
        if _looks_like_toc(text)
    ]
    if not toc_pages:
        return None

    candidates: List[Dict[str, Any]] = []
    for scan_page, text in normalized_texts.items():
        if _looks_like_toc(text):
            continue
        earlier_toc_pages = [
            (toc_scan_page, toc_text)
            for toc_scan_page, toc_text in toc_pages
            if toc_scan_page < scan_page
        ]
        if not earlier_toc_pages:
            continue
        for heading in _iter_body_heading_candidates(text):
            for toc_scan_page, toc_text in earlier_toc_pages:
                book_page = _toc_page_number_for_heading(toc_text, heading)
                if book_page is None:
                    continue
                candidates.append(
                    {
                        "anchor_scan_page": int(scan_page),
                        "anchor_book_page": int(book_page),
                        "sample_scan_page": int(toc_scan_page),
                        "sample_title": heading[:80],
                        "mapping_method": "front_matter_toc_heading",
                        "confidence": 0.82,
                        "sample_toc_excerpt": toc_text[:240],
                        "sample_body_excerpt": text[:240],
                    }
                )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            int(item["anchor_book_page"]),
            int(item["anchor_scan_page"]),
            -float(item.get("confidence") or 0),
        )
    )
    return normalize_page_mapping(candidates[0])


def _extract_visible_page_number_lines(text: str) -> List[int]:
    page_numbers: List[int] = []
    for raw_line in str(text or "").splitlines():
        line = unicodedata.normalize("NFKC", raw_line).strip()
        line = re.sub(r"[\s\.\-—_]+", "", line)
        if not line:
            continue
        if re.fullmatch(r"[0-9]{1,4}", line):
            value = int(line)
        else:
            value = parse_toc_page_number_token(line) or 0
        if 1 <= value <= 3000 and value not in page_numbers:
            page_numbers.append(value)
    return sorted(page_numbers)


def _best_visible_page_number_cluster(numbers: List[int], pages_per_scan: int) -> List[int]:
    if not numbers:
        return []
    unique_numbers = sorted(set(int(number) for number in numbers))
    best_cluster: List[int] = []
    for index, start_number in enumerate(unique_numbers):
        end_number = start_number + max(1, pages_per_scan) - 1
        cluster = [number for number in unique_numbers[index:] if number <= end_number]
        if not cluster:
            continue
        best_span = best_cluster[-1] - best_cluster[0] + 1 if best_cluster else 0
        span = cluster[-1] - cluster[0] + 1
        best_max = best_cluster[-1] if best_cluster else 0
        if (len(cluster), span, cluster[-1]) > (len(best_cluster), best_span, best_max):
            best_cluster = cluster
    return best_cluster


def infer_page_mapping_from_visible_page_numbers(
    page_texts: Dict[int, str],
) -> Optional[Dict[str, Any]]:
    """Infer mapping from isolated printed page numbers visible in OCR output.

    Some facsimile volumes do not expose a usable front-matter TOC. Their OCR,
    however, often captures printed page numbers as standalone lines. We fit a
    conservative linear page-count model from the max visible page number in
    consecutive scans.
    """

    scan_numbers: Dict[int, List[int]] = {}
    for raw_scan_page, text in sorted(page_texts.items()):
        scan_page = safe_int(raw_scan_page)
        if scan_page is None:
            continue
        numbers = _extract_visible_page_number_lines(text)
        if len(numbers) >= 2:
            scan_numbers[scan_page] = numbers

    if len(scan_numbers) < 3:
        return None

    scan_maxima = [(scan_page, max(numbers)) for scan_page, numbers in sorted(scan_numbers.items())]
    deltas: List[int] = []
    for (prev_scan, prev_max), (scan_page, current_max) in zip(scan_maxima, scan_maxima[1:]):
        scan_delta = scan_page - prev_scan
        page_delta = current_max - prev_max
        if scan_delta <= 0 or page_delta <= 0:
            continue
        per_scan = round(page_delta / scan_delta)
        if 1 <= per_scan <= 16:
            deltas.append(per_scan)
    if not deltas:
        return None

    deltas.sort()
    pages_per_scan = int(deltas[len(deltas) // 2])
    if pages_per_scan < 1:
        return None

    anchor_scan = None
    anchor_book = None
    for scan_page, numbers in sorted(scan_numbers.items()):
        cluster = _best_visible_page_number_cluster(numbers, pages_per_scan)
        if not cluster:
            continue
        max_number = max(cluster)
        min_number = min(cluster)
        min_count = 2 if pages_per_scan <= 2 else max(3, min(5, pages_per_scan // 2 + 1))
        min_span = pages_per_scan if pages_per_scan <= 2 else max(2, pages_per_scan - 2)
        if len(cluster) < min_count or max_number - min_number + 1 < min_span:
            continue
        anchor_scan = scan_page
        anchor_book = max(1, max_number - pages_per_scan + 1)
        break
    if anchor_scan is None or anchor_book is None:
        return None

    return normalize_page_mapping(
        {
            "anchor_scan_page": anchor_scan,
            "anchor_book_page": anchor_book,
            "pages_per_scan": pages_per_scan,
            "sample_scan_page": anchor_scan,
            "sample_title": f"visible_page_numbers:{anchor_book}-{anchor_book + pages_per_scan - 1}",
            "mapping_method": "visible_page_number_lines",
            "confidence": 0.7,
            "sample_body_excerpt": str(page_texts.get(anchor_scan, ""))[:240],
        }
    )


def load_page_mapping_cache(
    output_dir: Path,
    *,
    current_cache: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    cache: Dict[str, Dict[str, Any]] = dict(current_cache or {})
    cache_path = output_dir / PAGE_MAPPING_CACHE_FILENAME
    if not cache_path.exists():
        return cache
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return cache

    mappings = payload.get("mappings", payload) if isinstance(payload, dict) else {}
    if not isinstance(mappings, dict):
        return cache
    for ndl_id, mapping in mappings.items():
        if not isinstance(mapping, dict):
            continue
        normalized = normalize_page_mapping(mapping)
        if normalized is not None:
            cache[str(ndl_id)] = normalized
    return cache


def save_page_mapping_cache(
    output_dir: Path,
    ndl_id: str,
    mapping: Dict[str, Any],
    *,
    current_cache: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    normalized = normalize_page_mapping(mapping)
    if normalized is None:
        return dict(current_cache or {})

    output_dir.mkdir(parents=True, exist_ok=True)
    cache = load_page_mapping_cache(output_dir, current_cache=current_cache)
    cache[str(ndl_id)] = normalized
    payload = {
        "version": 1,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "mappings": cache,
    }
    cache_path = output_dir / PAGE_MAPPING_CACHE_FILENAME
    tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(cache_path)
    return cache


def load_page_mapping_failure_cache(
    output_dir: Path,
    *,
    current_cache: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    cache: Dict[str, str] = dict(current_cache or {})
    cache_path = output_dir / PAGE_MAPPING_FAILURE_CACHE_FILENAME
    if not cache_path.exists():
        return cache
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return cache

    failures = payload.get("failures", payload) if isinstance(payload, dict) else {}
    if not isinstance(failures, dict):
        return cache
    for ndl_id, record in failures.items():
        if isinstance(record, dict):
            reason = record.get("reason")
        else:
            reason = record
        if reason:
            cache[str(ndl_id)] = str(reason)
    return cache


def save_page_mapping_failure_cache(
    output_dir: Path,
    ndl_id: str,
    reason: str,
    *,
    current_cache: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cache = load_page_mapping_failure_cache(output_dir, current_cache=current_cache)
    cache[str(ndl_id)] = str(reason or "page_mapping_failed")
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    payload = {
        "version": 1,
        "updated_at": now,
        "failures": {
            key: {"reason": value, "updated_at": now}
            for key, value in sorted(cache.items())
        },
    }
    cache_path = output_dir / PAGE_MAPPING_FAILURE_CACHE_FILENAME
    tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(cache_path)
    return cache


def estimate_scan_page_for_book_page(
    page_mapping: Optional[Dict[str, Any]],
    book_page: int,
) -> Optional[int]:
    if not page_mapping:
        return None
    anchor_scan = safe_int(page_mapping.get("anchor_scan_page"))
    anchor_book = safe_int(page_mapping.get("anchor_book_page"))
    if anchor_scan is None or anchor_book is None or book_page < anchor_book:
        return None
    pages_per_scan = safe_int(page_mapping.get("pages_per_scan")) or 2
    pages_per_scan = max(1, int(pages_per_scan))
    return anchor_scan + max(0, (book_page - anchor_book) // pages_per_scan)


def estimate_book_pages_from_scan_page(
    page_mapping: Optional[Dict[str, Any]],
    scan_page: int,
) -> List[int]:
    if not page_mapping:
        return []
    anchor_scan = safe_int(page_mapping.get("anchor_scan_page"))
    anchor_book = safe_int(page_mapping.get("anchor_book_page"))
    if anchor_scan is None or anchor_book is None or scan_page < anchor_scan:
        return []
    pages_per_scan = safe_int(page_mapping.get("pages_per_scan")) or 2
    pages_per_scan = max(1, int(pages_per_scan))
    start_book_page = anchor_book + (scan_page - anchor_scan) * pages_per_scan
    return list(range(start_book_page, start_book_page + pages_per_scan))


def build_scan_page_range(
    page_mapping: Dict[str, Any],
    book_pages: List[int],
    *,
    page_window: int,
) -> Optional[Dict[str, Any]]:
    normalized = normalize_page_mapping(page_mapping)
    if normalized is None or not book_pages:
        return None
    anchor_scan = normalized["anchor_scan_page"]
    anchor_book = normalized["anchor_book_page"]
    pages_per_scan = max(1, int(normalized.get("pages_per_scan") or 2))

    start_book = max(1, min(book_pages) - page_window)
    end_book = max(book_pages) + page_window
    start_scan = anchor_scan + max(0, (start_book - anchor_book) // pages_per_scan)
    end_scan = anchor_scan + max(0, (end_book - anchor_book) // pages_per_scan)
    return {
        "anchor_scan_page": anchor_scan,
        "anchor_book_page": anchor_book,
        "pages_per_scan": pages_per_scan,
        "start_book_page": start_book,
        "end_book_page": end_book,
        "start_scan_page": start_scan,
        "end_scan_page": max(start_scan, end_scan),
        "sample_scan_page": normalized.get("sample_scan_page"),
        "sample_title": normalized.get("sample_title"),
    }
