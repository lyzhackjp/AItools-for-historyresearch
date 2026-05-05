import json
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import MethodType, SimpleNamespace
import importlib.util
from unittest.mock import patch

from modules.historical_citation.alignment import (
    align_translation,
    build_passage_candidates,
    parse_llm_json,
    score_evidence_cues,
    score_alignment_candidate,
    segment_page_text,
    trim_aligned_segment,
)
from modules.historical_citation.docx_parser import (
    build_citation_candidates,
    build_footnote_citation_units,
    build_footnote_contexts,
    parse_docx_document,
)
from modules.historical_citation.pdf_paper_parser import parse_pdf_paper
from modules.historical_citation.cross_validation import (
    classify_fulltext_page_check,
    normalized_text_similarity,
    render_cross_validation_markdown,
    select_fulltext_hit,
)
from modules.historical_citation.download_index import find_cached_range_pdf as find_cached_range_pdf_from_index
from modules.historical_citation.download_index import refresh_download_range_index
from modules.historical_citation.evidence_cues import load_evidence_cue_groups
from modules.historical_citation.footnote_parser import (
    extract_quotes,
    extract_volume_terms,
    parse_footnote_text,
    pick_translation_text,
)
from modules.historical_citation.llm_review import (
    DEFAULT_OLLAMA_REVIEW_TIMEOUT_SECONDS,
    OllamaChatClient,
    build_llm_review_prompt,
    build_multi_context_review_prompt,
    evaluate_review_client,
    heuristic_review_alignment,
    normalize_multi_context_review_payload,
    normalize_review_payload,
    parse_review_json_with_repair,
    review_alignment_with_llm,
    split_review_sentences,
)
from modules.historical_citation.ndl_search import (
    build_ndl_sru_queries,
    extract_japanese_era_years,
    extract_ndlsearch_fulltext_hits,
    iter_ndl_search_keywords,
    parse_ndl_sru_records,
    resolve_ndlsearch_detail_url,
    score_ndl_record,
    search_ndl_digital_fulltext,
    search_ndl_public_api,
    title_query_variants,
)
from modules.historical_citation.ndl_fulltext_context import (
    NDLFulltextHit,
    build_item_fulltext_target_and_page_map,
    expand_ndl_snippet_context,
    probe_ndl_fulltext_context,
    search_ndl_fulltext_in_item,
)
from modules.historical_citation.reporting import render_resume_markdown_report
from modules.historical_citation.progress import ProgressReporter
from modules.historical_citation.source_acquisition import (
    build_download_page_plan,
    build_restricted_download_requests,
    download_public_pdf,
    expand_page_window,
    select_preferred_source_match,
)
from modules.historical_citation.source_platforms import (
    CiNiiResearchPlatformAdapter,
    DietProceedingsPlatformAdapter,
    EGovLawPlatformAdapter,
    InternetArchivePlatformAdapter,
    JACARPlatformAdapter,
    JStagePlatformAdapter,
    JapanSearchPlatformAdapter,
    NDLSourcePlatformAdapter,
    is_plausible_source_match,
)
from modules.historical_citation.source_trials import source_trials_from_legacy
from modules.historical_citation.source_graph import (
    attach_source_graph_artifacts,
    build_manual_search_recipe,
    build_source_graph_node,
    build_source_query_plan,
    dedupe_result_dicts,
)
from modules.historical_citation.source_resolvers import resolve_source
from modules.historical_citation.fullrun import finalize_partial_payload, partial_payload_is_complete
from modules.historical_citation.models import CitationCandidate, NDLSearchMatch, ParsedFootnote, ParsedParagraph
from modules.historical_citation.page_mapping import (
    build_scan_page_range,
    estimate_book_pages_from_scan_page,
    estimate_scan_page_for_book_page,
    infer_page_mapping_from_front_matter_texts,
    infer_page_mapping_from_visible_page_numbers,
    load_page_mapping_cache,
    load_page_mapping_failure_cache,
    parse_toc_page_number_token,
    save_page_mapping_cache,
    save_page_mapping_failure_cache,
)
from modules.historical_citation.page_span import classify_page_span, split_citation_claims_for_pages
from modules.historical_citation.pdf_ocr import (
    detect_spread_gutter_x,
    extract_pages_directly as extract_pages_directly_module,
    extract_pdf_multi_panel_page_texts as extract_pdf_multi_panel_page_texts_module,
    extract_pdf_page_text as extract_pdf_page_text_module,
    extract_pdf_spread_page_texts as extract_pdf_spread_page_texts_module,
    map_target_page,
    split_double_page_image,
    split_multi_panel_image,
    wait_for_pdf_ready,
)
from modules.historical_citation.status import classify_result_status, classify_status
from modules.historical_citation_verifier import HistoricalCitationVerifier
from modules.ndlocr_lite import NDLOCRLiteConfig, NDLOCRLiteProcessor
from modules.workflows._legacy import load_legacy_module
from modules.workflows.ndl_download import NDLDownloadModule, NDLDownloadOutcome, NDLDownloadRequest


DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t>架空历史事件研究中，作者将其目的概括为：“为了完成制度维护的示范行动。”</w:t></w:r>
      <w:r><w:footnoteReference w:id="4" /></w:r>
    </w:p>
    <w:p>
      <w:r><w:t>无脚注段落。</w:t></w:r>
    </w:p>
  </w:body>
</w:document>
"""


FOOTNOTES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:footnote w:id="0" w:type="separator">
    <w:p><w:r><w:t>separator</w:t></w:r></w:p>
  </w:footnote>
  <w:footnote w:id="4">
    <w:p>
      <w:r>
        <w:t>佐藤一郎、高橋二郎「架空史料集：制度宣伝と事件叙述」、東京：架空出版社、2001年、41頁。</w:t>
      </w:r>
    </w:p>
  </w:footnote>
</w:footnotes>
"""


CORE_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
    xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>测试论文</dc:title>
</cp:coreProperties>
"""


class DummyNDLRecord:
    def __init__(self, title, url, ndl_id=None, author=None, date=None, publisher=None):
        self.title = title
        self.url = url
        self.ndl_id = ndl_id
        self.author = author
        self.date = date
        self.publisher = publisher
        self.metadata = {}


class DummyNDLModule:
    def search(self, keyword, max_results=5, use_api=True, headless=True):
        return [
            DummyNDLRecord(
                title="架空史料集：制度宣伝と事件叙述",
                url="https://dl.ndl.go.jp/pid/1234567",
                ndl_id="1234567",
                author="佐藤一郎 高橋二郎",
                date="2001",
                publisher="架空出版社",
            ),
            DummyNDLRecord(
                title="架空史料集：制度宣伝と事件叙述 別冊",
                url="https://dl.ndl.go.jp/pid/7654321",
                ndl_id="7654321",
                author="佐藤一郎",
                date="2002",
                publisher="別冊出版社",
            ),
        ]


class DummyMismatchNDLModule:
    def search(self, keyword, max_results=5, use_api=True, headless=True):
        del keyword, max_results, use_api, headless
        return [
            DummyNDLRecord(
                title="まったく別の資料",
                url="https://dl.ndl.go.jp/pid/00000000",
                ndl_id="00000000",
                author="別人",
                date="1999",
                publisher="別出版社",
            )
        ]


class DummyCountingNDLModule:
    def __init__(self):
        self.calls = []

    def search(self, keyword, max_results=5, use_api=True, headless=True):
        self.calls.append(
            {
                "keyword": keyword,
                "max_results": max_results,
                "use_api": use_api,
                "headless": headless,
            }
        )
        return []


class DummyResponse:
    def __init__(self, text, status_code=200, headers=None, chunks=None):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = chunks or []

    def iter_content(self, chunk_size=1024):
        del chunk_size
        yield from self._chunks

    def json(self):
        return json.loads(self.text)


class DummyPDFProcessor:
    def __init__(self, text):
        self.text = text

    def extract_text_by_region(self, pdf_path, page_number):
        del pdf_path, page_number
        return self.text


class DummyOCRResult:
    def __init__(self, text, success=True):
        self.text = text
        self.success = success


class DummyOCRProcessor:
    def __init__(self, text):
        self.text = text

    def process_image(self, image_path, **kwargs):
        del image_path, kwargs
        return DummyOCRResult(self.text)


class DummyLLMClient:
    def __init__(self, content):
        self.content = content

    def chat(self, messages, **kwargs):
        del messages, kwargs
        return {"content": self.content}


class DummyGenericPlatform:
    name = "example"

    def search(self, footnote, *, max_results=5):
        del footnote, max_results
        return [
            NDLSearchMatch(
                title="Example Archive Synthetic Source",
                url="https://example.invalid/source/1",
                platform="example",
                platform_item_id="example-1",
                score=0.77,
            )
        ]

    def select_preferred_match(self, matches):
        return matches[0] if matches else None

    def download_public_pdf(self, match, *, output_dir):
        del match, output_dir
        return None

    def build_restricted_download_requests(self, **kwargs):
        del kwargs
        return []


class DummyLink:
    def __init__(self, href, text=""):
        self.href = href
        self.text = text

    def get_attribute(self, name):
        return self.href if name == "href" else ""


class DummyClickableElement:
    def __init__(self, text="", attrs=None, displayed=True, enabled=True):
        self.text = text
        self.attrs = attrs or {}
        self.displayed = displayed
        self.enabled = enabled

    def get_attribute(self, name):
        if name == "textContent" or name == "innerText":
            return self.text
        return self.attrs.get(name, "")

    def is_displayed(self):
        return self.displayed

    def is_enabled(self):
        return self.enabled


class DummySwitchTo:
    def default_content(self):
        return None

    def frame(self, frame):
        del frame
        return None


class DummyBrowserDriver:
    def __init__(self, links=None, page_source="", body_text=""):
        self.links = links or []
        self.page_source = page_source
        self.body_text = body_text
        self.scripts = []
        self.current_url = "https://dl.ndl.go.jp/pid/99999999"
        self.switch_to = DummySwitchTo()

    def execute_script(self, script, *args):
        del args
        self.scripts.append(script)
        if "document.body" in script:
            return self.body_text
        if "textContent" in script or "innerText" in script:
            return ""

    def find_elements(self, by, selector):
        del by, selector
        return self.links


class TestHistoricalCitationVerifier(unittest.TestCase):
    def _make_docx(self) -> Path:
        tmpdir = Path(tempfile.mkdtemp())
        docx_path = tmpdir / "sample.docx"
        with zipfile.ZipFile(docx_path, "w") as archive:
            archive.writestr("word/document.xml", DOCUMENT_XML)
            archive.writestr("word/footnotes.xml", FOOTNOTES_XML)
            archive.writestr("docProps/core.xml", CORE_XML)
        return docx_path

    def _load_browser_module_or_skip(self):
        try:
            return load_legacy_module("ndl-search/browser_client.py")
        except ModuleNotFoundError as exc:
            self.skipTest(f"legacy browser client dependency unavailable: {exc.name}")

    def test_parse_docx_extracts_paragraphs_and_footnotes(self):
        verifier = HistoricalCitationVerifier()
        docx_path = self._make_docx()

        parsed = verifier.parse_docx(str(docx_path))

        self.assertEqual(parsed["document"]["title"], "测试论文")
        self.assertEqual(parsed["document"]["paragraph_count"], 2)
        self.assertEqual(parsed["document"]["footnote_count"], 1)
        self.assertEqual(parsed["paragraphs"][0].footnote_ids, ["4"])
        self.assertIn("为了完成制度维护的示范行动。", parsed["paragraphs"][0].quotes)

        footnote = parsed["footnotes"][0]
        self.assertEqual(footnote.title, "架空史料集：制度宣伝と事件叙述")
        self.assertEqual(footnote.author, "佐藤一郎、高橋二郎")
        self.assertEqual(footnote.publisher, "架空出版社")
        self.assertEqual(footnote.year, "2001")
        self.assertEqual(footnote.page_numbers, [41])

    def test_pdf_paper_parser_uses_ocr_fallback_when_text_layer_is_empty(self):
        import fitz

        tmpdir = Path(tempfile.mkdtemp())
        pdf_path = tmpdir / "blank.pdf"
        document = fitz.open()
        document.new_page(width=595, height=842)
        document.save(pdf_path)
        document.close()

        parsed = parse_pdf_paper(
            str(pdf_path),
            extract_quotes=extract_quotes,
            parse_footnote=parse_footnote_text,
            ocr_page_text_provider=lambda page_number: "正文说明①\n① 佐藤「史料」東京：出版社、2001年、1頁。",
        )

        self.assertEqual(parsed["document"]["input_format"], "pdf")
        self.assertEqual(len(parsed["paragraphs"]), 1)
        self.assertEqual(len(parsed["footnotes"]), 1)
        self.assertIn("pdf_page_no_text_layer", parsed["quality_flags"])
        self.assertIn("pdf_page_ocr_fallback_used", parsed["quality_flags"])
        self.assertEqual(parsed["pdf_parse_debug"][0]["parser_mode"], "ocr_text_fallback")

    def test_pdf_paper_parser_detects_larger_footnote_text_layer(self):
        from modules.historical_citation.pdf_paper_parser import (
            PdfLine,
            _infer_footnote_top,
            _parse_page_footnotes,
            _strip_footnote_footer,
        )

        lines = [
            PdfLine("正文说明①", 65.0, 470.0, 300.0, 484.0, 12.0, 12.0),
            PdfLine("① 佐藤一郎：『史料』、東京：出版社、2001 年、第1 頁。", 65.0, 618.0, 500.0, 632.0, 10.5, 11.4),
            PdfLine("125", 486.0, 730.0, 505.0, 742.0, 10.5, 10.5),
        ]

        footnote_top = _infer_footnote_top(lines, 793.7)
        footnote_lines = _strip_footnote_footer([line for line in lines if line.y0 >= footnote_top], 793.7)
        footnotes, marker_to_id = _parse_page_footnotes(2, footnote_lines, parse_footnote=parse_footnote_text)

        self.assertLess(footnote_top, 618.0)
        self.assertEqual(len(footnotes), 1)
        self.assertEqual(marker_to_id["①"], "p2n1")
        self.assertIn("佐藤一郎", footnotes[0].text)
        self.assertNotIn("125", footnotes[0].text)

    def test_next_stage_non_ndl_classifier_keeps_all_kanji_japanese_article_sources(self):
        from scripts.refine_historical_citation_pdf_next_stage import looks_like_non_ndl_direct_source

        classified = looks_like_non_ndl_direct_source(
            {
                "candidate_id": "p14-fp14n6",
                "footnote_id": "p14n6",
                "footnote": {
                    "source_type": "article",
                    "title": "『三条教則』関係資料一（解題）",
                    "text": "三宅守常：「『三条教則』関係資料一（解題）」、『明治聖徳記念学会紀要』第15号、1995年、第92頁。",
                    "page_numbers": [92],
                },
            }
        )

        self.assertEqual(classified["reasons"], [])

    def test_pdf_next_stage_rechecks_source_not_found_and_mismatch(self):
        from scripts.refine_historical_citation_pdf_next_stage import select_recheck_items

        selected = select_recheck_items(
            [
                {"candidate_id": "a", "verification_status": "source_found"},
                {"candidate_id": "b", "verification_status": "source_mismatch"},
                {"candidate_id": "c", "verification_status": "source_not_found"},
            ]
        )

        self.assertEqual([item["candidate_id"] for _offset, item in selected], ["b", "c"])

    def test_pdf_next_stage_filters_selection_by_candidate_and_footnote(self):
        from scripts.refine_historical_citation_pdf_next_stage import (
            apply_exact_selection,
            normalize_selector_values,
        )

        selection = [
            (0, {"candidate_id": "p1-fp1n1", "footnote_id": "p1n1"}),
            (1, {"candidate_id": "p2-fp2n1", "footnote_id": "p2n1"}),
            (2, {"candidate_id": "p2-fp2n8", "footnote_id": "p2n8"}),
        ]

        self.assertEqual(normalize_selector_values(["p2-fp2n1,p2-fp2n8", "p2-fp2n1"]), ["p2-fp2n1", "p2-fp2n8"])
        by_candidate = apply_exact_selection(selection, candidate_ids=["p2-fp2n1"])
        by_footnote = apply_exact_selection(selection, footnote_ids=["p2n8"])
        by_both = apply_exact_selection(selection, candidate_ids=["p2-fp2n1"], footnote_ids=["p2n8"])

        self.assertEqual([offset for offset, _item in by_candidate], [1])
        self.assertEqual([offset for offset, _item in by_footnote], [2])
        self.assertEqual(by_both, [])

    def test_pdf_next_stage_dedupes_resume_results_by_offset(self):
        from scripts.refine_historical_citation_pdf_next_stage import dedupe_by_offset, result_offsets

        first = {"candidate_id": "old", "artifacts": {"refinement_offset": 2}}
        second = {"candidate_id": "new", "artifacts": {"refinement_offset": 2}}
        third = {"candidate_id": "tail", "artifacts": {"refinement_offset": 3}}

        deduped = dedupe_by_offset([first, second, third])

        self.assertEqual([item["candidate_id"] for item in deduped], ["new", "tail"])
        self.assertEqual(result_offsets(deduped), {2, 3})

    def test_pdf_next_stage_separates_rechecked_download_results(self):
        from scripts.refine_historical_citation_pdf_next_stage import build_payload, split_rechecked_download_results

        normal = {
            "candidate_id": "normal",
            "verification_status": "matched",
            "notes": [],
            "artifacts": {"refinement_offset": 1},
        }
        rechecked = {
            "candidate_id": "rechecked",
            "verification_status": "fulltext_only_partial_support",
            "notes": ["download_after_source_recheck"],
            "artifacts": {"refinement_offset": 2},
        }

        download_results, rechecked_download_results = split_rechecked_download_results([normal, rechecked], [])

        self.assertEqual([item["candidate_id"] for item in download_results], ["normal"])
        self.assertEqual([item["candidate_id"] for item in rechecked_download_results], ["rechecked"])

        payload = build_payload(
            args=SimpleNamespace(
                label="sample",
                restricted_download=False,
                max_search_results=3,
                page_window=4,
                ocr_model="ndlocr_lite",
                download_max_attempts=2,
                download_timeout_seconds=900,
                slow_event_threshold_seconds=240,
                download_cache_dir="cache",
                platform_names=["ndl"],
                reparse_pdf=False,
                download_start_index=0,
                mismatch_start_index=0,
                recheck_download_start_index=0,
                max_recheck_downloads=None,
                retry_download_timeouts=True,
                no_force_ndl_fulltext=False,
                skip_recheck_downloads=False,
                prefer_ollama_review=True,
                review_model="gemma4:e4b",
                review_timeout_seconds=300,
                no_resume=False,
            ),
            combined={"document": {}, "summary": {}},
            download_selection_count=1,
            mismatch_selection_count=1,
            download_results=download_results,
            rechecked_download_results=rechecked_download_results,
            mismatch_results=[],
            non_ndl_sources=[],
            alias_audits=[],
            timeout_events=[],
            slow_events=[],
            execution_runs=[{"download_timeout_seconds": 900, "review_model": "gemma4:e4b"}],
        )

        self.assertEqual(payload["summaries"]["download_ocr_alignment"]["total"], 1)
        self.assertEqual(payload["summaries"]["rechecked_download_ocr_alignment"]["total"], 1)
        self.assertEqual(len(payload["rechecked_download_ocr_alignment_results"]), 1)
        self.assertEqual(payload["execution_runs"][0]["download_timeout_seconds"], 900)

    def test_pdf_next_stage_records_slow_events_from_progress(self):
        from scripts.refine_historical_citation_pdf_next_stage import build_slow_events_from_progress

        progress_path = Path(tempfile.mkdtemp()) / "progress.jsonl"
        events = [
            {
                "event": "candidate_started",
                "timestamp": "2026-05-01T10:00:00",
                "phase": "download_ocr_alignment",
                "global_current": 3,
                "global_total": 5,
                "candidate_id": "p1-f1",
                "footnote_id": "f1",
            },
            {
                "event": "worker_stage_started",
                "timestamp": "2026-05-01T10:01:00",
                "phase": "download_ocr_alignment",
                "global_current": 3,
                "global_total": 5,
                "candidate_id": "p1-f1",
                "footnote_id": "f1",
                "subphase": "snippet_context_expansion",
            },
            {
                "event": "worker_stage_completed",
                "timestamp": "2026-05-01T10:04:30",
                "phase": "download_ocr_alignment",
                "global_current": 3,
                "global_total": 5,
                "candidate_id": "p1-f1",
                "footnote_id": "f1",
                "subphase": "snippet_context_expansion",
                "status": "contexts_found",
                "metrics": {"context_count": 3},
            },
            {
                "event": "worker_stage_started",
                "timestamp": "2026-05-01T10:04:31",
                "phase": "download_ocr_alignment",
                "global_current": 3,
                "global_total": 5,
                "candidate_id": "p1-f1",
                "footnote_id": "f1",
                "subphase": "llm_context_review",
            },
            {
                "event": "worker_stage_completed",
                "timestamp": "2026-05-01T10:05:00",
                "phase": "download_ocr_alignment",
                "global_current": 3,
                "global_total": 5,
                "candidate_id": "p1-f1",
                "footnote_id": "f1",
                "subphase": "llm_context_review",
                "status": "partial_support",
                "metrics": {"model": "gemma4:e4b"},
            },
            {
                "event": "candidate_completed",
                "timestamp": "2026-05-01T10:05:01",
                "phase": "download_ocr_alignment",
                "global_current": 3,
                "global_total": 5,
                "candidate_id": "p1-f1",
                "footnote_id": "f1",
                "status": "fulltext_only_not_supported",
                "metrics": {"match_count": 2},
            },
        ]
        progress_path.write_text("\n".join(json.dumps(item) for item in events), encoding="utf-8")

        slow_events = build_slow_events_from_progress(progress_path, threshold_seconds=240)

        self.assertEqual(len(slow_events), 1)
        self.assertEqual(slow_events[0]["candidate_id"], "p1-f1")
        self.assertEqual(slow_events[0]["elapsed_seconds"], 301)
        self.assertEqual(slow_events[0]["status"], "fulltext_only_not_supported")
        self.assertEqual(slow_events[0]["last_subphase"], "llm_context_review")
        self.assertEqual(slow_events[0]["longest_subphase"], "snippet_context_expansion")
        self.assertEqual(slow_events[0]["longest_subphase_seconds"], 210)
        self.assertEqual(slow_events[0]["subphase_durations"][0]["metrics"]["context_count"], 3)

    def test_pdf_next_stage_slow_events_fallback_to_phase_total(self):
        from scripts.refine_historical_citation_pdf_next_stage import build_slow_events_from_progress

        progress_path = Path(tempfile.mkdtemp()) / "progress.jsonl"
        events = [
            {
                "event": "candidate_started",
                "timestamp": "2026-05-01T10:00:00",
                "phase": "source_mismatch_recheck",
                "global_current": 22,
                "global_total": 43,
                "candidate_id": "p4-fp4n5",
                "footnote_id": "p4n5",
            },
            {
                "event": "candidate_completed",
                "timestamp": "2026-05-01T10:04:00",
                "phase": "source_mismatch_recheck",
                "global_current": 22,
                "global_total": 43,
                "candidate_id": "p4-fp4n5",
                "footnote_id": "p4n5",
                "status": "source_found",
                "metrics": {"match_count": 15},
            },
        ]
        progress_path.write_text("\n".join(json.dumps(item) for item in events), encoding="utf-8")

        slow_events = build_slow_events_from_progress(progress_path, threshold_seconds=120)

        self.assertEqual(len(slow_events), 1)
        self.assertEqual(slow_events[0]["last_subphase"], "source_mismatch_recheck_total")
        self.assertEqual(slow_events[0]["longest_subphase"], "source_mismatch_recheck_total")
        self.assertEqual(slow_events[0]["longest_subphase_seconds"], 240)

    def test_pdf_next_stage_bypasses_download_worker_when_dependency_missing(self):
        from scripts import refine_historical_citation_pdf_next_stage as next_stage_script

        candidate = CitationCandidate(
            candidate_id="p2-f8",
            paragraph_index=2,
            paragraph_text="Yamagata opinion document.",
            translation_text="Yamagata opinion document.",
            footnote_id="p2n8",
            footnote=ParsedFootnote(id="p2n8", text="山縣有朋意見書, p. 306.", title="山縣有朋意見書"),
        )

        class FakeVerifier:
            def __init__(self, *_args, **_kwargs):
                pass

            def restricted_download_dependency_status(self):
                return {
                    "available": False,
                    "reason": "download_dependency_missing",
                    "dependency": "selenium",
                }

        def fake_run_download_ocr_alignment(**kwargs):
            return {
                "candidate_id": kwargs["candidate"].candidate_id,
                "artifacts": {},
                "verification_status": "download_failed",
            }

        with (
            patch.object(next_stage_script, "HistoricalCitationVerifier", FakeVerifier),
            patch.object(next_stage_script, "run_download_ocr_alignment", side_effect=fake_run_download_ocr_alignment),
            patch.object(next_stage_script.subprocess, "Popen") as popen,
        ):
            result, timeout_event = next_stage_script.run_download_ocr_alignment_with_timeout(
                candidate=candidate,
                source_item={"ndl_matches": []},
                output_dir=Path(tempfile.mkdtemp()),
                restricted_download=True,
                page_window=4,
                ocr_model="ndlocr_lite",
                download_max_attempts=1,
                timeout_seconds=600,
                allow_external_ndl_fallback=True,
                prefer_ollama_review=False,
            )

        popen.assert_not_called()
        self.assertIsNone(timeout_event)
        self.assertEqual(result["artifacts"]["download_worker_bypassed"]["reason"], "download_dependency_missing")
        self.assertEqual(result["artifacts"]["download_worker_bypassed"]["dependency"], "selenium")

    def test_pdf_next_stage_keeps_worker_timeout_for_formal_review_when_dependency_missing(self):
        from scripts import refine_historical_citation_pdf_next_stage as next_stage_script

        candidate = CitationCandidate(
            candidate_id="p4-fp4n5",
            paragraph_index=4,
            paragraph_text="Paris peace conference.",
            translation_text="Paris peace conference.",
            footnote_id="p4n5",
            footnote=ParsedFootnote(id="p4n5", text="日本外交文書。", title="日本外交文書"),
        )

        class FakeVerifier:
            def __init__(self, *_args, **_kwargs):
                pass

            def restricted_download_dependency_status(self):
                return {
                    "available": False,
                    "reason": "download_dependency_missing",
                    "dependency": "selenium",
                }

        class FakeProcess:
            returncode = 0
            pid = 12345

            def __init__(self, args, **_kwargs):
                self.args = args

            def communicate(self, timeout=None):
                payload_path = Path(self.args[-2])
                result_path = Path(self.args[-1])
                payload = json.loads(payload_path.read_text(encoding="utf-8"))
                result = payload["candidate"]
                result["verification_status"] = "download_failed"
                result.setdefault("artifacts", {})["worker_timeout_guard_used"] = True
                result_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                return b"", b""

        with (
            patch.object(next_stage_script, "HistoricalCitationVerifier", FakeVerifier),
            patch.object(next_stage_script.subprocess, "Popen", side_effect=FakeProcess) as popen,
            patch.dict(os.environ, {"HISTORICAL_CITATION_REVIEW_TIMEOUT_SECONDS": "300"}, clear=False),
        ):
            result, timeout_event = next_stage_script.run_download_ocr_alignment_with_timeout(
                candidate=candidate,
                source_item={"ndl_matches": []},
                output_dir=Path(tempfile.mkdtemp()),
                restricted_download=True,
                page_window=4,
                ocr_model="ndlocr_lite",
                download_max_attempts=1,
                timeout_seconds=180,
                allow_external_ndl_fallback=True,
                prefer_ollama_review=True,
            )

        popen.assert_called_once()
        self.assertIsNone(timeout_event)
        self.assertTrue(result["artifacts"]["worker_timeout_guard_used"])
        self.assertEqual(
            result["artifacts"]["download_dependency_precheck"]["reason"],
            "download_dependency_missing",
        )
        self.assertEqual(
            result["artifacts"]["download_worker_timeout_policy"]["effective_timeout_seconds"],
            600,
        )
        self.assertEqual(
            result["artifacts"]["download_worker_timeout_policy"]["review_timeout_seconds"],
            300,
        )
        self.assertEqual(
            result["artifacts"]["download_worker_timeout_policy"]["worker_overhead_seconds"],
            300,
        )
        self.assertNotIn("download_worker_bypassed", result["artifacts"])

    def test_pdf_next_stage_uses_volume_series_fulltext_before_rechecked_download(self):
        from scripts import refine_historical_citation_pdf_next_stage as next_stage_script

        candidate = CitationCandidate(
            candidate_id="p4-fp4n5",
            paragraph_index=4,
            paragraph_text="Japan explained its position on the South Sea Islands.",
            translation_text="Japan explained its position on the South Sea Islands.",
            footnote_id="p4n5",
            footnote=ParsedFootnote(
                id="p4n5",
                text="日本外交文書 巴里講和会議経過概要, pp.58-59.",
                title="日本外交文書",
                page_numbers=[58, 59],
                source_type="volume_series",
            ),
            notes=["download_after_source_recheck"],
            artifacts={
                "source_resolver_plan": {"source_type": "volume_series"},
                "source_graph": {"source_type": "volume_series"},
            },
        )

        class FakeVerifier:
            enrich_called = False

            def _mark_fulltext_only_hit_if_possible(self, marked_candidate, **kwargs):
                self.fulltext_kwargs = dict(kwargs)
                marked_candidate.verification_status = "fulltext_only_direct_support"
                marked_candidate.support_status = "fulltext_only_direct_support"
                marked_candidate.artifacts["fulltext_context_candidates"] = [
                    {"context_id": "ctx1", "cleaned_context": "帝国主張説明 南洋群島"}
                ]
                return True

            def _enrich_with_source_excerpt(self, *_args, **_kwargs):
                self.enrich_called = True
                raise AssertionError("download/OCR should not run after body-level fulltext review")

        verifier = FakeVerifier()
        result = next_stage_script.run_download_ocr_alignment(
            verifier=verifier,
            candidate=candidate,
            source_item={
                "ndl_matches": [
                    {
                        "title": "日本外交文書",
                        "url": "https://dl.ndl.go.jp/pid/11923430",
                        "ndl_id": "11923430",
                        "platform": "ndl",
                        "score": 1.0,
                    }
                ]
            },
            output_dir=Path(tempfile.mkdtemp()),
            restricted_download=True,
            page_window=4,
            ocr_model="ndlocr_lite",
            download_max_attempts=1,
        )

        self.assertFalse(verifier.enrich_called)
        self.assertEqual(result["verification_status"], "fulltext_only_direct_support")
        self.assertIn("volume_series_fulltext_review_before_download", result["notes"])
        self.assertEqual(verifier.fulltext_kwargs["max_context_candidates"], 5)
        self.assertEqual(verifier.fulltext_kwargs["max_hints_to_expand"], 3)
        self.assertEqual(verifier.fulltext_kwargs["max_expand_rounds"], 1)
        self.assertEqual(
            result["artifacts"]["volume_series_fulltext_review_before_download"]["reason"],
            "target_pid_fulltext_context_available_before_restricted_download",
        )

    def test_pdf_next_stage_worker_progress_reports_fulltext_subphases(self):
        from scripts import refine_historical_citation_pdf_next_stage as next_stage_script

        candidate = CitationCandidate(
            candidate_id="p4-fp4n5",
            paragraph_index=4,
            paragraph_text="Japan explained its position.",
            translation_text="Japan explained its position.",
            footnote_id="p4n5",
            footnote=ParsedFootnote(
                id="p4n5",
                text="日本外交文書 巴里講和会議経過概要, pp.58-59.",
                title="日本外交文書",
                page_numbers=[58, 59],
                source_type="volume_series",
            ),
            artifacts={
                "source_resolver_plan": {"source_type": "volume_series"},
                "source_graph": {"source_type": "volume_series"},
            },
        )

        class FakeVerifier:
            def _mark_fulltext_only_hit_if_possible(self, marked_candidate, **_kwargs):
                callback = getattr(self, "_progress_event_callback", None)
                if callable(callback):
                    callback(
                        event="worker_stage_started",
                        subphase="snippet_context_expansion",
                        metrics={"hint_count": 1},
                    )
                marked_candidate.verification_status = "fulltext_only_partial_support"
                marked_candidate.support_status = "fulltext_only_partial_support"
                marked_candidate.artifacts["fulltext_context_candidates"] = [
                    {"context_id": "ctx1", "cleaned_context": "牧野男 委任統治"}
                ]
                marked_candidate.artifacts["ndl_fulltext_probe"] = {"status": "direct_hit"}
                if callable(callback):
                    callback(
                        event="worker_stage_completed",
                        subphase="snippet_context_expansion",
                        status="contexts_found",
                        metrics={"context_count": 1},
                    )
                return True

        stream = io.StringIO()
        reporter = ProgressReporter(enabled=True, interval_seconds=0, stream=stream)
        reporter.update(
            phase="download_ocr_alignment",
            current=1,
            total=1,
            candidate_id=candidate.candidate_id,
            footnote_id=candidate.footnote_id,
        )
        try:
            result = next_stage_script.run_download_ocr_alignment(
                verifier=FakeVerifier(),
                candidate=candidate,
                source_item={
                    "ndl_matches": [
                        {
                            "title": "日本外交文書",
                            "url": "https://dl.ndl.go.jp/pid/11923430",
                            "ndl_id": "11923430",
                            "platform": "ndl",
                            "score": 1.0,
                        }
                    ]
                },
                output_dir=Path(tempfile.mkdtemp()),
                restricted_download=True,
                page_window=4,
                ocr_model="ndlocr_lite",
                download_max_attempts=1,
                progress_reporter=reporter,
            )
        finally:
            reporter.close()

        events = [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
        subphase_events = [(event["event"], event.get("subphase")) for event in events]
        self.assertEqual(result["verification_status"], "fulltext_only_partial_support")
        self.assertIn(("worker_stage_started", "source_graph_attach"), subphase_events)
        self.assertIn(("worker_stage_completed", "source_graph_attach"), subphase_events)
        self.assertIn(("worker_stage_started", "volume_series_fulltext_review"), subphase_events)
        self.assertIn(("worker_stage_completed", "volume_series_fulltext_review"), subphase_events)
        self.assertIn(("worker_stage_started", "snippet_context_expansion"), subphase_events)
        self.assertIn(("worker_stage_completed", "snippet_context_expansion"), subphase_events)
        fulltext_done = [
            event
            for event in events
            if event["event"] == "worker_stage_completed"
            and event.get("subphase") == "volume_series_fulltext_review"
        ][0]
        self.assertEqual(fulltext_done["metrics"]["context_count"], 1)
        self.assertEqual(fulltext_done["metrics"]["target_probe_status"], "direct_hit")

    def test_pdf_next_stage_stops_volume_series_lead_before_initial_download(self):
        from scripts import refine_historical_citation_pdf_next_stage as next_stage_script

        candidate = CitationCandidate(
            candidate_id="p6-fp6n6",
            paragraph_index=6,
            paragraph_text="Washington conference claim.",
            translation_text="Washington conference claim.",
            footnote_id="p6n6",
            footnote=ParsedFootnote(
                id="p6n6",
                text="日本外交文書, pp.170-171.",
                title="日本外交文書",
                page_numbers=[170, 171],
                source_type="volume_series",
            ),
            artifacts={
                "source_resolver_plan": {"source_type": "volume_series"},
                "source_graph": {"source_type": "volume_series"},
            },
        )

        class FakeVerifier:
            enrich_called = False

            def _mark_fulltext_only_hit_if_possible(self, marked_candidate, **kwargs):
                marked_candidate.verification_status = "fulltext_lead_only"
                marked_candidate.support_status = "fulltext_lead_only"
                return True

            def _enrich_with_source_excerpt(self, *_args, **_kwargs):
                self.enrich_called = True
                raise AssertionError("download/OCR should not run after volume-series lead stop")

        verifier = FakeVerifier()
        result = next_stage_script.run_download_ocr_alignment(
            verifier=verifier,
            candidate=candidate,
            source_item={
                "ndl_matches": [
                    {
                        "title": "日本外交文書",
                        "url": "https://dl.ndl.go.jp/pid/11927523",
                        "ndl_id": "11927523",
                        "platform": "ndl",
                        "score": 1.0,
                    }
                ]
            },
            output_dir=Path(tempfile.mkdtemp()),
            restricted_download=True,
            page_window=4,
            ocr_model="ndlocr_lite",
            download_max_attempts=1,
        )

        self.assertFalse(verifier.enrich_called)
        self.assertEqual(result["verification_status"], "fulltext_lead_only")
        self.assertIn("volume_series_fulltext_lead_before_download_stopped", result["notes"])
        self.assertEqual(
            result["artifacts"]["volume_series_fulltext_review_before_download"]["phase"],
            "download_ocr_alignment",
        )

    def test_ndl_adapter_can_force_fulltext_even_when_metadata_has_download_hint(self):
        footnote = ParsedFootnote(id="1", text="テスト史料、12頁。", title="テスト史料")
        adapter = NDLSourcePlatformAdapter(lambda: None, allow_external_fallback=False)
        adapter._search_public_api_cached = lambda _footnote, *, max_results: [  # type: ignore[method-assign]
            {
                "title": "テスト史料",
                "url": "https://dl.ndl.go.jp/pid/111",
                "ndl_id": "111",
                "metadata": {},
            }
        ]
        calls = []
        adapter._search_via_ndlsearch_fulltext = lambda _footnote, *, max_results, claim_text="": calls.append(max_results) or [  # type: ignore[method-assign]
            {
                "title": "テスト史料",
                "url": "https://dl.ndl.go.jp/pid/222",
                "ndl_id": "222",
                "metadata": {
                    "search_route": "ndl_digital_fulltext_api",
                    "fulltext_hints": [{"snippet": "テスト"}],
                },
            }
        ]

        with patch.dict(os.environ, {"HISTORICAL_CITATION_FORCE_NDL_FULLTEXT": "1"}, clear=False):
            matches = adapter.search(footnote, max_results=3)

        self.assertEqual(calls, [3])
        self.assertTrue(any(match.metadata.get("fulltext_hints") for match in matches))

    def test_ndl_adapter_injects_resolver_known_pid_candidates_before_public_results(self):
        cases = [
            (
                "gaiko_volume_series",
                ParsedFootnote(
                    id="gaiko1",
                    text="外务省编：《日本外交文书》第32卷，第216～221页。",
                    title="日本外交文書",
                    page_numbers=[216, 217, 218, 219, 220, 221],
                ),
                "3448049",
                "3448126",
            ),
            (
                "diary_date_volume",
                ParsedFootnote(
                    id="diary1",
                    text="『原敬日記』1900年5月12日条，第84頁。",
                    title="原敬日記",
                    page_numbers=[84],
                ),
                "2982137",
                "2982135",
            ),
            (
                "contained_known_document",
                ParsedFootnote(
                    id="contained1",
                    text="山縣有朋：《山縣有朋意見書》，第12頁。",
                    title="山縣有朋意見書",
                    author="山縣有朋",
                    page_numbers=[12],
                ),
                "9999999",
                "3025431",
            ),
        ]

        for label, footnote, public_pid, expected_first_pid in cases:
            with self.subTest(label=label):
                adapter = NDLSourcePlatformAdapter(lambda: None, allow_external_fallback=False)

                def fake_public_search(_footnote, *, max_results, pid=public_pid, title=footnote.title):
                    return [
                        {
                            "title": title,
                            "url": f"https://dl.ndl.go.jp/pid/{pid}",
                            "ndl_id": pid,
                            "metadata": {"search_route": "ndl_public_api"},
                        }
                    ]

                adapter._search_public_api_cached = fake_public_search  # type: ignore[method-assign]

                with patch.dict(os.environ, {"HISTORICAL_CITATION_SKIP_NDL_FULLTEXT": "1"}, clear=False):
                    matches = adapter.search(footnote, max_results=5)

                self.assertEqual(matches[0].ndl_id, expected_first_pid)
                self.assertEqual(matches[0].metadata["search_route"], "resolver_config_known_pid")
                self.assertTrue(matches[0].metadata["known_pid_candidate"])
                self.assertIn(public_pid, [match.ndl_id for match in matches])

    def test_diary_resolver_removes_publication_year_from_diary_dates(self):
        footnote = ParsedFootnote(
            id="diary_pub_year",
            text="原奎一郎编：《原敬日记》第2卷，东京：福村出版1981年版，第325页。",
            title="原敬日記",
            publisher="福村出版",
            publication_place="东京",
            year="1981",
            page_numbers=[325],
        )

        plan = resolve_source(footnote, claim_text="美国确是极有活力的国家。")

        self.assertEqual(plan.resolver, "DiaryDateResolver")
        self.assertEqual(plan.dates, [])
        self.assertIn("publication_year_removed_from_diary_dates", plan.warnings)
        self.assertIn("date_missing_for_diary_resolver", plan.warnings)
        self.assertIn("2982135", plan.known_pid_candidates)
        self.assertNotIn("1981年", plan.target_pid_queries)

    def test_diary_bibliographic_terms_are_not_specific_fulltext_evidence(self):
        verifier = HistoricalCitationVerifier()
        footnote = ParsedFootnote(
            id="diary_pub_year",
            text="原奎一郎编：《原敬日记》第2卷，东京：福村出版1981年版，第325页。",
            title="原敬日記",
            year="1981",
            page_numbers=[325],
        )
        plan = resolve_source(footnote, claim_text="美国确是极有活力的国家。")
        candidate = CitationCandidate(
            candidate_id="p4-fp4n1",
            paragraph_index=4,
            paragraph_text="美国确是极有活力的国家。",
            translation_text="美国确是极有活力的国家。",
            footnote_id="p4n1",
            footnote=footnote,
            artifacts={"source_resolver_plan": plan.to_dict()},
        )
        hint = {
            "query": "原敬日記 第二巻 1981年",
            "snippet": "第二卷政界進",
            "expanded_context": "記第二卷政界進出",
            "pdf_page": 216,
            "pid": "2982135",
            "book_id": "2982135",
        }

        self.assertFalse(verifier._hint_is_specific_fulltext_evidence(candidate, hint))
        self.assertNotIn("1981年", verifier._fulltext_specific_terms(candidate))
        self.assertNotIn("第2巻", verifier._fulltext_specific_terms(candidate))

    def test_source_graph_uses_paragraph_event_year_for_diary_context(self):
        footnote = ParsedFootnote(
            id="diary_context_year",
            text="原奎一郎编：《原敬日记》第2卷，东京：福村出版1981年版，第325页。",
            title="原敬日記",
            year="1981",
            page_numbers=[325],
        )
        candidate = CitationCandidate(
            candidate_id="p4-fp4n1",
            paragraph_index=4,
            paragraph_text=(
                "1918年原敬组阁。1908年内阁辞职后，原敬赴欧美考察，并在美国停留一个月，"
                "认为：美国确是极有活力的国家。此后1914年又讨论对美政策。"
            ),
            translation_text="美国确是极有活力的国家。",
            footnote_id="diary_context_year",
            footnote=footnote,
        )

        attach_source_graph_artifacts(candidate)

        resolved = candidate.artifacts["source_resolver_plan"]
        self.assertEqual(resolved["resolver"], "DiaryDateResolver")
        self.assertIn("1908年", resolved["dates"])
        self.assertNotIn("1981年", resolved["dates"])
        self.assertNotIn("1914年", resolved["dates"])
        self.assertEqual(candidate.artifacts["source_query_context_scope"], "translation_plus_paragraph_for_diary")

    def test_ndl_adapter_uses_claim_text_to_order_configured_volume_pids(self):
        footnote = ParsedFootnote(
            id="gaiko1",
            text="外务省编：《日本外交文书》第32卷，第216～221页。",
            title="日本外交文書",
            page_numbers=[216, 217, 218, 219, 220, 221],
        )
        adapter = NDLSourcePlatformAdapter(lambda: None, allow_external_fallback=False)
        adapter._search_public_api_cached = lambda _footnote, *, max_results: [  # type: ignore[method-assign]
            {
                "title": "日本外交文書",
                "url": "https://dl.ndl.go.jp/pid/3448049",
                "ndl_id": "3448049",
                "metadata": {"search_route": "ndl_public_api"},
            }
        ]

        with patch.dict(os.environ, {"HISTORICAL_CITATION_SKIP_NDL_FULLTEXT": "1"}, clear=False):
            matches = adapter.search(
                footnote,
                max_results=5,
                claim_text="约翰·海伊提出在华门户开放和机会均等原则，日本政府随后作出回答。",
            )

        self.assertEqual(matches[0].ndl_id, "3448128")
        self.assertEqual(matches[0].metadata["search_route"], "resolver_config_known_pid")
        self.assertEqual(matches[0].metadata["configured_pid_rank"], 1)

    def test_title_query_variants_cover_compound_imperial_constitution_title(self):
        variants = title_query_variants("帝国憲法義解・皇室典範義解")

        self.assertIn("帝国憲法義解 皇室典範義解", variants)
        self.assertIn("帝国憲法義解", variants)
        self.assertIn("皇室典範義解", variants)
        self.assertIn("帝國憲法義解 皇室典範義解", variants)

    def test_pdf_next_stage_refreshes_host_title_and_volume_hints(self):
        from scripts.refine_historical_citation_pdf_next_stage import footnote_from_dict

        religion = footnote_from_dict(
            {
                "id": "p2n3",
                "text": "［日］田中頼庸：《神祇官を復し教導寮等設置につき建白》，《日本近代思想大系 5：宗教と国家》，第 40 页。",
                "title": "神祇官を復し教導寮等設置につき建白",
            }
        )
        diplomacy = footnote_from_dict(
            {
                "id": "p2n1",
                "text": "外务省编：《日本外交文书》（外務省編：『日本外交文書』）第３２卷，东京：外务省１９５５年版，第２１６～２２１页。",
                "title": "日本外交文書",
            }
        )
        imperial = footnote_from_dict(
            {
                "id": "p3n1",
                "text": "［日］伊藤博文：《 帝国憲法義解 · 皇室典範義解》，丸善 1935 年，第 52 页。",
                "title": "帝国憲法義解 · 皇室典範義解",
            }
        )

        self.assertEqual(religion.host_title, "日本近代思想大系 5：宗教と国家")
        self.assertEqual(religion.contained_title, "神祇官を復し教導寮等設置につき建白")
        self.assertIn("第32巻", diplomacy.ndl_keyword)
        self.assertIn("明治32年", diplomacy.ndl_keyword)
        self.assertEqual(imperial.publisher, "丸善")
        self.assertEqual(imperial.year, "1935")

    def test_pdf_next_stage_claim_fulltext_recheck_uses_volume_and_claim_terms(self):
        from scripts.refine_historical_citation_pdf_next_stage import (
            augment_candidate_matches_with_claim_fulltext,
            build_claim_fulltext_global_queries,
        )

        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="论文句子。",
            translation_text="约翰·海伊提出在华门户开放、机会均等原则。",
            footnote_id="1",
            footnote=ParsedFootnote(
                id="1",
                text="外务省编：《日本外交文书》第32卷，第51-52页。",
                title="日本外交文書",
                ndl_keyword="日本外交文書 第32卷 第32巻 第三十二巻 明治32年",
            ),
            ndl_matches=[
                NDLSearchMatch(
                    title="日本外交文書",
                    url="https://dl.ndl.go.jp/pid/3448049",
                    ndl_id="3448049",
                    metadata={"search_route": "ndl_digital_fulltext_api"},
                )
            ],
        )

        queries = build_claim_fulltext_global_queries(verifier, candidate, max_queries=6)
        self.assertIn("日本外交文書 第32巻 門戶開放", queries)
        self.assertIn("門戶開放", queries)

        seen_queries = []

        def fake_search(keyword, *, max_results):
            seen_queries.append(keyword)
            if keyword == "日本外交文書 第32巻 門戶開放":
                return [
                    {
                        "title": "日本外交文書",
                        "url": "https://dl.ndl.go.jp/pid/3448128",
                        "ndl_id": "3448128",
                        "metadata": {
                            "search_route": "ndl_digital_fulltext_api",
                            "fulltext_hints": [
                                {
                                    "query": keyword,
                                    "snippet": "及門戶開放ニ關スル件。",
                                    "pdf_page": 32,
                                    "pid": "3448128",
                                }
                            ],
                        },
                    }
                ]
            return []

        added = augment_candidate_matches_with_claim_fulltext(
            verifier,
            candidate,
            max_results=3,
            search_fulltext=fake_search,
        )

        self.assertEqual(added, 1)
        self.assertIn("日本外交文書 第32巻 門戶開放", seen_queries)
        self.assertEqual(candidate.ndl_matches[-1].ndl_id, "3448128")
        self.assertTrue(candidate.ndl_matches[-1].metadata["claim_fulltext_global_recheck"])

    def test_gaiko_claim_fulltext_recheck_reaches_person_and_reply_queries(self):
        from scripts.refine_historical_citation_pdf_next_stage import (
            augment_candidate_matches_with_claim_fulltext,
            build_claim_fulltext_global_queries,
        )

        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="论文句子。",
            translation_text="约翰·海伊向各国提出在华门户开放、机会均等原则，得到了日本的赞同。",
            footnote_id="1",
            footnote=ParsedFootnote(
                id="1",
                text="外务省编：《日本外交文書》第32卷，第51-52页。",
                title="日本外交文書",
                ndl_keyword="日本外交文書 第32巻 明治32年",
            ),
        )
        attach_source_graph_artifacts(candidate)

        queries = build_claim_fulltext_global_queries(verifier, candidate, max_queries=16)
        self.assertIn("日本外交文書 第32巻 ジョン・ヘイ", queries)
        self.assertIn("日本外交文書 第32巻 帝國政府回答", queries)

        seen_queries = []

        def fake_search(keyword, *, max_results):
            seen_queries.append(keyword)
            if keyword == "日本外交文書 第32巻 ジョン・ヘイ":
                return [
                    {
                        "title": "日本外交文書",
                        "url": "https://dl.ndl.go.jp/pid/3448128",
                        "ndl_id": "3448128",
                        "metadata": {
                            "search_route": "ndl_digital_fulltext_api",
                            "fulltext_hints": [
                                {
                                    "query": keyword,
                                    "snippet": "ヘイ國務卿ノ提議。",
                                    "pdf_page": 32,
                                    "pid": "3448128",
                                }
                            ],
                        },
                    }
                ]
            return []

        added = augment_candidate_matches_with_claim_fulltext(
            verifier,
            candidate,
            max_results=3,
            search_fulltext=fake_search,
        )

        self.assertEqual(added, 1)
        self.assertIn("日本外交文書 第32巻 ジョン・ヘイ", seen_queries)

    def test_gaiko_claim_fulltext_recheck_translates_katsura_taft_harriman_terms(self):
        from scripts.refine_historical_citation_pdf_next_stage import build_claim_fulltext_global_queries

        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p2-fp2n3",
            paragraph_index=2,
            paragraph_text="论文句子。",
            translation_text="桂太郎与美国陆军部长塔夫脱达成桂塔夫脱备忘录，随后哈里曼提出共同管理南满铁路。",
            footnote_id="p2n3",
            footnote=ParsedFootnote(
                id="p2n3",
                text="外务省编：《日本外交文書》第38卷第1册，东京：外务省1958年版，第450～452页。",
                title="日本外交文書",
                ndl_keyword="日本外交文書 第38卷 第38巻 第三十八巻 明治38年 第1册 第1巻 明治1年",
            ),
        )
        attach_source_graph_artifacts(candidate)

        queries = build_claim_fulltext_global_queries(verifier, candidate, max_queries=20)
        joined = "\n".join(queries)

        self.assertIn("日本外交文書 第38巻 タフト", joined)
        self.assertIn("日本外交文書 第38巻 ハリマン", joined)
        self.assertIn("日本外交文書 第38巻 南満洲鉄道", joined)
        self.assertNotIn("日本外交文書 第1巻", joined)

    def test_claim_fulltext_recheck_translates_shingu_taima_terms(self):
        verifier = HistoricalCitationVerifier()
        footnote = parse_footnote_text(
            "p4n5",
            "［日］《奈良県における大麻問題》，《日本近代思想大系 5：宗教と国家》，第 184 页。",
        )
        candidate = CitationCandidate(
            candidate_id="p4-fp4n5",
            paragraph_index=4,
            paragraph_text="论文句子。",
            translation_text="土真宗信徒不设神棚，不接受伊势神宫大麻。",
            footnote_id="p4n5",
            footnote=footnote,
        )

        queries = verifier._claim_fulltext_queries(candidate)
        joined = "\n".join(queries)

        self.assertIn("神棚ヲ不設", joined)
        self.assertIn("伊勢皇大神宮大麻", joined)
        self.assertIn("神宮大麻等", joined)

    def test_claim_fulltext_recheck_keeps_taima_rumor_terms_distinct(self):
        verifier = HistoricalCitationVerifier()
        footnote = parse_footnote_text(
            "p4n9",
            "［日］《静岡県で大麻につき流言》，《日本近代思想大系 5：宗教と国家》，第 190 页。",
        )
        candidate = CitationCandidate(
            candidate_id="p4-fp4n9",
            paragraph_index=4,
            paragraph_text="论文句子。",
            translation_text="大麻的神符会化为蝴蝶，其时该户将遭时疫，故要在化蝶前焚毁、冲走大麻。",
            footnote_id="p4n9",
            footnote=footnote,
        )

        queries = verifier._claim_fulltext_queries(candidate)
        joined = "\n".join(queries)
        core_terms = verifier._fulltext_core_action_terms(candidate)

        self.assertIn("大麻ノ神ノ字ガ蝶", joined)
        self.assertIn("大麻ヲ水火ニ投ズ", joined)
        self.assertIn("時疫", joined)
        self.assertNotIn("神棚ヲ不設", joined)
        self.assertIn("蝶", core_terms)
        self.assertNotIn("神棚", core_terms)

    def test_claim_fulltext_recheck_translates_imperial_gikai_boundary_terms(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p3-fp3n2",
            paragraph_index=3,
            paragraph_text="论文句子。",
            translation_text="此乃宪法所裁定之准则，亦为政权与教权相互界定之疆域。",
            footnote_id="p3n2",
            footnote=ParsedFootnote(
                id="p3n2",
                text="［日］伊藤博文：《帝国憲法義解 · 皇室典範義解》，第 53 页。",
                title="帝国憲法義解 · 皇室典範義解",
                page_numbers=[53],
            ),
        )

        queries = verifier._claim_fulltext_queries(candidate)
        joined = "\n".join(queries)
        core_terms = verifier._fulltext_core_action_terms(candidate)

        self.assertIn("政權ト教權", joined)
        self.assertIn("相分界スルノ域", joined)
        self.assertIn("憲法ノ裁定スル所", joined)
        self.assertIn("相分界", core_terms)

    def test_source_collection_toc_hit_is_not_body_evidence(self):
        verifier = HistoricalCitationVerifier()
        footnote = parse_footnote_text(
            "p4n5",
            "［日］《奈良県における大麻問題》，《日本近代思想大系 5：宗教と国家》，第 184 页。",
        )
        candidate = CitationCandidate(
            candidate_id="p4-fp4n5",
            paragraph_index=4,
            paragraph_text="论文句子。",
            translation_text="土真宗信徒不设神棚，不接受伊势神宫大麻。",
            footnote_id="p4n5",
            footnote=footnote,
        )
        attach_source_graph_artifacts(candidate)
        hint = {
            "pid": "13260166",
            "pdf_page": 5,
            "query": "日本近代思想大系 5：宗教と国家 奈良県における大麻問題",
            "snippet": "神祇局設置案(一〇二)神官有志神祇官設置陳情書(一〇三)弥彦神社本地仏焼却事件(一一三)",
            "expanded_context": "神祇局設置案(一〇二)神官有志神祇官設置陳情書(一〇三)弥彦神社本地仏焼却事件(一一三)苗木藩葬祭処分(一一九)",
        }

        category = verifier._fulltext_hint_lead_category(candidate, hint)
        score, reasons = verifier._score_fulltext_context_candidate(candidate, hint, hint["expanded_context"])

        self.assertIn(category, {"toc_or_index", "title_or_series_only"})
        self.assertTrue(
            "toc_or_index_penalty" in reasons or "title_or_series_only_penalty" in reasons
        )
        self.assertLess(score, 10.0)

    def test_source_collection_contained_title_with_body_text_is_expandable(self):
        verifier = HistoricalCitationVerifier()
        footnote = parse_footnote_text(
            "p4n3",
            "［日］《皇大神宮大麻之儀ニ付再伺書》，《日本近代思想大系 5：宗教と国家》，第 188 页。",
        )
        footnote.host_title = "日本近代思想大系 5：宗教と国家"
        footnote.contained_title = "皇大神宮大麻之儀ニ付再伺書"
        footnote.source_relation = "contained_in_host"
        candidate = CitationCandidate(
            candidate_id="p4-fp4n3",
            paragraph_index=4,
            paragraph_text="论文句子。",
            translation_text="纳金没有定额，被戏称为敬神税。",
            footnote_id="p4n3",
            footnote=footnote,
        )
        attach_source_graph_artifacts(candidate)
        hint = {
            "pid": "13260166",
            "pdf_page": 102,
            "query": "皇大神宮大麻之儀ニ付再伺書",
            "snippet": (
                "神璽以下諸入費ニ被下金右之趣ヲ御一定奉願上、毎年壱ケ度御初穂取集各府県エ罷出可申事。"
                "○皇大神宮大麻之儀ニ付再伺書皇大神宮大麻之儀ニ付先般相伺候処、"
                "書面御霊代拝受之儀ハ即今難聞届旨御指令之趣、承知仕候。"
            ),
        }

        category = verifier._fulltext_hint_lead_category(candidate, hint)

        self.assertEqual(category, "body_candidate")

    def test_pdf_next_stage_refresh_replaces_stale_ndl_keyword(self):
        from scripts.refine_historical_citation_pdf_next_stage import refresh_footnote_structure

        footnote = ParsedFootnote(
            id="p2n3",
            text="外务省编：《日本外交文书》第38卷第1册，东京：外务省1958年版，第450～452页。",
            title="日本外交文書",
            ndl_keyword="日本外交文書 第38卷 第38巻 第三十八巻 明治38年 第1册 第1巻 明治1年",
        )

        refreshed = refresh_footnote_structure(footnote)

        self.assertIn("第38巻", refreshed.ndl_keyword)
        self.assertIn("第1册", refreshed.ndl_keyword)
        self.assertNotIn("第1巻", refreshed.ndl_keyword)
        self.assertNotIn("明治1年", refreshed.ndl_keyword)
        self.assertIn("pdf_next_stage_ndl_keyword_refreshed", refreshed.notes)

    def test_pdf_next_stage_repairs_running_header_orphaned_claim(self):
        from scripts.refine_historical_citation_pdf_next_stage import repair_pdf_running_header_claim

        candidate = CitationCandidate(
            candidate_id="p5-fp5n1",
            paragraph_index=5,
            paragraph_text="宗教世界 文化2026 年第 2 期THE WORLD RELIGIOUS CULTURES神，以秬凶清洗其地”。1874 年，平将门灵位迁入神田神社本殿左侧新设的祠堂之中，降级为摄社。",
            translation_text="宗教世界 文化2026 年第 2 期THE WORLD RELIGIOUS CULTURES神，以秬凶清洗其地”",
            footnote_id="p5n1",
            footnote=ParsedFootnote(id="p5n1", text="《神田神社の祭神問題》。", title="神田神社の祭神問題"),
            artifacts={
                "citation_unit": {
                    "text": "宗教世界 文化2026 年第 2 期THE WORLD RELIGIOUS CULTURES神，以秬凶清洗其地”",
                    "unit_type": "nearest_sentence",
                    "confidence": 0.82,
                    "claim_candidates": ["宗教世界 文化2026 年第 2 期THE WORLD RELIGIOUS CULTURES神，以秬凶清洗其地”"],
                    "following_unfootnoted_context": "1874 年，平将门灵位迁入神田神社本殿左侧新设的祠堂之中，降级为摄社。此年，神田祭因平将门缺位而未能举行。",
                }
            },
        )

        repair_pdf_running_header_claim(candidate)

        self.assertNotIn("THE WORLD RELIGIOUS CULTURES", candidate.translation_text)
        self.assertIn("1874 年，平将门灵位迁入神田神社", candidate.translation_text)
        self.assertIn("pdf_next_stage_running_header_claim_cleaned", candidate.notes)
        self.assertIn("pdf_next_stage_orphaned_quote_claim_expanded", candidate.notes)

    def test_source_graph_models_host_contained_collection_as_reusable_type(self):
        footnote = parse_footnote_text(
            "1",
            "［日］田中頼庸：《神祇官を復し教導寮等設置につき建白》，《日本近代思想大系 5：宗教と国家》，第 40 页。",
        )

        node = build_source_graph_node(footnote)
        plan = build_source_query_plan(footnote)
        recipe = build_manual_search_recipe(footnote, current_status="page_mapping_unavailable")

        self.assertEqual(node.source_type, "source_collection")
        self.assertEqual(node.resolver, "NihonKindaiShisoTaikeiResolver")
        self.assertIn("13260166", node.known_pid_candidates)
        self.assertIn("日本近代思想大系 5：宗教と国家", plan.host_bucket)
        self.assertIn("神祇官を復し教導寮等設置につき建白", plan.contained_bucket)
        self.assertEqual(recipe["suggested_pid_scope"], "13260166")

    def test_kindai_shiso_taikei_other_volumes_use_volume_specific_pid(self):
        footnote = parse_footnote_text(
            "1",
            "［日］植木枝盛：《尊王論》，《日本近代思想大系 2：天皇と華族》，第 163 页。",
        )

        node = build_source_graph_node(footnote)
        plan = resolve_source(footnote)

        self.assertEqual(node.resolver, "NihonKindaiShisoTaikeiResolver")
        self.assertEqual(plan.resolver, "NihonKindaiShisoTaikeiResolver")
        self.assertEqual(node.known_pid_candidates, ["13264501"])
        self.assertEqual(plan.known_pid_candidates, ["13264501"])
        self.assertNotIn("13260166", node.known_pid_candidates)
        self.assertNotIn("13260166", plan.known_pid_candidates)
        self.assertIn("日本近代思想大系 2：天皇と華族", plan.query_buckets["host"])
        self.assertNotIn("日本近代思想大系 5：宗教と国家", plan.query_buckets["host"])
        self.assertIn("尊王論", plan.query_buckets["contained"])

    def test_source_graph_models_downloadable_imperial_gikai_as_reusable_type(self):
        footnote = parse_footnote_text(
            "2",
            "［日］伊藤博文：《帝国憲法義解・皇室典範義解》，丸善 1935 年，第 52 页。",
        )

        node = build_source_graph_node(footnote)
        plan = build_source_query_plan(footnote)

        self.assertEqual(node.source_type, "downloadable_monograph")
        self.assertEqual(node.resolver, "DownloadableMonographResolver")
        self.assertIn("1272168", node.known_pid_candidates)
        self.assertIn("帝国憲法義解 皇室典範義解", plan.title_bucket)
        self.assertIn("帝國憲法義解・皇室典範義解", plan.title_bucket)

    def test_verifier_records_iiif_image_ocr_availability_for_imperial_gikai(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p3-fp3n1",
            paragraph_index=3,
            paragraph_text="信教自由。",
            translation_text="伊藤博文说明信教自由包含内部信仰与外部礼拜。",
            footnote_id="p3n1",
            footnote=ParsedFootnote(
                id="p3n1",
                text="伊藤博文：《帝国憲法義解・皇室典範義解》，丸善1935年，第52页。",
                title="帝国憲法義解・皇室典範義解",
                page_numbers=[52],
            ),
            artifacts={"source_resolver_plan": {"source_type": "downloadable_monograph", "known_pid_candidates": ["1272168"]}},
        )
        match = NDLSearchMatch(
            title="帝国憲法義解・皇室典範義解",
            url="https://dl.ndl.go.jp/pid/1272168",
            ndl_id="1272168",
        )

        class FakeResponse:
            def __init__(self, status_code, payload=None, headers=None):
                self.status_code = status_code
                self._payload = payload or {}
                self.headers = headers or {}

            def json(self):
                return self._payload

        def fake_get(url, **_kwargs):
            if "manifest.json" in url:
                return FakeResponse(200, {"label": "帝国憲法義解・皇室典範義解", "sequences": [{"canvases": [{}, {}]}]})
            if "fulltext-json" in url:
                return FakeResponse(200, {"text": "信仰歸依"}, {"content-type": "application/json"})
            return FakeResponse(404)

        with patch("modules.historical_citation_verifier.requests.get", side_effect=fake_get):
            self.assertTrue(verifier._probe_ndl_iiif_or_fulltext_json_availability(candidate, match))

        self.assertEqual(candidate.artifacts["iiif_image_ocr_available"]["ndl_id"], "1272168")
        self.assertEqual(candidate.artifacts["iiif_image_ocr_available"]["canvas_count"], 2)
        self.assertEqual(candidate.artifacts["ndl_fulltext_json_available"]["access_route"], "ndl_lab_fulltext_json")
        self.assertIn("iiif_image_ocr_available", candidate.notes)

    def test_source_graph_models_gaiko_bunsho_volume_series_with_document_queries(self):
        footnote = parse_footnote_text(
            "3",
            "外务省编：《日本外交文书》（外務省編：『日本外交文書』）第32卷，东京：外务省1955年版，第216～221页。",
        )

        node = build_source_graph_node(
            footnote,
            claim_text="约翰·海伊提出在华门户开放和机会均等原则，日本政府随后作出回答。",
        )
        plan = build_source_query_plan(
            footnote,
            claim_text="约翰·海伊提出在华门户开放和机会均等原则，日本政府随后作出回答。",
        )

        self.assertEqual(node.source_type, "volume_series")
        self.assertEqual(node.resolver, "NihonGaikoBunshoResolver")
        self.assertIn("第32巻", node.volume_terms)
        self.assertIn("3448126", node.known_pid_candidates)
        self.assertIn("ジョン・ヘイ", plan.person_bucket)
        self.assertIn("支那ニ於ケル商業上機會均等及門戸開放", plan.policy_bucket)
        global_queries = plan.global_fulltext_queries(max_queries=8)
        self.assertTrue(any("第32巻" in query for query in global_queries))
        self.assertIn("門戶開放", global_queries)
        self.assertIn("米國照會", global_queries)
        self.assertLess(global_queries.index("門戶開放"), 6)

    def test_source_resolver_uses_configured_gaiko_bunsho_volume_pid(self):
        tmpdir = Path(tempfile.mkdtemp())
        config_path = tmpdir / "source_resolvers.json"
        config_path.write_text(
            json.dumps(
                {
                    "nihon_gaiko_bunsho": {
                        "volumes": [
                            {
                                "volume": "第32巻",
                                "year": "明治32年",
                                "pid": "3448128",
                            }
                        ]
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        footnote = parse_footnote_text(
            "3a",
            "外务省编：《日本外交文书》（外務省編：『日本外交文書』）第32卷，东京：外务省1955年版，第216～221页。",
        )

        with patch.dict(os.environ, {"HISTORICAL_CITATION_SOURCE_RESOLVER_CONFIG": str(config_path)}):
            resolved = resolve_source(
                footnote,
                claim_text="明治32年，约翰·海伊提出门户开放照会，日本政府回答。",
            )

        self.assertEqual(resolved.resolver, "NihonGaikoBunshoResolver")
        self.assertEqual(resolved.pid_scope_strategy, "volume_pid_mapping_then_pid_snippet")
        self.assertIn("3448128", resolved.known_pid_candidates)
        self.assertNotIn("volume_pid_mapping_missing", resolved.warnings)
        self.assertIn("支那ニ於ケル商業上機會均等及門戸開放", resolved.target_pid_queries)
        self.assertTrue(resolved.target_pid_queries[0].startswith("支那ニ於ケル商業上"))
        self.assertEqual(resolved.target_pid_queries[1:3], ["門戶開放", "門戸開放"])

    def test_source_resolver_uses_configured_gaiko_claim_facets(self):
        tmpdir = Path(tempfile.mkdtemp())
        config_path = tmpdir / "source_resolvers.json"
        config_path.write_text(
            json.dumps(
                {
                    "nihon_gaiko_bunsho": {
                        "volumes": [
                            {
                                "volume": "特別巻",
                                "terms": ["特別巻", "実験文書"],
                                "pid": "999999",
                            }
                        ],
                        "claim_facets": [
                            {
                                "id": "experimental_document",
                                "trigger_terms": ["実験文書"],
                                "buckets": {
                                    "anchor": ["実験文書"],
                                    "theme": ["実験主題"],
                                    "action": ["実験回答"],
                                    "page_near": ["実験頁近傍"],
                                },
                                "target_pid_required_terms": ["実験回答"],
                                "pid_match_terms": ["実験文書"],
                            }
                        ],
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        footnote = ParsedFootnote(
            id="gaiko-config",
            text="外務省編：『日本外交文書 特別巻』，第12頁。",
            title="日本外交文書",
            ndl_keyword="日本外交文書 特別巻",
            page_numbers=[12],
        )

        with patch.dict(os.environ, {"HISTORICAL_CITATION_SOURCE_RESOLVER_CONFIG": str(config_path)}):
            resolved = resolve_source(
                footnote,
                claim_text="実験文書について実験主題を扱い、実験回答を行った。",
            )

        self.assertEqual(resolved.resolver, "NihonGaikoBunshoResolver")
        self.assertIn("999999", resolved.known_pid_candidates)
        self.assertIn("実験文書", resolved.query_buckets["anchor"])
        self.assertIn("実験主題", resolved.query_buckets["theme"])
        self.assertIn("実験回答", resolved.query_buckets["action"])
        self.assertIn("実験頁近傍", resolved.query_buckets["page_near"])
        self.assertIn("実験回答", resolved.target_pid_queries)
        self.assertNotIn("volume_pid_mapping_missing", resolved.warnings)

    def test_contained_document_resolver_adds_configured_claim_terms(self):
        tmpdir = Path(tempfile.mkdtemp())
        config_path = tmpdir / "source_resolvers.json"
        config_path.write_text(
            json.dumps(
                {
                    "contained_documents": {
                        "documents": [
                            {
                                "title": "山県有朋意見書",
                                "aliases": ["山縣有朋意見書"],
                                "pid": "3025431",
                                "person_terms": ["山縣有朋", "露國", "日露"],
                                "theme_terms": ["滿洲", "東三省"],
                                "action_terms": ["共同經營", "親交", "復讐心"],
                                "page_near_terms": ["外交政略"],
                            }
                        ]
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        footnote = ParsedFootnote(
            id="p2n8",
            text="大山梓编：《山县有朋意见书》，第306页。",
            title="山縣有朋意見書",
            page_numbers=[306],
        )

        with patch.dict(os.environ, {"HISTORICAL_CITATION_SOURCE_RESOLVER_CONFIG": str(config_path)}):
            resolved = resolve_source(
                footnote,
                claim_text="日本应与俄国共同经营中国东北，发展亲密交情，缓和复仇之心。",
            )
            recipe = build_manual_search_recipe(
                footnote,
                claim_text="日本应与俄国共同经营中国东北，发展亲密交情，缓和复仇之心。",
                current_status="fulltext_lead_only",
            )

        self.assertEqual(resolved.resolver, "ContainedDocumentResolver")
        self.assertIn("3025431", resolved.known_pid_candidates)
        self.assertIn("露國", resolved.query_buckets["person"])
        self.assertIn("滿洲", resolved.query_buckets["theme"])
        self.assertIn("共同經營", resolved.query_buckets["action"])
        self.assertIn("外交政略", resolved.query_buckets["page_near"])
        self.assertIn("共同經營", resolved.target_pid_queries)
        self.assertIn("復讐心", resolved.target_pid_queries)
        self.assertIn("共同經營", recipe["target_pid_queries"])
        self.assertIn("復讐心", recipe["target_pid_queries"])
        self.assertIn("滿洲", recipe["query_buckets"]["theme"])
        self.assertIn("共同經營", recipe["query_buckets"]["action"])
        self.assertIn("外交政略", recipe["query_buckets"]["page_near"])

    def test_source_resolver_maps_paris_peace_supplement_pid(self):
        footnote = ParsedFootnote(
            id="gaiko-paris",
            text="外务省编：《日本外交文書 大正期追補 巴里講和会議経過概要》，1971年版，第67-68页。",
            title="日本外交文書",
            ndl_keyword="日本外交文書 大正期追補 巴里講和会議経過概要 1971年",
            page_numbers=[67, 68],
        )

        resolved = resolve_source(
            footnote,
            claim_text="巴黎和会上，赤道以北德属太平洋群岛以委任统治划归日本，牧野决定接受会议决定。",
        )

        self.assertEqual(resolved.resolver, "NihonGaikoBunshoResolver")
        self.assertIn("11923430", resolved.known_pid_candidates)
        self.assertIn("巴里講和会議経過概要", resolved.query_buckets["document_title"])
        self.assertIn("帝國主張説明", resolved.query_buckets["document_heading"])
        self.assertIn("委任統治", resolved.query_buckets["document_heading"])
        self.assertIn("赤道以北", resolved.query_buckets["document_heading"])
        self.assertIn("巴里講和会議経過概要", resolved.query_buckets["anchor"])
        self.assertIn("委任統治", resolved.query_buckets["theme"])
        self.assertIn("決定ヲ受諾", resolved.query_buckets["action"])
        self.assertIn("赤道以北", resolved.query_buckets["page_near"])
        self.assertNotIn("山東", resolved.query_buckets["document_heading"])
        self.assertNotIn("還附ノ決定", resolved.query_buckets["document_heading"])
        self.assertNotIn("volume_pid_mapping_missing", resolved.warnings)

    def test_source_resolver_maps_washington_conference_pid_before_fulltext_leads(self):
        footnote = ParsedFootnote(
            id="gaiko-washington",
            text="外务省编：《日本外交文書 ワシントン会議 上》，1977年版，第120页。",
            title="日本外交文書",
            ndl_keyword="日本外交文書 ワシントン会議 上 軍備制限問題 1977年",
            page_numbers=[120],
        )

        resolved = resolve_source(footnote, claim_text="华盛顿会议上围绕海军军备限制问题展开交涉。")

        self.assertEqual(resolved.resolver, "NihonGaikoBunshoResolver")
        self.assertIn("11927523", resolved.known_pid_candidates)
        self.assertNotIn("3448160", resolved.known_pid_candidates)
        self.assertTrue(any("ワシントン" in query or "軍備制限" in query for query in resolved.target_pid_queries))
        self.assertIn("ワシントン会議", resolved.query_buckets["document_title"])
        self.assertIn("海軍軍備制限", resolved.query_buckets["document_heading"])
        self.assertIn("ワシントン会議", resolved.query_buckets["anchor"])
        self.assertIn("海軍軍備制限", resolved.query_buckets["theme"])
        self.assertIn("米国案ノ十対六", resolved.query_buckets["theme"])
        self.assertIn("製艦ヲ協定程度ニ制限", resolved.query_buckets["action"])
        self.assertIn("米国案ノ十対六", resolved.query_buckets["page_near"])
        self.assertTrue(any("ヒューズ" in query for query in resolved.target_pid_queries))
        self.assertTrue(any("比率" in query or "六割" in query or "十対" in query or "勢力比" in query or "主力艦" in query for query in resolved.target_pid_queries))

    def test_source_resolver_diary_adds_configured_claim_facets_to_plan(self):
        footnote = ParsedFootnote(
            id="diary-facet",
            text="『原敬日記』1908年，第325頁。",
            title="原敬日記",
            page_numbers=[325],
        )

        resolved = resolve_source(
            footnote,
            claim_text="美国受到经济不景气影响，但将来会对世界产生影响。",
        )

        self.assertEqual(resolved.resolver, "DiaryDateResolver")
        self.assertIn("米国", resolved.query_buckets["anchor"])
        self.assertIn("経済", resolved.query_buckets["theme"])
        self.assertIn("将来", resolved.query_buckets["theme"])
        self.assertIn("米国", resolved.target_pid_queries)
        self.assertTrue(any(term in resolved.target_pid_queries for term in ("経済", "經濟")))
        self.assertFalse(any("1981" in query for query in resolved.target_pid_queries))

    def test_source_resolver_kindai_taima_uses_configured_facets(self):
        footnote = parse_footnote_text(
            "p4n9",
            "［日］《静岡県で大麻につき流言》，《日本近代思想大系 5：宗教と国家》，第 190 页。",
        )

        resolved = resolve_source(
            footnote,
            claim_text="大麻的神符会化为蝴蝶，其时该户将遭时疫，故要在化蝶前焚毁、冲走大麻。",
        )

        self.assertEqual(resolved.resolver, "NihonKindaiShisoTaikeiResolver")
        self.assertIn("13260166", resolved.known_pid_candidates)
        self.assertIn("神宮大麻", resolved.query_buckets["theme"])
        self.assertIn("水火ニ投ズ", resolved.query_buckets["action"])
        self.assertIn("大麻ノ神ノ字ガ蝶", resolved.query_buckets["page_near"])
        self.assertIn("大麻ノ神ノ字ガ蝶", resolved.target_pid_queries)
        self.assertIn("水火ニ投ズ", resolved.target_pid_queries)

    def test_volume_series_early_general_context_is_front_matter_body_lead(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p6-fp6n6",
            paragraph_index=6,
            paragraph_text="休斯提出海军军备限制，规定主力舰比例为10:10:6。",
            translation_text="休斯提出海军军备限制，规定主力舰比例为10:10:6。",
            footnote_id="p6n6",
            footnote=ParsedFootnote(
                id="p6n6",
                text="外务省编：《日本外交文書 ワシントン会議 上》，1977年版。",
                title="日本外交文書",
            ),
            artifacts={
                "source_resolver_plan": {
                    "source_type": "volume_series",
                    "known_pid_candidates": ["11927523"],
                    "query_buckets": {
                        "theme": ["米国案ノ十対六", "海軍勢力比"],
                        "page_near": ["米国案ノ十対六"],
                    },
                }
            },
        )
        hint = {
            "pid": "11927523",
            "book_id": "11927523",
            "pdf_page": 8,
            "query": "海軍軍備制限問題",
            "snippet": (
                "英両国ニ対シ一会議開催ニ至ルマデノ経緯 "
                "日英米三国間ニ今後五ケ年間三国ノ製艦ヲ協定程度ニ制限スル一条約ヲ協定スルノ目的"
            ),
            "expanded_context": (
                "英両国ニ対シ一会議開催ニ至ルマデノ経緯 "
                "日英米三国間ニ今後五ケ年間三国ノ製艦ヲ協定程度ニ制限スル一条約ヲ協定スルノ目的"
            ),
        }

        category = verifier._fulltext_hint_lead_category(candidate, hint)
        _score, reasons = verifier._score_fulltext_context_candidate(
            candidate,
            hint,
            hint["expanded_context"],
        )

        self.assertEqual(category, "front_matter_body_lead")
        self.assertIn("front_matter_body_lead_penalty", reasons)

    def test_fulltext_context_penalizes_early_gaiko_title_page_hit(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p4-fp4n5",
            paragraph_index=4,
            paragraph_text="巴黎和会。",
            translation_text="牧野代表在巴黎和会上说明帝国主张。",
            footnote_id="p4n5",
            footnote=ParsedFootnote(
                id="p4n5",
                text="外务省编：《日本外交文书》巴黎讲和会议经过概要，1971年版。",
                title="日本外交文書",
                ndl_keyword="日本外交文書 巴里講和会議経過概要",
            ),
            artifacts={
                "source_resolver_plan": {
                    "source_type": "volume_series",
                    "known_pid_candidates": ["11923430"],
                    "target_pid_queries": ["巴里講和会議経過概要", "帝國主張説明", "牧野"],
                    "query_buckets": {
                        "document_title": ["巴里講和会議経過概要"],
                        "document_heading": ["帝國主張説明"],
                        "person": ["牧野"],
                    },
                }
            },
        )
        title_hint = {
            "pid": "11923430",
            "book_id": "11923430",
            "query": "巴里講和会議経過概要",
            "snippet": "巴里講和会議経過概要",
            "pdf_page": 3,
        }
        body_hint = {
            "pid": "11923430",
            "book_id": "11923430",
            "query": "牧野",
            "snippet": "帝國主張説明(牧野男)",
            "expanded_context": "帝國主張説明(牧野男) 二、聯盟委員管理。",
            "pdf_page": 9,
        }

        self.assertEqual(verifier._fulltext_hint_lead_category(candidate, title_hint), "title_or_series_only")
        self.assertEqual(verifier._fulltext_hint_lead_category(candidate, body_hint), "body_candidate")
        candidate.artifacts["ndl_fulltext_hints"] = [title_hint, body_hint]
        ordered = verifier._ordered_fulltext_hints_for_candidate(candidate, preferred_pid="11923430")
        self.assertEqual(ordered[0]["query"], "牧野")
        _score, reasons = verifier._score_fulltext_context_candidate(candidate, body_hint, body_hint["expanded_context"])
        self.assertTrue(any("document_heading:帝国主張説明" in reason for reason in reasons))

    def test_volume_series_context_missing_theme_is_demoted(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p4-fp4n5",
            paragraph_index=4,
            paragraph_text="巴黎和会上日本取得南洋委任统治。",
            translation_text="牧野决定接受会议决定，达成赤道以北南洋委任统治目标。",
            footnote_id="p4n5",
            footnote=ParsedFootnote(id="p4n5", text="日本外交文書。", title="日本外交文書"),
            artifacts={
                "source_resolver_plan": {
                    "source_type": "volume_series",
                    "query_buckets": {
                        "person": ["牧野"],
                        "action": ["決定ヲ受諾"],
                        "theme": ["委任統治", "南洋群島"],
                        "page_near": ["赤道以北"],
                    },
                }
            },
        )
        wrong_theme_hint = {
            "pid": "11923430",
            "query": "牧野委員",
            "snippet": "還附ノ決定ヲ講和會議ニ於テ見ムコトヲ希望フ。牧野委員日本ノ膠州灣ヲ攻略シタル趣旨ハ...",
            "pdf_page": 35,
        }
        theme_hint = {
            "pid": "11923430",
            "query": "委任統治",
            "snippet": "英國ノ委任統治案提出附委任統治案ニ關スル牧野男トロイドジョージトノ内談。",
            "pdf_page": 39,
        }

        wrong_score, wrong_reasons = verifier._score_fulltext_context_candidate(
            candidate,
            wrong_theme_hint,
            wrong_theme_hint["snippet"],
        )
        theme_score, theme_reasons = verifier._score_fulltext_context_candidate(
            candidate,
            theme_hint,
            theme_hint["snippet"],
        )

        self.assertIn("missing_volume_series_theme", wrong_reasons)
        self.assertNotIn("missing_volume_series_theme", theme_reasons)
        self.assertGreater(theme_score, wrong_score)

    def test_contained_document_title_only_fulltext_hit_is_lead(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p2-fp2n8",
            paragraph_index=2,
            paragraph_text="日本应与俄国发展亲密交情。",
            translation_text="日本应与俄国发展亲密交情，缓和其复仇之心。",
            footnote_id="p2n8",
            footnote=ParsedFootnote(
                id="p2n8",
                text="大山梓编：《山县有朋意见书》，东京：原书房1965年版，第306页。",
                title="山縣有朋意見書",
                contained_title="山縣有朋意見書",
                page_numbers=[306],
            ),
            artifacts={"source_resolver_plan": {"source_type": "contained_document"}},
        )
        title_only_hint = {
            "pid": "3025431",
            "book_id": "3025431",
            "query": "山縣有朋意見書 山縣有朋意見書",
            "snippet": "海軍々備の必要から扶桑、金剛、比叡の三艦が英国で起工される山縣有朋意見書",
            "expanded_context": "海軍々備の必要から扶桑、金剛、比叡の三艦が英国で起工される山縣有朋意見書",
            "pdf_page": 14,
        }

        category = verifier._fulltext_hint_lead_category(candidate, title_only_hint)
        _score, reasons = verifier._score_fulltext_context_candidate(
            candidate,
            title_only_hint,
            title_only_hint["expanded_context"],
        )

        self.assertEqual(category, "title_or_series_only")
        self.assertIn("title_or_series_only_penalty", reasons)

    def test_gaiko_open_door_compound_packet_groups_split_facets(self):
        verifier = HistoricalCitationVerifier(
            review_llm_client=DummyLLMClient(
                json.dumps(
                    {
                        "decision": "partial_support",
                        "best_context_id": "ctx2",
                        "supporting_context_ids": ["ctx2"],
                        "best_sentence_index": 0,
                        "confidence": 0.7,
                        "reason": "ctx2 covers the proposal but does not by itself cover Japan's reply.",
                    },
                    ensure_ascii=False,
                )
            )
        )
        candidate = CitationCandidate(
            candidate_id="p2-fp2n1",
            paragraph_index=2,
            paragraph_text="海伊提出门户开放原则并得到日本赞同。",
            translation_text="海伊提出门户开放原则并得到日本赞同。",
            footnote_id="p2n1",
            footnote=ParsedFootnote(
                id="p2n1",
                text="外务省编：《日本外交文書》第32巻，1955年，第32-34页。",
                title="日本外交文書",
                ndl_keyword="日本外交文書 第32巻",
                page_numbers=[32, 34],
            ),
            artifacts={
                "source_resolver_plan": {
                    "source_type": "volume_series",
                    "known_pid_candidates": ["3448128"],
                    "target_pid_queries": ["日本外交文書 第32巻 門戶開放"],
                    "query_buckets": {
                        "document_heading": ["合衆國ノ提議"],
                        "policy": ["日本國政府ハ", "承諾シタル", "門戶開放"],
                    },
                }
            },
        )
        contexts = [
            {
                "context_id": "ctx1",
                "pid": "3448128",
                "pdf_page": 34,
                "query": "日本國政府ハ",
                "cleaned_context": "日本國政府ハ右門戶開放ノ主義ヲ承諾シタル旨回答セリ。",
                "lead_category": "body_candidate",
                "score": 18.6,
            },
            {
                "context_id": "ctx2",
                "pid": "3448128",
                "pdf_page": 32,
                "query": "日本外交文書 第32巻 門戶開放",
                "cleaned_context": "清國ニ於ケル門戶開放ニ關スル合衆國ノ提議。",
                "lead_category": "body_candidate",
                "score": 18.5,
            },
        ]

        packet = verifier._build_fulltext_compound_evidence_packet(candidate, contexts)
        selected = verifier._select_fulltext_context_candidate(candidate, contexts)

        self.assertIsNotNone(packet)
        self.assertTrue(packet["complete"])
        self.assertEqual(selected["context_id"], "ctx2")
        stored_packet = candidate.artifacts["fulltext_compound_evidence_packet"]
        self.assertTrue(stored_packet["complete"])
        self.assertEqual(
            {facet["facet_id"] for facet in stored_packet["facets"] if facet["covered"]},
            {"us_proposal", "open_door_principle", "japan_acceptance"},
        )
        self.assertEqual(candidate.artifacts["fulltext_compound_evidence_review_gap"]["decision"], "partial_support")
        self.assertIn("fulltext_compound_evidence_requires_manual_review", candidate.notes)

    def test_gaiko_open_door_direct_review_adds_missing_compound_contexts(self):
        verifier = HistoricalCitationVerifier(
            review_llm_client=DummyLLMClient(
                json.dumps(
                    {
                        "decision": "direct_support",
                        "best_context_id": "ctx1",
                        "supporting_context_ids": ["ctx1"],
                        "best_sentence_index": 1,
                        "exact_sentence": "日本國政府ハ右門戶開放ノ主義ヲ承諾シタル旨回答セリ。",
                        "confidence": 0.95,
                        "reason": "ctx1 proves Japan accepted the principle.",
                    },
                    ensure_ascii=False,
                )
            )
        )
        candidate = CitationCandidate(
            candidate_id="p2-fp2n1",
            paragraph_index=2,
            paragraph_text="海伊提出门户开放原则并得到日本赞同。",
            translation_text="海伊提出门户开放原则并得到日本赞同。",
            footnote_id="p2n1",
            footnote=ParsedFootnote(
                id="p2n1",
                text="外务省编：《日本外交文書》第32巻，1955年，第32-34页。",
                title="日本外交文書",
                ndl_keyword="日本外交文書 第32巻",
                page_numbers=[32, 34],
            ),
            artifacts={
                "source_resolver_plan": {
                    "source_type": "volume_series",
                    "query_buckets": {
                        "document_heading": ["委任統治", "赤道以北", "獨領南洋", "牧野男", "決定ヲ受諾"],
                        "document_title": ["巴里講和会議経過概要"],
                    },
                }
            },
        )
        contexts = [
            {
                "context_id": "ctx1",
                "pdf_page": 34,
                "query": "日本國政府ハ",
                "cleaned_context": "日本國政府ハ右門戶開放ノ主義ヲ承諾シタル旨回答セリ。",
                "lead_category": "body_candidate",
            },
            {
                "context_id": "ctx2",
                "pdf_page": 32,
                "query": "合衆國ノ提議",
                "cleaned_context": "清國ニ於ケル門戶開放ニ關スル合衆國ノ提議。",
                "lead_category": "body_candidate",
            },
        ]

        verifier._select_fulltext_context_candidate(candidate, contexts)

        review = candidate.artifacts["llm_review"]
        self.assertEqual(review["decision"], "direct_support")
        self.assertEqual(review["supporting_context_ids"], ["ctx1", "ctx2"])
        self.assertTrue(review["compound_evidence_packet_used"])
        self.assertEqual(
            candidate.artifacts["fulltext_llm_review_basis"],
            "ndl_expanded_snippet_context_candidates_plus_compound_packet",
        )

    def test_volume_series_generic_compound_packet_uses_query_buckets(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p5-fp5n1",
            paragraph_index=5,
            paragraph_text="陆奥在条约改正问题上提出意见。",
            translation_text="陆奥在条约改正问题上提出意见。",
            footnote_id="p5n1",
            footnote=ParsedFootnote(
                id="p5n1",
                text="外务省编：《日本外交文書》，第120页。",
                title="日本外交文書",
                ndl_keyword="日本外交文書 条約改正",
            ),
            artifacts={
                "source_resolver_plan": {
                    "source_type": "volume_series",
                    "query_buckets": {
                        "document_heading": ["条約改正意見"],
                        "person": ["陸奥宗光"],
                        "document_title": ["日本外交文書"],
                    },
                }
            },
        )
        contexts = [
            {
                "context_id": "ctx1",
                "pdf_page": 8,
                "query": "条約改正意見",
                "cleaned_context": "条約改正意見ニ關シ外務省内ニテ議ス。",
                "lead_category": "body_candidate",
            },
            {
                "context_id": "ctx2",
                "pdf_page": 9,
                "query": "陸奥宗光",
                "cleaned_context": "陸奥宗光ハ右意見ヲ提出セリ。",
                "lead_category": "body_candidate",
            },
        ]

        packet = verifier._build_fulltext_compound_evidence_packet(candidate, contexts)

        self.assertIsNotNone(packet)
        self.assertEqual(packet["packet_type"], "volume_series_query_bucket_compound_claim")
        self.assertTrue(packet["complete"])
        self.assertEqual(packet["required_facet_ids"], ["bucket_document_heading", "bucket_person"])
        self.assertEqual(packet["supporting_context_ids"], ["ctx1", "ctx2"])

    def test_paris_mandate_packet_requires_acceptance_action_not_weak_decision_lead(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p4-fp4n5",
            paragraph_index=4,
            paragraph_text="日本代表牧野伸显决定接受会议决定，从而使日本达成了第一个既定目标。",
            translation_text="日本代表牧野伸显决定接受会议决定，从而使日本达成了第一个既定目标",
            footnote_id="p4n5",
            footnote=ParsedFootnote(
                id="p4n5",
                text="外务省编：《日本外交文書》巴黎讲和会议经过概要。",
                title="日本外交文書",
            ),
            artifacts={
                "source_resolver_plan": {
                    "source_type": "volume_series",
                    "query_buckets": {
                        "document_heading": ["委任統治", "赤道以北", "獨領南洋", "牧野男", "決定ヲ受諾"],
                        "document_title": ["巴里講和会議経過概要"],
                    },
                }
            },
        )
        contexts = [
            {
                "context_id": "ctx1",
                "pdf_page": 32,
                "query": "獨領南洋",
                "cleaned_context": "赤道以北ノ獨領南洋群島ニ關シ委任統治ノ形式ヲ議ス。",
                "lead_category": "body_candidate",
            },
            {
                "context_id": "ctx2",
                "pdf_page": 39,
                "query": "牧野男",
                "cleaned_context": "英國ノ委任統治案ニ關シ會議終了後牧野男ト協議ス。",
                "lead_category": "body_candidate",
            },
            {
                "context_id": "ctx3",
                "pdf_page": 255,
                "query": "會議ノ決定",
                "cleaned_context": "各國ノ投票權ニ付一國一票説出テシモ結局五國會議ノ決定ニ俟ツコトニ決ス。",
                "lead_category": "body_candidate",
            },
        ]

        packet = verifier._build_fulltext_compound_evidence_packet(candidate, contexts)

        self.assertIsNotNone(packet)
        self.assertEqual(packet["packet_type"], "volume_series_paris_mandate_compound_claim")
        self.assertFalse(packet["complete"])
        facets = {facet["facet_id"]: facet for facet in packet["facets"]}
        self.assertTrue(facets["mandate_territory"]["covered"])
        self.assertTrue(facets["mandate_system"]["covered"])
        self.assertTrue(facets["japanese_actor_makino"]["covered"])
        self.assertFalse(facets["decision_acceptance_action"]["covered"])
        self.assertTrue(facets["weak_meeting_decision_lead"]["covered"])
        self.assertIn("decision_acceptance_action", packet["required_facet_ids"])

    def test_paris_mandate_packet_complete_when_acceptance_action_is_present(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p4-fp4n5",
            paragraph_index=4,
            paragraph_text="日本代表牧野伸显决定接受会议决定，从而使日本达成了第一个既定目标。",
            translation_text="日本代表牧野伸显决定接受会议决定，从而使日本达成了第一个既定目标",
            footnote_id="p4n5",
            footnote=ParsedFootnote(
                id="p4n5",
                text="外务省编：《日本外交文書》巴黎讲和会议经过概要。",
                title="日本外交文書",
            ),
            artifacts={
                "source_resolver_plan": {
                    "source_type": "volume_series",
                    "query_buckets": {
                        "document_heading": ["委任統治", "赤道以北", "獨領南洋", "牧野男", "決定ヲ受諾"],
                        "document_title": ["巴里講和会議経過概要"],
                    },
                }
            },
        )
        contexts = [
            {
                "context_id": "ctx1",
                "pdf_page": 32,
                "query": "獨領南洋",
                "cleaned_context": "赤道以北ノ獨領南洋群島ニ關シ委任統治ノ形式ヲ議ス。",
                "lead_category": "body_candidate",
            },
            {
                "context_id": "ctx2",
                "pdf_page": 39,
                "query": "牧野男",
                "cleaned_context": "牧野男ハ右委任統治案ニ異議ナキ旨述ヘ決定ヲ受諾ス。",
                "lead_category": "body_candidate",
            },
            {
                "context_id": "ctx3",
                "pdf_page": 40,
                "query": "目的ヲ達成",
                "cleaned_context": "帝國委員ハ南洋群島ニ關スル主張ヲ貫徹シ目的ヲ達成セリ。",
                "lead_category": "body_candidate",
            },
        ]

        packet = verifier._build_fulltext_compound_evidence_packet(candidate, contexts)

        self.assertIsNotNone(packet)
        self.assertTrue(packet["complete"])
        self.assertEqual(
            packet["required_facet_ids"],
            [
                "mandate_territory",
                "mandate_system",
                "japanese_actor_makino",
                "decision_acceptance_action",
                "goal_or_outcome",
            ],
        )
        self.assertEqual(set(packet["supporting_context_ids"]), {"ctx1", "ctx2", "ctx3"})

    def test_washington_naval_limitation_packet_groups_ratio_and_speaker(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p6-fp6n6",
            paragraph_index=6,
            paragraph_text="美国国务卿休斯提出限制海军军备，规定主力舰比例为10:10:6。",
            translation_text="美国国务卿休斯提出限制海军军备，规定主力舰比例为10:10:6。",
            footnote_id="p6n6",
            footnote=ParsedFootnote(
                id="p6n6",
                text="外务省编：《日本外交文書 ワシントン会議 上》，1977年版。",
                title="日本外交文書",
            ),
            artifacts={"source_resolver_plan": {"source_type": "volume_series"}},
        )
        contexts = [
            {
                "context_id": "ctx1",
                "pdf_page": 8,
                "query": "海軍軍備制限問題",
                "cleaned_context": "日英米三国間ニ今後五ケ年間三国ノ製艦ヲ協定程度ニ制限スル一条約。",
                "lead_category": "body_candidate",
            },
            {
                "context_id": "ctx2",
                "pdf_page": 164,
                "query": "比率",
                "cleaned_context": "加藤、ヒューズ及ビバルフォアト会合シ比率、太平洋防備制限各問題ニツキ討議。",
                "lead_category": "body_candidate",
            },
            {
                "context_id": "ctx3",
                "pdf_page": 143,
                "query": "米国案ノ十対六",
                "cleaned_context": "報知米国案ノ十対六ノ比率ハ其根拠奈辺ニアルヤ了解ニ苦シム処ナリ。",
                "lead_category": "body_candidate",
            },
        ]

        packet = verifier._build_fulltext_compound_evidence_packet(candidate, contexts)

        self.assertIsNotNone(packet)
        self.assertEqual(packet["packet_type"], "volume_series_washington_naval_limitation_compound_claim")
        self.assertTrue(packet["complete"])
        self.assertEqual(
            packet["required_facet_ids"],
            ["naval_limitation_proposal", "hughes_or_us_speaker", "exact_ten_ten_six_ratio"],
        )
        self.assertEqual(packet["supporting_context_ids"], ["ctx1", "ctx2", "ctx3"])

    def test_washington_exact_ratio_packet_incomplete_without_exact_ratio(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p6-fp6n6",
            paragraph_index=6,
            paragraph_text="美国国务卿休斯提出限制海军军备，规定主力舰比例为10:10:6。",
            translation_text="美国国务卿休斯提出限制海军军备，规定主力舰比例为10:10:6。",
            footnote_id="p6n6",
            footnote=ParsedFootnote(
                id="p6n6",
                text="外务省编：《日本外交文書 ワシントン会議 上》，1977年版。",
                title="日本外交文書",
            ),
            artifacts={"source_resolver_plan": {"source_type": "volume_series"}},
        )
        contexts = [
            {
                "context_id": "ctx1",
                "pdf_page": 8,
                "query": "海軍軍備制限問題",
                "cleaned_context": "日英米三国間ニ今後五ケ年間三国ノ製艦ヲ協定程度ニ制限スル一条約。",
                "lead_category": "body_candidate",
            },
            {
                "context_id": "ctx2",
                "pdf_page": 164,
                "query": "比率",
                "cleaned_context": "加藤、ヒューズ及ビバルフォアト会合シ比率、太平洋防備制限各問題ニツキ討議。",
                "lead_category": "body_candidate",
            },
        ]

        packet = verifier._build_fulltext_compound_evidence_packet(candidate, contexts)

        self.assertIsNotNone(packet)
        self.assertFalse(packet["complete"])
        self.assertIn("exact_ten_ten_six_ratio", packet["required_facet_ids"])
        exact_facet = next(facet for facet in packet["facets"] if facet["facet_id"] == "exact_ten_ten_six_ratio")
        self.assertFalse(exact_facet["covered"])

    def test_failed_formal_review_does_not_promote_heuristic_direct_support(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p6-fp6n6",
            paragraph_index=6,
            paragraph_text="休斯提出海军军备限制。",
            translation_text="休斯提出海军军备限制。",
            footnote_id="p6n6",
            footnote=ParsedFootnote(id="p6n6", text="日本外交文書。", title="日本外交文書"),
            artifacts={
                "llm_review": {
                    "decision": "direct_support",
                    "confidence": 0.92,
                    "reason": "heuristic direct",
                    "provider": "heuristic_multi_context",
                    "llm_review_failed": True,
                    "llm_review_fallback_heuristic": True,
                    "llm_error": "ReadTimeout",
                }
            },
        )

        verifier._apply_fulltext_only_review_status(candidate)

        self.assertEqual(candidate.verification_status, "fulltext_only_partial_support")
        self.assertEqual(candidate.support_status, "fulltext_only_partial_support")
        self.assertIn("formal_review_failed_heuristic_direct_not_promoted", candidate.notes)
        self.assertIn("formal_review_failed_direct_downgraded", candidate.artifacts)

    def test_volume_series_generic_packet_does_not_require_publication_year(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p4-fp4n5",
            paragraph_index=4,
            paragraph_text="牧野代表接受会议决定。",
            translation_text="牧野代表接受会议决定。",
            footnote_id="p4n5",
            footnote=ParsedFootnote(
                id="p4n5",
                text="外务省编：《日本外交文書 大正期追補 巴里講和会議経過概要》，1971年版。",
                title="日本外交文書",
            ),
            artifacts={
                "source_resolver_plan": {
                    "source_type": "volume_series",
                    "query_buckets": {
                        "document_heading": ["帝國主張説明", "牧野男"],
                        "date": ["1971年"],
                        "document_title": ["巴里講和会議経過概要"],
                    },
                }
            },
        )
        contexts = [
            {
                "context_id": "ctx1",
                "pdf_page": 9,
                "query": "牧野男",
                "cleaned_context": "帝國主張説明(牧野男) 二、聯盟委員管理。",
                "lead_category": "body_candidate",
            }
        ]

        packet = verifier._build_fulltext_compound_evidence_packet(candidate, contexts)

        self.assertIsNone(packet)

    def test_volume_series_hint_expansion_diversifies_queries(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p6-fp6n6",
            paragraph_index=6,
            paragraph_text="休斯提出海军军备限制，规定主力舰比例为10:10:6。",
            translation_text="休斯提出海军军备限制，规定主力舰比例为10:10:6。",
            footnote_id="p6n6",
            footnote=ParsedFootnote(id="p6n6", text="日本外交文書 ワシントン会議 上", title="日本外交文書"),
            artifacts={"source_resolver_plan": {"source_type": "volume_series"}},
        )
        hints = [
            {"query": "日本外交文書 海軍軍備制限", "snippet": f"海軍軍備制限 {index}", "pdf_page": index}
            for index in range(6)
        ]
        hints.extend(
            [
                {"query": "ヒューズ", "snippet": "ヒューズ国務長官", "pdf_page": 22},
                {"query": "比率", "snippet": "主力艦比率", "pdf_page": 154},
                {"query": "米国案ノ十対六", "snippet": "米国案ノ十対六ノ比率", "pdf_page": 143},
            ]
        )

        selected = verifier._select_fulltext_hints_to_expand(candidate, hints, limit=4)

        selected_queries = [hint["query"] for hint in selected]
        self.assertEqual(selected_queries[0], "米国案ノ十対六")
        self.assertIn("ヒューズ", selected_queries[:3])
        self.assertIn("日本外交文書 海軍軍備制限", selected_queries)

    def test_claim_query_hit_is_prioritized_over_contained_title_body_hit(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p6-fp6n5",
            paragraph_index=6,
            paragraph_text="日莲宗提出“只得中和，阴不害阳，恶不妨善”。",
            translation_text="只得中和，阴不害阳，恶不妨善",
            footnote_id="p6n5",
            footnote=ParsedFootnote(
                id="p6n5",
                text="《諸宗説教要義》，《明治仏教思想資料集成：第二巻》，第264页。",
                title="諸宗説教要義",
                host_title="明治仏教思想資料集成：第二巻",
                contained_title="諸宗説教要義",
            ),
            artifacts={
                "source_resolver_plan": {
                    "source_type": "contained_document",
                    "target_pid_queries": ["諸宗説教要義"],
                    "query_buckets": {
                        "contained": ["諸宗説教要義"],
                        "host": ["明治仏教思想資料集成：第二巻"],
                    },
                },
                "ndl_fulltext_hints": [
                    {
                        "pid": "12223083",
                        "book_id": "12223083",
                        "query": "諸宗説教要義",
                        "snippet": "諸宗説教要義禪宗大徳寺妙心寺 恭ク惟ルニ聖運恢復ノ際ニ膺リ",
                        "expanded_context": "諸宗説教要義禪宗大徳寺妙心寺 恭ク惟ルニ聖運恢復ノ際ニ膺リ、敬神愛國ノ旨ヲ體スヘシ。",
                        "pdf_page": 138,
                    },
                    {
                        "pid": "12223083",
                        "book_id": "12223083",
                        "query": "阴不害阳",
                        "snippet": "天不能無陰人不能無惡、只中和ヲ得ハ陰不害陽惡不妨善",
                        "expanded_context": "第二天理人道ヲ明ニスヘキ事曰ク、天不能無陰人不能無惡、只中和ヲ得ハ陰不害陽惡不妨善。",
                        "pdf_page": 140,
                    },
                ],
            },
        )

        ordered = verifier._ordered_fulltext_hints_for_candidate(candidate, preferred_pid="12223083")
        self.assertEqual(ordered[0]["query"], "阴不害阳")
        self.assertTrue(verifier._hint_has_claim_snippet_evidence(candidate, ordered[0]))

        contexts = verifier._expand_fulltext_context_candidates(
            candidate,
            preferred_pid="12223083",
            max_candidates=2,
            max_hints_to_expand=2,
        )
        self.assertEqual(contexts[0]["query"], "阴不害阳")
        self.assertTrue(contexts[0]["claim_evidence"])
        self.assertGreater(contexts[0]["score"], contexts[1]["score"])

    def test_generic_claim_query_is_not_strong_claim_evidence(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p4-fp4n5",
            paragraph_index=4,
            paragraph_text="牧野决定接受会议决定。",
            translation_text="接受会议决定",
            footnote_id="p4n5",
            footnote=ParsedFootnote(
                id="p4n5",
                text="《日本外交文書》巴黎讲和会议经过概要。",
                title="日本外交文書",
            ),
            artifacts={"source_resolver_plan": {"source_type": "volume_series"}},
        )
        generic_hint = {
            "pid": "11923430",
            "book_id": "11923430",
            "query": "會議ノ決定",
            "snippet": "各國ノ投票權ニ付一國一票説出テシモ結局五國會議ノ決定ニ俟ツコトニ決ス",
            "expanded_context": "各國ノ投票權ニ付一國一票説出テシモ結局五國會議ノ決定ニ俟ツコトニ決ス。",
            "pdf_page": 255,
        }

        self.assertFalse(verifier._hint_has_claim_snippet_evidence(candidate, generic_hint))
        _score, reasons = verifier._score_fulltext_context_candidate(
            candidate,
            generic_hint,
            generic_hint["expanded_context"],
        )
        self.assertFalse(any("core_terms=会議ノ決定" in reason for reason in reasons))

    def test_fulltext_context_expansion_cache_reuses_same_pid_hit(self):
        verifier = HistoricalCitationVerifier()

        def build_candidate(candidate_id: str) -> CitationCandidate:
            return CitationCandidate(
                candidate_id=candidate_id,
                paragraph_index=1,
                paragraph_text="The claim needs source context.",
                translation_text="The claim needs source context.",
                footnote_id="fn1",
                footnote=ParsedFootnote(
                    id="fn1",
                    text="Contained document, in Host collection, p. 12.",
                    title="Contained document",
                    host_title="Host collection",
                    contained_title="Contained document",
                    page_numbers=[12],
                ),
                artifacts={
                    "source_resolver_plan": {
                        "source_type": "source_collection",
                        "known_pid_candidates": ["12345"],
                        "target_pid_queries": ["Contained document"],
                    },
                    "ndl_fulltext_hints": [
                        {
                            "pid": "12345",
                            "book_id": "12345",
                            "query": "Contained document",
                            "snippet": "Contained document lead text",
                            "pdf_page": 12,
                            "cid": "cid-12",
                        }
                    ],
                },
            )

        expanded = SimpleNamespace(
            context_text="Contained document body context. It gives enough evidence for the claim.",
            status="snippet_expanded",
            note="same-page expansion",
            evidence_hits=[{"cid": "cid-12"}],
        )
        first_candidate = build_candidate("first")
        second_candidate = build_candidate("second")

        with patch(
            "modules.historical_citation_verifier.expand_ndl_snippet_context",
            return_value=expanded,
        ) as expand_mock:
            first_contexts = verifier._expand_fulltext_context_candidates(
                first_candidate,
                preferred_pid="12345",
                max_hints_to_expand=1,
            )
            second_contexts = verifier._expand_fulltext_context_candidates(
                second_candidate,
                preferred_pid="12345",
                max_hints_to_expand=1,
            )

        self.assertEqual(expand_mock.call_count, 1)
        self.assertEqual(second_candidate.artifacts.get("fulltext_context_cache_hits"), 1)
        self.assertEqual(first_contexts[0]["cleaned_context"], second_contexts[0]["cleaned_context"])

    def test_fulltext_context_expansion_emits_progress_callback(self):
        verifier = HistoricalCitationVerifier()
        events = []
        verifier._progress_event_callback = lambda **payload: events.append(payload)
        candidate = CitationCandidate(
            candidate_id="p4-fp4n5",
            paragraph_index=4,
            paragraph_text="Japan explained the mandate issue.",
            translation_text="Japan explained the mandate issue.",
            footnote_id="p4n5",
            footnote=ParsedFootnote(
                id="p4n5",
                text="日本外交文書 巴里講和会議経過概要, pp.58-59.",
                title="日本外交文書",
                page_numbers=[58, 59],
                source_type="volume_series",
            ),
            artifacts={
                "source_resolver_plan": {"source_type": "volume_series"},
                "ndl_fulltext_hints": [
                    {
                        "pid": "11923430",
                        "book_id": "11923430",
                        "query": "牧野男 委任統治",
                        "snippet": "牧野男 委任統治",
                        "expanded_context": "牧野男ハ委任統治問題ニ付帝國主張ヲ説明セリ。",
                        "pdf_page": 39,
                    }
                ],
            },
        )

        contexts = verifier._expand_fulltext_context_candidates(
            candidate,
            preferred_pid="11923430",
            max_candidates=1,
            max_hints_to_expand=1,
        )

        self.assertEqual(len(contexts), 1)
        subphase_events = [(event["event"], event["subphase"]) for event in events]
        self.assertIn(("worker_stage_started", "snippet_context_expansion"), subphase_events)
        self.assertIn(("worker_stage_completed", "snippet_context_expansion"), subphase_events)
        completed = [
            event
            for event in events
            if event["event"] == "worker_stage_completed"
            and event["subphase"] == "snippet_context_expansion"
        ][0]
        self.assertEqual(completed["status"], "contexts_found")
        self.assertEqual(completed["metrics"]["context_count"], 1)

    def test_fulltext_context_selection_emits_llm_review_progress(self):
        class FakeReviewClient:
            provider = "ollama"
            model = "gemma4:e4b"

            def health_check(self):
                return {"provider": self.provider, "model": self.model}

        verifier = HistoricalCitationVerifier(review_llm_client=FakeReviewClient())
        events = []
        verifier._progress_event_callback = lambda **payload: events.append(payload)
        candidate = CitationCandidate(
            candidate_id="p6-fp6n6",
            paragraph_index=6,
            paragraph_text="Washington conference claim.",
            translation_text="Washington conference claim.",
            footnote_id="p6n6",
            footnote=ParsedFootnote(id="p6n6", text="日本外交文書, pp.170-171.", title="日本外交文書"),
        )
        contexts = [
            {
                "context_id": "ctx1",
                "cleaned_context": "ワシントン會議ノ一般説明。",
                "expanded_context": "ワシントン會議ノ一般説明。",
                "lead_category": "body_candidate",
            },
            {
                "context_id": "ctx2",
                "cleaned_context": "米国案ノ十対六ニ関スル説明。",
                "expanded_context": "米国案ノ十対六ニ関スル説明。",
                "lead_category": "body_candidate",
            },
        ]
        review_payload = {
            "decision": "partial_support",
            "confidence": 0.72,
            "best_context_id": "ctx2",
            "supporting_context_ids": ["ctx2"],
            "provider": "ollama",
            "model": "gemma4:e4b",
            "reason": "ctx2 is closer to the claim.",
        }

        with patch(
            "modules.historical_citation_verifier.review_context_candidates_with_llm",
            return_value=review_payload,
        ):
            selected = verifier._select_fulltext_context_candidate(candidate, contexts)

        self.assertEqual(selected["context_id"], "ctx2")
        subphase_events = [(event["event"], event["subphase"]) for event in events]
        self.assertIn(("worker_stage_started", "llm_context_review"), subphase_events)
        self.assertIn(("worker_stage_completed", "llm_context_review"), subphase_events)
        completed = [
            event
            for event in events
            if event["event"] == "worker_stage_completed"
            and event["subphase"] == "llm_context_review"
        ][0]
        self.assertEqual(completed["status"], "partial_support")
        self.assertEqual(completed["metrics"]["model"], "gemma4:e4b")
        self.assertEqual(completed["metrics"]["best_context_id"], "ctx2")

    def test_fulltext_context_expansion_disk_cache_reuses_across_verifiers(self):
        output_dir = Path(tempfile.mkdtemp())

        def build_candidate(candidate_id: str) -> CitationCandidate:
            return CitationCandidate(
                candidate_id=candidate_id,
                paragraph_index=1,
                paragraph_text="The claim needs source context.",
                translation_text="The claim needs source context.",
                footnote_id="fn1",
                footnote=ParsedFootnote(
                    id="fn1",
                    text="Contained document, in Host collection, p. 12.",
                    title="Contained document",
                    host_title="Host collection",
                    contained_title="Contained document",
                    page_numbers=[12],
                ),
                artifacts={
                    "source_resolver_plan": {
                        "source_type": "source_collection",
                        "known_pid_candidates": ["12345"],
                        "target_pid_queries": ["Contained document"],
                    },
                    "ndl_fulltext_hints": [
                        {
                            "pid": "12345",
                            "book_id": "12345",
                            "query": "Contained document",
                            "snippet": "Contained document lead text",
                            "pdf_page": 12,
                            "cid": "cid-12",
                        }
                    ],
                },
            )

        expanded = SimpleNamespace(
            context_text="Contained document body context persisted to disk.",
            status="snippet_expanded",
            note="same-page expansion",
            evidence_hits=[{"cid": "cid-12"}],
        )
        first_verifier = HistoricalCitationVerifier()
        with patch(
            "modules.historical_citation_verifier.expand_ndl_snippet_context",
            return_value=expanded,
        ) as expand_mock:
            first_verifier._expand_fulltext_context_candidates(
                build_candidate("first"),
                preferred_pid="12345",
                max_hints_to_expand=1,
                cache_dir=output_dir,
            )
        self.assertEqual(expand_mock.call_count, 1)

        cache_path = output_dir / HistoricalCitationVerifier.FULLTEXT_CONTEXT_EXPANSION_CACHE_FILENAME
        cache_payload = json.loads(cache_path.read_text(encoding="utf-8"))
        self.assertEqual(cache_payload["schema_version"], "historical_citation.fulltext_context_expansion_cache.v1")
        first_record = next(iter(cache_payload["records"].values()))
        self.assertEqual(first_record["snippet_hash"], "4e701080c844323f")

        second_candidate = build_candidate("second")
        second_verifier = HistoricalCitationVerifier()
        with patch("modules.historical_citation_verifier.expand_ndl_snippet_context") as expand_mock:
            second_contexts = second_verifier._expand_fulltext_context_candidates(
                second_candidate,
                preferred_pid="12345",
                max_hints_to_expand=1,
                cache_dir=output_dir,
            )

        self.assertEqual(expand_mock.call_count, 0)
        self.assertEqual(second_candidate.artifacts.get("fulltext_context_disk_cache_hits"), 1)
        self.assertIn("persisted to disk", second_contexts[0]["cleaned_context"])

    def test_source_resolver_models_hara_diary_as_date_first(self):
        footnote = ParsedFootnote(
            id="diary1",
            text="『原敬日記』1900年5月12日条，第84頁。",
            title="原敬日記",
            page_numbers=[84],
        )

        resolved = resolve_source(footnote, claim_text="1900年5月12日，原敬在日记中记录了相关交涉。")
        recipe = build_manual_search_recipe(
            footnote,
            claim_text="1900年5月12日，原敬在日记中记录了相关交涉。",
            current_status="page_mapping_unavailable",
        )

        self.assertEqual(resolved.resolver, "DiaryDateResolver")
        self.assertEqual(resolved.source_type, "diary")
        self.assertEqual(resolved.pid_scope_strategy, "date_to_volume_then_pid_snippet")
        self.assertIn("2982135", resolved.known_pid_candidates)
        self.assertIn("1900年5月12日", resolved.dates)
        self.assertIn("1900年5月12日", resolved.target_pid_queries)
        self.assertNotIn("1900年5月12日", resolved.global_queries)
        self.assertEqual(recipe["reason"], "diary_requires_date_first_lookup")

    def test_source_resolver_models_yamagata_opinion_as_contained_document(self):
        footnote = ParsedFootnote(
            id="contained1",
            text="山縣有朋：《山縣有朋意見書》，第12頁。",
            title="山縣有朋意見書",
            author="山縣有朋",
            page_numbers=[12],
        )

        resolved = resolve_source(footnote, claim_text="山縣有朋在意见书中提出了相关政策主张。")
        recipe = build_manual_search_recipe(
            footnote,
            claim_text="山縣有朋在意见书中提出了相关政策主张。",
            current_status="source_unavailable",
        )

        self.assertEqual(resolved.resolver, "ContainedDocumentResolver")
        self.assertEqual(resolved.source_type, "contained_document")
        self.assertEqual(resolved.pid_scope_strategy, "known_document_pid_then_host_fallback")
        self.assertIn("3025431", resolved.known_pid_candidates)
        self.assertNotIn("host_title_missing_for_contained_document", resolved.warnings)
        self.assertIn("山縣有朋意見書", resolved.target_pid_queries)
        self.assertEqual(recipe["reason"], "contained_document_requires_host_discovery")
        self.assertEqual(recipe["suggested_pid_scope"], "3025431")

    def test_source_graph_special_term_bucket_blocks_bare_ooasa_query(self):
        footnote = parse_footnote_text(
            "4",
            "［日］《静岡県で大麻につき流言》，《日本近代思想大系 5：宗教と国家》，第 121 页。",
        )
        plan = build_source_query_plan(footnote, claim_text="神宮大麻の配布をめぐって流言が生じた。")

        self.assertIn("大麻", plan.blocked_standalone_terms)
        self.assertNotIn("大麻", plan.global_fulltext_queries(max_queries=8))
        self.assertTrue(any("神宮大麻" in query for query in plan.special_term_bucket))

    def test_dedupe_result_dicts_uses_candidate_footnote_paragraph_and_source_key(self):
        item = {
            "candidate_id": "p4-fp4n1",
            "paragraph_index": 4,
            "translation_text": "同一论文句子。",
            "footnote_id": "p4n1",
            "footnote": {"id": "p4n1", "title": "日本外交文書", "text": "日本外交文書第32卷，第51页。"},
        }
        duplicate = dict(item)

        self.assertEqual(len(dedupe_result_dicts([item, duplicate])), 1)

    def test_partial_finalizer_writes_canonical_json_and_report(self):
        tmpdir = Path(tempfile.mkdtemp())
        payload = {
            "document": {"title": "PDF 论文", "paragraph_count": 1, "footnote_count": 1},
            "candidate_batch": {"total_candidates": 1, "processed_candidates": 1},
            "results": [
                {
                    "candidate_id": "p1-f1",
                    "paragraph_index": 1,
                    "paragraph_text": "论文句子。",
                    "translation_text": "论文句子。",
                    "footnote_id": "1",
                    "footnote": {"id": "1", "text": "脚注。", "title": "测试史料"},
                    "verification_status": "source_found",
                    "artifacts": {},
                }
            ],
        }

        self.assertTrue(partial_payload_is_complete(payload))
        finalized = finalize_partial_payload(payload, output_dir=tmpdir, require_complete=True)

        self.assertTrue((tmpdir / "verification_results.json").exists())
        self.assertTrue((tmpdir / "verification_report.md").exists())
        self.assertEqual(finalized["summary"]["total_candidates"], 1)

    def test_fullrun_next_stage_respects_restricted_download_flag(self):
        from scripts import run_historical_citation_pdf_fullrun as fullrun_script

        tmpdir = Path(tempfile.mkdtemp())
        calls = []

        def fake_run(cmd):
            calls.append(cmd)

        args = SimpleNamespace(
            no_next_stage=False,
            restricted_download=False,
            max_search_results=3,
            page_window=4,
            ocr_model="ndlocr_lite",
            next_stage_timeout=600,
            retry_timeout=900,
            review_model="gemma4:e4b",
            review_timeout_seconds=300,
            platform=["ndl"],
            candidate_id=["p2-fp2n1"],
            footnote_id=["p2n1"],
        )
        with patch.object(fullrun_script, "_run", side_effect=fake_run):
            fullrun_script._run_next_stage("paper.pdf", tmpdir / "combined.json", tmpdir, args)

        self.assertEqual(len(calls), 2)
        self.assertNotIn("--restricted-download", calls[0])
        self.assertNotIn("--restricted-download", calls[1])
        self.assertIn("--review-model", calls[0])
        self.assertIn("gemma4:e4b", calls[0])
        self.assertIn("--review-timeout-seconds", calls[0])
        self.assertIn("300", calls[0])
        self.assertIn("--candidate-id", calls[0])
        self.assertIn("p2-fp2n1", calls[0])
        self.assertIn("--footnote-id", calls[0])
        self.assertIn("p2n1", calls[0])
        self.assertIn("--retry-download-timeouts", calls[1])
        self.assertIn("900", calls[1])

        calls.clear()
        args.restricted_download = True
        with patch.object(fullrun_script, "_run", side_effect=fake_run):
            fullrun_script._run_next_stage("paper.pdf", tmpdir / "combined.json", tmpdir, args)

        self.assertIn("--restricted-download", calls[0])
        self.assertIn("--restricted-download", calls[1])

    def test_pdf_next_stage_defaults_to_formal_gemma_review(self):
        from scripts import refine_historical_citation_pdf_next_stage as next_stage_script
        from scripts import run_historical_citation_pdf_fullrun as fullrun_script

        next_stage_args = next_stage_script.build_parser().parse_args(
            ["paper.pdf", "--combined-json", "combined.json", "--output-dir", "out"]
        )
        fullrun_args = fullrun_script.build_parser().parse_args(["paper.pdf"])

        self.assertTrue(next_stage_args.prefer_ollama_review)
        self.assertEqual(next_stage_args.review_model, "gemma4:e4b")
        self.assertNotIn("qwen", next_stage_args.review_model.lower())
        self.assertEqual(fullrun_args.review_model, "gemma4:e4b")
        self.assertEqual(next_stage_args.review_timeout_seconds, 300)
        self.assertEqual(fullrun_args.review_timeout_seconds, 300)
        self.assertEqual(fullrun_args.next_stage_timeout, 600)
        self.assertEqual(fullrun_args.retry_timeout, 900)
        self.assertEqual(next_stage_args.slow_event_threshold_seconds, 240)
        self.assertEqual(next_stage_args.candidate_id, [])
        self.assertEqual(next_stage_args.footnote_id, [])
        self.assertEqual(fullrun_args.candidate_id, [])
        self.assertEqual(fullrun_args.footnote_id, [])

    def test_page_mapping_reuses_source_level_cache_alias(self):
        tmpdir = Path(tempfile.mkdtemp())
        source_cache_key = "日本外交文書|第32巻|明治32年"
        alias_key = f"source:{source_cache_key}"
        (tmpdir / "page_mapping_cache.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "mappings": {
                        alias_key: {
                            "anchor_scan_page": 12,
                            "anchor_book_page": 20,
                            "pages_per_scan": 2,
                            "ndl_id": "3448126",
                            "source_level_cache_key": source_cache_key,
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="论文句子。",
            translation_text="论文句子。",
            footnote_id="1",
            footnote=ParsedFootnote(
                id="1",
                text="日本外交文書第32巻，24頁。",
                title="日本外交文書",
                page_numbers=[24],
            ),
            ndl_matches=[
                NDLSearchMatch(
                    title="日本外交文書",
                    url="https://dl.ndl.go.jp/pid/3448126",
                    ndl_id="3448126",
                )
            ],
            artifacts={"source_level_cache_key": source_cache_key},
        )
        verifier._resolve_ndlsearch_matches = lambda _candidate: None  # type: ignore[method-assign]

        mapping = verifier._estimate_scan_page_range(
            candidate,
            output_dir=tmpdir,
            restricted_download=True,
            page_window=2,
            top_match=candidate.ndl_matches[0],
        )

        self.assertIsNotNone(mapping)
        self.assertEqual(mapping["start_scan_page"], 13)
        self.assertEqual(mapping["end_scan_page"], 15)
        self.assertIn("source_level_page_mapping_cache_hit", candidate.notes)
        cache_payload = json.loads((tmpdir / "page_mapping_cache.json").read_text(encoding="utf-8"))
        self.assertIn("3448126", cache_payload["mappings"])

    def test_source_level_ocr_cache_reuses_matching_pid_pages(self):
        tmpdir = Path(tempfile.mkdtemp())
        source_cache_key = "日本外交文書|第32巻|明治32年"
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="论文句子。",
            translation_text="论文句子。",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="日本外交文書第32巻，24頁。", title="日本外交文書"),
            artifacts={"source_level_cache_key": source_cache_key},
        )

        verifier._save_source_level_ocr_pages(
            candidate,
            output_dir=tmpdir,
            ndl_id="3448126",
            ocr_model="ndlocr_lite",
            extracted_pages=[(24, "門戸開放ニ関スル本文。")],
            page_label_mode="scan",
        )
        cached = verifier._load_source_level_ocr_pages(
            candidate,
            output_dir=tmpdir,
            ndl_id="3448126",
            target_pages=[24],
            ocr_model="ndlocr_lite",
            page_mapping=None,
        )

        self.assertIsNotNone(cached)
        pages, page_label_mode = cached
        self.assertEqual(page_label_mode, "scan")
        self.assertEqual(pages, [(24, "門戸開放ニ関スル本文。")])
        self.assertIn("source_level_ocr_cache_hit", candidate.notes)

        mismatch = CitationCandidate(
            candidate_id="p1-f2",
            paragraph_index=1,
            paragraph_text="论文句子。",
            translation_text="论文句子。",
            footnote_id="2",
            footnote=ParsedFootnote(id="2", text="日本外交文書第32巻，25頁。", title="日本外交文書"),
            artifacts={"source_level_cache_key": source_cache_key},
        )
        self.assertIsNone(
            verifier._load_source_level_ocr_pages(
                mismatch,
                output_dir=tmpdir,
                ndl_id="2530174",
                target_pages=[24],
                ocr_model="ndlocr_lite",
                page_mapping=None,
            )
        )

    def test_claim_fulltext_queries_expand_john_hay_to_japanese_terms(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="论文句子。",
            translation_text="约翰·海伊向各国提出在华门户开放、机会均等原则，得到了日本的赞同。",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="日本外交文書第32卷。", title="日本外交文書"),
        )

        queries = verifier._claim_fulltext_queries(candidate)

        self.assertIn("ジョン・ヘイ", queries)
        self.assertIn("米國國務長官", queries)
        self.assertIn("門戶開放", queries)
        self.assertIn("機會均等", queries)
        self.assertIn("帝國政府回答", queries)

    def test_fulltext_only_status_reflects_gemma_decision(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="论文句子。",
            translation_text="论文句子。",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="脚注。", title="测试史料"),
            verification_status="fulltext_only_hit",
            support_status="fulltext_only_hit",
            artifacts={
                "llm_review": {
                    "decision": "partial_support",
                    "reason": "只证明主题相关，尚不能作直接出处。",
                    "confidence": 0.8,
                }
            },
        )

        verifier._apply_fulltext_only_review_status(candidate)

        self.assertEqual(candidate.verification_status, "fulltext_only_partial_support")
        self.assertEqual(candidate.support_status, "fulltext_only_partial_support")
        self.assertEqual(candidate.support_reason, "只证明主题相关，尚不能作直接出处。")
        self.assertEqual(candidate.confidence, 0.8)

    def test_target_pid_fulltext_probe_records_no_hit_diagnostics(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="1900年5月12日，原敬在日记中记录了相关交涉。",
            translation_text="1900年5月12日，原敬在日记中记录了相关交涉。",
            footnote_id="1",
            footnote=ParsedFootnote(
                id="1",
                text="『原敬日記』1900年5月12日条，第84頁。",
                title="原敬日記",
                page_numbers=[84],
            ),
        )
        match = NDLSearchMatch(
            title="原敬日記",
            url="https://dl.ndl.go.jp/pid/2982135",
            ndl_id="2982135",
            score=0.9,
            metadata={"search_route": "resolver_config_known_pid", "known_pid_candidate": True},
        )

        with patch(
            "modules.historical_citation_verifier.probe_ndl_fulltext_context",
            return_value=SimpleNamespace(
                pid="2982135",
                title="原敬日記",
                status="no_direct_hit",
                hits=[],
                queries_tried=["1900年5月12日"],
                note="no direct hit",
            ),
        ):
            verifier._probe_target_pid_fulltext_hints(candidate, match)

        probe = candidate.artifacts["ndl_fulltext_probe"]
        self.assertEqual(probe["pid"], "2982135")
        self.assertEqual(probe["status"], "no_direct_hit")
        self.assertEqual(probe["hit_count"], 0)
        self.assertEqual(probe["pdf_page_hit_count"], 0)
        self.assertFalse(candidate.artifacts.get("ndl_fulltext_hints"))

    def test_diary_target_pid_probe_records_date_lookup_diagnostic(self):
        from modules.historical_citation.reporting import _format_diary_date_lookup_diagnostic

        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="1900年5月12日，原敬在日记中记录了相关交涉。",
            translation_text="1900年5月12日，原敬在日记中记录了相关交涉。",
            footnote_id="1",
            footnote=ParsedFootnote(
                id="1",
                text="『原敬日記』1900年5月12日条，第84頁。",
                title="原敬日記",
                page_numbers=[84],
            ),
            artifacts={
                "source_resolver_plan": {
                    "source_type": "diary",
                    "known_pid_candidates": ["2982135"],
                    "dates": ["1900年5月12日", "1900年"],
                    "target_pid_queries": ["1900年5月12日", "1900年", "原敬日記"],
                },
                "source_graph": {
                    "source_type": "diary",
                    "known_pid_candidates": ["2982135"],
                },
            },
        )
        match = NDLSearchMatch(title="原敬日記", url="https://dl.ndl.go.jp/pid/2982135", ndl_id="2982135")
        fake_probe = SimpleNamespace(
            pid="2982135",
            title="原敬日記",
            status="direct_hit",
            note="",
            queries_tried=["1900年5月12日", "1900年", "原敬日記"],
            hits=[
                SimpleNamespace(
                    query="原敬日記",
                    snippet="原敬日記の声価については今さら吹聴する必要はない。",
                    pdf_page=7,
                    pid="2982135",
                    cid="",
                    content_index=1,
                    page_basis="dl_ndl_fulltext_content_index",
                )
            ],
        )

        with patch("modules.historical_citation_verifier.probe_ndl_fulltext_context", return_value=fake_probe):
            verifier._probe_target_pid_fulltext_hints(candidate, match)

        diagnostic = candidate.artifacts["diary_date_lookup_diagnostic"]
        self.assertEqual(diagnostic["date_hit_count"], 0)
        self.assertEqual(diagnostic["title_hit_count"], 1)
        self.assertEqual(diagnostic["recommended_action"], "toc_index_then_small_page_window_ocr")
        self.assertEqual(diagnostic["small_page_window"]["start_page"], 82)
        self.assertEqual(diagnostic["small_page_window"]["end_page"], 86)
        self.assertIn("diary_date_lookup_needs_index_or_page_window_ocr", candidate.notes)
        diagnostic_line = _format_diary_date_lookup_diagnostic(candidate.artifacts)
        self.assertIn("Diary date lookup diagnostic", diagnostic_line)
        self.assertIn("scan_window=82-86", diagnostic_line)

    def test_contained_document_target_pid_probe_records_known_pid_diagnostic(self):
        from modules.historical_citation.reporting import (
            _format_contained_document_lookup_diagnostic,
            _format_source_type_diagnostic_summary,
        )

        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="山縣有朋在意见书中提出了相关政策主张。",
            translation_text="山縣有朋在意见书中提出了相关政策主张。",
            footnote_id="1",
            footnote=ParsedFootnote(
                id="1",
                text="山縣有朋：《山縣有朋意見書》，第12頁。",
                title="山縣有朋意見書",
                author="山縣有朋",
                page_numbers=[12],
            ),
            artifacts={
                "source_resolver_plan": {
                    "source_type": "contained_document",
                    "known_pid_candidates": ["3025431"],
                    "target_pid_queries": ["山縣有朋意見書"],
                },
                "source_graph": {
                    "source_type": "contained_document",
                    "known_pid_candidates": ["3025431"],
                    "contained_title": "山縣有朋意見書",
                    "host_title": "",
                },
            },
        )
        match = NDLSearchMatch(title="山県有朋意見書", url="https://dl.ndl.go.jp/pid/3025431", ndl_id="3025431")
        fake_probe = SimpleNamespace(
            pid="3025431",
            title="山県有朋意見書",
            status="direct_hit",
            note="",
            queries_tried=["山縣有朋意見書"],
            hits=[
                SimpleNamespace(
                    query="山縣有朋意見書",
                    snippet="山縣有朋意見書",
                    pdf_page=3,
                    pid="3025431",
                    cid="",
                    content_index=1,
                    page_basis="dl_ndl_fulltext_content_index",
                )
            ],
        )

        with patch("modules.historical_citation_verifier.probe_ndl_fulltext_context", return_value=fake_probe):
            verifier._probe_target_pid_fulltext_hints(candidate, match)

        diagnostic = candidate.artifacts["contained_document_lookup_diagnostic"]
        self.assertEqual(diagnostic["title_hit_count"], 1)
        self.assertTrue(diagnostic["host_missing"])
        self.assertEqual(diagnostic["recommended_action"], "known_document_pid_first_then_host_fallback")
        self.assertIn("contained_document_known_pid_first_then_host_fallback", candidate.notes)
        diagnostic_line = _format_contained_document_lookup_diagnostic(candidate.artifacts)
        self.assertIn("Contained document lookup diagnostic", diagnostic_line)
        self.assertIn("host=missing", diagnostic_line)
        summary_line = _format_source_type_diagnostic_summary(candidate.to_dict())
        self.assertIn("source_type=contained_document", summary_line)
        self.assertIn("contained=山縣有朋意見書", summary_line)
        self.assertIn("host=missing", summary_line)
        self.assertIn("next=known PID first, then host fallback", summary_line)

    def test_strict_resolver_forces_known_pid_probe_even_when_fulltext_hints_exist(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="约翰·海伊提出门户开放。",
            translation_text="约翰·海伊提出门户开放、机会均等。",
            footnote_id="1",
            footnote=ParsedFootnote(
                id="1",
                text="外務省編『日本外交文書』第32巻、216頁。",
                title="日本外交文書",
                page_numbers=[216],
            ),
            ndl_matches=[
                NDLSearchMatch(
                    title="日本外交文書",
                    url="https://dl.ndl.go.jp/pid/3448126",
                    ndl_id="3448126",
                    metadata={"search_route": "resolver_config_known_pid", "known_pid_candidate": True},
                ),
                NDLSearchMatch(
                    title="日本外交文書",
                    url="https://dl.ndl.go.jp/pid/3448128",
                    ndl_id="3448128",
                    metadata={
                        "search_route": "resolver_config_known_pid",
                        "known_pid_candidate": True,
                        "fulltext_hints": [
                            {
                                "query": "門戶開放",
                                "snippet": "門戶開放",
                                "pdf_page": 32,
                                "pid": "3448128",
                            }
                        ],
                    },
                ),
                NDLSearchMatch(
                    title="日本外交文書",
                    url="https://dl.ndl.go.jp/pid/14000000",
                    ndl_id="14000000",
                    metadata={
                        "search_route": "ndl_digital_fulltext_api",
                        "fulltext_hints": [
                            {
                                "query": "門戶開放",
                                "snippet": "別巻の門戶開放。",
                                "pdf_page": 5,
                                "pid": "14000000",
                            }
                        ],
                    },
                ),
            ],
            artifacts={
                "source_resolver_plan": {
                    "source_type": "volume_series",
                    "known_pid_candidates": ["3448128", "3448126"],
                    "target_pid_queries": ["門戶開放"],
                },
                "source_graph": {
                    "source_type": "volume_series",
                    "known_pid_candidates": ["3448128", "3448126"],
                },
            },
        )
        calls = []

        def fake_probe(pid, keywords):
            calls.append((pid, list(keywords)))
            return SimpleNamespace(
                pid=pid,
                title="日本外交文書",
                status="direct_hit",
                note="",
                queries_tried=["門戶開放"],
                hits=[
                    SimpleNamespace(
                        query="門戶開放",
                        snippet="支那ニ於ケル門戶開放。",
                        pdf_page=32,
                        pid=pid,
                        cid="",
                        content_index=1,
                        page_basis="dl_ndl_fulltext_content_index",
                    )
                ],
            )

        with patch("modules.historical_citation_verifier.probe_ndl_fulltext_context", side_effect=fake_probe):
            verifier._rerank_matches_for_candidate_fulltext(candidate)

        self.assertEqual([pid for pid, _keywords in calls], ["3448128"])
        self.assertEqual(candidate.artifacts["ndl_fulltext_probe"]["pid"], "3448128")
        self.assertEqual(candidate.artifacts["ndl_fulltext_probe"]["status"], "direct_hit")
        self.assertEqual(candidate.artifacts["target_pid_fulltext_probes"][0]["pid"], "3448128")
        self.assertNotIn("non_equivalent_fulltext_probes", candidate.artifacts)
        self.assertNotIn("14000000", {hint.get("pid") for hint in candidate.artifacts["ndl_fulltext_hints"]})

    def test_strict_resolver_does_not_let_fulltext_lead_overwrite_target_probe(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="原敬日记相关说明。",
            translation_text="1900年5月12日，原敬在日记中记录了相关交涉。",
            footnote_id="1",
            footnote=ParsedFootnote(
                id="1",
                text="『原敬日記』1900年5月12日条，第84頁。",
                title="原敬日記",
                page_numbers=[84],
            ),
            ndl_matches=[
                NDLSearchMatch(
                    title="影印原敬日記",
                    url="https://dl.ndl.go.jp/pid/14077924",
                    ndl_id="14077924",
                    metadata={
                        "search_route": "ndl_digital_fulltext_api",
                        "fulltext_hints": [
                            {
                                "query": "原敬日記",
                                "snippet": "影印原敬日記",
                                "pdf_page": 9,
                                "pid": "14077924",
                            }
                        ],
                    },
                ),
                NDLSearchMatch(
                    title="原敬日記",
                    url="https://dl.ndl.go.jp/pid/2982135",
                    ndl_id="2982135",
                    metadata={"search_route": "resolver_config_known_pid", "known_pid_candidate": True},
                ),
            ],
            artifacts={
                "source_resolver_plan": {
                    "source_type": "diary",
                    "known_pid_candidates": ["2982135"],
                    "dates": ["1900年5月12日", "1900年"],
                    "target_pid_queries": ["1900年5月12日", "1900年", "原敬日記"],
                },
                "source_graph": {
                    "source_type": "diary",
                    "known_pid_candidates": ["2982135"],
                },
            },
        )
        calls = []

        def fake_probe(pid, keywords):
            calls.append((pid, list(keywords)))
            return SimpleNamespace(
                pid=pid,
                title="原敬日記",
                status="direct_hit",
                note="",
                queries_tried=["1900年5月12日", "1900年", "原敬日記"],
                hits=[
                    SimpleNamespace(
                        query="原敬日記",
                        snippet="原敬日記の目次。",
                        pdf_page=7,
                        pid=pid,
                        cid="",
                        content_index=1,
                        page_basis="dl_ndl_fulltext_content_index",
                    )
                ],
            )

        with patch("modules.historical_citation_verifier.probe_ndl_fulltext_context", side_effect=fake_probe):
            verifier._rerank_matches_for_candidate_fulltext(candidate)

        self.assertEqual([pid for pid, _keywords in calls], ["2982135"])
        self.assertEqual(candidate.artifacts["ndl_fulltext_probe"]["pid"], "2982135")
        self.assertEqual(candidate.artifacts["diary_date_lookup_diagnostic"]["ndl_id"], "2982135")
        self.assertNotIn("14077924", {hint.get("pid") for hint in candidate.artifacts.get("ndl_fulltext_hints", [])})

    def test_strict_resolver_injects_known_pid_when_only_fulltext_lead_exists(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p6-fp6n6",
            paragraph_index=6,
            paragraph_text="休斯提出海军军备限制，规定主力舰比例为10:10:6。",
            translation_text="休斯提出海军军备限制，规定主力舰比例为10:10:6。",
            footnote_id="p6n6",
            footnote=ParsedFootnote(
                id="p6n6",
                text="外务省编：《日本外交文書 ワシントン会議 上》，1974年版。",
                title="日本外交文書",
            ),
            ndl_matches=[
                NDLSearchMatch(
                    title="日本外交文書に関する別資料",
                    url="https://dl.ndl.go.jp/pid/14000000",
                    ndl_id="14000000",
                    metadata={
                        "search_route": "ndl_digital_fulltext_api",
                        "claim_fulltext_global_recheck": True,
                        "fulltext_hints": [
                            {
                                "query": "日本外交文書 1974年",
                                "snippet": "別資料中の日本外交文書。",
                                "pdf_page": 23,
                                "pid": "14000000",
                            }
                        ],
                    },
                )
            ],
            artifacts={
                "source_resolver_plan": {
                    "source_type": "volume_series",
                    "known_pid_candidates": ["11927523"],
                    "target_pid_queries": ["米国案ノ十対六", "ヒューズ国務長官", "海軍軍備制限問題"],
                },
                "source_graph": {
                    "source_type": "volume_series",
                    "known_pid_candidates": ["11927523"],
                },
            },
        )
        calls = []

        def fake_probe(pid, keywords):
            calls.append((pid, list(keywords)))
            return SimpleNamespace(
                pid=pid,
                title="日本外交文書 ワシントン会議 上",
                status="direct_hit",
                note="",
                queries_tried=["米国案ノ十対六"],
                hits=[
                    SimpleNamespace(
                        query="米国案ノ十対六",
                        snippet="報知米国案ノ十対六ノ比率ハ其根拠奈辺ニアルヤ。",
                        pdf_page=143,
                        pid=pid,
                        cid="",
                        content_index=143,
                        page_basis="dl_ndl_fulltext_content_index",
                    )
                ],
            )

        with patch("modules.historical_citation_verifier.probe_ndl_fulltext_context", side_effect=fake_probe):
            verifier._rerank_matches_for_candidate_fulltext(candidate)

        self.assertEqual([pid for pid, _keywords in calls], ["11927523"])
        self.assertIn("strict_resolver_pid_candidate_injected", candidate.notes)
        self.assertEqual(candidate.artifacts["strict_resolver_pid_candidates_injected"], ["11927523"])
        self.assertEqual(candidate.ndl_matches[0].ndl_id, "11927523")
        self.assertEqual(candidate.artifacts["ndl_fulltext_probe"]["pid"], "11927523")
        self.assertIn("11927523", {hint.get("pid") for hint in candidate.artifacts["ndl_fulltext_hints"]})
        self.assertNotIn("14000000", {hint.get("pid") for hint in candidate.artifacts["ndl_fulltext_hints"]})

    def test_pdf_next_stage_records_equivalent_pid_group(self):
        from scripts.refine_historical_citation_pdf_next_stage import record_equivalent_pid_group

        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="论文句子。",
            translation_text="论文句子。",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="日本外交文書第32卷。", title="日本外交文書"),
            ndl_matches=[
                NDLSearchMatch(
                    title="日本外交文書",
                    url="https://dl.ndl.go.jp/pid/3448126",
                    ndl_id="3448126",
                    score=0.95,
                    metadata={"claim_fulltext_global_recheck": True, "claim_fulltext_global_query": "日本外交文書 門戶開放"},
                ),
                NDLSearchMatch(
                    title="日本外交文書",
                    url="https://dl.ndl.go.jp/pid/3448128",
                    ndl_id="3448128",
                    score=0.9,
                    metadata={"search_route": "ndl_digital_fulltext_api"},
                ),
                NDLSearchMatch(
                    title="別資料",
                    url="https://dl.ndl.go.jp/pid/9999999",
                    ndl_id="9999999",
                    score=0.7,
                ),
            ],
        )

        group = record_equivalent_pid_group(candidate)

        self.assertEqual([item["ndl_id"] for item in group], ["3448126", "3448128"])
        self.assertEqual(candidate.artifacts["equivalent_pid_group"][0]["fulltext_query"], "日本外交文書 門戶開放")
        self.assertIn("equivalent_pid_group_recorded", candidate.notes)

    def test_pdf_next_stage_equivalent_pid_group_includes_resolver_config_siblings(self):
        from scripts.refine_historical_citation_pdf_next_stage import record_equivalent_pid_group

        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="论文句子。",
            translation_text="论文句子。",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="日本外交文書第32巻。", title="日本外交文書"),
            ndl_matches=[
                NDLSearchMatch(
                    title="日本外交文書",
                    url="https://dl.ndl.go.jp/pid/3448126",
                    ndl_id="3448126",
                    score=0.95,
                )
            ],
            artifacts={
                "source_resolver_plan": {
                    "known_pid_candidates": ["3448126", "2530174", "3448128"]
                }
            },
        )

        group = record_equivalent_pid_group(candidate)

        self.assertEqual([item["ndl_id"] for item in group], ["3448126", "2530174", "3448128"])
        self.assertTrue(group[1]["configured_pid_candidate"])
        self.assertEqual(group[1]["search_route"], "resolver_config")

    def test_pdf_next_stage_separates_configured_equivalents_from_fulltext_leads(self):
        from scripts.refine_historical_citation_pdf_next_stage import record_equivalent_pid_group

        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="论文句子。",
            translation_text="论文句子。",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="日本外交文書第32巻。", title="日本外交文書"),
            ndl_matches=[
                NDLSearchMatch(
                    title="日本外交文書",
                    url="https://dl.ndl.go.jp/pid/3448128",
                    ndl_id="3448128",
                    score=0.95,
                    metadata={"search_route": "resolver_config_known_pid", "known_pid_candidate": True},
                ),
                NDLSearchMatch(
                    title="日本外交文書",
                    url="https://dl.ndl.go.jp/pid/3448132",
                    ndl_id="3448132",
                    score=0.7,
                    metadata={"search_route": "ndl_digital_fulltext_api"},
                ),
            ],
            artifacts={
                "source_resolver_plan": {
                    "source_type": "volume_series",
                    "known_pid_candidates": ["3448128", "3448126", "2530174"],
                }
            },
        )

        group = record_equivalent_pid_group(candidate)

        self.assertEqual([item["ndl_id"] for item in group], ["3448128", "3448126", "2530174"])
        self.assertNotIn("3448132", [item["ndl_id"] for item in group])
        self.assertEqual(candidate.artifacts["fulltext_lead_pid_group"][0]["ndl_id"], "3448132")
        self.assertEqual(
            candidate.artifacts["fulltext_lead_pid_group"][0]["scope"],
            "global_fulltext_lead_not_equivalent",
        )

    def test_fulltext_lead_manual_hint_uses_source_type_templates(self):
        from modules.historical_citation.reporting import _format_fulltext_lead_manual_hint

        volume_hint = _format_fulltext_lead_manual_hint(
            {
                "source_resolver_plan": {
                    "source_type": "volume_series",
                    "known_pid_candidates": ["3448128"],
                    "target_pid_queries": ["門戶開放"],
                },
                "fulltext_lead_pid_group": [{"ndl_id": "3448132"}],
            }
        )
        diary_hint = _format_fulltext_lead_manual_hint(
            {
                "source_resolver_plan": {
                    "source_type": "diary",
                    "known_pid_candidates": ["2982135"],
                    "target_pid_queries": ["1900年5月12日"],
                },
                "fulltext_lead_pid_group": [{"ndl_id": "2982137"}],
            }
        )
        contained_hint = _format_fulltext_lead_manual_hint(
            {
                "source_resolver_plan": {
                    "source_type": "contained_document",
                    "known_pid_candidates": ["3025431"],
                    "target_pid_queries": ["山縣有朋意見書"],
                },
                "source_graph": {
                    "host_title": "山縣有朋関係文書",
                    "contained_title": "山縣有朋意見書",
                },
                "fulltext_lead_pid_group": [{"ndl_id": "3363125"}],
            }
        )

        self.assertIn("volume_series: 先核对卷册/年份/文书题名", volume_hint)
        self.assertIn("diary: 先确认日期对应卷册", diary_hint)
        self.assertIn("目录/索引和小页窗 OCR", diary_hint)
        self.assertIn("contained_document: 先确认 host=山縣有朋関係文書", contained_hint)
        self.assertIn("contained=山縣有朋意見書", contained_hint)

    def test_pdf_next_stage_equivalent_pid_group_ignores_secondary_title_mismatch(self):
        from scripts.refine_historical_citation_pdf_next_stage import record_equivalent_pid_group

        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="论文句子。",
            translation_text="论文句子。",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="原敬日記1900年5月12日。", title="原敬日記"),
            ndl_matches=[
                NDLSearchMatch(
                    title="立憲国家と日露戦争 : 外交と内政 : 1898～1905",
                    url="https://dl.ndl.go.jp/pid/14016039",
                    ndl_id="14016039",
                    score=0.9,
                )
            ],
            artifacts={"source_resolver_plan": {"known_pid_candidates": ["2982135"]}},
        )

        group = record_equivalent_pid_group(candidate)

        self.assertEqual(group, [])
        self.assertNotIn("equivalent_pid_group", candidate.artifacts)

    def test_pdf_next_stage_equivalent_pid_group_ignores_wrong_diary_volume(self):
        from scripts.refine_historical_citation_pdf_next_stage import record_equivalent_pid_group

        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="论文句子。",
            translation_text="论文句子。",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="原敬日記1900年5月12日。", title="原敬日記"),
            ndl_matches=[
                NDLSearchMatch(
                    title="原敬日記",
                    url="https://dl.ndl.go.jp/pid/2982137",
                    ndl_id="2982137",
                    score=0.9,
                )
            ],
            artifacts={
                "source_resolver_plan": {
                    "source_type": "diary",
                    "known_pid_candidates": ["2982135"],
                }
            },
        )

        group = record_equivalent_pid_group(candidate)

        self.assertEqual(group, [])
        self.assertNotIn("equivalent_pid_group", candidate.artifacts)

    def test_fulltext_only_hit_promotes_unavailable_ndl_source_to_weak_evidence(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="论文句子。",
            translation_text="论文句子。",
            footnote_id="1",
            footnote=ParsedFootnote(
                id="1",
                text="田中頼庸「神祇官を復し教導寮等設置につき建白」『宗教と国家』40頁。",
                title="神祇官を復し教導寮等設置につき建白",
                host_title="日本近代思想大系 5：宗教と国家",
                contained_title="神祇官を復し教導寮等設置につき建白",
                source_relation="contained_in_host",
                page_numbers=[40],
            ),
            ndl_matches=[
                NDLSearchMatch(
                    title="日本近代思想大系",
                    url="https://dl.ndl.go.jp/pid/13260166",
                    ndl_id="13260166",
                    metadata={},
                )
            ],
            verification_status="download_failed",
        )

        def fake_probe(_candidate, _match):
            _candidate.artifacts["ndl_fulltext_hints"] = [
                {
                    "pid": "13260166",
                    "book_id": "13260166",
                    "pdf_page": 28,
                    "cid": "cid-4",
                    "query": "神祇官を復し教導寮等設置につき建白",
                    "snippet": "田中頼庸神祇官を復し教導寮等設置につき建白。",
                    "expanded_context": "前文。田中頼庸神祇官を復し教導寮等設置につき建白。後文。",
                    "page_basis": "dl_ndl_fulltext_content_index",
                }
            ]

        verifier._probe_target_pid_fulltext_hints = fake_probe  # type: ignore[method-assign]
        verifier._expand_first_fulltext_hint = lambda _candidate, **_kwargs: None  # type: ignore[method-assign]

        self.assertTrue(verifier._mark_fulltext_only_hit_if_possible(candidate))
        self.assertEqual(candidate.verification_status, "fulltext_only_hit")
        self.assertEqual(candidate.support_status, "fulltext_only_hit")
        self.assertEqual(candidate.artifacts["evidence_level"], "weak")

    def test_title_only_fulltext_hint_is_lead_not_hit(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="论文句子。",
            translation_text="约翰·海伊提出门户开放、机会均等。",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="日本外交文書第32卷、216頁。", title="日本外交文書", page_numbers=[216]),
            ndl_matches=[
                NDLSearchMatch(
                    title="日本外交文書",
                    url="https://dl.ndl.go.jp/pid/3448055",
                    ndl_id="3448055",
                    metadata={},
                )
            ],
            verification_status="download_failed",
        )

        def fake_probe(_candidate, _match):
            _candidate.artifacts["ndl_fulltext_hints"] = [
                {
                    "pid": "3448055",
                    "book_id": "3448055",
                    "pdf_page": 4,
                    "cid": "cid-4",
                    "query": "日本外交文書",
                    "snippet": "日本外交文書目次。",
                    "expanded_context": "日本外交文書目次。",
                    "page_basis": "dl_ndl_fulltext_content_index",
                }
            ]

        verifier._probe_target_pid_fulltext_hints = fake_probe  # type: ignore[method-assign]
        verifier._expand_first_fulltext_hint = lambda _candidate, **_kwargs: None  # type: ignore[method-assign]

        self.assertTrue(verifier._mark_fulltext_only_hit_if_possible(candidate))
        self.assertEqual(candidate.verification_status, "fulltext_lead_only")
        self.assertEqual(candidate.support_status, "fulltext_lead_only")
        self.assertEqual(candidate.artifacts["evidence_level"], "lead")

    def test_fulltext_only_hit_scores_parallel_contexts_before_selecting_best(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p4-fp4n9",
            paragraph_index=4,
            paragraph_text="围绕神宫大麻，地方上出现流言并有人把大麻投入水火。",
            translation_text="静冈县关于神宫大麻的流言称，有人把大麻投入水火或河流。",
            footnote_id="p4n9",
            footnote=ParsedFootnote(
                id="p4n9",
                text="《静岡県で大麻につき流言》，《日本近代思想大系 5：宗教と国家》，第103页。",
                title="静岡県で大麻につき流言",
                host_title="日本近代思想大系 5：宗教と国家",
                contained_title="静岡県で大麻につき流言",
                page_numbers=[103],
            ),
            ndl_matches=[
                NDLSearchMatch(
                    title="日本近代思想大系 5：宗教と国家",
                    url="https://dl.ndl.go.jp/pid/13260166",
                    ndl_id="13260166",
                    metadata={},
                )
            ],
            artifacts={
                "source_resolver_plan": {
                    "source_type": "source_collection",
                    "known_pid_candidates": ["13260166"],
                    "target_pid_queries": ["静岡県で大麻につき流言", "神宮大麻 流言"],
                }
            },
            verification_status="download_failed",
        )

        def fake_probe(_candidate, _match):
            _candidate.artifacts["ndl_fulltext_hints"] = [
                {
                    "pid": "13260166",
                    "book_id": "13260166",
                    "pdf_page": 103,
                    "cid": "bad",
                    "query": "神宮大麻 流言",
                    "snippet": "神宮大麻等に関する流言。",
                    "expanded_context": "神宮大麻等に関する流言。伊勢皇太神ノ大麻ヲ。",
                    "expanded_context_evidence_count": 1,
                },
                {
                    "pid": "13260166",
                    "book_id": "13260166",
                    "pdf_page": 103,
                    "cid": "good",
                    "query": "静岡県で大麻につき流言",
                    "snippet": "静岡県で大麻につき流言。",
                    "expanded_context": "静岡県で大麻につき流言。玉串ヲ焼捨或ハ河流ニ投ジ、水火ニ投ズルヲ禁ジ候。",
                    "expanded_context_evidence_count": 3,
                },
            ]

        verifier._probe_target_pid_fulltext_hints = fake_probe  # type: ignore[method-assign]

        self.assertTrue(verifier._mark_fulltext_only_hit_if_possible(candidate))
        self.assertEqual(candidate.verification_status, "fulltext_only_hit")
        self.assertEqual(candidate.artifacts["fulltext_selected_context_id"], "ctx1")
        self.assertIn("水火", candidate.matched_japanese)
        self.assertIn("河流", candidate.matched_japanese)
        self.assertGreaterEqual(len(candidate.artifacts["fulltext_context_candidates"]), 2)
        self.assertEqual(candidate.artifacts["fulltext_context_candidates"][0]["query"], "静岡県で大麻につき流言")

    def test_pdf_word_style_report_uses_resume_report_structure(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="论文句子。",
            translation_text="论文句子。",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="脚注。", title="测试史料"),
            verification_status="fulltext_only_hit",
            support_status="fulltext_only_hit",
            artifacts={
                "fulltext_only_hit": True,
                "fulltext_selected_context_id": "ctx1",
                "fulltext_context_candidates": [
                    {
                        "context_id": "ctx1",
                        "score": 5.5,
                        "lead_category": "body_candidate",
                        "pdf_page": 12,
                        "query": "测试 查询",
                        "cleaned_context": "清洗后的 OCR 或全文上下文。",
                        "score_reasons": ["body_candidate"],
                    }
                ],
            },
        )

        report = verifier._render_word_style_report(
            {"title": "PDF 论文", "paragraph_count": 1, "footnote_count": 1},
            [candidate],
            total_candidates=1,
            output_dir=Path(tempfile.mkdtemp()),
        )

        self.assertIn("历史引文核对中断点报告", report)
        self.assertIn("已处理候选详情", report)
        self.assertIn("fulltext_only_hit", report)
        self.assertIn("全文上下文候选 Top N", report)
        self.assertIn("清洗后的 OCR 或全文上下文", report)

    def test_docx_parser_module_extracts_document_with_callbacks(self):
        verifier = HistoricalCitationVerifier()
        docx_path = self._make_docx()

        parsed = parse_docx_document(
            str(docx_path),
            extract_quotes=verifier.extract_quotes,
            parse_footnote=verifier.parse_footnote,
        )

        self.assertEqual(parsed["document"]["paragraph_count"], 2)
        self.assertEqual(parsed["document"]["footnote_count"], 1)
        self.assertEqual(parsed["paragraphs"][0].footnote_ids, ["4"])
        self.assertEqual(parsed["footnotes"][0].page_numbers, [41])

    def test_build_candidates_prefers_quoted_translation(self):
        verifier = HistoricalCitationVerifier()
        parsed = verifier.parse_docx(str(self._make_docx()))

        candidates = verifier.build_candidates(parsed["paragraphs"], parsed["footnotes"])

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].translation_text, "为了完成制度维护的示范行动。")
        self.assertEqual(candidates[0].footnote_id, "4")

    def test_get_capabilities_describes_agent_safe_backends(self):
        verifier = HistoricalCitationVerifier(source_platforms=[DummyGenericPlatform()])

        capabilities = verifier.get_capabilities()

        self.assertEqual(capabilities["module"], "historical_citation_verifier")
        self.assertIn("historical_citation_parse", capabilities["output_types"])
        self.assertIn("example", capabilities["source_platforms"])
        self.assertTrue(capabilities["privacy"]["default_parse_is_offline"])
        self.assertIn("skill", capabilities["fallback_order"])
        self.assertIn("mcp", capabilities["fallback_order"])

    def test_parse_docx_package_wraps_candidates_without_search(self):
        verifier = HistoricalCitationVerifier()

        package = verifier.parse_docx_package(str(self._make_docx()))

        self.assertEqual(package["type"], "historical_citation_parse")
        self.assertEqual(package["backend"], "script")
        self.assertEqual(package["provider"], "local_rules")
        self.assertEqual(package["summary"]["candidate_count"], 1)
        self.assertEqual(package["candidates"][0]["footnote"]["page_numbers"], [41])
        self.assertFalse(package["needs_review"])
        self.assertGreaterEqual(package["confidence"], 0.8)

    def test_docx_parser_module_builds_candidates_with_callbacks(self):
        verifier = HistoricalCitationVerifier()
        parsed = verifier.parse_docx(str(self._make_docx()))

        candidates = build_citation_candidates(
            parsed["paragraphs"],
            parsed["footnotes"],
            pick_translation_text=lambda paragraph: verifier._pick_translation_text(
                paragraph,
                include_unquoted=False,
            ),
            is_verifiable_footnote=verifier._is_verifiable_footnote,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].candidate_id, "p1-f4")

    def test_footnote_parser_module_parses_core_fields(self):
        parsed = parse_footnote_text(
            "9",
            "架空太郎「近代制度史」東京：架空史料出版社、2001年、41-42頁。",
        )

        self.assertEqual(parsed.id, "9")
        self.assertEqual(parsed.title, "近代制度史")
        self.assertEqual(parsed.author, "架空太郎")
        self.assertEqual(parsed.publisher, "架空史料出版社")
        self.assertEqual(parsed.year, "2001")
        self.assertEqual(parsed.page_numbers, [41, 42])

    def test_footnote_parser_prefers_parenthetical_original_title(self):
        parsed = parse_footnote_text(
            "10",
            "外务省编：《日本外交文书》（外務省編：『日本外交文書』）第32卷，东京：外务省1955年版，第216～221页。",
        )

        self.assertEqual(parsed.title, "日本外交文書")
        self.assertEqual(parsed.page_numbers, [216, 217, 218, 219, 220, 221])

    def test_footnote_parser_keeps_gaiko_volume_ahead_of_fascicle(self):
        text = (
            "外务省编：《日本外交文书》第38卷第1册，东京：外务省1958年版，第450～452页。"
            " 日本外交文書 第38卷 第38巻 第三十八巻 明治38年 第1册 第1巻 明治1年"
        )

        terms = extract_volume_terms(text)
        parsed = ParsedFootnote(
            id="11",
            text="外务省编：《日本外交文书》第38卷第1册，东京：外务省1958年版，第450～452页。",
            title="日本外交文書",
            ndl_keyword="日本外交文書 第38卷 第38巻 第三十八巻 明治38年 第1册 第1巻 明治1年",
        )
        resolved = resolve_source(parsed)

        self.assertIn("第38巻", terms)
        self.assertIn("第1冊", terms)
        self.assertNotIn("第1巻", terms)
        self.assertNotIn("明治1年", terms)
        self.assertTrue(resolved.global_queries)
        self.assertEqual(resolved.known_pid_candidates[:2], ["3448160", "2530367"])
        self.assertIn("第38巻", resolved.global_queries[0])
        self.assertNotIn("第1巻", resolved.global_queries[0])

    def test_parse_docx_propagates_repeated_original_title_alias(self):
        verifier = HistoricalCitationVerifier()
        first = verifier.parse_footnote(
            "1",
            "外务省编：《日本外交文书》（外務省編：『日本外交文書』）第32卷，东京：外务省1955年版，第216～221页。",
        )
        second = verifier.parse_footnote(
            "2",
            "外务省编：《日本外交文书》第38卷第1册，东京：外务省1958年版，第450～452页。",
        )

        from modules.historical_citation.footnote_parser import apply_footnote_title_aliases

        apply_footnote_title_aliases([first, second])

        self.assertEqual(second.title, "日本外交文書")
        self.assertIn("title_alias_resolved:日本外交文书->日本外交文書", second.notes)

    def test_footnote_parser_module_extracts_quotes_and_translation_tail(self):
        quotes = extract_quotes("作者称“为了完成制度维护的示范行动”，并继续论述。")
        paragraph = type("Paragraph", (), {"quotes": [], "text": "说明：这是一段没有引号但可回退的译文内容"})()

        self.assertEqual(quotes, ["为了完成制度维护的示范行动"])
        self.assertEqual(pick_translation_text(paragraph), "这是一段没有引号但可回退的译文内容")

    def test_search_ndl_sources_ranks_best_match_first(self):
        verifier = HistoricalCitationVerifier(ndl_download_module=DummyNDLModule())
        parsed = verifier.parse_docx(str(self._make_docx()))
        candidate = verifier.build_candidates(parsed["paragraphs"], parsed["footnotes"])[0]

        matches = verifier.search_ndl_sources(candidate.footnote, max_results=2)

        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0].ndl_id, "1234567")
        self.assertGreater(matches[0].score, matches[1].score)

    def test_source_platform_filter_rejects_obvious_metadata_mismatch(self):
        parsed = parse_footnote_text(
            "1",
            "佐藤一郎「架空史料集：制度宣伝と事件叙述」東京：架空出版社、2001年、41頁。",
        )
        mismatch = NDLSearchMatch(
            title="まったく別の資料",
            url="https://dl.ndl.go.jp/pid/00000000",
            ndl_id="00000000",
            author="別人",
            date="1999",
            publisher="別出版社",
        )

        self.assertFalse(is_plausible_source_match(parsed, mismatch))
        self.assertIn("mismatch_reason", mismatch.metadata)

    def test_ndl_platform_keeps_top_relevance_result_when_metadata_score_is_low_but_not_zero(self):
        class LowScoreNDLModule:
            def search(self, keyword, max_results=5, use_api=True, headless=True):
                del keyword, max_results, use_api, headless
                return [
                    DummyNDLRecord(
                        title="abxyz",
                        url="https://dl.ndl.go.jp/pid/12345678",
                        ndl_id="12345678",
                    )
                ]

        adapter = NDLSourcePlatformAdapter(
            download_module_getter=lambda: LowScoreNDLModule(),
            prefer_external_module=True,
            allow_external_fallback=False,
        )
        matches = adapter.search(ParsedFootnote(id="1", text="abcde, 41頁", title="abcde"), max_results=1)

        self.assertEqual(matches[0].ndl_id, "12345678")
        self.assertEqual(matches[0].metadata["source_match_warning"], "ndl_relevance_low_metadata_score_fallback")
        self.assertFalse(matches[0].metadata.get("source_mismatch", False))

    def test_ndl_platform_caches_public_metadata_search(self):
        adapter = NDLSourcePlatformAdapter(
            download_module_getter=lambda: DummyCountingNDLModule(),
            prefer_external_module=False,
            allow_external_fallback=False,
        )
        footnote = ParsedFootnote(id="1", text="source", title="架空史料", page_numbers=[1])
        calls = []

        def fake_public_api(input_footnote, *, max_results):
            calls.append((input_footnote.title, max_results))
            return [
                {
                    "title": "架空史料",
                    "url": "https://dl.ndl.go.jp/pid/123456",
                    "ndl_id": "123456",
                    "metadata": {},
                }
            ]

        with patch("modules.historical_citation.source_platforms.search_ndl_public_api", fake_public_api):
            first = adapter.search(footnote, max_results=2)
            second = adapter.search(footnote, max_results=2)

        self.assertEqual(len(calls), 1)
        self.assertEqual(first[0].title, "架空史料")
        self.assertEqual(second[0].title, "架空史料")

    def test_verify_docx_marks_all_rejected_platform_results_as_source_mismatch(self):
        verifier = HistoricalCitationVerifier(ndl_download_module=DummyMismatchNDLModule())

        result = verifier.verify_docx(
            str(self._make_docx()),
            search_ndl=True,
            download_source=False,
            max_search_results=2,
            platform_names=["ndl"],
        )

        self.assertEqual(result["results"][0]["verification_status"], "source_mismatch")
        self.assertTrue(result["results"][0]["ndl_matches"][0]["metadata"]["source_mismatch"])
        self.assertEqual(result["summary"]["source_mismatch"], 1)
        self.assertEqual(result["summary"]["source_found"], 0)

    def test_verify_docx_package_records_quality_flags_and_artifacts(self):
        verifier = HistoricalCitationVerifier(ndl_download_module=DummyMismatchNDLModule())
        output_dir = Path(tempfile.mkdtemp())

        package = verifier.verify_docx_package(
            str(self._make_docx()),
            search_ndl=True,
            download_source=False,
            max_search_results=2,
            output_dir=str(output_dir),
            platform_names=["ndl"],
        )

        self.assertEqual(package["type"], "historical_citation_verification")
        self.assertTrue(package["needs_review"])
        self.assertIn("source_mismatch", package["quality_flags"])
        self.assertEqual(package["summary"]["source_mismatch"], 1)
        self.assertTrue(Path(package["artifacts"]["json_report"]).exists())
        self.assertEqual(package["execution"]["platform_names"], ["ndl"])

    def test_search_sources_supports_non_ndl_platform_adapters(self):
        verifier = HistoricalCitationVerifier(source_platforms=[DummyGenericPlatform()])
        footnote = parse_footnote_text(
            "1",
            "佐藤一郎「架空史料集：制度宣伝と事件叙述」東京：架空出版社、2001年、41頁。",
        )

        matches = verifier.search_sources(footnote, max_results=5)

        self.assertEqual(matches[0].platform, "example")
        self.assertEqual(matches[0].platform_item_id, "example-1")

    def test_ndl_adapter_can_skip_external_browser_fallback(self):
        footnote = parse_footnote_text(
            "1",
            "佐藤一郎「架空史料集：制度宣伝と事件叙述」東京：架空出版社、2001年、41頁。",
        )
        module = DummyCountingNDLModule()
        adapter = NDLSourcePlatformAdapter(
            download_module_getter=lambda: module,
            allow_external_fallback=False,
        )

        with patch("modules.historical_citation.source_platforms.search_ndl_public_api", return_value=[]):
            matches = adapter.search(footnote, max_results=3)

        self.assertEqual(matches, [])
        self.assertEqual(module.calls, [])

    def test_ndl_adapter_prefers_downloadable_pid_when_metadata_score_is_close(self):
        footnote = ParsedFootnote(
            id="1",
            text="華族会館史、482頁。",
            title="華族会館史",
            page_numbers=[482],
        )
        adapter = NDLSourcePlatformAdapter(
            download_module_getter=lambda: DummyCountingNDLModule(),
            allow_external_fallback=False,
        )
        records = [
            {
                "title": "華族会館史",
                "url": "https://ndlsearch.ndl.go.jp/books/R100000001-I1",
                "ndl_id": None,
                "metadata": {
                    "identifier": "R100000001-I1",
                    "ndlsearch_detail_resolution": {"status": "no_digital_pid", "ndl_ids": []},
                },
            },
            {
                "title": "華族会館史",
                "url": "https://dl.ndl.go.jp/pid/3017836",
                "ndl_id": "3017836",
                "metadata": {"identifier": "3017836"},
            },
        ]

        with patch("modules.historical_citation.source_platforms.search_ndl_public_api", return_value=records):
            matches = adapter.search(footnote, max_results=2)

        self.assertEqual(matches[0].ndl_id, "3017836")

    def test_ndl_adapter_searches_contained_title_first_for_fulltext(self):
        footnote = parse_footnote_text(
            "66",
            "「憲法ニ關スル演說」6, 7, 8, 9, 10, 11, 12頁。",
        )
        adapter = NDLSourcePlatformAdapter(
            download_module_getter=lambda: DummyCountingNDLModule(),
            allow_external_fallback=False,
        )
        seen_keywords = []

        def fake_fulltext(keyword, **_kwargs):
            seen_keywords.append(keyword)
            if keyword == "憲法ニ關スル演說":
                return [
                    {
                        "title": "華族同方会演説集",
                        "url": "https://dl.ndl.go.jp/pid/1558815",
                        "ndl_id": "1558815",
                        "metadata": {
                            "search_route": "ndl_digital_fulltext_api",
                            "fulltext_hints": [{"snippet": keyword, "pdf_page": 3}],
                        },
                    }
                ]
            return []

        with patch("modules.historical_citation.source_platforms.search_ndl_public_api", return_value=[]), patch(
            "modules.historical_citation.source_platforms.search_ndl_digital_fulltext",
            side_effect=fake_fulltext,
        ):
            matches = adapter.search(footnote, max_results=3)

        self.assertEqual(seen_keywords[0], "憲法ニ關スル演說")
        self.assertEqual(matches[0].ndl_id, "1558815")
        self.assertTrue(matches[0].metadata["fulltext_hints"])

    def test_ndl_adapter_merges_fulltext_hints_into_duplicate_public_record(self):
        adapter = NDLSourcePlatformAdapter(
            download_module_getter=lambda: DummyCountingNDLModule(),
            allow_external_fallback=False,
        )

        merged = adapter._merge_records(
            [
                {
                    "title": "華族同方会演説集",
                    "url": "https://dl.ndl.go.jp/pid/1558815",
                    "ndl_id": "1558815",
                    "metadata": {"search_route": "ndl_sru"},
                }
            ],
            [
                {
                    "title": "華族同方会演説集",
                    "url": "https://dl.ndl.go.jp/pid/1558815",
                    "ndl_id": "1558815",
                    "metadata": {
                        "search_route": "ndl_digital_fulltext_api",
                        "fulltext_hints": [{"snippet": "憲法ニ關スル演說", "pdf_page": 3}],
                    },
                }
            ],
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["metadata"]["fulltext_hints"][0]["pdf_page"], 3)
        self.assertIn("ndl_digital_fulltext_api", merged[0]["metadata"]["search_routes"])

    def test_japan_search_platform_normalizes_sparql_results(self):
        footnote = parse_footnote_text(
            "1",
            "佐藤一郎「架空史料集：制度宣伝と事件叙述」東京：架空出版社、2001年、41頁。",
        )
        payload = {
            "results": {
                "bindings": [
                    {
                        "item": {"value": "https://jpsearch.go.jp/item/synthetic-1"},
                        "label": {"value": "架空史料集：制度宣伝と事件叙述"},
                        "creator": {"value": "佐藤一郎"},
                        "publisher": {"value": "架空出版社"},
                        "date": {"value": "2001"},
                        "url": {"value": "https://example.invalid/synthetic-1"},
                    }
                ]
            }
        }
        adapter = JapanSearchPlatformAdapter(
            request_get=lambda *_args, **_kwargs: DummyResponse(json.dumps(payload), status_code=200)
        )

        matches = adapter.search(footnote, max_results=3)

        self.assertEqual(matches[0].platform, "japan_search")
        self.assertEqual(matches[0].platform_item_id, "https://jpsearch.go.jp/item/synthetic-1")
        self.assertGreater(matches[0].score, 0.8)

    def test_internet_archive_platform_search_and_pdf_download(self):
        footnote = parse_footnote_text(
            "1",
            "佐藤一郎「架空史料集：制度宣伝と事件叙述」東京：架空出版社、2001年、41頁。",
        )
        search_payload = {
            "response": {
                "docs": [
                    {
                        "identifier": "syntheticarchive",
                        "title": "架空史料集：制度宣伝と事件叙述",
                        "creator": "佐藤一郎",
                        "date": "2001",
                        "publisher": "架空出版社",
                    }
                ]
            }
        }
        metadata_payload = {"files": [{"name": "syntheticarchive_text.pdf"}]}

        def fake_get(url, **kwargs):
            if "advancedsearch" in url:
                return DummyResponse(json.dumps(search_payload), status_code=200)
            if "metadata" in url:
                return DummyResponse(json.dumps(metadata_payload), status_code=200)
            return DummyResponse("", status_code=200, headers={"content-type": "application/pdf"}, chunks=[b"%PDF"])

        adapter = InternetArchivePlatformAdapter(request_get=fake_get)
        matches = adapter.search(footnote, max_results=3)
        pdf_path = adapter.download_public_pdf(matches[0], output_dir=Path(tempfile.mkdtemp()))

        self.assertEqual(matches[0].platform, "internet_archive")
        self.assertEqual(matches[0].platform_item_id, "syntheticarchive")
        self.assertTrue(Path(pdf_path).exists())

    def test_extended_platform_adapters_normalize_public_search_results(self):
        footnote = parse_footnote_text(
            "1",
            "佐藤一郎「架空史料集：制度宣伝と事件叙述」東京：架空出版社、2001年、41頁。",
        )
        jstage = JStagePlatformAdapter(
            request_get=lambda *_args, **_kwargs: DummyResponse(
                '<a href="/article/synthetic/1/0/1/_article/-char/ja">架空史料集：制度宣伝と事件叙述</a>',
                status_code=200,
            )
        )
        cinii = CiNiiResearchPlatformAdapter(
            request_get=lambda *_args, **_kwargs: DummyResponse(
                '<a href="/crid/1234567890">架空史料集：制度宣伝と事件叙述</a>',
                status_code=200,
            )
        )
        jacar = JACARPlatformAdapter()
        diet = DietProceedingsPlatformAdapter(
            request_get=lambda *_args, **_kwargs: DummyResponse(
                json.dumps(
                    {
                        "speechRecord": [
                            {
                                "speechID": "synthetic-speech",
                                "nameOfHouse": "衆議院",
                                "speechURL": "https://kokkai.ndl.go.jp/synthetic",
                                "date": "2001-01-01",
                            }
                        ]
                    }
                ),
                status_code=200,
            )
        )
        egov = EGovLawPlatformAdapter()

        self.assertEqual(jstage.search(footnote)[0].platform, "jstage")
        self.assertEqual(cinii.search(footnote)[0].platform, "cinii_research")
        self.assertEqual(
            jacar.search(ParsedFootnote(id="2", text="JACAR Ref.B03041123400、1頁。", title=""))[0].platform_item_id,
            "B03041123400",
        )
        self.assertEqual(diet.search(footnote)[0].platform, "diet_proceedings")
        law_matches = egov.search(
            ParsedFootnote(id="3", text="「華族令」、1頁。", title="華族令", page_numbers=[1])
        )
        self.assertEqual(law_matches[0].platform, "egov_law")

    def test_align_translation_uses_heuristic_when_llm_unavailable(self):
        verifier = HistoricalCitationVerifier(llm_client=None)
        verifier._get_llm_client = lambda optional=False: None  # type: ignore[method-assign]

        page, segment, confidence, note = verifier._align_translation(
            "维护制度的实践路径",
            [
                (40, "これは関係の薄い前後文であり、主要な語はほとんど含まれていない。"),
                (41, "制度維持の実践手順を進めるべしという趣旨がここで強く述べられている。"),
            ],
        )

        self.assertEqual(page, 41)
        self.assertIn("制度維持", segment)
        self.assertIsNotNone(confidence)
        self.assertEqual(note, "heuristic_alignment_used")

    def test_alignment_module_segments_scores_and_selects_heuristic_match(self):
        extracted_pages = [
            (40, "関係のない短い説明文です。"),
            (41, "制度維持の実践手順を進めるという趣旨がここで強く述べられている。"),
        ]

        candidates = build_passage_candidates("维护制度的实践路径", extracted_pages)
        page, segment, confidence, note = align_translation("维护制度的实践路径", extracted_pages)

        self.assertEqual(candidates[0][0], 41)
        self.assertEqual(page, 41)
        self.assertIn("制度維持", segment)
        self.assertGreater(confidence, 0)
        self.assertEqual(note, "heuristic_alignment_used")

    def test_alignment_module_parses_llm_json_and_uses_llm_choice(self):
        page, segment, confidence, note = align_translation(
            "维护制度的实践路径",
            [
                (40, "制度維持とは別の説明であるが十分な長さを持つ文章。"),
                (41, "制度維持の実践手順を進めるという趣旨がここで強く述べられている。"),
            ],
            llm_client=DummyLLMClient('{"best_index": 1, "confidence": 0.88, "reason": "top candidate is closer"}'),
        )

        self.assertEqual(parse_llm_json("```json\n{\"best_index\": 1}\n```")["best_index"], 1)
        self.assertEqual(page, 41)
        self.assertIn("制度維持", segment)
        self.assertEqual(confidence, 0.88)
        self.assertEqual(note, "top candidate is closer")

    def test_alignment_module_respects_llm_rejection(self):
        page, segment, confidence, note = align_translation(
            "维护制度的实践路径",
            [(41, "これは候補としては長いが、制度維持の根拠ではない説明である。")],
            llm_client=DummyLLMClient('{"best_index": 0, "confidence": 0, "reason": "no direct support"}'),
        )

        self.assertIsNone(page)
        self.assertEqual(segment, "")
        self.assertEqual(confidence, 0.0)
        self.assertIn("llm_rejected_candidates", note)

    def test_llm_review_selects_exact_sentence_without_context(self):
        review = review_alignment_with_llm(
            "无需墨守早前诏敕",
            "前文である。必シモ前日ノ詔勅ヲ墨守スルノ要ヲ見サル。後文である。",
            llm_client=DummyLLMClient(
                '{"decision":"direct_support","best_index":2,"exact_sentence":"必シモ前日ノ詔勅ヲ墨守スルノ要ヲ見サル。","confidence":0.91,"reason":"direct"}'
            ),
        )

        prompt = build_llm_review_prompt("中文", "第一句。第二句。")
        self.assertEqual(split_review_sentences("第一句。第二句。"), ["第一句。", "第二句。"])
        self.assertIn("candidate_sentences", prompt)
        self.assertEqual(review["decision"], "direct_support")
        self.assertEqual(review["exact_sentence"], "必シモ前日ノ詔勅ヲ墨守スルノ要ヲ見サル。")
        self.assertEqual(review["confidence"], 0.91)
        self.assertTrue(review["llm_review_success"])

    def test_multi_context_review_allows_combined_direct_support(self):
        contexts = [
            {
                "context_id": "ctx1",
                "cleaned_context": "合衆國ノ提議ニ對スル返翰。清國ニ於ケル門戶開放ノ事。",
                "lead_category": "body_candidate",
            },
            {
                "context_id": "ctx2",
                "cleaned_context": "日本國政府ハ該主義ヲ承諾シタル旨回答セリ。",
                "lead_category": "body_candidate",
            },
        ]
        compound_packet = {
            "packet_type": "volume_series_open_door_compound_claim",
            "complete": True,
            "supporting_context_ids": ["ctx1", "ctx2"],
            "facets": [
                {"facet_id": "us_proposal", "covered": True, "hits": [{"context_id": "ctx1"}]},
                {"facet_id": "japan_acceptance", "covered": True, "hits": [{"context_id": "ctx2"}]},
            ],
        }
        prompt = build_multi_context_review_prompt(
            "海伊提出门户开放原则并得到日本赞同。",
            contexts,
            compound_evidence_packet=compound_packet,
        )
        review = normalize_multi_context_review_payload(
            {
                "decision": "direct_support",
                "best_context_id": "ctx1",
                "supporting_context_ids": ["ctx1", "ctx2"],
                "best_sentence_index": 0,
                "exact_sentence": "",
                "confidence": 0.86,
                "reason": "ctx1 covers the US proposal and ctx2 covers Japan's acceptance.",
            },
            contexts,
        )

        self.assertIn("supporting_context_ids", prompt["output_schema"])
        self.assertEqual(prompt["compound_evidence_packet"]["packet_type"], "volume_series_open_door_compound_claim")
        self.assertEqual(review["decision"], "direct_support")
        self.assertEqual(review["supporting_context_ids"], ["ctx1", "ctx2"])
        self.assertEqual(review["exact_sentence"], "")

    def test_llm_review_repairs_wrapped_json_and_records_coverage_flags(self):
        parsed, repaired = parse_review_json_with_repair(
            "模型说明：\n```json\n{\"decision\":\"partial_support\",\"best_index\":0,\"confidence\":0.4}\n```"
        )
        review = review_alignment_with_llm(
            "制度维护",
            "制度維持について述べる。",
            llm_client=DummyLLMClient(
                "模型说明：\n```json\n{\"decision\":\"partial_support\",\"best_index\":0,\"confidence\":0.4,\"reason\":\"related\"}\n```"
            ),
        )

        self.assertTrue(repaired)
        self.assertEqual(parsed["decision"], "partial_support")
        self.assertTrue(review["llm_review_success"])
        self.assertTrue(review["llm_review_json_repaired"])
        self.assertFalse(review["llm_review_fallback_heuristic"])

    def test_ollama_default_formal_review_model_prefers_gemma_policy(self):
        class TagsResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "models": [
                        {"name": "qwen2.5:7b"},
                        {"name": "gemma4:e4b"},
                    ]
                }

        with patch("modules.historical_citation.llm_review.requests.get", return_value=TagsResponse()):
            client = OllamaChatClient()

        self.assertEqual(client.model, "gemma4:e4b")
        self.assertEqual(client.timeout, DEFAULT_OLLAMA_REVIEW_TIMEOUT_SECONDS)
        self.assertTrue(client.is_formal_review_allowed())
        health = client.health_check()
        self.assertTrue(health["preferred_model_family"])
        self.assertEqual(health["timeout_seconds"], DEFAULT_OLLAMA_REVIEW_TIMEOUT_SECONDS)

    def test_ollama_review_timeout_reads_env_and_allows_explicit_override(self):
        with patch.dict(os.environ, {"HISTORICAL_CITATION_REVIEW_TIMEOUT_SECONDS": "456"}, clear=False):
            client = OllamaChatClient(model="gemma4:e4b")
            override = OllamaChatClient(model="gemma4:e4b", timeout=12)

        self.assertEqual(client.timeout, 456)
        self.assertEqual(override.timeout, 12)

    def test_ollama_model_policy_uses_explicit_allowlist_for_formal_review(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            policy_path = Path(tmpdir) / "model_policy.json"
            policy_path.write_text(
                json.dumps({"allowlist": ["qwen2.5:7b"], "blocklist": []}),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"HISTORICAL_CITATION_REVIEW_MODEL_POLICY": str(policy_path)},
                clear=False,
            ):
                gemma = OllamaChatClient(model="gemma4:e4b")
                qwen = OllamaChatClient(model="qwen2.5:7b")
                self.assertFalse(gemma.is_formal_review_allowed())
                self.assertTrue(qwen.is_formal_review_allowed())

        class PolicyAwareDummy(DummyLLMClient):
            provider = "ollama"
            model = "gemma4:e4b"

            def is_formal_review_allowed(self):
                return False

        review = review_alignment_with_llm(
            "制度维护",
            "制度維持について述べる。",
            llm_client=PolicyAwareDummy(
                '{"decision":"direct_support","best_index":1,"confidence":1,"reason":"should be blocked"}'
            ),
        )

        self.assertEqual(review["provider"], "heuristic")
        self.assertEqual(review["llm_error"], "model_not_allowlisted_for_formal_review")

    def test_source_trials_from_legacy_merges_replaced_unavailable_and_current(self):
        artifacts = {
            "source_attempts": [
                {
                    "selected_source_match": {"platform": "ndl", "ndl_id": "111", "title": "旧来源"},
                    "downloaded_page_range": [1, 2],
                    "verification_status": "needs_manual_review",
                    "support_status": "partial_support",
                    "confidence": 0.2,
                    "source_pdf": "old.pdf",
                    "matched_japanese": "old",
                }
            ],
            "source_unavailable_attempts": [
                {"source_id": "metadata-only", "reason": "no_digital_pid", "detail": "no pid"}
            ],
        }

        trials = source_trials_from_legacy(
            artifacts,
            current={
                "selected_source_match": {"platform": "ndl", "ndl_id": "222", "title": "当前来源"},
                "downloaded_page_range": [3, 4],
                "source_pdf": "new.pdf",
                "matched_japanese": "new",
                "verification_status": "matched",
                "support_status": "direct_support",
                "confidence": 0.9,
            },
        )

        self.assertEqual([trial["role"] for trial in trials], ["replaced", "unavailable", "current"])
        self.assertEqual(trials[-1]["source_id"], "222")

    def test_verifier_uses_llm_review_to_promote_direct_support(self):
        verifier = HistoricalCitationVerifier(
            review_llm_client=DummyLLMClient(
                '{"decision":"direct_support","best_index":1,"exact_sentence":"制度維持に関する直接の説明。","confidence":0.92,"reason":"direct"}'
            )
        )
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="制度維持の説明。",
            translation_text="制度維持",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="source", title="source", page_numbers=[41]),
            verification_status="matched",
            matched_japanese="制度維持に関する直接の説明。周辺文。",
            matched_page=41,
            confidence=0.2,
            notes=["cited_page_alignment_used; heuristic_alignment_used"],
            artifacts={"alignment_scope": "cited_pages", "page_distance_from_citation": 0},
        )

        verifier._review_precise_alignment(candidate)
        verifier._set_support_assessment(candidate)

        self.assertEqual(candidate.support_status, "direct_support")
        self.assertEqual(candidate.verification_status, "matched")
        self.assertEqual(candidate.matched_japanese, "制度維持に関する直接の説明。")
        self.assertEqual(candidate.artifacts["llm_review"]["provider"], "llm")

    def test_verifier_marks_heuristic_alignment_as_partial_support(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="制度維持の説明。",
            translation_text="制度維持",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="source", title="source", page_numbers=[41]),
            verification_status="matched",
            matched_japanese="制度維持に関する近い説明。",
            matched_page=41,
            confidence=0.35,
            notes=["cited_page_alignment_used; heuristic_alignment_used"],
            artifacts={"alignment_scope": "cited_pages", "page_distance_from_citation": 0},
        )

        verifier._set_support_assessment(candidate)

        self.assertEqual(candidate.support_status, "partial_support")
        self.assertEqual(candidate.verification_status, "needs_manual_review")
        self.assertIn("不能自动判为直接出处", candidate.support_reason)

    def test_verifier_marks_high_confidence_llm_alignment_as_direct_support(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="制度維持の説明。",
            translation_text="制度維持",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="source", title="source", page_numbers=[41]),
            verification_status="matched",
            matched_japanese="制度維持に関する直接の説明。",
            matched_page=41,
            confidence=0.88,
            notes=["cited_page_alignment_used"],
            artifacts={"alignment_scope": "cited_pages", "page_distance_from_citation": 0},
        )

        verifier._set_support_assessment(candidate)

        self.assertEqual(candidate.support_status, "direct_support")
        self.assertEqual(candidate.verification_status, "matched")

    def test_verifier_prioritizes_cited_pages_over_context_alignment(self):
        verifier = HistoricalCitationVerifier(llm_client=None)
        verifier._get_llm_client = lambda optional=False: None  # type: ignore[method-assign]
        footnote = ParsedFootnote(
            id="31",
            text="霞会館：《華族会館史》，三〇一-三〇二頁。",
            title="華族会館史",
            author="霞会館",
            page_numbers=[301, 302],
        )
        candidate = CitationCandidate(
            candidate_id="p22-f31",
            paragraph_index=22,
            paragraph_text="作者据此说明制度维护的实践路径。",
            translation_text="维护制度的实践路径",
            footnote_id="31",
            footnote=footnote,
        )
        candidate.artifacts["page_label_mode"] = "book"

        page, segment, confidence, note = verifier._align_translation_with_citation_priority(
            candidate,
            [
                (301, "これは華族会館の沿革に関する説明であり、明治期の会員構成と事務手続を述べている。"),
                (306, "制度維持の実践手順を進めるという趣旨がここで強く述べられている。"),
            ],
        )

        self.assertEqual(page, 301)
        self.assertIn("華族会館", segment)
        self.assertIsNotNone(confidence)
        self.assertEqual(candidate.artifacts["alignment_scope"], "cited_pages")
        self.assertEqual(candidate.artifacts["citation_priority_pages"], [301, 302])
        self.assertIn("context_alignment_preview_higher_confidence:p306", note)

    def test_alignment_module_trims_long_segments_around_best_window(self):
        long_segment = "前置き" * 120 + "制度維持の実践手順を進めるという中核表現" + "後続" * 120
        trimmed = trim_aligned_segment("维护制度的实践路径", long_segment)

        self.assertLessEqual(len(trimmed), 260)
        self.assertGreater(score_alignment_candidate("维护制度的实践路径", "制度維持の実践手順"), 0)
        self.assertGreaterEqual(len(segment_page_text("第一段\n\n第二段")), 2)

    def test_verifier_promotes_adjacent_context_when_cited_page_alignment_is_weak(self):
        verifier = HistoricalCitationVerifier(enable_llm_review=False)
        footnote = ParsedFootnote(id="31", text="source", title="source", page_numbers=[10])
        candidate = CitationCandidate(
            candidate_id="p1-f31",
            paragraph_index=1,
            paragraph_text="dummy",
            translation_text="改革派主张裁撤会议并将资金用于教育扩张。",
            footnote_id="31",
            footnote=footnote,
        )
        candidate.artifacts["page_label_mode"] = "book"
        extracted_pages = [
            (10, "会馆资金报告。"),
            (11, "改革派主张裁撤会议并将资金用于教育扩张。"),
        ]

        page, segment, confidence, note = verifier._align_translation_with_citation_priority(
            candidate,
            extracted_pages,
        )

        self.assertEqual(page, 11)
        self.assertIn("教育扩张", segment)
        self.assertGreaterEqual(confidence or 0.0, verifier.MIN_CONTEXT_PROMOTION_CONFIDENCE)
        self.assertEqual(candidate.artifacts["alignment_scope"], "context_promoted_from_cited_pages")
        self.assertIn("context_alignment_selected_over_weak_cited_page:p11", note)

    def test_verifier_records_distributed_claim_alignments_for_multi_page_notes(self):
        verifier = HistoricalCitationVerifier(enable_llm_review=False)
        footnote = ParsedFootnote(
            id="42",
            text="source",
            title="source",
            page_label="第92、93、94页",
            page_numbers=[92, 93, 94],
            page_span_type="distributed_pages",
        )
        translation = "岩仓出任馆长，并出台章程，由岩仓兼任督部长。"
        candidate = CitationCandidate(
            candidate_id="p1-f42",
            paragraph_index=1,
            paragraph_text="dummy",
            translation_text=translation,
            footnote_id="42",
            footnote=footnote,
        )
        candidate.artifacts["page_label_mode"] = "book"
        candidate.artifacts["citation_unit"] = {
            "text": translation,
            "unit_type": "multi_page_distributed_span",
            "claim_candidates": split_citation_claims_for_pages(translation),
        }
        candidate.artifacts["page_span"] = classify_page_span(
            footnote.page_numbers,
            page_label=footnote.page_label,
            citation_text=translation,
        )

        page, segment, confidence, note = verifier._align_translation_with_citation_priority(
            candidate,
            [
                (92, "岩仓出任馆长并负责华族会馆事务，同时说明制度安排与组织权限。"),
                (93, "宫内省出台章程以整理部局权限，同时说明制度安排与组织权限。"),
                (94, "由岩仓兼任督部长并统辖相关事务，同时说明制度安排与组织权限。"),
            ],
        )

        self.assertIn(page, {92, 93, 94})
        self.assertIn("[p", segment)
        self.assertGreater(confidence or 0.0, 0)
        self.assertEqual(candidate.artifacts["alignment_scope"], "distributed_cited_pages")
        self.assertIn("distributed_page_claim_alignment_used", note)

    def test_verifier_uses_continuous_page_window_for_two_page_range(self):
        verifier = HistoricalCitationVerifier(enable_llm_review=False)
        footnote = ParsedFootnote(
            id="43",
            text="source",
            title="source",
            page_label="第95-96页",
            page_numbers=[95, 96],
            page_span_type="continuous_range",
        )
        candidate = CitationCandidate(
            candidate_id="p1-f43",
            paragraph_index=1,
            paragraph_text="dummy",
            translation_text="会馆出台部长役局章程并总管华族事务。",
            footnote_id="43",
            footnote=footnote,
        )
        candidate.artifacts["page_label_mode"] = "book"
        candidate.artifacts["page_span"] = classify_page_span(
            footnote.page_numbers,
            page_label=footnote.page_label,
            citation_text=candidate.translation_text,
        )

        page, segment, _confidence, note = verifier._align_translation_with_citation_priority(
            candidate,
            [
                (95, "会馆出台部长役局章程并设置相关役局，同时说明制度安排与组织权限。"),
                (96, "该章程规定本局总管华族事务并执行政令，同时说明制度安排与组织权限。"),
            ],
        )

        self.assertEqual(page, 95)
        self.assertIn("章程", segment)
        self.assertEqual(candidate.artifacts["page_span_mode"], "continuous_range")
        self.assertIn("continuous_page_window_alignment_used", note)

    def test_footnote_specific_translation_prefers_quote_order(self):
        paragraph = ParsedParagraph(
            index=1,
            text="前文“第一处引文”中段“第二处引文”",
            footnote_ids=["31", "32"],
            quotes=["第一处引文", "第二处引文"],
        )

        self.assertEqual(pick_translation_text(paragraph, footnote_id="31"), "第一处引文")
        self.assertEqual(pick_translation_text(paragraph, footnote_id="32"), "第二处引文")

    def test_footnote_contexts_use_text_before_each_marker(self):
        text = "前一句说明通款社背景。后一句提出“分有立法之权”。结尾再说“扩充华族智识”。"
        positions = {
            "31": text.index("。") + 1,
            "32": text.index("”。") + 2,
            "33": text.index("扩充华族智识") + len("扩充华族智识") + 1,
        }

        contexts = build_footnote_contexts(text, positions)
        paragraph = ParsedParagraph(
            index=1,
            text=text,
            footnote_ids=["31", "32", "33"],
            quotes=["分有立法之权", "扩充华族智识"],
            footnote_positions=positions,
            footnote_contexts=contexts,
        )

        self.assertEqual(pick_translation_text(paragraph, footnote_id="31"), "前一句说明通款社背景。")
        self.assertEqual(pick_translation_text(paragraph, footnote_id="32"), "后一句提出“分有立法之权”。")
        self.assertEqual(pick_translation_text(paragraph, footnote_id="33"), "扩充华族智识")

        attached_contexts = build_footnote_contexts(text, {"32": text.index("”。") + 1})
        attached_paragraph = ParsedParagraph(
            index=1,
            text=text,
            footnote_ids=["32"],
            quotes=["分有立法之权"],
            footnote_positions={"32": text.index("”。") + 1},
            footnote_contexts=attached_contexts,
        )
        self.assertEqual(pick_translation_text(attached_paragraph, footnote_id="32"), "分有立法之权")

    def test_footnote_context_after_sentence_end_uses_nearest_sentence_not_whole_paragraph(self):
        text = "第一句只是背景。第二句才是这个脚注要证明的判断。"
        positions = {"18": len(text)}

        contexts = build_footnote_contexts(text, positions)
        units = build_footnote_citation_units(text, positions)

        self.assertEqual(contexts["18"], "第二句才是这个脚注要证明的判断。")
        self.assertEqual(units["18"]["unit_type"], "nearest_sentence")
        self.assertGreaterEqual(units["18"]["confidence"], 0.8)

    def test_footnote_context_keeps_semicolon_compound_sentence_together(self):
        text = (
            "背景句。"
            "目的上，二者关注普遍困境；方法上，二者都强调启蒙；"
            "组织运营上，二者都强调平等和民主。"
        )
        positions = {"32": len(text)}

        contexts = build_footnote_contexts(text, positions)
        units = build_footnote_citation_units(text, positions)

        self.assertIn("目的上", contexts["32"])
        self.assertIn("组织运营上", contexts["32"])
        self.assertEqual(units["32"]["text"], contexts["32"])

    def test_footnote_parser_classifies_comma_page_list_as_distributed(self):
        footnote = parse_footnote_text("42", "霞会館『華族会館史』第92、93、94页。")

        self.assertEqual(footnote.page_numbers, [92, 93, 94])
        self.assertEqual(footnote.page_span_type, "distributed_pages")

    def test_page_span_classifies_two_page_range_as_continuous(self):
        span = classify_page_span(
            [95, 96],
            page_label="第95-96页",
            citation_text="会馆出台章程并说明组织权限。",
        )

        self.assertEqual(span["mode"], "continuous_range")

    def test_long_footnote_context_records_claim_candidates(self):
        text = (
            "第一句只是铺垫。"
            "第二句包含多个事实判断，先说明甲方提出改革方案，又说明乙方反对并提出经费负担问题，"
            "再说明会馆内部出现持续争论和组织分歧，还说明经费征收、教育扩张、会议存废、"
            "会员负担以及与既有训示之间的关系都被放在同一个论述单元中处理，"
            "并且继续补充不同派别如何围绕会馆的公共性、俱乐部化方向、教育事业优先级、"
            "追加集资方式和既有组织权威展开争执，"
            "最后指出争论影响会馆运营和教育扩张。"
        )
        positions = {"19": len(text)}

        units = build_footnote_citation_units(text, positions)

        self.assertEqual(units["19"]["unit_type"], "previous_clause")
        self.assertLessEqual(len(units["19"]["text"]), 280)
        self.assertGreaterEqual(len(units["19"]["claim_candidates"]), 2)

    def test_iter_ndl_search_keywords_produces_fallback_variants(self):
        verifier = HistoricalCitationVerifier()
        parsed = verifier.parse_docx(str(self._make_docx()))
        footnote = parsed["footnotes"][0]

        keywords = verifier._iter_ndl_search_keywords(footnote)

        self.assertGreaterEqual(len(keywords), 3)
        self.assertIn(f"{footnote.title} {footnote.author}", keywords)
        self.assertIn(footnote.title, keywords)

    def test_ndl_search_module_builds_keywords_and_sru_queries(self):
        footnote = parse_footnote_text(
            "1",
            "佐藤一郎「架空史料集：制度宣伝と事件叙述」東京：架空出版社、2001年、41頁。",
        )

        keywords = iter_ndl_search_keywords(footnote)
        queries = build_ndl_sru_queries(footnote)

        self.assertIn(f"{footnote.title} {footnote.author}", keywords)
        self.assertTrue(any("title any" in query for query in queries))
        self.assertEqual(len(queries), len(set(queries)))

    def test_ndl_search_module_prioritizes_host_title_for_contained_sources(self):
        footnote = parse_footnote_text(
            "66",
            "「憲法ニ關スル演說」6, 7, 8, 9, 10, 11, 12頁。",
        )

        keywords = iter_ndl_search_keywords(footnote)
        queries = build_ndl_sru_queries(footnote)
        host_score = score_ndl_record(
            footnote,
            title="華族同方会演説集",
            author=None,
            year="1889",
            publisher=None,
        )
        article_only_score = score_ndl_record(
            footnote,
            title="憲法ニ関スル演説",
            author=None,
            year="1937",
            publisher=None,
        )

        self.assertEqual(footnote.host_title, "華族同方会演説集")
        self.assertEqual(footnote.contained_title, "憲法ニ關スル演說")
        self.assertEqual(keywords[0], "華族同方会演説集")
        self.assertTrue(any('title any "華族同方会演説集"' in query for query in queries))
        self.assertGreaterEqual(host_score, 0.80)
        self.assertGreater(host_score, article_only_score)

    def test_footnote_parser_infers_second_quoted_title_as_host_volume(self):
        footnote = parse_footnote_text(
            "x1",
            "［日］《宗教関係法令一覧》，安丸良夫、宮地正人編：《日本近代思想大系 5：宗教と国家》，岩波書店 1996 年，第 425 页。",
        )

        self.assertEqual(footnote.title, "宗教関係法令一覧")
        self.assertEqual(footnote.host_title, "日本近代思想大系 5：宗教と国家")
        self.assertEqual(footnote.contained_title, "宗教関係法令一覧")
        self.assertEqual(footnote.source_relation, "contained_in_host")
        self.assertTrue(footnote.ndl_keyword.startswith("日本近代思想大系 5：宗教と国家"))

    def test_ndl_search_module_extracts_html_fulltext_hints(self):
        html_text = """
        <div class="search-result-item">
          <h3><a href="/books/R100000002-I000000003875"><span>華族同方会演説集</span></a></h3>
          <div class="snippet">... 憲法ニ關スル演說 ニ於テ制度ノ要旨ヲ述ベ ... PDFページ 12 ...</div>
          <a href="https://dl.ndl.go.jp/pid/1558815">デジタル</a>
        </div>
        """

        hits = extract_ndlsearch_fulltext_hits(html_text, "憲法ニ關スル演說")

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["title"], "華族同方会演説集")
        self.assertEqual(hits[0]["ndl_id"], "1558815")
        self.assertEqual(hits[0]["metadata"]["fulltext_hints"][0]["pdf_page"], 12)

    def test_ndl_search_module_extracts_digital_fulltext_snippets(self):
        item_payload = {
            "searchHits": [
                {
                    "score": 224.0,
                    "content": {
                        "pid": "info:ndljp/pid/1558815",
                        "itemId": "1558815",
                        "type": "leaf",
                        "meta": {
                            "0001Dtct": ["華族同方会演説集"],
                            "0020Dtct": ["[華族同方会]"],
                            "0059Dk": ["1889-03"],
                        },
                        "rules": {"snippet": True},
                        "contentsBundles": [
                            {
                                "id": "bundle-1",
                                "contents": [
                                    {"id": "cid-1", "originalFileName": "0001.jp2"},
                                    {"id": "cid-2", "originalFileName": "0002.jp2"},
                                    {"id": "cid-3", "originalFileName": "0003.jp2"},
                                ],
                            }
                        ],
                    },
                }
            ]
        }
        snippet_payload = {
            "1558815": {
                "contents": [
                    {
                        "cid": "cid-3",
                        "index": 2,
                        "matches": [
                            {
                                "head": "",
                                "word": "憲法ニ關スル演說",
                                "tail": "明治二十二年",
                            }
                        ],
                    }
                ]
            }
        }
        calls = []

        def fake_post(url, **_kwargs):
            calls.append(url)
            payload = item_payload if url.endswith("/item/search") else snippet_payload
            return DummyResponse(json.dumps(payload, ensure_ascii=False), headers={"content-type": "application/json"})

        records = search_ndl_digital_fulltext("憲法ニ關スル演說", max_results=3, request_post=fake_post)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["ndl_id"], "1558815")
        self.assertEqual(records[0]["metadata"]["search_route"], "ndl_digital_fulltext_api")
        self.assertEqual(records[0]["metadata"]["fulltext_hints"][0]["pdf_page"], 3)
        self.assertEqual(len(calls), 2)

    def test_ndl_fulltext_context_maps_item_hits_to_pdf_pages(self):
        item_payload = {
            "pid": "info:ndljp/pid/2983729",
            "meta": {"0001Dtct": ["明治天皇"]},
            "contentsBundles": [
                {
                    "id": "bundle-1",
                    "contents": [
                        {"id": "cid-1"},
                        {"id": "cid-2"},
                        {"id": "cid-3"},
                    ],
                }
            ],
        }
        snippet_payload = {
            "2983729": {
                "contents": [
                    {
                        "cid": "cid-2",
                        "index": 1,
                        "matches": [
                            {
                                "head": "前文",
                                "word": "國體訓蒙",
                                "tail": "後文",
                            }
                        ],
                    }
                ]
            }
        }

        def fake_post(url, **_kwargs):
            self.assertTrue(url.endswith("/fulltext/search"))
            return DummyResponse(json.dumps(snippet_payload, ensure_ascii=False))

        title, hits = search_ndl_fulltext_in_item(
            "2983729",
            "國體訓蒙",
            item_payload=item_payload,
            request_post=fake_post,
        )

        self.assertEqual(title, "明治天皇")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].pdf_page, 2)
        self.assertEqual(hits[0].snippet, "前文國體訓蒙後文")

    def test_ndl_fulltext_context_records_no_direct_hit_and_global_leads(self):
        item_payload = {
            "pid": "info:ndljp/pid/2983729",
            "meta": {"0001Dtct": ["明治天皇"]},
            "contentsBundles": [{"id": "bundle-1", "contents": [{"id": "cid-1"}]}],
        }
        no_hit_payload = {"2983729": {"contents": []}}
        item_search_payload = {
            "searchHits": [
                {
                    "score": 10,
                    "content": {
                        "pid": "info:ndljp/pid/1262367",
                        "itemId": "1262367",
                        "type": "leaf",
                        "meta": {"0001Dtct": ["国体科学研究"]},
                        "rules": {"snippet": True},
                        "contentsBundles": [{"id": "b", "contents": [{"id": "c1"}]}],
                    },
                }
            ]
        }
        global_snippet_payload = {
            "1262367": {
                "contents": [
                    {
                        "cid": "c1",
                        "index": 0,
                        "matches": [{"head": "", "word": "國體訓蒙", "tail": ""}],
                    }
                ]
            }
        }

        def fake_get(_url, **_kwargs):
            return DummyResponse(json.dumps(item_payload, ensure_ascii=False))

        def fake_post(url, **_kwargs):
            if url.endswith("/item/search"):
                return DummyResponse(json.dumps(item_search_payload, ensure_ascii=False))
            payload = no_hit_payload if _kwargs["json"]["targets"][0]["pid"] == "2983729" else global_snippet_payload
            return DummyResponse(json.dumps(payload, ensure_ascii=False))

        probe = probe_ndl_fulltext_context(
            "2983729",
            ["國體訓蒙"],
            global_queries=["國體訓蒙 里見岸雄"],
            request_get=fake_get,
            request_post=fake_post,
        )

        self.assertEqual(probe.status, "no_direct_hit")
        self.assertEqual(probe.queries_tried, ["國體訓蒙"])
        self.assertFalse(probe.hits)
        self.assertEqual(probe.global_candidates[0]["pid"], "1262367")
        self.assertEqual(probe.global_candidates[0]["relation_to_target_pid"], "different_pid")

    def test_ndl_fulltext_context_builds_targets_from_detail_payload(self):
        pid, title, targets, page_map = build_item_fulltext_target_and_page_map(
            {
                "item": {
                    "pid": "info:ndljp/pid/759333",
                    "meta": {"0001Dtct": ["国体訓蒙"]},
                    "contentsBundles": [
                        {
                            "id": "bundle-a",
                            "contents": [{"id": "page-a"}, {"id": "page-b"}],
                        }
                    ],
                }
            }
        )

        self.assertEqual(pid, "759333")
        self.assertEqual(title, "国体訓蒙")
        self.assertEqual(targets, [{"pid": "759333", "bids": ["bundle-a"]}])
        self.assertEqual(page_map["page-b"], 2)

    def test_ndl_fulltext_context_expands_seed_snippet_on_same_page(self):
        item_payload = {
            "item": {
                "pid": "info:ndljp/pid/2983729",
                "meta": {"0001Dtct": ["明治天皇"]},
                "contentsBundles": [{"id": "bundle-a", "contents": [{"id": "cid-84"}]}],
            }
        }
        seed = NDLFulltextHit(
            pid="2983729",
            query="国体訓蒙",
            snippet="太田秀敬の著「国体訓蒙」を採用している",
            pdf_page=1,
            cid="cid-84",
        )

        def fake_post(_url, **kwargs):
            query = kwargs["json"]["keyword"]
            if query.startswith("太田秀敬"):
                payload = {
                    "2983729": {
                        "contents": [
                            {
                                "cid": "cid-84",
                                "index": 0,
                                "matches": [
                                    {
                                        "head": "中学、小学の教科中に国体学の一科を加え、",
                                        "word": "太田秀敬の著「",
                                        "tail": "国体訓蒙」を採用している",
                                    }
                                ],
                            }
                        ]
                    }
                }
            elif query.endswith("採用している"):
                payload = {
                    "2983729": {
                        "contents": [
                            {
                                "cid": "cid-84",
                                "index": 0,
                                "matches": [
                                    {
                                        "head": "太田秀敬の著「国体訓蒙」を",
                                        "word": "採用している",
                                        "tail": "。或る意味で明治初年の教育を風靡した",
                                    }
                                ],
                            }
                        ]
                    }
                }
            else:
                payload = {"2983729": {"contents": []}}
            return DummyResponse(json.dumps(payload, ensure_ascii=False))

        expanded = expand_ndl_snippet_context(
            "2983729",
            seed,
            item_payload=item_payload,
            max_rounds=2,
            edge_chars=8,
            request_post=fake_post,
        )

        self.assertIn("中学、小学の教科中", expanded.context_text)
        self.assertIn("明治初年の教育", expanded.context_text)
        self.assertEqual(expanded.pdf_page, 1)
        self.assertGreaterEqual(len(expanded.evidence_hits), 2)

    def test_cross_validation_selects_fulltext_hit_inside_downloaded_window(self):
        outside = NDLFulltextHit(pid="p", query="q", snippet="outside", pdf_page=8, cid="c8")
        inside = NDLFulltextHit(pid="p", query="q", snippet="inside", pdf_page=10, cid="c10")

        selected = select_fulltext_hit([outside, inside], preferred_page_range=[10, 12])

        self.assertIs(selected, inside)
        self.assertEqual(
            classify_fulltext_page_check(selected, [10, 12]),
            "fulltext_page_inside_downloaded_window",
        )
        self.assertGreaterEqual(normalized_text_similarity("本案第一条ニ於テ有爵者", "本案第一条ニ於テ有爵者"), 0.99)

    def test_cross_validation_markdown_renders_status_summary(self):
        from modules.historical_citation.cross_validation import FulltextOcrCrossValidationResult

        report = render_cross_validation_markdown(
            [
                FulltextOcrCrossValidationResult(
                    label="case-a",
                    paper_label="paper",
                    candidate_id="p1-f1",
                    footnote_id="1",
                    mode="downloadable_ocr",
                    source_title="史料",
                    footnote_pages=[1],
                    pid="123",
                    ndl_title="史料",
                    status="cross_validated",
                    conclusion="ok",
                    selected_pdf_page=5,
                )
            ]
        )

        self.assertIn("case-a", report)
        self.assertIn("cross_validated", report)
        self.assertIn("PID 123", report)

    def test_ndl_search_module_scores_matching_metadata_higher(self):
        footnote = parse_footnote_text(
            "1",
            "佐藤一郎「架空史料集：制度宣伝と事件叙述」東京：架空出版社、2001年、41頁。",
        )

        good_score = score_ndl_record(
            footnote,
            title=footnote.title,
            author=footnote.author,
            year="2001",
            publisher=footnote.publisher,
        )
        weak_score = score_ndl_record(
            footnote,
            title="参考資料 別巻の手記",
            author="別人",
            year="1970",
            publisher="別出版社",
        )

        self.assertGreater(good_score, weak_score)
        self.assertGreaterEqual(good_score, 0.9)

    def test_ndl_search_module_penalizes_japanese_era_year_mismatch(self):
        footnote = ParsedFootnote(
            id="1",
            text="内閣官報局：《法令全書：明治２年》，内閣官報局1887年版，第221页。",
            title="法令全書：明治２年",
            author="内閣官報局",
            year="1887",
        )

        self.assertEqual(extract_japanese_era_years(footnote.title), {"明治": [2]})
        mismatch_score = score_ndl_record(
            footnote,
            title="石川県法令全書. 明治22年6-9月",
            author=None,
            year="1889",
            publisher="北溟社",
        )
        matching_score = score_ndl_record(
            footnote,
            title="法令全書 : 明治2年",
            author="内閣官報局",
            year="1887",
            publisher="内閣官報局",
        )

        self.assertLess(mismatch_score, 0.20)
        self.assertGreater(matching_score, 0.70)

    def test_ndl_search_module_penalizes_generic_short_title_hit_for_subtitle_sources(self):
        footnote = ParsedFootnote(
            id="1",
            text="「華族：近代日本貴族の虚像と実像」，16頁。",
            title="華族：近代日本貴族の虚像と実像",
            page_numbers=[16],
        )

        generic_score = score_ndl_record(
            footnote,
            title="華族財産関係資料",
            author=None,
            year=None,
            publisher=None,
        )
        matching_score = score_ndl_record(
            footnote,
            title="華族 : 近代日本貴族の虚像と実像",
            author=None,
            year=None,
            publisher=None,
        )

        self.assertLess(generic_score, 0.20)
        self.assertGreater(matching_score, 0.70)

    def test_ndl_search_module_parses_sru_records_and_dedupes_public_search(self):
        inner_xml = """
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                 xmlns:dc="http://purl.org/dc/elements/1.1/"
                 xmlns:dcterms="http://purl.org/dc/terms/"
                 xmlns:foaf="http://xmlns.com/foaf/0.1/">
          <rdf:Description rdf:about="https://dl.ndl.go.jp/pid/99999999">
            <dcterms:title>架空史料集：制度宣伝と事件叙述</dcterms:title>
            <dcterms:identifier>https://dl.ndl.go.jp/pid/99999999</dcterms:identifier>
            <dc:creator>佐藤一郎</dc:creator>
            <dcterms:issued>2001</dcterms:issued>
            <dcterms:publisher><foaf:name>架空出版社</foaf:name></dcterms:publisher>
          </rdf:Description>
        </rdf:RDF>
        """
        xml = f"""
        <srw:searchRetrieveResponse xmlns:srw="http://www.loc.gov/zing/srw/">
          <srw:records>
            <srw:record><srw:recordData>{inner_xml.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}</srw:recordData></srw:record>
            <srw:record><srw:recordData>{inner_xml.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}</srw:recordData></srw:record>
          </srw:records>
        </srw:searchRetrieveResponse>
        """
        footnote = parse_footnote_text("1", "佐藤一郎「架空史料集：制度宣伝と事件叙述」東京：架空出版社、2001年、41頁。")

        parsed = parse_ndl_sru_records(xml)
        searched = search_ndl_public_api(
            footnote,
            max_results=5,
            request_get=lambda *_args, **_kwargs: DummyResponse(xml),
            sleep=lambda _seconds: None,
        )

        self.assertEqual(parsed[0]["ndl_id"], "99999999")
        self.assertEqual(parsed[0]["title"], footnote.title)
        self.assertEqual(len(searched), 1)

    def test_ndl_search_module_does_not_coerce_generic_identifier_to_pid(self):
        inner_xml = """
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                 xmlns:dc="http://purl.org/dc/elements/1.1/"
                 xmlns:dcterms="http://purl.org/dc/terms/">
          <rdf:Description rdf:about="https://ndlsearch.ndl.go.jp/books/R100000002-I000000003875">
            <dcterms:title>華族同方会演説集 (6)</dcterms:title>
            <dcterms:identifier>000000003875</dcterms:identifier>
          </rdf:Description>
        </rdf:RDF>
        """
        xml = f"""
        <srw:searchRetrieveResponse xmlns:srw="http://www.loc.gov/zing/srw/">
          <srw:records>
            <srw:record><srw:recordData>{inner_xml.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}</srw:recordData></srw:record>
          </srw:records>
        </srw:searchRetrieveResponse>
        """

        parsed = parse_ndl_sru_records(xml)

        self.assertIsNone(parsed[0]["ndl_id"])
        self.assertTrue(parsed[0]["url"].startswith("https://ndlsearch.ndl.go.jp/books/"))

    def test_source_acquisition_module_selects_match_and_expands_page_window(self):
        matches = [
            NDLSearchMatch(title="metadata only", url="https://example.invalid/item"),
            NDLSearchMatch(title="with pid", url="https://dl.ndl.go.jp/pid/99999999", ndl_id="99999999"),
        ]

        self.assertEqual(select_preferred_source_match(matches).ndl_id, "99999999")
        self.assertEqual(expand_page_window(41, 2), [41, 40, 42, 39, 43])

    def test_source_acquisition_module_prefers_likely_digital_pid_over_short_id(self):
        matches = [
            NDLSearchMatch(title="short id", url="https://dl.ndl.go.jp/pid/2211", ndl_id="2211"),
            NDLSearchMatch(title="digital pid", url="https://dl.ndl.go.jp/pid/3017836", ndl_id="3017836"),
        ]

        self.assertEqual(select_preferred_source_match(matches).ndl_id, "3017836")

    def test_verifier_prefers_ndl_match_that_covers_cited_pages(self):
        verifier = HistoricalCitationVerifier()
        verifier._get_ndl_total_pages_quick = lambda ndl_id: {"00929370": 25, "13180480": 132}.get(ndl_id)  # type: ignore[method-assign]
        matches = [
            NDLSearchMatch(title="too short", url="https://dl.ndl.go.jp/pid/00929370", ndl_id="00929370"),
            NDLSearchMatch(title="covers page", url="https://dl.ndl.go.jp/pid/13180480", ndl_id="13180480"),
        ]

        self.assertEqual(verifier._select_preferred_match_for_pages(matches, [92, 93]).ndl_id, "13180480")

    def test_verifier_treats_double_page_ndl_total_as_page_coverage(self):
        verifier = HistoricalCitationVerifier()
        verifier._get_ndl_total_pages_quick = lambda ndl_id: {"3017836": 514}.get(ndl_id)  # type: ignore[method-assign]
        matches = [
            NDLSearchMatch(title="metadata only", url="https://ndlsearch.ndl.go.jp/books/R100000001-I1", score=0.95),
            NDLSearchMatch(title="downloadable", url="https://dl.ndl.go.jp/pid/3017836", ndl_id="3017836", score=0.85),
        ]

        ordered = verifier._ordered_matches_for_pages(matches, [842])

        self.assertEqual(ordered[0].ndl_id, "3017836")

    def test_verifier_skips_cached_front_matter_mapping_failure(self):
        verifier = HistoricalCitationVerifier()

        self.assertTrue(verifier._should_skip_page_mapping_after_failure("front_matter_mapping_not_inferred"))

    def test_verifier_keeps_later_downloadable_candidates_available(self):
        verifier = HistoricalCitationVerifier()
        verifier._get_ndl_total_pages_quick = lambda ndl_id: {"11111111": None, "22222222": None}.get(ndl_id)  # type: ignore[method-assign]
        matches = [
            NDLSearchMatch(title="first unknown", url="https://dl.ndl.go.jp/pid/11111111", ndl_id="11111111", score=0.9),
            NDLSearchMatch(title="second unknown", url="https://dl.ndl.go.jp/pid/22222222", ndl_id="22222222", score=0.8),
        ]

        ordered = verifier._ordered_matches_for_pages(matches, [10])

        self.assertEqual([match.ndl_id for match in ordered], ["11111111", "22222222"])

    def test_ndl_search_resolves_detail_page_digital_pid(self):
        html = '<script id="__NUXT_DATA__">"https:\\/\\/dl.ndl.go.jp\\/pid\\/12345678"</script>'

        resolution = resolve_ndlsearch_detail_url(
            "https://ndlsearch.ndl.go.jp/books/R100000000-I1",
            request_get=lambda *_args, **_kwargs: DummyResponse(html),
        )

        self.assertEqual(resolution["status"], "resolved")
        self.assertEqual(resolution["ndl_ids"], ["12345678"])

    def test_ndl_search_reports_detail_page_without_digital_pid(self):
        html = '<script id="__NUXT_DATA__">["R100000000-I1","R100000000-I2"]</script>'

        resolution = resolve_ndlsearch_detail_url(
            "https://ndlsearch.ndl.go.jp/books/R100000000-I1",
            request_get=lambda *_args, **_kwargs: DummyResponse(html),
        )

        self.assertEqual(resolution["status"], "no_digital_pid")
        self.assertEqual(resolution["ndl_ids"], [])
        self.assertEqual(resolution["related_book_ids"], ["R100000000-I2"])

    def test_verifier_obtain_source_pdf_tries_next_ndl_match_after_failure(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="source", title="source", page_numbers=[10]),
            ndl_matches=[
                NDLSearchMatch(title="bad", url="https://dl.ndl.go.jp/pid/11111111", ndl_id="11111111", score=0.9),
                NDLSearchMatch(title="good", url="https://dl.ndl.go.jp/pid/22222222", ndl_id="22222222", score=0.8),
            ],
        )

        class DummyDownloadModule:
            def __init__(self):
                self.ndl_ids = []

            def download_first_match(self, **kwargs):
                self.ndl_ids.append(kwargs.get("ndl_id"))
                if kwargs.get("ndl_id") == "22222222":
                    return NDLDownloadOutcome(
                        success=True,
                        mode="restricted",
                        status="success",
                        keyword=kwargs["keyword"],
                        output_dir=str(output_dir),
                        file_path=str(output_dir / "ok.pdf"),
                    )
                return NDLDownloadOutcome(
                    success=False,
                    mode="restricted",
                    status="failed",
                    keyword=kwargs["keyword"],
                    output_dir=str(output_dir),
                    error_message="ndl_toc_not_found:11111111",
                )

        dummy_module = DummyDownloadModule()
        verifier._get_ndl_download_module = lambda: dummy_module  # type: ignore[method-assign]
        verifier._download_public_pdf = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._estimate_scan_page_range = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
            "anchor_scan_page": 10,
            "anchor_book_page": 10,
            "start_scan_page": 10,
            "end_scan_page": 10,
        }
        verifier._get_ndl_total_pages_quick = lambda _ndl_id: None  # type: ignore[method-assign]

        pdf_path = verifier._obtain_source_pdf(
            candidate,
            output_dir=output_dir,
            restricted_download=True,
            page_window=0,
            download_max_attempts=1,
        )

        self.assertEqual(pdf_path, str(output_dir / "ok.pdf"))
        self.assertEqual(dummy_module.ndl_ids[:2], ["11111111", "22222222"])
        self.assertEqual(candidate.artifacts["selected_source_match"]["ndl_id"], "22222222")

    def test_verifier_skips_stale_source_pdf_when_better_match_is_now_preferred(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="source", title="source", page_numbers=[10]),
            ndl_matches=[
                NDLSearchMatch(title="preferred", url="https://dl.ndl.go.jp/pid/11111111", ndl_id="11111111", score=0.9),
                NDLSearchMatch(title="stale", url="https://dl.ndl.go.jp/pid/22222222", ndl_id="22222222", score=0.8),
            ],
        )
        candidate.support_status = "not_supported"
        candidate.artifacts = {
            "source_pdf": str(output_dir / "stale.pdf"),
            "selected_source_match": {"ndl_id": "22222222", "platform": "ndl", "title": "stale"},
            "downloaded_page_range": [10, 10],
            "page_mapping": {"anchor_scan_page": 10, "anchor_book_page": 10, "start_scan_page": 10, "end_scan_page": 10},
            "mapped_footnote_pages": [10],
        }

        class DummyDownloadModule:
            def __init__(self):
                self.ndl_ids = []

            def download_first_match(self, **kwargs):
                self.ndl_ids.append(kwargs.get("ndl_id"))
                return NDLDownloadOutcome(
                    success=True,
                    mode="restricted",
                    status="success",
                    keyword=kwargs["keyword"],
                    output_dir=str(output_dir),
                    file_path=str(output_dir / "preferred.pdf"),
                )

        dummy_module = DummyDownloadModule()
        verifier._is_usable_pdf = lambda _path: True  # type: ignore[method-assign]
        verifier._get_ndl_download_module = lambda: dummy_module  # type: ignore[method-assign]
        verifier._download_public_pdf = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._estimate_scan_page_range = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
            "anchor_scan_page": 10,
            "anchor_book_page": 10,
            "start_scan_page": 10,
            "end_scan_page": 10,
        }
        verifier._get_ndl_total_pages_quick = lambda _ndl_id: None  # type: ignore[method-assign]

        pdf_path = verifier._obtain_source_pdf(
            candidate,
            output_dir=output_dir,
            restricted_download=True,
            page_window=0,
            download_max_attempts=1,
        )

        self.assertEqual(pdf_path, str(output_dir / "preferred.pdf"))
        self.assertEqual(dummy_module.ndl_ids, ["11111111"])
        self.assertIn(
            "source_pdf_reuse_skipped_preferred_match_changed:22222222->11111111",
            candidate.notes,
        )
        self.assertEqual(candidate.artifacts["selected_source_match"]["ndl_id"], "11111111")

    def test_verifier_preserves_exact_title_primary_source_after_weak_alignment(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="華族会館史、374頁。", title="華族会館史", page_numbers=[374]),
            ndl_matches=[
                NDLSearchMatch(title="華族会館史", url="https://dl.ndl.go.jp/pid/3017836", ndl_id="3017836", score=0.95),
                NDLSearchMatch(title="華族会館史 別資料", url="https://ndlsearch.ndl.go.jp/books/R1", score=0.8),
            ],
        )
        candidate.support_status = "needs_manual_review"
        candidate.confidence = 0.02
        candidate.artifacts = {
            "source_pdf": str(output_dir / "ndl_3017836_p198-p204.pdf"),
            "selected_source_match": {"ndl_id": "3017836", "platform": "ndl", "title": "華族会館史"},
            "downloaded_page_range": [198, 204],
            "page_mapping": {"anchor_scan_page": 16, "anchor_book_page": 1, "start_scan_page": 198, "end_scan_page": 204},
            "mapped_footnote_pages": [202],
        }

        self.assertFalse(verifier._should_try_alternate_source(candidate))
        self.assertIn("alternate_source_retry_skipped_exact_title_primary_source", candidate.notes)

    def test_verifier_allows_same_title_digital_fallback_after_weak_alignment(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(
                id="1",
                text="華族会館誌 上巻、384頁。",
                title="華族会館誌 上巻",
                page_numbers=[384],
            ),
            ndl_matches=[
                NDLSearchMatch(title="華族会館誌 上巻", url="https://dl.ndl.go.jp/pid/12095138", ndl_id="12095138", score=0.95),
                NDLSearchMatch(title="華族会館誌", url="https://dl.ndl.go.jp/pid/87025934", ndl_id="87025934", score=0.68),
            ],
        )
        candidate.support_status = "needs_manual_review"
        candidate.confidence = 0.02
        candidate.artifacts = {
            "source_pdf": str(output_dir / "ndl_12095138_p54-p55.pdf"),
            "selected_source_match": {"ndl_id": "12095138", "platform": "ndl", "title": "華族会館誌 上巻"},
            "downloaded_page_range": [54, 55],
            "page_mapping": {"anchor_scan_page": 8, "anchor_book_page": 12, "start_scan_page": 54, "end_scan_page": 55},
            "mapped_footnote_pages": [54],
        }

        self.assertTrue(verifier._should_try_alternate_source(candidate))

    def test_verifier_blocks_non_equivalent_fulltext_lead_from_alternate_retry(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="日本外交文書第32巻。", title="日本外交文書", page_numbers=[216]),
            ndl_matches=[
                NDLSearchMatch(title="日本外交文書", url="https://dl.ndl.go.jp/pid/3448128", ndl_id="3448128", score=0.95),
                NDLSearchMatch(
                    title="日本外交文書",
                    url="https://dl.ndl.go.jp/pid/3448132",
                    ndl_id="3448132",
                    score=0.7,
                    metadata={"search_route": "ndl_digital_fulltext_api"},
                ),
            ],
        )
        candidate.support_status = "needs_manual_review"
        candidate.confidence = 0.02
        candidate.artifacts = {
            "source_pdf": str(output_dir / "ndl_3448128_p32-p34.pdf"),
            "selected_source_match": {"ndl_id": "3448128", "platform": "ndl", "title": "日本外交文書"},
            "downloaded_page_range": [32, 34],
            "mapped_footnote_pages": [32],
            "source_resolver_plan": {
                "source_type": "volume_series",
                "known_pid_candidates": ["3448128", "3448126", "2530174"],
            },
            "equivalent_pid_group": [
                {"ndl_id": "3448128", "scope": "configured_or_same_source_equivalent"},
                {"ndl_id": "3448126", "scope": "configured_or_same_source_equivalent"},
                {"ndl_id": "2530174", "scope": "configured_or_same_source_equivalent"},
            ],
            "fulltext_lead_pid_group": [
                {"ndl_id": "3448132", "scope": "global_fulltext_lead_not_equivalent"}
            ],
        }

        self.assertFalse(verifier._should_try_alternate_source(candidate))
        self.assertIn("3448132", candidate.artifacts["non_equivalent_fulltext_lead_skipped_ids"])
        self.assertIn("alternate_source_retry_skipped_non_equivalent_fulltext_lead", candidate.notes)

    def test_verifier_preserves_source_when_only_wrong_volume_alternate_exists(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(
                id="1",
                text="華族会館誌 上巻、384頁。",
                title="華族会館誌 上巻",
                page_numbers=[384],
            ),
            ndl_matches=[
                NDLSearchMatch(title="華族会館誌 上巻", url="https://dl.ndl.go.jp/pid/12095138", ndl_id="12095138", score=0.95),
                NDLSearchMatch(title="華族会館誌 下巻", url="https://dl.ndl.go.jp/pid/865213900", ndl_id="865213900", score=0.7),
            ],
        )
        candidate.support_status = "needs_manual_review"
        candidate.confidence = 0.02
        candidate.artifacts = {
            "source_pdf": str(output_dir / "ndl_12095138_p54-p55.pdf"),
            "selected_source_match": {"ndl_id": "12095138", "platform": "ndl", "title": "華族会館誌 上巻"},
            "downloaded_page_range": [54, 55],
            "page_mapping": {"anchor_scan_page": 8, "anchor_book_page": 12, "start_scan_page": 54, "end_scan_page": 55},
            "mapped_footnote_pages": [54],
        }

        self.assertFalse(verifier._should_try_alternate_source(candidate))

    def test_verifier_filters_wrong_volume_matches_before_download(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(
                id="1",
                text="華族会館誌 上巻、384頁。",
                title="華族会館誌 上巻",
                page_numbers=[384],
            ),
            ndl_matches=[
                NDLSearchMatch(title="華族会館誌 下巻", url="https://dl.ndl.go.jp/pid/865213900", ndl_id="865213900", score=0.9),
                NDLSearchMatch(title="華族会館誌", url="https://dl.ndl.go.jp/pid/87025934", ndl_id="87025934", score=0.8),
            ],
        )

        class DummyDownloadModule:
            def __init__(self):
                self.ndl_ids = []

            def download_first_match(self, **kwargs):
                self.ndl_ids.append(kwargs.get("ndl_id"))
                return NDLDownloadOutcome(
                    success=True,
                    mode="restricted",
                    status="success",
                    keyword=kwargs["keyword"],
                    output_dir=str(output_dir),
                    file_path=str(output_dir / "ok.pdf"),
                )

        dummy_module = DummyDownloadModule()
        verifier._get_ndl_download_module = lambda: dummy_module  # type: ignore[method-assign]
        verifier._download_public_pdf = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._estimate_scan_page_range = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
            "anchor_scan_page": 54,
            "anchor_book_page": 384,
            "start_scan_page": 54,
            "end_scan_page": 54,
        }
        verifier._get_ndl_total_pages_quick = lambda _ndl_id: None  # type: ignore[method-assign]

        pdf_path = verifier._obtain_source_pdf(
            candidate,
            output_dir=output_dir,
            restricted_download=True,
            page_window=0,
            download_max_attempts=1,
        )

        self.assertEqual(pdf_path, str(output_dir / "ok.pdf"))
        self.assertEqual(dummy_module.ndl_ids, ["87025934"])
        self.assertEqual(candidate.artifacts["source_match_order"], ["87025934"])
        self.assertIn("source_match_wrong_volume_filtered", candidate.notes)

    def test_verifier_filters_metadata_mismatch_matches_before_download(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        mismatch = NDLSearchMatch(
            title="維新日誌",
            url="https://dl.ndl.go.jp/pid/11111111",
            ndl_id="11111111",
            score=0.9,
        )
        mismatch.metadata["source_mismatch"] = True
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="太政官日誌、39頁。", title="太政官日誌", page_numbers=[39]),
            ndl_matches=[
                mismatch,
                NDLSearchMatch(title="太政官日誌", url="https://dl.ndl.go.jp/pid/22222222", ndl_id="22222222", score=0.8),
            ],
        )

        class DummyDownloadModule:
            def __init__(self):
                self.ndl_ids = []

            def download_first_match(self, **kwargs):
                self.ndl_ids.append(kwargs.get("ndl_id"))
                return NDLDownloadOutcome(
                    success=True,
                    mode="restricted",
                    status="success",
                    keyword=kwargs["keyword"],
                    output_dir=str(output_dir),
                    file_path=str(output_dir / "ok.pdf"),
                )

        dummy_module = DummyDownloadModule()
        verifier._get_ndl_download_module = lambda: dummy_module  # type: ignore[method-assign]
        verifier._download_public_pdf = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._estimate_scan_page_range = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
            "anchor_scan_page": 39,
            "anchor_book_page": 39,
            "start_scan_page": 39,
            "end_scan_page": 39,
        }
        verifier._get_ndl_total_pages_quick = lambda _ndl_id: None  # type: ignore[method-assign]

        pdf_path = verifier._obtain_source_pdf(
            candidate,
            output_dir=output_dir,
            restricted_download=True,
            page_window=0,
            download_max_attempts=1,
        )

        self.assertEqual(pdf_path, str(output_dir / "ok.pdf"))
        self.assertEqual(dummy_module.ndl_ids, ["22222222"])
        self.assertEqual(candidate.artifacts["source_match_order"], ["22222222"])
        self.assertIn("source_match_metadata_mismatch_filtered", candidate.notes)

    def test_verifier_does_not_download_non_equivalent_fulltext_lead(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="日本外交文書第32巻、216頁。", title="日本外交文書", page_numbers=[216]),
            ndl_matches=[
                NDLSearchMatch(
                    title="日本外交文書",
                    url="https://dl.ndl.go.jp/pid/3448128",
                    ndl_id="3448128",
                    score=0.95,
                    metadata={"search_route": "resolver_config_known_pid", "known_pid_candidate": True},
                ),
                NDLSearchMatch(
                    title="日本外交文書",
                    url="https://dl.ndl.go.jp/pid/3448132",
                    ndl_id="3448132",
                    score=0.7,
                    metadata={"search_route": "ndl_digital_fulltext_api"},
                ),
            ],
            artifacts={
                "source_resolver_plan": {
                    "source_type": "volume_series",
                    "known_pid_candidates": ["3448128", "3448126", "2530174"],
                },
                "equivalent_pid_group": [
                    {"ndl_id": "3448128", "scope": "configured_or_same_source_equivalent"},
                    {"ndl_id": "3448126", "scope": "configured_or_same_source_equivalent"},
                    {"ndl_id": "2530174", "scope": "configured_or_same_source_equivalent"},
                ],
                "fulltext_lead_pid_group": [
                    {"ndl_id": "3448132", "scope": "global_fulltext_lead_not_equivalent"}
                ],
            },
        )

        class DummyDownloadModule:
            def __init__(self):
                self.ndl_ids = []

            def download_first_match(self, **kwargs):
                self.ndl_ids.append(kwargs.get("ndl_id"))
                if kwargs.get("ndl_id") == "3448132":
                    raise AssertionError("fulltext lead PID must not be downloaded automatically")
                return NDLDownloadOutcome(
                    success=False,
                    mode="restricted",
                    status="failed",
                    keyword=kwargs["keyword"],
                    output_dir=str(output_dir),
                )

        class FakeNDLPlatform:
            name = "ndl"

            def download_public_pdf(self, *_args, **_kwargs):
                return None

            def build_restricted_download_requests(self, **kwargs):
                return [
                    {
                        "keyword": "日本外交文書",
                        "ndl_id": kwargs["top_match"].ndl_id,
                        "output_dir": str(kwargs["output_dir"]),
                        "start_page": kwargs["start_page"],
                        "end_page": kwargs["end_page"],
                    }
                ]

        dummy_module = DummyDownloadModule()
        fake_platform = FakeNDLPlatform()
        verifier._resolve_ndlsearch_matches = lambda _candidate: None  # type: ignore[method-assign]
        verifier._get_platform_for_match = lambda _match: fake_platform  # type: ignore[method-assign]
        verifier._get_ndl_download_module = lambda: dummy_module  # type: ignore[method-assign]
        verifier._estimate_scan_page_range = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
            "anchor_scan_page": 32,
            "anchor_book_page": 216,
            "start_scan_page": 32,
            "end_scan_page": 32,
        }
        verifier._fulltext_pdf_page_fallback_plan = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._get_ndl_total_pages_quick = lambda _ndl_id: None  # type: ignore[method-assign]

        pdf_path = verifier._obtain_source_pdf(
            candidate,
            output_dir=output_dir,
            restricted_download=True,
            page_window=0,
            download_max_attempts=1,
        )

        self.assertIsNone(pdf_path)
        self.assertEqual(dummy_module.ndl_ids, ["3448128"])
        self.assertEqual(candidate.artifacts["source_match_order"], ["3448128"])
        self.assertIn("3448132", candidate.artifacts["non_equivalent_fulltext_lead_skipped_ids"])
        self.assertIn("source_match_non_equivalent_fulltext_lead_filtered", candidate.notes)

    def test_verifier_restores_prior_attempt_when_alternate_source_fails(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="source", title="source", page_numbers=[10]),
        )
        candidate.verification_status = "page_mapping_unavailable"
        candidate.support_status = "unassessed"
        candidate.artifacts = {
            "source_attempts": [
                {
                    "selected_source_match": {"ndl_id": "12095138", "title": "華族会館誌 上巻"},
                    "source_pdf": "prior.pdf",
                    "downloaded_page_range": [54, 55],
                    "page_mapping": {"anchor_scan_page": 8, "anchor_book_page": 12},
                    "mapped_footnote_pages": [54],
                    "matched_scan_page": 54,
                    "matched_book_pages": [384],
                    "page_label_mode": "book",
                    "matched_page": 384,
                    "matched_japanese": "prior japanese text",
                    "confidence": 0.0248,
                    "verification_status": "needs_manual_review",
                    "support_status": "needs_manual_review",
                    "support_reason": "weak but usable",
                    "evidence_scope": "cited_pages",
                    "alignment_scope": "cited_pages",
                    "llm_review": {
                        "provider": "ollama",
                        "decision": "not_supported",
                        "reason": "weak",
                    },
                    "llm_review_runtime": {"provider": "ollama", "available": True},
                }
            ]
        }

        restored = verifier._restore_prior_source_attempt_after_failed_retry(candidate)

        self.assertTrue(restored)
        self.assertEqual(candidate.verification_status, "needs_manual_review")
        self.assertEqual(candidate.support_status, "needs_manual_review")
        self.assertEqual(candidate.matched_page, 384)
        self.assertEqual(candidate.matched_japanese, "prior japanese text")
        self.assertEqual(candidate.artifacts["source_pdf"], "prior.pdf")
        self.assertEqual(candidate.artifacts["selected_source_match"]["ndl_id"], "12095138")
        self.assertEqual(candidate.artifacts["llm_review"]["provider"], "ollama")
        self.assertTrue(candidate.artifacts["llm_review_runtime"]["available"])
        self.assertIn("alternate_source_retry_failed_restored_prior_attempt", candidate.notes)

    def test_verifier_allows_alternate_source_when_selected_title_differs(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="華族会館史、374頁。", title="華族会館史", page_numbers=[374]),
            ndl_matches=[
                NDLSearchMatch(title="別資料", url="https://dl.ndl.go.jp/pid/3017836", ndl_id="3017836", score=0.95),
                NDLSearchMatch(title="華族会館史", url="https://dl.ndl.go.jp/pid/99999999", ndl_id="99999999", score=0.8),
            ],
        )
        candidate.support_status = "needs_manual_review"
        candidate.confidence = 0.02
        candidate.artifacts = {
            "source_pdf": str(output_dir / "ndl_3017836_p198-p204.pdf"),
            "selected_source_match": {"ndl_id": "3017836", "platform": "ndl", "title": "別資料"},
            "downloaded_page_range": [198, 204],
            "page_mapping": {"anchor_scan_page": 16, "anchor_book_page": 1, "start_scan_page": 198, "end_scan_page": 204},
            "mapped_footnote_pages": [202],
        }

        self.assertTrue(verifier._should_try_alternate_source(candidate))

    def test_verifier_obtain_source_pdf_resolves_ndlsearch_url_before_download(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="source", title="source", page_numbers=[10]),
            ndl_matches=[
                NDLSearchMatch(
                    title="detail only",
                    url="https://ndlsearch.ndl.go.jp/books/R100000000-I1",
                    platform="ndl",
                    platform_item_id="https://ndlsearch.ndl.go.jp/books/R100000000-I1",
                    score=0.9,
                ),
            ],
        )

        class DummyDownloadModule:
            def __init__(self):
                self.ndl_ids = []

            def download_first_match(self, **kwargs):
                self.ndl_ids.append(kwargs.get("ndl_id"))
                return NDLDownloadOutcome(
                    success=True,
                    mode="restricted",
                    status="success",
                    keyword=kwargs["keyword"],
                    output_dir=str(output_dir),
                    file_path=str(output_dir / "ok.pdf"),
                )

        dummy_module = DummyDownloadModule()
        verifier._ndlsearch_detail_resolution_cache[candidate.ndl_matches[0].url] = {
            "status": "resolved",
            "ndl_ids": ["12345678"],
            "related_book_ids": [],
            "method": "detail_page",
        }
        verifier._get_ndl_download_module = lambda: dummy_module  # type: ignore[method-assign]
        verifier._download_public_pdf = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._estimate_scan_page_range = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
            "anchor_scan_page": 10,
            "anchor_book_page": 10,
            "start_scan_page": 10,
            "end_scan_page": 10,
        }
        verifier._get_ndl_total_pages_quick = lambda _ndl_id: None  # type: ignore[method-assign]

        pdf_path = verifier._obtain_source_pdf(
            candidate,
            output_dir=output_dir,
            restricted_download=True,
            page_window=0,
            download_max_attempts=1,
        )

        self.assertEqual(pdf_path, str(output_dir / "ok.pdf"))
        self.assertEqual(dummy_module.ndl_ids, ["12345678"])
        self.assertTrue(candidate.ndl_matches[0].metadata["resolved_from_ndlsearch_url"])

    def test_verifier_skips_restricted_ndl_download_without_pid(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="source", title="source", page_numbers=[10]),
            ndl_matches=[
                NDLSearchMatch(
                    title="metadata only",
                    url="https://ndlsearch.ndl.go.jp/books/R100000136-I1",
                    platform="ndl",
                    metadata={
                        "fulltext_hints": [
                            {
                                "query": "source",
                                "snippet": "source snippet",
                                "pdf_page": 12,
                                "book_id": "R100000136-I1",
                            }
                        ]
                    },
                ),
            ],
        )

        class DummyDownloadModule:
            def download_first_match(self, **_kwargs):
                raise AssertionError("download should not run without an explicit NDL pid")

        verifier._get_ndl_download_module = lambda: DummyDownloadModule()  # type: ignore[method-assign]
        verifier._download_public_pdf = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._estimate_scan_page_range = lambda *_args, **_kwargs: None  # type: ignore[method-assign]

        pdf_path = verifier._obtain_source_pdf(
            candidate,
            output_dir=output_dir,
            restricted_download=True,
            page_window=0,
            download_max_attempts=1,
        )

        self.assertIsNone(pdf_path)
        self.assertIn("restricted_download_skipped_no_ndl_pid", candidate.notes)
        self.assertEqual(candidate.artifacts["source_availability"]["reason"], "no_digital_pid")
        self.assertEqual(candidate.artifacts["ndl_fulltext_hints"][0]["pdf_page"], 12)
        self.assertEqual(
            candidate.artifacts["ndl_fulltext_hints"][0]["page_match_status"],
            "pdf_page_hint_unmapped_to_source_page",
        )
        self.assertTrue(any(note.startswith("source_unavailable:no_digital_pid") for note in candidate.notes))

    def test_verifier_skips_restricted_ndl_download_without_page_mapping(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="source", title="source", page_numbers=[41]),
            ndl_matches=[
                NDLSearchMatch(title="source", url="https://dl.ndl.go.jp/pid/12345678", ndl_id="12345678", score=0.9),
            ],
        )

        class DummyDownloadModule:
            def download_first_match(self, **_kwargs):
                raise AssertionError("raw NDL page download should not run without page mapping")

        verifier._get_ndl_download_module = lambda: DummyDownloadModule()  # type: ignore[method-assign]
        verifier._download_public_pdf = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._estimate_scan_page_range = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._get_ndl_total_pages_quick = lambda _ndl_id: None  # type: ignore[method-assign]

        pdf_path = verifier._obtain_source_pdf(
            candidate,
            output_dir=output_dir,
            restricted_download=True,
            page_window=4,
            download_max_attempts=1,
        )

        self.assertIsNone(pdf_path)
        self.assertTrue(candidate.artifacts["page_mapping_required_but_unavailable"])
        self.assertIn("12345678", candidate.artifacts["page_mapping_unavailable_ndl_ids"])

    def test_verifier_uses_diary_known_pid_page_window_when_mapping_and_snippet_missing(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="1900年5月12日，原敬在日记中记录了相关交涉。",
            translation_text="1900年5月12日，原敬在日记中记录了相关交涉。",
            footnote_id="1",
            footnote=ParsedFootnote(
                id="1",
                text="『原敬日記』1900年5月12日条，第84頁。",
                title="原敬日記",
                page_numbers=[84],
            ),
            ndl_matches=[
                NDLSearchMatch(
                    title="原敬日記",
                    url="https://dl.ndl.go.jp/pid/2982135",
                    ndl_id="2982135",
                    score=0.9,
                    metadata={
                        "search_route": "resolver_config_known_pid",
                        "known_pid_candidate": True,
                    },
                )
            ],
            artifacts={
                "source_resolver_plan": {
                    "source_type": "diary",
                    "known_pid_candidates": ["2982135"],
                    "source_level_cache_key": "原敬日記|原敬日記|1900年5月12日|1900年",
                }
            },
        )

        class DummyDownloadModule:
            def __init__(self):
                self.requests = []

            def download_first_match(self, **kwargs):
                self.requests.append(kwargs)
                return NDLDownloadOutcome(
                    success=True,
                    mode="restricted",
                    status="success",
                    keyword=kwargs["keyword"],
                    output_dir=str(output_dir),
                    file_path=str(output_dir / "diary.pdf"),
                )

        class FakeNDLPlatform:
            name = "ndl"

            def download_public_pdf(self, *_args, **_kwargs):
                return None

            def build_restricted_download_requests(self, **kwargs):
                return [
                    {
                        "keyword": "原敬日記",
                        "ndl_id": kwargs["top_match"].ndl_id,
                        "output_dir": str(kwargs["output_dir"]),
                        "start_page": kwargs["start_page"],
                        "end_page": kwargs["end_page"],
                    }
                ]

        dummy_module = DummyDownloadModule()
        fake_platform = FakeNDLPlatform()
        verifier._resolve_ndlsearch_matches = lambda _candidate: None  # type: ignore[method-assign]
        verifier._get_platform_for_match = lambda _match: fake_platform  # type: ignore[method-assign]
        verifier._get_ndl_download_module = lambda: dummy_module  # type: ignore[method-assign]
        verifier._download_public_pdf = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._estimate_scan_page_range = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._fulltext_pdf_page_fallback_plan = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._get_ndl_total_pages_quick = lambda _ndl_id: None  # type: ignore[method-assign]

        pdf_path = verifier._obtain_source_pdf(
            candidate,
            output_dir=output_dir,
            restricted_download=True,
            page_window=4,
            download_max_attempts=1,
        )

        self.assertEqual(pdf_path, str(output_dir / "diary.pdf"))
        self.assertEqual(dummy_module.requests[0]["start_page"], 82)
        self.assertEqual(dummy_module.requests[0]["end_page"], 86)
        self.assertEqual(candidate.artifacts["downloaded_page_range"], [82, 86])
        self.assertEqual(candidate.artifacts["known_pid_page_window_fallback"]["ndl_id"], "2982135")
        self.assertEqual(candidate.artifacts["known_pid_page_window_fallback"]["page_window"], 2)
        self.assertFalse(candidate.artifacts.get("page_mapping_required_but_unavailable"))
        self.assertIn("diary_known_pid_page_window_fallback_used:book_pages=84", candidate.notes)

    def test_contained_document_known_pid_page_window_fallback_uses_cited_page(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p2-f8",
            paragraph_index=2,
            paragraph_text="Yamagata opinion document.",
            translation_text="Yamagata opinion document.",
            footnote_id="p2n8",
            footnote=ParsedFootnote(
                id="p2n8",
                text="山縣有朋意見書, p. 306.",
                title="山縣有朋意見書",
                page_numbers=[306],
            ),
            ndl_matches=[],
            artifacts={
                "source_resolver_plan": {
                    "source_type": "contained_document",
                    "known_pid_candidates": ["3025431"],
                }
            },
        )
        top_match = NDLSearchMatch(
            title="山縣有朋意見書",
            url="https://dl.ndl.go.jp/pid/3025431",
            ndl_id="3025431",
            score=0.9,
            metadata={"search_route": "resolver_config_known_pid"},
        )

        plan = verifier._known_pid_page_window_fallback_plan(candidate, top_match, page_window=4)

        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan["start_page"], 304)
        self.assertEqual(plan["end_page"], 308)
        self.assertEqual(
            plan["note"],
            "contained_document_known_pid_page_window_fallback_used:book_pages=306",
        )
        artifact = candidate.artifacts["known_pid_page_window_fallback"]
        self.assertEqual(artifact["ndl_id"], "3025431")
        self.assertEqual(artifact["source_type"], "contained_document")
        self.assertEqual(artifact["basis"], "known_document_pid_without_snippet_or_page_mapping")
        self.assertEqual(artifact["page_window"], 2)

    def test_known_pid_page_window_precedes_title_only_fulltext_page_hint(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p2-f8",
            paragraph_index=2,
            paragraph_text="Yamagata opinion document.",
            translation_text="Yamagata opinion document.",
            footnote_id="p2n8",
            footnote=ParsedFootnote(
                id="p2n8",
                text="山縣有朋意見書, p. 306.",
                title="山縣有朋意見書",
                page_numbers=[306],
            ),
            ndl_matches=[
                NDLSearchMatch(
                    title="山縣有朋意見書",
                    url="https://dl.ndl.go.jp/pid/3025431",
                    ndl_id="3025431",
                    score=0.9,
                    metadata={
                        "search_route": "resolver_config_known_pid",
                        "fulltext_hints": [
                            {
                                "query": "山縣有朋意見書",
                                "snippet": "山縣有朋意見書",
                                "pdf_page": 3,
                                "book_id": "3025431",
                            }
                        ],
                    },
                )
            ],
            artifacts={
                "source_resolver_plan": {
                    "source_type": "contained_document",
                    "known_pid_candidates": ["3025431"],
                }
            },
        )

        class DummyDownloadModule:
            def __init__(self):
                self.requests = []

            def download_first_match(self, **kwargs):
                self.requests.append(kwargs)
                return NDLDownloadOutcome(
                    success=True,
                    mode="restricted",
                    status="success",
                    keyword=kwargs["keyword"],
                    output_dir=str(output_dir),
                    file_path=str(output_dir / "contained.pdf"),
                )

        class FakeNDLPlatform:
            name = "ndl"

            def download_public_pdf(self, *_args, **_kwargs):
                return None

            def build_restricted_download_requests(self, **kwargs):
                return [
                    {
                        "keyword": "山縣有朋意見書",
                        "ndl_id": kwargs["top_match"].ndl_id,
                        "output_dir": str(kwargs["output_dir"]),
                        "start_page": kwargs["start_page"],
                        "end_page": kwargs["end_page"],
                    }
                ]

        dummy_module = DummyDownloadModule()
        fake_platform = FakeNDLPlatform()
        verifier._resolve_ndlsearch_matches = lambda _candidate: None  # type: ignore[method-assign]
        verifier._get_platform_for_match = lambda _match: fake_platform  # type: ignore[method-assign]
        verifier._get_ndl_download_module = lambda: dummy_module  # type: ignore[method-assign]
        verifier._download_public_pdf = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._estimate_scan_page_range = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._probe_target_pid_fulltext_hints = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._get_ndl_total_pages_quick = lambda _ndl_id: None  # type: ignore[method-assign]

        pdf_path = verifier._obtain_source_pdf(
            candidate,
            output_dir=output_dir,
            restricted_download=True,
            page_window=4,
            download_max_attempts=1,
        )

        self.assertEqual(pdf_path, str(output_dir / "contained.pdf"))
        self.assertEqual(dummy_module.requests[0]["start_page"], 304)
        self.assertEqual(dummy_module.requests[0]["end_page"], 308)
        self.assertEqual(candidate.artifacts["downloaded_page_range"], [304, 308])
        self.assertEqual(candidate.artifacts["known_pid_page_window_fallback"]["ndl_id"], "3025431")
        self.assertNotIn("fulltext_pdf_page_fallback", candidate.artifacts)
        self.assertIn("contained_document_known_pid_page_window_fallback_used:book_pages=306", candidate.notes)

    def test_known_pid_page_window_fallback_skips_wide_distributed_pages(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p4-f2",
            paragraph_index=4,
            paragraph_text="Hara diary cites distributed pages.",
            translation_text="Hara diary cites distributed pages.",
            footnote_id="p4n2",
            footnote=ParsedFootnote(
                id="p4n2",
                text="原敬日記, pp. 51, 163, 287.",
                title="原敬日記",
                page_numbers=[51, 163, 287],
            ),
            ndl_matches=[],
            artifacts={
                "source_resolver_plan": {
                    "source_type": "diary",
                    "known_pid_candidates": ["2982137"],
                }
            },
        )
        top_match = NDLSearchMatch(
            title="原敬日記",
            url="https://dl.ndl.go.jp/pid/2982137",
            ndl_id="2982137",
            score=0.9,
            metadata={"search_route": "resolver_config_known_pid"},
        )

        plan = verifier._known_pid_page_window_fallback_plan(candidate, top_match, page_window=4)

        self.assertIsNone(plan)
        self.assertNotIn("known_pid_page_window_fallback", candidate.artifacts)
        skipped = candidate.artifacts["known_pid_page_window_fallback_skipped"]
        self.assertEqual(skipped["reason"], "distributed_pages_would_make_large_window")
        self.assertEqual(skipped["source_type"], "diary")
        self.assertEqual(skipped["page_span"], 236)
        self.assertIn(
            "known_pid_page_window_fallback_skipped[2982137]:distributed_pages_would_make_large_window",
            candidate.notes,
        )

    def test_download_dependency_missing_is_structured_when_selenium_unavailable(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p2-f8",
            paragraph_index=2,
            paragraph_text="Yamagata opinion document.",
            translation_text="Yamagata opinion document.",
            footnote_id="p2n8",
            footnote=ParsedFootnote(id="p2n8", text="山縣有朋意見書, p. 306.", title="山縣有朋意見書"),
            ndl_matches=[
                NDLSearchMatch(
                    title="山縣有朋意見書",
                    url="https://dl.ndl.go.jp/pid/3025431",
                    ndl_id="3025431",
                    score=0.9,
                )
            ],
        )

        def fail_download(*_args, **_kwargs):
            candidate.artifacts["downloaded_page_range"] = [304, 308]
            raise ModuleNotFoundError("No module named 'selenium'")

        verifier._obtain_source_pdf = fail_download  # type: ignore[method-assign]
        verifier._mark_fulltext_only_hit_if_possible = lambda *_args, **_kwargs: False  # type: ignore[method-assign]

        verifier._enrich_with_source_excerpt(
            candidate,
            output_dir=Path(tempfile.mkdtemp()),
            restricted_download=True,
            page_window=4,
            ocr_model="ndlocr_lite",
            download_max_attempts=1,
        )

        self.assertEqual(candidate.verification_status, "download_failed")
        self.assertEqual(candidate.artifacts["download_exception"]["reason"], "download_dependency_missing")
        self.assertEqual(candidate.artifacts["download_planned_page_range"], [304, 308])
        self.assertNotIn("downloaded_page_range", candidate.artifacts)
        self.assertEqual(candidate.artifacts["source_availability"]["reason"], "download_dependency_missing")
        self.assertIn("source_unavailable:download_dependency_missing[3025431]:No module named 'selenium'", candidate.notes)

    def test_restricted_download_dependency_precheck_skips_browser_request(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p2-f8",
            paragraph_index=2,
            paragraph_text="Yamagata opinion document.",
            translation_text="Yamagata opinion document.",
            footnote_id="p2n8",
            footnote=ParsedFootnote(id="p2n8", text="山縣有朋意見書, p. 306.", title="山縣有朋意見書", page_numbers=[306]),
            ndl_matches=[
                NDLSearchMatch(
                    title="山縣有朋意見書",
                    url="https://dl.ndl.go.jp/pid/3025431",
                    ndl_id="3025431",
                    score=0.9,
                    metadata={"known_pid_candidate": True},
                )
            ],
            artifacts={
                "source_resolver_plan": {
                    "source_type": "contained_document",
                    "known_pid_candidates": ["3025431"],
                }
            },
        )

        class FakeNDLPlatform:
            name = "ndl"

            def download_public_pdf(self, *_args, **_kwargs):
                return None

            def build_restricted_download_requests(self, *_args, **_kwargs):
                raise AssertionError("browser request should be skipped when dependency is missing")

        verifier._resolve_ndlsearch_matches = lambda _candidate: None  # type: ignore[method-assign]
        verifier._get_platform_for_match = lambda _match: FakeNDLPlatform()  # type: ignore[method-assign]
        verifier._download_public_pdf = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._estimate_scan_page_range = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._fulltext_pdf_page_fallback_plan = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._get_ndl_total_pages_quick = lambda _ndl_id: 500  # type: ignore[method-assign]
        verifier._restricted_download_dependency_status = lambda _module=None: {  # type: ignore[method-assign]
            "available": False,
            "reason": "download_dependency_missing",
            "dependency": "selenium",
            "message": "No module named 'selenium'",
        }

        pdf_path = verifier._obtain_source_pdf(
            candidate,
            output_dir=output_dir,
            restricted_download=True,
            page_window=4,
            download_max_attempts=1,
        )

        self.assertIsNone(pdf_path)
        self.assertEqual(candidate.artifacts["download_dependency_check"]["reason"], "download_dependency_missing")
        self.assertEqual(candidate.artifacts["download_planned_page_range"], [304, 308])
        self.assertNotIn("downloaded_page_range", candidate.artifacts)
        self.assertEqual(candidate.artifacts["source_availability"]["reason"], "download_dependency_missing")
        self.assertIn("restricted_download_dependency_missing:selenium", candidate.notes)

    def test_known_pid_page_window_out_of_scan_range_requires_page_mapping(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p4-f1",
            paragraph_index=4,
            paragraph_text="Hara diary citation without date.",
            translation_text="Hara diary citation without date.",
            footnote_id="p4n1",
            footnote=ParsedFootnote(
                id="p4n1",
                text="原敬日記 第2巻, p. 325.",
                title="原敬日記",
                page_numbers=[325],
            ),
            ndl_matches=[
                NDLSearchMatch(
                    title="原敬日記",
                    url="https://dl.ndl.go.jp/pid/2982135",
                    ndl_id="2982135",
                    score=0.9,
                    metadata={"known_pid_candidate": True},
                )
            ],
            artifacts={
                "source_resolver_plan": {
                    "source_type": "diary",
                    "known_pid_candidates": ["2982135"],
                }
            },
        )

        class FakeNDLPlatform:
            name = "ndl"

            def download_public_pdf(self, *_args, **_kwargs):
                return None

        verifier._resolve_ndlsearch_matches = lambda _candidate: None  # type: ignore[method-assign]
        verifier._get_platform_for_match = lambda _match: FakeNDLPlatform()  # type: ignore[method-assign]
        verifier._get_ndl_download_module = lambda: None  # type: ignore[method-assign]
        verifier._download_public_pdf = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._estimate_scan_page_range = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._fulltext_pdf_page_fallback_plan = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._get_ndl_total_pages_quick = lambda _ndl_id: 219  # type: ignore[method-assign]

        pdf_path = verifier._obtain_source_pdf(
            candidate,
            output_dir=output_dir,
            restricted_download=True,
            page_window=4,
            download_max_attempts=1,
        )

        self.assertIsNone(pdf_path)
        self.assertTrue(candidate.artifacts["page_mapping_required_but_unavailable"])
        self.assertEqual(
            candidate.artifacts["known_pid_page_window_requires_page_mapping"]["reason"],
            "book_page_scan_page_assumption_out_of_range",
        )
        self.assertEqual(candidate.artifacts["source_availability"]["reason"], "mapped_page_out_of_scan_range")
        self.assertIn("known_pid_page_window_requires_page_mapping[2982135]", candidate.notes)

    def test_diary_date_queries_add_japanese_era_year_variants(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p4-fp4n1",
            paragraph_index=4,
            paragraph_text="In 1908 Hara discussed America.",
            translation_text="In 1908 Hara discussed America.",
            footnote_id="p4n1",
            footnote=ParsedFootnote(
                id="p4n1",
                text="Hara diary volume 2, 1981 reprint, p. 325.",
                title="\u539f\u656c\u65e5\u8a18",
                year="1981",
                page_numbers=[325],
            ),
            artifacts={
                "source_resolver_plan": {
                    "source_type": "diary",
                    "dates": ["1908\u5e74"],
                    "target_pid_queries": ["1908\u5e74", "\u539f\u656c\u65e5\u8a18"],
                    "query_buckets": {"date": ["1908\u5e74"]},
                }
            },
        )

        queries = verifier._diary_date_queries(candidate)

        self.assertIn("1908\u5e74", queries)
        self.assertIn("\u660e\u6cbb41\u5e74", queries)
        self.assertIn("\u660e\u6cbb\u56db\u5341\u4e00\u5e74", queries)
        self.assertNotIn("1981\u5e74", queries)

    def test_diary_target_pid_probe_filters_publication_year_keywords(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p4-fp4n1",
            paragraph_index=4,
            paragraph_text="In 1908 Hara discussed America.",
            translation_text="In 1908 Hara discussed America.",
            footnote_id="p4n1",
            footnote=ParsedFootnote(
                id="p4n1",
                text="Hara diary volume 2, 1981 reprint, p. 325.",
                title="\u539f\u656c\u65e5\u8a18",
                year="1981",
                page_numbers=[325],
            ),
            artifacts={
                "source_resolver_plan": {
                    "source_type": "diary",
                    "known_pid_candidates": ["2982135"],
                    "dates": ["1908\u5e74"],
                    "target_pid_queries": ["1908\u5e74", "\u539f\u656c\u65e5\u8a18"],
                    "query_buckets": {"date": ["1908\u5e74"]},
                }
            },
        )
        match = NDLSearchMatch(
            title="\u539f\u656c\u65e5\u8a18",
            url="https://dl.ndl.go.jp/pid/2982135",
            ndl_id="2982135",
            platform="ndl",
        )
        captured = {}

        class Probe:
            pid = "2982135"
            title = "\u539f\u656c\u65e5\u8a18"
            status = "no_direct_hit"
            hits = []
            queries_tried = []
            note = ""

        def fake_probe(pid, keywords):
            captured["pid"] = pid
            captured["keywords"] = list(keywords)
            return Probe()

        with patch("modules.historical_citation_verifier.probe_ndl_fulltext_context", fake_probe):
            verifier._probe_target_pid_fulltext_hints(candidate, match)

        self.assertEqual(captured["pid"], "2982135")
        self.assertIn("\u660e\u6cbb41\u5e74", captured["keywords"])
        self.assertIn("\u660e\u6cbb\u56db\u5341\u4e00\u5e74", captured["keywords"])
        self.assertFalse(any("1981" in keyword for keyword in captured["keywords"]))

    def test_diary_claim_queries_add_us_economy_future_terms(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p4-fp4n1",
            paragraph_index=4,
            paragraph_text="1908\u5e74\uff0c\u7f8e\u56fd\u786e\u662f\u6781\u6709\u6d3b\u529b\u7684\u56fd\u5bb6\u3002",
            translation_text="\u7f8e\u56fd\u53d7\u5230\u7ecf\u6d4e\u4e0d\u666f\u6c14\u5f71\u54cd\uff0c\u4f46\u5c06\u6765\u4f1a\u5bf9\u4e16\u754c\u4ea7\u751f\u5f71\u54cd\u3002",
            footnote_id="p4n1",
            footnote=ParsedFootnote(
                id="p4n1",
                text="Hara diary volume 2, 1981 reprint, p. 325.",
                title="\u539f\u656c\u65e5\u8a18",
                year="1981",
                page_numbers=[325],
            ),
            artifacts={
                "source_resolver_plan": {
                    "source_type": "diary",
                    "dates": ["1908\u5e74"],
                    "query_buckets": {"date": ["1908\u5e74"]},
                }
            },
        )

        queries = verifier._diary_claim_fulltext_queries(candidate)

        self.assertTrue(any("\u660e\u6cbb\u56db\u5341\u4e00\u5e74" in query for query in queries))
        self.assertTrue(any("\u7c73\u570b" in query or "\u7c73\u56fd" in query for query in queries))
        self.assertTrue(any("\u4e0d\u666f\u6c23" in query or "\u4e0d\u666f\u6c17" in query for query in queries))
        self.assertTrue(any("\u5c07\u4f86" in query or "\u5c06\u6765" in query for query in queries))
        self.assertFalse(any("1981" in query for query in queries))

    def test_diary_claim_facets_can_be_loaded_from_resolver_config(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p7-f1",
            paragraph_index=7,
            paragraph_text="China policy discussions shaped the diary entry.",
            translation_text="\u4e2d\u56fd\u653f\u7b56\u5f71\u54cd\u4e86\u539f\u656c\u7684\u5224\u65ad\u3002",
            footnote_id="p7n1",
            footnote=ParsedFootnote(
                id="p7n1",
                text="\u300e\u539f\u656c\u65e5\u8a18\u300f\u7b2c2\u5dfb\u3002",
                title="\u539f\u656c\u65e5\u8a18",
                page_numbers=[120],
            ),
            artifacts={
                "source_resolver_plan": {
                    "source_type": "diary",
                    "dates": ["1908\u5e74"],
                    "query_buckets": {"date": ["1908\u5e74"]},
                }
            },
        )
        fake_config = {
            "hara_takashi_diary": {
                "claim_facets": [
                    {
                        "id": "china",
                        "role": "anchor",
                        "trigger_terms": ["\u4e2d\u56fd", "China"],
                        "terms": ["\u6e05\u570b", "\u652f\u90a3"],
                    },
                    {
                        "id": "policy",
                        "role": "theme",
                        "trigger_terms": ["\u653f\u7b56", "policy"],
                        "terms": ["\u653f\u7b56", "\u5916\u4ea4"],
                    },
                    {
                        "id": "influence",
                        "role": "theme",
                        "trigger_terms": ["\u5f71\u54cd", "influence"],
                        "terms": ["\u5f71\u97ff"],
                    },
                ]
            }
        }

        with patch("modules.historical_citation_verifier._load_resolver_config", return_value=fake_config):
            buckets = verifier._diary_claim_term_buckets(candidate)
            queries = verifier._diary_claim_fulltext_queries(candidate)
            packet = verifier._diary_claim_facet_packet(
                candidate,
                "\u660e\u6cbb\u56db\u5341\u4e00\u5e74 \u6e05\u570b\u306b\u5c0d\u3059\u308b\u653f\u7b56\u306f\u5927\u304d\u306a\u5f71\u97ff",
            )

        self.assertEqual(set(buckets), {"china", "policy", "influence"})
        self.assertTrue(any("\u6e05\u570b \u653f\u7b56" in query for query in queries))
        self.assertIn("china", packet["covered_facets"])
        self.assertIn("policy", packet["covered_facets"])
        self.assertIn("influence", packet["covered_facets"])
        self.assertGreaterEqual(packet["score_bonus"], 3.0)

    def test_diary_claim_facets_ignore_broad_paragraph_background(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p4-fp4n1",
            paragraph_index=4,
            paragraph_text=(
                "\u5916\u4ea4\u653f\u7b56\u3001\u82f1\u56fd\u3001\u4fc4\u56fd\u3001\u5185\u9601\u306e\u80cc\u666f\u8aac\u660e\u3002"
                "\u7f8e\u56fd\u306f\u7d4c\u6e08\u4e0d\u666f\u6c17\u306e\u5f71\u97ff\u3092\u53d7\u3051\u305f\u304c\u3001\u5c06\u6765\u306e\u5f71\u97ff\u304c\u5927\u304d\u3044\u3002"
            ),
            translation_text=(
                "\u7f8e\u56fd\u306f\u7d4c\u6e08\u4e0d\u666f\u6c14\u306e\u5f71\u54cd\u3092\u53d7\u3051\u305f\u304c\u3001"
                "\u5c06\u6765\u306e\u4e16\u754c\u3078\u306e\u5f71\u54cd\u304c\u5927\u304d\u3044\u3002"
            ),
            footnote_id="p4n1",
            footnote=ParsedFootnote(
                id="p4n1",
                text="\u300e\u539f\u656c\u65e5\u8a18\u300f\u7b2c2\u5dfb\u3002",
                title="\u539f\u656c\u65e5\u8a18",
                page_numbers=[325],
            ),
            artifacts={"source_resolver_plan": {"source_type": "diary", "dates": ["1908\u5e74"]}},
        )

        buckets = verifier._diary_claim_term_buckets(candidate)

        self.assertIn("us", buckets)
        self.assertIn("economy", buckets)
        self.assertIn("future_influence", buckets)
        self.assertNotIn("russia", buckets)
        self.assertNotIn("britain", buckets)
        self.assertNotIn("diplomacy_policy", buckets)
        self.assertEqual(candidate.artifacts["diary_claim_facet_trigger_scope"], "translation_text")

    def test_diary_claim_facets_prioritize_claim_hint_over_date_only(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p4-fp4n1",
            paragraph_index=4,
            paragraph_text="1908\u5e74\uff0c\u7f8e\u56fd\u786e\u662f\u6781\u6709\u6d3b\u529b\u7684\u56fd\u5bb6\u3002",
            translation_text="\u7f8e\u56fd\u53d7\u5230\u7ecf\u6d4e\u4e0d\u666f\u6c14\u5f71\u54cd\uff0c\u4f46\u5c06\u6765\u4f1a\u5bf9\u4e16\u754c\u4ea7\u751f\u5f71\u54cd\u3002",
            footnote_id="p4n1",
            footnote=ParsedFootnote(
                id="p4n1",
                text="Hara diary volume 2, 1981 reprint, p. 325.",
                title="\u539f\u656c\u65e5\u8a18",
                year="1981",
                page_numbers=[325],
            ),
            artifacts={
                "source_resolver_plan": {
                    "source_type": "diary",
                    "dates": ["1908\u5e74"],
                    "query_buckets": {"date": ["1908\u5e74"]},
                },
                "ndl_fulltext_hints": [
                    {
                        "query": "\u660e\u6cbb\u56db\u5341\u4e00\u5e74",
                        "snippet": "\u660e\u6cbb\u56db\u5341\u4e00\u5e74 \u4e00\u6708\u5341\u56db\u65e5 \u5185\u52d9\u5927\u81e3\u539f\u656c",
                        "pdf_page": 148,
                        "pid": "2982135",
                        "book_id": "2982135",
                    },
                    {
                        "query": "\u660e\u6cbb\u56db\u5341\u4e00\u5e74 \u7c73\u570b \u5c07\u4f86",
                        "snippet": "\u7c73\u570b\u8cc7\u672c\u5bb6\u3001\u4e0d\u666f\u6c23\u3001\u5c07\u4f86\u65e5\u672c\u306b\u6295\u8cc7\u3059\u308b\u3053\u3068\u306b\u5927\u5f71\u97ff\u3042\u308b",
                        "expanded_context": "\u7c73\u570b\u8cc7\u672c\u5bb6\u306e\u4e0d\u666f\u6c23\u3068\u5c07\u4f86\u65e5\u672c\u306b\u6295\u8cc7\u3059\u308b\u3053\u3068\u306b\u5927\u5f71\u97ff\u3042\u308b\u3079\u3057",
                        "pdf_page": 30,
                        "pid": "2982135",
                        "book_id": "2982135",
                    },
                ],
            },
        )

        selected = verifier._select_fulltext_hints_to_expand(
            candidate,
            verifier._ordered_fulltext_hints_for_candidate(candidate, preferred_pid="2982135"),
            limit=2,
        )
        score, reasons = verifier._score_fulltext_context_candidate(
            candidate,
            selected[0],
            selected[0].get("expanded_context") or selected[0].get("snippet") or "",
        )

        self.assertEqual(selected[0]["pdf_page"], 30)
        self.assertGreater(score, 4.0)
        self.assertTrue(any(reason.startswith("diary_claim_facets=") for reason in reasons))

    def test_diary_date_pdf_page_route_prefers_claim_facets(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p4-fp4n1",
            paragraph_index=4,
            paragraph_text="1908\u5e74\uff0c\u7f8e\u56fd\u786e\u662f\u6781\u6709\u6d3b\u529b\u7684\u56fd\u5bb6\u3002",
            translation_text="\u7f8e\u56fd\u53d7\u5230\u7ecf\u6d4e\u4e0d\u666f\u6c14\u5f71\u54cd\uff0c\u4f46\u5c06\u6765\u4f1a\u5bf9\u4e16\u754c\u4ea7\u751f\u5f71\u54cd\u3002",
            footnote_id="p4n1",
            footnote=ParsedFootnote(
                id="p4n1",
                text="Hara diary volume 2, 1981 reprint, p. 325.",
                title="\u539f\u656c\u65e5\u8a18",
                year="1981",
                page_numbers=[325],
            ),
            artifacts={
                "source_resolver_plan": {
                    "source_type": "diary",
                    "dates": ["1908\u5e74"],
                    "query_buckets": {"date": ["1908\u5e74"]},
                }
            },
        )
        match = NDLSearchMatch(
            title="\u539f\u656c\u65e5\u8a18",
            url="https://dl.ndl.go.jp/pid/2982135",
            ndl_id="2982135",
            platform="ndl",
            metadata={
                "fulltext_hints": [
                    {
                        "query": "\u660e\u6cbb41\u5e74 \u7c73\u56fd \u4e0d\u666f\u6c17",
                        "snippet": "\u7c73\u570b\u306b\u884c\u304f\u306a\u3089\u3070\u6b50\u6d32\u307e\u3067\u8d74\u304d\u3066\u306f\u5982\u4f55",
                        "pdf_page": 16,
                        "cid": "cid-16",
                        "book_id": "2982135",
                    },
                    {
                        "query": "\u660e\u6cbb41\u5e74 \u7c73\u56fd \u5c06\u6765",
                        "snippet": "\u7c73\u570b\u8cc7\u672c\u5bb6\u306f\u5c07\u4f86\u65e5\u672c\u306b\u6295\u8cc7\u3059\u308b\u3053\u3068\u306b\u5927\u5f71\u97ff\u3042\u308b",
                        "pdf_page": 30,
                        "cid": "cid-30",
                        "book_id": "2982135",
                    },
                ]
            },
        )
        verifier._probe_target_pid_fulltext_hints = lambda *_args, **_kwargs: None  # type: ignore[method-assign]

        plan = verifier._diary_date_pdf_page_fallback_plan(candidate, match, page_window=4)

        self.assertIsNotNone(plan)
        self.assertEqual(plan["mapped_footnote_pages"], [30])
        self.assertEqual(candidate.artifacts["diary_date_pdf_page_fallback"]["selected_pdf_page"], 30)
        top = candidate.artifacts["diary_date_pdf_page_fallback"]["top_candidates"][0]
        self.assertIn("future_influence", top["claim_facets"])
        self.assertEqual(top["pdf_page"], 30)

    def test_diary_date_pdf_page_hint_routes_before_book_page_window(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p4-fp4n1",
            paragraph_index=4,
            paragraph_text="In 1908 Hara thought America was energetic.",
            translation_text="America was energetic.",
            footnote_id="p4n1",
            footnote=ParsedFootnote(
                id="p4n1",
                text="Hara diary volume 2, 1981 reprint, p. 325.",
                title="\u539f\u656c\u65e5\u8a18",
                year="1981",
                page_numbers=[325],
            ),
            ndl_matches=[
                NDLSearchMatch(
                    title="\u539f\u656c\u65e5\u8a18",
                    url="https://dl.ndl.go.jp/pid/2982135",
                    ndl_id="2982135",
                    platform="ndl",
                    score=0.9,
                    metadata={
                        "known_pid_candidate": True,
                        "fulltext_hints": [
                            {
                                "query": "\u660e\u6cbb\u56db\u5341\u4e00\u5e74",
                                "snippet": "\u660e\u6cbb\u56db\u5341\u4e00\u5e74 \u539f\u656c\u65e5\u8a18",
                                "expanded_context": "\u660e\u6cbb\u56db\u5341\u4e00\u5e74 \u7c73\u56fd",
                                "pdf_page": 120,
                                "cid": "cid-120",
                                "book_id": "2982135",
                            }
                        ],
                    },
                )
            ],
            artifacts={
                "source_resolver_plan": {
                    "source_type": "diary",
                    "known_pid_candidates": ["2982135"],
                    "dates": ["1908\u5e74"],
                    "target_pid_queries": ["1908\u5e74", "\u539f\u656c\u65e5\u8a18"],
                    "query_buckets": {"date": ["1908\u5e74"]},
                }
            },
        )

        class DummyDownloadModule:
            def __init__(self):
                self.requests = []

            def download_first_match(self, **kwargs):
                self.requests.append(kwargs)
                return NDLDownloadOutcome(
                    success=True,
                    mode="restricted",
                    status="success",
                    keyword=kwargs["keyword"],
                    output_dir=str(output_dir),
                    file_path=str(output_dir / "diary.pdf"),
                )

        class FakeNDLPlatform:
            name = "ndl"

            def download_public_pdf(self, *_args, **_kwargs):
                return None

            def build_restricted_download_requests(self, **kwargs):
                return [
                    {
                        "keyword": "diary",
                        "ndl_id": kwargs["top_match"].ndl_id,
                        "output_dir": str(kwargs["output_dir"]),
                        "start_page": kwargs["start_page"],
                        "end_page": kwargs["end_page"],
                    }
                ]

        dummy_module = DummyDownloadModule()
        fake_platform = FakeNDLPlatform()
        verifier._resolve_ndlsearch_matches = lambda _candidate: None  # type: ignore[method-assign]
        verifier._get_platform_for_match = lambda _match: fake_platform  # type: ignore[method-assign]
        verifier._get_ndl_download_module = lambda: dummy_module  # type: ignore[method-assign]
        verifier._download_public_pdf = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._probe_target_pid_fulltext_hints = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._estimate_scan_page_range = lambda *_args, **_kwargs: (_ for _ in ()).throw(  # type: ignore[method-assign]
            AssertionError("date route should run before OCR page mapping")
        )
        verifier._get_ndl_total_pages_quick = lambda _ndl_id: 219  # type: ignore[method-assign]

        pdf_path = verifier._obtain_source_pdf(
            candidate,
            output_dir=output_dir,
            restricted_download=True,
            page_window=4,
            download_max_attempts=1,
        )

        self.assertEqual(pdf_path, str(output_dir / "diary.pdf"))
        self.assertEqual(dummy_module.requests[0]["start_page"], 116)
        self.assertEqual(dummy_module.requests[0]["end_page"], 124)
        self.assertEqual(candidate.artifacts["mapped_footnote_pages"], [120])
        self.assertEqual(candidate.artifacts["downloaded_page_range"], [116, 124])
        self.assertEqual(candidate.artifacts["diary_date_pdf_page_fallback"]["selected_pdf_page"], 120)
        self.assertNotIn("known_pid_page_window_requires_page_mapping", candidate.artifacts)
        self.assertIn("diary_date_pdf_page_fallback_used:pdf_page=120", candidate.notes)

    def test_verifier_uses_ndl_fulltext_pdf_page_hint_when_page_mapping_missing(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="source", title="source", page_numbers=[216]),
            ndl_matches=[
                NDLSearchMatch(
                    title="source",
                    url="https://dl.ndl.go.jp/pid/12345678",
                    ndl_id="12345678",
                    score=0.9,
                    metadata={
                        "fulltext_hints": [
                            {
                                "query": "source",
                                "snippet": "source snippet",
                                "pdf_page": 10,
                                "cid": "cid-10",
                                "book_id": "12345678",
                            }
                        ]
                    },
                ),
            ],
        )

        class DummyDownloadModule:
            def __init__(self):
                self.requests = []

            def download_first_match(self, **kwargs):
                self.requests.append(kwargs)
                return NDLDownloadOutcome(
                    success=True,
                    mode="restricted",
                    status="success",
                    keyword=kwargs["keyword"],
                    output_dir=str(output_dir),
                    file_path=str(output_dir / "ok.pdf"),
                )

        class FakeNDLPlatform:
            name = "ndl"

            def download_public_pdf(self, *_args, **_kwargs):
                return None

            def build_restricted_download_requests(self, **kwargs):
                return [
                    {
                        "keyword": "source",
                        "ndl_id": kwargs["top_match"].ndl_id,
                        "output_dir": str(kwargs["output_dir"]),
                        "start_page": kwargs["start_page"],
                        "end_page": kwargs["end_page"],
                    }
                ]

        dummy_module = DummyDownloadModule()
        fake_platform = FakeNDLPlatform()
        verifier._resolve_ndlsearch_matches = lambda _candidate: None  # type: ignore[method-assign]
        verifier._get_platform_for_match = lambda _match: fake_platform  # type: ignore[method-assign]
        verifier._get_ndl_download_module = lambda: dummy_module  # type: ignore[method-assign]
        verifier._estimate_scan_page_range = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._get_ndl_total_pages_quick = lambda _ndl_id: None  # type: ignore[method-assign]

        pdf_path = verifier._obtain_source_pdf(
            candidate,
            output_dir=output_dir,
            restricted_download=True,
            page_window=2,
            download_max_attempts=1,
        )

        self.assertEqual(pdf_path, str(output_dir / "ok.pdf"))
        self.assertEqual(dummy_module.requests[0]["start_page"], 8)
        self.assertEqual(dummy_module.requests[0]["end_page"], 12)
        self.assertEqual(candidate.artifacts["downloaded_page_range"], [8, 12])
        self.assertEqual(candidate.artifacts["mapped_footnote_pages"], [10])
        self.assertEqual(candidate.artifacts["fulltext_pdf_page_fallback"]["pdf_page"], 10)
        self.assertFalse(candidate.artifacts.get("page_mapping_required_but_unavailable"))
        self.assertIn("fulltext_pdf_page_fallback_used:pdf_page=10", candidate.notes)

    def test_verifier_does_not_downgrade_page_mapping_block_to_no_pid(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="source", title="source", page_numbers=[41]),
        )
        candidate.artifacts["page_mapping_required_but_unavailable"] = True
        candidate.artifacts["page_mapping_unavailable_ndl_ids"] = ["12345678"]

        verifier._mark_source_unavailable(
            candidate,
            reason="no_digital_pid",
            detail="metadata-only candidate",
        )

        self.assertNotIn("source_availability", candidate.artifacts)
        self.assertFalse(any(note.startswith("source_unavailable:no_digital_pid") for note in candidate.notes))

    def test_verifier_rejects_download_when_ndl_adjusts_requested_page_range(self):
        output_dir = Path(tempfile.mkdtemp())
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="source", title="source", page_numbers=[209]),
            ndl_matches=[
                NDLSearchMatch(title="source", url="https://dl.ndl.go.jp/pid/3019147", ndl_id="3019147", score=0.9),
            ],
        )

        class DummyDownloadModule:
            def download_first_match(self, **kwargs):
                return NDLDownloadOutcome(
                    success=True,
                    mode="restricted",
                    status="success",
                    keyword=kwargs["keyword"],
                    output_dir=str(output_dir),
                    file_path=str(output_dir / "wrong_tail.pdf"),
                    metadata={
                        "requested_start_page": 109,
                        "requested_end_page": 113,
                        "actual_start_page": 101,
                        "actual_end_page": 105,
                        "range_adjusted": True,
                    },
                )

        verifier._get_ndl_download_module = lambda: DummyDownloadModule()  # type: ignore[method-assign]
        verifier._download_public_pdf = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._estimate_scan_page_range = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
            "anchor_scan_page": 12,
            "anchor_book_page": 10,
            "pages_per_scan": 2,
            "start_scan_page": 109,
            "end_scan_page": 113,
        }
        verifier._get_ndl_total_pages_quick = lambda _ndl_id: None  # type: ignore[method-assign]

        pdf_path = verifier._obtain_source_pdf(
            candidate,
            output_dir=output_dir,
            restricted_download=True,
            page_window=4,
            download_max_attempts=1,
        )

        self.assertIsNone(pdf_path)
        self.assertTrue(candidate.artifacts["page_mapping_required_but_unavailable"])
        self.assertEqual(candidate.artifacts["downloaded_page_range_requested"], [109, 113])
        self.assertEqual(candidate.artifacts["downloaded_page_range_actual"], [101, 105])
        self.assertIn("source_pdf_rejected_adjusted_range", candidate.notes)
        self.assertNotIn("selected_source_match", candidate.artifacts)

    def test_verifier_rejects_mapped_page_beyond_ndl_scan_total_before_cache_or_download(self):
        output_dir = Path(tempfile.mkdtemp())
        cached_pdf = output_dir / "ndl_3019147_p109-p113.pdf"
        cached_pdf.write_bytes(b"%PDF-1.7\n%%EOF")
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="source", title="source", page_numbers=[209]),
            ndl_matches=[
                NDLSearchMatch(title="source", url="https://dl.ndl.go.jp/pid/3019147", ndl_id="3019147", score=0.9),
            ],
        )

        class DummyDownloadModule:
            def download_first_match(self, **_kwargs):
                raise AssertionError("download should not run when mapped page exceeds scan total")

        verifier._get_ndl_download_module = lambda: DummyDownloadModule()  # type: ignore[method-assign]
        verifier._download_public_pdf = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        verifier._estimate_scan_page_range = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
            "anchor_scan_page": 12,
            "anchor_book_page": 10,
            "pages_per_scan": 2,
            "start_scan_page": 109,
            "end_scan_page": 113,
        }
        verifier._get_ndl_total_pages_quick = lambda _ndl_id: 105  # type: ignore[method-assign]
        verifier._is_usable_pdf = lambda path: Path(path).exists()  # type: ignore[method-assign]

        pdf_path = verifier._obtain_source_pdf(
            candidate,
            output_dir=output_dir,
            restricted_download=True,
            page_window=4,
            download_max_attempts=1,
        )

        self.assertIsNone(pdf_path)
        self.assertTrue(candidate.artifacts["page_mapping_required_but_unavailable"])
        self.assertIn("3019147", candidate.artifacts["page_mapping_unavailable_ndl_ids"])
        self.assertTrue(any(note.startswith("mapped_footnote_page_out_of_scan_range[3019147]") for note in candidate.notes))
        self.assertNotIn("source_pdf_cached_range_reused:3019147:p109-p113", candidate.notes)

    def test_source_acquisition_module_builds_mapped_and_plain_page_plans(self):
        mapped_plan = build_download_page_plan(
            [41],
            page_window=4,
            page_mapping={
                "anchor_scan_page": 15,
                "anchor_book_page": 3,
                "start_scan_page": 32,
                "end_scan_page": 36,
            },
        )
        plain_plan = build_download_page_plan([41], page_window=4)

        self.assertEqual(mapped_plan["start_page"], 32)
        self.assertEqual(mapped_plan["end_page"], 36)
        self.assertEqual(mapped_plan["mapped_footnote_pages"], [34])
        self.assertEqual(plain_plan["start_page"], 37)
        self.assertEqual(plain_plan["end_page"], 45)

    def test_verifier_finds_cached_range_pdf_superset(self):
        output_dir = Path(tempfile.mkdtemp())
        cached_pdf = output_dir / "ndl_12345678_p10-p20.pdf"
        cached_pdf.write_bytes(b"%PDF-1.7\n%%EOF")
        verifier = HistoricalCitationVerifier()
        verifier._is_usable_pdf = lambda path: Path(path).exists()  # type: ignore[method-assign]

        found = verifier._find_cached_range_pdf(
            output_dir,
            ndl_id="12345678",
            start_page=12,
            end_page=18,
        )

        self.assertIsNotNone(found)
        self.assertEqual(found[0], cached_pdf)
        self.assertEqual(found[1:], (10, 20))

    def test_download_index_persists_ndl_range_records(self):
        output_dir = Path(tempfile.mkdtemp())
        cached_pdf = output_dir / "ndl_99999999_p5-p9.pdf"
        cached_pdf.write_bytes(b"%PDF-1.7\n%%EOF")

        index = refresh_download_range_index(output_dir)
        found = find_cached_range_pdf_from_index(
            output_dir,
            ndl_id="99999999",
            start_page=6,
            end_page=8,
            is_usable_pdf=lambda path: Path(path).exists(),
        )

        self.assertEqual(index["records"][0]["ndl_id"], "99999999")
        self.assertTrue((output_dir / "download_range_index.json").exists())
        self.assertEqual(found[0], cached_pdf)

    def test_source_acquisition_module_builds_restricted_requests_and_downloads_public_pdf(self):
        output_dir = Path(tempfile.mkdtemp())
        match = NDLSearchMatch(
            title="架空史料集",
            url="https://dl.ndl.go.jp/pid/99999999",
            ndl_id="99999999",
        )

        requests_payload = build_restricted_download_requests(
            keywords=["架空史料集 佐藤一郎"],
            top_match=match,
            fallback_title="fallback",
            output_dir=output_dir,
            start_page=32,
            end_page=36,
        )
        pdf_path = download_public_pdf(
            match,
            output_dir=output_dir,
            request_get=lambda *_args, **_kwargs: DummyResponse(
                "",
                headers={"content-type": "application/pdf"},
                chunks=[b"%PDF-1.7\n", b"%%EOF"],
            ),
        )

        self.assertEqual(requests_payload[0]["ndl_id"], "99999999")
        self.assertEqual(requests_payload[0]["filename"], "ndl_99999999_p32-p36.pdf")
        self.assertEqual(requests_payload[0]["start_page"], 32)
        self.assertEqual(requests_payload[0]["end_page"], 36)
        self.assertTrue(Path(pdf_path).exists())

    def test_ndl_download_module_marks_browser_recoverable_errors(self):
        module = NDLDownloadModule()

        self.assertTrue(module._is_browser_recoverable_error("download_link_not_found"))
        self.assertTrue(module._is_browser_recoverable_error("lambda_http_403: forbidden"))
        self.assertFalse(module._is_browser_recoverable_error("title_mismatch"))

    def test_ndl_download_module_rejects_html_saved_as_pdf(self):
        output_dir = Path(tempfile.mkdtemp())
        bad_pdf = output_dir / "bad.pdf"
        bad_pdf.write_bytes(b"<!DOCTYPE html><title>404</title>")
        module = NDLDownloadModule()
        outcome = NDLDownloadOutcome(
            success=True,
            mode="restricted",
            status="success",
            keyword="synthetic",
            output_dir=str(output_dir),
            file_path=str(bad_pdf),
        )

        validated = module._validated_outcome(outcome)

        self.assertFalse(validated.success)
        self.assertEqual(validated.status, "invalid_pdf")
        self.assertIn("pdf_magic_mismatch", validated.error_message)
        self.assertFalse(bad_pdf.exists())

    def test_ndl_download_module_fast_fails_missing_toc_before_browser(self):
        output_dir = Path(tempfile.mkdtemp())
        module = NDLDownloadModule()
        request = NDLDownloadRequest(
            keyword="synthetic",
            output_dir=output_dir,
            ndl_id="22678830",
            restricted=True,
            start_page=1,
            end_page=1,
        )

        with patch("modules.workflows.ndl_download.requests.get", return_value=DummyResponse("", status_code=404)):
            with patch.object(module, "_browser_client_class", side_effect=AssertionError("browser should not open")):
                outcome = module.download(request)

        self.assertFalse(outcome.success)
        self.assertEqual(outcome.status, "not_found")
        self.assertEqual(outcome.error_message, "ndl_toc_not_found:22678830")

    def test_ndl_download_module_fast_fails_empty_toc_before_browser(self):
        output_dir = Path(tempfile.mkdtemp())
        module = NDLDownloadModule()
        request = NDLDownloadRequest(
            keyword="synthetic",
            output_dir=output_dir,
            ndl_id="13007334",
            restricted=True,
            start_page=1,
            end_page=1,
        )

        with patch(
            "modules.workflows.ndl_download.requests.get",
            return_value=DummyResponse('{"contentsBundles":[]}', status_code=200),
        ):
            with patch.object(module, "_browser_client_class", side_effect=AssertionError("browser should not open")):
                outcome = module.download(request)

        self.assertFalse(outcome.success)
        self.assertEqual(outcome.status, "not_found")
        self.assertEqual(outcome.error_message, "ndl_toc_empty:13007334")

    def test_ndlocr_lite_build_command_uses_absolute_paths(self):
        output_dir = Path(tempfile.mkdtemp())
        image_path = output_dir / "page.png"
        image_path.write_bytes(b"synthetic")
        processor = NDLOCRLiteProcessor(NDLOCRLiteConfig(ndlocr_path="ndlocr-lite/src/ocr.py"))

        command = processor._build_command(str(image_path), str(output_dir / "ocr"))

        self.assertTrue(Path(command[command.index("--sourceimg") + 1]).is_absolute())
        self.assertTrue(Path(command[command.index("--output") + 1]).is_absolute())

    def test_ndl_browser_client_finds_download_link_after_scrolling_top(self):
        if importlib.util.find_spec("selenium") is None:
            self.skipTest("selenium unavailable")

        browser_module = self._load_browser_module_or_skip()
        client = browser_module.NDLBrowserClient(headless=True, output_dir=str(Path(tempfile.mkdtemp())))
        client.driver = DummyBrowserDriver(
            links=[
                DummyLink(
                    "https://d111.cloudfront.net/download/file.pdf?Key-Pair-Id=abc",
                    "PDFファイルを開く",
                )
            ]
        )

        self.assertTrue(client._is_download_href("https://x/download/file.pdf", "PDFファイルを開く"))
        found = client._find_download_url_on_page()

        self.assertIn("Key-Pair-Id", found)
        self.assertTrue(any("scrollTo" in script for script in client.driver.scripts))

    def test_ndl_browser_client_falls_back_to_html_presigned_link(self):
        if importlib.util.find_spec("selenium") is None:
            self.skipTest("selenium unavailable")

        browser_module = self._load_browser_module_or_skip()
        client = browser_module.NDLBrowserClient(headless=True, output_dir=str(Path(tempfile.mkdtemp())))
        client.driver = DummyBrowserDriver(
            links=[],
            page_source='href="https://example.cloudfront.net/download/out.pdf?Key-Pair-Id=abc&amp;Signature=def"',
        )

        found = client._find_download_url_on_page()

        self.assertEqual(found, "https://example.cloudfront.net/download/out.pdf?Key-Pair-Id=abc&Signature=def")

    def test_ndl_browser_client_finds_print_button_from_id_or_text(self):
        if importlib.util.find_spec("selenium") is None:
            self.skipTest("selenium unavailable")

        browser_module = self._load_browser_module_or_skip()
        client = browser_module.NDLBrowserClient(headless=True, output_dir=str(Path(tempfile.mkdtemp())))
        print_button = DummyClickableElement("印刷", attrs={"id": "open-printing-modal"})
        remote_copy_link = DummyClickableElement(
            "国立国会図書館サーチから遠隔複写（PDFダウンロード）を申し込むには",
            attrs={"href": "https://ndlsearch.ndl.go.jp/help/pdfdownload"},
        )
        client.driver = DummyBrowserDriver(links=[remote_copy_link, print_button])

        found = client._find_print_button()

        self.assertIs(found, print_button)

    def test_ndl_browser_client_detects_remote_copy_only_page(self):
        if importlib.util.find_spec("selenium") is None:
            self.skipTest("selenium unavailable")

        browser_module = self._load_browser_module_or_skip()
        client = browser_module.NDLBrowserClient(headless=True, output_dir=str(Path(tempfile.mkdtemp())))
        client.driver = DummyBrowserDriver(
            links=[
                DummyClickableElement(
                    "国立国会図書館サーチから遠隔複写（PDFダウンロード）を申し込むには",
                    attrs={"href": "https://ndlsearch.ndl.go.jp/help/pdfdownload"},
                )
            ],
            body_text="国立国会図書館サーチから遠隔複写（PDFダウンロード）を申し込むには",
            page_source='<a href="https://ndlsearch.ndl.go.jp/help/pdfdownload">help</a>',
        )

        self.assertTrue(client._page_indicates_remote_copy_only())
        self.assertIsNone(client._find_print_button())

    def test_ndl_browser_client_adjusts_near_end_invalid_page_range(self):
        if importlib.util.find_spec("selenium") is None:
            self.skipTest("selenium unavailable")

        browser_module = self._load_browser_module_or_skip()
        client = browser_module.NDLBrowserClient(headless=True, output_dir=str(Path(tempfile.mkdtemp())))

        adjusted = client._adjust_download_range_from_error(
            "lambda_exception: invalid_page_range:394-390/390",
            start_page=394,
            end_page=396,
        )
        far_adjusted = client._adjust_download_range_from_error(
            "lambda_exception: invalid_page_range:479-390/390",
            start_page=479,
            end_page=481,
        )

        self.assertEqual(adjusted, (388, 390))
        self.assertIsNone(far_adjusted)

    def test_extract_pages_directly_maps_local_page_range(self):
        verifier = HistoricalCitationVerifier()
        captured = []

        def fake_extract(self, pdf_path, *, page_number, output_dir, ocr_model):
            captured.append(page_number)
            return f"text-{page_number}"

        verifier._extract_pdf_page_text = MethodType(fake_extract, verifier)  # type: ignore[method-assign]

        result, page_label_mode = verifier._extract_pages_directly(
            "dummy.pdf",
            pages=[40, 41, 42],
            local_page_range=[40, 42],
            output_dir=Path(tempfile.mkdtemp()),
            ocr_model="ndlocr_lite",
        )

        self.assertEqual(captured, [1, 2, 3])
        self.assertEqual(result, [(40, "text-1"), (41, "text-2"), (42, "text-3")])
        self.assertEqual(page_label_mode, "scan")

    def test_extract_pages_directly_splits_double_page_into_book_pages(self):
        verifier = HistoricalCitationVerifier()

        def fake_spread_extract(self, pdf_path, *, page_number, scan_page_number, book_page_numbers, output_dir, ocr_model):
            return [(book_page_numbers[0], f"right-{scan_page_number}"), (book_page_numbers[1], f"left-{scan_page_number}")]

        verifier._extract_pdf_spread_page_texts = MethodType(fake_spread_extract, verifier)  # type: ignore[method-assign]

        result, page_label_mode = verifier._extract_pages_directly(
            "dummy.pdf",
            pages=[34],
            local_page_range=[32, 36],
            output_dir=Path(tempfile.mkdtemp()),
            ocr_model="ndlocr_lite",
            page_mapping={"anchor_scan_page": 15, "anchor_book_page": 3},
        )

        self.assertEqual(result, [(41, "right-34"), (42, "left-34")])
        self.assertEqual(page_label_mode, "book")

    def test_pdf_ocr_module_maps_target_pages_and_reports_pending_for_missing_pdf(self):
        readiness = wait_for_pdf_ready(
            "missing.pdf",
            local_page_range=[32, 36],
            timeout_seconds=0,
            sleep=lambda _seconds: None,
        )

        self.assertEqual(map_target_page(32, [32, 36]), 1)
        self.assertEqual(map_target_page(36, [32, 36]), 5)
        self.assertIsNone(map_target_page(37, [32, 36]))
        self.assertEqual(map_target_page(12, None), 12)
        self.assertEqual(readiness["status"], "pending")

    def test_pdf_ocr_module_detects_and_splits_double_page_image(self):
        try:
            from PIL import Image, ImageDraw
        except Exception as exc:  # pragma: no cover - depends on optional PIL
            self.skipTest(f"PIL unavailable: {exc}")

        output_dir = Path(tempfile.mkdtemp())
        image_path = output_dir / "spread.png"
        image = Image.new("RGB", (900, 700), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((440, 0, 460, 700), fill=(230, 230, 230))
        image.save(image_path)

        gutter_x = detect_spread_gutter_x(image)
        split_paths = split_double_page_image(
            str(image_path),
            scan_page_number=34,
            output_dir=output_dir,
        )

        self.assertGreater(gutter_x, 300)
        self.assertLess(gutter_x, 600)
        self.assertTrue(Path(split_paths["right"]).exists())
        self.assertTrue(Path(split_paths["left"]).exists())

    def test_pdf_ocr_module_extracts_direct_text_before_ocr(self):
        output_dir = Path(tempfile.mkdtemp())
        direct_text = "直接抽取されたテキスト" * 10

        text = extract_pdf_page_text_module(
            "dummy.pdf",
            page_number=1,
            output_dir=output_dir,
            ocr_model="ndlocr_lite",
            pdf_processor_getter=lambda: DummyPDFProcessor(direct_text),
            ocr_processor_getter=lambda: DummyOCRProcessor("ocr should not be used"),
            render_page=lambda *_args: (_ for _ in ()).throw(AssertionError("render should not run")),
        )

        self.assertEqual(text, direct_text)

    def test_pdf_ocr_module_falls_back_to_ocr_for_short_direct_text(self):
        output_dir = Path(tempfile.mkdtemp())

        text = extract_pdf_page_text_module(
            "dummy.pdf",
            page_number=1,
            output_dir=output_dir,
            ocr_model="ndlocr_lite",
            pdf_processor_getter=lambda: DummyPDFProcessor("short"),
            ocr_processor_getter=lambda: DummyOCRProcessor("OCRで取得した十分に長い日本語テキスト" * 3),
            render_page=lambda _path, _page, _out: "page.png",
        )

        self.assertIn("OCRで取得", text)

    def test_pdf_ocr_module_extracts_spread_pages_and_direct_pages(self):
        output_dir = Path(tempfile.mkdtemp())
        spread = extract_pdf_spread_page_texts_module(
            "dummy.pdf",
            page_number=1,
            scan_page_number=34,
            book_page_numbers=[41, 42],
            output_dir=output_dir,
            ocr_model="ndlocr_lite",
            render_page=lambda _path, _page, _out: "spread.png",
            split_image=lambda _image, _scan, _out: {"right": "right.png", "left": "left.png"},
            ocr_image=lambda image, _out, _model: f"text-{image}",
        )
        direct, mode = extract_pages_directly_module(
            "dummy.pdf",
            pages=[41],
            local_page_range=None,
            output_dir=output_dir,
            ocr_model="ndlocr_lite",
            extract_page_text=lambda _path, page, _out, _model: f"direct-{page}",
            extract_spread_page_texts=lambda *_args: [],
        )

        self.assertEqual(spread, [(41, "text-right.png"), (42, "text-left.png")])
        self.assertEqual(direct, [(41, "direct-41")])
        self.assertEqual(mode, "scan")

    def test_pdf_ocr_module_extracts_multi_panel_pages(self):
        output_dir = Path(tempfile.mkdtemp())
        panels = extract_pdf_multi_panel_page_texts_module(
            "dummy.pdf",
            page_number=1,
            scan_page_number=67,
            book_page_numbers=[476, 477, 478, 479],
            output_dir=output_dir,
            ocr_model="ndlocr_lite",
            render_page=lambda _path, _page, _out: "scan.png",
            split_image=lambda _image, _scan, _count, _out: [
                "panel-1.png",
                "panel-2.png",
                "panel-3.png",
                "panel-4.png",
            ],
            ocr_image=lambda image, _out, _model: f"text-{image}",
        )

        self.assertEqual(
            panels,
            [
                (476, "text-panel-1.png"),
                (477, "text-panel-2.png"),
                (478, "text-panel-3.png"),
                (479, "text-panel-4.png"),
            ],
        )

    def test_pdf_ocr_module_extract_pages_prefers_spread_when_mapping_exists(self):
        output_dir = Path(tempfile.mkdtemp())

        result, mode = extract_pages_directly_module(
            "dummy.pdf",
            pages=[34],
            local_page_range=[32, 36],
            output_dir=output_dir,
            ocr_model="ndlocr_lite",
            page_mapping={"anchor_scan_page": 15, "anchor_book_page": 3},
            extract_page_text=lambda *_args: (_ for _ in ()).throw(AssertionError("direct extraction should not run")),
            extract_spread_page_texts=lambda _path, page, scan, book_pages, _out, _model: [
                (book_pages[0], f"right-{page}-{scan}"),
                (book_pages[1], f"left-{page}-{scan}"),
            ],
        )

        self.assertEqual(result, [(41, "right-3-34"), (42, "left-3-34")])
        self.assertEqual(mode, "book")

    def test_pdf_ocr_module_extract_pages_prefers_multi_panel_when_available(self):
        output_dir = Path(tempfile.mkdtemp())

        result, mode = extract_pages_directly_module(
            "dummy.pdf",
            pages=[8],
            local_page_range=[8, 8],
            output_dir=output_dir,
            ocr_model="ndlocr_lite",
            page_mapping={"anchor_scan_page": 8, "anchor_book_page": 12, "pages_per_scan": 8},
            extract_page_text=lambda *_args: (_ for _ in ()).throw(AssertionError("whole scan should not run")),
            extract_spread_page_texts=lambda *_args: (_ for _ in ()).throw(
                AssertionError("spread splitting should not run for multi-page scans")
            ),
            extract_multi_panel_page_texts=lambda _path, page, scan, book_pages, _out, _model: [
                (book_page, f"panel-{page}-{scan}-{book_page}")
                for book_page in book_pages
            ],
        )

        self.assertEqual(result[0], (12, "panel-1-8-12"))
        self.assertEqual(result[-1], (19, "panel-1-8-19"))
        self.assertEqual(len(result), 8)
        self.assertEqual(mode, "book")

    def test_pdf_ocr_module_falls_back_to_whole_page_when_multi_panel_missing(self):
        output_dir = Path(tempfile.mkdtemp())

        result, mode = extract_pages_directly_module(
            "dummy.pdf",
            pages=[8],
            local_page_range=[8, 8],
            output_dir=output_dir,
            ocr_model="ndlocr_lite",
            page_mapping={"anchor_scan_page": 8, "anchor_book_page": 12, "pages_per_scan": 8},
            extract_page_text=lambda _path, page, _out, _model: f"whole-scan-{page}",
            extract_spread_page_texts=lambda *_args: [],
            extract_multi_panel_page_texts=lambda *_args: [],
        )

        self.assertEqual(result[0], (12, "whole-scan-1"))
        self.assertEqual(result[-1], (19, "whole-scan-1"))
        self.assertEqual(len(result), 8)
        self.assertEqual(mode, "book")

    def test_estimate_scan_page_range_uses_disk_cache_and_first_ndl_id_match(self):
        verifier = HistoricalCitationVerifier()
        parsed = verifier.parse_docx(str(self._make_docx()))
        candidate = verifier.build_candidates(parsed["paragraphs"], parsed["footnotes"])[0]
        candidate.ndl_matches = [
            DummyNDLRecord(
                title="metadata-only match",
                url="https://example.invalid/no-pid",
                ndl_id=None,
            ),
            DummyNDLRecord(
                title="架空史料集：制度宣伝と事件叙述",
                url="https://dl.ndl.go.jp/pid/99999999",
                ndl_id="99999999",
            ),
        ]
        output_dir = Path(tempfile.mkdtemp())
        (output_dir / HistoricalCitationVerifier.PAGE_MAPPING_CACHE_FILENAME).write_text(
            json.dumps(
                {
                    "version": 1,
                    "mappings": {
                        "99999999": {
                            "anchor_scan_page": 15,
                            "anchor_book_page": 3,
                            "sample_scan_page": 7,
                            "sample_title": "第一章",
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        def fail_infer(**_kwargs):
            raise AssertionError("disk cache should avoid front-matter inference")

        verifier._infer_front_matter_page_mapping = fail_infer  # type: ignore[method-assign]

        mapping = verifier._estimate_scan_page_range(
            candidate,
            output_dir=output_dir,
            restricted_download=True,
            page_window=4,
        )

        self.assertIsNotNone(mapping)
        self.assertEqual(mapping["start_book_page"], 37)
        self.assertEqual(mapping["end_book_page"], 45)
        self.assertEqual(mapping["start_scan_page"], 32)
        self.assertEqual(mapping["end_scan_page"], 36)

    def test_page_mapping_module_persists_normalized_cache(self):
        output_dir = Path(tempfile.mkdtemp())

        saved = save_page_mapping_cache(
            output_dir,
            "99999999",
            {
                "anchor_scan_page": "15",
                "anchor_book_page": "3",
                "sample_scan_page": 7,
                "sample_title": "第一章",
            },
        )
        loaded = load_page_mapping_cache(output_dir)

        self.assertEqual(saved["99999999"]["anchor_scan_page"], 15)
        self.assertEqual(loaded["99999999"]["anchor_book_page"], 3)
        self.assertEqual(loaded["99999999"]["sample_title"], "第一章")

    def test_page_mapping_module_persists_failure_cache(self):
        output_dir = Path(tempfile.mkdtemp())

        saved = save_page_mapping_failure_cache(
            output_dir,
            "99999999",
            "front_matter_mapping_not_inferred",
        )
        loaded = load_page_mapping_failure_cache(output_dir)

        self.assertEqual(saved["99999999"], "front_matter_mapping_not_inferred")
        self.assertEqual(loaded["99999999"], "front_matter_mapping_not_inferred")

    def test_verifier_skips_cached_page_mapping_failures(self):
        verifier = HistoricalCitationVerifier()

        self.assertTrue(verifier._should_skip_page_mapping_after_failure("front_matter_mapping_not_inferred"))
        self.assertTrue(verifier._should_skip_page_mapping_after_failure("ndl_toc_empty"))
        self.assertTrue(verifier._should_skip_page_mapping_after_failure("download_not_pdf"))
        self.assertEqual(
            verifier._normalize_download_unavailability_reason("download_not_pdf: b'<!DOCTYP'"),
            "download_not_pdf",
        )
        self.assertEqual(
            verifier._normalize_download_unavailability_reason("download_http_403: https://dl.ndl.go.jp/api/download"),
            "download_http_403",
        )

    def test_page_mapping_module_converts_between_book_and_scan_pages(self):
        mapping = {"anchor_scan_page": 15, "anchor_book_page": 3}

        self.assertEqual(estimate_scan_page_for_book_page(mapping, 41), 34)
        self.assertEqual(estimate_book_pages_from_scan_page(mapping, 34), [41, 42])

        scan_range = build_scan_page_range(mapping, [41], page_window=4)

        self.assertIsNotNone(scan_range)
        self.assertEqual(scan_range["start_book_page"], 37)
        self.assertEqual(scan_range["end_book_page"], 45)
        self.assertEqual(scan_range["start_scan_page"], 32)
        self.assertEqual(scan_range["end_scan_page"], 36)

    def test_page_mapping_module_supports_multi_page_scans(self):
        mapping = {"anchor_scan_page": 8, "anchor_book_page": 12, "pages_per_scan": 8}

        self.assertEqual(estimate_scan_page_for_book_page(mapping, 18), 8)
        self.assertEqual(estimate_scan_page_for_book_page(mapping, 100), 19)
        self.assertEqual(estimate_book_pages_from_scan_page(mapping, 9), [20, 21, 22, 23, 24, 25, 26, 27])

        scan_range = build_scan_page_range(mapping, [100], page_window=2)

        self.assertEqual(scan_range["start_scan_page"], 18)
        self.assertEqual(scan_range["end_scan_page"], 19)
        self.assertEqual(scan_range["pages_per_scan"], 8)

    def test_page_mapping_module_parses_toc_page_number_tokens(self):
        self.assertEqual(parse_toc_page_number_token("一"), 1)
        self.assertEqual(parse_toc_page_number_token("一四"), 14)
        self.assertEqual(parse_toc_page_number_token("三〇八"), 308)
        self.assertEqual(parse_toc_page_number_token("三百八"), 308)
        self.assertEqual(parse_toc_page_number_token("４７５"), 475)

    def test_page_mapping_module_infers_generic_toc_body_anchor(self):
        mapping = infer_page_mapping_from_front_matter_texts(
            {
                3: "目次\n第一章 華族制度の成立……7\n第二章 貴族院と華族……31",
                8: "第一章 華族制度の成立\n明治期における制度形成を述べる。",
            }
        )

        self.assertIsNotNone(mapping)
        self.assertEqual(mapping["anchor_scan_page"], 8)
        self.assertEqual(mapping["anchor_book_page"], 7)
        self.assertEqual(mapping["mapping_method"], "front_matter_toc_heading")

    def test_page_mapping_module_infers_anchor_from_japanese_numbered_toc(self):
        mapping = infer_page_mapping_from_front_matter_texts(
            {
                13: "目次\n第一編華族及び華族制度\n第一章明治以前の貴族制の沿革…………一\n第一節 日本における貴族制 一",
                17: "第一章明治以前の貴族制の沿革\n第一節日本における貴族制\n明治の華族は、明治二年六月十七日...",
            }
        )

        self.assertIsNotNone(mapping)
        self.assertEqual(mapping["anchor_scan_page"], 17)
        self.assertEqual(mapping["anchor_book_page"], 1)

    def test_page_mapping_module_infers_visible_page_number_mapping(self):
        mapping = infer_page_mapping_from_visible_page_numbers(
            {
                8: "13\n12\n15\n17\n16\n19\n18",
                9: "21\n20\n25\n24\n27",
                10: "29\n28\n33\n32",
                11: "37\n36\n41\n40\n42",
            }
        )

        self.assertIsNotNone(mapping)
        self.assertEqual(mapping["anchor_scan_page"], 8)
        self.assertEqual(mapping["anchor_book_page"], 12)
        self.assertEqual(mapping["pages_per_scan"], 8)
        self.assertEqual(mapping["mapping_method"], "visible_page_number_lines")

    def test_page_mapping_module_ignores_visible_page_number_outliers(self):
        mapping = infer_page_mapping_from_visible_page_numbers(
            {
                6: "2\n3\n4\n7",
                7: "4\n5\n9",
                8: "5\n13\n12\n15\n17\n16\n19\n18",
                9: "21\n20\n25\n24\n27",
                10: "29\n28\n33\n32",
                11: "37\n36\n41\n40\n42",
            }
        )

        self.assertIsNotNone(mapping)
        self.assertEqual(mapping["anchor_scan_page"], 8)
        self.assertEqual(mapping["anchor_book_page"], 12)
        self.assertEqual(mapping["pages_per_scan"], 8)

    def test_verifier_refines_cached_mapping_from_existing_ocr_text(self):
        output_dir = Path(tempfile.mkdtemp())
        sample_dir = output_dir / "page_map_99999999"
        for scan_page, text in {
            8: "5\n13\n12\n15\n17\n16\n19\n18",
            9: "21\n20\n25\n24\n27",
            10: "29\n28\n33\n32",
            11: "37\n36\n41\n40\n42",
        }.items():
            ocr_dir = sample_dir / f"ocr_page_{scan_page:04d}_cached"
            ocr_dir.mkdir(parents=True)
            (ocr_dir / f"page_{scan_page:04d}.txt").write_text(text, encoding="utf-8")

        verifier = HistoricalCitationVerifier()
        refined = verifier._refine_cached_page_mapping_from_samples(
            {"anchor_scan_page": 20, "anchor_book_page": 3, "pages_per_scan": 2},
            ndl_id="99999999",
            output_dir=output_dir,
        )

        self.assertEqual(refined["anchor_scan_page"], 8)
        self.assertEqual(refined["anchor_book_page"], 12)
        self.assertEqual(refined["pages_per_scan"], 8)

    def test_clean_ocr_text_for_review_removes_watermark_and_page_number_lines(self):
        verifier = HistoricalCitationVerifier()

        cleaned = verifier._clean_ocr_text_for_review("第一行\n41\nE000000000\n第二行")

        self.assertEqual(cleaned, "第一行\n\n第二行")

    def test_normalize_review_payload_clears_out_of_range_best_index(self):
        normalized = normalize_review_payload(
            {
                "decision": "partial_support",
                "best_index": 99,
                "exact_sentence": "should be cleared",
                "confidence": 0.8,
                "reason": "too many candidate lines confused the model",
            },
            ["候補一", "候補二"],
        )

        self.assertEqual(normalized["decision"], "partial_support")
        self.assertEqual(normalized["best_index"], 0)
        self.assertEqual(normalized["exact_sentence"], "")

    def test_evidence_cues_upgrade_composite_claim_to_partial_support(self):
        translation = (
            "会议派认为新的资金收集方法过于加重同族负担，"
            "且会馆应遵从天皇敕谕。"
        )
        japanese = (
            "其費用ノ額三萬三千六百圓、八年分ノ二倍ニ踰エサルヘシ。"
            "資本寄附ハ又此外タリ。本館ノ事タルヤ上ハ天子ノ聖訓ヲ奉戴シ、"
            "財用ハ事功ノ本ナリ。"
        )

        self.assertGreaterEqual(score_evidence_cues(translation, japanese), 0.25)
        review = heuristic_review_alignment(translation, japanese)

        self.assertEqual(review["decision"], "partial_support")
        self.assertIn("資金", review["cue_matches"])

    def test_evidence_cues_can_load_project_specific_config(self):
        config_path = Path(tempfile.mkdtemp()) / "cue_config.json"
        config_path.write_text(
            json.dumps({"cue_groups": [["Alpha", "甲"], ["Beta", "乙"]]}, ensure_ascii=False),
            encoding="utf-8",
        )
        load_evidence_cue_groups.cache_clear()

        groups = load_evidence_cue_groups(str(config_path))

        self.assertIn(("Alpha", "甲"), groups)

    def test_build_review_context_prefers_pages_near_match(self):
        verifier = HistoricalCitationVerifier()
        candidate = verifier.build_candidates(
            verifier.parse_docx(str(self._make_docx()))["paragraphs"],
            verifier.parse_docx(str(self._make_docx()))["footnotes"],
        )[0]
        candidate.matched_page = 42

        context = verifier._build_review_context(
            candidate,
            extracted_pages=[
                (149, "p149"),
                (40, "p150"),
                (41, "p41"),
                (42, "p42"),
                (43, "p153"),
                (44, "p154"),
                (45, "p155"),
            ],
        )

        self.assertEqual([item["page"] for item in context], [40, 41, 42, 43, 44])

    def test_clear_transient_verification_state_preserves_source_artifacts(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="source", title="source", page_numbers=[41]),
        )
        candidate.notes = [
            "double_page_mapping_used: book_p1->scan_p17",
            "page_distance_from_citation:4",
            "cited_page_alignment_used; heuristic_alignment_used",
            "source_pdf_reused",
        ]
        candidate.artifacts = {
            "source_pdf": "source.pdf",
            "page_mapping": {"anchor_scan_page": 17, "anchor_book_page": 1},
            "alignment_scope": "cited_pages",
            "page_distance_from_citation": 4,
            "matched_scan_page": 169,
        }
        candidate.matched_page = 306
        candidate.matched_japanese = "old segment"
        candidate.confidence = 0.45

        verifier._clear_transient_verification_state(candidate)

        self.assertEqual(candidate.notes, ["double_page_mapping_used: book_p1->scan_p17"])
        self.assertEqual(candidate.artifacts["source_pdf"], "source.pdf")
        self.assertEqual(candidate.artifacts["page_mapping"]["anchor_scan_page"], 17)
        self.assertNotIn("alignment_scope", candidate.artifacts)
        self.assertIsNone(candidate.matched_page)
        self.assertEqual(candidate.matched_japanese, "")
        self.assertIsNone(candidate.confidence)

    def test_clear_successful_source_acquisition_noise_keeps_mapping_note(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="source", title="source", page_numbers=[41]),
        )
        candidate.notes = [
            "ndlsearch_detail_resolution:no_digital_pid",
            "restricted_download_skipped_no_ndl_pid",
            "page_mapping_retry_after_soft_failure:1:temporary",
            "double_page_mapping_used: book_p1->scan_p17",
        ]

        verifier._clear_successful_source_acquisition_noise(candidate)

        self.assertEqual(candidate.notes, ["double_page_mapping_used: book_p1->scan_p17"])

    def test_successful_source_acquisition_clears_stale_unavailability_state(self):
        verifier = HistoricalCitationVerifier()
        candidate = CitationCandidate(
            candidate_id="p1-f1",
            paragraph_index=1,
            paragraph_text="translated text",
            translation_text="translated text",
            footnote_id="1",
            footnote=ParsedFootnote(id="1", text="source", title="source", page_numbers=[41]),
            verification_status="needs_manual_review",
            matched_japanese="可用 OCR 片段",
        )
        candidate.notes = [
            "source_unavailable:no_digital_pid",
            "restricted_download_skipped_no_ndl_pid",
            "cited_page_alignment_used",
        ]
        candidate.artifacts = {
            "source_pdf": "source.pdf",
            "source_availability": {
                "status": "unavailable",
                "reason": "no_digital_pid",
                "source_id": "metadata-only",
            },
            "selected_source_match": {"ndl_id": "12345678"},
        }

        verifier._clear_successful_source_acquisition_noise(candidate)

        self.assertNotIn("source_availability", candidate.artifacts)
        self.assertEqual(candidate.notes, ["cited_page_alignment_used"])
        self.assertEqual(classify_result_status(candidate.to_dict()), "needs_manual_review")

    def test_summarize_results_counts_statuses(self):
        verifier = HistoricalCitationVerifier(ndl_download_module=DummyNDLModule())
        parsed = verifier.parse_docx(str(self._make_docx()))
        candidate = verifier.build_candidates(parsed["paragraphs"], parsed["footnotes"])[0]
        candidate.ndl_matches = verifier.search_ndl_sources(candidate.footnote, max_results=2)
        candidate.verification_status = "needs_manual_review"

        summary = verifier._summarize_results([candidate])

        self.assertEqual(summary["total_candidates"], 1)
        self.assertEqual(summary["source_found"], 1)
        self.assertEqual(summary["needs_manual_review"], 1)
        self.assertEqual(summary["source_not_found"], 0)

    def test_summarize_results_does_not_double_count_source_found_status(self):
        verifier = HistoricalCitationVerifier(ndl_download_module=DummyNDLModule())
        parsed = verifier.parse_docx(str(self._make_docx()))
        candidate = verifier.build_candidates(parsed["paragraphs"], parsed["footnotes"])[0]
        candidate.ndl_matches = verifier.search_ndl_sources(candidate.footnote, max_results=2)
        candidate.verification_status = "source_found"

        summary = verifier._summarize_results([candidate])

        self.assertEqual(summary["source_found"], 1)

    def test_render_markdown_report_uses_shared_page_trace(self):
        verifier = HistoricalCitationVerifier(ndl_download_module=DummyNDLModule())
        parsed = verifier.parse_docx(str(self._make_docx()))
        candidate = verifier.build_candidates(parsed["paragraphs"], parsed["footnotes"])[0]
        candidate.ndl_matches = verifier.search_ndl_sources(candidate.footnote, max_results=2)
        candidate.verification_status = "matched"
        candidate.matched_page = 42
        candidate.matched_japanese = "架空事件の目的は、制度を維持するための実践にあった。"
        candidate.support_status = "direct_support"
        candidate.support_reason = "脚注页内段落与中文引文形成高置信直接对应"
        candidate.evidence_scope = "cited_pages"
        candidate.artifacts["page_mapping"] = {"anchor_scan_page": 15, "anchor_book_page": 3}
        candidate.artifacts["mapped_footnote_pages"] = [34]
        candidate.artifacts["downloaded_page_range"] = [32, 36]
        candidate.artifacts["page_label_mode"] = "book"
        candidate.artifacts["matched_scan_page"] = 34

        report = verifier.render_markdown_report(parsed["document"], [candidate])

        self.assertIn("映射锚点 书页3->扫描页15", report)
        self.assertIn("下载扫描范围 32-36", report)
        self.assertIn("匹配扫描页 34", report)
        self.assertIn("出处有效性: 可作为直接出处", report)

    def test_render_resume_markdown_report_includes_candidate_detail(self):
        checkpoint = {
            "results": {
                "p5-f4": {
                    "candidate_id": "p5-f4",
                    "footnote_id": "4",
                    "translation_text": "为了完成制度维护的示范行动。",
                    "verification_status": "matched",
                    "support_status": "direct_support",
                    "support_reason": "脚注页内段落与中文引文形成高置信直接对应",
                    "evidence_scope": "cited_pages",
                    "matched_page": 42,
                    "matched_japanese": "架空事件の目的は、制度を維持するための実践にあった。",
                    "notes": ["double_page_mapping_used: book_p3->scan_p15"],
                    "ndl_matches": [
                        {
                            "title": "架空史料集 : 制度宣伝と事件叙述",
                            "score": 0.93,
                            "url": "https://dl.ndl.go.jp/pid/99999999",
                        }
                    ],
                    "footnote": {
                        "title": "架空史料集：制度宣伝と事件叙述",
                        "text": "佐藤一郎、高橋二郎「架空史料集：制度宣伝と事件叙述」、2001年、41頁。",
                        "page_numbers": [41],
                    },
                    "artifacts": {
                        "selected_source_match": {
                            "ndl_id": "99999999",
                            "title": "架空史料集 : 制度宣伝と事件叙述",
                        },
                        "downloaded_page_range": [32, 36],
                        "mapped_footnote_pages": [34],
                        "source_attempts": [
                            {
                                "selected_source_match": {
                                    "ndl_id": "88888888",
                                    "title": "架空史料集 別PID",
                                },
                                "downloaded_page_range": [30, 34],
                                "confidence": 0.05,
                                "support_status": "needs_manual_review",
                            }
                        ],
                        "review_context": [{"page": 42, "text": "架空事件の目的は…"}],
                    },
                },
                "p6-f5": {
                    "candidate_id": "p6-f5",
                    "footnote_id": "5",
                    "translation_text": "不可下载来源。",
                    "verification_status": "page_mapping_unavailable",
                    "support_status": "unassessed",
                    "support_reason": "",
                    "matched_page": None,
                    "matched_japanese": "",
                    "notes": ["page_mapping_skipped_after_failure:remote_copy_only_no_print"],
                    "ndl_matches": [
                        {
                            "title": "远程复写限定文献",
                            "score": 0.9,
                            "url": "https://dl.ndl.go.jp/pid/11111111",
                        }
                    ],
                    "footnote": {
                        "title": "远程复写限定文献",
                        "text": "远程复写限定文献，第1页。",
                        "page_numbers": [1],
                    },
                    "artifacts": {},
                }
            },
            "artifacts": {
                "downloaded_pdfs": [{"name": "架空史料集_99999999.pdf", "size": 1024, "modified_at": "2026-04-24T00:00:00"}],
                "page_maps": [{"name": "page_map_99999999", "pdf_count": 1, "modified_at": "2026-04-24T00:00:00"}],
                "download_range_index": {
                    "records": [
                        {
                            "ndl_id": "99999999",
                            "start_page": 32,
                            "end_page": 36,
                            "name": "ndl_99999999_p32-p36.pdf",
                            "size": 1024,
                        }
                    ]
                },
            },
        }

        report = render_resume_markdown_report(
            document={"title": "测试论文"},
            checkpoint=checkpoint,
            total_candidates=2,
            output_dir=Path(tempfile.mkdtemp()),
        )

        self.assertIn("## 已处理候选详情", report)
        self.assertIn("双开页换算后的扫描页: 34", report)
        self.assertIn("出处有效性: 可作为直接出处", report)
        self.assertIn("架空事件の目的は、制度を維持するための実践にあった。", report)
        self.assertIn("架空史料集 : 制度宣伝と事件叙述", report)
        self.assertIn("来源候选尝试记录", report)
        self.assertIn("88888888", report)
        self.assertIn("可检索但当前不可下载", report)
        self.assertIn("remote_copy_only_no_print", report)
        self.assertIn("NDL 页窗 PDF 复用索引", report)

    def test_progress_reporter_emits_json_events(self):
        stream = io.StringIO()
        reporter = ProgressReporter(enabled=True, interval_seconds=0, stream=stream)
        reporter.update(phase="ocr", current=1, total=2, candidate_id="p1-f1")
        reporter.event("candidate_started")
        reporter.close()

        payload = json.loads(stream.getvalue().strip())
        self.assertEqual(payload["schema_version"], "historical_citation.progress.v1")
        self.assertEqual(payload["event"], "candidate_started")
        self.assertEqual(payload["phase"], "ocr")
        self.assertEqual(payload["candidate_id"], "p1-f1")

    def test_classify_status_refines_download_failures_from_notes(self):
        self.assertEqual(
            classify_status("download_failed", ["batch_controller_timeout_after_600s"]),
            "download_timeout",
        )
        self.assertEqual(
            classify_status("download_failed", ["same_source_timeout_as_previous"]),
            "skipped_same_source_failed",
        )
        self.assertEqual(
            classify_status("download_failed", ["restricted_download_failed[keyword]: No NDL search results were returned."]),
            "source_not_found",
        )
        self.assertEqual(
            classify_status("download_failed", ["batch_controller_resume_exit_1"]),
            "runner_failed",
        )
        self.assertEqual(
            classify_status("download_failed", ["page_mapping_required_for_ndl_restricted_download[12345678]"]),
            "page_mapping_unavailable",
        )
        self.assertEqual(
            classify_status("download_failed", ["source_unavailable:no_digital_pid"]),
            "source_unavailable",
        )
        self.assertEqual(
            classify_status(
                "download_failed",
                [
                    "page_mapping_required_for_ndl_restricted_download[12345678]",
                    "source_unavailable:no_digital_pid",
                ],
            ),
            "page_mapping_unavailable",
        )
        self.assertEqual(
            classify_status(
                "page_mapping_unavailable",
                [
                    "mapped_footnote_page_out_of_scan_range[3019147]:mapped=[111]/total=105",
                    "restricted_download_skipped_no_ndl_pid",
                ],
            ),
            "page_mapping_unavailable",
        )
        self.assertEqual(
            classify_result_status(
                {
                    "verification_status": "page_mapping_unavailable",
                    "notes": [],
                    "artifacts": {
                        "source_availability": {
                            "status": "unavailable",
                            "reason": "download_not_pdf",
                        }
                    },
                }
            ),
            "source_unavailable",
        )
        self.assertEqual(
            classify_result_status(
                {
                    "verification_status": "page_mapping_unavailable",
                    "notes": [
                        "page_mapping_required_for_ndl_restricted_download[12345678]",
                        "source_unavailable:no_digital_pid",
                    ],
                    "artifacts": {
                        "page_mapping_required_but_unavailable": True,
                        "page_mapping_unavailable_ndl_ids": ["12345678"],
                        "source_availability": {
                            "status": "unavailable",
                            "reason": "no_digital_pid",
                        },
                    },
                }
            ),
            "page_mapping_unavailable",
        )
        self.assertEqual(
            classify_result_status(
                {
                    "verification_status": "page_mapping_unavailable",
                    "notes": ["mapped_footnote_page_out_of_scan_range[3019147]:mapped=[111]/total=105"],
                    "artifacts": {
                        "page_mapping_required_but_unavailable": True,
                        "page_mapping_unavailable_ndl_ids": ["3019147"],
                        "source_availability": {
                            "status": "unavailable",
                            "reason": "mapped_page_out_of_scan_range",
                        },
                    },
                }
            ),
            "page_mapping_unavailable",
        )

    def test_resume_report_shows_refined_status_breakdown(self):
        checkpoint = {
            "results": {
                "p1-f1": {
                    "candidate_id": "p1-f1",
                    "footnote_id": "1",
                    "translation_text": "测试译文",
                    "verification_status": "download_failed",
                    "matched_page": None,
                    "matched_japanese": "",
                    "notes": ["batch_controller_timeout_after_600s"],
                    "ndl_matches": [],
                    "footnote": {
                        "title": "测试文献",
                        "text": "测试文献，1頁。",
                        "page_numbers": [1],
                    },
                    "artifacts": {},
                }
            },
            "artifacts": {},
        }

        report = render_resume_markdown_report(
            document={"title": "测试论文"},
            checkpoint=checkpoint,
            total_candidates=1,
            output_dir=Path(tempfile.mkdtemp()),
        )

        self.assertEqual(classify_result_status(checkpoint["results"]["p1-f1"]), "download_timeout")
        self.assertIn("下载或处理超时 (`download_timeout`): 1", report)
        self.assertIn("download_failed / download_timeout", report)
        self.assertIn("状态说明: 下载或处理超时", report)


    def test_resume_report_renders_adapter_probe_and_known_pid_fallback_diagnostics(self):
        checkpoint = {
            "results": {
                "p1-f1": {
                    "candidate_id": "p1-f1",
                    "footnote_id": "1",
                    "translation_text": "1900年5月12日，原敬在日记中记录了相关交涉。",
                    "verification_status": "source_found",
                    "support_status": "needs_manual_review",
                    "matched_page": None,
                    "matched_japanese": "",
                    "notes": [
                        "diary_known_pid_page_window_fallback_used:book_pages=84",
                        "diary_date_pdf_page_fallback_used:pdf_page=84",
                    ],
                    "ndl_matches": [
                        {
                            "title": "原敬日記",
                            "url": "https://dl.ndl.go.jp/pid/2982135",
                            "ndl_id": "2982135",
                            "score": 0.9,
                            "metadata": {
                                "search_route": "resolver_config_known_pid",
                                "known_pid_candidate": True,
                            },
                        },
                        {
                            "title": "原敬関係文書",
                            "url": "https://dl.ndl.go.jp/pid/14077946",
                            "ndl_id": "14077946",
                            "score": 0.4,
                            "metadata": {"search_route": "ndl_digital_fulltext_api"},
                        },
                    ],
                    "footnote": {
                        "title": "原敬日記",
                        "text": "『原敬日記』1900年5月12日条，第84頁。",
                        "page_numbers": [84],
                        "source_type": "diary",
                    },
                    "artifacts": {
                        "source_match_order": ["2982135", "14077946"],
                        "downloaded_page_range": [82, 86],
                        "source_resolver_plan": {
                            "source_type": "diary",
                            "verification_mode": "date_volume_known_pid",
                            "pid_scope_strategy": "known_pid_candidates",
                            "source_level_cache_key": "原敬日記|1900-05-12",
                            "known_pid_candidates": ["2982135"],
                            "target_pid_queries": ["1900年5月12日", "1900年", "原敬日記"],
                        },
                        "known_pid_page_window_fallback": {
                            "ndl_id": "2982135",
                            "cited_book_pages": [84],
                            "start_page": 82,
                            "end_page": 86,
                            "evidence_level": "diagnostic_until_ocr_llm_review",
                        },
                        "diary_date_pdf_page_fallback": {
                            "ndl_id": "2982135",
                            "selected_pdf_page": 84,
                            "start_page": 82,
                            "end_page": 86,
                            "selected_query": "\u660e\u6cbb33\u5e74 \u7c73\u56fd \u5c06\u6765",
                            "selected_match_scope": "context",
                            "selected_lead_category": "body",
                            "evidence_level": "routing_only_until_ocr_llm_review",
                            "top_candidates": [
                                {
                                    "pdf_page": 84,
                                    "claim_facets": ["economy", "future_influence", "us"],
                                }
                            ],
                        },
                        "diary_claim_facet_trigger_scope": "translation_text",
                        "diary_date_lookup_diagnostic": {
                            "source_type": "diary",
                            "ndl_id": "2982135",
                            "known_pid_candidates": ["2982135"],
                            "date_queries": ["1900年5月12日", "1900年"],
                            "date_hit_count": 0,
                            "title_queries": ["原敬日記"],
                            "title_hit_count": 4,
                            "recommended_action": "toc_index_then_small_page_window_ocr",
                            "small_page_window": {
                                "cited_book_pages": [84],
                                "start_page": 82,
                                "end_page": 86,
                                "page_window": 2,
                            },
                        },
                        "ndl_fulltext_probe": {
                            "pid": "2982135",
                            "status": "no_direct_hit",
                            "hit_count": 0,
                            "specific_hit_count": 0,
                            "pdf_page_hit_count": 0,
                            "first_pdf_pages": [],
                            "queries_tried": ["1900年5月12日", "原敬日記"],
                        },
                        "fulltext_lead_pid_group": [
                            {
                                "ndl_id": "14077946",
                                "title": "影印原敬日記. 第1巻",
                                "search_route": "ndl_digital_fulltext_api",
                                "scope": "global_fulltext_lead_not_equivalent",
                            }
                        ],
                        "non_equivalent_fulltext_lead_skipped_ids": ["14077946"],
                    },
                }
            },
            "artifacts": {},
        }

        report = render_resume_markdown_report(
            document={"title": "テスト論文"},
            checkpoint=checkpoint,
            total_candidates=1,
            output_dir=Path(tempfile.mkdtemp()),
        )

        self.assertIn("Adapter Candidate Order: 2982135 (known/resolver_config_known_pid)", report)
        self.assertIn("Source-type diagnostic summary: source_type=diary", report)
        self.assertIn("diag=source_type=diary", report)
        self.assertIn("target_snippet=no_direct_hit/hits=0/specific=0", report)
        self.assertIn("diary_date_hits=0/title_hits=4", report)
        self.assertIn("next=toc/index + small page-window OCR", report)
        self.assertIn("page_window=82-86", report)
        self.assertIn("skipped_fulltext_leads=14077946", report)
        self.assertIn("Target PID snippet probe: pid=2982135 | status=no_direct_hit", report)
        self.assertIn("Known PID page-window fallback: PID=2982135", report)
        self.assertIn("Diary date PDF-page route fallback: PID=2982135", report)
        self.assertIn("selected_pdf_page=84", report)
        self.assertIn("diary_pdf_route=p84/window=82-86", report)
        self.assertIn("diary_claim_scope=translation_text", report)
        self.assertIn("Diary claim facet trigger scope: translation_text", report)
        self.assertIn("facets=economy,future_influence,us", report)
        self.assertIn("routing_only_until_ocr_llm_review", report)
        self.assertIn("scan_window=82-86", report)
        self.assertIn("hits=0", report)
        self.assertIn("全文线索 PID 组（非等价）", report)
        self.assertIn("不能作为自动候选轮换的等价来源", report)
        self.assertIn("全文 lead 人工回查建议", report)
        self.assertIn("diary: 先确认日期对应卷册", report)
        self.assertIn("先回查严格 PID 2982135", report)
        self.assertIn("在目标 PID 内搜 1900年5月12日", report)
        self.assertIn("非等价全文线索已跳过自动轮换: 14077946", report)
        self.assertIn("PID=14077946", report)

    def test_resume_report_indexes_three_source_type_diagnostics(self):
        checkpoint = {
            "results": {
                "gaiko": {
                    "candidate_id": "gaiko",
                    "footnote_id": "g1",
                    "translation_text": "门户开放。",
                    "verification_status": "fulltext_only_hit",
                    "support_status": "needs_manual_review",
                    "matched_page": None,
                    "matched_japanese": "",
                    "notes": [],
                    "ndl_matches": [
                        {
                            "title": "日本外交文書",
                            "url": "https://dl.ndl.go.jp/pid/3448128",
                            "ndl_id": "3448128",
                            "score": 0.9,
                            "metadata": {"search_route": "resolver_config_known_pid", "known_pid_candidate": True},
                        }
                    ],
                    "footnote": {
                        "title": "日本外交文書",
                        "text": "日本外交文書第32巻，第216頁。",
                        "page_numbers": [216],
                    },
                    "artifacts": {
                        "source_resolver_plan": {
                            "source_type": "volume_series",
                            "known_pid_candidates": ["3448128"],
                        },
                        "ndl_fulltext_probe": {
                            "pid": "3448128",
                            "status": "direct_hit",
                            "hit_count": 10,
                            "specific_hit_count": 10,
                            "pdf_page_hit_count": 10,
                            "first_pdf_pages": [32],
                        },
                    },
                },
                "diary": {
                    "candidate_id": "diary",
                    "footnote_id": "d1",
                    "translation_text": "1900年5月12日。",
                    "verification_status": "source_found",
                    "support_status": "needs_manual_review",
                    "matched_page": None,
                    "matched_japanese": "",
                    "notes": [],
                    "ndl_matches": [
                        {
                            "title": "原敬日記",
                            "url": "https://dl.ndl.go.jp/pid/2982135",
                            "ndl_id": "2982135",
                            "score": 0.9,
                            "metadata": {"search_route": "resolver_config_known_pid", "known_pid_candidate": True},
                        }
                    ],
                    "footnote": {
                        "title": "原敬日記",
                        "text": "原敬日記，1900年5月12日，第84頁。",
                        "page_numbers": [84],
                    },
                    "artifacts": {
                        "source_resolver_plan": {
                            "source_type": "diary",
                            "known_pid_candidates": ["2982135"],
                        },
                        "ndl_fulltext_probe": {
                            "pid": "2982135",
                            "status": "no_direct_hit",
                            "hit_count": 0,
                            "specific_hit_count": 0,
                            "pdf_page_hit_count": 0,
                        },
                        "diary_date_lookup_diagnostic": {
                            "source_type": "diary",
                            "ndl_id": "2982135",
                            "date_hit_count": 0,
                            "title_hit_count": 4,
                            "small_page_window": {"cited_book_pages": [84], "start_page": 82, "end_page": 86},
                        },
                        "known_pid_page_window_fallback": {
                            "ndl_id": "2982135",
                            "cited_book_pages": [84],
                            "start_page": 82,
                            "end_page": 86,
                        },
                    },
                },
                "contained": {
                    "candidate_id": "contained",
                    "footnote_id": "c1",
                    "translation_text": "山縣有朋意見書。",
                    "verification_status": "fulltext_only_hit",
                    "support_status": "needs_manual_review",
                    "matched_page": None,
                    "matched_japanese": "",
                    "notes": [],
                    "ndl_matches": [
                        {
                            "title": "山県有朋意見書",
                            "url": "https://dl.ndl.go.jp/pid/3025431",
                            "ndl_id": "3025431",
                            "score": 0.9,
                            "metadata": {"search_route": "resolver_config_known_pid", "known_pid_candidate": True},
                        }
                    ],
                    "footnote": {
                        "title": "山縣有朋意見書",
                        "text": "山縣有朋意見書，第12頁。",
                        "page_numbers": [12],
                    },
                    "artifacts": {
                        "source_resolver_plan": {
                            "source_type": "contained_document",
                            "known_pid_candidates": ["3025431"],
                        },
                        "manual_search_recipe": {
                            "reason": "contained_document_requires_host_discovery",
                            "suggested_pid_scope": "3025431",
                            "suggested_queries": ["山縣有朋意見書 復讐心"],
                            "target_pid_queries": ["復讐心", "共同經營", "滿洲"],
                            "query_buckets": {
                                "contained": ["山縣有朋意見書"],
                                "theme": ["滿洲"],
                                "action": ["共同經營", "復讐心"],
                                "page_near": ["外交政略"],
                            },
                        },
                        "contained_document_lookup_diagnostic": {
                            "source_type": "contained_document",
                            "ndl_id": "3025431",
                            "known_pid_candidates": ["3025431"],
                            "host_missing": True,
                            "contained_title": "山縣有朋意見書",
                            "title_hit_count": 10,
                        },
                    },
                },
            },
            "artifacts": {},
        }

        report = render_resume_markdown_report(
            document={"title": "三类史料测试"},
            checkpoint=checkpoint,
            total_candidates=3,
            output_dir=Path(tempfile.mkdtemp()),
        )

        self.assertIn("diag=source_type=volume_series", report)
        self.assertIn("target_snippet=direct_hit/hits=10/specific=10", report)
        self.assertIn("diag=source_type=diary", report)
        self.assertIn("diary_date_hits=0/title_hits=4", report)
        self.assertIn("diag=source_type=contained_document", report)
        self.assertIn("next=known PID first, then host fallback", report)
        self.assertIn("pid_query=復讐心, 共同經營, 滿洲", report)
        self.assertIn("theme=滿洲", report)
        self.assertIn("action=共同經營, 復讐心", report)


if __name__ == "__main__":
    unittest.main()
