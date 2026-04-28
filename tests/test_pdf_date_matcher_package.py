import tempfile
import unittest
from pathlib import Path

from modules.pdf_date_matcher import DateEntry, MatchedPair, PDFDateMatcher


class TestPDFDateMatcherPackage(unittest.TestCase):
    def _matcher(self) -> PDFDateMatcher:
        output_dir = Path(tempfile.mkdtemp())
        return PDFDateMatcher(
            source_pdf_path="source.pdf",
            annotation_pdf_path="annotation.pdf",
            output_dir=str(output_dir),
        )

    def test_get_capabilities_is_offline_by_default(self):
        matcher = self._matcher()

        capabilities = matcher.get_capabilities()

        self.assertEqual(capabilities["module"], "pdf_date_matcher")
        self.assertIn("training_samples", capabilities["output_types"])
        self.assertTrue(capabilities["privacy"]["offline_by_default"])
        self.assertFalse(capabilities["privacy"]["auto_load_api_key"])
        self.assertIn("skill", capabilities["fallback_order"])
        self.assertIn("mcp", capabilities["fallback_order"])

    def test_parse_annotation_dates_package_extracts_era_dates(self):
        matcher = self._matcher()
        text_by_page = {
            1: "明治三十六年一月一日 晴。日誌本文。",
            2: "明治三十六年一月二日 雨。続き。",
        }

        package = matcher.parse_annotation_dates_package(text_by_page)

        self.assertEqual(package["type"], "date_extraction")
        self.assertEqual(package["summary"]["date_count"], 2)
        self.assertFalse(package["needs_review"])
        self.assertIn("1903-01-01", package["dates"])
        self.assertEqual(package["dates"]["1903-01-01"]["era"], "明治")

    def test_match_dates_package_wraps_matched_pairs(self):
        matcher = self._matcher()
        annotation_dates = {
            "1903-01-01": DateEntry(
                date_str="明治36年1月1日",
                year=1903,
                month=1,
                day=1,
                era="明治",
                era_year=36,
                text_content="annotation text",
                source_page=7,
            )
        }
        source_results = {
            3: {
                "dates": [
                    {
                        "era": "明治",
                        "era_year": 36,
                        "year": 1903,
                        "month": 1,
                        "day": 1,
                        "date_str": "明治三十六年一月一日",
                    }
                ]
            }
        }

        package = matcher.match_dates_package(annotation_dates, source_results)

        self.assertEqual(package["type"], "date_match_pairs")
        self.assertEqual(package["summary"]["matched_pair_count"], 1)
        self.assertEqual(package["matched_pairs"][0]["source_page"], 3)
        self.assertFalse(package["needs_review"])

    def test_generate_training_data_package_does_not_save_by_default(self):
        matcher = self._matcher()
        pair = MatchedPair(
            source_image_path="source_images/page_0003.png",
            source_page=3,
            annotation_text="annotation text",
            annotation_page=7,
            date_info={"year": 1903, "month": 1, "day": 1},
        )

        package = matcher.generate_training_data_package([pair])

        self.assertEqual(package["type"], "training_samples")
        self.assertEqual(package["summary"]["training_sample_count"], 1)
        self.assertEqual(package["samples"][0]["annotation_pdf_page"], 7)
        self.assertIn("artifacts_not_saved", package["quality_flags"])
        self.assertFalse((matcher.training_dir / "training_samples.json").exists())


if __name__ == "__main__":
    unittest.main()
