from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .reporting import render_resume_markdown_report
from .source_graph import dedupe_result_dicts
from .status import classify_result_status


def load_json_payload(path: str | Path) -> Dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def summarize_result_dicts(results: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counter = Counter(classify_result_status(result) for result in results)
    summary: Dict[str, int] = {
        "total_candidates": len(results),
        "source_found": 0,
        "source_not_found": 0,
        "source_mismatch": 0,
        "matched": 0,
        "needs_manual_review": 0,
        "download_failed": 0,
        "ocr_failed": 0,
        "page_mapping_unavailable": 0,
    }
    for result in results:
        status = str(result.get("verification_status") or "unknown")
        if result.get("ndl_matches") and status != "source_mismatch":
            summary["source_found"] += 1
        if status in summary and status != "source_found":
            summary[status] += 1
    for status, count in counter.items():
        summary[f"refined:{status}"] = count
    return summary


def _result_sort_key(item: Dict[str, Any]) -> tuple[int, str]:
    artifacts = item.get("artifacts") or {}
    offset = artifacts.get("refinement_offset")
    try:
        return int(offset), str(item.get("candidate_id") or "")
    except (TypeError, ValueError):
        pass
    candidate_id = str(item.get("candidate_id") or "")
    digits = "".join(ch if ch.isdigit() else " " for ch in candidate_id).split()
    first_number = int(digits[0]) if digits else 999999
    return first_number, candidate_id


def merge_result_payloads(payloads: Iterable[Dict[str, Any]], *, paper_id: str = "") -> Dict[str, Any]:
    payload_list = [payload for payload in payloads if isinstance(payload, dict)]
    if not payload_list:
        return {"document": {}, "summary": summarize_result_dicts([]), "results": []}
    document = next((payload.get("document") for payload in payload_list if payload.get("document")), {}) or {}
    pdf_parse_debug: List[Any] = []
    results: List[Dict[str, Any]] = []
    for payload in payload_list:
        for item in payload.get("pdf_parse_debug") or []:
            if item not in pdf_parse_debug:
                pdf_parse_debug.append(item)
        results.extend([item for item in payload.get("results") or [] if isinstance(item, dict)])
    deduped = dedupe_result_dicts(sorted(results, key=_result_sort_key), paper_id=paper_id)
    candidate_batch = {
        "total_candidates": len(deduped),
        "processed_candidates": len(deduped),
        "duplicate_candidate_count": max(0, len(results) - len(deduped)),
        "finalized_from_payload_count": len(payload_list),
    }
    return {
        "document": document,
        "summary": summarize_result_dicts(deduped),
        "candidate_batch": candidate_batch,
        "pdf_parse_debug": pdf_parse_debug,
        "results": deduped,
    }


def partial_payload_is_complete(payload: Dict[str, Any]) -> bool:
    results = payload.get("results") or []
    batch = payload.get("candidate_batch") or {}
    if not isinstance(results, list) or not results:
        return False
    total = batch.get("total_candidates")
    processed = batch.get("processed_candidates")
    try:
        total_int = int(total)
    except (TypeError, ValueError):
        total_int = 0
    try:
        processed_int = int(processed)
    except (TypeError, ValueError):
        processed_int = len(results)
    if total_int:
        return len(results) >= total_int or processed_int >= total_int
    return bool(results)


def finalize_partial_payload(
    partial_payload: Dict[str, Any],
    *,
    output_dir: str | Path,
    paper_id: str = "",
    require_complete: bool = False,
) -> Dict[str, Any]:
    if require_complete and not partial_payload_is_complete(partial_payload):
        raise ValueError("partial payload is not complete")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    finalized = merge_result_payloads([partial_payload], paper_id=paper_id)
    finalized["finalizer"] = {
        "source": "partial_payload",
        "partial_complete": partial_payload_is_complete(partial_payload),
        "require_complete": require_complete,
    }
    json_path = output_path / "verification_results.json"
    markdown_path = output_path / "verification_report.md"
    json_path.write_text(json.dumps(finalized, ensure_ascii=False, indent=2), encoding="utf-8")
    checkpoint = {
        "results": {
            str(index): item
            for index, item in enumerate(finalized.get("results") or [])
        },
        "artifacts": {},
    }
    markdown_path.write_text(
        render_resume_markdown_report(
            document=finalized.get("document") or {},
            checkpoint=checkpoint,
            total_candidates=len(finalized.get("results") or []),
            output_dir=output_path,
        ),
        encoding="utf-8",
    )
    finalized["artifacts"] = {
        "json_report": str(json_path.resolve()),
        "markdown_report": str(markdown_path.resolve()),
    }
    return finalized


def finalize_partial_file(
    partial_json_path: str | Path,
    *,
    output_dir: Optional[str | Path] = None,
    paper_id: str = "",
    require_complete: bool = False,
) -> Dict[str, Any]:
    partial_path = Path(partial_json_path)
    payload = load_json_payload(partial_path)
    target_dir = Path(output_dir) if output_dir else partial_path.parent
    return finalize_partial_payload(
        payload,
        output_dir=target_dir,
        paper_id=paper_id,
        require_complete=require_complete,
    )
