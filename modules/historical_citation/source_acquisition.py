from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import requests

from .models import NDLSearchMatch
from .page_mapping import estimate_scan_page_for_book_page


def is_likely_digital_ndl_pid(value: Optional[str]) -> bool:
    token = str(value or "")
    return token.isdigit() and len(token) >= 7


def select_preferred_source_match(matches: Sequence[NDLSearchMatch]) -> Optional[NDLSearchMatch]:
    top_match = next((match for match in matches if is_likely_digital_ndl_pid(match.ndl_id)), None)
    if top_match is not None:
        return top_match
    top_match = next((match for match in matches if match.ndl_id), None)
    if top_match is not None:
        return top_match
    return matches[0] if matches else None


def expand_page_window(page_number: int, page_window: int) -> List[int]:
    pages = [page_number]
    for offset in range(1, page_window + 1):
        pages.extend([page_number - offset, page_number + offset])
    deduped: List[int] = []
    for page in pages:
        if page not in deduped:
            deduped.append(page)
    return deduped


def build_download_page_plan(
    page_numbers: Sequence[int],
    *,
    page_window: int,
    page_mapping: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    normalized_pages = [int(page) for page in page_numbers] or [1]
    if page_mapping:
        mapped_pages = [
            scan_page
            for scan_page in (
                estimate_scan_page_for_book_page(page_mapping, page) for page in normalized_pages
            )
            if scan_page is not None
        ]
        if mapped_pages:
            return {
                "start_page": int(page_mapping["start_scan_page"]),
                "end_page": int(page_mapping["end_scan_page"]),
                "mapped_footnote_pages": mapped_pages,
                "page_mapping": page_mapping,
                "note": (
                    "double_page_mapping_used: "
                    f"book_p{page_mapping['anchor_book_page']}->scan_p{page_mapping['anchor_scan_page']}"
                ),
            }

    return {
        "start_page": max(1, min(normalized_pages) - page_window),
        "end_page": max(normalized_pages) + page_window,
        "mapped_footnote_pages": [],
        "page_mapping": None,
        "note": "",
    }


def build_restricted_download_requests(
    *,
    keywords: Iterable[str],
    top_match: Optional[NDLSearchMatch],
    fallback_title: str,
    output_dir: Path,
    start_page: int,
    end_page: int,
) -> List[Dict[str, Any]]:
    requests_payload: List[Dict[str, Any]] = []
    filename_token = top_match.ndl_id if top_match and top_match.ndl_id else uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"{fallback_title}:{start_page}-{end_page}",
    ).hex[:12]
    filename = f"ndl_{filename_token}_p{start_page}-p{end_page}.pdf"
    for keyword in keywords:
        requests_payload.append(
            {
                "keyword": keyword,
                "filename": filename,
                "ndl_id": top_match.ndl_id if top_match else None,
                "title": top_match.title if top_match else fallback_title,
                "output_dir": str(output_dir),
                "restricted": True,
                "headless": True,
                "start_page": start_page,
                "end_page": end_page,
                "max_attempts": 3,
            }
        )
    return requests_payload


def download_public_pdf(
    match: NDLSearchMatch,
    *,
    output_dir: Path,
    request_get: Callable[..., Any] = requests.get,
    filename_token: Optional[str] = None,
) -> Optional[str]:
    pdf_url = match.pdf_url or (f"https://dl.ndl.go.jp/pid/{match.ndl_id}/pdf" if match.ndl_id else None)
    if not pdf_url:
        return None

    filename = f"{match.ndl_id or filename_token or uuid.uuid4().hex}.pdf"
    target_path = output_dir / filename
    response = request_get(pdf_url, timeout=120, stream=True)
    if response.status_code != 200:
        return None

    content_type = response.headers.get("content-type", "").lower()
    if "pdf" not in content_type and not pdf_url.lower().endswith(".pdf"):
        return None

    with open(target_path, "wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 128):
            if chunk:
                handle.write(chunk)
    return str(target_path.resolve())
