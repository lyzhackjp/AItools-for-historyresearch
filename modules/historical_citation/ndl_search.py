from __future__ import annotations

import html
import re
import time
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlencode, urljoin
from xml.etree import ElementTree as ET

import requests

from .contained_sources import contained_source_search_titles, normalize_source_lookup_title
from .docx_parser import clean_text
from .footnote_parser import extract_volume_terms
from .models import ParsedFootnote


NDL_SRU_URL = "https://ndlsearch.ndl.go.jp/api/sru"
NDL_DIGITAL_API_URL = "https://dl.ndl.go.jp/api"
NDLSEARCH_SEARCH_URL = "https://ndlsearch.ndl.go.jp/search"
NDLSEARCH_BOOK_RE = re.compile(r"https?://ndlsearch\.ndl\.go\.jp/(?:[a-z]{2}/)?books/([A-Za-z0-9_-]+)")
NDLSEARCH_RELATIVE_BOOK_RE = re.compile(r"href=[\"'](/(?:[a-z]{2}/)?books/([A-Za-z0-9_-]+))[\"']")
NDL_DIGITAL_PID_RE = re.compile(r"dl\.ndl\.go\.jp/(?:pid|info:ndljp/pid)/(\d{6,})")


def normalize_match_text(text: str) -> str:
    cleaned = unicodedata.normalize("NFKC", clean_text(text))
    cleaned = re.sub(r"[（(][^）)]*[）)]", "", cleaned)
    cleaned = (
        cleaned.replace("人", "亻")
        .replace("戰", "戦")
        .replace("國", "国")
        .replace("會", "会")
        .replace("體", "体")
        .replace("訓", "训")
        .replace("號", "号")
        .replace("竜", "龍")
        .replace("實", "実")
        .replace("踐", "践")
        .replace("聽", "聴")
        .replace("營", "営")
        .replace("廳", "庁")
        .replace("驒", "駄")
        .replace("覺", "覚")
        .replace("證", "証")
        .replace("証", "証")
        .replace("擔", "担")
        .replace("豫", "予")
        .replace("終", "终")
        .replace("爐", "炉")
        .replace("兒", "児")
        .replace("聲", "声")
        .replace("變", "変")
        .replace("號", "号")
        .replace("關", "関")
        .replace("縣", "県")
        .replace("處", "処")
        .replace("祿", "禄")
        .replace("學", "学")
        .replace("與", "与")
    )
    cleaned = re.sub(r"[「」『』《》“”\"'`・･、，。．：:；;（）()！？【】\[\]\-—\s]", "", cleaned)
    return cleaned.lower()


def extract_japanese_era_years(text: str) -> Dict[str, List[int]]:
    normalized = unicodedata.normalize("NFKC", text or "")
    era_years: Dict[str, List[int]] = {}
    for era, raw_year in re.findall(r"(明治|大正|昭和|平成|令和)\s*([0-9]+|元)\s*年?", normalized):
        year = 1 if raw_year == "元" else int(raw_year)
        era_years.setdefault(era, [])
        if year not in era_years[era]:
            era_years[era].append(year)
    return era_years


