import unittest

from modules.academic_note_generator import AcademicNoteGenerator


class FakeTaskManager:
    def __init__(self, response):
        self.response = response

    def execute_task(self, task_type, **kwargs):
        self.last_task_type = task_type
        self.last_kwargs = kwargs
        return self.response


class AcademicNoteGeneratorPackageTests(unittest.TestCase):
    def test_generate_reading_note_package_wraps_task_output(self):
        generator = AcademicNoteGenerator(api_provider="ollama", test_mode=False)
        generator.task_manager = FakeTaskManager(
            {
                "success": True,
                "backend": "local_llm",
                "metadata": {
                    "backend": "local_llm",
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                },
                "data": {
                    "note_content": "Tokugawa governance shaped [[Edo]].",
                    "entities": [
                        {"text": "Tokugawa Ieyasu", "category": "person"},
                        {"text": "Edo", "category": "location"},
                    ],
                },
            }
        )

        package = generator.generate_reading_note_package(
            "Tokugawa governance shaped Edo.",
            {"id": "paper-1", "title": "Tokugawa governance", "year": "2024"},
        )

        self.assertEqual(package["type"], "academic_note")
        self.assertEqual(package["backend"], "local_llm")
        self.assertEqual(package["provider"], "ollama")
        self.assertEqual(package["model"], "gemma4:e4b")
        self.assertIn("Tokugawa Ieyasu", package["entities"]["person"])
        self.assertTrue(package["markdown"])
        self.assertFalse(package["needs_review"])
        self.assertGreater(package["confidence"], 0.7)
        self.assertEqual(package["export_summary"]["entity_count"], 2)

    def test_degraded_package_sets_review_flags(self):
        generator = AcademicNoteGenerator(api_provider="qwen", test_mode=False)
        generator.task_manager = FakeTaskManager(
            {
                "success": False,
                "backend": "llm_api",
                "metadata": {"backend": "llm_api", "provider": "qwen"},
                "error": "provider unavailable",
                "data": {},
            }
        )

        package = generator.generate_reading_note_package(
            "Short text.",
            {"title": "Failed note"},
        )

        self.assertEqual(package["type"], "academic_note")
        self.assertTrue(package["needs_review"])
        self.assertIn("note_generation_fallback_used", package["quality_flags"])
        self.assertIn("fallback_backend", package["quality_flags"])
        self.assertLess(package["confidence"], 0.8)

    def test_batch_process_package_reports_statistics(self):
        generator = AcademicNoteGenerator(api_provider="qwen", test_mode=True)
        package = generator.batch_process_package(
            [
                {"text": "Tokugawa governance shaped Edo.", "metadata": {"title": "A"}},
                {"text": "Fukuzawa discussed civilization.", "metadata": {"title": "B"}},
            ]
        )

        self.assertEqual(package["type"], "academic_note_batch")
        self.assertEqual(package["statistics"]["total"], 2)
        self.assertEqual(package["statistics"]["with_markdown"], 2)
        self.assertEqual(len(package["notes"]), 2)
        self.assertIn("script", {note["backend"] for note in package["notes"]})


if __name__ == "__main__":
    unittest.main()
