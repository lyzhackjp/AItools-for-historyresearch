import os
import tempfile
import unittest

from tools.workflow.research_project import PaperRecord, ResearchProject
from tools.workflow.stages.stage7_format import Stage7Format


class TestStage7FormatChain(unittest.TestCase):
    def test_stage7_uses_latest_draft_and_records_metadata(self):
        project = ResearchProject(topic="Meiji State", language="en", bilingual=False)
        project.paper_draft = "# Draft\n\nOriginal draft body."
        project.polished_draft = "# Draft\n\nPolished draft body."
        project.style_transferred_draft = "# Draft\n\nStyled draft body with inline citation (Smith, 2012)."
        project.literature = [
            PaperRecord(
                id="paper-1",
                title="State Formation in Meiji Japan",
                authors=["Smith, John"],
                year="2012",
                journal="Journal of Modern Japan",
                doi="10.1234/example",
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            word_path = os.path.join(tmpdir, "final.docx")
            with open(word_path, "w", encoding="utf-8") as handle:
                handle.write("placeholder")

            stage = Stage7Format(project)
            stage._export_to_word = lambda final_paper, formatted_refs, fmt: {"markdown_docx": word_path}  # noqa: ARG005
            result = stage.run(format="chicago")

        self.assertIn("Styled draft body", result["final_paper"])
        self.assertIn("## References", result["final_paper"])
        self.assertEqual(len(result["formatted_citations"]), 1)
        metadata = project.get_stage_metadata(7)
        self.assertEqual(metadata["execution_summary"]["source_draft"], "style_transferred_draft")
        self.assertEqual(metadata["execution_summary"]["formatted_reference_count"], 1)
        self.assertEqual(metadata["execution_summary"]["citation_format_package"]["type"], "citation_formatting")
        self.assertEqual(metadata["execution_summary"]["citation_format_package"]["summary"]["record_count"], 1)
        self.assertEqual(metadata["package_protocol"]["registered_package_count"], 1)
        self.assertEqual(metadata["packages"][0]["type"], "citation_formatting")
        self.assertEqual(metadata["artifact_protocol"]["registered_artifact_count"], 1)
        self.assertEqual(project.artifacts[0]["type"], "word_export")
        self.assertEqual(len(metadata["normalized_citation_records"]), 1)
        self.assertEqual(project.stage7_status.value, "done")

    def test_stage7_merges_stage2_book_citation_records(self):
        project = ResearchProject(topic="Meiji Sources", language="en", bilingual=False)
        project.paper_draft = "# Draft\n\nBody."
        project.set_stage_metadata(
            2,
            book_citation_records=[
                {
                    "id": "book-1",
                    "type": "book",
                    "title": "近代日本政治史",
                    "authors": ["田中太郎"],
                    "year": "1988",
                    "publisher": "東京史学出版社",
                    "confidence": 0.91,
                    "needs_review": False,
                }
            ],
        )

        stage = Stage7Format(project)
        stage._export_to_word = lambda final_paper, formatted_refs, fmt: {}  # noqa: ARG005
        result = stage.run(format="chicago")

        self.assertEqual(len(result["normalized_records"]), 1)
        self.assertIn("近代日本政治史", result["formatted_citations"][0])
        metadata = project.get_stage_metadata(7)
        self.assertEqual(metadata["execution_summary"]["formatted_reference_count"], 1)
        self.assertEqual(metadata["normalized_citation_records"][0]["type"], "book")
        self.assertEqual(metadata["package_protocol"]["registered_package_count"], 1)


if __name__ == "__main__":
    unittest.main()
