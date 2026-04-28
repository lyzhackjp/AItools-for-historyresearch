from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.historical_citation.reporting import (
    build_artifact_summary,
    render_resume_markdown_report,
    summarize_checkpoint,
)
from modules.historical_citation.models import NDLSearchMatch
from modules.historical_citation.progress import ProgressReporter
from modules.historical_citation_verifier import HistoricalCitationVerifier


DOWNLOAD_FAILURE_CACHE_FILENAME = "download_failure_cache.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resume historical citation verification with candidate-level checkpoints."
    )
    parser.add_argument("docx_path", help="Path to the input .docx paper")
    parser.add_argument(
        "--output-dir",
        default="output/historical_citation_resume",
        help="Directory for checkpoint, reports, and downloaded artifacts",
    )
    parser.add_argument(
        "--checkpoint-file",
        default=None,
        help="Optional explicit checkpoint JSON path",
    )
    parser.add_argument(
        "--max-search-results",
        type=int,
        default=3,
        help="Maximum number of NDL candidates per citation",
    )
    parser.add_argument(
        "--page-window",
        type=int,
        default=4,
        help="How many pages around the cited page to inspect and keep as OCR context",
    )
    parser.add_argument(
        "--ocr-model",
        default="ndlocr_lite",
        help="OCR model to use when page text must be extracted from images",
    )
    parser.add_argument(
        "--ocr-page-window",
        type=int,
        default=None,
        help="Optional smaller page window for OCR/context extraction. Defaults to --page-window.",
    )
    parser.add_argument(
        "--download-max-attempts",
        type=int,
        default=3,
        help="Maximum restricted-download attempts per request. Use 1 for fast candidate probes.",
    )
    parser.add_argument(
        "--ignore-download-failure-cache",
        action="store_true",
        help="Retry downloads even when this candidate/page window is already in the local failure cache.",
    )
    parser.add_argument(
        "--stop-after",
        type=int,
        default=None,
        help="Process at most this many remaining candidates in this run",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Only generate reports from the current checkpoint/artifacts without processing more candidates",
    )
    parser.add_argument(
        "--retry-status",
        action="append",
        default=[],
        help="Re-process checkpointed candidates with this verification status. May be passed multiple times.",
    )
    parser.add_argument(
        "--only-candidate-id",
        action="append",
        default=[],
        help="Only process the given candidate id. Existing checkpoint entries for these ids are retried.",
    )
    parser.add_argument(
        "--skip-candidate-id",
        action="append",
        default=[],
        help="Mark the given candidate id as download_failed so later resume runs can move past it.",
    )
    parser.add_argument(
        "--skip-reason",
        default="manually_skipped_blocking_candidate",
        help="Note to attach when --skip-candidate-id is used.",
    )
    parser.add_argument(
        "--platform",
        action="append",
        default=[],
        help="Source platform to search. May be repeated. Defaults to NDL for resume compatibility.",
    )
    parser.add_argument(
        "--no-ndl-browser-fallback",
        action="store_true",
        help="Use NDL public API only during metadata search; skip slow Selenium/browser fallback search.",
    )
    parser.add_argument(
        "--search-only",
        action="store_true",
        help="Only search source metadata and write checkpoints; skip restricted download, page mapping, OCR, and alignment.",
    )
    parser.add_argument(
        "--no-llm-review",
        action="store_true",
        help="Disable the precision LLM review step after OCR alignment.",
    )
    parser.add_argument(
        "--ollama-review",
        action="store_true",
        help="Use local Ollama for the precision LLM review step when available.",
    )
    parser.add_argument(
        "--progress-json",
        action="store_true",
        help="Emit JSONL progress events for CLI monitors or future frontend progress views.",
    )
    parser.add_argument(
        "--progress-interval",
        type=float,
        default=30.0,
        help="Seconds between JSON heartbeat events when --progress-json is enabled.",
    )
    parser.add_argument(
        "--progress-file",
        default=None,
        help="Optional JSONL file path for progress events. Implies --progress-json.",
    )
    return parser


