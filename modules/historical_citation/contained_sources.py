from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

from .docx_parser import clean_text


DEFAULT_CONTAINED_SOURCE_HOSTS: Dict[str, List[str]] = {
    # Public bibliographic hint: this article title is indexed separately by NDL
    # but the downloadable item is the host volume.
    "憲法ニ關スル演說": ["華族同方会演説集"],
    "憲法ニ関スル演説": ["華族同方会演説集"],
}


def normalize_source_lookup_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", clean_text(value or ""))
    translation = str.maketrans(
        {
            "關": "関",
            "說": "説",
            "會": "会",
            "舊": "旧",
            "國": "国",
            "圖": "図",
            "學": "学",
        }
    )
    normalized = normalized.translate(translation)
    return re.sub(r"[\s\u3000『』「」《》〈〉（）()［］\[\]・,，.。:：;；、\-ー―—_/]+", "", normalized)


def _coerce_host_list(value: Any) -> List[str]:
    if isinstance(value, str):
        return [clean_text(value)] if clean_text(value) else []
    if isinstance(value, list):
        hosts: List[str] = []
        for item in value:
            cleaned = clean_text(str(item or ""))
            if cleaned and cleaned not in hosts:
                hosts.append(cleaned)
        return hosts
    return []


def _load_configured_hosts() -> Dict[str, List[str]]:
    """Load optional local mappings without making them repository state.

    The default mapping is intentionally tiny. Project-specific or private
    mappings can live outside the module and be pointed to with
    HISTORICAL_CITATION_CONTAINED_SOURCE_CONFIG.
    """

    config_paths: List[Path] = []
    env_path = os.environ.get("HISTORICAL_CITATION_CONTAINED_SOURCE_CONFIG")
    if env_path:
        config_paths.append(Path(env_path))
    config_paths.append(Path("config") / "historical_citation_contained_sources.json")

    mappings: Dict[str, List[str]] = {}
    for path in config_paths:
        try:
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        items: List[Any]
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            items = list(payload.get("items") or [])
            for key, value in payload.items():
                if key != "items":
                    items.append({"contained_title": key, "host_title": value})
        elif isinstance(payload, dict):
            items = [{"contained_title": key, "host_title": value} for key, value in payload.items()]
        elif isinstance(payload, list):
            items = payload
        else:
            items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            contained = clean_text(str(item.get("contained_title") or item.get("title") or ""))
            hosts = _coerce_host_list(item.get("host_title") or item.get("host_titles"))
            if contained and hosts:
                mappings[contained] = hosts
    return mappings


def contained_source_host_titles(title: str, footnote_text: str = "") -> List[str]:
    lookup = normalize_source_lookup_title(title)
    if not lookup:
        return []

    merged: Dict[str, List[str]] = dict(DEFAULT_CONTAINED_SOURCE_HOSTS)
    merged.update(_load_configured_hosts())
    hosts: List[str] = []
    for contained_title, host_titles in merged.items():
        contained_lookup = normalize_source_lookup_title(contained_title)
        if contained_lookup and (
            lookup == contained_lookup
            or lookup in contained_lookup
            or contained_lookup in lookup
        ):
            for host in host_titles:
                cleaned = clean_text(host)
                if cleaned and cleaned not in hosts:
                    hosts.append(cleaned)

    inferred = infer_host_titles_from_footnote_text(title, footnote_text)
    for host in inferred:
        if host and host not in hosts:
            hosts.append(host)
    return hosts


def infer_host_titles_from_footnote_text(title: str, footnote_text: str) -> List[str]:
    """Infer host titles from common "contained in" footnote formulations."""

    if not footnote_text:
        return []
    quoted_titles = [
        clean_text(match)
        for match in re.findall(r"[『「《〈](.{2,80}?)[』」》〉]", footnote_text)
        if clean_text(match)
    ]
    if len(quoted_titles) < 2:
        return []
    title_lookup = normalize_source_lookup_title(title)
    hosts: List[str] = []
    relation_words = ("所収", "所載", "収録", "收録", "載録", "收入", "収め")
    for quoted in quoted_titles:
        quoted_lookup = normalize_source_lookup_title(quoted)
        if not quoted_lookup or quoted_lookup == title_lookup:
            continue
        if any(word in footnote_text for word in relation_words):
            hosts.append(quoted)
    return hosts


def apply_contained_source_metadata(footnote: Any) -> Any:
    hosts = contained_source_host_titles(
        getattr(footnote, "title", "") or "",
        getattr(footnote, "text", "") or "",
    )
    if not hosts:
        return footnote
    setattr(footnote, "contained_title", getattr(footnote, "title", "") or "")
    setattr(footnote, "host_title", hosts[0])
    setattr(footnote, "source_relation", "contained_in_host")
    notes = getattr(footnote, "notes", None)
    if isinstance(notes, list) and "contained_source_host_inferred" not in notes:
        notes.append("contained_source_host_inferred")
    return footnote


def contained_source_search_titles(footnote: Any) -> List[str]:
    titles: List[str] = []
    for value in [
        getattr(footnote, "host_title", "") or "",
        *contained_source_host_titles(
            getattr(footnote, "title", "") or "",
            getattr(footnote, "text", "") or "",
        ),
        getattr(footnote, "contained_title", "") or "",
        getattr(footnote, "title", "") or "",
    ]:
        cleaned = clean_text(value)
        if cleaned and cleaned not in titles:
            titles.append(cleaned)
    return titles
