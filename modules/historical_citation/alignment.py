from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .docx_parser import clean_text
from .evidence_cues import evidence_cue_matches, score_evidence_cues
from .ndl_search import normalize_match_text


PassageCandidate = Tuple[int, str, float]
AlignmentResult = Tuple[Optional[int], str, Optional[float], str]


def score_alignment_candidate(translation_text: str, segment: str) -> float:
    translation_norm = normalize_match_text(translation_text)
    segment_norm = normalize_match_text(segment)
    if not translation_norm or not segment_norm:
        return 0.0

    sequence_ratio = SequenceMatcher(None, translation_norm[:400], segment_norm[:400]).ratio()
    translation_han = set(re.findall(r"[\u3400-\u9fff]", translation_text))
    segment_han = set(re.findall(r"[\u3400-\u9fff]", segment))
    han_overlap = len(translation_han & segment_han) / max(1, len(translation_han))

    translation_bigrams = {
        translation_norm[index : index + 2]
        for index in range(max(0, len(translation_norm) - 1))
        if re.search(r"[\u3400-\u9fff]", translation_norm[index : index + 2])
    }
    segment_bigrams = {
        segment_norm[index : index + 2]
        for index in range(max(0, len(segment_norm) - 1))
        if re.search(r"[\u3400-\u9fff]", segment_norm[index : index + 2])
    }
    bigram_overlap = len(translation_bigrams & segment_bigrams) / max(1, len(translation_bigrams))

    cue_score = score_evidence_cues(translation_text, segment)

    return min(1.0, sequence_ratio * 0.20 + han_overlap * 0.35 + bigram_overlap * 0.25 + cue_score * 0.20)


def segment_page_text(text: str) -> List[str]:
    normalized = text.replace("\r", "\n")
    blocks = [block.strip() for block in re.split(r"\n{2,}", normalized) if block.strip()]
    if blocks:
        return blocks

    sentences = re.split(r"(?<=[。！？??])", normalized)
    grouped: List[str] = []
    buffer = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(buffer) + len(sentence) < 140:
            buffer += sentence
            continue
        if buffer:
            grouped.append(buffer)
        buffer = sentence
    if buffer:
        grouped.append(buffer)
    return grouped or [clean_text(text)]


def build_passage_candidates(
    translation_text: str,
    extracted_pages: Sequence[Tuple[int, str]],
) -> List[PassageCandidate]:
    passage_candidates: List[PassageCandidate] = []
    for page_number, page_text in extracted_pages:
        for segment in segment_page_text(page_text):
            if len(clean_text(segment)) >= 20:
                score = score_alignment_candidate(translation_text, segment)
                passage_candidates.append((page_number, segment, score))
    passage_candidates.sort(key=lambda item: item[2], reverse=True)
    return passage_candidates


def trim_aligned_segment(translation_text: str, segment: str) -> str:
    cleaned_segment = clean_text(re.split(r"E\d{6,}", segment, maxsplit=1)[0])
    if len(cleaned_segment) <= 260:
        return cleaned_segment

    best_text = cleaned_segment
    best_score = score_alignment_candidate(translation_text, cleaned_segment)
    window_size = 220
    step = 60
    for start in range(0, max(1, len(cleaned_segment) - window_size + 1), step):
        window = cleaned_segment[start : start + window_size]
        score = score_alignment_candidate(translation_text, window)
        if score > best_score:
            best_score = score
            best_text = window
    return best_text


def parse_llm_json(raw_content: str) -> Dict[str, Any]:
    content = raw_content.strip()
    fence_match = re.search(r"\{.*\}", content, re.DOTALL)
    if fence_match:
        content = fence_match.group(0)
    return json.loads(content)


def build_alignment_prompt(
    translation_text: str,
    shortlist: Sequence[PassageCandidate],
) -> Dict[str, Any]:
    return {
        "task": "你是史料引文核对助手。请从候选日文段落中选出最可能对应中文译文原句的段落。允许意译，不要求词面完全一致。若都不合适，请返回 best_index=0。只返回 JSON。",
        "output_schema": {
            "best_index": "整数，从 0 开始。0 表示没有合适候选；1 表示候选 1。",
            "confidence": "0 到 1 的小数",
            "reason": "一句话说明理由",
        },
        "translation": translation_text,
        "candidates": [
            {"index": idx + 1, "page": page_number, "text": segment}
            for idx, (page_number, segment, _score) in enumerate(shortlist)
        ],
    }


def align_translation(
    translation_text: str,
    extracted_pages: Sequence[Tuple[int, str]],
    *,
    llm_client: Any = None,
) -> AlignmentResult:
    passage_candidates = build_passage_candidates(translation_text, extracted_pages)
    if not passage_candidates:
        return None, "", None, "no_passage_candidates"

    if llm_client is None:
        best_page, best_segment, heuristic_score = passage_candidates[0]
        best_segment = trim_aligned_segment(translation_text, best_segment)
        return best_page, best_segment, round(heuristic_score, 4), "heuristic_alignment_used"

    shortlist = passage_candidates[:12]
    prompt = build_alignment_prompt(translation_text, shortlist)
    try:
        response = llm_client.chat(
            [{"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}],
            temperature=0.1,
            max_tokens=800,
        )
        parsed = parse_llm_json(response.get("content", ""))
    except Exception as exc:  # noqa: BLE001
        page_number, segment, heuristic_score = shortlist[0]
        segment = trim_aligned_segment(translation_text, segment)
        return page_number, segment, round(heuristic_score, 4), f"llm_alignment_failed: {exc}"

    try:
        best_index = int(str(parsed.get("best_index") or "0"))
    except (TypeError, ValueError):
        best_index = 0
    confidence = float(parsed.get("confidence", 0.0) or 0.0) if best_index else 0.0
    if best_index <= 0 or best_index > len(shortlist):
        reason = parsed.get("reason", "llm_rejected_candidates")
        return None, "", confidence, f"llm_rejected_candidates:{reason}"
    page_number, segment, heuristic_score = shortlist[best_index - 1]
    segment = trim_aligned_segment(translation_text, segment)
    if not confidence:
        confidence = round(heuristic_score, 4)
    return page_number, segment, confidence, parsed.get("reason", "")
