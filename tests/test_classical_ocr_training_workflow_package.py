import unittest

from modules.classical_ocr_training_workflow import (
    ClassicalOCRTrainingWorkflow,
    ContentType,
    ProcessingResult,
    ProcessingStage,
    TrainingSample,
    create_default_config,
)


class TestClassicalOCRTrainingWorkflowPackage(unittest.TestCase):
    def _workflow(self) -> ClassicalOCRTrainingWorkflow:
        return ClassicalOCRTrainingWorkflow(create_default_config())

    def test_get_capabilities_describes_training_prep_contract(self):
        workflow = self._workflow()

        capabilities = workflow.get_capabilities()

        self.assertEqual(capabilities["module"], "classical_ocr_training_workflow")
        self.assertEqual(capabilities["layer"], "training_prep")
        self.assertIn("training_workflow_summary", capabilities["output_types"])
        self.assertIn("pdf_date_matcher", capabilities["fallback_order"])
        self.assertIn("skill", capabilities["fallback_order"])
        self.assertTrue(capabilities["privacy"]["offline_by_default"])

    def test_build_summary_package_wraps_processing_results(self):
        workflow = self._workflow()
        workflow.current_stage = ProcessingStage.TRAINING_DATA_GENERATED
        results = [
            ProcessingResult(
                stage=ProcessingStage.PDF_LOADED.value,
                success=True,
                message="loaded",
            ),
            ProcessingResult(
                stage=ProcessingStage.FAILED.value,
                success=False,
                message="failed",
                errors=["missing_dependency:fitz"],
            ),
        ]

        package = workflow.build_summary_package(results=results, output_dir="out")

        self.assertEqual(package["type"], "training_workflow_summary")
        self.assertEqual(package["summary"]["result_count"], 2)
        self.assertEqual(package["summary"]["failed_results"], 1)
        self.assertTrue(package["needs_review"])
        self.assertIn("failed_workflow_stage", package["quality_flags"])
        self.assertIn("workflow_not_completed", package["quality_flags"])

    def test_build_training_samples_package_does_not_write_artifacts(self):
        workflow = self._workflow()
        samples = [
            TrainingSample(
                image_path="handwritten/page_0001/line_0001.png",
                annotation_text="明治三十六年一月一日の日記本文",
                source_page=1,
                date_key="1903-01-01",
                content_type=ContentType.HANDWRITTEN.value,
                confidence=0.82,
            )
        ]

        package = workflow.build_training_samples_package(samples, output_dir="out")

        self.assertEqual(package["type"], "training_samples")
        self.assertEqual(package["summary"]["training_sample_count"], 1)
        self.assertEqual(package["summary"]["content_types"], [ContentType.HANDWRITTEN.value])
        self.assertIn("artifacts_not_saved", package["quality_flags"])
        self.assertEqual(package["samples"][0]["date_key"], "1903-01-01")


if __name__ == "__main__":
    unittest.main()
