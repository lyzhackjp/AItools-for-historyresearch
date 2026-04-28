from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ParsedParagraph:
    index: int
    text: str
    footnote_ids: List[str] = field(default_factory=list)
    quotes: List[str] = field(default_factory=list)
    footnote_positions: Dict[str, int] = field(default_factory=dict)
    footnote_contexts: Dict[str, str] = field(default_factory=dict)
    footnote_citation_units: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedFootnote:
    id: str
    text: str
    title: str = ""
    author: str = ""
    publisher: str = ""
    publication_place: str = ""
    year: str = ""
    page_label: str = ""
    page_numbers: List[int] = field(default_factory=list)
    page_span_type: str = ""
    page_span_source: str = ""
    source_type: str = "book"
    ndl_keyword: str = ""
    host_title: str = ""
    contained_title: str = ""
    source_relation: str = ""
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NDLSearchMatch:
    title: str
    url: str
    ndl_id: Optional[str] = None
    platform: str = "ndl"
    platform_item_id: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    publisher: Optional[str] = None
    pdf_url: Optional[str] = None
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CitationCandidate:
    candidate_id: str
    paragraph_index: int
    paragraph_text: str
    translation_text: str
    footnote_id: str
    footnote: ParsedFootnote
    ndl_matches: List[NDLSearchMatch] = field(default_factory=list)
    verification_status: str = "parsed"
    matched_japanese: str = ""
    matched_page: Optional[int] = None
    confidence: Optional[float] = None
    support_status: str = "unassessed"
    support_reason: str = ""
    evidence_scope: str = ""
    notes: List[str] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["footnote"] = self.footnote.to_dict()
        payload["ndl_matches"] = [item.to_dict() for item in self.ndl_matches]
        return payload