def score_ndl_record(
    footnote: ParsedFootnote,
    *,
    title: str,
    author: Optional[str],
    year: Optional[str],
    publisher: Optional[str],
) -> float:
    footnote_title = normalize_match_text(footnote.title)
    record_title = normalize_match_text(title)
    title_ratio = SequenceMatcher(None, footnote_title, record_title).ratio() if footnote_title and record_title else 0.0
    score = title_ratio * 0.7
    host_title = getattr(footnote, "host_title", "") or ""
    host_score = 0.0
    if host_title:
        host_lookup = normalize_source_lookup_title(host_title)
        record_lookup = normalize_source_lookup_title(title)
        host_ratio = SequenceMatcher(None, host_lookup, record_lookup).ratio() if host_lookup and record_lookup else 0.0
        host_score = host_ratio * 0.82
        if host_lookup and record_lookup and (host_lookup in record_lookup or record_lookup in host_lookup):
            host_score = max(host_score, 0.86)
        score = max(score, host_score)

    if footnote_title and record_title and footnote_title in record_title:
        score += 0.15

    footnote_has_subtitle = bool(re.search(r"[：:\-—のと・／/\s]", footnote.title or ""))
    significant_terms = [
        normalize_match_text(term)
        for term in title_query_terms(footnote.title)
        if len(normalize_match_text(term)) >= 4
    ]
    if (
        not host_score
        and footnote_has_subtitle
        and significant_terms
        and not any(term in record_title for term in significant_terms)
    ):
        score = min(score * 0.45, 0.19)

    footnote_era_years = extract_japanese_era_years(footnote.title)
    record_era_years = extract_japanese_era_years(title)
    for era, expected_years in footnote_era_years.items():
        record_years = record_era_years.get(era) or []
        if record_years and not set(expected_years).intersection(record_years):
            return min(score * 0.25, 0.19)
        if record_years and set(expected_years).intersection(record_years):
            score += 0.1

    normalized_author = normalize_match_text(footnote.author)
    record_author = normalize_match_text(author or "")
    if normalized_author and record_author and (normalized_author in record_author or record_author in normalized_author):
        score += 0.1

    if footnote.year and year and str(footnote.year)[:4] == str(year)[:4]:
        score += 0.05

    normalized_publisher = normalize_match_text(footnote.publisher)
    record_publisher = normalize_match_text(publisher or "")
    if normalized_publisher and record_publisher and normalized_publisher in record_publisher:
        score += 0.03

    return min(score, 1.0)


def title_query_terms(title: str) -> List[str]:
    if not title:
        return []
    primary_parts = [part for part in re.split(r"[：:\-—]", title) if part.strip()]
    terms: List[str] = []
    for part in primary_parts:
        cleaned = clean_text(part)
        if cleaned and cleaned not in terms:
            terms.append(cleaned)
        sub_chunks = [
            clean_text(chunk)
            for chunk in re.split(r"[のと・／/]", cleaned)
            if clean_text(chunk)
        ]
        for chunk in sub_chunks:
            if chunk not in terms:
                terms.append(chunk)
    extra_chunks = re.findall(r"[\u3040-\u30ff\u3400-\u9fffA-Za-z0-9]{2,}", title)
    for chunk in extra_chunks:
        if chunk not in terms:
            terms.append(chunk)
    return terms[:6]


def author_query_terms(author: str) -> List[str]:
    if not author:
        return []
    authors = [
        clean_text(item)
        for item in re.split(r"[、,，;；]", author)
        if clean_text(item)
    ]
    return authors[:2]


def title_query_variants(title: str) -> List[str]:
    """Generate conservative NDL title variants for compound Japanese titles."""

    cleaned = clean_text(title)
    if not cleaned:
        return []
    variants: List[str] = []

    def add(value: str) -> None:
        normalized = clean_text(value)
        if normalized and normalized not in variants:
            variants.append(normalized)

    add(cleaned)
    add(re.sub(r"[・·／/、，,;；]+", " ", cleaned))
    add(re.sub(r"[\s　・·／/、，,;；]+", "", cleaned))
    for part in re.split(r"[・·／/、，,;；]+", cleaned):
        add(part)

    orthographic_pairs = (("国", "國"), ("条", "條"), ("体", "體"), ("学", "學"), ("会", "會"))
    snapshot = list(variants)
    for variant in snapshot:
        old_style = variant
        new_style = variant
        for modern, historical in orthographic_pairs:
            old_style = old_style.replace(modern, historical)
            new_style = new_style.replace(historical, modern)
        add(old_style)
        add(new_style)
    return variants[:10]


