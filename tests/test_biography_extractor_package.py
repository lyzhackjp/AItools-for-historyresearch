import tempfile
import unittest
from pathlib import Path

from modules.biography_extractor import BiographyExtractor


class TestBiographyExtractorPackage(unittest.TestCase):
    def _extractor(self) -> BiographyExtractor:
        return BiographyExtractor(
            pdf_path="synthetic.pdf",
            output_dir=str(Path(tempfile.mkdtemp())),
        )

    def test_get_capabilities_is_offline_by_default(self):
        extractor = self._extractor()

        capabilities = extractor.get_capabilities()

        self.assertEqual(capabilities["module"], "biography_extractor")
        self.assertIn("biography_entities", capabilities["output_types"])
        self.assertTrue(capabilities["privacy"]["offline_by_default"])
        self.assertFalse(capabilities["privacy"]["auto_load_api_key"])
        self.assertFalse(capabilities["privacy"]["llm_fallback_enabled"])
        self.assertIn("skill", capabilities["fallback_order"])
        self.assertIn("mcp", capabilities["fallback_order"])

    def test_extract_entities_package_parses_vertical_text(self):
        extractor = self._extractor()
        text = "\n".join(
            [
                "山田太郎（ヤマダタロウ）",
                "本籍: 東京府",
                "東京大学卒業",
                "南満洲鉄道 昭和10年",
            ]
        )

        package = extractor.extract_entities_package(text, page_num=5, source_id="page-5")

        self.assertEqual(package["type"], "biography_entities")
        self.assertEqual(package["summary"]["person_count"], 1)
        self.assertEqual(package["persons"][0]["name"], "山田太郎")
        self.assertEqual(package["persons"][0]["page_number"], 5)
        self.assertFalse(package["needs_review"])

    def test_process_ocr_results_package_flags_empty_text(self):
        extractor = self._extractor()
        ocr_results = [
            {
                "success": True,
                "page_number": 1,
                "text": "佐藤一郎（サトウイチロウ）\n京都帝大卒業\n満鉄 昭和12年",
            },
            {"success": False, "page_number": 2, "text": ""},
        ]

        package = extractor.process_ocr_results_package(ocr_results)

        self.assertEqual(package["type"], "biography_batch")
        self.assertEqual(package["summary"]["ocr_result_count"], 2)
        self.assertEqual(package["summary"]["person_count"], 1)
        self.assertIn("ocr_failures_present", package["quality_flags"])
        self.assertIn("empty_ocr_text", package["quality_flags"])


if __name__ == "__main__":
    unittest.main()
