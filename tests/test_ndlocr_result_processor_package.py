import unittest

from modules.ndlocr_lite import NDLOCRLiteResult
from modules.ndlocr_result_processor import NDLOCRResultProcessor


class TestNDLOCRResultProcessorPackage(unittest.TestCase):
    def test_process_result_package_wraps_cleaned_text(self):
        result = NDLOCRLiteResult()
        result.success = True
        result.text = "  Tokugawa text  "
        result.pages = [{"filename": "page_0001.txt", "text": "  Tokugawa text  "}]
        result.processing_time = 0.4

        processor = NDLOCRResultProcessor()
        package = processor.process_result_package(result, source_path="page.png")

        self.assertEqual(package["type"], "processed_ocr_result")
        self.assertEqual(package["backend"], "script")
        self.assertEqual(package["provider"], "ndlocr_result_processor")
        self.assertFalse(package["needs_review"])
        self.assertIn("Tokugawa text", package["text"])
        self.assertEqual(package["statistics"]["total_pages"], 1)

    def test_failed_result_package_requires_review(self):
        result = NDLOCRLiteResult()
        result.success = False
        result.error = "missing engine"

        processor = NDLOCRResultProcessor()
        package = processor.process_result_package(result)

        self.assertTrue(package["needs_review"])
        self.assertIn("postprocess_failed", package["quality_flags"])
        self.assertIn("no_processed_text", package["quality_flags"])

    def test_batch_package_flags_empty_input(self):
        processor = NDLOCRResultProcessor()

        package = processor.batch_process_package([])

        self.assertEqual(package["type"], "processed_ocr_batch")
        self.assertTrue(package["needs_review"])
        self.assertIn("no_results", package["quality_flags"])


if __name__ == "__main__":
    unittest.main()
