import tempfile
import unittest
from pathlib import Path

from tools.workflow.research_project import ResearchProject


class TestResearchProjectArtifactManager(unittest.TestCase):
    def test_register_package_mounts_artifacts_quality_and_review(self):
        project = ResearchProject(topic="Artifact protocol", language="zh")
        package = {
            "type": "task_execution",
            "success": True,
            "confidence": 0.42,
            "needs_review": True,
            "quality_flags": ["low_confidence"],
            "artifacts": [
                {
                    "type": "task_execution_json",
                    "path": "workflow_output/task.json",
                    "written": True,
                }
            ],
        }

        summary = project.register_package(package, stage=3, source="unit-test")

        self.assertEqual(summary["type"], "task_execution")
        self.assertEqual(summary["artifact_count"], 1)
        self.assertIn("low_confidence", project.quality_flags)
        self.assertEqual(len(project.review_queue), 1)
        self.assertEqual(project.review_queue[0]["package_type"], "task_execution")
        self.assertEqual(project.artifacts[0]["stage"], 3)
        self.assertIn(project.artifacts[0]["id"], project.stage_metadata["stage3"]["artifact_ids"])
        self.assertIn(project.review_queue[0]["id"], project.stage_metadata["stage3"]["review_item_ids"])

    def test_quality_and_artifact_summary_are_persisted(self):
        project = ResearchProject(topic="Persistence", language="en")
        project.register_artifact("workflow_checkpoint", stage=5, path="workflow_output/checkpoint.json")
        project.add_quality_flag("manual_review_needed")

        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = Path(tmp_dir) / "project.json"
            project.save(str(save_path))
            restored = ResearchProject.load(str(save_path))

        summary = restored.get_quality_summary()
        self.assertEqual(summary["artifact_summary"]["total_artifacts"], 1)
        self.assertEqual(summary["artifact_summary"]["by_stage"]["stage5"], 1)
        self.assertIn("manual_review_needed", summary["quality_flags"])


if __name__ == "__main__":
    unittest.main()
