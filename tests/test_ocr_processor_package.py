import unittest

from modules.ocr_processor import OCRProcessor


def make_processor_without_model_load() -> OCRProcessor:
    processor = OCRProcessor.__new__(OCRProcessor)
    processor.ndl_available = False
    processor.ndl_model = None
    processor.ndl_processor = None
    processor.ndl_model_path = None
    return processor


class TestOCRProcessorPackage(unittest.TestCase):
    def test_result_to_package_marks_successful_ocr(self):
        processor = make_processor_without_model_load()

        package = processor._result_to_package(
            {
                "success": True,
                "text": "Tokugawa archive",
                "words": [{"word": "Tokugawa", "confidence": 90}],
                "language": "en",
                "method": "tesseract",
            },
            source_path="page.png",
        )

        self.assertEqual(package["type"], "ocr_result")
        self.assertEqual(package["provider"], "tesseract")
        self.assertFalse(package["needs_review"])
        self.assertGreater(package["confidence"], 0.8)

    def test_extract_text_from_image_package_wraps_legacy_result(self):
        processor = make_processor_without_model_load()
        processor.extract_text_from_image = lambda image_path, language="zh", config=None: {
            "success": True,
            "text": "Meiji document",
            "words": [],
            "language": language,
            "config": config,
            "method": "tesseract",
        }

        package = processor.extract_text_from_image_package("page.png", language="en")

        self.assertEqual(package["source_path"], "page.png")
        self.assertIn("capabilities", package)
        self.assertEqual(package["metadata"]["language"], "en")

    def test_batch_package_flags_empty_input(self):
        processor = make_processor_without_model_load()

        package = processor.batch_ocr_package([])

        self.assertEqual(package["type"], "ocr_batch")
        self.assertTrue(package["needs_review"])
        self.assertIn("no_images", package["quality_flags"])


if __name__ == "__main__":
    unittest.main()
