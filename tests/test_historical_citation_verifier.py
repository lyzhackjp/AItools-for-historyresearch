import json
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import MethodType
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
from modules.historical_citation.cross_validation import (
    classify_fulltext_page_check,
    normalized_text_similarity,
    render_cross_validation_markdown,
    select_fulltext_hit,
)
from modules.historical_citation.download_index import find_cached_range_pdf as find_cached_range_pdf_from_index
from modules.historical_citation.download_index import refresh_download_range_index
from modules.historical_citation.evidence_cues import load_evidence_cue_groups
from modules.historical_citation.footnote_parser import extract_quotes, parse_footnote_text, pick_translation_text
from modules.historical_citation.llm_review import (
    OllamaChatClient,
    build_llm_review_prompt,
    evaluate_review_client,
    heuristic_review_alignment,
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


if __name__ == "__main__":
    unittest.main()
