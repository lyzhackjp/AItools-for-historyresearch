import tempfile
import unittest
from pathlib import Path

from tools.workflow.research_project import PaperRecord, ResearchProject, StageStatus
from tools.workflow.stages.stage3_extract import Stage3Extract


class FakeTaskManager:
    def get_task_options(self, task_type):
        self.last_task_type = task_type
        return {
            "task_type": task_type,
            "backends": [
                {"name": "llm_api", "kind": "api", "available": True},
                {"name": "script", "kind": "script", "available": True},
            ],
        }

    def get_task_registry(self, detailed=False):
        return {
            "schema_version": "1.0",
            "module": "task_manager",
            "tasks": {
                "ner": {
                    "name": "ner",
                    "aliases": [],
                    "backends": ["script", "llm_api"],
                    "capability": self.get_task_options("ner") if detailed else {},
                }
            },
            "aliases": {},
        }

    def get_capabilities(self):
        return {
            "type": "task_manager_capabilities",
            "schema_version": "1.0",
            "module": "task_manager",
            "mode": "api",
            "provider": "qwen",
            "backend_options": ["script", "local_llm", "llm_api"],
            "privacy": {"exposes_secret_values": False},
        }

    def execute_task(self, task_type, **kwargs):
        text = kwargs["text"]
        if "Tokugawa" in text:
            entities = [
                {
                    "entity": "Tokugawa Ieyasu",
                    "category": "person",
                    "confidence": 0.92,
                    "needs_review": False,
                }
            ]
        else:
            entities = [
                {
                    "entity": "Edo",
                    "category": "location",
                    "confidence": 0.45,
                    "needs_review": True,
                }
            ]
        return {
            "success": True,
            "data": {"entities": entities},
            "backend": kwargs.get("backend") or "llm_api",
            "metadata": {
                "backend": kwargs.get("backend") or "llm_api",
                "provider": kwargs.get("provider") or "qwen",
                "model": kwargs.get("model") or "fake-model",
            },
        }

    def execute_task_package(self, task_type, **kwargs):
        result = self.execute_task(task_type, **kwargs)
        metadata = result["metadata"]
        return {
            "type": "task_execution",
            "task_type": task_type,
            "success": result["success"],
            "backend": metadata["backend"],
            "provider": metadata["provider"],
            "model": metadata["model"],
            "confidence": 0.9,
            "needs_review": False,
            "quality_flags": [],
            "data": result["data"],
            "result": result,
            "artifacts": [],
        }


class Stage3WorkflowIntegrationTest(unittest.TestCase):
    def test_stage3_records_capabilities_and_review_queue(self):
        project = ResearchProject(topic="Early Edo politics", language="en")
        project.literature = [
            PaperRecord(
                id="paper-1",
                title="Tokugawa state formation",
                abstract="Tokugawa Ieyasu consolidated power in Edo.",
            )
        ]
        project.obsidian_notes = [
            {
                "id": "note-1",
                "title": "Edo note",
                "content": "Edo emerged as a political center in the early modern period.",
            }
        ]

        stage = Stage3Extract(project)
        stage.task_manager = FakeTaskManager()

        result = stage.run(test_mode=False, backend="llm_api")

        self.assertEqual(project.stage3_status, StageStatus.DONE)
        self.assertEqual(result["total_entities"], 2)
        self.assertIn("stage3_manual_review_needed", project.quality_flags)
        self.assertEqual(len(project.review_queue), 1)

        metadata = project.get_stage_metadata(3)
        self.assertEqual(metadata["capability_snapshot"]["task_type"], "ner")
        self.assertEqual(metadata["task_layer_snapshot"]["registry"]["module"], "task_manager")
        self.assertFalse(metadata["task_layer_snapshot"]["manager"]["privacy"]["exposes_secret_values"])
        self.assertEqual(metadata["requested_execution"]["backend"], "llm_api")
        self.assertEqual(metadata["execution_summary"]["documents_processed"], 2)
        self.assertEqual(metadata["execution_summary"]["needs_review_count"], 1)
        self.assertEqual(metadata["execution_summary"]["packages"][0]["type"], "ner_extraction")
        self.assertEqual(metadata["execution_summary"]["packages"][0]["backend"], "llm_api")
        self.assertEqual(metadata["execution_summary"]["packages"][0]["task_package"]["type"], "task_execution")
        self.assertFalse(metadata["execution_summary"]["packages"][0]["needs_review"])
        self.assertTrue(metadata["execution_summary"]["packages"][1]["needs_review"])
        self.assertIn("low_confidence_entities", metadata["execution_summary"]["packages"][1]["quality_flags"])

    def test_research_project_persists_stage_metadata(self):
        project = ResearchProject(topic="Persistence test", language="en")
        project.set_stage_metadata(3, capability_snapshot={"task_type": "ner"})
        project.add_review_item({"stage": 3, "entity": "Edo"})
        project.add_artifact({"stage": 3, "path": "workflow_output/example.json"})
        project.add_quality_flag("stage3_manual_review_needed")

        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "project.json"
            project.save(str(save_path))
            restored = ResearchProject.load(str(save_path))

        self.assertEqual(restored.get_stage_metadata(3)["capability_snapshot"]["task_type"], "ner")
        self.assertEqual(restored.review_queue[0]["entity"], "Edo")
        self.assertEqual(restored.artifacts[0]["stage"], 3)
        self.assertIn("stage3_manual_review_needed", restored.quality_flags)


if __name__ == "__main__":
    unittest.main()
