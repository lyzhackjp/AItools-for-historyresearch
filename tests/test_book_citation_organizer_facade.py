import tempfile
import unittest
from pathlib import Path

from modules.book_citation_organizer import BookCitationOrganizer, BookMetadata


class FixtureBookCitationOrganizer(BookCitationOrganizer):
    def extract_pages_text(self, file_path: Path, start_page: int, end_page: int) -> str:
        if start_page == 1:
            return "\n".join(
                [
                    "書名: 近代日本政治史",
                    "著者: 田中太郎",
                    "出版社: 東京史学出版社",
                    "出版: 1988",
                    "ISBN: 978-4-0000-0000-0",
                ]
            )
        return "初版発行 1988\n全 320 頁"

    def _get_page_count(self, file_path: Path) -> int:
        return 10


class TestBookCitationOrganizerFacade(unittest.TestCase):
    def test_metadata_exports_unified_citation_record(self):
        metadata = BookMetadata(
            original_filename="sample.pdf",
            title="近代日本政治史",
            author="田中太郎",
            publisher="東京史学出版社",
            publish_year="1988",
            confidence=0.91,
            needs_review=False,
            backend="script",
            provider="local_rules",
        )
        record = metadata.to_citation_record()
        self.assertEqual(record["type"], "book")
        self.assertEqual(record["title"], "近代日本政治史")
        self.assertEqual(record["authors"], ["田中太郎"])
        self.assertFalse(record["needs_review"])

    def test_process_single_file_adds_quality_and_backend_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "input"
            output_dir = Path(temp_dir) / "output"
            input_dir.mkdir()
            output_dir.mkdir()
            source = input_dir / "scan.pdf"
            source.write_bytes(b"%PDF-1.4\n")

            organizer = FixtureBookCitationOrganizer(
                str(input_dir),
                str(output_dir),
                enable_llm=False,
                copy_files=False,
            )
            result = organizer.process_single_file(source)

            self.assertEqual(result.process_status, "success")
            self.assertEqual(result.title, "近代日本政治史")
            self.assertEqual(result.author, "田中太郎")
            self.assertEqual(result.publish_year, "1988")
            self.assertEqual(result.backend, "script")
            self.assertGreaterEqual(result.confidence, 0.7)
            self.assertFalse(result.needs_review)
            self.assertIn("formatted", result.citation_record)

    def test_summary_exposes_capabilities_and_review_count(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            organizer = FixtureBookCitationOrganizer(temp_dir, temp_dir, enable_llm=False)
            organizer.results = [
                BookMetadata(process_status="success", needs_review=False),
                BookMetadata(process_status="failed", needs_review=True),
            ]
            summary = organizer.get_summary()

            self.assertEqual(summary["total_files"], 2)
            self.assertEqual(summary["needs_review"], 1)
            self.assertIn("capabilities", summary)
            self.assertEqual(summary["capabilities"]["module"], "book_citation_organizer")


if __name__ == "__main__":
    unittest.main()
