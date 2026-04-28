import unittest

from modules.ndlkotenocr_lite import (
    NDLKotenOCRLiteConfig,
    NDLKotenOCRLiteProcessor,
    NDLKotenOCRLiteResult,
)


def make_processor_without_probe() -> NDLKotenOCRLiteProcessor:
    processor = NDLKotenOCRLiteProcessor.__new__(NDLKotenOCRLiteProcessor)
    processor.config = NDLKotenOCRLiteConfig()
    processor._ndlkoten_executable = None
    processor._model_dir = None
    processor._config_dir = None
    return processor


class TestNDLKotenOCRLitePackage(unittest.TestCase):
    def test_result_to_package_records_classical_provider(self):
        result = NDLKotenOCRLiteResult()
        result.success = True
        result.pages = [{"filename": "page_0001.txt", "text": "Koten text", "path": "page_0001.txt"}]

        package = result.to_package(source_path="koten.png")

        self.assertEqual(package["type"], "ocr_result")
        self.assertEqual(package["provider"], "ndlkotenocr_lite")
        self.assertEqual(package["model"], "ndlkotenocr-lite")
        self.assertFalse(package["needs_review"])

    def test_capabilities_work_without_installation(self):
        processor = make_processor_without_probe()

        capabilities = processor.get_capabilities()

        self.assertFalse(capabilities["available"])
        self.assertIn("classical_japanese_ocr", capabilities["capabilities"])

    def test_process_image_package_wraps_failure(self):
        processor = make_processor_without_probe()

        package = processor.process_image_package("missing.png")

        self.assertTrue(package["needs_review"])
        self.assertIn("ocr_failed", package["quality_flags"])
        self.assertIn("capabilities", package)


if __name__ == "__main__":
    unittest.main()
