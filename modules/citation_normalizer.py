"""
Unified citation normalization helpers.

This module now centers on a shared citation-record schema so the workflow,
formatters, and writing stages can exchange the same structured metadata.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from modules.citation_formats import CitationFormatter


CitationInput = Union[str, Sequence[str]]


@dataclass
class CitationParseResult:
    raw_text: str
    detected_style: str
    record: Dict[str, Any]


class CitationNormalizer:
    """Normalize raw citations into a unified citation-record schema."""

    SUPPORTED_STYLES = ["chicago", "apa", "mla", "gb7714", "ieee", "harvard"]

    STYLE_PATTERNS = {
        "apa": [r"\(\d{4}[a-z]?\)", r"\.\s+[A-Z][^.]+\.\s+\d+\("],
        "mla": [r"vol\.\s*\d+", r"pp\.\s*\d+"],
        "gb7714": [r"^\[\d+\]", r"\[[JMDC]\]"],
        "ieee": [r"^\[\d+\]", r"vol\.\s*\d+", r"no\.\s*\d+"],
        "harvard": [r"\(\d{4}[a-z]?\)\s+['\"]"],
        "chicago": [r"\".+?\.\"", r"\.\s+\d{4}[,\.]"],
    }

    TYPE_MARKERS = {
        "book": [r"\[M\]", r"\bpress\b", r"\bpublisher\b"],
        "article": [r"\[J\]", r"\bjournal\b", r"vol\.", r"no\."],
        "conference": [r"\[C\]", r"\bconference\b", r"\bproceedings\b"],
        "dissertation": [r"\[D\]", r"\bdissertation\b", r"\bthesis\b"],
        "electronic": [r"\[EB/OL\]", r"https?://", r"\bdoi:"],
    }

    def __init__(
        self,
        style: str = "chicago",
        test_mode: bool = True,
        use_llm: bool = False,
        provider: str = "qwen",
        backend: str = "script",
        model: Optional[str] = None,
    ):
        if style not in self.SUPPORTED_STYLES:
            raise ValueError(f"Unsupported citation style: {style}")
        self.style = style
        self.test_mode = test_mode
        self.use_llm = use_llm
        self.provider = provider
        self.backend = backend or "script"
        self.model = model
        self.formatter = CitationFormatter()

    def detect_format(self, citation: str) -> str:
        """Best-effort citation style detection."""

        scores = {style: 0 for style in self.SUPPORTED_STYLES}
        text = citation or ""
        for style, patterns in self.STYLE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    scores[style] += 1
        best_style = max(scores, key=scores.get)
        return best_style if scores[best_style] else "unknown"

    def parse_citation(self, citation: str) -> Dict[str, Any]:
        """Parse one citation into a normalized record."""

        return self.normalize_record(citation, target_style=self.style)

    def normalize(
        self,
        citations: CitationInput,
        target_style: Optional[str] = None,
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Normalize a single citation or a batch.

        The return type follows the input type for easier compatibility.
        """

        if isinstance(citations, str):
            return self.normalize_record(citations, target_style=target_style)
        return self.normalize_batch(list(citations), target_style=target_style)

    def normalize_batch(
        self,
        citations: Sequence[str],
        target_style: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Normalize a batch of citations."""

        return [
            self.normalize_record(citation, target_style=target_style, index=index)
            for index, citation in enumerate(citations, start=1)
        ]

    def normalize_record(
        self,
        citation: str,
        target_style: Optional[str] = None,
        index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Normalize one citation into the shared record schema."""

        text = self._clean_text(citation)
        detected_style = self.detect_format(text)
        record_type = self._detect_type(text)
        authors = self._extract_authors(text)
        year = self._extract_year(text)
        title = self._extract_title(text, authors=authors, year=year)
        pages = self._extract_pages(text)
        volume = self._extract_volume(text)
        issue = self._extract_issue(text)
        doi = self._extract_doi(text)
        url = self._extract_url(text)
        journal_or_publisher = self._extract_container(text, title=title, year=year)
        journal = journal_or_publisher if record_type == "article" else ""
        publisher = journal_or_publisher if record_type != "article" else ""

        record: Dict[str, Any] = {
            "raw_text": text,
            "detected_style": detected_style,
            "type": record_type,
            "title": title,
            "authors": authors,
            "author": self._join_authors(authors),
            "year": year,
            "journal_or_publisher": journal_or_publisher,
            "journal": journal,
            "publisher": publisher,
            "pages": pages,
            "volume": volume,
            "issue": issue,
            "doi": doi,
            "url": url,
            "backend": self.backend,
            "provider": self.provider,
            "model": self.model,
            "notes": [],
        }
        record["confidence"] = self._estimate_confidence(record)
        record["needs_review"] = bool(
            not record["title"]
            or not record["authors"]
            or not record["year"]
            or record["confidence"] < 0.65
        )
        if record["needs_review"]:
            record["notes"].append("citation record is incomplete and should be reviewed manually")

        render_style = target_style or self.style
        record["normalized_citation"] = self.formatter.format_record(record, style=render_style, index=index)
        record["target_style"] = render_style
        return record

    def convert_format(
        self,
        citation: str,
        target_style: str,
        index: Optional[int] = None,
    ) -> str:
        """Convert one raw citation into the requested rendered style."""

        record = self.normalize_record(citation, target_style=target_style, index=index)
        return record["normalized_citation"]

    def validate_fields(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Lightweight validation summary for downstream review."""

        missing = [field for field in ("title", "authors", "year") if not record.get(field)]
        warnings = []
        if record.get("year") and not re.fullmatch(r"\d{4}", str(record["year"])):
            warnings.append("year is not a plain 4-digit value")
        if record.get("doi") and not str(record["doi"]).startswith("10."):
            warnings.append("doi does not look canonical")
        return {
            "is_valid": not missing,
            "missing_fields": missing,
            "warnings": warnings,
        }

    def _clean_text(self, citation: str) -> str:
        return re.sub(r"\s+", " ", (citation or "").strip())

    def _detect_type(self, citation: str) -> str:
        lowered = citation.lower()
        for record_type, markers in self.TYPE_MARKERS.items():
            if any(re.search(marker, lowered, re.IGNORECASE) for marker in markers):
                return record_type
        if "http" in lowered or "doi" in lowered:
            return "electronic"
        if re.search(r"vol\.\s*\d+|no\.\s*\d+", citation, re.IGNORECASE):
            return "article"
        return "article"

    def _extract_authors(self, citation: str) -> List[str]:
        prefix = citation
        year_match = re.search(r"\b(19|20)\d{2}[a-z]?\b", citation)
        if year_match:
            prefix = citation[: year_match.start()]
        prefix = prefix.strip(" .,:;[]()")
        if '"' in prefix:
            prefix = prefix.split('"', 1)[0].strip()
        if "“" in prefix:
            prefix = prefix.split("“", 1)[0].strip()
        parts = re.split(r"\s+and\s+|,\s*&\s*|,\s+and\s+|;|，|、", prefix)
        authors = [part.strip(" .,:;[]()") for part in parts if part.strip(" .,:;[]()")]
        if not authors and prefix:
            authors = [prefix]
        return authors[:6]

    def _extract_year(self, citation: str) -> str:
        match = re.search(r"\b(19|20)\d{2}[a-z]?\b", citation)
        return match.group(0) if match else ""

    def _extract_title(self, citation: str, authors: List[str], year: str) -> str:
        quote_match = re.search(r"[\"“](.+?)[\"”]", citation)
        if quote_match:
            return quote_match.group(1).strip(" .")

        working = citation
        if authors:
            author_prefix = self._join_authors(authors)
            if working.startswith(author_prefix):
                working = working[len(author_prefix) :].strip(" .,:;")
        if year:
            working = working.replace(year, " ", 1)
        parts = [part.strip(" .,:;") for part in re.split(r"\.\s+|\s+\[.\]\s+|,\s+", working) if part.strip(" .,:;")]
        for part in parts:
            lowered = part.lower()
            if len(part) < 3:
                continue
            if lowered.startswith(("vol", "no", "pp", "doi", "http")):
                continue
            if re.fullmatch(r"\d+(?:-\d+)?", part):
                continue
            return part
        return ""

    def _extract_pages(self, citation: str) -> str:
        match = re.search(r"(?:pp?\.?\s*)?(\d+\s*[-–]\s*\d+)", citation, re.IGNORECASE)
        return re.sub(r"\s+", "", match.group(1)) if match else ""

    def _extract_volume(self, citation: str) -> str:
        match = re.search(r"vol\.?\s*(\d+)", citation, re.IGNORECASE)
        return match.group(1) if match else ""

    def _extract_issue(self, citation: str) -> str:
        match = re.search(r"no\.?\s*(\d+)", citation, re.IGNORECASE)
        if match:
            return match.group(1)
        paren_match = re.search(r"\b\d+\((\d+)\)", citation)
        return paren_match.group(1) if paren_match else ""

    def _extract_doi(self, citation: str) -> str:
        match = re.search(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", citation, re.IGNORECASE)
        return match.group(1).rstrip(".,;)") if match else ""

    def _extract_url(self, citation: str) -> str:
        match = re.search(r"(https?://[^\s]+)", citation, re.IGNORECASE)
        return match.group(1).rstrip(".,;)") if match else ""

    def _extract_container(self, citation: str, title: str, year: str) -> str:
        working = citation
        if title:
            working = working.replace(title, " ", 1)
        if year:
            working = working.replace(year, " ", 1)
        if self._extract_doi(citation):
            working = working.replace(self._extract_doi(citation), " ")
        if self._extract_url(citation):
            working = working.replace(self._extract_url(citation), " ")
        parts = [part.strip(" .,:;[]()") for part in re.split(r"\.\s+|,\s+", working) if part.strip(" .,:;[]()")]
        candidates = []
        for part in parts:
            lowered = part.lower()
            if not part or part == year:
                continue
            if part in self._extract_authors(citation):
                continue
            if part == title:
                continue
            if lowered.startswith(("vol", "no", "pp", "doi", "http")):
                continue
            if re.fullmatch(r"\d+(?:-\d+)?", part):
                continue
            candidates.append(part)
        return candidates[0] if candidates else ""

    def _estimate_confidence(self, record: Dict[str, Any]) -> float:
        score = 0.25
        for field in ("title", "authors", "year"):
            if record.get(field):
                score += 0.18
        for field in ("pages", "volume", "issue", "doi", "url", "journal_or_publisher"):
            if record.get(field):
                score += 0.05
        return round(min(score, 0.95), 2)

    def _join_authors(self, authors: Iterable[str]) -> str:
        cleaned = [author.strip() for author in authors if author and author.strip()]
        if not cleaned:
            return "Unknown"
        if len(cleaned) == 1:
            return cleaned[0]
        return ", ".join(cleaned)


def create_citation_normalizer(style: str = "chicago", **kwargs: Any) -> CitationNormalizer:
    """Compatibility factory."""

    return CitationNormalizer(style=style, **kwargs)
