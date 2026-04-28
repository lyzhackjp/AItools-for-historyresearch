import unittest

from modules.style_transfer import StyleTransfer
from tools.workflow.research_project import ResearchProject
from tools.workflow.stages.stage6_polish import Stage6Polish


class StyleTransferPackageTests(unittest.TestCase):
    def test_transfer_style_package_wraps_script_result(self):
        transfer = StyleTransfer(api_provider="qwen", test_mode=True)
        package = transfer.transfer_style_package(
            "This draft has a historical argument and preserves citations.",
            target_style="academic history prose",
        )

        self.assertEqual(package["type"], "style_transfer")
        self.assertEqual(package["backend"], "script")
        self.assertIn("rewritten_text", package)
        self.assertIn("statistics", package)
        self.assertGreaterEqual(package["confidence"], 0.5)

    def test_empty_input_package_sets_review_flags(self):
        transfer = StyleTransfer(api_provider="qwen", test_mode=True)
        package = transfer.transfer_style_package("", target_style="academic history prose")

        self.assertTrue(package["needs_review"])
        self.assertIn("empty_input", package["quality_flags"])
        self.assertLess(package["confidence"], 0.7)

    def test_stage6_records_style_transfer_package_summary(self):
        project = ResearchProject(topic="Meiji", language="en", bilingual=False)
        project.paper_draft = (
            "# Introduction\n\n"
            "This paragraph introduces the argument in a fairly repetitive way. "
            "This paragraph introduces the argument in a fairly repetitive way.\n\n"
            "# Analysis\n\n"
            "This section develops the argument but does not yet provide a conclusion."
        )
        stage = Stage6Polish(project)
        stage.style_transfer = StyleTransfer(api_provider="qwen", test_mode=True)

        result = stage.run(test_mode=True, target_style="academic history prose")

        self.assertIn("style_transferred_draft", result)
        summary = project.get_stage_metadata(6)["execution_summary"]["style_transfer"]
        self.assertEqual(summary["package_type"], "style_transfer")
        self.assertIn("quality_flags", summary)


if __name__ == "__main__":
    unittest.main()
