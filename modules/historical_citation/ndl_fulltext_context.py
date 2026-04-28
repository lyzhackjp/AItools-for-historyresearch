from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional

import requests

from .docx_parser import clean_text
from .ndl_search import NDL_DIGITAL_API_URL, search_ndl_digital_fulltext


def ndl_digital_json_headers(*, referer: str = "https://dl.ndl.go.jp/") -> Dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://dl.ndl.go.jp",
        "Referer": referer,
    }


def strip_info_pid(value: Any) -> str:
    token = str(value or "").strip()
    prefix = "info:ndljp/pid/"
    return token.replace(prefix, "") if token.startswith(prefix) else token


@dataclass
class NDLFulltextHit:
    pid: str
    query: str
    snippet: str
    pdf_page: Optional[int] = None
    cid: str = ""
    content_index: Optional[int] = None
    mode: str = "SNIPPET"
    page_basis: str = "dl_ndl_fulltext_content_index"
    head: str = ""
    word: str = ""
    tail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NDLFulltextProbe:
    pid: str
    title: str
    status: str
    queries_tried: List[str] = field(default_factory=list)
    hits: List[NDLFulltextHit] = field(default_factory=list)
    note: str = ""
    global_candidates: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["hits"] = [hit.to_dict() for hit in self.hits]
        return payload


@dataclass
class NDLExpandedSnippetContext:
    pid: str
    pdf_page: Optional[int]
    cid: str
    seed_query: str
    context_text: str
    status: str = "snippet_expanded"
    note: str = "NDL SNIPPET 接龙生成的上下文窗口，不等同于完整 OCR 段落。"
    evidence_hits: List[NDLFulltextHit] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["evidence_hits"] = [hit.to_dict() for hit in self.evidence_hits]
        return payload


def fetch_ndl_digital_item(
    pid: str,
    *,
    request_get: Callable[..., Any] = requests.get,
) -> Dict[str, Any]:
    cleaned_pid = strip_info_pid(pid)
    if not cleaned_pid:
        return {}
    try:
        response = request_get(
            f"{NDL_DIGITAL_API_URL}/item/search/info:ndljp/pid/{cleaned_pid}",
            headers=ndl_digital_json_headers(referer=f"https://dl.ndl.go.jp/pid/{cleaned_pid}"),
            timeout=30,
        )
    except Exception:
        return {}
    if int(getattr(response, "status_code", 0) or 0) != 200:
        return {}
    try:
        payload = response.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _first_meta_value(meta: Dict[str, Any], key: str) -> str:
    value = meta.get(key)
    if isinstance(value, list):
        return str(value[0] or "") if value else ""
    return str(value or "")


