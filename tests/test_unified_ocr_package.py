import unittest

from modules.unified_ocr_processor import UnifiedOCRProcessor, UnifiedOCRResult


class TestUnifiedOCRPackage(unittest.TestCase):
    def test_result_to_package_marks_successful_text(self):
        result = UnifiedOCRResult()
        result.success = True
        result.text = "Tokugawa archive page."
        result.pages = [{"page": 1, "text": "Tokugawa archive page.", "confidence": 0.86}]
        result.model_type = "tesseract"
        result.model_description = "Tesseract OCR"
        result.backend_kind = "local_engine"
        result.provider = "tesseract"

        package = result.to_package(source_path="page_0001.png")

        self.assertEqual(package["type"], "ocr_result")
        self.assertEqual(package["backend"], "local_engine")
        self.assertEqual(package["provider"], "tesseract")
        self.assertFalse(package["needs_review"])
        self.assertGreater(package["confidence"], 0.8)

    def test_process_image_package_wraps_processor_result(self):
        processor = UnifiedOCRProcessor()
        fake = UnifiedOCRResult()
        fake.success = True
        fake.text = "Meiji document"
        fake.pages = [{"page": 1, "text": "Meiji document"}]
        fake.model_type = "tesseract"
        fake.backend_kind = "local_engine"
        fake.provider = "tesseract"
        processor.process_image = lambda **kwargs: fake

        package = processor.process_image_package("page.png", model_type="tesseract")

        self.assertEqual(package["source_path"], "page.png")
        self.assertIn("capabilities", package)
        self.assertEqual(package["model"], "tesseract")

    def test_failed_result_requires_review(self):
        result = UnifiedOCRResult()
        result.success = False
        result.error = "backend missing"

        package = result.to_package(source_path="missing.png")

        self.assertTrue(package["needs_review"])
        self.assertIn("ocr_failed", package["quality_flags"])
        self.assertIn("no_text", package["quality_flags"])


if __name__ == "__main__":
    unittest.main()
