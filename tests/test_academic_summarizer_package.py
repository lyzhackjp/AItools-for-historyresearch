import unittest

from modules.academic_summarizer import AcademicSummarizer


class TestAcademicSummarizerPackage(unittest.TestCase):
    def test_full_analysis_package_exposes_workflow_metadata(self):
        text = (
            "Tokugawa governance shaped early modern Japanese institutions. "
            "The article studies political order, archival sources, and comparative methods. "
        ) * 8
        summarizer = AcademicSummarizer(test_mode=True)

        result = summarizer.generate_full_analysis_package(text, metadata={"title": "Tokugawa study"})

        self.assertEqual(result["type"], "academic_analysis")
        self.assertEqual(result["backend"], "script")
        self.assertEqual(result["provider"], "mock_rules")
        self.assertIn("workflow_metadata", result["analysis"])
        self.assertIn("research_question_extraction", result["analysis"]["workflow_metadata"]["capabilities"])
        self.assertFalse(result["needs_review"])

    def test_short_text_is_flagged_for_review(self):
        summarizer = AcademicSummarizer(test_mode=True)

        result = summarizer.generate_full_analysis_package("short note")

        self.assertTrue(result["needs_review"])
        self.assertIn("very_short_text", result["quality_flags"])
        self.assertLess(result["confidence"], 0.78)


if __name__ == "__main__":
    unittest.main()
