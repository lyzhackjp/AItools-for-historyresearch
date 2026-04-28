"""Book citation organization facade.

The organizer keeps the old public API while exposing the newer workflow
contract used by Stage 2: normalized citation records, backend metadata,
confidence, review flags, and artifact summaries.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

try:
    from modules.pdf_processor import PDFProcessor

    PDF_PROCESSOR_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    PDFProcessor = None  # type: ignore
    PDF_PROCESSOR_AVAILABLE = False

try:
    from modules.llm_client import LLMClient

    LLM_CLIENT_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    LLMClient = None  # type: ignore
    LLM_CLIENT_AVAILABLE = False

from modules.citation_formats import CitationFormatter


UNKNOWN = "unknown"
SUPPORTED_STYLES = ("chicago", "apa", "gb7714", "mla", "ieee", "harvard")


@dataclass
class BookMetadata:
    """Structured metadata for one scanned book or book-like source."""

    original_filename: str = ""
    new_filename: str = ""
    title: str = ""
    author: str = ""
    publisher: str = ""
    publish_year: str = ""
    isbn: str = ""
    pages: str = ""
    edition: str = ""
    language: str = "ja"
    front_pages_text: str = ""
    back_pages_text: str = ""
    citation_chicago: str = ""
    citation_apa: str = ""
    citation_gb7714: str = ""
    citation_mla: str = ""
    citation_ieee: str = ""
    citation_harvard: str = ""
    process_status: str = "pending"
    error_message: str = ""
    backend: str = "script"
    provider: str = "local_rules"
    model: Optional[str] = None
    confidence: float = 0.0
    needs_review: bool = True
    review_notes: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    citation_record: Dict[str, Any] = field(default_factory=dict)
    extraction_summary: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a CSV-friendly payload while keeping legacy column names."""

        return {
            "original_filename": self.original_filename,
            "new_filename": self.new_filename,
            "title": self.title,
            "author": self.author,
            "publisher": self.publisher,
            "publish_year": self.publish_year,
            "isbn": self.isbn,
            "pages": self.pages,
            "edition": self.edition,
            "language": self.language,
            "Chicago": self.citation_chicago,
            "APA": self.citation_apa,
            "GB/T7714": self.citation_gb7714,
            "MLA": self.citation_mla,
            "IEEE": self.citation_ieee,
            "Harvard": self.citation_harvard,
            "process_status": self.process_status,
            "error_message": self.error_message,
            "backend": self.backend,
            "provider": self.provider,
            "model": self.model or "",
            "confidence": f"{self.confidence:.2f}",
            "needs_review": self.needs_review,
            "review_notes": "; ".join(self.review_notes),
        }

    def to_citation_record(self) -> Dict[str, Any]:
        """Return the shared citation-record schema used by downstream stages."""

        if self.citation_record:
            return dict(self.citation_record)
        authors = [item.strip() for item in re.split(r"[;,、／/]| and ", self.author) if item.strip()]
        return {
            "raw_text": self.front_pages_text[:500],
            "detected_style": "book_metadata",
            "type": "book",
            "title": self.title,
            "authors": authors,
            "author": self.author,
            "year": self.publish_year,
            "journal_or_publisher": self.publisher,
            "publisher": self.publisher,
            "pages": self.pages,
            "edition": self.edition,
            "isbn": self.isbn,
            "backend": self.backend,
            "provider": self.provider,
            "model": self.model,
            "confidence": self.confidence,
            "needs_review": self.needs_review,
            "notes": list(self.review_notes),
            "normalized_citation": self.citation_chicago,
            "target_style": "chicago",
        }


