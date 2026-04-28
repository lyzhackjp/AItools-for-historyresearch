from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .docx_parser import clean_text
from .ndl_fulltext_context import (
    NDLFulltextHit,
    expand_ndl_snippet_context,
    fetch_ndl_digital_item,
    probe_ndl_fulltext_context,
)
from .ndl_search import normalize_match_text


@dataclass
class FulltextOcrCrossValidationResult:
    label: str
    paper_label: str
    candidate_id: str
    footnote_id: str
    mode: str
    source_title: str
    footnote_pages: List[int]
    pid: str
    ndl_title: str
    status: str
    conclusion: str
    queries_tried: List[str] = field(default_factory=list)
    selected_query: str = ""
    selected_pdf_page: Optional[int] = None
    selected_cid: str = ""
    hit_count: int = 0
    downloaded_page_range: List[int] = field(default_factory=list)
    matched_page: Optional[int] = None
    page_check: str = ""
    ocr_fulltext_similarity: Optional[float] = None
    ocr_excerpt: str = ""
    fulltext_excerpt: str = ""
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_checkpoint_candidate(checkpoint_path: Path, candidate_id: str) -> Dict[str, Any]:
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    results = payload.get("results") or {}
    if isinstance(results, dict):
        candidate = results.get(candidate_id)
    else:
        candidate = next((item for item in results if item.get("candidate_id") == candidate_id), None)
    if not candidate:
        raise KeyError(f"candidate_id not found in checkpoint: {candidate_id}")
    return candidate


def shorten_evidence_text(text: str, limit: int = 700) -> str:
    cleaned = clean_text(text or "")
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "..."


def normalized_text_similarity(left: str, right: str) -> Optional[float]:
    normalized_left = normalize_match_text(left or "")
    normalized_right = normalize_match_text(right or "")
    if not normalized_left or not normalized_right:
        return None
    if normalized_right in normalized_left or normalized_left in normalized_right:
        return 1.0
    return round(SequenceMatcher(None, normalized_left, normalized_right).ratio(), 4)


def select_fulltext_hit(
    hits: Sequence[NDLFulltextHit],
    *,
    preferred_page_range: Sequence[int] = (),
) -> Optional[NDLFulltextHit]:
    if not hits:
        return None
    if preferred_page_range:
        start = min(preferred_page_range)
        end = max(preferred_page_range)
        in_range = [hit for hit in hits if hit.pdf_page is not None and start <= hit.pdf_page <= end]
        if in_range:
            return in_range[0]
        midpoint = (start + end) / 2
        return min(
            hits,
            key=lambda hit: abs((hit.pdf_page if hit.pdf_page is not None else midpoint + 9999) - midpoint),
        )
    return hits[0]


def classify_fulltext_page_check(
    hit: Optional[NDLFulltextHit],
    downloaded_page_range: Sequence[int],
) -> str:
    if not hit or hit.pdf_page is None:
        return "no_pdf_page"
    if not downloaded_page_range:
        return "fulltext_pdf_page_only"
    start = min(downloaded_page_range)
    end = max(downloaded_page_range)
    if start <= hit.pdf_page <= end:
        return "fulltext_page_inside_downloaded_window"
    return "fulltext_page_outside_downloaded_window"