def load_checkpoint(checkpoint_path: Path) -> Dict[str, Any]:
    if checkpoint_path.exists():
        return json.loads(checkpoint_path.read_text(encoding="utf-8"))
    return {
        "document": {},
        "processed_order": [],
        "results": {},
        "artifacts": {},
        "updated_at": None,
    }


def save_checkpoint(checkpoint_path: Path, checkpoint: Dict[str, Any]) -> None:
    checkpoint["updated_at"] = datetime.now().isoformat(timespec="seconds")
    checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")


def load_download_failure_cache(output_dir: Path) -> Dict[str, Any]:
    cache_path = output_dir / DOWNLOAD_FAILURE_CACHE_FILENAME
    if not cache_path.exists():
        return {"failures": {}}
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"failures": {}}
    if not isinstance(payload, dict):
        return {"failures": {}}
    payload.setdefault("failures", {})
    return payload


def save_download_failure_cache(output_dir: Path, cache: Dict[str, Any]) -> None:
    cache["updated_at"] = datetime.now().isoformat(timespec="seconds")
    (output_dir / DOWNLOAD_FAILURE_CACHE_FILENAME).write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def candidate_download_cache_keys(candidate) -> List[str]:
    pages = ",".join(str(page) for page in (candidate.footnote.page_numbers or [1]))
    keys = [f"candidate:{candidate.candidate_id}"]
    attempted_ndl_ids = [
        str(ndl_id)
        for ndl_id in (candidate.artifacts.get("download_attempted_ndl_ids") or [])
        if ndl_id
    ]
    ndl_ids = attempted_ndl_ids or [
        str(getattr(match, "ndl_id", ""))
        for match in candidate.ndl_matches[:3]
        if getattr(match, "ndl_id", None)
    ]
    for ndl_id in ndl_ids:
        keys.append(f"ndl:{ndl_id}:remote_copy_only")
        keys.append(f"ndl:{ndl_id}:pages:{pages}")
    downloaded_range = candidate.artifacts.get("downloaded_page_range")
    if isinstance(downloaded_range, list) and len(downloaded_range) == 2:
        for ndl_id in ndl_ids:
            keys.append(f"ndl:{ndl_id}:range:{downloaded_range[0]}-{downloaded_range[1]}")
    return keys


