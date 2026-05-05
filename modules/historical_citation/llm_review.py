from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

from .alignment import evidence_cue_matches, parse_llm_json, score_alignment_candidate, score_evidence_cues
from .docx_parser import clean_text


REVIEW_DECISIONS = {"direct_support", "partial_support", "not_supported", "uncertain"}
FORMAL_REVIEW_PREFERRED_MODEL_MARKERS = ("gemma", "deepseek")
DEFAULT_OLLAMA_REVIEW_TIMEOUT_SECONDS = 300
DEFAULT_OLLAMA_MODEL_POLICY_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "historical_citation_ollama_model_policy.json"
)


def _split_model_markers(raw_value: str) -> List[str]:
    return [item.strip().lower() for item in str(raw_value or "").split(",") if item.strip()]


def _model_matches_marker(model: str, markers: Iterable[str]) -> bool:
    lowered = str(model or "").lower()
    return any(marker and marker in lowered for marker in markers)


def is_preferred_review_model(model: str) -> bool:
    return _model_matches_marker(model, FORMAL_REVIEW_PREFERRED_MODEL_MARKERS)


def _configured_ollama_timeout(explicit_timeout: Optional[int] = None) -> int:
    if explicit_timeout is not None:
        try:
            return max(1, int(explicit_timeout))
        except (TypeError, ValueError):
            return DEFAULT_OLLAMA_REVIEW_TIMEOUT_SECONDS
    raw_timeout = os.environ.get("HISTORICAL_CITATION_REVIEW_TIMEOUT_SECONDS")
    if raw_timeout:
        try:
            return max(1, int(raw_timeout))
        except (TypeError, ValueError):
            return DEFAULT_OLLAMA_REVIEW_TIMEOUT_SECONDS
    return DEFAULT_OLLAMA_REVIEW_TIMEOUT_SECONDS


def split_review_sentences(text: str, *, limit: int = 12) -> List[str]:
    normalized = str(text or "").replace("\r", "\n")
    sentences: List[str] = []
    buffer = ""
    min_chars = 4
    sentence_breaks = {chr(codepoint) for codepoint in (0x3002, 0xff0e, 0x002e, 0x0021, 0xff01, 0x003f, 0xff1f)}
    for char in normalized:
        if char == "\n":
            cleaned = clean_text(buffer)
            if len(cleaned) >= min_chars and cleaned not in sentences:
                sentences.append(cleaned)
            buffer = ""
            continue
        buffer += char
        if char in sentence_breaks:
            cleaned = clean_text(buffer)
            if len(cleaned) >= min_chars and cleaned not in sentences:
                sentences.append(cleaned)
            buffer = ""
            if len(sentences) >= limit:
                break
    cleaned = clean_text(buffer)
    if len(sentences) < limit and len(cleaned) >= min_chars and cleaned not in sentences:
        sentences.append(cleaned)
    if sentences:
        return sentences
    fallback = clean_text(normalized)
    return [fallback[:260]] if fallback else []


def build_llm_review_prompt(
    translation_text: str,
    matched_japanese: str,
) -> Dict[str, Any]:
    candidates = split_review_sentences(matched_japanese)
    return {
        "task": (
            "你是历史论文史料引文核对助手。请判断候选日文句子中是否有一句能够直接对应论文中的中文句子或引文。"
            "只允许选择精确对应的一句，不要输出上下文。"
            "direct_support 必须表示所选日文句本身足以支撑中文句子的主要事实判断；"
            "如果只是共享人名、机构名、关键词，或者缺少中文句中的关键行为、关系、因果、评价对象，必须判为 partial_support。"
            "若只能证明主题相关而不能直接支撑中文句子，判为 partial_support，且 exact_sentence 留空。"
            "若不对应，判为 not_supported。只返回 JSON。"
        ),
        "decision_rules": [
            "direct_support: 单个日文候选句即可作为中文句子或引文的直接出处。",
            "partial_support: 候选句与主题、人物、机构、页码相关，但不能单独支撑中文句子的核心事实。",
            "not_supported: 候选句与中文句子无实质对应。",
            "uncertain: OCR 或语义关系不足以判断。",
        ],
        "output_schema": {
            "decision": "direct_support | partial_support | not_supported | uncertain",
            "best_index": "整数。0 表示没有精确对应句；1 表示候选 1，以此类推。",
            "exact_sentence": "仅 direct_support 时填写所选日文原句；必须只包含精确对应句，不包含上下文。其他判定为空字符串。",
            "confidence": "0 到 1 的小数。",
            "reason": "一句话说明依据。",
        },
        "paper_sentence": translation_text,
        "candidate_sentences": [
            {"index": index + 1, "text": sentence}
            for index, sentence in enumerate(candidates)
        ],
    }


