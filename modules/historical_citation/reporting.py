from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from .download_index import refresh_download_range_index
from .models import CitationCandidate
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


def _current_evidence_status(result: Dict[str, Any]) -> str:
    artifacts = result.get("artifacts") or {}
    if result.get("matched_japanese"):
        llm_review = artifacts.get("llm_review") or {}
        provider = llm_review.get("provider") if isinstance(llm_review, dict) else None
        if provider:
            return f"ocr_aligned_with_{provider}_review"
        return "ocr_aligned"
    if artifacts.get("source_pdf"):
        return "pdf_acquired_without_alignment"
    availability = artifacts.get("source_availability") if isinstance(artifacts, dict) else None
    if isinstance(availability, dict) and availability.get("status") == "unavailable":
        return f"source_unavailable:{availability.get('reason') or 'unknown'}"
    if artifacts.get("page_mapping_required_but_unavailable"):
        return "page_mapping_blocked"
    return "no_current_evidence"


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
                lines.append(f"- [{platform}] {label} | score={match.score:.3f} | {match.url or '无链接'}")
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
        )
    ]
    if pending_items:
        lines.append("## 未覆盖或需复核")
        lines.append("")
        for item in pending_items:
            refined_status = classify_candidate_status(item)
            lines.append(
                f"- 脚注 {item.footnote_id} | {item.verification_status} / {refined_status} | "
                f"{item.footnote.title or item.footnote.text[:40]}"
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
            lines.append(
                f"- 脚注 {result.get('footnote_id')} | {status_label} | "
                f"{support_status_label(support_status)} | "
                f"{footnote.get('title') or footnote.get('text', '')[:40]}"
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
            lines.append(f"- 当前证据状态: {_current_evidence_status(result)}")
            support_status = result.get("support_status") or "unassessed"
            support_reason = result.get("support_reason") or ""
            evidence_scope = result.get("evidence_scope") or artifacts.get("alignment_scope") or ""
            lines.append(f"- 出处有效性: {support_status_label(support_status)} (`{support_status}`)")
            lines.append(f"- 有效性依据: {support_reason or '尚未生成'}")
            lines.append(f"- 证据范围: {evidence_scope or '未记录'}")
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
            if artifacts.get("mapped_footnote_pages"):
                mapped_pages = ", ".join(str(page) for page in artifacts["mapped_footnote_pages"])
                lines.append(f"- 双开页换算后的扫描页: {mapped_pages}")
            availability = artifacts.get("source_availability") or {}
            if isinstance(availability, dict) and availability.get("status") == "unavailable":
                reason = availability.get("reason") or "unknown"
                detail = availability.get("detail") or ""
                lines.append(f"- 来源可下载性: unavailable / {reason}{(' / ' + str(detail)) if detail else ''}")
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
            llm_runtime = artifacts.get("llm_review_runtime") or {}
            if isinstance(llm_runtime, dict) and llm_runtime:
                lines.append(
                    f"- 本地模型健康检查: {llm_runtime.get('provider')} "
                    f"available={llm_runtime.get('available')} "
                    f"model={llm_runtime.get('selected_model') or 'n/a'}"
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
            if ndl_matches:
                lines.append("**NDL 候选**")
                lines.append("")
                for match in ndl_matches[:3]:
                    label = match.get("title") or match.get("ndl_id") or "未命名"
                    score = match.get("score")
                    url = match.get("url") or ""
                    lines.append(f"- {label} | score={score} | {url}")
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
