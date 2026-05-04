from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.historical_citation.footnote_parser import parse_footnote_text
from modules.historical_citation.models import CitationCandidate, NDLSearchMatch
from modules.historical_citation.ndl_fulltext_context import search_ndl_fulltext_in_item
from modules.historical_citation.ndl_search import search_ndl_digital_fulltext
from modules.historical_citation.reporting import (
    _format_contained_document_lookup_diagnostic,
    _format_diary_date_lookup_diagnostic,
    _format_fulltext_lead_manual_hint,
)
from modules.historical_citation.source_graph import attach_source_graph_artifacts, build_source_query_plan
from modules.historical_citation.source_platforms import NDLSourcePlatformAdapter
from modules.historical_citation_verifier import HistoricalCitationVerifier
from scripts.refine_historical_citation_pdf_next_stage import record_equivalent_pid_group


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Probe reusable historical source-type resolvers against NDL Digital Collection."
    )
    parser.add_argument("--output-dir", default="output/historical_citation_source_type_probe")
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--max-queries", type=int, default=5)
    parser.add_argument("--max-known-pids", type=int, default=3)
    return parser


def _cases() -> List[Dict[str, str]]:
    return [
        {
            "case_id": "nihon_gaiko_bunsho_volume_series",
            "label": "日本外交文書 第32巻",
            "footnote": "外务省编：《日本外交文书》（外務省編：『日本外交文書』）第32卷，东京：外务省1955年版，第216～221页。",
            "claim": "约翰·海伊提出在华门户开放和机会均等原则，日本政府随后作出回答。",
        },
        {
            "case_id": "hara_takashi_diary_date",
            "label": "原敬日記 日期型",
            "footnote": "原敬：《原敬日記》，1900年5月12日，第84頁。",
            "claim": "1900年5月12日，原敬在日记中记录了相关交涉。",
        },
        {
            "case_id": "yamagata_opinion_document",
            "label": "山縣有朋意見書",
            "footnote": "山縣有朋：《山縣有朋意見書》，第12頁。",
            "claim": "山縣有朋在意见书中提出了相关政策主张。",
        },
    ]


def _append_unique(items: List[str], values: Iterable[Any]) -> None:
    for value in values:
        text = str(value or "").strip()
        if text and text not in items:
            items.append(text)


def _match_from_record(record: Dict[str, Any]) -> NDLSearchMatch:
    metadata = dict(record.get("metadata") or {})
    if record.get("search_route"):
        metadata.setdefault("search_route", record.get("search_route"))
    if record.get("fulltext_query"):
        metadata.setdefault("claim_fulltext_global_query", record.get("fulltext_query"))
    return NDLSearchMatch(
        title=str(record.get("title") or ""),
        url=str(record.get("url") or ""),
        ndl_id=record.get("ndl_id"),
        platform=record.get("platform") or "ndl",
        platform_item_id=record.get("platform_item_id"),
        author=record.get("author"),
        date=record.get("date"),
        publisher=record.get("publisher"),
        pdf_url=record.get("pdf_url"),
        score=float(record.get("score") or 0),
        metadata=metadata,
    )


def _summarize_global_record(record: Dict[str, Any]) -> Dict[str, Any]:
    metadata = record.get("metadata") or {}
    hints = metadata.get("fulltext_hints") or []
    first_hint = hints[0] if hints and isinstance(hints[0], dict) else {}
    return {
        "ndl_id": record.get("ndl_id"),
        "title": record.get("title"),
        "url": record.get("url"),
        "score": record.get("score"),
        "search_route": metadata.get("search_route"),
        "metadata": dict(metadata),
        "hint_pdf_page": first_hint.get("pdf_page"),
        "hint_snippet": str(first_hint.get("snippet") or "")[:180],
    }


def _summarize_adapter_match(match: NDLSearchMatch) -> Dict[str, Any]:
    metadata = match.metadata or {}
    return {
        "ndl_id": match.ndl_id,
        "title": match.title,
        "url": match.url,
        "score": match.score,
        "search_route": metadata.get("search_route"),
        "search_routes": metadata.get("search_routes") or [],
        "known_pid_candidate": bool(metadata.get("known_pid_candidate")),
        "configured_pid_rank": metadata.get("configured_pid_rank"),
        "resolver": metadata.get("resolver"),
        "candidate_note": metadata.get("candidate_note"),
    }


