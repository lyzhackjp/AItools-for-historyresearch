from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import uuid
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from xml.etree import ElementTree as ET

import requests

from modules.workflows._legacy import load_legacy_module
from modules.historical_citation.alignment import (
    align_translation,
    parse_llm_json,
    score_alignment_candidate,
    segment_page_text,
    trim_aligned_segment,
)
from modules.historical_citation.docx_parser import (
    build_citation_candidates,
    collect_text,
    extract_paragraph_content,
    parse_docx_document,
)
from modules.historical_citation.cross_validation import (
    cross_validate_fulltext_ocr_case,
    cross_validate_fulltext_ocr_cases,
)
from modules.historical_citation.footnote_parser import (
    DEFAULT_PAGE_PATTERNS,
    DEFAULT_QUOTE_PATTERNS,
    DEFAULT_STOPWORD_PREFIXES,
    DEFAULT_TITLE_PATTERNS,
    detect_source_type,
    extract_author,
    extract_pages,
    extract_publisher,
    extract_quotes,
    extract_title,
    is_verifiable_footnote,
    parse_footnote_text,
    pick_translation_text,
)
from modules.historical_citation.download_index import (
    find_cached_range_pdf as find_cached_range_pdf_from_index,
)
from modules.historical_citation.llm_review import (
    OllamaChatClient,
    review_alignment_with_llm,
)
from modules.historical_citation.models import (
    CitationCandidate,
    NDLSearchMatch,
    ParsedFootnote,
    ParsedParagraph,
)
from modules.historical_citation.ndl_fulltext_context import probe_ndl_fulltext_context
from modules.historical_citation.ndl_search import (
    author_query_terms,
    build_ndl_sru_queries,
    iter_ndl_search_keywords,
    parse_ndl_sru_records,
    resolve_ndlsearch_detail_url,
    score_ndl_record,
    search_ndl_public_api,
    title_query_terms,
)
from modules.historical_citation.page_mapping import (
    PAGE_MAPPING_CACHE_FILENAME,
    build_scan_page_range,
    estimate_book_pages_from_scan_page,
    estimate_scan_page_for_book_page,
    infer_page_mapping_from_front_matter_texts,
    infer_page_mapping_from_visible_page_numbers,
    load_page_mapping_cache,
    load_page_mapping_failure_cache,
    save_page_mapping_cache,
    save_page_mapping_failure_cache,
)
from modules.historical_citation.page_span import (
    classify_page_span,
    split_citation_claims_for_pages,
)
from modules.historical_citation.pdf_ocr import (
    detect_spread_gutter_x,
    extract_pages_directly as extract_pages_directly_from_pdf,
    extract_pdf_page_text as extract_pdf_page_text_from_pdf,
    extract_pdf_multi_panel_page_texts as extract_pdf_multi_panel_page_texts_from_pdf,
    extract_pdf_spread_page_texts as extract_pdf_spread_page_texts_from_pdf,
    map_target_page,
    ocr_image_text as ocr_image_text_from_pdf,
    render_pdf_page,
    split_double_page_image,
    wait_for_pdf_ready,
)
from modules.historical_citation.reporting import (
    describe_page_trace,
    render_verification_markdown_report,
    summarize_candidates,
)
from modules.historical_citation.source_acquisition import (
    build_download_page_plan,
    build_restricted_download_requests,
    download_public_pdf,
    expand_page_window,
    is_likely_digital_ndl_pid,
    select_preferred_source_match,
)
from modules.historical_citation.source_trials import append_source_trial, build_source_trial
from modules.historical_citation.source_platforms import (
    SourcePlatformAdapter,
    SourcePlatformRegistry,
    default_source_platform_registry,
)


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _normalize_source_title_for_compare(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "").lower()
    return re.sub(r"[\s《》『』「」【】\[\]（）()、，,。．.・:：;；\-―ー_]+", "", normalized)


def _source_title_base_without_volume(text: str) -> str:
    normalized = _normalize_source_title_for_compare(text)
    return re.sub(r"(上巻|下巻|上卷|下卷|上冊|下冊|上册|下册|第[一二三四五六七八九十0-9]+巻|第[一二三四五六七八九十0-9]+卷)", "", normalized)


