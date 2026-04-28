"""
Stage 4: examine sources via citation-network analysis and outline review.

This stage now records structured execution summaries and quality flags back
into the workflow project metadata.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

_AI_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..")
if _AI_TOOLS not in sys.path:
    sys.path.insert(0, _AI_TOOLS)

from tools.workflow.research_project import CitationNetwork, OutlineReview, PaperRecord, ResearchProject


class Stage4Examine:
    """Stage 4 citation-network and outline-review workflow."""

    NAME = "examine"
    STAGE_NUM = 4

    def __init__(self, project: ResearchProject):
        self.project = project
        self.cna = None
        self.roa = None
        self._warnings: List[str] = []
        self._review_items: List[Dict[str, Any]] = []

    def _get_citation_analyzer(self):
        """Create the citation-network analyzer lazily."""

        if self.cna is None:
            from modules.citation_network_analyzer import CitationNetworkAnalyzer

            self.cna = CitationNetworkAnalyzer()
        return self.cna

    def _get_outline_analyzer(self):
        """Create the outline analyzer lazily."""

        if self.roa is None:
            from modules.reverse_outline_analyzer import ReverseOutlineAnalyzer

            self.roa = ReverseOutlineAnalyzer(api_provider="qwen", test_mode=False)
        return self.roa

    def run(self, **kwargs) -> Dict[str, Any]:
        """Run stage 4 and write structured metadata into the project."""

        del kwargs  # reserved for future stage-specific options
        print("[Stage 4] Start source examination")
        stage2_records = self._get_stage2_citation_records()
        print(f"[Stage 4] Literature: {len(self.project.literature)}")
        print(f"[Stage 4] Stage 2 citation records: {len(stage2_records)}")

        self.project.mark_stage_start(self.STAGE_NUM)
        citation_capabilities = self._get_citation_analyzer().get_capabilities()
        self.project.set_stage_metadata(
            self.STAGE_NUM,
            capability_snapshot={
                "citation_analysis": citation_capabilities,
                "outline_review": "reverse_outline_analyzer",
            },
        )

        results: Dict[str, Any] = {}
        citation_summary: Dict[str, Any] = {
            "nodes": 0,
            "edges": 0,
            "key_sources": 0,
            "orphan_sources": 0,
        }

        if self.project.literature or stage2_records:
            network_result = self.analyze_citation_network(
                self.project.literature,
                citation_records=stage2_records,
            )
            network = network_result["network"]
            results["citation_network"] = network
            results["citation_package"] = network_result["package"]
            self.project.register_package(
                network_result["package"],
                stage=self.STAGE_NUM,
                source="citation_network_analyzer",
            )
            results["key_sources"] = network_result["key_source_ids"]
            self.project.citation_network = network
            self.project.key_source_ids = network_result["key_source_ids"]
            citation_summary = network_result["summary"]
            print(
                f"[Stage 4] Citation network: {len(network.nodes)} nodes, "
                f"{len(network.edges)} edges"
            )
            print(f"[Stage 4] Key sources: {len(network_result['key_source_ids'])}")
        else:
            print("[Stage 4] No literature available for citation analysis")
            results["citation_network"] = None
            results["key_sources"] = []
            self._warnings.append("citation_network_skipped_no_sources")

        outline_review = None
        outline_summary = {"available": False, "logical_gaps": 0, "deviation_flags": 0}
        if self.project.paper_draft and len(self.project.paper_draft) > 200:
            try:
                outline_review = self.analyze_paper_outline(self.project.paper_draft)
                results["outline_review"] = outline_review
                self.project.outline_review = outline_review
                outline_summary = {
                    "available": True,
                    "logical_gaps": len(outline_review.logical_gaps),
                    "deviation_flags": len(outline_review.deviation_flags),
                }
                outline_package = self._build_outline_package(outline_review)
                results["outline_package"] = outline_package
                self.project.register_package(
                    outline_package,
                    stage=self.STAGE_NUM,
                    source="reverse_outline_analyzer",
                )
                self._register_outline_review_items(outline_review)
                print("[Stage 4] Outline review complete")
            except Exception as exc:  # noqa: BLE001
                print(f"[Stage 4] Outline review failed: {exc}")
                results["outline_review"] = None
                self._warnings.append("outline_review_failed")
        else:
            print("[Stage 4] No usable paper draft for outline review, skipping")
            results["outline_review"] = None
            self._warnings.append("outline_review_skipped_no_draft")

        self._flush_review_items()
        self.project.set_stage_metadata(
            self.STAGE_NUM,
            execution_summary={
                "citation_analysis": citation_summary,
                "outline_review": outline_summary,
                "warning_count": len(self._warnings),
                "review_count": len(self._review_items),
            },
            warnings=self._warnings,
        )

        self.project.mark_stage_done(self.STAGE_NUM)
        print("[Stage 4] Done")
        return results

    def analyze_citation_network(
        self,
        literature: List[PaperRecord],
        citation_records: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Build a lightweight citation network from project literature."""

        citation_records = citation_records or []
        print(
            f"[Stage 4] Analyze citation network: "
            f"{len(literature)} papers + {len(citation_records)} citation records"
        )
        analyzer = self._get_citation_analyzer()
        documents = [
            {
                "id": paper.id,
                "title": paper.title,
                "authors": paper.authors,
                "year": paper.year,
                "journal": paper.journal,
                "source": paper.source,
                "text": f"{paper.title}\n{paper.abstract or ''}",
                "metadata": {"doi": paper.doi, "url": paper.url},
            }
            for paper in literature
        ]
        documents.extend(
            self._citation_record_to_document(record, index)
            for index, record in enumerate(citation_records, start=len(documents) + 1)
        )
        language = self._detect_language()
        language_map = {"english": "english", "japanese": "japanese", "chinese": "chinese"}
        analysis = analyzer.analyze_documents_package(documents, language=language_map.get(language, "english"))
        graph = analysis["graph"]
        summary = analysis["summary"]

        network = CitationNetwork(
            nodes=graph.get("nodes", []),
            edges=[
                {
                    "from_id": edge["source"],
                    "to_id": edge["target"],
                    "type": edge["type"],
                    "confidence": edge.get("confidence", 0.0),
                }
                for edge in graph.get("edges", [])[:500]
            ],
            key_source_ids=summary.get("key_source_ids", []),
            orphan_ids=summary.get("orphan_ids", []),
        )

        if summary.get("total_edges", 0) == 0 and summary.get("total_nodes", 0) > 3:
            self.project.add_quality_flag("stage4_sparse_citation_network")
        for flag in analysis.get("quality_flags", []):
            self.project.add_quality_flag(f"stage4_{flag}")
        if analysis.get("needs_review"):
            self._review_items.append(
                {
                    "stage": self.STAGE_NUM,
                    "type": "citation_network_quality",
                    "message": "Citation network package requires manual review.",
                    "quality_flags": analysis.get("quality_flags", []),
                    "confidence": analysis.get("confidence", 0.0),
                }
            )

        return {
            "network": network,
            "package": {
                "type": analysis.get("type"),
                "backend": analysis.get("backend"),
                "provider": analysis.get("provider"),
                "model": analysis.get("model"),
                "confidence": analysis.get("confidence"),
                "needs_review": analysis.get("needs_review"),
                "quality_flags": analysis.get("quality_flags", []),
                "summary": summary,
            },
            "key_source_ids": summary.get("key_source_ids", []),
            "summary": {
                "nodes": summary.get("total_nodes", 0),
                "edges": summary.get("total_edges", 0),
                "key_sources": summary.get("key_source_count", 0),
                "orphan_sources": summary.get("orphan_count", 0),
                "average_edge_confidence": summary.get("average_edge_confidence", 0.0),
                "stage2_citation_records": len(citation_records),
                "backend": analysis.get("backend"),
                "provider": analysis.get("provider"),
                "confidence": analysis.get("confidence"),
                "needs_review": analysis.get("needs_review"),
                "quality_flags": analysis.get("quality_flags", []),
            },
        }

    def _get_stage2_citation_records(self) -> List[Dict[str, Any]]:
        metadata = self.project.get_stage_metadata(2)
        records = metadata.get("book_citation_records", [])
        return [record for record in records if isinstance(record, dict)]

    def _citation_record_to_document(self, record: Dict[str, Any], index: int) -> Dict[str, Any]:
        authors = record.get("authors") or record.get("author") or []
        if isinstance(authors, str):
            authors = [item.strip() for item in authors.split(",") if item.strip()]
        title = record.get("title") or f"Citation Record {index}"
        return {
            "id": record.get("id") or f"citation_record_{index}",
            "title": title,
            "authors": authors,
            "year": record.get("year", ""),
            "journal": record.get("journal", ""),
            "source": record.get("journal_or_publisher") or record.get("publisher") or record.get("source", ""),
            "type": record.get("type") or record.get("record_type") or "source",
            "confidence": record.get("confidence", 0.7),
            "text": "\n".join(
                str(part)
                for part in (
                    title,
                    record.get("normalized_citation", ""),
                    record.get("raw_text", ""),
                )
                if part
            ),
            "metadata": {
                "doi": record.get("doi", ""),
                "url": record.get("url", ""),
                "needs_review": record.get("needs_review", False),
                "from_stage2_citation_record": True,
            },
        }

    def analyze_paper_outline(self, paper_text: str) -> Optional[OutlineReview]:
        """Analyze paper logic with the outline analyzer or a rule-based fallback."""

        print(f"[Stage 4] Analyze paper outline: {len(paper_text)} chars")
        try:
            analyzer = self._get_outline_analyzer()
            language = self._detect_language()
            result = analyzer.analyze(paper_text, language=language)
            return self._parse_outline_result(result)
        except Exception as exc:  # noqa: BLE001
            print(f"[Stage 4] Outline analyzer unavailable, fallback to rules: {exc}")
            return self._fallback_outline_review(paper_text)

    def _detect_language(self) -> str:
        """Resolve the workflow language into analyzer labels."""

        lang = self.project.language.lower()
        if lang in ("en", "english"):
            return "english"
        if lang in ("ja", "japanese"):
            return "japanese"
        return "chinese"

    def _parse_outline_result(self, result: Any) -> OutlineReview:
        """Normalize analyzer output into OutlineReview."""

        if isinstance(result, dict):
            return OutlineReview(
                section_word_counts=result.get("section_word_counts", {}),
                section_ratios=result.get("section_ratios", {}),
                logical_gaps=result.get("logical_gaps", []),
                deviation_flags=result.get("deviation_flags", []),
                suggestions=result.get("suggestions", []),
            )
        return OutlineReview()

    def _fallback_outline_review(self, paper_text: str) -> OutlineReview:
        """Rule-based fallback when the outline analyzer is unavailable."""

        import re

        section_headers = {
            "abstract": r"(摘要|Abstract)",
            "introduction": r"(序章|导论|Introduction|前言)",
            "literature_review": r"(文献综述|研究回顾|Literature Review)",
            "methodology": r"(研究方法|Methodology)",
            "analysis": r"(分析|Analysis|正文)",
            "discussion": r"(讨论|Discussion)",
            "conclusion": r"(结论|Conclusion|结语)",
            "references": r"(参考文献|References)",
        }

        section_word_counts: Dict[str, int] = {}
        sections_found = set()
        for section_name, pattern in section_headers.items():
            matches = list(re.finditer(pattern, paper_text, re.IGNORECASE))
            if not matches:
                continue
            start = matches[0].end()
            next_pattern = "|".join(section_headers.values())
            next_match = re.search(next_pattern, paper_text[start:], re.IGNORECASE)
            end = start + next_match.start() if next_match else len(paper_text)
            section_text = paper_text[start:end]
            section_word_counts[section_name] = len(section_text)
            sections_found.add(section_name)

        total = sum(section_word_counts.values()) or 1
        section_ratios = {key: round(value / total, 3) for key, value in section_word_counts.items()}

        logical_gaps = []
        if "abstract" not in sections_found:
            logical_gaps.append("missing abstract")
        if "introduction" not in sections_found:
            logical_gaps.append("missing introduction")
        if "conclusion" not in sections_found:
            logical_gaps.append("missing conclusion")
        if "literature_review" not in sections_found:
            logical_gaps.append("missing literature review")

        deviation_flags = []
        for section, ratio in section_ratios.items():
            if section == "references" and ratio > 0.4:
                deviation_flags.append(f"{section} too long ({ratio:.1%})")

        suggestions = []
        if logical_gaps:
            suggestions.append("add missing sections: " + ", ".join(logical_gaps))
        if not sections_found:
            suggestions.append("unable to detect section structure")

        return OutlineReview(
            section_word_counts=section_word_counts,
            section_ratios=section_ratios,
            logical_gaps=logical_gaps,
            deviation_flags=deviation_flags,
            suggestions=suggestions,
        )

    def _build_outline_package(self, review: OutlineReview) -> Dict[str, Any]:
        quality_flags: List[str] = []
        if review.logical_gaps:
            quality_flags.append("logical_gaps")
        if review.deviation_flags:
            quality_flags.append("outline_deviation_flags")
        if not review.section_word_counts:
            quality_flags.append("section_structure_missing")
        confidence = max(0.25, 0.9 - 0.1 * len(quality_flags))
        return {
            "type": "outline_review",
            "success": True,
            "backend": "script",
            "provider": "reverse_outline_analyzer",
            "model": None,
            "confidence": round(confidence, 2),
            "needs_review": bool(quality_flags),
            "quality_flags": quality_flags,
            "summary": {
                "logical_gaps": len(review.logical_gaps),
                "deviation_flags": len(review.deviation_flags),
                "suggestions": len(review.suggestions),
                "sections": len(review.section_word_counts),
            },
            "data": review.to_dict(),
            "artifacts": [],
        }

    def _register_outline_review_items(self, review: OutlineReview) -> None:
        """Convert outline warnings into workflow review items."""

        for item in review.logical_gaps:
            self._review_items.append(
                {
                    "stage": self.STAGE_NUM,
                    "type": "outline_gap",
                    "message": item,
                }
            )
        for item in review.deviation_flags:
            self._review_items.append(
                {
                    "stage": self.STAGE_NUM,
                    "type": "outline_deviation",
                    "message": item,
                }
            )
        if review.logical_gaps:
            self.project.add_quality_flag("stage4_outline_review_needed")

    def _flush_review_items(self) -> None:
        """Persist stage review items to the project."""

        for item in self._review_items:
            self.project.add_review_item(item)

    def print_review_summary(self, review: OutlineReview) -> None:
        """Print a compact review summary."""

        if not review:
            return
        print("\n[Stage 4] Outline review summary")
        print("-" * 40)
        print(f"Sections: {len(review.section_word_counts)}")
        print(f"Logical gaps: {len(review.logical_gaps)}")
        print(f"Deviation flags: {len(review.deviation_flags)}")
