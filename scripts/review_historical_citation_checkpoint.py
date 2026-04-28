from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import fields
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.historical_citation.llm_review import (  # noqa: E402
    OllamaChatClient,
    heuristic_review_alignment,
    review_alignment_with_llm,
)
from modules.historical_citation.models import CitationCandidate, NDLSearchMatch, ParsedFootnote  # noqa: E402
from modules.historical_citation.progress import ProgressReporter  # noqa: E402
from modules.historical_citation_verifier import HistoricalCitationVerifier  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review existing historical citation OCR alignments from a checkpoint."
    )
    parser.add_argument("checkpoint_file", help="Path to resume_checkpoint.json")
    parser.add_argument(
        "--output-checkpoint",
        default=None,
        help="Reviewed checkpoint output path. Defaults to llm_review_checkpoint.json next to the input.",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Update the input checkpoint in place instead of writing a separate reviewed checkpoint.",
    )
    parser.add_argument(
        "--report-path",
        default=None,
        help="Markdown report output path. Defaults to llm_review_report.md next to the checkpoint.",
    )
    parser.add_argument(
        "--provider",
        choices=("ollama", "heuristic"),
        default="ollama",
        help="Review backend. Ollama uses the local model server; heuristic is deterministic fallback.",
    )
    parser.add_argument("--model", default=None, help="Optional Ollama model name.")
    parser.add_argument("--timeout", type=int, default=180, help="Ollama request timeout in seconds.")
    parser.add_argument(
        "--title",
        action="append",
        default=[],
        help="Only review candidates whose footnote title contains this text. May be repeated.",
    )
    parser.add_argument(
        "--candidate-id",
        action="append",
        default=[],
        help="Only review this candidate id. May be repeated.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=None,
        help="Stop after reviewing this many candidates.",
    )
    parser.add_argument(
        "--progress-json",
        action="store_true",
        help="Emit JSONL progress events and periodic heartbeats for frontend/CLI monitors.",
    )
    parser.add_argument(
        "--progress-interval",
        type=float,
        default=30.0,
        help="Seconds between JSON heartbeat events when --progress-json is enabled.",
    )
    return parser


