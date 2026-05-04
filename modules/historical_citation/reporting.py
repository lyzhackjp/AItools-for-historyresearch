from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from .download_index import refresh_download_range_index
from .models import CitationCandidate
from .models import ParsedFootnote
from .source_graph import build_manual_search_recipe, build_source_graph_node
from .source_trials import source_trials_from_legacy
from .status import (
    classify_candidate_status,
    classify_result_status,
    count_refined_candidate_statuses,
    count_refined_result_statuses,
    count_support_candidate_statuses,
    count_support_result_statuses,
    refined_status_label,
    support_status_label,
)


def truncate_text(value: Any, limit: int = 1600) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n……"


def format_page_list(pages: Any) -> str:
    if not pages:
        return "未标页"
    normalized = [str(page) for page in pages if page is not None]
    if not normalized:
        return "未标页"
    return ", ".join(normalized)


def _source_identity(source_match: Any) -> str:
    if not isinstance(source_match, dict):
        return "unknown"
    return str(
        source_match.get("ndl_id")
        or source_match.get("platform_item_id")
        or source_match.get("url")
        or "unknown"
    )


def _format_page_range(page_range: Any) -> str:
    if isinstance(page_range, (list, tuple)) and len(page_range) == 2:
        return f"{page_range[0]}-{page_range[1]}"
    return "n/a"


def _source_attempt_lines(artifacts: Dict[str, Any], *, current: Optional[Dict[str, Any]] = None) -> list[str]:
    lines: list[str] = []
    trials = source_trials_from_legacy(artifacts, current=current)
    if trials:
        for index, trial in enumerate(trials, start=1):
            if not isinstance(trial, dict):
                continue
            source_id = trial.get("source_id") or trial.get("ndl_id") or "unknown"
            title = trial.get("title") or ""
            status = trial.get("support_status") or trial.get("verification_status") or "unknown"
            confidence = trial.get("confidence", "N/A")
            page_range = _format_page_range(trial.get("page_range"))
            role = trial.get("role") or "unknown"
            failure = trial.get("failure_reason") or ""
            lines.append(
                f"- #{index} `{source_id}` {title} | platform={trial.get('platform') or 'unknown'} "
                f"| pages={page_range} | confidence={confidence} | status={status} | "
                f"role={role}{(' | reason=' + str(failure)) if failure else ''}"
            )
        return lines

    attempts = list(artifacts.get("source_attempts") or [])
    for index, attempt in enumerate(attempts, start=1):
        if not isinstance(attempt, dict):
            continue
        source = attempt.get("selected_source_match") or {}
        source_id = _source_identity(source)
        title = source.get("title") if isinstance(source, dict) else ""
        status = attempt.get("support_status") or attempt.get("verification_status") or "unknown"
        confidence = attempt.get("confidence", "N/A")
        page_range = _format_page_range(attempt.get("downloaded_page_range"))
        replacement = "replaced"
        lines.append(
            f"- #{index} `{source_id}` {title or ''} | pages={page_range} | "
            f"confidence={confidence} | status={status} | {replacement}"
        )
    unavailable_attempts = list(artifacts.get("source_unavailable_attempts") or [])
    for attempt in unavailable_attempts:
        if not isinstance(attempt, dict):
            continue
        source_id = attempt.get("source_id") or attempt.get("ndl_id") or "unknown"
        reason = attempt.get("reason") or "unknown"
        detail = attempt.get("detail") or ""
        lines.append(
            f"- #{len(lines) + 1} `{source_id}` | pages=n/a | confidence=N/A | "
            f"status=source_unavailable | reason={reason}{(' | ' + str(detail)) if detail else ''}"
        )
    if current:
        source = current.get("selected_source_match") or {}
        if source:
            source_id = _source_identity(source)
            title = source.get("title") if isinstance(source, dict) else ""
            status = current.get("support_status") or current.get("verification_status") or "unknown"
            confidence = current.get("confidence", "N/A")
            page_range = _format_page_range(current.get("downloaded_page_range"))
            lines.append(
                f"- #{len(lines) + 1} `{source_id}` {title or ''} | pages={page_range} | "
                f"confidence={confidence} | status={status} | current"
            )
    return lines


def _match_dict_value(match: Any, key: str, default: Any = None) -> Any:
    if isinstance(match, dict):
        return match.get(key, default)
    return getattr(match, key, default)


