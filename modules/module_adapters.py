from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from modules.unified_task_executor import TaskConfig, TaskResult, TaskType, UnifiedTaskExecutor
from modules.historical_citation_workspace import HistoricalCitationWorkspaceInterface


def _read_text_file(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    return path.read_text(encoding="utf-8")


@dataclass(frozen=True)
class AdapterSpec:
    task_type: str
    adapter_class: str
    primary_method: str
    required_inputs: List[str]
    optional_inputs: List[str]
    aliases: List[str]
    description: str
    package_method: str = "execute_package"
    supports_file_input: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BaseAdapter:
    task_type: TaskType = TaskType.CUSTOM

    def __init__(
        self,
        mode: str = "api",
        provider: str = "qwen",
        model: Optional[str] = None,
        backend: Optional[str] = None,
    ):
        self.executor = UnifiedTaskExecutor(default_mode=mode)
        self.executor.set_provider(provider)
        self.provider = provider
        self.model = model
        self.backend = backend

    def set_mode(self, mode: str) -> None:
        self.executor.set_mode(mode)

    def get_mode(self) -> str:
        return self.executor.get_mode()

    def set_provider(self, provider: str) -> None:
        self.provider = provider
        self.executor.set_provider(provider)

    def set_model(self, model: str) -> None:
        self.model = model

    def set_backend(self, backend: Optional[str]) -> None:
        self.backend = backend

    def get_capabilities(self) -> Dict[str, Any]:
        capability = self.executor.get_task_capability(self.task_type)
        return {
            **capability,
            "adapter": get_adapter_spec(self.task_type.value),
        }

    def _create_config(self, **kwargs: Any) -> TaskConfig:
        extra_params = dict(kwargs.pop("extra_params", {}))
        if kwargs.get("local_provider"):
            extra_params["local_provider"] = kwargs["local_provider"]
        if kwargs.get("local_model"):
            extra_params["local_model"] = kwargs["local_model"]
        if kwargs.get("local_base_url"):
            extra_params["local_base_url"] = kwargs["local_base_url"]
        if kwargs.get("api_key"):
            extra_params["api_key"] = kwargs["api_key"]
        if kwargs.get("base_url"):
            extra_params["base_url"] = kwargs["base_url"]

        return TaskConfig(
            task_type=self.task_type,
            provider=kwargs.get("provider", self.provider),
            model=kwargs.get("model", self.model),
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 2000),
            timeout=kwargs.get("timeout", 60),
            max_retries=kwargs.get("max_retries", 3),
            cache_enabled=kwargs.get("cache_enabled", True),
            custom_prompt=kwargs.get("custom_prompt"),
            backend=kwargs.get("backend", self.backend),
            fallback_backends=list(kwargs.get("fallback_backends", [])),
            preferred_providers=list(kwargs.get("preferred_providers", [])),
            extra_params=extra_params,
        )

    def _handle_result(self, result: TaskResult) -> Dict[str, Any]:
        if not result.success:
            return {
                "success": False,
                "error": result.error,
                "mode": result.mode,
                "backend": result.metadata.get("backend"),
                "execution_time": result.execution_time,
                "metadata": result.metadata,
            }

        return {
            "success": True,
            "data": result.data,
            "mode": result.mode,
            "backend": result.metadata.get("backend"),
            "execution_time": result.execution_time,
            "metadata": result.metadata,
        }

    def _split_execution_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        config = self._create_config(**kwargs)
        payload = dict(kwargs)
        payload.pop("provider", None)
        payload.pop("model", None)
        payload.pop("temperature", None)
        payload.pop("max_tokens", None)
        payload.pop("timeout", None)
        payload.pop("max_retries", None)
        payload.pop("cache_enabled", None)
        payload.pop("custom_prompt", None)
        payload.pop("backend", None)
        payload.pop("fallback_backends", None)
        payload.pop("preferred_providers", None)
        payload.pop("extra_params", None)
        payload.pop("local_provider", None)
        payload.pop("local_model", None)
        payload.pop("local_base_url", None)
        payload.pop("api_key", None)
        payload.pop("base_url", None)
        return {"config": config, "payload": payload}

    def _execute(self, **kwargs: Any) -> Dict[str, Any]:
        execution = self._split_execution_kwargs(kwargs)
        return self._handle_result(
            self.executor.execute(self.task_type, config=execution["config"], **execution["payload"])
        )

    def execute_package(
        self,
        *,
        artifacts: Optional[List[Dict[str, Any]]] = None,
        artifact_path: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        execution = self._split_execution_kwargs(kwargs)
        return self.executor.execute_package(
            self.task_type,
            config=execution["config"],
            artifacts=artifacts,
            artifact_path=artifact_path,
            **execution["payload"],
        )


class NERAdapter(BaseAdapter):
    task_type = TaskType.NER

    def recognize(
        self,
        text: str,
        categories: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self._execute(text=text, categories=categories, **kwargs)

    def recognize_from_file(
        self,
        file_path: str,
        categories: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self.recognize(_read_text_file(file_path), categories=categories, **kwargs)


class AcademicNoteAdapter(BaseAdapter):
    task_type = TaskType.ACADEMIC_NOTE

    def generate(self, text: str, source: str = "unknown", **kwargs: Any) -> Dict[str, Any]:
        return self._execute(text=text, source=source, **kwargs)

    def generate_from_file(
        self,
        file_path: str,
        source: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        path = Path(file_path)
        return self.generate(_read_text_file(file_path), source=source or path.name, **kwargs)

    def save_note(self, note_content: str, output_path: str, title: Optional[str] = None) -> Dict[str, Any]:
        try:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(note_content, encoding="utf-8")
            return {"success": True, "path": str(path), "title": title}
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": str(exc)}


class PaperPolishAdapter(BaseAdapter):
    task_type = TaskType.PAPER_POLISH

    def polish(self, text: str, language: str = "zh", **kwargs: Any) -> Dict[str, Any]:
        return self._execute(text=text, language=language, **kwargs)

    def polish_paragraphs(
        self,
        paragraphs: List[str],
        language: str = "zh",
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        return [self.polish(paragraph, language=language, **kwargs) for paragraph in paragraphs]


class CitationAdapter(BaseAdapter):
    task_type = TaskType.CITATION_NORMALIZE

    def normalize(self, citation: str, target_style: str = "gb7714", **kwargs: Any) -> Dict[str, Any]:
        return self._execute(citation=citation, target_style=target_style, **kwargs)

    def normalize_batch(
        self,
        citations: List[str],
        target_style: str = "gb7714",
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        return [self.normalize(citation, target_style=target_style, **kwargs) for citation in citations]


class HistoricalCitationAdapter:
    """Thin task-layer adapter around the workspace-safe citation verifier."""

    def __init__(
        self,
        mode: str = "script",
        provider: str = "local_rules",
        model: Optional[str] = None,
        backend: Optional[str] = "script",
        verifier: Optional[Any] = None,
    ):
        self.mode = mode
        self.provider = provider
        self.model = model
        self.backend = backend
        self.interface = HistoricalCitationWorkspaceInterface(verifier=verifier)

    def set_mode(self, mode: str) -> None:
        self.mode = mode

    def get_mode(self) -> str:
        return self.mode

    def set_provider(self, provider: str) -> None:
        self.provider = provider

    def set_model(self, model: str) -> None:
        self.model = model

    def set_backend(self, backend: Optional[str]) -> None:
        self.backend = backend

    def get_capabilities(self) -> Dict[str, Any]:
        capabilities = self.interface.get_capabilities()
        capabilities["adapter"] = get_adapter_spec("historical_citation")
        return capabilities

    def parse_docx_package(self, file_path: str, include_unquoted: bool = False, **kwargs: Any) -> Dict[str, Any]:
        del kwargs
        return self.interface.parse_docx_package(file_path, include_unquoted=include_unquoted)

    def verify_docx_package(self, file_path: str, **kwargs: Any) -> Dict[str, Any]:
        return self.interface.verify_docx_package(file_path, **kwargs)

    def execute_package(
        self,
        *,
        file_path: str,
        action: str = "parse",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self.interface.build_package(file_path=file_path, action=action, **kwargs)


class OCRAdapter(BaseAdapter):
    task_type = TaskType.OCR_CORRECTION

    def correct(self, text: str, language: str = "zh", **kwargs: Any) -> Dict[str, Any]:
        return self._execute(text=text, language=language, **kwargs)


class SummaryAdapter(BaseAdapter):
    task_type = TaskType.TEXT_SUMMARY

    def summarize(self, text: str, max_length: int = 200, **kwargs: Any) -> Dict[str, Any]:
        return self._execute(text=text, max_length=max_length, **kwargs)


class ReverseOutlineAdapter(BaseAdapter):
    task_type = TaskType.REVERSE_OUTLINE

    def analyze(self, text: str, language: str = "zh", **kwargs: Any) -> Dict[str, Any]:
        return self._execute(text=text, language=language, **kwargs)


class StyleTransferAdapter(BaseAdapter):
    task_type = TaskType.STYLE_TRANSFER

    def analyze_style(self, text: str, **kwargs: Any) -> Dict[str, Any]:
        custom_prompt = (
            "Analyze the style of the text. Return JSON with sentence_structure, vocabulary, tone, and rhetorical_patterns.\n"
            "Text:\n{text}"
        )
        return self._execute(text=text, custom_prompt=custom_prompt, **kwargs)

    def transfer_style(self, text: str, target_style: str, **kwargs: Any) -> Dict[str, Any]:
        return self._execute(text=text, target_style=target_style, **kwargs)


class VirtualPersonaAdapter(BaseAdapter):
    task_type = TaskType.VIRTUAL_PERSONA

    def chat(
        self,
        message: str,
        persona: str,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self._execute(message=message, persona=persona, history=history or [], **kwargs)


class EntityDisambiguationAdapter(BaseAdapter):
    task_type = TaskType.ENTITY_DISAMBIGUATION

    def disambiguate(
        self,
        entity: str,
        context: str,
        candidates: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self._execute(entity=entity, context=context, candidates=candidates or [], **kwargs)


ADAPTER_CLASSES: Dict[str, Type[BaseAdapter]] = {
    "ner": NERAdapter,
    "academic_note": AcademicNoteAdapter,
    "paper_polish": PaperPolishAdapter,
    "citation_normalize": CitationAdapter,
    "historical_citation": HistoricalCitationAdapter,
    "ocr_correction": OCRAdapter,
    "text_summary": SummaryAdapter,
    "reverse_outline": ReverseOutlineAdapter,
    "style_transfer": StyleTransferAdapter,
    "virtual_persona": VirtualPersonaAdapter,
    "entity_disambiguation": EntityDisambiguationAdapter,
}

ADAPTER_ALIASES: Dict[str, str] = {
    "citation": "citation_normalize",
    "history_citation": "historical_citation",
    "historical_citation_verifier": "historical_citation",
    "ocr": "ocr_correction",
    "summary": "text_summary",
    "outline_review": "reverse_outline",
}

ADAPTER_SPECS: Dict[str, AdapterSpec] = {
    "ner": AdapterSpec(
        task_type="ner",
        adapter_class="NERAdapter",
        primary_method="recognize",
        required_inputs=["text"],
        optional_inputs=["categories"],
        aliases=[],
        description="Historical named entity recognition adapter.",
        supports_file_input=True,
    ),
    "academic_note": AdapterSpec(
        task_type="academic_note",
        adapter_class="AcademicNoteAdapter",
        primary_method="generate",
        required_inputs=["text"],
        optional_inputs=["source"],
        aliases=[],
        description="Academic note generation adapter.",
        supports_file_input=True,
    ),
    "paper_polish": AdapterSpec(
        task_type="paper_polish",
        adapter_class="PaperPolishAdapter",
        primary_method="polish",
        required_inputs=["text"],
        optional_inputs=["language"],
        aliases=[],
        description="Academic paper polish adapter.",
    ),
    "citation_normalize": AdapterSpec(
        task_type="citation_normalize",
        adapter_class="CitationAdapter",
        primary_method="normalize",
        required_inputs=["citation"],
        optional_inputs=["target_style"],
        aliases=["citation"],
        description="Citation normalization adapter.",
    ),
    "historical_citation": AdapterSpec(
        task_type="historical_citation",
        adapter_class="HistoricalCitationAdapter",
        primary_method="execute_package",
        required_inputs=["file_path"],
        optional_inputs=[
            "action",
            "include_unquoted",
            "search_ndl",
            "download_source",
            "restricted_download",
            "platform_names",
        ],
        aliases=["history_citation", "historical_citation_verifier"],
        description="Workspace-safe DOCX historical citation parse/verification adapter.",
        supports_file_input=True,
    ),
    "ocr_correction": AdapterSpec(
        task_type="ocr_correction",
        adapter_class="OCRAdapter",
        primary_method="correct",
        required_inputs=["text"],
        optional_inputs=["language"],
        aliases=["ocr"],
        description="OCR text correction adapter.",
    ),
    "text_summary": AdapterSpec(
        task_type="text_summary",
        adapter_class="SummaryAdapter",
        primary_method="summarize",
        required_inputs=["text"],
        optional_inputs=["max_length"],
        aliases=["summary"],
        description="Text summary adapter.",
    ),
    "reverse_outline": AdapterSpec(
        task_type="reverse_outline",
        adapter_class="ReverseOutlineAdapter",
        primary_method="analyze",
        required_inputs=["text"],
        optional_inputs=["language"],
        aliases=["outline_review"],
        description="Reverse outline adapter.",
    ),
    "style_transfer": AdapterSpec(
        task_type="style_transfer",
        adapter_class="StyleTransferAdapter",
        primary_method="transfer_style",
        required_inputs=["text", "target_style"],
        optional_inputs=[],
        aliases=[],
        description="Style transfer adapter.",
    ),
    "virtual_persona": AdapterSpec(
        task_type="virtual_persona",
        adapter_class="VirtualPersonaAdapter",
        primary_method="chat",
        required_inputs=["message", "persona"],
        optional_inputs=["history"],
        aliases=[],
        description="Virtual persona adapter.",
    ),
    "entity_disambiguation": AdapterSpec(
        task_type="entity_disambiguation",
        adapter_class="EntityDisambiguationAdapter",
        primary_method="disambiguate",
        required_inputs=["entity", "context"],
        optional_inputs=["candidates"],
        aliases=[],
        description="Entity disambiguation adapter.",
    ),
}

ADAPTER_REGISTRY: Dict[str, Type[BaseAdapter]] = dict(ADAPTER_CLASSES)
for alias, canonical in ADAPTER_ALIASES.items():
    ADAPTER_REGISTRY[alias] = ADAPTER_CLASSES[canonical]


def canonical_adapter_type(adapter_type: str) -> str:
    value = adapter_type.strip().lower()
    return ADAPTER_ALIASES.get(value, value)


def get_adapter_spec(adapter_type: str) -> Dict[str, Any]:
    canonical = canonical_adapter_type(adapter_type)
    spec = ADAPTER_SPECS.get(canonical)
    if spec is None:
        raise ValueError(f"Unknown adapter type: {adapter_type}")
    return spec.to_dict()


def list_adapter_specs() -> List[Dict[str, Any]]:
    return [spec.to_dict() for spec in ADAPTER_SPECS.values()]


def get_adapter_registry(detailed: bool = False) -> Dict[str, Any]:
    registry = {
        name: {
            "task_type": name,
            "adapter_class": adapter_class.__name__,
            "aliases": ADAPTER_SPECS[name].aliases,
        }
        for name, adapter_class in ADAPTER_CLASSES.items()
    }
    if detailed:
        for name, payload in registry.items():
            payload["spec"] = ADAPTER_SPECS[name].to_dict()
    return {
        "schema_version": "1.0",
        "module": "module_adapters",
        "adapters": registry,
        "aliases": dict(ADAPTER_ALIASES),
    }


def create_adapter(
    adapter_type: str,
    mode: str = "api",
    provider: str = "qwen",
    **kwargs: Any,
) -> BaseAdapter:
    adapter_class = ADAPTER_CLASSES.get(canonical_adapter_type(adapter_type))
    if adapter_class is None:
        raise ValueError(f"Unknown adapter type: {adapter_type}")
    return adapter_class(mode=mode, provider=provider, **kwargs)