def _safe_dataclass_kwargs(cls: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {item.name for item in fields(cls)}
    return {key: value for key, value in (payload or {}).items() if key in allowed}


def candidate_from_result(result: Dict[str, Any]) -> CitationCandidate:
    footnote_payload = result.get("footnote") or {}
    footnote = ParsedFootnote(**_safe_dataclass_kwargs(ParsedFootnote, footnote_payload))
    candidate = CitationCandidate(
        candidate_id=str(result.get("candidate_id") or ""),
        paragraph_index=int(result.get("paragraph_index") or 0),
        paragraph_text=str(result.get("paragraph_text") or ""),
        translation_text=str(result.get("translation_text") or ""),
        footnote_id=str(result.get("footnote_id") or footnote.id),
        footnote=footnote,
    )
    candidate.ndl_matches = [
        NDLSearchMatch(**_safe_dataclass_kwargs(NDLSearchMatch, item))
        for item in (result.get("ndl_matches") or [])
        if isinstance(item, dict)
    ]
    candidate.verification_status = str(result.get("verification_status") or "parsed")
    candidate.matched_japanese = str(result.get("matched_japanese") or "")
    candidate.matched_page = result.get("matched_page")
    candidate.confidence = result.get("confidence")
    candidate.support_status = str(result.get("support_status") or "unassessed")
    candidate.support_reason = str(result.get("support_reason") or "")
    candidate.evidence_scope = str(result.get("evidence_scope") or "")
    candidate.notes = list(result.get("notes") or [])
    candidate.artifacts = dict(result.get("artifacts") or {})
    return candidate


def ordered_result_ids(checkpoint: Dict[str, Any]) -> List[str]:
    results = checkpoint.get("results") or {}
    seen = set()
    ordered: List[str] = []
    for candidate_id in checkpoint.get("processed_order") or []:
        if candidate_id in results and candidate_id not in seen:
            ordered.append(candidate_id)
            seen.add(candidate_id)
    for candidate_id in results:
        if candidate_id not in seen:
            ordered.append(candidate_id)
            seen.add(candidate_id)
    return ordered


def should_review(
    candidate_id: str,
    result: Dict[str, Any],
    *,
    candidate_ids: Sequence[str],
    title_filters: Sequence[str],
) -> bool:
    if candidate_ids and candidate_id not in set(candidate_ids):
        return False
    title = str((result.get("footnote") or {}).get("title") or "")
    if title_filters and not any(item in title for item in title_filters):
        return False
    return bool(result.get("matched_japanese") and result.get("translation_text"))


def preview(text: str, limit: int = 180) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def review_candidate(
    candidate: CitationCandidate,
    *,
    verifier: HistoricalCitationVerifier,
    provider: str,
    llm_client: Optional[Any],
) -> Dict[str, Any]:
    if provider == "ollama" and llm_client is not None:
        review = review_alignment_with_llm(
            candidate.translation_text,
            candidate.matched_japanese,
            llm_client=llm_client,
        )
    else:
        review = heuristic_review_alignment(candidate.translation_text, candidate.matched_japanese)
    review["reviewed_at"] = datetime.now().isoformat(timespec="seconds")
    candidate.artifacts["llm_review"] = review
    verifier._set_support_assessment(candidate)
    return review


def render_report(
    *,
    checkpoint_path: Path,
    output_checkpoint_path: Path,
    reviewed: List[Dict[str, Any]],
    skipped_count: int,
    provider: str,
    model: str,
    elapsed_seconds: float,
    title_filters: Sequence[str],
    candidate_ids: Sequence[str],
) -> str:
    decision_counts = Counter(item["review"].get("decision", "unknown") for item in reviewed)
    support_counts = Counter(item["candidate"].support_status for item in reviewed)
    by_title: Dict[str, Counter] = defaultdict(Counter)
    for item in reviewed:
        title = item["candidate"].footnote.title or "(untitled)"
        by_title[title][item["review"].get("decision", "unknown")] += 1

    lines = [
        "# 历史引文 OCR 对齐大模型复核报告",
        "",
        f"- 生成时间: {datetime.now().isoformat(timespec='seconds')}",
        f"- 输入 checkpoint: `{checkpoint_path.resolve()}`",
        f"- 输出 checkpoint: `{output_checkpoint_path.resolve()}`",
        f"- 复核后端: `{provider}`",
        f"- 模型: `{model or 'n/a'}`",
        f"- 已复核候选: {len(reviewed)}",
        f"- 总耗时: {elapsed_seconds:.1f} 秒",
        f"- 平均每候选耗时: {(elapsed_seconds / len(reviewed)):.1f} 秒" if reviewed else "- 平均每候选耗时: n/a",
        f"- 因无 OCR 片段或不符合筛选条件跳过: {skipped_count}",
    ]
    if title_filters:
        lines.append(f"- 文献筛选: {', '.join(title_filters)}")
    if candidate_ids:
        lines.append(f"- 候选 ID 筛选: {', '.join(candidate_ids)}")

    lines.extend(["", "## 判定分布", ""])
    for key, value in decision_counts.most_common():
        lines.append(f"- `{key}`: {value}")
    if not decision_counts:
        lines.append("- 无可复核候选")

    lines.extend(["", "## 出处有效性分布", ""])
    for key, value in support_counts.most_common():
        lines.append(f"- `{key}`: {value}")
    if not support_counts:
        lines.append("- 无可复核候选")

    lines.extend(["", "## 分文献结果", ""])
    for title, counts in sorted(by_title.items(), key=lambda item: (-sum(item[1].values()), item[0])):
        parts = ", ".join(f"{key}={value}" for key, value in counts.most_common())
        lines.append(f"- {title}: {parts}")
    if not by_title:
        lines.append("- 无可复核文献")

    lines.extend(["", "## 候选明细", ""])
    for item in reviewed:
        candidate = item["candidate"]
        review = item["review"]
        pages = ", ".join(str(page) for page in candidate.footnote.page_numbers or [])
        lines.extend(
            [
                f"### {candidate.candidate_id}",
                "",
                f"- 文献: {candidate.footnote.title or '(untitled)'}",
                f"- 脚注页码: {pages or 'n/a'}",
                f"- 当前状态: `{candidate.verification_status}` / `{candidate.support_status}`",
                f"- LLM 判定: `{review.get('decision', 'unknown')}`; confidence={review.get('confidence', 0)}",
                f"- 判定理由: {review.get('reason') or 'n/a'}",
                f"- 精确日文句: {preview(review.get('exact_sentence') or '') or 'n/a'}",
                f"- 论文侧句子预览: {preview(candidate.translation_text)}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    started_at = time.perf_counter()
    checkpoint_path = Path(args.checkpoint_file)
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

    if args.in_place:
        output_checkpoint_path = checkpoint_path
    elif args.output_checkpoint:
        output_checkpoint_path = Path(args.output_checkpoint)
    else:
        output_checkpoint_path = checkpoint_path.with_name("llm_review_checkpoint.json")
    report_path = Path(args.report_path) if args.report_path else checkpoint_path.with_name("llm_review_report.md")

    verifier = HistoricalCitationVerifier(enable_llm_review=False)
    llm_client = None
    model = ""
    if args.provider == "ollama":
        llm_client = OllamaChatClient(model=args.model, timeout=args.timeout)
        model = llm_client.model

    ordered_ids = ordered_result_ids(checkpoint)
    reviewable_ids = [
        candidate_id
        for candidate_id in ordered_ids
        if should_review(
            candidate_id,
            (checkpoint.get("results") or {}).get(candidate_id) or {},
            candidate_ids=args.candidate_id,
            title_filters=args.title,
        )
    ]
    if args.max_candidates is not None:
        reviewable_ids = reviewable_ids[: args.max_candidates]
    progress = ProgressReporter(enabled=args.progress_json, interval_seconds=args.progress_interval)
    progress.event(
        "llm_review_started",
        provider=args.provider,
        model=model,
        total=len(reviewable_ids),
        checkpoint=str(checkpoint_path.resolve()),
    )

    reviewed: List[Dict[str, Any]] = []
    skipped_count = 0
    results = checkpoint.setdefault("results", {})
    for candidate_id in ordered_ids:
        result = results.get(candidate_id) or {}
        if not should_review(
            candidate_id,
            result,
            candidate_ids=args.candidate_id,
            title_filters=args.title,
        ):
            skipped_count += 1
            continue
        candidate = candidate_from_result(result)
        progress.update(
            phase="llm_review",
            current=len(reviewed) + 1,
            total=len(reviewable_ids),
            candidate_id=candidate_id,
            footnote_id=candidate.footnote_id,
            title=candidate.footnote.title,
        )
        progress.event("candidate_review_started")
        review = review_candidate(
            candidate,
            verifier=verifier,
            provider=args.provider,
            llm_client=llm_client,
        )
        results[candidate_id] = candidate.to_dict()
        reviewed.append({"candidate": candidate, "review": review})
        print(
            json.dumps(
                {
                    "event": "candidate_reviewed",
                    "candidate_id": candidate_id,
                    "decision": review.get("decision"),
                    "support_status": candidate.support_status,
                    "reviewed": len(reviewed),
                    "total": len(reviewable_ids),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        progress.event(
            "candidate_review_finished",
            decision=review.get("decision"),
            support_status=candidate.support_status,
            confidence=review.get("confidence"),
        )
        if args.max_candidates is not None and len(reviewed) >= args.max_candidates:
            break

    elapsed_seconds = time.perf_counter() - started_at
    checkpoint["updated_at"] = datetime.now().isoformat(timespec="seconds")
    checkpoint["llm_review"] = {
        "provider": args.provider,
        "model": model,
        "reviewed_at": checkpoint["updated_at"],
        "reviewed_candidates": [item["candidate"].candidate_id for item in reviewed],
    }
    output_checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    output_checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")

    report = render_report(
        checkpoint_path=checkpoint_path,
        output_checkpoint_path=output_checkpoint_path,
        reviewed=reviewed,
        skipped_count=skipped_count,
        provider=args.provider,
        model=model,
        elapsed_seconds=elapsed_seconds,
        title_filters=args.title,
        candidate_ids=args.candidate_id,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    print(
        json.dumps(
            {
                "reviewed_candidates": len(reviewed),
                "skipped_candidates": skipped_count,
                "provider": args.provider,
                "model": model,
                "elapsed_seconds": round(elapsed_seconds, 1),
                "seconds_per_candidate": round(elapsed_seconds / len(reviewed), 1) if reviewed else None,
                "output_checkpoint": str(output_checkpoint_path.resolve()),
                "report": str(report_path.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    progress.event(
        "llm_review_finished",
        reviewed_candidates=len(reviewed),
        skipped_candidates=skipped_count,
        elapsed_seconds=round(elapsed_seconds, 1),
    )
    progress.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
