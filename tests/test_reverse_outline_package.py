import unittest

from modules.reverse_outline_analyzer import ReverseOutlineAnalyzer
from tools.workflow.research_project import ResearchProject
from tools.workflow.stages.stage6_polish import Stage6Polish


class ReverseOutlinePackageTests(unittest.TestCase):
    def test_analyze_package_wraps_heuristic_review(self):
        analyzer = ReverseOutlineAnalyzer(api_provider="qwen", test_mode=True)
        text = (
            "# Introduction\n\n"
            "This introduction frames the problem and outlines the question.\n\n"
            "# Analysis\n\n"
            "This analysis develops evidence and argument across the draft.\n\n"
            "# Conclusion\n\n"
            "This conclusion returns to the central claim."
        )

        package = analyzer.analyze_package(text, use_llm=False, language="en")

        self.assertEqual(package["type"], "outline_review")
        self.assertEqual(package["backend"], "script")
        self.assertIn("section_word_counts", package)
        self.assertIn("statistics", package)
        self.assertGreaterEqual(package["statistics"]["section_count"], 2)
        self.assertIn("confidence", package)

    def test_short_draft_package_sets_review_flags(self):
        analyzer = ReverseOutlineAnalyzer(api_provider="qwen", test_mode=True)
        package = analyzer.analyze_package("Too short.", use_llm=False, language="en")

        self.assertEqual(package["type"], "outline_review")
        self.assertTrue(package["needs_review"])
        self.assertIn("draft_too_short", package["quality_flags"])
        self.assertLessEqual(package["confidence"], 0.2)

    def test_stage6_records_outline_package_summary(self):
        project = ResearchProject(topic="Meiji", language="en", bilingual=False)
        project.paper_draft = (
            "# Introduction\n\n"
            "This paragraph introduces the argument in a fairly repetitive way. "
            "This paragraph introduces the argument in a fairly repetitive way.\n\n"
            "# Analysis\n\n"
            "This section develops the argument but does not yet provide a conclusion."
        )
        stage = Stage6Polish(project)
        stage.outline_analyzer = ReverseOutlineAnalyzer(api_provider="qwen", test_mode=True)

        result = stage.run(test_mode=True)

        self.assertIsNotNone(result.get("outline_review"))
        summary = project.get_stage_metadata(6)["execution_summary"]["reverse_outline"]
        self.assertEqual(summary["package_type"], "outline_review")
        self.assertIn("quality_flags", summary)


if __name__ == "__main__":
    unittest.main()
