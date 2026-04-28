from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable

from .models import CitationCandidate


REFINED_STATUS_LABELS = {
    "matched": "已形成对照",
    "needs_manual_review": "待人工复核",
    "source_not_found": "NDL 未检到来源",
    "source_mismatch": "NDL 候选疑似误配",
    "source_unavailable": "可检索但当前不可下载",
    "restricted_download_failed": "受限下载失败",
    "page_mapping_unavailable": "页码映射未校准",
    "download_timeout": "下载或处理超时",
    "runner_failed": "续跑子进程异常",
    "ocr_failed": "OCR 失败",
    "alignment_failed": "对齐失败",
    "skipped_same_source_failed": "同源失败跳过",
    "download_failed": "下载失败",
    "unknown": "未知状态",
}

SUPPORT_STATUS_LABELS = {
    "direct_support": "可作为直接出处",
    "page_mismatch_but_support": "原文对应但脚注页码疑似不准",
    "partial_support": "部分对应或只能作背景材料",
    "not_supported": "未构成有效对应",
    "needs_manual_review": "需人工复核出处有效性",
    "unassessed": "尚未判断出处有效性",
}


def _join_notes(notes: Iterable[Any]) -> str:
    return " ; ".join(str(note) for note in notes if note is not None).lower()


def _notes_indicate_source_unavailable(joined_notes: str) -> bool:
    hard_unavailable_markers = (
        "remote_copy_only_no_print",
        "download_not_pdf",
        "download_http_404",
        "download_http_403",
        "print_button_not_found",
        "download_link_not_found",
    )
    if any(marker in joined_notes for marker in hard_unavailable_markers):
        return True
    page_mapping_markers = (
        "page_mapping_required_for_ndl_restricted_download",
        "mapped_footnote_page_out_of_scan_range",
        "source_pdf_rejected_adjusted_range",
        "restricted_download_range_adjusted",
    )
    page_mapping_blocked = any(marker in joined_notes for marker in page_mapping_markers)
    page_mapping_source_unavailable_markers = (
        "source_unavailable:no_digital_pid",
        "source_unavailable:mapped_page_out_of_scan_range",
        "source_unavailable:downloaded_page_range_adjusted",
    )
    if "source_unavailable:" in joined_notes and not any(
        marker in joined_notes for marker in page_mapping_source_unavailable_markers
    ):
        return True
    if (
        ("restricted_download_skipped_no_ndl_pid" in joined_notes or "source_unavailable:no_digital_pid" in joined_notes)
        and not page_mapping_blocked
    ):
        return True
    return False


def classify_status(verification_status: str, notes: Iterable[Any] = ()) -> str:
    status = verification_status or "unknown"
    joined_notes = _join_notes(notes)

    if _notes_indicate_source_unavailable(joined_notes):
        return "source_unavailable"

    if status in {"matched", "needs_manual_review", "source_not_found", "ocr_failed", "page_mapping_unavailable"}:
        return status
    if status == "download_failed":
        if (
            "page_mapping_required" in joined_notes
            or "verified_page_mapping" in joined_notes
            or "mapped_footnote_page_out_of_scan_range" in joined_notes
            or "source_pdf_rejected_adjusted_range" in joined_notes
            or "restricted_download_range_adjusted" in joined_notes
        ):
            return "page_mapping_unavailable"
        if "same_source" in joined_notes:
            return "skipped_same_source_failed"
        if "no ndl search results" in joined_notes:
            return "source_not_found"
        if "timeout" in joined_notes or "batch_controller_timeout" in joined_notes:
            return "download_timeout"
        if "batch_controller_resume_exit" in joined_notes:
            return "runner_failed"
        if (
            "restricted_download_failed" in joined_notes
            or "source_pdf_not_available" in joined_notes
            or "cannot open broken document" in joined_notes
            or "temp_pdf_2080" in joined_notes
        ):
            return "restricted_download_failed"
    return status


def classify_result_status(result: Dict[str, Any]) -> str:
    artifacts = result.get("artifacts") or {}
    status = str(result.get("verification_status") or "unknown")
    has_material_evidence = bool(
        result.get("matched_japanese")
        or artifacts.get("source_pdf")
        or artifacts.get("llm_review")
    )
    if has_material_evidence and status in {"matched", "needs_manual_review"}:
        return status

    availability = artifacts.get("source_availability") if isinstance(artifacts, dict) else None
    if isinstance(availability, dict) and availability.get("status") == "unavailable":
        current_source = artifacts.get("selected_source_match") or {}
        current_source_id = str(
            current_source.get("ndl_id")
            or current_source.get("platform_item_id")
            or current_source.get("url")
            or ""
        )
        availability_source_id = str(
            availability.get("source_id")
            or availability.get("ndl_id")
            or availability.get("platform_item_id")
            or availability.get("url")
            or ""
        )
        if current_source_id and availability_source_id and current_source_id != availability_source_id:
            return classify_status(status, result.get("notes") or ())
        page_mapping_blocked = bool(artifacts.get("page_mapping_required_but_unavailable"))
        if (
            availability.get("reason") in {"no_digital_pid", "mapped_page_out_of_scan_range", "downloaded_page_range_adjusted"}
            and page_mapping_blocked
            and artifacts.get("page_mapping_unavailable_ndl_ids")
        ):
            return classify_status(
                str(result.get("verification_status") or "unknown"),
                result.get("notes") or (),
            )
        return "source_unavailable"
    return classify_status(
        status,
        result.get("notes") or (),
    )


def classify_candidate_status(candidate: CitationCandidate) -> str:
    return classify_status(candidate.verification_status, candidate.notes)


def refined_status_label(status: str) -> str:
    return REFINED_STATUS_LABELS.get(status, status)


def support_status_label(status: str) -> str:
    return SUPPORT_STATUS_LABELS.get(status, status)


def candidate_support_status(candidate: CitationCandidate) -> str:
    return getattr(candidate, "support_status", None) or "unassessed"


def result_support_status(result: Dict[str, Any]) -> str:
    return str(result.get("support_status") or "unassessed")


def count_refined_result_statuses(results: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counter = Counter(classify_result_status(result) for result in results)
    return dict(counter)


def count_refined_candidate_statuses(candidates: Iterable[CitationCandidate]) -> Dict[str, int]:
    counter = Counter(classify_candidate_status(candidate) for candidate in candidates)
    return dict(counter)


def count_support_result_statuses(results: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counter = Counter(result_support_status(result) for result in results)
    return dict(counter)


def count_support_candidate_statuses(candidates: Iterable[CitationCandidate]) -> Dict[str, int]:
    counter = Counter(candidate_support_status(candidate) for candidate in candidates)
    return dict(counter)
