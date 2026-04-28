import json
import os
import time
from typing import Any, Dict, List, Optional, Union

import requests

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency at runtime
    OpenAI = None

try:
    from anthropic import Anthropic
except ImportError:  # pragma: no cover - optional dependency at runtime
    Anthropic = None

from modules.secure_api_key_manager import get_secure_key_manager


class LLMClient:
    """Unified LLM client for the project's supported providers."""

    SUPPORTED_PROVIDERS = [
        "openai",
        "anthropic",
        "dashscope",
        "minimax",
        "zhipu",
        "volcano",
        "deepseek",
        "ollama",
        "custom",
    ]

    PROVIDER_ALIASES = {
        "qwen": "dashscope",
        "chatgpt": "openai",
        "claude": "anthropic",
    }

    def __init__(
        self,
        config: Optional[Union[Dict[str, Any], str]] = None,
        **kwargs: Any,
    ):
        merged = self._normalize_config(config, kwargs)
        self.config = merged
        self.provider = self._normalize_provider(merged.get("provider", "openai"))
        self.model = merged.get("model") or self._get_default_model()
        self.base_url = merged.get("base_url") or self._get_base_url()
        self.max_retries = int(merged.get("max_retries", 3))
        self.retry_delay = float(merged.get("retry_delay", 1))
        self.timeout = int(merged.get("timeout", 180))
        self.api_key = self._get_api_key(merged)
        self.client = None
        self._init_client()

    def _normalize_config(
        self,
        config: Optional[Union[Dict[str, Any], str]],
        extra: Dict[str, Any],
    ) -> Dict[str, Any]:
        if isinstance(config, str):
            merged: Dict[str, Any] = {"provider": config}
        elif isinstance(config, dict):
            merged = dict(config)
        else:
            merged = {}

        merged.update({k: v for k, v in extra.items() if v is not None})
        return merged

    def _normalize_provider(self, provider: str) -> str:
        lowered = str(provider).strip().lower()
        normalized = self.PROVIDER_ALIASES.get(lowered, lowered)
        return normalized if normalized in self.SUPPORTED_PROVIDERS else "openai"

    def _get_default_model(self) -> str:
        defaults = {
            "openai": "gpt-4",
            "anthropic": "claude-3-sonnet-20240229",
            "dashscope": "qwen-turbo",
            "minimax": "abab6-chat",
            "zhipu": "glm-4",
            "volcano": "doubao-seed-1-8-251228",
            "deepseek": "deepseek-chat",
            "ollama": os.getenv("OLLAMA_MODEL", "llama3.1"),
            "custom": "gpt-4",
        }
        return defaults.get(self.provider, "gpt-4")

    def _get_api_key(self, config: Dict[str, Any]) -> Optional[str]:
        explicit_key = config.get("api_key")
        if explicit_key:
            return explicit_key

        key_manager = get_secure_key_manager()
        provider_to_service = {
            "dashscope": "qwen",
            "minimax": "minimax",
            "openai": "openai",
            "anthropic": "anthropic",
            "deepseek": "deepseek",
            "zhipu": "zhipu",
            "volcano": "volcano",
            "ollama": "ollama",
            "custom": "custom",
        }

        service_name = provider_to_service.get(self.provider, self.provider)
        key = key_manager.get_key(service_name)
        if key:
            return key

        env_vars = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "dashscope": "DASHSCOPE_API_KEY",
            "minimax": "MINIMAX_API_KEY",
            "zhipu": "ZHIPU_API_KEY",
            "volcano": "VOLCANO_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "ollama": None,
            "custom": "LLM_API_KEY",
        }
        env_var = env_vars.get(self.provider)
        return os.getenv(env_var) if env_var else None

    def _get_base_url(self) -> Optional[str]:
        base_urls = {
            "ollama": "http://localhost:11434",
            "deepseek": "https://api.deepseek.com",
            "zhipu": "https://open.bigmodel.cn/api/paas/v4",
            "custom": os.getenv("LLM_BASE_URL"),
        }
        return self.config.get("base_url") or base_urls.get(self.provider)

    def _init_client(self):
        if self.provider == "anthropic":
            if Anthropic is None:
                return
            self.client = Anthropic(api_key=self.api_key)
            return

        openai_like_providers = {"openai", "deepseek", "zhipu", "ollama", "custom"}
        if self.provider in openai_like_providers:
            if OpenAI is None:
                return
            if self.provider == "ollama":
                self.client = OpenAI(
                    api_key=self.api_key or "ollama",
                    base_url=self._ollama_openai_base_url(),
                )
            else:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def academic_polish(self, text: str, language: str = "zh") -> Dict[str, Any]:
        prompts = {
            "zh": (
                "你是一位专业的历史学论文编辑，请对下文进行学术化润色。"
                "修正语法错误，压缩冗余表达，保持原意和历史专名。"
                "只输出润色后的正文。"
            ),
            "ja": (
                "あなたは歴史学の学術論文編集者です。以下の文章を学術的に校訂し、"
                "冗長さを減らし、原意と固有名詞を保ってください。"
                "校訂後の本文のみを出力してください。"
            ),
            "en": (
                "You are an academic editor specializing in history. "
                "Polish the text, remove redundancy, keep the original meaning, "
                "and preserve historical terms. Output only the revised text."
            ),
        }
        prompt = prompts.get(language, prompts["zh"])
        return self._call_llm(f"{prompt}\n\n{text}")

    def remove_redundancy(self, text: str) -> str:
        prompt = (
            "你是一位专业的学术编辑，请删除下文中的重复表达、空洞填充和与主题无关的内容，"
            "保持信息完整，只输出处理后的正文。"
        )
        result = self._call_llm(f"{prompt}\n\n{text}")
        return result.get("content", text)

    def ocr_correction(self, ocr_text: str, language: str = "zh") -> str:
        prompts = {
            "zh": "请校正以下 OCR 文本中的错别字、漏字、冗余字符和格式错误，只输出校正后的文本。",
            "ja": "以下の OCR テキストの誤字、脱字、余分な文字、書式エラーを補正し、補正後の本文のみを出力してください。",
            "en": "Correct OCR mistakes in the text below and output only the corrected text.",
        }
        prompt = prompts.get(language, prompts["zh"])
        result = self._call_llm(f"{prompt}\n\n{ocr_text}")
        return result.get("content", ocr_text)

    def text_to_structure(self, text: str, structure_type: str = "general") -> Dict[str, Any]:
        prompts = {
            "general": "请将以下文本整理成 JSON 结构化数据，保留层级关系。",
            "table": "请从以下文本中提取表格信息，并输出 JSON 数组。",
            "key_value": "请从以下文本中提取键值对，并输出 JSON 对象。",
            "timeline": "请提取时间线信息，并输出包含时间和事件的 JSON 数组。",
        }
        prompt = prompts.get(structure_type, prompts["general"])
        result = self._call_llm(f"{prompt}\n\n{text}")
        return {"structured_data": result.get("content", ""), "format": structure_type}

    def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        if not messages:
            return {"content": "", "usage": {}, "error": "messages is empty"}

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                if self.provider == "anthropic":
                    return self._chat_anthropic(messages, **kwargs)
                if self.provider == "dashscope":
                    return self._chat_dashscope(messages, **kwargs)
                if self.provider == "minimax":
                    return self._chat_minimax(messages, **kwargs)
                if self.provider == "volcano":
                    return self._chat_volcano(messages, **kwargs)
                if self.provider == "zhipu":
                    return self._chat_zhipu(messages, **kwargs)
                if self.provider == "ollama":
                    return self._chat_ollama(messages, **kwargs)
                if self.provider == "deepseek":
                    return self._chat_openai_compatible(messages, **kwargs)
                return self._chat_openai_compatible(messages, **kwargs)
            except Exception as exc:  # pragma: no cover - network/provider failures
                last_error = exc
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))

        return {"content": "", "usage": {}, "error": str(last_error) if last_error else "unknown"}

    def _call_llm(self, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def _chat_openai_compatible(self, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        if self.client is None:
            raise RuntimeError(f"{self.provider} client is unavailable")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 4000),
        )
        usage = getattr(response, "usage", None)
        return {
            "content": response.choices[0].message.content,
            "usage": {
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            },
            "provider": self.provider,
            "model": self.model,
        }

    def _chat_anthropic(self, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        if self.client is None:
            raise RuntimeError("anthropic client is unavailable")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=kwargs.get("max_tokens", 4000),
            temperature=kwargs.get("temperature", 0.7),
            messages=messages,
        )
        return {
            "content": response.content[0].text,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            "provider": self.provider,
            "model": self.model,
        }

    def _chat_dashscope(self, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        prompt = self._messages_to_prompt(messages)
        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": {"prompt": prompt},
            "parameters": {
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 2000),
            },
        }
        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        result = response.json()
        return {
            "content": result.get("output", {}).get("text", ""),
            "usage": result.get("usage", {}),
            "provider": self.provider,
            "model": self.model,
        }

    def _chat_minimax(self, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }
        group_id = os.getenv("MINIMAX_GROUP_ID", "")
        if group_id:
            payload["group_id"] = group_id

        response = requests.post(
            "https://api.minimax.chat/v1/text/chatcompletion_pro",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        result = response.json()
        content = ""
        if result.get("choices"):
            first_choice = result["choices"][0]
            if first_choice.get("messages"):
                content = first_choice["messages"][0].get("text", "")
            elif first_choice.get("message"):
                content = first_choice["message"].get("content", "")
        if not content:
            content = result.get("reply", "")
        return {
            "content": content,
            "usage": result.get("usage", {}),
            "provider": self.provider,
            "model": self.model,
        }

    def _chat_zhipu(self, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        result = response.json()
        return {
            "content": result["choices"][0]["message"]["content"],
            "usage": result.get("usage", {}),
            "provider": self.provider,
            "model": self.model,
        }

    def _chat_volcano(self, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }
        response = requests.post(
            "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        result = response.json()
        return {
            "content": result["choices"][0]["message"]["content"],
            "usage": result.get("usage", {}),
            "provider": self.provider,
            "model": self.model,
        }

    def _chat_ollama(self, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.3),
                "num_predict": kwargs.get("max_tokens", kwargs.get("num_predict", 512)),
            },
        }
        response = requests.post(
            f"{self._ollama_native_base_url()}/api/chat",
            json=payload,
            timeout=kwargs.get("timeout", max(self.timeout, 300)),
        )
        response.raise_for_status()
        result = response.json()
        content = result.get("message", {}).get("content", "")
        quality_flags = []
        if not str(content).strip():
            quality_flags.append("empty_content")
        if result.get("done_reason") in {"length", "num_predict"}:
            quality_flags.append("length_limited")
        return {
            "content": content,
            "usage": self._normalize_ollama_usage(result),
            "provider": self.provider,
            "model": self.model,
            "backend": "local_llm",
            "done_reason": result.get("done_reason"),
            "needs_review": bool(quality_flags),
            "quality_flags": quality_flags,
        }

    def _ollama_native_base_url(self) -> str:
        base_url = (self.base_url or "http://localhost:11434").rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3].rstrip("/")
        return base_url

    def _ollama_openai_base_url(self) -> str:
        return f"{self._ollama_native_base_url()}/v1"

    def _normalize_ollama_usage(self, result: Dict[str, Any]) -> Dict[str, Any]:
        usage = result.get("usage")
        if isinstance(usage, dict):
            return usage
        return {
            "prompt_tokens": result.get("prompt_eval_count"),
            "completion_tokens": result.get("eval_count"),
            "total_tokens": (
                (result.get("prompt_eval_count") or 0)
                + (result.get("eval_count") or 0)
            ) or None,
            "total_duration": result.get("total_duration"),
        }

    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        parts = []
        for item in messages:
            role = item.get("role", "user").upper()
            content = item.get("content", "")
            parts.append(f"{role}: {content}")
        return "\n\n".join(parts)

    def set_model(self, model: str):
        self.model = model

    def set_provider(self, provider: str):
        normalized = self._normalize_provider(provider)
        if normalized in self.SUPPORTED_PROVIDERS:
            self.provider = normalized
            self.model = self._get_default_model()
            self.api_key = self._get_api_key(self.config)
            self.base_url = self._get_base_url()
            self._init_client()

    def get_provider_info(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "has_api_key": bool(self.api_key),
            "base_url": self.base_url,
        }

    def get_capabilities(self) -> Dict[str, Any]:
        """Return a small, agent-friendly provider capability snapshot."""
        is_ollama = self.provider == "ollama"
        return {
            "type": "llm_provider",
            "schema_version": "2026-04-25",
            "provider": self.provider,
            "model": self.model,
            "backend": "local_llm" if is_ollama else "llm_api",
            "base_url": self._ollama_native_base_url() if is_ollama else self.base_url,
            "api_key_required": not is_ollama,
            "supports_chat": True,
            "small_model_friendly": is_ollama,
            "recommended_smoke": {
                "max_tokens": 64,
                "temperature": 0.1,
                "prompt": "Say OK only.",
            },
            "quality_flags": [] if (is_ollama or self.api_key) else ["missing_api_key"],
        }


def create_llm_client(config: Optional[Union[Dict[str, Any], str]] = None, **kwargs: Any) -> LLMClient:
    return LLMClient(config, **kwargs)
