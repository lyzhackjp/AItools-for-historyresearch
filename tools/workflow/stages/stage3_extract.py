"""
Stage 3: extract entities and relations from literature and notes.

This stage now routes NER decisions through the unified task layer so the
workflow can discover available backends and persist execution metadata.
"""

from __future__ import annotations

import os
import re
import sys
import uuid
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import requests

_AI_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..")
if _AI_TOOLS not in sys.path:
    sys.path.insert(0, _AI_TOOLS)

from modules.task_manager import TaskManager
from tools.workflow.research_project import (
    EntityRelation,
    HistoricalEntity,
    PaperRecord,
    ResearchProject,
)


class Stage3Extract:
    """Stage 3 entity extraction workflow."""

    NAME = "extract"
    STAGE_NUM = 3

    def __init__(self, project: ResearchProject):
        self.project = project
        self.task_manager: Optional[TaskManager] = None
        self.ner_disambiguator = None
        self._stage_reviews: List[Dict[str, Any]] = []
        self._stage_warnings: List[str] = []
        self._disambiguation_packages: List[Dict[str, Any]] = []

    def _get_task_manager(self) -> TaskManager:
        """Create the workflow task manager lazily."""

        if self.task_manager is None:
            self.task_manager = TaskManager(mode="api", provider="qwen")
        return self.task_manager

    def _get_ner_disambiguator(self):
        """Create the NER disambiguator lazily."""

        if self.ner_disambiguator is None:
            try:
                from modules.ner_disambiguation import NERDisambiguation

                self.ner_disambiguator = NERDisambiguation()
                print("[Stage 3] NERDisambiguation loaded")
            except Exception as exc:  # noqa: BLE001
                print(f"[Stage 3] Failed to load NERDisambiguation: {exc}")
                self.ner_disambiguator = None
        return self.ner_disambiguator

    def _fetch_crossref_metadata(self, doi: str) -> Optional[Dict[str, Any]]:
        """Fetch metadata from CrossRef when a record is missing an abstract."""

        clean_doi = doi.strip()
        if clean_doi.startswith("https://doi.org/"):
            clean_doi = clean_doi[16:]
        if clean_doi.startswith("http://doi.org/"):
            clean_doi = clean_doi[15:]
        if not clean_doi:
            return None

        try:
            response = requests.get(
                f"https://api.crossref.org/works/{clean_doi}",
                headers={"Accept": "application/json"},
                timeout=15,
            )
            if response.status_code != 200:
                return None

            data = response.json().get("message", {})
            authors = []
            for item in data.get("author", []):
                name = " ".join(filter(None, [item.get("given", ""), item.get("family", "")]))
                if name:
                    authors.append(name)

            abstract = data.get("abstract", "") or ""
            abstract = re.sub(r"<[^>]+>", "", abstract)

            container = data.get("container-title", [])
            journal = container[0] if container else ""

            published = data.get("published-print", data.get("published-online", {}))
            date_parts = published.get("date-parts", [[]])
            year = ""
            if date_parts and date_parts[0]:
                year = str(date_parts[0][0])

            return {
                "abstract": abstract,
                "authors": authors,
                "journal": journal,
                "year": year,
            }
        except Exception as exc:  # noqa: BLE001
            print(f"[Stage 3] CrossRef fetch failed [{doi[:40]}]: {exc}")
            return None

    def run(self, **kwargs) -> Dict[str, Any]:
        """Run stage 3 and persist execution metadata back into the project."""

        print(f"[Stage 3] Start extraction | language: {self.project.language}")
        print(
            f"[Stage 3] Literature: {len(self.project.literature)} | "
            f"Notes: {len(self.project.obsidian_notes)}"
        )

        self.project.mark_stage_start(self.STAGE_NUM)
        task_manager = self._get_task_manager()
        task_layer_snapshot = self._get_task_layer_snapshot(task_manager)
        capability_snapshot = task_layer_snapshot.get("ner_options", {})
        execution_config = self._build_execution_config(kwargs)

        self.project.set_stage_metadata(
            self.STAGE_NUM,
            capability_snapshot=capability_snapshot,
            task_layer_snapshot=task_layer_snapshot,
            requested_execution={
                key: value
                for key, value in execution_config.items()
                if key in {"backend", "provider", "model", "fallback_backends", "categories"}
            },
        )

        all_entities: List[HistoricalEntity] = []
        all_relations: List[EntityRelation] = []
        execution_records: List[Dict[str, Any]] = []

        literature_entities, literature_relations, literature_records = self._extract_from_literature(
            execution_config
        )
        all_entities.extend(literature_entities)
        all_relations.extend(literature_relations)
        execution_records.extend(literature_records)
        print(f"[Stage 3] Literature entities: {len(literature_entities)}")

        if self.project.obsidian_notes:
            note_entities, note_relations, note_records = self._extract_from_notes(execution_config)
            all_entities.extend(note_entities)
            all_relations.extend(note_relations)
            execution_records.extend(note_records)
            print(f"[Stage 3] Note entities: {len(note_entities)}")

        if all_entities and self.project.language != "en":
            all_entities = self._disambiguate_entities(all_entities)

        merged_entities = self._merge_entities(all_entities)
        merged_relations = self._deduplicate_relations(all_relations)

        self.project.entities = merged_entities
        self.project.entity_relations = merged_relations

        self._flush_review_items()
        backend_summary = self._summarize_execution_records(execution_records)
        if self._disambiguation_packages:
            backend_summary["disambiguation_packages"] = self._disambiguation_packages
        self.project.set_stage_metadata(
            self.STAGE_NUM,
            execution_summary=backend_summary,
            review_count=len(self._stage_reviews),
            warning_count=len(self._stage_warnings),
        )

        self.project.mark_stage_done(self.STAGE_NUM)

        result = {
            "entities": merged_entities,
            "relations": merged_relations,
            "total_entities": len(merged_entities),
            "total_relations": len(merged_relations),
            "execution_summary": backend_summary,
            "review_count": len(self._stage_reviews),
        }

        print(
            f"[Stage 3] Done | entities: {len(merged_entities)} | "
            f"relations: {len(merged_relations)}"
        )
        self._print_entity_summary(merged_entities)
        return result

    def _build_execution_config(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve stage-level execution preferences."""

        categories = kwargs.get("categories") or [
            "person",
            "location",
            "organization",
            "event",
            "concept",
            "literature",
        ]
        fallback_backends = kwargs.get("fallback_backends")
        if fallback_backends is None:
            fallback_backends = ["local_llm", "script"]

        execution_config = {
            "backend": kwargs.get("ner_backend") or kwargs.get("backend"),
            "provider": kwargs.get("ner_provider") or kwargs.get("provider") or "qwen",
            "model": kwargs.get("ner_model") or kwargs.get("model"),
            "fallback_backends": list(fallback_backends),
            "categories": list(categories),
            "temperature": kwargs.get("temperature", 0.1),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }
        if kwargs.get("test_mode"):
            execution_config["backend"] = "script"
            execution_config["fallback_backends"] = []
        return execution_config

    def _get_task_layer_snapshot(self, task_manager: TaskManager) -> Dict[str, Any]:
        """Capture a redacted unified task-layer snapshot for Stage 3."""

        ner_options = task_manager.get_task_options("ner")
        snapshot: Dict[str, Any] = {
            "schema_version": "1.0",
            "task": "ner",
            "ner_options": ner_options,
        }
        if hasattr(task_manager, "get_task_registry"):
            registry = task_manager.get_task_registry(detailed=True)
            snapshot["registry"] = {
                "schema_version": registry.get("schema_version"),
                "module": registry.get("module"),
                "task": registry.get("tasks", {}).get("ner", {}),
                "aliases": {
                    alias: canonical
                    for alias, canonical in registry.get("aliases", {}).items()
                    if canonical == "ner"
                },
            }
        if hasattr(task_manager, "get_capabilities"):
            capabilities = task_manager.get_capabilities()
            snapshot["manager"] = {
                "type": capabilities.get("type"),
                "schema_version": capabilities.get("schema_version"),
                "module": capabilities.get("module"),
                "mode": capabilities.get("mode"),
                "provider": capabilities.get("provider"),
                "backend_options": capabilities.get("backend_options", []),
                "privacy": capabilities.get("privacy", {}),
            }
        return snapshot

    def _extract_from_literature(
        self,
        execution_config: Dict[str, Any],
    ) -> Tuple[List[HistoricalEntity], List[EntityRelation], List[Dict[str, Any]]]:
        """Extract entities from literature records."""

        entities: List[HistoricalEntity] = []
        relations: List[EntityRelation] = []
        execution_records: List[Dict[str, Any]] = []

        for paper in self.project.literature:
            original_abstract = paper.abstract or ""
            original_authors = list(paper.authors) if paper.authors else []

            doi_to_use = paper.doi or ""
            if not doi_to_use and paper.url:
                match = re.search(r"(10\.\d{4,}/[^\s\?#]+)", paper.url)
                if match:
                    doi_to_use = match.group(1).rstrip(".")

            if not original_abstract and doi_to_use:
                metadata = self._fetch_crossref_metadata(doi_to_use)
                if metadata:
                    paper.abstract = metadata.get("abstract", "")
                    if not paper.authors and metadata.get("authors"):
                        paper.authors = metadata["authors"]
                    if not paper.journal and metadata.get("journal"):
                        paper.journal = metadata["journal"]

            authors_str = " ".join(paper.authors) if paper.authors else ""
            text = f"{paper.title} {authors_str} {paper.journal or ''} {paper.abstract or ''}".strip()
            if not text or len(text) < 10:
                text = paper.title

            try:
                extracted, record = self._ner_extract(
                    text=text,
                    source_kind="paper",
                    source_id=paper.id or paper.title,
                    source_title=paper.title,
                    execution_config=execution_config,
                )
                for entity in extracted:
                    entity.related_entities.append(f"paper:{paper.id}")
                entities.extend(extracted)
                execution_records.append(record)
            except Exception as exc:  # noqa: BLE001
                print(f"[Stage 3] Literature extraction failed [{paper.title[:40]}]: {exc}")
                self._stage_warnings.append(f"paper:{paper.id or paper.title}")
            finally:
                paper.abstract = original_abstract
                paper.authors = original_authors

        return entities, relations, execution_records

    def _extract_from_notes(
        self,
        execution_config: Dict[str, Any],
    ) -> Tuple[List[HistoricalEntity], List[EntityRelation], List[Dict[str, Any]]]:
        """Extract entities from Obsidian notes."""

        entities: List[HistoricalEntity] = []
        relations: List[EntityRelation] = []
        execution_records: List[Dict[str, Any]] = []

        for note in self.project.obsidian_notes:
            content = note.get("content", "") or ""
            if not content or len(content) < 20:
                continue

            try:
                extracted, record = self._ner_extract(
                    text=content,
                    source_kind="note",
                    source_id=note.get("id", note.get("title", "note")),
                    source_title=note.get("title", ""),
                    execution_config=execution_config,
                )
                for entity in extracted:
                    entity.related_entities.append(f"note:{note.get('id', note.get('title', ''))}")
                entities.extend(extracted)
                execution_records.append(record)
            except Exception as exc:  # noqa: BLE001
                print(f"[Stage 3] Note extraction failed [{note.get('title', '')[:40]}]: {exc}")
                self._stage_warnings.append(f"note:{note.get('id', note.get('title', ''))}")

        return entities, relations, execution_records

    def _ner_extract(
        self,
        text: str,
        source_kind: str,
        source_id: str,
        source_title: str,
        execution_config: Dict[str, Any],
    ) -> Tuple[List[HistoricalEntity], Dict[str, Any]]:
        """Run NER through the unified task layer and normalize the results."""

        result, task_package = self._execute_ner_task(
            "ner",
            text=text,
            categories=execution_config["categories"],
            backend=execution_config.get("backend"),
            provider=execution_config.get("provider"),
            model=execution_config.get("model"),
            fallback_backends=execution_config.get("fallback_backends", []),
            temperature=execution_config.get("temperature", 0.1),
            max_tokens=execution_config.get("max_tokens", 2000),
        )
        if not result.get("success"):
            raise RuntimeError(result.get("error") or "NER task failed")

        payload = result.get("data", {}) or {}
        items = payload.get("entities", [])
        metadata = result.get("metadata", {}) or {}

        entities: List[HistoricalEntity] = []
        for item in items:
            entity = self._normalize_entity(item)
            entity.related_entities.append(f"source:{source_kind}:{source_id}")
            entities.append(entity)
            self._register_review_signal(
                source_kind=source_kind,
                source_id=source_id,
                source_title=source_title,
                entity=entity,
                raw_item=item,
                metadata=metadata,
            )

        execution_record = {
            "type": "ner_extraction",
            "source_kind": source_kind,
            "source_id": source_id,
            "source_title": source_title,
            "backend": result.get("backend") or metadata.get("backend"),
            "provider": metadata.get("provider"),
            "model": metadata.get("model"),
            "entity_count": len(entities),
            "needs_review_count": sum(
                1 for item in items if item.get("needs_review") or float(item.get("confidence", 0.0)) < 0.6
            ),
            "confidence": self._estimate_ner_confidence(items, metadata),
            "needs_review": any(
                item.get("needs_review") or float(item.get("confidence", 0.0)) < 0.6 for item in items
            ),
            "quality_flags": self._ner_quality_flags(text, items, metadata),
            "categories": execution_config.get("categories", []),
            "entity_names": [entity.name for entity in entities[:20]],
            "task_package": self._summarize_task_package(task_package),
        }
        return entities, execution_record

    def _execute_ner_task(self, task_type: str, **kwargs: Any) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        manager = self._get_task_manager()
        if hasattr(manager, "execute_task_package"):
            task_package = manager.execute_task_package(task_type, **kwargs)
            result = task_package.get("result") or {
                "success": task_package.get("success"),
                "data": task_package.get("data", {}),
                "backend": task_package.get("backend"),
                "metadata": {
                    "backend": task_package.get("backend"),
                    "provider": task_package.get("provider"),
                    "model": task_package.get("model"),
                },
                "error": task_package.get("error"),
            }
            return result, task_package
        return manager.execute_task(task_type, **kwargs), None

    def _summarize_task_package(self, package: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not package:
            return None
        return {
            "type": package.get("type"),
            "task_type": package.get("task_type"),
            "backend": package.get("backend"),
            "provider": package.get("provider"),
            "model": package.get("model"),
            "confidence": package.get("confidence"),
            "needs_review": package.get("needs_review"),
            "quality_flags": package.get("quality_flags", []),
            "artifact_count": len(package.get("artifacts", []) or []),
        }

    def _ner_quality_flags(
        self,
        text: str,
        items: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ) -> List[str]:
        flags: List[str] = []
        if not text or not text.strip():
            flags.append("empty_text")
        if 0 < len(text.strip()) < 20:
            flags.append("very_short_text")
        if not items:
            flags.append("no_entities")
        if any(float(item.get("confidence", 0.0)) < 0.6 for item in items):
            flags.append("low_confidence_entities")
        if not metadata.get("backend"):
            flags.append("missing_backend_metadata")
        return flags

    def _estimate_ner_confidence(self, items: List[Dict[str, Any]], metadata: Dict[str, Any]) -> float:
        if not items:
            return 0.25
        values = [float(item.get("confidence", 0.5)) for item in items]
        confidence = sum(values) / len(values)
        if not metadata.get("backend"):
            confidence -= 0.1
        return round(max(0.1, min(confidence, 0.95)), 2)

    def _llm_extract_entities(
        self,
        text: str,
        title: str = "",
        max_tokens: int = 2000,
    ) -> List[HistoricalEntity]:
        """Backward-compatible helper that prefers the remote LLM backend."""

        entities, _ = self._ner_extract(
            text=text,
            source_kind="llm_text",
            source_id=title or "text",
            source_title=title,
            execution_config={
                "backend": "llm_api",
                "provider": "qwen",
                "model": None,
                "fallback_backends": ["local_llm", "script"],
                "categories": ["person", "location", "organization", "event", "concept", "literature"],
                "temperature": 0.1,
                "max_tokens": max_tokens,
            },
        )
        return entities

    def _normalize_entity(self, item: Dict[str, Any]) -> HistoricalEntity:
        """Convert normalized task output into workflow entity objects."""

        name = item.get("entity") or item.get("text") or item.get("name") or ""
        notes = item.get("reason") or item.get("meaning") or ""
        return HistoricalEntity(
            id=str(uuid.uuid4())[:8],
            name=name,
            name_zh=item.get("name_zh", "") or item.get("standard_name", ""),
            category=item.get("category", "unknown"),
            confidence=float(item.get("confidence", 0.5)),
            notes=notes,
            related_entities=[],
        )

    def _register_review_signal(
        self,
        source_kind: str,
        source_id: str,
        source_title: str,
        entity: HistoricalEntity,
        raw_item: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> None:
        """Queue low-confidence or flagged entities for manual review."""

        needs_review = bool(raw_item.get("needs_review")) or entity.confidence < 0.6
        if not needs_review:
            return

        self._stage_reviews.append(
            {
                "stage": self.STAGE_NUM,
                "type": "entity_review",
                "source_kind": source_kind,
                "source_id": source_id,
                "source_title": source_title,
                "entity": entity.name,
                "category": entity.category,
                "confidence": entity.confidence,
                "backend": metadata.get("backend"),
                "provider": metadata.get("provider"),
                "model": metadata.get("model"),
            }
        )

    def _flush_review_items(self) -> None:
        """Persist stage review items into the project review queue."""

        for item in self._stage_reviews:
            self.project.add_review_item(item)
        if self._stage_reviews:
            self.project.add_quality_flag("stage3_manual_review_needed")
        if self._stage_warnings:
            self.project.add_quality_flag("stage3_partial_extraction_warnings")

    def _summarize_execution_records(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build a compact execution summary for stage metadata."""

        backend_counter = Counter(record.get("backend") or "unknown" for record in records)
        provider_counter = Counter(record.get("provider") or "unknown" for record in records)
        return {
            "documents_processed": len(records),
            "entities_extracted": sum(record.get("entity_count", 0) for record in records),
            "needs_review_count": sum(record.get("needs_review_count", 0) for record in records),
            "by_backend": dict(backend_counter),
            "by_provider": dict(provider_counter),
            "packages": [
                {
                    key: record.get(key)
                    for key in (
                        "type",
                        "source_kind",
                        "source_id",
                        "source_title",
                        "backend",
                        "provider",
                        "model",
                        "entity_count",
                        "confidence",
                        "needs_review",
                        "quality_flags",
                        "categories",
                        "task_package",
                    )
                }
                for record in records
            ],
        }

    def _disambiguate_entities(self, entities: List[HistoricalEntity]) -> List[HistoricalEntity]:
        """Run entity disambiguation when available."""

        try:
            disambiguator = self._get_ner_disambiguator()
            if disambiguator is None:
                return entities

            print(f"[Stage 3] Disambiguating {len(entities)} entities")
            ner_results = [
                (entity.name, entity.category, 0, len(entity.name))
                for entity in entities
                if entity.name
            ]
            if not ner_results:
                return entities

            if hasattr(disambiguator, "disambiguate_package"):
                package = disambiguator.disambiguate_package(ner_results, self.project.topic)
                self._disambiguation_packages.append(self._summarize_disambiguation_package(package))
                disambiguated_items = package.get("entities", [])
                if package.get("needs_review"):
                    self.project.add_quality_flag("stage3_disambiguation_review_needed")
            else:
                disambiguated_items = disambiguator.disambiguate(ner_results, self.project.topic)
            disambiguated_map = {
                item.get("original_entity", ""): item
                for item in disambiguated_items
                if item.get("original_entity")
            }

            resolved: List[HistoricalEntity] = []
            for entity in entities:
                data = disambiguated_map.get(entity.name)
                if data:
                    entity.category = data.get("disambiguated_type", entity.category)
                    entity.confidence = float(data.get("confidence", entity.confidence))
                    if data.get("standard_name"):
                        entity.name_zh = data["standard_name"]
                resolved.append(entity)
            return resolved
        except Exception as exc:  # noqa: BLE001
            print(f"[Stage 3] Entity disambiguation failed: {exc}")
            self._stage_warnings.append("entity_disambiguation_failed")
            return entities

    def _summarize_disambiguation_package(self, package: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": package.get("type"),
            "backend": package.get("backend"),
            "provider": package.get("provider"),
            "model": package.get("model"),
            "confidence": package.get("confidence"),
            "needs_review": bool(package.get("needs_review")),
            "quality_flags": package.get("quality_flags", []),
            "summary": package.get("summary", {}),
        }

    def _merge_entities(self, entities: List[HistoricalEntity]) -> List[HistoricalEntity]:
        """Merge duplicate entities and keep the highest-confidence version."""

        if not entities:
            return []

        seen: Dict[str, HistoricalEntity] = {}
        for entity in entities:
            key = entity.name.lower().strip()
            if not key:
                continue
            if key not in seen or entity.confidence > seen[key].confidence:
                seen[key] = entity

        merged = list(seen.values())
        merged.sort(key=lambda item: (item.category, -item.confidence, item.name))
        print(f"[Stage 3] Entity dedupe: {len(entities)} -> {len(merged)}")
        return merged

    def _deduplicate_relations(self, relations: List[EntityRelation]) -> List[EntityRelation]:
        """Deduplicate entity relations."""

        seen = set()
        unique: List[EntityRelation] = []
        for relation in relations:
            key = (
                relation.from_entity.lower(),
                relation.to_entity.lower(),
                relation.relation_type,
            )
            if key not in seen:
                seen.add(key)
                unique.append(relation)
        return unique

    def _print_entity_summary(self, entities: List[HistoricalEntity]) -> None:
        """Print a compact entity summary for the console workflow."""

        counts = Counter(entity.category for entity in entities)
        for category, count in counts.most_common():
            sample = [entity.name for entity in entities if entity.category == category][:3]
            print(f"  [{category}] {count}: {', '.join(sample)}")
