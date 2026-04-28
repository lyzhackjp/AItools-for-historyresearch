"""
Workflow orchestrator for the end-to-end historical research pipeline.

The orchestrator is responsible for stage invocation, checkpoint persistence,
artifact registration, and exception summaries. Individual stages remain
responsible for domain execution logic.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

_AI_TOOLS = os.path.dirname(os.path.dirname(__file__))
if _AI_TOOLS not in sys.path:
    sys.path.insert(0, _AI_TOOLS)

from modules.artifact_manager import ArtifactManager
from tools.workflow.research_project import ResearchProject, StageStatus
from tools.workflow.stages.stage1_collect import Stage1Collect
from tools.workflow.stages.stage2_organize import Stage2Organize
from tools.workflow.stages.stage3_extract import Stage3Extract
from tools.workflow.stages.stage4_examine import Stage4Examine
from tools.workflow.stages.stage5_write import Stage5Write
from tools.workflow.stages.stage6_polish import Stage6Polish
from tools.workflow.stages.stage7_format import Stage7Format


class WorkflowOrchestrator:
    """High-level coordinator for stages 1-7."""

    STAGES = [
        (1, "collect_materials", "stage1_collect"),
        (2, "organize_sources", "stage2_organize"),
        (3, "extract_entities", "stage3_extract"),
        (4, "examine_sources", "stage4_examine"),
        (5, "write_draft", "stage5_write"),
        (6, "polish_draft", "stage6_polish"),
        (7, "format_citations", "stage7_format"),
    ]

    STAGE_OUTPUT_FILES = {
        5: "paper_draft.md",
        7: "final_paper.md",
    }

    def __init__(
        self,
        topic: str,
        language: str = "en",
        bilingual: bool = True,
        citation_format: str = "chicago",
        output_dir: str = "./workflow_output",
    ):
        self.project = ResearchProject(
            topic=topic,
            language=language,
            bilingual=bilingual,
            citation_format=citation_format,
        )
        self.output_dir = output_dir
        self._stage_handlers = {
            1: self._run_stage1,
            2: self._run_stage2,
            3: self._run_stage3,
            4: self._run_stage4,
            5: self._run_stage5,
            6: self._run_stage6,
            7: self._run_stage7,
        }
        self._stage_labels = {stage_num: stage_name for stage_num, stage_name, _ in self.STAGES}
        self.artifact_manager = ArtifactManager(self.output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

    def run_all(self) -> ResearchProject:
        """Run all implemented stages in sequence."""

        print("=" * 60)
        print(f"WorkflowOrchestrator start | topic: {self.project.topic}")
        print(f"language: {self.project.language} | bilingual: {self.project.bilingual}")
        print("=" * 60)

        for stage_num, stage_name, _ in self.STAGES:
            if stage_num not in self._stage_handlers:
                print(f"\n[Stage {stage_num}] {stage_name} - not implemented, skipping")
                self._skip_stage(stage_num)
                continue

            status = getattr(self.project, f"stage{stage_num}_status")
            if status == StageStatus.DONE:
                print(f"\n[Stage {stage_num}] {stage_name} - already done, skipping")
                continue

            print(f"\n{'=' * 60}")
            print(f"[Stage {stage_num}] {stage_name}")
            print("=" * 60)

            try:
                self.run_stage(stage_num)
            except Exception as exc:  # noqa: BLE001
                print(f"[Stage {stage_num}] failed: {exc}")
                continue

        print("\n" + "=" * 60)
        print("WorkflowOrchestrator finished")
        print("=" * 60)
        print(self.project.summary())

        save_path = self._save_checkpoint(label="final")
        self.project.register_artifact(
            "workflow_checkpoint",
            path=save_path,
            source="workflow_orchestrator",
            metadata={"label": "final checkpoint"},
        )
        print(f"final checkpoint saved: {save_path}")
        return self.project

    def run_stage(self, stage_num: int, **kwargs) -> Any:
        """Run a single stage and register orchestrator-level metadata."""

        handler = self._stage_handlers.get(stage_num)
        if handler is None:
            print(f"[Stage {stage_num}] not implemented, skipping")
            self._skip_stage(stage_num)
            return None

        stage_name = self._stage_labels.get(stage_num, f"stage_{stage_num}")
        started_at = datetime.now().isoformat(timespec="seconds")
        self.project.set_stage_metadata(
            stage_num,
            orchestrator_started_at=started_at,
            stage_name=stage_name,
            invoked_via="workflow_orchestrator",
        )

        try:
            result = handler(**kwargs)
            self._ensure_stage_done(stage_num)
            checkpoint_path = self._save_checkpoint(stage_num)
            self.project.set_stage_metadata(
                stage_num,
                orchestrator_finished_at=datetime.now().isoformat(timespec="seconds"),
                result_summary=self._build_result_summary(result),
                checkpoint_path=checkpoint_path,
            )
            self._register_stage_artifact(
                stage_num,
                artifact_type="workflow_checkpoint",
                path=checkpoint_path,
                label=f"Stage {stage_num} checkpoint",
            )
            self._register_stage_output_artifact(stage_num)
            return result
        except Exception as exc:  # noqa: BLE001
            self.project.mark_stage_failed(stage_num, str(exc))
            self.project.set_stage_metadata(
                stage_num,
                orchestrator_finished_at=datetime.now().isoformat(timespec="seconds"),
                exception_summary=str(exc),
            )
            checkpoint_path = self._save_checkpoint(stage_num, suffix="failed")
            self._register_stage_failure_package(
                stage_num,
                error=str(exc),
                checkpoint_path=checkpoint_path,
            )
            raise

    def get_output(self, stage_num: int) -> Any:
        """Return the main output for a given stage."""

        attrs = {
            1: "literature",
            2: "book_metadata",
            3: "entities",
            4: "citation_network",
            5: "paper_draft",
            6: "polished_draft",
            7: "final_paper",
        }
        attr = attrs.get(stage_num)
        if attr is None:
            return None
        return getattr(self.project, attr, None)

    def export(self, path: str = "", fmt: str = "markdown") -> str:
        """Export the final paper or current draft."""

        del fmt  # reserved for future format-specific exporters
        content = self.project.final_paper or self.project.paper_draft
        if not content:
            print("[Export] no paper content available")
            return ""

        if not path:
            ts = datetime.now().strftime("%Y%m%d")
            safe = "".join(char if char.isalnum() else "_" for char in self.project.topic[:20])
            path = os.path.join(self.output_dir, f"{safe}_{ts}.md")

        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        self._register_stage_artifact(
            stage_num=7 if self.project.final_paper else 5,
            artifact_type="export",
            path=path,
            label="exported_paper",
        )
        print(f"[Export] paper exported: {path}")
        return path

    @classmethod
    def load(cls, path: str) -> "WorkflowOrchestrator":
        """Restore a workflow from a saved checkpoint."""

        project = ResearchProject.load(path)
        workflow = cls(
            topic=project.topic,
            language=project.language,
            bilingual=project.bilingual,
            citation_format=project.citation_format,
        )
        workflow.project = project
        print(f"[Load] restored project {project.id} | {project.topic}")
        print(workflow.project.summary())
        return workflow

    def _run_stage1(self, **kwargs) -> Any:
        stage = Stage1Collect(self.project)
        search_limit = kwargs.get("search_limit", 60)
        result = stage.run(search_limit=search_limit)
        self._shared_explorer = getattr(stage, "explorer", None)
        return result

    def _run_stage2(self, **kwargs) -> Any:
        stage = Stage2Organize(self.project)
        return stage.run(**kwargs)

    def _run_stage3(self, **kwargs) -> Any:
        stage = Stage3Extract(self.project)
        return stage.run(**kwargs)

    def _run_stage4(self, **kwargs) -> Any:
        stage = Stage4Examine(self.project)
        return stage.run(**kwargs)

    def _run_stage5(self, **kwargs) -> Any:
        stage = Stage5Write(self.project, explorer=getattr(self, "_shared_explorer", None))
        topic = kwargs.get("topic", self.project.topic)
        style = kwargs.get("style", "academic_history")
        result = stage.run(topic=topic, style=style)
        stage.save_paper(os.path.join(self.output_dir, self.STAGE_OUTPUT_FILES[5]))
        return result

    def _run_stage6(self, **kwargs) -> Any:
        stage = Stage6Polish(self.project)
        target_style = kwargs.get("target_style", "")
        return stage.run(target_style=target_style)

    def _run_stage7(self, **kwargs) -> Any:
        stage = Stage7Format(self.project)
        fmt = kwargs.get("format", self.project.citation_format)
        result = stage.run(format=fmt)
        if self.project.final_paper:
            out_path = os.path.join(self.output_dir, self.STAGE_OUTPUT_FILES[7])
            with open(out_path, "w", encoding="utf-8") as handle:
                handle.write(self.project.final_paper)
            print(f"[Stage 7] final paper saved: {out_path}")
        return result

    def _ensure_stage_done(self, stage_num: int) -> None:
        """Ensure successful stages do not remain in running/pending state."""

        status = getattr(self.project, f"stage{stage_num}_status")
        if status in {StageStatus.PENDING, StageStatus.RUNNING}:
            self.project.mark_stage_done(stage_num)

    def _skip_stage(self, stage_num: int) -> None:
        """Mark a stage as skipped."""

        if hasattr(self.project, f"stage{stage_num}_status"):
            self.project.mark_stage_skipped(stage_num)

    def _build_result_summary(self, result: Any) -> Dict[str, Any]:
        """Create a compact, serializable summary of stage results."""

        if isinstance(result, dict):
            summary = {}
            for key, value in result.items():
                if isinstance(value, (str, int, float, bool)) or value is None:
                    summary[key] = value
                elif isinstance(value, list):
                    summary[f"{key}_count"] = len(value)
                elif hasattr(value, "nodes") and hasattr(value, "edges"):
                    summary[key] = {
                        "nodes": len(getattr(value, "nodes", [])),
                        "edges": len(getattr(value, "edges", [])),
                    }
                else:
                    summary[key] = type(value).__name__
            return summary
        return {"result_type": type(result).__name__}

    def _artifact_exists(self, stage_num: int, artifact_type: str, path: str) -> bool:
        normalized = os.path.abspath(path)
        for artifact in self.project.artifacts:
            if (
                artifact.get("stage") == stage_num
                and artifact.get("type") == artifact_type
                and os.path.abspath(artifact.get("path", "")) == normalized
            ):
                return True
        return False

    def _register_stage_artifact(self, stage_num: int, artifact_type: str, path: str, label: str) -> None:
        """Register an artifact in project metadata if the file exists."""

        if not path or not os.path.exists(path) or self._artifact_exists(stage_num, artifact_type, path):
            return
        self.project.register_artifact(
            artifact_type,
            stage=stage_num,
            path=os.path.abspath(path),
            source="workflow_orchestrator",
            metadata={"label": label},
        )

    def _register_stage_failure_package(self, stage_num: int, error: str, checkpoint_path: str) -> None:
        """Register failed-stage metadata through the project package protocol."""

        package = {
            "type": "workflow_stage_failure",
            "success": False,
            "confidence": 0.0,
            "needs_review": True,
            "quality_flags": [f"stage{stage_num}_failed"],
            "error": error,
            "summary": f"Stage {stage_num} failed: {error}",
            "artifacts": [
                {
                    "type": "workflow_checkpoint",
                    "path": os.path.abspath(checkpoint_path),
                    "label": f"Stage {stage_num} failed checkpoint",
                    "written": True,
                }
            ],
        }
        summary = self.project.register_package(package, stage=stage_num, source="workflow_orchestrator")
        self.project.set_stage_metadata(stage_num, failure_package=summary)

    def _register_stage_output_artifact(self, stage_num: int) -> None:
        """Register known stage output files."""

        output_name = self.STAGE_OUTPUT_FILES.get(stage_num)
        if not output_name:
            return
        path = os.path.join(self.output_dir, output_name)
        label = f"Stage {stage_num} output"
        self._register_stage_artifact(stage_num, "stage_output", path, label)

    def _save_checkpoint(self, stage_num: Optional[int] = None, label: str = "", suffix: str = "") -> str:
        """Persist a checkpoint and return its absolute path."""

        safe_topic = "".join(char if char.isalnum() else "_" for char in self.project.topic[:20])
        parts = ["project", safe_topic, self.project.id]
        if stage_num is not None:
            parts.append(f"stage{stage_num}")
        if label:
            parts.append(label)
        if suffix:
            parts.append(suffix)
        filename = "_".join(parts) + ".json"
        artifact = self.artifact_manager.write_json_artifact(
            self.project.to_dict(),
            filename,
            artifact_type="workflow_checkpoint",
            stage=stage_num,
            source="workflow_orchestrator",
        )
        return os.path.abspath(artifact["path"])
