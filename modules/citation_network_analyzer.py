"""
Citation network analysis helpers.

This module provides a stable citation-record schema plus graph-building and
summary utilities for workflow stages.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional


class CitationNetworkAnalyzer:
    """Analyze citation relationships and produce normalized graph data."""

    CITATION_PATTERNS = {
        "japanese": [
            re.compile(r"\[(\d+)\]"),
            re.compile(r"([一-龥ぁ-んァ-ンA-Za-z0-9\s]{4,})（(\d{4})）"),
        ],
        "chinese": [
            re.compile(r"\[(\d+)\]"),
            re.compile(r"([一-龥A-Za-z0-9\s]{4,})（(\d{4})）"),
        ],
        "english": [
            re.compile(r"\(([A-Z][A-Za-z]+(?:\s+et al\.)?,?\s*\d{4})\)"),
            re.compile(r"\[(\d+)\]"),
        ],
    }

    def __init__(self):
        self.citation_graph: Dict[str, Any] = {"nodes": [], "edges": [], "metadata": {}}
        self.documents: Dict[str, Dict[str, Any]] = {}
        self.citations = defaultdict(list)
        self.cited_by = defaultdict(list)
        self.academic_schools: List[Dict[str, Any]] = []
        self.evolution_timeline: List[Dict[str, Any]] = []
        self.records: List[Dict[str, Any]] = []

    def get_capabilities(self) -> Dict[str, Any]:
        """Return a workflow-facing capability snapshot."""
        return {
            "module": "citation_network_analyzer",
            "backend": "script",
            "provider": "rule_based_graph",
            "model": None,
            "capabilities": [
                "citation_record_normalization",
                "citation_graph_building",
                "citation_graph_summary",
                "review_flagging",
            ],
            "fallback_order": ["script:rule_based_graph", "llm_citation_extractor", "mcp_citation_service"],
        }

    def normalize_document(self, doc: Dict[str, Any], index: int = 0) -> Dict[str, Any]:
        """Normalize a source document into the citation-record schema."""

        title = (doc.get("title") or f"Document {index + 1}").strip()
        authors = doc.get("authors") or []
        if isinstance(authors, str):
            authors = [item.strip() for item in authors.split(",") if item.strip()]
        record_type = doc.get("type") or ("article" if doc.get("journal") else "source")
        record = {
            "id": doc.get("id") or self._generate_doc_id(title),
            "title": title,
            "authors": authors,
            "year": str(doc.get("year", "") or ""),
            "text": doc.get("text", "") or doc.get("abstract", "") or "",
            "journal": doc.get("journal", "") or "",
            "source": doc.get("source", "") or "",
            "record_type": record_type,
            "metadata": dict(doc.get("metadata", {})),
            "confidence": float(doc.get("confidence", 0.7)),
        }
        return record

    def extract_citations(self, text: str, language: str = "chinese") -> List[Dict[str, Any]]:
        """Extract lightweight citation mentions from text."""

        citations: List[Dict[str, Any]] = []
        seen = set()
        patterns = self.CITATION_PATTERNS.get(language, self.CITATION_PATTERNS["english"])

        for pattern in patterns:
            for match in pattern.finditer(text or ""):
                mention = match.group(0).strip()
                parsed = self._parse_citation(mention)
                if not parsed:
                    continue
                key = (parsed.get("title", ""), parsed.get("year", ""), parsed.get("raw", ""))
                if key in seen:
                    continue
                seen.add(key)
                parsed["matched_text"] = mention
                citations.append(parsed)
        return citations

    def analyze_documents(self, documents: List[Dict[str, Any]], language: str = "english") -> Dict[str, Any]:
        """Normalize documents, build the graph, and compute a summary."""

        self.documents.clear()
        self.citations.clear()
        self.cited_by.clear()
        self.records = [self.normalize_document(doc, index) for index, doc in enumerate(documents)]
        graph = self.build_citation_graph(self.records, language=language)
        summary = self._build_graph_summary(graph)
        return {"graph": graph, "records": self.records, "summary": summary}

    def analyze_documents_package(self, documents: List[Dict[str, Any]], language: str = "english") -> Dict[str, Any]:
        """Analyze documents and wrap the graph in the unified workflow envelope."""
        result = self.analyze_documents(documents, language=language)
        graph = result["graph"]
        summary = result["summary"]
        quality_flags: List[str] = []
        if not documents:
            quality_flags.append("no_documents")
        if summary.get("total_nodes", 0) and summary.get("total_edges", 0) == 0:
            quality_flags.append("no_citation_edges")
        if summary.get("orphan_count", 0) == summary.get("total_nodes", 0) and summary.get("total_nodes", 0) > 1:
            quality_flags.append("all_documents_isolated")
        if summary.get("average_edge_confidence", 0.0) and summary["average_edge_confidence"] < 0.55:
            quality_flags.append("low_average_edge_confidence")

        confidence = self._estimate_package_confidence(summary, quality_flags)
        graph.setdefault("metadata", {})
        graph["metadata"]["execution"] = {
            **self.get_capabilities(),
            "confidence": confidence,
            "needs_review": bool(quality_flags),
            "quality_flags": quality_flags,
        }
        return {
            "type": "citation_network",
            "language": language,
            "records": result["records"],
            "nodes": graph.get("nodes", []),
            "edges": graph.get("edges", []),
            "graph": graph,
            "summary": summary,
            "backend": "script",
            "provider": "rule_based_graph",
            "model": None,
            "confidence": confidence,
            "needs_review": bool(quality_flags),
            "quality_flags": quality_flags,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

    def build_citation_graph(self, documents: List[Dict[str, Any]], language: str = "english") -> Dict[str, Any]:
        """Build citation graph data using normalized records."""

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        self.documents = {}

        for index, doc in enumerate(documents):
            record = self.normalize_document(doc, index) if "record_type" not in doc else dict(doc)
            record_id = record["id"]
            self.documents[record_id] = record
            nodes.append(
                {
                    "id": record_id,
                    "label": record["title"],
                    "title": record["title"],
                    "authors": record["authors"],
                    "year": record["year"],
                    "type": record["record_type"],
                    "is_core": False,
                    "citation_count": 0,
                    "cited_by_count": 0,
                    "confidence": record.get("confidence", 0.7),
                    "metadata": {
                        "journal": record.get("journal", ""),
                        "source": record.get("source", ""),
                    },
                }
            )

        for source_id, record in self.documents.items():
            citations = self.extract_citations(record.get("text", ""), language=language)
            self.citations[source_id] = []
            for target_id, target in self.documents.items():
                if source_id == target_id:
                    continue
                confidence = self._match_confidence(record, target, citations)
                if confidence <= 0:
                    continue
                edges.append(
                    {
                        "source": source_id,
                        "target": target_id,
                        "type": "cites",
                        "confidence": round(confidence, 3),
                        "evidence": {"matched_title": target["title"]},
                    }
                )
                self.citations[source_id].append(target_id)
                self.cited_by[target_id].append(source_id)

        node_index = {node["id"]: node for node in nodes}
        for edge in edges:
            node_index[edge["source"]]["citation_count"] += 1
            node_index[edge["target"]]["cited_by_count"] += 1

        ranked = sorted(nodes, key=lambda node: (node["cited_by_count"] + node["citation_count"], node["year"]), reverse=True)
        cutoff = max(1, len(ranked) // 5) if ranked else 0
        key_source_ids = {node["id"] for node in ranked[:cutoff] if (node["cited_by_count"] + node["citation_count"]) > 0}
        for node in nodes:
            node["is_core"] = node["id"] in key_source_ids

        self.citation_graph = {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "source_documents": len(documents),
                "language": language,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
            },
        }
        return self.citation_graph

    def analyze_academic_evolution(self) -> List[Dict[str, Any]]:
        """Summarize graph activity by publication year."""

        if not self.citation_graph["nodes"]:
            return []

        nodes_by_year = defaultdict(list)
        for node in self.citation_graph["nodes"]:
            if node.get("year"):
                nodes_by_year[node["year"]].append(node)

        timeline = []
        for year in sorted(nodes_by_year):
            year_nodes = nodes_by_year[year]
            timeline.append(
                {
                    "year": year,
                    "works_count": len(year_nodes),
                    "total_citations": sum(item["citation_count"] for item in year_nodes),
                    "key_works": [item["title"] for item in sorted(year_nodes, key=lambda x: x["cited_by_count"], reverse=True)[:3]],
                    "foundational_works": [item["title"] for item in year_nodes if item["is_core"]],
                }
            )

        self.evolution_timeline = timeline
        return timeline

    def identify_academic_schools(self) -> List[Dict[str, Any]]:
        """Identify citation clusters around highly connected records."""

        if not self.citation_graph["nodes"]:
            return []

        schools = []
        ranked = sorted(
            self.citation_graph["nodes"],
            key=lambda node: (node["cited_by_count"], node["citation_count"]),
            reverse=True,
        )
        for node in ranked[:5]:
            if node["cited_by_count"] + node["citation_count"] < 2:
                continue
            member_ids = set(self.citations.get(node["id"], [])) | set(self.cited_by.get(node["id"], []))
            members = []
            for item in self.citation_graph["nodes"]:
                if item["id"] in member_ids:
                    members.append(
                        {
                            "id": item["id"],
                            "title": item["title"],
                            "authors": item.get("authors", []),
                            "year": item.get("year", ""),
                        }
                    )
            schools.append(
                {
                    "id": f"school_{len(schools) + 1}",
                    "founder": node["title"],
                    "founder_id": node["id"],
                    "members": members,
                    "member_count": len(members),
                    "citation_count": node["cited_by_count"] + node["citation_count"],
                    "description": f"Citation cluster centered on {node['title']}.",
                }
            )

        self.academic_schools = schools
        return schools

    def find_peripheral_works(self, centrality_threshold: float = 0.1) -> List[Dict[str, Any]]:
        """Find low-centrality records that still receive some attention."""

        if not self.citation_graph["nodes"]:
            return []

        centrality = self._calculate_centrality()
        works = []
        for node in self.citation_graph["nodes"]:
            score = centrality.get(node["id"], 0.0)
            if score < centrality_threshold and node["cited_by_count"] > 0:
                works.append(
                    {
                        "id": node["id"],
                        "title": node["title"],
                        "authors": node.get("authors", []),
                        "year": node.get("year", ""),
                        "centrality": score,
                        "cited_by_count": node["cited_by_count"],
                        "novelty_score": self._calculate_novelty_score(node["id"]),
                    }
                )
        works.sort(key=lambda item: item["novelty_score"], reverse=True)
        return works[:10]

    def get_citation_statistics(self) -> Dict[str, Any]:
        """Return aggregate graph statistics."""

        if not self.citation_graph["nodes"]:
            return {}

        most_cited = sorted(self.citation_graph["nodes"], key=lambda node: node["cited_by_count"], reverse=True)[:10]
        return {
            "total_documents": len(self.documents),
            "total_citations": len(self.citation_graph["edges"]),
            "avg_citations_per_doc": len(self.citation_graph["edges"]) / len(self.documents) if self.documents else 0.0,
            "most_cited_works": [
                {
                    "id": node["id"],
                    "title": node["title"],
                    "authors": node.get("authors", []),
                    "citation_count": node["cited_by_count"],
                }
                for node in most_cited
            ],
            "isolated_documents": len(
                [
                    node
                    for node in self.citation_graph["nodes"]
                    if node["citation_count"] == 0 and node["cited_by_count"] == 0
                ]
            ),
        }

    def generate_graph_export(self, format: str = "json") -> str:
        """Export the current citation graph."""

        if format == "json":
            return json.dumps(self.citation_graph, ensure_ascii=False, indent=2)
        if format == "gexf":
            return self._export_as_gexf()
        if format == "csv":
            return self._export_as_csv()
        return json.dumps(self.citation_graph, ensure_ascii=False)

    def visualize_as_markdown(self) -> str:
        """Render a compact Markdown report for the current graph."""

        stats = self.get_citation_statistics()
        lines = [
            "# Citation Network Report",
            "",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            "",
            f"- Total documents: {stats.get('total_documents', 0)}",
            f"- Total citation edges: {stats.get('total_citations', 0)}",
            f"- Isolated documents: {stats.get('isolated_documents', 0)}",
            "",
        ]
        if stats.get("most_cited_works"):
            lines.extend(["## Most Cited", ""])
            for work in stats["most_cited_works"][:5]:
                lines.append(f"- **{work['title']}** ({work['citation_count']} incoming citations)")
        return "\n".join(lines)

    def _build_graph_summary(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        key_source_ids = [node["id"] for node in nodes if node.get("is_core")]
        orphan_ids = [node["id"] for node in nodes if node.get("citation_count", 0) == 0 and node.get("cited_by_count", 0) == 0]
        return {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "key_source_count": len(key_source_ids),
            "key_source_ids": key_source_ids,
            "orphan_count": len(orphan_ids),
            "orphan_ids": orphan_ids,
            "average_edge_confidence": round(sum(edge.get("confidence", 0.0) for edge in edges) / len(edges), 3) if edges else 0.0,
        }

    def _estimate_package_confidence(self, summary: Dict[str, Any], quality_flags: List[str]) -> float:
        if summary.get("total_nodes", 0) == 0:
            return 0.2
        confidence = 0.45
        if summary.get("total_edges", 0) > 0:
            confidence += 0.25
        if summary.get("key_source_count", 0) > 0:
            confidence += 0.10
        confidence += min(0.15, summary.get("average_edge_confidence", 0.0) * 0.15)
        confidence -= min(0.25, len(quality_flags) * 0.08)
        return round(max(0.1, min(confidence, 0.95)), 2)

    def _parse_citation(self, citation_str: str) -> Dict[str, Any]:
        """Parse a citation mention into a lightweight record."""

        citation = {"raw": citation_str, "title": citation_str.strip(), "confidence": 0.35}
        year_match = re.search(r"(19|20)\d{2}", citation_str)
        if year_match:
            citation["year"] = year_match.group(0)
            citation["confidence"] += 0.15

        quoted = re.search(r"[\"“「『《](.+?)[\"”」』》]", citation_str)
        if quoted:
            citation["title"] = quoted.group(1).strip()
            citation["confidence"] += 0.15
        else:
            stripped = re.sub(r"\[\d+\]|\((19|20)\d{2}\)", "", citation_str).strip(" ,.;")
            if stripped:
                citation["title"] = stripped

        page_match = re.search(r"(?:pp?\.?\s*)?(\d+(?:-\d+)?)", citation_str)
        if page_match:
            citation["page"] = page_match.group(1)
        return citation

    def _generate_doc_id(self, title: str) -> str:
        return "doc_" + hashlib.md5(title.encode("utf-8")).hexdigest()[:8]

    def _match_confidence(
        self,
        source_record: Dict[str, Any],
        target_record: Dict[str, Any],
        extracted_citations: List[Dict[str, Any]],
    ) -> float:
        """Estimate confidence that source cites target."""

        target_title = target_record["title"].lower()
        source_text = (source_record.get("text", "") or "").lower()
        title_words = [word.lower() for word in re.findall(r"[A-Za-z\u4e00-\u9fff]{4,}", target_record["title"]) if len(word) >= 4]
        if title_words:
            overlap = sum(1 for word in title_words if word in source_text)
            if overlap >= 2:
                return min(0.9, 0.4 + 0.15 * overlap)

        for citation in extracted_citations:
            cited_title = citation.get("title", "").lower()
            if cited_title and (cited_title in target_title or target_title in cited_title):
                return max(0.55, citation.get("confidence", 0.4))
        return 0.0

    def _calculate_centrality(self) -> Dict[str, float]:
        total = max(1, len(self.documents) * 2)
        return {
            node_id: (len(self.cited_by.get(node_id, [])) + len(self.citations.get(node_id, []))) / total
            for node_id in self.documents
        }

    def _calculate_novelty_score(self, doc_id: str) -> float:
        cited_by_count = len(self.cited_by.get(doc_id, []))
        cites_count = len(self.citations.get(doc_id, []))
        if cites_count > 0:
            novelty = cited_by_count / cites_count
        else:
            novelty = cited_by_count * 0.5
        return min(novelty, 1.0)

    def _export_as_gexf(self) -> str:
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<gexf xmlns="http://www.gexf.net/1.3" version="1.3">',
            '  <graph mode="static" defaultedgettype="directed">',
            "    <nodes>",
        ]
        for node in self.citation_graph.get("nodes", []):
            lines.append(f'      <node id="{node["id"]}" label="{node["label"]}" />')
        lines.extend(["    </nodes>", "    <edges>"])
        for index, edge in enumerate(self.citation_graph.get("edges", [])):
            lines.append(f'      <edge id="{index}" source="{edge["source"]}" target="{edge["target"]}" />')
        lines.extend(["    </edges>", "  </graph>", "</gexf>"])
        return "\n".join(lines)

    def _export_as_csv(self) -> str:
        lines = ["Source,Target,Type,Confidence"]
        for edge in self.citation_graph.get("edges", []):
            lines.append(
                f'"{edge["source"]}","{edge["target"]}","{edge["type"]}","{edge.get("confidence", 0.0)}"'
            )
        return "\n".join(lines)


def create_citation_analyzer() -> CitationNetworkAnalyzer:
    """Factory helper preserved for compatibility."""

    return CitationNetworkAnalyzer()
