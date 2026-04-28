"""
Stage 6: polish the draft.

This stage now consumes paper polishing, reverse-outline review, and optional
style transfer through unified protocol surfaces and writes the results back
into project metadata.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

_AI_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..")
if _AI_TOOLS not in sys.path:
    sys.path.insert(0, _AI_TOOLS)

from modules.task_manager import TaskManager
from tools.workflow.research_project import OutlineReview, ResearchProject


class Stage6Polish:
    """Polish the draft, optionally transfer style, then re-run outline review."""

    NAME = "polish"
    STAGE_NUM = 6

    def __init__(self, project: ResearchProject):
        self.project = project
        self.task_manager: Optional[TaskManager] = None
        self.polisher = None
        self.style_transfer = None
        self.outline_analyzer = None
        self._warnings: List[str] = []
        self._review_items: List[Dict[str, Any]] = []
        self._registered_packages: List[Dict[str, Any]] = []
        self._last_polish_result: Optional[Dict[str, Any]] = None
        self._last_outline_result: Optional[Dict[str, Any]] = None

    def _get_task_manager(self) -> TaskManager:
        if self.task_manager is None:
            self.task_manager = TaskManager(mode="api", provider="qwen")
        return self.task_manager

    def _get_polisher(self):
        if self.polisher is None:
            from modules.paper_polisher import PaperPolisher

            self.polisher = PaperPolisher(api_provider="qwen", test_mode=False)
        return self.polisher

    def _get_outline_analyzer(self):
        if self.outline_analyzer is None:
            from modules.reverse_outline_analyzer import ReverseOutlineAnalyzer

            self.outline_analyzer = ReverseOutlineAnalyzer(api_provider="qwen", test_mode=False)
        return self.outline_analyzer

    def _get_style_transfer(self):
        if self.style_transfer is None:
            from modules.style_transfer import StyleTransfer

            self.style_transfer = StyleTransfer(api_provider="qwen", test_mode=False)
        return self.style_transfer

    def run(self, **kwargs) -> Dict[str, Any]:
        if not self.project.paper_draft:
            print("[Stage 6] No draft available, skipping")
            self.project.mark_stage_skipped(self.STAGE_NUM)
            return {}

        self._warnings = []
        self._review_items = []
        self._registered_packages = []
        print(f"[Stage 6] Start polishing | original draft: {len(self.project.paper_draft)} chars")
        self.project.mark_stage_start(self.STAGE_NUM)
        self.project.set_stage_metadata(
            self.STAGE_NUM,
            capability_snapshot={
                "paper_polish": self._get_task_manager().get_task_options("paper_polish"),
                "reverse_outline": self._get_task_manager().get_task_options("reverse_outline"),
                "style_transfer": self._get_task_manager().get_task_options("style_transfer"),
            },
            requested_execution=self._build_requested_execution(kwargs),
        )

        results: Dict[str, Any] = {}
        polished_result = self._run_polish(self.project.paper_draft, **kwargs)
        polished_text = polished_result.get("polished_text") or self.project.paper_draft
        self.project.polished_draft = polished_text
        self._last_polish_result = polished_result
        results["polished_draft"] = polished_text

        if polished_result.get("needs_review"):
            self.project.add_quality_flag("stage6_polish_review_needed")
            self._review_items.append(
                {
                    "stage": self.STAGE_NUM,
                    "type": "paper_polish",
                    "message": "Paper polish used a fallback or returned a low-confidence result.",
                    "backend": polished_result.get("backend"),
                    "provider": polished_result.get("provider"),
                    "model": polished_result.get("model"),
                }
            )

        style_result = None
        target_style = kwargs.get("target_style", "")
        if target_style:
            style_kwargs = dict(kwargs)
            style_kwargs.pop("target_style", None)
            style_result = self._run_style_transfer(polished_text, target_style=target_style, **style_kwargs)
            styled_text = style_result.get("rewritten_text") or polished_text
            self.project.style_transferred_draft = styled_text
            results["style_transferred_draft"] = styled_text
            if style_result.get("needs_review"):
                self.project.add_quality_flag("stage6_style_transfer_review_needed")
                self._review_items.append(
                    {
                        "stage": self.STAGE_NUM,
                        "type": "style_transfer",
                        "message": "Style transfer returned a low-confidence or fallback result.",
                        "backend": style_result.get("backend"),
                        "provider": style_result.get("provider"),
                        "model": style_result.get("model"),
                    }
                )
        else:
            self.project.style_transferred_draft = ""
            results["style_transferred_draft"] = None

        review_input = self.project.style_transferred_draft or polished_text
        outline_result = self._run_outline_review(review_input, **kwargs)
        self._last_outline_result = outline_result
        review_obj = outline_result.get("review")
        if review_obj is not None:
            self.project.outline_review = review_obj
            results["outline_review"] = review_obj
            self._register_outline_review_items(review_obj, outline_result)
        else:
            results["outline_review"] = None

        self._flush_review_items()
        self.project.set_stage_metadata(
            self.STAGE_NUM,
            execution_summary={
                "paper_polish": {
                    "backend": polished_result.get("backend"),
                    "provider": polished_result.get("provider"),
                    "model": polished_result.get("model"),
                    "confidence": polished_result.get("confidence"),
                    "needs_review": polished_result.get("needs_review"),
                    "quality_flags": polished_result.get("quality_flags", []),
                    "package_type": polished_result.get("package", {}).get("type"),
                    "original_chars": len(self.project.paper_draft),
                    "polished_chars": len(polished_text),
                    "revision_note_count": len(polished_result.get("revision_notes", [])),
                },
                "style_transfer": {
                    "requested": bool(target_style),
                    "backend": style_result.get("backend") if style_result else None,
                    "provider": style_result.get("provider") if style_result else None,
                    "model": style_result.get("model") if style_result else None,
                    "confidence": style_result.get("confidence") if style_result else None,
                    "needs_review": style_result.get("needs_review") if style_result else None,
                    "quality_flags": style_result.get("quality_flags", []) if style_result else [],
                    "package_type": style_result.get("package", {}).get("type") if style_result else None,
                    "target_style": target_style or None,
                    "output_chars": len(self.project.style_transferred_draft) if self.project.style_transferred_draft else 0,
                },
                "reverse_outline": {
                    "backend": outline_result.get("backend"),
                    "provider": outline_result.get("provider"),
                    "model": outline_result.get("model"),
                    "confidence": outline_result.get("confidence"),
                    "needs_review": outline_result.get("needs_review"),
                    "quality_flags": outline_result.get("quality_flags", []),
                    "package_type": outline_result.get("package", {}).get("type"),
                    "logical_gaps": len(review_obj.logical_gaps) if review_obj else 0,
                    "deviation_flags": len(review_obj.deviation_flags) if review_obj else 0,
                },
                "warning_count": len(self._warnings),
                "review_count": len(self._review_items),
            },
            package_protocol={
                "registry": "ResearchProject.register_package",
                "registered_package_count": len(self._registered_packages),
                "registered_packages": self._registered_packages,
            },
            warnings=self._warnings,
        )

        self.project.mark_stage_done(self.STAGE_NUM)
        print("[Stage 6] Done")
        return results

    def polish_paper(self, paper_text: str, **kwargs: Any) -> str:
        result = self._run_polish(paper_text, **kwargs)
        self._last_polish_result = result
        return result.get("polished_text") or paper_text

    def transfer_style(self, paper_text: str, target_style: str = "", **kwargs: Any) -> str:
        if not target_style:
            return paper_text
        result = self._run_style_transfer(paper_text, target_style=target_style, **kwargs)
        return result.get("rewritten_text") or paper_text

    def _recheck_outline(self, paper_text: str, **kwargs: Any) -> Optional[OutlineReview]:
        result = self._run_outline_review(paper_text, **kwargs)
        self._last_outline_result = result
        return result.get("review")

    def _run_polish(self, paper_text: str, **kwargs: Any) -> Dict[str, Any]:
        polisher = self._get_polisher()
        polish_kwargs = {
            "backend": self._resolve_backend(kwargs, "paper_polish"),
            "fallback_backends": self._resolve_fallbacks(kwargs, "paper_polish"),
            "provider": kwargs.get("provider", "qwen"),
            "model": kwargs.get("model"),
        }
        if hasattr(polisher, "polish_text_package"):
            package = polisher.polish_text_package(
                paper_text,
                language=self.project.language,
                **polish_kwargs,
            )
            self._register_stage_package(package, source="paper_polisher")
            result = {
                "polished_text": package.get("polished_text"),
                "revision_notes": package.get("revision_notes", []),
                "backend": package.get("backend"),
                "provider": package.get("provider"),
                "model": package.get("model"),
                "confidence": package.get("confidence"),
                "needs_review": package.get("needs_review"),
                "quality_flags": package.get("quality_flags", []),
                "package": package,
            }
        else:
            result = polisher.polish_text(
                paper_text,
                language=self.project.language,
                **polish_kwargs,
            )
        if len(result.get("polished_text", "")) < max(100, len(paper_text) * 0.2):
            self._warnings.append("paper_polish_output_suspiciously_short")
            result["polished_text"] = paper_text
            result["needs_review"] = True
            result.setdefault("quality_flags", []).append("suspicious_length_change")
        return result

    def _run_style_transfer(self, paper_text: str, target_style: str, **kwargs: Any) -> Dict[str, Any]:
        transfer = self._get_style_transfer()
        transfer_kwargs = {
            "target_style": target_style,
            "provider": kwargs.get("style_provider") or kwargs.get("provider") or "qwen",
            "model": kwargs.get("style_model") or kwargs.get("model"),
            "backend": self._resolve_backend(kwargs, "style_transfer"),
            "fallback_backends": self._resolve_fallbacks(kwargs, "style_transfer"),
            "temperature": kwargs.get("style_temperature", 0.2),
            "max_tokens": kwargs.get("style_max_tokens", 4000),
        }
        if hasattr(transfer, "transfer_style_package"):
            package = transfer.transfer_style_package(paper_text, **transfer_kwargs)
            self._register_stage_package(package, source="style_transfer")
            result = {
                "rewritten_text": package.get("rewritten_text"),
                "style_analysis": package.get("style_analysis", {}),
                "target_style": package.get("target_style"),
                "backend": package.get("backend"),
                "provider": package.get("provider"),
                "model": package.get("model"),
                "confidence": package.get("confidence"),
                "needs_review": package.get("needs_review"),
                "quality_flags": package.get("quality_flags", []),
                "package": package,
            }
        else:
            result = transfer.transfer_style_result(paper_text, **transfer_kwargs)
        if result.get("needs_review"):
            self._warnings.append("style_transfer_review_needed")
        return result

    def _run_outline_review(self, paper_text: str, **kwargs: Any) -> Dict[str, Any]:
        analyzer = self._get_outline_analyzer()
        outline_kwargs = {
            "use_llm": not bool(kwargs.get("test_mode")),
            "language": self.project.language,
            "backend": self._resolve_backend(kwargs, "reverse_outline"),
            "fallback_backends": self._resolve_fallbacks(kwargs, "reverse_outline"),
            "provider": kwargs.get("outline_provider") or kwargs.get("provider") or "qwen",
            "model": kwargs.get("outline_model") or kwargs.get("model"),
        }
        if hasattr(analyzer, "analyze_package"):
            package = analyzer.analyze_package(paper_text, **outline_kwargs)
            self._register_stage_package(package, source="reverse_outline_analyzer")
            result = {
                "section_word_counts": package.get("section_word_counts", {}),
                "section_ratios": package.get("section_ratios", {}),
                "logical_gaps": package.get("logical_gaps", []),
                "deviation_flags": package.get("deviation_flags", []),
                "suggestions": package.get("suggestions", []),
                "backend": package.get("backend"),
                "provider": package.get("provider"),
                "model": package.get("model"),
                "confidence": package.get("confidence"),
                "needs_review": package.get("needs_review"),
                "quality_flags": package.get("quality_flags", []),
                "package": package,
            }
        else:
            result = analyzer.analyze(paper_text, **outline_kwargs)
        review = OutlineReview(
            section_word_counts=result.get("section_word_counts", {}),
            section_ratios=result.get("section_ratios", {}),
            logical_gaps=list(result.get("logical_gaps", [])),
            deviation_flags=list(result.get("deviation_flags", [])),
            suggestions=list(result.get("suggestions", [])),
        )
        return {
            "review": review,
            "backend": result.get("backend"),
            "provider": result.get("provider"),
            "model": result.get("model"),
            "confidence": result.get("confidence"),
            "needs_review": result.get("needs_review"),
            "quality_flags": result.get("quality_flags", []),
            "package": result.get("package"),
        }

    def _build_requested_execution(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "paper_polish_backend": self._resolve_backend(kwargs, "paper_polish"),
            "style_transfer_backend": self._resolve_backend(kwargs, "style_transfer"),
            "reverse_outline_backend": self._resolve_backend(kwargs, "reverse_outline"),
            "target_style": kwargs.get("target_style") or None,
            "test_mode": bool(kwargs.get("test_mode", False)),
        }

    def _resolve_backend(self, kwargs: Dict[str, Any], task_name: str) -> Optional[str]:
        if kwargs.get("test_mode"):
            return "script"
        task_specific = kwargs.get(f"{task_name}_backend")
        if task_specific:
            return task_specific
        return kwargs.get("backend")

    def _resolve_fallbacks(self, kwargs: Dict[str, Any], task_name: str) -> List[str]:
        if kwargs.get("test_mode"):
            return []
        task_specific = kwargs.get(f"{task_name}_fallback_backends")
        if task_specific is not None:
            return list(task_specific)
        generic = kwargs.get("fallback_backends")
        if generic is not None:
            return list(generic)
        return ["local_llm", "script"] if task_name != "reverse_outline" else ["script"]

    def _register_stage_package(self, package: Optional[Dict[str, Any]], *, source: str) -> None:
        if not isinstance(package, dict):
            return
        summary = self.project.register_package(package, stage=self.STAGE_NUM, source=source)
        self._registered_packages.append(summary)

    def _register_outline_review_items(self, review: OutlineReview, outline_result: Dict[str, Any]) -> None:
        if review.logical_gaps:
            self.project.add_quality_flag("stage6_outline_review_needed")
        if outline_result.get("needs_review"):
            self.project.add_quality_flag("stage6_polish_review_needed")
        for item in review.logical_gaps:
            self._review_items.append(
                {
                    "stage": self.STAGE_NUM,
                    "type": "outline_gap",
                    "message": item,
                    "backend": outline_result.get("backend"),
                }
            )
        for item in review.deviation_flags:
            self._review_items.append(
                {
                    "stage": self.STAGE_NUM,
                    "type": "outline_deviation",
                    "message": item,
                    "backend": outline_result.get("backend"),
                }
            )

    def _flush_review_items(self) -> None:
        for item in self._review_items:
            self.project.add_review_item(item)
