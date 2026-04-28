import tempfile
import unittest
from pathlib import Path

from modules.biography_pipeline import BiographyPipeline, PipelineConfig


class TestBiographyPipelinePackage(unittest.TestCase):
    def _pipeline(self) -> BiographyPipeline:
        return BiographyPipeline(
            PipelineConfig(
                pdf_path="synthetic.pdf",
                output_dir=str(Path(tempfile.mkdtemp())),
            )
        )

    def test_get_capabilities_is_thin_offline_wrapper(self):
        pipeline = self._pipeline()

        capabilities = pipeline.get_capabilities()

        self.assertEqual(capabilities["module"], "biography_pipeline")
        self.assertIn("biography_batch", capabilities["output_types"])
        self.assertTrue(capabilities["privacy"]["offline_by_default"])
        self.assertFalse(capabilities["privacy"]["secret_file_loading"])
        self.assertIn("biographical_ner", capabilities["fallback_order"])
        self.assertIn("skill", capabilities["fallback_order"])

    def test_process_ocr_results_package_delegates_to_ner_package(self):
        pipeline = self._pipeline()
        ocr_results = [
            {
                "success": True,
                "page_number": 3,
                "image_path": "page_0003.png",
                "text": "鈴木梅四郎\n本籍：東京府\n学歴：東京帝国大学経済学部卒業\n昭和5年 満鉄調査部",
            }
        ]

        package = pipeline.process_ocr_results_package(ocr_results)

        self.assertEqual(package["type"], "biography_batch")
        self.assertEqual(package["summary"]["ocr_result_count"], 1)
        self.assertEqual(package["summary"]["person_count"], 1)
        self.assertEqual(package["persons"][0]["name"], "鈴木梅四郎")
        self.assertFalse(package["needs_review"])
        self.assertEqual(package["source_package"]["type"], "biography_entities")

    def test_build_summary_package_flags_failed_pipeline(self):
        pipeline = self._pipeline()

        package = pipeline.build_summary_package(success=False, errors=["pdf_missing"])

        self.assertEqual(package["type"], "biography_pipeline_summary")
        self.assertFalse(package["success"])
        self.assertTrue(package["needs_review"])
        self.assertIn("pipeline_failed", package["quality_flags"])
        self.assertIn("error:pdf_missing", package["quality_flags"])


if __name__ == "__main__":
    unittest.main()