def _item_content(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    item = payload.get("item")
    if isinstance(item, dict):
        return item
    content = payload.get("content")
    if isinstance(content, dict):
        return content
    if payload.get("contentsBundles") or payload.get("pid") or payload.get("itemId"):
        return payload
    hits = payload.get("searchHits")
    if isinstance(hits, list) and hits:
        first_content = (hits[0] or {}).get("content")
        if isinstance(first_content, dict):
            return first_content
    return {}


def _item_title(content: Dict[str, Any]) -> str:
    meta = content.get("meta") if isinstance(content.get("meta"), dict) else {}
    return _first_meta_value(meta, "0001Dtct") or _first_meta_value(meta, "title")


def build_item_fulltext_target_and_page_map(
    item_payload: Dict[str, Any],
    *,
    fallback_pid: str = "",
) -> tuple[str, str, List[Dict[str, Any]], Dict[str, int]]:
    """Build NDL fulltext target payloads and cid->PDF-page maps for one item."""

    content = _item_content(item_payload)
    pid = strip_info_pid(content.get("pid") or content.get("itemId") or fallback_pid)
    title = _item_title(content)
    page_map: Dict[str, int] = {}
    bundle_ids: List[str] = []
    for bundle in content.get("contentsBundles") or []:
        bundle_id = str(bundle.get("id") or "")
        if bundle_id:
            bundle_ids.append(bundle_id)
        for index, page_content in enumerate(bundle.get("contents") or [], start=1):
            content_id = str(page_content.get("id") or "")
            if content_id:
                page_map[content_id] = index
    targets = [{"pid": pid, "bids": bundle_ids}] if pid and bundle_ids else []
    return pid, title, targets, page_map


def _keyword_list(query: str) -> List[str]:
    return [part for part in clean_text(query).replace("\u3000", " ").split(" ") if part]


def search_ndl_fulltext_in_item(
    pid: str,
    query: str,
    *,
    mode: str = "SNIPPET",
    size: int = 100,
    item_payload: Optional[Dict[str, Any]] = None,
    request_get: Callable[..., Any] = requests.get,
    request_post: Callable[..., Any] = requests.post,
) -> tuple[str, List[NDLFulltextHit]]:
    """Search a keyword inside one NDL Digital Collection PID.

    `SNIPPET` works for many restricted items and is the safest evidence layer.
    `CONTENT` can return fuller content for some open items, but many restricted
    PIDs simply return no results even when snippet search works.
    """

    cleaned_pid = strip_info_pid(pid)
    cleaned_query = clean_text(query)
    if not cleaned_pid or not cleaned_query:
        return "", []
    payload = item_payload or fetch_ndl_digital_item(cleaned_pid, request_get=request_get)
    resolved_pid, title, targets, page_map = build_item_fulltext_target_and_page_map(
        payload,
        fallback_pid=cleaned_pid,
    )
    if not targets:
        return title, []
    search_payload = {
        "keyword": cleaned_query,
        "keywords": _keyword_list(cleaned_query),
        "targets": targets,
        "mode": mode,
        "sort": "CONTENT" if mode == "CONTENT" else "SCORE",
        "size": max(1, min(int(size), 10000)),
        "fullTextInterval": False,
        "ftInterval": 400,
    }
    try:
        response = request_post(
            f"{NDL_DIGITAL_API_URL}/fulltext/search",
            json=search_payload,
            headers=ndl_digital_json_headers(referer=f"https://dl.ndl.go.jp/pid/{cleaned_pid}"),
            timeout=30,
        )
    except Exception:
        return title, []
    if int(getattr(response, "status_code", 0) or 0) != 200:
        return title, []
    try:
        result = response.json()
    except Exception:
        return title, []
    hits: List[NDLFulltextHit] = []
    item_result = (result or {}).get(str(resolved_pid or cleaned_pid)) or {}
    for content in item_result.get("contents") or []:
        cid = str(content.get("cid") or "")
        pdf_page: Optional[int] = page_map.get(cid)
        content_index: Optional[int] = None
        if content.get("index") is not None:
            try:
                content_index = int(content.get("index"))
            except (TypeError, ValueError):
                content_index = None
        if pdf_page is None and content_index is not None:
            pdf_page = content_index + 1
        for match in content.get("matches") or []:
            head = clean_text(str(match.get("head") or ""))
            word = clean_text(str(match.get("word") or ""))
            tail = clean_text(str(match.get("tail") or ""))
            snippet = clean_text("".join([head, word, tail]))
            if not snippet:
                continue
            hits.append(
                NDLFulltextHit(
                    pid=str(resolved_pid or cleaned_pid),
                    query=cleaned_query,
                    snippet=snippet,
                    pdf_page=pdf_page,
                    cid=cid,
                    content_index=content_index,
                    mode=mode,
                    head=head,
                    word=word,
                    tail=tail,
                )
            )
    return title, hits


def dedupe_fulltext_hits(hits: Iterable[NDLFulltextHit]) -> List[NDLFulltextHit]:
    seen: set[tuple[str, Optional[int], str]] = set()
    deduped: List[NDLFulltextHit] = []
    for hit in hits:
        key = (hit.pid, hit.pdf_page, hit.snippet)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hit)
    return deduped


def _merge_overlapping_text(base: str, addition: str, *, min_overlap: int = 8) -> str:
    left = clean_text(base)
    right = clean_text(addition)
    if not left:
        return right
    if not right:
        return left
    if right in left:
        return left
    if left in right:
        return right
    max_overlap = min(len(left), len(right))
    for size in range(max_overlap, min_overlap - 1, -1):
        if left.endswith(right[:size]):
            return clean_text(left + right[size:])
        if right.endswith(left[:size]):
            return clean_text(right + left[size:])
    return left


def _edge_query(text: str, *, side: str, chars: int) -> str:
    compact = clean_text(text)
    if len(compact) <= chars:
        return compact
    return compact[:chars] if side == "left" else compact[-chars:]


def _same_location_hits(
    hits: Iterable[NDLFulltextHit],
    *,
    cid: str,
    pdf_page: Optional[int],
) -> List[NDLFulltextHit]:
    matched: List[NDLFulltextHit] = []
    for hit in hits:
        if cid and hit.cid and hit.cid != cid:
            continue
        if pdf_page is not None and hit.pdf_page is not None and hit.pdf_page != pdf_page:
            continue
        matched.append(hit)
    return matched