def find_cached_download_failure(candidate, cache: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    failures = cache.get("failures", {})
    for key in candidate_download_cache_keys(candidate):
        failure = failures.get(key)
        if failure:
            return {"key": key, **failure}
    return None


def remember_download_failure(candidate, cache: Dict[str, Any]) -> None:
    failures = cache.setdefault("failures", {})
    notes = [str(note) for note in (candidate.notes or [])]
    note_blob = "\n".join(notes)
    record = {
        "candidate_id": candidate.candidate_id,
        "status": candidate.verification_status,
        "downloaded_page_range": candidate.artifacts.get("downloaded_page_range"),
        "note_tail": notes[-5:],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    for key in candidate_download_cache_keys(candidate):
        if key.endswith(":remote_copy_only") and "remote_copy_only_no_print" not in note_blob:
            continue
        failures[key] = record


def seed_download_failure_cache_from_checkpoint(
    checkpoint: Dict[str, Any],
    candidate_by_id: Dict[str, Any],
    cache: Dict[str, Any],
) -> bool:
    changed = False
    download_markers = (
        "source_pdf_not_available",
        "restricted_download_failed",
        "download_fast_failed",
        "pdf_low_resolution_for_ocr",
        "download_not_pdf",
        "presigned_not_pdf",
    )
    for candidate_id, result in checkpoint.get("results", {}).items():
        if result.get("verification_status") != "download_failed":
            continue
        note_blob = "\n".join(str(note) for note in (result.get("notes") or []))
        if not any(marker in note_blob for marker in download_markers):
            continue
        candidate = candidate_by_id.get(candidate_id)
        if candidate is None:
            continue
        hydrate_candidate_from_checkpoint(candidate, result)
        before = len(cache.get("failures", {}))
        remember_download_failure(candidate, cache)
        changed = changed or len(cache.get("failures", {})) != before
    return changed


def hydrate_candidate_from_checkpoint(candidate, result: Dict[str, Any]) -> None:
    candidate.ndl_matches = [
        NDLSearchMatch(**match)
        for match in result.get("ndl_matches", [])
        if isinstance(match, dict)
    ]
    candidate.verification_status = result.get("verification_status", candidate.verification_status)
    candidate.matched_japanese = result.get("matched_japanese", candidate.matched_japanese)
    candidate.matched_page = result.get("matched_page", candidate.matched_page)
    candidate.confidence = result.get("confidence", candidate.confidence)
    candidate.support_status = result.get("support_status", getattr(candidate, "support_status", "unassessed"))
    candidate.support_reason = result.get("support_reason", getattr(candidate, "support_reason", ""))
    candidate.evidence_scope = result.get("evidence_scope", getattr(candidate, "evidence_scope", ""))
    candidate.notes = list(result.get("notes", []) or [])
    candidate.artifacts = dict(result.get("artifacts", {}) or {})


def clear_explicit_retry_control_state(candidate) -> None:
    """Reset per-attempt fallback controls when the user explicitly retries a candidate."""

    for key in (
        "alternate_source_retry_count",
        "source_match_skip_ids",
        "source_match_skipped_ids",
        "download_fast_failure",
    ):
        candidate.artifacts.pop(key, None)
    candidate.notes = [
        note
        for note in (candidate.notes or [])
        if not str(note).startswith("alternate_source_retry_after_weak_alignment:")
        and not str(note).startswith("download_fast_failed:")
    ]


def clear_source_refresh_state(candidate) -> None:
    """Remove stale download/OCR evidence before replacing source matches."""

    for key in (
        "alignment_scope",
        "citation_priority_pages",
        "cited_extracted_pages",
        "context_alignment_preview",
        "direct_extracted_pages",
        "subprocess_extracted_pages",
        "extracted_page_texts",
        "matched_scan_page",
        "matched_book_pages",
        "page_distance_from_citation",
        "review_context_window",
        "review_context",
        "llm_review",
        "page_label_mode",
        "pdf_readiness",
        "ocr_backend_available",
        "source_pdf",
        "selected_source_match",
        "page_mapping",
        "mapped_footnote_pages",
        "downloaded_page_range",
        "download_attempt",
        "download_attempted_ndl_ids",
        "source_attempts",
        "source_unavailable_attempts",
        "source_availability",
        "source_match_skip_ids",
        "source_match_skipped_ids",
        "alternate_source_retry_count",
        "download_fast_failure",
    ):
        candidate.artifacts.pop(key, None)
    candidate.matched_page = None
    candidate.matched_japanese = ""
    candidate.confidence = None
    candidate.support_status = "unassessed"
    candidate.support_reason = ""
    candidate.evidence_scope = ""
    candidate.notes = []


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = Path(args.checkpoint_file) if args.checkpoint_file else output_dir / "resume_checkpoint.json"

    verifier = HistoricalCitationVerifier(
        allow_external_ndl_fallback=not args.no_ndl_browser_fallback,
        enable_llm_review=not args.no_llm_review,
        prefer_ollama_review=args.ollama_review,
    )
    parsed = verifier.parse_docx(args.docx_path)
    candidates = verifier.build_candidates(parsed["paragraphs"], parsed["footnotes"])
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    progress_stream = None
    if args.progress_file:
        progress_path = Path(args.progress_file)
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        progress_stream = progress_path.open("a", encoding="utf-8")
    progress = ProgressReporter(
        enabled=args.progress_json or bool(args.progress_file),
        interval_seconds=args.progress_interval,
        stream=progress_stream,
    )

    checkpoint = load_checkpoint(checkpoint_path)
    download_failure_cache = load_download_failure_cache(output_dir)
    if seed_download_failure_cache_from_checkpoint(checkpoint, candidate_by_id, download_failure_cache):
        save_download_failure_cache(output_dir, download_failure_cache)
    checkpoint["document"] = parsed["document"]
    checkpoint["artifacts"] = build_artifact_summary(output_dir)

    for candidate_id in args.skip_candidate_id or []:
        candidate = candidate_by_id.get(candidate_id)
        if candidate is None:
            continue
        candidate.verification_status = "download_failed"
        candidate.notes.append(args.skip_reason)
        checkpoint["results"][candidate_id] = candidate.to_dict()
        if candidate_id not in checkpoint.setdefault("processed_order", []):
            checkpoint["processed_order"].append(candidate_id)

    retry_statuses = set(args.retry_status or [])
    target_candidate_ids = set(args.only_candidate_id or [])
    retry_candidate_ids = set()
    if retry_statuses or target_candidate_ids:
        for candidate_id, result in list(checkpoint.get("results", {}).items()):
            if target_candidate_ids and candidate_id not in target_candidate_ids:
                continue
            should_retry = (
                result.get("verification_status") in retry_statuses
                if retry_statuses
                else bool(target_candidate_ids)
            )
            if should_retry:
                retry_candidate_ids.add(candidate_id)

    candidate_pool = [
        candidate for candidate in candidates if not target_candidate_ids or candidate.candidate_id in target_candidate_ids
    ]
    processed_ids = set(checkpoint.get("results", {}).keys()) - retry_candidate_ids
    remaining_candidates = [candidate for candidate in candidate_pool if candidate.candidate_id not in processed_ids]
    progress.event(
        "resume_started",
        total_candidates=len(candidates),
        target_candidates=len(candidate_pool),
        remaining_candidates=len(remaining_candidates),
        checkpoint=str(checkpoint_path.resolve()),
        llm_review_enabled=not args.no_llm_review,
        ollama_review=args.ollama_review,
    )

    if not args.report_only:
        processed_now = 0
        platform_names = args.platform or ["ndl"]
        for candidate in remaining_candidates:
            progress.update(
                phase="candidate",
                current=processed_now + 1,
                total=len(remaining_candidates),
                candidate_id=candidate.candidate_id,
                footnote_id=candidate.footnote_id,
                title=candidate.footnote.title,
            )
            progress.event(
                "candidate_started",
                page_numbers=candidate.footnote.page_numbers,
            )
            checkpoint_result = checkpoint.get("results", {}).get(candidate.candidate_id)
            if checkpoint_result:
                hydrate_candidate_from_checkpoint(candidate, checkpoint_result)
                if candidate.candidate_id in retry_candidate_ids:
                    clear_explicit_retry_control_state(candidate)
            if not candidate.ndl_matches or args.search_only:
                if args.search_only:
                    clear_source_refresh_state(candidate)
                progress.update(phase="source_search")
                progress.event("source_search_started")
                candidate.ndl_matches = verifier.search_sources(
                    candidate.footnote,
                    max_results=args.max_search_results,
                    platform_names=platform_names,
                )
                progress.event("source_search_finished", match_count=len(candidate.ndl_matches))
            if candidate.ndl_matches:
                if all(match.metadata.get("source_mismatch") for match in candidate.ndl_matches):
                    candidate.verification_status = "source_mismatch"
                    candidate.notes.append("all_source_candidates_failed_metadata_filter")
                else:
                    candidate.verification_status = "source_found"
                if candidate.verification_status != "source_mismatch" and not args.search_only:
                    existing_pdf = candidate.artifacts.get("source_pdf")
                    has_existing_pdf = bool(existing_pdf and verifier._is_usable_pdf(existing_pdf))
                    cached_failure = None
                    if not args.ignore_download_failure_cache and not has_existing_pdf:
                        cached_failure = find_cached_download_failure(candidate, download_failure_cache)

                    mapping = None
                    if cached_failure:
                        candidate.verification_status = "download_failed"
                        candidate.artifacts["download_fast_failure"] = cached_failure
                        candidate.notes.append(f"download_fast_failed:{cached_failure.get('key')}")
                    elif not has_existing_pdf:
                        progress.update(phase="page_mapping")
                        progress.event("page_mapping_started")
                        mapping = verifier._estimate_scan_page_range(
                            candidate,
                            output_dir=output_dir,
                            restricted_download=True,
                            page_window=args.page_window,
                        )
                        progress.event(
                            "page_mapping_finished",
                            mapped=bool(mapping),
                            ndl_id=(mapping or {}).get("ndl_id") if isinstance(mapping, dict) else None,
                        )
                    if mapping and not cached_failure:
                        candidate.artifacts["page_mapping"] = mapping
                        candidate.artifacts["mapped_footnote_pages"] = [
                            scan_page
                            for scan_page in (
                                verifier._estimate_scan_page_for_book_page(mapping, page)
                                for page in candidate.footnote.page_numbers
                            )
                            if scan_page is not None
                        ]
                    if not cached_failure:
                        progress.update(phase="download_ocr_alignment")
                        progress.event("download_ocr_alignment_started")
                        verifier._enrich_with_source_excerpt(
                            candidate,
                            output_dir=output_dir,
                            restricted_download=True,
                            page_window=args.ocr_page_window
                            if args.ocr_page_window is not None
                            else args.page_window,
                            ocr_model=args.ocr_model,
                            download_max_attempts=args.download_max_attempts,
                        )
                        progress.event(
                            "download_ocr_alignment_finished",
                            verification_status=candidate.verification_status,
                            support_status=candidate.support_status,
                            confidence=candidate.confidence,
                            llm_provider=(candidate.artifacts.get("llm_review") or {}).get("provider"),
                            llm_success=(candidate.artifacts.get("llm_review") or {}).get("llm_review_success"),
                            llm_fallback=(candidate.artifacts.get("llm_review") or {}).get("llm_review_fallback_heuristic"),
                        )
                        if candidate.verification_status == "download_failed":
                            remember_download_failure(candidate, download_failure_cache)
                            save_download_failure_cache(output_dir, download_failure_cache)
            else:
                candidate.verification_status = "source_not_found"

            checkpoint["results"][candidate.candidate_id] = candidate.to_dict()
            checkpoint.setdefault("processed_order", []).append(candidate.candidate_id)
            checkpoint["artifacts"] = build_artifact_summary(output_dir)
            save_checkpoint(checkpoint_path, checkpoint)
            progress.event(
                "candidate_finished",
                verification_status=candidate.verification_status,
                support_status=candidate.support_status,
                confidence=candidate.confidence,
                evidence_status=(
                    "ocr_aligned" if candidate.matched_japanese else
                    "pdf_acquired" if candidate.artifacts.get("source_pdf") else
                    "no_current_evidence"
                ),
            )

            processed_now += 1
            if args.stop_after is not None and processed_now >= args.stop_after:
                break

    checkpoint["artifacts"] = build_artifact_summary(output_dir)
    save_checkpoint(checkpoint_path, checkpoint)

    report_path = output_dir / "partial_resume_report.md"
    report_path.write_text(
        render_resume_markdown_report(
            document=parsed["document"],
            checkpoint=checkpoint,
            total_candidates=len(candidates),
            output_dir=output_dir,
        ),
        encoding="utf-8",
    )

    summary = summarize_checkpoint(checkpoint, total_candidates=len(candidates))
    progress.event("resume_finished", **summary)
    progress.close()
    if progress_stream is not None:
        progress_stream.close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"checkpoint: {checkpoint_path.resolve()}")
    print(f"report: {report_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