def iter_ndl_search_keywords(footnote: ParsedFootnote) -> List[str]:
    keywords: List[str] = []
    source_titles = contained_source_search_titles(footnote)
    host_title = getattr(footnote, "host_title", "") or ""
    contained_title = getattr(footnote, "contained_title", "") or ""
    volume_terms = extract_volume_terms(getattr(footnote, "text", "") or "")
    volume_candidates = [
        " ".join(part for part in [footnote.title, term] if part).strip()
        for term in volume_terms
    ]
    raw_candidates = []
    if volume_terms and not host_title:
        raw_candidates.extend([footnote.ndl_keyword, *volume_candidates])
    raw_candidates.extend(
        [
            *source_titles,
            " ".join(part for part in [host_title, contained_title or footnote.title] if part).strip(),
            footnote.ndl_keyword,
            " ".join(part for part in [footnote.title, footnote.author] if part).strip(),
            footnote.title,
            *title_query_variants(footnote.title),
        ]
    )
    compact_title = clean_text(re.sub(r"[：:「」『』《》\-\u2014\u3000]+", " ", footnote.title or ""))
    if compact_title:
        raw_candidates.append(compact_title)
    title_terms = title_query_terms(footnote.title)
    author_terms = author_query_terms(footnote.author)
    raw_candidates.extend(
        [
            " ".join(part for part in [title_terms[0] if title_terms else "", title_terms[-1] if len(title_terms) >= 2 else ""]).strip(),
            " ".join(part for part in [title_terms[0] if title_terms else "", author_terms[0] if author_terms else ""]).strip(),
            " ".join(title_terms[:3]).strip(),
        ]
    )
    for item in raw_candidates:
        cleaned = clean_text(item)
        if cleaned and cleaned not in keywords:
            keywords.append(cleaned)
    return keywords[:6]


