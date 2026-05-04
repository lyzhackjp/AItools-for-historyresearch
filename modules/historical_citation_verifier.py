from __future__ import annotations

import hashlib
import importlib.util
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
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
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
from modules.historical_citation.pdf_paper_parser import parse_pdf_paper
from modules.historical_citation.cross_validation import (
    cross_validate_fulltext_ocr_case,
    cross_validate_fulltext_ocr_cases,
)
from modules.historical_citation.footnote_parser import (
    DEFAULT_PAGE_PATTERNS,
    DEFAULT_QUOTE_PATTERNS,
    DEFAULT_STOPWORD_PREFIXES,
    DEFAULT_TITLE_PATTERNS,
    apply_footnote_title_aliases,
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
    review_context_candidates_with_llm,
)
from modules.historical_citation.models import (
    CitationCandidate,
    NDLSearchMatch,
    ParsedFootnote,
    ParsedParagraph,
)
from modules.historical_citation.ndl_fulltext_context import (
    NDLFulltextHit,
    expand_ndl_snippet_context,
    probe_ndl_fulltext_context,
)
from modules.historical_citation.ndl_search import (
    author_query_terms,
    build_ndl_sru_queries,
    iter_ndl_search_keywords,
    normalize_match_text,
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
from modules.historical_citation.progress import build_progress_event
from modules.historical_citation.reporting import (
    describe_page_trace,
    render_resume_markdown_report,
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
from modules.historical_citation.source_graph import (
    attach_source_graph_artifacts,
    build_manual_search_recipe,
    build_source_query_plan,
    candidate_source_claim_context,
    dedupe_candidates,
)
from modules.historical_citation.source_platforms import (
    SourcePlatformAdapter,
    SourcePlatformRegistry,
    default_source_platform_registry,
)
from modules.historical_citation.source_resolvers import _load_resolver_config


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
    SOURCE_LEVEL_OCR_CACHE_FILENAME = "source_level_ocr_cache.json"
    FULLTEXT_CONTEXT_EXPANSION_CACHE_FILENAME = "fulltext_context_expansion_cache.json"
    FULLTEXT_CONTEXT_EXPANSION_PAYLOAD_FIELDS = (
        "expanded_context",
        "expanded_context_status",
        "expanded_context_note",
        "expanded_context_evidence_count",
    )

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
    DEFAULT_DIARY_CLAIM_FACET_RULES = (
        {
            "id": "us",
            "role": "anchor",
            "trigger_patterns": [r"\u7f8e\u56fd|\u7f8e\u570b|America|United States|U\.S\."],
            "terms": ["\u7c73\u56fd", "\u7c73\u570b", "\u7c73"],
        },
        {
            "id": "economy",
            "role": "theme",
            "trigger_patterns": [
                r"\u7ecf\u6d4e|\u7d93\u6fdf|\u7d4c\u6e08|\u4e0d\u666f\u6c14|\u4e0d\u666f\u6c23|\u4e0d\u666f\u6c17|\u6050\u614c|recession|depression|econom"
            ],
            "terms": [
                "\u7d4c\u6e08",
                "\u7d93\u6fdf",
                "\u4e0d\u666f\u6c17",
                "\u4e0d\u666f\u6c23",
                "\u666f\u6c17",
                "\u666f\u6c23",
                "\u6050\u614c",
                "\u8cc7\u672c",
                "\u8cc7\u672c\u5bb6",
            ],
        },
        {
            "id": "future_influence",
            "role": "theme",
            "trigger_patterns": [
                r"\u5c06\u6765|\u5c07\u4f86|\u672a\u6765|\u524d\u666f|\u4e16\u754c|\u5f71\u54cd|\u5f71\u97ff|future|world|influence"
            ],
            "terms": [
                "\u5c06\u6765",
                "\u5c07\u4f86",
                "\u4e16\u754c",
                "\u5f71\u97ff",
                "\u524d\u9014",
                "\u5149\u660e",
                "\u6d0b\u3005",
                "\u6d0b\u6d0b",
            ],
        },
        {
            "id": "vitality",
            "role": "theme",
            "trigger_patterns": [r"\u6d3b\u529b|\u6d3b\u6c14|\u6d3b\u6c23|\u6d3b\u6c17|\u6709\u529b|\u52e2\u3044|vital|energetic"],
            "terms": ["\u6d3b\u6c17", "\u6d3b\u6c23", "\u6d3b\u529b", "\u6709\u529b", "\u76db\u3093"],
        },
    )
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
        self._fulltext_context_expansion_cache: Dict[Tuple[str, str, str, str, str], Dict[str, Any]] = {}
        self._fulltext_context_expansion_loaded_paths: set[str] = set()
        self._last_page_mapping_sample_failure: Optional[str] = None
        self._restricted_download_dependency_status_cache: Optional[Dict[str, Any]] = None
        self._progress_event_callback: Optional[Callable[..., None]] = None

    def _emit_progress_event(
        self,
        event: str,
        *,
        subphase: str,
        status: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        callback = self._progress_event_callback
        if not callable(callback):
            return
        try:
            callback(event=event, subphase=subphase, status=status, metrics=metrics or {})
        except Exception:
            return

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
            "input_formats": ["docx", "pdf"],
            "output_types": ["historical_citation_parse", "historical_citation_verification"],
            "source_platforms": source_platforms,
            "capabilities": [
                "docx_footnote_parse",
                "pdf_paper_footnote_parse",
                "pdf_paper_ocr_fallback",
                "translation_quote_candidate_building",
                "source_metadata_search",
                "source_metadata_search_cache",
                "restricted_download_request_building",
                "pdf_page_window_ocr",
                "translation_source_alignment",
                "verification_batch_merge",
                "jsonl_progress_events",
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

    def parse_pdf_package(
        self,
        file_path: str,
        *,
        include_unquoted: bool = True,
        output_dir: Optional[str] = None,
        ocr_model: str = "ndlocr_lite",
    ) -> Dict[str, Any]:
        """Parse a Chinese PDF paper into citation candidates without network access."""
        parsed = self.parse_pdf(
            file_path,
            ocr_output_dir=Path(output_dir) / "pdf_input_ocr" if output_dir else None,
            ocr_model=ocr_model,
        )
        candidates = self.build_candidates(
            parsed["paragraphs"],
            parsed["footnotes"],
            include_unquoted=include_unquoted,
        )
        raw_candidate_count = len(candidates)
        candidates = dedupe_candidates(candidates, paper_id=str(parsed["document"].get("file_path") or file_path))
        candidate_dicts = [item.to_dict() for item in candidates]
        quality_flags = self._parse_quality_flags(parsed, candidates)
        if parsed.get("pdf_parse_debug"):
            unmapped_pages = [
                item
                for item in parsed["pdf_parse_debug"]
                if item.get("footnotes_found") and not item.get("body_markers_found")
            ]
            if unmapped_pages:
                quality_flags.append("pdf_footnotes_without_body_markers")
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
            "quality_flags": sorted(set(quality_flags)),
            "document": parsed["document"],
            "paragraphs": [item.to_dict() for item in parsed["paragraphs"]],
            "footnotes": [item.to_dict() for item in parsed["footnotes"]],
            "candidates": candidate_dicts,
            "summary": {
                "paragraph_count": len(parsed["paragraphs"]),
                "footnote_count": len(parsed["footnotes"]),
                "candidate_count": len(candidates),
                "raw_candidate_count": raw_candidate_count,
                "deduped_candidate_count": len(candidates),
                "duplicate_candidate_count": max(0, raw_candidate_count - len(candidates)),
                "include_unquoted": include_unquoted,
                "input_format": "pdf",
            },
            "pdf_parse_debug": parsed.get("pdf_parse_debug", []),
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

    def verify_pdf_package(
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
        include_unquoted: bool = True,
        candidate_offset: int = 0,
        candidate_limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run verification for a Chinese PDF paper and wrap output in a package."""
        result = self.verify_pdf(
            file_path,
            search_ndl=search_ndl,
            download_source=download_source,
            restricted_download=restricted_download,
            max_search_results=max_search_results,
            page_window=page_window,
            ocr_model=ocr_model,
            output_dir=output_dir,
            platform_names=platform_names,
            include_unquoted=include_unquoted,
            candidate_offset=candidate_offset,
            candidate_limit=candidate_limit,
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
            "pdf_parse_debug": result.get("pdf_parse_debug", []),
            "execution": {
                "search_ndl": search_ndl,
                "download_source": download_source,
                "restricted_download": restricted_download,
                "max_search_results": max_search_results,
                "page_window": page_window,
                "ocr_model": ocr_model,
                "platform_names": list(platform_names or []),
                "include_unquoted": include_unquoted,
                "input_format": "pdf",
                "candidate_offset": candidate_offset,
                "candidate_limit": candidate_limit,
            },
            "capabilities": self.get_capabilities(),
        }

    def _load_page_mapping_cache(self, output_dir: Path) -> Dict[str, Dict[str, Any]]:
        self._page_mapping_cache = load_page_mapping_cache(
            output_dir,
            current_cache=self._page_mapping_cache,
        )
        return self._page_mapping_cache

    def _source_level_cache_key_for_candidate(self, candidate: CitationCandidate) -> str:
        direct = str(candidate.artifacts.get("source_level_cache_key") or "").strip()
        if direct:
            return direct
        resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
        if isinstance(resolver_plan, dict):
            return str(resolver_plan.get("source_level_cache_key") or "").strip()
        return ""

    def _source_level_page_mapping_cache_id(self, source_level_cache_key: str) -> str:
        return f"source:{source_level_cache_key}" if source_level_cache_key else ""

    def _save_page_mapping_cache(
        self,
        output_dir: Path,
        ndl_id: str,
        mapping: Dict[str, Any],
        *,
        source_level_cache_key: str = "",
    ) -> None:
        mapping_to_save = dict(mapping)
        if ndl_id:
            mapping_to_save.setdefault("ndl_id", str(ndl_id))
        if source_level_cache_key:
            mapping_to_save.setdefault("source_level_cache_key", source_level_cache_key)
        self._page_mapping_cache = save_page_mapping_cache(
            output_dir,
            ndl_id,
            mapping_to_save,
            current_cache=self._page_mapping_cache,
        )
        source_cache_id = self._source_level_page_mapping_cache_id(source_level_cache_key)
        if source_cache_id:
            alias_mapping = dict(mapping_to_save)
            alias_mapping["source_level_cache_alias"] = True
            alias_mapping["source_level_cache_note"] = f"alias_for_ndl:{ndl_id}"
            self._page_mapping_cache = save_page_mapping_cache(
                output_dir,
                source_cache_id,
                alias_mapping,
                current_cache=self._page_mapping_cache,
            )

    def _load_source_level_page_mapping_cache(
        self,
        candidate: CitationCandidate,
        *,
        ndl_id: str,
        output_dir: Path,
    ) -> Optional[Dict[str, Any]]:
        source_level_cache_key = self._source_level_cache_key_for_candidate(candidate)
        source_cache_id = self._source_level_page_mapping_cache_id(source_level_cache_key)
        if not source_cache_id:
            return None
        self._load_page_mapping_cache(output_dir)
        cached = self._page_mapping_cache.get(source_cache_id)
        if not cached:
            return None
        cached_ndl_id = str(cached.get("ndl_id") or "")
        if cached_ndl_id and cached_ndl_id != str(ndl_id):
            candidate.notes.append(
                f"source_level_page_mapping_cache_pid_mismatch:{cached_ndl_id}!={ndl_id}"
            )
            candidate.artifacts["source_level_page_mapping_cache_mismatch"] = {
                "source_level_cache_key": source_level_cache_key,
                "cached_ndl_id": cached_ndl_id,
                "current_ndl_id": str(ndl_id),
            }
            return None
        candidate.notes.append("source_level_page_mapping_cache_hit")
        candidate.artifacts["source_level_page_mapping_cache_hit"] = {
            "source_level_cache_key": source_level_cache_key,
            "ndl_id": str(ndl_id),
        }
        self._save_page_mapping_cache(
            output_dir,
            str(ndl_id),
            cached,
            source_level_cache_key=source_level_cache_key,
        )
        return cached

    def _source_level_ocr_cache_key(
        self,
        candidate: CitationCandidate,
        *,
        ndl_id: str,
        ocr_model: str,
    ) -> str:
        source_level_cache_key = self._source_level_cache_key_for_candidate(candidate)
        if not source_level_cache_key or not ndl_id:
            return ""
        return f"{source_level_cache_key}|ndl:{ndl_id}|ocr:{ocr_model or 'unknown'}"

    def _source_level_ocr_cache_path(self, output_dir: Path) -> Path:
        return output_dir / self.SOURCE_LEVEL_OCR_CACHE_FILENAME

    def _load_source_level_ocr_cache(self, output_dir: Path) -> Dict[str, Any]:
        path = self._source_level_ocr_cache_path(output_dir)
        if not path.exists():
            return {"version": 1, "records": {}}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "records": {}}
        if not isinstance(payload, dict):
            return {"version": 1, "records": {}}
        records = payload.get("records")
        if not isinstance(records, dict):
            payload["records"] = {}
        return payload

    def _write_source_level_ocr_cache(self, output_dir: Path, payload: Dict[str, Any]) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        payload["version"] = 1
        payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
        path = self._source_level_ocr_cache_path(output_dir)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)

    def _required_ocr_cache_pages(
        self,
        *,
        target_pages: Sequence[int],
        page_mapping: Optional[Dict[str, Any]],
        page_label_mode: str,
    ) -> List[int]:
        required: List[int] = []
        if page_label_mode == "book" and page_mapping:
            for scan_page in target_pages:
                for book_page in self._estimate_book_pages_from_scan_page(page_mapping, int(scan_page)):
                    if book_page not in required:
                        required.append(book_page)
        else:
            for page in target_pages:
                page_int = int(page)
                if page_int not in required:
                    required.append(page_int)
        return required

    def _load_source_level_ocr_pages(
        self,
        candidate: CitationCandidate,
        *,
        output_dir: Path,
        ndl_id: str,
        target_pages: Sequence[int],
        ocr_model: str,
        page_mapping: Optional[Dict[str, Any]],
    ) -> Optional[Tuple[List[Tuple[int, str]], str]]:
        cache_key = self._source_level_ocr_cache_key(candidate, ndl_id=ndl_id, ocr_model=ocr_model)
        if not cache_key:
            return None
        payload = self._load_source_level_ocr_cache(output_dir)
        record = (payload.get("records") or {}).get(cache_key)
        if not isinstance(record, dict):
            return None
        cached_ndl_id = str(record.get("ndl_id") or "")
        if cached_ndl_id and cached_ndl_id != str(ndl_id):
            candidate.notes.append(f"source_level_ocr_cache_pid_mismatch:{cached_ndl_id}!={ndl_id}")
            return None
        page_label_mode = str(record.get("page_label_mode") or "scan")
        required_pages = self._required_ocr_cache_pages(
            target_pages=target_pages,
            page_mapping=page_mapping,
            page_label_mode=page_label_mode,
        )
        page_entries = record.get("pages") or []
        cached_pages: Dict[int, str] = {}
        for entry in page_entries:
            if not isinstance(entry, dict):
                continue
            page = entry.get("page")
            text = entry.get("text")
            try:
                page_int = int(page)
            except (TypeError, ValueError):
                continue
            if isinstance(text, str) and text.strip():
                cached_pages[page_int] = text
        missing_pages = [page for page in required_pages if page not in cached_pages]
        if missing_pages:
            candidate.artifacts["source_level_ocr_cache_miss"] = {
                "cache_key": cache_key,
                "missing_pages": missing_pages,
            }
            return None
        extracted = sorted(cached_pages.items(), key=lambda item: item[0])
        candidate.notes.append("source_level_ocr_cache_hit")
        candidate.artifacts["source_level_ocr_cache_hit"] = {
            "cache_key": cache_key,
            "page_label_mode": page_label_mode,
            "pages": required_pages,
        }
        return extracted, page_label_mode

    def _save_source_level_ocr_pages(
        self,
        candidate: CitationCandidate,
        *,
        output_dir: Path,
        ndl_id: str,
        ocr_model: str,
        extracted_pages: Sequence[Tuple[int, str]],
        page_label_mode: str,
    ) -> None:
        if not extracted_pages:
            return
        cache_key = self._source_level_ocr_cache_key(candidate, ndl_id=ndl_id, ocr_model=ocr_model)
        if not cache_key:
            return
        payload = self._load_source_level_ocr_cache(output_dir)
        records = payload.setdefault("records", {})
        if not isinstance(records, dict):
            records = {}
            payload["records"] = records
        record = records.get(cache_key)
        if not isinstance(record, dict):
            record = {
                "source_level_cache_key": self._source_level_cache_key_for_candidate(candidate),
                "ndl_id": str(ndl_id),
                "ocr_model": ocr_model,
                "page_label_mode": page_label_mode,
                "pages": [],
            }
        page_map: Dict[int, Dict[str, Any]] = {}
        for entry in record.get("pages") or []:
            if not isinstance(entry, dict):
                continue
            try:
                page_int = int(entry.get("page"))
            except (TypeError, ValueError):
                continue
            page_map[page_int] = entry
        for page, text in extracted_pages:
            if not str(text or "").strip():
                continue
            page_map[int(page)] = {
                "page": int(page),
                "text": text,
                "cleaned_text": self._clean_ocr_text_for_review(text),
            }
        record["pages"] = [page_map[key] for key in sorted(page_map)]
        record["page_label_mode"] = page_label_mode
        record["downloaded_page_range"] = candidate.artifacts.get("downloaded_page_range")
        record["source_pdf"] = candidate.artifacts.get("source_pdf")
        record["updated_at"] = datetime.now().isoformat(timespec="seconds")
        records[cache_key] = record
        self._write_source_level_ocr_cache(output_dir, payload)
        candidate.notes.append("source_level_ocr_cache_saved")

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
                    claim_text=self._source_claim_context_for_queries(candidate),
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

            candidate.artifacts["manual_search_recipe"] = build_manual_search_recipe(
                candidate.footnote,
                claim_text=self._source_claim_context_for_queries(candidate),
                current_status=candidate.verification_status,
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

    def verify_pdf(
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
        include_unquoted: bool = True,
        candidate_offset: int = 0,
        candidate_limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        report_dir = Path(output_dir or Path("output") / "historical_citation_pdf_verification" / uuid.uuid4().hex[:8])
        report_dir.mkdir(parents=True, exist_ok=True)
        parsed = self.parse_pdf(
            file_path,
            ocr_output_dir=report_dir / "pdf_input_ocr",
            ocr_model=ocr_model,
        )
        candidates = self.build_candidates(
            parsed["paragraphs"],
            parsed["footnotes"],
            include_unquoted=include_unquoted,
        )
        raw_candidate_count = len(candidates)
        candidates = dedupe_candidates(candidates, paper_id=str(parsed["document"].get("file_path") or file_path))
        total_candidate_count = len(candidates)
        batch_offset = max(candidate_offset, 0)
        if batch_offset or candidate_limit is not None:
            batch_end = None if candidate_limit is None else batch_offset + max(candidate_limit, 0)
            candidates = candidates[batch_offset:batch_end]
        candidate_batch = {
            "total_candidates": total_candidate_count,
            "offset": batch_offset,
            "limit": candidate_limit,
            "processed_candidates": len(candidates),
            "raw_candidate_count": raw_candidate_count,
            "duplicate_candidate_count": max(0, raw_candidate_count - total_candidate_count),
        }
        progress_path = report_dir / "progress.jsonl"
        partial_json_path = report_dir / "verification_results.partial.json"
        if progress_path.exists():
            progress_path.unlink()

        verification_results: List[CitationCandidate] = []
        for processed_index, candidate in enumerate(candidates, start=1):
            if search_ndl:
                candidate.ndl_matches = self.search_sources(
                    candidate.footnote,
                    max_results=max_search_results,
                    platform_names=platform_names,
                    claim_text=self._source_claim_context_for_queries(candidate),
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

            candidate.artifacts["manual_search_recipe"] = build_manual_search_recipe(
                candidate.footnote,
                claim_text=self._source_claim_context_for_queries(candidate),
                current_status=candidate.verification_status,
            )
            verification_results.append(candidate)
            progress_record = build_progress_event(
                "candidate_completed",
                phase="verification",
                current=processed_index,
                total=len(candidates),
                global_current=batch_offset + processed_index,
                global_total=total_candidate_count,
                candidate_id=candidate.candidate_id,
                footnote_id=candidate.footnote_id,
                status=candidate.verification_status,
                metrics={"match_count": len(candidate.ndl_matches or [])},
            )
            with progress_path.open("a", encoding="utf-8") as progress_file:
                progress_file.write(json.dumps(progress_record, ensure_ascii=False) + "\n")
            partial_json_path.write_text(
                json.dumps(
                    {
                        "document": parsed["document"],
                        "summary": self._summarize_results(verification_results),
                        "candidate_batch": candidate_batch,
                        "pdf_parse_debug": parsed.get("pdf_parse_debug", []),
                        "results": [item.to_dict() for item in verification_results],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        summary = self._summarize_results(verification_results)
        json_path = report_dir / "verification_results.json"
        markdown_path = report_dir / "verification_report.md"
        json_path.write_text(
            json.dumps(
                {
                    "document": parsed["document"],
                    "summary": summary,
                    "candidate_batch": candidate_batch,
                    "pdf_parse_debug": parsed.get("pdf_parse_debug", []),
                    "results": [item.to_dict() for item in verification_results],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        markdown_path.write_text(
            self._render_word_style_report(
                parsed["document"],
                verification_results,
                total_candidates=total_candidate_count,
                output_dir=report_dir,
                key_offset=batch_offset,
            ),
            encoding="utf-8",
        )

        return {
            "success": True,
            "document": parsed["document"],
            "summary": summary,
            "candidate_batch": candidate_batch,
            "paragraphs": [item.to_dict() for item in parsed["paragraphs"]],
            "footnotes": [item.to_dict() for item in parsed["footnotes"]],
            "pdf_parse_debug": parsed.get("pdf_parse_debug", []),
            "results": [item.to_dict() for item in verification_results],
            "artifacts": {
                "output_dir": str(report_dir.resolve()),
                "json_report": str(json_path.resolve()),
                "markdown_report": str(markdown_path.resolve()),
                "partial_json_report": str(partial_json_path.resolve()),
                "progress_jsonl": str(progress_path.resolve()),
            },
        }

    def _render_word_style_report(
        self,
        document: Dict[str, Any],
        candidates: Sequence[CitationCandidate],
        *,
        total_candidates: int,
        output_dir: Path,
        key_offset: int = 0,
    ) -> str:
        checkpoint = {
            "results": {
                f"{key_offset + index}:{candidate.candidate_id}": candidate.to_dict()
                for index, candidate in enumerate(candidates)
            },
            "artifacts": {},
        }
        return render_resume_markdown_report(
            document=document,
            checkpoint=checkpoint,
            total_candidates=total_candidates,
            output_dir=output_dir,
        )

    def parse_docx(self, file_path: str) -> Dict[str, Any]:
        parsed = parse_docx_document(
            file_path,
            extract_quotes=self.extract_quotes,
            parse_footnote=self.parse_footnote,
        )
        apply_footnote_title_aliases(parsed["footnotes"])
        return parsed

    def parse_pdf(
        self,
        file_path: str,
        *,
        ocr_output_dir: Optional[Path] = None,
        ocr_model: str = "ndlocr_lite",
        enable_ocr_fallback: bool = True,
    ) -> Dict[str, Any]:
        ocr_page_text_provider = None
        if enable_ocr_fallback:
            ocr_root = ocr_output_dir or Path("output") / "historical_citation_pdf_input_ocr" / Path(file_path).stem

            def ocr_page_text_provider(page_number: int) -> str:
                return extract_pdf_page_text_from_pdf(
                    file_path,
                    page_number=page_number,
                    output_dir=ocr_root,
                    ocr_model=ocr_model,
                    pdf_processor_getter=self._get_pdf_processor,
                    ocr_processor_getter=self._get_ocr_processor,
                )

        return parse_pdf_paper(
            file_path,
            extract_quotes=self.extract_quotes,
            parse_footnote=self.parse_footnote,
            ocr_page_text_provider=ocr_page_text_provider,
        )

    def build_candidates(
        self,
        paragraphs: Sequence[ParsedParagraph],
        footnotes: Sequence[ParsedFootnote],
        *,
        include_unquoted: bool = False,
    ) -> List[CitationCandidate]:
        candidates = build_citation_candidates(
            paragraphs,
            footnotes,
            pick_translation_text=lambda paragraph, footnote_id=None: self._pick_translation_text(
                paragraph,
                include_unquoted=include_unquoted,
                footnote_id=footnote_id,
            ),
            is_verifiable_footnote=self._is_verifiable_footnote,
        )
        for candidate in candidates:
            attach_source_graph_artifacts(candidate)
        return candidates

    def parse_footnote(self, note_id: str, text: str) -> ParsedFootnote:
        return parse_footnote_text(
            note_id,
            text,
            title_patterns=self.TITLE_PATTERNS,
            page_patterns=self.PAGE_PATTERNS,
        )

    def extract_quotes(self, text: str) -> List[str]:
        return extract_quotes(text, quote_patterns=self.QUOTE_PATTERNS)

    def search_ndl_sources(
        self,
        footnote: ParsedFootnote,
        *,
        max_results: int = 5,
        claim_text: str = "",
    ) -> List[NDLSearchMatch]:
        return self.search_sources(
            footnote,
            max_results=max_results,
            platform_names=["ndl"],
            claim_text=claim_text,
        )

    def search_sources(
        self,
        footnote: ParsedFootnote,
        *,
        max_results: int = 5,
        platform_names: Optional[Iterable[str]] = None,
        claim_text: str = "",
    ) -> List[NDLSearchMatch]:
        return self._get_source_platform_registry().search(
            footnote,
            max_results=max_results,
            platform_names=platform_names,
            claim_text=claim_text,
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
        flags.extend(parsed.get("quality_flags", []) or [])
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
                "download_dependency_missing": 50,
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
        if "no module named 'selenium'" in normalized or ("modulenotfounderror" in normalized and "selenium" in normalized):
            return "download_dependency_missing"
        if "ndl_toc_not_found" in normalized:
            return "ndl_toc_not_found"
        if "ndl_toc_empty" in normalized:
            return "ndl_toc_empty"
        if "invalid_page_range" in normalized:
            return "invalid_page_range"
        return ""

    def restricted_download_dependency_status(self) -> Dict[str, Any]:
        return dict(self._restricted_download_dependency_status())

    def _restricted_download_dependency_status(self, module: Any = None) -> Dict[str, Any]:
        effective_module = module if module is not None else self._ndl_download_module
        if effective_module is not None:
            module_class = effective_module.__class__
            if not (
                module_class.__name__ == "NDLDownloadModule"
                and module_class.__module__ == "modules.workflows.ndl_download"
            ):
                return {
                    "available": True,
                    "policy": "injected_download_module_not_prechecked",
                }
        if module is None and self._restricted_download_dependency_status_cache is not None:
            return self._restricted_download_dependency_status_cache
        if self._prefer_external_ndl_module and self._ndl_download_module is not None:
            status = {
                "available": True,
                "policy": "external_ndl_download_module_not_prechecked",
            }
            self._restricted_download_dependency_status_cache = status
            return status
        if importlib.util.find_spec("selenium") is None:
            status = {
                "available": False,
                "reason": "download_dependency_missing",
                "dependency": "selenium",
                "message": "No module named 'selenium'",
            }
            if module is None:
                self._restricted_download_dependency_status_cache = status
            return status
        status = {"available": True, "dependency": "selenium"}
        if module is None:
            self._restricted_download_dependency_status_cache = status
        return status

    def _mark_restricted_download_dependency_missing(
        self,
        candidate: CitationCandidate,
        *,
        top_match: Optional[NDLSearchMatch],
        status: Dict[str, Any],
    ) -> None:
        planned_range = candidate.artifacts.pop("downloaded_page_range", None)
        if planned_range and not candidate.artifacts.get("download_planned_page_range"):
            candidate.artifacts["download_planned_page_range"] = planned_range
        candidate.artifacts["download_dependency_check"] = dict(status)
        message = str(status.get("message") or status.get("reason") or "download_dependency_missing")
        dependency = str(status.get("dependency") or "")
        note = f"restricted_download_dependency_missing:{dependency or 'unknown'}"
        if note not in candidate.notes:
            candidate.notes.append(note)
        ndl_id = str(getattr(top_match, "ndl_id", "") or getattr(top_match, "platform_item_id", "") or "")
        self._mark_source_unavailable(
            candidate,
            reason="download_dependency_missing",
            ndl_id=ndl_id or None,
            source_id=self._match_identity(top_match) if top_match is not None else None,
            detail=message,
        )

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
        source_id = (
            getattr(match, "ndl_id", None)
            or getattr(match, "platform_item_id", None)
            or getattr(match, "url", None)
            if match is not None
            else None
        )
        for hint in raw_hints[:10]:
            if not isinstance(hint, dict):
                continue
            enriched = dict(hint)
            if source_id:
                enriched.setdefault("book_id", str(source_id))
                enriched.setdefault("pid", str(source_id))
            if match is not None:
                enriched.setdefault("source_title", getattr(match, "title", None))
                enriched.setdefault("source_url", getattr(match, "url", None))
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

    def _fulltext_hit_to_artifact(self, hit: Any) -> Dict[str, Any]:
        return {
            "query": getattr(hit, "query", "") or "",
            "snippet": getattr(hit, "snippet", "") or "",
            "pdf_page": getattr(hit, "pdf_page", None),
            "pid": getattr(hit, "pid", "") or "",
            "book_id": getattr(hit, "pid", "") or "",
            "cid": getattr(hit, "cid", "") or "",
            "content_index": getattr(hit, "content_index", None),
            "page_basis": getattr(hit, "page_basis", "dl_ndl_fulltext_content_index"),
            "search_route": "ndl_digital_target_fulltext",
        }

    def _is_diary_source(self, candidate: CitationCandidate) -> bool:
        resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
        source_graph = candidate.artifacts.get("source_graph") or {}
        if not isinstance(resolver_plan, dict):
            resolver_plan = {}
        if not isinstance(source_graph, dict):
            source_graph = {}
        return str(resolver_plan.get("source_type") or source_graph.get("source_type") or "") == "diary"

    def _is_date_query_text(self, value: Any) -> bool:
        text = unicodedata.normalize("NFKC", str(value or ""))
        return bool(
            re.search(r"(?:1[89]\d{2}|20\d{2})\s*\u5e74", text)
            or re.search(
                r"(?:\u660e\u6cbb|\u5927\u6b63|\u662d\u548c|\u5e73\u6210|\u4ee4\u548c)"
                r"\s*[0-9\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5143]+"
                r"\s*\u5e74",
                text,
            )
        )

    def _date_query_is_publication_year_only(self, candidate: CitationCandidate, value: Any) -> bool:
        publication_year = str(getattr(candidate.footnote, "year", "") or "").strip()
        if not publication_year:
            return False
        text = unicodedata.normalize("NFKC", str(value or ""))
        gregorian_years = set(re.findall(r"(1[89]\d{2}|20\d{2})\s*\u5e74", text))
        if not gregorian_years:
            return False
        has_era_year = re.search(
            r"(?:\u660e\u6cbb|\u5927\u6b63|\u662d\u548c|\u5e73\u6210|\u4ee4\u548c)"
            r"\s*[0-9\u4e00-\u9fff\u5143]+\s*\u5e74",
            text,
        )
        return not has_era_year and gregorian_years == {publication_year}

    def _japanese_number_under_100(self, value: int) -> str:
        digits = {
            1: "\u4e00",
            2: "\u4e8c",
            3: "\u4e09",
            4: "\u56db",
            5: "\u4e94",
            6: "\u516d",
            7: "\u4e03",
            8: "\u516b",
            9: "\u4e5d",
        }
        if value <= 0:
            return ""
        if value < 10:
            return digits.get(value, "")
        tens, ones = divmod(value, 10)
        if tens == 1:
            prefix = "\u5341"
        else:
            prefix = f"{digits.get(tens, '')}\u5341"
        return prefix + (digits.get(ones, "") if ones else "")

    def _gregorian_date_to_japanese_era_variants(self, value: Any) -> List[str]:
        text = unicodedata.normalize("NFKC", str(value or ""))
        variants: List[str] = []
        pattern = re.compile(
            r"(1[89]\d{2}|20\d{2})\s*\u5e74"
            r"(?:\s*(\d{1,2})\s*\u6708(?:\s*(\d{1,2})\s*\u65e5)?)?"
        )
        era_ranges = [
            ("\u660e\u6cbb", 1868, 1912),
            ("\u5927\u6b63", 1912, 1926),
            ("\u662d\u548c", 1926, 1989),
            ("\u5e73\u6210", 1989, 2019),
            ("\u4ee4\u548c", 2019, 2100),
        ]
        for match in pattern.finditer(text):
            year = int(match.group(1))
            month = match.group(2)
            day = match.group(3)
            suffix = ""
            if month:
                suffix += f"{int(month)}\u6708"
            if day:
                suffix += f"{int(day)}\u65e5"
            for era, start_year, end_year in era_ranges:
                if not (start_year <= year <= end_year):
                    continue
                era_year = year - start_year + 1
                year_forms = ["\u5143", "1"] if era_year == 1 else [str(era_year)]
                kanji_year = self._japanese_number_under_100(era_year)
                if kanji_year and kanji_year not in year_forms:
                    year_forms.append(kanji_year)
                for year_form in year_forms:
                    variants.append(f"{era}{year_form}\u5e74{suffix}")
        return list(dict.fromkeys(variants))

    def _diary_date_queries(self, candidate: CitationCandidate) -> List[str]:
        if not self._is_diary_source(candidate):
            return []
        resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
        source_graph = candidate.artifacts.get("source_graph") or {}
        if not isinstance(resolver_plan, dict):
            resolver_plan = {}
        if not isinstance(source_graph, dict):
            source_graph = {}
        query_buckets = resolver_plan.get("query_buckets") or {}
        if not isinstance(query_buckets, dict):
            query_buckets = {}
        roots: List[str] = []

        def add(value: Any) -> None:
            cleaned = unicodedata.normalize("NFKC", str(value or "")).strip()
            if (
                cleaned
                and self._is_date_query_text(cleaned)
                and not self._date_query_is_publication_year_only(candidate, cleaned)
                and cleaned not in roots
            ):
                roots.append(cleaned)

        for value in resolver_plan.get("dates") or []:
            add(value)
        for value in source_graph.get("dates") or []:
            add(value)
        for value in query_buckets.get("date") or []:
            add(value)
        authoritative_roots = list(roots)
        for value in resolver_plan.get("target_pid_queries") or []:
            cleaned = unicodedata.normalize("NFKC", str(value or "")).strip()
            if not cleaned or not self._is_date_query_text(cleaned):
                continue
            if authoritative_roots and not any(root in cleaned or cleaned in root for root in authoritative_roots):
                continue
            add(cleaned)
        variants: List[str] = []
        for value in roots:
            if value not in variants:
                variants.append(value)
            for variant in self._gregorian_date_to_japanese_era_variants(value):
                if variant not in variants:
                    variants.append(variant)
        return variants

    def _diary_date_hint_match_scope(
        self,
        candidate: CitationCandidate,
        hint: Dict[str, Any],
    ) -> str:
        date_queries = [normalize_match_text(query) for query in self._diary_date_queries(candidate)]
        date_queries = [query for query in date_queries if query]
        if not date_queries:
            return ""
        query = normalize_match_text(str(hint.get("query") or hint.get("keyword") or ""))
        evidence_text = normalize_match_text(
            " ".join(str(hint.get(key) or "") for key in ("snippet", "expanded_context"))
        )
        query_match = any(date_query in query or query in date_query for date_query in date_queries if query)
        evidence_match = any(date_query in evidence_text for date_query in date_queries)
        if query_match and evidence_match:
            return "query_and_snippet"
        if evidence_match:
            return "snippet"
        if query_match:
            return "query_only"
        return ""

    def _diary_claim_facet_rules(self) -> List[Dict[str, Any]]:
        config = _load_resolver_config().get("hara_takashi_diary") or {}
        rules = config.get("claim_facets") if isinstance(config, dict) else None
        if isinstance(rules, list) and rules:
            return [rule for rule in rules if isinstance(rule, dict) and str(rule.get("id") or "").strip()]
        return [dict(rule) for rule in self.DEFAULT_DIARY_CLAIM_FACET_RULES]

    def _diary_claim_facet_roles(self) -> Dict[str, str]:
        roles: Dict[str, str] = {}
        for rule in self._diary_claim_facet_rules():
            bucket = str(rule.get("id") or "").strip()
            if bucket:
                roles[bucket] = str(rule.get("role") or "theme")
        return roles

    def _diary_claim_term_buckets(self, candidate: CitationCandidate) -> Dict[str, List[str]]:
        if not self._is_diary_source(candidate):
            return {}
        claim_text = _clean_text(candidate.translation_text)
        trigger_scope = "translation_text"
        if not claim_text:
            claim_text = _clean_text(candidate_source_claim_context(candidate))
            trigger_scope = "candidate_source_claim_context"
        candidate.artifacts["diary_claim_facet_trigger_scope"] = trigger_scope
        trigger = unicodedata.normalize("NFKC", claim_text)
        normalized_trigger = normalize_match_text(trigger)
        buckets: Dict[str, List[str]] = {}

        def add(bucket: str, values: Sequence[str]) -> None:
            items = buckets.setdefault(bucket, [])
            for value in values:
                value = str(value or "").strip()
                if value and value not in items:
                    items.append(value)

        def triggered(rule: Dict[str, Any]) -> bool:
            patterns = rule.get("trigger_patterns") or []
            if isinstance(patterns, str):
                patterns = [patterns]
            for pattern in patterns if isinstance(patterns, list) else []:
                try:
                    if re.search(str(pattern), trigger, re.IGNORECASE):
                        return True
                except re.error:
                    continue
            terms = rule.get("trigger_terms") or []
            if isinstance(terms, str):
                terms = [terms]
            for term in terms if isinstance(terms, list) else []:
                normalized_term = normalize_match_text(str(term or ""))
                if normalized_term and normalized_term in normalized_trigger:
                    return True
            return False

        for rule in self._diary_claim_facet_rules():
            bucket = str(rule.get("id") or "").strip()
            terms = rule.get("terms") or []
            if isinstance(terms, str):
                terms = [terms]
            if bucket and isinstance(terms, list) and triggered(rule):
                add(bucket, [str(term) for term in terms])
        return {bucket: values for bucket, values in buckets.items() if values}

    def _diary_claim_fulltext_queries(self, candidate: CitationCandidate) -> List[str]:
        buckets = self._diary_claim_term_buckets(candidate)
        if not buckets:
            return []
        dates = self._diary_date_queries(candidate)
        era_dates = [
            date
            for date in dates
            if re.search(r"(?:\u660e\u6cbb|\u5927\u6b63|\u662d\u548c|\u5e73\u6210|\u4ee4\u548c)", date)
        ]
        date_anchors = [date for date in dates if not self._is_year_only_fulltext_term(date)][:2] or era_dates[:2] or dates[:2]
        roles = self._diary_claim_facet_roles()
        anchor_terms: List[str] = []
        secondary_terms: List[str] = []
        for bucket, terms in buckets.items():
            role = roles.get(bucket, "theme")
            target = anchor_terms if role in {"anchor", "actor", "country", "person", "place", "institution"} else secondary_terms
            for term in terms[:3]:
                if term and term not in target:
                    target.append(term)
        if not anchor_terms:
            for terms in buckets.values():
                for term in terms[:2]:
                    if term and term not in anchor_terms:
                        anchor_terms.append(term)
        if not secondary_terms:
            for bucket, terms in buckets.items():
                for term in terms[:2]:
                    if term and term not in anchor_terms and term not in secondary_terms:
                        secondary_terms.append(term)
        queries: List[str] = []

        def add(value: str) -> None:
            cleaned = " ".join(str(value or "").split())
            if cleaned and cleaned not in queries:
                queries.append(cleaned)

        for term in secondary_terms[:6]:
            for date in date_anchors:
                for anchor in anchor_terms[:2]:
                    add(f"{date} {anchor} {term}")
        if not secondary_terms:
            for date in date_anchors:
                for anchor in anchor_terms[:4]:
                    add(f"{date} {anchor}")
        for anchor in anchor_terms[:3]:
            economy_terms = buckets.get("economy") or []
            future_terms = buckets.get("future_influence") or []
            vitality_terms = buckets.get("vitality") or []
            for economy in economy_terms[:2]:
                for future in future_terms[:2]:
                    add(f"{anchor} {economy} {future}")
            for vitality in vitality_terms[:2]:
                for future in future_terms[:2]:
                    add(f"{anchor} {vitality} {future}")
        if len(buckets) >= 2:
            all_terms = [term for terms in buckets.values() for term in terms[:2]]
            for first in all_terms[:4]:
                for second in all_terms[:6]:
                    if first != second:
                        add(f"{first} {second}")
        return queries[:18]

    def _diary_claim_facet_packet(self, candidate: CitationCandidate, text: Any) -> Dict[str, Any]:
        buckets = self._diary_claim_term_buckets(candidate)
        if not buckets:
            return {}
        normalized_text = normalize_match_text(str(text or ""))
        facet_hits: Dict[str, List[str]] = {}
        for bucket, terms in buckets.items():
            hits = []
            for term in terms:
                normalized_term = normalize_match_text(term)
                if normalized_term and normalized_term in normalized_text:
                    hits.append(term)
            if hits:
                facet_hits[bucket] = hits[:4]
        if not facet_hits:
            return {}
        required_facets = set(buckets)
        covered = set(facet_hits)
        roles = self._diary_claim_facet_roles()
        bonus = min(4.0, len(covered) * 0.9)
        if {"us", "economy", "future_influence"}.issubset(covered):
            bonus += 1.5
        elif {"us", "future_influence"}.issubset(covered) or {"us", "economy"}.issubset(covered):
            bonus += 0.75
        else:
            anchor_covered = any(
                bucket in covered
                and roles.get(bucket, "theme") in {"anchor", "actor", "country", "person", "place", "institution"}
                for bucket in buckets
            )
            covered_theme_count = sum(
                1
                for bucket in covered
                if roles.get(bucket, "theme") not in {"anchor", "actor", "country", "person", "place", "institution"}
            )
            if anchor_covered and covered_theme_count >= 2:
                bonus += 1.25
            elif anchor_covered and covered_theme_count >= 1:
                bonus += 0.65
            elif len(covered) >= 2:
                bonus += 0.35
        return {
            "facet_hits": facet_hits,
            "covered_facets": sorted(covered),
            "missing_facets": sorted(required_facets - covered),
            "facet_roles": {bucket: roles.get(bucket, "theme") for bucket in sorted(buckets)},
            "score_bonus": min(5.0, bonus),
        }

    def _record_diary_date_lookup_diagnostic(
        self,
        candidate: CitationCandidate,
        *,
        ndl_id: str,
        hit_artifacts: Sequence[Dict[str, Any]],
    ) -> None:
        resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
        source_graph = candidate.artifacts.get("source_graph") or {}
        if not isinstance(resolver_plan, dict):
            resolver_plan = {}
        if not isinstance(source_graph, dict):
            source_graph = {}
        source_type = str(resolver_plan.get("source_type") or source_graph.get("source_type") or "")
        if source_type != "diary":
            return

        target_queries = [str(query) for query in (resolver_plan.get("target_pid_queries") or []) if str(query or "")]
        date_queries = self._diary_date_queries(candidate)
        title_queries = [
            str(query)
            for query in [
                getattr(candidate.footnote, "title", ""),
                getattr(candidate.footnote, "host_title", ""),
                getattr(candidate.footnote, "ndl_keyword", ""),
                *target_queries,
            ]
            if str(query or "") and not self._is_date_query_text(str(query))
        ]
        title_queries = list(dict.fromkeys(title_queries))
        date_hit_count = sum(1 for hint in hit_artifacts if self._diary_date_hint_match_scope(candidate, hint))
        title_hit_count = sum(1 for hint in hit_artifacts if str(hint.get("query") or "") in title_queries)
        if date_hit_count > 0 or title_hit_count <= 0:
            candidate.artifacts.pop("diary_date_lookup_diagnostic", None)
            return

        page_numbers: List[int] = []
        for page in candidate.footnote.page_numbers or []:
            try:
                page_number = int(page)
            except (TypeError, ValueError):
                continue
            if page_number > 0:
                page_numbers.append(page_number)
        page_window = 2
        small_page_window: Dict[str, Any] = {}
        if page_numbers:
            small_page_window = {
                "cited_book_pages": page_numbers,
                "start_page": max(1, min(page_numbers) - page_window),
                "end_page": max(page_numbers) + page_window,
                "page_window": page_window,
            }
        known_pids = [
            str(pid)
            for pid in [
                *(resolver_plan.get("known_pid_candidates") or []),
                *(source_graph.get("known_pid_candidates") or []),
            ]
            if str(pid or "")
        ]
        diagnostic = {
            "source_type": "diary",
            "ndl_id": ndl_id,
            "known_pid_candidates": list(dict.fromkeys(known_pids)),
            "date_queries": date_queries,
            "date_hit_count": date_hit_count,
            "title_queries": title_queries,
            "title_hit_count": title_hit_count,
            "recommended_action": "toc_index_then_small_page_window_ocr",
            "small_page_window": small_page_window,
            "evidence_level": "diagnostic_until_ocr_llm_review",
        }
        candidate.artifacts["diary_date_lookup_diagnostic"] = diagnostic
        note = "diary_date_lookup_needs_index_or_page_window_ocr"
        if note not in candidate.notes:
            candidate.notes.append(note)

    def _record_contained_document_lookup_diagnostic(
        self,
        candidate: CitationCandidate,
        *,
        ndl_id: str,
        hit_artifacts: Sequence[Dict[str, Any]],
    ) -> None:
        resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
        source_graph = candidate.artifacts.get("source_graph") or {}
        if not isinstance(resolver_plan, dict):
            resolver_plan = {}
        if not isinstance(source_graph, dict):
            source_graph = {}
        source_type = str(resolver_plan.get("source_type") or source_graph.get("source_type") or "")
        if source_type != "contained_document":
            return
        host_title = str(
            source_graph.get("host_title")
            or resolver_plan.get("host_title")
            or getattr(candidate.footnote, "host_title", "")
            or ""
        ).strip()
        contained_title = str(
            source_graph.get("contained_title")
            or resolver_plan.get("contained_title")
            or getattr(candidate.footnote, "contained_title", "")
            or getattr(candidate.footnote, "title", "")
            or ""
        ).strip()
        title_queries = [
            str(query)
            for query in [
                contained_title,
                getattr(candidate.footnote, "title", ""),
                *(resolver_plan.get("target_pid_queries") or []),
            ]
            if str(query or "")
        ]
        title_queries = list(dict.fromkeys(title_queries))
        title_hit_count = sum(1 for hint in hit_artifacts if str(hint.get("query") or "") in title_queries)
        known_pids = [
            str(pid)
            for pid in [
                *(resolver_plan.get("known_pid_candidates") or []),
                *(source_graph.get("known_pid_candidates") or []),
            ]
            if str(pid or "")
        ]
        if not known_pids and title_hit_count <= 0:
            candidate.artifacts.pop("contained_document_lookup_diagnostic", None)
            return
        diagnostic = {
            "source_type": "contained_document",
            "ndl_id": ndl_id,
            "known_pid_candidates": list(dict.fromkeys(known_pids)),
            "host_title": host_title,
            "host_missing": not bool(host_title),
            "contained_title": contained_title,
            "title_queries": title_queries,
            "title_hit_count": title_hit_count,
            "recommended_action": "known_document_pid_first_then_host_fallback",
            "evidence_level": "diagnostic_until_ocr_llm_review",
        }
        candidate.artifacts["contained_document_lookup_diagnostic"] = diagnostic
        note = "contained_document_known_pid_first_then_host_fallback"
        if note not in candidate.notes:
            candidate.notes.append(note)

    def _source_claim_context_for_queries(self, candidate: CitationCandidate) -> str:
        return candidate_source_claim_context(candidate)

    def _claim_fulltext_queries(self, candidate: CitationCandidate) -> List[str]:
        queries: List[str] = []

        def add(value: Any) -> None:
            cleaned = _clean_text(str(value or ""))
            if cleaned and cleaned not in queries:
                queries.append(cleaned)

        citation_unit = candidate.artifacts.get("citation_unit") or {}
        if isinstance(citation_unit, dict):
            for claim in citation_unit.get("claim_candidates") or []:
                add(claim)
            add(citation_unit.get("text"))
        add(candidate.translation_text)

        source_text = " ".join(queries)
        cross_lingual_variants = (
            (
                ("约翰·海伊", "約翰", "海伊", "John Hay", "Hay"),
                (
                    "ジョン・ヘイ",
                    "ヘイ",
                    "ヘイ氏",
                    "ヘイ國務卿",
                    "ヘイ国務卿",
                    "ヘイ國務長官",
                    "ヘイ国務長官",
                    "米國國務長官",
                    "米国国務長官",
                    "米國務卿",
                    "米国務卿",
                    "合衆國國務長官",
                ),
            ),
            (
                ("门户开放", "門戸開放", "門戶開放", "open door", "Open Door"),
                (
                    "門戶開放",
                    "門戸開放",
                    "對支門戶開放",
                    "対支門戸開放",
                    "門戶開放主義",
                    "門戸開放主義",
                    "支那門戶開放",
                    "支那門戸開放",
                    "支那ニ於ケル商業上機會均等及門戸開放",
                    "商業上機會均等及門戸開放",
                ),
            ),
            (
                ("机会均等", "機會均等", "機会均等", "equal opportunity"),
                (
                    "機會均等",
                    "機会均等",
                    "商業上機會均等",
                    "商業上機会均等",
                    "商業上機會均等及門戸開放",
                    "商業上機会均等及門戸開放",
                ),
            ),
            (
                ("赞同", "同意", "回答", "照会", "各国", "日本的赞同"),
                (
                    "米國照會",
                    "米国照会",
                    "米國政府照會",
                    "米国政府照会",
                    "米國國務長官照會",
                    "米国国務長官照会",
                    "帝國政府回答",
                    "帝国政府回答",
                    "帝國政府ノ回答",
                    "帝国政府ノ回答",
                    "各國回答",
                    "各国回答",
                    "同意",
                    "賛成",
                    "贊成",
                ),
            ),
            (
                ("赤道以北", "德属太平洋", "德屬太平洋", "太平洋群岛", "太平洋群島", "委任统治", "委任統治", "托管", "既定目标"),
                (
                    "赤道以北",
                    "獨領南洋",
                    "独領南洋",
                    "南洋群島",
                    "太平洋群島",
                    "委任統治",
                    "委任統治ノ形式",
                    "C式委任統治",
                    "C類委任統治",
                    "會議ノ決定",
                    "会議ノ決定",
                    "決定ヲ受諾",
                    "決定ヲ講和會議",
                    "講和會議ニ於テ",
                ),
            ),
            (
                ("10:10:6", "１０∶１０∶６", "十比十比六", "十对六", "十對六", "十対六", "主力舰比例", "主力艦比率"),
                (
                    "米国案ノ十対六",
                    "米國案ノ十對六",
                    "十対六",
                    "十對六",
                    "十・十・六",
                    "十、十、六",
                    "主力艦比率",
                    "海軍勢力比",
                    "勢力比",
                    "六割",
                ),
            ),
            (
                (
                    "桂太郎",
                    "桂 塔夫脱",
                    "桂・塔夫脱",
                    "塔夫脱",
                    "塔夫脫",
                    "哈里曼",
                    "南满铁路",
                    "南滿鐵路",
                    "南满洲铁路",
                    "南滿洲鐵路",
                    "共同管理",
                ),
                (
                    "桂太郎",
                    "タフト",
                    "タフト陸軍長官",
                    "桂・タフト",
                    "桂・タフト協定",
                    "桂・タフト覚書",
                    "桂タフト協定",
                    "ハリマン",
                    "満鉄",
                    "南満洲鉄道",
                    "南滿洲鐵道",
                    "南満洲鐵道",
                    "南滿洲鉄道",
                    "南満鐵道",
                    "南満鉄道",
                    "共同經營",
                    "共同経営",
                    "共同管理",
                    "豫備協定",
                    "予備協定",
                ),
            ),
            (
                (
                    "伊势神宫大麻",
                    "伊勢神宮大麻",
                    "神宫大麻",
                    "神宮大麻",
                    "不设神棚",
                    "不設神棚",
                    "神棚",
                    "土真宗",
                ),
                (
                    "伊勢皇大神宮大麻",
                    "皇大神宮大麻",
                    "神宮大麻",
                    "神宮大麻等",
                    "神棚ヲ不設",
                    "従前宗門ニ寄、神棚ヲ不設",
                    "宗門ニ寄、神棚ヲ不設",
                ),
            ),
            (
                (
                    "流言",
                    "化为蝴蝶",
                    "化為蝴蝶",
                    "蝴蝶",
                    "时疫",
                    "時疫",
                    "焚毁",
                    "焚毀",
                    "冲走",
                    "沖走",
                ),
                (
                    "伊勢皇太神ノ大麻",
                    "大麻ヲ水火ニ投ズ",
                    "水火ニ投ズル",
                    "玉串ヲ焼捨",
                    "焼捨",
                    "河流ニ投ジ",
                    "大麻ノ神ノ字ガ蝶",
                    "蝶ニ化スル",
                    "時疫",
                    "死絶",
                    "妄伝浮説",
                    "妄傳浮説",
                ),
            ),
            (
                (
                    "政权与教权",
                    "政權與教權",
                    "政权和教权",
                    "政權和教權",
                    "政权",
                    "政權",
                    "教权",
                    "教權",
                    "相互界定",
                    "界定",
                    "疆域",
                    "宪法所裁定",
                    "憲法所裁定",
                    "裁定之准则",
                    "裁定之準則",
                ),
                (
                    "政權ト教權",
                    "政権ト教権",
                    "政權ト教權ト相分界",
                    "政権ト教権ト相分界",
                    "相分界スルノ域",
                    "憲法ノ裁定スル所",
                    "憲法ノ認定スル所",
                    "裁定スル所",
                    "認定スル所",
                    "教權",
                    "教権",
                    "政權",
                    "政権",
                ),
            ),
            (
                (
                    "平将门",
                    "平將門",
                    "平将門",
                    "神田神社",
                    "神田明神",
                    "神田祭",
                    "摄社",
                    "攝社",
                    "祭神",
                    "灵位",
                    "靈位",
                ),
                (
                    "平将門",
                    "神田神社",
                    "神田明神",
                    "神田祭",
                    "祭神",
                    "祭神ノ座",
                    "攝社",
                    "摂社",
                    "朝廷ニ對スル反逆者",
                    "朝廷に対する反逆者",
                ),
            ),
        )
        for triggers, variants in cross_lingual_variants:
            if any(trigger and trigger in source_text for trigger in triggers):
                for variant in variants:
                    add(variant)

        shared_terms = (
            "政教一致",
            "治国安民",
            "門戸開放",
            "门户开放",
            "機會均等",
            "机会均等",
            "正理",
            "自由",
            "良心",
        )
        source_text = " ".join(queries)
        for term in shared_terms:
            if term in source_text:
                add(term)

        conversion_pairs = (
            ("门", "門"),
            ("户", "戸"),
            ("戶", "戸"),
            ("开", "開"),
            ("机", "機"),
            ("会", "會"),
            ("国", "國"),
            ("张", "張"),
            ("之", "ノ"),
            ("和", "ト"),
        )
        snapshot = list(queries)
        for query in snapshot:
            converted = query
            for old, new in conversion_pairs:
                converted = converted.replace(old, new)
            add(converted)
            add(converted.replace("伸張", "伸長"))
            add(converted.replace("良心", "本心"))
            add(converted.replace("伸張", "伸長").replace("良心", "本心"))
            add(converted.replace("治國安民", "民ヲ安ズル"))

        phrase_candidates: List[str] = []
        for query in list(queries):
            for chunk in re.findall(r"[\u3400-\u9fffぁ-んァ-ンー]{2,18}", query):
                if len(chunk) >= 4 or chunk in {"正理", "自由", "良心", "本心"}:
                    phrase_candidates.append(chunk)
        for phrase in phrase_candidates:
            add(phrase)
        source_query_plan = build_source_query_plan(
            candidate.footnote,
            claim_text=self._source_claim_context_for_queries(candidate),
        )
        candidate.artifacts["source_query_plan"] = source_query_plan.to_dict()
        for bucket_name in (
            "contained_bucket",
            "date_bucket",
            "person_bucket",
            "policy_bucket",
            "special_term_bucket",
        ):
            for term in getattr(source_query_plan, bucket_name, []):
                add(term)
        for query in source_query_plan.global_fulltext_queries(max_queries=8):
            add(query)
        return queries[:50]

    def _apply_fulltext_only_review_status(self, candidate: CitationCandidate) -> None:
        review = candidate.artifacts.get("llm_review")
        if not isinstance(review, dict) or not review:
            return
        decision = str(review.get("decision") or "uncertain")
        reason = str(review.get("reason") or "")
        if review.get("confidence") is not None:
            try:
                candidate.confidence = float(review.get("confidence"))
            except (TypeError, ValueError):
                pass
        formal_review_failed_with_heuristic = bool(
            review.get("llm_review_failed") and review.get("llm_review_fallback_heuristic")
        )
        if decision == "direct_support" and formal_review_failed_with_heuristic:
            candidate.verification_status = "fulltext_only_partial_support"
            candidate.support_status = "fulltext_only_partial_support"
            candidate.support_reason = (
                reason
                or "Heuristic review found possible direct support, but formal LLM review failed; not promoted to direct support."
            )
            candidate.artifacts["formal_review_failed_direct_downgraded"] = {
                "provider": review.get("provider") or "",
                "model": review.get("model") or "",
                "llm_error": review.get("llm_error") or "",
            }
            note = "formal_review_failed_heuristic_direct_not_promoted"
            if note not in candidate.notes:
                candidate.notes.append(note)
            return
        if decision == "direct_support":
            candidate.verification_status = "fulltext_only_direct_support"
            candidate.support_status = "fulltext_only_direct_support"
            candidate.support_reason = reason or "Final review judged the expanded NDL fulltext context as direct support."
        elif decision == "partial_support":
            candidate.verification_status = "fulltext_only_partial_support"
            candidate.support_status = "fulltext_only_partial_support"
            candidate.support_reason = reason or "Final review judged the expanded NDL fulltext context as partial support."
        elif decision == "not_supported":
            candidate.verification_status = "fulltext_only_not_supported"
            candidate.support_status = "fulltext_only_not_supported"
            candidate.support_reason = reason or "Final review judged the expanded NDL fulltext context as not supporting the claim."
            candidate.artifacts.setdefault(
                "candidate_rotation_after_not_supported",
                {
                    "attempted": False,
                    "reason": "not_supported_review_recorded_before_alternate_context_rotation",
                },
            )
        elif decision == "uncertain":
            candidate.support_reason = reason or candidate.support_reason

    def _try_alternate_fulltext_context_after_not_supported(
        self,
        candidate: CitationCandidate,
        *,
        used_hint: Optional[Dict[str, Any]] = None,
        preferred_pid: str = "",
    ) -> bool:
        review = candidate.artifacts.get("llm_review")
        if not isinstance(review, dict) or review.get("decision") != "not_supported":
            return False
        if not (self._prefer_ollama_review or self._review_llm_client is not None):
            return False
        used_key = None
        if isinstance(used_hint, dict):
            used_key = (
                used_hint.get("pid") or used_hint.get("book_id"),
                used_hint.get("pdf_page"),
                used_hint.get("snippet"),
            )
        attempts: List[Dict[str, Any]] = []
        candidate.artifacts["candidate_rotation_after_not_supported"] = {
            "attempted": True,
            "attempts": attempts,
        }
        for hint in self._ordered_fulltext_hints_for_candidate(candidate, preferred_pid=preferred_pid):
            hint_key = (hint.get("pid") or hint.get("book_id"), hint.get("pdf_page"), hint.get("snippet"))
            if used_key is not None and hint_key == used_key:
                continue
            if not self._hint_is_specific_fulltext_evidence(candidate, hint):
                continue
            if not hint.get("expanded_context"):
                self._expand_first_fulltext_hint(candidate, preferred_pid=str(hint.get("pid") or hint.get("book_id") or preferred_pid))
            context_text = str(hint.get("expanded_context") or "")
            if not context_text:
                attempts.append({"pid": hint_key[0], "pdf_page": hint_key[1], "status": "no_expanded_context"})
                continue
            candidate.matched_japanese = context_text
            try:
                candidate.matched_page = int(hint.get("pdf_page"))
            except (TypeError, ValueError):
                candidate.matched_page = None
            attempts.append({"pid": hint_key[0], "pdf_page": hint_key[1], "status": "reviewed"})
            self._review_precise_alignment(candidate)
            self._apply_fulltext_only_review_status(candidate)
            next_review = candidate.artifacts.get("llm_review")
            if not isinstance(next_review, dict) or next_review.get("decision") != "not_supported":
                candidate.artifacts["candidate_rotation_after_not_supported"]["resolved"] = True
                candidate.notes.append("candidate_rotation_after_not_supported_resolved")
                return True
        candidate.artifacts["candidate_rotation_after_not_supported"]["resolved"] = False
        candidate.notes.append("candidate_rotation_after_not_supported_exhausted")
        return False

    def _is_year_only_fulltext_term(self, value: Any) -> bool:
        term = normalize_match_text(str(value or ""))
        return bool(re.fullmatch(r"(?:1[89]\d{2}|20\d{2})年?", term))

    def _is_bibliographic_locator_fulltext_term(self, candidate: CitationCandidate, value: Any) -> bool:
        term = normalize_match_text(str(value or ""))
        if not term:
            return False
        if self._is_year_only_fulltext_term(term):
            return True
        title_like_terms = [
            normalize_match_text(item)
            for item in [
                candidate.footnote.title,
                candidate.footnote.host_title,
                candidate.footnote.ndl_keyword,
            ]
            if item
        ]
        has_title = any(title and len(title) >= 3 and title in term for title in title_like_terms)
        if not has_title:
            return False
        has_full_date = bool(
            re.search(r"(?:1[89]\d{2}|20\d{2})年\d{1,2}月\d{1,2}日", term)
            or re.search(r"(?:明治|大正|昭和|平成|令和)[0-9一二三四五六七八九十百元]+年\d{1,2}月\d{1,2}日", term)
        )
        has_year_locator = bool(re.search(r"(?:1[89]\d{2}|20\d{2})年?", term)) and not has_full_date
        has_volume_locator = bool(re.search(r"第?[0-9一二三四五六七八九十百]+(?:巻|卷|冊|册)|(?:上巻|下巻|上卷|下卷)", term))
        return has_year_locator or has_volume_locator

    def _fulltext_specific_terms(self, candidate: CitationCandidate) -> List[str]:
        terms: List[str] = []
        title_like_terms = [
            normalize_match_text(value)
            for value in [
                candidate.footnote.title,
                candidate.footnote.host_title,
                candidate.footnote.ndl_keyword,
            ]
            if value
        ]

        def add(value: Any) -> None:
            normalized = normalize_match_text(str(value or ""))
            if normalized and normalized not in terms:
                terms.append(normalized)

        add(getattr(candidate.footnote, "contained_title", "") or "")
        resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
        if isinstance(resolver_plan, dict):
            for query in resolver_plan.get("target_pid_queries") or []:
                normalized_query = normalize_match_text(str(query or ""))
                if self._is_year_only_fulltext_term(query) or self._is_bibliographic_locator_fulltext_term(candidate, query):
                    continue
                if normalized_query and normalized_query in title_like_terms:
                    continue
                add(query)
            query_buckets = resolver_plan.get("query_buckets") or {}
            if isinstance(query_buckets, dict):
                for bucket_name, bucket_values in query_buckets.items():
                    bucket = str(bucket_name or "")
                    if bucket in {"title", "host", "volume", "blocked_standalone"}:
                        continue
                    if isinstance(bucket_values, list):
                        for value in bucket_values:
                            if bucket == "date" and self._is_year_only_fulltext_term(value):
                                continue
                            add(value)
        for query in self._claim_fulltext_queries(candidate):
            if self._is_bibliographic_locator_fulltext_term(candidate, query):
                continue
            add(query)
        return [term for term in terms if len(term) >= 2]

    def _hint_is_specific_fulltext_evidence(
        self,
        candidate: CitationCandidate,
        hint: Dict[str, Any],
    ) -> bool:
        query = normalize_match_text(str(hint.get("query") or ""))
        snippet = normalize_match_text(str(hint.get("snippet") or ""))
        if not query and not snippet:
            return False
        title_like_terms = [
            normalize_match_text(value)
            for value in [
                candidate.footnote.title,
                candidate.footnote.host_title,
                candidate.footnote.ndl_keyword,
            ]
            if value
        ]
        if query and query in title_like_terms and not candidate.footnote.contained_title:
            return False
        for term in self._fulltext_specific_terms(candidate):
            if term and (term in query or term in snippet):
                return True
        return False

    def _hint_has_claim_snippet_evidence(
        self,
        candidate: CitationCandidate,
        hint: Dict[str, Any],
    ) -> bool:
        raw_text = " ".join(
            str(hint.get(key) or "")
            for key in ("snippet", "expanded_context")
        )
        if any(
            marker in raw_text
            for marker in (
                "政教一致",
                "民ヲ安ズル",
                "民ヲ安",
                "治メ民",
                "門戶開放",
                "門戸開放",
                "本心ノ自由",
                "良心ノ自由",
                "正理ノ伸",
            )
        ):
            return True
        text = normalize_match_text(raw_text)
        if not text:
            return False
        generic_claim_terms = self._generic_fulltext_claim_terms()
        title_like_terms = [
            normalize_match_text(value)
            for value in [
                candidate.footnote.title,
                candidate.footnote.host_title,
                candidate.footnote.contained_title,
                candidate.footnote.ndl_keyword,
                "日本外交文書",
                "日本近代思想大系",
            ]
            if value
        ]
        broad_collection_terms = {
            normalize_match_text(value)
            for value in [
                "講和會議",
                "講和会議",
                "巴里講和會議",
                "巴里講和会議",
                "巴里講和会議経過概要",
                "巴里講和會議經過概要",
                "ワシントン会議",
                "華盛頓会議",
                "大正期追補",
                "追補 [1]",
            ]
        }
        hint_query = normalize_match_text(str(hint.get("query") or ""))
        for query in self._claim_fulltext_queries(candidate):
            term = normalize_match_text(query)
            if len(term) < 4:
                continue
            if term in generic_claim_terms:
                continue
            if term in broad_collection_terms:
                continue
            if any(
                title_term
                and len(title_term) >= 4
                and (term == title_term or term in title_term or title_term in term)
                for title_term in title_like_terms
            ):
                continue
            if hint_query and term == hint_query:
                return True
            if term in text:
                return True
        return False

    def _generic_fulltext_claim_terms(self) -> set[str]:
        return {
            normalize_match_text(value)
            for value in [
                "会議",
                "會議",
                "会議ノ決定",
                "會議ノ決定",
                "会議の決定",
                "會議の決定",
                "会議決定",
                "會議決定",
                "会议决定",
                "決定",
                "决定",
                "方針",
                "政策",
                "提案",
                "提議",
            ]
        }

    def _fulltext_hint_specificity_score(self, candidate: CitationCandidate, hint: Dict[str, Any]) -> float:
        query = normalize_match_text(str(hint.get("query") or ""))
        snippet = normalize_match_text(str(hint.get("snippet") or ""))
        text = query + snippet
        score = 0.0
        if self._hint_has_claim_snippet_evidence(candidate, hint):
            score += 4.0
        for term in self._fulltext_specific_terms(candidate):
            if term and term in text:
                score += min(2.0, max(0.5, len(term) / 6.0))
        diary_packet = self._diary_claim_facet_packet(
            candidate,
            " ".join(str(hint.get(key) or "") for key in ("query", "snippet", "expanded_context")),
        )
        if diary_packet:
            score += min(3.0, float(diary_packet.get("score_bonus") or 0))
        score += min(1.0, len(query) / 18.0)
        if hint.get("pdf_page"):
            score += 0.1
        return score

    def _ordered_fulltext_hints_for_candidate(
        self,
        candidate: CitationCandidate,
        *,
        preferred_pid: str = "",
    ) -> List[Dict[str, Any]]:
        hints = candidate.artifacts.get("ndl_fulltext_hints")
        if not isinstance(hints, list):
            return []
        typed_hints = []
        for hint in hints:
            if not isinstance(hint, dict):
                continue
            if preferred_pid:
                hint_source = str(hint.get("book_id") or hint.get("pid") or "")
                if hint_source and hint_source != preferred_pid:
                    continue
            typed_hints.append(hint)
        lead_rank = {
            "body_candidate": 0,
            "short_or_unexpanded": 1,
            "title_or_series_only": 2,
            "toc_or_index": 3,
            "wrong_pid": 4,
        }
        return sorted(
            typed_hints,
            key=lambda hint: (
                lead_rank.get(self._fulltext_hint_lead_category(candidate, hint), 5),
                not self._hint_has_claim_snippet_evidence(candidate, hint),
                not self._hint_is_specific_fulltext_evidence(candidate, hint),
                -self._fulltext_hint_specificity_score(candidate, hint),
                not bool(hint.get("expanded_context")),
                not bool(hint.get("pdf_page")),
            ),
        )

    def _clean_fulltext_context_text(self, text: Any) -> str:
        cleaned = str(text or "").replace("\r", "\n")
        cleaned = re.sub(r"[ \t　]+", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        cleaned = re.sub(r"(?m)^\s+", "", cleaned)
        return cleaned.strip()

    def _fulltext_core_action_terms(self, candidate: CitationCandidate) -> List[str]:
        blob = " ".join(
            str(value or "")
            for value in [
                candidate.translation_text,
                candidate.paragraph_text,
                candidate.footnote.text,
                candidate.footnote.title,
                candidate.footnote.host_title,
                candidate.footnote.contained_title,
                candidate.footnote.ndl_keyword,
            ]
        )
        citation_unit = candidate.artifacts.get("citation_unit") or {}
        claim_focus_parts: List[str] = [str(candidate.translation_text or "")]
        if isinstance(citation_unit, dict):
            claim_focus_parts.append(str(citation_unit.get("text") or ""))
            claim_focus_parts.extend(str(item or "") for item in citation_unit.get("claim_candidates") or [])
        claim_focus = " ".join(claim_focus_parts)
        terms: List[str] = []

        def add(value: Any) -> None:
            cleaned = str(value or "").strip()
            if cleaned and cleaned not in terms:
                terms.append(cleaned)

        if "大麻" in blob:
            add("神宮大麻")
            taima_acceptance_markers = (
                "神棚",
                "不设",
                "不設",
                "不接受",
                "不受",
                "土真宗",
                "宗門",
                "伊势神宫",
                "伊勢神宮",
            )
            taima_rumor_markers = (
                "流言",
                "蝴蝶",
                "蝶",
                "时疫",
                "時疫",
                "焚毁",
                "焚毀",
                "冲走",
                "沖走",
                "水火",
                "投",
                "焼",
                "烧",
                "流",
            )
            if any(marker in claim_focus for marker in taima_acceptance_markers):
                for value in [
                    "皇大神宮",
                    "神棚",
                    "宗門",
                    "神宮大麻等",
                    "不受者",
                ]:
                    add(value)
            if any(marker in claim_focus for marker in taima_rumor_markers):
                for value in [
                    "流言",
                    "妄伝",
                    "妄傳",
                    "妄説",
                    "水火",
                    "投ズ",
                    "投じ",
                    "焼捨",
                    "焼捨て",
                    "焼却",
                    "河流",
                    "玉串",
                    "時疫",
                    "蝶",
                    "死絶",
                ]:
                    add(value)
            if not any(marker in claim_focus for marker in (*taima_acceptance_markers, *taima_rumor_markers)):
                for value in [
                    "皇大神宮",
                    "神田神社",
                    "窪田次郎",
                    "配布",
                    "流言",
                    "妄伝",
                    "水火",
                    "投ズ",
                    "焼捨",
                    "河流",
                    "玉串",
                    "神棚",
                    "時疫",
                    "蝶",
                ]:
                    add(value)
                add(value)
        if any(marker in blob for marker in ("门户开放", "門戸開放", "門戶開放", "机会均等", "機會均等", "John Hay", "海伊", "ヘイ")):
            for value in [
                "支那ニ於ケル商業上機會均等及門戸開放",
                "支那ニ於ケル商業上機会均等及門戸開放",
                "門戶開放",
                "門戸開放",
                "機會均等",
                "機会均等",
                "米國照會",
                "米国照会",
                "帝國政府回答",
                "帝国政府回答",
                "各國回答",
                "各国回答",
                "ヘイ",
                "國務卿",
                "国務卿",
            ]:
                add(value)
        if any(marker in blob for marker in ("巴黎", "巴里", "講和", "讲和", "パリ", "牧野")):
            for value in [
                "巴里講和會議",
                "巴里講和会議",
                "巴黎講和会議",
                "講和會議",
                "講和会議",
                "牧野",
                "人種的差別撤廃",
                "人種的差別撤廢",
                "委員會",
                "委員会",
                "受諾",
                "留保",
            ]:
                add(value)
            if any(marker in claim_focus for marker in ("赤道", "南洋", "太平洋", "委任", "托管", "既定目標", "既定目标")):
                for value in [
                    "委任統治",
                    "赤道以北",
                    "獨領南洋",
                    "独領南洋",
                    "南洋群島",
                    "太平洋群島",
                    "會議ノ決定",
                    "会議ノ決定",
                    "決定ヲ受諾",
                ]:
                    add(value)
            if any(marker in claim_focus for marker in ("山東", "山东", "膠州", "胶州", "還附", "归还", "歸還")):
                for value in ["山東", "膠州灣", "膠州湾", "還附ノ決定"]:
                    add(value)
        if any(marker in blob for marker in ("ワシントン", "華盛頓", "华盛顿", "軍備", "军备", "主力艦")):
            for value in [
                "ワシントン會議",
                "ワシントン会議",
                "華盛頓會議",
                "軍備制限",
                "海軍軍備制限",
                "主力艦",
                "主力艦比率",
                "米国案ノ十対六",
                "米國案ノ十對六",
                "十対六",
                "十對六",
                "比率",
                "ヒューズ",
                "内田",
                "加藤",
                "防備",
            ]:
                add(value)
        if any(
            marker in blob
            for marker in (
                "桂太郎",
                "塔夫脱",
                "塔夫脫",
                "タフト",
                "哈里曼",
                "ハリマン",
                "南满铁路",
                "南滿鐵路",
                "南満洲鉄道",
                "南滿洲鐵道",
                "満鉄",
                "满铁",
            )
        ):
            for value in [
                "桂太郎",
                "タフト",
                "タフト陸軍長官",
                "桂・タフト",
                "ハリマン",
                "満鉄",
                "南満洲鉄道",
                "南滿洲鐵道",
                "共同經營",
                "共同経営",
                "豫備協定",
                "予備協定",
            ]:
                add(value)
        if any(marker in blob for marker in ("信教", "信仰", "宗教", "帝国憲法義解", "帝國憲法義解")):
            for value in [
                "信仰",
                "信仰歸依",
                "信仰帰依",
                "内部ニ於ケル信",
                "外部ニ於ケル禮拜",
                "外部ニ於ケル礼拝",
                "臣民ノ義務",
                "法憲",
                "法律規則",
                "布教",
                "自由",
            ]:
                add(value)
            if any(
                marker in blob
                for marker in (
                    "政权",
                    "政權",
                    "教权",
                    "教權",
                    "相互界定",
                    "疆域",
                    "裁定",
                )
            ):
                for value in [
                    "政權ト教權",
                    "政権ト教権",
                    "相分界",
                    "相分界スルノ域",
                    "憲法ノ裁定スル所",
                    "憲法ノ認定スル所",
                ]:
                    add(value)
        if any(marker in blob for marker in ("神田神社", "神田明神", "平将门", "平将門", "平將門", "神田祭", "祭神")):
            for value in [
                "神田神社",
                "神田明神",
                "平将門",
                "神田祭",
                "祭神",
                "祭神ノ座",
                "攝社",
                "摂社",
                "朝廷ニ對スル反逆者",
                "朝廷に対する反逆者",
            ]:
                add(value)
        return terms

    def _fulltext_hint_lead_category(self, candidate: CitationCandidate, hint: Dict[str, Any]) -> str:
        raw_text = " ".join(
            str(hint.get(key) or "")
            for key in ("query", "snippet", "expanded_context", "source_title")
        )
        normalized_text = normalize_match_text(raw_text)
        pid = str(hint.get("pid") or hint.get("book_id") or "")
        strict_ids = self._strict_resolver_known_pid_scope(candidate)
        if strict_ids and pid and pid not in strict_ids:
            return "wrong_pid"
        core_terms = [
            normalize_match_text(term)
            for term in self._fulltext_core_action_terms(candidate)
            if normalize_match_text(term)
        ]
        title_like_terms = [
            normalize_match_text(value)
            for value in [
                candidate.footnote.title,
                candidate.footnote.host_title,
                candidate.footnote.contained_title,
                candidate.footnote.ndl_keyword,
                "日本外交文書",
                "日本近代思想大系",
            ]
            if value
        ]
        query = normalize_match_text(str(hint.get("query") or ""))
        snippet = normalize_match_text(str(hint.get("snippet") or ""))
        expanded = normalize_match_text(str(hint.get("expanded_context") or ""))
        evidence_text = normalize_match_text(
            " ".join(
                str(hint.get(key) or "")
                for key in ("snippet", "expanded_context", "source_title")
            )
        )
        has_core = any(term in evidence_text for term in core_terms)
        substantive_core_terms = [
            term
            for term in core_terms
            if term
            and not any(
                title_term
                and len(title_term) >= 4
                and (term == title_term or term in title_term or title_term in term)
                for title_term in title_like_terms
            )
        ]
        has_substantive_core = any(term in evidence_text for term in substantive_core_terms)
        resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
        source_graph = candidate.artifacts.get("source_graph") or {}
        if not isinstance(resolver_plan, dict):
            resolver_plan = {}
        if not isinstance(source_graph, dict):
            source_graph = {}
        source_type = str(resolver_plan.get("source_type") or source_graph.get("source_type") or "")
        contained_title_terms = [
            normalize_match_text(value)
            for value in [
                candidate.footnote.contained_title,
                candidate.footnote.title if source_type == "contained_document" else "",
            ]
            if value
        ]
        front_markers = ("目次", "總目次", "総目次", "索引", "件名索引", "人名索引", "日付索引", "細目", "凡例")
        toc_page_marker_count = len(re.findall(r"[\(（][0-9一二三四五六七八九〇零十百]+[\)）]", raw_text))
        if any(marker in raw_text for marker in front_markers) and not has_substantive_core:
            return "toc_or_index"
        if toc_page_marker_count >= 3 and not has_substantive_core:
            return "toc_or_index"
        has_long_body_after_contained_title = False
        if source_type in {"contained_document", "source_collection"} and contained_title_terms:
            contained_title_body_text = snippet or expanded or evidence_text
            for term in contained_title_terms:
                if not term:
                    continue
                pos = contained_title_body_text.find(term)
                if pos < 0:
                    continue
                after = contained_title_body_text[pos + len(term) :]
                if len(after) >= 32:
                    has_long_body_after_contained_title = True
                    break
        if (
            source_type in {"contained_document", "source_collection"}
            and contained_title_terms
            and any(term and term in evidence_text for term in contained_title_terms)
            and not has_substantive_core
            and not self._hint_has_claim_snippet_evidence(candidate, hint)
            and not has_long_body_after_contained_title
        ):
            return "title_or_series_only"
        if (
            source_type in {"contained_document", "source_collection"}
            and contained_title_terms
            and any(term and term in query for term in contained_title_terms)
            and not has_substantive_core
            and not self._hint_has_claim_snippet_evidence(candidate, hint)
            and not has_long_body_after_contained_title
        ):
            return "title_or_series_only"
        publication_markers = ("不許複製", "印刷", "発行", "發行", "Published")
        if (
            any(marker in raw_text for marker in publication_markers)
            and not has_substantive_core
            and any(term and term in snippet for term in title_like_terms)
        ):
            return "title_or_series_only"
        try:
            pdf_page = int(hint.get("pdf_page") or 0)
        except (TypeError, ValueError):
            pdf_page = 0
        if pdf_page and pdf_page <= 8 and snippet and (snippet == query or len(snippet) <= 40):
            return "title_or_series_only"
        if (
            pdf_page
            and pdf_page <= 8
            and not has_substantive_core
            and any(term and term in snippet for term in title_like_terms)
        ):
            return "title_or_series_only"
        high_precision_volume_markers = (
            "米国案ノ十対六",
            "米國案ノ十對六",
            "十対六",
            "十對六",
            "ヒューズ",
            "委任統治",
            "赤道以北",
            "決定ヲ受諾",
            "米國照會",
            "米国照会",
            "帝國政府回答",
            "帝国政府回答",
        )
        if (
            source_type == "volume_series"
            and pdf_page
            and pdf_page <= 12
            and not self._hint_has_claim_snippet_evidence(candidate, hint)
            and not any(marker in raw_text for marker in high_precision_volume_markers)
            and any(marker in raw_text for marker in ("経緯", "經緯", "概要", "問題", "会議開催", "會議開催"))
        ):
            return "front_matter_body_lead"
        if query and query in title_like_terms and not has_core and not candidate.footnote.contained_title:
            return "title_or_series_only"
        if snippet and not has_core and any(term and snippet == term for term in title_like_terms):
            return "title_or_series_only"
        if (
            len(expanded or snippet) < 28
            and not has_core
            and not self._hint_is_specific_fulltext_evidence(candidate, hint)
            and not self._hint_has_claim_snippet_evidence(candidate, hint)
        ):
            return "short_or_unexpanded"
        return "body_candidate"

    def _score_fulltext_context_candidate(
        self,
        candidate: CitationCandidate,
        hint: Dict[str, Any],
        context_text: str,
    ) -> Tuple[float, List[str]]:
        score = self._fulltext_hint_specificity_score(candidate, hint)
        reasons: List[str] = [f"hint_specificity={round(score, 3)}"]
        category = self._fulltext_hint_lead_category(candidate, hint)
        if category == "body_candidate":
            score += 1.0
            reasons.append("body_candidate")
        elif category == "wrong_pid":
            score -= 8.0
            reasons.append("wrong_pid_penalty")
        elif category == "toc_or_index":
            score -= 5.0
            reasons.append("toc_or_index_penalty")
        elif category == "front_matter_body_lead":
            score -= 2.0
            reasons.append("front_matter_body_lead_penalty")
        elif category == "title_or_series_only":
            score -= 3.5
            reasons.append("title_or_series_only_penalty")
        elif category == "short_or_unexpanded":
            score -= 1.5
            reasons.append("short_context_penalty")

        normalized_context = normalize_match_text(
            " ".join(
                [
                    str(hint.get("query") or ""),
                    str(hint.get("snippet") or ""),
                    context_text,
                ]
            )
        )
        title_like_terms = [
            normalize_match_text(value)
            for value in [
                candidate.footnote.title,
                candidate.footnote.host_title,
                candidate.footnote.contained_title,
                candidate.footnote.ndl_keyword,
                "日本外交文書",
                "日本近代思想大系",
            ]
            if value
        ]
        broad_collection_terms = {
            normalize_match_text(value)
            for value in [
                "講和會議",
                "講和会議",
                "巴里講和會議",
                "巴里講和会議",
                "巴里講和会議経過概要",
                "巴里講和會議經過概要",
                "ワシントン会議",
                "華盛頓会議",
                "大正期追補",
                "追補 [1]",
            ]
        }
        broad_collection_terms.update(self._generic_fulltext_claim_terms())
        core_matches = []
        for term in self._fulltext_core_action_terms(candidate):
            normalized_term = normalize_match_text(term)
            if not normalized_term or normalized_term in broad_collection_terms:
                continue
            if any(
                title_term
                and len(title_term) >= 4
                and (
                    normalized_term == title_term
                    or normalized_term in title_term
                    or title_term in normalized_term
                )
                for title_term in title_like_terms
            ):
                continue
            if normalized_term in normalized_context:
                core_matches.append(normalized_term)
        if core_matches:
            bonus = min(4.0, len(core_matches) * 1.1)
            score += bonus
            reasons.append(f"core_terms={','.join(core_matches[:5])}")

        diary_packet = self._diary_claim_facet_packet(
            candidate,
            " ".join([str(hint.get("snippet") or ""), context_text]),
        )
        if diary_packet:
            bonus = float(diary_packet.get("score_bonus") or 0)
            if bonus:
                score += bonus
                facets = ",".join(diary_packet.get("covered_facets") or [])
                reasons.append(f"diary_claim_facets={facets}")

        resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
        specific_target_matches: List[str] = []
        specific_target_buckets: set[str] = set()
        specific_target_score = 0.0
        if isinstance(resolver_plan, dict):
            bucket_weights = {
                "document_heading": 2.4,
                "policy": 1.8,
                "action": 1.8,
                "theme": 1.6,
                "page_near": 1.6,
                "contained": 1.4,
                "special_term": 1.4,
                "document_title": 1.1,
                "person": 1.0,
                "anchor": 1.0,
                "date": 0.8,
                "target_pid_queries": 1.2,
            }

            def add_specific_match(value: Any, bucket: str) -> None:
                nonlocal specific_target_score
                term = normalize_match_text(str(value or ""))
                if len(term) < 4:
                    return
                if bucket in {"title", "host", "volume", "blocked_standalone"}:
                    return
                if bucket == "date" and self._is_year_only_fulltext_term(value):
                    return
                if bucket == "target_pid_queries" and self._is_year_only_fulltext_term(value):
                    return
                if self._is_bibliographic_locator_fulltext_term(candidate, value):
                    return
                if term in broad_collection_terms and bucket not in {
                    "document_heading",
                    "policy",
                    "theme",
                    "page_near",
                }:
                    return
                if bucket == "target_pid_queries" and any(
                    title_term
                    and len(title_term) >= 4
                    and (term == title_term or term in title_term or title_term in term)
                    for title_term in title_like_terms
                ):
                    return
                if term not in normalized_context:
                    return
                label = f"{bucket}:{term}"
                if label in specific_target_matches:
                    return
                specific_target_matches.append(label)
                specific_target_buckets.add(bucket)
                weight = bucket_weights.get(bucket, 1.0)
                if term in broad_collection_terms:
                    weight = min(weight, 0.5)
                specific_target_score += weight

            query_buckets = resolver_plan.get("query_buckets") or {}
            if isinstance(query_buckets, dict):
                for bucket_name, bucket_values in query_buckets.items():
                    if isinstance(bucket_values, list):
                        for value in bucket_values:
                            add_specific_match(value, str(bucket_name or "other"))
            for value in resolver_plan.get("target_pid_queries") or []:
                add_specific_match(value, "target_pid_queries")
        if specific_target_matches:
            score += min(5.0, specific_target_score)
            reasons.append(f"specific_targets={','.join(specific_target_matches[:3])}")
        query_buckets_for_theme = resolver_plan.get("query_buckets") if isinstance(resolver_plan, dict) else {}
        if (
            isinstance(query_buckets_for_theme, dict)
            and str(resolver_plan.get("source_type") or "") == "volume_series"
            and query_buckets_for_theme.get("theme")
            and "theme" not in specific_target_buckets
        ):
            score -= 3.0
            reasons.append("missing_volume_series_theme")

        cleaned_length = len(self._clean_fulltext_context_text(context_text))
        if cleaned_length >= 220:
            score += 1.0
            reasons.append("long_context")
        elif cleaned_length >= 90:
            score += 0.5
            reasons.append("medium_context")
        try:
            evidence_count = int(hint.get("expanded_context_evidence_count") or 0)
        except (TypeError, ValueError):
            evidence_count = 0
        if evidence_count:
            score += min(1.0, evidence_count * 0.25)
            reasons.append(f"expanded_evidence_count={evidence_count}")
        if hint.get("pdf_page"):
            score += 0.15
            reasons.append("pdf_page_hint")
        return score, reasons

    def _fulltext_context_expansion_cache_key(
        self,
        hint: Dict[str, Any],
        pid: str = "",
    ) -> Tuple[str, str, str, str, str]:
        resolved_pid = str(pid or hint.get("pid") or hint.get("book_id") or "")
        query = normalize_match_text(str(hint.get("query") or ""))[:160]
        cid = str(hint.get("cid") or "")
        content_index = hint.get("content_index")
        if content_index is None or content_index == "":
            location = str(hint.get("pdf_page") or "")
        else:
            location = str(content_index)
        if cid:
            location = f"cid:{cid}|idx:{location}"
        page_basis = str(hint.get("page_basis") or "")
        snippet = normalize_match_text(str(hint.get("snippet") or ""))
        snippet_hash = hashlib.sha1(snippet.encode("utf-8", errors="ignore")).hexdigest()[:16]
        return (resolved_pid, query, location, page_basis, snippet_hash)

    def _fulltext_context_expansion_cache_record_key(
        self,
        cache_key: Tuple[str, str, str, str, str],
    ) -> str:
        return json.dumps(list(cache_key), ensure_ascii=False, separators=(",", ":"))

    def _fulltext_context_expansion_cache_path(self, output_dir: Path) -> Path:
        return output_dir / self.FULLTEXT_CONTEXT_EXPANSION_CACHE_FILENAME

    def _load_fulltext_context_expansion_disk_cache(self, output_dir: Optional[Path]) -> None:
        if output_dir is None:
            return
        path = self._fulltext_context_expansion_cache_path(output_dir)
        path_key = str(path.resolve())
        if path_key in self._fulltext_context_expansion_loaded_paths:
            return
        self._fulltext_context_expansion_loaded_paths.add(path_key)
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        records = payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(records, dict):
            return
        for key_text, record in records.items():
            if not isinstance(record, dict):
                continue
            try:
                key_values = json.loads(str(key_text))
            except json.JSONDecodeError:
                continue
            if not isinstance(key_values, list) or len(key_values) != 5:
                continue
            cache_key = tuple(str(value) for value in key_values)
            expansion_payload = {
                field: record[field]
                for field in self.FULLTEXT_CONTEXT_EXPANSION_PAYLOAD_FIELDS
                if field in record
            }
            if expansion_payload.get("expanded_context"):
                expansion_payload["_disk_cache_record"] = True
                self._fulltext_context_expansion_cache.setdefault(cache_key, expansion_payload)

    def _write_fulltext_context_expansion_disk_cache(
        self,
        output_dir: Optional[Path],
        cache_key: Tuple[str, str, str, str, str],
        expansion_payload: Dict[str, Any],
    ) -> None:
        if output_dir is None:
            return
        output_dir.mkdir(parents=True, exist_ok=True)
        path = self._fulltext_context_expansion_cache_path(output_dir)
        try:
            payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except (OSError, json.JSONDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        records = payload.setdefault("records", {})
        if not isinstance(records, dict):
            records = {}
            payload["records"] = records
        record = {
            field: expansion_payload[field]
            for field in self.FULLTEXT_CONTEXT_EXPANSION_PAYLOAD_FIELDS
            if field in expansion_payload
        }
        record.update(
            {
                "pid": cache_key[0],
                "query": cache_key[1],
                "location": cache_key[2],
                "page_basis": cache_key[3],
                "snippet_hash": cache_key[4],
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        records[self._fulltext_context_expansion_cache_record_key(cache_key)] = record
        payload["schema_version"] = "historical_citation.fulltext_context_expansion_cache.v1"
        payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)

    def _select_diary_fulltext_hints_to_expand(
        self,
        candidate: CitationCandidate,
        hints: Sequence[Dict[str, Any]],
        *,
        limit: int,
    ) -> List[Dict[str, Any]]:
        selected: List[Dict[str, Any]] = []
        selected_ids: set[int] = set()

        def hint_text(hint: Dict[str, Any]) -> str:
            return " ".join(
                str(hint.get(key) or "")
                for key in ("query", "snippet", "expanded_context", "source_title")
            )

        scored_hints: List[Tuple[float, int, Dict[str, Any]]] = []
        lead_rank = {
            "body_candidate": 0,
            "short_or_unexpanded": 1,
            "title_or_series_only": 2,
            "toc_or_index": 3,
            "wrong_pid": 4,
        }
        for index, hint in enumerate(hints):
            if not isinstance(hint, dict):
                continue
            packet = self._diary_claim_facet_packet(candidate, hint_text(hint))
            scope = self._diary_date_hint_match_scope(candidate, hint)
            score = float(packet.get("score_bonus") or 0) if packet else 0.0
            if scope == "query_and_snippet":
                score += 1.5
            elif scope == "snippet":
                score += 1.0
            elif scope == "query_only":
                score += 0.25
            score += max(0.0, 1.0 - 0.25 * lead_rank.get(self._fulltext_hint_lead_category(candidate, hint), 4))
            scored_hints.append((score, index, hint))
        scored_hints.sort(key=lambda item: (-item[0], item[1]))
        diary_selected: List[Dict[str, Any]] = []
        for score, _index, hint in scored_hints:
            if score <= 0 or len(diary_selected) >= limit:
                break
            diary_selected.append(hint)
            selected_ids.add(id(hint))
        if diary_selected:
            candidate.artifacts["diary_fulltext_context_hint_selection"] = [
                {
                    "query": str(hint.get("query") or ""),
                    "pdf_page": hint.get("pdf_page"),
                    "lead_category": self._fulltext_hint_lead_category(candidate, hint),
                    "date_scope": self._diary_date_hint_match_scope(candidate, hint),
                    "claim_facets": self._diary_claim_facet_packet(candidate, hint_text(hint)).get("covered_facets", []),
                }
                for hint in diary_selected
            ]
            selected.extend(diary_selected)
        seen_query_keys: set[str] = set()
        for hint in selected:
            query_key = normalize_match_text(str(hint.get("query") or "")) or normalize_match_text(str(hint.get("snippet") or ""))[:80]
            if query_key:
                seen_query_keys.add(query_key)
        for hint in hints:
            if not isinstance(hint, dict) or id(hint) in selected_ids:
                continue
            query_key = normalize_match_text(str(hint.get("query") or "")) or normalize_match_text(str(hint.get("snippet") or ""))[:80]
            if query_key and query_key in seen_query_keys:
                continue
            selected.append(hint)
            selected_ids.add(id(hint))
            if query_key:
                seen_query_keys.add(query_key)
            if len(selected) >= limit:
                break
        return selected[:limit]

    def _select_fulltext_hints_to_expand(
        self,
        candidate: CitationCandidate,
        hints: Sequence[Dict[str, Any]],
        *,
        limit: int,
    ) -> List[Dict[str, Any]]:
        if limit <= 0:
            return []
        resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
        source_graph = candidate.artifacts.get("source_graph") or {}
        if not isinstance(resolver_plan, dict):
            resolver_plan = {}
        if not isinstance(source_graph, dict):
            source_graph = {}
        source_type = str(resolver_plan.get("source_type") or source_graph.get("source_type") or "")
        if source_type == "diary":
            return self._select_diary_fulltext_hints_to_expand(candidate, hints, limit=limit)
        if source_type != "volume_series":
            return list(hints[:limit])
        selected: List[Dict[str, Any]] = []
        selected_ids: set[int] = set()
        critical_groups = self._volume_series_critical_hint_groups(candidate)
        selected_critical_groups: List[Dict[str, str]] = []

        def hint_text(hint: Dict[str, Any]) -> str:
            return normalize_match_text(
                " ".join(
                    str(hint.get(key) or "")
                    for key in ("query", "snippet", "expanded_context", "source_title")
                )
            )

        for group in critical_groups:
            if len(selected) >= limit:
                break
            terms = [
                normalize_match_text(term)
                for term in group.get("terms", [])
                if normalize_match_text(term)
            ]
            if not terms:
                continue
            matching_hints = [
                hint
                for hint in hints
                if isinstance(hint, dict)
                and id(hint) not in selected_ids
                and any(term in hint_text(hint) for term in terms)
            ]
            if not matching_hints:
                continue
            matching_hints.sort(
                key=lambda hint: (
                    self._fulltext_hint_lead_category(candidate, hint) != "body_candidate",
                    not any(
                        normalize_match_text(term) in normalize_match_text(str(hint.get("query") or ""))
                        for term in group.get("terms", [])
                    ),
                    -self._fulltext_hint_specificity_score(candidate, hint),
                    not bool(hint.get("pdf_page")),
                )
            )
            picked = matching_hints[0]
            selected.append(picked)
            selected_ids.add(id(picked))
            selected_critical_groups.append(
                {
                    "group_id": str(group.get("group_id") or ""),
                    "query": str(picked.get("query") or ""),
                    "pdf_page": str(picked.get("pdf_page") or ""),
                }
            )
        if selected_critical_groups:
            candidate.artifacts["fulltext_context_critical_hint_groups"] = selected_critical_groups
        seen_query_keys: set[str] = set()
        for hint in selected:
            query_key = normalize_match_text(str(hint.get("query") or ""))
            if not query_key:
                query_key = normalize_match_text(str(hint.get("snippet") or ""))[:80]
            if query_key:
                seen_query_keys.add(query_key)
        for hint in hints:
            if not isinstance(hint, dict):
                continue
            if id(hint) in selected_ids:
                continue
            query_key = normalize_match_text(str(hint.get("query") or ""))
            if not query_key:
                query_key = normalize_match_text(str(hint.get("snippet") or ""))[:80]
            if query_key and query_key in seen_query_keys:
                continue
            selected.append(hint)
            selected_ids.add(id(hint))
            if query_key:
                seen_query_keys.add(query_key)
            if len(selected) >= limit:
                break
        if len(selected) < limit:
            for hint in hints:
                if not isinstance(hint, dict) or id(hint) in selected_ids:
                    continue
                selected.append(hint)
                selected_ids.add(id(hint))
                if len(selected) >= limit:
                    break
        return selected

    def _volume_series_critical_hint_groups(self, candidate: CitationCandidate) -> List[Dict[str, Any]]:
        resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
        if not isinstance(resolver_plan, dict):
            resolver_plan = {}
        trigger_text = " ".join(
            str(value or "")
            for value in [
                candidate.translation_text,
                candidate.paragraph_text,
                candidate.footnote.text,
                candidate.footnote.title,
                candidate.footnote.ndl_keyword,
            ]
        )
        resolver_trigger_terms: List[str] = []
        if isinstance(resolver_plan, dict):
            resolver_trigger_terms.extend(str(item or "") for item in resolver_plan.get("target_pid_queries") or [])
            query_buckets = resolver_plan.get("query_buckets") or {}
            if isinstance(query_buckets, dict):
                for values in query_buckets.values():
                    if isinstance(values, list):
                        resolver_trigger_terms.extend(str(item or "") for item in values)
        resolver_trigger_text = " ".join(resolver_trigger_terms)
        groups: List[Dict[str, Any]] = []

        def add_group(group_id: str, terms: Sequence[str]) -> None:
            cleaned_terms = []
            for term in terms:
                normalized = normalize_match_text(term)
                if normalized and normalized not in [normalize_match_text(value) for value in cleaned_terms]:
                    cleaned_terms.append(term)
            if cleaned_terms:
                groups.append({"group_id": group_id, "terms": cleaned_terms})

        washington_trigger = any(
            term in trigger_text
            for term in ("ワシントン", "華盛頓", "华盛顿", "軍備", "军备", "主力艦", "主力舰", "休斯", "ヒューズ")
        )
        exact_ratio_trigger = any(
            term in trigger_text
            for term in ("10:10:6", "１０∶１０∶６", "十对六", "十對六", "十対六", "主力舰比例", "主力艦比率")
        )
        if washington_trigger and exact_ratio_trigger:
            add_group(
                "washington_exact_ten_ten_six_ratio",
                [
                    "米国案ノ十対六",
                    "米國案ノ十對六",
                    "十対六",
                    "十對六",
                    "十・十・六",
                    "十、十、六",
                    "10:10:6",
                    "１０∶１０∶６",
                ],
            )
        if washington_trigger and any(term in trigger_text for term in ("休斯", "ヒューズ", "Hughes")):
            add_group("washington_hughes_speaker", ["ヒューズ国務長官", "ヒューズ國務長官", "ヒューズ"])
        if washington_trigger:
            add_group("washington_naval_limitation", ["海軍軍備制限問題", "海軍軍備制限", "軍備制限問題"])

        taft_harriman_trigger = any(
            term in trigger_text
            for term in (
                "桂太郎",
                "塔夫脱",
                "塔夫脫",
                "タフト",
                "哈里曼",
                "ハリマン",
                "南满铁路",
                "南滿鐵路",
                "南満洲鉄道",
                "満鉄",
            )
        )
        if taft_harriman_trigger:
            add_group(
                "gaiko_katsura_taft_harriman",
                [
                    "タフト",
                    "タフト陸軍長官",
                    "桂・タフト",
                    "ハリマン",
                    "満鉄",
                    "南満洲鉄道",
                    "南滿洲鐵道",
                    "共同經營",
                    "共同経営",
                ],
            )

        paris_trigger_text = f"{trigger_text} {resolver_trigger_text}"
        paris_trigger = any(term in trigger_text for term in ("巴黎", "巴里", "パリ", "講和", "讲和", "牧野"))
        if paris_trigger and any(
            term in paris_trigger_text
            for term in ("赤道以北", "太平洋群", "委任", "托管", "既定目标", "會議決定", "会议决定", "南洋", "獨領南洋", "独領南洋")
        ):
            add_group(
                "paris_mandate_decision",
                [
                    "委任統治",
                    "委任統治ノ形式",
                    "C式委任統治",
                    "C類委任統治",
                    "赤道以北",
                    "獨領南洋",
                    "独領南洋",
                    "南洋群島",
                    "太平洋群島",
                    "會議ノ決定",
                    "会議ノ決定",
                    "決定ヲ受諾",
                ],
            )
        if paris_trigger and "牧野" in trigger_text:
            add_group("paris_makino_claim_statement", ["帝國主張説明", "帝国主張説明", "牧野男", "牧野委員"])
        return groups

    def _expand_fulltext_context_candidates(
        self,
        candidate: CitationCandidate,
        *,
        preferred_pid: str = "",
        max_candidates: int = 5,
        max_hints_to_expand: int = 3,
        max_expand_rounds: int = 2,
        cache_dir: Optional[Path] = None,
    ) -> List[Dict[str, Any]]:
        self._load_fulltext_context_expansion_disk_cache(cache_dir)
        hints = self._ordered_fulltext_hints_for_candidate(candidate, preferred_pid=preferred_pid)
        hints_to_expand = self._select_fulltext_hints_to_expand(
            candidate,
            hints,
            limit=max_hints_to_expand,
        )
        candidate.artifacts["fulltext_context_expanded_hint_queries"] = [
            str(hint.get("query") or "")
            for hint in hints_to_expand
            if isinstance(hint, dict)
        ]
        self._emit_progress_event(
            "worker_stage_started",
            subphase="snippet_context_expansion",
            metrics={
                "preferred_pid": preferred_pid,
                "hint_count": len(hints_to_expand),
                "max_candidates": max_candidates,
                "max_expand_rounds": max_expand_rounds,
                "cache_dir": str(cache_dir) if cache_dir is not None else "",
            },
        )
        expanded_candidates: List[Dict[str, Any]] = []
        seen: set[Tuple[str, Any, str]] = set()
        for hint in hints_to_expand:
            if not isinstance(hint, dict):
                continue
            pid = str(hint.get("pid") or hint.get("book_id") or preferred_pid or "")
            snippet = str(hint.get("snippet") or "")
            if not hint.get("expanded_context") and pid and snippet:
                cache_key = self._fulltext_context_expansion_cache_key(hint, pid)
                cached_expansion = self._fulltext_context_expansion_cache.get(cache_key)
                if cached_expansion:
                    hint.update(
                        {
                            field: cached_expansion[field]
                            for field in self.FULLTEXT_CONTEXT_EXPANSION_PAYLOAD_FIELDS
                            if field in cached_expansion
                        }
                    )
                    candidate.artifacts["fulltext_context_cache_hits"] = (
                        int(candidate.artifacts.get("fulltext_context_cache_hits") or 0) + 1
                    )
                    if cached_expansion.get("_disk_cache_record"):
                        candidate.artifacts["fulltext_context_disk_cache_hits"] = (
                            int(candidate.artifacts.get("fulltext_context_disk_cache_hits") or 0) + 1
                        )
                else:
                    try:
                        pdf_page = int(hint.get("pdf_page")) if hint.get("pdf_page") is not None else None
                    except (TypeError, ValueError):
                        pdf_page = None
                    seed = NDLFulltextHit(
                        pid=pid,
                        query=str(hint.get("query") or ""),
                        snippet=snippet,
                        pdf_page=pdf_page,
                        cid=str(hint.get("cid") or ""),
                        content_index=hint.get("content_index"),
                        mode="SNIPPET",
                        page_basis=str(hint.get("page_basis") or "dl_ndl_fulltext_content_index"),
                    )
                    try:
                        expanded = expand_ndl_snippet_context(
                            pid,
                            seed,
                            max_rounds=max(0, int(max_expand_rounds)),
                        )
                        context_text = getattr(expanded, "context_text", "") or ""
                        if context_text:
                            expansion_payload = {
                                "expanded_context": context_text,
                                "expanded_context_status": getattr(expanded, "status", "snippet_expanded"),
                                "expanded_context_note": getattr(expanded, "note", ""),
                                "expanded_context_evidence_count": len(
                                    getattr(expanded, "evidence_hits", []) or []
                                ),
                            }
                            hint.update(expansion_payload)
                            self._fulltext_context_expansion_cache[cache_key] = dict(expansion_payload)
                            self._write_fulltext_context_expansion_disk_cache(
                                cache_dir,
                                cache_key,
                                expansion_payload,
                            )
                    except Exception as exc:  # noqa: BLE001
                        hint["expanded_context_status"] = "expand_failed"
                        hint["expanded_context_error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
            context_text = str(hint.get("expanded_context") or hint.get("snippet") or "")
            cleaned_context = self._clean_fulltext_context_text(context_text)
            if not cleaned_context:
                continue
            key = (
                pid,
                hint.get("pdf_page"),
                normalize_match_text(cleaned_context[:400]),
            )
            if key in seen:
                continue
            seen.add(key)
            score, reasons = self._score_fulltext_context_candidate(candidate, hint, cleaned_context)
            category = self._fulltext_hint_lead_category(candidate, hint)
            expanded_candidates.append(
                {
                    "context_id": f"ctx{len(expanded_candidates) + 1}",
                    "pid": pid,
                    "book_id": pid,
                    "pdf_page": hint.get("pdf_page"),
                    "query": hint.get("query") or "",
                    "snippet": hint.get("snippet") or "",
                    "cid": hint.get("cid") or "",
                    "content_index": hint.get("content_index"),
                    "page_basis": hint.get("page_basis") or "",
                    "expanded_context_status": hint.get("expanded_context_status") or "",
                    "expanded_context_note": hint.get("expanded_context_note") or "",
                    "expanded_context_evidence_count": hint.get("expanded_context_evidence_count") or 0,
                    "expanded_context": context_text,
                    "cleaned_context": cleaned_context,
                    "lead_category": category,
                    "score": round(score, 4),
                    "score_reasons": reasons,
                    "specific": self._hint_is_specific_fulltext_evidence(candidate, hint),
                    "claim_evidence": self._hint_has_claim_snippet_evidence(candidate, hint),
                }
            )
        expanded_candidates.sort(
            key=lambda item: (
                item.get("lead_category") != "body_candidate",
                -float(item.get("score") or 0.0),
                not bool(item.get("pdf_page")),
            )
        )
        for index, item in enumerate(expanded_candidates, start=1):
            item["context_id"] = f"ctx{index}"
        top_candidates = expanded_candidates[:max_candidates]
        if top_candidates:
            candidate.artifacts["fulltext_context_candidates"] = top_candidates
            candidate.artifacts["fulltext_only_context"] = top_candidates[0].get("cleaned_context") or ""
        self._emit_progress_event(
            "worker_stage_completed",
            subphase="snippet_context_expansion",
            status="contexts_found" if top_candidates else "no_context",
            metrics={
                "preferred_pid": preferred_pid,
                "expanded_hint_count": len(hints_to_expand),
                "context_count": len(top_candidates),
                "raw_context_count": len(expanded_candidates),
                "cache_hits": int(candidate.artifacts.get("fulltext_context_cache_hits") or 0),
                "disk_cache_hits": int(candidate.artifacts.get("fulltext_context_disk_cache_hits") or 0),
            },
        )
        return top_candidates

    def _generic_volume_series_compound_facet_definitions(
        self,
        resolver_plan: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        query_buckets = resolver_plan.get("query_buckets") or {}
        if not isinstance(query_buckets, dict):
            return []

        def clean_terms(bucket_name: str) -> List[str]:
            values = query_buckets.get(bucket_name) or []
            if not isinstance(values, list):
                return []
            terms: List[str] = []
            for value in values:
                term = str(value or "").strip()
                if len(normalize_match_text(term)) < 3:
                    continue
                if term not in terms:
                    terms.append(term)
            return terms[:8]

        facet_specs = [
            ("document_heading", "document heading / in-volume title", True),
            ("policy", "policy / diplomatic action term", True),
            ("theme", "theme term", True),
            ("page_near", "page-near term", True),
            ("contained", "contained document term", True),
            ("special_term", "special source term", True),
            ("person", "person term", False),
            ("date", "date term", False),
            ("document_title", "volume/document title lead", False),
        ]
        facets: List[Dict[str, Any]] = []
        for bucket_name, label, required in facet_specs:
            terms = clean_terms(bucket_name)
            if not terms:
                continue
            facets.append(
                {
                    "facet_id": f"bucket_{bucket_name}",
                    "label": label,
                    "required": required,
                    "terms": terms,
                    "bucket": bucket_name,
                }
            )
        required_count = sum(1 for facet in facets if facet.get("required"))
        if required_count < 2:
            for facet in facets:
                if required_count >= 2:
                    break
                bucket = str(facet.get("bucket") or "")
                terms = [str(term or "") for term in facet.get("terms") or []]
                event_date_like = bucket == "date" and any("月" in term or "日" in term for term in terms)
                if bucket == "person" or event_date_like:
                    facet["required"] = True
                    required_count += 1
        if required_count < 2:
            return []
        return facets

    def _build_fulltext_compound_evidence_packet(
        self,
        candidate: CitationCandidate,
        context_candidates: Sequence[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
        source_graph = candidate.artifacts.get("source_graph") or {}
        if not isinstance(resolver_plan, dict):
            resolver_plan = {}
        if not isinstance(source_graph, dict):
            source_graph = {}
        source_type = str(resolver_plan.get("source_type") or source_graph.get("source_type") or "")
        if source_type != "volume_series":
            return None
        trigger_text = " ".join(
            str(value or "")
            for value in [
                candidate.translation_text,
                candidate.paragraph_text,
                candidate.footnote.text,
                candidate.footnote.title,
                candidate.footnote.ndl_keyword,
            ]
        )
        resolver_trigger_terms: List[str] = []
        resolver_trigger_terms.extend(str(item or "") for item in resolver_plan.get("target_pid_queries") or [])
        query_buckets_for_trigger = resolver_plan.get("query_buckets") or {}
        if isinstance(query_buckets_for_trigger, dict):
            for values in query_buckets_for_trigger.values():
                if isinstance(values, list):
                    resolver_trigger_terms.extend(str(item or "") for item in values)
        resolver_trigger_text = " ".join(resolver_trigger_terms)
        open_door_trigger = any(
            term in trigger_text
            for term in (
                "门户开放",
                "門戶開放",
                "門戸開放",
                "John Hay",
                "海伊",
                "ヘイ",
                "機会均等",
                "機會均等",
            )
        )
        washington_naval_trigger = any(
            term in trigger_text
            for term in (
                "ワシントン",
                "華盛頓",
                "华盛顿",
                "軍備",
                "军备",
                "主力艦",
                "主力舰",
                "休斯",
                "ヒューズ",
                "１０∶１０∶６",
                "10:10:6",
                "十対六",
                "十對六",
            )
        )
        paris_trigger_text = f"{trigger_text} {resolver_trigger_text}"
        paris_context_trigger = any(
            term in trigger_text
            for term in (
                "巴黎",
                "巴里",
                "パリ",
                "講和",
                "讲和",
                "牧野",
            )
        )
        paris_mandate_context = any(
            term in paris_trigger_text
            for term in (
                "委任",
                "托管",
                "南洋",
                "赤道以北",
                "獨領南洋",
                "独領南洋",
                "南洋群島",
                "太平洋群島",
            )
        )
        paris_mandate_trigger = paris_context_trigger and paris_mandate_context
        if open_door_trigger:
            packet_type = "volume_series_open_door_compound_claim"
            facet_definitions: List[Dict[str, Any]] = [
                {
                    "facet_id": "us_proposal",
                    "label": "US proposal / Hay note",
                    "required": True,
                    "terms": [
                        "合衆國ノ提議",
                        "合衆国ノ提議",
                        "合衆國政府ノ提議",
                        "合衆国政府ノ提議",
                        "合衆國政府カ宣言",
                        "合衆国政府カ宣言",
                        "米國政府照會",
                        "米国政府照会",
                        "米國照會",
                        "米国照会",
                        "ヘイ國務卿",
                        "ヘイ国務卿",
                    ],
                },
                {
                    "facet_id": "open_door_principle",
                    "label": "open-door / equal opportunity principle",
                    "required": True,
                    "terms": [
                        "清國ニ於ケル門戶開放",
                        "清国ニ於ケル門戸開放",
                        "門戶開放",
                        "門戸開放",
                        "機會均等",
                        "機会均等",
                    ],
                },
                {
                    "facet_id": "japan_acceptance",
                    "label": "Japanese government reply / acceptance",
                    "required": True,
                    "terms": [
                        "日本國政府ハ",
                        "日本国政府ハ",
                        "承諾シタル",
                        "該主義ヲ承諾",
                        "帝國政府回答",
                        "帝国政府回答",
                        "回答セリ",
                    ],
                },
            ]
        elif paris_mandate_trigger:
            packet_type = "volume_series_paris_mandate_compound_claim"
            decision_required = any(
                term in trigger_text
                for term in (
                    "接受",
                    "受諾",
                    "受诺",
                    "承諾",
                    "承诺",
                    "会议决定",
                    "會議決定",
                    "会議ノ決定",
                    "會議ノ決定",
                )
            )
            goal_required = any(
                term in trigger_text
                for term in ("目标", "目標", "既定", "达成", "達成", "实现", "實現")
            )
            facet_definitions = [
                {
                    "facet_id": "mandate_territory",
                    "label": "South Seas / north-of-equator mandate territory",
                    "required": True,
                    "terms": [
                        "赤道以北",
                        "獨領南洋",
                        "独領南洋",
                        "南洋群島",
                        "南洋群岛",
                        "太平洋群島",
                        "太平洋群岛",
                    ],
                },
                {
                    "facet_id": "mandate_system",
                    "label": "mandate system / British mandate proposal",
                    "required": True,
                    "terms": [
                        "委任統治",
                        "委任統治ノ形式",
                        "C式委任統治",
                        "C類委任統治",
                        "受任國",
                        "統治受任國",
                        "英国ノ委任統治案",
                        "英國ノ委任統治案",
                    ],
                },
                {
                    "facet_id": "japanese_actor_makino",
                    "label": "Makino / Japanese delegate",
                    "required": "牧野" in trigger_text,
                    "terms": [
                        "牧野男",
                        "牧野委員",
                        "牧野伸顕",
                        "牧野伸显",
                        "日本委員",
                        "帝國委員",
                        "帝国委員",
                    ],
                },
                {
                    "facet_id": "decision_acceptance_action",
                    "label": "acceptance of the decision / no objection",
                    "required": decision_required,
                    "terms": [
                        "決定ヲ受諾",
                        "決定ヲ受入",
                        "決定ヲ受ケ入",
                        "受諾",
                        "受入",
                        "受け入",
                        "承諾",
                        "同意",
                        "異議ナシ",
                        "異議ナキ",
                    ],
                },
                {
                    "facet_id": "goal_or_outcome",
                    "label": "stated goal / achieved outcome",
                    "required": goal_required,
                    "terms": [
                        "目標",
                        "目的",
                        "目的ヲ達",
                        "目的ヲ達成",
                        "達成",
                        "要求ヲ貫徹",
                        "主張ヲ貫徹",
                    ],
                },
                {
                    "facet_id": "weak_meeting_decision_lead",
                    "label": "weak meeting-decision lead",
                    "required": False,
                    "terms": [
                        "會議ノ決定",
                        "会議ノ決定",
                        "會議決定",
                        "会議決定",
                    ],
                },
            ]
        elif washington_naval_trigger:
            packet_type = "volume_series_washington_naval_limitation_compound_claim"
            exact_ratio_required = any(
                term in trigger_text
                for term in ("１０∶１０∶６", "10:10:6", "十対六", "十對六", "十对六")
            )
            ratio_required = exact_ratio_required or any(
                term in trigger_text
                for term in ("１０∶１０∶６", "10:10:6", "比例", "比率", "主力舰", "主力艦", "六割")
            )
            speaker_required = any(term in trigger_text for term in ("休斯", "ヒューズ", "Hughes"))
            facet_definitions = [
                {
                    "facet_id": "naval_limitation_proposal",
                    "label": "naval limitation proposal",
                    "required": True,
                    "terms": [
                        "海軍軍備制限問題",
                        "海軍軍備制限",
                        "軍備制限問題",
                        "日英米三国間",
                        "日英米三國間",
                        "製艦ヲ協定程度ニ制限",
                        "制限スル一条約",
                    ],
                },
                {
                    "facet_id": "hughes_or_us_speaker",
                    "label": "Hughes / US speaker",
                    "required": speaker_required,
                    "terms": [
                        "ヒューズ",
                        "ヒューズ国務長官",
                        "ヒューズ國務長官",
                        "国務長官",
                        "國務長官",
                    ],
                },
                {
                    "facet_id": "exact_ten_ten_six_ratio",
                    "label": "exact 10:10:6 / ten-to-six ratio",
                    "required": exact_ratio_required,
                    "terms": [
                        "米国案ノ十対六",
                        "米國案ノ十對六",
                        "十対六",
                        "十對六",
                        "十・十・六",
                        "十、十、六",
                        "10:10:6",
                        "１０∶１０∶６",
                    ],
                },
                {
                    "facet_id": "capital_ship_ratio",
                    "label": "capital-ship ratio",
                    "required": ratio_required and not exact_ratio_required,
                    "terms": [
                        "主力艦比率",
                        "主力艦",
                        "勢力比",
                        "海軍勢力比",
                        "比率",
                        "六割",
                    ],
                },
            ]
        else:
            packet_type = "volume_series_query_bucket_compound_claim"
            facet_definitions = self._generic_volume_series_compound_facet_definitions(resolver_plan)
            if not facet_definitions:
                return None
        if sum(1 for facet in facet_definitions if facet.get("required")) < 2:
            return None
        facets: List[Dict[str, Any]] = []
        supporting_context_ids: List[str] = []
        for facet in facet_definitions:
            hits: List[Dict[str, Any]] = []
            normalized_terms = [
                (term, normalize_match_text(term))
                for term in facet.get("terms", [])
                if str(term or "").strip()
            ]
            for context in context_candidates:
                if not isinstance(context, dict):
                    continue
                context_id = str(context.get("context_id") or "")
                raw_text = " ".join(
                    str(context.get(key) or "")
                    for key in (
                        "query",
                        "snippet",
                        "expanded_context",
                        "cleaned_context",
                    )
                )
                raw_text = raw_text + " " + " ".join(
                    str(reason) for reason in context.get("score_reasons") or []
                )
                normalized_text = normalize_match_text(raw_text)
                matched_terms = [
                    term
                    for term, normalized_term in normalized_terms
                    if term in raw_text or (normalized_term and normalized_term in normalized_text)
                ]
                if not matched_terms:
                    continue
                if context_id and context_id not in supporting_context_ids:
                    supporting_context_ids.append(context_id)
                cleaned = self._clean_fulltext_context_text(
                    context.get("cleaned_context")
                    or context.get("expanded_context")
                    or context.get("snippet")
                    or ""
                )
                hits.append(
                    {
                        "context_id": context_id,
                        "pdf_page": context.get("pdf_page"),
                        "query": context.get("query") or "",
                        "matched_terms": matched_terms[:5],
                        "score": context.get("score"),
                        "lead_category": context.get("lead_category") or "",
                        "excerpt": cleaned[:260],
                    }
                )
            facets.append(
                {
                    "facet_id": facet["facet_id"],
                    "label": facet["label"],
                    "required": bool(facet.get("required")),
                    "covered": bool(hits),
                    "hits": hits[:4],
                }
            )
        required_facets = [facet for facet in facets if facet.get("required")]
        complete = bool(required_facets) and all(facet.get("covered") for facet in required_facets)
        return {
            "packet_type": packet_type,
            "source_type": source_type,
            "complete": complete,
            "required_facet_ids": [str(facet.get("facet_id") or "") for facet in required_facets],
            "supporting_context_ids": supporting_context_ids,
            "facets": facets,
            "instruction": (
                "Read the covered facets together when judging whether the same NDL volume "
                "supports the paper sentence."
            ),
        }

    def _record_fulltext_compound_evidence_review_gap(
        self,
        candidate: CitationCandidate,
        review: Dict[str, Any],
    ) -> None:
        packet = candidate.artifacts.get("fulltext_compound_evidence_packet") or {}
        if not isinstance(packet, dict) or not packet.get("complete"):
            return
        decision = str(review.get("decision") or "uncertain")
        if decision == "direct_support":
            return
        gap = {
            "decision": decision,
            "best_context_id": review.get("best_context_id") or "",
            "supporting_context_ids": review.get("supporting_context_ids") or [],
            "reason": review.get("reason") or "",
            "note": (
                "Compound same-source evidence covers all required facets, but the final review "
                "did not judge it as direct support."
            ),
        }
        candidate.artifacts["fulltext_compound_evidence_review_gap"] = gap
        note = "fulltext_compound_evidence_requires_manual_review"
        if note not in candidate.notes:
            candidate.notes.append(note)

    def _augment_direct_review_with_compound_evidence(
        self,
        candidate: CitationCandidate,
        review: Dict[str, Any],
    ) -> None:
        packet = candidate.artifacts.get("fulltext_compound_evidence_packet") or {}
        if not isinstance(packet, dict) or not packet.get("complete"):
            return
        if str(review.get("decision") or "") != "direct_support":
            return
        supporting_context_ids: List[str] = []
        raw_supporting = review.get("supporting_context_ids") or []
        if isinstance(raw_supporting, str):
            raw_supporting = [item.strip() for item in raw_supporting.split(",")]
        if isinstance(raw_supporting, list):
            for item in raw_supporting:
                context_id = str(item or "").strip()
                if context_id and context_id not in supporting_context_ids:
                    supporting_context_ids.append(context_id)
        best_context_id = str(review.get("best_context_id") or "").strip()
        if best_context_id and best_context_id not in supporting_context_ids:
            supporting_context_ids.insert(0, best_context_id)

        added_context_ids: List[str] = []
        covered_facet_ids: List[str] = []
        for facet in packet.get("facets") or []:
            if not isinstance(facet, dict) or not facet.get("required", True):
                continue
            hits = facet.get("hits") or []
            if not isinstance(hits, list) or not hits:
                continue
            hit_context_id = ""
            for hit in hits:
                if not isinstance(hit, dict):
                    continue
                hit_context_id = str(hit.get("context_id") or "").strip()
                if hit_context_id:
                    break
            if not hit_context_id:
                continue
            covered_facet_ids.append(str(facet.get("facet_id") or "facet"))
            if hit_context_id not in supporting_context_ids:
                supporting_context_ids.append(hit_context_id)
                added_context_ids.append(hit_context_id)
        if not added_context_ids:
            return
        review["supporting_context_ids"] = supporting_context_ids
        review["compound_evidence_packet_used"] = True
        review["compound_evidence_added_context_ids"] = added_context_ids
        review["compound_evidence_facet_ids"] = covered_facet_ids
        candidate.artifacts["fulltext_compound_evidence_packet_used"] = {
            "added_context_ids": added_context_ids,
            "facet_ids": covered_facet_ids,
        }

    def _select_fulltext_context_candidate(
        self,
        candidate: CitationCandidate,
        context_candidates: Sequence[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not context_candidates:
            return None
        candidate_by_id = {
            str(item.get("context_id") or ""): item
            for item in context_candidates
            if isinstance(item, dict)
        }
        selected = next(iter(context_candidates))
        compound_packet = self._build_fulltext_compound_evidence_packet(candidate, context_candidates)
        if compound_packet:
            candidate.artifacts["fulltext_compound_evidence_packet"] = compound_packet
            candidate.artifacts[
                "fulltext_llm_review_basis"
            ] = "ndl_expanded_snippet_context_candidates_plus_compound_packet"
        if (
            self._enable_llm_review
            and (self._prefer_ollama_review or self._review_llm_client is not None)
        ):
            self._emit_progress_event(
                "worker_stage_started",
                subphase="llm_context_review",
                metrics={
                    "context_count": len(context_candidates),
                    "compound_packet": bool(compound_packet),
                },
            )
            llm_client = self._get_review_llm_client(optional=True)
            if llm_client is None:
                candidate.artifacts["llm_review"] = {
                    "decision": "uncertain",
                    "confidence": 0.0,
                    "exact_sentence": "",
                    "best_context_id": str(selected.get("context_id") or ""),
                    "reason": "未配置可用 LLM 精核模型",
                    "provider": "none",
                    "eligible_for_llm_review": True,
                    "llm_review_success": False,
                    "llm_review_json_repaired": False,
                    "llm_review_fallback_heuristic": False,
                    "llm_review_failed": True,
                }
                self._emit_progress_event(
                    "worker_stage_completed",
                    subphase="llm_context_review",
                    status="unavailable",
                    metrics={"provider": "none", "best_context_id": str(selected.get("context_id") or "")},
                )
            else:
                try:
                    health_check = getattr(llm_client, "health_check", None)
                    if callable(health_check):
                        candidate.artifacts["llm_review_runtime"] = health_check()
                    review = review_context_candidates_with_llm(
                        candidate.translation_text,
                        list(context_candidates),
                        llm_client=llm_client,
                        compound_evidence_packet=compound_packet,
                    )
                except Exception as exc:  # noqa: BLE001
                    self._emit_progress_event(
                        "worker_stage_failed",
                        subphase="llm_context_review",
                        status="failed",
                        metrics={"error_type": type(exc).__name__},
                    )
                    raise
                self._augment_direct_review_with_compound_evidence(candidate, review)
                candidate.artifacts["llm_review"] = review
                self._record_fulltext_compound_evidence_review_gap(candidate, review)
                review_context_id = str(review.get("best_context_id") or "")
                selected = candidate_by_id.get(review_context_id) or selected
                self._emit_progress_event(
                    "worker_stage_completed",
                    subphase="llm_context_review",
                    status=str(review.get("decision") or "completed"),
                    metrics={
                        "provider": review.get("provider") or "",
                        "model": review.get("model") or "",
                        "best_context_id": review_context_id,
                        "confidence": review.get("confidence"),
                        "supporting_context_count": len(review.get("supporting_context_ids") or []),
                    },
                )
        candidate.artifacts["fulltext_selected_context_id"] = selected.get("context_id")
        candidate.artifacts["fulltext_selected_lead_category"] = selected.get("lead_category")
        candidate.matched_japanese = str(selected.get("cleaned_context") or selected.get("expanded_context") or "")
        try:
            candidate.matched_page = int(selected.get("pdf_page"))
        except (TypeError, ValueError):
            candidate.matched_page = None
        return selected

    def _fulltext_context_expansion_limit(self, candidate: CitationCandidate) -> int:
        resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
        source_graph = candidate.artifacts.get("source_graph") or {}
        source_type = ""
        if isinstance(resolver_plan, dict):
            source_type = str(resolver_plan.get("source_type") or "")
        if not source_type and isinstance(source_graph, dict):
            source_type = str(source_graph.get("source_type") or "")
        if source_type == "volume_series":
            return 8
        if source_type == "diary":
            return 5
        return 3

    def _probe_target_pid_fulltext_hints(
        self,
        candidate: CitationCandidate,
        match: NDLSearchMatch,
    ) -> None:
        ndl_id = str(getattr(match, "ndl_id", "") or "")
        if not ndl_id:
            return
        existing_probes = candidate.artifacts.get("target_pid_fulltext_probes") or []
        if isinstance(existing_probes, list):
            for probe in existing_probes:
                if not isinstance(probe, dict):
                    continue
                if str(probe.get("pid") or "") != ndl_id:
                    continue
                try:
                    hit_count = int(probe.get("hit_count") or 0)
                except (TypeError, ValueError):
                    hit_count = 0
                if hit_count <= 0:
                    continue
                if "target_pid_fulltext_probe_reused" not in candidate.notes:
                    candidate.notes.append("target_pid_fulltext_probe_reused")
                self._emit_progress_event(
                    "worker_stage_completed",
                    subphase="target_pid_fulltext_probe",
                    status="reused",
                    metrics={"pid": ndl_id, "hit_count": hit_count},
                )
                return
        keywords: List[str] = []
        resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
        target_pid_queries: List[str] = []
        bucket_keywords: List[str] = []
        if isinstance(resolver_plan, dict):
            if resolver_plan.get("source_level_cache_key"):
                candidate.artifacts["source_level_cache_key"] = resolver_plan.get("source_level_cache_key")
            for item in resolver_plan.get("target_pid_queries") or []:
                cleaned = str(item or "").strip()
                if cleaned and cleaned not in target_pid_queries:
                    target_pid_queries.append(cleaned)
            query_buckets = resolver_plan.get("query_buckets") or {}
            if isinstance(query_buckets, dict):
                for bucket_name in (
                    "document_heading",
                    "policy",
                    "person",
                    "anchor",
                    "theme",
                    "action",
                    "page_near",
                    "document_title",
                    "special_term",
                ):
                    for item in query_buckets.get(bucket_name) or []:
                        cleaned = str(item or "").strip()
                        if cleaned and cleaned not in bucket_keywords:
                            bucket_keywords.append(cleaned)
        claim_queries = self._claim_fulltext_queries(candidate)
        tail_queries = [
            getattr(candidate.footnote, "contained_title", ""),
            getattr(candidate.footnote, "title", ""),
            getattr(candidate.footnote, "host_title", ""),
            *self._iter_ndl_search_keywords(candidate.footnote),
        ]

        def add_keyword(item: Any) -> None:
            cleaned = str(item or "").strip()
            if self._is_diary_source(candidate) and self._date_query_is_publication_year_only(candidate, cleaned):
                return
            if cleaned and cleaned not in keywords:
                keywords.append(cleaned)

        # Keep a small source-title anchor, then prioritize claim/document terms.
        # Long title variant lists can otherwise crowd out quote-level probes.
        for item in target_pid_queries[:4]:
            add_keyword(item)
        for item in self._diary_date_queries(candidate):
            add_keyword(item)
        for item in self._diary_claim_fulltext_queries(candidate):
            add_keyword(item)
        for item in [*bucket_keywords, *claim_queries, *target_pid_queries[4:], *tail_queries]:
            add_keyword(item)
        strict_ids = self._strict_resolver_known_pid_scope(candidate)
        query_limit = 24 if (self._fulltext_context_expansion_limit(candidate) > 3 or ndl_id in strict_ids) else 10
        probe_keywords = keywords[:query_limit]
        self._emit_progress_event(
            "worker_stage_started",
            subphase="target_pid_fulltext_probe",
            metrics={"pid": ndl_id, "query_count": len(probe_keywords)},
        )
        try:
            probe = probe_ndl_fulltext_context(ndl_id, probe_keywords)
        except Exception as exc:  # noqa: BLE001
            candidate.notes.append(f"ndl_digital_target_fulltext_failed:{type(exc).__name__}")
            self._emit_progress_event(
                "worker_stage_failed",
                subphase="target_pid_fulltext_probe",
                status="failed",
                metrics={"pid": ndl_id, "error_type": type(exc).__name__},
            )
            return
        hit_artifacts = [self._fulltext_hit_to_artifact(hit) for hit in getattr(probe, "hits", [])]
        hit_artifacts.sort(
            key=lambda hint: (
                not self._hint_is_specific_fulltext_evidence(candidate, hint),
                -self._fulltext_hint_specificity_score(candidate, hint),
                not bool(hint.get("pdf_page")),
            )
        )
        pdf_pages: List[int] = []
        for hint in hit_artifacts:
            try:
                page = int(hint.get("pdf_page") or 0)
            except (TypeError, ValueError):
                continue
            if page > 0 and page not in pdf_pages:
                pdf_pages.append(page)
        probe_record = {
            "pid": getattr(probe, "pid", ndl_id),
            "title": getattr(probe, "title", ""),
            "status": getattr(probe, "status", ""),
            "hit_count": len(hit_artifacts),
            "specific_hit_count": sum(
                1 for hint in hit_artifacts if self._hint_is_specific_fulltext_evidence(candidate, hint)
            ),
            "pdf_page_hit_count": sum(1 for hint in hit_artifacts if hint.get("pdf_page")),
            "first_pdf_pages": pdf_pages[:5],
            "queries_tried": list(getattr(probe, "queries_tried", []) or []),
            "note": getattr(probe, "note", ""),
        }
        strict_ids = self._strict_resolver_known_pid_scope(candidate)
        metadata = getattr(match, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            metadata = {}
        if strict_ids and ndl_id not in strict_ids:
            probe_record["skipped_as_target"] = True
            probe_record["skip_reason"] = "non_equivalent_fulltext_lead"
            skipped = candidate.artifacts.setdefault("non_equivalent_fulltext_probes", [])
            if isinstance(skipped, list) and not any(
                isinstance(item, dict) and item.get("pid") == probe_record.get("pid")
                for item in skipped
            ):
                skipped.append(probe_record)
            if "target_pid_probe_skipped_non_equivalent_fulltext_lead" not in candidate.notes:
                candidate.notes.append("target_pid_probe_skipped_non_equivalent_fulltext_lead")
            self._emit_progress_event(
                "worker_stage_completed",
                subphase="target_pid_fulltext_probe",
                status="skipped_non_equivalent",
                metrics={
                    "pid": ndl_id,
                    "hit_count": int(probe_record.get("hit_count") or 0),
                    "specific_hit_count": int(probe_record.get("specific_hit_count") or 0),
                    "pdf_page_hit_count": int(probe_record.get("pdf_page_hit_count") or 0),
                },
            )
            return
        probes = candidate.artifacts.setdefault("target_pid_fulltext_probes", [])
        if isinstance(probes, list):
            probes[:] = [
                item
                for item in probes
                if not isinstance(item, dict) or item.get("pid") != probe_record.get("pid")
            ]
            probes.append(probe_record)

        def probe_rank(item: Dict[str, Any]) -> Tuple[int, int, int, int]:
            return (
                1 if item.get("status") == "direct_hit" else 0,
                int(item.get("specific_hit_count") or 0),
                int(item.get("hit_count") or 0),
                int(item.get("pdf_page_hit_count") or 0),
            )

        current_probe = candidate.artifacts.get("ndl_fulltext_probe")
        current_pid = str(current_probe.get("pid") or "") if isinstance(current_probe, dict) else ""
        if (
            not isinstance(current_probe, dict)
            or (strict_ids and current_pid not in strict_ids)
            or probe_rank(probe_record) > probe_rank(current_probe)
        ):
            candidate.artifacts["ndl_fulltext_probe"] = probe_record
        self._record_diary_date_lookup_diagnostic(candidate, ndl_id=ndl_id, hit_artifacts=hit_artifacts)
        self._record_contained_document_lookup_diagnostic(candidate, ndl_id=ndl_id, hit_artifacts=hit_artifacts)
        if getattr(probe, "status", "") != "direct_hit":
            self._emit_progress_event(
                "worker_stage_completed",
                subphase="target_pid_fulltext_probe",
                status=str(getattr(probe, "status", "") or "no_direct_hit"),
                metrics={
                    "pid": ndl_id,
                    "hit_count": int(probe_record.get("hit_count") or 0),
                    "specific_hit_count": int(probe_record.get("specific_hit_count") or 0),
                    "pdf_page_hit_count": int(probe_record.get("pdf_page_hit_count") or 0),
                },
            )
            return
        stored = candidate.artifacts.setdefault("ndl_fulltext_hints", [])
        if not isinstance(stored, list):
            candidate.artifacts["ndl_fulltext_hints"] = stored = []
        for hint in hit_artifacts[:12]:
            if not any(
                isinstance(item, dict)
                and item.get("snippet") == hint.get("snippet")
                and item.get("pdf_page") == hint.get("pdf_page")
                for item in stored
            ):
                stored.append(hint)
        if stored and "ndl_digital_target_fulltext_hit" not in candidate.notes:
            candidate.notes.append("ndl_digital_target_fulltext_hit")
        self._emit_progress_event(
            "worker_stage_completed",
            subphase="target_pid_fulltext_probe",
            status="direct_hit",
            metrics={
                "pid": ndl_id,
                "hit_count": int(probe_record.get("hit_count") or 0),
                "specific_hit_count": int(probe_record.get("specific_hit_count") or 0),
                "pdf_page_hit_count": int(probe_record.get("pdf_page_hit_count") or 0),
            },
        )

    def _rerank_matches_for_candidate_fulltext(self, candidate: CitationCandidate) -> None:
        if not candidate.ndl_matches:
            return
        strict_ids = self._strict_resolver_known_pid_scope(candidate)
        resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
        source_graph = candidate.artifacts.get("source_graph") or {}
        if not isinstance(resolver_plan, dict):
            resolver_plan = {}
        if not isinstance(source_graph, dict):
            source_graph = {}
        strict_order: Dict[str, int] = {}
        for pid in [
            *(resolver_plan.get("known_pid_candidates") or []),
            *(source_graph.get("known_pid_candidates") or []),
        ]:
            pid_text = str(pid or "")
            if pid_text and pid_text not in strict_order:
                strict_order[pid_text] = len(strict_order)
        if strict_ids:
            existing_ids = {
                str(getattr(match, "ndl_id", "") or getattr(match, "platform_item_id", "") or "")
                for match in candidate.ndl_matches
            }
            injected: List[str] = []
            strict_existing_ids = {pid for pid in strict_ids if pid in existing_ids}
            first_strict_pid = next((pid for pid in strict_order if pid in strict_ids), next(iter(strict_ids), ""))
            for pid in ([] if strict_existing_ids or not first_strict_pid else [first_strict_pid]):
                candidate.ndl_matches.append(
                    NDLSearchMatch(
                        title=str(candidate.footnote.title or candidate.footnote.host_title or "NDL Digital"),
                        url=f"https://dl.ndl.go.jp/pid/{pid}",
                        ndl_id=pid,
                        platform="ndl",
                        score=1.0,
                        metadata={
                            "search_route": "resolver_config_known_pid",
                            "known_pid_candidate": True,
                            "injected_for_strict_pid_scope": True,
                        },
                    )
                )
                injected.append(pid)
                existing_ids.add(pid)
            if injected:
                candidate.artifacts["strict_resolver_pid_candidates_injected"] = injected
                note = "strict_resolver_pid_candidate_injected"
                if note not in candidate.notes:
                    candidate.notes.append(note)

        def strict_match_order(match: NDLSearchMatch) -> Tuple[int, int, int]:
            ndl_id = str(getattr(match, "ndl_id", "") or getattr(match, "platform_item_id", "") or "")
            metadata = getattr(match, "metadata", {}) or {}
            try:
                rank = int(metadata.get("source_rank") or 9999) if isinstance(metadata, dict) else 9999
            except (TypeError, ValueError):
                rank = 9999
            return (
                0 if strict_ids and ndl_id in strict_ids else 1,
                strict_order.get(ndl_id, 9999),
                rank,
            )

        matches_for_probe = sorted(candidate.ndl_matches, key=strict_match_order) if strict_ids else candidate.ndl_matches
        for match in matches_for_probe:
            if getattr(match, "platform", "ndl") != "ndl":
                continue
            ndl_id = str(getattr(match, "ndl_id", "") or getattr(match, "platform_item_id", "") or "")
            if strict_ids and ndl_id not in strict_ids:
                continue
            self._store_ndl_fulltext_hints(candidate, match)
            if strict_ids:
                self._probe_target_pid_fulltext_hints(candidate, match)
                current_probe = candidate.artifacts.get("ndl_fulltext_probe") or {}
                if (
                    isinstance(current_probe, dict)
                    and str(current_probe.get("pid") or "") == ndl_id
                    and current_probe.get("status") == "direct_hit"
                    and int(current_probe.get("specific_hit_count") or 0) > 0
                ):
                    break
                continue
            if any(
                self._hint_is_specific_fulltext_evidence(candidate, hint)
                for hint in self._ordered_fulltext_hints_for_candidate(candidate, preferred_pid=ndl_id)
            ):
                continue
            self._probe_target_pid_fulltext_hints(candidate, match)

        def match_score(match: NDLSearchMatch) -> float:
            ndl_id = str(getattr(match, "ndl_id", "") or getattr(match, "platform_item_id", "") or "")
            score = float(getattr(match, "score", 0.0) or 0.0)
            footnote_year = str(getattr(candidate.footnote, "year", "") or "")
            record_year_text = str(getattr(match, "date", "") or "")
            footnote_year_match = re.search(r"(?:18|19|20)\d{2}", footnote_year)
            record_year_match = re.search(r"(?:18|19|20)\d{2}", record_year_text)
            if footnote_year_match and record_year_match:
                if footnote_year_match.group(0) == record_year_match.group(0):
                    score += 0.55
                else:
                    score -= 0.45
            footnote_publisher = normalize_match_text(str(getattr(candidate.footnote, "publisher", "") or ""))
            record_publisher = normalize_match_text(
                " ".join(
                    str(value or "")
                    for value in [
                        getattr(match, "publisher", ""),
                        getattr(match, "author", ""),
                        getattr(match, "title", ""),
                    ]
                )
            )
            if footnote_publisher and record_publisher:
                if footnote_publisher in record_publisher:
                    score += 0.45
                elif len(footnote_publisher) >= 3:
                    score -= 0.2
            best_hint_bonus = 0.0
            for hint in self._ordered_fulltext_hints_for_candidate(candidate):
                hint_source = str(hint.get("book_id") or hint.get("pid") or "")
                if ndl_id and hint_source and hint_source != ndl_id:
                    continue
                if not self._hint_is_specific_fulltext_evidence(candidate, hint):
                    continue
                hint_bonus = 1.0
                query = normalize_match_text(str(hint.get("query") or ""))
                snippet = normalize_match_text(str(hint.get("snippet") or ""))
                if "民ヲ安ズル" in query or "民ヲ安ズル" in snippet:
                    hint_bonus += 0.8
                if "門戸開放" in query or "門戶開放" in snippet:
                    hint_bonus += 0.5
                if hint.get("pdf_page"):
                    hint_bonus += 0.1
                best_hint_bonus = max(best_hint_bonus, hint_bonus)
            score += best_hint_bonus
            return score

        candidate.ndl_matches.sort(
            key=lambda match: (
                bool(getattr(match, "metadata", {}).get("source_mismatch")),
                -match_score(match),
                int(getattr(match, "metadata", {}).get("source_rank") or 9999),
            )
        )

    def _expand_first_fulltext_hint(self, candidate: CitationCandidate, *, preferred_pid: str = "") -> None:
        for hint in self._ordered_fulltext_hints_for_candidate(candidate, preferred_pid=preferred_pid):
            if hint.get("expanded_context"):
                continue
            pid = str(hint.get("pid") or hint.get("book_id") or "")
            snippet = str(hint.get("snippet") or "")
            if not pid or not snippet:
                continue
            try:
                pdf_page = int(hint.get("pdf_page")) if hint.get("pdf_page") is not None else None
            except (TypeError, ValueError):
                pdf_page = None
            seed = NDLFulltextHit(
                pid=pid,
                query=str(hint.get("query") or ""),
                snippet=snippet,
                pdf_page=pdf_page,
                cid=str(hint.get("cid") or ""),
                content_index=hint.get("content_index"),
                mode="SNIPPET",
                page_basis=str(hint.get("page_basis") or "dl_ndl_fulltext_content_index"),
            )
            try:
                expanded = expand_ndl_snippet_context(pid, seed, max_rounds=2)
            except Exception as exc:  # noqa: BLE001
                hint["expanded_context_status"] = "expand_failed"
                hint["expanded_context_error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
                return
            context_text = getattr(expanded, "context_text", "") or ""
            if context_text:
                hint["expanded_context"] = context_text
                hint["expanded_context_status"] = getattr(expanded, "status", "snippet_expanded")
                hint["expanded_context_note"] = getattr(expanded, "note", "")
                hint["expanded_context_evidence_count"] = len(getattr(expanded, "evidence_hits", []) or [])
                candidate.artifacts["fulltext_only_context"] = context_text
                return

    def _mark_fulltext_only_hit_if_possible(
        self,
        candidate: CitationCandidate,
        *,
        output_dir: Optional[Path] = None,
        max_context_candidates: Optional[int] = None,
        max_hints_to_expand: Optional[int] = None,
        max_expand_rounds: int = 2,
    ) -> bool:
        self._rerank_matches_for_candidate_fulltext(candidate)
        strict_ids = self._strict_resolver_known_pid_scope(candidate)
        for match in candidate.ndl_matches or []:
            if getattr(match, "platform", "ndl") != "ndl":
                continue
            ndl_id = str(getattr(match, "ndl_id", "") or getattr(match, "platform_item_id", "") or "")
            if strict_ids and ndl_id not in strict_ids:
                continue
            self._store_ndl_fulltext_hints(candidate, match)
            self._probe_target_pid_fulltext_hints(candidate, match)
            context_limit = (
                max(1, int(max_context_candidates))
                if max_context_candidates is not None
                else self._fulltext_context_expansion_limit(candidate)
            )
            hint_limit = (
                max(1, int(max_hints_to_expand))
                if max_hints_to_expand is not None
                else self._fulltext_context_expansion_limit(candidate)
            )
            context_candidates = self._expand_fulltext_context_candidates(
                candidate,
                preferred_pid=ndl_id,
                max_candidates=context_limit,
                max_hints_to_expand=hint_limit,
                max_expand_rounds=max_expand_rounds,
                cache_dir=output_dir,
            )
            if not context_candidates:
                continue
            body_context = next(
                (item for item in context_candidates if item.get("lead_category") == "body_candidate"),
                None,
            )
            if body_context is None:
                candidate.verification_status = "fulltext_lead_only"
                candidate.support_status = "fulltext_lead_only"
                candidate.support_reason = (
                    "NDL Digital SNIPPET only produced title/index or loose leads; "
                    "it is not yet quote-level evidence."
                )
                candidate.evidence_scope = "ndl_fulltext_lead"
                candidate.artifacts["fulltext_lead_only"] = True
                candidate.artifacts["evidence_level"] = "lead"
                candidate.artifacts["fulltext_lead_category"] = context_candidates[0].get("lead_category")
                if "fulltext_lead_only" not in candidate.notes:
                    candidate.notes.append("fulltext_lead_only")
                return True
            candidate.verification_status = "fulltext_only_hit"
            candidate.support_status = "fulltext_only_hit"
            candidate.support_reason = "NDL Digital target-PID SNIPPET provides weak page/context evidence; no OCR PDF was acquired."
            candidate.evidence_scope = "ndl_fulltext_snippet"
            candidate.artifacts["fulltext_only_hit"] = True
            candidate.artifacts["evidence_level"] = "weak"
            candidate.artifacts["fulltext_llm_review_basis"] = "ndl_expanded_snippet_context_candidates"
            selected_context = self._select_fulltext_context_candidate(candidate, context_candidates)
            if selected_context:
                self._apply_fulltext_only_review_status(candidate)
            if "fulltext_only_hit" not in candidate.notes:
                candidate.notes.append("fulltext_only_hit")
            return True
        return False

    def _fulltext_pdf_page_fallback_plan(
        self,
        candidate: CitationCandidate,
        top_match: NDLSearchMatch,
        *,
        page_window: int,
        specific_only: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Use NDL fulltext PDF page hints as a weak download window fallback.

        This does not claim that the PDF page is the cited book page. It only
        prevents PDF refinement from stopping before OCR when NDL exposes a
        same-PID snippet page but front-matter page mapping failed.
        """

        self._store_ndl_fulltext_hints(candidate, top_match)
        self._probe_target_pid_fulltext_hints(candidate, top_match)
        ndl_id = str(getattr(top_match, "ndl_id", None) or "")
        hints = self._ordered_fulltext_hints_for_candidate(candidate, preferred_pid=ndl_id)
        for hint in hints:
            if specific_only and not self._hint_is_specific_fulltext_evidence(candidate, hint):
                continue
            hint_source = str(hint.get("book_id") or hint.get("pid") or "")
            if ndl_id and hint_source and hint_source != ndl_id:
                continue
            try:
                pdf_page = int(hint.get("pdf_page") or 0)
            except (TypeError, ValueError):
                continue
            if pdf_page <= 0:
                continue
            pages = [page for page in self._expand_page_window(pdf_page, page_window) if page >= 1]
            if not pages:
                continue
            fallback_plan = {
                "start_page": min(pages),
                "end_page": max(pages),
                "mapped_footnote_pages": [pdf_page],
                "page_mapping": None,
                "note": f"fulltext_pdf_page_fallback_used:pdf_page={pdf_page}",
            }
            specific = self._hint_is_specific_fulltext_evidence(candidate, hint)
            fallback_artifact = {
                "ndl_id": ndl_id or hint_source,
                "pdf_page": pdf_page,
                "query": hint.get("query") or hint.get("keyword") or "",
                "cid": hint.get("cid") or "",
                "page_basis": hint.get("page_basis") or "",
                "specific": specific,
            }
            attempts = candidate.artifacts.setdefault("fulltext_pdf_page_fallback_attempts", [])
            if isinstance(attempts, list) and not any(
                isinstance(item, dict)
                and item.get("ndl_id") == fallback_artifact["ndl_id"]
                and item.get("pdf_page") == pdf_page
                and item.get("query") == fallback_artifact["query"]
                for item in attempts
            ):
                attempts.append(dict(fallback_artifact))
            existing = candidate.artifacts.get("fulltext_pdf_page_fallback")
            if not isinstance(existing, dict) or (specific and not existing.get("specific")):
                candidate.artifacts["fulltext_pdf_page_fallback"] = fallback_artifact
            return fallback_plan
        return None

    def _diary_date_pdf_page_fallback_plan(
        self,
        candidate: CitationCandidate,
        top_match: NDLSearchMatch,
        *,
        page_window: int,
    ) -> Optional[Dict[str, Any]]:
        """Use diary date snippets as routing hints, not as support evidence."""

        if not self._is_diary_source(candidate):
            return None
        date_queries = self._diary_date_queries(candidate)
        if not date_queries:
            return None
        self._store_ndl_fulltext_hints(candidate, top_match)
        self._probe_target_pid_fulltext_hints(candidate, top_match)
        ndl_id = str(getattr(top_match, "ndl_id", None) or getattr(top_match, "platform_item_id", None) or "")
        hints = self._ordered_fulltext_hints_for_candidate(candidate, preferred_pid=ndl_id)
        route_candidates: List[Dict[str, Any]] = []
        lead_rank = {
            "body_candidate": 0,
            "short_or_unexpanded": 1,
            "title_or_series_only": 2,
            "toc_or_index": 3,
            "wrong_pid": 4,
        }
        for hint in hints:
            hint_source = str(hint.get("book_id") or hint.get("pid") or "")
            if ndl_id and hint_source and hint_source != ndl_id:
                continue
            try:
                pdf_page = int(hint.get("pdf_page") or 0)
            except (TypeError, ValueError):
                continue
            if pdf_page <= 0:
                continue
            match_scope = self._diary_date_hint_match_scope(candidate, hint)
            if not match_scope:
                continue
            lead_category = self._fulltext_hint_lead_category(candidate, hint)
            score = 0.0
            if match_scope == "query_and_snippet":
                score += 5.0
            elif match_scope == "snippet":
                score += 4.0
            else:
                score += 1.0
            if lead_category == "body_candidate":
                score += 3.0
            elif lead_category == "short_or_unexpanded":
                score += 1.0
            elif lead_category == "title_or_series_only":
                score -= 1.0
            elif lead_category == "toc_or_index":
                score -= 2.0
            if self._hint_has_claim_snippet_evidence(candidate, hint):
                score += 2.0
            diary_packet = self._diary_claim_facet_packet(
                candidate,
                " ".join(str(hint.get(key) or "") for key in ("query", "snippet", "expanded_context")),
            )
            if diary_packet:
                score += float(diary_packet.get("score_bonus") or 0)
            if pdf_page > 12:
                score += 0.25
            snippet = self._clean_fulltext_context_text(
                " ".join(str(hint.get(key) or "") for key in ("snippet", "expanded_context"))
            )
            route_candidates.append(
                {
                    "ndl_id": ndl_id or hint_source,
                    "pdf_page": pdf_page,
                    "query": hint.get("query") or hint.get("keyword") or "",
                    "cid": hint.get("cid") or "",
                    "page_basis": hint.get("page_basis") or "",
                    "lead_category": lead_category,
                    "match_scope": match_scope,
                    "score": round(score, 3),
                    "claim_facets": diary_packet.get("covered_facets", []) if diary_packet else [],
                    "snippet": snippet[:360],
                    "evidence_level": "routing_only_until_ocr_llm_review",
                }
            )
        if not route_candidates:
            return None
        route_candidates.sort(
            key=lambda item: (
                -float(item.get("score") or 0),
                lead_rank.get(str(item.get("lead_category") or ""), 5),
                int(item.get("pdf_page") or 0),
            )
        )
        selected = route_candidates[0]
        pdf_page = int(selected["pdf_page"])
        pages = [page for page in self._expand_page_window(pdf_page, page_window) if page >= 1]
        if not pages:
            return None
        artifact = {
            "ndl_id": selected.get("ndl_id") or ndl_id,
            "date_queries": date_queries[:10],
            "selected_pdf_page": pdf_page,
            "selected_query": selected.get("query") or "",
            "selected_match_scope": selected.get("match_scope") or "",
            "selected_lead_category": selected.get("lead_category") or "",
            "top_candidates": route_candidates[:5],
            "cited_book_pages": list(candidate.footnote.page_numbers or []),
            "start_page": min(pages),
            "end_page": max(pages),
            "page_window": page_window,
            "evidence_level": "routing_only_until_ocr_llm_review",
            "reason": "diary_date_fulltext_page_hint_before_book_page_assumption",
        }
        candidate.artifacts["diary_date_pdf_page_fallback"] = artifact
        attempts = candidate.artifacts.setdefault("diary_date_pdf_page_fallback_attempts", [])
        if isinstance(attempts, list):
            attempts[:] = route_candidates[:8]
        note = f"diary_date_pdf_page_fallback_used:pdf_page={pdf_page}"
        return {
            "start_page": min(pages),
            "end_page": max(pages),
            "mapped_footnote_pages": [pdf_page],
            "page_mapping": None,
            "note": note,
        }

    def _known_pid_page_window_fallback_plan(
        self,
        candidate: CitationCandidate,
        top_match: NDLSearchMatch,
        *,
        page_window: int,
    ) -> Optional[Dict[str, Any]]:
        """Allow a small diagnostic OCR window for strict known-PID sources.

        Diary citations and contained documents can resolve to a trusted NDL
        PID while target-PID snippets still expose only a title/index lead. In
        that narrow case we can try a small cited-page window, but it remains
        weak routing evidence until OCR and Gemma review confirm the passage.
        """

        page_numbers: List[int] = []
        for page in candidate.footnote.page_numbers or []:
            try:
                page_number = int(page)
            except (TypeError, ValueError):
                continue
            if page_number > 0:
                page_numbers.append(page_number)
        if not page_numbers:
            return None
        resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
        source_graph = candidate.artifacts.get("source_graph") or {}
        if not isinstance(resolver_plan, dict):
            resolver_plan = {}
        if not isinstance(source_graph, dict):
            source_graph = {}
        source_type = str(resolver_plan.get("source_type") or source_graph.get("source_type") or "")
        allowed_source_types = {"diary", "contained_document"}
        if source_type not in allowed_source_types:
            return None
        ndl_id = str(getattr(top_match, "ndl_id", "") or getattr(top_match, "platform_item_id", "") or "")
        metadata = getattr(top_match, "metadata", {}) or {}
        known_pids = {
            str(pid)
            for pid in [
                *(resolver_plan.get("known_pid_candidates") or []),
                *(source_graph.get("known_pid_candidates") or []),
            ]
            if str(pid or "")
        }
        if not ndl_id or (ndl_id not in known_pids and not metadata.get("known_pid_candidate")):
            return None
        bounded_window = max(1, min(int(page_window or 1), 2))
        page_span = max(page_numbers) - min(page_numbers)
        max_safe_span = bounded_window * 2 + 4
        if len(set(page_numbers)) > 1 and page_span > max_safe_span:
            artifact = {
                "ndl_id": ndl_id,
                "source_type": source_type,
                "known_pid_candidates": sorted(known_pids),
                "cited_book_pages": page_numbers,
                "page_window": bounded_window,
                "reason": "distributed_pages_would_make_large_window",
                "page_span": page_span,
                "max_safe_span": max_safe_span,
                "evidence_level": "diagnostic_skipped_before_ocr",
            }
            candidate.artifacts["known_pid_page_window_fallback_skipped"] = artifact
            candidate.notes.append(
                f"known_pid_page_window_fallback_skipped[{ndl_id}]:distributed_pages_would_make_large_window"
            )
            return None
        start_page = max(1, min(page_numbers) - bounded_window)
        end_page = max(page_numbers) + bounded_window
        basis_by_type = {
            "diary": "known_pid_date_to_volume_without_snippet_or_page_mapping",
            "contained_document": "known_document_pid_without_snippet_or_page_mapping",
        }
        artifact = {
            "ndl_id": ndl_id,
            "source_type": source_type,
            "known_pid_candidates": sorted(known_pids),
            "cited_book_pages": page_numbers,
            "start_page": start_page,
            "end_page": end_page,
            "page_window": bounded_window,
            "basis": basis_by_type.get(source_type, "known_pid_without_snippet_or_page_mapping"),
            "evidence_level": "diagnostic_until_ocr_llm_review",
        }
        candidate.artifacts["known_pid_page_window_fallback"] = artifact
        note_prefix = "diary" if source_type == "diary" else "contained_document"
        return {
            "start_page": start_page,
            "end_page": end_page,
            "mapped_footnote_pages": [],
            "page_mapping": None,
            "note": f"{note_prefix}_known_pid_page_window_fallback_used:book_pages={','.join(str(page) for page in page_numbers)}",
        }

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

    def _strict_resolver_known_pid_scope(self, candidate: CitationCandidate) -> set[str]:
        resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
        source_graph = candidate.artifacts.get("source_graph") or {}
        if not isinstance(resolver_plan, dict):
            resolver_plan = {}
        if not isinstance(source_graph, dict):
            source_graph = {}
        source_type = str(resolver_plan.get("source_type") or source_graph.get("source_type") or "")
        if source_type not in {"contained_document", "diary", "volume_series", "source_collection", "downloadable_monograph"}:
            return set()
        return {
            str(pid)
            for pid in [
                *(resolver_plan.get("known_pid_candidates") or []),
                *(source_graph.get("known_pid_candidates") or []),
            ]
            if str(pid or "")
        }

    def _strict_equivalent_source_ids(self, candidate: CitationCandidate) -> set[str]:
        source_ids = self._strict_resolver_known_pid_scope(candidate)
        equivalent_group = candidate.artifacts.get("equivalent_pid_group") or []
        if isinstance(equivalent_group, list):
            for item in equivalent_group:
                if not isinstance(item, dict):
                    continue
                source_id = str(item.get("ndl_id") or item.get("source_id") or item.get("pid") or "")
                if source_id and item.get("scope") != "global_fulltext_lead_not_equivalent":
                    source_ids.add(source_id)
        return source_ids

    def _fulltext_lead_source_ids(self, candidate: CitationCandidate) -> set[str]:
        fulltext_leads = candidate.artifacts.get("fulltext_lead_pid_group") or []
        if not isinstance(fulltext_leads, list):
            return set()
        return {
            str(item.get("ndl_id") or item.get("source_id") or item.get("pid") or "")
            for item in fulltext_leads
            if isinstance(item, dict) and str(item.get("ndl_id") or item.get("source_id") or item.get("pid") or "")
        }

    def _is_non_equivalent_fulltext_lead(self, candidate: CitationCandidate, match: NDLSearchMatch) -> bool:
        source_id = self._match_identity(match)
        if not source_id:
            return False
        strict_ids = self._strict_equivalent_source_ids(candidate)
        if not strict_ids:
            return False
        if source_id in strict_ids:
            return False
        if source_id in self._fulltext_lead_source_ids(candidate):
            return True
        metadata = getattr(match, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            return False
        routes = {str(route) for route in (metadata.get("search_routes") or []) if route}
        route = str(metadata.get("search_route") or "")
        if route:
            routes.add(route)
        return bool(metadata.get("claim_fulltext_global_recheck")) or any("fulltext" in route for route in routes)

    def _filter_non_equivalent_fulltext_leads(
        self,
        candidate: CitationCandidate,
        matches: Sequence[NDLSearchMatch],
        *,
        note: str,
    ) -> List[NDLSearchMatch]:
        kept: List[NDLSearchMatch] = []
        removed: List[str] = []
        for match in matches:
            if self._is_non_equivalent_fulltext_lead(candidate, match):
                removed.append(self._match_identity(match))
            else:
                kept.append(match)
        if removed:
            candidate.artifacts["non_equivalent_fulltext_lead_skipped_ids"] = sorted(set(removed))
            if note not in candidate.notes:
                candidate.notes.append(note)
        return kept

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
        remaining = self._filter_non_equivalent_fulltext_leads(
            candidate,
            remaining,
            note="alternate_source_retry_skipped_non_equivalent_fulltext_lead",
        )
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
            if self._is_non_equivalent_fulltext_lead(candidate, match):
                continue
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
                "llm_review": candidate.artifacts.get("llm_review"),
                "llm_review_runtime": candidate.artifacts.get("llm_review_runtime"),
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
            "llm_review",
            "llm_review_runtime",
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
            "llm_review",
            "llm_review_runtime",
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
            cached = self._load_source_level_page_mapping_cache(
                candidate,
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
                self._save_page_mapping_cache(
                    output_dir,
                    str(ndl_id),
                    cached,
                    source_level_cache_key=self._source_level_cache_key_for_candidate(candidate),
                )
        if not cached:
            return None
        source_level_cache_key = self._source_level_cache_key_for_candidate(candidate)
        source_cache_id = self._source_level_page_mapping_cache_id(source_level_cache_key)
        if source_cache_id and source_cache_id not in self._page_mapping_cache:
            self._save_page_mapping_cache(
                output_dir,
                str(ndl_id),
                cached,
                source_level_cache_key=source_level_cache_key,
            )

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
            message = str(exc)
            candidate.verification_status = "download_failed"
            candidate.notes.append(message)
            planned_range = candidate.artifacts.pop("downloaded_page_range", None)
            if planned_range:
                candidate.artifacts["download_planned_page_range"] = planned_range
            normalized_error = self._normalize_download_unavailability_reason(message)
            if normalized_error:
                first_match = candidate.ndl_matches[0] if candidate.ndl_matches else None
                ndl_id = str(getattr(first_match, "ndl_id", "") or getattr(first_match, "platform_item_id", "") or "")
                candidate.artifacts["download_exception"] = {
                    "type": type(exc).__name__,
                    "reason": normalized_error,
                    "message": message,
                }
                self._mark_source_unavailable(
                    candidate,
                    reason=normalized_error,
                    ndl_id=ndl_id or None,
                    source_id=self._match_identity(first_match) if first_match is not None else None,
                    detail=message,
                )
            self._mark_fulltext_only_hit_if_possible(candidate, output_dir=output_dir)
            return

        if not pdf_path:
            if candidate.artifacts.get("page_mapping_required_but_unavailable"):
                candidate.verification_status = "page_mapping_unavailable"
                candidate.notes.append("source_pdf_not_downloaded_without_verified_page_mapping")
            else:
                candidate.verification_status = "download_failed"
                if candidate.artifacts.get("iiif_image_ocr_available") or candidate.artifacts.get("ndl_fulltext_json_available"):
                    candidate.verification_status = "iiif_image_ocr_available"
                    candidate.support_status = "iiif_image_ocr_available"
                    candidate.notes.append("source_pdf_not_available_but_iiif_image_ocr_available")
                    candidate.artifacts["source_pdf_availability"] = "iiif_or_fulltext_json_available"
                else:
                    candidate.notes.append("source_pdf_not_available")
            self._mark_fulltext_only_hit_if_possible(candidate, output_dir=output_dir)
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

        selected_source = candidate.artifacts.get("selected_source_match") or {}
        selected_ndl_id = str(selected_source.get("ndl_id") or selected_source.get("platform_item_id") or "")
        cached_ocr = (
            self._load_source_level_ocr_pages(
                candidate,
                output_dir=output_dir,
                ndl_id=selected_ndl_id,
                target_pages=target_pages,
                ocr_model=ocr_model,
                page_mapping=candidate.artifacts.get("page_mapping"),
            )
            if selected_ndl_id
            else None
        )
        used_source_level_ocr_cache = cached_ocr is not None
        if cached_ocr is not None:
            extracted_pages, page_label_mode = cached_ocr
        else:
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

        if not extracted_pages and not used_source_level_ocr_cache:
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
            page_label_mode = "scan"
        candidate.artifacts["subprocess_extracted_pages"] = [page for page, _text in extracted_pages]

        if not extracted_pages:
            candidate.verification_status = "ocr_failed"
            candidate.notes.append(
                "page_text_not_extracted"
                f" | readiness={candidate.artifacts.get('pdf_readiness', {}).get('status', 'unknown')}"
            )
            return

        if selected_ndl_id and not used_source_level_ocr_cache:
            self._save_source_level_ocr_pages(
                candidate,
                output_dir=output_dir,
                ndl_id=selected_ndl_id,
                ocr_model=ocr_model,
                extracted_pages=extracted_pages,
                page_label_mode=page_label_mode,
            )
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
        self._rerank_matches_for_candidate_fulltext(candidate)
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
                rerank_index = {
                    self._match_identity(match): index
                    for index, match in enumerate(candidate.ndl_matches)
                }
                matches_to_try.sort(
                    key=lambda match: (
                        not any(
                            self._hint_is_specific_fulltext_evidence(candidate, hint)
                            for hint in self._ordered_fulltext_hints_for_candidate(
                                candidate,
                                preferred_pid=str(
                                    getattr(match, "ndl_id", None)
                                    or getattr(match, "platform_item_id", None)
                                    or ""
                                ),
                            )
                        ),
                        rerank_index.get(self._match_identity(match), 9999),
                    )
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
        strict_filtered_matches = self._filter_non_equivalent_fulltext_leads(
            candidate,
            matches_to_try,
            note="source_match_non_equivalent_fulltext_lead_filtered",
        )
        if strict_filtered_matches:
            matches_to_try = strict_filtered_matches
        elif matches_to_try:
            candidate.artifacts["source_match_order"] = []
            candidate.notes.append("source_match_only_non_equivalent_fulltext_leads")
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
        if not public_pdf_path:
            for top_match in matches_to_try:
                self._probe_ndl_iiif_or_fulltext_json_availability(candidate, top_match)
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
                fulltext_fallback_plan: Optional[Dict[str, Any]] = None
                if platform is not None and platform.name == "ndl" and page_numbers and not mapping:
                    fulltext_fallback_plan = self._fulltext_pdf_page_fallback_plan(
                        candidate,
                        top_match,
                        page_window=page_window,
                        specific_only=True,
                    )
                diary_date_fallback_plan: Optional[Dict[str, Any]] = None
                if platform is not None and platform.name == "ndl" and page_numbers and not mapping and not fulltext_fallback_plan:
                    diary_date_fallback_plan = self._diary_date_pdf_page_fallback_plan(
                        candidate,
                        top_match,
                        page_window=page_window,
                    )
                if (
                    not mapping
                    and not fulltext_fallback_plan
                    and not diary_date_fallback_plan
                    and candidate.artifacts.get("ocr_backend_available", True)
                ):
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
                known_pid_page_window_plan: Optional[Dict[str, Any]] = None
                if (
                    platform is not None
                    and platform.name == "ndl"
                    and page_numbers
                    and not mapping
                    and not fulltext_fallback_plan
                    and not diary_date_fallback_plan
                ):
                    known_pid_page_window_plan = self._known_pid_page_window_fallback_plan(
                        candidate,
                        top_match,
                        page_window=page_window,
                    )
                if (
                    platform is not None
                    and platform.name == "ndl"
                    and page_numbers
                    and not mapping
                    and not fulltext_fallback_plan
                    and not diary_date_fallback_plan
                    and not known_pid_page_window_plan
                    and not candidate.artifacts.get("known_pid_page_window_fallback_skipped")
                ):
                    fulltext_fallback_plan = self._fulltext_pdf_page_fallback_plan(
                        candidate,
                        top_match,
                        page_window=page_window,
                        specific_only=False,
                    )
                if (
                    platform is not None
                    and platform.name == "ndl"
                    and page_numbers
                    and not mapping
                    and not fulltext_fallback_plan
                    and not diary_date_fallback_plan
                    and not known_pid_page_window_plan
                ):
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
                page_plan = fulltext_fallback_plan or diary_date_fallback_plan or known_pid_page_window_plan or build_download_page_plan(
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
                elif (fulltext_fallback_plan or diary_date_fallback_plan) and page_plan.get("mapped_footnote_pages"):
                    candidate.artifacts["mapped_footnote_pages"] = page_plan["mapped_footnote_pages"]
                elif known_pid_page_window_plan:
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
                    if known_pid_page_window_plan:
                        candidate.artifacts["known_pid_page_window_requires_page_mapping"] = {
                            "ndl_id": ndl_id,
                            "source_type": (
                                candidate.artifacts.get("known_pid_page_window_fallback") or {}
                            ).get("source_type"),
                            "cited_book_pages": (
                                candidate.artifacts.get("known_pid_page_window_fallback") or {}
                            ).get("cited_book_pages", []),
                            "planned_scan_window": [start_page, end_page],
                            "total_scan_pages": int(total_scan_pages),
                            "reason": "book_page_scan_page_assumption_out_of_range",
                        }
                        candidate.notes.append(
                            f"known_pid_page_window_requires_page_mapping[{ndl_id or candidate.footnote.title}]"
                        )
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
                dependency_status = self._restricted_download_dependency_status(module)
                if not dependency_status.get("available", False):
                    self._mark_restricted_download_dependency_missing(
                        candidate,
                        top_match=top_match,
                        status=dependency_status,
                    )
                    return None
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
                        normalized_error = self._normalize_download_unavailability_reason(str(error_message))
                        if normalized_error:
                            self._mark_source_unavailable(
                                candidate,
                                reason=normalized_error,
                                ndl_id=str(ndl_id) if ndl_id else None,
                                source_id=self._match_identity(top_match),
                                detail=str(error_message),
                            )
                        if (
                            normalized_error in {"remote_copy_only_no_print", "remote_copy_only", "print_disabled"}
                            and any(
                                self._hint_is_specific_fulltext_evidence(candidate, hint)
                                for hint in self._ordered_fulltext_hints_for_candidate(
                                    candidate,
                                    preferred_pid=str(ndl_id or ""),
                                )
                            )
                        ):
                            candidate.notes.append("restricted_download_stopped_after_specific_fulltext_unavailable")
                            return None
        planned_range = candidate.artifacts.pop("downloaded_page_range", None)
        if planned_range and not candidate.artifacts.get("download_attempt"):
            candidate.artifacts["download_planned_page_range"] = planned_range
        return None

    def _probe_ndl_iiif_or_fulltext_json_availability(
        self,
        candidate: CitationCandidate,
        match: Optional[NDLSearchMatch],
    ) -> bool:
        if match is None or getattr(match, "platform", "ndl") != "ndl":
            return False
        ndl_id = str(getattr(match, "ndl_id", "") or getattr(match, "platform_item_id", "") or "")
        if not is_likely_digital_ndl_pid(ndl_id):
            return False
        resolver_plan = candidate.artifacts.get("source_resolver_plan") or {}
        source_graph = candidate.artifacts.get("source_graph") or {}
        if not isinstance(resolver_plan, dict):
            resolver_plan = {}
        if not isinstance(source_graph, dict):
            source_graph = {}
        source_type = str(resolver_plan.get("source_type") or source_graph.get("source_type") or "")
        if source_type not in {"downloadable_monograph", "source_collection", "contained_document", "diary"}:
            return False
        manifest_url = f"https://dl.ndl.go.jp/api/iiif/{ndl_id}/manifest.json"
        fulltext_json_url = f"https://lab.ndl.go.jp/dl/api/book/fulltext-json/{ndl_id}"
        available = False
        try:
            response = requests.get(
                manifest_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            if response.status_code == 200:
                payload = response.json()
                canvases = payload.get("sequences", [{}])[0].get("canvases", []) if isinstance(payload, dict) else []
                label = payload.get("label", "") if isinstance(payload, dict) else ""
                candidate.artifacts["iiif_image_ocr_available"] = {
                    "ndl_id": ndl_id,
                    "manifest_url": manifest_url,
                    "label": label,
                    "canvas_count": len(canvases) if isinstance(canvases, list) else None,
                    "access_route": "ndl_iiif_manifest",
                }
                if "iiif_image_ocr_available" not in candidate.notes:
                    candidate.notes.append("iiif_image_ocr_available")
                available = True
        except Exception as exc:  # noqa: BLE001
            candidate.artifacts.setdefault("iiif_image_ocr_probe_errors", []).append(
                {"ndl_id": ndl_id, "route": "manifest", "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
            )
        try:
            response = requests.get(
                fulltext_json_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            if response.status_code == 200:
                candidate.artifacts["ndl_fulltext_json_available"] = {
                    "ndl_id": ndl_id,
                    "url": fulltext_json_url,
                    "access_route": "ndl_lab_fulltext_json",
                    "content_type": response.headers.get("content-type", ""),
                }
                if "ndl_fulltext_json_available" not in candidate.notes:
                    candidate.notes.append("ndl_fulltext_json_available")
                available = True
        except Exception as exc:  # noqa: BLE001
            candidate.artifacts.setdefault("iiif_image_ocr_probe_errors", []).append(
                {"ndl_id": ndl_id, "route": "fulltext_json", "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
            )
        return available

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
