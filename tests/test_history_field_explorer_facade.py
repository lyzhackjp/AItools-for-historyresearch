import unittest

from modules.history_field_explorer import create_explorer


class TestHistoryFieldExplorerFacade(unittest.TestCase):
    def test_explore_records_execution_metadata_in_test_mode(self):
        explorer = create_explorer(language="en", test_mode=True)
        report = explorer.explore("Tudor England", search_limit=5)

        payload = report.to_dict()
        execution = payload["metadata"]["execution"]

        self.assertEqual(execution["module"], "history_field_explorer")
        self.assertEqual(execution["backend"], "script")
        self.assertGreater(execution["paper_count"], 0)
        self.assertIn("field_drafting", execution["capabilities"])
        self.assertFalse(execution["needs_review"])

    def test_draft_paper_returns_backend_and_quality_metadata(self):
        explorer = create_explorer(language="en", test_mode=True)
        explorer.explore("Tudor England", search_limit=5)

        result = explorer.draft_paper(bilingual=False)

        self.assertEqual(result["backend"], "script")
        self.assertEqual(result["provider"], "fallback")
        self.assertIn("confidence", result)
        self.assertIn("needs_review", result)
        self.assertIn("quality", result["metadata"])
        self.assertTrue(result["full_text"])

    def test_explore_package_wraps_field_report(self):
        explorer = create_explorer(language="en", test_mode=True)

        package = explorer.explore_package("Tudor England", search_limit=5)

        self.assertEqual(package["type"], "field_research")
        self.assertEqual(package["backend"], "script")
        self.assertFalse(package["needs_review"])
        self.assertGreater(package["export_summary"]["paper_count"], 0)
        self.assertGreater(package["export_summary"]["core_question_count"], 0)
        self.assertIn("report", package)

    def test_draft_paper_package_wraps_draft_result(self):
        explorer = create_explorer(language="en", test_mode=True)
        explorer.explore("Tudor England", search_limit=5)

        package = explorer.draft_paper_package(bilingual=False)

        self.assertEqual(package["type"], "field_draft")
        self.assertEqual(package["backend"], "script")
        self.assertIn("draft", package)
        self.assertTrue(package["draft"]["full_text"])
        self.assertIn("char_count", package["export_summary"])


if __name__ == "__main__":
    unittest.main()
