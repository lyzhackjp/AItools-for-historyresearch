"""
Style analysis and conservative style transfer facade.

This module keeps the older public API while routing rewrite work through the
unified task layer and using local heuristics for style-matrix analysis.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from modules.task_manager import TaskManager


class StyleTransfer:
    """Analyze writing style and rewrite text toward a target style."""

    STYLE_MATRIX_DIMENSIONS = [
        "sentence_structure",
        "vocabulary_choices",
        "tone_narrative",
        "rhetorical_patterns",
    ]

    DEFAULT_SYSTEM_PROMPT = (
        "Analyze academic style and rewrite text conservatively while preserving "
        "claims, evidence, and citations."
    )

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
        self.llm_client = None
        self.analyzed_styles: Dict[str, Dict[str, Any]] = {}
        self._task_manager: Optional[TaskManager] = None

    def _get_task_manager(self) -> TaskManager:
        if self._task_manager is None:
            self._task_manager = TaskManager(mode="api", provider=self.api_provider)
        return self._task_manager

    def _init_llm_client(self) -> TaskManager:
        """Compatibility shim for older callers."""

        self.llm_client = self._get_task_manager()
        return self.llm_client

    def get_capabilities(self) -> Dict[str, Any]:
        task_options = self._get_task_manager().get_task_options("style_transfer")
        task_options.update(
            {
                "module": "StyleTransfer",
                "task": "style_transfer",
                "output_type": "style_transfer",
                "test_mode": self.test_mode,
                "legacy_methods": [
                    "analyze_style_matrix",
                    "transfer_style",
                    "transfer_style_result",
                    "few_shot_style_imitation",
                ],
                "fallback_order": ["llm_api", "local_llm", "script", "skill", "mcp"],
                "quality_signals": [
                    "empty_input",
                    "empty_output",
                    "fallback_backend",
                    "low_confidence",
                    "suspicious_length_change",
                    "aggressive_rewrite_risk",
                ],
            }
        )
        return task_options

    def analyze_style_matrix(self, text: str, author_name: Optional[str] = None) -> Dict[str, Any]:
        """Produce a stable local style matrix."""

        sentence_structure = self.extract_sentence_patterns(text)
        vocabulary_profile = self.extract_vocabulary_profile(text)
        tone_narrative = self.analyze_tone_narrative(text)
        rhetorical_patterns = self.analyze_rhetorical_patterns(text)

        analysis = {
            "sentence_structure": sentence_structure,
            "vocabulary_choices": vocabulary_profile,
            "tone_narrative": tone_narrative,
            "rhetorical_patterns": rhetorical_patterns,
            "overall_style_summary": self._build_style_summary(
                author_name,
                sentence_structure,
                vocabulary_profile,
                tone_narrative,
                rhetorical_patterns,
            ),
        }
        if author_name:
            self.analyzed_styles[author_name] = analysis
        return analysis

    def extract_sentence_patterns(self, text: str) -> Dict[str, Any]:
        sentences = self._split_sentences(text)
        lengths = [len(sentence) for sentence in sentences]
        average_length = round(sum(lengths) / len(lengths), 2) if lengths else 0.0
        long_ratio = round(sum(1 for length in lengths if length >= 60) / len(lengths), 3) if lengths else 0.0
        short_ratio = round(sum(1 for length in lengths if length <= 20) / len(lengths), 3) if lengths else 0.0
        connectors = re.findall(r"(therefore|however|moreover|thus|hence|因此|然而|同时|此外)", text, re.IGNORECASE)
        return {
            "average_length": average_length,
            "long_sentences_ratio": long_ratio,
            "short_sentences_ratio": short_ratio,
            "connector_density": round(len(connectors) / max(len(sentences), 1), 2),
            "sample_sentences": sentences[:3],
        }

    def extract_vocabulary_profile(self, text: str) -> Dict[str, Any]:
        tokens = self._tokenize(text)
        frequencies: Dict[str, int] = {}
        for token in tokens:
            if len(token) < 2:
                continue
            frequencies[token] = frequencies.get(token, 0) + 1
        top_terms = sorted(frequencies.items(), key=lambda item: item[1], reverse=True)[:10]
        academic_terms = self._identify_academic_terms(text)
        return {
            "top_frequency_words": top_terms,
            "academic_terms": academic_terms[:10],
            "estimated_register": "formal" if len(academic_terms) >= 3 else "semi-formal",
            "token_count": len(tokens),
        }

    def analyze_tone_narrative(self, text: str) -> Dict[str, Any]:
        subjective_markers = ["I argue", "I suggest", "我认为", "笔者认为", "in my view"]
        objective_markers = ["research shows", "evidence indicates", "研究表明", "资料显示", "the evidence suggests"]
        critical_markers = ["however", "problematic", "insufficient", "然而", "不足", "值得商榷"]

        subjective_count = sum(text.count(marker) for marker in subjective_markers)
        objective_count = sum(text.count(marker) for marker in objective_markers)
        critical_count = sum(text.count(marker) for marker in critical_markers)

        if objective_count > subjective_count:
            perspective = "objective"
        elif subjective_count > objective_count:
            perspective = "subjective"
        else:
            perspective = "mixed"

        return {
            "narrative_perspective": perspective,
            "critical_stance": "critical" if critical_count > 1 else "measured",
            "emotional_color": "restrained",
            "subjective_markers_count": subjective_count,
            "objective_markers_count": objective_count,
        }

    def analyze_rhetorical_patterns(self, text: str) -> Dict[str, Any]:
        comparison_markers = re.findall(r"(compared with|in contrast|whereas|相比之下|相反|与此同时)", text, re.IGNORECASE)
        causal_markers = re.findall(r"(because|therefore|thus|hence|因为|因此|由此可见)", text, re.IGNORECASE)
        listing_markers = re.findall(r"(first,|second,|finally,|首先|其次|最后)", text, re.IGNORECASE)
        preference = "logical-argumentation"
        if comparison_markers:
            preference = "comparison-heavy"
        elif listing_markers:
            preference = "enumerative"
        return {
            "rhetorical_preference": preference,
            "logical_connectors": {
                "comparison": len(comparison_markers),
                "causal": len(causal_markers),
                "listing": len(listing_markers),
            },
            "argumentation_mode": "deductive" if len(causal_markers) >= len(comparison_markers) else "comparative",
        }

    def transfer_style(
        self,
        text: str,
        style_matrix: Optional[Dict[str, Any]] = None,
        *,
        target_style: Optional[str] = None,
        style_reference: str = "",
        **kwargs: Any,
    ) -> str:
        """Return rewritten text for backward compatibility."""

        result = self.transfer_style_result(
            text,
            style_matrix=style_matrix,
            target_style=target_style,
            style_reference=style_reference,
            **kwargs,
        )
        return result.get("rewritten_text") or text

    def transfer_style_result(
        self,
        text: str,
        style_matrix: Optional[Dict[str, Any]] = None,
        *,
        target_style: Optional[str] = None,
        style_reference: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute style transfer and return unified metadata."""

        resolved_target_style = target_style or self._resolve_target_style(style_matrix, style_reference)
        backend = kwargs.get("backend", self.backend)
        fallback_backends = kwargs.get("fallback_backends")
        if fallback_backends is None:
            fallback_backends = ["local_llm", "script"]
        if self.test_mode and not backend:
            backend = "script"
            fallback_backends = []

        response = self._get_task_manager().style_transfer(
            text=text,
            target_style=resolved_target_style,
            provider=kwargs.get("provider", self.api_provider),
            model=kwargs.get("model", self.model),
            backend=backend,
            fallback_backends=list(fallback_backends),
            temperature=kwargs.get("temperature", 0.2),
            max_tokens=kwargs.get("max_tokens", 4000),
        )
        payload = response.get("data", {}) if response.get("success") else {}
        rewritten_text = payload.get("rewritten_text") or text
        return {
            "rewritten_text": rewritten_text,
            "style_analysis": payload.get("style_analysis") or style_matrix or {},
            "target_style": resolved_target_style,
            "backend": response.get("backend") or response.get("metadata", {}).get("backend"),
            "provider": response.get("metadata", {}).get("provider", self.api_provider),
            "model": response.get("metadata", {}).get("model", self.model),
            "confidence": payload.get("confidence", 0.7 if rewritten_text != text else 0.55),
            "needs_review": bool(payload.get("needs_review", False)),
        }

    def transfer_style_package(
        self,
        text: str,
        style_matrix: Optional[Dict[str, Any]] = None,
        *,
        target_style: Optional[str] = None,
        style_reference: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Transfer style and return a `style_transfer` envelope."""

        result = self.transfer_style_result(
            text,
            style_matrix=style_matrix,
            target_style=target_style,
            style_reference=style_reference,
            **kwargs,
        )
        flags = self._package_quality_flags(text, result)
        return {
            "type": "style_transfer",
            "schema_version": "2026-04-25",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source": kwargs.get("source", "polished_draft"),
            "original_text": text,
            "rewritten_text": result.get("rewritten_text", text),
            "style_analysis": result.get("style_analysis", {}),
            "target_style": result.get("target_style") or target_style or "academic history prose",
            "backend": result.get("backend") or ("script" if self.test_mode else self.backend),
            "provider": result.get("provider", self.api_provider),
            "model": result.get("model", self.model),
            "confidence": self._package_confidence(result, flags),
            "needs_review": bool(flags) or bool(result.get("needs_review")),
            "quality_flags": flags,
            "statistics": {
                "original_chars": len(text or ""),
                "rewritten_chars": len(result.get("rewritten_text", "") or ""),
                "style_dimension_count": len(result.get("style_analysis", {}) or {}),
            },
            "capabilities": self.get_capabilities(),
        }

    def few_shot_style_imitation(
        self,
        text: str,
        reference_examples: List[Tuple[str, str]],
        author_name: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Learn a target style from a few examples and rewrite the text."""

        reference_targets = [target for _, target in reference_examples if target.strip()]
        if reference_targets:
            style_reference = "\n\n".join(reference_targets[:3])
        else:
            style_reference = author_name or "academic history prose"
        return self.transfer_style(
            text,
            target_style=author_name or "few-shot style imitation",
            style_reference=style_reference,
            **kwargs,
        )

    def batch_style_analysis(self, documents: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        results = []
        for document in documents:
            text = document.get("text", "")
            author = document.get("author")
            results.append(
                {
                    "author": author,
                    "analysis": self.analyze_style_matrix(text, author),
                    "text_length": len(text),
                }
            )
        return results

    def compare_styles(
        self,
        style1: Dict[str, Any],
        style2: Dict[str, Any],
        style1_name: str = "Style 1",
        style2_name: str = "Style 2",
    ) -> Dict[str, Any]:
        similarities: List[str] = []
        differences: List[str] = []

        register1 = style1.get("vocabulary_choices", {}).get("estimated_register")
        register2 = style2.get("vocabulary_choices", {}).get("estimated_register")
        if register1 == register2:
            similarities.append(f"Both styles use a {register1} register.")
        else:
            differences.append(f"Register differs: {style1_name}={register1}, {style2_name}={register2}.")

        perspective1 = style1.get("tone_narrative", {}).get("narrative_perspective")
        perspective2 = style2.get("tone_narrative", {}).get("narrative_perspective")
        if perspective1 == perspective2:
            similarities.append(f"Both styles share a {perspective1} narrative perspective.")
        else:
            differences.append(
                f"Narrative perspective differs: {style1_name}={perspective1}, {style2_name}={perspective2}."
            )

        rhetoric1 = style1.get("rhetorical_patterns", {}).get("rhetorical_preference")
        rhetoric2 = style2.get("rhetorical_patterns", {}).get("rhetorical_preference")
        if rhetoric1 == rhetoric2:
            similarities.append(f"Both styles prefer {rhetoric1}.")
        else:
            differences.append(f"Rhetorical preference differs: {style1_name}={rhetoric1}, {style2_name}={rhetoric2}.")

        return {
            "styles": {
                style1_name: style1,
                style2_name: style2,
            },
            "similarities": similarities,
            "differences": differences,
        }

    def _resolve_target_style(
        self,
        style_matrix: Optional[Dict[str, Any]],
        style_reference: str,
    ) -> str:
        if style_reference.strip():
            return style_reference.strip()[:500]
        if style_matrix and style_matrix.get("overall_style_summary"):
            return str(style_matrix["overall_style_summary"])
        return "academic history prose"

    def _split_sentences(self, text: str) -> List[str]:
        return [part.strip() for part in re.split(r"[。！？!?]\s*|\n+", text) if part.strip()]

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[A-Za-z][A-Za-z\-']+|[\u4e00-\u9fff]{2,}", text)

    def _identify_academic_terms(self, text: str) -> List[str]:
        candidates = [
            "historiography",
            "methodology",
            "archive",
            "evidence",
            "discourse",
            "史料",
            "论证",
            "方法论",
            "研究史",
            "档案",
            "史学",
        ]
        return [term for term in candidates if term.lower() in text.lower()]

    def _build_style_summary(
        self,
        author_name: Optional[str],
        sentence_structure: Dict[str, Any],
        vocabulary_profile: Dict[str, Any],
        tone_narrative: Dict[str, Any],
        rhetorical_patterns: Dict[str, Any],
    ) -> str:
        author_label = author_name or "The style"
        return (
            f"{author_label} favors {vocabulary_profile.get('estimated_register', 'formal')} diction, "
            f"an {tone_narrative.get('narrative_perspective', 'mixed')} narrative perspective, "
            f"average sentence length around {sentence_structure.get('average_length', 0)}, and "
            f"{rhetorical_patterns.get('rhetorical_preference', 'logical-argumentation')} argumentation."
        )

    def _package_quality_flags(self, original_text: str, result: Dict[str, Any]) -> List[str]:
        flags = []
        original = original_text or ""
        rewritten = result.get("rewritten_text", "") or ""
        if not original.strip():
            flags.append("empty_input")
        if original.strip() and not rewritten.strip():
            flags.append("empty_output")
        if result.get("backend") in {"script", "fallback"} and not self.test_mode:
            flags.append("fallback_backend")
        if result.get("needs_review"):
            flags.append("backend_review_requested")
        confidence = result.get("confidence")
        if isinstance(confidence, (int, float)) and confidence < 0.6:
            flags.append("low_confidence")
        if original.strip() and rewritten.strip():
            ratio = len(rewritten) / max(len(original), 1)
            if ratio < 0.4 or ratio > 1.8:
                flags.append("suspicious_length_change")
            if ratio > 1.4 and result.get("backend") not in {"script", None}:
                flags.append("aggressive_rewrite_risk")
        return sorted(set(flags))

    def _package_confidence(self, result: Dict[str, Any], flags: List[str]) -> float:
        confidence = result.get("confidence")
        if not isinstance(confidence, (int, float)):
            confidence = 0.65
        if "fallback_backend" in flags:
            confidence -= 0.1
        if "empty_output" in flags:
            confidence -= 0.35
        if "suspicious_length_change" in flags:
            confidence -= 0.15
        if "aggressive_rewrite_risk" in flags:
            confidence -= 0.1
        if "low_confidence" in flags:
            confidence = min(confidence, 0.55)
        return round(max(0.0, min(1.0, float(confidence))), 3)


def create_style_transfer(api_provider: str = "qwen", test_mode: bool = True, **kwargs: Any) -> StyleTransfer:
    """Compatibility factory."""

    return StyleTransfer(api_provider=api_provider, test_mode=test_mode, **kwargs)
