import unittest

from modules.ner_disambiguation import EntityDisambiguator, NERDisambiguation
from tools.workflow.research_project import HistoricalEntity, PaperRecord, ResearchProject
from tools.workflow.stages.stage3_extract import Stage3Extract


class FakeTaskManagerForDisambiguation:
    def get_task_options(self, task_type):
        return {"task_type": task_type, "backends": [{"name": "script", "available": True}]}

    def execute_task(self, task_type, **kwargs):
        return {
            "success": True,
            "data": {
                "entities": [
                    {
                        "entity": "江户",
                        "category": "location",
                        "confidence": 0.86,
                        "needs_review": False,
                    }
                ]
            },
            "backend": "script",
            "metadata": {"backend": "script", "provider": "rule", "model": "fake"},
        }


class NERDisambiguationPackageTest(unittest.TestCase):
    def test_batch_disambiguate_package_records_standard_name(self):
        disambiguator = EntityDisambiguator()

        package = disambiguator.batch_disambiguate_package(
            [{"entity": "江户", "category": "location"}],
            "江户幕府 将军 统治",
        )

        self.assertEqual(package["type"], "entity_disambiguation")
        self.assertEqual(package["summary"]["resolved_count"], 1)
        self.assertEqual(package["summary"]["standard_name_count"], 1)
        self.assertFalse(package["needs_review"])
        self.assertEqual(package["entities"][0]["standard_name"], "德川幕府")
        self.assertEqual(package["entities"][0]["type"], "organization")

    def test_wrapper_disambiguate_package_keeps_legacy_shape(self):
        wrapper = NERDisambiguation()

        package = wrapper.disambiguate_package(
            [("江户", "location", 0, 2)],
            "江户城 江户湾",
        )

        self.assertEqual(package["entities"][0]["original_entity"], "江户")
        self.assertIn("disambiguated_type", package["entities"][0])
        self.assertIn("standard_name", package["entities"][0])

    def test_unknown_entity_package_needs_review(self):
        disambiguator = EntityDisambiguator()

        package = disambiguator.batch_disambiguate_package(
            [{"entity": "Unknown Entity", "category": "person"}],
            "context",
        )

        self.assertTrue(package["needs_review"])
        self.assertIn("unknown_entity_rules", package["quality_flags"])
        self.assertEqual(package["summary"]["unknown_count"], 1)

    def test_stage3_records_disambiguation_package_summary(self):
        project = ResearchProject(topic="江户幕府 将军 统治", language="zh")
        project.literature = [
            PaperRecord(
                id="paper-1",
                title="江户政治",
                abstract="江户幕府形成政治中心。",
            )
        ]
        stage = Stage3Extract(project)
        stage.task_manager = FakeTaskManagerForDisambiguation()

        result = stage.run(test_mode=True)

        self.assertEqual(result["total_entities"], 1)
        self.assertEqual(project.entities[0].category, "organization")
        self.assertEqual(project.entities[0].name_zh, "德川幕府")
        packages = project.get_stage_metadata(3)["execution_summary"]["disambiguation_packages"]
        self.assertEqual(packages[0]["type"], "entity_disambiguation")
        self.assertEqual(packages[0]["summary"]["resolved_count"], 1)


if __name__ == "__main__":
    unittest.main()