def expand_ndl_snippet_context(
    pid: str,
    seed_hit: NDLFulltextHit,
    *,
    item_payload: Optional[Dict[str, Any]] = None,
    max_rounds: int = 6,
    edge_chars: int = 18,
    request_get: Callable[..., Any] = requests.get,
    request_post: Callable[..., Any] = requests.post,
) -> NDLExpandedSnippetContext:
    """Expand a snippet by repeatedly querying its left/right edges.

    This is intentionally conservative: it only accepts snippets from the same
    cid/PDF page as the seed hit, so global loose matches cannot drift into a
    different source or page.
    """

    context = clean_text(seed_hit.snippet)
    evidence: List[NDLFulltextHit] = [seed_hit]
    payload = item_payload or fetch_ndl_digital_item(pid, request_get=request_get)
    for _round in range(max(0, int(max_rounds))):
        grew = False
        for side in ("left", "right"):
            query = _edge_query(context, side=side, chars=max(4, int(edge_chars)))
            if not query:
                continue
            _title, hits = search_ndl_fulltext_in_item(
                pid,
                query,
                mode="SNIPPET",
                size=20,
                item_payload=payload,
                request_get=request_get,
                request_post=request_post,
            )
            candidates = _same_location_hits(hits, cid=seed_hit.cid, pdf_page=seed_hit.pdf_page)
            best_text = context
            best_hit: Optional[NDLFulltextHit] = None
            for hit in candidates:
                merged = _merge_overlapping_text(context, hit.snippet)
                if len(merged) > len(best_text):
                    best_text = merged
                    best_hit = hit
            if best_hit is not None:
                context = best_text
                evidence.append(best_hit)
                grew = True
        if not grew:
            break
    return NDLExpandedSnippetContext(
        pid=seed_hit.pid,
        pdf_page=seed_hit.pdf_page,
        cid=seed_hit.cid,
        seed_query=seed_hit.query,
        context_text=context,
        evidence_hits=dedupe_fulltext_hits(evidence),
    )


def probe_ndl_fulltext_context(
    pid: str,
    keyword_variants: Iterable[str],
    *,
    global_queries: Optional[Iterable[str]] = None,
    max_global_results: int = 8,
    request_get: Callable[..., Any] = requests.get,
    request_post: Callable[..., Any] = requests.post,
) -> NDLFulltextProbe:
    """Probe direct item snippets first, then keep global hits as weak leads."""

    item_payload = fetch_ndl_digital_item(pid, request_get=request_get)
    resolved_pid, title, _targets, _page_map = build_item_fulltext_target_and_page_map(
        item_payload,
        fallback_pid=pid,
    )
    direct_hits: List[NDLFulltextHit] = []
    queries_tried: List[str] = []
    for query in keyword_variants:
        cleaned_query = clean_text(query)
        if not cleaned_query or cleaned_query in queries_tried:
            continue
        queries_tried.append(cleaned_query)
        _title, hits = search_ndl_fulltext_in_item(
            resolved_pid or pid,
            cleaned_query,
            mode="SNIPPET",
            item_payload=item_payload,
            request_get=request_get,
            request_post=request_post,
        )
        if hits:
            direct_hits.extend(hits)
    direct_hits = dedupe_fulltext_hits(direct_hits)
    global_candidates: List[Dict[str, Any]] = []
    if not direct_hits and global_queries:
        for global_query in global_queries:
            cleaned_query = clean_text(global_query)
            if not cleaned_query:
                continue
            records = search_ndl_digital_fulltext(
                cleaned_query,
                max_results=max_global_results,
                request_post=request_post,
            )
            for record in records:
                candidate_pid = str(record.get("ndl_id") or "")
                metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
                global_candidates.append(
                    {
                        "query": cleaned_query,
                        "title": record.get("title") or "",
                        "pid": candidate_pid,
                        "url": record.get("url") or "",
                        "relation_to_target_pid": "same_pid"
                        if candidate_pid == str(resolved_pid or pid)
                        else "different_pid",
                        "fulltext_hints": metadata.get("fulltext_hints") or [],
                        "search_route": metadata.get("search_route") or "",
                    }
                )
    status = "direct_hit" if direct_hits else "no_direct_hit"
    note = (
        "目标 PID 内有 NDL SNIPPET 命中，可作为弱上下文证据。"
        if direct_hits
        else "目标 PID 内未发现这些关键词的 NDL SNIPPET 命中；全站命中只能作为线索，不能替代目标书内证据。"
    )
    return NDLFulltextProbe(
        pid=str(resolved_pid or strip_info_pid(pid)),
        title=title,
        status=status,
        queries_tried=queries_tried,
        hits=direct_hits,
        note=note,
        global_candidates=global_candidates,
    )
