from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.historical_citation.models import CitationCandidate, NDLSearchMatch, ParsedFootnote
from modules.historical_citation.footnote_parser import extract_volume_terms, parse_footnote_text
from modules.historical_citation.ndl_search import search_ndl_digital_fulltext
from modules.historical_citation.page_span import split_citation_claims_for_pages
from modules.historical_citation.progress import ProgressReporter, build_progress_event
from modules.historical_citation.reporting import build_artifact_summary, render_resume_markdown_report
from modules.historical_citation.source_acquisition import is_likely_digital_ndl_pid
from modules.historical_citation.source_graph import (
    attach_source_graph_artifacts,
    build_manual_search_recipe,
    build_source_query_plan,
    candidate_source_claim_context,
    dedupe_result_dicts,
)
from modules.historical_citation_verifier import HistoricalCitationVerifier


SIMPLIFIED_SOURCE_HINTS = set(
    "论战对协调整临时笔记资长编摘译术历书动变间关华报"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the next-stage refinement for PDF historical citation verification reports."
    )
    parser.add_argument("pdf_path", help="Input Chinese paper PDF")
    parser.add_argument("--combined-json", required=True, help="Merged verification_results.combined.json")
    parser.add_argument("--output-dir", required=True, help="Output directory for refinement artifacts")
    parser.add_argument("--label", default="PDF 论文", help="Privacy-safe report label")
    parser.add_argument("--max-search-results", type=int, default=3)
    parser.add_argument("--page-window", type=int, default=4)
    parser.add_argument("--ocr-model", default="ndlocr_lite")
    parser.add_argument("--restricted-download", action="store_true")
    parser.add_argument("--download-max-attempts", type=int, default=1)
    parser.add_argument("--max-downloads", type=int, default=None, help="Limit source_found dl.ndl download attempts")
    parser.add_argument("--max-mismatch", type=int, default=None, help="Limit source_mismatch re-search attempts")
    parser.add_argument(
        "--candidate-id",
        action="append",
        default=[],
        help="Restrict next-stage processing to one or more candidate_id values. May be repeated or comma-separated.",
    )
    parser.add_argument(
        "--footnote-id",
        action="append",
        default=[],
        help="Restrict next-stage processing to one or more footnote_id values. May be repeated or comma-separated.",
    )
    parser.add_argument("--download-start-index", type=int, default=0, help="Zero-based start within the selected download list")
    parser.add_argument("--mismatch-start-index", type=int, default=0, help="Zero-based start within the selected mismatch list")
    parser.add_argument("--recheck-download-start-index", type=int, default=0, help="Zero-based start within rechecked downloadable items")
    parser.add_argument("--max-recheck-downloads", type=int, default=None, help="Limit downloads discovered by source recheck")
    parser.add_argument(
        "--retry-download-timeouts",
        action="store_true",
        help="Retry prior download_timeout entries instead of treating them as completed during resume.",
    )
    parser.add_argument("--skip-downloads", action="store_true")
    parser.add_argument("--skip-mismatch-recheck", action="store_true")
    parser.add_argument("--skip-recheck-downloads", action="store_true")
    parser.add_argument("--no-resume", action="store_true", help="Ignore an existing next_stage_refinement.json")
    parser.add_argument(
        "--download-timeout-seconds",
        type=int,
        default=600,
        help="Per-candidate timeout for download/OCR/alignment. Use 0 to run inline without timeout.",
    )
    parser.add_argument(
        "--slow-event-threshold-seconds",
        type=int,
        default=240,
        help="Record candidate processing events at or above this duration. Use 0 to disable.",
    )
    parser.add_argument(
        "--download-cache-dir",
        default="",
        help="Optional shared directory for NDL page-window PDFs, page mapping, and OCR cache.",
    )
    parser.add_argument(
        "--platform-names",
        nargs="+",
        default=None,
        help="Limit source recheck platforms, for example: --platform-names ndl",
    )
    parser.add_argument(
        "--reparse-pdf",
        action="store_true",
        help="Reparse the input PDF instead of reusing candidates stored in combined-json.",
    )
    parser.add_argument(
        "--no-force-ndl-fulltext",
        action="store_true",
        help="Do not force NDL fulltext probing during PDF source recheck.",
    )
    parser.add_argument("--no-ndl-browser-fallback", action="store_true")
    parser.add_argument(
        "--prefer-ollama-review",
        action="store_true",
        default=True,
        help="Use the local Ollama review client for the final LLM citation-support check.",
    )
    parser.add_argument(
        "--no-ollama-review",
        dest="prefer_ollama_review",
        action="store_false",
        help="Use the configured non-Ollama review client instead of the formal local Gemma workflow.",
    )
    parser.add_argument(
        "--review-model",
        default="gemma4:e4b",
        help="Ollama model name for final LLM review. Formal workflow default: gemma4:e4b.",
    )
    parser.add_argument(
        "--review-timeout-seconds",
        type=int,
        default=300,
        help="HTTP timeout for each final LLM review request.",
    )
    return parser