class HistoricalCitationVerifier:
    """Verify translated historical quotes against cited Japanese sources."""

    PAGE_MAPPING_CACHE_FILENAME = PAGE_MAPPING_CACHE_FILENAME

    QUOTE_PATTERNS = DEFAULT_QUOTE_PATTERNS
    TITLE_PATTERNS = DEFAULT_TITLE_PATTERNS
    PAGE_PATTERNS = DEFAULT_PAGE_PATTERNS
    STOPWORD_PREFIXES = DEFAULT_STOPWORD_PREFIXES
    PAGE_MAPPING_SAMPLE_END_PAGE = 40
    MIN_CITED_PAGE_ALIGNMENT_CONFIDENCE = 0.08
    MIN_PASSAGE_ALIGNMENT_CONFIDENCE = 0.12
    MIN_DIRECT_SUPPORT_CONFIDENCE = 0.60
    MAX_CONTEXT_PROMOTION_PAGE_DISTANCE = 1
    MIN_CONTEXT_PROMOTION_CONFIDENCE = 0.30
    MAX_WEAK_CITED_ALIGNMENT_CONFIDENCE = 0.20
    CONTEXT_ALIGNMENT_BETTER_MARGIN = 0.15
    SOURCE_FALLBACK_MAX_RETRIES = 1
    TRANSIENT_VERIFICATION_NOTE_PREFIXES = (
        "page_distance_from_citation:",
        "cited_page_alignment_used",
        "cited_pages_no_alignment_context_fallback",
        "cited_pages_not_extracted_context_fallback",
        "context_alignment_preview_higher_confidence:",
        "heuristic_alignment_used",
        "llm_alignment_failed:",
        "no_passage_candidates",
        "low_alignment_confidence_on_cited_pages:",
        "source_pdf_reused",
        "source_pdf_cached_range_reused:",
        "source_pdf_not_downloaded_without_verified_page_mapping",
        "source_pdf_not_available",
        "page_text_not_extracted",
        "ocr_backend_unavailable:",
        "page_mapping_skipped_after_failure:",
        "page_mapping_required_for_ndl_restricted_download[",
        "page_mapping_retry_after_soft_failure:",
        "restricted_download_skipped[",
        "restricted_download_skipped_no_ndl_pid",
        "restricted_download_failed",
        "restricted_download_range_adjusted[",
        "mapped_footnote_page_out_of_scan_range[",
        "source_pdf_rejected_adjusted_range",
        "source_unavailable:",
        "download_fast_failed:",
        "ndlsearch_detail_resolution:no_digital_pid",
        "source_match_metadata_mismatch_filtered",
        "source_match_all_metadata_mismatched",
    )
    SUCCESSFUL_SOURCE_ACQUISITION_NOISE_PREFIXES = (
        "page_mapping_skipped_after_failure:",
        "page_mapping_required_for_ndl_restricted_download[",
        "page_mapping_retry_after_soft_failure:",
        "restricted_download_skipped[",
        "restricted_download_skipped_no_ndl_pid",
        "restricted_download_failed",
        "download_fast_failed:",
        "ndlsearch_detail_resolution:no_digital_pid",
        "source_unavailable:",
        "source_pdf_reuse_skipped_range_filename_mismatch",
    )
    TRANSIENT_VERIFICATION_ARTIFACT_KEYS = (
        "alignment_scope",
        "citation_priority_pages",
        "cited_extracted_pages",
        "context_alignment_preview",
        "direct_extracted_pages",
        "subprocess_extracted_pages",
        "extracted_page_texts",
        "matched_scan_page",
        "matched_book_pages",
        "page_distance_from_citation",
        "review_context_window",
        "review_context",
        "llm_review",
        "page_label_mode",
        "pdf_readiness",
        "ocr_backend_available",
        "page_mapping_required_but_unavailable",
        "page_mapping_unavailable_ndl_ids",
        "download_attempted_ndl_ids",
        "download_attempt",
        "downloaded_page_range_requested",
        "downloaded_page_range_actual",
        "source_availability",
    )
    HARD_PAGE_MAPPING_FAILURE_MARKERS = (
        "remote_copy_only_no_print",
        "ndl_toc_not_found",
        "ndl_toc_empty",
        "front_matter_mapping_not_inferred",
        "download_not_pdf",
        "download_http_404",
        "download_http_403",
        "print_button_not_found",
        "download_link_not_found",
    )

    def __init__(
        self,
        ndl_download_module: Any = None,
        pdf_processor: Any = None,
        ocr_processor: Any = None,
        llm_client: Any = None,
        review_llm_client: Any = None,
        enable_llm_review: bool = True,
        prefer_ollama_review: bool = False,
        source_platforms: Optional[Sequence[SourcePlatformAdapter]] = None,
        allow_external_ndl_fallback: bool = True,
    ):
        self._ndl_download_module = ndl_download_module
        self._prefer_external_ndl_module = ndl_download_module is not None
        self._allow_external_ndl_fallback = allow_external_ndl_fallback
        self._pdf_processor = pdf_processor
        self._ocr_processor = ocr_processor
        self._llm_client = llm_client
        self._review_llm_client = review_llm_client
        self._enable_llm_review = enable_llm_review
        self._prefer_ollama_review = prefer_ollama_review
        self._source_platform_registry: Optional[SourcePlatformRegistry] = (
            SourcePlatformRegistry(source_platforms) if source_platforms is not None else None
        )
        self._page_mapping_cache: Dict[str, Dict[str, Any]] = {}
        self._page_mapping_failure_cache: Dict[str, str] = {}
        self._ndl_total_pages_cache: Dict[str, Optional[int]] = {}
        self._ndlsearch_detail_resolution_cache: Dict[str, Dict[str, Any]] = {}
        self._last_page_mapping_sample_failure: Optional[str] = None

    def get_capabilities(self) -> Dict[str, Any]:
        """Return an agent/workflow-facing capability snapshot."""
        if self._source_platform_registry is not None:
            source_platforms = [platform.name for platform in self._source_platform_registry.platforms]
        else:
            source_platforms = [
                "ndl",
                "japan_search",
                "internet_archive",
                "jstage",
                "cinii_research",
                "jacar",
                "diet_proceedings",
                "egov_law",
            ]
        return {
            "module": "historical_citation_verifier",
            "backend": "script",
            "provider": "local_rules",
            "model": None,
            "input_formats": ["docx"],
            "output_types": ["historical_citation_parse", "historical_citation_verification"],
            "source_platforms": source_platforms,
            "capabilities": [
                "docx_footnote_parse",
                "translation_quote_candidate_building",
                "source_metadata_search",
                "restricted_download_request_building",
                "pdf_page_window_ocr",
                "translation_source_alignment",
                "markdown_json_report_export",
            ],
            "fallback_order": [
                "script:docx_parser",
                "public_api:ndl",
                "public_api:japan_search",
                "public_api:internet_archive",
                "local_ocr",
                "llm_api",
                "local_llm",
                "skill",
                "mcp",
            ],
            "privacy": {
                "default_parse_is_offline": True,
                "external_search_requires_search_ndl": True,
                "download_requires_download_source": True,
            },
        }

    def parse_docx_package(
        self,
        file_path: str,
        *,
        include_unquoted: bool = False,
    ) -> Dict[str, Any]:
        """Parse a DOCX into a stable package without network search or downloads."""
        parsed = self.parse_docx(file_path)
        candidates = self.build_candidates(
            parsed["paragraphs"],
            parsed["footnotes"],
            include_unquoted=include_unquoted,
        )
        candidate_dicts = [item.to_dict() for item in candidates]
        quality_flags = self._parse_quality_flags(parsed, candidates)
        confidence = self._estimate_parse_confidence(parsed, candidates, quality_flags)
        return {
            "type": "historical_citation_parse",
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "backend": "script",
            "provider": "local_rules",
            "model": None,
            "confidence": confidence,
            "needs_review": bool(quality_flags),
            "quality_flags": quality_flags,
            "document": parsed["document"],
            "paragraphs": [item.to_dict() for item in parsed["paragraphs"]],
            "footnotes": [item.to_dict() for item in parsed["footnotes"]],
            "candidates": candidate_dicts,
            "summary": {
                "paragraph_count": len(parsed["paragraphs"]),
                "footnote_count": len(parsed["footnotes"]),
                "candidate_count": len(candidates),
                "include_unquoted": include_unquoted,
            },
            "capabilities": self.get_capabilities(),
        }

    def verify_docx_package(
        self,
        file_path: str,
        *,
        search_ndl: bool = True,
        download_source: bool = False,
        restricted_download: bool = False,
        max_search_results: int = 5,
        page_window: int = 4,
        ocr_model: str = "ndlocr_lite",
        output_dir: Optional[str] = None,
        platform_names: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Run verification and wrap legacy output in a workflow package."""
        result = self.verify_docx(
            file_path,
            search_ndl=search_ndl,
            download_source=download_source,
            restricted_download=restricted_download,
            max_search_results=max_search_results,
            page_window=page_window,
            ocr_model=ocr_model,
            output_dir=output_dir,
            platform_names=platform_names,
        )
        quality_flags = self._verification_quality_flags(result)
        confidence = self._estimate_verification_confidence(result, quality_flags)
        return {
            "type": "historical_citation_verification",
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "backend": "script",
            "provider": "local_rules",
            "model": None,
            "confidence": confidence,
            "needs_review": bool(quality_flags),
            "quality_flags": quality_flags,
            "document": result.get("document", {}),
            "summary": result.get("summary", {}),
            "results": result.get("results", []),
            "artifacts": result.get("artifacts", {}),
            "execution": {
                "search_ndl": search_ndl,
                "download_source": download_source,
                "restricted_download": restricted_download,
                "max_search_results": max_search_results,
                "page_window": page_window,
                "ocr_model": ocr_model,
                "platform_names": list(platform_names or []),
            },
            "capabilities": self.get_capabilities(),
        }

    def _load_page_mapping_cache(self, output_dir: Path) -> Dict[str, Dict[str, Any]]:
        self._page_mapping_cache = load_page_mapping_cache(
            output_dir,
            current_cache=self._page_mapping_cache,
        )
        return self._page_mapping_cache

    def _save_page_mapping_cache(self, output_dir: Path, ndl_id: str, mapping: Dict[str, Any]) -> None:
        self._page_mapping_cache = save_page_mapping_cache(
            output_dir,
            ndl_id,
            mapping,
            current_cache=self._page_mapping_cache,
        )

    def _load_page_mapping_failure_cache(self, output_dir: Path) -> Dict[str, str]:
        self._page_mapping_failure_cache = load_page_mapping_failure_cache(
            output_dir,
            current_cache=self._page_mapping_failure_cache,
        )
        return self._page_mapping_failure_cache

    def _save_page_mapping_failure_cache(self, output_dir: Path, ndl_id: str, reason: str) -> None:
        self._page_mapping_failure_cache = save_page_mapping_failure_cache(
            output_dir,
            ndl_id,
            reason,
            current_cache=self._page_mapping_failure_cache,
        )

    def _get_ndl_total_pages_quick(self, ndl_id: Optional[str]) -> Optional[int]:
        if not ndl_id:
            return None
        cache_key = str(ndl_id)
        if cache_key in self._ndl_total_pages_cache:
            return self._ndl_total_pages_cache[cache_key]
        total_pages: Optional[int] = None
        try:
            response = requests.get(
                f"https://dl.ndl.go.jp/api/meta/search/toc/facet/{cache_key}",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            if response.status_code == 200:
                payload = response.json()
                bundles = payload.get("contentsBundles") or []
                contents = (bundles[0] if bundles else {}).get("contents") or []
                if contents:
                    total_pages = len(contents)
        except Exception:
            total_pages = None
        self._ndl_total_pages_cache[cache_key] = total_pages
        return total_pages

    def _resolve_ndlsearch_match_pid(self, match: NDLSearchMatch) -> None:
        if (
            (getattr(match, "platform", None) or "ndl") != "ndl"
            or getattr(match, "ndl_id", None)
            or not getattr(match, "url", None)
        ):
            return
        metadata = getattr(match, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
            setattr(match, "metadata", metadata)
        resolution = metadata.get("ndlsearch_detail_resolution")
        if not isinstance(resolution, dict):
            if match.url in self._ndlsearch_detail_resolution_cache:
                resolution = self._ndlsearch_detail_resolution_cache[match.url]
            else:
                resolution = resolve_ndlsearch_detail_url(match.url)
                self._ndlsearch_detail_resolution_cache[match.url] = resolution
            metadata["ndlsearch_detail_resolution"] = {
                key: value for key, value in resolution.items() if key != "url"
            }
        ndl_ids = resolution.get("ndl_ids") or []
        if ndl_ids:
            match.ndl_id = str(ndl_ids[0])
            match.url = f"https://dl.ndl.go.jp/pid/{match.ndl_id}"
            match.platform_item_id = match.ndl_id
            metadata["resolved_from_ndlsearch_url"] = True

    def _resolve_ndlsearch_matches(self, candidate: CitationCandidate) -> None:
        for match in candidate.ndl_matches:
            self._resolve_ndlsearch_match_pid(match)

    def _ordered_matches_for_pages(
        self,
        matches: Sequence[NDLSearchMatch],
        page_numbers: Sequence[int],
    ) -> List[NDLSearchMatch]:
        if not matches:
            return []
        max_page = max([int(page) for page in page_numbers if int(page) > 0], default=0)
        indexed_matches = list(enumerate(matches))

        def sort_key(item: Tuple[int, NDLSearchMatch]) -> Tuple[int, int, float, int]:
            index, match = item
            ndl_id = getattr(match, "ndl_id", None)
            total_pages = self._get_ndl_total_pages_quick(ndl_id) if ndl_id else None
            if max_page and total_pages and (
                max_page <= total_pages
                or max_page - total_pages <= 20
                or max_page <= total_pages * 2 + 40
            ):
                page_rank = 0
            elif total_pages and max_page and max_page - total_pages > 20:
                page_rank = 2
            else:
                page_rank = 1
            digital_rank = 0 if is_likely_digital_ndl_pid(ndl_id) else 1
            return (page_rank, digital_rank, -float(getattr(match, "score", 0) or 0), index)

        return [match for _index, match in sorted(indexed_matches, key=sort_key)]

    def _select_preferred_match_for_pages(
        self,
        matches: Sequence[NDLSearchMatch],
        page_numbers: Sequence[int],
    ) -> Optional[NDLSearchMatch]:
        ordered = self._ordered_matches_for_pages(matches, page_numbers)
        if ordered:
            return ordered[0]
        return select_preferred_source_match(matches)

    def verify_docx(
        self,
        file_path: str,
        *,
        search_ndl: bool = True,
        download_source: bool = False,
        restricted_download: bool = False,
        max_search_results: int = 5,
        page_window: int = 4,
        ocr_model: str = "ndlocr_lite",
        output_dir: Optional[str] = None,
        platform_names: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        parsed = self.parse_docx(file_path)
        candidates = self.build_candidates(parsed["paragraphs"], parsed["footnotes"])
        report_dir = Path(output_dir or Path("output") / "historical_citation_verification" / uuid.uuid4().hex[:8])
        report_dir.mkdir(parents=True, exist_ok=True)

        verification_results: List[CitationCandidate] = []
        for candidate in candidates:
            if search_ndl:
                candidate.ndl_matches = self.search_sources(
                    candidate.footnote,
                    max_results=max_search_results,
                    platform_names=platform_names,
                )
                if candidate.ndl_matches:
                    if all(match.metadata.get("source_mismatch") for match in candidate.ndl_matches):
                        candidate.verification_status = "source_mismatch"
                        candidate.notes.append("all_source_candidates_failed_metadata_filter")
                    else:
                        candidate.verification_status = "source_found"
                else:
                    candidate.verification_status = "source_not_found"

            if download_source and candidate.ndl_matches and candidate.verification_status != "source_mismatch":
                self._enrich_with_source_excerpt(
                    candidate,
                    output_dir=report_dir,
                    restricted_download=restricted_download,
                    page_window=page_window,
                    ocr_model=ocr_model,
                )

            verification_results.append(candidate)

        summary = self._summarize_results(verification_results)
        json_path = report_dir / "verification_results.json"
        markdown_path = report_dir / "verification_report.md"
        json_path.write_text(
            json.dumps(
                {
                    "document": parsed["document"],
                    "summary": summary,
                    "results": [item.to_dict() for item in verification_results],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        markdown_path.write_text(
            self.render_markdown_report(parsed["document"], verification_results),
            encoding="utf-8",
        )

        return {
            "success": True,
            "document": parsed["document"],
            "summary": summary,
            "paragraphs": [item.to_dict() for item in parsed["paragraphs"]],
            "footnotes": [item.to_dict() for item in parsed["footnotes"]],
            "results": [item.to_dict() for item in verification_results],
            "artifacts": {
                "output_dir": str(report_dir.resolve()),
                "json_report": str(json_path.resolve()),
                "markdown_report": str(markdown_path.resolve()),
            },
        }

    def parse_docx(self, file_path: str) -> Dict[str, Any]:
        return parse_docx_document(
            file_path,
            extract_quotes=self.extract_quotes,
            parse_footnote=self.parse_footnote,
        )

    def build_candidates(
        self,
        paragraphs: Sequence[ParsedParagraph],
        footnotes: Sequence[ParsedFootnote],
        *,
        include_unquoted: bool = False,
    ) -> List[CitationCandidate]:
        return build_citation_candidates(
            paragraphs,
            footnotes,
            pick_translation_text=lambda paragraph, footnote_id=None: self._pick_translation_text(
                paragraph,
                include_unquoted=include_unquoted,
                footnote_id=footnote_id,
            ),
            is_verifiable_footnote=self._is_verifiable_footnote,
        )

    def parse_footnote(self, note_id: str, text: str) -> ParsedFootnote:
        return parse_footnote_text(
            note_id,
            text,
            title_patterns=self.TITLE_PATTERNS,
            page_patterns=self.PAGE_PATTERNS,
        )

    def extract_quotes(self, text: str) -> List[str]:
        return extract_quotes(text, quote_patterns=self.QUOTE_PATTERNS)

    def search_ndl_sources(self, footnote: ParsedFootnote, *, max_results: int = 5) -> List[NDLSearchMatch]:
        return self.search_sources(footnote, max_results=max_results, platform_names=["ndl"])

    def search_sources(
        self,
        footnote: ParsedFootnote,
        *,
        max_results: int = 5,
        platform_names: Optional[Iterable[str]] = None,
    ) -> List[NDLSearchMatch]:
        return self._get_source_platform_registry().search(
            footnote,
            max_results=max_results,
            platform_names=platform_names,
        )

    def probe_ndl_fulltext_context(
        self,
        pid: str,
        keyword_variants: Iterable[str],
        *,
        global_queries: Optional[Iterable[str]] = None,
        max_global_results: int = 8,
    ) -> Dict[str, Any]:
        """Probe target-PID NDL fulltext snippets for weak page evidence."""

        return probe_ndl_fulltext_context(
            pid,
            keyword_variants,
            global_queries=global_queries,
            max_global_results=max_global_results,
        ).to_dict()

    def cross_validate_fulltext_ocr_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        """Cross-check one checkpoint candidate's OCR against NDL fulltext snippets."""

        return cross_validate_fulltext_ocr_case(case).to_dict()

    def cross_validate_fulltext_ocr_cases(self, cases: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in cross_validate_fulltext_ocr_cases(cases)]

    def _search_ndl_via_download_module(
        self,
        footnote: ParsedFootnote,
        *,
        max_results: int,
        use_api: bool,
    ) -> List[Any]:
        module = self._get_ndl_download_module()
        collected: List[Any] = []
        seen_keys: set[str] = set()
        for keyword in self._iter_ndl_search_keywords(footnote):
            try:
                records = module.search(
                    keyword,
                    max_results=max_results,
                    use_api=use_api,
                    headless=True,
                )
            except BaseException:
                continue
            for record in records:
                key = getattr(record, "ndl_id", None) or getattr(record, "url", None) or getattr(record, "title", None)
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    collected.append(record)
            if collected:
                break
        return collected[:max_results]

    def render_markdown_report(
        self,
        document: Dict[str, Any],
        candidates: Sequence[CitationCandidate],
    ) -> str:
        return render_verification_markdown_report(document, candidates)

    def _summarize_results(self, candidates: Sequence[CitationCandidate]) -> Dict[str, int]:
        return summarize_candidates(candidates)

    def _parse_quality_flags(
        self,
        parsed: Dict[str, Any],
        candidates: Sequence[CitationCandidate],
    ) -> List[str]:
        flags: List[str] = []
        paragraphs = parsed.get("paragraphs", [])
        footnotes = parsed.get("footnotes", [])
        if not paragraphs:
            flags.append("no_paragraphs")
        if not footnotes:
            flags.append("no_footnotes")
        if footnotes and not candidates:
            flags.append("no_verifiable_candidates")
        if any(not item.footnote.title for item in candidates):
            flags.append("candidate_missing_title")
        if any(not item.footnote.page_numbers for item in candidates):
            flags.append("candidate_missing_page_numbers")
        if any(not item.translation_text for item in candidates):
            flags.append("candidate_missing_translation_text")
        return flags

    def _estimate_parse_confidence(
        self,
        parsed: Dict[str, Any],
        candidates: Sequence[CitationCandidate],
        quality_flags: Sequence[str],
    ) -> float:
        confidence = 0.35
        if parsed.get("paragraphs"):
            confidence += 0.20
        if parsed.get("footnotes"):
            confidence += 0.20
        if candidates:
            confidence += 0.15
        confidence -= min(0.30, len(quality_flags) * 0.08)
        return round(max(0.1, min(confidence, 0.95)), 2)

    def _verification_quality_flags(self, result: Dict[str, Any]) -> List[str]:
        flags = self._summary_quality_flags(result.get("summary", {}))
        for item in result.get("results", []):
            if not item.get("translation_text"):
                flags.append("result_missing_translation_text")
            if item.get("confidence") is not None and item.get("confidence", 0) < 0.45:
                flags.append("low_alignment_confidence")
            if item.get("notes"):
                flags.extend(f"note:{note}" for note in item.get("notes", [])[:3])
        return sorted(set(flags))

    def _summary_quality_flags(self, summary: Dict[str, Any]) -> List[str]:
        flags: List[str] = []
        if summary.get("total_candidates", 0) == 0:
            flags.append("no_candidates")
        status_keys = [
            "source_not_found",
            "source_mismatch",
            "needs_manual_review",
            "download_failed",
            "download_timeout",
            "runner_failed",
            "page_mapping_unavailable",
            "unmatched",
        ]
        for key in status_keys:
            if summary.get(key, 0):
                flags.append(key)
        return flags

    def _estimate_verification_confidence(
        self,
        result: Dict[str, Any],
        quality_flags: Sequence[str],
    ) -> float:
        summary = result.get("summary", {})
        total = max(int(summary.get("total_candidates", 0) or 0), 1)
        matched = int(summary.get("matched", 0) or 0)
        source_found = int(summary.get("source_found", 0) or 0)
        confidence = 0.35 + (matched / total) * 0.35 + (source_found / total) * 0.15
        if result.get("artifacts", {}).get("json_report"):
            confidence += 0.05
        confidence -= min(0.35, len(quality_flags) * 0.06)
        return round(max(0.1, min(confidence, 0.95)), 2)

    def _describe_page_trace(self, candidate: CitationCandidate) -> str:
        return describe_page_trace(candidate)

    def _measure_page_distance_from_citation(self, candidate: CitationCandidate) -> Optional[int]:
        cited_pages = list(candidate.footnote.page_numbers or [])
        if not cited_pages:
            return None

        matched_book_pages = candidate.artifacts.get("matched_book_pages")
        if matched_book_pages:
            return min(abs(int(matched_page) - int(cited_page)) for matched_page in matched_book_pages for cited_page in cited_pages)

        if candidate.matched_page is None:
            return None
        return min(abs(int(candidate.matched_page) - int(cited_page)) for cited_page in cited_pages)

    def _clean_ocr_text_for_review(self, text: str) -> str:
        cleaned = unicodedata.normalize("NFKC", text.replace("\r", "\n"))
        cleaned = (
            cleaned.replace("亞", "亜")
            .replace("戰", "戦")
            .replace("國", "国")
            .replace("會", "会")
            .replace("體", "体")
            .replace("讀", "読")
            .replace("號", "号")
            .replace("龜", "亀")
            .replace("實", "実")
            .replace("踐", "践")
            .replace("聖", "圣")
            .replace("萬", "万")
            .replace("廣", "広")
            .replace("驛", "駅")
            .replace("觸", "触")
            .replace("譯", "訳")
            .replace("證", "証")
            .replace("拜", "拝")
            .replace("豫", "予")
            .replace("竝", "並")
            .replace("爲", "為")
            .replace("兩", "両")
            .replace("壹", "一")
            .replace("貳", "二")
            .replace("參", "三")
        )
        cleaned = re.sub(r"E\d{6,}", "", cleaned)
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r" ?\n ?", "\n", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        cleaned = re.sub(r"(?<=\w)-\n(?=\w)", "", cleaned)
        lines = []
        for raw_line in cleaned.splitlines():
            line = raw_line.strip()
            if not line:
                lines.append("")
                continue
            if re.fullmatch(r"[0-9０-９]{1,4}", line):
                continue
            lines.append(line)
        cleaned = "\n".join(lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def _clear_transient_verification_state(self, candidate: CitationCandidate) -> None:
        candidate.notes = [
            note
            for note in (candidate.notes or [])
            if not any(str(note).startswith(prefix) for prefix in self.TRANSIENT_VERIFICATION_NOTE_PREFIXES)
        ]
        for key in self.TRANSIENT_VERIFICATION_ARTIFACT_KEYS:
            candidate.artifacts.pop(key, None)
        candidate.matched_page = None
        candidate.matched_japanese = ""
        candidate.confidence = None
        candidate.support_status = "unassessed"
        candidate.support_reason = ""
        candidate.evidence_scope = ""

    def _clear_successful_source_acquisition_noise(self, candidate: CitationCandidate) -> None:
        candidate.notes = [
            note
            for note in (candidate.notes or [])
            if not any(str(note).startswith(prefix) for prefix in self.SUCCESSFUL_SOURCE_ACQUISITION_NOISE_PREFIXES)
        ]
        candidate.artifacts.pop("source_availability", None)

    def _mark_source_unavailable(
        self,
        candidate: CitationCandidate,
        *,
        reason: str,
        ndl_id: Optional[str] = None,
        source_id: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        normalized_reason = str(reason or "unknown")
        if (
            normalized_reason == "no_digital_pid"
            and candidate.artifacts.get("page_mapping_required_but_unavailable")
            and candidate.artifacts.get("page_mapping_unavailable_ndl_ids")
        ):
            return
        current = candidate.artifacts.get("source_availability")
        if isinstance(current, dict) and current.get("status") == "unavailable":
            priority = {
                "no_digital_pid": 10,
                "ndl_toc_not_found": 30,
                "ndl_toc_empty": 30,
                "invalid_page_range": 30,
                "remote_copy_only_no_print": 50,
                "download_not_pdf": 50,
                "download_http_404": 50,
                "print_button_not_found": 50,
                "download_link_not_found": 50,
                "mapped_page_out_of_scan_range": 60,
                "downloaded_page_range_adjusted": 60,
            }
            current_reason = str(current.get("reason") or "unknown")
            if priority.get(normalized_reason, 1) < priority.get(current_reason, 1):
                return
        availability = {
            "status": "unavailable",
            "reason": normalized_reason,
        }
        normalized_source_id = source_id or ndl_id
        if normalized_source_id:
            availability["source_id"] = str(normalized_source_id)
        if ndl_id:
            availability["ndl_id"] = str(ndl_id)
        if detail:
            availability["detail"] = str(detail)
        candidate.artifacts["source_availability"] = availability
        self._record_source_unavailability_attempt(candidate, availability)
        note = f"source_unavailable:{normalized_reason}"
        if ndl_id:
            note += f"[{ndl_id}]"
        if detail:
            note += f":{detail}"
        if note not in candidate.notes:
            candidate.notes.append(note)

    def _record_source_unavailability_attempt(
        self,
        candidate: CitationCandidate,
        availability: Dict[str, Any],
    ) -> None:
        attempts = candidate.artifacts.setdefault("source_unavailable_attempts", [])
        if not isinstance(attempts, list):
            candidate.artifacts["source_unavailable_attempts"] = attempts = []
        source_id = str(availability.get("source_id") or availability.get("ndl_id") or "")
        reason = str(availability.get("reason") or "unknown")
        if any(
            isinstance(item, dict)
            and str(item.get("source_id") or item.get("ndl_id") or "") == source_id
            and str(item.get("reason") or "") == reason
            for item in attempts
        ):
            return
        attempt = {
                "source_id": source_id,
                "ndl_id": availability.get("ndl_id"),
                "reason": reason,
                "detail": availability.get("detail"),
                "verification_status": "source_unavailable",
            }
        attempts.append(attempt)
        append_source_trial(
            candidate.artifacts,
            build_source_trial(
                role="unavailable",
                source=attempt,
                verification_status="source_unavailable",
                failure_reason=reason,
                detail=availability.get("detail"),
            ),
        )

    def _normalize_download_unavailability_reason(self, error_message: str) -> str:
        normalized = str(error_message or "").lower()
        if "remote_copy_only_no_print" in normalized:
            return "remote_copy_only_no_print"
        if "download_not_pdf" in normalized:
            return "download_not_pdf"
        if "download_http_404" in normalized:
            return "download_http_404"
        if "download_http_403" in normalized:
            return "download_http_403"
        if "print_button_not_found" in normalized:
            return "print_button_not_found"
        if "download_link_not_found" in normalized:
            return "download_link_not_found"
        if "ndl_toc_not_found" in normalized:
            return "ndl_toc_not_found"
        if "ndl_toc_empty" in normalized:
            return "ndl_toc_empty"
        if "invalid_page_range" in normalized:
            return "invalid_page_range"
        return ""

    def _serialize_extracted_pages(
        self,
        extracted_pages: Sequence[Tuple[int, str]],
    ) -> List[Dict[str, Any]]:
        payload: List[Dict[str, Any]] = []
        for page_number, page_text in extracted_pages:
            payload.append(
                {
                    "page": page_number,
                    "text": page_text,
                    "cleaned_text": self._clean_ocr_text_for_review(page_text),
                }
            )
        return payload

    def _build_review_context(
        self,
        candidate: CitationCandidate,
        *,
        extracted_pages: Sequence[Tuple[int, str]],
        context_radius: int = 2,
    ) -> List[Dict[str, Any]]:
        page_entries = self._serialize_extracted_pages(extracted_pages)
        if not page_entries:
            return []

        matched_page = candidate.matched_page
        if matched_page is None:
            return page_entries[: min(5, len(page_entries))]

        nearby_entries = [
            entry
            for entry in page_entries
            if abs(int(entry["page"]) - int(matched_page)) <= context_radius
        ]
        selected_entries = nearby_entries or page_entries[: min(5, len(page_entries))]
        return sorted(selected_entries, key=lambda item: int(item.get("page", 0)))

    def _review_precise_alignment(self, candidate: CitationCandidate) -> None:
        if not self._enable_llm_review or not candidate.matched_japanese:
            return
        llm_client = self._get_review_llm_client(optional=True)
        if llm_client is None:
            candidate.artifacts["llm_review"] = {
                "decision": "uncertain",
                "confidence": 0.0,
                "exact_sentence": "",
                "reason": "未配置可用 LLM 精核模型",
                "provider": "none",
                "eligible_for_llm_review": True,
                "llm_review_success": False,
                "llm_review_json_repaired": False,
                "llm_review_fallback_heuristic": False,
                "llm_review_failed": True,
            }
            return
        health_check = getattr(llm_client, "health_check", None)
        if callable(health_check):
            candidate.artifacts["llm_review_runtime"] = health_check()
        review = review_alignment_with_llm(
            candidate.translation_text,
            candidate.matched_japanese,
            llm_client=llm_client,
        )
        candidate.artifacts["llm_review"] = review

    def _match_identity(self, match: Optional[NDLSearchMatch]) -> str:
        if match is None:
            return ""
        return str(
            getattr(match, "ndl_id", None)
            or getattr(match, "platform_item_id", None)
            or getattr(match, "url", "")
            or ""
        )

    def _source_match_to_artifact(self, match: Optional[NDLSearchMatch]) -> Dict[str, Any]:
        if match is None:
            return {}
        metadata = getattr(match, "metadata", {}) or {}
        compact_metadata: Dict[str, Any] = {}
        if isinstance(metadata, dict):
            for key in (
                "identifier",
                "search_route",
                "source_rank",
                "source_match_warning",
                "ndlsearch_detail_resolution",
                "fulltext_hints",
            ):
                if key in metadata:
                    compact_metadata[key] = metadata.get(key)
        payload = {
            "ndl_id": getattr(match, "ndl_id", None),
            "platform_item_id": getattr(match, "platform_item_id", None),
            "url": getattr(match, "url", None),
            "platform": getattr(match, "platform", None),
            "title": getattr(match, "title", None),
            "score": getattr(match, "score", None),
        }
        if compact_metadata:
            payload["metadata"] = compact_metadata
        return payload

    def _store_ndl_fulltext_hints(
        self,
        candidate: CitationCandidate,
        match: Optional[NDLSearchMatch],
    ) -> None:
        metadata = getattr(match, "metadata", {}) if match is not None else {}
        if not isinstance(metadata, dict):
            return
        raw_hints = metadata.get("fulltext_hints") or []
        if not isinstance(raw_hints, list) or not raw_hints:
            return
        stored = candidate.artifacts.setdefault("ndl_fulltext_hints", [])
        if not isinstance(stored, list):
            candidate.artifacts["ndl_fulltext_hints"] = stored = []
        citation_pages = list(candidate.footnote.page_numbers or [])
        for hint in raw_hints[:10]:
            if not isinstance(hint, dict):
                continue
            enriched = dict(hint)
            if citation_pages:
                enriched["citation_pages"] = citation_pages
            if hint.get("pdf_page") and citation_pages:
                enriched["page_match_status"] = "pdf_page_hint_unmapped_to_source_page"
            elif hint.get("pdf_page"):
                enriched["page_match_status"] = "pdf_page_hint_only"
            else:
                enriched["page_match_status"] = "snippet_without_page_hint"
            key = (
                enriched.get("book_id"),
                enriched.get("pdf_page"),
                enriched.get("snippet"),
            )
            if any(
                isinstance(item, dict)
                and (item.get("book_id"), item.get("pdf_page"), item.get("snippet")) == key
                for item in stored
            ):
                continue
            stored.append(enriched)
        if stored and "ndlsearch_fulltext_hints_recorded" not in candidate.notes:
            candidate.notes.append("ndlsearch_fulltext_hints_recorded")

    def _selected_source_identity(self, candidate: CitationCandidate) -> str:
        selected = candidate.artifacts.get("selected_source_match") or {}
        if not isinstance(selected, dict):
            return ""
        return str(
            selected.get("ndl_id")
            or selected.get("platform_item_id")
            or selected.get("url")
            or ""
        )

    def _should_try_alternate_source(self, candidate: CitationCandidate) -> bool:
        try:
            retry_count = int(candidate.artifacts.get("alternate_source_retry_count") or 0)
        except (TypeError, ValueError):
            retry_count = 0
        if retry_count >= self.SOURCE_FALLBACK_MAX_RETRIES:
            return False
        if not candidate.ndl_matches or len(candidate.ndl_matches) <= 1:
            return False
        current_source_id = self._selected_source_identity(candidate)
        if not current_source_id:
            return False
        tried_ids = {
            str(item)
            for item in (candidate.artifacts.get("source_match_skip_ids") or [])
            if item
        }
        tried_ids.add(current_source_id)
        remaining = [
            match for match in candidate.ndl_matches
            if self._match_identity(match) and self._match_identity(match) not in tried_ids
        ]
        if not remaining:
            return False
        if (
            self._should_preserve_selected_source_after_weak_alignment(candidate)
            and not self._has_viable_same_title_digital_alternate(candidate, remaining)
        ):
            note = "alternate_source_retry_skipped_exact_title_primary_source"
            if note not in candidate.notes:
                candidate.notes.append(note)
            return False
        support_status = str(candidate.support_status or "")
        confidence = float(candidate.confidence or 0.0)
        if support_status == "not_supported":
            return True
        if support_status == "needs_manual_review" and confidence < self.MIN_PASSAGE_ALIGNMENT_CONFIDENCE:
            return True
        return False

    def _should_preserve_selected_source_after_weak_alignment(self, candidate: CitationCandidate) -> bool:
        selected = candidate.artifacts.get("selected_source_match")
        if not isinstance(selected, dict):
            return False
        selected_id = str(
            selected.get("ndl_id")
            or selected.get("platform_item_id")
            or selected.get("item_id")
            or ""
        )
        if not is_likely_digital_ndl_pid(selected_id):
            return False

        footnote_title = _normalize_source_title_for_compare(
            candidate.footnote.title or candidate.footnote.ndl_keyword
        )
        selected_title = _normalize_source_title_for_compare(str(selected.get("title") or ""))
        if not footnote_title or not selected_title:
            return False
        title_matches = footnote_title in selected_title or selected_title in footnote_title
        if not title_matches:
            return False

        return bool(
            candidate.artifacts.get("source_pdf")
            and (
                candidate.artifacts.get("mapped_footnote_pages")
                or candidate.artifacts.get("page_mapping")
                or candidate.artifacts.get("downloaded_page_range")
            )
        )

    def _has_viable_same_title_digital_alternate(
        self,
        candidate: CitationCandidate,
        remaining_matches: Sequence[NDLSearchMatch],
    ) -> bool:
        footnote_title = _normalize_source_title_for_compare(
            candidate.footnote.title or candidate.footnote.ndl_keyword
        )
        footnote_base = _source_title_base_without_volume(
            candidate.footnote.title or candidate.footnote.ndl_keyword
        )
        if not footnote_title and not footnote_base:
            return False

        footnote_has_upper = "上巻" in footnote_title or "上卷" in footnote_title
        footnote_has_lower = "下巻" in footnote_title or "下卷" in footnote_title
        for match in remaining_matches:
            ndl_id = getattr(match, "ndl_id", None) or getattr(match, "platform_item_id", None)
            if not is_likely_digital_ndl_pid(str(ndl_id or "")):
                continue
            match_title = _normalize_source_title_for_compare(str(getattr(match, "title", "") or ""))
            match_base = _source_title_base_without_volume(str(getattr(match, "title", "") or ""))
            if footnote_has_upper and ("下巻" in match_title or "下卷" in match_title):
                continue
            if footnote_has_lower and ("上巻" in match_title or "上卷" in match_title):
                continue
            if (
                footnote_title
                and match_title
                and (footnote_title in match_title or match_title in footnote_title)
            ):
                return True
            if (
                footnote_base
                and match_base
                and (footnote_base in match_base or match_base in footnote_base)
            ):
                return True
        return False

    def _match_conflicts_footnote_volume(
        self,
        footnote: ParsedFootnote,
        match: NDLSearchMatch,
    ) -> bool:
        footnote_title = _normalize_source_title_for_compare(footnote.title or footnote.ndl_keyword)
        match_title = _normalize_source_title_for_compare(str(getattr(match, "title", "") or ""))
        if not footnote_title or not match_title:
            return False
        footnote_has_upper = "上巻" in footnote_title or "上卷" in footnote_title
        footnote_has_lower = "下巻" in footnote_title or "下卷" in footnote_title
        if footnote_has_upper and ("下巻" in match_title or "下卷" in match_title):
            return True
        if footnote_has_lower and ("上巻" in match_title or "上卷" in match_title):
            return True
        return False

    def _record_source_attempt_snapshot(self, candidate: CitationCandidate) -> None:
        attempts = candidate.artifacts.setdefault("source_attempts", [])
        if not isinstance(attempts, list):
            candidate.artifacts["source_attempts"] = attempts = []
        snapshot = {
                "selected_source_match": candidate.artifacts.get("selected_source_match"),
                "source_pdf": candidate.artifacts.get("source_pdf"),
                "downloaded_page_range": candidate.artifacts.get("downloaded_page_range"),
                "page_mapping": candidate.artifacts.get("page_mapping"),
                "mapped_footnote_pages": candidate.artifacts.get("mapped_footnote_pages"),
                "matched_scan_page": candidate.artifacts.get("matched_scan_page"),
                "matched_book_pages": candidate.artifacts.get("matched_book_pages"),
                "page_label_mode": candidate.artifacts.get("page_label_mode"),
                "matched_page": candidate.matched_page,
                "matched_japanese": candidate.matched_japanese,
                "confidence": candidate.confidence,
                "verification_status": candidate.verification_status,
                "support_status": candidate.support_status,
                "support_reason": candidate.support_reason,
                "evidence_scope": candidate.evidence_scope,
                "alignment_scope": candidate.artifacts.get("alignment_scope"),
            }
        attempts.append(snapshot)
        append_source_trial(
            candidate.artifacts,
            build_source_trial(
                role="replaced",
                source=snapshot.get("selected_source_match") or {},
                page_range=snapshot.get("downloaded_page_range"),
                verification_status=snapshot.get("verification_status"),
                support_status=snapshot.get("support_status"),
                confidence=snapshot.get("confidence"),
                has_pdf=bool(snapshot.get("source_pdf")),
                has_alignment=bool(snapshot.get("matched_japanese")),
            ),
        )

    def _prepare_alternate_source_retry(self, candidate: CitationCandidate) -> bool:
        source_id = self._selected_source_identity(candidate)
        if not source_id:
            return False
        skip_ids = [
            str(item)
            for item in (candidate.artifacts.get("source_match_skip_ids") or [])
            if item
        ]
        if source_id not in skip_ids:
            skip_ids.append(source_id)
        candidate.artifacts["source_match_skip_ids"] = skip_ids
        candidate.artifacts["alternate_source_retry_count"] = int(
            candidate.artifacts.get("alternate_source_retry_count") or 0
        ) + 1
        self._record_source_attempt_snapshot(candidate)
        candidate.notes.append(f"alternate_source_retry_after_weak_alignment:{source_id}")
        for key in (
            "source_pdf",
            "selected_source_match",
            "page_mapping",
            "mapped_footnote_pages",
            "downloaded_page_range",
            "download_attempt",
        ):
            candidate.artifacts.pop(key, None)
        return True

    def _restore_prior_source_attempt_after_failed_retry(self, candidate: CitationCandidate) -> bool:
        failed_statuses = {
            "download_failed",
            "page_mapping_unavailable",
            "ocr_failed",
            "source_not_found",
            "source_mismatch",
        }
        if candidate.verification_status not in failed_statuses:
            return False
        attempts = candidate.artifacts.get("source_attempts")
        if not isinstance(attempts, list):
            return False
        prior_attempt = next(
            (
                attempt for attempt in reversed(attempts)
                if isinstance(attempt, dict)
                and attempt.get("source_pdf")
                and (attempt.get("matched_japanese") or attempt.get("matched_page") is not None)
            ),
            None,
        )
        if not prior_attempt:
            return False

        for key in (
            "selected_source_match",
            "source_pdf",
            "downloaded_page_range",
            "page_mapping",
            "mapped_footnote_pages",
            "matched_scan_page",
            "matched_book_pages",
            "page_label_mode",
            "alignment_scope",
        ):
            if key in prior_attempt:
                candidate.artifacts[key] = prior_attempt.get(key)

        candidate.matched_page = prior_attempt.get("matched_page")
        candidate.matched_japanese = str(prior_attempt.get("matched_japanese") or "")
        candidate.confidence = prior_attempt.get("confidence")
        candidate.verification_status = str(prior_attempt.get("verification_status") or "needs_manual_review")
        candidate.support_status = str(prior_attempt.get("support_status") or "needs_manual_review")
        candidate.support_reason = str(prior_attempt.get("support_reason") or "备用来源失败，已恢复上一份可用弱证据")
        candidate.evidence_scope = str(prior_attempt.get("evidence_scope") or prior_attempt.get("alignment_scope") or "")
        note = "alternate_source_retry_failed_restored_prior_attempt"
        if note not in candidate.notes:
            candidate.notes.append(note)
        return True

    def _set_support_assessment(self, candidate: CitationCandidate) -> None:
        """Classify whether the located passage actually supports the citation.

        Pipeline status says whether OCR/alignment produced a passage. This
        stricter support status says whether that passage can be trusted as the
        source for the paper's claim.
        """

        candidate.evidence_scope = str(candidate.artifacts.get("alignment_scope") or "")
        note_blob = "\n".join(str(note) for note in candidate.notes or []).lower()
        confidence = float(candidate.confidence or 0.0)
        page_distance = candidate.artifacts.get("page_distance_from_citation")
        try:
            normalized_page_distance = int(page_distance) if page_distance is not None else None
        except (TypeError, ValueError):
            normalized_page_distance = None

        llm_review = candidate.artifacts.get("llm_review")
        if isinstance(llm_review, dict):
            decision = str(llm_review.get("decision") or "uncertain")
            reason = str(llm_review.get("reason") or "")
            exact_sentence = _clean_text(str(llm_review.get("exact_sentence") or ""))
            if decision == "direct_support" and exact_sentence:
                candidate.matched_japanese = exact_sentence
                review_confidence = llm_review.get("confidence")
                if review_confidence is not None:
                    try:
                        candidate.confidence = float(review_confidence)
                    except (TypeError, ValueError):
                        pass
                if normalized_page_distance is not None and normalized_page_distance > 1:
                    candidate.support_status = "page_mismatch_but_support"
                    candidate.support_reason = reason or "LLM 判定原文直接对应，但页码与脚注不一致"
                else:
                    candidate.support_status = "direct_support"
                    candidate.support_reason = reason or "LLM 判定原文句子与论文句子直接对应"
                candidate.verification_status = "matched"
                return
            if decision == "not_supported":
                candidate.support_status = "not_supported"
                candidate.support_reason = reason or "LLM 判定候选 OCR 文本不构成有效对应"
                candidate.verification_status = "needs_manual_review"
                return
            if decision == "partial_support":
                candidate.support_status = "partial_support"
                candidate.support_reason = reason or "LLM 判定只能证明相关，不能作为直接出处"
                candidate.verification_status = "needs_manual_review"
                return
            if decision == "uncertain" and reason:
                candidate.support_status = "needs_manual_review"
                candidate.support_reason = reason
                candidate.verification_status = "needs_manual_review"
                return

        if not candidate.matched_japanese:
            candidate.support_status = "not_supported" if "llm_rejected" in note_blob else "needs_manual_review"
            candidate.support_reason = "未能在抽取文本中定位可用日文段落"
            candidate.verification_status = "needs_manual_review"
            return

        if confidence < self.MIN_PASSAGE_ALIGNMENT_CONFIDENCE:
            candidate.support_status = "needs_manual_review"
            candidate.support_reason = f"页内候选相似度偏低，仅 {confidence:.4f}"
            candidate.verification_status = "needs_manual_review"
            return

        if normalized_page_distance is not None and normalized_page_distance > 1:
            if confidence >= self.MIN_DIRECT_SUPPORT_CONFIDENCE and "llm_alignment_failed" not in note_blob:
                candidate.support_status = "page_mismatch_but_support"
                candidate.support_reason = "原文段落可对应中文引文，但最佳页与脚注页码不一致"
                candidate.verification_status = "matched"
            else:
                candidate.support_status = "partial_support"
                candidate.support_reason = "找到相近段落，但最佳页偏离脚注页码，需要核对作者页码"
                candidate.verification_status = "needs_manual_review"
            return

        weak_alignment_markers = (
            "heuristic_alignment_used",
            "llm_alignment_failed:",
            "context_alignment_preview_higher_confidence:",
            "context_alignment_selected_over_weak_cited_page:",
            "cited_pages_no_alignment_context_fallback",
            "cited_pages_not_extracted_context_fallback",
        )
        if candidate.evidence_scope != "cited_pages" or any(marker in note_blob for marker in weak_alignment_markers):
            candidate.support_status = "partial_support"
            candidate.support_reason = "材料位于脚注页或上下文附近，但当前只能证明相关，不能自动判为直接出处"
            candidate.verification_status = "needs_manual_review"
            return

        if confidence >= self.MIN_DIRECT_SUPPORT_CONFIDENCE:
            candidate.support_status = "direct_support"
            candidate.support_reason = "脚注页内段落与中文引文形成高置信直接对应"
            candidate.verification_status = "matched"
            return

        candidate.support_status = "partial_support"
        candidate.support_reason = f"页码贴合，但对齐置信度 {confidence:.4f} 未达到直接出处阈值"
        candidate.verification_status = "needs_manual_review"

    def _citation_priority_page_numbers(self, candidate: CitationCandidate) -> List[int]:
        if candidate.artifacts.get("page_label_mode") == "book":
            raw_pages = candidate.footnote.page_numbers
        else:
            raw_pages = candidate.artifacts.get("mapped_footnote_pages") or candidate.footnote.page_numbers

        page_numbers: List[int] = []
        for page in raw_pages or []:
            try:
                page_number = int(page)
            except (TypeError, ValueError):
                continue
            if page_number >= 1 and page_number not in page_numbers:
                page_numbers.append(page_number)
        return page_numbers

    def _page_distance_to_citation_pages(
        self,
        page_number: Optional[int],
        cited_page_numbers: Sequence[int],
    ) -> Optional[int]:
        if page_number is None or not cited_page_numbers:
            return None
        try:
            normalized_page = int(page_number)
        except (TypeError, ValueError):
            return None
        distances: List[int] = []
        for cited_page in cited_page_numbers:
            try:
                distances.append(abs(normalized_page - int(cited_page)))
            except (TypeError, ValueError):
                continue
        return min(distances) if distances else None

    def _citation_page_span(self, candidate: CitationCandidate) -> Dict[str, Any]:
        existing = candidate.artifacts.get("page_span")
        if isinstance(existing, dict) and existing.get("mode"):
            return existing
        citation_unit = candidate.artifacts.get("citation_unit") or {}
        span = classify_page_span(
            candidate.footnote.page_numbers,
            page_label=candidate.footnote.page_label,
            citation_text=str(
                citation_unit.get("text")
                or candidate.translation_text
                or candidate.paragraph_text
            ),
            unit_type=str(citation_unit.get("unit_type") or ""),
        )
        candidate.artifacts["page_span"] = span
        return span

    def _continuous_cited_page_windows(
        self,
        cited_pages: Sequence[Tuple[int, str]],
        cited_page_numbers: Sequence[int],
    ) -> List[Tuple[int, str]]:
        if len(cited_pages) < 2:
            return list(cited_pages)
        by_page = {int(page): text for page, text in cited_pages}
        ordered_pages = [page for page in sorted(cited_page_numbers) if page in by_page]
        if len(ordered_pages) < 2:
            return list(cited_pages)
        combined = "\n\n".join(by_page[page] for page in ordered_pages if by_page.get(page))
        if not combined.strip():
            return list(cited_pages)
        return list(cited_pages) + [(ordered_pages[0], combined)]

    def _align_distributed_page_claims(
        self,
        candidate: CitationCandidate,
        cited_pages: Sequence[Tuple[int, str]],
    ) -> Tuple[Optional[int], str, Optional[float], str]:
        citation_unit = candidate.artifacts.get("citation_unit") or {}
        claims = [
            str(item)
            for item in (
                citation_unit.get("claim_candidates")
                or split_citation_claims_for_pages(candidate.translation_text)
            )
            if str(item or "").strip()
        ]
        if not claims:
            claims = [candidate.translation_text]

        alignments: List[Dict[str, Any]] = []
        matched_texts: List[str] = []
        confidence_values: List[float] = []
        for index, claim in enumerate(claims[:8], start=1):
            page, text, confidence, note = align_translation(
                claim,
                cited_pages,
                llm_client=None,
            )
            confidence_value = float(confidence or 0.0)
            alignment = {
                "claim_index": index,
                "claim_text": claim,
                "matched_page": page,
                "confidence": round(confidence_value, 4),
                "note": note,
                "matched_text": trim_aligned_segment(claim, text) if text else "",
            }
            alignments.append(alignment)
            if text:
                matched_texts.append(f"[p{page}] {alignment['matched_text']}")
                confidence_values.append(confidence_value)

        candidate.artifacts["distributed_claim_alignments"] = alignments
        if not confidence_values:
            return None, "", None, "distributed_page_claim_alignment_used; no_claim_alignment"

        best_alignment = max(
            alignments,
            key=lambda item: float(item.get("confidence") or 0.0),
        )
        average_confidence = sum(confidence_values) / max(1, len(confidence_values))
        candidate.artifacts["distributed_claim_alignment_summary"] = {
            "aligned_claims": len(confidence_values),
            "total_claims": len(claims[:8]),
            "average_confidence": round(average_confidence, 4),
            "best_page": best_alignment.get("matched_page"),
            "best_confidence": best_alignment.get("confidence"),
        }
        return (
            best_alignment.get("matched_page"),
            "\n\n".join(matched_texts),
            round(max(confidence_values), 4),
            "distributed_page_claim_alignment_used",
        )

    def _split_extracted_pages_by_citation(
        self,
        candidate: CitationCandidate,
        extracted_pages: Sequence[Tuple[int, str]],
    ) -> Tuple[List[Tuple[int, str]], List[Tuple[int, str]], List[int]]:
        cited_page_numbers = self._citation_priority_page_numbers(candidate)
        cited_set = set(cited_page_numbers)
        if not cited_set:
            return [], list(extracted_pages), []

        cited_pages: List[Tuple[int, str]] = []
        context_pages: List[Tuple[int, str]] = []
        for page_number, page_text in extracted_pages:
            try:
                normalized_page = int(page_number)
            except (TypeError, ValueError):
                context_pages.append((page_number, page_text))
                continue
            if normalized_page in cited_set:
                cited_pages.append((page_number, page_text))
            else:
                context_pages.append((page_number, page_text))
        return cited_pages, context_pages, cited_page_numbers

    def _align_translation_with_citation_priority(
        self,
        candidate: CitationCandidate,
        extracted_pages: Sequence[Tuple[int, str]],
    ) -> Tuple[Optional[int], str, Optional[float], str]:
        cited_pages, context_pages, cited_page_numbers = self._split_extracted_pages_by_citation(
            candidate,
            extracted_pages,
        )
        candidate.artifacts["citation_priority_pages"] = cited_page_numbers
        candidate.artifacts["cited_extracted_pages"] = [page for page, _text in cited_pages]

        if not cited_page_numbers:
            candidate.artifacts["alignment_scope"] = "all_extracted_pages"
            return self._align_translation(candidate.translation_text, extracted_pages)

        if cited_pages:
            page_span = self._citation_page_span(candidate)
            page_span_mode = str(page_span.get("mode") or "")
            candidate.artifacts["page_span_mode"] = page_span_mode
            if page_span_mode == "distributed_pages" and len(cited_pages) >= 2:
                best_page, best_japanese, confidence, note = self._align_distributed_page_claims(
                    candidate,
                    cited_pages,
                )
                candidate.artifacts["alignment_scope"] = "distributed_cited_pages"
                if best_japanese:
                    return best_page, best_japanese, confidence, note

            alignment_pages = cited_pages
            if page_span_mode == "continuous_range" and len(cited_pages) >= 2:
                alignment_pages = self._continuous_cited_page_windows(cited_pages, cited_page_numbers)
                candidate.artifacts["continuous_page_window_pages"] = cited_page_numbers

            best_page, best_japanese, confidence, note = self._align_translation(
                candidate.translation_text,
                alignment_pages,
            )
            candidate.artifacts["alignment_scope"] = "cited_pages"
            notes = ["cited_page_alignment_used"]
            if page_span_mode == "continuous_range":
                notes.append("continuous_page_window_alignment_used")
            if note:
                notes.append(note)

            if context_pages:
                context_page, context_segment, context_confidence, context_note = align_translation(
                    candidate.translation_text,
                    context_pages,
                    llm_client=None,
                )
                if context_page is not None:
                    context_page_distance = self._page_distance_to_citation_pages(
                        context_page,
                        cited_page_numbers,
                    )
                    candidate.artifacts["context_alignment_preview"] = {
                        "page": context_page,
                        "confidence": context_confidence,
                        "note": context_note,
                        "page_distance_from_citation": context_page_distance,
                        "text": trim_aligned_segment(candidate.translation_text, context_segment),
                    }
                    cited_confidence = confidence or 0.0
                    context_confidence_value = context_confidence or 0.0
                    context_is_much_better = (
                        context_confidence_value
                        > cited_confidence + self.CONTEXT_ALIGNMENT_BETTER_MARGIN
                    )
                    context_is_near_cited_page = (
                        context_page_distance is not None
                        and context_page_distance <= self.MAX_CONTEXT_PROMOTION_PAGE_DISTANCE
                    )
                    cited_alignment_is_weak = (
                        not best_japanese
                        or cited_confidence < self.MAX_WEAK_CITED_ALIGNMENT_CONFIDENCE
                    )
                    context_is_actionable = (
                        context_confidence_value >= self.MIN_CONTEXT_PROMOTION_CONFIDENCE
                    )
                    if context_is_much_better:
                        notes.append(f"context_alignment_preview_higher_confidence:p{context_page}")
                    if (
                        context_is_much_better
                        and context_is_actionable
                        and context_is_near_cited_page
                        and cited_alignment_is_weak
                    ):
                        candidate.artifacts["alignment_scope"] = "context_promoted_from_cited_pages"
                        candidate.artifacts["context_alignment_selected"] = {
                            "page": context_page,
                            "confidence": context_confidence,
                            "note": context_note,
                            "page_distance_from_citation": context_page_distance,
                        }
                        notes.append(f"context_alignment_selected_over_weak_cited_page:p{context_page}")
                        return context_page, context_segment, context_confidence, "; ".join(notes)

            if best_japanese:
                return best_page, best_japanese, confidence, "; ".join(notes)

            fallback_page, fallback_japanese, fallback_confidence, fallback_note = self._align_translation(
                candidate.translation_text,
                extracted_pages,
            )
            candidate.artifacts["alignment_scope"] = "context_fallback"
            notes.append("cited_pages_no_alignment_context_fallback")
            if fallback_note:
                notes.append(fallback_note)
            return fallback_page, fallback_japanese, fallback_confidence, "; ".join(notes)

        candidate.artifacts["alignment_scope"] = "context_fallback"
        best_page, best_japanese, confidence, note = self._align_translation(candidate.translation_text, extracted_pages)
        fallback_note = "cited_pages_not_extracted_context_fallback"
        if note:
            fallback_note = f"{fallback_note}; {note}"
        return best_page, best_japanese, confidence, fallback_note

    def _extract_paragraph_content(self, node: ET.Element) -> Tuple[str, List[str]]:
        return extract_paragraph_content(node)

    def _collect_text(self, node: ET.Element) -> str:
        return collect_text(node)

    def _pick_translation_text(
        self,
        paragraph: ParsedParagraph,
        *,
        include_unquoted: bool,
        footnote_id: Optional[str] = None,
    ) -> str:
        return pick_translation_text(paragraph, include_unquoted=include_unquoted, footnote_id=footnote_id)

    def _is_verifiable_footnote(self, footnote: ParsedFootnote) -> bool:
        return is_verifiable_footnote(footnote, stopword_prefixes=self.STOPWORD_PREFIXES)

    def _extract_title(self, text: str) -> str:
        return extract_title(text, title_patterns=self.TITLE_PATTERNS)

    def _extract_author(self, text: str, *, title: str) -> str:
        return extract_author(text, title=title)

    def _extract_publisher(self, text: str, *, title: str) -> Tuple[str, str]:
        return extract_publisher(text, title=title)

    def _extract_pages(self, text: str) -> Tuple[str, List[int]]:
        return extract_pages(text, page_patterns=self.PAGE_PATTERNS)

    def _detect_source_type(self, text: str) -> str:
        return detect_source_type(text)

    def _score_ndl_record(
        self,
        footnote: ParsedFootnote,
        *,
        title: str,
        author: Optional[str],
        year: Optional[str],
        publisher: Optional[str],
    ) -> float:
        return score_ndl_record(
            footnote,
            title=title,
            author=author,
            year=year,
            publisher=publisher,
        )

    def _search_ndl_public_api(self, footnote: ParsedFootnote, *, max_results: int) -> List[Dict[str, Any]]:
        return search_ndl_public_api(footnote, max_results=max_results)

    def _iter_ndl_search_keywords(self, footnote: ParsedFootnote) -> List[str]:
        return iter_ndl_search_keywords(footnote)

    def _build_ndl_sru_queries(self, footnote: ParsedFootnote) -> List[str]:
        return build_ndl_sru_queries(footnote)

    def _title_query_terms(self, title: str) -> List[str]:
        return title_query_terms(title)

    def _author_query_terms(self, author: str) -> List[str]:
        return author_query_terms(author)

    def _parse_ndl_sru_records(self, xml_text: str) -> List[Dict[str, Any]]:
        return parse_ndl_sru_records(xml_text)

    def _should_skip_page_mapping_after_failure(self, reason: Optional[str]) -> bool:
        if not reason:
            return False
        normalized = str(reason).lower()
        return any(marker.lower() in normalized for marker in self.HARD_PAGE_MAPPING_FAILURE_MARKERS)

    def _get_pdf_page_count(self, pdf_path: str) -> Optional[int]:
        try:
            import fitz

            document = fitz.open(pdf_path)
            try:
                return len(document)
            finally:
                document.close()
        except Exception:
            return None

    def _is_pdf_header_file(self, path: Path) -> bool:
        try:
            if not path.exists() or path.stat().st_size <= 0:
                return False
            with path.open("rb") as handle:
                return handle.read(4).startswith(b"%PDF")
        except OSError:
            return False

    def _sample_pdf_page_span(self, path: Path) -> Optional[Tuple[int, int]]:
        match = re.search(r"_p(\d+)(?:-p(\d+))?\.pdf$", path.name)
        if not match:
            return None
        start_page = int(match.group(1))
        end_page = int(match.group(2) or start_page)
        if end_page < start_page:
            return None
        return start_page, end_page

    def _collect_cached_page_mapping_sample_texts(
        self,
        sample_dir: Path,
        *,
        max_scan_page: int,
    ) -> Dict[int, str]:
        page_texts: Dict[int, str] = {}
        for txt_path in sorted(sample_dir.glob("ocr_page_*_*/*.txt")):
            match = re.match(r"page_(\d{4})\.txt$", txt_path.name)
            if not match:
                continue
            scan_page = int(match.group(1))
            if scan_page > max_scan_page or scan_page in page_texts:
                continue
            try:
                text = txt_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if str(text or "").strip():
                page_texts[scan_page] = text
        return page_texts

    def _select_inferred_page_mapping(self, page_texts: Dict[int, str]) -> Optional[Dict[str, Any]]:
        visible_mapping = infer_page_mapping_from_visible_page_numbers(page_texts)
        toc_mapping = infer_page_mapping_from_front_matter_texts(page_texts)
        if visible_mapping and int(visible_mapping.get("pages_per_scan") or 2) > 2:
            return visible_mapping
        return toc_mapping or visible_mapping

    def _refine_cached_page_mapping_from_samples(
        self,
        cached: Dict[str, Any],
        *,
        ndl_id: str,
        output_dir: Path,
    ) -> Dict[str, Any]:
        sample_dir = output_dir / f"page_map_{ndl_id}"
        if not sample_dir.exists():
            return cached
        sample_end_page = int(self.PAGE_MAPPING_SAMPLE_END_PAGE)
        page_texts = self._collect_cached_page_mapping_sample_texts(
            sample_dir,
            max_scan_page=sample_end_page,
        )
        inferred = self._select_inferred_page_mapping(page_texts)
        if not inferred:
            return cached
        cached_pages_per_scan = int(cached.get("pages_per_scan") or 2)
        inferred_pages_per_scan = int(inferred.get("pages_per_scan") or 2)
        if inferred_pages_per_scan != cached_pages_per_scan and inferred_pages_per_scan > 2:
            self._save_page_mapping_cache(output_dir, str(ndl_id), inferred)
            return inferred
        return cached

    def _collect_page_mapping_sample_texts(
        self,
        sample_dir: Path,
        *,
        max_scan_page: int,
    ) -> Dict[int, str]:
        page_texts: Dict[int, str] = self._collect_cached_page_mapping_sample_texts(
            sample_dir,
            max_scan_page=max_scan_page,
        )
        for pdf_path in sorted(sample_dir.glob("*.pdf")):
            if not self._is_pdf_header_file(pdf_path):
                continue
            span = self._sample_pdf_page_span(pdf_path)
            if span is None:
                continue
            start_scan_page, end_scan_page = span
            page_count = self._get_pdf_page_count(str(pdf_path)) or 0
            if page_count < 1:
                continue
            for local_page in range(1, page_count + 1):
                scan_page = start_scan_page + local_page - 1
                if scan_page > end_scan_page or scan_page > max_scan_page:
                    break
                if scan_page in page_texts:
                    continue
                try:
                    text = self._extract_pdf_page_text(
                        str(pdf_path),
                        page_number=local_page,
                        output_dir=sample_dir,
                        ocr_model="ndlocr_lite",
                    )
                except Exception:
                    continue
                if str(text or "").strip():
                    page_texts[scan_page] = text
        return page_texts

    def _download_page_mapping_sample_pages(
        self,
        *,
        ndl_id: str,
        title: str,
        sample_dir: Path,
        pages: Sequence[int],
    ) -> List[int]:
        self._last_page_mapping_sample_failure = None
        missing_pages = [
            int(page)
            for page in pages
            if page >= 1 and not any(sample_dir.glob(f"*_p{int(page)}.pdf"))
        ]
        if not missing_pages:
            return []

        legacy_browser = load_legacy_module("ndl-search/browser_client.py")
        client = legacy_browser.NDLBrowserClient(headless=True, output_dir=str(sample_dir))
        downloaded_pages: List[int] = []
        try:
            client.login()
            book = legacy_browser.NDLBook(
                title=title or ndl_id,
                ndl_id=str(ndl_id),
                pid=str(ndl_id),
                total_pages=0,
                url=f"https://dl.ndl.go.jp/pid/{ndl_id}",
            )
            chunks: List[Tuple[int, int]] = []
            chunk_start = missing_pages[0]
            previous_page = missing_pages[0]
            for page in missing_pages[1:]:
                if page == previous_page + 1 and page - chunk_start < 20:
                    previous_page = page
                    continue
                chunks.append((chunk_start, previous_page))
                chunk_start = page
                previous_page = page
            chunks.append((chunk_start, previous_page))

            failure_reasons: List[str] = []
            for start_page, end_page in chunks:
                filename = f"_sample_{ndl_id}_p{start_page}-p{end_page}.pdf"
                try:
                    result = client._download_single_range(
                        book,
                        start_page=start_page,
                        end_page=end_page,
                        filename=filename,
                        dir_path=sample_dir,
                    )
                except Exception:
                    continue
                output_path = Path(getattr(result, "output_path", "") or "")
                if getattr(result, "success", False) and self._is_pdf_header_file(output_path):
                    downloaded_pages.extend(range(start_page, end_page + 1))
                    continue
                error_message = str(getattr(result, "error_message", "") or "")
                failure_reason = self._normalize_download_unavailability_reason(error_message)
                if failure_reason:
                    failure_reasons.append(failure_reason)
                if failure_reason in self.HARD_PAGE_MAPPING_FAILURE_MARKERS:
                    self._last_page_mapping_sample_failure = failure_reason
                    break
            if not downloaded_pages and not self._last_page_mapping_sample_failure and failure_reasons:
                self._last_page_mapping_sample_failure = failure_reasons[-1]
        finally:
            client.close()
        return downloaded_pages

    def _estimate_scan_page_range(
        self,
        candidate: CitationCandidate,
        *,
        output_dir: Path,
        restricted_download: bool,
        page_window: int,
        top_match: Optional[NDLSearchMatch] = None,
    ) -> Optional[Dict[str, Any]]:
        if not restricted_download or not candidate.footnote.page_numbers:
            return None
        self._resolve_ndlsearch_matches(candidate)
        top_match = top_match or self._select_preferred_match_for_pages(candidate.ndl_matches, candidate.footnote.page_numbers)
        ndl_id = getattr(top_match, "ndl_id", None)
        if not ndl_id:
            return None
        self._load_page_mapping_failure_cache(output_dir)
        cached_failure = self._page_mapping_failure_cache.get(str(ndl_id))
        if cached_failure and self._should_skip_page_mapping_after_failure(cached_failure):
            candidate.notes.append(f"page_mapping_skipped_after_failure:{cached_failure}")
            if self._normalize_download_unavailability_reason(cached_failure):
                self._mark_source_unavailable(
                    candidate,
                    reason=self._normalize_download_unavailability_reason(cached_failure),
                    ndl_id=str(ndl_id),
                    detail=str(cached_failure),
                )
            return None
        if cached_failure:
            candidate.notes.append(f"page_mapping_retry_after_soft_failure:{cached_failure}")
        self._load_page_mapping_cache(output_dir)
        cached = self._page_mapping_cache.get(str(ndl_id))
        if cached is not None:
            cached = self._refine_cached_page_mapping_from_samples(
                cached,
                ndl_id=str(ndl_id),
                output_dir=output_dir,
            )
        if cached is None:
            cached = self._infer_front_matter_page_mapping(
                ndl_id=ndl_id,
                title=getattr(top_match, "title", None) or candidate.footnote.title,
                keyword=candidate.footnote.ndl_keyword or candidate.footnote.title,
                output_dir=output_dir,
            )
            if cached:
                self._save_page_mapping_cache(output_dir, str(ndl_id), cached)
        if not cached:
            return None

        mapping = build_scan_page_range(
            cached,
            candidate.footnote.page_numbers,
            page_window=page_window,
        )
        if mapping:
            mapping["ndl_id"] = str(ndl_id)
        return mapping

    def _infer_front_matter_page_mapping(
        self,
        *,
        ndl_id: str,
        title: str,
        keyword: str,
        output_dir: Path,
    ) -> Optional[Dict[str, Any]]:
        sample_dir = output_dir / f"page_map_{ndl_id}"
        sample_dir.mkdir(parents=True, exist_ok=True)
        cached_failure = self._page_mapping_failure_cache.get(str(ndl_id))
        if cached_failure and self._should_skip_page_mapping_after_failure(cached_failure):
            return None
        sample_end_page = int(self.PAGE_MAPPING_SAMPLE_END_PAGE)
        cached_page_texts = self._collect_cached_page_mapping_sample_texts(
            sample_dir,
            max_scan_page=sample_end_page,
        )
        mapping = self._select_inferred_page_mapping(cached_page_texts)
        if mapping:
            return mapping

        page_texts = self._collect_page_mapping_sample_texts(
            sample_dir,
            max_scan_page=sample_end_page,
        )
        mapping = self._select_inferred_page_mapping(page_texts)
        if mapping:
            return mapping

        first_sample_pages = list(range(1, min(20, sample_end_page) + 1))
        self._download_page_mapping_sample_pages(
            ndl_id=str(ndl_id),
            title=title,
            sample_dir=sample_dir,
            pages=first_sample_pages,
        )
        if self._last_page_mapping_sample_failure:
            self._save_page_mapping_failure_cache(output_dir, str(ndl_id), self._last_page_mapping_sample_failure)
            return None
        page_texts = self._collect_page_mapping_sample_texts(
            sample_dir,
            max_scan_page=sample_end_page,
        )
        mapping = self._select_inferred_page_mapping(page_texts)
        if mapping:
            return mapping

        if sample_end_page > 20:
            self._download_page_mapping_sample_pages(
                ndl_id=str(ndl_id),
                title=title,
                sample_dir=sample_dir,
                pages=range(21, sample_end_page + 1),
            )
            if self._last_page_mapping_sample_failure:
                self._save_page_mapping_failure_cache(output_dir, str(ndl_id), self._last_page_mapping_sample_failure)
                return None
            page_texts = self._collect_page_mapping_sample_texts(
                sample_dir,
                max_scan_page=sample_end_page,
            )
            mapping = self._select_inferred_page_mapping(page_texts)
            if mapping:
                return mapping

        self._save_page_mapping_failure_cache(output_dir, str(ndl_id), "front_matter_mapping_not_inferred")
        return None

    def _enrich_with_source_excerpt(
        self,
        candidate: CitationCandidate,
        *,
        output_dir: Path,
        restricted_download: bool,
        page_window: int,
        ocr_model: str,
        download_max_attempts: int = 3,
    ) -> None:
        self._clear_transient_verification_state(candidate)
        ocr_backend_available = self._is_ocr_backend_available(ocr_model)
        candidate.artifacts["ocr_backend_available"] = ocr_backend_available
        try:
            pdf_path = self._obtain_source_pdf(
                candidate,
                output_dir=output_dir,
                restricted_download=restricted_download,
                page_window=page_window,
                download_max_attempts=download_max_attempts,
            )
        except BaseException as exc:  # noqa: BLE001
            candidate.verification_status = "download_failed"
            candidate.notes.append(str(exc))
            return

        if not pdf_path:
            if candidate.artifacts.get("page_mapping_required_but_unavailable"):
                candidate.verification_status = "page_mapping_unavailable"
                candidate.notes.append("source_pdf_not_downloaded_without_verified_page_mapping")
            else:
                candidate.verification_status = "download_failed"
                candidate.notes.append("source_pdf_not_available")
            return
        self._clear_successful_source_acquisition_noise(candidate)
        candidate.artifacts["source_pdf"] = pdf_path
        readiness = self._wait_for_pdf_ready(
            pdf_path,
            local_page_range=candidate.artifacts.get("downloaded_page_range"),
            output_dir=output_dir,
        )
        candidate.artifacts["pdf_readiness"] = readiness
        if not ocr_backend_available:
            candidate.verification_status = "ocr_failed"
            candidate.notes.append(f"ocr_backend_unavailable:{ocr_model}")
            return

        page_numbers = candidate.artifacts.get("mapped_footnote_pages") or candidate.footnote.page_numbers or [1]
        local_page_range = candidate.artifacts.get("downloaded_page_range")
        target_pages: List[int] = []
        for base_page in page_numbers:
            for page in self._expand_page_window(base_page, page_window):
                if page >= 1 and page not in target_pages:
                    target_pages.append(page)

        extracted_pages, page_label_mode = self._extract_pages_directly(
            pdf_path,
            pages=target_pages,
            local_page_range=local_page_range,
            output_dir=output_dir,
            ocr_model=ocr_model,
            page_mapping=candidate.artifacts.get("page_mapping"),
        )
        candidate.artifacts["page_label_mode"] = page_label_mode
        candidate.artifacts["direct_extracted_pages"] = [page for page, _text in extracted_pages]

        if not extracted_pages:
            for delay in (0, 4, 8):
                if delay:
                    time.sleep(delay)
                extracted_pages = self._extract_pages_via_subprocess(
                    pdf_path,
                    pages=target_pages,
                    local_page_range=local_page_range,
                    output_dir=output_dir,
                    ocr_model=ocr_model,
                )
                if extracted_pages:
                    break
            candidate.artifacts["page_label_mode"] = "scan"
        candidate.artifacts["subprocess_extracted_pages"] = [page for page, _text in extracted_pages]

        if not extracted_pages:
            candidate.verification_status = "ocr_failed"
            candidate.notes.append(
                "page_text_not_extracted"
                f" | readiness={candidate.artifacts.get('pdf_readiness', {}).get('status', 'unknown')}"
            )
            return

        candidate.artifacts["extracted_page_texts"] = self._serialize_extracted_pages(extracted_pages)

        best_page, best_japanese, confidence, note = self._align_translation_with_citation_priority(
            candidate,
            extracted_pages,
        )
        candidate.matched_page = best_page
        candidate.matched_japanese = best_japanese
        candidate.confidence = confidence
        page_mapping = candidate.artifacts.get("page_mapping")
        if best_page is not None and page_mapping:
            if candidate.artifacts.get("page_label_mode") == "book":
                candidate.artifacts["matched_book_pages"] = [best_page]
                matched_scan_page = self._estimate_scan_page_for_book_page(page_mapping, best_page)
                if matched_scan_page is not None:
                    candidate.artifacts["matched_scan_page"] = matched_scan_page
            else:
                candidate.artifacts["matched_scan_page"] = best_page
                matched_book_pages = self._estimate_book_pages_from_scan_page(page_mapping, best_page)
                if matched_book_pages:
                    candidate.artifacts["matched_book_pages"] = matched_book_pages
        page_distance = self._measure_page_distance_from_citation(candidate)
        if page_distance is not None:
            candidate.artifacts["page_distance_from_citation"] = page_distance
            if page_distance > 1:
                candidate.notes.append(f"page_distance_from_citation:{page_distance}")
        if note:
            candidate.notes.append(note)
        candidate.verification_status = "matched" if best_japanese else "needs_manual_review"
        if (
            best_japanese
            and candidate.artifacts.get("alignment_scope") == "cited_pages"
            and confidence is not None
            and confidence < self.MIN_CITED_PAGE_ALIGNMENT_CONFIDENCE
        ):
            candidate.notes.append(f"low_alignment_confidence_on_cited_pages:{confidence:.4f}")
            candidate.verification_status = "needs_manual_review"
        if best_japanese and page_distance is not None and page_distance > 1:
            candidate.verification_status = "needs_manual_review"
        self._review_precise_alignment(candidate)
        self._set_support_assessment(candidate)
        candidate.artifacts["review_context_window"] = page_window
        candidate.artifacts["review_context"] = self._build_review_context(
            candidate,
            extracted_pages=extracted_pages,
            context_radius=max(2, page_window),
        )
        if self._should_try_alternate_source(candidate) and self._prepare_alternate_source_retry(candidate):
            self._enrich_with_source_excerpt(
                candidate,
                output_dir=output_dir,
                restricted_download=restricted_download,
                page_window=page_window,
                ocr_model=ocr_model,
                download_max_attempts=download_max_attempts,
            )
            self._restore_prior_source_attempt_after_failed_retry(candidate)

    def _obtain_source_pdf(
        self,
        candidate: CitationCandidate,
        *,
        output_dir: Path,
        restricted_download: bool,
        page_window: int,
        download_max_attempts: int = 3,
    ) -> Optional[str]:
        self._resolve_ndlsearch_matches(candidate)
        first_match = candidate.ndl_matches[0] if candidate.ndl_matches else None
        first_platform = self._get_platform_for_match(first_match)
        if first_platform is not None:
            same_platform_matches = [
                match for match in candidate.ndl_matches if (match.platform or "ndl") == first_platform.name
            ]
            if first_platform.name == "ndl":
                matches_to_try = self._ordered_matches_for_pages(
                    same_platform_matches,
                    candidate.footnote.page_numbers,
                )
            else:
                preferred = first_platform.select_preferred_match(same_platform_matches)
                matches_to_try = ([preferred] if preferred else []) + [
                    match for match in same_platform_matches if match is not preferred
                ]
        else:
            matches_to_try = self._ordered_matches_for_pages(candidate.ndl_matches, candidate.footnote.page_numbers)
        if not matches_to_try and first_match:
            matches_to_try = [first_match]
        volume_filtered_matches = [
            match for match in matches_to_try
            if not self._match_conflicts_footnote_volume(candidate.footnote, match)
        ]
        if volume_filtered_matches:
            if len(volume_filtered_matches) != len(matches_to_try):
                candidate.notes.append("source_match_wrong_volume_filtered")
            matches_to_try = volume_filtered_matches
        metadata_filtered_matches = [
            match
            for match in matches_to_try
            if not getattr(match, "metadata", {}).get("source_mismatch")
        ]
        if metadata_filtered_matches:
            if len(metadata_filtered_matches) != len(matches_to_try):
                candidate.notes.append("source_match_metadata_mismatch_filtered")
            matches_to_try = metadata_filtered_matches
        elif matches_to_try:
            candidate.notes.append("source_match_all_metadata_mismatched")
            candidate.artifacts["source_match_order"] = []
            return None
        candidate.artifacts["source_match_order"] = [
            getattr(match, "ndl_id", None) or getattr(match, "platform_item_id", None) or getattr(match, "url", "")
            for match in matches_to_try
        ]
        skip_ids = {
            str(item)
            for item in (candidate.artifacts.get("source_match_skip_ids") or [])
            if item
        }
        if skip_ids:
            matches_to_try = [
                match
                for match in matches_to_try
                if self._match_identity(match) not in skip_ids
            ]
            candidate.artifacts["source_match_skipped_ids"] = sorted(skip_ids)
            if not matches_to_try:
                candidate.notes.append("source_match_retry_exhausted")
                return None

        existing_pdf = candidate.artifacts.get("source_pdf")
        if existing_pdf and self._is_usable_pdf(existing_pdf):
            existing_source_id = str(
                (candidate.artifacts.get("selected_source_match") or {}).get("ndl_id")
                or (candidate.artifacts.get("selected_source_match") or {}).get("platform_item_id")
                or ""
            )
            preferred_source_id = ""
            if matches_to_try:
                preferred_match = matches_to_try[0]
                preferred_source_id = str(
                    getattr(preferred_match, "ndl_id", None)
                    or getattr(preferred_match, "platform_item_id", None)
                    or ""
                )
            prior_support = str(getattr(candidate, "support_status", "") or "")
            if (
                existing_source_id
                and preferred_source_id
                and existing_source_id != preferred_source_id
                and prior_support not in {"direct_support", "page_mismatch_but_support"}
            ):
                candidate.notes.append(
                    f"source_pdf_reuse_skipped_preferred_match_changed:{existing_source_id}->{preferred_source_id}"
                )
                candidate.artifacts.pop("page_mapping", None)
                candidate.artifacts.pop("mapped_footnote_pages", None)
                candidate.artifacts.pop("downloaded_page_range", None)
            elif existing_source_id and existing_source_id in skip_ids:
                candidate.notes.append(f"source_pdf_reuse_skipped_source_retry:{existing_source_id}")
                candidate.artifacts.pop("page_mapping", None)
                candidate.artifacts.pop("mapped_footnote_pages", None)
                candidate.artifacts.pop("downloaded_page_range", None)
            else:
                downloaded_range = candidate.artifacts.get("downloaded_page_range")
                if isinstance(downloaded_range, list) and len(downloaded_range) == 2:
                    expected_range_token = f"p{downloaded_range[0]}-p{downloaded_range[1]}"
                    if expected_range_token not in Path(existing_pdf).stem:
                        candidate.notes.append("source_pdf_reuse_skipped_range_filename_mismatch")
                    else:
                        candidate.notes.append("source_pdf_reused")
                        return existing_pdf
                else:
                    candidate.notes.append("source_pdf_reused")
                    return existing_pdf

        public_pdf_path = None
        for top_match in matches_to_try:
            platform = self._get_platform_for_match(top_match)
            try:
                public_pdf_path = (
                    platform.download_public_pdf(top_match, output_dir=output_dir)
                    if platform is not None
                    else self._download_public_pdf(top_match, output_dir=output_dir)
                )
            except Exception as exc:  # noqa: BLE001
                candidate.notes.append(f"public_pdf_failed: {exc}")
                public_pdf_path = None
            if public_pdf_path:
                candidate.artifacts["selected_source_match"] = {
                    "ndl_id": getattr(top_match, "ndl_id", None),
                    "platform_item_id": getattr(top_match, "platform_item_id", None),
                    "url": getattr(top_match, "url", None),
                    "platform": getattr(top_match, "platform", None),
                    "title": getattr(top_match, "title", None),
                }
                return public_pdf_path
        if restricted_download:
            page_numbers = candidate.footnote.page_numbers or [1]
            module = self._get_ndl_download_module()
            seen_download_requests: set[Tuple[str, str, int, int]] = set()
            for top_match in matches_to_try:
                platform = self._get_platform_for_match(top_match)
                ndl_id = getattr(top_match, "ndl_id", None)
                if platform is not None and platform.name == "ndl" and not ndl_id:
                    candidate.artifacts["selected_source_match"] = self._source_match_to_artifact(top_match)
                    self._store_ndl_fulltext_hints(candidate, top_match)
                    resolution = getattr(top_match, "metadata", {}).get("ndlsearch_detail_resolution") or {}
                    if isinstance(resolution, dict) and resolution.get("status"):
                        candidate.notes.append(f"ndlsearch_detail_resolution:{resolution.get('status')}")
                    candidate.notes.append("restricted_download_skipped_no_ndl_pid")
                    self._mark_source_unavailable(
                        candidate,
                        reason="no_digital_pid",
                        source_id=self._match_identity(top_match),
                        detail=str(getattr(top_match, "url", "") or getattr(top_match, "title", "") or ""),
                    )
                    continue
                mapping = candidate.artifacts.get("page_mapping")
                if isinstance(mapping, dict) and mapping.get("ndl_id") and str(mapping.get("ndl_id")) != str(ndl_id):
                    mapping = None
                if not mapping and candidate.artifacts.get("ocr_backend_available", True):
                    try:
                        mapping = self._estimate_scan_page_range(
                            candidate,
                            output_dir=output_dir,
                            restricted_download=restricted_download,
                            page_window=page_window,
                            top_match=top_match,
                        )
                    except Exception as exc:  # noqa: BLE001
                        candidate.notes.append(f"page_mapping_failed: {exc}")
                        mapping = None
                if platform is not None and platform.name == "ndl" and page_numbers and not mapping:
                    candidate.artifacts["page_mapping_required_but_unavailable"] = True
                    unavailable_ids = candidate.artifacts.setdefault("page_mapping_unavailable_ndl_ids", [])
                    if ndl_id and ndl_id not in unavailable_ids:
                        unavailable_ids.append(ndl_id)
                    mapping_failure = self._page_mapping_failure_cache.get(str(ndl_id)) if ndl_id else None
                    normalized_failure = self._normalize_download_unavailability_reason(str(mapping_failure or ""))
                    if normalized_failure:
                        self._mark_source_unavailable(
                            candidate,
                            reason=normalized_failure,
                            ndl_id=str(ndl_id),
                            source_id=self._match_identity(top_match),
                            detail=str(mapping_failure),
                        )
                    candidate.notes.append(
                        f"page_mapping_required_for_ndl_restricted_download[{ndl_id or candidate.footnote.title}]"
                    )
                    continue
                mapping_failure = self._page_mapping_failure_cache.get(str(ndl_id)) if ndl_id else None
                if mapping_failure and self._should_skip_page_mapping_after_failure(mapping_failure):
                    candidate.notes.append(f"restricted_download_skipped[{ndl_id or candidate.footnote.title}]: {mapping_failure}")
                    continue
                page_plan = build_download_page_plan(
                    page_numbers,
                    page_window=page_window,
                    page_mapping=mapping,
                )
                start_page = int(page_plan["start_page"])
                end_page = int(page_plan["end_page"])
                if page_plan.get("page_mapping"):
                    candidate.artifacts["page_mapping"] = mapping
                    candidate.artifacts["mapped_footnote_pages"] = page_plan["mapped_footnote_pages"]
                    candidate.artifacts.pop("page_mapping_required_but_unavailable", None)
                    candidate.artifacts.pop("page_mapping_unavailable_ndl_ids", None)
                    if page_plan.get("note"):
                        candidate.notes.append(str(page_plan["note"]))
                total_scan_pages = self._get_ndl_total_pages_quick(ndl_id) if ndl_id else None
                mapped_footnote_pages = [
                    int(page)
                    for page in (page_plan.get("mapped_footnote_pages") or [])
                    if page is not None
                ]
                if total_scan_pages and (
                    any(page > int(total_scan_pages) or page < 1 for page in mapped_footnote_pages)
                    or int(start_page) > int(total_scan_pages)
                ):
                    candidate.artifacts["page_mapping_required_but_unavailable"] = True
                    unavailable_ids = candidate.artifacts.setdefault("page_mapping_unavailable_ndl_ids", [])
                    if ndl_id and ndl_id not in unavailable_ids:
                        unavailable_ids.append(ndl_id)
                    candidate.notes.append(
                        f"mapped_footnote_page_out_of_scan_range[{ndl_id or candidate.footnote.title}]:"
                        f"mapped={mapped_footnote_pages or [start_page, end_page]}/total={int(total_scan_pages)}"
                    )
                    self._mark_source_unavailable(
                        candidate,
                        reason="mapped_page_out_of_scan_range",
                        ndl_id=str(ndl_id) if ndl_id else None,
                        source_id=self._match_identity(top_match),
                        detail=f"mapped={mapped_footnote_pages or [start_page, end_page]}/total={int(total_scan_pages)}",
                    )
                    continue
                candidate.artifacts["downloaded_page_range"] = [start_page, end_page]
                attempted_ndl_ids = candidate.artifacts.setdefault("download_attempted_ndl_ids", [])
                if ndl_id and ndl_id not in attempted_ndl_ids:
                    attempted_ndl_ids.append(ndl_id)
                cached_range_pdf = self._find_cached_range_pdf(
                    output_dir,
                    ndl_id=ndl_id,
                    start_page=start_page,
                    end_page=end_page,
                )
                if cached_range_pdf is not None:
                    cached_pdf_path, cached_start, cached_end = cached_range_pdf
                    candidate.artifacts["selected_source_match"] = {
                        "ndl_id": ndl_id,
                        "platform_item_id": getattr(top_match, "platform_item_id", None),
                        "url": getattr(top_match, "url", None),
                        "platform": getattr(top_match, "platform", None),
                        "title": getattr(top_match, "title", None),
                    }
                    candidate.artifacts["downloaded_page_range"] = [cached_start, cached_end]
                    candidate.notes.append(
                        f"source_pdf_cached_range_reused:{ndl_id}:p{cached_start}-p{cached_end}"
                    )
                    return str(cached_pdf_path)
                if platform is not None:
                    requests_payload = platform.build_restricted_download_requests(
                        footnote=candidate.footnote,
                        top_match=top_match,
                        fallback_title=candidate.footnote.title,
                        output_dir=output_dir,
                        start_page=start_page,
                        end_page=end_page,
                    )
                else:
                    requests_payload = build_restricted_download_requests(
                        keywords=self._iter_ndl_search_keywords(candidate.footnote),
                        top_match=top_match,
                        fallback_title=candidate.footnote.title,
                        output_dir=output_dir,
                        start_page=start_page,
                        end_page=end_page,
                    )
                for request_kwargs in requests_payload:
                    request_kwargs["max_attempts"] = max(1, int(download_max_attempts or 1))
                    request_key = (
                        str(request_kwargs.get("ndl_id") or ""),
                        str(request_kwargs.get("keyword") if not request_kwargs.get("ndl_id") else ""),
                        int(request_kwargs.get("start_page") or start_page),
                        int(request_kwargs.get("end_page") or end_page),
                    )
                    if request_key in seen_download_requests:
                        continue
                    seen_download_requests.add(request_key)
                    outcome = module.download_first_match(**request_kwargs)
                    if getattr(outcome, "success", False):
                        outcome_metadata = getattr(outcome, "metadata", {}) or {}
                        actual_start = outcome_metadata.get("actual_start_page")
                        actual_end = outcome_metadata.get("actual_end_page")
                        requested_start = outcome_metadata.get("requested_start_page") or start_page
                        requested_end = outcome_metadata.get("requested_end_page") or end_page
                        if outcome_metadata.get("range_adjusted") or (
                            actual_start is not None
                            and actual_end is not None
                            and (int(actual_start) != int(start_page) or int(actual_end) != int(end_page))
                        ):
                            candidate.artifacts["downloaded_page_range_requested"] = [
                                int(requested_start),
                                int(requested_end),
                            ]
                            candidate.artifacts["downloaded_page_range_actual"] = [
                                int(actual_start or start_page),
                                int(actual_end or end_page),
                            ]
                            candidate.artifacts["page_mapping_required_but_unavailable"] = True
                            candidate.notes.append(
                                "restricted_download_range_adjusted"
                                f"[{ndl_id or candidate.footnote.title}]:"
                                f"{int(requested_start)}-{int(requested_end)}->"
                                f"{int(actual_start or start_page)}-{int(actual_end or end_page)}"
                            )
                            candidate.notes.append("source_pdf_rejected_adjusted_range")
                            self._mark_source_unavailable(
                                candidate,
                                reason="downloaded_page_range_adjusted",
                                ndl_id=str(ndl_id) if ndl_id else None,
                                source_id=self._match_identity(top_match),
                                detail=(
                                    f"{int(requested_start)}-{int(requested_end)}->"
                                    f"{int(actual_start or start_page)}-{int(actual_end or end_page)}"
                                ),
                            )
                            continue
                        candidate.artifacts["selected_source_match"] = {
                            "ndl_id": ndl_id,
                            "platform_item_id": getattr(top_match, "platform_item_id", None),
                            "url": getattr(top_match, "url", None),
                            "platform": getattr(top_match, "platform", None),
                            "title": getattr(top_match, "title", None),
                        }
                        candidate.artifacts["download_attempt"] = {
                            "keyword": request_kwargs["keyword"],
                            "mode": getattr(outcome, "mode", None),
                            "metadata": outcome_metadata,
                        }
                        return getattr(outcome, "file_path", None)
                    error_message = getattr(outcome, "error_message", None)
                    if error_message:
                        candidate.notes.append(f"restricted_download_failed[{request_kwargs['keyword']}]: {error_message}")
        return None

    def _is_usable_pdf(self, pdf_path: str) -> bool:
        try:
            import fitz

            path = Path(pdf_path)
            if not path.exists() or path.stat().st_size <= 0:
                return False
            with path.open("rb") as handle:
                if not handle.read(4).startswith(b"%PDF"):
                    return False
            document = fitz.open(str(path))
            try:
                if len(document) < 1:
                    return False
                page = document[0]
                text = (page.get_text("text") or "").strip()
                long_side = max(float(page.rect.width), float(page.rect.height))
                image_count = len(page.get_images(full=True))
                if len(text) >= 20:
                    return True
                if image_count and long_side < 1000:
                    return False
                return True
            finally:
                document.close()
        except Exception:
            return False

    def _find_cached_range_pdf(
        self,
        output_dir: Path,
        *,
        ndl_id: Optional[str],
        start_page: int,
        end_page: int,
    ) -> Optional[Tuple[Path, int, int]]:
        return find_cached_range_pdf_from_index(
            output_dir,
            ndl_id=ndl_id,
            start_page=start_page,
            end_page=end_page,
            is_usable_pdf=self._is_usable_pdf,
        )

    def _download_public_pdf(self, match: NDLSearchMatch, *, output_dir: Path) -> Optional[str]:
        return download_public_pdf(match, output_dir=output_dir)

    def _expand_page_window(self, page_number: int, page_window: int) -> List[int]:
        return expand_page_window(page_number, page_window)

    def _map_target_page(self, page: int, local_page_range: Any) -> Optional[int]:
        return map_target_page(page, local_page_range)

    def _estimate_scan_page_for_book_page(
        self,
        page_mapping: Optional[Dict[str, Any]],
        book_page: int,
    ) -> Optional[int]:
        return estimate_scan_page_for_book_page(page_mapping, book_page)

    def _estimate_book_pages_from_scan_page(
        self,
        page_mapping: Optional[Dict[str, Any]],
        scan_page: int,
    ) -> List[int]:
        return estimate_book_pages_from_scan_page(page_mapping, scan_page)

    def _extract_pages_directly(
        self,
        pdf_path: str,
        *,
        pages: Sequence[int],
        local_page_range: Any,
        output_dir: Path,
        ocr_model: str,
        page_mapping: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Tuple[int, str]], str]:
        return extract_pages_directly_from_pdf(
            pdf_path,
            pages=pages,
            local_page_range=local_page_range,
            output_dir=output_dir,
            ocr_model=ocr_model,
            page_mapping=page_mapping,
            extract_page_text=lambda path, page, out, model: self._extract_pdf_page_text(
                path,
                page_number=page,
                output_dir=out,
                ocr_model=model,
            ),
            extract_spread_page_texts=lambda path, page, scan, book_pages, out, model: self._extract_pdf_spread_page_texts(
                path,
                page_number=page,
                scan_page_number=scan,
                book_page_numbers=book_pages,
                output_dir=out,
                ocr_model=model,
            ),
            extract_multi_panel_page_texts=lambda path, page, scan, book_pages, out, model: self._extract_pdf_multi_panel_page_texts(
                path,
                page_number=page,
                scan_page_number=scan,
                book_page_numbers=book_pages,
                output_dir=out,
                ocr_model=model,
            ),
        )

    def _wait_for_pdf_ready(
        self,
        pdf_path: str,
        *,
        local_page_range: Any,
        output_dir: Path,
        timeout_seconds: int = 45,
    ) -> Dict[str, Any]:
        del output_dir
        return wait_for_pdf_ready(
            pdf_path,
            local_page_range=local_page_range,
            timeout_seconds=timeout_seconds,
        )

    def _extract_pdf_spread_page_texts(
        self,
        pdf_path: str,
        *,
        page_number: int,
        scan_page_number: int,
        book_page_numbers: Sequence[int],
        output_dir: Path,
        ocr_model: str,
    ) -> List[Tuple[int, str]]:
        return extract_pdf_spread_page_texts_from_pdf(
            pdf_path,
            page_number=page_number,
            scan_page_number=scan_page_number,
            book_page_numbers=book_page_numbers,
            output_dir=output_dir,
            ocr_model=ocr_model,
            render_page=lambda path, page, out: self._render_pdf_page(path, page_number=page, output_dir=out),
            split_image=lambda image, scan, out: self._split_double_page_image(
                image,
                scan_page_number=scan,
                output_dir=out,
            ),
            ocr_image=lambda image, out, model: self._ocr_image_text(
                image,
                output_dir=out,
                ocr_model=model,
            ),
        )

    def _extract_pdf_multi_panel_page_texts(
        self,
        pdf_path: str,
        *,
        page_number: int,
        scan_page_number: int,
        book_page_numbers: Sequence[int],
        output_dir: Path,
        ocr_model: str,
    ) -> List[Tuple[int, str]]:
        return extract_pdf_multi_panel_page_texts_from_pdf(
            pdf_path,
            page_number=page_number,
            scan_page_number=scan_page_number,
            book_page_numbers=book_page_numbers,
            output_dir=output_dir,
            ocr_model=ocr_model,
            render_page=lambda path, page, out: self._render_pdf_page(path, page_number=page, output_dir=out),
            ocr_image=lambda image, out, model: self._ocr_image_text(
                image,
                output_dir=out,
                ocr_model=model,
            ),
        )

    def _split_double_page_image(
        self,
        image_path: str,
        *,
        scan_page_number: int,
        output_dir: Path,
    ) -> Dict[str, str]:
        return split_double_page_image(
            image_path,
            scan_page_number=scan_page_number,
            output_dir=output_dir,
        )

    def _detect_spread_gutter_x(self, image: Any) -> int:
        return detect_spread_gutter_x(image)

    def _ocr_image_text(
        self,
        image_path: str,
        *,
        output_dir: Path,
        ocr_model: str,
    ) -> str:
        return ocr_image_text_from_pdf(
            image_path,
            output_dir=output_dir,
            ocr_model=ocr_model,
            ocr_processor_getter=self._get_ocr_processor,
        )

    def _extract_pdf_page_text(
        self,
        pdf_path: str,
        *,
        page_number: int,
        output_dir: Path,
        ocr_model: str,
    ) -> str:
        return extract_pdf_page_text_from_pdf(
            pdf_path,
            page_number=page_number,
            output_dir=output_dir,
            ocr_model=ocr_model,
            pdf_processor_getter=self._get_pdf_processor,
            ocr_processor_getter=self._get_ocr_processor,
            render_page=lambda path, page, out: self._render_pdf_page(path, page_number=page, output_dir=out),
        )

    def _extract_pages_via_subprocess(
        self,
        pdf_path: str,
        *,
        pages: Sequence[int],
        local_page_range: Any,
        output_dir: Path,
        ocr_model: str,
        attempts_per_page: int = 1,
    ) -> List[Tuple[int, str]]:
        project_root = Path(__file__).resolve().parent.parent
        script = """
import json
import sys
import time
from pathlib import Path
from modules.historical_citation_verifier import HistoricalCitationVerifier

pdf_path = sys.argv[1]
output_dir = Path(sys.argv[2])
ocr_model = sys.argv[3]
pages = json.loads(sys.argv[4])
local_page_range = json.loads(sys.argv[5])
attempts_per_page = int(sys.argv[6])

verifier = HistoricalCitationVerifier()
results = []
for page in pages:
    pdf_page_number = page
    if (
        isinstance(local_page_range, list)
        and len(local_page_range) == 2
        and local_page_range[0] <= page <= local_page_range[1]
    ):
        pdf_page_number = page - local_page_range[0] + 1
    text = ""
    for attempt in range(max(1, attempts_per_page)):
        verifier = HistoricalCitationVerifier()
        text = verifier._extract_pdf_page_text(
            pdf_path,
            page_number=pdf_page_number,
            output_dir=output_dir,
            ocr_model=ocr_model,
        )
        if text and text.strip():
            break
        if attempt + 1 < attempts_per_page:
            time.sleep(8 * (attempt + 1))
    if text and text.strip():
        results.append([page, text])

print("__RESULT_START__")
print(json.dumps(results, ensure_ascii=False))
print("__RESULT_END__")
"""
        command = [
            sys.executable,
            "-c",
            script,
            pdf_path,
            str(output_dir),
            ocr_model,
            json.dumps(list(pages), ensure_ascii=False),
            json.dumps(local_page_range or [], ensure_ascii=False),
            str(max(1, int(attempts_per_page or 1))),
        ]
        try:
            process = subprocess.run(command, cwd=str(project_root), capture_output=True, timeout=600)
        except subprocess.TimeoutExpired as exc:
            stdout_text = (exc.stdout or b"").decode("utf-8", errors="ignore")
            stderr_text = (exc.stderr or b"").decode("utf-8", errors="ignore")
            debug_payload = {
                "command": command[:3] + ["<inline-script>", "<pdf-path>", "<output-dir>", ocr_model],
                "returncode": "timeout",
                "pages": list(pages),
                "local_page_range": list(local_page_range or []),
                "stdout_preview": stdout_text[:2000],
                "stderr_preview": stderr_text[:2000],
            }
            try:
                (output_dir / "ocr_subprocess_debug.json").write_text(
                    json.dumps(debug_payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                (output_dir / "ocr_subprocess_stdout.log").write_text(stdout_text, encoding="utf-8")
                (output_dir / "ocr_subprocess_stderr.log").write_text(stderr_text, encoding="utf-8")
            except Exception:
                pass
            return []
        stdout_text = (process.stdout or b"").decode("utf-8", errors="ignore")
        stderr_text = (process.stderr or b"").decode("utf-8", errors="ignore")
        debug_payload: Dict[str, Any] = {
            "command": command[:3] + ["<inline-script>", "<pdf-path>", "<output-dir>", ocr_model],
            "returncode": process.returncode,
            "pages": list(pages),
            "local_page_range": list(local_page_range or []),
            "stdout_preview": stdout_text[:2000],
            "stderr_preview": stderr_text[:2000],
        }
        if process.returncode != 0:
            try:
                (output_dir / "ocr_subprocess_debug.json").write_text(
                    json.dumps(debug_payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                (output_dir / "ocr_subprocess_stdout.log").write_text(stdout_text, encoding="utf-8")
                (output_dir / "ocr_subprocess_stderr.log").write_text(stderr_text, encoding="utf-8")
            except Exception:
                pass
            return []
        content = stdout_text.strip()
        if not content:
            try:
                (output_dir / "ocr_subprocess_debug.json").write_text(
                    json.dumps(debug_payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                (output_dir / "ocr_subprocess_stdout.log").write_text(stdout_text, encoding="utf-8")
                (output_dir / "ocr_subprocess_stderr.log").write_text(stderr_text, encoding="utf-8")
            except Exception:
                pass
            return []
        start_marker = "__RESULT_START__"
        end_marker = "__RESULT_END__"
        start_index = content.find(start_marker)
        end_index = content.rfind(end_marker)
        if start_index == -1 or end_index == -1 or end_index <= start_index:
            try:
                (output_dir / "ocr_subprocess_debug.json").write_text(
                    json.dumps(debug_payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                (output_dir / "ocr_subprocess_stdout.log").write_text(stdout_text, encoding="utf-8")
                (output_dir / "ocr_subprocess_stderr.log").write_text(stderr_text, encoding="utf-8")
            except Exception:
                pass
            return []
        payload = content[start_index + len(start_marker) : end_index].strip()
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            try:
                (output_dir / "ocr_subprocess_debug.json").write_text(
                    json.dumps(debug_payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                (output_dir / "ocr_subprocess_stdout.log").write_text(stdout_text, encoding="utf-8")
                (output_dir / "ocr_subprocess_stderr.log").write_text(stderr_text, encoding="utf-8")
            except Exception:
                pass
            return []
        results = [
            (int(item[0]), str(item[1]))
            for item in parsed
            if isinstance(item, list) and len(item) == 2
        ]
        debug_payload["result_count"] = len(results)
        try:
            (output_dir / "ocr_subprocess_debug.json").write_text(
                json.dumps(debug_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        return results

    def _is_ocr_backend_available(self, ocr_model: str) -> bool:
        try:
            from modules.unified_ocr_processor import UnifiedOCRProcessor

            processor = UnifiedOCRProcessor()
            if processor.is_model_available(ocr_model):
                return True
            if processor.is_model_available("tesseract"):
                return True
            return self._llm_client is not None and processor.is_model_available("llm_ocr")
        except Exception:
            return False

    def _render_pdf_page(self, pdf_path: str, *, page_number: int, output_dir: Path) -> Optional[str]:
        return render_pdf_page(pdf_path, page_number=page_number, output_dir=output_dir)

    def _align_translation(
        self,
        translation_text: str,
        extracted_pages: Sequence[Tuple[int, str]],
    ) -> Tuple[Optional[int], str, Optional[float], str]:
        llm_client = self._llm_client
        if llm_client is None and os.environ.get("HISTORICAL_CITATION_ENABLE_GENERAL_LLM_ALIGNMENT") == "1":
            llm_client = self._get_llm_client(optional=True)
        return align_translation(
            translation_text,
            extracted_pages,
            llm_client=llm_client,
        )

    def _score_alignment_candidate(self, translation_text: str, segment: str) -> float:
        return score_alignment_candidate(translation_text, segment)

    def _trim_aligned_segment(self, translation_text: str, segment: str) -> str:
        return trim_aligned_segment(translation_text, segment)

    def _segment_page_text(self, text: str) -> List[str]:
        return segment_page_text(text)

    def _parse_llm_json(self, raw_content: str) -> Dict[str, Any]:
        return parse_llm_json(raw_content)

    def _get_ndl_download_module(self):
        if self._ndl_download_module is None:
            from modules.ndl_download_workflow import NDLDownloadModule

            self._ndl_download_module = NDLDownloadModule()
        return self._ndl_download_module

    def _get_source_platform_registry(self) -> SourcePlatformRegistry:
        if self._source_platform_registry is None:
            self._source_platform_registry = default_source_platform_registry(
                ndl_download_module_getter=self._get_ndl_download_module,
                prefer_external_ndl_module=self._prefer_external_ndl_module,
                allow_external_ndl_fallback=self._allow_external_ndl_fallback,
            )
        return self._source_platform_registry

    def _get_platform_for_match(self, match: Optional[NDLSearchMatch]) -> Optional[SourcePlatformAdapter]:
        if match is None:
            return None
        return self._get_source_platform_registry().get(match.platform or "ndl")

    def _get_pdf_processor(self):
        if self._pdf_processor is None:
            from modules.pdf_processor import PDFProcessor

            self._pdf_processor = PDFProcessor(output_dir=str(Path("output") / "historical_citation_verification"))
        return self._pdf_processor

    def _get_ocr_processor(self):
        if self._ocr_processor is None:
            from modules.unified_ocr_processor import UnifiedOCRConfig, UnifiedOCRProcessor

            self._ocr_processor = UnifiedOCRProcessor(
                UnifiedOCRConfig(
                    default_model="ndlocr_lite",
                    fallback_models=["tesseract"],
                    tesseract_path=self._detect_tesseract_path(),
                )
            )
        return self._ocr_processor

    def _detect_tesseract_path(self) -> Optional[str]:
        candidates = [
            os.environ.get("TESSERACT_CMD"),
            os.environ.get("TESSERACT_PATH"),
            shutil.which("tesseract"),
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return str(Path(candidate))
        return None

    def _get_llm_client(self, *, optional: bool = False):
        if self._llm_client is None:
            try:
                from app.config import config
                from modules.llm_client import LLMClient

                self._llm_client = LLMClient(config["default"].LLM_CONFIG)
            except Exception:
                if optional:
                    return None
                raise
        return self._llm_client

    def _get_review_llm_client(self, *, optional: bool = False):
        if self._review_llm_client is not None:
            return self._review_llm_client
        if self._prefer_ollama_review:
            try:
                self._review_llm_client = OllamaChatClient()
                return self._review_llm_client
            except Exception:
                if optional:
                    return None
                raise
        return self._get_llm_client(optional=optional)
