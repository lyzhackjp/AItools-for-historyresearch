from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple


class EntityDisambiguator:
    """Disambiguate ambiguous historical entities using lightweight context rules."""

    AMBIGUOUS_ENTITIES: Dict[str, List[Dict[str, Any]]] = {
        "江户": [
            {"type": "location", "meaning": "东京的旧称或德川幕府所在地", "context_pattern": ["江户城", "江户湾", "江户幕府"], "standard_name": "江户"},
            {"type": "organization", "meaning": "江户幕府的简称", "context_pattern": ["幕府", "将军", "统治"], "standard_name": "德川幕府"},
        ],
        "萨摩": [
            {"type": "location", "meaning": "萨摩地区或鹿儿岛相关地理区域", "context_pattern": ["半岛", "地区", "鹿儿岛"], "standard_name": "萨摩"},
            {"type": "organization", "meaning": "萨摩藩", "context_pattern": ["藩", "藩士", "维新"], "standard_name": "萨摩藩"},
        ],
        "长州": [
            {"type": "location", "meaning": "长州地区", "context_pattern": ["地区", "山口", "海岸"], "standard_name": "长州"},
            {"type": "organization", "meaning": "长州藩", "context_pattern": ["藩", "藩士", "征讨"], "standard_name": "长州藩"},
        ],
        "会津": [
            {"type": "location", "meaning": "会津若松及周边地区", "context_pattern": ["若松", "地区", "地方"], "standard_name": "会津"},
            {"type": "organization", "meaning": "会津藩", "context_pattern": ["藩", "藩士", "战争"], "standard_name": "会津藩"},
        ],
        "幕府": [
            {"type": "organization", "meaning": "武士政权组织", "context_pattern": ["建立", "统治", "德川"], "standard_name": "幕府"},
            {"type": "historical_period", "meaning": "幕府时期作为历史时段", "context_pattern": ["时代", "前期", "后期"], "standard_name": "幕府时期"},
        ],
        "平安": [
            {"type": "location", "meaning": "平安京", "context_pattern": ["京", "都", "迁都"], "standard_name": "平安京"},
            {"type": "historical_period", "meaning": "平安时代", "context_pattern": ["时代", "前期", "后期"], "standard_name": "平安时代"},
        ],
        "明治": [
            {"type": "historical_period", "meaning": "明治时期或明治年号", "context_pattern": ["维新", "时代", "年"], "standard_name": "明治"},
            {"type": "person", "meaning": "明治天皇", "context_pattern": ["天皇", "陛下", "诏书"], "standard_name": "明治天皇"},
        ],
        "天皇": [
            {"type": "person", "meaning": "具体日本天皇", "context_pattern": ["陛下", "诏书", "御真影"], "standard_name": "天皇"},
            {"type": "concept", "meaning": "天皇制度概念", "context_pattern": ["制度", "制", "统治"], "standard_name": "天皇制"},
        ],
    }

    CONTEXT_KEYWORDS = {
        "organization": ["藩", "幕府", "政府", "院", "会", "官厅"],
        "location": ["县", "縣", "府", "都", "市", "村", "町", "地区", "半岛"],
        "person": ["氏", "公", "侯", "天皇", "将军", "学者"],
        "event": ["事件", "战争", "维新", "革命", "运动"],
        "historical_period": ["时代", "前期", "中期", "后期", "年号"],
        "concept": ["制度", "思想", "主义", "理论"],
    }

    def get_capabilities(self) -> Dict[str, Any]:
        """Return a machine-readable snapshot for workflow and agent routing."""

        return {
            "module": "ner_disambiguation",
            "layer": "analysis_postprocess",
            "backend": "script",
            "provider": "rule_dictionary",
            "model": None,
            "tasks": [
                "entity_disambiguation",
                "standard_name_resolution",
                "alias_context_resolution",
                "relation_rule_scan",
            ],
            "output_types": ["entity_disambiguation"],
            "rule_count": sum(len(candidates) for candidates in self.AMBIGUOUS_ENTITIES.values()),
            "ambiguous_entities": sorted(self.AMBIGUOUS_ENTITIES.keys()),
            "supported_types": sorted(self.CONTEXT_KEYWORDS.keys()),
            "supports": {
                "batch": True,
                "confidence": True,
                "standard_name": True,
                "external_ai_backend": False,
                "package_output": True,
            },
            "privacy": {
                "local_first": True,
                "secrets_required": False,
                "logs_raw_text": False,
            },
        }

    def disambiguate(self, entity: str, context: str) -> Dict[str, Any]:
        candidates = self.AMBIGUOUS_ENTITIES.get(entity)
        if not candidates:
            return {
                "entity": entity,
                "type": "unknown",
                "meaning": "No disambiguation rule matched.",
                "confidence": 0.0,
                "standard_name": entity,
            }

        best_candidate = None
        best_score = 0.0
        for candidate in candidates:
            score = self._calculate_match_score(context, candidate)
            if score > best_score:
                best_candidate = candidate
                best_score = score

        if best_candidate is None:
            return self._default_disambiguation(entity, context)

        return {
            "entity": entity,
            "type": best_candidate["type"],
            "meaning": best_candidate["meaning"],
            "confidence": round(best_score, 2),
            "standard_name": best_candidate.get("standard_name", entity),
        }

    def _calculate_match_score(self, context: str, candidate: Dict[str, Any]) -> float:
        score = 0.0
        for pattern in candidate.get("context_pattern", []):
            if pattern and pattern in context:
                score += 0.35
        for keyword in self.CONTEXT_KEYWORDS.get(candidate["type"], []):
            if keyword in context:
                score += 0.1
        return min(score, 1.0)

    def _default_disambiguation(self, entity: str, context: str) -> Dict[str, Any]:
        type_scores: Dict[str, int] = {}
        for entity_type, keywords in self.CONTEXT_KEYWORDS.items():
            type_scores[entity_type] = sum(1 for keyword in keywords if keyword in context)
        best_type = max(type_scores.items(), key=lambda item: item[1])[0] if type_scores else "unknown"
        confidence = 0.5 if type_scores.get(best_type, 0) > 0 else 0.0
        return {
            "entity": entity,
            "type": best_type,
            "meaning": "Inferred from coarse context keywords.",
            "confidence": confidence,
            "standard_name": entity,
        }

    def batch_disambiguate(self, entities: List[Dict[str, Any]], context: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for entity in entities:
            entity_text = entity.get("text") or entity.get("entity") or ""
            if not entity_text:
                results.append(entity)
                continue
            info = self.disambiguate(entity_text, context)
            merged = dict(entity)
            merged.update(info)
            results.append(merged)
        return results

    def batch_disambiguate_package(
        self,
        entities: List[Dict[str, Any]],
        context: str,
    ) -> Dict[str, Any]:
        """Disambiguate entities and return a workflow-friendly package."""

        quality_flags = []
        if not entities:
            quality_flags.append("empty_entities")
        if not str(context or "").strip():
            quality_flags.append("empty_context")

        results = self.batch_disambiguate(entities, context or "")
        low_confidence_count = sum(1 for item in results if float(item.get("confidence", 0.0)) < 0.5)
        unknown_count = sum(1 for item in results if item.get("type") == "unknown")
        standard_name_count = sum(
            1
            for item in results
            if item.get("standard_name") and item.get("standard_name") != (item.get("entity") or item.get("text"))
        )

        if low_confidence_count:
            quality_flags.append("low_confidence_disambiguation")
        if unknown_count:
            quality_flags.append("unknown_entity_rules")

        confidence_values = [float(item.get("confidence", 0.0)) for item in results]
        average_confidence = round(sum(confidence_values) / len(confidence_values), 2) if confidence_values else 0.0

        return {
            "type": "entity_disambiguation",
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "backend": "script",
            "provider": "rule_dictionary",
            "model": None,
            "confidence": self._package_confidence(results, quality_flags, average_confidence),
            "needs_review": bool(quality_flags),
            "quality_flags": quality_flags,
            "entities": results,
            "summary": {
                "input_count": len(entities),
                "resolved_count": len(results),
                "standard_name_count": standard_name_count,
                "unknown_count": unknown_count,
                "low_confidence_count": low_confidence_count,
                "average_confidence": average_confidence,
            },
            "capabilities": self.get_capabilities(),
            "error": "",
        }

    def _package_confidence(
        self,
        results: List[Dict[str, Any]],
        quality_flags: List[str],
        average_confidence: float,
    ) -> float:
        if not results:
            return 0.0
        score = average_confidence
        if "empty_context" in quality_flags:
            score -= 0.15
        if "unknown_entity_rules" in quality_flags:
            score -= 0.10
        return round(max(0.0, min(1.0, score)), 2)


class NERDisambiguation:
    """Compatibility wrapper for workflow stage usage."""

    def __init__(self):
        self.disambiguator = EntityDisambiguator()

    def get_capabilities(self) -> Dict[str, Any]:
        return self.disambiguator.get_capabilities()

    def disambiguate(
        self,
        ner_results: List[Tuple[str, str, int, int]],
        context: str,
    ) -> List[Dict[str, Any]]:
        outputs: List[Dict[str, Any]] = []
        for entity_text, entity_type, start_pos, end_pos in ner_results:
            info = self.disambiguator.disambiguate(entity_text, context)
            outputs.append(
                {
                    "original_entity": entity_text,
                    "original_type": entity_type,
                    "start_pos": start_pos,
                    "end_pos": end_pos,
                    "disambiguated_type": info.get("type", entity_type),
                    "standard_name": info.get("standard_name", entity_text),
                    "confidence": info.get("confidence", 0.0),
                    "meaning": info.get("meaning", ""),
                }
            )
        return outputs

    def disambiguate_package(
        self,
        ner_results: List[Tuple[str, str, int, int]],
        context: str,
    ) -> Dict[str, Any]:
        entities = [
            {
                "text": entity_text,
                "entity": entity_text,
                "original_type": entity_type,
                "start_pos": start_pos,
                "end_pos": end_pos,
            }
            for entity_text, entity_type, start_pos, end_pos in ner_results
        ]
        package = self.disambiguator.batch_disambiguate_package(entities, context)
        package["entities"] = [
            {
                "original_entity": item.get("entity") or item.get("text", ""),
                "original_type": item.get("original_type", ""),
                "start_pos": item.get("start_pos", 0),
                "end_pos": item.get("end_pos", 0),
                "disambiguated_type": item.get("type", item.get("original_type", "")),
                "standard_name": item.get("standard_name", item.get("entity") or item.get("text", "")),
                "confidence": item.get("confidence", 0.0),
                "meaning": item.get("meaning", ""),
            }
            for item in package.get("entities", [])
        ]
        return package


class EntityRelationResolver:
    RELATION_PATTERNS = {
        "located_in": ["位于", "在", "属于"],
        "participated_in": ["参加", "参与", "出席"],
        "founded": ["创建", "建立", "创立"],
        "ruled_by": ["统治", "支配", "管辖"],
    }

    def resolve_relations(self, text: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        relations: List[Dict[str, Any]] = []
        for relation_type, patterns in self.RELATION_PATTERNS.items():
            for pattern in patterns:
                if pattern in text:
                    relations.append({"type": relation_type, "pattern": pattern, "context": text[:160]})
        return relations

    def resolve_relations_package(self, text: str, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        relations = self.resolve_relations(text, entities)
        quality_flags = []
        if not relations:
            quality_flags.append("no_relations_detected")
        return {
            "type": "entity_relation_resolution",
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "backend": "script",
            "provider": "rule_dictionary",
            "model": None,
            "confidence": 0.75 if relations else 0.35,
            "needs_review": bool(quality_flags),
            "quality_flags": quality_flags,
            "relations": relations,
            "summary": {"relation_count": len(relations), "entity_count": len(entities)},
            "error": "",
        }
