import unittest

from modules.ndlocr_lite import NDLOCRLiteConfig, NDLOCRLiteProcessor, NDLOCRLiteResult


def make_processor_without_probe() -> NDLOCRLiteProcessor:
    processor = NDLOCRLiteProcessor.__new__(NDLOCRLiteProcessor)
    processor.config = NDLOCRLiteConfig()
    processor._ndlocr_executable = None
    return processor


class TestNDLOCRLitePackage(unittest.TestCase):
    def test_result_to_package_records_local_engine_metadata(self):
        result = NDLOCRLiteResult()
        result.success = True
        result.pages = [{"filename": "page_0001.txt", "text": "Tokugawa text", "path": "page_0001.txt"}]
        result.processing_time = 1.2

        package = result.to_package(source_path="page.png")

        self.assertEqual(package["type"], "ocr_result")
        self.assertEqual(package["backend"], "local_engine")
        self.assertEqual(package["provider"], "ndlocr_lite")
        self.assertFalse(package["needs_review"])
        self.assertIn("Tokugawa text", package["text"])

    def test_processor_capabilities_are_available_without_installation(self):
        processor = make_processor_without_probe()

        capabilities = processor.get_capabilities()

        self.assertEqual(capabilities["provider"], "ndlocr_lite")
        self.assertFalse(capabilities["available"])
        self.assertIn("japanese_print_ocr", capabilities["capabilities"])

    def test_process_image_package_wraps_failure(self):
        processor = make_processor_without_probe()

        package = processor.process_image_package("missing.png")

        self.assertTrue(package["needs_review"])
        self.assertIn("ocr_failed", package["quality_flags"])
        self.assertIn("capabilities", package)


if __name__ == "__main__":
    unittest.main()
