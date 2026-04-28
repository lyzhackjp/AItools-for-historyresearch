from __future__ import annotations

from typing import Any, Dict, List, Optional


def source_identity(source: Any) -> str:
    if not isinstance(source, dict):
        return "unknown"
    return str(
        source.get("source_id")
        or source.get("ndl_id")
        or source.get("platform_item_id")
        or source.get("url")
        or "unknown"
    )


def source_platform(source: Any) -> str:
    if not isinstance(source, dict):
        return "unknown"
    return str(source.get("platform") or ("ndl" if source.get("ndl_id") else "unknown"))


def build_source_trial(
    *,
    role: str,
    source: Optional[Dict[str, Any]] = None,
    page_range: Any = None,
    verification_status: Optional[str] = None,
    support_status: Optional[str] = None,
    confidence: Any = None,
    failure_reason: Optional[str] = None,
    detail: Optional[str] = None,
    has_pdf: Optional[bool] = None,
    has_alignment: Optional[bool] = None,
) -> Dict[str, Any]:
    source = source or {}
    return {
        "schema_version": "1.0",
        "role": role,
        "platform": source_platform(source),
        "source_id": source_identity(source),
        "ndl_id": source.get("ndl_id"),
        "platform_item_id": source.get("platform_item_id"),
        "url": source.get("url"),
        "title": source.get("title"),
        "page_range": list(page_range) if isinstance(page_range, (list, tuple)) else page_range,
        "verification_status": verification_status or "unknown",
        "support_status": support_status or "unassessed",
        "confidence": confidence,
        "failure_reason": failure_reason,
        "detail": detail,
        "has_pdf": bool(has_pdf),
        "has_alignment": bool(has_alignment),
    }


def append_source_trial(artifacts: Dict[str, Any], trial: Dict[str, Any]) -> None:
    trials = artifacts.setdefault("source_trials", [])
    if not isinstance(trials, list):
        artifacts["source_trials"] = trials = []
    key = (
        trial.get("role"),
        trial.get("source_id"),
        trial.get("page_range"),
        trial.get("verification_status"),
        trial.get("failure_reason"),
    )
    for existing in trials:
        if not isinstance(existing, dict):
            continue
        existing_key = (
            existing.get("role"),
            existing.get("source_id"),
            existing.get("page_range"),
            existing.get("verification_status"),
            existing.get("failure_reason"),
        )
        if existing_key == key:
            return
    trials.append(trial)


def source_trials_from_legacy(
    artifacts: Dict[str, Any],
    *,
    current: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    trials: List[Dict[str, Any]] = [
        dict(item)
        for item in (artifacts.get("source_trials") or [])
        if isinstance(item, dict)
    ]
    seen = {
        (
            item.get("role"),
            item.get("source_id"),
            str(item.get("page_range")),
            item.get("verification_status"),
            item.get("failure_reason"),
        )
        for item in trials
    }

    def add(trial: Dict[str, Any]) -> None:
        key = (
            trial.get("role"),
            trial.get("source_id"),
            str(trial.get("page_range")),
            trial.get("verification_status"),
            trial.get("failure_reason"),
        )
        if key in seen:
            return
        seen.add(key)
        trials.append(trial)

    for attempt in artifacts.get("source_attempts") or []:
        if not isinstance(attempt, dict):
            continue
        source = attempt.get("selected_source_match") or {}
        add(
            build_source_trial(
                role="replaced",
                source=source,
                page_range=attempt.get("downloaded_page_range"),
                verification_status=attempt.get("verification_status"),
                support_status=attempt.get("support_status"),
                confidence=attempt.get("confidence"),
                has_pdf=bool(attempt.get("source_pdf")),
                has_alignment=bool(attempt.get("matched_japanese")),
            )
        )

    for attempt in artifacts.get("source_unavailable_attempts") or []:
        if not isinstance(attempt, dict):
            continue
        source = {
            "ndl_id": attempt.get("ndl_id"),
            "platform_item_id": attempt.get("platform_item_id"),
            "url": attempt.get("url"),
            "source_id": attempt.get("source_id"),
            "platform": attempt.get("platform"),
            "title": attempt.get("title"),
        }
        add(
            build_source_trial(
                role="unavailable",
                source=source,
                verification_status=attempt.get("verification_status") or "source_unavailable",
                failure_reason=attempt.get("reason"),
                detail=attempt.get("detail"),
            )
        )

    if current:
        source = current.get("selected_source_match") or {}
        if source:
            add(
                build_source_trial(
                    role="current",
                    source=source,
                    page_range=current.get("downloaded_page_range"),
                    verification_status=current.get("verification_status"),
                    support_status=current.get("support_status"),
                    confidence=current.get("confidence"),
                    has_pdf=bool(current.get("source_pdf")),
                    has_alignment=bool(current.get("matched_japanese")),
                )
            )

    return trials
