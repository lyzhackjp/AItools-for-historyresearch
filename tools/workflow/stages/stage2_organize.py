"""
Stage 2: organize research materials into notes and citations.

This stage now records note-generation and Obsidian-export summaries into the
workflow metadata model.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

_AI_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..")
if _AI_TOOLS not in sys.path:
    sys.path.insert(0, _AI_TOOLS)

from tools.workflow.research_project import PaperRecord, ResearchProject


class Stage2Organize:
    """Stage 2 note generation and citation formatting."""

    NAME = "organize"
    STAGE_NUM = 2

    def __init__(self, project: ResearchProject):
        self.project = project
        self.note_generator = None
        self.book_organizer = None
        self.obsidian_integration = None
        self._review_items: List[Dict[str, Any]] = []
        self._warnings: List[str] = []
        self._note_packages: List[Dict[str, Any]] = []

    def _get_note_generator(self):
        if self.note_generator is None:
            from modules.academic_note_generator import AcademicNoteGenerator

            self.note_generator = AcademicNoteGenerator(api_provider="qwen", test_mode=False)
        return self.note_generator

    def _get_book_organizer(self):
        if self.book_organizer is None:
            from modules.book_citation_organizer import BookCitationOrganizer

            self.book_organizer = BookCitationOrganizer(
                input_dir=".",
                output_dir=self.project.topic[:20] + "_books",
                enable_llm=False,
            )
        return self.book_organizer

    def _get_obsidian_integration(self):
        if self.obsidian_integration is None:
            try:
                from modules.obsidian_integration import ObsidianIntegration

                vault_path = os.path.normpath(
                    os.path.join(
                        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                        "..",
                        "workflow_output",
                        "obsidian_vault",
                    )
                )
                self.obsidian_integration = ObsidianIntegration(vault_path=vault_path)
                print(f"[Stage 2] Obsidian vault ready: {vault_path}")
            except Exception as exc:  # noqa: BLE001
                print(f"[Stage 2] Failed to initialize Obsidian integration: {exc}")
                self.obsidian_integration = None
        return self.obsidian_integration

    def run(self, **kwargs) -> Dict[str, Any]:
        """Run stage 2 note organization."""

        print(f"[Stage 2] Start organizing materials | literature: {len(self.project.literature)}")
        print(f"[Stage 2] Citation format: {self.project.citation_format}")

        self.project.mark_stage_start(self.STAGE_NUM)
        self.project.set_stage_metadata(
            self.STAGE_NUM,
            capability_snapshot={
                "academic_note": "task_manager_academic_note",
                "obsidian_export": "obsidian_integration",
                "citation_format": self.project.citation_format,
            },
        )

        notes = self.generate_notes(self.project.literature)
        self.project.obsidian_notes = notes

        vault_results = self._export_to_obsidian_vault(notes)
        citations = self.format_citations(self.project.literature, format=self.project.citation_format)
        self.project.formatted_citations = citations

        book_notes = []
        if self.project.book_metadata:
            book_notes = self._process_book_metadata()
            print(f"[Stage 2] Book notes: {len(book_notes)}")
            self.project.formatted_citations.extend(
                note.get("citation", "") for note in book_notes if note.get("citation")
            )

        self._flush_review_items()
        book_summary = {
            "total_books": len(book_notes),
            "records_needing_review": sum(1 for note in book_notes if note.get("needs_review")),
            "record_count": sum(1 for note in book_notes if note.get("citation_record")),
        }
        note_summary = {
            "total_notes": len(notes),
            "notes_needing_review": sum(1 for note in notes if note.get("needs_review")),
            "notes_with_entities": sum(1 for note in notes if any(note.get("entities", {}).values())),
        }
        self.project.set_stage_metadata(
            self.STAGE_NUM,
            execution_summary={
                "notes": note_summary,
                "vault_export": vault_results,
                "citations": {"count": len(citations), "format": self.project.citation_format},
                "book_metadata": book_summary,
                "warning_count": len(self._warnings),
                "review_count": len(self._review_items),
                "note_packages": self._note_packages,
            },
            book_citation_records=[
                note.get("citation_record")
                for note in book_notes
                if note.get("citation_record")
            ],
            warnings=self._warnings,
        )

        if vault_results.get("vault_path"):
            self.project.register_artifact(
                "obsidian_vault",
                stage=self.STAGE_NUM,
                path=os.path.abspath(vault_results["vault_path"]),
                source="stage2_organize",
                metadata={"label": "Obsidian vault export"},
            )

        self.project.mark_stage_done(self.STAGE_NUM)

        result = {
            "notes": notes,
            "citations": citations,
            "book_notes": book_notes,
            "total_notes": len(notes) + len(book_notes),
            "obsidian_vault": vault_results,
        }
        print(f"[Stage 2] Done | notes: {len(notes)} | citations: {len(citations)}")
        return result

    def _export_to_obsidian_vault(self, notes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Export note markdown into the managed Obsidian vault."""

        obsidian = self._get_obsidian_integration()
        if obsidian is None:
            self._warnings.append("obsidian_export_unavailable")
            return {}

        print(f"[Stage 2] Export to Obsidian vault: {len(notes)} notes")
        results = {
            "notes_created": 0,
            "links_created": 0,
            "knowledge_graph": {"nodes": 0, "edges": 0},
            "vault_path": str(obsidian.vault_path) if obsidian.vault_path else "",
            "vault_packages": [],
        }

        for note in notes:
            content = note.get("content", "") or note.get("markdown", "")
            if not isinstance(content, str):
                content = str(content)
            if hasattr(obsidian, "create_note_package"):
                package = obsidian.create_note_package(
                    title=note.get("title", "Untitled"),
                    content=content,
                    note_type="reading_note",
                    folder="Literature Notes",
                )
                self._register_stage_package(package, source="obsidian_note_export")
                results["vault_packages"].append(self._summarize_vault_package(package, note))
                ok = bool(package.get("export_summary", {}).get("note_created"))
                if package.get("needs_review"):
                    self._review_items.append(
                        {
                            "stage": self.STAGE_NUM,
                            "type": "obsidian_export_review",
                            "source_id": note.get("id") or note.get("paper_id"),
                            "title": note.get("title", "Untitled"),
                            "message": ", ".join(package.get("quality_flags", [])) or package.get("error", ""),
                        }
                    )
                    self.project.add_quality_flag("stage2_obsidian_export_review_needed")
            else:
                ok, _ = obsidian.create_note(
                    title=note.get("title", "Untitled"),
                    content=content,
                    note_type="reading_note",
                    folder="Literature Notes",
                )
            if ok:
                results["notes_created"] += 1
                results["links_created"] += len(self._extract_links_from_content(content))

        try:
            if hasattr(obsidian, "build_knowledge_graph_package"):
                graph_package = obsidian.build_knowledge_graph_package()
                self._register_stage_package(graph_package, source="obsidian_graph")
                graph_data = {
                    "nodes": graph_package.get("nodes", []),
                    "edges": graph_package.get("edges", []),
                }
                results["graph_package"] = {
                    "type": graph_package.get("type"),
                    "confidence": graph_package.get("confidence"),
                    "needs_review": bool(graph_package.get("needs_review")),
                    "quality_flags": graph_package.get("quality_flags", []),
                    "export_summary": graph_package.get("export_summary", {}),
                }
                if graph_package.get("needs_review") and graph_package.get("quality_flags"):
                    self.project.add_quality_flag("stage2_obsidian_graph_review_needed")
            else:
                graph_data = obsidian.build_knowledge_graph_data()
            results["knowledge_graph"] = {
                "nodes": len(graph_data.get("nodes", [])),
                "edges": len(graph_data.get("edges", [])),
            }
        except Exception as exc:  # noqa: BLE001
            self._warnings.append("obsidian_graph_build_failed")
            print(f"[Stage 2] Knowledge graph build failed: {exc}")

        return results

    def _summarize_vault_package(self, package: Dict[str, Any], note: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "source_id": note.get("id") or note.get("paper_id"),
            "source_title": note.get("title", "Untitled"),
            "type": package.get("type"),
            "backend": package.get("backend"),
            "provider": package.get("provider"),
            "model": package.get("model"),
            "confidence": package.get("confidence"),
            "needs_review": bool(package.get("needs_review")),
            "quality_flags": package.get("quality_flags", []),
            "relative_path": package.get("relative_path", ""),
            "export_summary": package.get("export_summary", {}),
        }

    def _extract_links_from_content(self, content: str) -> List[str]:
        import re

        return list(set(re.findall(r"\[\[([^\]]+)\]\]", content)))

    def generate_notes(self, literature: List[PaperRecord]) -> List[Dict[str, Any]]:
        """Generate structured notes for literature items."""

        if not literature:
            print("[Stage 2] No literature available for notes")
            return []

        print(f"[Stage 2] Generate notes: {len(literature)} papers")
        try:
            generator = self._get_note_generator()
        except Exception as exc:  # noqa: BLE001
            print(f"[Stage 2] Note generator init failed: {exc}")
            self._warnings.append("note_generator_unavailable")
            return self._generate_simple_notes(literature)

        notes = []
        for index, paper in enumerate(literature):
            try:
                text = f"{paper.title}\n\n{paper.abstract or ''}".strip()
                if len(text) < 20:
                    text = paper.title
                metadata = {
                    "title": paper.title,
                    "authors": ", ".join(paper.authors) if paper.authors else "",
                    "year": paper.year,
                    "source": paper.source,
                    "journal": paper.journal or "",
                    "subject_tag": self._guess_subject_tag(),
                }
                if hasattr(generator, "generate_reading_note_package"):
                    package = generator.generate_reading_note_package(text, metadata)
                    self._register_stage_package(package, source="academic_note_generator")
                    self._note_packages.append(self._summarize_note_package(package, paper, index))
                    generated = self._note_payload_from_package(package)
                else:
                    generated = generator.generate_reading_note(text, metadata)
                notes.append(self._normalize_generated_note(paper, generated, index))
            except Exception as exc:  # noqa: BLE001
                print(f"[Stage 2] Note generation failed [{paper.title[:40]}]: {exc}")
                self._warnings.append(f"note_generation_failed:{paper.id or index}")
                notes.append(self._fallback_note_record(paper, index, reason=str(exc)))

            if (index + 1) % 10 == 0:
                print(f"[Stage 2] Note progress: {index + 1}/{len(literature)}")
        return notes

    def _register_stage_package(self, package: Dict[str, Any], source: str) -> None:
        """Register a Stage 2 package through the project-level package protocol."""

        if not isinstance(package, dict):
            return
        self.project.register_package(package, stage=self.STAGE_NUM, source=source)

    def _summarize_note_package(
        self,
        package: Dict[str, Any],
        paper: PaperRecord,
        index: int,
    ) -> Dict[str, Any]:
        return {
            "source_id": paper.id or f"paper_{index}",
            "source_title": paper.title,
            "type": package.get("type"),
            "backend": package.get("backend"),
            "provider": package.get("provider"),
            "model": package.get("model"),
            "confidence": package.get("confidence"),
            "needs_review": bool(package.get("needs_review")),
            "quality_flags": package.get("quality_flags", []),
            "export_summary": package.get("export_summary", {}),
        }

    def _note_payload_from_package(self, package: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": package.get("source_title", "Untitled"),
            "markdown": package.get("markdown", ""),
            "summary": package.get("summary", ""),
            "entities": package.get("entities", {}),
            "keywords": package.get("keywords", []),
            "backend": package.get("backend"),
            "provider": package.get("provider"),
            "model": package.get("model"),
            "needs_review": bool(package.get("needs_review")),
            "review_reason": ", ".join(package.get("quality_flags", [])),
        }

    def _normalize_generated_note(self, paper: PaperRecord, generated: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Normalize generator output into stage note records."""

        markdown = generated.get("markdown")
        if not markdown:
            markdown = generated.get("raw_note_content") or self._fallback_note(paper)

        note = {
            "id": paper.id or f"paper_{index}",
            "title": paper.title,
            "authors": paper.authors,
            "year": paper.year,
            "source": paper.source,
            "content": markdown,
            "paper_id": paper.id,
            "entities": generated.get("entities", {}),
            "keywords": generated.get("keywords", []),
            "backend": generated.get("backend"),
            "provider": generated.get("provider"),
            "model": generated.get("model"),
            "needs_review": bool(generated.get("needs_review")),
        }
        if note["needs_review"]:
            self._review_items.append(
                {
                    "stage": self.STAGE_NUM,
                    "type": "note_review",
                    "source_id": note["id"],
                    "title": note["title"],
                    "backend": note.get("backend"),
                    "provider": note.get("provider"),
                    "model": note.get("model"),
                    "message": generated.get("review_reason", "note generation fallback used"),
                }
            )
            self.project.add_quality_flag("stage2_note_review_needed")
        return note

    def _generate_simple_notes(self, literature: List[PaperRecord]) -> List[Dict[str, Any]]:
        notes = []
        for index, paper in enumerate(literature):
            notes.append(self._fallback_note_record(paper, index, reason="simple_fallback"))
        return notes

    def _fallback_note_record(self, paper: PaperRecord, index: int, reason: str) -> Dict[str, Any]:
        note = {
            "id": paper.id or f"paper_{index}",
            "title": paper.title,
            "authors": paper.authors,
            "year": paper.year,
            "source": paper.source,
            "content": self._fallback_note(paper),
            "paper_id": paper.id,
            "entities": {},
            "keywords": [],
            "backend": "script",
            "provider": "fallback",
            "model": "fallback-note",
            "needs_review": True,
        }
        self._review_items.append(
            {
                "stage": self.STAGE_NUM,
                "type": "note_review",
                "source_id": note["id"],
                "title": note["title"],
                "message": reason,
            }
        )
        self.project.add_quality_flag("stage2_note_review_needed")
        return note

    def _fallback_note(self, paper: PaperRecord) -> str:
        lines = [
            "---",
            "type: reading_note",
            "tags: [#literature_note]",
            "---",
            "",
            f"# {paper.title}",
            "",
            f"**Authors**: {', '.join(paper.authors) if paper.authors else 'Unknown'}",
            f"**Year**: {paper.year or 'Unknown'}",
            f"**Source**: {paper.source or 'Unknown'}",
            f"**Journal**: {paper.journal or 'N/A'}",
            "",
            "## Summary",
            "",
            paper.abstract or "_No abstract available_",
            "",
            "## Key Citation",
            "",
            f"> {paper.title} ({paper.year or 'n.d.'})",
        ]
        return "\n".join(lines)

    def _guess_subject_tag(self) -> str:
        topic = self.project.topic.lower()
        if any(key in topic for key in ["england", "tudor", "victorian"]):
            return "british_history"
        if any(key in topic for key in ["japan", "japanese", "meiji", "edo"]):
            return "japanese_history"
        if any(key in topic for key in ["china", "chinese", "qing", "ming"]):
            return "chinese_history"
        return "history"

    def format_citations(self, literature: List[PaperRecord], format: str = "chicago") -> List[str]:
        if not literature:
            return []

        print(f"[Stage 2] Format citations: {len(literature)} items ({format})")
        citations = []
        for paper in literature:
            try:
                if format == "apa":
                    citation = self._apa_citation(paper)
                elif format == "gb7714":
                    citation = self._gb7714_citation(paper)
                elif format == "mla":
                    citation = self._mla_citation(paper)
                else:
                    citation = self._chicago_citation(paper)
                citations.append(citation)
            except Exception as exc:  # noqa: BLE001
                print(f"[Stage 2] Citation fallback used [{paper.title[:40]}]: {exc}")
                citations.append(self._chicago_citation(paper))
        return citations

    def _chicago_citation(self, paper: PaperRecord) -> str:
        authors = ", ".join(paper.authors) if paper.authors else "Unknown"
        title = f"\"{paper.title}\"" if paper.title else "Unknown"
        journal = paper.journal or ""
        year = paper.year or "n.d."
        url = f" {paper.url}" if paper.url else ""
        doi = f" https://doi.org/{paper.doi}" if paper.doi else ""
        return f"{authors}. {title}. {journal} {year}.{url}{doi}".strip()

    def _apa_citation(self, paper: PaperRecord) -> str:
        authors = ", ".join(paper.authors) if paper.authors else "Unknown"
        return f"{authors} ({paper.year or 'n.d.'}). {paper.title}. {paper.journal or paper.source}."

    def _gb7714_citation(self, paper: PaperRecord) -> str:
        authors = ", ".join(paper.authors) if paper.authors else "Unknown"
        return f"{authors}. {paper.title}[J]. {paper.journal or paper.source}, {paper.year or 'n.d.'}."

    def _mla_citation(self, paper: PaperRecord) -> str:
        authors = ", ".join(paper.authors) if paper.authors else "Unknown"
        return f"{authors}. \"{paper.title}.\" {paper.journal or paper.source}, {paper.year or 'n.d.'}."

    def _process_book_metadata(self) -> List[Dict[str, Any]]:
        """Normalize project book metadata into workflow citation records."""

        try:
            organizer = self._get_book_organizer()
            from modules.book_citation_organizer import BookMetadata as CitationBookMetadata
        except Exception as exc:  # noqa: BLE001
            self._warnings.append(f"book_metadata_processing_failed:{exc}")
            return []

        book_notes: List[Dict[str, Any]] = []
        for index, book in enumerate(self.project.book_metadata):
            try:
                source = book.to_dict() if hasattr(book, "to_dict") else dict(book)
                metadata = CitationBookMetadata(
                    original_filename=source.get("original_filename", ""),
                    new_filename=source.get("new_filename", ""),
                    title=source.get("title", ""),
                    author=source.get("author", ""),
                    publisher=source.get("publisher", ""),
                    publish_year=source.get("year", "") or source.get("publish_year", ""),
                    isbn=source.get("isbn", ""),
                    pages=source.get("pages", ""),
                    edition=source.get("edition", ""),
                )
                if not metadata.new_filename:
                    metadata.new_filename = organizer.generate_citation_filenames(metadata)
                organizer._populate_citations(metadata)
                organizer._finalize_quality(metadata, ["project_book_metadata"])
                citation = metadata.citation_record.get("formatted", {}).get(
                    self.project.citation_format,
                    metadata.citation_chicago,
                )
                note = {
                    "id": source.get("id") or f"book_{index}",
                    "title": metadata.title,
                    "author": metadata.author,
                    "year": metadata.publish_year,
                    "citation": citation,
                    "citation_record": metadata.to_citation_record(),
                    "backend": metadata.backend,
                    "provider": metadata.provider,
                    "model": metadata.model,
                    "confidence": metadata.confidence,
                    "needs_review": metadata.needs_review,
                    "review_notes": list(metadata.review_notes),
                }
                if metadata.needs_review:
                    self._review_items.append(
                        {
                            "stage": self.STAGE_NUM,
                            "type": "book_metadata_review",
                            "source_id": note["id"],
                            "title": note["title"],
                            "message": "; ".join(metadata.review_notes) or "book metadata needs review",
                        }
                    )
                    self.project.add_quality_flag("stage2_book_metadata_review_needed")
                book_notes.append(note)
            except Exception as exc:  # noqa: BLE001
                self._warnings.append(f"book_metadata_record_failed:{index}:{type(exc).__name__}")
        return book_notes

    def _flush_review_items(self) -> None:
        for item in self._review_items:
            self.project.add_review_item(item)
