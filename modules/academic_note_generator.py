"""
Academic note generation facade.

This module keeps the legacy public API while routing note generation and
entity extraction through the unified task layer.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from modules.task_manager import TaskManager

try:
    from prompts.prompt_loader import PromptLoader, PromptTemplate

    PROMPT_LOADER_AVAILABLE = True
except ImportError:
    PROMPT_LOADER_AVAILABLE = False


class AcademicNoteGenerator:
    """Generate Obsidian-friendly academic notes from source text."""

    ENTITY_TYPES = {
        "person": "Person",
        "location": "Location",
        "event": "Event",
        "concept": "Concept",
        "literature": "Literature",
    }

    DEFAULT_NOTE_TEMPLATE = """---
type: reading_note
tags:
  - "#literature_note"
  - "#{subject_tag}"
created: {created_date}
source: {source_title}
---

# {title}

## Summary

{summary}

## Chapter Outline

{chapter_outline}

## Knowledge Graph Highlights

{knowledge_graph}

---

**Metadata**
- Authors: {authors}
- Year: {year}
- Keywords: {keywords}
"""

    def __init__(self, api_provider: str = "qwen", test_mode: bool = True):
        self.api_provider = api_provider
        self.test_mode = test_mode
        self.task_manager = TaskManager(mode="api", provider=api_provider or "qwen")
        self._prompt_loader = None
        self._prompt_template = None

    def get_capabilities(self) -> Dict[str, Any]:
        """Return a workflow/agent friendly capability snapshot."""

        return {
            "module": "AcademicNoteGenerator",
            "task": "academic_note",
            "available": True,
            "test_mode": self.test_mode,
            "backend_options": [
                {
                    "backend": "script",
                    "provider": "academic_note_generator",
                    "model": "mock-note-generator" if self.test_mode else "template-fallback",
                    "available": True,
                    "description": "Deterministic template and entity fallback.",
                },
                {
                    "backend": "llm_api",
                    "provider": self.api_provider,
                    "model": None,
                    "available": not self.test_mode,
                    "description": "Remote LLM note generation through TaskManager.",
                },
                {
                    "backend": "local_llm",
                    "provider": "ollama",
                    "model": "configured local model",
                    "available": not self.test_mode,
                    "description": "Small/local model path with script fallback.",
                },
                {
                    "backend": "skill",
                    "provider": "historyresearch-workspace",
                    "model": "workspace-skill",
                    "available": True,
                    "description": "Future AI-agent skill backend for note protocol alignment.",
                },
                {
                    "backend": "mcp",
                    "provider": "external_tool",
                    "model": "configured",
                    "available": False,
                    "description": "Reserved MCP note generation backend.",
                },
            ],
            "fallback_order": ["llm_api", "local_llm", "script", "skill", "mcp"],
            "output_type": "academic_note",
            "quality_signals": [
                "empty_markdown",
                "no_entities",
                "note_generation_fallback_used",
                "fallback_backend",
                "short_summary",
            ],
        }

    def _get_prompt_loader(self):
        if self._prompt_loader is None and PROMPT_LOADER_AVAILABLE:
            self._prompt_loader = PromptLoader()
        return self._prompt_loader

    def _get_prompt_template(self):
        if self._prompt_template is None:
            loader = self._get_prompt_loader()
            self._prompt_template = PromptTemplate(loader) if loader else None
        return self._prompt_template

    def generate_reading_note(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        custom_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a structured reading note with normalized execution metadata."""

        metadata = metadata or {}
        if self.test_mode:
            return self._generate_mock_note(text, metadata)

        source_title = metadata.get("title", "Unknown Source")
        backend = metadata.get("backend") or "llm_api"
        fallback_backends = list(metadata.get("fallback_backends") or ["local_llm", "script"])

        try:
            result = self.task_manager.execute_task(
                "academic_note",
                text=text,
                source=source_title,
                backend=backend,
                provider=metadata.get("provider", self.api_provider),
                model=metadata.get("model"),
                custom_prompt=custom_prompt,
                fallback_backends=fallback_backends,
                temperature=metadata.get("temperature", 0.3),
                max_tokens=metadata.get("max_tokens", 3000),
            )
        except Exception as exc:  # noqa: BLE001
            result = {"success": False, "error": str(exc), "metadata": {}}

        note_payload = self._normalize_note_result(result, text, metadata)
        note_payload["markdown"] = self.apply_note_template(note_payload)
        return note_payload

    def generate_reading_note_package(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        custom_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a reading note and wrap it as an `academic_note` envelope."""

        metadata = metadata or {}
        try:
            note = self.generate_reading_note(text, metadata, custom_prompt=custom_prompt)
            error = None
        except Exception as exc:  # noqa: BLE001
            note = self._generate_mock_note(text, metadata)
            note["needs_review"] = True
            note["review_reason"] = str(exc)
            error = str(exc)

        flags = self._package_quality_flags(note)
        return {
            "type": "academic_note",
            "schema_version": "2026-04-25",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_id": metadata.get("id") or metadata.get("source_id"),
            "source_title": metadata.get("title", "Unknown Title"),
            "markdown": note.get("markdown", ""),
            "summary": note.get("summary", ""),
            "entities": note.get("entities", {}),
            "keywords": note.get("keywords", []),
            "export_summary": self._build_export_summary(note),
            "backend": note.get("backend") or "script",
            "provider": note.get("provider", self.api_provider),
            "model": note.get("model"),
            "confidence": self._package_confidence(note, flags),
            "needs_review": bool(flags) or bool(note.get("needs_review")),
            "quality_flags": flags,
            "capabilities": self.get_capabilities(),
            "metadata": {
                "authors": metadata.get("authors", ""),
                "year": metadata.get("year", ""),
                "source": metadata.get("source", ""),
                "subject_tag": metadata.get("subject_tag", "history"),
            },
            "error": error,
        }

    def extract_entities(
        self,
        text: str,
        entity_types: Optional[List[str]] = None,
    ) -> Dict[str, List[str]]:
        """Extract entities grouped by type through the unified task layer."""

        categories = entity_types or list(self.ENTITY_TYPES.keys())
        if self.test_mode:
            return self._extract_mock_entities(text, categories)

        try:
            result = self.task_manager.execute_task(
                "ner",
                text=text,
                categories=categories,
                backend="script" if self.test_mode else None,
                provider=self.api_provider,
                fallback_backends=["local_llm", "script"],
                temperature=0.1,
                max_tokens=1500,
            )
        except Exception:  # noqa: BLE001
            return self._extract_mock_entities(text, categories)

        grouped = {category: [] for category in categories}
        if not result.get("success"):
            return grouped

        for item in (result.get("data") or {}).get("entities", []):
            name = item.get("entity") or item.get("text") or item.get("name")
            category = item.get("category", "concept")
            if name and category in grouped and name not in grouped[category]:
                grouped[category].append(name)
        return grouped

    def build_knowledge_graph(
        self,
        entities: Dict[str, List[str]],
        relationships: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Build lightweight graph data from extracted entities."""

        nodes = []
        links = []
        node_id_map = {}

        for entity_type, entity_list in entities.items():
            for entity in entity_list:
                entity_id = self._generate_entity_id(entity)
                node_id_map[entity] = entity_id
                nodes.append(
                    {
                        "id": entity_id,
                        "label": entity,
                        "type": entity_type,
                        "category": self.ENTITY_TYPES.get(entity_type, entity_type),
                    }
                )

        for rel in relationships or []:
            source = rel.get("source")
            target = rel.get("target")
            if source in node_id_map and target in node_id_map:
                links.append(
                    {
                        "source": node_id_map[source],
                        "target": node_id_map[target],
                        "type": rel.get("type", "related_to"),
                        "label": rel.get("label", rel.get("type", "related_to")),
                    }
                )

        return {
            "nodes": nodes,
            "links": links,
            "stats": {
                "total_nodes": len(nodes),
                "total_links": len(links),
                "entity_types": {key: len(value) for key, value in entities.items()},
            },
        }

    def apply_note_template(self, content: Dict[str, Any], template: Optional[str] = None) -> str:
        """Render note content to Markdown."""

        template = template or self.DEFAULT_NOTE_TEMPLATE
        rendered = template.format(
            title=content.get("title", "Untitled"),
            summary=content.get("summary", ""),
            chapter_outline=self._format_chapter_outline(content.get("chapters", [])),
            knowledge_graph=self._format_knowledge_graph(content.get("entities", {})),
            created_date=content.get("created_date", datetime.now().strftime("%Y-%m-%d")),
            source_title=content.get("source_title", "Unknown"),
            subject_tag=content.get("subject_tag", "history"),
            authors=content.get("authors", "Unknown"),
            year=content.get("year", "Unknown"),
            keywords=", ".join(content.get("keywords", [])),
        )
        return rendered

    def create_bidirectional_links(self, text: str, entities: Dict[str, List[str]]) -> str:
        """Wrap known entities with Obsidian wiki links."""

        linked_text = text
        all_entities: List[str] = []
        for entity_list in entities.values():
            all_entities.extend(entity_list)
        all_entities = sorted(set(all_entities), key=len, reverse=True)

        for entity in all_entities:
            if not entity or f"[[{entity}]]" in linked_text:
                continue
            linked_text = re.sub(rf"(?<!\[\[){re.escape(entity)}(?!\]\])", f"[[{entity}]]", linked_text)
        return linked_text

    def batch_process(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate notes for multiple source documents."""

        results = []
        for document in documents:
            results.append(
                self.generate_reading_note(
                    document.get("text", ""),
                    document.get("metadata", {}),
                )
            )
        return results

    def batch_process_package(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate notes for multiple documents as an `academic_note_batch`."""

        notes = [
            self.generate_reading_note_package(
                document.get("text", ""),
                document.get("metadata", {}),
            )
            for document in documents
        ]
        quality_flags = sorted(
            {
                flag
                for note in notes
                for flag in note.get("quality_flags", [])
            }
        )
        return {
            "type": "academic_note_batch",
            "schema_version": "2026-04-25",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "notes": notes,
            "statistics": {
                "total": len(notes),
                "needs_review": sum(1 for note in notes if note.get("needs_review")),
                "with_entities": sum(1 for note in notes if any(note.get("entities", {}).values())),
                "with_markdown": sum(1 for note in notes if note.get("markdown")),
            },
            "backend": "hybrid" if len({note.get("backend") for note in notes}) > 1 else (notes[0].get("backend") if notes else "script"),
            "provider": self.api_provider,
            "model": None,
            "confidence": round(
                sum(note.get("confidence", 0.0) for note in notes) / len(notes),
                3,
            ) if notes else 0.0,
            "needs_review": any(note.get("needs_review") for note in notes),
            "quality_flags": quality_flags,
            "capabilities": self.get_capabilities(),
        }

    def _normalize_note_result(
        self,
        result: Dict[str, Any],
        text: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Normalize task-layer output into the module's stable note schema."""

        payload = (result.get("data") or {}) if result.get("success") else {}
        note_markdown = payload.get("note_content") or payload.get("content") or payload.get("raw_response") or ""
        entities = self._normalize_entities(
            payload.get("entities")
            or self.extract_entities(text, list(self.ENTITY_TYPES.keys()))
        )

        summary = self._derive_summary(note_markdown or text)
        chapters = self._derive_chapters(note_markdown or text)
        keywords = self._derive_keywords(entities)
        needs_review = not result.get("success") or not note_markdown.strip()

        content = {
            "title": metadata.get("title", "Unknown Title"),
            "summary": self.create_bidirectional_links(summary, entities),
            "chapters": chapters,
            "entities": entities,
            "keywords": keywords,
            "authors": metadata.get("authors", ""),
            "year": metadata.get("year", ""),
            "created_date": datetime.now().strftime("%Y-%m-%d"),
            "source_title": metadata.get("title", "Unknown Title"),
            "subject_tag": metadata.get("subject_tag", "history"),
            "backend": "script" if not result.get("success") else (result.get("backend") or result.get("metadata", {}).get("backend")),
            "provider": "fallback" if not result.get("success") else result.get("metadata", {}).get("provider", self.api_provider),
            "model": "fallback-note" if not result.get("success") else result.get("metadata", {}).get("model"),
            "needs_review": needs_review,
            "raw_note_content": note_markdown,
        }
        if needs_review:
            content["review_reason"] = result.get("error") or "note_generation_fallback_used"
        return content

    def _build_export_summary(self, note: Dict[str, Any]) -> Dict[str, Any]:
        markdown = note.get("markdown", "") or ""
        entities = note.get("entities", {}) or {}
        return {
            "markdown_chars": len(markdown),
            "entity_count": sum(len(values) for values in entities.values()),
            "keyword_count": len(note.get("keywords", []) or []),
            "has_bidirectional_links": "[[" in markdown and "]]" in markdown,
            "needs_review": bool(note.get("needs_review")),
        }

    def _package_quality_flags(self, note: Dict[str, Any]) -> List[str]:
        flags = []
        markdown = note.get("markdown", "") or ""
        entities = note.get("entities", {}) or {}
        if not markdown.strip():
            flags.append("empty_markdown")
        if not any(entities.values()):
            flags.append("no_entities")
        if note.get("needs_review"):
            flags.append("note_generation_fallback_used")
        if note.get("backend") in {"script", "fallback"} and not self.test_mode:
            flags.append("fallback_backend")
        if len(note.get("summary", "") or "") < 20:
            flags.append("short_summary")
        return sorted(set(flags))

    def _package_confidence(self, note: Dict[str, Any], flags: List[str]) -> float:
        confidence = 0.85
        if note.get("backend") in {"script", "fallback"}:
            confidence -= 0.15
        if "empty_markdown" in flags:
            confidence -= 0.35
        if "no_entities" in flags:
            confidence -= 0.1
        if note.get("needs_review"):
            confidence -= 0.15
        return round(max(0.0, min(1.0, confidence)), 3)

    def _normalize_entities(self, data: Any) -> Dict[str, List[str]]:
        """Normalize various entity payload shapes into grouped lists."""

        grouped = {category: [] for category in self.ENTITY_TYPES}
        if isinstance(data, dict):
            for category, values in data.items():
                if category not in grouped:
                    continue
                for value in values or []:
                    if value and value not in grouped[category]:
                        grouped[category].append(value)
            return grouped

        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                name = item.get("entity") or item.get("text") or item.get("name")
                category = item.get("category", "concept")
                if name and category in grouped and name not in grouped[category]:
                    grouped[category].append(name)
        return grouped

    def _derive_summary(self, text: str) -> str:
        sentences = [part.strip() for part in re.split(r"[。！？!?]\s*|\n+", text) if part.strip()]
        return " ".join(sentences[:2])[:400] if sentences else text[:400]

    def _derive_chapters(self, text: str) -> List[Dict[str, Any]]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        bullet_candidates = [line.lstrip("-* ").strip() for line in lines if line.startswith(("-", "*"))]
        if bullet_candidates:
            return [{"title": "Key Arguments", "main_points": bullet_candidates[:6]}]

        sentences = [part.strip() for part in re.split(r"[。！？!?]\s*|\n+", text) if part.strip()]
        return [{"title": "Key Arguments", "main_points": sentences[:5]}] if sentences else []

    def _derive_keywords(self, entities: Dict[str, List[str]]) -> List[str]:
        keywords = []
        for category in ("concept", "event", "person", "location", "literature"):
            for item in entities.get(category, []):
                if item not in keywords:
                    keywords.append(item)
                if len(keywords) >= 8:
                    return keywords
        return keywords

    def _format_chapter_outline(self, chapters: List[Dict[str, Any]]) -> str:
        if not chapters:
            return "No chapter structure available."
        lines = []
        for chapter in chapters:
            title = chapter.get("title", "Untitled Section")
            lines.append(f"### {title}")
            for point in chapter.get("main_points", []):
                lines.append(f"- {point}")
            lines.append("")
        return "\n".join(lines).strip()

    def _format_knowledge_graph(self, entities: Dict[str, List[str]]) -> str:
        if not entities:
            return "No entity information available."
        lines = []
        for category, values in entities.items():
            if not values:
                continue
            rendered = ", ".join(f"[[{value}]]" for value in values[:10])
            lines.append(f"- **{category}**: {rendered}")
        return "\n".join(lines) if lines else "No entity information available."

    def _generate_entity_id(self, entity: str) -> str:
        return "node_" + hashlib.md5(entity.encode("utf-8")).hexdigest()[:8]

    def _generate_mock_note(self, text: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Generate deterministic test-mode note data."""

        entities = self._extract_mock_entities(text, list(self.ENTITY_TYPES.keys()))
        content = {
            "title": metadata.get("title", "Test Title"),
            "summary": self.create_bidirectional_links("Mock summary for test mode.", entities),
            "chapters": [
                {
                    "title": "Key Arguments",
                    "main_points": [
                        "Mock argument one",
                        "Mock argument two",
                    ],
                }
            ],
            "entities": entities,
            "keywords": self._derive_keywords(entities),
            "authors": metadata.get("authors", ""),
            "year": metadata.get("year", ""),
            "created_date": datetime.now().strftime("%Y-%m-%d"),
            "source_title": metadata.get("title", "Test Title"),
            "subject_tag": metadata.get("subject_tag", "history"),
            "backend": "script",
            "provider": self.api_provider,
            "model": "mock-note-generator",
            "needs_review": False,
        }
        content["markdown"] = self.apply_note_template(content)
        return content

    def _extract_mock_entities(
        self,
        text: str,
        entity_types: Optional[List[str]] = None,
    ) -> Dict[str, List[str]]:
        del text
        entity_types = entity_types or list(self.ENTITY_TYPES.keys())
        mock_entities = {
            "person": ["Tokugawa Ieyasu", "Fukuzawa Yukichi"],
            "location": ["Edo", "Kyoto"],
            "event": ["Meiji Restoration"],
            "concept": ["kokutai", "civilization and enlightenment"],
            "literature": ["An Outline of a Theory of Civilization"],
        }
        return {key: value for key, value in mock_entities.items() if key in entity_types}


def create_academic_note_generator(
    api_provider: str = "qwen",
    test_mode: bool = True,
) -> AcademicNoteGenerator:
    """Factory helper preserved for compatibility."""

    return AcademicNoteGenerator(api_provider=api_provider, test_mode=test_mode)
