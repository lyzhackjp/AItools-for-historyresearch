from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from modules.secure_api_key_manager import SecureAPIKeyManager, get_secure_key_manager


class ExecutionMode(Enum):
    API = "api"
    SCRIPT = "script"
    AUTO = "auto"


class TaskType(Enum):
    NER = "ner"
    ACADEMIC_NOTE = "academic_note"
    PAPER_POLISH = "paper_polish"
    CITATION_NORMALIZE = "citation_normalize"
    STYLE_TRANSFER = "style_transfer"
    OCR_CORRECTION = "ocr_correction"
    TEXT_SUMMARY = "text_summary"
    ENTITY_DISAMBIGUATION = "entity_disambiguation"
    REVERSE_OUTLINE = "reverse_outline"
    VIRTUAL_PERSONA = "virtual_persona"
    DATA_STRUCTURE = "data_structure"
    CUSTOM = "custom"


TASK_NAME_ALIASES: Dict[str, TaskType] = {
    "summary": TaskType.TEXT_SUMMARY,
    "text_summary": TaskType.TEXT_SUMMARY,
    "citation": TaskType.CITATION_NORMALIZE,
    "citation_normalize": TaskType.CITATION_NORMALIZE,
    "ocr": TaskType.OCR_CORRECTION,
    "ocr_correction": TaskType.OCR_CORRECTION,
    "virtual_persona": TaskType.VIRTUAL_PERSONA,
    "entity_disambiguation": TaskType.ENTITY_DISAMBIGUATION,
    "outline_review": TaskType.REVERSE_OUTLINE,
    "reverse_outline": TaskType.REVERSE_OUTLINE,
}

PROVIDER_ALIASES = {
    "qwen": "dashscope",
    "dashscope": "dashscope",
    "chatgpt": "openai",
    "claude": "anthropic",
    "local": "ollama",
}

REMOTE_PROVIDER_LABELS = [
    ("qwen", "Qwen / DashScope"),
    ("openai", "OpenAI"),
    ("deepseek", "DeepSeek"),
    ("minimax", "MiniMax"),
    ("zhipu", "Zhipu"),
    ("volcano", "Volcano"),
    ("anthropic", "Anthropic"),
    ("gemini", "Gemini"),
]


def _normalize_provider(provider: Optional[str]) -> str:
    value = (provider or "qwen").strip().lower()
    return PROVIDER_ALIASES.get(value, value)


def _normalize_task_type(task_type: Union[TaskType, str]) -> TaskType:
    if isinstance(task_type, TaskType):
        return task_type
    value = (task_type or "").strip().lower()
    if value in TASK_NAME_ALIASES:
        return TASK_NAME_ALIASES[value]
    return TaskType(value)


class _FormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _safe_format(template: str, payload: Mapping[str, Any]) -> str:
    return template.format_map(_FormatDict({key: value for key, value in payload.items()}))


@dataclass
class BackendOption:
    name: str
    kind: str
    label: str
    description: str = ""
    available: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "label": self.label,
            "description": self.description,
            "available": self.available,
            "metadata": self.metadata,
        }


@dataclass
class TaskResult:
    success: bool
    data: Any
    mode: str
    task_type: str
    execution_time: float
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "mode": self.mode,
            "task_type": self.task_type,
            "execution_time": self.execution_time,
            "error": self.error,
            "metadata": self.metadata,
        }

    def to_package(self, artifacts: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        validation = self.metadata.get("validation", {})
        return {
            "type": "task_execution",
            "schema_version": "1.0",
            "task_type": self.task_type,
            "success": self.success,
            "mode": self.mode,
            "backend": self.metadata.get("backend"),
            "provider": self.metadata.get("provider"),
            "model": self.metadata.get("model"),
            "confidence": validation.get("confidence", 1.0 if self.success else 0.0),
            "needs_review": validation.get("needs_review", not self.success),
            "quality_flags": validation.get("quality_flags", []),
            "validation": validation,
            "execution_time": self.execution_time,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
            "artifacts": artifacts or [],
            "artifact_policy": {
                "writes_by_default": False,
                "allowed_when_explicit_path": True,
                "forbidden_roots": ["secrets"],
            },
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }


@dataclass
class TaskConfig:
    task_type: TaskType
    provider: str = "qwen"
    model: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 2000
    timeout: int = 60
    max_retries: int = 3
    cache_enabled: bool = True
    custom_prompt: Optional[str] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)
    backend: Optional[str] = None
    fallback_backends: List[str] = field(default_factory=list)
    preferred_providers: List[str] = field(default_factory=list)


