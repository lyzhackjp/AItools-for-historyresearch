from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple


DEFAULT_EVIDENCE_CUE_CONFIG = Path(__file__).with_name("evidence_cues.default.json")


def _normalize_cue_groups(payload: Any) -> Tuple[Tuple[str, ...], ...]:
    if isinstance(payload, dict):
        raw_groups = payload.get("cue_groups") or payload.get("groups") or []
    else:
        raw_groups = payload or []

    groups: List[Tuple[str, ...]] = []
    for raw_group in raw_groups:
        if isinstance(raw_group, str):
            group = (raw_group.strip(),)
        else:
            group = tuple(
                str(item).strip()
                for item in (raw_group or [])
                if str(item or "").strip()
            )
        if group:
            groups.append(group)
    return tuple(groups)


@lru_cache(maxsize=16)
def load_evidence_cue_groups(config_path: Optional[str] = None) -> Tuple[Tuple[str, ...], ...]:
    """Load configurable cross-script cue groups.

    Users can provide a project-specific JSON file through
    HISTORICAL_CITATION_CUE_CONFIG or by passing config_path. The file can be
    either {"cue_groups": [[...], ...]} or a raw list of lists.
    """

    resolved_path = Path(
        config_path
        or os.environ.get("HISTORICAL_CITATION_CUE_CONFIG")
        or DEFAULT_EVIDENCE_CUE_CONFIG
    )
    try:
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        if resolved_path == DEFAULT_EVIDENCE_CUE_CONFIG:
            return tuple()
        return load_evidence_cue_groups(str(DEFAULT_EVIDENCE_CUE_CONFIG))
    return _normalize_cue_groups(payload)


def evidence_cue_matches(
    translation_text: str,
    segment: str,
    *,
    cue_groups: Optional[Sequence[Sequence[str]]] = None,
) -> List[str]:
    """Return cross-script source cues found on both the paper and OCR sides."""

    translation = str(translation_text or "")
    evidence = str(segment or "")
    groups = tuple(tuple(group) for group in (cue_groups or load_evidence_cue_groups()))
    matched: List[str] = []
    for group in groups:
        if any(term in translation for term in group) and any(term in evidence for term in group):
            matched.append(group[0])
    return matched


def score_evidence_cues(
    translation_text: str,
    segment: str,
    *,
    cue_groups: Optional[Sequence[Sequence[str]]] = None,
) -> float:
    groups = tuple(tuple(group) for group in (cue_groups or load_evidence_cue_groups()))
    translation = str(translation_text or "")
    active_groups = [
        group
        for group in groups
        if any(term in translation for term in group)
    ]
    if not active_groups:
        return 0.0
    matched = evidence_cue_matches(translation_text, segment, cue_groups=active_groups)
    return len(matched) / max(1, len(active_groups))
