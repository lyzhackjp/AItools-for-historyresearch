"""
Unified workflow data models for the historical research pipeline.

This module defines the project-wide data structure shared across stages 1-7.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class StageStatus(Enum):
    """Execution status for each workflow stage."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PaperRecord:
    """Single literature record produced by stage 1."""

    id: str = ""
    title: str = ""
    authors: List[str] = field(default_factory=list)
    year: str = ""
    source: str = ""
    url: str = ""
    doi: str = ""
    abstract: str = ""
    journal: str = ""
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PaperRecord":
        return cls(**{key: value for key, value in data.items() if key in cls.__annotations__})


@dataclass
class BookMetadata:
    """Book metadata produced by stage 2."""

    id: str = ""
    title: str = ""
    author: str = ""
    publisher: str = ""
    year: str = ""
    isbn: str = ""
    pages: str = ""
    edition: str = ""
    original_filename: str = ""
    new_filename: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HistoricalEntity:
    """Historical entity produced by stage 3."""

    id: str = ""
    name: str = ""
    name_zh: str = ""
    category: str = ""
    confidence: float = 0.0
    notes: str = ""
    related_entities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EntityRelation:
    """Relationship between historical entities."""

    from_entity: str = ""
    to_entity: str = ""
    relation_type: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CitationNetwork:
    """Citation graph produced by stage 4."""

    nodes: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, str]] = field(default_factory=list)
    key_source_ids: List[str] = field(default_factory=list)
    orphan_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OutlineReview:
    """Structured outline review report."""

    section_word_counts: Dict[str, int] = field(default_factory=dict)
    section_ratios: Dict[str, float] = field(default_factory=dict)
    logical_gaps: List[str] = field(default_factory=list)
    deviation_flags: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StageResult:
    """Recorded execution result for one stage."""

    stage: int
    name: str
    status: StageStatus
    output: Any = None
    error: Optional[str] = None
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "name": self.name,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass
class ResearchProject:
    """
    End-to-end project state shared by all workflow stages.

    The shape is intentionally serializable so the workflow can resume safely.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    topic: str = ""
    language: str = "en"
    bilingual: bool = True
    citation_format: str = "chicago"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = ""

    stage1_status: StageStatus = StageStatus.PENDING
    literature: List[PaperRecord] = field(default_factory=list)

    stage2_status: StageStatus = StageStatus.PENDING
    book_metadata: List[BookMetadata] = field(default_factory=list)
    obsidian_notes: List[Dict[str, Any]] = field(default_factory=list)
    formatted_citations: List[str] = field(default_factory=list)

    stage3_status: StageStatus = StageStatus.PENDING
    entities: List[HistoricalEntity] = field(default_factory=list)
    entity_relations: List[EntityRelation] = field(default_factory=list)

    stage4_status: StageStatus = StageStatus.PENDING
    citation_network: Optional[CitationNetwork] = None
    key_source_ids: List[str] = field(default_factory=list)

    stage5_status: StageStatus = StageStatus.PENDING
    paper_draft: str = ""

    stage6_status: StageStatus = StageStatus.PENDING
    polished_draft: str = ""
    style_transferred_draft: str = ""
    outline_review: Optional[OutlineReview] = None

    stage7_status: StageStatus = StageStatus.PENDING
    final_paper: str = ""

    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    quality_flags: List[str] = field(default_factory=list)
    review_queue: List[Dict[str, Any]] = field(default_factory=list)
    stage_metadata: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    _stage_history: List[StageResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable project snapshot."""

        return {
            "id": self.id,
            "topic": self.topic,
            "language": self.language,
            "bilingual": self.bilingual,
            "citation_format": self.citation_format,
            "created_at": self.created_at,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "literature": [item.to_dict() for item in self.literature],
            "book_metadata": [item.to_dict() for item in self.book_metadata],
            "obsidian_notes": self.obsidian_notes,
            "formatted_citations": self.formatted_citations,
            "entities": [item.to_dict() for item in self.entities],
            "entity_relations": [item.to_dict() for item in self.entity_relations],
            "citation_network": self.citation_network.to_dict() if self.citation_network else None,
            "key_source_ids": self.key_source_ids,
            "paper_draft": self.paper_draft,
            "polished_draft": self.polished_draft,
            "style_transferred_draft": self.style_transferred_draft,
            "outline_review": self.outline_review.to_dict() if self.outline_review else None,
            "final_paper": self.final_paper,
            "artifacts": self.artifacts,
            "quality_flags": self.quality_flags,
            "review_queue": self.review_queue,
            "stage_metadata": self.stage_metadata,
            "stage_status": {
                "stage1": self.stage1_status.value,
                "stage2": self.stage2_status.value,
                "stage3": self.stage3_status.value,
                "stage4": self.stage4_status.value,
                "stage5": self.stage5_status.value,
                "stage6": self.stage6_status.value,
                "stage7": self.stage7_status.value,
            },
        }

    def save(self, path: str) -> None:
        """Persist the project to JSON for resume/replay."""

        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "ResearchProject":
        """Restore a project from JSON."""

        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        project = cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            topic=data.get("topic", ""),
            language=data.get("language", "en"),
            bilingual=data.get("bilingual", True),
            citation_format=data.get("citation_format", "chicago"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
        project.literature = [PaperRecord.from_dict(item) for item in data.get("literature", [])]
        project.book_metadata = [BookMetadata(**item) for item in data.get("book_metadata", [])]
        project.obsidian_notes = list(data.get("obsidian_notes", []))
        project.formatted_citations = list(data.get("formatted_citations", []))
        project.entities = [HistoricalEntity(**item) for item in data.get("entities", [])]
        project.entity_relations = [EntityRelation(**item) for item in data.get("entity_relations", [])]

        citation_network = data.get("citation_network")
        if citation_network:
            project.citation_network = CitationNetwork(**citation_network)

        project.key_source_ids = list(data.get("key_source_ids", []))
        project.paper_draft = data.get("paper_draft", "")
        project.polished_draft = data.get("polished_draft", "")
        project.style_transferred_draft = data.get("style_transferred_draft", "")

        outline_review = data.get("outline_review")
        if outline_review:
            project.outline_review = OutlineReview(**outline_review)

        project.final_paper = data.get("final_paper", "")
        project.artifacts = list(data.get("artifacts", []))
        project.quality_flags = list(data.get("quality_flags", []))
        project.review_queue = list(data.get("review_queue", []))
        project.stage_metadata = dict(data.get("stage_metadata", {}))

        status_map = {
            "pending": StageStatus.PENDING,
            "running": StageStatus.RUNNING,
            "done": StageStatus.DONE,
            "failed": StageStatus.FAILED,
            "skipped": StageStatus.SKIPPED,
        }
        for key, value in data.get("stage_status", {}).items():
            stage_num = int(key.replace("stage", ""))
            setattr(project, f"stage{stage_num}_status", status_map.get(value, StageStatus.PENDING))
        return project

    def mark_stage_start(self, stage: int) -> None:
        """Mark a stage as running and initialize its metadata."""

        setattr(self, f"stage{stage}_status", StageStatus.RUNNING)
        self.updated_at = datetime.now().isoformat(timespec="seconds")
        metadata = self.stage_metadata.setdefault(f"stage{stage}", {})
        metadata["started_at"] = self.updated_at
        metadata["status"] = StageStatus.RUNNING.value

    def mark_stage_done(self, stage: int) -> None:
        """Mark a stage as completed."""

        setattr(self, f"stage{stage}_status", StageStatus.DONE)
        self.updated_at = datetime.now().isoformat(timespec="seconds")
        metadata = self.stage_metadata.setdefault(f"stage{stage}", {})
        metadata["finished_at"] = self.updated_at
        metadata["status"] = StageStatus.DONE.value

    def mark_stage_failed(self, stage: int, error: str) -> None:
        """Mark a stage as failed and record the error summary."""

        setattr(self, f"stage{stage}_status", StageStatus.FAILED)
        self.updated_at = datetime.now().isoformat(timespec="seconds")
        metadata = self.stage_metadata.setdefault(f"stage{stage}", {})
        metadata["finished_at"] = self.updated_at
        metadata["status"] = StageStatus.FAILED.value
        metadata["error"] = error

    def mark_stage_skipped(self, stage: int = 6) -> None:
        """Mark a stage as skipped."""

        setattr(self, f"stage{stage}_status", StageStatus.SKIPPED)
        self.updated_at = datetime.now().isoformat(timespec="seconds")
        metadata = self.stage_metadata.setdefault(f"stage{stage}", {})
        metadata["finished_at"] = self.updated_at
        metadata["status"] = StageStatus.SKIPPED.value

    def set_stage_metadata(self, stage: int, **metadata: Any) -> Dict[str, Any]:
        """Merge structured stage metadata into the project."""

        stage_data = self.stage_metadata.setdefault(f"stage{stage}", {})
        stage_data.update(metadata)
        self.updated_at = datetime.now().isoformat(timespec="seconds")
        return stage_data

    def get_stage_metadata(self, stage: int) -> Dict[str, Any]:
        """Return stage metadata if present."""

        return self.stage_metadata.get(f"stage{stage}", {})

    def add_artifact(self, artifact: Dict[str, Any]) -> None:
        """Attach a structured artifact descriptor to the project."""

        payload = dict(artifact)
        payload.setdefault("id", str(uuid.uuid4())[:8])
        payload.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
        self.artifacts.append(payload)
        stage = payload.get("stage")
        if stage is not None:
            metadata = self.stage_metadata.setdefault(f"stage{stage}", {})
            metadata.setdefault("artifact_ids", []).append(payload["id"])
        self.updated_at = datetime.now().isoformat(timespec="seconds")

    def add_quality_flag(self, flag: str) -> None:
        """Record a project-level quality flag once."""

        if flag and flag not in self.quality_flags:
            self.quality_flags.append(flag)
            self.updated_at = datetime.now().isoformat(timespec="seconds")

    def add_quality_flags(self, flags: List[str]) -> None:
        """Record multiple project-level quality flags."""

        for flag in flags:
            self.add_quality_flag(flag)

    def add_review_item(self, item: Dict[str, Any]) -> None:
        """Add a structured manual review item."""

        payload = dict(item)
        payload.setdefault("id", str(uuid.uuid4())[:8])
        payload.setdefault("status", "open")
        payload.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
        self.review_queue.append(payload)
        stage = payload.get("stage")
        if stage is not None:
            metadata = self.stage_metadata.setdefault(f"stage{stage}", {})
            metadata.setdefault("review_item_ids", []).append(payload["id"])
        self.updated_at = datetime.now().isoformat(timespec="seconds")

    def register_artifact(
        self,
        artifact_type: str,
        *,
        stage: Optional[int] = None,
        path: Optional[str] = None,
        source: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create and attach a normalized artifact descriptor."""

        artifact = {
            "type": artifact_type,
            "stage": stage,
            "path": path,
            "source": source,
            "metadata": metadata or {},
        }
        self.add_artifact({key: value for key, value in artifact.items() if value is not None})
        return self.artifacts[-1]

    def _coerce_artifact_items(self, artifacts: Any) -> List[Dict[str, Any]]:
        if isinstance(artifacts, list):
            return [dict(item) for item in artifacts if isinstance(item, dict)]
        if isinstance(artifacts, dict):
            items: List[Dict[str, Any]] = []
            for name, value in artifacts.items():
                if isinstance(value, dict):
                    item = dict(value)
                    item.setdefault("type", name)
                    items.append(item)
                else:
                    items.append({"type": name, "value": value})
            return items
        return []

    def register_package(
        self,
        package: Dict[str, Any],
        *,
        stage: Optional[int] = None,
        source: str = "",
    ) -> Dict[str, Any]:
        """Attach package artifacts, quality flags, and review state to the project."""

        package_type = str(package.get("type", "package"))
        flags = [str(flag) for flag in package.get("quality_flags", []) if flag]
        needs_review = bool(package.get("needs_review")) or bool(flags)
        confidence = package.get("confidence")

        artifact_count = 0
        for artifact in self._coerce_artifact_items(package.get("artifacts", [])):
            payload = {
                **artifact,
                "stage": artifact.get("stage", stage),
                "source": artifact.get("source", source or package_type),
                "package_type": package_type,
            }
            self.add_artifact(payload)
            artifact_count += 1

        self.add_quality_flags(flags)
        if needs_review:
            self.add_review_item(
                {
                    "stage": stage,
                    "type": "package_review",
                    "package_type": package_type,
                    "source": source,
                    "confidence": confidence,
                    "quality_flags": flags,
                    "summary": package.get("summary") or package.get("error") or "",
                }
            )

        summary = {
            "type": package_type,
            "stage": stage,
            "source": source,
            "success": bool(package.get("success", True)),
            "confidence": confidence,
            "needs_review": needs_review,
            "quality_flags": flags,
            "artifact_count": artifact_count,
        }
        if stage is not None:
            metadata = self.stage_metadata.setdefault(f"stage{stage}", {})
            metadata.setdefault("packages", []).append(summary)
        self.updated_at = datetime.now().isoformat(timespec="seconds")
        return summary

    def get_artifact_summary(self) -> Dict[str, Any]:
        """Return artifact counts suitable for reports and checkpoints."""

        by_type: Dict[str, int] = {}
        by_stage: Dict[str, int] = {}
        for artifact in self.artifacts:
            artifact_type = str(artifact.get("type", "unknown"))
            by_type[artifact_type] = by_type.get(artifact_type, 0) + 1
            if artifact.get("stage") is not None:
                stage_key = f"stage{artifact['stage']}"
                by_stage[stage_key] = by_stage.get(stage_key, 0) + 1
        return {
            "total_artifacts": len(self.artifacts),
            "by_type": by_type,
            "by_stage": by_stage,
        }

    def get_quality_summary(self) -> Dict[str, Any]:
        """Return project quality and review status in one compact shape."""

        open_review_count = sum(1 for item in self.review_queue if item.get("status", "open") == "open")
        return {
            "quality_flags": list(self.quality_flags),
            "quality_flag_count": len(self.quality_flags),
            "review_queue_count": len(self.review_queue),
            "open_review_count": open_review_count,
            "artifact_summary": self.get_artifact_summary(),
        }

    def summary(self) -> str:
        """Return a compact status summary."""

        lines = [
            f"ResearchProject({self.id}) - {self.topic}",
            f"  Language: {self.language} | Bilingual: {self.bilingual}",
            f"  Stage 1 (Collect): {self.stage1_status.value} - {len(self.literature)} papers",
            f"  Stage 2 (Organize): {self.stage2_status.value}",
            f"  Stage 3 (Extract): {self.stage3_status.value} - {len(self.entities)} entities",
            f"  Stage 4 (Examine): {self.stage4_status.value}",
            f"  Stage 5 (Write): {self.stage5_status.value} - {len(self.paper_draft)} chars",
            f"  Stage 6 (Polish): {self.stage6_status.value}",
            f"  Stage 7 (Format): {self.stage7_status.value}",
            f"  Review queue: {len(self.review_queue)} | Artifacts: {len(self.artifacts)}",
        ]
        return "\n".join(lines)