@dataclass
class ExternalBackendRegistration:
    task_type: TaskType
    name: str
    kind: str
    label: str
    handler: Callable[[Dict[str, Any], TaskConfig], Any]
    description: str = ""
    availability_checker: Optional[Callable[[], bool]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_available(self) -> bool:
        if self.availability_checker is None:
            return True
        try:
            return bool(self.availability_checker())
        except Exception:
            return False

    def to_option(self) -> BackendOption:
        return BackendOption(
            name=self.name,
            kind=self.kind,
            label=self.label,
            description=self.description,
            available=self.is_available(),
            metadata=self.metadata,
        )


class BaseTaskHandler:
    task_type: TaskType = TaskType.CUSTOM
    display_name: str = "Custom Task"
    description: str = ""
    supports_api: bool = True
    supports_script: bool = True
    supports_local_llm: bool = True

    def __init__(self, key_manager: SecureAPIKeyManager):
        self.key_manager = key_manager

    def get_required_params(self) -> List[str]:
        return []

    def build_prompt(self, input_data: Dict[str, Any], config: TaskConfig) -> str:
        raise NotImplementedError

    def parse_api_response(
        self,
        content: str,
        input_data: Dict[str, Any],
        config: TaskConfig,
    ) -> Any:
        return {"content": content}

    def execute_api(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        llm_client = self._create_llm_client(config)
        prompt = self._render_prompt(input_data, config)
        response = llm_client._call_llm(  # noqa: SLF001 - legacy compatibility
            prompt,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        content = response.get("content", "")
        quality_flags = response.get("quality_flags", [])
        if response.get("needs_review") and "empty_content" in quality_flags:
            raise RuntimeError("LLM backend returned empty content")
        parsed = self.parse_api_response(content, input_data, config)
        if isinstance(parsed, dict):
            parsed.setdefault("raw_response", content)
        return parsed

    def execute_script(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        raise NotImplementedError

    def get_supported_backends(self, executor: "UnifiedTaskExecutor") -> List[BackendOption]:
        options: List[BackendOption] = []
        if self.supports_script:
            options.append(
                BackendOption(
                    name="script",
                    kind="script",
                    label="Rule-based Script",
                    description="Local deterministic fallback implementation.",
                    available=True,
                )
            )
        if self.supports_api:
            options.append(
                BackendOption(
                    name="llm_api",
                    kind="api",
                    label="Remote LLM API",
                    description="Uses configured remote LLM providers from secrets.",
                    available=executor.has_remote_provider(),
                    metadata={"providers": executor.get_available_providers(include_status=True)},
                )
            )
        if self.supports_local_llm:
            options.append(
                BackendOption(
                    name="local_llm",
                    kind="local",
                    label="Local LLM",
                    description="Uses a local model endpoint such as Ollama.",
                    available=True,
                    metadata={"default_provider": "ollama"},
                )
            )
        for registration in executor.list_external_backends(self.task_type):
            options.append(registration.to_option())
        return options

    def execute_backend(
        self,
        backend_name: str,
        input_data: Dict[str, Any],
        config: TaskConfig,
        executor: "UnifiedTaskExecutor",
    ) -> Any:
        normalized = (backend_name or "").strip().lower()
        if normalized == "script":
            return self.execute_script(input_data, config)
        if normalized in {"api", "llm_api"}:
            return self.execute_api(input_data, config)
        if normalized == "local_llm":
            local_provider = config.extra_params.get("local_provider", "ollama")
            local_model = config.extra_params.get("local_model") or config.model or "llama3.1"
            local_base_url = config.extra_params.get("local_base_url") or "http://localhost:11434"
            local_config = replace(
                config,
                provider=local_provider,
                model=local_model,
                extra_params={**config.extra_params, "base_url": local_base_url},
            )
            return self.execute_api(input_data, local_config)

        registration = executor.get_external_backend(self.task_type, normalized)
        if registration is None:
            raise ValueError(f"Unsupported backend '{backend_name}' for task '{self.task_type.value}'.")
        if not registration.is_available():
            raise RuntimeError(f"Backend '{backend_name}' is registered but not currently available.")
        return registration.handler(dict(input_data), config)

    def _render_prompt(self, input_data: Dict[str, Any], config: TaskConfig) -> str:
        prompt = config.custom_prompt or self.build_prompt(input_data, config)
        return _safe_format(prompt, input_data)

    def _create_llm_client(self, config: TaskConfig):
        from modules.llm_client import create_llm_client

        provider = _normalize_provider(config.provider)
        if provider == "ollama":
            llm_config = {
                "provider": "ollama",
                "model": config.model or "llama3.1",
                "base_url": config.extra_params.get("base_url") or "http://localhost:11434",
                "api_key": config.extra_params.get("api_key"),
            }
            return create_llm_client(llm_config)

        llm_config = self.key_manager.create_provider_config(provider)
        llm_config["provider"] = provider
        if config.model:
            llm_config["model"] = config.model
        if config.extra_params.get("base_url"):
            llm_config["base_url"] = config.extra_params["base_url"]
        if config.extra_params.get("api_key"):
            llm_config["api_key"] = config.extra_params["api_key"]
        return create_llm_client(llm_config)


class NERHandler(BaseTaskHandler):
    task_type = TaskType.NER
    display_name = "Named Entity Recognition"
    description = "Recognize historical people, places, organizations, events, and dates."

    PERSON_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,4}(?:天皇|将军|公|侯|氏|子)?")
    DATE_PATTERNS = [
        re.compile(r"\d{3,4}年(?:\d{1,2}月(?:\d{1,2}日)?)?"),
        re.compile(r"(?:明治|大正|昭和|平成|令和)\d{1,2}年"),
    ]
    LOCATION_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,6}(?:国|都|道|府|县|縣|市|村|町)")

    def get_required_params(self) -> List[str]:
        return ["text"]

    def build_prompt(self, input_data: Dict[str, Any], config: TaskConfig) -> str:
        categories = input_data.get("categories") or [
            "person",
            "location",
            "organization",
            "event",
            "date",
            "work",
            "concept",
        ]
        return (
            "Identify historical named entities in the text.\n"
            "Allowed categories: {categories}\n"
            "Return JSON only with shape: "
            '{"entities":[{"text":"...","category":"...","position":0,"confidence":0.0}]}\n'
            "Text:\n{text}"
        ).replace("{categories}", ", ".join(categories))

    def parse_api_response(
        self,
        content: str,
        input_data: Dict[str, Any],
        config: TaskConfig,
    ) -> Any:
        try:
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                parsed = json.loads(match.group())
                parsed.setdefault("entities", [])
                return parsed
        except json.JSONDecodeError:
            pass
        return {"entities": [], "raw_response": content}

    def execute_script(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        text = input_data.get("text", "")
        categories = set(input_data.get("categories") or ["person", "location", "date"])
        entities: List[Dict[str, Any]] = []

        if "person" in categories:
            for match in self.PERSON_PATTERN.finditer(text):
                entities.append(
                    {
                        "text": match.group(),
                        "category": "person",
                        "position": match.start(),
                        "confidence": 0.45,
                    }
                )
        if "location" in categories:
            for match in self.LOCATION_PATTERN.finditer(text):
                entities.append(
                    {
                        "text": match.group(),
                        "category": "location",
                        "position": match.start(),
                        "confidence": 0.4,
                    }
                )
        if "date" in categories:
            for pattern in self.DATE_PATTERNS:
                for match in pattern.finditer(text):
                    entities.append(
                        {
                            "text": match.group(),
                            "category": "date",
                            "position": match.start(),
                            "confidence": 0.7,
                        }
                    )

        deduped: List[Dict[str, Any]] = []
        seen = set()
        for entity in entities:
            key = (entity["text"], entity["category"], entity["position"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entity)
        return {"entities": deduped}


class AcademicNoteHandler(BaseTaskHandler):
    task_type = TaskType.ACADEMIC_NOTE
    display_name = "Academic Notes"
    description = "Convert source text into structured academic notes."

    def get_required_params(self) -> List[str]:
        return ["text"]

    def build_prompt(self, input_data: Dict[str, Any], config: TaskConfig) -> str:
        return (
            "Turn the source into a structured academic note in Markdown.\n"
            "Include sections: Title, Summary, Key Arguments, Entities, Open Questions.\n"
            "Source: {source}\n"
            "Text:\n{text}"
        )

    def execute_script(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        text = input_data.get("text", "").strip()
        source = input_data.get("source", "unknown")
        sentences = [part.strip() for part in re.split(r"[。！？!?]\s*|\n+", text) if part.strip()]
        summary = " ".join(sentences[:2])[:280]
        entities = NERHandler(self.key_manager).execute_script({"text": text}, config).get("entities", [])
        note = [
            "---",
            "type: reading_note",
            f"created: {datetime.now().strftime('%Y-%m-%d')}",
            f"source: {source}",
            "---",
            "",
            "# Summary",
            summary or text[:280],
            "",
            "## Key Arguments",
        ]
        for sentence in sentences[:5]:
            note.append(f"- {sentence}")
        note.extend(["", "## Entities"])
        for entity in entities[:10]:
            note.append(f"- {entity['text']} ({entity['category']})")
        note.extend(["", "## Excerpt", f"> {text[:300]}"])
        return {
            "note_content": "\n".join(note),
            "source": source,
            "entities": entities,
        }


class PaperPolishHandler(BaseTaskHandler):
    task_type = TaskType.PAPER_POLISH
    display_name = "Paper Polish"
    description = "Polish academic prose while keeping arguments stable."

    def get_required_params(self) -> List[str]:
        return ["text"]

    def build_prompt(self, input_data: Dict[str, Any], config: TaskConfig) -> str:
        language = input_data.get("language", "zh")
        return (
            "Polish the academic writing conservatively.\n"
            "Keep claims, evidence, and citations unchanged.\n"
            f"Target language: {language}\n"
            "Return JSON with keys polished_text and revision_notes.\n"
            "Text:\n{text}"
        )

    def parse_api_response(
        self,
        content: str,
        input_data: Dict[str, Any],
        config: TaskConfig,
    ) -> Any:
        try:
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                parsed = json.loads(match.group())
                parsed.setdefault("polished_text", input_data.get("text", ""))
                return parsed
        except json.JSONDecodeError:
            pass
        return {"polished_text": content or input_data.get("text", ""), "revision_notes": []}

    def execute_script(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        text = input_data.get("text", "")
        polished = re.sub(r"\s+", " ", text).strip()
        polished = polished.replace("非常非常", "非常").replace("基本上基本", "基本")
        notes = []
        if polished != text:
            notes.append("Collapsed repeated wording and normalized whitespace.")
        return {"polished_text": polished, "revision_notes": notes}


class CitationNormalizeHandler(BaseTaskHandler):
    task_type = TaskType.CITATION_NORMALIZE
    display_name = "Citation Normalize"
    description = "Normalize citations into a target style."

    def get_required_params(self) -> List[str]:
        return ["citation"]

    def build_prompt(self, input_data: Dict[str, Any], config: TaskConfig) -> str:
        target_style = input_data.get("target_style", "gb7714")
        return (
            "Normalize the citation to the requested style.\n"
            f"Target style: {target_style}\n"
            "Return JSON with normalized_citation and notes.\n"
            "Citation:\n{citation}"
        )

    def execute_script(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        citation = re.sub(r"\s+", " ", input_data.get("citation", "")).strip(" .,;")
        target_style = input_data.get("target_style", "gb7714")
        normalized = citation
        if target_style.lower() == "gb7714" and citation and not citation.endswith("."):
            normalized = citation + "."
        return {
            "normalized_citation": normalized,
            "target_style": target_style,
            "notes": [],
            "confidence": 0.55 if normalized else 0.0,
            "needs_review": not bool(normalized),
        }


class OCRCorrectionHandler(BaseTaskHandler):
    task_type = TaskType.OCR_CORRECTION
    display_name = "OCR Correction"
    description = "Correct common OCR noise in extracted text."

    def get_required_params(self) -> List[str]:
        return ["text"]

    def build_prompt(self, input_data: Dict[str, Any], config: TaskConfig) -> str:
        language = input_data.get("language", "zh")
        return (
            "Correct OCR mistakes conservatively.\n"
            f"Language: {language}\n"
            "Return JSON with corrected_text and notes.\n"
            "OCR text:\n{text}"
        )

    def execute_script(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        text = input_data.get("text", "")
        replacements = {
            " ,": ",",
            " .": ".",
            " , ": ", ",
            " . ": ". ",
            "  ": " ",
            "— ": "—",
            "「 ": "「",
            " 」": "」",
        }
        corrected = text
        for old, new in replacements.items():
            corrected = corrected.replace(old, new)
        return {"corrected_text": corrected.strip(), "notes": ["Applied lightweight OCR cleanup rules."]}


class TextSummaryHandler(BaseTaskHandler):
    task_type = TaskType.TEXT_SUMMARY
    display_name = "Text Summary"
    description = "Summarize a passage."

    def get_required_params(self) -> List[str]:
        return ["text"]

    def build_prompt(self, input_data: Dict[str, Any], config: TaskConfig) -> str:
        max_length = input_data.get("max_length", 200)
        return (
            "Summarize the text.\n"
            f"Maximum length: {max_length} characters.\n"
            "Return JSON with summary and bullet_points.\n"
            "Text:\n{text}"
        )

    def execute_script(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        text = input_data.get("text", "").strip()
        max_length = int(input_data.get("max_length", 200))
        sentences = [part.strip() for part in re.split(r"[。！？!?]\s*|\n+", text) if part.strip()]
        summary = " ".join(sentences[:2]) or text
        return {
            "summary": summary[:max_length],
            "bullet_points": sentences[:3],
        }


class ReverseOutlineHandler(BaseTaskHandler):
    task_type = TaskType.REVERSE_OUTLINE
    display_name = "Reverse Outline"
    description = "Review draft structure, logic gaps, and section balance."

    SECTION_PATTERNS: Dict[str, str] = {
        "abstract": r"^(abstract|摘要)$",
        "introduction": r"^(introduction|导论|引言|前言|序章)$",
        "literature_review": r"^(literature review|研究回顾|文献综述)$",
        "methodology": r"^(methodology|research method|研究方法|方法)$",
        "analysis": r"^(analysis|正文|分析)$",
        "discussion": r"^(discussion|讨论)$",
        "conclusion": r"^(conclusion|结论|结语)$",
        "references": r"^(references|参考文献)$",
    }

    def get_required_params(self) -> List[str]:
        return ["text"]

    def build_prompt(self, input_data: Dict[str, Any], config: TaskConfig) -> str:
        language = input_data.get("language", "zh")
        return (
            "Review the draft with a reverse-outline lens.\n"
            f"Language: {language}\n"
            "Return JSON with section_word_counts, section_ratios, logical_gaps, "
            "deviation_flags, suggestions, confidence, and needs_review.\n"
            "Draft:\n{text}"
        )

    def parse_api_response(
        self,
        content: str,
        input_data: Dict[str, Any],
        config: TaskConfig,
    ) -> Any:
        try:
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                parsed = json.loads(match.group())
                parsed.setdefault("section_word_counts", {})
                parsed.setdefault("section_ratios", {})
                parsed.setdefault("logical_gaps", [])
                parsed.setdefault("deviation_flags", [])
                parsed.setdefault("suggestions", [])
                parsed.setdefault("confidence", 0.65)
                parsed.setdefault("needs_review", bool(parsed.get("logical_gaps") or parsed.get("deviation_flags")))
                return parsed
        except json.JSONDecodeError:
            pass
        return self.execute_script(input_data, config)

    def execute_script(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        text = input_data.get("text", "")
        section_word_counts, ordered_sections = self._extract_sections(text)
        total = sum(section_word_counts.values()) or max(len(text), 1)
        section_ratios = {
            section: round(count / total, 3)
            for section, count in section_word_counts.items()
        }
        logical_gaps = self._detect_logical_gaps(section_word_counts)
        deviation_flags = self._detect_deviation_flags(section_ratios, total)
        suggestions = self._build_suggestions(logical_gaps, deviation_flags, ordered_sections)
        confidence = 0.55
        if ordered_sections:
            confidence += 0.15
        if "introduction" in section_word_counts and "conclusion" in section_word_counts:
            confidence += 0.1
        confidence = min(confidence, 0.9)
        return {
            "section_word_counts": section_word_counts,
            "section_ratios": section_ratios,
            "logical_gaps": logical_gaps,
            "deviation_flags": deviation_flags,
            "suggestions": suggestions,
            "confidence": round(confidence, 2),
            "needs_review": bool(logical_gaps or deviation_flags),
        }

    def _extract_sections(self, text: str) -> Tuple[Dict[str, int], List[str]]:
        lines = text.splitlines()
        sections: List[Tuple[str, int]] = []
        for index, raw_line in enumerate(lines):
            line = raw_line.strip().strip("#").strip()
            if not line or len(line) > 80:
                continue
            normalized = re.sub(r"^[0-9一二三四五六七八九十IVXivx.、\-\s]+", "", line).lower()
            for section_name, pattern in self.SECTION_PATTERNS.items():
                if re.match(pattern, normalized, re.IGNORECASE):
                    sections.append((section_name, index))
                    break

        section_word_counts: Dict[str, int] = {}
        ordered_sections: List[str] = []
        if sections:
            for offset, (section_name, start_index) in enumerate(sections):
                end_index = sections[offset + 1][1] if offset + 1 < len(sections) else len(lines)
                body = "\n".join(lines[start_index + 1 : end_index]).strip()
                section_word_counts[section_name] = len(body.replace(" ", ""))
                ordered_sections.append(section_name)
            return section_word_counts, ordered_sections

        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        if not paragraphs:
            return {}, []
        total_paragraphs = len(paragraphs)
        buckets = {
            "introduction": paragraphs[: max(1, total_paragraphs // 4)],
            "analysis": paragraphs[max(1, total_paragraphs // 4) : max(2, total_paragraphs - 1)],
            "conclusion": paragraphs[max(1, total_paragraphs - 1) :],
        }
        for section_name, parts in buckets.items():
            body = "\n\n".join(parts).strip()
            if body:
                section_word_counts[section_name] = len(body.replace(" ", ""))
                ordered_sections.append(section_name)
        return section_word_counts, ordered_sections

    def _detect_logical_gaps(self, section_word_counts: Dict[str, int]) -> List[str]:
        gaps: List[str] = []
        if not section_word_counts:
            return ["unable to detect section structure"]
        for required in ("introduction", "analysis", "conclusion"):
            if required not in section_word_counts:
                gaps.append(f"missing {required}")
        return gaps

    def _detect_deviation_flags(self, section_ratios: Dict[str, float], total_length: int) -> List[str]:
        flags: List[str] = []
        if total_length < 1200:
            flags.append("draft may be too short for stable outline review")
        for section, ratio in section_ratios.items():
            if section == "references":
                continue
            if ratio < 0.05:
                flags.append(f"{section} is too short ({ratio:.1%})")
            elif ratio > 0.6:
                flags.append(f"{section} is too long ({ratio:.1%})")
        return flags

    def _build_suggestions(
        self,
        logical_gaps: List[str],
        deviation_flags: List[str],
        ordered_sections: List[str],
    ) -> List[str]:
        suggestions: List[str] = []
        if logical_gaps:
            suggestions.append("Add missing structural sections before final polishing.")
        if deviation_flags:
            suggestions.append("Rebalance section lengths and tighten the most dominant section.")
        if ordered_sections and ordered_sections[:1] != ["introduction"]:
            suggestions.append("Ensure the draft opens with a clear introduction or research framing section.")
        if not suggestions:
            suggestions.append("Structure looks broadly stable; continue with argument-level revision.")
        return suggestions


class EntityDisambiguationHandler(BaseTaskHandler):
    task_type = TaskType.ENTITY_DISAMBIGUATION
    display_name = "Entity Disambiguation"
    description = "Choose the most likely entity candidate using context."

    def get_required_params(self) -> List[str]:
        return ["entity", "context"]

    def build_prompt(self, input_data: Dict[str, Any], config: TaskConfig) -> str:
        candidates = input_data.get("candidates") or []
        return (
            "Resolve the entity using the context.\n"
            f"Candidates: {json.dumps(candidates, ensure_ascii=False)}\n"
            "Return JSON with resolved_entity, confidence, and explanation.\n"
            "Entity: {entity}\n"
            "Context:\n{context}"
        )

    def execute_script(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        entity = input_data.get("entity", "")
        context = input_data.get("context", "")
        candidates = input_data.get("candidates") or []
        resolved = entity
        confidence = 0.35
        explanation = "No candidate list was provided."
        if candidates:
            resolved = candidates[0]
            explanation = "Defaulted to the first candidate because no stronger signal was found."
            confidence = 0.4
            for candidate in candidates:
                if candidate in context:
                    resolved = candidate
                    confidence = 0.75
                    explanation = "Selected the candidate explicitly mentioned in the context."
                    break
        return {
            "resolved_entity": resolved,
            "confidence": confidence,
            "explanation": explanation,
        }


class StyleTransferHandler(BaseTaskHandler):
    task_type = TaskType.STYLE_TRANSFER
    display_name = "Style Transfer"
    description = "Rewrite text toward a target style conservatively."

    def get_required_params(self) -> List[str]:
        return ["text", "target_style"]

    def build_prompt(self, input_data: Dict[str, Any], config: TaskConfig) -> str:
        return (
            "Analyze the source style and rewrite it conservatively.\n"
            "Return JSON with style_analysis and rewritten_text.\n"
            "Target style: {target_style}\n"
            "Text:\n{text}"
        )

    def parse_api_response(
        self,
        content: str,
        input_data: Dict[str, Any],
        config: TaskConfig,
    ) -> Any:
        try:
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                parsed = json.loads(match.group())
                parsed.setdefault("style_analysis", {"target_style": input_data.get("target_style", "academic")})
                parsed.setdefault("rewritten_text", input_data.get("text", ""))
                parsed.setdefault("confidence", 0.65)
                parsed.setdefault("needs_review", False)
                return parsed
        except json.JSONDecodeError:
            pass
        return {
            "style_analysis": {"target_style": input_data.get("target_style", "academic")},
            "rewritten_text": content or input_data.get("text", ""),
            "confidence": 0.55,
            "needs_review": False,
        }

    def execute_script(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        text = input_data.get("text", "")
        target_style = input_data.get("target_style", "academic")
        rewritten = re.sub(r"\s+", " ", text).strip()
        return {
            "style_analysis": {
                "tone": "neutral",
                "target_style": target_style,
            },
            "rewritten_text": rewritten,
            "confidence": 0.55 if rewritten else 0.0,
            "needs_review": False,
        }


class VirtualPersonaHandler(BaseTaskHandler):
    task_type = TaskType.VIRTUAL_PERSONA
    display_name = "Virtual Persona"
    description = "Limited persona-based research dialogue."

    def get_required_params(self) -> List[str]:
        return ["message", "persona"]

    def build_prompt(self, input_data: Dict[str, Any], config: TaskConfig) -> str:
        history = input_data.get("history") or []
        history_blob = json.dumps(history, ensure_ascii=False)
        return (
            "Reply in character while staying grounded in verifiable information.\n"
            "Persona: {persona}\n"
            f"History: {history_blob}\n"
            "Return JSON with reply and safety_notes.\n"
            "User message:\n{message}"
        )

    def execute_script(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        persona = input_data.get("persona", "research assistant")
        message = input_data.get("message", "")
        return {
            "reply": f"[{persona}] {message}",
            "safety_notes": ["Script backend does not fabricate citations or facts."],
        }


class UnifiedTaskExecutor:
    def __init__(self, default_mode: str = "api"):
        self.key_manager = get_secure_key_manager()
        self.mode = ExecutionMode.AUTO
        self.provider = "qwen"
        self.cache_enabled = True
        self._cache: Dict[str, TaskResult] = {}
        self._handlers: Dict[TaskType, BaseTaskHandler] = {}
        self._execution_history: List[TaskResult] = []
        self._external_backends: Dict[Tuple[TaskType, str], ExternalBackendRegistration] = {}
        self._register_handlers()
        self.set_mode(default_mode)

    def _register_handlers(self) -> None:
        handlers: Sequence[BaseTaskHandler] = (
            NERHandler(self.key_manager),
            AcademicNoteHandler(self.key_manager),
            PaperPolishHandler(self.key_manager),
            CitationNormalizeHandler(self.key_manager),
            OCRCorrectionHandler(self.key_manager),
            TextSummaryHandler(self.key_manager),
            ReverseOutlineHandler(self.key_manager),
            EntityDisambiguationHandler(self.key_manager),
            StyleTransferHandler(self.key_manager),
            VirtualPersonaHandler(self.key_manager),
        )
        for handler in handlers:
            self._handlers[handler.task_type] = handler

    def set_mode(self, mode: str) -> None:
        self.mode = ExecutionMode((mode or "auto").strip().lower())

    def get_mode(self) -> str:
        return self.mode.value

    def set_provider(self, provider: str) -> None:
        self.provider = provider

    def enable_cache(self, enabled: bool) -> None:
        self.cache_enabled = bool(enabled)

    def clear_cache(self) -> None:
        self._cache.clear()

    def register_backend(
        self,
        task_type: Union[TaskType, str],
        name: str,
        handler: Callable[[Dict[str, Any], TaskConfig], Any],
        *,
        kind: str = "custom",
        label: Optional[str] = None,
        description: str = "",
        availability_checker: Optional[Callable[[], bool]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        normalized_task = _normalize_task_type(task_type)
        normalized_name = name.strip().lower()
        self._external_backends[(normalized_task, normalized_name)] = ExternalBackendRegistration(
            task_type=normalized_task,
            name=normalized_name,
            kind=kind,
            label=label or normalized_name,
            handler=handler,
            description=description,
            availability_checker=availability_checker,
            metadata=metadata or {},
        )

    def list_external_backends(
        self,
        task_type: Union[TaskType, str],
    ) -> List[ExternalBackendRegistration]:
        normalized_task = _normalize_task_type(task_type)
        return [
            registration
            for (registered_task, _), registration in self._external_backends.items()
            if registered_task == normalized_task
        ]

    def get_external_backend(
        self,
        task_type: Union[TaskType, str],
        name: str,
    ) -> Optional[ExternalBackendRegistration]:
        normalized_task = _normalize_task_type(task_type)
        return self._external_backends.get((normalized_task, name.strip().lower()))

    def has_remote_provider(self, provider: Optional[str] = None) -> bool:
        statuses = self.get_available_providers(include_status=True)
        if provider:
            normalized = _normalize_provider(provider)
            for item in statuses:
                if _normalize_provider(item["name"]) == normalized:
                    return bool(item["configured"])
            return False
        return any(item["configured"] for item in statuses if item["kind"] == "remote")

    def get_available_providers(self, include_status: bool = False) -> List[Any]:
        report = self.key_manager.get_status_report()
        services = report.get("services", {})
        providers = [
            {
                "name": name,
                "label": label,
                "kind": "remote",
                "configured": bool(services.get(name, {}).get("has_key")),
            }
            for name, label in REMOTE_PROVIDER_LABELS
        ]
        providers.append(
            {
                "name": "ollama",
                "label": "Local LLM / Ollama",
                "kind": "local",
                "configured": True,
            }
        )
        if include_status:
            return providers
        return [item["name"] for item in providers]

    def get_task_capability(self, task_type: Union[TaskType, str]) -> Dict[str, Any]:
        normalized = _normalize_task_type(task_type)
        handler = self._handlers[normalized]
        return {
            "task_type": normalized.value,
            "label": handler.display_name,
            "description": handler.description,
            "required_params": handler.get_required_params(),
            "backends": [item.to_dict() for item in handler.get_supported_backends(self)],
            "providers": self.get_available_providers(include_status=True),
        }

    def get_all_task_capabilities(self) -> Dict[str, Dict[str, Any]]:
        return {
            task_type.value: self.get_task_capability(task_type)
            for task_type in self._handlers
        }

    def _validate_output_data(self, data: Any, *, success: bool, error: Optional[str] = None) -> Dict[str, Any]:
        quality_flags: List[str] = []
        confidence = 1.0 if success else 0.0
        needs_review = not success

        if error:
            quality_flags.append("execution_error")
        if data is None:
            quality_flags.append("empty_output")
            needs_review = True
            confidence = 0.0
        elif isinstance(data, str):
            if not data.strip():
                quality_flags.append("empty_output")
                needs_review = True
                confidence = min(confidence, 0.2)
        elif isinstance(data, (list, tuple, set)):
            if not data:
                quality_flags.append("empty_output")
                needs_review = True
                confidence = min(confidence, 0.4)
        elif isinstance(data, dict):
            if not data:
                quality_flags.append("empty_output")
                needs_review = True
                confidence = min(confidence, 0.4)
            if "confidence" in data:
                try:
                    confidence = float(data.get("confidence") or 0.0)
                except (TypeError, ValueError):
                    quality_flags.append("invalid_confidence")
                    confidence = 0.0
                    needs_review = True
            needs_review = bool(data.get("needs_review", needs_review))
            data_flags = data.get("quality_flags", [])
            if isinstance(data_flags, str):
                quality_flags.append(data_flags)
            elif isinstance(data_flags, (list, tuple, set)):
                quality_flags.extend(str(item) for item in data_flags if item)

        return {
            "status": "passed" if success and not quality_flags else "needs_review",
            "confidence": max(0.0, min(1.0, confidence)),
            "needs_review": bool(needs_review or quality_flags),
            "quality_flags": sorted(set(quality_flags)),
        }

    def write_execution_artifact(self, package: Dict[str, Any], output_path: Union[str, Path]) -> Dict[str, Any]:
        path = Path(output_path)
        resolved = path.resolve()
        if "secrets" in {part.lower() for part in resolved.parts}:
            raise ValueError("Refusing to write task execution artifact under secrets/")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(package, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return {
            "type": "task_execution_json",
            "path": str(path),
            "format": "json",
            "written": True,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

    def _resolve_config(
        self,
        task_type: Union[TaskType, str],
        config: Optional[TaskConfig],
    ) -> TaskConfig:
        normalized_task = _normalize_task_type(task_type)
        if config is None:
            return TaskConfig(task_type=normalized_task, provider=self.provider)
        resolved = replace(config, task_type=normalized_task)
        if not resolved.provider:
            resolved.provider = self.provider
        return resolved

    def _get_cache_key(
        self,
        task_type: TaskType,
        input_data: Dict[str, Any],
        config: TaskConfig,
    ) -> str:
        payload = {
            "task_type": task_type.value,
            "mode": self.mode.value,
            "provider": config.provider,
            "model": config.model,
            "backend": config.backend,
            "fallback_backends": config.fallback_backends,
            "custom_prompt": config.custom_prompt,
            "input_data": input_data,
        }
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _resolve_backend_chain(self, config: TaskConfig) -> List[str]:
        if config.backend:
            primary = config.backend.strip().lower()
        elif self.mode == ExecutionMode.SCRIPT:
            primary = "script"
        elif self.mode == ExecutionMode.API:
            primary = "llm_api"
        else:
            primary = "llm_api" if self.has_remote_provider(config.provider) else "local_llm"

        chain = [primary]
        for backend in config.fallback_backends:
            normalized = (backend or "").strip().lower()
            if normalized and normalized not in chain:
                chain.append(normalized)

        if self.mode == ExecutionMode.AUTO:
            auto_fallbacks = {
                "llm_api": ["local_llm", "script"],
                "local_llm": ["script"],
                "skill": ["llm_api", "local_llm", "script"],
                "mcp": ["llm_api", "local_llm", "script"],
            }
            for backend in auto_fallbacks.get(primary, []):
                if backend not in chain:
                    chain.append(backend)
        return chain

    def execute(
        self,
        task_type: Union[TaskType, str],
        config: Optional[TaskConfig] = None,
        **input_data: Any,
    ) -> TaskResult:
        resolved_config = self._resolve_config(task_type, config)
        handler = self._handlers[resolved_config.task_type]
        missing = [name for name in handler.get_required_params() if not input_data.get(name)]
        if missing:
            error = f"Missing required params: {', '.join(missing)}"
            return TaskResult(
                success=False,
                data=None,
                mode=self.mode.value,
                task_type=resolved_config.task_type.value,
                execution_time=0.0,
                error=error,
                metadata={
                    "missing_params": missing,
                    "validation": self._validate_output_data(None, success=False, error=error),
                },
            )

        cache_key = self._get_cache_key(resolved_config.task_type, input_data, resolved_config)
        if self.cache_enabled and resolved_config.cache_enabled and cache_key in self._cache:
            cached = self._cache[cache_key]
            replayed = replace(
                cached,
                metadata={**cached.metadata, "cache_hit": True},
            )
            self._execution_history.append(replayed)
            return replayed

        start = time.perf_counter()
        backend_errors: Dict[str, str] = {}
        backend_chain = self._resolve_backend_chain(resolved_config)

        for backend_name in backend_chain:
            try:
                data = handler.execute_backend(backend_name, input_data, resolved_config, self)
                execution_time = time.perf_counter() - start
                validation = self._validate_output_data(data, success=True)
                result = TaskResult(
                    success=True,
                    data=data,
                    mode=self.mode.value,
                    task_type=resolved_config.task_type.value,
                    execution_time=execution_time,
                    metadata={
                        "backend": backend_name,
                        "attempted_backends": backend_chain,
                        "provider": _normalize_provider(resolved_config.provider),
                        "model": resolved_config.model,
                        "cache_hit": False,
                        "timestamp": datetime.now().isoformat(),
                        "validation": validation,
                        "confidence": validation["confidence"],
                        "needs_review": validation["needs_review"],
                        "quality_flags": validation["quality_flags"],
                    },
                )
                if self.cache_enabled and resolved_config.cache_enabled:
                    self._cache[cache_key] = result
                self._execution_history.append(result)
                return result
            except Exception as exc:  # noqa: BLE001 - surface backend failures in metadata
                backend_errors[backend_name] = f"{type(exc).__name__}: {exc}"

        execution_time = time.perf_counter() - start
        result = TaskResult(
            success=False,
            data=None,
            mode=self.mode.value,
            task_type=resolved_config.task_type.value,
            execution_time=execution_time,
            error=next(reversed(backend_errors.values()), "No backend executed."),
            metadata={
                "attempted_backends": backend_chain,
                "backend_errors": backend_errors,
                "provider": _normalize_provider(resolved_config.provider),
                "model": resolved_config.model,
                "cache_hit": False,
                "timestamp": datetime.now().isoformat(),
                "validation": self._validate_output_data(
                    None,
                    success=False,
                    error=next(reversed(backend_errors.values()), "No backend executed."),
                ),
            },
        )
        self._execution_history.append(result)
        return result

    def execute_package(
        self,
        task_type: Union[TaskType, str],
        config: Optional[TaskConfig] = None,
        *,
        artifacts: Optional[List[Dict[str, Any]]] = None,
        artifact_path: Optional[Union[str, Path]] = None,
        **input_data: Any,
    ) -> Dict[str, Any]:
        result = self.execute(task_type, config=config, **input_data)
        package = result.to_package(artifacts=artifacts)
        if artifact_path:
            package["artifacts"].append(self.write_execution_artifact(package, artifact_path))
        return package

    def execute_with_prompt(
        self,
        task_type: Union[TaskType, str],
        custom_prompt: str,
        **kwargs: Any,
    ) -> TaskResult:
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
            task_type=_normalize_task_type(task_type),
            provider=config_kwargs.pop("provider", self.provider),
            model=config_kwargs.pop("model", None),
            temperature=config_kwargs.pop("temperature", 0.3),
            max_tokens=config_kwargs.pop("max_tokens", 2000),
            timeout=config_kwargs.pop("timeout", 60),
            max_retries=config_kwargs.pop("max_retries", 3),
            cache_enabled=config_kwargs.pop("cache_enabled", True),
            custom_prompt=custom_prompt,
            backend=config_kwargs.pop("backend", None),
            fallback_backends=config_kwargs.pop("fallback_backends", []),
            preferred_providers=config_kwargs.pop("preferred_providers", []),
            extra_params=config_kwargs.pop("extra_params", {}),
        )
        return self.execute(task_type, config=config, **kwargs)

    def batch_execute(
        self,
        task_type: Union[TaskType, str],
        input_list: Iterable[Dict[str, Any]],
        config: Optional[TaskConfig] = None,
    ) -> List[TaskResult]:
        return [self.execute(task_type, config=config, **item) for item in input_list]

    def get_supported_tasks(self) -> List[str]:
        return [task_type.value for task_type in self._handlers]

    def get_execution_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [result.to_dict() for result in self._execution_history[-limit:]]

    def get_statistics(self) -> Dict[str, Any]:
        if not self._execution_history:
            return {
                "total_executions": 0,
                "success_rate": 0.0,
                "average_execution_time": 0.0,
                "by_task": {},
                "by_backend": {},
                "cache_entries": len(self._cache),
                "mode": self.mode.value,
                "provider": self.provider,
            }

        total = len(self._execution_history)
        success_count = sum(1 for item in self._execution_history if item.success)
        total_time = sum(item.execution_time for item in self._execution_history)
        by_task = Counter(item.task_type for item in self._execution_history)
        by_backend = Counter(item.metadata.get("backend", "unknown") for item in self._execution_history)
        return {
            "total_executions": total,
            "success_rate": success_count / total,
            "average_execution_time": total_time / total,
            "by_task": dict(by_task),
            "by_backend": dict(by_backend),
            "cache_entries": len(self._cache),
            "mode": self.mode.value,
            "provider": self.provider,
        }


def get_task_executor() -> UnifiedTaskExecutor:
    return UnifiedTaskExecutor()
