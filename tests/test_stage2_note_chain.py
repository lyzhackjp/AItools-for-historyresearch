import tempfile
import unittest

from modules.academic_note_generator import AcademicNoteGenerator
from tools.workflow.research_project import BookMetadata, PaperRecord, ResearchProject, StageStatus
from tools.workflow.stages.stage2_organize import Stage2Organize


class FakeTaskManager:
    def execute_task(self, task_type, **kwargs):
        if task_type == "academic_note":
            return {
                "success": True,
                "backend": kwargs.get("backend") or "llm_api",
                "metadata": {
                    "backend": kwargs.get("backend") or "llm_api",
                    "provider": kwargs.get("provider") or "qwen",
                    "model": kwargs.get("model") or "fake-note-model",
                },
                "data": {
                    "note_content": "# Summary\nTokugawa governance shaped Edo.",
                    "entities": [
                        {"text": "Tokugawa Ieyasu", "category": "person"},
                        {"text": "Edo", "category": "location"},
                    ],
                },
            }
        if task_type == "ner":
            return {
                "success": True,
                "data": {
                    "entities": [
                        {"text": "Tokugawa Ieyasu", "category": "person"},
                        {"text": "Edo", "category": "location"},
                    ]
                },
                "metadata": {"provider": "qwen", "model": "fake-ner"},
            }
        raise AssertionError(f"Unexpected task: {task_type}")


class FakeObsidian:
    def __init__(self, vault_path):
        self.vault_path = vault_path
        self.created = []

    def create_note(self, title, content, note_type="note", folder=None):
        self.created.append((title, content, note_type, folder))
        return True, f"{self.vault_path}/{title}.md"

    def build_knowledge_graph_data(self):
        return {"nodes": [{"id": "Tokugawa Ieyasu"}], "edges": [{"source": "a", "target": "b"}]}


class Stage2NoteChainTest(unittest.TestCase):
    def test_academic_note_generator_normalizes_task_output(self):
        generator = AcademicNoteGenerator(api_provider="qwen", test_mode=False)
        generator.task_manager = FakeTaskManager()

        result = generator.generate_reading_note(
            "Tokugawa governance shaped Edo.",
            {"title": "Tokugawa governance", "authors": "Smith", "year": "2024"},
        )

        self.assertIn("markdown", result)
        self.assertEqual(result["backend"], "llm_api")
        self.assertIn("Tokugawa Ieyasu", result["entities"]["person"])
        self.assertIn("Edo", result["entities"]["location"])
        self.assertFalse(result["needs_review"])

    def test_stage2_records_note_summary_and_vault_artifact(self):
        project = ResearchProject(topic="Tokugawa note chain", language="en")
        project.literature = [
            PaperRecord(
                id="paper-1",
                title="Tokugawa governance",
                abstract="Tokugawa governance shaped Edo institutions and politics.",
                authors=["Smith"],
                year="2024",
                source="journal",
            )
        ]

        stage = Stage2Organize(project)
        generator = AcademicNoteGenerator(api_provider="qwen", test_mode=False)
        generator.task_manager = FakeTaskManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            stage._get_note_generator = lambda: generator
            stage._get_obsidian_integration = lambda: FakeObsidian(temp_dir)
            result = stage.run()

        self.assertEqual(project.stage2_status, StageStatus.DONE)
        self.assertEqual(result["total_notes"], 1)
        self.assertEqual(project.get_stage_metadata(2)["execution_summary"]["notes"]["total_notes"], 1)
        note_packages = project.get_stage_metadata(2)["execution_summary"]["note_packages"]
        self.assertEqual(note_packages[0]["type"], "academic_note")
        self.assertEqual(note_packages[0]["backend"], "llm_api")
        registered_packages = project.get_stage_metadata(2)["packages"]
        self.assertEqual(registered_packages[0]["type"], "academic_note")
        self.assertEqual(registered_packages[0]["stage"], 2)
        self.assertEqual(project.get_stage_metadata(2)["execution_summary"]["vault_export"]["notes_created"], 1)
        self.assertTrue(any(item["type"] == "obsidian_vault" for item in project.artifacts))

    def test_stage2_normalizes_book_metadata_records(self):
        project = ResearchProject(topic="Book citation chain", language="ja", citation_format="chicago")
        project.book_metadata = [
            BookMetadata(
                id="book-1",
                title="近代日本政治史",
                author="田中太郎",
                publisher="東京史学出版社",
                year="1988",
                pages="320",
            )
        ]

        stage = Stage2Organize(project)
        stage._get_obsidian_integration = lambda: None
        result = stage.run()

        self.assertEqual(result["total_notes"], 1)
        self.assertEqual(len(result["book_notes"]), 1)
        self.assertEqual(project.get_stage_metadata(2)["execution_summary"]["book_metadata"]["record_count"], 1)
        self.assertEqual(
            project.get_stage_metadata(2)["book_citation_records"][0]["type"],
            "book",
        )
        self.assertTrue(project.formatted_citations)


if __name__ == "__main__":
    unittest.main()