def format_review_prompt_for_llm(prompt: Dict[str, Any]) -> str:
    return (
        "Use the JSON payload below to complete the historical citation review. "
        "The input text is already present inside JSON fields such as "
        "paper_sentence, candidate_sentences, and contexts. Do not claim that "
        "the input is missing or empty. Return exactly one JSON object that "
        "follows output_schema. Do not use Markdown.\n\n"
        f"{json.dumps(prompt, ensure_ascii=False)}"
    )


def normalize_review_payload(payload: Dict[str, Any], sentences: List[str]) -> Dict[str, Any]:
    decision = str(payload.get("decision") or "uncertain").strip()
    if decision not in REVIEW_DECISIONS:
        decision = "uncertain"
    try:
        best_index = int(str(payload.get("best_index") or "0"))
    except (TypeError, ValueError):
        best_index = 0
    if best_index < 0 or best_index > len(sentences):
        best_index = 0
    try:
        confidence = float(payload.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    exact_sentence = clean_text(str(payload.get("exact_sentence") or ""))
    if decision == "direct_support" and best_index > 0 and best_index <= len(sentences):
        selected_sentence = sentences[best_index - 1]
        if not exact_sentence or exact_sentence not in selected_sentence:
            exact_sentence = selected_sentence
    if decision == "direct_support" and not exact_sentence:
        decision = "uncertain"
    if decision != "direct_support":
        exact_sentence = ""
    return {
        "decision": decision,
        "best_index": best_index,
        "exact_sentence": exact_sentence,
        "confidence": round(confidence, 4),
        "reason": clean_text(str(payload.get("reason") or "")),
    }


def _extract_first_json_object(raw_content: str) -> str:
    text = str(raw_content or "")
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            _payload, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        return text[index : index + end]
    raise json.JSONDecodeError("No JSON object found", text, 0)


def parse_review_json_with_repair(raw_content: str) -> tuple[Dict[str, Any], bool]:
    stripped = str(raw_content or "").strip()
    try:
        return json.loads(stripped), False
    except json.JSONDecodeError:
        pass
    try:
        parsed = parse_llm_json(stripped)
        repaired = stripped != _extract_first_json_object(stripped).strip()
        return parsed, True or repaired
    except Exception:
        extracted = _extract_first_json_object(stripped)
        return json.loads(extracted), True


def heuristic_review_alignment(translation_text: str, matched_japanese: str) -> Dict[str, Any]:
    sentences = split_review_sentences(matched_japanese)
    if not sentences:
        return {
            "decision": "not_supported",
            "best_index": 0,
            "exact_sentence": "",
            "confidence": 0.0,
            "reason": "没有可供判定的日文候选句。",
            "provider": "heuristic",
        }
    scored = [
        (index + 1, sentence, score_alignment_candidate(translation_text, sentence))
        for index, sentence in enumerate(sentences)
    ]
    best_index, best_sentence, best_score = max(scored, key=lambda item: item[2])
    cue_score = score_evidence_cues(translation_text, matched_japanese)
    cue_matches = evidence_cue_matches(translation_text, matched_japanese)
    if best_score >= 0.45:
        decision = "direct_support"
    elif best_score >= 0.16 or (cue_score >= 0.25 and len(cue_matches) >= 2):
        decision = "partial_support"
    else:
        decision = "not_supported"
    return {
        "decision": decision,
        "best_index": best_index if decision != "not_supported" else 0,
        "exact_sentence": best_sentence if decision == "direct_support" else "",
        "confidence": round(best_score, 4),
        "reason": "启发式复核：按中文汉字重合与片段相似度评分。",
        "provider": "heuristic",
        "eligible_for_llm_review": False,
        "llm_review_success": False,
        "llm_review_json_repaired": False,
        "llm_review_fallback_heuristic": True,
        "llm_review_failed": False,
        "cue_score": round(cue_score, 4),
        "cue_matches": cue_matches,
    }


def _context_candidate_text(context: Dict[str, Any]) -> str:
    return clean_text(
        str(
            context.get("cleaned_context")
            or context.get("text")
            or context.get("expanded_context")
            or context.get("snippet")
            or ""
        )
    )


def build_multi_context_review_prompt(
    translation_text: str,
    contexts: List[Dict[str, Any]],
    *,
    compound_evidence_packet: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    context_payloads: List[Dict[str, Any]] = []
    for index, context in enumerate(contexts, start=1):
        context_id = str(context.get("context_id") or f"ctx{index}")
        context_text = _context_candidate_text(context)
        context_payloads.append(
            {
                "context_id": context_id,
                "score": context.get("score"),
                "query": context.get("query") or "",
                "pdf_page": context.get("pdf_page"),
                "lead_category": context.get("lead_category") or "",
                "score_reasons": context.get("score_reasons") or [],
                "candidate_sentences": [
                    {"index": sentence_index + 1, "text": sentence}
                    for sentence_index, sentence in enumerate(split_review_sentences(context_text, limit=8))
                ],
            }
        )
    return {
        "task": (
            "You are checking historical citation evidence. The paper sentence is in Chinese. "
            "Several Japanese fulltext/OCR contexts are provided from the same target source. "
            "Choose the primary context that best supports the paper sentence. If a compound claim "
            "is split across adjacent or complementary contexts from the same source, you may use "
            "the primary context plus supporting contexts to decide whether the context set is "
            "direct_support, partial_support, not_supported, or uncertain. "
            "When compound_evidence_packet is present, treat its listed facets as a guide "
            "to which same-source contexts should be read together. "
            "Do not choose table-of-contents/title/index hits when a body-text context is available. "
            "Return JSON only."
        ),
        "decision_rules": [
            "direct_support: one selected Japanese sentence, or a small set of same-source contexts/facets, directly supports the main factual claim.",
            "partial_support: the selected context shares source/topic/person/page clues but misses a key action, relation, or judgment.",
            "not_supported: none of the contexts provides substantive evidence for the paper sentence.",
            "uncertain: OCR/context quality is too weak to judge.",
        ],
        "output_schema": {
            "decision": "direct_support | partial_support | not_supported | uncertain",
            "best_context_id": "context_id of the best context, or empty string if none",
            "supporting_context_ids": "array of context_id values used in the judgment; include best_context_id when applicable",
            "best_sentence_index": "1-based sentence index inside the best context, or 0",
            "exact_sentence": "for single-sentence direct_support, use the exact Japanese sentence; for multi-context direct_support, may be empty",
            "confidence": "decimal from 0 to 1",
            "reason": "one short explanation of why the best context wins",
            "context_assessments": [
                {
                    "context_id": "context id",
                    "assessment": "why this context is sufficient or insufficient",
                }
            ],
        },
        "paper_sentence": translation_text,
        "contexts": context_payloads,
        "compound_evidence_packet": compound_evidence_packet or {},
    }


def normalize_multi_context_review_payload(
    payload: Dict[str, Any],
    contexts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    context_ids = [str(context.get("context_id") or f"ctx{index + 1}") for index, context in enumerate(contexts)]
    context_by_id = {context_id: contexts[index] for index, context_id in enumerate(context_ids)}
    decision = str(payload.get("decision") or "uncertain").strip()
    if decision not in REVIEW_DECISIONS:
        decision = "uncertain"
    best_context_id = str(payload.get("best_context_id") or "").strip()
    if best_context_id not in context_by_id:
        best_context_id = context_ids[0] if context_ids and decision != "not_supported" else ""
    supporting_context_ids: List[str] = []
    raw_supporting = payload.get("supporting_context_ids") or payload.get("support_context_ids") or []
    if isinstance(raw_supporting, str):
        raw_supporting = [item.strip() for item in raw_supporting.split(",")]
    if isinstance(raw_supporting, list):
        for item in raw_supporting:
            context_id = str(item or "").strip()
            if context_id in context_by_id and context_id not in supporting_context_ids:
                supporting_context_ids.append(context_id)
    if best_context_id and best_context_id not in supporting_context_ids:
        supporting_context_ids.insert(0, best_context_id)
    try:
        best_sentence_index = int(str(payload.get("best_sentence_index") or payload.get("best_index") or "0"))
    except (TypeError, ValueError):
        best_sentence_index = 0
    try:
        confidence = float(payload.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    exact_sentence = clean_text(str(payload.get("exact_sentence") or ""))
    selected_sentences: List[str] = []
    if best_context_id and best_context_id in context_by_id:
        selected_sentences = split_review_sentences(_context_candidate_text(context_by_id[best_context_id]), limit=8)
    if best_sentence_index < 0 or best_sentence_index > len(selected_sentences):
        best_sentence_index = 0
    if decision == "direct_support" and best_sentence_index > 0:
        selected_sentence = selected_sentences[best_sentence_index - 1]
        if not exact_sentence or exact_sentence not in selected_sentence:
            exact_sentence = selected_sentence
    multi_context_direct = decision == "direct_support" and len(supporting_context_ids) >= 2
    if decision == "direct_support" and (not best_context_id or (not exact_sentence and not multi_context_direct)):
        decision = "uncertain"
    if decision != "direct_support":
        exact_sentence = ""
    assessments: List[Dict[str, str]] = []
    raw_assessments = payload.get("context_assessments") or []
    if isinstance(raw_assessments, list):
        for item in raw_assessments[:8]:
            if not isinstance(item, dict):
                continue
            context_id = str(item.get("context_id") or "").strip()
            if context_id not in context_by_id:
                continue
            assessments.append(
                {
                    "context_id": context_id,
                    "assessment": clean_text(str(item.get("assessment") or item.get("reason") or ""))[:500],
                }
            )
    return {
        "decision": decision,
        "best_context_id": best_context_id,
        "best_index": best_sentence_index,
        "best_sentence_index": best_sentence_index,
        "supporting_context_ids": supporting_context_ids,
        "exact_sentence": exact_sentence,
        "confidence": round(confidence, 4),
        "reason": clean_text(str(payload.get("reason") or "")),
        "context_assessments": assessments,
    }


def heuristic_review_context_candidates(
    translation_text: str,
    contexts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if not contexts:
        return {
            "decision": "not_supported",
            "best_context_id": "",
            "best_index": 0,
            "best_sentence_index": 0,
            "exact_sentence": "",
            "confidence": 0.0,
            "reason": "No expanded context candidates were available.",
            "provider": "heuristic_multi_context",
            "eligible_for_llm_review": False,
            "llm_review_success": False,
            "llm_review_json_repaired": False,
            "llm_review_fallback_heuristic": True,
            "llm_review_failed": False,
            "supporting_context_ids": [],
            "context_assessments": [],
        }
    decision_rank = {
        "direct_support": 3,
        "partial_support": 2,
        "uncertain": 1,
        "not_supported": 0,
    }
    scored: List[Tuple[float, Dict[str, Any], Dict[str, Any]]] = []
    assessments: List[Dict[str, str]] = []
    for index, context in enumerate(contexts, start=1):
        context_id = str(context.get("context_id") or f"ctx{index}")
        review = heuristic_review_alignment(translation_text, _context_candidate_text(context))
        context_score = float(context.get("score") or 0.0)
        lead_category = str(context.get("lead_category") or "")
        score_reasons = [str(item) for item in (context.get("score_reasons") or [])]
        has_core_terms = any(item.startswith("core_terms=") for item in score_reasons)
        if lead_category == "body_candidate" and has_core_terms and context_score >= 10.0:
            sentences = split_review_sentences(_context_candidate_text(context), limit=8)
            core_terms: List[str] = []
            for item in score_reasons:
                if item.startswith("core_terms="):
                    core_terms.extend(term for term in item.removeprefix("core_terms=").split(",") if term)
            best_sentence = ""
            best_index = 0
            for sentence_index, sentence in enumerate(sentences, start=1):
                if any(term and term in sentence for term in core_terms):
                    best_sentence = sentence
                    best_index = sentence_index
                    break
            if not best_sentence and sentences:
                best_sentence = sentences[0]
                best_index = 1
            review = {
                **review,
                "decision": "direct_support",
                "best_index": best_index,
                "exact_sentence": best_sentence,
                "confidence": round(min(0.92, max(0.72, context_score / 18.0)), 4),
                "reason": "Score-based fallback: body context contains multiple source-type core action terms.",
            }
        elif lead_category == "body_candidate" and context_score >= 7.0 and review.get("decision") == "not_supported":
            review = {
                **review,
                "decision": "partial_support",
                "best_index": int(review.get("best_index") or 0),
                "exact_sentence": "",
                "confidence": round(min(0.78, max(0.45, context_score / 18.0)), 4),
                "reason": "Score-based fallback: body context is strongly source-specific but not enough for direct support.",
            }
        combined = (
            decision_rank.get(str(review.get("decision") or "not_supported"), 0) * 100.0
            + float(review.get("confidence") or 0.0) * 10.0
            + context_score
        )
        scored.append((combined, context, review))
        assessments.append(
            {
                "context_id": context_id,
                "assessment": (
                    f"{review.get('decision')} confidence={review.get('confidence')} "
                    f"score={round(context_score, 3)}"
                ),
            }
        )
    _combined, best_context, best_review = max(scored, key=lambda item: item[0])
    best_context_id = str(best_context.get("context_id") or "ctx1")
    result = dict(best_review)
    result.update(
        {
            "best_context_id": best_context_id,
            "best_sentence_index": result.get("best_index", 0),
            "supporting_context_ids": [best_context_id] if best_context_id else [],
            "provider": "heuristic_multi_context",
            "eligible_for_llm_review": False,
            "llm_review_success": False,
            "llm_review_json_repaired": False,
            "llm_review_fallback_heuristic": True,
            "llm_review_failed": False,
            "context_assessments": assessments,
        }
    )
    return result


def review_context_candidates_with_llm(
    translation_text: str,
    contexts: List[Dict[str, Any]],
    *,
    llm_client: Any,
    enforce_model_policy: bool = True,
    compound_evidence_packet: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not contexts:
        return heuristic_review_context_candidates(translation_text, contexts)
    prompt = build_multi_context_review_prompt(
        translation_text,
        contexts,
        compound_evidence_packet=compound_evidence_packet,
    )
    raw_content = ""
    attempts = 0
    json_repaired = False
    allow_formal = getattr(llm_client, "is_formal_review_allowed", None)
    if enforce_model_policy and callable(allow_formal) and not allow_formal():
        result = heuristic_review_context_candidates(translation_text, contexts)
        result["eligible_for_llm_review"] = True
        result["llm_review_failed"] = True
        result["llm_error"] = "model_not_allowlisted_for_formal_review"
        result["blocked_model"] = getattr(llm_client, "model", None)
        return result
    try:
        while True:
            attempts += 1
            response = llm_client.chat(
                [{"role": "user", "content": format_review_prompt_for_llm(prompt)}],
                temperature=0.0,
                max_tokens=1200,
            )
            raw_content = str(response.get("content", ""))
            try:
                parsed, repaired = parse_review_json_with_repair(raw_content)
                json_repaired = json_repaired or repaired
                break
            except Exception:
                if attempts >= 2:
                    raise
                repair_prompt = build_multi_context_review_prompt(
                    translation_text,
                    contexts,
                    compound_evidence_packet=compound_evidence_packet,
                )
                prompt = {
                    "task": "The previous output was not valid JSON. Return exactly one JSON object.",
                    "output_schema": repair_prompt["output_schema"],
                    "paper_sentence": translation_text,
                    "contexts": repair_prompt["contexts"],
                    "compound_evidence_packet": repair_prompt["compound_evidence_packet"],
                }
    except Exception as exc:  # noqa: BLE001
        result = heuristic_review_context_candidates(translation_text, contexts)
        result["llm_error"] = f"{type(exc).__name__}: {exc}"
        result["eligible_for_llm_review"] = True
        result["llm_review_failed"] = True
        result["llm_review_attempts"] = attempts
        if raw_content:
            result["llm_response_preview"] = raw_content[:500]
        return result
    result = normalize_multi_context_review_payload(parsed, contexts)
    if _looks_like_prompt_misread(result):
        fallback = heuristic_review_context_candidates(translation_text, contexts)
        fallback["eligible_for_llm_review"] = True
        fallback["llm_review_failed"] = True
        fallback["llm_review_attempts"] = attempts
        fallback["llm_error"] = "prompt_misread_or_encoding_loss"
        fallback["llm_response_preview"] = raw_content[:500]
        return fallback
    best_context = next(
        (context for context in contexts if str(context.get("context_id") or "") == result.get("best_context_id")),
        contexts[0],
    )
    cue_score = score_evidence_cues(translation_text, _context_candidate_text(best_context))
    cue_matches = evidence_cue_matches(translation_text, _context_candidate_text(best_context))
    result["cue_score"] = round(cue_score, 4)
    result["cue_matches"] = cue_matches
    if result["decision"] == "not_supported" and cue_score >= 0.25 and len(cue_matches) >= 2:
        result["decision"] = "partial_support"
        cue_reason = "deterministic source cues indicate partial evidence despite the model rejection"
        result["reason"] = f"{result.get('reason')}; {cue_reason}".strip("; ")
    result["provider"] = getattr(llm_client, "provider", "llm")
    result["eligible_for_llm_review"] = True
    result["llm_review_success"] = True
    result["llm_review_json_repaired"] = json_repaired
    result["llm_review_fallback_heuristic"] = False
    result["llm_review_failed"] = False
    result["llm_review_attempts"] = attempts
    model = getattr(llm_client, "model", None)
    if model:
        result["model"] = model
    return result


def _looks_like_prompt_misread(review: Dict[str, Any]) -> bool:
    reason = str(review.get("reason") or "").lower()
    exact = str(review.get("exact_sentence") or "")
    markers = (
        "未提供",
        "缺少",
        "no input",
        "not provided",
        "paper sentence is empty",
        "input is empty",
        "input is missing",
        "provided, but the paper sentence is empty",
        "question marks",
        "all question marks",
        "uninformative",
        "paper_sentence",
        "candidate_sentences",
    )
    if any(marker.lower() in reason for marker in markers):
        return True
    if reason.count("?") >= 6 or exact.count("?") >= 6:
        return True
    return False


def review_alignment_with_llm(
    translation_text: str,
    matched_japanese: str,
    *,
    llm_client: Any,
    enforce_model_policy: bool = True,
) -> Dict[str, Any]:
    sentences = split_review_sentences(matched_japanese)
    if not sentences:
        return heuristic_review_alignment(translation_text, matched_japanese)
    prompt = build_llm_review_prompt(translation_text, matched_japanese)
    raw_content = ""
    attempts = 0
    json_repaired = False
    allow_formal = getattr(llm_client, "is_formal_review_allowed", None)
    if enforce_model_policy and callable(allow_formal) and not allow_formal():
        result = heuristic_review_alignment(translation_text, matched_japanese)
        result["eligible_for_llm_review"] = True
        result["llm_review_failed"] = True
        result["llm_error"] = "model_not_allowlisted_for_formal_review"
        result["blocked_model"] = getattr(llm_client, "model", None)
        return result
    try:
        while True:
            attempts += 1
            response = llm_client.chat(
                [{"role": "user", "content": format_review_prompt_for_llm(prompt)}],
                temperature=0.0,
                max_tokens=700,
            )
            raw_content = str(response.get("content", ""))
            try:
                parsed, repaired = parse_review_json_with_repair(raw_content)
                json_repaired = json_repaired or repaired
                break
            except Exception:
                if attempts >= 2:
                    raise
                prompt = {
                    "task": "上一次输出不是可解析 JSON。请只返回一个 JSON 对象，不要解释。",
                    "output_schema": build_llm_review_prompt(translation_text, matched_japanese)["output_schema"],
                    "paper_sentence": translation_text,
                    "candidate_sentences": build_llm_review_prompt(translation_text, matched_japanese)["candidate_sentences"],
                }
    except Exception as exc:  # noqa: BLE001
        result = heuristic_review_alignment(translation_text, matched_japanese)
        result["llm_error"] = f"{type(exc).__name__}: {exc}"
        result["eligible_for_llm_review"] = True
        result["llm_review_failed"] = True
        result["llm_review_attempts"] = attempts
        if raw_content:
            result["llm_response_preview"] = raw_content[:500]
        return result
    result = normalize_review_payload(parsed, sentences)
    if _looks_like_prompt_misread(result):
        fallback = heuristic_review_alignment(translation_text, matched_japanese)
        fallback["eligible_for_llm_review"] = True
        fallback["llm_review_failed"] = True
        fallback["llm_review_attempts"] = attempts
        fallback["llm_error"] = "prompt_misread_or_encoding_loss"
        fallback["llm_response_preview"] = raw_content[:500]
        return fallback
    cue_score = score_evidence_cues(translation_text, matched_japanese)
    cue_matches = evidence_cue_matches(translation_text, matched_japanese)
    result["cue_score"] = round(cue_score, 4)
    result["cue_matches"] = cue_matches
    if result["decision"] == "not_supported" and cue_score >= 0.25 and len(cue_matches) >= 2:
        result["decision"] = "partial_support"
        cue_reason = "deterministic source cues indicate partial evidence despite the model rejection"
        result["reason"] = f"{result.get('reason')}; {cue_reason}".strip("; ")
    result["provider"] = getattr(llm_client, "provider", "llm")
    result["eligible_for_llm_review"] = True
    result["llm_review_success"] = True
    result["llm_review_json_repaired"] = json_repaired
    result["llm_review_fallback_heuristic"] = False
    result["llm_review_failed"] = False
    result["llm_review_attempts"] = attempts
    model = getattr(llm_client, "model", None)
    if model:
        result["model"] = model
    return result


class OllamaChatClient:
    provider = "ollama"

    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None, timeout: Optional[int] = None):
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")
        self.model = model or os.environ.get("HISTORICAL_CITATION_REVIEW_MODEL") or self._select_model()
        self.timeout = _configured_ollama_timeout(timeout)

    def _select_model(self) -> str:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=8)
            response.raise_for_status()
            models = [item.get("name", "") for item in response.json().get("models", [])]
        except Exception:
            return "gemma4:e4b"
        policy = self._load_model_policy()
        for marker in policy.get("allowlist") or []:
            for model in models:
                if marker and marker in model.lower():
                    return model
        evaluated_models = sorted(
            [
                item
                for item in policy.get("evaluated_models") or []
                if item.get("passed") and item.get("model")
            ],
            key=lambda item: float(item.get("score") or 0),
            reverse=True,
        )
        for item in evaluated_models:
            marker = str(item.get("model") or "").lower()
            for model in models:
                if marker and marker in model.lower():
                    return model
        preferred_markers = (*FORMAL_REVIEW_PREFERRED_MODEL_MARKERS, "llama", "mistral")
        for marker in preferred_markers:
            for model in models:
                if marker in model.lower():
                    return model
        return models[0] if models else "gemma4:e4b"

    def _load_model_policy(self) -> Dict[str, Any]:
        configured_path = os.environ.get("HISTORICAL_CITATION_REVIEW_MODEL_POLICY")
        policy_path = Path(configured_path) if configured_path else DEFAULT_OLLAMA_MODEL_POLICY_PATH
        if not policy_path.exists():
            return {"loaded": False, "path": str(policy_path)}
        try:
            payload = json.loads(policy_path.read_text(encoding="utf-8-sig"))
        except Exception as exc:  # noqa: BLE001
            return {
                "loaded": False,
                "path": str(policy_path),
                "error": f"{type(exc).__name__}: {exc}",
            }
        allowlist = [
            str(item).strip().lower()
            for item in payload.get("allowlist", [])
            if str(item).strip()
        ]
        blocklist = [
            str(item).strip().lower()
            for item in payload.get("blocklist", [])
            if str(item).strip()
        ]
        return {
            "loaded": True,
            "path": str(policy_path),
            "allowlist": allowlist,
            "blocklist": blocklist,
            "minimum_score": payload.get("minimum_score"),
            "evaluated_models": payload.get("evaluated_models") or [],
        }

    def is_formal_review_allowed(self) -> bool:
        allow_unevaluated = os.environ.get("HISTORICAL_CITATION_ALLOW_UNEVALUATED_REVIEW_MODEL") == "1"
        allowlist = _split_model_markers(os.environ.get("HISTORICAL_CITATION_REVIEW_MODEL_ALLOWLIST", ""))
        blocklist = _split_model_markers(os.environ.get("HISTORICAL_CITATION_REVIEW_MODEL_BLOCKLIST", ""))
        model = str(self.model or "").lower()
        if _model_matches_marker(model, blocklist):
            return False
        if allowlist:
            return _model_matches_marker(model, allowlist)
        policy = self._load_model_policy()
        if _model_matches_marker(model, policy.get("blocklist") or []):
            return False
        if policy.get("loaded") or os.environ.get("HISTORICAL_CITATION_REVIEW_MODEL_POLICY"):
            return _model_matches_marker(model, policy.get("allowlist") or [])
        return allow_unevaluated or is_preferred_review_model(model)

    def health_check(self) -> Dict[str, Any]:
        started = time.time()
        policy = self._load_model_policy()
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=8)
            response.raise_for_status()
            models = [item.get("name", "") for item in response.json().get("models", [])]
            return {
                "provider": self.provider,
                "base_url": self.base_url,
                "available": True,
                "selected_model": self.model,
                "timeout_seconds": self.timeout,
                "model_count": len(models),
                "formal_review_allowed": self.is_formal_review_allowed(),
                "preferred_model_family": is_preferred_review_model(str(self.model or "")),
                "model_policy": policy,
                "latency_ms": round((time.time() - started) * 1000, 1),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "provider": self.provider,
                "base_url": self.base_url,
                "available": False,
                "selected_model": self.model,
                "timeout_seconds": self.timeout,
                "formal_review_allowed": self.is_formal_review_allowed(),
                "preferred_model_family": is_preferred_review_model(str(self.model or "")),
                "model_policy": policy,
                "error": f"{type(exc).__name__}: {exc}",
                "latency_ms": round((time.time() - started) * 1000, 1),
            }

    def chat(self, messages: List[Dict[str, str]], *, temperature: float = 0.0, max_tokens: int = 700) -> Dict[str, str]:
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": False,
                "think": False,
                "format": "json",
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return {"content": payload.get("message", {}).get("content", "")}


def default_review_evaluation_cases() -> List[Dict[str, Any]]:
    return [
        {
            "case_id": "direct_chinese_japanese_policy",
            "translation_text": "无需墨守早前诏敕",
            "matched_japanese": "前文である。必シモ前日ノ詔勅ヲ墨守スルノ要ヲ見サル。後文である。",
            "expected_decision": "direct_support",
            "expected_exact_contains": "詔勅",
        },
        {
            "case_id": "partial_shared_topic_only",
            "translation_text": "会议派认为新的集资方法过于加重同族负担，且会馆应遵从天皇敕谕。",
            "matched_japanese": "本館ノ事タルヤ上ハ天子ノ聖訓ヲ奉戴ス。資金ノ調達ニ関スル議論モ別ニ見ユ。",
            "expected_decision": "partial_support",
            "expected_exact_contains": "",
        },
        {
            "case_id": "not_supported_unrelated",
            "translation_text": "改革派主张裁撤会议并将资金用于教育扩张。",
            "matched_japanese": "本日は天候晴朗ニシテ来賓多ク、祝辞及ビ会計報告ヲ朗読シタ。",
            "expected_decision": "not_supported",
            "expected_exact_contains": "",
        },
    ]


def evaluate_review_client(
    llm_client: Any,
    *,
    cases: Optional[Iterable[Dict[str, Any]]] = None,
    minimum_score: float = 0.67,
) -> Dict[str, Any]:
    started = time.time()
    case_results: List[Dict[str, Any]] = []
    for case in cases or default_review_evaluation_cases():
        review = review_alignment_with_llm(
            str(case.get("translation_text") or ""),
            str(case.get("matched_japanese") or ""),
            llm_client=llm_client,
            enforce_model_policy=False,
        )
        expected_decision = str(case.get("expected_decision") or "")
        expected_exact_contains = str(case.get("expected_exact_contains") or "")
        decision_ok = review.get("decision") == expected_decision
        exact_ok = True
        if expected_exact_contains:
            exact_ok = expected_exact_contains in str(review.get("exact_sentence") or "")
        case_results.append(
            {
                "case_id": case.get("case_id"),
                "expected_decision": expected_decision,
                "actual_decision": review.get("decision"),
                "decision_ok": decision_ok,
                "exact_ok": exact_ok,
                "provider": review.get("provider"),
                "confidence": review.get("confidence"),
                "llm_review_success": review.get("llm_review_success"),
                "llm_review_failed": review.get("llm_review_failed"),
                "llm_error": review.get("llm_error"),
                "reason": review.get("reason"),
            }
        )
    correct = sum(1 for item in case_results if item["decision_ok"] and item["exact_ok"])
    total = len(case_results)
    score = correct / max(1, total)
    model = getattr(llm_client, "model", None)
    return {
        "provider": getattr(llm_client, "provider", "llm"),
        "model": model,
        "preferred_model_family": is_preferred_review_model(str(model or "")),
        "formal_review_allowed": (
            llm_client.is_formal_review_allowed()
            if hasattr(llm_client, "is_formal_review_allowed")
            else None
        ),
        "score": round(score, 4),
        "minimum_score": minimum_score,
        "passed": score >= minimum_score,
        "correct": correct,
        "total": total,
        "latency_ms": round((time.time() - started) * 1000, 1),
        "cases": case_results,
    }
