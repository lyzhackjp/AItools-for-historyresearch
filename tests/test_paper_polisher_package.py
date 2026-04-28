import unittest

from modules.paper_polisher import PaperPolisher
from tools.workflow.research_project import ResearchProject
from tools.workflow.stages.stage6_polish import Stage6Polish


class PaperPolisherPackageTests(unittest.TestCase):
    def test_polish_text_package_wraps_script_result(self):
        polisher = PaperPolisher(api_provider="qwen", test_mode=True)
        package = polisher.polish_text_package(
            "这个研究非常非常重要，基本上基本上可以说明问题，并且需要保留原有论证。",
            language="zh",
        )

        self.assertEqual(package["type"], "paper_polish")
        self.assertEqual(package["backend"], "script")
        self.assertIn("polished_text", package)
        self.assertIn("revision_notes", package)
        self.assertEqual(package["statistics"]["paragraph_count"], 1)
        self.assertGreaterEqual(package["confidence"], 0.5)

    def test_short_paragraph_package_is_marked(self):
        polisher = PaperPolisher(api_provider="qwen", test_mode=True)
        package = polisher.polish_paragraph_package("短段落。", language="zh")

        self.assertEqual(package["polished_text"], "短段落。")
        self.assertIn("short_input_skipped", package["quality_flags"])
        self.assertTrue(package["needs_review"])

    def test_stage6_records_paper_polish_package_summary(self):
        project = ResearchProject(topic="Meiji", language="zh", bilingual=False)
        project.paper_draft = (
            "# 引言\n\n"
            "这个研究非常非常重要，基本上基本上可以说明问题。"
            "这个段落用于测试论文润色 package 是否能进入 Stage 6 元数据。"
        )
        stage = Stage6Polish(project)
        stage.polisher = PaperPolisher(api_provider="qwen", test_mode=True)

        result = stage.run(test_mode=True)

        self.assertIn("polished_draft", result)
        summary = project.get_stage_metadata(6)["execution_summary"]["paper_polish"]
        self.assertEqual(summary["package_type"], "paper_polish")
        self.assertEqual(summary["backend"], "script")
        self.assertIn("quality_flags", summary)


if __name__ == "__main__":
    unittest.main()