def strip_ndlsearch_html(value: str) -> str:
    cleaned = re.sub(r"<script\b.*?</script>", " ", value or "", flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<style\b.*?</style>", " ", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    return clean_text(re.sub(r"\s+", " ", cleaned))


def extract_pdf_page_hint(text: str) -> Optional[int]:
    normalized = unicodedata.normalize("NFKC", text or "")
    patterns = [
        r"(?:PDF|pdf)?\s*(?:ページ|頁|p\.?|コマ)\s*[:：]?\s*(\d{1,5})",
        r"(\d{1,5})\s*(?:ページ|頁|p\.?|コマ)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if not match:
            continue
        try:
            value = int(match.group(1))
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


def _query_in_text(query: str, text: str) -> bool:
    query_lookup = normalize_source_lookup_title(query)
    text_lookup = normalize_source_lookup_title(text)
    return bool(query_lookup and text_lookup and query_lookup in text_lookup)


def _snippet_around_query(query: str, text: str, *, radius: int = 90) -> str:
    if not text:
        return ""
    if query and query in text:
        index = text.find(query)
    else:
        query_lookup = normalize_source_lookup_title(query)
        text_lookup = normalize_source_lookup_title(text)
        index = text_lookup.find(query_lookup) if query_lookup else -1
        if index >= 0 and len(text_lookup) != len(text):
            index = max(0, min(len(text), index))
    if index < 0:
        return text[: radius * 2].strip()
    start = max(0, index - radius)
    end = min(len(text), index + len(query) + radius)
    return text[start:end].strip()


def extract_ndlsearch_fulltext_hits(
    html_text: str,
    keyword: str,
    *,
    base_url: str = "https://ndlsearch.ndl.go.jp",
    max_results: int = 5,
) -> List[Dict[str, Any]]:
    normalized = _normalize_embedded_url_text(html_text)
    matches = list(NDLSEARCH_RELATIVE_BOOK_RE.finditer(normalized))
    hits_by_id: Dict[str, Dict[str, Any]] = {}
    for index, match in enumerate(matches):
        href, book_id = match.group(1), match.group(2)
        chunk_start = normalized.rfind("search-result-item", 0, match.start())
        if chunk_start == -1:
            chunk_start = max(0, match.start() - 1500)
        else:
            chunk_start = max(0, chunk_start - 300)
        next_match_start = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        chunk_end = min(len(normalized), max(next_match_start, match.end() + 2200))
        chunk = normalized[chunk_start:chunk_end]
        chunk_text = strip_ndlsearch_html(chunk)
        if keyword and not _query_in_text(keyword, chunk_text):
            continue

        title = ""
        title_match = re.search(r"<span[^>]*>(.*?)</span>", normalized[match.end() : match.end() + 1200], re.DOTALL)
        if title_match:
            title = strip_ndlsearch_html(title_match.group(1))
        if not title:
            aria_match = re.search(r"aria-label=[\"']([^\"']+)[\"']", normalized[match.start() : match.end() + 500])
            if aria_match:
                title = strip_ndlsearch_html(aria_match.group(1))

        url = urljoin(base_url, href)
        ndl_ids = extract_digital_pids_from_ndlsearch_html(chunk)
        snippet = _snippet_around_query(keyword, chunk_text)
        hint = {
            "query": keyword,
            "snippet": snippet,
            "pdf_page": extract_pdf_page_hint(chunk_text),
            "book_id": book_id,
            "url": url,
            "page_basis": "ndlsearch_pdf_page_hint",
        }
        record = hits_by_id.setdefault(
            book_id,
            {
                "title": title,
                "url": url,
                "ndl_id": ndl_ids[0] if ndl_ids else None,
                "author": None,
                "date": None,
                "publisher": None,
                "metadata": {
                    "identifier": book_id,
                    "search_route": "ndlsearch_html_fulltext",
                    "fulltext_hints": [],
                },
            },
        )
        if title and not record.get("title"):
            record["title"] = title
        if ndl_ids and not record.get("ndl_id"):
            record["ndl_id"] = ndl_ids[0]
        hints = record["metadata"].setdefault("fulltext_hints", [])
        if not any(item.get("snippet") == snippet and item.get("pdf_page") == hint["pdf_page"] for item in hints):
            hints.append(hint)
    return list(hits_by_id.values())[:max_results]


def search_ndlsearch_fulltext(
    keyword: str,
    *,
    max_results: int,
    request_get: Callable[..., Any] = requests.get,
    use_browser: bool = False,
) -> List[Dict[str, Any]]:
    if not clean_text(keyword):
        return []
    collected: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()
    param_sets = [
        {"cs": "bib", "from": "0", "size": str(max_results), "q": keyword},
        {"cs": "bib", "from": "0", "size": str(max_results), "q-anywhere": keyword},
        {"cs": "all", "from": "0", "size": str(max_results), "q": keyword},
    ]
    for params in param_sets:
        try:
            response = request_get(
                NDLSEARCH_SEARCH_URL,
                params=params,
                headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/xhtml+xml"},
                timeout=30,
            )
        except Exception:
            continue
        if int(getattr(response, "status_code", 0) or 0) != 200:
            continue
        hits = extract_ndlsearch_fulltext_hits(
            getattr(response, "text", "") or "",
            keyword,
            base_url="https://ndlsearch.ndl.go.jp",
            max_results=max_results,
        )
        for hit in hits:
            key = str(hit.get("ndl_id") or hit.get("url") or hit.get("title") or "")
            if key and key not in seen_keys:
                seen_keys.add(key)
                collected.append(hit)
        if collected:
            break
    if not collected and use_browser:
        try:
            rendered_html = fetch_ndlsearch_rendered_search_html(keyword, max_results=max_results)
        except Exception:
            rendered_html = ""
        if rendered_html:
            collected = extract_ndlsearch_fulltext_hits(
                rendered_html,
                keyword,
                base_url="https://ndlsearch.ndl.go.jp",
                max_results=max_results,
            )
    return collected[:max_results]


def _strip_ndl_info_pid(value: str) -> str:
    token = str(value or "")
    prefix = "info:ndljp/pid/"
    return token.replace(prefix, "") if token.startswith(prefix) else token


def _first_meta_value(meta: Dict[str, Any], key: str) -> str:
    value = meta.get(key)
    if isinstance(value, list):
        return str(value[0] or "") if value else ""
    return str(value or "")


def _build_fulltext_targets_and_page_maps(
    search_hits: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], Dict[str, Dict[str, int]]]:
    targets: List[Dict[str, Any]] = []
    page_maps: Dict[str, Dict[str, int]] = {}
    for hit in search_hits:
        content = hit.get("content") or {}
        pid = _strip_ndl_info_pid(content.get("pid") or content.get("itemId") or "")
        bundles = content.get("contentsBundles") or []
        if not pid or content.get("type") != "leaf" or not (content.get("rules") or {}).get("snippet"):
            continue
        bundle_ids: List[str] = []
        for bundle in bundles:
            bundle_id = str(bundle.get("id") or "")
            if not bundle_id:
                continue
            bundle_ids.append(bundle_id)
            content_page_map = page_maps.setdefault(pid, {})
            for index, page_content in enumerate(bundle.get("contents") or [], start=1):
                content_id = page_content.get("id")
                if content_id:
                    content_page_map[str(content_id)] = index
        if bundle_ids:
            targets.append({"pid": pid, "bids": bundle_ids})
    return targets, page_maps


def _records_from_ndl_digital_item_search(
    payload: Dict[str, Any],
    *,
    keyword: str,
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for rank, hit in enumerate(payload.get("searchHits") or [], start=1):
        content = hit.get("content") or {}
        meta = content.get("meta") or {}
        pid = _strip_ndl_info_pid(content.get("pid") or content.get("itemId") or "")
        title = _first_meta_value(meta, "0001Dtct") or _first_meta_value(meta, "title")
        author = _first_meta_value(meta, "0020Dtct")
        date = _first_meta_value(meta, "0059Dk") or _first_meta_value(meta, "0058Dod")
        publisher = _first_meta_value(meta, "0021Dtct") or _first_meta_value(meta, "0274Dt")
        if not title and not pid:
            continue
        records.append(
            {
                "title": title,
                "url": f"https://dl.ndl.go.jp/pid/{pid}" if pid else "",
                "ndl_id": pid or None,
                "author": author or None,
                "date": date or None,
                "publisher": publisher or None,
                "metadata": {
                    "identifier": pid or content.get("itemId"),
                    "search_route": "ndl_digital_fulltext_api",
                    "source_rank": rank,
                    "ndl_digital_score": hit.get("score"),
                    "fulltext_query": keyword,
                    "fulltext_hints": [],
                },
            }
        )
    return records


def _merge_ndl_digital_snippets(
    records: List[Dict[str, Any]],
    snippet_payload: Dict[str, Any],
    *,
    keyword: str,
    page_maps: Dict[str, Dict[str, int]],
) -> None:
    records_by_pid = {str(record.get("ndl_id") or ""): record for record in records}
    for pid, item in (snippet_payload or {}).items():
        record = records_by_pid.get(str(pid))
        if not record:
            continue
        hints = record.setdefault("metadata", {}).setdefault("fulltext_hints", [])
        for content in (item or {}).get("contents") or []:
            cid = str(content.get("cid") or "")
            pdf_page = page_maps.get(str(pid), {}).get(cid)
            if pdf_page is None and content.get("index") is not None:
                try:
                    pdf_page = int(content.get("index")) + 1
                except (TypeError, ValueError):
                    pdf_page = None
            for match in content.get("matches") or []:
                snippet = clean_text(
                    "".join(str(match.get(part) or "") for part in ("head", "word", "tail"))
                )
                if not snippet:
                    continue
                hint = {
                    "query": keyword,
                    "snippet": snippet,
                    "pdf_page": pdf_page,
                    "pid": str(pid),
                    "cid": cid,
                    "page_basis": "dl_ndl_fulltext_content_index",
                }
                if not any(
                    existing.get("snippet") == hint["snippet"]
                    and existing.get("pdf_page") == hint["pdf_page"]
                    for existing in hints
                    if isinstance(existing, dict)
                ):
                    hints.append(hint)


def search_ndl_digital_fulltext(
    keyword: str,
    *,
    max_results: int,
    request_post: Callable[..., Any] = requests.post,
) -> List[Dict[str, Any]]:
    """Search NDL Digital Collection full text and return standard records.

    This mirrors the public frontend calls used by dl.ndl.go.jp. It is more
    useful than the NDL Search HTML page for "contained work" cases because the
    snippet endpoint returns the actual host PID and page-like content index.
    """

    cleaned_keyword = clean_text(keyword)
    if not cleaned_keyword:
        return []
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://dl.ndl.go.jp",
        "Referer": "https://dl.ndl.go.jp/fulltext-search",
    }
    search_payload = {
        "keyword": cleaned_keyword,
        "pageNum": "0",
        "pageSize": str(max(1, min(int(max_results), 20))),
        "sortKey": "SCORE",
        "order": "DESC",
        "fullText": True,
        "excludeVolumeNum": False,
        "fullTextInterval": False,
        "ftInterval": 400,
    }
    try:
        response = request_post(
            f"{NDL_DIGITAL_API_URL}/item/search",
            json=search_payload,
            headers=headers,
            timeout=30,
        )
    except Exception:
        return []
    if int(getattr(response, "status_code", 0) or 0) != 200:
        return []
    try:
        item_payload = response.json()
    except Exception:
        return []
    records = _records_from_ndl_digital_item_search(item_payload, keyword=cleaned_keyword)
    targets, page_maps = _build_fulltext_targets_and_page_maps(item_payload.get("searchHits") or [])
    if targets:
        snippet_payload = {
            "keyword": cleaned_keyword,
            "keywords": cleaned_keyword.replace("\u3000", " ").split(" "),
            "targets": targets[: max(1, min(int(max_results), 20))],
            "mode": "SNIPPET",
            "sort": "SCORE",
            "size": 10,
            "fullTextInterval": False,
            "ftInterval": 400,
        }
        try:
            snippet_response = request_post(
                f"{NDL_DIGITAL_API_URL}/fulltext/search",
                json=snippet_payload,
                headers=headers,
                timeout=30,
            )
            if int(getattr(snippet_response, "status_code", 0) or 0) == 200:
                _merge_ndl_digital_snippets(
                    records,
                    snippet_response.json(),
                    keyword=cleaned_keyword,
                    page_maps=page_maps,
                )
        except Exception:
            pass
    return records[:max_results]


def fetch_ndlsearch_rendered_search_html(
    keyword: str,
    *,
    max_results: int = 5,
    timeout_ms: int = 30000,
) -> str:
    """Fetch NDL Search after browser rendering.

    This is intentionally opt-in. NDL's public HTML sometimes includes enough
    SSR data for snippets, but the browser path is useful when snippet cards are
    only visible after the frontend has hydrated.
    """

    from playwright.sync_api import sync_playwright

    query = urlencode({"cs": "bib", "from": "0", "size": str(max_results), "q": keyword})
    url = f"{NDLSEARCH_SEARCH_URL}?{query}"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            try:
                page.wait_for_selector(".search-result-item, a[href*='/books/']", timeout=timeout_ms // 2)
            except Exception:
                pass
            return page.content()
        finally:
            browser.close()


def extract_ndlsearch_book_id(url: str) -> Optional[str]:
    match = NDLSEARCH_BOOK_RE.search(url or "")
    return match.group(1) if match else None


def _normalize_embedded_url_text(text: str) -> str:
    return html.unescape(text or "").replace("\\/", "/")


def extract_digital_pids_from_ndlsearch_html(html_text: str) -> List[str]:
    normalized = _normalize_embedded_url_text(html_text)
    pids: List[str] = []
    for pid in NDL_DIGITAL_PID_RE.findall(normalized):
        if pid not in pids:
            pids.append(pid)
    return pids


def extract_related_ndlsearch_book_ids(html_text: str, *, current_book_id: Optional[str] = None) -> List[str]:
    related: List[str] = []
    for book_id in re.findall(r"R\d+-I[\w-]+", html_text or ""):
        if book_id == current_book_id or book_id in related:
            continue
        related.append(book_id)
    return related


def resolve_ndlsearch_detail_url(
    url: str,
    *,
    request_get: Callable[..., Any] = requests.get,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Resolve an NDL Search detail page to digital NDL PIDs when present.

    NDL Search can return metadata-only book pages. This resolver is deliberately
    conservative: it only returns PIDs that are explicitly embedded in the detail
    page, and it records related NDL Search IDs for diagnostics without treating
    them as downloadable replacements.
    """

    direct_pid_match = NDL_DIGITAL_PID_RE.search(_normalize_embedded_url_text(url or ""))
    if direct_pid_match:
        return {
            "status": "resolved",
            "url": url,
            "ndl_ids": [direct_pid_match.group(1)],
            "related_book_ids": [],
            "method": "direct_pid_url",
        }

    book_id = extract_ndlsearch_book_id(url)
    if not book_id:
        return {
            "status": "unsupported_url",
            "url": url,
            "ndl_ids": [],
            "related_book_ids": [],
            "method": "none",
        }

    try:
        response = request_get(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/xhtml+xml"},
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "request_failed",
            "url": url,
            "book_id": book_id,
            "ndl_ids": [],
            "related_book_ids": [],
            "error": f"{type(exc).__name__}:{exc}",
            "method": "detail_page",
        }

    status_code = int(getattr(response, "status_code", 0) or 0)
    html_text = getattr(response, "text", "") or ""
    if status_code != 200:
        return {
            "status": "http_error",
            "url": url,
            "book_id": book_id,
            "status_code": status_code,
            "ndl_ids": [],
            "related_book_ids": [],
            "method": "detail_page",
        }

    ndl_ids = extract_digital_pids_from_ndlsearch_html(html_text)
    related_book_ids = extract_related_ndlsearch_book_ids(html_text, current_book_id=book_id)
    return {
        "status": "resolved" if ndl_ids else "no_digital_pid",
        "url": url,
        "book_id": book_id,
        "ndl_ids": ndl_ids,
        "related_book_ids": related_book_ids[:20],
        "method": "detail_page",
    }


def build_ndl_sru_queries(footnote: ParsedFootnote) -> List[str]:
    title_terms = title_query_terms(footnote.title)
    author_terms = author_query_terms(footnote.author)
    queries: List[str] = []
    host_title = getattr(footnote, "host_title", "") or ""
    contained_title = getattr(footnote, "contained_title", "") or footnote.title

    primary = title_terms[0] if title_terms else ""
    secondary = title_terms[-1] if len(title_terms) >= 2 else ""
    tertiary = title_terms[1] if len(title_terms) >= 3 else ""

    if host_title:
        queries.append(f'title any "{host_title}"')
        if contained_title and contained_title != host_title:
            queries.append(f'title any "{host_title}" AND anywhere any "{contained_title}"')
            queries.append(f'anywhere any "{contained_title}"')
    if primary and author_terms:
        queries.append(f'title any "{primary}" AND creator any "{author_terms[0]}"')
    if primary and secondary and primary != secondary and author_terms:
        queries.append(f'title any "{primary} {secondary}" AND creator any "{author_terms[0]}"')
    if primary and secondary and primary != secondary:
        queries.append(f'title any "{primary} {secondary}"')
    if primary and tertiary and tertiary not in {primary, secondary}:
        queries.append(f'title any "{primary} {tertiary}"')
    if primary:
        queries.append(f'title any "{primary}"')
    if footnote.title:
        compact = re.sub(r"[：:「」『』《》]", " ", footnote.title)
        compact = clean_text(compact)
        if compact:
            queries.append(f'title any "{compact}"')
            queries.append(f'anywhere any "{compact}"')
    for keyword in iter_ndl_search_keywords(footnote):
        queries.append(f'anywhere any "{keyword}"')

    deduped: List[str] = []
    for item in queries:
        if item not in deduped:
            deduped.append(item)
    return deduped


def parse_ndl_sru_records(xml_text: str) -> List[Dict[str, Any]]:
    root = ET.fromstring(xml_text)
    namespaces = {
        "srw": "http://www.loc.gov/zing/srw/",
        "dc": "http://purl.org/dc/elements/1.1/",
        "dcndl": "http://ndl.go.jp/dcndl/terms/",
        "dcterms": "http://purl.org/dc/terms/",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "foaf": "http://xmlns.com/foaf/0.1/",
    }
    records: List[Dict[str, Any]] = []
    for rank, record in enumerate(root.findall(".//srw:recordData", namespaces), start=1):
        inner_xml = html.unescape("".join(record.itertext())).strip()
        if not inner_xml:
            continue
        try:
            rdf_root = ET.fromstring(inner_xml)
        except ET.ParseError:
            continue
        title = (
            rdf_root.findtext(".//dcterms:title", default="", namespaces=namespaces)
            or rdf_root.findtext(".//dc:title//rdf:value", default="", namespaces=namespaces)
            or rdf_root.findtext(".//dc:title", default="", namespaces=namespaces)
        )
        identifier = (
            rdf_root.findtext(".//dcterms:identifier", default="", namespaces=namespaces)
            or rdf_root.findtext(".//dc:identifier", default="", namespaces=namespaces)
        )
        author = rdf_root.findtext(".//dc:creator", default="", namespaces=namespaces)
        date = rdf_root.findtext(".//dcterms:issued", default="", namespaces=namespaces) or rdf_root.findtext(".//dc:date", default="", namespaces=namespaces)
        publisher = (
            rdf_root.findtext(".//dcterms:publisher//foaf:name", default="", namespaces=namespaces)
            or rdf_root.findtext(".//dc:publisher", default="", namespaces=namespaces)
        )
        pid_match = re.search(r"dl\.ndl\.go\.jp/(?:pid|info:ndljp/pid)/(\d{6,})", inner_xml)
        identifier_pid_match = re.search(
            r"(?:dl\.ndl\.go\.jp/(?:pid|info:ndljp/pid)/|info:ndljp/pid/)(\d{6,})",
            identifier or "",
        )
        ndl_id_match = pid_match or identifier_pid_match
        ndl_id = ndl_id_match.group(1) if ndl_id_match else ""
        resource_url = ""
        if ndl_id:
            resource_url = f"https://dl.ndl.go.jp/pid/{ndl_id}"
        else:
            bib_resource = rdf_root.find(".//dcndl:BibAdminResource", namespaces)
            if bib_resource is not None:
                resource_url = bib_resource.attrib.get(f"{{{namespaces['rdf']}}}about", "")
            if not resource_url:
                description = rdf_root.find(".//rdf:Description", namespaces)
                if description is not None:
                    resource_url = description.attrib.get(f"{{{namespaces['rdf']}}}about", "")
        records.append(
            {
                "title": title,
                "url": resource_url,
                "ndl_id": ndl_id or None,
                "author": author or None,
                "date": date or None,
                "publisher": publisher or None,
                "metadata": {
                    "identifier": identifier,
                    "search_route": "ndl_sru",
                    "source_rank": rank,
                },
            }
        )
    return records


def search_ndl_public_api(
    footnote: ParsedFootnote,
    *,
    max_results: int,
    request_get: Callable[..., Any] = requests.get,
    sleep: Callable[[float], None] = time.sleep,
) -> List[Dict[str, Any]]:
    last_error: Optional[Exception] = None
    collected: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()
    for query in build_ndl_sru_queries(footnote):
        for attempt in range(1, 4):
            try:
                response = request_get(
                    NDL_SRU_URL,
                    params={
                        "operation": "searchRetrieve",
                        "version": "1.2",
                        "query": query,
                        "startRecord": 1,
                        "maximumRecords": max_results,
                        "recordSchema": "dcndl",
                    },
                    timeout=30,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                if response.status_code >= 500:
                    sleep(1.0 * attempt)
                    continue
                records = parse_ndl_sru_records(response.text)
                if records:
                    for record in records:
                        key = record.get("ndl_id") or record.get("url") or record.get("title")
                        if key and key not in seen_keys:
                            seen_keys.add(key)
                            collected.append(record)
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                sleep(1.0 * attempt)
                continue
    if collected:
        return collected
    if last_error is not None:
        raise last_error
    return []