def load_json(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def match_from_dict(payload: Dict[str, Any]) -> NDLSearchMatch:
    return NDLSearchMatch(
        title=payload.get("title") or "",
        url=payload.get("url") or "",
        ndl_id=payload.get("ndl_id"),
        platform=payload.get("platform") or "ndl",
        platform_item_id=payload.get("platform_item_id"),
        author=payload.get("author"),
        date=payload.get("date"),
        publisher=payload.get("publisher"),
        pdf_url=payload.get("pdf_url"),
        score=float(payload.get("score") or 0),
        metadata=dict(payload.get("metadata") or {}),
    )


def footnote_from_dict(payload: Dict[str, Any]) -> ParsedFootnote:
    footnote = ParsedFootnote(
        id=str(payload.get("id") or ""),
        text=str(payload.get("text") or ""),
        title=str(payload.get("title") or ""),
        author=str(payload.get("author") or ""),
        publisher=str(payload.get("publisher") or ""),
        publication_place=str(payload.get("publication_place") or ""),
        year=str(payload.get("year") or ""),
        page_label=str(payload.get("page_label") or ""),
        page_numbers=[int(page) for page in (payload.get("page_numbers") or []) if str(page).isdigit()],
        page_span_type=str(payload.get("page_span_type") or ""),
        page_span_source=str(payload.get("page_span_source") or ""),
        source_type=str(payload.get("source_type") or "book"),
        ndl_keyword=str(payload.get("ndl_keyword") or ""),
        host_title=str(payload.get("host_title") or ""),
        contained_title=str(payload.get("contained_title") or ""),
        source_relation=str(payload.get("source_relation") or ""),
        notes=[str(note) for note in (payload.get("notes") or [])],
    )
    return refresh_footnote_structure(footnote)


def _merge_unique_notes(left: Sequence[str], right: Sequence[str]) -> List[str]:
    notes: List[str] = []
    for note in [*left, *right]:
        if note and note not in notes:
            notes.append(str(note))
    return notes


def _fill_publication_hints_from_text(footnote: ParsedFootnote) -> None:
    normalized = unicodedata.normalize("NFKC", footnote.text or "")
    if not footnote.year:
        year_match = re.search(r"((?:18|19|20)\d{2})\s*年", normalized)
        if year_match:
            footnote.year = year_match.group(1)
    if not footnote.publisher:
        publisher_match = re.search(
            r"[，,、]\s*([^，,。；;《》]{1,24}?)\s*((?:18|19|20)\d{2})\s*年",
            normalized,
        )
        if publisher_match:
            publisher = publisher_match.group(1).strip()
            publisher = re.sub(r"^(?:東京|东京|京都|大阪|Kyoto|Tokyo)\s*[:：]\s*", "", publisher)
            publisher = re.sub(r"(?:18|19|20)\d{2}\s*年版?$", "", publisher).strip()
            if publisher and len(publisher) <= 16:
                footnote.publisher = publisher
    if footnote.publisher:
        publisher = unicodedata.normalize("NFKC", str(footnote.publisher or "")).strip()
        publisher = re.sub(r"^(?:東京|东京|京都|大阪|Kyoto|Tokyo)\s*[:：]\s*", "", publisher)
        publisher = re.sub(r"(?:18|19|20)\d{2}\s*年版?$", "", publisher).strip()
        if "《" in publisher or "》" in publisher or len(publisher) > 16:
            publisher = ""
        footnote.publisher = publisher


def _should_replace_reparsed_ndl_keyword(footnote: ParsedFootnote, reparsed: ParsedFootnote) -> bool:
    if not reparsed.ndl_keyword:
        return False
    if not footnote.ndl_keyword:
        return True
    if reparsed.ndl_keyword == footnote.ndl_keyword:
        return False
    if reparsed.host_title or reparsed.contained_title or reparsed.source_relation:
        return True
    if any(str(note).startswith("volume_hint:") for note in reparsed.notes):
        return True
    old_keyword = unicodedata.normalize("NFKC", footnote.ndl_keyword or "")
    new_keyword = unicodedata.normalize("NFKC", reparsed.ndl_keyword or "")
    stale_fascicle_volume = re.search(r"第\s*([0-9一二三四五六七八九十百]+)\s*[册冊].{0,12}第\s*\1\s*[巻卷]", old_keyword)
    stale_meiji_from_fascicle = "明治1年" in old_keyword or "明治元年" in old_keyword
    return bool((stale_fascicle_volume or stale_meiji_from_fascicle) and new_keyword not in old_keyword)


RUNNING_HEADER_PATTERNS = (
    re.compile(
        r"^\s*宗教世界\s*文化\s*\d{4}\s*年第\s*[0-9一二三四五六七八九十]+\s*期\s*THE\s+WORLD\s+RELIGIOUS\s+CULTURES\s*",
        re.IGNORECASE,
    ),
    re.compile(r"^\s*THE\s+WORLD\s+RELIGIOUS\s+CULTURES\s*", re.IGNORECASE),
)


def _clean_claim_spacing(text: Any) -> str:
    cleaned = str(text or "").replace("\u3000", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def strip_pdf_running_header_from_claim(text: Any) -> Tuple[str, bool]:
    cleaned = _clean_claim_spacing(text)
    changed = False
    while cleaned:
        before = cleaned
        for pattern in RUNNING_HEADER_PATTERNS:
            cleaned = pattern.sub("", cleaned).strip()
        if cleaned == before:
            break
        changed = True
    return cleaned, changed


def _first_following_claim_sentence(text: Any, *, limit: int = 180) -> str:
    cleaned = _clean_claim_spacing(text)
    if not cleaned:
        return ""
    match = re.search(r".{18,}?[。！？]", cleaned)
    if match:
        return match.group(0)[:limit].strip()
    return cleaned[:limit].strip()


def repair_pdf_running_header_claim(candidate: CitationCandidate) -> None:
    citation_unit = candidate.artifacts.get("citation_unit") or {}
    if not isinstance(citation_unit, dict):
        return
    original_unit_text = str(citation_unit.get("text") or "")
    cleaned_unit_text, header_removed = strip_pdf_running_header_from_claim(original_unit_text)
    cleaned_translation, translation_header_removed = strip_pdf_running_header_from_claim(candidate.translation_text)
    if not (header_removed or translation_header_removed):
        return

    repaired = cleaned_unit_text or cleaned_translation
    following = _first_following_claim_sentence(citation_unit.get("following_unfootnoted_context"))
    orphaned_quote_tail = bool(repaired) and len(repaired) < 42 and bool(following)
    if orphaned_quote_tail:
        repaired = _clean_claim_spacing(f"{repaired}{following}")
        citation_unit["unit_type"] = "running_header_orphaned_quote_expanded"
        citation_unit["confidence"] = min(float(citation_unit.get("confidence") or 0.72), 0.72)
        citation_unit["reason"] = (
            f"{citation_unit.get('reason') or 'nearest citation unit'}; "
            "PDF running header stripped and following sentence appended"
        )
        if "pdf_next_stage_orphaned_quote_claim_expanded" not in candidate.notes:
            candidate.notes.append("pdf_next_stage_orphaned_quote_claim_expanded")

    if repaired:
        candidate.translation_text = repaired
        citation_unit["text"] = repaired
        citation_unit["claim_candidates"] = split_citation_claims_for_pages(repaired)
        candidate.artifacts["citation_unit"] = citation_unit
        if "pdf_next_stage_running_header_claim_cleaned" not in candidate.notes:
            candidate.notes.append("pdf_next_stage_running_header_claim_cleaned")


def refresh_footnote_structure(footnote: ParsedFootnote) -> ParsedFootnote:
    """Re-derive parser-sensitive metadata from the original footnote text.

    Old PDF combined reports may predate newer parser rules. Reusing their
    stale `host_title`, `contained_title`, or `ndl_keyword` silently pushes the
    next-stage workflow toward wrong NDL PIDs, so the refinement entry point
    refreshes those fields without discarding stable IDs or prior title aliases.
    """

    if not footnote.text:
        return footnote
    try:
        reparsed = parse_footnote_text(footnote.id, footnote.text)
    except Exception:
        return footnote
    if reparsed.title and (
        not footnote.title
        or reparsed.host_title
        or any(note.startswith("volume_hint:") for note in reparsed.notes)
    ):
        footnote.title = reparsed.title
    for field in (
        "host_title",
        "contained_title",
        "source_relation",
        "page_label",
        "page_span_type",
        "page_span_source",
        "source_type",
        "year",
    ):
        value = getattr(reparsed, field, "")
        if value:
            setattr(footnote, field, value)
    if reparsed.page_numbers:
        footnote.page_numbers = list(reparsed.page_numbers)
    if _should_replace_reparsed_ndl_keyword(footnote, reparsed):
        footnote.ndl_keyword = reparsed.ndl_keyword
        if "pdf_next_stage_ndl_keyword_refreshed" not in footnote.notes:
            footnote.notes.append("pdf_next_stage_ndl_keyword_refreshed")
    _fill_publication_hints_from_text(footnote)
    footnote.notes = _merge_unique_notes(footnote.notes, reparsed.notes)
    if "pdf_next_stage_footnote_restructured" not in footnote.notes:
        footnote.notes.append("pdf_next_stage_footnote_restructured")
    return footnote


def candidate_from_dict(payload: Dict[str, Any]) -> CitationCandidate:
    candidate = CitationCandidate(
        candidate_id=str(payload.get("candidate_id") or ""),
        paragraph_index=int(payload.get("paragraph_index") or 0),
        paragraph_text=str(payload.get("paragraph_text") or ""),
        translation_text=str(payload.get("translation_text") or ""),
        footnote_id=str(payload.get("footnote_id") or ""),
        footnote=footnote_from_dict(payload.get("footnote") or {}),
        ndl_matches=[match_from_dict(match) for match in (payload.get("ndl_matches") or [])],
        verification_status=str(payload.get("verification_status") or "parsed"),
        matched_japanese=str(payload.get("matched_japanese") or ""),
        matched_page=payload.get("matched_page"),
        confidence=payload.get("confidence"),
        support_status=str(payload.get("support_status") or "unassessed"),
        support_reason=str(payload.get("support_reason") or ""),
        evidence_scope=str(payload.get("evidence_scope") or ""),
        notes=[str(note) for note in (payload.get("notes") or [])],
        artifacts=dict(payload.get("artifacts") or {}),
    )
    repair_pdf_running_header_claim(candidate)
    attach_source_graph_artifacts(candidate)
    return candidate


def result_offset(item: Dict[str, Any]) -> Optional[int]:
    artifacts = item.get("artifacts") or {}
    try:
        return int(artifacts.get("refinement_offset"))
    except (TypeError, ValueError):
        return None


def result_offsets(items: Sequence[Dict[str, Any]]) -> set[int]:
    return {offset for item in items if (offset := result_offset(item)) is not None}


def is_rechecked_download_result(item: Dict[str, Any]) -> bool:
    notes = item.get("notes") or []
    return any(str(note) == "download_after_source_recheck" for note in notes)


def split_rechecked_download_results(
    download_results: Sequence[Dict[str, Any]],
    rechecked_download_results: Sequence[Dict[str, Any]] | None = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    normal: List[Dict[str, Any]] = []
    rechecked: List[Dict[str, Any]] = []
    for item in download_results:
        if is_rechecked_download_result(item):
            rechecked.append(item)
        else:
            normal.append(item)
    rechecked.extend(rechecked_download_results or [])
    return dedupe_by_offset(normal), dedupe_by_offset(rechecked)


def completed_download_offset_set(
    items: Sequence[Dict[str, Any]],
    *,
    retry_timeouts: bool,
) -> set[int]:
    completed: set[int] = set()
    for item in items:
        offset = result_offset(item)
        if offset is None:
            continue
        if retry_timeouts and item.get("verification_status") == "download_timeout":
            continue
        completed.add(offset)
    return completed


def timeout_event_key(event: Dict[str, Any]) -> Tuple[str, str]:
    return str(event.get("global_current") or ""), str(event.get("candidate_id") or "")


def result_timeout_key(item: Dict[str, Any]) -> Tuple[str, str]:
    offset = result_offset(item)
    global_current = str(offset + 1) if offset is not None else ""
    return global_current, str(item.get("candidate_id") or "")


def parse_progress_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def progress_candidate_key(event: Dict[str, Any]) -> Tuple[str, str, str]:
    return (
        str(event.get("phase") or ""),
        str(event.get("global_current") or ""),
        str(event.get("candidate_id") or ""),
    )


SLOW_EVENT_WRAPPER_SUBPHASES = {
    "volume_series_fulltext_review",
}


def _is_slow_event_wrapper_subphase(value: Any) -> bool:
    return str(value or "") in SLOW_EVENT_WRAPPER_SUBPHASES


def build_slow_events_from_progress(
    progress_path: Path,
    *,
    threshold_seconds: int = 240,
) -> List[Dict[str, Any]]:
    if threshold_seconds <= 0 or not progress_path.exists():
        return []
    active: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    active_subphases: Dict[Tuple[Tuple[str, str, str], str], Dict[str, Any]] = {}
    subphase_durations: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    last_subphase_event: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    slow_events: List[Dict[str, Any]] = []
    for line in progress_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        event_name = str(event.get("event") or "")
        key = progress_candidate_key(event)
        subphase = str(event.get("subphase") or "")
        if subphase and event_name.startswith("worker_stage_"):
            last_subphase_event[key] = event
        if event_name == "worker_stage_started" and subphase:
            active_subphases[(key, subphase)] = event
            continue
        if event_name in {"worker_stage_completed", "worker_stage_failed"} and subphase:
            started_subphase = active_subphases.pop((key, subphase), None)
            if not started_subphase:
                continue
            started_at = parse_progress_timestamp(started_subphase.get("timestamp")) if started_subphase else None
            completed_at = parse_progress_timestamp(event.get("timestamp"))
            elapsed_subphase = (
                round((completed_at - started_at).total_seconds(), 3)
                if started_at and completed_at
                else None
            )
            subphase_durations.setdefault(key, []).append(
                {
                    "subphase": subphase,
                    "status": event.get("status"),
                    "event": event_name,
                    "elapsed_seconds": elapsed_subphase,
                    "started_at": started_subphase.get("timestamp") if started_subphase else None,
                    "completed_at": event.get("timestamp"),
                    "metrics": event.get("metrics") or {},
                }
            )
            continue
        if event_name == "candidate_started":
            active[key] = event
            continue
        if event_name != "candidate_completed":
            continue
        started = active.pop(key, None)
        if not started:
            continue
        started_at = parse_progress_timestamp(started.get("timestamp"))
        completed_at = parse_progress_timestamp(event.get("timestamp"))
        if not started_at or not completed_at:
            continue
        elapsed_seconds = (completed_at - started_at).total_seconds()
        if elapsed_seconds < threshold_seconds:
            continue
        subphases = subphase_durations.get(key) or []
        leaf_subphases = [
            item
            for item in subphases
            if not _is_slow_event_wrapper_subphase(item.get("subphase"))
        ]
        subphases_for_summary = leaf_subphases or subphases
        longest_subphase = next(
            (
                item
                for item in sorted(
                    subphases_for_summary,
                    key=lambda value: float(value.get("elapsed_seconds") or -1),
                    reverse=True,
                )
                if item.get("elapsed_seconds") is not None
            ),
            None,
        )
        latest_subphase = next((item for item in reversed(subphases_for_summary) if item.get("subphase")), None)
        if latest_subphase is None:
            latest_subphase = last_subphase_event.get(key) or {}
        fallback_subphase = None
        if not latest_subphase or not latest_subphase.get("subphase"):
            phase_name = str(event.get("phase") or started.get("phase") or "candidate")
            fallback_subphase = {
                "subphase": f"{phase_name}_total",
                "status": event.get("status"),
                "event": "candidate_completed",
                "elapsed_seconds": round(elapsed_seconds, 3),
                "started_at": started.get("timestamp"),
                "completed_at": event.get("timestamp"),
                "metrics": event.get("metrics") or {},
            }
            latest_subphase = fallback_subphase
        if longest_subphase is None and fallback_subphase is not None:
            longest_subphase = fallback_subphase
        slow_events.append(
            {
                "phase": event.get("phase") or started.get("phase"),
                "candidate_id": event.get("candidate_id") or started.get("candidate_id"),
                "footnote_id": event.get("footnote_id") or started.get("footnote_id"),
                "global_current": event.get("global_current") or started.get("global_current"),
                "global_total": event.get("global_total") or started.get("global_total"),
                "status": event.get("status"),
                "elapsed_seconds": round(elapsed_seconds, 3),
                "started_at": started.get("timestamp"),
                "completed_at": event.get("timestamp"),
                "metrics": event.get("metrics") or {},
                "last_subphase": latest_subphase.get("subphase"),
                "last_subphase_status": latest_subphase.get("status"),
                "longest_subphase": longest_subphase.get("subphase") if longest_subphase else None,
                "longest_subphase_seconds": longest_subphase.get("elapsed_seconds") if longest_subphase else None,
                "subphase_durations": subphases,
            }
        )
    slow_events.sort(key=lambda item: float(item.get("elapsed_seconds") or 0), reverse=True)
    return slow_events


def build_execution_run(args: argparse.Namespace, *, started_at: str) -> Dict[str, Any]:
    return {
        "started_at": started_at,
        "mode": "retry_or_resume" if args.retry_download_timeouts else "initial_or_resume",
        "restricted_download": args.restricted_download,
        "download_timeout_seconds": args.download_timeout_seconds,
        "retry_download_timeouts": args.retry_download_timeouts,
        "resume": not args.no_resume,
        "max_search_results": args.max_search_results,
        "page_window": args.page_window,
        "ocr_model": args.ocr_model,
        "review_model": args.review_model or os.environ.get("HISTORICAL_CITATION_REVIEW_MODEL", ""),
        "review_timeout_seconds": args.review_timeout_seconds,
        "force_ndl_fulltext": not args.no_force_ndl_fulltext,
        "slow_event_threshold_seconds": args.slow_event_threshold_seconds,
        "candidate_ids": normalize_selector_values(getattr(args, "candidate_id", []) or []),
        "footnote_ids": normalize_selector_values(getattr(args, "footnote_id", []) or []),
    }


def clear_resolved_timeout_events(
    timeout_events: Sequence[Dict[str, Any]],
    result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if result.get("verification_status") == "download_timeout":
        return list(timeout_events)
    resolved_key = result_timeout_key(result)
    return [event for event in timeout_events if timeout_event_key(event) != resolved_key]


def append_timeout_event(
    timeout_events: Sequence[Dict[str, Any]],
    timeout_event: Dict[str, Any],
) -> List[Dict[str, Any]]:
    key = timeout_event_key(timeout_event)
    return [event for event in timeout_events if timeout_event_key(event) != key] + [timeout_event]


def has_downloadable_ndl_pid(item: Dict[str, Any]) -> bool:
    for match in item.get("ndl_matches") or []:
        if (match.get("metadata") or {}).get("source_mismatch"):
            continue
        url = str(match.get("url") or "")
        ndl_id = match.get("ndl_id")
        if "dl.ndl.go.jp" in url or is_likely_digital_ndl_pid(ndl_id):
            return True
    return False


def has_kana(text: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff]", text or ""))


def has_japanese_source_markers(text: str) -> bool:
    return bool(re.search(r"[「『]|(?:紀要|学会|學會|頁|号|號|東京|編)", text or ""))


def has_parenthetical_original(text: str) -> bool:
    return bool(re.search(r"[（(][^）)]{0,120}[：:]\s*[「『《].+?[」』》]", text or ""))


def looks_like_non_ndl_direct_source(item: Dict[str, Any]) -> Dict[str, Any]:
    footnote = item.get("footnote") or {}
    title = str(footnote.get("title") or "")
    text = str(footnote.get("text") or "")
    source_type = str(footnote.get("source_type") or "")
    reasons: List[str] = []
    if source_type == "article" and not has_kana(title + text) and not has_japanese_source_markers(title + text):
        reasons.append("中文或非日文期刊论文来源")
    if "《" in text and "》" in text and re.search(r"\d{4}年?第?\d+期", text):
        reasons.append("期刊卷期型引用，通常不进入 NDL 史料下载/OCR 流")
    if any(char in SIMPLIFIED_SOURCE_HINTS for char in title) and not has_parenthetical_original(text):
        reasons.append("题名含简体中文线索且未给出日文原题")
    if "译" in text or "译校" in text:
        reasons.append("译本/摘译本，需另行确认原始日文底本")
    return {
        "candidate_id": item.get("candidate_id"),
        "footnote_id": item.get("footnote_id"),
        "title": title,
        "page_numbers": footnote.get("page_numbers") or [],
        "source_type": source_type,
        "reasons": reasons,
    }


def classify_non_ndl_direct_sources(results: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for item in results:
        classified = looks_like_non_ndl_direct_source(item)
        if classified["reasons"]:
            items.append(classified)
    return items


def audit_title_aliases(results: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    audits: List[Dict[str, Any]] = []
    previous: List[Dict[str, Any]] = []
    for offset, item in enumerate(results):
        footnote = item.get("footnote") or {}
        notes = [str(note) for note in footnote.get("notes") or []]
        for note in notes:
            if not note.startswith("title_alias_resolved:") or "->" not in note:
                continue
            old_title, new_title = note.split(":", 1)[1].split("->", 1)
            support = "not_found"
            support_candidate = ""
            for prev in reversed(previous):
                prev_footnote = prev.get("footnote") or {}
                prev_text = str(prev_footnote.get("text") or "")
                prev_title = str(prev_footnote.get("title") or "")
                if old_title in prev_text and new_title in prev_text:
                    support = "defined_in_previous_footnote"
                    support_candidate = str(prev.get("candidate_id") or "")
                    break
                if prev_title == new_title and old_title in prev_text:
                    support = "previous_title_with_original_text"
                    support_candidate = str(prev.get("candidate_id") or "")
                    break
            audits.append(
                {
                    "offset": offset,
                    "candidate_id": item.get("candidate_id"),
                    "footnote_id": item.get("footnote_id"),
                    "old_title": old_title,
                    "resolved_title": new_title,
                    "support": support,
                    "support_candidate_id": support_candidate,
                    "needs_manual_review": support == "not_found",
                }
            )
        previous.append(item)
    return audits


def select_items(
    results: Sequence[Dict[str, Any]],
    *,
    status: Optional[str] = None,
    downloadable: Optional[bool] = None,
) -> List[tuple[int, Dict[str, Any]]]:
    selected: List[tuple[int, Dict[str, Any]]] = []
    for offset, item in enumerate(results):
        if status is not None and item.get("verification_status") != status:
            continue
        if downloadable is not None and has_downloadable_ndl_pid(item) != downloadable:
            continue
        selected.append((offset, item))
    return selected


def select_recheck_items(results: Sequence[Dict[str, Any]]) -> List[tuple[int, Dict[str, Any]]]:
    """PDF refinement rechecks both metadata mismatches and no-hit cases.

    The Word resume workflow already reaches download/OCR terminal states. PDF
    fast scans can intentionally stop at source_not_found/source_mismatch, so
    next-stage refinement must send both states through fulltext/multiplatform
    probing before deciding that no source evidence is available.
    """

    return [
        (offset, item)
        for offset, item in enumerate(results)
        if item.get("verification_status") in {"source_mismatch", "source_not_found"}
    ]


def normalize_selector_values(values: Sequence[str]) -> List[str]:
    normalized: List[str] = []
    for value in values or []:
        for part in str(value or "").split(","):
            cleaned = part.strip()
            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)
    return normalized


def item_matches_exact_selection(
    item: Dict[str, Any],
    *,
    candidate_ids: Sequence[str] = (),
    footnote_ids: Sequence[str] = (),
) -> bool:
    if candidate_ids and str(item.get("candidate_id") or "") not in set(candidate_ids):
        return False
    if footnote_ids and str(item.get("footnote_id") or "") not in set(footnote_ids):
        return False
    return True


def apply_exact_selection(
    selection: Sequence[tuple[int, Dict[str, Any]]],
    *,
    candidate_ids: Sequence[str] = (),
    footnote_ids: Sequence[str] = (),
) -> List[tuple[int, Dict[str, Any]]]:
    if not candidate_ids and not footnote_ids:
        return list(selection)
    return [
        (offset, item)
        for offset, item in selection
        if item_matches_exact_selection(item, candidate_ids=candidate_ids, footnote_ids=footnote_ids)
    ]


def candidate_for_offset(
    candidates: Sequence[CitationCandidate],
    offset: int,
    source_item: Dict[str, Any],
) -> Optional[CitationCandidate]:
    if offset < 0 or offset >= len(candidates):
        try:
            candidate = candidate_from_dict(source_item)
        except Exception:
            return None
        candidate.artifacts["refinement_source_candidate_id"] = source_item.get("candidate_id")
        candidate.artifacts["refinement_offset"] = offset
        return candidate
    candidate = candidates[offset]
    candidate.artifacts["refinement_source_candidate_id"] = source_item.get("candidate_id")
    candidate.artifacts["refinement_offset"] = offset
    return candidate


def source_matches_from_item(item: Dict[str, Any]) -> List[NDLSearchMatch]:
    return [match_from_dict(match) for match in item.get("ndl_matches") or []]


def _clean_query(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _append_unique(items: List[str], value: Any) -> None:
    cleaned = _clean_query(value)
    if cleaned and cleaned not in items:
        items.append(cleaned)


def _preferred_volume_terms(footnote: ParsedFootnote) -> List[str]:
    raw_terms = extract_volume_terms(
        " ".join(
            str(item or "")
            for item in [
                footnote.text,
                footnote.ndl_keyword,
                footnote.title,
                footnote.host_title,
            ]
        )
    )
    terms: List[str] = []
    for term in raw_terms:
        _append_unique(terms, term)
    return sorted(
        terms,
        key=lambda term: (
            0 if "巻" in term else 1 if "卷" in term else 2 if "年" in term else 3,
            len(term),
            term,
        ),
    )


def _source_title_terms(footnote: ParsedFootnote) -> List[str]:
    titles: List[str] = []
    for value in [
        footnote.host_title,
        footnote.title,
        footnote.ndl_keyword.split(" ")[0] if footnote.ndl_keyword else "",
    ]:
        _append_unique(titles, value)
        for part in re.split(r"[・·:：/、，,;；\s]+", str(value or "")):
            if len(part.strip()) >= 4:
                _append_unique(titles, part)
    return titles[:4]


def _claim_term_priority(term: str) -> Tuple[int, int, int, int, str]:
    if any(marker in term for marker in ("門戸開放", "門戶開放", "门户开放")):
        marker_group = 0
    elif any(marker in term for marker in ("タフト", "ハリマン", "南満", "南滿", "満鉄", "桂・タフト")):
        marker_group = 0
    elif any(
        marker in term
        for marker in (
            "政教一致",
            "治国安民",
            "治國安民",
            "民ヲ安ズル",
            "本心ノ自由",
            "良心ノ自由",
            "正理ノ伸",
        )
    ):
        marker_group = 1
    elif any(marker in term for marker in ("機會均等", "机会均等")):
        marker_group = 2
    else:
        marker_group = 3
    historical_script_bonus = 0 if any(char in term for char in "門戶戸機會國ヲノ") else 1
    return (
        marker_group,
        historical_script_bonus,
        0 if 4 <= len(term) <= 18 else 1,
        len(term),
        term,
    )


def _claim_term_bucket(term: str) -> str:
    if any(marker in term for marker in ("ジョン・ヘイ", "ヘイ", "米國國務", "米国国務", "米國務卿", "米国務卿", "合衆國")):
        return "hay"
    if any(marker in term for marker in ("タフト", "ハリマン", "南満", "南滿", "満鉄", "桂・タフト", "共同經營", "共同経営")):
        return "katsura_taft_harriman"
    if any(marker in term for marker in ("門戸開放", "門戶開放", "门户开放")):
        return "open_door"
    if any(marker in term for marker in ("機會均等", "機会均等", "机会均等")):
        return "equal_opportunity"
    if any(marker in term for marker in ("照會", "照会", "回答", "同意", "賛成", "贊成", "各國", "各国", "帝國政府", "帝国政府")):
        return "reply_position"
    if any(marker in term for marker in ("政教一致", "治国安民", "治國安民", "民ヲ安ズル", "本心ノ自由", "良心ノ自由", "正理ノ伸")):
        return "core_claim"
    return "other"


def _claim_terms_for_global_fulltext(
    verifier: HistoricalCitationVerifier,
    candidate: CitationCandidate,
) -> List[str]:
    terms: List[str] = []
    for query in verifier._claim_fulltext_queries(candidate):
        cleaned = _clean_query(query)
        if len(cleaned) < 4:
            continue
        if len(cleaned) > 42 and not any(marker in cleaned for marker in ("門戸開放", "政教一致", "本心ノ自由")):
            continue
        _append_unique(terms, cleaned)
    ranked_terms = sorted(terms, key=_claim_term_priority)
    bucket_limits = {
        "hay": 2,
        "open_door": 2,
        "equal_opportunity": 1,
        "reply_position": 1,
        "core_claim": 6,
        "katsura_taft_harriman": 4,
        "other": 2,
    }
    bucket_order = [
        "hay",
        "katsura_taft_harriman",
        "open_door",
        "equal_opportunity",
        "reply_position",
        "core_claim",
        "other",
    ]
    selected: List[str] = []
    for bucket in bucket_order:
        taken = 0
        for term in ranked_terms:
            if _claim_term_bucket(term) != bucket or term in selected:
                continue
            selected.append(term)
            taken += 1
            if len(selected) >= 6 or taken >= bucket_limits[bucket]:
                break
        if len(selected) >= 6:
            break
    for term in ranked_terms:
        if len(selected) >= 6:
            break
        if term not in selected:
            selected.append(term)
    return selected[:6]


def source_claim_context_for_queries(candidate: CitationCandidate) -> str:
    return candidate_source_claim_context(candidate)


def build_claim_fulltext_global_queries(
    verifier: HistoricalCitationVerifier,
    candidate: CitationCandidate,
    *,
    max_queries: int,
) -> List[str]:
    """Build NDL Digital global fulltext probes from source title, volume, and claim terms."""

    queries: List[str] = []
    source_plan = build_source_query_plan(
        candidate.footnote,
        claim_text=source_claim_context_for_queries(candidate),
    )
    candidate.artifacts["source_query_plan"] = source_plan.to_dict()
    titles = _source_title_terms(candidate.footnote)
    for title in [*source_plan.host_bucket, *source_plan.title_bucket]:
        _append_unique(titles, title)
    volume_terms = _preferred_volume_terms(candidate.footnote)
    for term in source_plan.volume_bucket:
        _append_unique(volume_terms, term)
    claim_terms = _claim_terms_for_global_fulltext(verifier, candidate)
    for term in [
        *source_plan.contained_bucket,
        *source_plan.person_bucket,
        *source_plan.policy_bucket,
        *source_plan.date_bucket,
        *source_plan.special_term_bucket,
    ]:
        _append_unique(claim_terms, term)
    if not titles or not claim_terms:
        return []

    resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
    if isinstance(resolver_plan, dict) and resolver_plan.get("source_type") == "volume_series":
        resolver_titles = list(titles)
        resolver_volumes = [str(term) for term in (resolver_plan.get("volume_terms") or volume_terms) if str(term or "")]
        resolver_targets = [str(term) for term in (resolver_plan.get("target_pid_queries") or []) if str(term or "")]
        query_buckets = resolver_plan.get("query_buckets") or {}
        if isinstance(query_buckets, dict):
            for bucket_name in ("document_heading", "policy", "person", "document_title", "page_near"):
                for value in query_buckets.get(bucket_name) or []:
                    _append_unique(resolver_targets, value)
        for title in resolver_titles[:1]:
            for volume in resolver_volumes[:1] or [""]:
                for target in resolver_targets:
                    _append_unique(queries, " ".join(item for item in [title, volume, target] if item))
                    if len(queries) >= max_queries:
                        return queries
        for target in resolver_targets:
            if len(str(target)) >= 4:
                _append_unique(queries, target)
                if len(queries) >= max_queries:
                    return queries

    for query in source_plan.global_fulltext_queries(max_queries=max_queries):
        _append_unique(queries, query)
        if len(queries) >= max_queries:
            return queries

    if volume_terms:
        for title in titles:
            for volume in volume_terms:
                for claim in claim_terms:
                    _append_unique(queries, " ".join([title, volume, claim]))
                    if len(queries) >= max_queries:
                        return queries

    for title in titles:
        for claim in claim_terms:
            _append_unique(queries, " ".join([title, claim]))
            if len(queries) >= max_queries:
                return queries
    return queries[:max_queries]


def _match_identity(match: NDLSearchMatch) -> str:
    return str(match.ndl_id or match.platform_item_id or match.url or "")


def _merge_match_metadata(existing: NDLSearchMatch, incoming: NDLSearchMatch) -> None:
    metadata = existing.metadata
    incoming_metadata = incoming.metadata or {}
    incoming_hints = incoming_metadata.get("fulltext_hints") or []
    hints = metadata.setdefault("fulltext_hints", [])
    if not isinstance(hints, list):
        hints = []
        metadata["fulltext_hints"] = hints
    for hint in incoming_hints:
        if not isinstance(hint, dict):
            continue
        if not any(
            isinstance(item, dict)
            and item.get("snippet") == hint.get("snippet")
            and item.get("pdf_page") == hint.get("pdf_page")
            for item in hints
        ):
            hints.append(dict(hint))
    routes = set(str(route) for route in (metadata.get("search_routes") or []) if route)
    for route in [metadata.get("search_route"), incoming_metadata.get("search_route"), "claim_fulltext_global_recheck"]:
        if route:
            routes.add(str(route))
    metadata["search_routes"] = sorted(routes)
    metadata["claim_fulltext_global_recheck"] = True
    for key, value in incoming_metadata.items():
        if key in {"fulltext_hints", "search_routes"}:
            continue
        metadata.setdefault(key, value)
    existing.score = max(float(existing.score or 0.0), float(incoming.score or 0.0), 0.2)


def augment_candidate_matches_with_claim_fulltext(
    verifier: HistoricalCitationVerifier,
    candidate: CitationCandidate,
    *,
    max_results: int,
    search_fulltext: Callable[..., List[Dict[str, Any]]] = search_ndl_digital_fulltext,
) -> int:
    """Add NDL Digital PIDs found only by volume + claim fulltext queries."""

    queries = build_claim_fulltext_global_queries(
        verifier,
        candidate,
        max_queries=max(1, min(16, int(max_results or 3) * 4)),
    )
    if not queries:
        return 0
    candidate.artifacts["claim_fulltext_query_strategy"] = "title_volume_claim_layers"
    existing_by_id = {
        _match_identity(match): match
        for match in candidate.ndl_matches
        if _match_identity(match)
    }
    added = 0
    max_added = max(1, min(12, int(max_results or 3) * 4))
    tried: List[str] = []
    for query in queries:
        tried.append(query)
        try:
            records = search_fulltext(query, max_results=max(1, int(max_results or 3)))
        except Exception as exc:  # noqa: BLE001
            candidate.notes.append(f"claim_fulltext_global_recheck_failed:{type(exc).__name__}")
            continue
        for record in records:
            metadata = dict(record.get("metadata") or {})
            metadata["claim_fulltext_global_recheck"] = True
            metadata["claim_fulltext_global_query"] = query
            record = {**record, "metadata": metadata}
            match = match_from_dict(record)
            identity = _match_identity(match)
            if not identity:
                continue
            existing = existing_by_id.get(identity)
            if existing is not None:
                _merge_match_metadata(existing, match)
                continue
            if added >= max_added:
                continue
            match.metadata["claim_fulltext_global_recheck"] = True
            match.metadata["claim_fulltext_global_query"] = query
            candidate.ndl_matches.append(match)
            existing_by_id[identity] = match
            added += 1
    if tried:
        candidate.artifacts["claim_fulltext_global_queries"] = tried
    if added:
        candidate.notes.append(f"claim_fulltext_global_recheck_added:{added}")
    return added


def _normalized_equivalent_title(title: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(title or "")).lower()
    normalized = re.sub(r"[\s　・:：,，.。;；、\-‐‑–—_()（）\[\]【】『』「」]+", "", normalized)
    normalized = re.sub(r"(第?[0-9０-９一二三四五六七八九十百]+(巻|卷|冊|册|編|篇|集|号|號))$", "", normalized)
    normalized = re.sub(r"(上巻|下巻|中巻|前編|後編|別巻|総目録|索引)$", "", normalized)
    return normalized


def _match_is_fulltext_lead(match: NDLSearchMatch) -> bool:
    metadata = match.metadata if isinstance(match.metadata, dict) else {}
    routes = {str(route) for route in (metadata.get("search_routes") or []) if route}
    route = str(metadata.get("search_route") or "")
    if route:
        routes.add(route)
    return bool(metadata.get("claim_fulltext_global_recheck")) or any("fulltext" in route for route in routes)


def _pid_group_record(match: NDLSearchMatch, *, rank: int, identity: str, scope: str) -> Dict[str, Any]:
    metadata = match.metadata if isinstance(match.metadata, dict) else {}
    return {
        "rank": rank,
        "ndl_id": match.ndl_id or match.platform_item_id or identity,
        "title": match.title,
        "date": match.date,
        "publisher": match.publisher,
        "url": match.url,
        "score": match.score,
        "search_route": metadata.get("search_route"),
        "search_routes": metadata.get("search_routes"),
        "fulltext_query": metadata.get("claim_fulltext_global_query"),
        "claim_fulltext_global_recheck": bool(metadata.get("claim_fulltext_global_recheck")),
        "scope": scope,
    }


def record_equivalent_pid_group(candidate: CitationCandidate, *, max_items: int = 8) -> List[Dict[str, Any]]:
    """Record same-title/same-base NDL Digital PIDs so the report exposes viable siblings."""

    matches = [match for match in candidate.ndl_matches or [] if _match_identity(match)]
    resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
    configured_pids = []
    if isinstance(resolver_plan, dict):
        configured_pids = [str(pid) for pid in (resolver_plan.get("known_pid_candidates") or []) if str(pid or "")]
    strict_configured_only = bool(configured_pids) and str(resolver_plan.get("source_type") or "") in {
        "contained_document",
        "diary",
        "volume_series",
    }

    source_base = _normalized_equivalent_title(
        candidate.footnote.host_title or candidate.footnote.title
    )
    anchor_title = candidate.footnote.host_title or candidate.footnote.title or (matches[0].title if matches else "")
    anchor_base = source_base or _normalized_equivalent_title(anchor_title)
    if not anchor_base:
        candidate.artifacts.pop("equivalent_pid_group", None)
        return []

    group: List[Dict[str, Any]] = []
    fulltext_leads: List[Dict[str, Any]] = []
    seen: set[str] = set()
    lead_seen: set[str] = set()
    for index, match in enumerate(matches):
        title_base = _normalized_equivalent_title(match.title)
        identity = _match_identity(match)
        if not identity or identity in seen:
            continue
        if strict_configured_only and identity not in configured_pids:
            if (
                title_base == anchor_base
                and identity not in lead_seen
                and _match_is_fulltext_lead(match)
                and len(fulltext_leads) < max_items
            ):
                fulltext_leads.append(
                    _pid_group_record(
                        match,
                        rank=len(fulltext_leads) + 1,
                        identity=identity,
                        scope="global_fulltext_lead_not_equivalent",
                    )
                )
                lead_seen.add(identity)
            continue
        if title_base != anchor_base and identity not in configured_pids:
            continue
        group.append(
            _pid_group_record(
                match,
                rank=index + 1,
                identity=identity,
                scope="configured_or_same_source_equivalent",
            )
        )
        seen.add(identity)
        if len(group) >= max_items:
            break

    for pid in configured_pids:
        if len(group) >= max_items:
            break
        if pid in seen:
            continue
        group.append(
            {
                "rank": len(group) + 1,
                "ndl_id": pid,
                "title": candidate.footnote.title,
                "date": None,
                "publisher": None,
                "url": f"https://dl.ndl.go.jp/pid/{pid}",
                "score": None,
                "search_route": "resolver_config",
                "search_routes": ["resolver_config"],
                "fulltext_query": None,
                "claim_fulltext_global_recheck": False,
                "configured_pid_candidate": True,
                "scope": "configured_or_same_source_equivalent",
            }
        )
        seen.add(pid)

    if fulltext_leads:
        candidate.artifacts["fulltext_lead_pid_group"] = fulltext_leads
        if "fulltext_lead_pid_group_recorded" not in candidate.notes:
            candidate.notes.append("fulltext_lead_pid_group_recorded")
    else:
        candidate.artifacts.pop("fulltext_lead_pid_group", None)

    if len(group) > 1:
        candidate.artifacts["equivalent_pid_group"] = group
        if "equivalent_pid_group_recorded" not in candidate.notes:
            candidate.notes.append("equivalent_pid_group_recorded")
        return group
    else:
        candidate.artifacts.pop("equivalent_pid_group", None)
    return []


def write_progress(path: Path, event: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def load_existing_refinement(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def dedupe_by_offset(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_offset: Dict[int, Dict[str, Any]] = {}
    fallback: List[Dict[str, Any]] = []
    for item in items:
        offset = result_offset(item)
        if offset is None:
            fallback.append(item)
        else:
            by_offset[offset] = item
    return [by_offset[offset] for offset in sorted(by_offset)] + dedupe_result_dicts(fallback)


def summarize_dict_results(items: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    candidates: List[CitationCandidate] = []
    # The reporting summary helper expects dataclasses; for this lightweight
    # refinement report a direct status count is enough and easier to preserve.
    status_counts: Dict[str, int] = {"total": len(items)}
    for item in items:
        status = str(item.get("verification_status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    return status_counts


def _worker_progress_event(
    reporter: Optional[ProgressReporter],
    event: str,
    *,
    subphase: str,
    status: Optional[str] = None,
    metrics: Optional[Dict[str, Any]] = None,
) -> None:
    if reporter is None or not reporter.enabled:
        return
    reporter.update(subphase=subphase, status=status or "running")
    reporter.event(event, subphase=subphase, status=status, metrics=metrics)


def run_download_ocr_alignment(
    *,
    verifier: HistoricalCitationVerifier,
    candidate: CitationCandidate,
    source_item: Dict[str, Any],
    output_dir: Path,
    restricted_download: bool,
    page_window: int,
    ocr_model: str,
    download_max_attempts: int,
    progress_reporter: Optional[ProgressReporter] = None,
) -> Dict[str, Any]:
    _worker_progress_event(progress_reporter, "worker_stage_started", subphase="source_graph_attach")
    attach_source_graph_artifacts(candidate)
    _worker_progress_event(
        progress_reporter,
        "worker_stage_completed",
        subphase="source_graph_attach",
        metrics={"source_type": _candidate_source_type(candidate)},
    )
    candidate.ndl_matches = source_matches_from_item(source_item)
    candidate.verification_status = "source_found"
    if _try_volume_series_fulltext_review_before_download(
        verifier=verifier,
        candidate=candidate,
        output_dir=output_dir,
        restricted_download=restricted_download,
        progress_reporter=progress_reporter,
    ):
        candidate.artifacts["manual_search_recipe"] = build_manual_search_recipe(
            candidate.footnote,
            claim_text=source_claim_context_for_queries(candidate),
            current_status=candidate.verification_status,
        )
        return candidate.to_dict()
    _worker_progress_event(
        progress_reporter,
        "worker_stage_started",
        subphase="download_ocr_enrichment",
        metrics={"restricted_download": restricted_download, "page_window": page_window},
    )
    verifier._enrich_with_source_excerpt(
        candidate,
        output_dir=output_dir,
        restricted_download=restricted_download,
        page_window=page_window,
        ocr_model=ocr_model,
        download_max_attempts=max(download_max_attempts, 1),
    )
    _worker_progress_event(
        progress_reporter,
        "worker_stage_completed",
        subphase="download_ocr_enrichment",
        status=candidate.verification_status,
        metrics={"support_status": candidate.support_status},
    )
    candidate.artifacts["manual_search_recipe"] = build_manual_search_recipe(
        candidate.footnote,
        claim_text=source_claim_context_for_queries(candidate),
        current_status=candidate.verification_status,
    )
    return candidate.to_dict()


def _candidate_source_type(candidate: CitationCandidate) -> str:
    resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
    if isinstance(resolver_plan, dict) and resolver_plan.get("source_type"):
        return str(resolver_plan.get("source_type") or "")
    source_graph = candidate.artifacts.get("source_graph") or {}
    if isinstance(source_graph, dict) and source_graph.get("source_type"):
        return str(source_graph.get("source_type") or "")
    return str(getattr(candidate.footnote, "source_type", "") or "")


def _try_volume_series_fulltext_review_before_download(
    *,
    verifier: HistoricalCitationVerifier,
    candidate: CitationCandidate,
    output_dir: Path,
    restricted_download: bool,
    progress_reporter: Optional[ProgressReporter] = None,
) -> bool:
    if not restricted_download:
        return False
    if _candidate_source_type(candidate) != "volume_series":
        return False
    if not candidate.ndl_matches:
        return False
    mark_fulltext = getattr(verifier, "_mark_fulltext_only_hit_if_possible", None)
    if not callable(mark_fulltext):
        return False
    _worker_progress_event(
        progress_reporter,
        "worker_stage_started",
        subphase="volume_series_fulltext_review",
        metrics={"restricted_download": restricted_download},
    )
    previous_progress_callback = getattr(verifier, "_progress_event_callback", None)
    progress_callback_attached = False
    if progress_reporter is not None and progress_reporter.enabled:
        def relay_verifier_progress(
            *,
            event: str,
            subphase: str,
            status: Optional[str] = None,
            metrics: Optional[Dict[str, Any]] = None,
        ) -> None:
            _worker_progress_event(
                progress_reporter,
                event,
                subphase=subphase,
                status=status,
                metrics=metrics,
            )

        try:
            setattr(verifier, "_progress_event_callback", relay_verifier_progress)
            progress_callback_attached = True
        except Exception:
            progress_callback_attached = False
    try:
        reviewed = bool(
            mark_fulltext(
                candidate,
                output_dir=output_dir,
                max_context_candidates=5,
                max_hints_to_expand=3,
                max_expand_rounds=1,
            )
        )
    except Exception as exc:  # noqa: BLE001
        candidate.notes.append(f"volume_series_fulltext_review_before_download_failed:{type(exc).__name__}")
        _worker_progress_event(
            progress_reporter,
            "worker_stage_failed",
            subphase="volume_series_fulltext_review",
            status="failed",
            metrics={"error_type": type(exc).__name__},
        )
        return False
    finally:
        if progress_callback_attached:
            try:
                setattr(verifier, "_progress_event_callback", previous_progress_callback)
            except Exception:
                pass
    metrics = {
        "reviewed": reviewed,
        "status": candidate.verification_status,
        "context_count": len(candidate.artifacts.get("fulltext_context_candidates") or []),
        "target_probe_status": (candidate.artifacts.get("ndl_fulltext_probe") or {}).get("status"),
        "cache_hits": int(candidate.artifacts.get("fulltext_context_cache_hits") or 0),
        "disk_cache_hits": int(candidate.artifacts.get("fulltext_context_disk_cache_hits") or 0),
    }
    _worker_progress_event(
        progress_reporter,
        "worker_stage_completed",
        subphase="volume_series_fulltext_review",
        status=candidate.verification_status,
        metrics=metrics,
    )
    if not reviewed:
        candidate.notes.append("volume_series_fulltext_review_before_download_no_context")
        return False
    phase = (
        "rechecked_download_ocr_alignment"
        if "download_after_source_recheck" in candidate.notes
        else "download_ocr_alignment"
    )
    candidate.artifacts["volume_series_fulltext_review_before_download"] = {
        "status": candidate.verification_status,
        "phase": phase,
        "reason": "target_pid_fulltext_context_available_before_restricted_download",
    }
    if candidate.verification_status == "fulltext_lead_only":
        candidate.notes.append("volume_series_fulltext_lead_before_download_stopped")
        return True
    if str(candidate.verification_status or "").startswith("fulltext_only"):
        candidate.notes.append("volume_series_fulltext_review_before_download")
        return True
    return False


DOWNLOAD_WORKER_CODE = r"""
import json
import sys
from pathlib import Path

from scripts.refine_historical_citation_pdf_next_stage import (
    HistoricalCitationVerifier,
    candidate_from_dict,
    run_download_ocr_alignment,
)
from modules.historical_citation.progress import ProgressReporter

payload_path = Path(sys.argv[1])
result_path = Path(sys.argv[2])
payload = json.loads(payload_path.read_text(encoding="utf-8"))
verifier = HistoricalCitationVerifier(
    allow_external_ndl_fallback=bool(payload.get("allow_external_ndl_fallback", True)),
    prefer_ollama_review=bool(payload.get("prefer_ollama_review", False)),
)
candidate = candidate_from_dict(payload["candidate"])
progress_path_text = str(payload.get("progress_path") or "")
progress_stream = None
try:
    if progress_path_text:
        progress_path = Path(progress_path_text)
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        progress_stream = progress_path.open("a", encoding="utf-8")
    reporter = ProgressReporter(
        enabled=bool(progress_stream),
        interval_seconds=float(payload.get("progress_interval_seconds") or 30),
        stream=progress_stream,
    )
    with reporter:
        reporter.update(
            phase=payload.get("progress_phase") or "download_ocr_alignment",
            current=payload.get("progress_current"),
            total=payload.get("progress_total"),
            global_current=payload.get("progress_global_current"),
            global_total=payload.get("progress_global_total"),
            candidate_id=candidate.candidate_id,
            footnote_id=candidate.footnote_id,
            worker_pid=payload.get("worker_pid"),
            subphase="worker_boot",
            status="running",
        )
        reporter.event("worker_started", subphase="worker_boot", status="running")
        result = run_download_ocr_alignment(
            verifier=verifier,
            candidate=candidate,
            source_item=payload["source_item"],
            output_dir=Path(payload["output_dir"]),
            restricted_download=bool(payload.get("restricted_download", False)),
            page_window=int(payload.get("page_window") or 4),
            ocr_model=str(payload.get("ocr_model") or "ndlocr_lite"),
            download_max_attempts=int(payload.get("download_max_attempts") or 1),
            progress_reporter=reporter,
        )
        reporter.update(subphase="worker_complete", status=result.get("verification_status") or "completed")
        reporter.event(
            "worker_completed",
            subphase="worker_complete",
            status=result.get("verification_status") or "completed",
            metrics={"support_status": result.get("support_status")},
        )
finally:
    if progress_stream is not None:
        progress_stream.close()
result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
"""


def kill_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    try:
        os.kill(pid, 9)
    except OSError:
        pass


def run_download_ocr_alignment_with_timeout(
    *,
    candidate: CitationCandidate,
    source_item: Dict[str, Any],
    output_dir: Path,
    restricted_download: bool,
    page_window: int,
    ocr_model: str,
    download_max_attempts: int,
    timeout_seconds: int,
    allow_external_ndl_fallback: bool,
    prefer_ollama_review: bool,
    progress_path: Optional[Path] = None,
    progress_phase: str = "download_ocr_alignment",
    progress_current: Optional[int] = None,
    progress_total: Optional[int] = None,
    progress_global_current: Optional[int] = None,
    progress_global_total: Optional[int] = None,
    progress_interval_seconds: float = 30.0,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    precheck_verifier: Optional[HistoricalCitationVerifier] = None
    requested_timeout_seconds = timeout_seconds
    if restricted_download:
        precheck_verifier = HistoricalCitationVerifier(
            allow_external_ndl_fallback=allow_external_ndl_fallback,
            prefer_ollama_review=prefer_ollama_review,
        )
        dependency_status = precheck_verifier.restricted_download_dependency_status()
        if not dependency_status.get("available", False):
            candidate.artifacts["download_dependency_precheck"] = dict(dependency_status)
            if not prefer_ollama_review or timeout_seconds <= 0:
                result = run_download_ocr_alignment(
                    verifier=precheck_verifier,
                    candidate=candidate,
                    source_item=source_item,
                    output_dir=output_dir,
                    restricted_download=restricted_download,
                    page_window=page_window,
                    ocr_model=ocr_model,
                    download_max_attempts=download_max_attempts,
                )
                result.setdefault("artifacts", {})["download_worker_bypassed"] = {
                    "reason": "download_dependency_missing",
                    "dependency": dependency_status.get("dependency") or "",
                }
                return result, None
    if timeout_seconds > 0 and prefer_ollama_review:
        try:
            review_timeout_seconds = int(os.environ.get("HISTORICAL_CITATION_REVIEW_TIMEOUT_SECONDS") or 0)
        except ValueError:
            review_timeout_seconds = 0
        try:
            worker_overhead_seconds = max(
                90,
                int(os.environ.get("HISTORICAL_CITATION_FORMAL_REVIEW_WORKER_OVERHEAD_SECONDS") or 300),
            )
        except ValueError:
            worker_overhead_seconds = 300
        effective_timeout_seconds = max(
            timeout_seconds,
            review_timeout_seconds + worker_overhead_seconds if review_timeout_seconds else timeout_seconds,
        )
        if effective_timeout_seconds != timeout_seconds:
            candidate.artifacts["download_worker_timeout_policy"] = {
                "requested_timeout_seconds": requested_timeout_seconds,
                "effective_timeout_seconds": effective_timeout_seconds,
                "review_timeout_seconds": review_timeout_seconds,
                "worker_overhead_seconds": worker_overhead_seconds,
                "reason": "formal_review_timeout_guard",
            }
            timeout_seconds = effective_timeout_seconds
    if timeout_seconds <= 0:
        verifier = precheck_verifier or HistoricalCitationVerifier(
            allow_external_ndl_fallback=allow_external_ndl_fallback,
            prefer_ollama_review=prefer_ollama_review,
        )
        return (
            run_download_ocr_alignment(
                verifier=verifier,
                candidate=candidate,
                source_item=source_item,
                output_dir=output_dir,
                restricted_download=restricted_download,
                page_window=page_window,
                ocr_model=ocr_model,
                download_max_attempts=download_max_attempts,
            ),
            None,
        )

    task_dir = output_dir / "_download_tasks"
    task_dir.mkdir(parents=True, exist_ok=True)
    offset = candidate.artifacts.get("refinement_offset", "unknown")
    token = re.sub(r"[^0-9A-Za-z_.-]+", "_", f"{offset}_{candidate.candidate_id}_{candidate.footnote_id}")
    payload_path = task_dir / f"{token}.payload.json"
    result_path = task_dir / f"{token}.result.json"
    stdout_path = task_dir / f"{token}.stdout.log"
    stderr_path = task_dir / f"{token}.stderr.log"
    payload = {
        "candidate": candidate.to_dict(),
        "source_item": source_item,
        "output_dir": str(output_dir),
        "restricted_download": restricted_download,
        "page_window": page_window,
        "ocr_model": ocr_model,
        "download_max_attempts": download_max_attempts,
        "allow_external_ndl_fallback": allow_external_ndl_fallback,
        "prefer_ollama_review": prefer_ollama_review,
        "progress_path": str(progress_path) if progress_path else "",
        "progress_phase": progress_phase,
        "progress_current": progress_current,
        "progress_total": progress_total,
        "progress_global_current": progress_global_current,
        "progress_global_total": progress_global_total,
        "progress_interval_seconds": progress_interval_seconds,
    }
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    process = subprocess.Popen(
        [sys.executable, "-c", DOWNLOAD_WORKER_CODE, str(payload_path), str(result_path)],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        kill_process_tree(process.pid)
        stdout, stderr = process.communicate()
        stdout_path.write_bytes(stdout or b"")
        stderr_path.write_bytes(stderr or b"")
        candidate.verification_status = "download_timeout"
        candidate.notes.append(f"download_ocr_timeout_after_{timeout_seconds}s")
        candidate.artifacts["download_timeout"] = {
            "timeout_seconds": timeout_seconds,
            "payload": str(payload_path),
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
        }
        timeout_event = build_progress_event(
            "candidate_timeout",
            phase="download_ocr_alignment",
            global_current=(int(offset) + 1 if str(offset).isdigit() else None),
            candidate_id=candidate.candidate_id,
            footnote_id=candidate.footnote_id,
            status="download_timeout",
            metrics={"timeout_seconds": timeout_seconds},
        )
        return candidate.to_dict(), timeout_event

    stdout_path.write_bytes(stdout or b"")
    stderr_path.write_bytes(stderr or b"")
    if process.returncode != 0 or not result_path.exists():
        candidate.verification_status = "download_failed"
        candidate.notes.append(f"download_worker_failed:returncode={process.returncode}")
        candidate.artifacts["download_worker"] = {
            "returncode": process.returncode,
            "payload": str(payload_path),
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
        }
        return candidate.to_dict(), None
    try:
        return json.loads(result_path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as exc:
        candidate.verification_status = "download_failed"
        candidate.notes.append(f"download_worker_result_invalid:{exc}")
        candidate.artifacts["download_worker"] = {
            "returncode": process.returncode,
            "payload": str(payload_path),
            "result": str(result_path),
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
        }
        return candidate.to_dict(), None


def render_markdown(
    *,
    label: str,
    document: Dict[str, Any],
    total_candidates: int,
    output_dir: Path,
    download_results: Sequence[Dict[str, Any]],
    rechecked_download_results: Sequence[Dict[str, Any]],
    mismatch_results: Sequence[Dict[str, Any]],
    non_ndl_sources: Sequence[Dict[str, Any]],
    alias_audits: Sequence[Dict[str, Any]],
    timeout_events: Sequence[Dict[str, Any]],
    slow_events: Sequence[Dict[str, Any]],
    execution_runs: Sequence[Dict[str, Any]],
) -> str:
    by_key: Dict[str, Dict[str, Any]] = {}
    for item in [*mismatch_results, *download_results, *rechecked_download_results]:
        offset = result_offset(item)
        key = str(offset) if offset is not None else str(item.get("candidate_id") or len(by_key))
        by_key[key] = dict(item)
    checkpoint = {
        "results": by_key,
        "artifacts": build_artifact_summary(output_dir),
        "next_stage": {
            "label": label,
            "download_ocr_alignment_count": len(download_results),
            "rechecked_download_ocr_alignment_count": len(rechecked_download_results),
            "source_recheck_count": len(mismatch_results),
            "non_ndl_direct_source_count": len(non_ndl_sources),
            "title_alias_audit_count": len(alias_audits),
            "timeout_count": len(timeout_events),
            "slow_event_count": len(slow_events),
            "execution_run_count": len(execution_runs),
            "timeout_events": list(timeout_events),
            "slow_events": list(slow_events),
            "execution_runs": list(execution_runs),
            "non_ndl_direct_sources": list(non_ndl_sources),
            "title_alias_audit": list(alias_audits),
        },
    }
    markdown = render_resume_markdown_report(
        document=document,
        checkpoint=checkpoint,
        total_candidates=total_candidates,
        output_dir=output_dir,
    )
    if not slow_events and not execution_runs:
        return markdown
    lines = [
        markdown.rstrip(),
        "",
    ]
    if execution_runs:
        lines.extend(["## 运行历史", ""])
        for index, item in enumerate(execution_runs[-10:], start=max(1, len(execution_runs) - 9)):
            lines.append(
                f"- {index}. {item.get('started_at') or 'unknown'} | {item.get('mode') or 'unknown'} | "
                f"timeout={item.get('download_timeout_seconds')}s | "
                f"retry={item.get('retry_download_timeouts')} | "
                f"model={item.get('review_model') or 'unknown'}"
            )
        lines.append("")
    if slow_events:
        lines.extend(["## 处理慢路径", ""])
        for item in slow_events[:20]:
            subphase_parts: List[str] = []
            if item.get("last_subphase"):
                subphase_parts.append(
                    f"last={item.get('last_subphase')}"
                    + (f"/{item.get('last_subphase_status')}" if item.get("last_subphase_status") else "")
                )
            if item.get("longest_subphase"):
                subphase_parts.append(
                    f"longest={item.get('longest_subphase')}"
                    + (
                        f"/{item.get('longest_subphase_seconds')}s"
                        if item.get("longest_subphase_seconds") is not None
                        else ""
                    )
                )
            subphase_summary = f" | {'; '.join(subphase_parts)}" if subphase_parts else ""
            lines.append(
                f"- {item.get('phase') or 'unknown'} | 脚注 {item.get('footnote_id') or 'n/a'} | "
                f"{item.get('candidate_id') or 'n/a'} | {item.get('status') or 'unknown'} | "
                f"{item.get('elapsed_seconds')}s{subphase_summary}"
            )
        lines.append("")
    return "\n".join(lines)


def build_payload(
    *,
    args: argparse.Namespace,
    combined: Dict[str, Any],
    download_selection_count: int,
    mismatch_selection_count: int,
    download_results: Sequence[Dict[str, Any]],
    rechecked_download_results: Sequence[Dict[str, Any]],
    mismatch_results: Sequence[Dict[str, Any]],
    non_ndl_sources: Sequence[Dict[str, Any]],
    alias_audits: Sequence[Dict[str, Any]],
    timeout_events: Sequence[Dict[str, Any]],
    slow_events: Sequence[Dict[str, Any]],
    execution_runs: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "label": args.label,
        "document": combined.get("document", {}),
        "source_summary": combined.get("summary", {}),
        "execution": {
            "restricted_download": args.restricted_download,
            "max_search_results": args.max_search_results,
            "page_window": args.page_window,
            "ocr_model": args.ocr_model,
            "download_max_attempts": args.download_max_attempts,
            "download_timeout_seconds": args.download_timeout_seconds,
            "slow_event_threshold_seconds": args.slow_event_threshold_seconds,
            "download_cache_dir": args.download_cache_dir,
            "platform_names": list(args.platform_names or []),
            "reparse_pdf": args.reparse_pdf,
            "download_selection_count": download_selection_count,
            "mismatch_selection_count": mismatch_selection_count,
            "candidate_ids": normalize_selector_values(getattr(args, "candidate_id", []) or []),
            "footnote_ids": normalize_selector_values(getattr(args, "footnote_id", []) or []),
            "download_start_index": args.download_start_index,
            "mismatch_start_index": args.mismatch_start_index,
            "recheck_download_start_index": args.recheck_download_start_index,
            "max_recheck_downloads": args.max_recheck_downloads,
            "retry_download_timeouts": args.retry_download_timeouts,
            "force_ndl_fulltext": not args.no_force_ndl_fulltext,
            "recheck_downloads": not args.skip_recheck_downloads,
            "prefer_ollama_review": args.prefer_ollama_review,
            "review_model": args.review_model or os.environ.get("HISTORICAL_CITATION_REVIEW_MODEL", ""),
            "review_timeout_seconds": args.review_timeout_seconds,
            "resume": not args.no_resume,
        },
        "download_ocr_alignment_results": list(download_results),
        "rechecked_download_ocr_alignment_results": list(rechecked_download_results),
        "source_mismatch_recheck_results": list(mismatch_results),
        "non_ndl_direct_sources": list(non_ndl_sources),
        "title_alias_audit": list(alias_audits),
        "timeout_events": list(timeout_events),
        "slow_events": list(slow_events),
        "execution_runs": list(execution_runs),
        "summaries": {
            "download_ocr_alignment": summarize_dict_results(download_results),
            "rechecked_download_ocr_alignment": summarize_dict_results(rechecked_download_results),
            "source_mismatch_recheck": summarize_dict_results(mismatch_results),
            "slow_events": {"total": len(slow_events)},
        },
    }


def write_outputs(
    *,
    json_path: Path,
    markdown_path: Path,
    args: argparse.Namespace,
    combined: Dict[str, Any],
    download_selection_count: int,
    mismatch_selection_count: int,
    progress_path: Path,
    download_results: Sequence[Dict[str, Any]],
    rechecked_download_results: Sequence[Dict[str, Any]],
    mismatch_results: Sequence[Dict[str, Any]],
    non_ndl_sources: Sequence[Dict[str, Any]],
    alias_audits: Sequence[Dict[str, Any]],
    timeout_events: Sequence[Dict[str, Any]],
    execution_runs: Sequence[Dict[str, Any]],
) -> None:
    slow_events = build_slow_events_from_progress(
        progress_path,
        threshold_seconds=args.slow_event_threshold_seconds,
    )
    payload = build_payload(
        args=args,
        combined=combined,
        download_selection_count=download_selection_count,
        mismatch_selection_count=mismatch_selection_count,
        download_results=download_results,
        rechecked_download_results=rechecked_download_results,
        mismatch_results=mismatch_results,
        non_ndl_sources=non_ndl_sources,
        alias_audits=alias_audits,
        timeout_events=timeout_events,
        slow_events=slow_events,
        execution_runs=execution_runs,
    )
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(
        render_markdown(
            label=args.label,
            document=combined.get("document", {}),
            total_candidates=len(combined.get("results") or []),
            output_dir=markdown_path.parent,
            download_results=download_results,
            rechecked_download_results=rechecked_download_results,
            mismatch_results=mismatch_results,
            non_ndl_sources=non_ndl_sources,
            alias_audits=alias_audits,
            timeout_events=timeout_events,
            slow_events=slow_events,
            execution_runs=execution_runs,
        ),
        encoding="utf-8",
    )


def main() -> int:
    args = build_parser().parse_args()
    if args.review_model:
        os.environ["HISTORICAL_CITATION_REVIEW_MODEL"] = args.review_model
    previous_review_timeout = os.environ.get("HISTORICAL_CITATION_REVIEW_TIMEOUT_SECONDS")
    os.environ["HISTORICAL_CITATION_REVIEW_TIMEOUT_SECONDS"] = str(max(1, int(args.review_timeout_seconds or 1)))
    os.environ.pop("HISTORICAL_CITATION_SKIP_NDL_FULLTEXT", None)
    previous_force_fulltext = os.environ.get("HISTORICAL_CITATION_FORCE_NDL_FULLTEXT")
    if args.no_force_ndl_fulltext:
        os.environ.pop("HISTORICAL_CITATION_FORCE_NDL_FULLTEXT", None)
    else:
        os.environ["HISTORICAL_CITATION_FORCE_NDL_FULLTEXT"] = "1"
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    download_cache_dir = Path(args.download_cache_dir) if args.download_cache_dir else output_dir / "download_ocr_alignment"
    download_cache_dir.mkdir(parents=True, exist_ok=True)
    progress_path = output_dir / "next_stage_progress.jsonl"
    json_path = output_dir / "next_stage_refinement.json"
    markdown_path = output_dir / "next_stage_refinement_report.md"
    run_started_at = datetime.now().isoformat(timespec="seconds")
    resume_enabled = not args.no_resume
    if progress_path.exists() and not resume_enabled:
        progress_path.unlink()
    elif progress_path.exists() and resume_enabled:
        write_progress(progress_path, build_progress_event("run_resumed", phase="pdf_next_stage_refinement"))

    combined = load_json(args.combined_json)
    source_results = combined.get("results") or []
    verifier = HistoricalCitationVerifier(
        allow_external_ndl_fallback=not args.no_ndl_browser_fallback,
        prefer_ollama_review=args.prefer_ollama_review,
    )
    candidates: List[CitationCandidate] = []
    if args.reparse_pdf:
        parsed = verifier.parse_pdf(
            args.pdf_path,
            ocr_output_dir=output_dir / "pdf_input_ocr",
            ocr_model=args.ocr_model,
        )
        candidates = verifier.build_candidates(parsed["paragraphs"], parsed["footnotes"], include_unquoted=True)

    selected_candidate_ids = normalize_selector_values(args.candidate_id)
    selected_footnote_ids = normalize_selector_values(args.footnote_id)

    download_selection = apply_exact_selection(
        select_items(source_results, status="source_found", downloadable=True),
        candidate_ids=selected_candidate_ids,
        footnote_ids=selected_footnote_ids,
    )
    if args.download_start_index:
        download_selection = download_selection[max(args.download_start_index, 0) :]
    if args.max_downloads is not None:
        download_selection = download_selection[: max(args.max_downloads, 0)]
    mismatch_selection = apply_exact_selection(
        select_recheck_items(source_results),
        candidate_ids=selected_candidate_ids,
        footnote_ids=selected_footnote_ids,
    )
    if args.mismatch_start_index:
        mismatch_selection = mismatch_selection[max(args.mismatch_start_index, 0) :]
    if args.max_mismatch is not None:
        mismatch_selection = mismatch_selection[: max(args.max_mismatch, 0)]

    non_ndl_sources = classify_non_ndl_direct_sources(source_results)
    alias_audits = audit_title_aliases(source_results)

    existing_payload = load_existing_refinement(json_path) if resume_enabled else {}
    raw_download_results: List[Dict[str, Any]] = dedupe_by_offset(
        existing_payload.get("download_ocr_alignment_results") or []
    )
    raw_rechecked_download_results: List[Dict[str, Any]] = dedupe_by_offset(
        existing_payload.get("rechecked_download_ocr_alignment_results") or []
    )
    download_results, rechecked_download_results = split_rechecked_download_results(
        raw_download_results,
        raw_rechecked_download_results,
    )
    mismatch_results: List[Dict[str, Any]] = dedupe_by_offset(
        existing_payload.get("source_mismatch_recheck_results") or []
    )
    timeout_events: List[Dict[str, Any]] = list(existing_payload.get("timeout_events") or [])
    execution_runs: List[Dict[str, Any]] = list(existing_payload.get("execution_runs") or [])
    if not execution_runs and existing_payload.get("execution"):
        previous_execution = dict(existing_payload.get("execution") or {})
        previous_execution.setdefault("started_at", existing_payload.get("created_at") or "unknown")
        previous_execution.setdefault("mode", "legacy_next_stage_run")
        execution_runs.append(previous_execution)
    execution_runs.append(build_execution_run(args, started_at=run_started_at))

    write_outputs(
        json_path=json_path,
        markdown_path=markdown_path,
        args=args,
        combined=combined,
        download_selection_count=len(download_selection),
        mismatch_selection_count=len(mismatch_selection),
        progress_path=progress_path,
        download_results=download_results,
        rechecked_download_results=rechecked_download_results,
        mismatch_results=mismatch_results,
        non_ndl_sources=non_ndl_sources,
        alias_audits=alias_audits,
        timeout_events=timeout_events,
        execution_runs=execution_runs,
    )

    if not args.skip_downloads:
        completed_download_offsets = completed_download_offset_set(
            download_results,
            retry_timeouts=args.retry_download_timeouts,
        )
        for current, (offset, source_item) in enumerate(download_selection, start=1):
            if offset in completed_download_offsets:
                continue
            candidate = candidate_for_offset(candidates, offset, source_item)
            if candidate is None:
                continue
            attach_source_graph_artifacts(candidate)
            write_progress(
                progress_path,
                build_progress_event(
                    "candidate_started",
                    phase="download_ocr_alignment",
                    current=current,
                    total=len(download_selection),
                    global_current=offset + 1,
                    global_total=len(source_results),
                    candidate_id=candidate.candidate_id,
                    footnote_id=candidate.footnote_id,
                ),
            )
            download_result, timeout_event = run_download_ocr_alignment_with_timeout(
                candidate=candidate,
                source_item=source_item,
                output_dir=download_cache_dir,
                restricted_download=args.restricted_download,
                page_window=args.page_window,
                ocr_model=args.ocr_model,
                download_max_attempts=args.download_max_attempts,
                timeout_seconds=args.download_timeout_seconds,
                allow_external_ndl_fallback=not args.no_ndl_browser_fallback,
                prefer_ollama_review=args.prefer_ollama_review,
                progress_path=progress_path,
                progress_phase="download_ocr_alignment",
                progress_current=current,
                progress_total=len(download_selection),
                progress_global_current=offset + 1,
                progress_global_total=len(source_results),
            )
            download_results.append(download_result)
            download_results = dedupe_by_offset(download_results)
            completed_download_offsets.add(offset)
            if timeout_event:
                timeout_events = append_timeout_event(timeout_events, timeout_event)
                write_progress(progress_path, timeout_event)
            else:
                timeout_events = clear_resolved_timeout_events(timeout_events, download_result)
            write_outputs(
                json_path=json_path,
                markdown_path=markdown_path,
                args=args,
                combined=combined,
                download_selection_count=len(download_selection),
                mismatch_selection_count=len(mismatch_selection),
                progress_path=progress_path,
                download_results=download_results,
                rechecked_download_results=rechecked_download_results,
                mismatch_results=mismatch_results,
                non_ndl_sources=non_ndl_sources,
                alias_audits=alias_audits,
                timeout_events=timeout_events,
                execution_runs=execution_runs,
            )
            if not timeout_event:
                write_progress(
                    progress_path,
                    build_progress_event(
                        "candidate_completed",
                        phase="download_ocr_alignment",
                        current=current,
                        total=len(download_selection),
                        global_current=offset + 1,
                        global_total=len(source_results),
                        candidate_id=candidate.candidate_id,
                        footnote_id=candidate.footnote_id,
                        status=download_result.get("verification_status"),
                        metrics={"match_count": len(download_result.get("ndl_matches") or [])},
                    ),
                )

    if not args.skip_mismatch_recheck:
        completed_mismatch_offsets = result_offsets(mismatch_results)
        for current, (offset, source_item) in enumerate(mismatch_selection, start=1):
            if offset in completed_mismatch_offsets:
                continue
            candidate = candidate_for_offset(candidates, offset, source_item)
            if candidate is None:
                continue
            attach_source_graph_artifacts(candidate)
            write_progress(
                progress_path,
                build_progress_event(
                    "candidate_started",
                    phase="source_mismatch_recheck",
                    current=current,
                    total=len(mismatch_selection),
                    global_current=offset + 1,
                    global_total=len(source_results),
                    candidate_id=candidate.candidate_id,
                    footnote_id=candidate.footnote_id,
                ),
            )
            candidate.ndl_matches = verifier.search_sources(
                candidate.footnote,
                max_results=args.max_search_results,
                platform_names=args.platform_names,
                claim_text=source_claim_context_for_queries(candidate),
            )
            augment_candidate_matches_with_claim_fulltext(
                verifier,
                candidate,
                max_results=args.max_search_results,
            )
            verifier._rerank_matches_for_candidate_fulltext(candidate)
            for match in candidate.ndl_matches:
                verifier._store_ndl_fulltext_hints(candidate, match)
            record_equivalent_pid_group(candidate)
            if candidate.ndl_matches:
                if all(match.metadata.get("source_mismatch") for match in candidate.ndl_matches):
                    candidate.verification_status = "source_mismatch"
                    candidate.notes.append("fulltext_multiplatform_recheck_no_plausible_match")
                else:
                    candidate.verification_status = "source_found"
                    candidate.notes.append("fulltext_multiplatform_recheck_found_candidate")
                    if not args.no_force_ndl_fulltext:
                        candidate.notes.append("ndl_fulltext_forced_during_pdf_recheck")
            else:
                candidate.verification_status = "source_not_found"
                candidate.notes.append("fulltext_multiplatform_recheck_no_results")
            candidate.artifacts["manual_search_recipe"] = build_manual_search_recipe(
                candidate.footnote,
                claim_text=source_claim_context_for_queries(candidate),
                current_status=candidate.verification_status,
            )
            recheck_result = candidate.to_dict()
            mismatch_results.append(recheck_result)
            write_outputs(
                json_path=json_path,
                markdown_path=markdown_path,
                args=args,
                combined=combined,
                download_selection_count=len(download_selection),
                mismatch_selection_count=len(mismatch_selection),
                progress_path=progress_path,
                download_results=download_results,
                rechecked_download_results=rechecked_download_results,
                mismatch_results=mismatch_results,
                non_ndl_sources=non_ndl_sources,
                alias_audits=alias_audits,
                timeout_events=timeout_events,
                execution_runs=execution_runs,
            )
            write_progress(
                progress_path,
                build_progress_event(
                    "candidate_completed",
                    phase="source_mismatch_recheck",
                    current=current,
                    total=len(mismatch_selection),
                    global_current=offset + 1,
                    global_total=len(source_results),
                    candidate_id=candidate.candidate_id,
                    footnote_id=candidate.footnote_id,
                    status=candidate.verification_status,
                    metrics={"match_count": len(candidate.ndl_matches or [])},
                ),
            )
            write_outputs(
                json_path=json_path,
                markdown_path=markdown_path,
                args=args,
                combined=combined,
                download_selection_count=len(download_selection),
                mismatch_selection_count=len(mismatch_selection),
                progress_path=progress_path,
                download_results=download_results,
                rechecked_download_results=rechecked_download_results,
                mismatch_results=mismatch_results,
                non_ndl_sources=non_ndl_sources,
                alias_audits=alias_audits,
                timeout_events=timeout_events,
                execution_runs=execution_runs,
            )

    if not args.skip_downloads and not args.skip_recheck_downloads:
        completed_download_offsets = completed_download_offset_set(
            [*download_results, *rechecked_download_results],
            retry_timeouts=args.retry_download_timeouts,
        )
        rechecked_download_items = [
            (offset, item)
            for item in mismatch_results
            if (offset := result_offset(item)) is not None
            and offset not in completed_download_offsets
            and item.get("verification_status") == "source_found"
            and has_downloadable_ndl_pid(item)
            and item_matches_exact_selection(
                item,
                candidate_ids=selected_candidate_ids,
                footnote_ids=selected_footnote_ids,
            )
        ]
        if args.recheck_download_start_index:
            rechecked_download_items = rechecked_download_items[max(args.recheck_download_start_index, 0) :]
        if args.max_recheck_downloads is not None:
            rechecked_download_items = rechecked_download_items[: max(args.max_recheck_downloads, 0)]
        for current, (offset, recheck_result) in enumerate(rechecked_download_items, start=1):
            candidate = candidate_from_dict(recheck_result)
            candidate.artifacts["refinement_offset"] = offset
            candidate.notes.append("download_after_source_recheck")
            write_progress(
                progress_path,
                build_progress_event(
                    "candidate_started",
                    phase="rechecked_download_ocr_alignment",
                    current=current,
                    total=len(rechecked_download_items),
                    global_current=offset + 1,
                    global_total=len(source_results),
                    candidate_id=candidate.candidate_id,
                    footnote_id=candidate.footnote_id,
                ),
            )
            download_result, timeout_event = run_download_ocr_alignment_with_timeout(
                candidate=candidate,
                source_item=recheck_result,
                output_dir=download_cache_dir,
                restricted_download=args.restricted_download,
                page_window=args.page_window,
                ocr_model=args.ocr_model,
                download_max_attempts=args.download_max_attempts,
                timeout_seconds=args.download_timeout_seconds,
                allow_external_ndl_fallback=not args.no_ndl_browser_fallback,
                prefer_ollama_review=args.prefer_ollama_review,
                progress_path=progress_path,
                progress_phase="rechecked_download_ocr_alignment",
                progress_current=current,
                progress_total=len(rechecked_download_items),
                progress_global_current=offset + 1,
                progress_global_total=len(source_results),
            )
            notes = download_result.setdefault("notes", [])
            if "download_after_source_recheck" not in notes:
                notes.append("download_after_source_recheck")
            rechecked_download_results.append(download_result)
            rechecked_download_results = dedupe_by_offset(rechecked_download_results)
            completed_download_offsets.add(offset)
            if timeout_event:
                timeout_event["phase"] = "rechecked_download_ocr_alignment"
                timeout_events = append_timeout_event(timeout_events, timeout_event)
                write_progress(progress_path, timeout_event)
            else:
                timeout_events = clear_resolved_timeout_events(timeout_events, download_result)
                write_progress(
                    progress_path,
                    build_progress_event(
                        "candidate_completed",
                        phase="rechecked_download_ocr_alignment",
                        current=current,
                        total=len(rechecked_download_items),
                        global_current=offset + 1,
                        global_total=len(source_results),
                        candidate_id=candidate.candidate_id,
                        footnote_id=candidate.footnote_id,
                        status=download_result.get("verification_status"),
                        metrics={"match_count": len(download_result.get("ndl_matches") or [])},
                    ),
                )
            write_outputs(
                json_path=json_path,
                markdown_path=markdown_path,
                args=args,
                combined=combined,
                download_selection_count=len(download_selection),
                mismatch_selection_count=len(mismatch_selection),
                progress_path=progress_path,
                download_results=download_results,
                rechecked_download_results=rechecked_download_results,
                mismatch_results=mismatch_results,
                non_ndl_sources=non_ndl_sources,
                alias_audits=alias_audits,
                timeout_events=timeout_events,
                execution_runs=execution_runs,
            )

    write_outputs(
        json_path=json_path,
        markdown_path=markdown_path,
        args=args,
        combined=combined,
        download_selection_count=len(download_selection),
        mismatch_selection_count=len(mismatch_selection),
        progress_path=progress_path,
        download_results=download_results,
        rechecked_download_results=rechecked_download_results,
        mismatch_results=mismatch_results,
        non_ndl_sources=non_ndl_sources,
        alias_audits=alias_audits,
        timeout_events=timeout_events,
        execution_runs=execution_runs,
    )
    print(json.dumps({"json_report": str(json_path.resolve()), "markdown_report": str(markdown_path.resolve())}, ensure_ascii=False, indent=2))
    if previous_force_fulltext is None:
        os.environ.pop("HISTORICAL_CITATION_FORCE_NDL_FULLTEXT", None)
    else:
        os.environ["HISTORICAL_CITATION_FORCE_NDL_FULLTEXT"] = previous_force_fulltext
    if previous_review_timeout is None:
        os.environ.pop("HISTORICAL_CITATION_REVIEW_TIMEOUT_SECONDS", None)
    else:
        os.environ["HISTORICAL_CITATION_REVIEW_TIMEOUT_SECONDS"] = previous_review_timeout
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
