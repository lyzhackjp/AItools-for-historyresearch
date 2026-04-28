import json
import tempfile
import unittest
from pathlib import Path

from modules.workflows.ndl_download import NDLDownloadModule, NDLDownloadRequest
from modules.workflows.pdf_to_ner import PDFToNERConfig, PDFToNERPipeline


class FakeStatus:
    def __init__(self, value):
        self.value = value


class FakePublicDownloadResult:
    def __init__(self):
        self.status = FakeStatus("success")
        self.file_path = "downloads/public.pdf"
        self.file_size = 1234
        self.error_message = None
        self.attempts = 1
        self.download_time = 0.5
        self.checksum = "abc123"


class FakePublicSearcher:
    def __init__(self, output_dir, headless):
        self.output_dir = output_dir
        self.headless = headless
        self.closed = False

    def search(self, keyword, max_results, use_api):
        return []

    def search_and_download(self, keyword, filename, max_attempts, use_api):
        return FakePublicDownloadResult()

    def close(self):
        self.closed = True


class FakeBrowserResult:
    def __init__(self):
        self.success = True
        self.output_path = "downloads/restricted.pdf"
        self.total_pages = 12
        self.is_encrypted = False
        self.chunks = [1, 2]
        self.error_message = None


class FakeBook:
    def __init__(self, title, ndl_id, url):
        self.title = title
        self.ndl_id = ndl_id
        self.pid = ndl_id
        self.url = url
        self.author = None
        self.date = None
        self.publisher = None


class FakeBrowserClient:
    login_called = False

    def __init__(self, headless, output_dir):
        self.headless = headless
        self.output_dir = output_dir

    def login(self):
        FakeBrowserClient.login_called = True

    def search_and_get_book(self, keyword):
        return [
            FakeBook("Book A", "0001", "https://example.com/1"),
            FakeBook("Book B", "0002", "https://example.com/2"),
        ]

    def download_book(self, book, filename=None, download_dir=None):
        return FakeBrowserResult()

    def close(self):
        return None


class ReusableWorkflowTests(unittest.TestCase):
    def test_public_ndl_download_outcome(self):
        module = NDLDownloadModule(project_root=Path.cwd())
        module._public_searcher_class = lambda: FakePublicSearcher
        module._validate_pdf_file = lambda file_path: {
            "valid": True,
            "reason": "ok",
            "path": file_path,
            "file_size": 1234,
        }

        outcome = module.download(
            NDLDownloadRequest(keyword="ethics", output_dir="tmp/public")
        )

        self.assertTrue(outcome.success)
        self.assertEqual(outcome.mode, "public")
        self.assertEqual(outcome.status, "success")
        self.assertEqual(outcome.file_path, "downloads/public.pdf")

    def test_restricted_ndl_download_can_select_result(self):
        module = NDLDownloadModule(project_root=Path.cwd())
        module._browser_client_class = lambda: FakeBrowserClient
        module._validate_pdf_file = lambda file_path: {
            "valid": True,
            "reason": "ok",
            "path": file_path,
            "file_size": 1234,
        }

        outcome = module.download(
            NDLDownloadRequest(
                keyword="biography",
                output_dir="tmp/restricted",
                restricted=True,
                result_index=1,
            )
        )

        self.assertTrue(outcome.success)
        self.assertEqual(outcome.mode, "restricted")
        self.assertEqual(outcome.selected_result.ndl_id, "0002")
        self.assertTrue(FakeBrowserClient.login_called)

    def test_merge_ner_outputs_builds_jsonl_and_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pipeline = PDFToNERPipeline(
                PDFToNERConfig(
                    pdf_path=root / "dummy.pdf",
                    output_dir=root / "workflow_output",
                    start_page=1,
                    end_page=2,
                    run_ocr=False,
                    run_ner=False,
                ),
                project_root=root,
            )
            paths = pipeline._ensure_dirs()

            for page in (1, 2):
                page_dir = paths["ner"] / f"page_{page:04d}"
                page_dir.mkdir(parents=True, exist_ok=True)
                payload = {
                    "page": page,
                    "persons": [
                        {
                            "entry_id": page,
                            "needs_review": False,
                            "person_info": {
                                "name": f"Person {page}",
                                "birth_date": "1900",
                                "birth_date_raw": "1900",
                                "registered_domicile": "Tokyo",
                            },
                            "current_status": {
                                "organization": "Org",
                                "title": "Title",
                            },
                            "trajectory_summary": {
                                "organization_flow": "Org A -> Org B",
                                "location_flow": "Tokyo -> Osaka",
                            },
                            "career_trajectory": [{"organization": "Org"}],
                            "address_raw": "Address",
                            "review_reason": None,
                        }
                    ],
                }
                (page_dir / f"page_{page:04d}_ner.json").write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            summary = pipeline.merge_ner_outputs([1, 2], paths)

            self.assertEqual(summary["person_count"], 2)
            self.assertTrue(Path(summary["jsonl"]).exists())
            self.assertTrue(Path(summary["csv"]).exists())


if __name__ == "__main__":
    unittest.main()
