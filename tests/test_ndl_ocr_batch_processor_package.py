import tempfile
import unittest
from pathlib import Path

from modules.ndl_ocr_batch_processor import NDLOCRBatchProcessor


class NDLOCRBatchProcessorPackageTests(unittest.TestCase):
    def test_missing_engine_returns_structured_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_dir = root / "images"
            image_dir.mkdir()
            (image_dir / "page_0001.png").write_bytes(b"not-a-real-image")

            processor = NDLOCRBatchProcessor(
                ndlocr_path=str(root / "missing_ocr.py")
            )
            package = processor.process_batch_package(
                str(image_dir),
                str(root / "ocr_output"),
            )

        self.assertEqual(package["type"], "ocr_batch")
        self.assertEqual(package["backend"], "local_engine")
        self.assertEqual(package["provider"], "ndlocr_batch")
        self.assertTrue(package["needs_review"])
        self.assertIn("engine_unavailable", package["quality_flags"])
        self.assertIn("batch_error", package["quality_flags"])
        self.assertEqual(package["statistics"]["total"], 0)

    def test_manual_results_are_normalized_to_page_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_dir = root / "images"
            output_dir = root / "out"
            image_dir.mkdir()
            processor = NDLOCRBatchProcessor(
                ndlocr_path=str(root / "missing_ocr.py")
            )
            processor.available = True
            processor.availability_message = "NDL OCR可用"

            package = processor._build_batch_package(
                [
                    {
                        "page": 1,
                        "filename": "page_0001.png",
                        "success": True,
                        "text": "伊藤博文",
                        "char_count": 4,
                        "output_path": str(output_dir / "page_0001"),
                        "error": None,
                    },
                    {
                        "page": 2,
                        "filename": "page_0002.png",
                        "success": False,
                        "text": "",
                        "char_count": 0,
                        "output_path": str(output_dir / "page_0002"),
                        "error": "timeout",
                    },
                ],
                image_dir,
                output_dir,
            )

        self.assertEqual(package["statistics"]["total"], 2)
        self.assertEqual(package["statistics"]["success"], 1)
        self.assertAlmostEqual(package["confidence"], 0.5)
        self.assertTrue(package["needs_review"])
        self.assertIn("page_failures", package["quality_flags"])
        self.assertEqual(package["pages"][0]["text"], "伊藤博文")
        self.assertFalse(package["pages"][1]["success"])
        self.assertIn("page_failed", package["pages"][1]["quality_flags"])

    def test_strict_mode_preserves_legacy_failure_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                NDLOCRBatchProcessor(
                    ndlocr_path=str(Path(tmp) / "missing_ocr.py"),
                    strict=True,
                )


if __name__ == "__main__":
    unittest.main()
