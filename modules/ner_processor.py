from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional

from modules.unified_task_executor import TaskConfig, TaskType, UnifiedTaskExecutor


class NERProcessor:
    """Historical NER processor with unified multi-backend execution."""

    ENTITY_CATEGORIES = {
        "person": "Historical Figure",
        "location": "Location",
        "organization": "Organization",
        "event": "Historical Event",
        "date": "Date/Period",
        "work": "Work/Literature",
        "concept": "Concept/Idea",
        "custom": "Custom",
    }

    JAPAN_HISTORICAL_ENTITIES = {
        "eras": ["明治", "大正", "昭和", "平成", "令和", "奈良", "平安", "镰仓", "室町", "战国", "江户"],
        "institutions": ["幕府", "朝廷", "国会", "贵族院", "众议院", "内务省", "外务省", "太政官"],
        "political_groups": ["萨摩藩", "长州藩", "土佐藩", "肥前藩", "公家", "武家", "藩士", "平民"],
    }

    PERSON_PATTERNS = [
        re.compile(r"[\u4e00-\u9fff]{2,4}(?:天皇|将军|公|侯|氏|子)?"),
    ]
    LOCATION_PATTERNS = [
        re.compile(r"[\u4e00-\u9fff]{2,6}(?:国|都|道|府|县|縣|市|村|町)"),
    ]
    DATE_PATTERNS = [
        re.compile(r"\d{3,4}年(?:\d{1,2}月(?:\d{1,2}日)?)?"),
        re.compile(r"(?:明治|大正|昭和|平成|令和)\d{1,2}年"),
    ]

    def __init__(
        self,
        api_provider: str = "qwen",
        test_mode: bool = True,
        backend: Optional[str] = None,
        local_model: Optional[str] = None,
    ):
        self.api_provider = api_provider
        self.test_mode = test_mode
        self.backend = backend
        self.local_model = local_model
        self.executor = UnifiedTaskExecutor(default_mode="script" if test_mode else "auto")
        self.executor.set_provider(api_provider)
        self.last_result_metadata: Dict[str, Any] = {}
        self.recognized_entities: List[Dict[str, Any]] = []
        self.entity_cache: Dict[str, List[Dict[str, Any]]] = {}

    def get_capabilities(self) -> Dict[str, Any]:
        capability = self.executor.get_task_capability("ner")
        capability.setdefault("module", "ner_processor")
        capability.setdefault("fallback_order", ["script", "local_llm", "llm_api", "skill", "mcp", "hybrid"])
        capability["active_backend"] = self._default_backend()
        capability["provider"] = self.api_provider
        capability["model"] = self.local_model
        capability["test_mode"] = self.test_mode
        return capability

    def _default_backend(self) -> str:
        if self.backend:
            return self.backend
        if self.test_mode:
            return "script"
        return "llm_api"

    def _default_fallbacks(self, backend: str) -> List[str]:
        if backend == "script":
            return []
        if backend == "local_llm":
            return ["script"]
        return ["local_llm", "script"]

    def _normalize_entity(self, entity: Dict[str, Any], text: str, backend: str) -> Dict[str, Any]:
        name = entity.get("entity") or entity.get("text") or entity.get("name") or ""
        start_pos = entity.get("start_pos")
        end_pos = entity.get("end_pos")
        if start_pos is None and entity.get("position") is not None:
            start_pos = int(entity["position"])
        if end_pos is None and start_pos is not None and name:
            end_pos = int(start_pos) + len(name)
        confidence = entity.get("confidence")
        if confidence is None:
            confidence = 0.45 if backend == "script" else 0.75
        normalized = {
            "entity": name,
            "text": name,
            "category": entity.get("category", "unknown"),
            "start_pos": start_pos,
            "end_pos": end_pos,
            "confidence": float(confidence),
            "notes": entity.get("notes", ""),
            "source": entity.get("source", backend),
            "backend": backend,
            "provider": self.last_result_metadata.get("provider", self.api_provider),
            "model": self.last_result_metadata.get("model"),
            "needs_review": bool(entity.get("needs_review", False)),
        }
        if not normalized["entity"] and start_pos is not None and end_pos is not None:
            normalized["entity"] = text[start_pos:end_pos]
            normalized["text"] = normalized["entity"]
        return normalized

    def _rule_entities(self, text: str, categories: Optional[List[str]]) -> List[Dict[str, Any]]:
        allowed = set(categories or ["person", "location", "date"])
        entities: List[Dict[str, Any]] = []

        if "person" in allowed:
            for pattern in self.PERSON_PATTERNS:
                for match in pattern.finditer(text):
                    entities.append(
                        {
                            "entity": match.group(),
                            "category": "person",
                            "start_pos": match.start(),
                            "end_pos": match.end(),
                            "confidence": 0.4,
                            "source": "rule",
                        }
                    )
        if "location" in allowed:
            for pattern in self.LOCATION_PATTERNS:
                for match in pattern.finditer(text):
                    entities.append(
                        {
                            "entity": match.group(),
                            "category": "location",
                            "start_pos": match.start(),
                            "end_pos": match.end(),
                            "confidence": 0.45,
                            "source": "rule",
                        }
                    )
        if "date" in allowed:
            for pattern in self.DATE_PATTERNS:
                for match in pattern.finditer(text):
                    entities.append(
                        {
                            "entity": match.group(),
                            "category": "date",
                            "start_pos": match.start(),
                            "end_pos": match.end(),
                            "confidence": 0.7,
                            "source": "rule",
                        }
                    )

        # Lexicon enrichment
        joined_lexicon = {
            "date": self.JAPAN_HISTORICAL_ENTITIES["eras"],
            "organization": self.JAPAN_HISTORICAL_ENTITIES["institutions"] + self.JAPAN_HISTORICAL_ENTITIES["political_groups"],
        }
        for category, candidates in joined_lexicon.items():
            if category not in allowed and category != "organization":
                continue
            if category == "organization" and "organization" not in allowed:
                continue
            for candidate in candidates:
                start = 0
                while True:
                    pos = text.find(candidate, start)
                    if pos == -1:
                        break
                    entities.append(
                        {
                            "entity": candidate,
                            "category": category,
                            "start_pos": pos,
                            "end_pos": pos + len(candidate),
                            "confidence": 0.8,
                            "source": "lexicon",
                        }
                    )
                    start = pos + 1
        return entities

    def _merge_entities(self, text: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged: Dict[tuple, Dict[str, Any]] = {}
        for entity in entities:
            normalized = self._normalize_entity(entity, text, entity.get("backend", entity.get("source", "script")))
            key = (normalized["entity"], normalized["category"], normalized["start_pos"], normalized["end_pos"])
            existing = merged.get(key)
            if existing is None or normalized["confidence"] > existing["confidence"]:
                merged[key] = normalized
            elif existing is not None:
                existing["needs_review"] = existing["needs_review"] or normalized["needs_review"]
        ordered = list(merged.values())
        ordered.sort(key=lambda item: (item.get("start_pos") or 10**9, item["entity"]))
        return ordered

    def recognize_historical_entities(
        self,
        text: str,
        categories: Optional[List[str]] = None,
        backend: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        cache_key = json.dumps({"text": text[:500], "categories": categories, "backend": backend}, ensure_ascii=False)
        if cache_key in self.entity_cache:
            return self.entity_cache[cache_key]

        selected_backend = backend or self._default_backend()
        config = TaskConfig(
            task_type=TaskType.NER,
            provider=self.api_provider,
            model=self.local_model if selected_backend == "local_llm" else None,
            backend=selected_backend,
            fallback_backends=self._default_fallbacks(selected_backend),
            cache_enabled=True,
            extra_params={"local_model": self.local_model} if self.local_model else {},
        )
        result = self.executor.execute("ner", config=config, text=text, categories=categories)
        self.last_result_metadata = result.metadata

        executor_entities = result.data.get("entities", []) if result.success and isinstance(result.data, dict) else []
        rule_entities = self._rule_entities(text, categories)
        if selected_backend == "script":
            merged = self._merge_entities(text, rule_entities + executor_entities)
        else:
            merged = self._merge_entities(text, executor_entities + rule_entities)

        self.recognized_entities.extend(merged)
        self.entity_cache[cache_key] = merged
        return merged

    def recognize_historical_entities_package(
        self,
        text: str,
        categories: Optional[List[str]] = None,
        backend: Optional[str] = None,
        source: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run NER and return a workflow-ready extraction envelope."""
        entities = self.recognize_historical_entities(text, categories=categories, backend=backend)
        relationships = self.extract_entity_relationships(text, entities)
        stats = self.get_entity_statistics(entities)
        quality_flags = self._package_quality_flags(text, entities)
        confidence = self._package_confidence(entities, quality_flags)
        metadata = dict(self.last_result_metadata or {})
        selected_backend = metadata.get("backend") or backend or self._default_backend()
        provider = metadata.get("provider") or self.api_provider
        model = metadata.get("model") or (self.local_model if selected_backend == "local_llm" else None)
        return {
            "type": "ner_extraction",
            "source": dict(source or {}),
            "text_length": len(text or ""),
            "entities": entities,
            "relationships": relationships,
            "classified_entities": self.classify_entities(entities),
            "statistics": stats,
            "backend": selected_backend,
            "provider": provider,
            "model": model,
            "confidence": confidence,
            "needs_review": bool(quality_flags),
            "quality_flags": quality_flags,
            "capabilities": self.get_capabilities(),
        }

    def _package_quality_flags(self, text: str, entities: List[Dict[str, Any]]) -> List[str]:
        flags: List[str] = []
        if not text or not text.strip():
            flags.append("empty_text")
        if 0 < len(text.strip()) < 20:
            flags.append("very_short_text")
        if not entities:
            flags.append("no_entities")
        if any(float(entity.get("confidence", 0.0)) < 0.6 for entity in entities):
            flags.append("low_confidence_entities")
        if not self.last_result_metadata.get("backend"):
            flags.append("missing_backend_metadata")
        return flags

    def _package_confidence(self, entities: List[Dict[str, Any]], quality_flags: List[str]) -> float:
        if not entities:
            return 0.2
        confidence = sum(float(entity.get("confidence", 0.0)) for entity in entities) / len(entities)
        confidence -= min(0.25, len(quality_flags) * 0.05)
        return round(max(0.1, min(confidence, 0.95)), 2)

    def classify_entities(self, entities: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        classified: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for entity in entities:
            classified[entity.get("category", "unknown")].append(entity)
        return dict(classified)

    def extract_entity_relationships(self, text: str, entities: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        relationships: List[Dict[str, str]] = []
        if len(entities) < 2:
            return relationships

        sentences = [sentence.strip() for sentence in re.split(r"[。！？!?]\s*|\n+", text) if sentence.strip()]
        for sentence in sentences:
            present = [entity for entity in entities if entity["entity"] in sentence]
            if len(present) < 2:
                continue
            relation = "co_occurs"
            if "属于" in sentence or "属" in sentence:
                relation = "belongs_to"
            elif "对抗" in sentence or "反对" in sentence:
                relation = "opposes"
            elif "参与" in sentence or "参加" in sentence:
                relation = "participated_in"
            for index in range(len(present) - 1):
                relationships.append(
                    {
                        "source": present[index]["entity"],
                        "target": present[index + 1]["entity"],
                        "relation": relation,
                        "description": sentence[:120],
                    }
                )
        return relationships

    def batch_process_documents(
        self,
        documents: List[Dict[str, Any]],
        categories: Optional[List[str]] = None,
        backend: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for document in documents:
            text = document.get("text", "")
            metadata = document.get("metadata", {})
            entities = self.recognize_historical_entities(text, categories=categories, backend=backend)
            results.append(
                {
                    "metadata": metadata,
                    "entities": entities,
                    "classified_entities": self.classify_entities(entities),
                    "relationships": self.extract_entity_relationships(text, entities),
                    "entity_count": len(entities),
                    "backend": self.last_result_metadata.get("backend"),
                }
            )
        return results

    def batch_process_documents_package(
        self,
        documents: List[Dict[str, Any]],
        categories: Optional[List[str]] = None,
        backend: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process many documents and return a batch-level NER envelope."""
        packages = []
        for index, document in enumerate(documents):
            source = dict(document.get("metadata", {}))
            source.setdefault("index", index)
            if document.get("id"):
                source.setdefault("id", document["id"])
            if document.get("title"):
                source.setdefault("title", document["title"])
            packages.append(
                self.recognize_historical_entities_package(
                    document.get("text", ""),
                    categories=categories,
                    backend=backend,
                    source=source,
                )
            )
        quality_flags = []
        if not packages:
            quality_flags.append("no_documents")
        if any(package.get("needs_review") for package in packages):
            quality_flags.append("document_review_needed")
        entity_count = sum(len(package.get("entities", [])) for package in packages)
        return {
            "type": "ner_batch",
            "documents_processed": len(packages),
            "entity_count": entity_count,
            "packages": packages,
            "backend": packages[-1].get("backend") if packages else (backend or self._default_backend()),
            "provider": packages[-1].get("provider") if packages else self.api_provider,
            "model": packages[-1].get("model") if packages else self.local_model,
            "confidence": round(
                sum(package.get("confidence", 0.0) for package in packages) / len(packages),
                2,
            )
            if packages
            else 0.2,
            "needs_review": bool(quality_flags),
            "quality_flags": quality_flags,
            "capabilities": self.get_capabilities(),
        }

    def get_entity_statistics(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(entities)
        category_counts = defaultdict(int)
        confidence_sum = 0.0
        for entity in entities:
            category_counts[entity.get("category", "unknown")] += 1
            confidence_sum += float(entity.get("confidence", 0.0))
        return {
            "total_entities": total,
            "category_distribution": dict(category_counts),
            "average_confidence": confidence_sum / total if total else 0.0,
            "most_common_category": max(category_counts.items(), key=lambda item: item[1])[0] if category_counts else None,
            "backend": self.last_result_metadata.get("backend"),
        }

    def filter_entities_by_confidence(
        self,
        entities: List[Dict[str, Any]],
        threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        return [entity for entity in entities if float(entity.get("confidence", 0.0)) >= threshold]

    def search_entities(self, query: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        return [
            entity
            for entity in entities
            if query_lower in entity.get("entity", "").lower()
            or query_lower in entity.get("notes", "").lower()
        ]

    def export_entities_for_obsidian(
        self,
        entities: List[Dict[str, Any]],
        output_format: str = "json",
    ) -> str:
        if output_format == "markdown":
            lines = ["# Entities", ""]
            for entity in entities:
                lines.append(
                    f"- [[{entity.get('entity', '')}]] ({entity.get('category', 'unknown')}, confidence={entity.get('confidence', 0.0):.2f})"
                )
            return "\n".join(lines)
        return json.dumps(entities, ensure_ascii=False, indent=2)

    def create_entity_network(
        self,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        nodes = [
            {
                "id": entity.get("entity"),
                "label": entity.get("entity"),
                "category": entity.get("category"),
                "confidence": entity.get("confidence"),
            }
            for entity in entities
        ]
        edges = [
            {
                "source": relation.get("source"),
                "target": relation.get("target"),
                "relation": relation.get("relation"),
                "label": relation.get("relation"),
            }
            for relation in relationships
        ]
        return {"nodes": nodes, "edges": edges, "stats": {"total_nodes": len(nodes), "total_edges": len(edges)}}

    def recognize_person_entities(self, text: str) -> List[Dict[str, Any]]:
        return self.recognize_historical_entities(text, ["person"])

    def recognize_location_entities(self, text: str) -> List[Dict[str, Any]]:
        return self.recognize_historical_entities(text, ["location"])

    def recognize_event_entities(self, text: str) -> List[Dict[str, Any]]:
        return self.recognize_historical_entities(text, ["event"])

    def recognize_organization_entities(self, text: str) -> List[Dict[str, Any]]:
        return self.recognize_historical_entities(text, ["organization"])


def create_ner_processor(api_provider: str = "qwen", test_mode: bool = True) -> NERProcessor:
    return NERProcessor(api_provider=api_provider, test_mode=test_mode)