def _format_adapter_candidate_order(result: Dict[str, Any], *, limit: int = 6) -> Optional[str]:
    artifacts = result.get("artifacts") or {}
    matches = result.get("ndl_matches") or []
    by_id: Dict[str, Dict[str, Any]] = {}
    derived_order: list[str] = []
    for match in matches:
        source_id = str(
            _match_dict_value(match, "ndl_id")
            or _match_dict_value(match, "platform_item_id")
            or _match_dict_value(match, "url")
            or ""
        )
        if not source_id:
            continue
        metadata = _match_dict_value(match, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            metadata = {}
        by_id[source_id] = {
            "route": metadata.get("search_route") or metadata.get("source_route") or "",
            "known": bool(metadata.get("known_pid_candidate")),
        }
        if source_id not in derived_order:
            derived_order.append(source_id)

    raw_order = artifacts.get("source_match_order") or artifacts.get("adapter_candidate_order") or []
    order: list[str] = []
    for item in raw_order if isinstance(raw_order, list) else []:
        if isinstance(item, dict):
            source_id = str(item.get("ndl_id") or item.get("source_id") or item.get("pid") or "")
            if source_id:
                by_id.setdefault(
                    source_id,
                    {
                        "route": item.get("search_route") or item.get("route") or "",
                        "known": bool(item.get("known_pid_candidate")),
                    },
                )
        else:
            source_id = str(item or "")
        if source_id and source_id not in order:
            order.append(source_id)
    if not order:
        order = derived_order
    if not order:
        return None

    labels: list[str] = []
    for source_id in order[:limit]:
        meta = by_id.get(source_id, {})
        route = str(meta.get("route") or "")
        known = "known" if meta.get("known") else "candidate"
        suffix = f"{known}/{route}" if route else known
        labels.append(f"{source_id} ({suffix})")
    if len(order) > limit:
        labels.append(f"+{len(order) - limit} more")
    return f"- Adapter Candidate Order: {' -> '.join(labels)}"


def _format_ndl_fulltext_probe(artifacts: Dict[str, Any]) -> Optional[str]:
    probe = artifacts.get("ndl_fulltext_probe") or {}
    if not isinstance(probe, dict) or not probe:
        return None
    queries = probe.get("queries_tried") or []
    if isinstance(queries, list):
        query_label = "; ".join(str(query) for query in queries[:3] if str(query).strip())
    else:
        query_label = str(queries)
    first_pages = probe.get("first_pdf_pages") or []
    if isinstance(first_pages, list) and first_pages:
        page_label = ",".join(str(page) for page in first_pages[:5])
    else:
        page_label = "n/a"
    return (
        f"- Target PID snippet probe: pid={probe.get('pid') or 'n/a'} "
        f"| status={probe.get('status') or 'unknown'} "
        f"| hits={probe.get('hit_count', 0)} "
        f"| specific_hits={probe.get('specific_hit_count', 0)} "
        f"| pdf_page_hits={probe.get('pdf_page_hit_count', 0)} "
        f"| pdf_pages={page_label}"
        f"{(' | queries=' + query_label) if query_label else ''}"
    )


def _format_fulltext_context_candidates(artifacts: Dict[str, Any], *, limit: int = 5) -> List[str]:
    candidates = artifacts.get("fulltext_context_candidates") or []
    if not isinstance(candidates, list) or not candidates:
        return []
    selected_context_id = str(artifacts.get("fulltext_selected_context_id") or "")
    lines = ["- 全文上下文候选 Top N:"]
    for item in candidates[:limit]:
        if not isinstance(item, dict):
            continue
        context_id = str(item.get("context_id") or "ctx")
        selected = " | selected" if selected_context_id and context_id == selected_context_id else ""
        page = item.get("pdf_page") or "n/a"
        category = item.get("lead_category") or "unknown"
        score = item.get("score", "n/a")
        query = truncate_text(str(item.get("query") or ""), limit=90)
        lines.append(
            f"  - {context_id}{selected} | score={score} | {category} | pdf_page={page} | query={query}"
        )
        cleaned = item.get("cleaned_context") or item.get("expanded_context") or item.get("snippet") or ""
        if cleaned:
            lines.append(f"    - 清洗后上下文: {truncate_text(str(cleaned), limit=360)}")
        reasons = item.get("score_reasons") or []
        if isinstance(reasons, list) and reasons:
            lines.append(f"    - score reasons: {', '.join(str(reason) for reason in reasons[:5])}")
    return lines


def _format_fulltext_compound_evidence_packet(artifacts: Dict[str, Any]) -> List[str]:
    packet = artifacts.get("fulltext_compound_evidence_packet") or {}
    if not isinstance(packet, dict) or not packet:
        return []
    facets = packet.get("facets") or []
    if not isinstance(facets, list) or not facets:
        return []
    complete = bool(packet.get("complete"))
    supporting_context_ids = packet.get("supporting_context_ids") or []
    if isinstance(supporting_context_ids, list):
        supporting_label = ", ".join(str(item) for item in supporting_context_ids[:6])
    else:
        supporting_label = ""
    lines = [
        "- 复合证据包: "
        f"type={packet.get('packet_type') or 'unknown'} | "
        f"complete={complete}"
        f"{(' | contexts=' + supporting_label) if supporting_label else ''}"
    ]
    for facet in facets:
        if not isinstance(facet, dict):
            continue
        hits = facet.get("hits") or []
        hit_labels: List[str] = []
        if isinstance(hits, list):
            for hit in hits[:3]:
                if not isinstance(hit, dict):
                    continue
                terms = hit.get("matched_terms") or []
                term_label = "/".join(str(term) for term in terms[:3]) if isinstance(terms, list) else ""
                hit_labels.append(
                    f"{hit.get('context_id') or 'ctx?'}"
                    f"@p{hit.get('pdf_page') or 'n/a'}"
                    f"{(':' + term_label) if term_label else ''}"
                )
        lines.append(
            "  - "
            f"{facet.get('facet_id') or 'facet'} | "
            f"covered={bool(facet.get('covered'))} | "
            f"{'; '.join(hit_labels) if hit_labels else 'no hit'}"
        )
    gap = artifacts.get("fulltext_compound_evidence_review_gap") or {}
    if isinstance(gap, dict) and gap:
        lines.append(
            "- 复合证据复核提示: 已覆盖必要 facet，但最终精核未判 direct_support，"
            f"当前判定={gap.get('decision') or 'unknown'}"
        )
    return lines


def _format_iiif_image_ocr_availability(artifacts: Dict[str, Any]) -> Optional[str]:
    manifest = artifacts.get("iiif_image_ocr_available") or {}
    fulltext = artifacts.get("ndl_fulltext_json_available") or {}
    if not isinstance(manifest, dict):
        manifest = {}
    if not isinstance(fulltext, dict):
        fulltext = {}
    if not manifest and not fulltext:
        return None
    bits: list[str] = []
    if manifest:
        bits.append(
            f"IIIF manifest pid={manifest.get('ndl_id') or 'n/a'} canvases={manifest.get('canvas_count', 'n/a')}"
        )
    if fulltext:
        bits.append(f"fulltext-json pid={fulltext.get('ndl_id') or 'n/a'}")
    return f"- 可读图像/OCR 路径: {' | '.join(bits)}"


def _format_known_pid_page_window_fallback(artifacts: Dict[str, Any]) -> Optional[str]:
    fallback = artifacts.get("known_pid_page_window_fallback") or {}
    if not isinstance(fallback, dict) or not fallback:
        return None
    start_page = fallback.get("start_page")
    end_page = fallback.get("end_page")
    window = f"{start_page}-{end_page}" if start_page is not None and end_page is not None else "n/a"
    cited_pages = format_page_list(fallback.get("cited_book_pages") or [])
    return (
        f"- Known PID page-window fallback: PID={fallback.get('ndl_id') or 'n/a'} "
        f"| cited_pages={cited_pages} | scan_window={window} "
        f"| evidence={fallback.get('evidence_level') or 'diagnostic'}"
    )


def _format_diary_date_pdf_page_fallback(artifacts: Dict[str, Any]) -> Optional[str]:
    fallback = artifacts.get("diary_date_pdf_page_fallback") or {}
    if not isinstance(fallback, dict) or not fallback:
        return None
    start_page = fallback.get("start_page")
    end_page = fallback.get("end_page")
    window = f"{start_page}-{end_page}" if start_page is not None and end_page is not None else "n/a"
    top_candidates = fallback.get("top_candidates") or []
    top_candidate: Dict[str, Any] = {}
    if isinstance(top_candidates, list) and top_candidates and isinstance(top_candidates[0], dict):
        top_candidate = top_candidates[0]
    claim_facets = top_candidate.get("claim_facets") or []
    if isinstance(claim_facets, list) and claim_facets:
        facet_label = ",".join(str(facet) for facet in claim_facets[:6])
    else:
        facet_label = "n/a"
    return (
        f"- Diary date PDF-page route fallback: PID={fallback.get('ndl_id') or 'n/a'} "
        f"| selected_pdf_page={fallback.get('selected_pdf_page') or 'n/a'} "
        f"| scan_window={window} "
        f"| query={truncate_text(fallback.get('selected_query') or 'n/a', limit=120)} "
        f"| scope={fallback.get('selected_match_scope') or 'n/a'} "
        f"| lead={fallback.get('selected_lead_category') or 'n/a'} "
        f"| facets={facet_label} "
        f"| evidence={fallback.get('evidence_level') or 'routing_only_until_ocr_llm_review'}"
    )


def _format_diary_date_lookup_diagnostic(artifacts: Dict[str, Any]) -> Optional[str]:
    diagnostic = artifacts.get("diary_date_lookup_diagnostic") or {}
    if not isinstance(diagnostic, dict) or not diagnostic:
        return None
    window = diagnostic.get("small_page_window") or {}
    if not isinstance(window, dict):
        window = {}
    start_page = window.get("start_page")
    end_page = window.get("end_page")
    window_label = f"{start_page}-{end_page}" if start_page is not None and end_page is not None else "n/a"
    date_queries = ", ".join(str(query) for query in (diagnostic.get("date_queries") or [])[:3]) or "n/a"
    return (
        f"- Diary date lookup diagnostic: PID={diagnostic.get('ndl_id') or 'n/a'} "
        f"| date_hits={diagnostic.get('date_hit_count', 0)} "
        f"| title_hits={diagnostic.get('title_hit_count', 0)} "
        f"| date_queries={date_queries} "
        f"| next=toc/index + small page-window OCR "
        f"| cited_pages={format_page_list(window.get('cited_book_pages') or [])} "
        f"| scan_window={window_label}"
    )


def _format_contained_document_lookup_diagnostic(artifacts: Dict[str, Any]) -> Optional[str]:
    diagnostic = artifacts.get("contained_document_lookup_diagnostic") or {}
    if not isinstance(diagnostic, dict) or not diagnostic:
        return None
    known_pids = ", ".join(str(pid) for pid in (diagnostic.get("known_pid_candidates") or []) if str(pid or "")) or "n/a"
    host = diagnostic.get("host_title") or ("missing" if diagnostic.get("host_missing") else "n/a")
    contained = diagnostic.get("contained_title") or "n/a"
    return (
        f"- Contained document lookup diagnostic: PID={diagnostic.get('ndl_id') or 'n/a'} "
        f"| known_pids={known_pids} "
        f"| contained={contained} "
        f"| host={host} "
        f"| title_hits={diagnostic.get('title_hit_count', 0)} "
        f"| next=known document PID first, then host fallback"
    )


def _format_source_type_diagnostic_summary(result: Dict[str, Any]) -> Optional[str]:
    artifacts = result.get("artifacts") or {}
    if not isinstance(artifacts, dict):
        return None
    resolver_plan = artifacts.get("source_resolver_plan") or {}
    source_graph = artifacts.get("source_graph") or {}
    if not isinstance(resolver_plan, dict):
        resolver_plan = {}
    if not isinstance(source_graph, dict):
        source_graph = {}
    source_type = str(resolver_plan.get("source_type") or source_graph.get("source_type") or "")
    if not source_type:
        return None
    known_pids = [
        str(pid)
        for pid in [
            *(resolver_plan.get("known_pid_candidates") or []),
            *(source_graph.get("known_pid_candidates") or []),
        ]
        if str(pid or "")
    ]
    known_pids = list(dict.fromkeys(known_pids))
    bits = [f"source_type={source_type}"]
    if known_pids:
        bits.append(f"strict_pid={', '.join(known_pids[:3])}")

    probe = artifacts.get("ndl_fulltext_probe") or {}
    if isinstance(probe, dict) and probe:
        bits.append(
            f"target_snippet={probe.get('status') or 'unknown'}"
            f"/hits={probe.get('hit_count', 0)}"
            f"/specific={probe.get('specific_hit_count', 0)}"
        )
        first_pages = probe.get("first_pdf_pages") or []
        if isinstance(first_pages, list) and first_pages:
            bits.append(f"pdf_pages={','.join(str(page) for page in first_pages[:3])}")

    diary_diagnostic = artifacts.get("diary_date_lookup_diagnostic") or {}
    diary_pdf_route = artifacts.get("diary_date_pdf_page_fallback") or {}
    known_window = artifacts.get("known_pid_page_window_fallback") or {}
    contained_diagnostic = artifacts.get("contained_document_lookup_diagnostic") or {}
    if isinstance(diary_diagnostic, dict) and diary_diagnostic:
        bits.append(
            f"diary_date_hits={diary_diagnostic.get('date_hit_count', 0)}"
            f"/title_hits={diary_diagnostic.get('title_hit_count', 0)}"
        )
        bits.append("next=toc/index + small page-window OCR")
    if isinstance(diary_pdf_route, dict) and diary_pdf_route:
        selected_page = diary_pdf_route.get("selected_pdf_page")
        start_page = diary_pdf_route.get("start_page")
        end_page = diary_pdf_route.get("end_page")
        route_label = f"diary_pdf_route=p{selected_page or 'n/a'}"
        if start_page is not None and end_page is not None:
            route_label += f"/window={start_page}-{end_page}"
        bits.append(route_label)
        bits.append(f"route_evidence={diary_pdf_route.get('evidence_level') or 'routing_only_until_ocr_llm_review'}")
    diary_claim_scope = artifacts.get("diary_claim_facet_trigger_scope")
    if diary_claim_scope:
        bits.append(f"diary_claim_scope={diary_claim_scope}")
    if isinstance(known_window, dict) and known_window:
        start_page = known_window.get("start_page")
        end_page = known_window.get("end_page")
        if start_page is not None and end_page is not None:
            bits.append(f"page_window={start_page}-{end_page}")
        else:
            bits.append("page_window=planned")
    if isinstance(contained_diagnostic, dict) and contained_diagnostic:
        contained = contained_diagnostic.get("contained_title") or "n/a"
        host = contained_diagnostic.get("host_title") or ("missing" if contained_diagnostic.get("host_missing") else "n/a")
        bits.append(f"contained={contained}")
        bits.append(f"host={host}")
        bits.append(f"title_hits={contained_diagnostic.get('title_hit_count', 0)}")
        bits.append("next=known PID first, then host fallback")

    skipped_fulltext_leads = artifacts.get("non_equivalent_fulltext_lead_skipped_ids") or []
    if isinstance(skipped_fulltext_leads, list) and skipped_fulltext_leads:
        bits.append(f"skipped_fulltext_leads={', '.join(str(item) for item in skipped_fulltext_leads[:4])}")
    if len(bits) <= 1:
        return None
    return f"- Source-type diagnostic summary: {' | '.join(bits)}"


def _compact_source_type_diagnostic_summary(result: Dict[str, Any], *, limit: int = 220) -> str:
    summary = _format_source_type_diagnostic_summary(result) or ""
    summary = summary.replace("- Source-type diagnostic summary:", "").strip()
    return truncate_text(summary, limit=limit).replace("\n", " ")


def _format_fulltext_lead_manual_hint(artifacts: Dict[str, Any]) -> Optional[str]:
    fulltext_leads = artifacts.get("fulltext_lead_pid_group") or []
    if not isinstance(fulltext_leads, list) or not fulltext_leads:
        return None
    resolver_plan = artifacts.get("source_resolver_plan") or {}
    if not isinstance(resolver_plan, dict):
        resolver_plan = {}
    source_graph = artifacts.get("source_graph") or {}
    if not isinstance(source_graph, dict):
        source_graph = {}
    source_type = str(resolver_plan.get("source_type") or source_graph.get("source_type") or "")
    strict_pids = [str(pid) for pid in (resolver_plan.get("known_pid_candidates") or []) if str(pid or "")]
    target_queries = [str(query) for query in (resolver_plan.get("target_pid_queries") or []) if str(query or "")]
    lead_pids = [
        str(item.get("ndl_id") or item.get("source_id") or item.get("pid") or "")
        for item in fulltext_leads
        if isinstance(item, dict) and str(item.get("ndl_id") or item.get("source_id") or item.get("pid") or "")
    ]
    bits: list[str] = []
    if source_type == "volume_series":
        bits.append("volume_series: 先核对卷册/年份/文书题名，避免同题名错卷")
    elif source_type == "diary":
        bits.append("diary: 先确认日期对应卷册；若日期 snippet 为 0，改查目录/索引和小页窗 OCR")
    elif source_type in {"contained_document", "source_collection"}:
        host_title = str(source_graph.get("host_title") or resolver_plan.get("host_title") or "")
        contained_title = str(source_graph.get("contained_title") or resolver_plan.get("contained_title") or "")
        host_bit = f"host={host_title}" if host_title else "host PID"
        contained_bit = f"contained={contained_title}" if contained_title else "析出题名"
        bits.append(f"contained_document: 先确认 {host_bit} 与 {contained_bit}，只在 host/严格 PID 内搜析出文献")
    else:
        bits.append("先区分严格等价来源与全站全文线索")
    if strict_pids:
        bits.append(f"先回查严格 PID {', '.join(strict_pids[:4])}")
    if target_queries:
        bits.append(f"在目标 PID 内搜 {', '.join(target_queries[:3])}")
    if lead_pids:
        bits.append(f"全文 lead {', '.join(lead_pids[:4])} 仅用于判断是否误入其它卷册")
    return f"- 全文 lead 人工回查建议: {'；'.join(bits)}" if bits else None


def _current_evidence_status(result: Dict[str, Any]) -> str:
    artifacts = result.get("artifacts") or {}
    if result.get("matched_japanese"):
        llm_review = artifacts.get("llm_review") or {}
        provider = llm_review.get("provider") if isinstance(llm_review, dict) else None
        if provider:
            return f"ocr_aligned_with_{provider}_review"
        return "ocr_aligned"
    if artifacts.get("known_pid_page_window_fallback"):
        return "known_pid_page_window_diagnostic_ocr"
    if artifacts.get("diary_date_lookup_diagnostic"):
        return "diary_date_lookup_diagnostic"
    if artifacts.get("contained_document_lookup_diagnostic"):
        return "contained_document_lookup_diagnostic"
    if artifacts.get("fulltext_lead_only"):
        return "ndl_fulltext_lead_only"
    if artifacts.get("fulltext_only_hit") or artifacts.get("ndl_fulltext_hints"):
        return "ndl_fulltext_only_weak_evidence"
    if artifacts.get("iiif_image_ocr_available") or artifacts.get("ndl_fulltext_json_available"):
        return "iiif_image_ocr_available"
    if artifacts.get("source_pdf"):
        return "pdf_acquired_without_alignment"
    availability = artifacts.get("source_availability") if isinstance(artifacts, dict) else None
    if isinstance(availability, dict) and availability.get("status") == "unavailable":
        return f"source_unavailable:{availability.get('reason') or 'unknown'}"
    if artifacts.get("page_mapping_required_but_unavailable"):
        return "page_mapping_blocked"
    return "no_current_evidence"


def _footnote_from_result(result: Dict[str, Any]) -> ParsedFootnote:
    payload = result.get("footnote") or {}
    return ParsedFootnote(
        id=str(payload.get("id") or result.get("footnote_id") or ""),
        text=str(payload.get("text") or ""),
        title=str(payload.get("title") or ""),
        author=str(payload.get("author") or ""),
        publisher=str(payload.get("publisher") or ""),
        publication_place=str(payload.get("publication_place") or ""),
        year=str(payload.get("year") or ""),
        page_label=str(payload.get("page_label") or ""),
        page_numbers=list(payload.get("page_numbers") or []),
        page_span_type=str(payload.get("page_span_type") or ""),
        page_span_source=str(payload.get("page_span_source") or ""),
        source_type=str(payload.get("source_type") or "book"),
        ndl_keyword=str(payload.get("ndl_keyword") or ""),
        host_title=str(payload.get("host_title") or ""),
        contained_title=str(payload.get("contained_title") or ""),
        source_relation=str(payload.get("source_relation") or ""),
        notes=list(payload.get("notes") or []),
    )


def _source_graph_from_result(result: Dict[str, Any]) -> Dict[str, Any]:
    artifacts = result.get("artifacts") or {}
    source_graph = artifacts.get("source_graph")
    if isinstance(source_graph, dict) and source_graph:
        return source_graph
    footnote = _footnote_from_result(result)
    return build_source_graph_node(
        footnote,
        claim_text=str(result.get("translation_text") or result.get("paragraph_text") or ""),
    ).to_dict()


def _manual_search_recipe_from_result(result: Dict[str, Any], *, current_status: str) -> Dict[str, Any]:
    artifacts = result.get("artifacts") or {}
    recipe = artifacts.get("manual_search_recipe")
    if isinstance(recipe, dict) and recipe:
        return recipe
    footnote = _footnote_from_result(result)
    return build_manual_search_recipe(
        footnote,
        claim_text=str(result.get("translation_text") or result.get("paragraph_text") or ""),
        current_status=current_status,
    )


def _format_manual_recipe_values(values: Any, *, limit: int = 3, text_limit: int = 80) -> str:
    if not isinstance(values, list):
        values = [values]
    labels: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in labels:
            continue
        labels.append(truncate_text(text, limit=text_limit))
        if len(labels) >= limit:
            break
    return ", ".join(labels)


def _format_manual_search_recipe(manual_recipe: Dict[str, Any]) -> Optional[str]:
    if not isinstance(manual_recipe, dict) or not manual_recipe:
        return None
    reason = manual_recipe.get("reason") or "manual_review"
    recipe_bits: list[str] = []
    pid_scope = manual_recipe.get("suggested_pid_scope") or ""
    if pid_scope:
        recipe_bits.append(f"PID={pid_scope}")

    suggested_queries = manual_recipe.get("suggested_queries") or []
    suggested_label = _format_manual_recipe_values(suggested_queries, limit=2)
    if suggested_label:
        recipe_bits.append(f"query={suggested_label}")

    target_pid_queries = manual_recipe.get("target_pid_queries") or []
    target_label = _format_manual_recipe_values(target_pid_queries, limit=4)
    if target_label:
        recipe_bits.append(f"pid_query={target_label}")

    query_buckets = manual_recipe.get("query_buckets") or {}
    if isinstance(query_buckets, dict) and query_buckets:
        bucket_bits: list[str] = []
        seen: set[str] = set()
        priority = [
            "document_title",
            "document_heading",
            "anchor",
            "contained",
            "host",
            "volume",
            "date",
            "person",
            "theme",
            "action",
            "policy",
            "page_near",
            "special_term",
            "title",
            "blocked_standalone",
        ]
        for bucket_name in [*priority, *sorted(str(key) for key in query_buckets.keys())]:
            if bucket_name in seen:
                continue
            seen.add(bucket_name)
            values = query_buckets.get(bucket_name)
            value_label = _format_manual_recipe_values(values, limit=3, text_limit=48)
            if value_label:
                bucket_bits.append(f"{bucket_name}={value_label}")
            if len(bucket_bits) >= 6:
                break
        if bucket_bits:
            recipe_bits.append("buckets=" + truncate_text("; ".join(bucket_bits), limit=320))

    blocked_terms = manual_recipe.get("blocked_standalone_terms") or []
    blocked_label = _format_manual_recipe_values(blocked_terms, limit=3)
    if blocked_label and "blocked_standalone" not in str(query_buckets):
        recipe_bits.append(f"blocked={blocked_label}")
    return f"- 人工检索建议: {reason}{(' | ' + ' | '.join(recipe_bits)) if recipe_bits else ''}"


def _processing_history_lines(result: Dict[str, Any]) -> list[str]:
    artifacts = result.get("artifacts") or {}
    lines: list[str] = []
    if artifacts.get("download_timeout"):
        timeout = artifacts.get("download_timeout") or {}
        timeout_seconds = timeout.get("timeout_seconds") if isinstance(timeout, dict) else None
        lines.append(f"download_timeout: {timeout_seconds or 'unknown'}s")
    if artifacts.get("candidate_rotation_after_not_supported"):
        rotation = artifacts.get("candidate_rotation_after_not_supported") or {}
        if isinstance(rotation, dict):
            lines.append(
                "candidate_rotation_after_not_supported: "
                f"attempted={bool(rotation.get('attempted'))}, resolved={rotation.get('resolved', 'n/a')}"
            )
    if artifacts.get("source_attempts"):
        lines.append(f"source_attempts: {len(artifacts.get('source_attempts') or [])}")
    if artifacts.get("source_unavailable_attempts"):
        lines.append(f"source_unavailable_attempts: {len(artifacts.get('source_unavailable_attempts') or [])}")
    known_window = artifacts.get("known_pid_page_window_fallback") or {}
    if isinstance(known_window, dict) and known_window:
        lines.append(
            "known_pid_page_window_fallback: "
            f"pid={known_window.get('ndl_id') or 'n/a'}, "
            f"pages={format_page_list(known_window.get('cited_book_pages') or [])}, "
            f"window={known_window.get('start_page') or 'n/a'}-{known_window.get('end_page') or 'n/a'}"
        )
    diary_pdf_route = artifacts.get("diary_date_pdf_page_fallback") or {}
    if isinstance(diary_pdf_route, dict) and diary_pdf_route:
        lines.append(
            "diary_date_pdf_page_fallback: "
            f"pid={diary_pdf_route.get('ndl_id') or 'n/a'}, "
            f"selected_pdf_page={diary_pdf_route.get('selected_pdf_page') or 'n/a'}, "
            f"window={diary_pdf_route.get('start_page') or 'n/a'}-{diary_pdf_route.get('end_page') or 'n/a'}, "
            f"evidence={diary_pdf_route.get('evidence_level') or 'routing_only_until_ocr_llm_review'}"
        )
    diary_diagnostic = artifacts.get("diary_date_lookup_diagnostic") or {}
    if isinstance(diary_diagnostic, dict) and diary_diagnostic:
        lines.append(
            "diary_date_lookup_diagnostic: "
            f"pid={diary_diagnostic.get('ndl_id') or 'n/a'}, "
            f"date_hits={diary_diagnostic.get('date_hit_count', 0)}, "
            f"title_hits={diary_diagnostic.get('title_hit_count', 0)}, "
            "next=toc/index + small page-window OCR"
        )
    contained_diagnostic = artifacts.get("contained_document_lookup_diagnostic") or {}
    if isinstance(contained_diagnostic, dict) and contained_diagnostic:
        lines.append(
            "contained_document_lookup_diagnostic: "
            f"pid={contained_diagnostic.get('ndl_id') or 'n/a'}, "
            f"title_hits={contained_diagnostic.get('title_hit_count', 0)}, "
            "next=known document PID first, then host fallback"
        )
    for note in result.get("notes") or []:
        note_text = str(note)
        if any(
            marker in note_text
            for marker in (
                "timeout",
                "retry",
                "candidate_rotation",
                "page_mapping",
                "known_pid_page_window",
                "diary_date_pdf_page",
            )
        ):
            lines.append(note_text)
    return lines[:10]


def _llm_review_counters(results: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counters = Counter()
    for result in results:
        review = (result.get("artifacts") or {}).get("llm_review") or {}
        if not isinstance(review, dict):
            continue
        if review.get("eligible_for_llm_review"):
            counters["eligible_for_llm_review"] += 1
        if review.get("llm_review_success"):
            counters["llm_review_success"] += 1
        if review.get("llm_review_json_repaired"):
            counters["llm_review_json_repaired"] += 1
        if review.get("llm_review_fallback_heuristic"):
            counters["llm_review_fallback_heuristic"] += 1
        if review.get("llm_review_failed"):
            counters["llm_review_failed"] += 1
    return dict(counters)


def _source_unavailable_reason(result: Dict[str, Any]) -> Optional[str]:
    artifacts = result.get("artifacts") or {}
    if result.get("matched_japanese") or artifacts.get("source_pdf"):
        return None
    has_page_mapping_block = (
        isinstance(artifacts, dict)
        and bool(artifacts.get("page_mapping_required_but_unavailable"))
        and bool(artifacts.get("page_mapping_unavailable_ndl_ids"))
    )
    availability = artifacts.get("source_availability") if isinstance(artifacts, dict) else None
    if isinstance(availability, dict) and availability.get("status") == "unavailable":
        reason = str(availability.get("reason") or "unknown")
        if reason in {"no_digital_pid", "mapped_page_out_of_scan_range", "downloaded_page_range_adjusted"} and has_page_mapping_block:
            return None
        return reason
    notes = "\n".join(str(note) for note in (result.get("notes") or []))
    if "remote_copy_only_no_print" in notes:
        return "remote_copy_only_no_print"
    if "restricted_download_skipped_no_ndl_pid" in notes and not has_page_mapping_block:
        return "no_digital_pid"
    if "download_not_pdf" in notes:
        return "download_not_pdf"
    if "download_http_404" in notes:
        return "download_http_404"
    if "download_http_403" in notes:
        return "download_http_403"
    if "print_button_not_found" in notes:
        return "print_button_not_found"
    if "download_link_not_found" in notes:
        return "download_link_not_found"
    failures = artifacts.get("download_fast_failure") or {}
    failure_text = str(failures)
    if "remote_copy_only_no_print" in failure_text:
        return "remote_copy_only_no_print"
    return None


def _is_remote_copy_only_result(result: Dict[str, Any]) -> bool:
    return _source_unavailable_reason(result) == "remote_copy_only_no_print"


def _append_not_downloadable_section(lines: list[str], results: Sequence[Dict[str, Any]]) -> None:
    blocked = [
        (result, reason)
        for result in results
        for reason in [_source_unavailable_reason(result)]
        if reason
    ]
    if not blocked:
        return
    lines.append("## 可检索但当前不可下载")
    lines.append("")
    for result, reason in blocked:
        footnote = result.get("footnote") or {}
        matches = result.get("ndl_matches") or []
        first_match = matches[0] if matches else {}
        lines.append(
            f"- 脚注 {result.get('footnote_id')} | {footnote.get('title') or footnote.get('text', '')[:40]} "
            f"| reason={reason} | {first_match.get('url') or 'no url'}"
        )
    lines.append("")


def describe_page_trace(candidate: CitationCandidate) -> str:
    book_pages = format_page_list(candidate.footnote.page_numbers)
    parts = [f"脚注书页 {book_pages}"]

    mapped_pages = candidate.artifacts.get("mapped_footnote_pages")
    if mapped_pages:
        parts.append(f"估算扫描页 {format_page_list(mapped_pages)}")

    download_range = candidate.artifacts.get("downloaded_page_range")
    if isinstance(download_range, (list, tuple)) and len(download_range) == 2:
        parts.append(f"下载扫描范围 {download_range[0]}-{download_range[1]}")

    page_mapping = candidate.artifacts.get("page_mapping")
    if isinstance(page_mapping, dict):
        anchor_book = page_mapping.get("anchor_book_page")
        anchor_scan = page_mapping.get("anchor_scan_page")
        if anchor_book and anchor_scan:
            parts.append(f"映射锚点 书页{anchor_book}->扫描页{anchor_scan}")

    matched_book_pages = candidate.artifacts.get("matched_book_pages")
    if matched_book_pages:
        parts.append(f"匹配书页 {format_page_list(matched_book_pages)}")
    elif candidate.matched_page is not None:
        page_label_mode = candidate.artifacts.get("page_label_mode")
        label = "匹配书页" if page_label_mode == "book" else "匹配扫描页"
        parts.append(f"{label} {candidate.matched_page}")

    matched_scan_page = candidate.artifacts.get("matched_scan_page")
    if matched_scan_page is not None:
        parts.append(f"匹配扫描页 {matched_scan_page}")

    page_distance = candidate.artifacts.get("page_distance_from_citation")
    if page_distance is not None:
        parts.append(f"页距 {page_distance}")

    return "；".join(parts)


def summarize_candidates(candidates: Sequence[CitationCandidate]) -> Dict[str, int]:
    summary: Dict[str, int] = {
        "total_candidates": len(candidates),
        "source_found": 0,
        "source_not_found": 0,
        "source_mismatch": 0,
        "download_failed": 0,
        "ocr_failed": 0,
        "page_mapping_unavailable": 0,
        "matched": 0,
        "needs_manual_review": 0,
    }
    for item in candidates:
        if item.ndl_matches:
            if not all(match.metadata.get("source_mismatch") for match in item.ndl_matches):
                summary["source_found"] += 1
        else:
            summary["source_not_found"] += 1

        if item.verification_status in summary and item.verification_status != "source_found":
            summary[item.verification_status] += 1
    for status, count in count_refined_candidate_statuses(candidates).items():
        summary[f"refined:{status}"] = count
    for status, count in count_support_candidate_statuses(candidates).items():
        summary[f"support:{status}"] = count
    return summary


def _append_refined_status_breakdown(lines: list[str], refined_counts: Dict[str, int]) -> None:
    if not refined_counts:
        return
    lines.append("## 状态细分")
    lines.append("")
    for status, count in sorted(refined_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {refined_status_label(status)} (`{status}`): {count}")
    lines.append("")


def _append_support_status_breakdown(lines: list[str], support_counts: Dict[str, int]) -> None:
    visible_counts = {
        status: count
        for status, count in support_counts.items()
        if count and status != "unassessed"
    }
    if not visible_counts:
        return
    lines.append("## 出处有效性细分")
    lines.append("")
    for status, count in sorted(visible_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {support_status_label(status)} (`{status}`): {count}")
    lines.append("")


def render_verification_markdown_report(
    document: Dict[str, Any],
    candidates: Sequence[CitationCandidate],
) -> str:
    summary = summarize_candidates(candidates)
    lines = [
        "# 史料引文核对报告",
        "",
        f"- 文档标题: {document.get('title', '')}",
        f"- 段落数: {document.get('paragraph_count', 0)}",
        f"- 脚注数: {document.get('footnote_count', 0)}",
        f"- 引文候选数: {len(candidates)}",
        f"- 已找到线上来源: {summary.get('source_found', 0)}",
        f"- 成功抽取并给出对照: {summary.get('matched', 0)}",
        f"- 待人工复核: {summary.get('needs_manual_review', 0)}",
        f"- 在线上平台未检到来源: {summary.get('source_not_found', 0)}",
        f"- 线上候选疑似误配: {summary.get('source_mismatch', 0)}",
        f"- 可检索但当前不可下载: {summary.get('refined:source_unavailable', 0)}",
        f"- 页码映射未校准: {summary.get('page_mapping_unavailable', 0)}",
        f"- 已检到但下载/识别失败: {summary.get('download_failed', 0) + summary.get('ocr_failed', 0)}",
        f"- 可作为直接出处: {summary.get('support:direct_support', 0)}",
        f"- 部分对应/背景材料: {summary.get('support:partial_support', 0)}",
        f"- 未构成有效对应: {summary.get('support:not_supported', 0)}",
        "",
    ]

    if not candidates:
        lines.extend(["未识别到可核对的引文候选。", ""])
        return "\n".join(lines)

    _append_refined_status_breakdown(lines, count_refined_candidate_statuses(candidates))
    _append_support_status_breakdown(lines, count_support_candidate_statuses(candidates))
    _append_not_downloadable_section(lines, [item.to_dict() for item in candidates])

    for item in candidates:
        refined_status = classify_candidate_status(item)
        status_label = item.verification_status
        if refined_status != item.verification_status:
            status_label = f"{item.verification_status} / {refined_status}"
        support_status = getattr(item, "support_status", "") or "unassessed"
        support_reason = getattr(item, "support_reason", "") or ""
        evidence_scope = getattr(item, "evidence_scope", "") or item.artifacts.get("alignment_scope", "")
        lines.extend(
            [
                f"## 段落 {item.paragraph_index} / 脚注 {item.footnote_id}",
                "",
                f"- 状态: {status_label}",
                f"- 状态说明: {refined_status_label(refined_status)}",
                f"- 出处有效性: {support_status_label(support_status)} (`{support_status}`)",
                f"- 有效性依据: {support_reason or '尚未生成'}",
                f"- 证据范围: {evidence_scope or '未记录'}",
                f"- Source graph: {(item.artifacts.get('source_graph') or {}).get('source_type', 'unknown')} | "
                f"family={(item.artifacts.get('source_graph') or {}).get('source_family', 'unknown')} | "
                f"resolver={(item.artifacts.get('source_graph') or {}).get('resolver', 'unknown')}",
                f"- Resolver plan: mode={(item.artifacts.get('source_resolver_plan') or {}).get('verification_mode', 'unknown')} | "
                f"pid_scope={(item.artifacts.get('source_resolver_plan') or {}).get('pid_scope_strategy', 'unknown')}",
                f"- 来源: {item.footnote.author}《{item.footnote.title}》 {item.footnote.page_label}".strip(),
                f"- 置信度: {item.confidence if item.confidence is not None else 'N/A'}",
                f"- 页码信息: {describe_page_trace(item)}",
                "",
                "### 中文译文",
                "",
                item.translation_text or item.paragraph_text,
                "",
                "### 日文原文",
                "",
                item.matched_japanese or "未自动定位到原文，请人工复核。",
                "",
            ]
        )
        if item.ndl_matches:
            lines.append("### 线上候选")
            lines.append("")
            for match in item.ndl_matches[:3]:
                label = match.title or "未命名结果"
                platform = match.platform or "unknown"
                route = (match.metadata or {}).get("search_route") or ""
                route_label = f" | route={route}" if route else ""
                lines.append(
                    f"- [{platform}] {label} | score={match.score:.3f}{route_label} | {match.url or '无链接'}"
                )
            lines.append("")
        source_attempts = _source_attempt_lines(
            item.artifacts,
            current={
                "selected_source_match": item.artifacts.get("selected_source_match"),
                "downloaded_page_range": item.artifacts.get("downloaded_page_range"),
                "confidence": item.confidence,
                "support_status": item.support_status,
                "verification_status": item.verification_status,
            },
        )
        if source_attempts:
            lines.append("### 来源候选尝试记录")
            lines.append("")
            lines.extend(source_attempts)
            lines.append("")
        llm_review = item.artifacts.get("llm_review") or {}
        if llm_review:
            lines.append("### LLM 精核")
            lines.append("")
            lines.append(f"- 判定: {support_status_label(llm_review.get('decision') or 'uncertain')} (`{llm_review.get('decision') or 'uncertain'}`)")
            lines.append(f"- 模型/来源: {llm_review.get('provider') or 'unknown'} {llm_review.get('model') or ''}".strip())
            lines.append(f"- 置信度: {llm_review.get('confidence', 'N/A')}")
            lines.append(f"- 理由: {llm_review.get('reason') or '未提供'}")
            if llm_review.get("exact_sentence"):
                lines.append("")
                lines.append("```text")
                lines.append(str(llm_review.get("exact_sentence")))
                lines.append("```")
            lines.append("")
        review_context = item.artifacts.get("review_context") or []
        if review_context:
            lines.append("### 上下文 OCR（清洗后）")
            lines.append("")
            for context_item in review_context:
                page_label = "书页" if item.artifacts.get("page_label_mode") == "book" else "页"
                lines.append(f"- {page_label} {context_item.get('page')}")
                lines.append("")
                lines.append(context_item.get("cleaned_text") or context_item.get("text") or "")
                lines.append("")
        if item.notes:
            lines.append("### 备注")
            lines.append("")
            for note in item.notes[:6]:
                lines.append(f"- {note}")
            lines.append("")

    pending_items = [
        item
        for item in candidates
        if item.verification_status in (
            "source_not_found",
            "source_mismatch",
            "download_failed",
            "ocr_failed",
            "page_mapping_unavailable",
            "needs_manual_review",
            "fulltext_only_hit",
            "fulltext_lead_only",
            "iiif_image_ocr_available",
        )
    ]
    if pending_items:
        lines.append("## 未覆盖或需复核")
        lines.append("")
        for item in pending_items:
            refined_status = classify_candidate_status(item)
            diagnostic = _compact_source_type_diagnostic_summary(item.to_dict())
            diagnostic_suffix = f" | diag={diagnostic}" if diagnostic else ""
            lines.append(
                f"- 脚注 {item.footnote_id} | {item.verification_status} / {refined_status} | "
                f"{item.footnote.title or item.footnote.text[:40]}"
                f"{diagnostic_suffix}"
            )
        lines.append("")
    return "\n".join(lines)


def summarize_checkpoint(checkpoint: Dict[str, Any], total_candidates: int) -> Dict[str, int]:
    status_counter = Counter()
    support_counter = Counter()
    source_found = 0
    for result in checkpoint.get("results", {}).values():
        status_counter[result.get("verification_status", "unknown")] += 1
        support_counter[result.get("support_status") or "unassessed"] += 1
        if result.get("ndl_matches"):
            source_found += 1

    summary = {
        "total_candidates": total_candidates,
        "processed_candidates": len(checkpoint.get("results", {})),
        "remaining_candidates": max(0, total_candidates - len(checkpoint.get("results", {}))),
        "source_found": source_found,
        "matched": status_counter.get("matched", 0),
        "needs_manual_review": status_counter.get("needs_manual_review", 0),
        "source_not_found": status_counter.get("source_not_found", 0),
        "source_mismatch": status_counter.get("source_mismatch", 0),
        "download_failed": status_counter.get("download_failed", 0),
        "ocr_failed": status_counter.get("ocr_failed", 0),
        "page_mapping_unavailable": status_counter.get("page_mapping_unavailable", 0),
    }
    for status, count in count_refined_result_statuses(checkpoint.get("results", {}).values()).items():
        summary[f"refined:{status}"] = count
    for status, count in support_counter.items():
        summary[f"support:{status}"] = count
    llm_counts = _llm_review_counters(list(checkpoint.get("results", {}).values()))
    summary.update({f"llm:{key}": value for key, value in llm_counts.items()})
    return summary


def build_artifact_summary(output_dir: Path) -> Dict[str, Any]:
    pdf_files = sorted(output_dir.glob("*.pdf"))
    page_maps = sorted(output_dir.glob("page_map_*"))
    download_range_index = refresh_download_range_index(output_dir)
    return {
        "downloaded_pdfs": [
            {
                "name": pdf_file.name,
                "size": pdf_file.stat().st_size,
                "modified_at": datetime.fromtimestamp(pdf_file.stat().st_mtime).isoformat(timespec="seconds"),
            }
            for pdf_file in pdf_files
        ],
        "page_maps": [
            {
                "name": page_map.name,
                "pdf_count": len(list(page_map.glob("*.pdf"))),
                "modified_at": datetime.fromtimestamp(page_map.stat().st_mtime).isoformat(timespec="seconds"),
            }
            for page_map in page_maps
        ],
        "download_range_index": download_range_index,
    }


def render_resume_markdown_report(
    *,
    document: Dict[str, Any],
    checkpoint: Dict[str, Any],
    total_candidates: int,
    output_dir: Path,
) -> str:
    summary = summarize_checkpoint(checkpoint, total_candidates=total_candidates)
    artifact_summary = checkpoint.get("artifacts") or {}
    lines = [
        "# 历史引文核对中断点报告",
        "",
        f"- 文档标题: {document.get('title', '')}",
        f"- 全部候选数: {summary['total_candidates']}",
        f"- 已处理候选数: {summary['processed_candidates']}",
        f"- 剩余候选数: {summary['remaining_candidates']}",
        f"- 已找到线上来源: {summary['source_found']}",
        f"- 已形成对照: {summary['matched']}",
        f"- 待人工复核: {summary['needs_manual_review']}",
        f"- 来源未检到: {summary['source_not_found']}",
        f"- 来源疑似误配: {summary['source_mismatch']}",
        f"- 可检索但当前不可下载: {summary.get('refined:source_unavailable', 0)}",
        f"- 下载失败: {summary['download_failed']}",
        f"- OCR 失败: {summary['ocr_failed']}",
        f"- 页码映射未校准: {summary.get('page_mapping_unavailable', 0)}",
        f"- 可作为直接出处: {summary.get('support:direct_support', 0)}",
        f"- 页码疑似不准但原文对应: {summary.get('support:page_mismatch_but_support', 0)}",
        f"- 部分对应/背景材料: {summary.get('support:partial_support', 0)}",
        f"- 未构成有效对应: {summary.get('support:not_supported', 0)}",
        f"- 进入 LLM 精核: {summary.get('llm:eligible_for_llm_review', 0)}",
        f"- LLM 精核成功: {summary.get('llm:llm_review_success', 0)}",
        f"- LLM JSON 修复成功: {summary.get('llm:llm_review_json_repaired', 0)}",
        f"- 启发式兜底精核: {summary.get('llm:llm_review_fallback_heuristic', 0)}",
        f"- 输出目录: {output_dir.resolve()}",
        "",
    ]
    refined_counts = count_refined_result_statuses(checkpoint.get("results", {}).values())
    _append_refined_status_breakdown(lines, refined_counts)
    _append_support_status_breakdown(lines, count_support_result_statuses(checkpoint.get("results", {}).values()))
    _append_not_downloadable_section(lines, list(checkpoint.get("results", {}).values()))

    downloaded_pdfs = artifact_summary.get("downloaded_pdfs") or []
    if downloaded_pdfs:
        lines.append("## 已落盘文献 PDF")
        lines.append("")
        for item in downloaded_pdfs:
            lines.append(f"- {item['name']} | {item['size']} bytes | {item['modified_at']}")
        lines.append("")

    page_maps = artifact_summary.get("page_maps") or []
    if page_maps:
        lines.append("## 已建立页码映射样本")
        lines.append("")
        for item in page_maps:
            lines.append(f"- {item['name']} | 样本 PDF 数 {item['pdf_count']} | {item['modified_at']}")
        lines.append("")

    indexed_ranges = (artifact_summary.get("download_range_index") or {}).get("records") or []
    if indexed_ranges:
        lines.append("## NDL 页窗 PDF 复用索引")
        lines.append("")
        for item in indexed_ranges:
            lines.append(
                f"- `{item.get('ndl_id')}` p{item.get('start_page')}-p{item.get('end_page')} | "
                f"{item.get('name')} | {item.get('size')} bytes"
            )
        lines.append("")

    processed_results = list(checkpoint.get("results", {}).values())
    if processed_results:
        lines.append("## 已处理候选")
        lines.append("")
        for result in processed_results:
            footnote = result.get("footnote", {})
            refined_status = classify_result_status(result)
            status_label = result.get("verification_status")
            if refined_status != status_label:
                status_label = f"{status_label} / {refined_status}"
            support_status = result.get("support_status") or "unassessed"
            diagnostic = _compact_source_type_diagnostic_summary(result)
            diagnostic_suffix = f" | diag={diagnostic}" if diagnostic else ""
            lines.append(
                f"- 脚注 {result.get('footnote_id')} | {status_label} | "
                f"{support_status_label(support_status)} | "
                f"{footnote.get('title') or footnote.get('text', '')[:40]}"
                f"{diagnostic_suffix}"
            )
        lines.append("")

        lines.append("## 已处理候选详情")
        lines.append("")
        for result in processed_results:
            footnote = result.get("footnote", {})
            artifacts = result.get("artifacts", {}) or {}
            refined_status = classify_result_status(result)
            status_label = result.get("verification_status")
            if refined_status != status_label:
                status_label = f"{status_label} / {refined_status}"
            lines.append(f"### 脚注 {result.get('footnote_id')} | {status_label}")
            lines.append("")
            lines.append(f"- 候选 ID: {result.get('candidate_id')}")
            lines.append(f"- 状态说明: {refined_status_label(refined_status)}")
            lines.append(f"- 当前状态: {refined_status}")
            lines.append(f"- 当前证据状态: {_current_evidence_status(result)}")
            support_status = result.get("support_status") or "unassessed"
            support_reason = result.get("support_reason") or ""
            evidence_scope = result.get("evidence_scope") or artifacts.get("alignment_scope") or ""
            lines.append(f"- 出处有效性: {support_status_label(support_status)} (`{support_status}`)")
            lines.append(f"- 有效性依据: {support_reason or '尚未生成'}")
            lines.append(f"- 证据范围: {evidence_scope or '未记录'}")
            source_graph = _source_graph_from_result(result)
            if source_graph:
                lines.append(
                    f"- Source graph: {source_graph.get('source_type') or 'unknown'} "
                    f"| family={source_graph.get('source_family') or 'unknown'} "
                    f"| resolver={source_graph.get('resolver') or 'unknown'}"
                )
                if source_graph.get("host_title"):
                    lines.append(f"- Host title: {source_graph.get('host_title')}")
                if source_graph.get("contained_title"):
                    lines.append(f"- Contained title: {source_graph.get('contained_title')}")
                if source_graph.get("volume_terms"):
                    lines.append(f"- 卷册线索: {', '.join(str(item) for item in source_graph.get('volume_terms') or [])}")
                if source_graph.get("known_pid_candidates"):
                    lines.append(
                        f"- 已知 PID 候选: {', '.join(str(item) for item in source_graph.get('known_pid_candidates') or [])}"
                    )
            resolver_plan = artifacts.get("source_resolver_plan") or {}
            if isinstance(resolver_plan, dict) and resolver_plan:
                lines.append(
                    f"- Resolver plan: mode={resolver_plan.get('verification_mode') or 'unknown'} "
                    f"| pid_scope={resolver_plan.get('pid_scope_strategy') or 'unknown'} "
                    f"| cache={resolver_plan.get('source_level_cache_key') or 'n/a'}"
                )
                if resolver_plan.get("warnings"):
                    lines.append(f"- Resolver warnings: {', '.join(str(item) for item in resolver_plan.get('warnings') or [])}")
            source_type_summary = _format_source_type_diagnostic_summary(result)
            if source_type_summary:
                lines.append(source_type_summary)
            adapter_order_line = _format_adapter_candidate_order(result)
            if adapter_order_line:
                lines.append(adapter_order_line)
            history_lines = _processing_history_lines(result)
            if history_lines:
                lines.append(f"- 处理历史: {'; '.join(history_lines)}")
            manual_recipe = _manual_search_recipe_from_result(result, current_status=refined_status)
            manual_recipe_line = _format_manual_search_recipe(manual_recipe)
            if manual_recipe_line:
                lines.append(manual_recipe_line)
            evidence_level = artifacts.get("evidence_level")
            if evidence_level:
                lines.append(f"- 证据等级: {evidence_level}")
            citation_unit = artifacts.get("citation_unit") or {}
            if isinstance(citation_unit, dict):
                lines.append(
                    f"- 论文侧引用单位: {citation_unit.get('unit_type') or 'unknown'} "
                    f"| confidence={citation_unit.get('confidence', 'N/A')} "
                    f"| {citation_unit.get('reason') or ''}".rstrip()
                )
            page_span = artifacts.get("page_span") or {}
            if isinstance(page_span, dict) and page_span.get("mode"):
                lines.append(
                    f"- 脚注页码类型: {page_span.get('mode')} | "
                    f"{page_span.get('reason') or ''}"
                )
            lines.append(f"- 文献题名: {footnote.get('title') or '未解析'}")
            if footnote.get("host_title"):
                lines.append(f"- 析出文献宿主书: {footnote.get('host_title')}")
            if footnote.get("source_relation"):
                lines.append(f"- 来源关系: {footnote.get('source_relation')}")
            lines.append(f"- 脚注页码: {format_page_list(footnote.get('page_numbers', []) or [])}")
            if artifacts.get("downloaded_page_range"):
                page_range = artifacts["downloaded_page_range"]
                lines.append(f"- 下载/抽取页范围: {page_range[0]}-{page_range[1]}")
            if artifacts.get("source_level_ocr_cache_hit"):
                cache_hit = artifacts.get("source_level_ocr_cache_hit") or {}
                lines.append(
                    f"- Source-level OCR cache: hit | pages={format_page_list(cache_hit.get('pages') or [])}"
                )
            if artifacts.get("mapped_footnote_pages"):
                mapped_pages = ", ".join(str(page) for page in artifacts["mapped_footnote_pages"])
                lines.append(f"- 双开页换算后的扫描页: {mapped_pages}")
            availability = artifacts.get("source_availability") or {}
            if isinstance(availability, dict) and availability.get("status") == "unavailable":
                reason = availability.get("reason") or "unknown"
                detail = availability.get("detail") or ""
                lines.append(f"- 来源可下载性: unavailable / {reason}{(' / ' + str(detail)) if detail else ''}")
            known_pid_fallback_line = _format_known_pid_page_window_fallback(artifacts)
            if known_pid_fallback_line:
                lines.append(known_pid_fallback_line)
            diary_pdf_route_line = _format_diary_date_pdf_page_fallback(artifacts)
            if diary_pdf_route_line:
                lines.append(diary_pdf_route_line)
            diary_claim_scope = artifacts.get("diary_claim_facet_trigger_scope")
            if diary_claim_scope:
                lines.append(f"- Diary claim facet trigger scope: {diary_claim_scope}")
            skipped_fulltext_leads = artifacts.get("non_equivalent_fulltext_lead_skipped_ids") or []
            if isinstance(skipped_fulltext_leads, list) and skipped_fulltext_leads:
                lines.append(
                    "- 非等价全文线索已跳过自动轮换: "
                    f"{', '.join(str(item) for item in skipped_fulltext_leads)}"
                )
            fulltext_probe_line = _format_ndl_fulltext_probe(artifacts)
            if fulltext_probe_line:
                lines.append(fulltext_probe_line)
            iiif_line = _format_iiif_image_ocr_availability(artifacts)
            if iiif_line:
                lines.append(iiif_line)
            fulltext_context_lines = _format_fulltext_context_candidates(artifacts)
            if fulltext_context_lines:
                lines.extend(fulltext_context_lines)
            compound_packet_lines = _format_fulltext_compound_evidence_packet(artifacts)
            if compound_packet_lines:
                lines.extend(compound_packet_lines)
            diary_diagnostic_line = _format_diary_date_lookup_diagnostic(artifacts)
            if diary_diagnostic_line:
                lines.append(diary_diagnostic_line)
            contained_diagnostic_line = _format_contained_document_lookup_diagnostic(artifacts)
            if contained_diagnostic_line:
                lines.append(contained_diagnostic_line)
            ndl_fulltext_hints = artifacts.get("ndl_fulltext_hints") or []
            if isinstance(ndl_fulltext_hints, list) and ndl_fulltext_hints:
                lines.append("- NDL 全文命中线索: available_snippet_hint")
                for hint in ndl_fulltext_hints[:3]:
                    if not isinstance(hint, dict):
                        continue
                    pdf_page = hint.get("pdf_page")
                    page_status = hint.get("page_match_status") or "unknown"
                    snippet = truncate_text(str(hint.get("snippet") or ""), limit=160)
                    lines.append(
                        f"  - pdf_page={pdf_page or 'n/a'} | {page_status} | {snippet}"
                    )
                    expanded_context = hint.get("expanded_context")
                    if expanded_context:
                        lines.append(
                            f"    - 接龙上下文: {truncate_text(str(expanded_context), limit=260)}"
                        )
            if result.get("matched_page") is not None:
                lines.append(f"- 当前最佳匹配页: {result.get('matched_page')}")
            if result.get("confidence") is not None:
                lines.append(f"- 置信度: {result.get('confidence')}")
            llm_review = artifacts.get("llm_review") or {}
            if llm_review:
                model_label = " ".join(
                    str(part)
                    for part in [llm_review.get("provider"), llm_review.get("model")]
                    if part
                )
                lines.append(
                    f"- LLM 精核: {support_status_label(llm_review.get('decision') or 'uncertain')} "
                    f"| confidence={llm_review.get('confidence', 'N/A')} | {model_label or 'unknown'}"
                )
                lines.append(
                    "- LLM 精核状态: "
                    f"success={bool(llm_review.get('llm_review_success'))}, "
                    f"json_repaired={bool(llm_review.get('llm_review_json_repaired'))}, "
                    f"heuristic_fallback={bool(llm_review.get('llm_review_fallback_heuristic'))}, "
                    f"failed={bool(llm_review.get('llm_review_failed'))}"
                )
                if llm_review.get("reason"):
                    lines.append(f"- LLM 精核理由: {llm_review.get('reason')}")
                if llm_review.get("supporting_context_ids"):
                    lines.append(
                        "- LLM 组合上下文: "
                        + ", ".join(str(item) for item in llm_review.get("supporting_context_ids") or [])
                    )
                if llm_review.get("compound_evidence_packet_used"):
                    added = llm_review.get("compound_evidence_added_context_ids") or []
                    facets = llm_review.get("compound_evidence_facet_ids") or []
                    lines.append(
                        "- LLM 复合证据补齐: "
                        f"contexts={', '.join(str(item) for item in added) if isinstance(added, list) else added} "
                        f"| facets={', '.join(str(item) for item in facets) if isinstance(facets, list) else facets}"
                    )
                if artifacts.get("fulltext_llm_review_basis"):
                    lines.append(f"- LLM 精核证据基底: {artifacts.get('fulltext_llm_review_basis')}")
            llm_runtime = artifacts.get("llm_review_runtime") or {}
            if isinstance(llm_runtime, dict) and llm_runtime:
                lines.append(
                    f"- 本地模型健康检查: {llm_runtime.get('provider')} "
                    f"available={llm_runtime.get('available')} "
                    f"model={llm_runtime.get('selected_model') or 'n/a'} "
                    f"timeout={llm_runtime.get('timeout_seconds') or 'n/a'}s"
                )
            if artifacts.get("page_distance_from_citation") is not None:
                lines.append(f"- 与脚注页码距离: {artifacts.get('page_distance_from_citation')}")
            if result.get("notes"):
                lines.append(f"- 备注: {'; '.join(str(note) for note in result.get('notes', []))}")
            lines.append("")

            if result.get("translation_text"):
                lines.append("**中文译文/论文引文**")
                lines.append("")
                lines.append("```text")
                lines.append(truncate_text(result.get("translation_text"), limit=1200))
                lines.append("```")
                lines.append("")

            if footnote.get("text"):
                lines.append("**脚注原文**")
                lines.append("")
                lines.append("```text")
                lines.append(truncate_text(footnote.get("text"), limit=1000))
                lines.append("```")
                lines.append("")

            ndl_matches = result.get("ndl_matches") or []
            claim_queries = artifacts.get("claim_fulltext_global_queries") or []
            if isinstance(claim_queries, list) and claim_queries:
                lines.append("**NDL 全文查询层**")
                lines.append("")
                for query in claim_queries[:6]:
                    lines.append(f"- {truncate_text(str(query), limit=180)}")
                lines.append("")
            equivalent_group = artifacts.get("equivalent_pid_group") or []
            if isinstance(equivalent_group, list) and equivalent_group:
                lines.append("**严格等价 PID 组**")
                lines.append("")
                for item in equivalent_group[:6]:
                    if not isinstance(item, dict):
                        continue
                    title = item.get("title") or item.get("ndl_id") or "未命名"
                    ndl_id = item.get("ndl_id") or "n/a"
                    date = item.get("date") or ""
                    route = item.get("search_route") or item.get("fulltext_query") or ""
                    suffix = f" | {route}" if route else ""
                    lines.append(f"- {title} | PID={ndl_id} | {date}{suffix}")
                lines.append("")
            fulltext_leads = artifacts.get("fulltext_lead_pid_group") or []
            if isinstance(fulltext_leads, list) and fulltext_leads:
                lines.append("**全文线索 PID 组（非等价）**")
                lines.append("")
                lines.append("- 说明: 这些 PID 来自全站全文命中，只能用于人工回查或二次检索，不能作为自动候选轮换的等价来源。")
                fulltext_lead_hint = _format_fulltext_lead_manual_hint(artifacts)
                if fulltext_lead_hint:
                    lines.append(fulltext_lead_hint)
                for item in fulltext_leads[:6]:
                    if not isinstance(item, dict):
                        continue
                    title = item.get("title") or item.get("ndl_id") or "未命名"
                    ndl_id = item.get("ndl_id") or "n/a"
                    route = item.get("search_route") or item.get("fulltext_query") or ""
                    suffix = f" | {route}" if route else ""
                    lines.append(f"- {title} | PID={ndl_id}{suffix}")
                lines.append("")
            if ndl_matches:
                lines.append("**NDL 候选**")
                lines.append("")
                for match in ndl_matches[:3]:
                    label = match.get("title") or match.get("ndl_id") or "未命名"
                    score = match.get("score")
                    url = match.get("url") or ""
                    metadata = match.get("metadata") if isinstance(match.get("metadata"), dict) else {}
                    route = metadata.get("search_route") or ""
                    route_label = f" | route={route}" if route else ""
                    lines.append(f"- {label} | score={score}{route_label} | {url}")
                lines.append("")

            source_attempts = _source_attempt_lines(
                artifacts,
                current={
                    "selected_source_match": artifacts.get("selected_source_match"),
                    "downloaded_page_range": artifacts.get("downloaded_page_range"),
                    "confidence": result.get("confidence"),
                    "support_status": result.get("support_status"),
                    "verification_status": result.get("verification_status"),
                },
            )
            if source_attempts:
                lines.append("**来源候选尝试记录**")
                lines.append("")
                lines.extend(source_attempts)
                lines.append("")

            if result.get("matched_japanese"):
                lines.append("**日文原文片段（当前最佳匹配）**")
                lines.append("")
                lines.append("```text")
                lines.append(truncate_text(result.get("matched_japanese"), limit=1800))
                lines.append("```")
                lines.append("")

            distributed_alignments = artifacts.get("distributed_claim_alignments") or []
            if distributed_alignments:
                lines.append("**多页分隔式信息对齐**")
                lines.append("")
                for alignment in distributed_alignments[:8]:
                    lines.append(
                        f"- claim#{alignment.get('claim_index')} | "
                        f"page={alignment.get('matched_page')} | "
                        f"confidence={alignment.get('confidence')}"
                    )
                lines.append("")

            llm_review = artifacts.get("llm_review") or {}
            if llm_review.get("exact_sentence"):
                lines.append("**LLM 精核句（不含上下文）**")
                lines.append("")
                lines.append("```text")
                lines.append(truncate_text(llm_review.get("exact_sentence"), limit=800))
                lines.append("```")
                lines.append("")

            review_context = artifacts.get("review_context") or []
            if review_context:
                lines.append("**上下文 OCR（清洗后）**")
                lines.append("")
                for context_item in review_context:
                    lines.append(f"页 {context_item.get('page')}")
                    lines.append("")
                    lines.append("```text")
                    lines.append(truncate_text(context_item.get("text"), limit=1200))
                    lines.append("```")
                    lines.append("")

    if summary["remaining_candidates"]:
        lines.append("## 续跑说明")
        lines.append("")
        lines.append("- checkpoint 已保存，可从当前目录继续补跑，不需要重头开始。")
        lines.append("- 下一轮会优先复用本目录下已有的 `page_map_*`、`page_mapping_cache.json` 与已下载 PDF。")
        lines.append("")

    return "\n".join(lines)