class BookCitationOrganizer:
    """Organize scanned books into citation-ready records and filenames."""

    SUPPORTED_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff")

    FRONT_PAGE_PATTERNS: Dict[str, Sequence[str]] = {
        "title": (
            r"(?:書名|书名|Title)\s*[:：]\s*(?P<value>[^\n]+)",
            r"^[『「《]?([^』」》\n]{2,80})[』」》]?\s*$",
        ),
        "author": (
            r"(?:著者|作者|編者|编者|Author|Writer)\s*[:：]\s*(?P<value>[^\n]+)",
            r"([^\n]{1,40})(?:著|編|编)\b",
        ),
        "publisher": (
            r"(?:出版社|出版者|Publisher)\s*[:：]\s*(?P<value>[^\n]+)",
            r"([^\n]{2,40}(?:書店|书店|出版社|出版会|出版會|Press))",
        ),
        "publish_year": (
            r"(?:出版|発行|发行|Published)[^\d]{0,8}(?P<value>(?:18|19|20)\d{2})",
            r"\b((?:18|19|20)\d{2})\b",
        ),
        "isbn": (
            r"ISBN\s*[:：-]?\s*(?P<value>[\d\-Xx]{10,17})",
        ),
        "pages": (
            r"(?:頁数|页数|Pages)\s*[:：]\s*(?P<value>\d+)",
        ),
        "edition": (
            r"(?:版次|Edition)\s*[:：]\s*(?P<value>[^\n]+)",
            r"(初版|新版|改訂版|第\d+版)",
        ),
    }

    BACK_PAGE_PATTERNS: Dict[str, Sequence[str]] = {
        "publisher": (
            r"(?:発行所|发行所|印刷所|出版社)\s*[:：]\s*(?P<value>[^\n]+)",
        ),
        "publish_year": (
            r"(?:初版|第一版|発行|发行)[^\d]{0,8}(?P<value>(?:18|19|20)\d{2})",
        ),
        "pages": (
            r"(?:全|總|总)?\s*(?P<value>\d{2,5})\s*(?:頁|页|p\b)",
        ),
    }

    def __init__(
        self,
        input_dir: str,
        output_dir: str,
        api_key: Optional[str] = None,
        llm_provider: str = "dashscope",
        llm_model: Optional[str] = None,
        front_pages: int = 5,
        back_pages: int = 5,
        copy_files: bool = True,
        overwrite: bool = False,
        enable_llm: Optional[bool] = None,
        metadata_backends: Optional[Sequence[str]] = None,
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.front_pages = max(1, int(front_pages))
        self.back_pages = max(0, int(back_pages))
        self.copy_files = copy_files
        self.overwrite = overwrite
        self.api_key = api_key
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.enable_llm = bool(api_key) if enable_llm is None else bool(enable_llm)
        self.metadata_backends = tuple(metadata_backends or ("regex", "llm" if self.enable_llm else "regex"))
        self.citation_formatter = CitationFormatter()
        self.results: List[BookMetadata] = []
        self._llm_client: Optional[Any] = None
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "module": "book_citation_organizer",
            "backends": [
                {
                    "backend": "script",
                    "provider": "local_rules",
                    "model": None,
                    "capabilities": ["regex_metadata", "filename_policy", "citation_render"],
                    "available": True,
                },
                {
                    "backend": "llm_api",
                    "provider": self.llm_provider,
                    "model": self.llm_model,
                    "capabilities": ["metadata_completion"],
                    "available": bool(self.enable_llm and LLM_CLIENT_AVAILABLE),
                },
            ],
            "supported_styles": list(SUPPORTED_STYLES),
            "supported_extensions": list(self.SUPPORTED_EXTENSIONS),
        }

    def scan_directory(self) -> List[Path]:
        files: List[Path] = []
        if not self.input_dir.exists():
            return files
        for ext in self.SUPPORTED_EXTENSIONS:
            files.extend(self.input_dir.glob(f"*{ext}"))
            files.extend(self.input_dir.glob(f"*{ext.upper()}"))
        return sorted(set(files))

    def extract_pages_text(self, file_path: Path, start_page: int, end_page: int) -> str:
        """Extract page text without creating unmanaged temporary artifacts."""

        if file_path.suffix.lower() != ".pdf":
            return "[image_ocr_not_configured]"
        if not PDF_PROCESSOR_AVAILABLE or PDFProcessor is None:
            return "[pdf_processor_unavailable]"

        text_parts: List[str] = []
        try:
            processor = PDFProcessor(str(file_path))
            page_count = getattr(processor, "page_count", end_page)
            for page_num in range(start_page, min(end_page, page_count) + 1):
                page_text = processor.extract_text(page_num)
                if page_text:
                    text_parts.append(f"[Page {page_num}]\n{page_text}")
        except Exception as exc:  # pragma: no cover - depends on external PDFs
            return f"[pdf_extract_error:{type(exc).__name__}]"
        return "\n\n".join(text_parts)

    def extract_metadata_with_regex(self, text: str, patterns: Dict[str, Sequence[str]]) -> Dict[str, str]:
        results: Dict[str, str] = {}
        for field_name, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, text or "", re.MULTILINE | re.IGNORECASE)
                if not match:
                    continue
                value = match.groupdict().get("value") if match.groupdict() else match.group(1)
                value = self._clean_field(value)
                if value:
                    results[field_name] = value
                    break
        return results

    def extract_metadata_with_llm(self, front_text: str, back_text: str) -> Dict[str, str]:
        if not self.enable_llm or not LLM_CLIENT_AVAILABLE:
            return {}

        client = self._get_llm_client()
        if client is None:
            return {}

        prompt = (
            "Extract bibliographic metadata from the following book front/back matter. "
            "Return compact JSON only with keys: title, author, publisher, publish_year, "
            "isbn, pages, edition, language. If uncertain, use an empty string.\n\n"
            f"FRONT:\n{front_text[:4000]}\n\nBACK:\n{back_text[:3000]}"
        )
        result = client.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=800,
        )
        content = result.get("content", "") if isinstance(result, dict) else ""
        parsed = self._parse_json_object(content)
        return {key: self._clean_field(value) for key, value in parsed.items() if isinstance(value, str)}

    def generate_citation_filenames(self, metadata: BookMetadata, style: str = "chicago") -> str:
        title = self._safe_filename_part(metadata.title or UNKNOWN, max_length=50)
        author = self._safe_filename_part(metadata.author or UNKNOWN, max_length=30)
        year = self._safe_filename_part(metadata.publish_year or "n.d.", max_length=12)
        ext = Path(metadata.original_filename).suffix or ".pdf"

        if style == "apa":
            stem = f"{year}_{author}_{title}"
        else:
            stem = f"{author}_{title}_{year}"
        return f"{stem}{ext}"

    def process_single_file(self, file_path: Path) -> BookMetadata:
        metadata = BookMetadata(original_filename=file_path.name, process_status="processing")

        try:
            total_pages = self._get_page_count(file_path)
            front_start = 1
            front_end = min(self.front_pages, total_pages)
            back_start = max(1, total_pages - self.back_pages + 1) if self.back_pages else total_pages
            back_end = total_pages

            metadata.front_pages_text = self.extract_pages_text(file_path, front_start, front_end)
            metadata.back_pages_text = (
                self.extract_pages_text(file_path, back_start, back_end)
                if self.back_pages and back_start > front_end
                else ""
            )

            extraction_sources = self._populate_metadata(metadata)
            metadata.new_filename = self.generate_citation_filenames(metadata)
            self._populate_citations(metadata)
            self._finalize_quality(metadata, extraction_sources)
            metadata.process_status = "success" if not metadata.error_message else "failed"
        except Exception as exc:
            metadata.process_status = "failed"
            metadata.error_message = f"{type(exc).__name__}: {exc}"
            metadata.needs_review = True
            metadata.review_notes.append("processing failed")
        return metadata

    def process_all(self) -> List[BookMetadata]:
        self.results = []
        for file_path in self.scan_directory():
            result = self.process_single_file(file_path)
            self.results.append(result)
            if result.process_status == "success" and result.new_filename:
                artifact = self._save_file(file_path, result.new_filename)
                if artifact:
                    result.artifacts.append(artifact)
        return self.results

    def export_csv(self, output_path: str) -> bool:
        if not self.results:
            return False

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(self.results[0].to_dict().keys())
        try:
            with path.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for result in self.results:
                    writer.writerow(result.to_dict())
            return True
        except Exception:
            return False

    def export_records(self, output_path: str) -> bool:
        """Export normalized citation records for workflow reuse."""

        records = [result.to_citation_record() for result in self.results]
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False

    def get_summary(self) -> Dict[str, Any]:
        total = len(self.results)
        success = sum(1 for item in self.results if item.process_status == "success")
        failed = sum(1 for item in self.results if item.process_status == "failed")
        review = sum(1 for item in self.results if item.needs_review)
        return {
            "total_files": total,
            "success": success,
            "failed": failed,
            "pending": sum(1 for item in self.results if item.process_status == "pending"),
            "needs_review": review,
            "success_rate": f"{success / total * 100:.1f}%" if total else "0%",
            "capabilities": self.get_capabilities(),
        }

    def _populate_metadata(self, metadata: BookMetadata) -> List[str]:
        sources: List[str] = []
        combined_regex = {}
        if "regex" in self.metadata_backends:
            combined_regex.update(self.extract_metadata_with_regex(metadata.front_pages_text, self.FRONT_PAGE_PATTERNS))
            back_meta = self.extract_metadata_with_regex(metadata.back_pages_text, self.BACK_PAGE_PATTERNS)
            for key, value in back_meta.items():
                combined_regex.setdefault(key, value)
            self._apply_metadata(metadata, combined_regex)
            if combined_regex:
                sources.append("regex")

        if "llm" in self.metadata_backends:
            llm_meta = self.extract_metadata_with_llm(metadata.front_pages_text, metadata.back_pages_text)
            self._apply_metadata(metadata, llm_meta, fill_only=True)
            if llm_meta:
                sources.append("llm")

        metadata.extraction_summary = {
            "sources": sources,
            "front_chars": len(metadata.front_pages_text or ""),
            "back_chars": len(metadata.back_pages_text or ""),
            "filled_fields": [
                field_name
                for field_name in ("title", "author", "publisher", "publish_year", "isbn", "pages", "edition")
                if getattr(metadata, field_name)
            ],
        }
        return sources

    def _apply_metadata(self, metadata: BookMetadata, values: Dict[str, str], fill_only: bool = False) -> None:
        allowed = {"title", "author", "publisher", "publish_year", "isbn", "pages", "edition", "language"}
        for key, value in values.items():
            if key not in allowed or not value:
                continue
            if fill_only and getattr(metadata, key):
                continue
            setattr(metadata, key, value)

    def _populate_citations(self, metadata: BookMetadata) -> None:
        record = metadata.to_citation_record()
        metadata.citation_record = record
        formatted = self.citation_formatter.format_book_citation(
            title=metadata.title,
            author=metadata.author,
            publisher=metadata.publisher,
            year=metadata.publish_year,
            pages=metadata.pages,
            edition=metadata.edition,
            language=metadata.language,
        )
        metadata.citation_chicago = formatted.get("chicago", "")
        metadata.citation_apa = formatted.get("apa", "")
        metadata.citation_gb7714 = formatted.get("gb7714", "")
        metadata.citation_mla = formatted.get("mla", "")
        metadata.citation_ieee = formatted.get("ieee", "")
        metadata.citation_harvard = formatted.get("harvard", "")
        metadata.citation_record.update(
            {
                "normalized_citation": metadata.citation_chicago,
                "formatted": formatted,
                "target_style": "chicago",
            }
        )

    def _finalize_quality(self, metadata: BookMetadata, extraction_sources: Sequence[str]) -> None:
        required = ("title", "author", "publish_year")
        missing = [field_name for field_name in required if not getattr(metadata, field_name)]
        optional_present = sum(1 for field_name in ("publisher", "isbn", "pages", "edition") if getattr(metadata, field_name))
        score = 0.25
        score += 0.45 * ((len(required) - len(missing)) / len(required))
        score += 0.20 * min(optional_present / 2, 1)
        score += 0.10 if extraction_sources else 0
        metadata.confidence = round(min(score, 0.98), 2)
        metadata.needs_review = bool(missing or metadata.confidence < 0.70)
        metadata.review_notes = [f"missing {field_name}" for field_name in missing]
        if not extraction_sources:
            metadata.review_notes.append("no metadata extraction source succeeded")
        metadata.backend = "hybrid" if "llm" in extraction_sources else "script"
        metadata.provider = self.llm_provider if "llm" in extraction_sources else "local_rules"
        metadata.model = self.llm_model if "llm" in extraction_sources else None
        metadata.capabilities = ["regex_metadata", "citation_render", "filename_policy"]
        if "llm" in extraction_sources:
            metadata.capabilities.append("metadata_completion")
        metadata.citation_record.update(
            {
                "backend": metadata.backend,
                "provider": metadata.provider,
                "model": metadata.model,
                "confidence": metadata.confidence,
                "needs_review": metadata.needs_review,
                "notes": list(metadata.review_notes),
            }
        )

    def _save_file(self, original_path: Path, new_filename: str) -> Dict[str, Any]:
        output_path = self.output_dir / new_filename
        if output_path.exists() and not self.overwrite:
            counter = 1
            while output_path.exists():
                output_path = self.output_dir / f"{Path(new_filename).stem}_{counter}{Path(new_filename).suffix}"
                counter += 1
        if self.copy_files:
            shutil.copy2(original_path, output_path)
        else:
            shutil.move(str(original_path), str(output_path))
        return {
            "path": str(output_path),
            "type": "source_copy" if self.copy_files else "source_move",
            "stage": "organize",
            "description": "organized book source file",
        }

    def _get_page_count(self, file_path: Path) -> int:
        if file_path.suffix.lower() != ".pdf" or not PDF_PROCESSOR_AVAILABLE or PDFProcessor is None:
            return 1
        try:
            processor = PDFProcessor(str(file_path))
            return max(1, int(getattr(processor, "page_count", 1)))
        except Exception:
            return 1

    def _get_llm_client(self) -> Optional[Any]:
        if self._llm_client is not None:
            return self._llm_client
        if not LLM_CLIENT_AVAILABLE or LLMClient is None:
            return None
        config = {
            "provider": self.llm_provider,
            "model": self.llm_model,
            "api_key": self.api_key,
        }
        self._llm_client = LLMClient({key: value for key, value in config.items() if value})
        return self._llm_client

    def _parse_json_object(self, content: str) -> Dict[str, Any]:
        if not content:
            return {}
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _clean_field(self, value: Any) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip(" \t\r\n:：,，.;；")
        if len(text) > 300:
            text = text[:300].rstrip()
        return text

    def _safe_filename_part(self, value: str, max_length: int) -> str:
        cleaned = re.sub(r'[\\/:*?"<>|]', "", value or UNKNOWN)
        cleaned = re.sub(r"\s+", "_", cleaned).strip("._ ")
        return (cleaned or UNKNOWN)[:max_length]


def create_book_citation_organizer(input_dir: str, output_dir: str, **kwargs: Any) -> BookCitationOrganizer:
    return BookCitationOrganizer(input_dir=input_dir, output_dir=output_dir, **kwargs)
