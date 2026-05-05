from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from modules.module_adapters import (
    AcademicNoteAdapter,
    CitationAdapter,
    EntityDisambiguationAdapter,
    HistoricalCitationAdapter,
    NERAdapter,
    OCRAdapter,
    PaperPolishAdapter,
    ReverseOutlineAdapter,
    StyleTransferAdapter,
    SummaryAdapter,
    VirtualPersonaAdapter,
)
from modules.secure_api_key_manager import get_secure_key_manager
from modules.unified_task_executor import TaskConfig, TaskResult, TaskType, UnifiedTaskExecutor

try:
    from config.local_llm_config import get_local_model, get_model_role_for_task
except Exception:  # pragma: no cover - fallback for partial installs
    def get_local_model(role: str = "chat_primary") -> str:
        return os.getenv("OLLAMA_MODEL", "llama3.1")

    def get_model_role_for_task(task_type: str) -> str:
        return "chat_primary"


@dataclass
class TaskPreset:
    name: str
    task_type: str
    provider: str = "qwen"
    model: Optional[str] = None
    backend: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 2000
    custom_prompt: Optional[str] = None
    description: str = ""


@dataclass(frozen=True)
class TaskRegistryEntry:
    name: str
    adapter: str
    description: str
    input_contract: List[str]
    output_contract: List[str]