def _probe_adapter_candidates(footnote, *, max_results: int, claim_text: str = "") -> Dict[str, Any]:
    adapter = NDLSourcePlatformAdapter(lambda: None, allow_external_fallback=False)
    try:
        matches = adapter.search(footnote, max_results=max_results, claim_text=claim_text)
        error = ""
    except Exception as exc:  # noqa: BLE001
        matches = []
        error = f"{type(exc).__name__}: {exc}"
    return {
        "error": error,
        "matches": [_summarize_adapter_match(match) for match in matches],
    }


def _probe_global_queries(queries: List[str], *, max_results: int) -> List[Dict[str, Any]]:
    probes: List[Dict[str, Any]] = []
    for query in queries:
        try:
            records = search_ndl_digital_fulltext(query, max_results=max_results)
            error = ""
        except Exception as exc:  # noqa: BLE001
            records = []
            error = f"{type(exc).__name__}: {exc}"
        probes.append(
            {
                "query": query,
                "error": error,
                "records": [_summarize_global_record(record) for record in records],
            }
        )
    return probes


def _probe_known_pids(
    known_pids: List[str],
    target_queries: List[str],
    *,
    max_known_pids: int,
) -> List[Dict[str, Any]]:
    probes: List[Dict[str, Any]] = []
    for pid in known_pids[:max_known_pids]:
        pid_probe = {"pid": pid, "queries": []}
        for query in target_queries:
            try:
                title, hits = search_ndl_fulltext_in_item(pid, query, size=10)
                error = ""
            except Exception as exc:  # noqa: BLE001
                title = ""
                hits = []
                error = f"{type(exc).__name__}: {exc}"
            pid_probe["queries"].append(
                {
                    "query": query,
                    "title": title,
                    "error": error,
                    "hit_count": len(hits),
                    "first_hit": hits[0].to_dict() if hits else None,
                }
            )
        probes.append(pid_probe)
    return probes


def _build_diary_date_lookup_diagnostic(
    *,
    source_type: str,
    known_pids: List[str],
    target_queries: List[str],
    pid_probes: List[Dict[str, Any]],
    footnote: Any,
) -> Dict[str, Any]:
    if source_type != "diary" or not pid_probes:
        return {}

    def is_date_query(value: str) -> bool:
        return bool(
            re.search(r"(?:1[89]\d{2}|20\d{2})年", value)
            or re.search(r"(?:明治|大正|昭和|平成|令和)[0-9一二三四五六七八九十百元]+年", value)
        )

    date_queries = [query for query in target_queries if is_date_query(query)]
    title_queries = [query for query in target_queries if not is_date_query(query)]
    date_hit_count = 0
    title_hit_count = 0
    first_pid = str(pid_probes[0].get("pid") or "")
    for pid_probe in pid_probes:
        for query_probe in pid_probe.get("queries") or []:
            query = str(query_probe.get("query") or "")
            hit_count = int(query_probe.get("hit_count") or 0)
            if query in date_queries:
                date_hit_count += hit_count
            if query in title_queries:
                title_hit_count += hit_count
    if date_hit_count > 0 or title_hit_count <= 0:
        return {}
    page_numbers: List[int] = []
    for page in getattr(footnote, "page_numbers", []) or []:
        try:
            page_number = int(page)
        except (TypeError, ValueError):
            continue
        if page_number > 0:
            page_numbers.append(page_number)
    small_page_window: Dict[str, Any] = {}
    if page_numbers:
        small_page_window = {
            "cited_book_pages": page_numbers,
            "start_page": max(1, min(page_numbers) - 2),
            "end_page": max(page_numbers) + 2,
            "page_window": 2,
        }
    return {
        "source_type": "diary",
        "ndl_id": first_pid,
        "known_pid_candidates": known_pids,
        "date_queries": date_queries,
        "date_hit_count": date_hit_count,
        "title_queries": title_queries,
        "title_hit_count": title_hit_count,
        "recommended_action": "toc_index_then_small_page_window_ocr",
        "small_page_window": small_page_window,
        "evidence_level": "diagnostic_until_ocr_llm_review",
    }