def cross_validate_fulltext_ocr_case(case: Dict[str, Any]) -> FulltextOcrCrossValidationResult:
    checkpoint_path = Path(case["checkpoint"])
    candidate = load_checkpoint_candidate(checkpoint_path, str(case["candidate_id"]))
    footnote = candidate.get("footnote") or {}
    artifacts = candidate.get("artifacts") or {}
    pid = str(case["pid"])
    queries = [str(item) for item in case.get("queries") or [] if str(item).strip()]
    probe = probe_ndl_fulltext_context(pid, queries)
    downloaded_range = [int(item) for item in artifacts.get("downloaded_page_range") or []]
    selected_hit = select_fulltext_hit(probe.hits, preferred_page_range=downloaded_range)
    expanded_text = ""
    notes: List[str] = []
    if selected_hit:
        item_payload = fetch_ndl_digital_item(pid)
        expanded = expand_ndl_snippet_context(
            pid,
            selected_hit,
            item_payload=item_payload,
            max_rounds=int(case.get("max_expand_rounds", 5)),
        )
        expanded_text = expanded.context_text
    ocr_text = candidate.get("matched_japanese") or ""
    similarity = normalized_text_similarity(ocr_text, expanded_text) if ocr_text and expanded_text else None
    mode = str(case.get("mode") or ("downloadable_ocr" if artifacts.get("source_pdf") else "fulltext_only"))
    page_status = classify_fulltext_page_check(selected_hit, downloaded_range)
    if mode == "downloadable_ocr":
        if page_status == "fulltext_page_inside_downloaded_window" and similarity is not None and similarity >= 0.2:
            status = "cross_validated"
            conclusion = "NDL 全文命中页落在已下载/OCR页窗内，且与 OCR 片段存在可见文本重合。"
        elif page_status == "fulltext_page_inside_downloaded_window":
            status = "page_cross_validated_text_needs_review"
            conclusion = "NDL 全文命中页落在已下载/OCR页窗内，但 OCR 与全文片段文本重合度偏低，需人工查看版面或 OCR。"
        else:
            status = "needs_review"
            conclusion = "NDL 全文命中未能与已下载/OCR页窗形成稳定交叉验证。"
    else:
        status = "fulltext_only_hit" if selected_hit else "no_fulltext_hit"
        conclusion = (
            "既有流程未取得 OCR，但 NDL 全文片段可定位到 PDF 页，可作为下载/OCR前的弱证据线索。"
            if selected_hit
            else "既有流程未取得 OCR，本轮 NDL 全文片段也未命中。"
        )
        if selected_hit and footnote.get("page_numbers"):
            notes.append("NDL 返回的是 PDF 页码，未经过书页映射，不能直接等同于脚注页码。")
    return FulltextOcrCrossValidationResult(
        label=str(case.get("label") or case["candidate_id"]),
        paper_label=str(case.get("paper_label") or ""),
        candidate_id=str(candidate.get("candidate_id") or case["candidate_id"]),
        footnote_id=str(candidate.get("footnote_id") or ""),
        mode=mode,
        source_title=str(footnote.get("title") or ""),
        footnote_pages=[int(item) for item in footnote.get("page_numbers") or []],
        pid=pid,
        ndl_title=probe.title,
        status=status,
        conclusion=conclusion,
        queries_tried=probe.queries_tried,
        selected_query=selected_hit.query if selected_hit else "",
        selected_pdf_page=selected_hit.pdf_page if selected_hit else None,
        selected_cid=selected_hit.cid if selected_hit else "",
        hit_count=len(probe.hits),
        downloaded_page_range=downloaded_range,
        matched_page=candidate.get("matched_page"),
        page_check=page_status,
        ocr_fulltext_similarity=similarity,
        ocr_excerpt=shorten_evidence_text(ocr_text),
        fulltext_excerpt=shorten_evidence_text(expanded_text or (selected_hit.snippet if selected_hit else "")),
        notes=notes,
    )


def cross_validate_fulltext_ocr_cases(cases: Sequence[Dict[str, Any]]) -> List[FulltextOcrCrossValidationResult]:
    return [cross_validate_fulltext_ocr_case(case) for case in cases]


def render_cross_validation_markdown(results: Sequence[FulltextOcrCrossValidationResult]) -> str:
    lines = [
        "# NDL 全文命中与 OCR 交叉验证小样本报告",
        "",
        "本报告用于测试 NDL 全文 SNIPPET 与既有下载/OCR结果的交叉验证能力。论文原文、OCR片段与全文片段均保留在本地 output 目录，不应上传 GitHub。",
        "",
        "## 摘要",
        "",
    ]
    for result in results:
        page = result.selected_pdf_page if result.selected_pdf_page is not None else "n/a"
        lines.append(
            f"- {result.paper_label} | {result.label} | {result.mode} | {result.status} | PID {result.pid} | PDF {page}"
        )
    for result in results:
        lines.extend(
            [
                "",
                f"## {result.paper_label} / {result.label}",
                "",
                f"- 候选 ID: {result.candidate_id}",
                f"- 脚注 ID: {result.footnote_id}",
                f"- 文献题名: {result.source_title}",
                f"- 脚注页码: {', '.join(str(item) for item in result.footnote_pages) or 'n/a'}",
                f"- 模式: {result.mode}",
                f"- NDL PID: {result.pid}",
                f"- NDL 题名: {result.ndl_title or 'n/a'}",
                f"- 查询词: {', '.join(result.queries_tried) or 'n/a'}",
                f"- 选中全文命中: query={result.selected_query or 'n/a'}; PDF页={result.selected_pdf_page or 'n/a'}; cid={result.selected_cid or 'n/a'}",
                f"- 已下载页窗: {result.downloaded_page_range or 'n/a'}",
                f"- 页码检查: {result.page_check}",
                f"- OCR/全文相似度: {result.ocr_fulltext_similarity if result.ocr_fulltext_similarity is not None else 'n/a'}",
                f"- 结论: {result.conclusion}",
            ]
        )
        if result.notes:
            lines.append(f"- 备注: {'; '.join(result.notes)}")
        if result.ocr_excerpt:
            lines.extend(["", "### OCR 片段", "", "```text", result.ocr_excerpt, "```"])
        if result.fulltext_excerpt:
            lines.extend(["", "### NDL 全文片段/接龙上下文", "", "```text", result.fulltext_excerpt, "```"])
    return "\n".join(lines) + "\n"
