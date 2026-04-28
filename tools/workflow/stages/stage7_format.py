"""
Stage 7: format citations and assemble the final paper.

This stage now consumes unified citation records, records structured execution
metadata, and registers export artifacts for final outputs.
"""

from __future__ import annotations

import datetime
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

_AI_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..")
if _AI_TOOLS not in sys.path:
    sys.path.insert(0, _AI_TOOLS)

from tools.workflow.research_project import PaperRecord, ResearchProject

_word_exporter = None


def _get_word_exporter():
    global _word_exporter
    if _word_exporter is None:
        try:
            from tools.workflow.word_exporter import export_paper_to_word, export_paper_with_footnotes

            _word_exporter = (export_paper_to_word, export_paper_with_footnotes)
        except Exception as exc:  # noqa: BLE001
            print(f"[Stage 7] Word exporter load failed: {exc}")
            _word_exporter = (None, None)
    return _word_exporter


class Stage7Format:
    """Format final references and export the final paper."""

    NAME = "format"
    STAGE_NUM = 7

    def __init__(self, project: ResearchProject):
        self.project = project
        self.formatter = None
        self.normalizer = None
        self._warnings: List[str] = []
        self._review_items: List[Dict[str, Any]] = []
        self._registered_packages: List[Dict[str, Any]] = []
        self._registered_artifacts: List[Dict[str, Any]] = []
        self._citation_format_package: Dict[str, Any] = {}

    def _get_formatter(self):
        if self.formatter is None:
            from modules.citation_formats import CitationFormatter

            self.formatter = CitationFormatter()
        return self.formatter

    def _get_normalizer(self):
        if self.normalizer is None:
            from modules.citation_normalizer import CitationNormalizer

            self.normalizer = CitationNormalizer(style=self.project.citation_format, test_mode=False)
        return self.normalizer

    def run(self, format: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        source_text, source_kind = self._select_input_text()
        if not source_text:
            print("[Stage 7] No draft available for formatting, skipping")
            self.project.mark_stage_skipped(self.STAGE_NUM)
            return {}

        target_format = format or self.project.citation_format or "chicago"
        print(f"[Stage 7] Start formatting | target format: {target_format}")
        print(f"[Stage 7] Input draft source: {source_kind} | chars: {len(source_text)}")

        self._warnings = []
        self._review_items = []
        self._registered_packages = []
        self._registered_artifacts = []
        self._citation_format_package = {}
        self.project.mark_stage_start(self.STAGE_NUM)
        self.project.set_stage_metadata(
            self.STAGE_NUM,
            capability_snapshot={
                "citation_normalizer": "unified_citation_record",
                "citation_formatter": "citation_formats.format_record",
                "word_export": bool(_get_word_exporter()[0]),
            },
            requested_execution={
                "target_format": target_format,
                "source_draft": source_kind,
            },
        )

        normalized_records = self._normalize_literature(target_format)
        formatted_refs = [record["normalized_citation"] for record in normalized_records]
        self._citation_format_package = self._format_records_package(normalized_records, target_format)
        final_paper, append_meta = self.format_paper(
            source_text,
            normalized_records=normalized_records,
            target_format=target_format,
        )

        self.project.final_paper = final_paper
        self.project.citation_format = target_format
        self.project.formatted_citations = formatted_refs

        word_paths = {}
        try:
            word_paths = self._export_to_word(final_paper, formatted_refs, target_format)
        except Exception as exc:  # noqa: BLE001
            self._warnings.append("word_export_failed")
            print(f"[Stage 7] Word export failed: {exc}")

        self._register_artifacts(word_paths)
        self._flush_review_items()

        records_needing_review = sum(1 for record in normalized_records if record.get("needs_review"))
        if records_needing_review:
            self.project.add_quality_flag("stage7_citation_review_needed")
        if not normalized_records:
            self.project.add_quality_flag("stage7_no_references")

        self.project.set_stage_metadata(
            self.STAGE_NUM,
            normalized_citation_records=[
                {
                    "title": record.get("title"),
                    "year": record.get("year"),
                    "type": record.get("type"),
                    "needs_review": record.get("needs_review"),
                    "confidence": record.get("confidence"),
                    "normalized_citation": record.get("normalized_citation"),
                }
                for record in normalized_records
            ],
            execution_summary={
                "source_draft": source_kind,
                "input_chars": len(source_text),
                "output_chars": len(final_paper),
                "formatted_reference_count": len(formatted_refs),
                "records_needing_review": records_needing_review,
                "appended_references": append_meta["appended_references"],
                "stripped_existing_references": append_meta["stripped_existing_references"],
                "inline_marker_count": append_meta["inline_marker_count"],
                "word_file_count": len(word_paths),
                "warning_count": len(self._warnings),
                "review_count": len(self._review_items),
                "citation_format_package": self._citation_format_package,
            },
            warnings=self._warnings,
            output_artifacts=word_paths,
            package_protocol={
                "registry": "ResearchProject.register_package",
                "registered_package_count": len(self._registered_packages),
                "registered_packages": self._registered_packages,
            },
            artifact_protocol={
                "registry": "ResearchProject.register_artifact",
                "registered_artifact_count": len(self._registered_artifacts),
                "registered_artifacts": self._registered_artifacts,
            },
        )

        self.project.mark_stage_done(self.STAGE_NUM)
        print(f"[Stage 7] Done | final chars: {len(final_paper)} | references: {len(formatted_refs)}")
        return {
            "final_paper": final_paper,
            "formatted_citations": formatted_refs,
            "normalized_records": normalized_records,
            "format": target_format,
            "word_files": word_paths,
        }

    def format_paper(
        self,
        paper_text: str,
        normalized_records: List[Dict[str, Any]],
        target_format: str = "chicago",
    ) -> Tuple[str, Dict[str, Any]]:
        print("[Stage 7] Formatting final paper body and references")
        inline_marker_count = len(re.findall(r"\[[0-9,\-]+\]|\([A-Z][A-Za-z]+,\s*\d{4}\)", paper_text))
        body_text, stripped_existing = self._strip_existing_references_section(paper_text)
        final_text = self._append_references(
            body_text,
            [record["normalized_citation"] for record in normalized_records],
            target_format,
        )
        return final_text, {
            "inline_marker_count": inline_marker_count,
            "stripped_existing_references": stripped_existing,
            "appended_references": bool(normalized_records),
        }

    def format_reference_list(
        self,
        literature: List[PaperRecord],
        target_format: str = "chicago",
    ) -> List[str]:
        records = [self._paper_to_citation_record(paper, target_format, index) for index, paper in enumerate(literature, start=1)]
        return [record["normalized_citation"] for record in records]

    def _format_records_package(
        self,
        normalized_records: List[Dict[str, Any]],
        target_format: str,
    ) -> Dict[str, Any]:
        formatter = self._get_formatter()
        if not hasattr(formatter, "format_batch_package"):
            return {}
        try:
            formatter.reset_index()
            package = formatter.format_batch_package(normalized_records, style=target_format)
            self._register_stage_package(package, source="citation_formatter")
            return {
                "type": package.get("type"),
                "backend": package.get("backend"),
                "provider": package.get("provider"),
                "model": package.get("model"),
                "style": package.get("style"),
                "confidence": package.get("confidence"),
                "needs_review": bool(package.get("needs_review")),
                "quality_flags": package.get("quality_flags", []),
                "summary": package.get("summary", {}),
            }
        except Exception as exc:  # noqa: BLE001
            self._warnings.append("citation_format_package_failed")
            package = {
                "type": "citation_formatting",
                "backend": "script",
                "provider": "rule_templates",
                "model": None,
                "style": target_format,
                "confidence": 0.0,
                "needs_review": True,
                "quality_flags": ["citation_format_package_failed"],
                "summary": {"record_count": len(normalized_records), "rendered_count": 0, "style": target_format},
                "error": str(exc),
            }
            self._register_stage_package(package, source="citation_formatter")
            return package

    def _select_input_text(self) -> Tuple[str, str]:
        if self.project.style_transferred_draft:
            return self.project.style_transferred_draft, "style_transferred_draft"
        if self.project.polished_draft:
            return self.project.polished_draft, "polished_draft"
        if self.project.paper_draft:
            return self.project.paper_draft, "paper_draft"
        return "", ""

    def _normalize_literature(self, target_format: str) -> List[Dict[str, Any]]:
        stage2_records = self._get_stage2_citation_records()
        if not self.project.literature and not stage2_records:
            self._warnings.append("no_sources_for_formatting")
            return []

        records: List[Dict[str, Any]] = []
        for index, paper in enumerate(self.project.literature, start=1):
            record = self._paper_to_citation_record(paper, target_format, index)
            records.append(record)
            if record.get("needs_review"):
                self._review_items.append(
                    {
                        "stage": self.STAGE_NUM,
                        "type": "citation_record_review",
                        "message": f"Citation record for '{paper.title or paper.id}' needs manual review.",
                        "title": record.get("title"),
                        "confidence": record.get("confidence"),
                    }
                )
        for offset, source_record in enumerate(stage2_records, start=len(records) + 1):
            record = self._format_existing_citation_record(source_record, target_format, offset)
            records.append(record)
            if record.get("needs_review"):
                self._review_items.append(
                    {
                        "stage": self.STAGE_NUM,
                        "type": "citation_record_review",
                        "message": f"Stage 2 citation record for '{record.get('title')}' needs manual review.",
                        "title": record.get("title"),
                        "confidence": record.get("confidence"),
                    }
                )
        return records

    def _get_stage2_citation_records(self) -> List[Dict[str, Any]]:
        metadata = self.project.get_stage_metadata(2)
        records = metadata.get("book_citation_records", [])
        return [record for record in records if isinstance(record, dict)]

    def _format_existing_citation_record(
        self,
        record: Dict[str, Any],
        target_format: str,
        index: int,
    ) -> Dict[str, Any]:
        normalized = dict(record)
        authors = normalized.get("authors") or normalized.get("author") or []
        if isinstance(authors, str):
            authors = [item.strip() for item in authors.split(",") if item.strip()]
        normalized["authors"] = authors
        normalized["author"] = self._join_authors(authors)
        normalized.setdefault("type", normalized.get("record_type") or "book")
        normalized.setdefault("title", "Untitled")
        normalized.setdefault("year", "")
        normalized.setdefault("journal_or_publisher", normalized.get("publisher", ""))
        normalized.setdefault("backend", "script")
        normalized.setdefault("provider", "stage2_citation_record")
        normalized.setdefault("model", None)
        validation = self._get_normalizer().validate_fields(normalized)
        normalized["validation"] = validation
        normalized["needs_review"] = bool(validation["missing_fields"]) or bool(normalized.get("needs_review"))
        normalized["confidence"] = float(normalized.get("confidence", 0.7) or 0.0)
        normalized["normalized_citation"] = self._get_formatter().format_record(
            normalized,
            style=target_format,
            index=index,
        )
        normalized["target_style"] = target_format
        return normalized

    def _paper_to_citation_record(
        self,
        paper: PaperRecord,
        target_format: str,
        index: int,
    ) -> Dict[str, Any]:
        raw_citation = self._paper_to_raw_citation(paper)
        record = self._get_normalizer().normalize_record(raw_citation, target_style=target_format, index=index)
        authors = list(paper.authors or record.get("authors") or [])
        container = paper.journal or paper.source or record.get("journal_or_publisher") or ""
        record_type = "article" if (paper.journal or paper.doi) else "electronic" if paper.url else "book"

        record.update(
            {
                "title": paper.title or record.get("title") or "Untitled",
                "authors": authors,
                "author": self._join_authors(authors),
                "year": paper.year or record.get("year") or "",
                "journal_or_publisher": container,
                "journal": paper.journal or (container if record_type == "article" else ""),
                "publisher": "" if record_type == "article" else container,
                "source": paper.source,
                "doi": paper.doi or record.get("doi") or "",
                "url": paper.url or record.get("url") or "",
                "type": record_type,
            }
        )

        validation = self._get_normalizer().validate_fields(record)
        record["validation"] = validation
        record["needs_review"] = bool(validation["missing_fields"]) or bool(record.get("needs_review"))
        if paper.title and authors and paper.year:
            record["confidence"] = max(float(record.get("confidence", 0.0)), 0.78)
        record["normalized_citation"] = self._get_formatter().format_record(record, style=target_format, index=index)
        return record

    def _paper_to_raw_citation(self, paper: PaperRecord) -> str:
        authors = self._join_authors(paper.authors)
        title = paper.title or "Untitled"
        container = paper.journal or paper.source or ""
        year = paper.year or "n.d."
        pieces = [authors, f"\"{title}.\""]
        if container:
            pieces.append(container)
        pieces.append(year)
        if paper.doi:
            pieces.append(f"https://doi.org/{paper.doi}")
        elif paper.url:
            pieces.append(paper.url)
        return ". ".join(piece.strip(" .") for piece in pieces if piece).strip() + "."

    def _append_references(self, paper_text: str, refs: List[str], fmt: str) -> str:
        del fmt
        if not refs:
            return paper_text

        header = {
            "en": "\n\n## References\n\n",
            "ja": "\n\n## 参考文献\n\n",
            "zh": "\n\n## 参考文献\n\n",
        }.get(self.project.language[:2].lower(), "\n\n## References\n\n")
        ref_lines = [f"{index}. {ref}" for index, ref in enumerate(refs, start=1)]
        return paper_text.rstrip() + header + "\n".join(ref_lines)

    def _strip_existing_references_section(self, paper_text: str) -> Tuple[str, bool]:
        pattern = re.compile(r"(?is)\n{0,2}(##\s*(references|参考文献)\s*\n.*)$")
        match = pattern.search(paper_text)
        if not match:
            return paper_text.rstrip(), False
        return paper_text[: match.start()].rstrip(), True

    def _export_to_word(self, final_paper: str, formatted_refs: List[str], fmt: str) -> Dict[str, str]:
        print("[Stage 7] Exporting Word outputs")
        export_fn, export_fn_with_footnotes = _get_word_exporter()
        if export_fn is None:
            return {}

        paths: Dict[str, str] = {}
        out_dir = os.path.join(_AI_TOOLS, "workflow_output")
        os.makedirs(out_dir, exist_ok=True)
        safe = "".join(char if char.isalnum() else "_" for char in self.project.topic[:20])
        stamp = datetime.datetime.now().strftime("%Y%m%d")
        base = f"{safe}_{stamp}"

        title_match = re.match(r"^#\s+(.+)$", final_paper)
        title = title_match.group(1).strip() if title_match else self.project.topic

        markdown_path = os.path.join(out_dir, f"{base}.docx")
        export_fn(
            final_paper,
            output_path=markdown_path,
            language=self.project.language,
            title=title,
            citation_format=fmt,
        )
        if os.path.exists(markdown_path):
            paths["markdown_docx"] = markdown_path

        if formatted_refs and export_fn_with_footnotes:
            footnotes_path = os.path.join(out_dir, f"{base}_footnotes.docx")
            export_fn_with_footnotes(
                final_paper,
                footnotes=[{"id": str(index), "text": ref} for index, ref in enumerate(formatted_refs, start=1)],
                output_path=footnotes_path,
                language=self.project.language,
                title=title,
            )
            if os.path.exists(footnotes_path):
                paths["footnotes_docx"] = footnotes_path
        return paths

    def _register_artifacts(self, word_paths: Dict[str, str]) -> None:
        for label, path in word_paths.items():
            if not path or not os.path.exists(path):
                continue
            artifact = self.project.register_artifact(
                "word_export",
                stage=self.STAGE_NUM,
                path=os.path.abspath(path),
                source="stage7_format",
                metadata={
                    "label": label,
                    "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
                },
            )
            self._registered_artifacts.append(artifact)

    def _flush_review_items(self) -> None:
        for item in self._review_items:
            self.project.add_review_item(item)

    def _register_stage_package(self, package: Optional[Dict[str, Any]], *, source: str) -> None:
        if not isinstance(package, dict):
            return
        summary = self.project.register_package(package, stage=self.STAGE_NUM, source=source)
        self._registered_packages.append(summary)

    def _join_authors(self, authors: List[str]) -> str:
        cleaned = [author.strip() for author in authors if author and author.strip()]
        if not cleaned:
            return "Unknown"
        if len(cleaned) == 1:
            return cleaned[0]
        return ", ".join(cleaned)
