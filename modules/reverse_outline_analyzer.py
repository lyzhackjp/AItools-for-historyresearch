"""
Reverse outline analysis facade.

The analyzer keeps a stable local heuristic fallback while exposing the same
multi-backend capability surface as the unified task layer.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from modules.task_manager import TaskManager


class ReverseOutlineAnalyzer:
    """Analyze draft structure, balance, and logic gaps."""

    SECTION_PATTERNS = {
        "abstract": r"^(abstract|摘要)$",
        "introduction": r"^(introduction|导论|引言|前言|序章)$",
        "literature_review": r"^(literature review|研究回顾|文献综述)$",
        "methodology": r"^(methodology|research method|研究方法|方法)$",
        "analysis": r"^(analysis|正文|分析)$",
        "discussion": r"^(discussion|讨论)$",
        "conclusion": r"^(conclusion|结论|结语)$",
        "references": r"^(references|参考文献)$",
    }

    def __init__(
        self,
        api_provider: str = "qwen",
        test_mode: bool = True,
        backend: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_provider = api_provider
        self.test_mode = test_mode
        self.backend = backend
        self.model = model
        self._task_manager: Optional[TaskManager] = None

    def _get_task_manager(self) -> TaskManager:
        if self._task_manager is None:
            self._task_manager = TaskManager(mode="api", provider=self.api_provider)
        return self._task_manager

    def get_capabilities(self) -> Dict[str, Any]:
        task_options = self._get_task_manager().get_task_options("reverse_outline")
        task_options.update(
            {
                "module": "ReverseOutlineAnalyzer",
                "task": "reverse_outline",
                "output_type": "outline_review",
                "test_mode": self.test_mode,
                "legacy_methods": [
                    "analyze",
                    "extract_outline",
                    "detect_imbalance",
                    "check_logic_gaps",
                    "suggest_revisions",
                ],
                "fallback_order": ["llm_api", "local_llm", "script", "skill", "mcp"],
                "quality_signals": [
                    "draft_too_short",
                    "missing_sections",
                    "section_imbalance",
                    "fallback_backend",
                    "low_confidence",
                ],
            }
        )
        return task_options

    def analyze(
        self,
        paper_text: str,
        use_llm: bool = True,
        language: str = "zh",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Analyze a draft and return the normalized outline-review payload."""

        if not paper_text or len(paper_text.strip()) < 100:
            return {
                "success": False,
                "error": "draft_too_short",
                "section_word_counts": {},
                "section_ratios": {},
                "logical_gaps": ["draft too short for reverse-outline analysis"],
                "deviation_flags": [],
                "suggestions": ["Expand the draft before running reverse-outline review."],
                "confidence": 0.0,
                "needs_review": True,
                "backend": "script",
                "provider": None,
                "model": None,
            }

        backend = kwargs.get("backend", self.backend)
        fallback_backends = kwargs.get("fallback_backends")
        if fallback_backends is None:
            fallback_backends = ["script"]
        if self.test_mode and not backend:
            backend = "script"
            fallback_backends = []
        if not use_llm and not backend:
            backend = "script"

        response = self._get_task_manager().reverse_outline(
            text=paper_text,
            language=language,
            provider=kwargs.get("provider", self.api_provider),
            model=kwargs.get("model", self.model),
            backend=backend,
            fallback_backends=list(fallback_backends),
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 2000),
        )
        if response.get("success"):
            return self._normalize_task_response(response)

        fallback = self._heuristic_outline_review(paper_text)
        fallback.update(
            {
                "success": True,
                "backend": "script",
                "provider": None,
                "model": None,
                "notes": ["task layer failed, used local heuristic fallback"],
            }
        )
        return fallback

    def analyze_package(
        self,
        paper_text: str,
        use_llm: bool = True,
        language: str = "zh",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Analyze a draft and return an `outline_review` package."""

        result = self.analyze(
            paper_text,
            use_llm=use_llm,
            language=language,
            **kwargs,
        )
        flags = self._package_quality_flags(result)
        return {
            "type": "outline_review",
            "schema_version": "2026-04-25",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source": kwargs.get("source", "paper_draft"),
            "language": language,
            "section_word_counts": result.get("section_word_counts", {}),
            "section_ratios": result.get("section_ratios", {}),
            "logical_gaps": result.get("logical_gaps", []),
            "deviation_flags": result.get("deviation_flags", []),
            "suggestions": result.get("suggestions", []),
            "outline": result.get("outline", {}),
            "imbalance_issues": result.get("imbalance_issues", []),
            "backend": result.get("backend") or "script",
            "provider": result.get("provider"),
            "model": result.get("model"),
            "confidence": self._package_confidence(result, flags),
            "needs_review": bool(flags) or bool(result.get("needs_review")),
            "quality_flags": flags,
            "summary": result.get("summary", ""),
            "statistics": {
                "section_count": len(result.get("section_word_counts", {})),
                "logical_gap_count": len(result.get("logical_gaps", [])),
                "deviation_flag_count": len(result.get("deviation_flags", [])),
                "draft_chars": len(paper_text or ""),
            },
            "capabilities": self.get_capabilities(),
            "error": result.get("error"),
        }

    def extract_outline(self, paper_text: str) -> Dict[str, Any]:
        """Backward-compatible helper returning the structured outline summary."""

        return self._heuristic_outline_review(paper_text)["outline"]

    def detect_imbalance(self, outline: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Backward-compatible imbalance report helper."""

        issues: List[Dict[str, Any]] = []
        total_length = outline.get("total_length", 0)
        for section in outline.get("sections", []):
            ratio = section.get("percentage", 0.0)
            if ratio < 5:
                issues.append(
                    {
                        "type": "section_too_short",
                        "severity": "medium",
                        "section": section.get("name", ""),
                        "message": f"{section.get('name', 'section')} is too short",
                    }
                )
            elif ratio > 60:
                issues.append(
                    {
                        "type": "section_too_long",
                        "severity": "medium",
                        "section": section.get("name", ""),
                        "message": f"{section.get('name', 'section')} dominates the draft",
                    }
                )
        if total_length < 1200:
            issues.append(
                {
                    "type": "length_warning",
                    "severity": "high",
                    "message": "draft may be too short for stable argumentative balance",
                }
            )
        return issues

    def check_logic_gaps(self, outline: Dict[str, Any], use_llm: bool = True) -> List[Dict[str, Any]]:
        """Backward-compatible logic-gap helper."""

        del use_llm
        gaps: List[Dict[str, Any]] = []
        section_names = {section.get("name") for section in outline.get("sections", [])}
        for required in ("introduction", "analysis", "conclusion"):
            if required not in section_names:
                gaps.append(
                    {
                        "type": "missing_section",
                        "severity": "high",
                        "message": f"missing {required}",
                    }
                )
        return gaps

    def suggest_revisions(
        self,
        outline: Dict[str, Any],
        imbalance_issues: List[Dict[str, Any]],
        logic_gaps: List[Dict[str, Any]],
        use_llm: bool = True,
    ) -> List[str]:
        """Backward-compatible revision suggestion helper."""

        del outline, use_llm
        suggestions: List[str] = []
        if logic_gaps:
            suggestions.append("Add the missing structural sections before line editing.")
        if imbalance_issues:
            suggestions.append("Rebalance section lengths and compress the most dominant section.")
        if not suggestions:
            suggestions.append("The outline is broadly stable; continue with evidence-level revision.")
        return suggestions

    def _normalize_task_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        payload = response.get("data", {})
        normalized = self._heuristic_outline_review("")
        normalized.update(
            {
                "success": True,
                "section_word_counts": payload.get("section_word_counts", {}),
                "section_ratios": payload.get("section_ratios", {}),
                "logical_gaps": payload.get("logical_gaps", []),
                "deviation_flags": payload.get("deviation_flags", []),
                "suggestions": payload.get("suggestions", []),
                "confidence": payload.get("confidence", 0.65),
                "needs_review": bool(payload.get("needs_review", False)),
                "backend": response.get("backend") or response.get("metadata", {}).get("backend"),
                "provider": response.get("metadata", {}).get("provider"),
                "model": response.get("metadata", {}).get("model"),
            }
        )
        normalized["outline"] = self._build_outline_from_counts(normalized["section_word_counts"], normalized["section_ratios"])
        normalized["imbalance_issues"] = self._build_imbalance_issues(normalized["section_ratios"], normalized["outline"]["total_length"])
        normalized["logic_gaps"] = [
            {"type": "missing_section", "severity": "high", "message": gap}
            for gap in normalized["logical_gaps"]
        ]
        normalized["revision_suggestions"] = list(normalized["suggestions"])
        normalized["summary"] = self._generate_summary(
            normalized["section_word_counts"],
            normalized["logical_gaps"],
            normalized["deviation_flags"],
        )
        return normalized

    def _heuristic_outline_review(self, paper_text: str) -> Dict[str, Any]:
        section_word_counts = self._extract_section_counts(paper_text)
        total_length = sum(section_word_counts.values()) or len(paper_text.replace(" ", ""))
        section_ratios = {
            name: round(count / total_length, 3)
            for name, count in section_word_counts.items()
            if total_length
        }
        logical_gaps = [
            gap["message"]
            for gap in self.check_logic_gaps(
                self._build_outline_from_counts(section_word_counts, section_ratios),
                use_llm=False,
            )
        ]
        deviation_flags = [
            issue["message"]
            for issue in self._build_imbalance_issues(section_ratios, total_length)
        ]
        suggestions = self.suggest_revisions({}, self._build_imbalance_issues(section_ratios, total_length), [], use_llm=False)
        outline = self._build_outline_from_counts(section_word_counts, section_ratios)
        imbalance_issues = self._build_imbalance_issues(section_ratios, total_length)
        return {
            "success": True,
            "outline": outline,
            "imbalance_issues": imbalance_issues,
            "logic_gaps": [
                {"type": "missing_section", "severity": "high", "message": gap}
                for gap in logical_gaps
            ],
            "revision_suggestions": suggestions,
            "summary": self._generate_summary(section_word_counts, logical_gaps, deviation_flags),
            "section_word_counts": section_word_counts,
            "section_ratios": section_ratios,
            "logical_gaps": logical_gaps,
            "deviation_flags": deviation_flags,
            "suggestions": suggestions,
            "confidence": self._estimate_confidence(section_word_counts, logical_gaps, deviation_flags),
            "needs_review": bool(logical_gaps or deviation_flags),
        }

    def _extract_section_counts(self, paper_text: str) -> Dict[str, int]:
        if not paper_text:
            return {}
        lines = paper_text.splitlines()
        sections: List[tuple[str, int]] = []
        for index, raw_line in enumerate(lines):
            line = raw_line.strip().strip("#").strip()
            if not line or len(line) > 80:
                continue
            normalized = re.sub(r"^[0-9一二三四五六七八九十IVXivx.、\-\s]+", "", line).lower()
            for section_name, pattern in self.SECTION_PATTERNS.items():
                if re.match(pattern, normalized, re.IGNORECASE):
                    sections.append((section_name, index))
                    break

        counts: Dict[str, int] = {}
        if sections:
            for offset, (section_name, start_index) in enumerate(sections):
                end_index = sections[offset + 1][1] if offset + 1 < len(sections) else len(lines)
                body = "\n".join(lines[start_index + 1 : end_index]).strip()
                counts[section_name] = len(body.replace(" ", ""))
            return counts

        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", paper_text) if part.strip()]
        if not paragraphs:
            return {}
        total = len(paragraphs)
        counts["introduction"] = len("\n\n".join(paragraphs[: max(1, total // 4)]).replace(" ", ""))
        counts["analysis"] = len("\n\n".join(paragraphs[max(1, total // 4) : max(2, total - 1)]).replace(" ", ""))
        counts["conclusion"] = len("\n\n".join(paragraphs[max(1, total - 1) :]).replace(" ", ""))
        return counts

    def _build_outline_from_counts(
        self,
        section_word_counts: Dict[str, int],
        section_ratios: Dict[str, float],
    ) -> Dict[str, Any]:
        sections = []
        total_length = sum(section_word_counts.values())
        for name, count in section_word_counts.items():
            sections.append(
                {
                    "name": name,
                    "length": count,
                    "percentage": round(section_ratios.get(name, 0.0) * 100, 2),
                    "word_count": count,
                    "paragraphs": [],
                }
            )
        return {"total_length": total_length, "sections": sections, "unstructured_content": []}

    def _build_imbalance_issues(self, section_ratios: Dict[str, float], total_length: int) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        if total_length < 1200:
            issues.append(
                {
                    "type": "length_warning",
                    "severity": "high",
                    "message": "draft may be too short for stable reverse-outline review",
                    "suggestion": "expand the draft before relying on section-balance analysis",
                }
            )
        for section, ratio in section_ratios.items():
            if section == "references":
                continue
            if ratio < 0.05:
                issues.append(
                    {
                        "type": "section_too_short",
                        "severity": "medium",
                        "section": section,
                        "message": f"{section} is too short ({ratio:.1%})",
                        "suggestion": f"expand {section} or merge it into a neighboring section",
                    }
                )
            elif ratio > 0.6:
                issues.append(
                    {
                        "type": "section_too_long",
                        "severity": "medium",
                        "section": section,
                        "message": f"{section} is too long ({ratio:.1%})",
                        "suggestion": f"split or compress {section}",
                    }
                )
        return issues

    def _estimate_confidence(
        self,
        section_word_counts: Dict[str, int],
        logical_gaps: List[str],
        deviation_flags: List[str],
    ) -> float:
        confidence = 0.5
        if section_word_counts:
            confidence += 0.15
        if "introduction" in section_word_counts and "conclusion" in section_word_counts:
            confidence += 0.1
        if not logical_gaps:
            confidence += 0.1
        if not deviation_flags:
            confidence += 0.05
        return round(min(confidence, 0.9), 2)

    def _generate_summary(
        self,
        section_word_counts: Dict[str, int],
        logical_gaps: List[str],
        deviation_flags: List[str],
    ) -> str:
        parts = [f"{len(section_word_counts)} sections detected"]
        if logical_gaps:
            parts.append(f"{len(logical_gaps)} structural gaps")
        if deviation_flags:
            parts.append(f"{len(deviation_flags)} balance flags")
        if len(parts) == 1:
            parts.append("outline looks broadly stable")
        return "; ".join(parts)

    def _package_quality_flags(self, result: Dict[str, Any]) -> List[str]:
        flags = []
        if result.get("error") == "draft_too_short":
            flags.append("draft_too_short")
        if result.get("logical_gaps"):
            flags.append("missing_sections")
        if result.get("deviation_flags"):
            flags.append("section_imbalance")
        if result.get("backend") in {"script", "fallback"} and not self.test_mode:
            flags.append("fallback_backend")
        confidence = result.get("confidence")
        if isinstance(confidence, (int, float)) and confidence < 0.6:
            flags.append("low_confidence")
        if result.get("needs_review"):
            flags.append("review_requested")
        return sorted(set(flags))

    def _package_confidence(self, result: Dict[str, Any], flags: List[str]) -> float:
        confidence = result.get("confidence")
        if not isinstance(confidence, (int, float)):
            confidence = 0.6
        if "draft_too_short" in flags:
            confidence = min(confidence, 0.2)
        if "fallback_backend" in flags:
            confidence -= 0.1
        if "missing_sections" in flags:
            confidence -= 0.05
        if "section_imbalance" in flags:
            confidence -= 0.05
        return round(max(0.0, min(1.0, float(confidence))), 3)
