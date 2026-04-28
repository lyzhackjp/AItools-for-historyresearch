"""
Stage 5: draft the paper.

This stage now records a structured draft snapshot and review signals back into
the workflow project metadata.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, List

_AI_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..")
if _AI_TOOLS not in sys.path:
    sys.path.insert(0, _AI_TOOLS)

from tools.workflow.research_project import ResearchProject


class Stage5Write:
    """Draft the paper from collected literature and stage-1 exploration."""

    NAME = "write"
    STAGE_NUM = 5

    def __init__(self, project: ResearchProject, explorer=None):
        self.project = project
        self.explorer = explorer
        self._warnings: List[str] = []
        self._review_items: List[Dict[str, Any]] = []
        self._draft_package_summary: Dict[str, Any] = {}
        self._draft_package: Dict[str, Any] = {}

    def _get_or_create_explorer(self):
        if self.explorer is None:
            from modules.history_field_explorer import create_explorer

            self.explorer = create_explorer(language=self.project.language, test_mode=False)
        return self.explorer

    def run(self, topic: str = "", style: str = "academic_history") -> str:
        topic = topic or self.project.topic
        print(f"[Stage 5] Start draft generation: {topic}")
        print(f"[Stage 5] Language: {self.project.language} | Bilingual: {self.project.bilingual} | Style: {style}")

        self.project.mark_stage_start(self.STAGE_NUM)
        self.project.set_stage_metadata(
            self.STAGE_NUM,
            requested_execution={
                "topic": topic,
                "style": style,
                "language": self.project.language,
                "bilingual": self.project.bilingual,
            },
            source_snapshot=self._build_source_snapshot(),
        )

        explorer = self._get_or_create_explorer()
        if not getattr(getattr(explorer, "report", None), "search_results_count", 0):
            print("[Stage 5] Stage 1 data not ready, running exploration first")
            explorer.explore(topic, search_limit=40)

        if hasattr(explorer, "draft_paper_package"):
            package = explorer.draft_paper_package(
                topic=topic,
                language=self.project.language,
                bilingual=self.project.bilingual,
                style=style,
            )
            result = package.get("draft", {})
            self._draft_package = package
            self._draft_package_summary = self._summarize_draft_package(package)
            if package.get("needs_review"):
                self.project.add_quality_flag("stage5_field_draft_review_needed")
        else:
            result = explorer.draft_paper(
                topic=topic,
                language=self.project.language,
                bilingual=self.project.bilingual,
                style=style,
            )
            self._draft_package_summary = {}
            self._draft_package = {}

        paper_text = result.get("full_text", "") or ""
        self.project.paper_draft = paper_text
        self._record_draft_metadata(paper_text, style=style)
        self._register_draft_packages()
        self._flush_review_items()
        self.project.mark_stage_done(self.STAGE_NUM)

        print(f"[Stage 5] Done | draft length: {len(paper_text)} chars")
        return paper_text

    def save_paper(self, path: str = "") -> str:
        if not self.project.paper_draft:
            print("[Stage 5] No draft available to save")
            return ""

        import datetime

        if not path:
            stamp = datetime.datetime.now().strftime("%Y-%m-%d")
            safe_topic = "".join(char if char.isalnum() else "_" for char in self.project.topic[:20])
            path = f"paper_{safe_topic}_{stamp}.md"

        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.project.paper_draft)
        print(f"[Stage 5] Draft saved: {path}")
        return path

    def _record_draft_metadata(self, paper_text: str, style: str) -> None:
        char_count = len(paper_text)
        paragraph_count = len([part for part in re.split(r"\n\s*\n", paper_text) if part.strip()])
        heading_count = len(
            re.findall(
                r"(?im)^(#+\s+.+|第[一二三四五六七八九十0-9]+[章节].+|[一二三四五六七八九十]+、.+|abstract|introduction|conclusion|references|参考文献)$",
                paper_text,
            )
        )
        citation_placeholder_count = len(re.findall(r"\[[0-9,\-]+\]|\([A-Z][A-Za-z]+,\s*\d{4}\)", paper_text))
        reference_section_present = bool(re.search(r"(?im)^(references|参考文献)\s*$", paper_text))
        source_snapshot = self._build_source_snapshot()
        summary = {
            "char_count": char_count,
            "paragraph_count": paragraph_count,
            "heading_count": heading_count,
            "citation_placeholder_count": citation_placeholder_count,
            "reference_section_present": reference_section_present,
            "literature_count": len(self.project.literature),
            "source_record_count": source_snapshot["source_record_count"],
            "book_citation_record_count": source_snapshot["book_citation_record_count"],
            "note_count": source_snapshot["note_count"],
            "entity_count": source_snapshot["entity_count"],
            "style": style,
        }
        if self._draft_package_summary:
            summary["draft_package"] = self._draft_package_summary

        if char_count < 2000:
            self._warnings.append("draft_too_short")
            self.project.add_quality_flag("stage5_draft_too_short")
            self._review_items.append(
                {
                    "stage": self.STAGE_NUM,
                    "type": "draft_length",
                    "message": "Stage 5 draft is short and should be reviewed before polishing.",
                }
            )
        if heading_count < 2:
            self._warnings.append("draft_structure_weak")
            self.project.add_quality_flag("stage5_structure_review_needed")
            self._review_items.append(
                {
                    "stage": self.STAGE_NUM,
                    "type": "draft_structure",
                    "message": "Draft has very few detectable sections.",
                }
            )
        if citation_placeholder_count == 0:
            self._warnings.append("draft_missing_citation_placeholders")
            self._review_items.append(
                {
                    "stage": self.STAGE_NUM,
                    "type": "draft_citations",
                    "message": "Draft does not contain detectable citation placeholders.",
                }
            )
        if source_snapshot["source_record_count"] == 0:
            self._warnings.append("draft_generated_without_source_records")
            self.project.add_quality_flag("stage5_no_source_records")
            self._review_items.append(
                {
                    "stage": self.STAGE_NUM,
                    "type": "draft_sources",
                    "message": "Draft was generated without unified source records.",
                }
            )

        self.project.set_stage_metadata(
            self.STAGE_NUM,
            execution_summary=summary,
            source_snapshot=source_snapshot,
            warnings=self._warnings,
        )

    def _register_draft_packages(self) -> None:
        metadata = self.project.get_stage_metadata(self.STAGE_NUM)
        execution_summary = metadata.get("execution_summary", {})
        quality_flags = list(self._warnings)
        if self._draft_package:
            self.project.register_package(
                self._draft_package,
                stage=self.STAGE_NUM,
                source="history_field_explorer",
            )
        draft_package = {
            "type": "paper_draft",
            "success": bool(self.project.paper_draft),
            "backend": self._draft_package_summary.get("backend", "script"),
            "provider": self._draft_package_summary.get("provider", "stage5_write"),
            "model": self._draft_package_summary.get("model"),
            "confidence": 0.85 if not quality_flags else max(0.35, 0.85 - 0.08 * len(set(quality_flags))),
            "needs_review": bool(quality_flags),
            "quality_flags": sorted(set(quality_flags)),
            "summary": {
                key: execution_summary.get(key)
                for key in (
                    "char_count",
                    "paragraph_count",
                    "heading_count",
                    "citation_placeholder_count",
                    "reference_section_present",
                    "source_record_count",
                    "book_citation_record_count",
                    "note_count",
                    "entity_count",
                    "style",
                )
            },
            "artifacts": [],
        }
        self.project.register_package(draft_package, stage=self.STAGE_NUM, source="stage5_write")

    def _build_source_snapshot(self) -> Dict[str, Any]:
        stage2_metadata = self.project.get_stage_metadata(2)
        stage3_metadata = self.project.get_stage_metadata(3)
        stage3_execution = stage3_metadata.get("execution_summary", {})
        ner_packages = [
            package
            for package in stage3_execution.get("packages", [])
            if isinstance(package, dict) and package.get("type") == "ner_extraction"
        ]
        book_records = [
            record
            for record in stage2_metadata.get("book_citation_records", [])
            if isinstance(record, dict)
        ]
        literature_records = [
            {
                "id": paper.id,
                "title": paper.title,
                "authors": paper.authors,
                "year": paper.year,
                "source": paper.source,
                "doi": paper.doi,
                "url": paper.url,
                "type": "literature",
            }
            for paper in self.project.literature
        ]
        source_records = literature_records + book_records
        return {
            "source_record_count": len(source_records),
            "literature_record_count": len(literature_records),
            "book_citation_record_count": len(book_records),
            "note_count": len(self.project.obsidian_notes),
            "entity_count": len(self.project.entities),
            "relation_count": len(self.project.entity_relations),
            "formatted_citation_count": len(self.project.formatted_citations),
            "records_needing_review": sum(1 for record in book_records if record.get("needs_review")),
            "ner_package_count": len(ner_packages),
            "ner_packages_needing_review": sum(1 for package in ner_packages if package.get("needs_review")),
            "ner_backends": sorted({package.get("backend") or "unknown" for package in ner_packages}),
            "ner_quality_flags": sorted(
                {
                    flag
                    for package in ner_packages
                    for flag in package.get("quality_flags", [])
                    if flag
                }
            ),
            "sample_titles": [
                record.get("title", "")
                for record in source_records[:5]
                if record.get("title")
            ],
        }

    def _summarize_draft_package(self, package: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": package.get("type"),
            "backend": package.get("backend"),
            "provider": package.get("provider"),
            "model": package.get("model"),
            "confidence": package.get("confidence"),
            "needs_review": bool(package.get("needs_review")),
            "quality_flags": package.get("quality_flags", []),
            "export_summary": package.get("export_summary", {}),
        }

    def _flush_review_items(self) -> None:
        for item in self._review_items:
            self.project.add_review_item(item)
