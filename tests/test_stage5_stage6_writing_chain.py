import unittest

from tools.workflow.research_project import PaperRecord, ResearchProject
from tools.workflow.stages.stage5_write import Stage5Write
from tools.workflow.stages.stage6_polish import Stage6Polish


class _DummyReport:
    search_results_count = 5


class _DummyExplorer:
    def __init__(self, full_text):
        self.report = _DummyReport()
        self._full_text = full_text

    def draft_paper(self, **kwargs):
        del kwargs
        return {"full_text": self._full_text}


class _PackageExplorer(_DummyExplorer):
    def draft_paper_package(self, **kwargs):
        draft = self.draft_paper(**kwargs)
        draft.update(
            {
                "topic": kwargs.get("topic", ""),
                "language": kwargs.get("language", "en"),
                "bilingual": kwargs.get("bilingual", False),
                "style": kwargs.get("style", "academic_history"),
                "backend": "script",
                "provider": "fallback",
                "model": None,
                "confidence": 0.8,
                "needs_review": False,
                "metadata": {"quality": {"char_count": len(self._full_text), "section_count": 3}},
            }
        )
        return {
            "type": "field_draft",
            "backend": "script",
            "provider": "fallback",
            "model": None,
            "confidence": 0.8,
            "needs_review": False,
            "quality_flags": [],
            "draft": draft,
            "export_summary": {"char_count": len(self._full_text), "section_count": 3},
        }


class TestStage5Stage6WritingChain(unittest.TestCase):
    def test_stage5_records_draft_metadata(self):
        project = ResearchProject(topic="Tokugawa", language="en", bilingual=False)
        project.literature = [
            PaperRecord(id="paper-1", title="Tokugawa governance", authors=["Smith"], year="2012")
        ]
        project.set_stage_metadata(
            2,
            book_citation_records=[
                {
                    "id": "book-1",
                    "title": "近代日本政治史",
                    "authors": ["田中太郎"],
                    "year": "1988",
                    "type": "book",
                    "needs_review": False,
                }
            ],
        )
        project.set_stage_metadata(
            3,
            execution_summary={
                "packages": [
                    {
                        "type": "ner_extraction",
                        "source_kind": "paper",
                        "source_id": "paper-1",
                        "backend": "llm_api",
                        "provider": "qwen",
                        "entity_count": 2,
                        "confidence": 0.72,
                        "needs_review": True,
                        "quality_flags": ["low_confidence_entities"],
                    }
                ]
            },
        )
        draft = (
            "# Introduction\n\n"
            "This draft introduces the question and cites prior work (Smith, 2012).\n\n"
            "# Analysis\n\n"
            "The analysis section develops the argument with a second citation [1].\n\n"
            "# Conclusion\n\n"
            "The conclusion closes the argument.\n\n"
            "References\n"
        )
        stage = Stage5Write(project, explorer=_DummyExplorer(draft))
        result = stage.run(topic="Tokugawa", style="academic_history")

        self.assertEqual(result, draft)
        metadata = project.get_stage_metadata(5)
        self.assertIn("execution_summary", metadata)
        self.assertGreaterEqual(metadata["execution_summary"]["heading_count"], 2)
        self.assertEqual(metadata["execution_summary"]["source_record_count"], 2)
        self.assertEqual(metadata["source_snapshot"]["book_citation_record_count"], 1)
        self.assertEqual(metadata["source_snapshot"]["ner_package_count"], 1)
        self.assertEqual(metadata["source_snapshot"]["ner_packages_needing_review"], 1)
        self.assertIn("llm_api", metadata["source_snapshot"]["ner_backends"])
        self.assertIn("low_confidence_entities", metadata["source_snapshot"]["ner_quality_flags"])
        self.assertEqual(project.stage5_status.value, "done")
        self.assertTrue(any(item["type"] == "paper_draft" for item in metadata["packages"]))

    def test_stage5_records_field_draft_package_summary(self):
        project = ResearchProject(topic="Tokugawa", language="en", bilingual=False)
        draft = (
            "# Introduction\n\nText with citation (Smith, 2012).\n\n"
            "# Analysis\n\nArgument [1].\n\n"
            "# Conclusion\n\nEnd.\n\nReferences\n"
        )
        stage = Stage5Write(project, explorer=_PackageExplorer(draft))
        result = stage.run(topic="Tokugawa", style="academic_history")

        self.assertEqual(result, draft)
        summary = project.get_stage_metadata(5)["execution_summary"]
        self.assertEqual(summary["draft_package"]["type"], "field_draft")
        self.assertEqual(summary["draft_package"]["backend"], "script")
        self.assertEqual(summary["draft_package"]["export_summary"]["section_count"], 3)
        metadata = project.get_stage_metadata(5)
        package_types = {item["type"] for item in metadata["packages"]}
        self.assertIn("field_draft", package_types)
        self.assertIn("paper_draft", package_types)

    def test_stage6_records_review_items_and_metadata(self):
        project = ResearchProject(topic="Meiji", language="en", bilingual=False)
        project.paper_draft = (
            "# Introduction\n\n"
            "This paragraph introduces the argument in a fairly repetitive way. "
            "This paragraph introduces the argument in a fairly repetitive way.\n\n"
            "# Analysis\n\n"
            "This section develops the argument but does not yet provide a conclusion."
        )
        stage = Stage6Polish(project)
        result = stage.run(test_mode=True, target_style="academic_history")

        self.assertIn("polished_draft", result)
        self.assertIsNotNone(result.get("outline_review"))
        metadata = project.get_stage_metadata(6)
        self.assertIn("capability_snapshot", metadata)
        self.assertIn("execution_summary", metadata)
        package_types = {item["type"] for item in metadata["packages"]}
        self.assertIn("paper_polish", package_types)
        self.assertIn("style_transfer", package_types)
        self.assertIn("outline_review", package_types)
        self.assertEqual(
            metadata["package_protocol"]["registered_package_count"],
            len(metadata["package_protocol"]["registered_packages"]),
        )
        self.assertEqual(metadata["package_protocol"]["registered_package_count"], 3)
        self.assertGreaterEqual(len(project.review_queue), 1)
        self.assertIn("stage6_outline_review_needed", project.quality_flags)
        self.assertEqual(project.stage6_status.value, "done")


if __name__ == "__main__":
    unittest.main()