def _build_contained_document_lookup_diagnostic(
    *,
    source_type: str,
    known_pids: List[str],
    target_queries: List[str],
    pid_probes: List[Dict[str, Any]],
    footnote: Any,
) -> Dict[str, Any]:
    if source_type != "contained_document" or not pid_probes:
        return {}
    title_hit_count = 0
    for pid_probe in pid_probes:
        for query_probe in pid_probe.get("queries") or []:
            if str(query_probe.get("query") or "") in target_queries:
                title_hit_count += int(query_probe.get("hit_count") or 0)
    contained_title = str(getattr(footnote, "contained_title", "") or getattr(footnote, "title", "") or "").strip()
    host_title = str(getattr(footnote, "host_title", "") or "").strip()
    if not known_pids and title_hit_count <= 0:
        return {}
    return {
        "source_type": "contained_document",
        "ndl_id": str(pid_probes[0].get("pid") or ""),
        "known_pid_candidates": known_pids,
        "host_title": host_title,
        "host_missing": not bool(host_title),
        "contained_title": contained_title,
        "title_queries": target_queries,
        "title_hit_count": title_hit_count,
        "recommended_action": "known_document_pid_first_then_host_fallback",
        "evidence_level": "diagnostic_until_ocr_llm_review",
    }


def probe_case(
    case: Dict[str, str],
    *,
    max_results: int,
    max_queries: int,
    max_known_pids: int,
) -> Dict[str, Any]:
    verifier = HistoricalCitationVerifier()
    footnote = parse_footnote_text(case["case_id"], case["footnote"])
    candidate = CitationCandidate(
        candidate_id=case["case_id"],
        paragraph_index=1,
        paragraph_text=case["claim"],
        translation_text=case["claim"],
        footnote_id=footnote.id,
        footnote=footnote,
    )
    attach_source_graph_artifacts(candidate)
    resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
    source_query_plan = build_source_query_plan(footnote, claim_text=case["claim"])
    candidate.artifacts["source_query_plan"] = source_query_plan.to_dict()

    global_queries: List[str] = []
    _append_unique(global_queries, resolver_plan.get("global_queries") or [])
    _append_unique(global_queries, source_query_plan.global_fulltext_queries(max_queries=max_queries))
    global_queries = global_queries[:max_queries]
    global_probes = _probe_global_queries(global_queries, max_results=max_results)
    for probe in global_probes:
        for record in probe.get("records") or []:
            if record.get("ndl_id") or record.get("url"):
                candidate.ndl_matches.append(_match_from_record(record))

    known_pids = [str(pid) for pid in (resolver_plan.get("known_pid_candidates") or []) if str(pid or "")]
    target_queries: List[str] = []
    _append_unique(target_queries, resolver_plan.get("target_pid_queries") or [])
    target_queries = target_queries[:max_queries]
    pid_probes = _probe_known_pids(
        known_pids,
        target_queries,
        max_known_pids=max_known_pids,
    )
    diary_date_lookup_diagnostic = _build_diary_date_lookup_diagnostic(
        source_type=str(resolver_plan.get("source_type") or ""),
        known_pids=known_pids,
        target_queries=target_queries,
        pid_probes=pid_probes,
        footnote=footnote,
    )
    contained_document_lookup_diagnostic = _build_contained_document_lookup_diagnostic(
        source_type=str(resolver_plan.get("source_type") or ""),
        known_pids=known_pids,
        target_queries=target_queries,
        pid_probes=pid_probes,
        footnote=footnote,
    )
    adapter_candidate_probe = _probe_adapter_candidates(
        footnote,
        max_results=max_results,
        claim_text=case["claim"],
    )
    equivalent_group = record_equivalent_pid_group(candidate)

    return {
        "case_id": case["case_id"],
        "label": case["label"],
        "footnote": footnote.to_dict(),
        "claim": case["claim"],
        "resolver": resolver_plan.get("resolver"),
        "source_type": resolver_plan.get("source_type"),
        "source_level_cache_key": resolver_plan.get("source_level_cache_key"),
        "known_pid_candidates": known_pids,
        "target_pid_queries": target_queries,
        "global_queries": global_queries,
        "adapter_candidate_probe": adapter_candidate_probe,
        "global_probes": global_probes,
        "pid_probes": pid_probes,
        "diary_date_lookup_diagnostic": diary_date_lookup_diagnostic,
        "contained_document_lookup_diagnostic": contained_document_lookup_diagnostic,
        "equivalent_pid_group": equivalent_group,
        "fulltext_lead_pid_group": candidate.artifacts.get("fulltext_lead_pid_group") or [],
        "fulltext_lead_manual_hint": _format_fulltext_lead_manual_hint(candidate.artifacts) or "",
        "notes": candidate.notes,
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# Historical Citation Source-Type Probe",
        "",
        f"- Created at: {payload.get('created_at')}",
        f"- Cases: {len(payload.get('cases') or [])}",
        "",
    ]
    for case in payload.get("cases") or []:
        manual_hint = str(case.get("fulltext_lead_manual_hint") or "").strip()
        if manual_hint.startswith("- "):
            manual_hint = manual_hint[2:].strip()
        diary_diagnostic = _format_diary_date_lookup_diagnostic(
            {"diary_date_lookup_diagnostic": case.get("diary_date_lookup_diagnostic") or {}}
        )
        if diary_diagnostic and diary_diagnostic.startswith("- "):
            diary_diagnostic = diary_diagnostic[2:].strip()
        if diary_diagnostic and diary_diagnostic.startswith("Diary date lookup diagnostic:"):
            diary_diagnostic = diary_diagnostic.split(":", 1)[1].strip()
        contained_diagnostic = _format_contained_document_lookup_diagnostic(
            {"contained_document_lookup_diagnostic": case.get("contained_document_lookup_diagnostic") or {}}
        )
        if contained_diagnostic and contained_diagnostic.startswith("- "):
            contained_diagnostic = contained_diagnostic[2:].strip()
        if contained_diagnostic and contained_diagnostic.startswith("Contained document lookup diagnostic:"):
            contained_diagnostic = contained_diagnostic.split(":", 1)[1].strip()
        lines.extend(
            [
                f"## {case['label']}",
                "",
                f"- Resolver: `{case.get('resolver')}` / `{case.get('source_type')}`",
                f"- Source cache key: `{case.get('source_level_cache_key')}`",
                f"- Known PID candidates: {', '.join(case.get('known_pid_candidates') or []) or 'n/a'}",
                f"- Strict equivalent PID group: {', '.join(str(item.get('ndl_id')) for item in case.get('equivalent_pid_group') or []) or 'n/a'}",
                f"- Fulltext lead PID group (not equivalent): {', '.join(str(item.get('ndl_id')) for item in case.get('fulltext_lead_pid_group') or []) or 'n/a'}",
                f"- Fulltext lead manual hint: {manual_hint or 'n/a'}",
                f"- Diary date lookup diagnostic: {diary_diagnostic or 'n/a'}",
                f"- Contained document lookup diagnostic: {contained_diagnostic or 'n/a'}",
                "",
                "### Adapter Candidate Order",
                "",
            ]
        )
        adapter_probe = case.get("adapter_candidate_probe") or {}
        if adapter_probe.get("error"):
            lines.append(f"- Error: `{adapter_probe.get('error')}`")
        for index, match in enumerate(adapter_probe.get("matches") or [], start=1):
            marker = "known" if match.get("known_pid_candidate") else "searched"
            lines.append(
                f"- {index}. PID `{match.get('ndl_id')}` ({marker})"
                f" route=`{match.get('search_route')}` title={match.get('title')}"
            )
        lines.extend(
            [
                "",
                "### Global Queries",
                "",
            ]
        )
        for probe in case.get("global_probes") or []:
            records = probe.get("records") or []
            first = records[0] if records else {}
            lines.append(
                f"- `{probe.get('query')}` -> {len(records)} records"
                + (f" | first PID={first.get('ndl_id')} title={first.get('title')}" if first else "")
            )
        lines.extend(["", "### Target PID Snippets", ""])
        for pid_probe in case.get("pid_probes") or []:
            lines.append(f"- PID `{pid_probe.get('pid')}`")
            for query_probe in pid_probe.get("queries") or []:
                first_hit = query_probe.get("first_hit") or {}
                snippet = str(first_hit.get("snippet") or "")[:120]
                lines.append(
                    f"  - `{query_probe.get('query')}` -> {query_probe.get('hit_count')} hits"
                    + (f" | page={first_hit.get('pdf_page')} | {snippet}" if first_hit else "")
                )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "cases": [
            probe_case(
                case,
                max_results=args.max_results,
                max_queries=args.max_queries,
                max_known_pids=args.max_known_pids,
            )
            for case in _cases()
        ],
    }
    json_path = output_dir / "source_type_probe_results.json"
    md_path = output_dir / "source_type_probe_report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path.resolve()), "report": str(md_path.resolve())}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
