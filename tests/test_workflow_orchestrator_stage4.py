import tempfile
import unittest

from tools.workflow.research_project import PaperRecord, ResearchProject, StageStatus
from tools.workflow.stages.stage4_examine import Stage4Examine
from tools.workflow.workflow_orchestrator import WorkflowOrchestrator


class WorkflowOrchestratorStage4Test(unittest.TestCase):
    def test_orchestrator_registers_checkpoint_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow = WorkflowOrchestrator(topic="Checkpoint test", language="en", output_dir=temp_dir)

            def fake_stage(**kwargs):
                del kwargs
                workflow.project.paper_draft = "draft"
                workflow.project.mark_stage_done(5)
                return {"status": "ok", "paragraphs": [1, 2, 3]}

            workflow._stage_handlers[5] = fake_stage
            result = workflow.run_stage(5)

            self.assertEqual(result["status"], "ok")
            metadata = workflow.project.get_stage_metadata(5)
            self.assertEqual(metadata["invoked_via"], "workflow_orchestrator")
            self.assertTrue(metadata["checkpoint_path"].endswith(".json"))
            self.assertEqual(metadata["result_summary"]["paragraphs_count"], 3)
            self.assertTrue(any(item["type"] == "workflow_checkpoint" and item["stage"] == 5 for item in workflow.project.artifacts))
            manifest = workflow.artifact_manager.package_manifest()
            self.assertEqual(manifest["artifact_count"], 1)
            self.assertEqual(manifest["artifacts"][0]["type"], "workflow_checkpoint")
            self.assertTrue(manifest["artifacts"][0]["written"])

    def test_orchestrator_registers_failed_stage_package(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow = WorkflowOrchestrator(topic="Failure checkpoint", language="en", output_dir=temp_dir)

            def failing_stage(**kwargs):
                del kwargs
                raise RuntimeError("synthetic stage failure")

            workflow._stage_handlers[3] = failing_stage

            with self.assertRaises(RuntimeError):
                workflow.run_stage(3)

            metadata = workflow.project.get_stage_metadata(3)
            self.assertIn("failure_package", metadata)
            self.assertIn("stage3_failed", workflow.project.quality_flags)
            self.assertEqual(workflow.project.review_queue[0]["package_type"], "workflow_stage_failure")
            self.assertTrue(
                any(
                    item["type"] == "workflow_checkpoint"
                    and item["stage"] == 3
                    and item.get("package_type") == "workflow_stage_failure"
                    for item in workflow.project.artifacts
                )
            )

    def test_stage4_records_execution_summary_and_review_items(self):
        project = ResearchProject(topic="Outline test", language="en")
        project.literature = [
            PaperRecord(
                id="paper-1",
                title="Tokugawa governance",
                abstract="Tokugawa governance shaped Edo institutions.",
                year="2001",
            ),
            PaperRecord(
                id="paper-2",
                title="Edo institutions and governance",
                abstract="This paper discusses Tokugawa governance and Edo institutions in detail.",
                year="2010",
            ),
        ]
        project.paper_draft = "Introduction\n" + ("Analysis of Tokugawa governance. " * 20)

        stage = Stage4Examine(project)

        def fake_outline_analyzer():
            class Analyzer:
                def analyze(self, text, language="english"):
                    del text, language
                    return {
                        "section_word_counts": {"introduction": 200, "analysis": 400},
                        "section_ratios": {"introduction": 0.33, "analysis": 0.67},
                        "logical_gaps": ["missing conclusion"],
                        "deviation_flags": ["analysis too long"],
                        "suggestions": ["add a conclusion"],
                    }

            return Analyzer()

        stage._get_outline_analyzer = fake_outline_analyzer
        result = stage.run()

        self.assertIsNotNone(result["citation_network"])
        self.assertIsNotNone(result["outline_review"])
        self.assertEqual(project.stage4_status, StageStatus.DONE)

        metadata = project.get_stage_metadata(4)
        self.assertEqual(metadata["execution_summary"]["citation_analysis"]["nodes"], 2)
        self.assertEqual(metadata["execution_summary"]["citation_analysis"]["backend"], "script")
        self.assertFalse(metadata["execution_summary"]["citation_analysis"]["needs_review"])
        self.assertIn("citation_graph_building", metadata["capability_snapshot"]["citation_analysis"]["capabilities"])
        self.assertEqual(metadata["execution_summary"]["outline_review"]["logical_gaps"], 1)
        self.assertIn("stage4_outline_review_needed", project.quality_flags)
        self.assertEqual(len(project.review_queue), 3)
        self.assertTrue(any(item.get("package_type") == "outline_review" for item in project.review_queue))
        self.assertTrue(any(item["type"] == "citation_network" for item in metadata["packages"]))

    def test_stage4_consumes_stage2_book_citation_records(self):
        project = ResearchProject(topic="Book network", language="en")
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
                    "normalized_citation": "田中太郎. 近代日本政治史 [M]. 東京史学出版社, 1988.",
                    "confidence": 0.9,
                }
            ],
        )

        stage = Stage4Examine(project)
        result = stage.run()

        self.assertIsNotNone(result["citation_network"])
        metadata = project.get_stage_metadata(4)
        self.assertEqual(metadata["execution_summary"]["citation_analysis"]["nodes"], 1)
        self.assertEqual(metadata["execution_summary"]["citation_analysis"]["stage2_citation_records"], 1)
        self.assertTrue(metadata["execution_summary"]["citation_analysis"]["needs_review"])
        self.assertIn("stage4_no_citation_edges", project.quality_flags)


if __name__ == "__main__":
    unittest.main()