class TaskManager:
    DEFAULT_PRESETS: Dict[str, TaskPreset] = {
        "ner_quick": TaskPreset(
            name="ner_quick",
            task_type="ner",
            provider="qwen",
            backend="script",
            temperature=0.1,
            max_tokens=1000,
            description="Fast local NER pass.",
        ),
        "ner_detailed": TaskPreset(
            name="ner_detailed",
            task_type="ner",
            provider="qwen",
            backend="llm_api",
            temperature=0.1,
            max_tokens=2000,
            description="Detailed remote LLM NER pass.",
        ),
        "ner_local_academic": TaskPreset(
            name="ner_local_academic",
            task_type="ner",
            provider="ollama",
            model=get_local_model(get_model_role_for_task("ner")),
            backend="local_llm",
            temperature=0.1,
            max_tokens=2000,
            description="Local Qwen NER pass for historical texts.",
        ),
        "note_standard": TaskPreset(
            name="note_standard",
            task_type="academic_note",
            provider="qwen",
            backend="llm_api",
            temperature=0.3,
            max_tokens=3000,
            description="Standard academic note generation.",
        ),
        "note_local_academic": TaskPreset(
            name="note_local_academic",
            task_type="academic_note",
            provider="ollama",
            model=get_local_model(get_model_role_for_task("academic_note")),
            backend="local_llm",
            temperature=0.3,
            max_tokens=4096,
            description="Local Qwen academic note generation.",
        ),
        "polish_conservative": TaskPreset(
            name="polish_conservative",
            task_type="paper_polish",
            provider="qwen",
            backend="llm_api",
            temperature=0.2,
            max_tokens=4000,
            description="Conservative paper polish.",
        ),
        "polish_local_academic": TaskPreset(
            name="polish_local_academic",
            task_type="paper_polish",
            provider="ollama",
            model=get_local_model(get_model_role_for_task("paper_polish")),
            backend="local_llm",
            temperature=0.2,
            max_tokens=4096,
            description="Local conservative academic polish.",
        ),
        "summary_short": TaskPreset(
            name="summary_short",
            task_type="text_summary",
            provider="qwen",
            backend="script",
            temperature=0.3,
            max_tokens=500,
            description="Short summary.",
        ),
        "summary_local_small": TaskPreset(
            name="summary_local_small",
            task_type="text_summary",
            provider="ollama",
            model=get_local_model("fast_local"),
            backend="local_llm",
            temperature=0.1,
            max_tokens=256,
            custom_prompt="用不超过{max_length}个汉字概括下列文本，只输出摘要：\n{text}",
            description="Small local Ollama model summary smoke preset.",
        ),
        "outline_local_reason": TaskPreset(
            name="outline_local_reason",
            task_type="reverse_outline",
            provider="ollama",
            model=get_local_model(get_model_role_for_task("reverse_outline")),
            backend="local_llm",
            temperature=0.2,
            max_tokens=4096,
            description="Local Gemma reverse-outline and logic review.",
        ),
        "outline_standard": TaskPreset(
            name="outline_standard",
            task_type="reverse_outline",
            provider="qwen",
            backend="script",
            temperature=0.1,
            max_tokens=1500,
            description="Reverse outline review with stable script fallback.",
        ),
        "ocr_correct": TaskPreset(
            name="ocr_correct",
            task_type="ocr_correction",
            provider="qwen",
            backend="script",
            temperature=0.1,
            max_tokens=4000,
            description="OCR cleanup preset.",
        ),
        "ocr_correct_local": TaskPreset(
            name="ocr_correct_local",
            task_type="ocr_correction",
            provider="ollama",
            model=get_local_model(get_model_role_for_task("ocr_correction")),
            backend="local_llm",
            temperature=0.1,
            max_tokens=4096,
            description="Local LLM OCR text cleanup preset.",
        ),
        "citation_gb": TaskPreset(
            name="citation_gb",
            task_type="citation_normalize",
            provider="qwen",
            backend="script",
            temperature=0.1,
            max_tokens=1000,
            description="GB/T 7714 normalization preset.",
        ),
        "historical_citation_parse": TaskPreset(
            name="historical_citation_parse",
            task_type="historical_citation",
            provider="local_rules",
            backend="script",
            temperature=0.0,
            max_tokens=0,
            description="Offline DOCX historical citation parse package.",
        ),
        "historical_citation_verify_metadata": TaskPreset(
            name="historical_citation_verify_metadata",
            task_type="historical_citation",
            provider="local_rules",
            backend="script",
            temperature=0.0,
            max_tokens=0,
            description="Historical citation verification metadata/search package; downloads remain explicit.",
        ),
    }

    TASK_ALIASES = {
        "summary": "text_summary",
        "text_summary": "text_summary",
        "citation": "citation_normalize",
        "citation_normalize": "citation_normalize",
        "history_citation": "historical_citation",
        "historical_citation": "historical_citation",
        "historical_citation_verifier": "historical_citation",
        "outline_review": "reverse_outline",
        "reverse_outline": "reverse_outline",
        "ocr": "ocr_correction",
        "ocr_correction": "ocr_correction",
        "virtual_persona": "virtual_persona",
        "entity_disambiguation": "entity_disambiguation",
    }

    TASK_REGISTRY: Dict[str, TaskRegistryEntry] = {
        "ner": TaskRegistryEntry(
            name="ner",
            adapter="NERAdapter",
            description="Historical named entity recognition.",
            input_contract=["text", "categories?"],
            output_contract=["entities", "confidence", "needs_review", "quality_flags"],
        ),
        "academic_note": TaskRegistryEntry(
            name="academic_note",
            adapter="AcademicNoteAdapter",
            description="Academic note generation from research text.",
            input_contract=["text", "source?"],
            output_contract=["note", "summary", "confidence", "needs_review", "quality_flags"],
        ),
        "paper_polish": TaskRegistryEntry(
            name="paper_polish",
            adapter="PaperPolishAdapter",
            description="Conservative academic writing polish.",
            input_contract=["text", "language?"],
            output_contract=["polished_text", "changes", "confidence", "needs_review", "quality_flags"],
        ),
        "citation_normalize": TaskRegistryEntry(
            name="citation_normalize",
            adapter="CitationAdapter",
            description="Citation normalization into a requested style.",
            input_contract=["citation", "target_style?"],
            output_contract=["normalized_citation", "confidence", "needs_review", "quality_flags"],
        ),
        "historical_citation": TaskRegistryEntry(
            name="historical_citation",
            adapter="HistoricalCitationAdapter",
            description="Workspace-safe DOCX historical citation parse and verification.",
            input_contract=[
                "file_path",
                "action?",
                "include_unquoted?",
                "search_ndl?",
                "download_source?",
                "restricted_download?",
                "platform_names?",
            ],
            output_contract=[
                "historical_citation_workspace_package",
                "confidence",
                "needs_review",
                "quality_flags",
            ],
        ),
        "ocr_correction": TaskRegistryEntry(
            name="ocr_correction",
            adapter="OCRAdapter",
            description="OCR text cleanup and correction.",
            input_contract=["text", "language?"],
            output_contract=["corrected_text", "confidence", "needs_review", "quality_flags"],
        ),
        "text_summary": TaskRegistryEntry(
            name="text_summary",
            adapter="SummaryAdapter",
            description="Short text summary with script/local/API backends.",
            input_contract=["text", "max_length?"],
            output_contract=["summary", "confidence", "needs_review", "quality_flags"],
        ),
        "reverse_outline": TaskRegistryEntry(
            name="reverse_outline",
            adapter="ReverseOutlineAdapter",
            description="Reverse outline and structure analysis.",
            input_contract=["text", "language?"],
            output_contract=["outline", "structure", "confidence", "needs_review", "quality_flags"],
        ),
        "style_transfer": TaskRegistryEntry(
            name="style_transfer",
            adapter="StyleTransferAdapter",
            description="Conservative style transfer for academic text.",
            input_contract=["text", "target_style"],
            output_contract=["rewritten_text", "style_analysis", "confidence", "needs_review", "quality_flags"],
        ),
        "virtual_persona": TaskRegistryEntry(
            name="virtual_persona",
            adapter="VirtualPersonaAdapter",
            description="Persona-guided historical research dialogue.",
            input_contract=["message", "persona", "history?"],
            output_contract=["response", "confidence", "needs_review", "quality_flags"],
        ),
        "entity_disambiguation": TaskRegistryEntry(
            name="entity_disambiguation",
            adapter="EntityDisambiguationAdapter",
            description="Entity candidate disambiguation and relation support.",
            input_contract=["entity", "context", "candidates?"],
            output_contract=["resolved_entity", "confidence", "needs_review", "quality_flags"],
        ),
    }

    def __init__(self, mode: str = "api", provider: str = "qwen"):
        self._mode = mode
        self._provider = provider
        self.key_manager = get_secure_key_manager()
        self.executor = UnifiedTaskExecutor(default_mode=mode)
        self.executor.set_provider(provider)
        self._presets = self.DEFAULT_PRESETS.copy()
        self._task_history: List[Dict[str, Any]] = []
        self._adapters = self._build_adapters()

    def _build_adapters(self) -> Dict[str, Any]:
        common = {"mode": self._mode, "provider": self._provider}
        adapters = {
            "ner": NERAdapter(**common),
            "academic_note": AcademicNoteAdapter(**common),
            "paper_polish": PaperPolishAdapter(**common),
            "citation_normalize": CitationAdapter(**common),
            "historical_citation": HistoricalCitationAdapter(mode="script", provider="local_rules", backend="script"),
            "ocr_correction": OCRAdapter(**common),
            "text_summary": SummaryAdapter(**common),
            "reverse_outline": ReverseOutlineAdapter(**common),
            "style_transfer": StyleTransferAdapter(**common),
            "virtual_persona": VirtualPersonaAdapter(**common),
            "entity_disambiguation": EntityDisambiguationAdapter(**common),
        }
        adapters["citation"] = adapters["citation_normalize"]
        adapters["history_citation"] = adapters["historical_citation"]
        adapters["historical_citation_verifier"] = adapters["historical_citation"]
        adapters["outline_review"] = adapters["reverse_outline"]
        adapters["ocr"] = adapters["ocr_correction"]
        adapters["summary"] = adapters["text_summary"]
        return adapters

    def _canonical_task_name(self, task_type: str) -> str:
        value = task_type.strip().lower()
        return self.TASK_ALIASES.get(value, value)

    def _apply_preset(self, task_type: str, preset: Optional[str], kwargs: Dict[str, Any]) -> Dict[str, Any]:
        if not preset:
            return kwargs
        preset_config = self._presets.get(preset)
        if preset_config is None:
            return kwargs
        if self._canonical_task_name(task_type) != self._canonical_task_name(preset_config.task_type):
            return kwargs
        merged = dict(kwargs)
        merged.setdefault("provider", preset_config.provider)
        merged.setdefault("model", preset_config.model)
        merged.setdefault("backend", preset_config.backend)
        merged.setdefault("temperature", preset_config.temperature)
        merged.setdefault("max_tokens", preset_config.max_tokens)
        if preset_config.custom_prompt:
            merged.setdefault("custom_prompt", preset_config.custom_prompt)
        return merged

    def _record_task(self, task_type: str, result: Dict[str, Any]) -> None:
        metadata = result.get("metadata", {})
        self._task_history.append(
            {
                "task_type": self._canonical_task_name(task_type),
                "mode": result.get("mode", self._mode),
                "provider": metadata.get("provider", self._provider),
                "backend": result.get("backend") or metadata.get("backend"),
                "success": bool(result.get("success")),
                "execution_time": float(result.get("execution_time", 0.0)),
                "timestamp": datetime.now().isoformat(),
            }
        )

    def _preset_to_dict(self, preset: TaskPreset) -> Dict[str, Any]:
        payload = asdict(preset)
        payload["task_type"] = self._canonical_task_name(payload["task_type"])
        return payload

    def _aliases_for_task(self, task_type: str) -> List[str]:
        return sorted(
            alias
            for alias, canonical in self.TASK_ALIASES.items()
            if canonical == task_type and alias != task_type
        )

    def _safe_task_capability(self, task_type: str) -> Dict[str, Any]:
        adapter = self._adapters.get(task_type)
        builtin_task_types = {item.value for item in TaskType}
        if task_type not in builtin_task_types and adapter is not None and hasattr(adapter, "get_capabilities"):
            try:
                capabilities = adapter.get_capabilities()
                return {
                    "task_type": task_type,
                    "label": capabilities.get("module", task_type),
                    "description": self.TASK_REGISTRY.get(task_type, TaskRegistryEntry(task_type, "", "", [], [])).description,
                    "required_params": self.TASK_REGISTRY.get(task_type, TaskRegistryEntry(task_type, "", "", [], [])).input_contract,
                    "backends": [
                        {
                            "name": backend,
                            "kind": "external" if backend in {"skill", "mcp"} else backend,
                            "label": backend,
                            "available": backend == "script",
                            "description": "Workspace adapter backend option.",
                            "metadata": {},
                        }
                        for backend in capabilities.get("backend_options", ["script"])
                    ],
                    "providers": self.executor.get_available_providers(include_status=True),
                    "capabilities": capabilities,
                }
            except Exception as exc:  # noqa: BLE001
                return {
                    "task_type": task_type,
                    "available": False,
                    "error": str(exc),
                    "backends": [],
                }
        try:
            return self.executor.get_task_capability(task_type)
        except Exception as exc:
            return {
                "task_type": task_type,
                "available": False,
                "error": str(exc),
                "backends": [],
            }

    def _safe_backend_names(self, capability: Dict[str, Any]) -> List[str]:
        backends = capability.get("backends", [])
        names: List[str] = []
        for item in backends:
            if isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
        return names

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.executor.set_mode(mode)
        for adapter in self._adapters.values():
            adapter.set_mode(mode)

    @property
    def provider(self) -> str:
        return self._provider

    def set_provider(self, provider: str) -> None:
        self._provider = provider
        self.executor.set_provider(provider)
        for adapter in self._adapters.values():
            adapter.set_provider(provider)

    def get_available_providers(self, detailed: bool = False) -> List[Any]:
        return self.executor.get_available_providers(include_status=detailed)

    def get_available_tasks(self, detailed: bool = False) -> Any:
        tasks = list(self.TASK_REGISTRY.keys())
        if detailed:
            return {task: self._safe_task_capability(task) for task in tasks}
        return tasks

    def get_task_options(self, task_type: str) -> Dict[str, Any]:
        canonical = self._canonical_task_name(task_type)
        if canonical in self._adapters and canonical not in {item.value for item in TaskType}:
            return self._safe_task_capability(canonical)
        return self.executor.get_task_capability(canonical)

    def get_presets(self) -> Dict[str, TaskPreset]:
        return self._presets

    def get_preset_options(self) -> Dict[str, Any]:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for preset in self._presets.values():
            task_type = self._canonical_task_name(preset.task_type)
            grouped.setdefault(task_type, []).append(self._preset_to_dict(preset))
        return {
            "schema_version": "1.0",
            "presets": {name: self._preset_to_dict(preset) for name, preset in self._presets.items()},
            "by_task": grouped,
        }

    def get_task_registry(self, detailed: bool = False) -> Dict[str, Any]:
        registry: Dict[str, Any] = {}
        preset_options = self.get_preset_options()["by_task"]
        for task_type, entry in self.TASK_REGISTRY.items():
            capability = self._safe_task_capability(task_type)
            payload = {
                "name": entry.name,
                "canonical_name": task_type,
                "aliases": self._aliases_for_task(task_type),
                "adapter": entry.adapter,
                "description": entry.description,
                "input_contract": list(entry.input_contract),
                "output_contract": list(entry.output_contract),
                "available": task_type in self._adapters,
                "backends": self._safe_backend_names(capability),
                "presets": [item["name"] for item in preset_options.get(task_type, [])],
            }
            if detailed:
                payload["capability"] = capability
                payload["preset_details"] = preset_options.get(task_type, [])
            registry[task_type] = payload
        return {
            "schema_version": "1.0",
            "module": "task_manager",
            "mode": self._mode,
            "provider": self._provider,
            "tasks": registry,
            "aliases": dict(self.TASK_ALIASES),
        }

    def get_history_summary(self) -> Dict[str, Any]:
        stats = self.get_statistics()
        return {
            "total_tasks": stats["total_tasks"],
            "success_rate": stats["success_rate"],
            "average_time": stats["average_time"],
            "task_distribution": stats["task_distribution"],
            "backend_distribution": stats["backend_distribution"],
        }

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "type": "task_manager_capabilities",
            "schema_version": "1.0",
            "module": "task_manager",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "mode": self._mode,
            "provider": self._provider,
            "tasks": self.get_task_registry(detailed=True)["tasks"],
            "presets": self.get_preset_options(),
            "history_summary": self.get_history_summary(),
            "backend_options": ["script", "local_llm", "llm_api", "skill", "mcp"],
            "fallback_order": ["script", "local_llm", "llm_api", "skill", "mcp"],
            "privacy": {
                "uses_secure_key_manager": True,
                "exposes_secret_values": False,
                "secret_status_is_redacted": True,
                "artifact_policy": "no_intermediate_files_by_default",
            },
        }

    def add_preset(self, preset: TaskPreset) -> None:
        self._presets[preset.name] = preset

    def remove_preset(self, name: str) -> None:
        if name in self._presets and name not in self.DEFAULT_PRESETS:
            del self._presets[name]

    def execute_task(self, task_type: str, preset: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
        canonical = self._canonical_task_name(task_type)
        merged_kwargs = self._apply_preset(canonical, preset, kwargs)
        adapter = self._adapters.get(canonical)
        if adapter is None:
            raise ValueError(f"Unsupported task type: {task_type}")

        if canonical == "ner":
            result = adapter.recognize(
                merged_kwargs.pop("text"),
                categories=merged_kwargs.pop("categories", None),
                **merged_kwargs,
            )
        elif canonical == "academic_note":
            result = adapter.generate(
                merged_kwargs.pop("text"),
                source=merged_kwargs.pop("source", "unknown"),
                **merged_kwargs,
            )
        elif canonical == "paper_polish":
            result = adapter.polish(
                merged_kwargs.pop("text"),
                language=merged_kwargs.pop("language", "zh"),
                **merged_kwargs,
            )
        elif canonical == "citation_normalize":
            result = adapter.normalize(
                merged_kwargs.pop("citation"),
                target_style=merged_kwargs.pop("target_style", "gb7714"),
                **merged_kwargs,
            )
        elif canonical == "historical_citation":
            result = adapter.execute_package(
                file_path=merged_kwargs.pop("file_path"),
                action=merged_kwargs.pop("action", "parse"),
                **merged_kwargs,
            )
        elif canonical == "ocr_correction":
            result = adapter.correct(
                merged_kwargs.pop("text"),
                language=merged_kwargs.pop("language", "zh"),
                **merged_kwargs,
            )
        elif canonical == "text_summary":
            result = adapter.summarize(
                merged_kwargs.pop("text"),
                max_length=merged_kwargs.pop("max_length", 200),
                **merged_kwargs,
            )
        elif canonical == "reverse_outline":
            result = adapter.analyze(
                merged_kwargs.pop("text"),
                language=merged_kwargs.pop("language", "zh"),
                **merged_kwargs,
            )
        elif canonical == "style_transfer":
            result = adapter.transfer_style(
                merged_kwargs.pop("text"),
                target_style=merged_kwargs.pop("target_style"),
                **merged_kwargs,
            )
        elif canonical == "virtual_persona":
            result = adapter.chat(
                merged_kwargs.pop("message"),
                persona=merged_kwargs.pop("persona"),
                history=merged_kwargs.pop("history", None),
                **merged_kwargs,
            )
        elif canonical == "entity_disambiguation":
            result = adapter.disambiguate(
                merged_kwargs.pop("entity"),
                context=merged_kwargs.pop("context"),
                candidates=merged_kwargs.pop("candidates", None),
                **merged_kwargs,
            )
        else:
            raise ValueError(f"Unsupported task type: {task_type}")

        self._record_task(canonical, result)
        return result

    def execute_task_package(self, task_type: str, preset: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
        canonical = self._canonical_task_name(task_type)
        started = datetime.now()
        result: Dict[str, Any]
        try:
            result = self.execute_task(canonical, preset=preset, **kwargs)
        except Exception as exc:
            result = {
                "success": False,
                "data": {},
                "error": str(exc),
                "mode": self._mode,
                "backend": kwargs.get("backend"),
                "execution_time": (datetime.now() - started).total_seconds(),
                "metadata": {"provider": kwargs.get("provider", self._provider)},
                "confidence": 0.0,
                "needs_review": True,
                "quality_flags": ["task_execution_failed"],
            }
            self._record_task(canonical, result)

        metadata = result.get("metadata", {})
        data = result if canonical == "historical_citation" else result.get("data", result)
        return {
            "type": "task_execution",
            "schema_version": "1.0",
            "task_type": canonical,
            "requested_task_type": task_type,
            "preset": preset,
            "success": bool(result.get("success")),
            "mode": result.get("mode", self._mode),
            "backend": result.get("backend") or metadata.get("backend") or kwargs.get("backend"),
            "provider": metadata.get("provider", kwargs.get("provider", self._provider)),
            "model": metadata.get("model", kwargs.get("model")),
            "confidence": float(result.get("confidence", metadata.get("confidence", 0.0)) or 0.0),
            "needs_review": bool(result.get("needs_review", metadata.get("needs_review", False))),
            "quality_flags": list(result.get("quality_flags", metadata.get("quality_flags", [])) or []),
            "execution_time": float(result.get("execution_time", 0.0) or 0.0),
            "data": data,
            "result": result,
            "task_options": self.get_task_registry(detailed=False)["tasks"].get(canonical, {}),
            "artifacts": [],
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

    def ner(
        self,
        text: str,
        categories: Optional[List[str]] = None,
        preset: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self.execute_task("ner", preset=preset, text=text, categories=categories, **kwargs)

    def academic_note(
        self,
        text: str,
        source: str = "unknown",
        preset: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self.execute_task("academic_note", preset=preset, text=text, source=source, **kwargs)

    def paper_polish(
        self,
        text: str,
        language: str = "zh",
        preset: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self.execute_task("paper_polish", preset=preset, text=text, language=language, **kwargs)

    def citation_normalize(
        self,
        citation: str,
        target_style: str = "gb7714",
        preset: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self.execute_task(
            "citation_normalize",
            preset=preset,
            citation=citation,
            target_style=target_style,
            **kwargs,
        )

    def historical_citation(
        self,
        file_path: str,
        action: str = "parse",
        preset: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self.execute_task(
            "historical_citation",
            preset=preset,
            file_path=file_path,
            action=action,
            **kwargs,
        )

    def ocr_correct(
        self,
        text: str,
        language: str = "zh",
        preset: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self.execute_task("ocr_correction", preset=preset, text=text, language=language, **kwargs)

    def summarize(
        self,
        text: str,
        max_length: int = 200,
        preset: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self.execute_task("text_summary", preset=preset, text=text, max_length=max_length, **kwargs)

    def reverse_outline(
        self,
        text: str,
        language: str = "zh",
        preset: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self.execute_task("reverse_outline", preset=preset, text=text, language=language, **kwargs)

    def style_transfer(self, text: str, target_style: str, **kwargs: Any) -> Dict[str, Any]:
        return self.execute_task("style_transfer", text=text, target_style=target_style, **kwargs)

    def virtual_persona_chat(
        self,
        message: str,
        persona: str,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self.execute_task("virtual_persona", message=message, persona=persona, history=history or [], **kwargs)

    def entity_disambiguation(
        self,
        entity: str,
        context: str,
        candidates: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self.execute_task(
            "entity_disambiguation",
            entity=entity,
            context=context,
            candidates=candidates or [],
            **kwargs,
        )

    def execute_with_prompt(self, task_type: str, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        config_keys = {
            "provider",
            "model",
            "temperature",
            "max_tokens",
            "timeout",
            "max_retries",
            "cache_enabled",
            "backend",
            "fallback_backends",
            "preferred_providers",
            "extra_params",
        }
        config_kwargs = {key: kwargs.pop(key) for key in list(kwargs.keys()) if key in config_keys}
        config = TaskConfig(
            task_type=TaskType(self._canonical_task_name(task_type)),
            provider=config_kwargs.pop("provider", self._provider),
            model=config_kwargs.pop("model", None),
            temperature=config_kwargs.pop("temperature", 0.3),
            max_tokens=config_kwargs.pop("max_tokens", 2000),
            timeout=config_kwargs.pop("timeout", 60),
            max_retries=config_kwargs.pop("max_retries", 3),
            cache_enabled=config_kwargs.pop("cache_enabled", True),
            custom_prompt=prompt,
            backend=config_kwargs.pop("backend", None),
            fallback_backends=config_kwargs.pop("fallback_backends", []),
            preferred_providers=config_kwargs.pop("preferred_providers", []),
            extra_params=config_kwargs.pop("extra_params", {}),
        )
        result = self.executor.execute(self._canonical_task_name(task_type), config=config, **kwargs)
        payload = {
            "success": result.success,
            "data": result.data,
            "mode": result.mode,
            "backend": result.metadata.get("backend"),
            "error": result.error,
            "execution_time": result.execution_time,
            "metadata": result.metadata,
        }
        self._record_task(task_type, payload)
        return payload

    def batch_execute(
        self,
        task_type: str,
        inputs: List[Dict[str, Any]],
        preset: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return [self.execute_task(task_type, preset=preset, **item) for item in inputs]

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._task_history[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        if not self._task_history:
            return {
                "total_tasks": 0,
                "success_rate": 0.0,
                "average_time": 0.0,
                "task_distribution": {},
                "backend_distribution": {},
                "mode": self._mode,
                "provider": self._provider,
            }

        total = len(self._task_history)
        success_count = sum(1 for entry in self._task_history if entry["success"])
        average_time = sum(entry["execution_time"] for entry in self._task_history) / total
        task_distribution: Dict[str, int] = {}
        backend_distribution: Dict[str, int] = {}
        for entry in self._task_history:
            task_distribution[entry["task_type"]] = task_distribution.get(entry["task_type"], 0) + 1
            backend = entry.get("backend") or "unknown"
            backend_distribution[backend] = backend_distribution.get(backend, 0) + 1
        return {
            "total_tasks": total,
            "success_rate": success_count / total,
            "average_time": average_time,
            "task_distribution": task_distribution,
            "backend_distribution": backend_distribution,
            "mode": self._mode,
            "provider": self._provider,
            "executor": self.executor.get_statistics(),
        }

    def export_results(self, results: List[Dict[str, Any]], output_path: str, format: str = "json") -> bool:
        try:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            if format == "json":
                path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
            elif format == "txt":
                lines = []
                for index, result in enumerate(results, start=1):
                    lines.append(f"=== Result {index} ===")
                    lines.append(f"success: {result.get('success')}")
                    lines.append(f"mode: {result.get('mode')}")
                    lines.append(f"backend: {result.get('backend')}")
                    lines.append(json.dumps(result.get("data", {}), ensure_ascii=False))
                    lines.append("")
                path.write_text("\n".join(lines), encoding="utf-8")
            elif format == "csv":
                import csv

                with path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(["success", "mode", "backend", "execution_time"])
                    for result in results:
                        writer.writerow(
                            [
                                result.get("success"),
                                result.get("mode"),
                                result.get("backend"),
                                result.get("execution_time"),
                            ]
                        )
            else:
                raise ValueError(f"Unsupported export format: {format}")
            return True
        except Exception:
            return False

    def get_api_key_status(self) -> Dict[str, Any]:
        return self.key_manager.get_status_report()


def get_task_manager() -> TaskManager:
    return TaskManager()
