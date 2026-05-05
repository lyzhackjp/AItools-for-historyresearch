from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional


CONFIG_PATH = Path(__file__).with_name("local_llm_profiles.json")
DEFAULT_PROFILE_NAME = "m5_pro_48gb_history_research"

ROLE_ENV_OVERRIDES = {
    "chat_primary": ("LOCAL_LLM_PRIMARY_MODEL", "MLX_MODEL", "OLLAMA_MODEL"),
    "reasoning_multimodal": ("LOCAL_LLM_REASONING_MODEL",),
    "fast_local": ("LOCAL_LLM_FAST_MODEL",),
    "embedding": ("LOCAL_LLM_EMBED_MODEL", "OLLAMA_EMBED_MODEL"),
    "embedding_alt": ("LOCAL_LLM_ALT_EMBED_MODEL",),
}

LOCAL_PROVIDERS = {"ollama", "mlx"}


@lru_cache(maxsize=4)
def load_local_llm_profiles(config_path: Optional[str] = None) -> Dict[str, Any]:
    path = Path(config_path) if config_path else CONFIG_PATH
    return json.loads(path.read_text(encoding="utf-8-sig"))


def get_local_llm_profile(profile_name: Optional[str] = None) -> Dict[str, Any]:
    payload = load_local_llm_profiles()
    selected = profile_name or os.getenv("LOCAL_LLM_PROFILE") or payload.get("default_profile") or DEFAULT_PROFILE_NAME
    profiles = payload.get("profiles", {})
    if selected not in profiles:
        selected = payload.get("default_profile") or DEFAULT_PROFILE_NAME
    return profiles[selected]


def get_local_provider(profile_name: Optional[str] = None) -> str:
    env_provider = os.getenv("LOCAL_LLM_PROVIDER") or os.getenv("LLM_PROVIDER")
    if env_provider and env_provider.strip().lower() in LOCAL_PROVIDERS:
        return env_provider.strip().lower()

    profile = get_local_llm_profile(profile_name)
    provider = str(profile.get("runtime", {}).get("provider", "ollama")).strip().lower()
    return provider if provider in LOCAL_PROVIDERS else "ollama"


def get_ollama_base_url(profile_name: Optional[str] = None) -> str:
    profile = get_local_llm_profile(profile_name)
    runtime = profile.get("runtime", {})
    generic_llm_base_url = os.getenv("LLM_BASE_URL") if os.getenv("LLM_PROVIDER", "").lower() == "ollama" else None
    return (
        os.getenv("OLLAMA_BASE_URL")
        or os.getenv("OLLAMA_HOST")
        or generic_llm_base_url
        or runtime.get("base_url")
        or "http://localhost:11434"
    ).rstrip("/")


def get_mlx_base_url(profile_name: Optional[str] = None) -> str:
    profile = get_local_llm_profile(profile_name)
    runtime = profile.get("runtime", {})
    generic_llm_base_url = os.getenv("LLM_BASE_URL") if os.getenv("LLM_PROVIDER", "").lower() == "mlx" else None
    profile_base_url = runtime.get("base_url") if str(runtime.get("provider", "")).lower() == "mlx" else None
    return (
        os.getenv("MLX_BASE_URL")
        or generic_llm_base_url
        or profile_base_url
        or "http://127.0.0.1:8080/v1"
    ).rstrip("/")


def get_local_base_url(profile_name: Optional[str] = None, provider: Optional[str] = None) -> str:
    selected_provider = (provider or get_local_provider(profile_name)).strip().lower()
    if selected_provider == "mlx":
        return get_mlx_base_url(profile_name)
    return get_ollama_base_url(profile_name)


def get_ollama_keep_alive(profile_name: Optional[str] = None) -> str:
    profile = get_local_llm_profile(profile_name)
    runtime = profile.get("runtime", {})
    return os.getenv("OLLAMA_KEEP_ALIVE") or runtime.get("keep_alive", "10m")


def get_local_model(role: str = "chat_primary", profile_name: Optional[str] = None) -> str:
    for env_var in ROLE_ENV_OVERRIDES.get(role, ()):
        value = os.getenv(env_var)
        if value:
            return value

    profile = get_local_llm_profile(profile_name)
    model_config = profile.get("models", {}).get(role) or profile.get("models", {}).get("chat_primary", {})
    return model_config.get("id") or model_config.get("base_model") or "llama3.1"


def get_local_model_options(role: str = "chat_primary", profile_name: Optional[str] = None) -> Dict[str, Any]:
    profile = get_local_llm_profile(profile_name)
    model_config = dict(profile.get("models", {}).get(role) or profile.get("models", {}).get("chat_primary", {}))
    option_keys = ("num_ctx", "temperature", "top_p", "repeat_penalty", "num_predict", "dimension")
    return {key: model_config[key] for key in option_keys if key in model_config}


def get_model_role_for_task(task_type: str, profile_name: Optional[str] = None) -> str:
    profile = get_local_llm_profile(profile_name)
    routing = profile.get("task_routing", {})
    return routing.get(task_type, routing.get("default", "chat_primary"))


def get_local_model_for_task(task_type: str, profile_name: Optional[str] = None) -> str:
    return get_local_model(get_model_role_for_task(task_type, profile_name), profile_name)


def build_ollama_llm_config(
    role: str = "chat_primary",
    profile_name: Optional[str] = None,
    **overrides: Any,
) -> Dict[str, Any]:
    options = get_local_model_options(role, profile_name)
    config: Dict[str, Any] = {
        "provider": "ollama",
        "model": get_local_model(role, profile_name),
        "base_url": get_ollama_base_url(profile_name),
        "keep_alive": get_ollama_keep_alive(profile_name),
    }
    config.update(options)
    config.update({key: value for key, value in overrides.items() if value is not None})
    return config


def build_mlx_llm_config(
    role: str = "chat_primary",
    profile_name: Optional[str] = None,
    **overrides: Any,
) -> Dict[str, Any]:
    options = get_local_model_options(role, profile_name)
    config: Dict[str, Any] = {
        "provider": "mlx",
        "model": get_local_model(role, profile_name),
        "base_url": get_mlx_base_url(profile_name),
    }
    config.update(options)
    config.update({key: value for key, value in overrides.items() if value is not None})
    return config


def build_local_llm_config(
    role: str = "chat_primary",
    profile_name: Optional[str] = None,
    **overrides: Any,
) -> Dict[str, Any]:
    provider = str(overrides.pop("provider", None) or get_local_provider(profile_name)).strip().lower()
    if provider == "mlx":
        return build_mlx_llm_config(role, profile_name, **overrides)
    return build_ollama_llm_config(role, profile_name, **overrides)


def get_rag_defaults(profile_name: Optional[str] = None) -> Dict[str, Any]:
    profile = get_local_llm_profile(profile_name)
    rag = dict(profile.get("rag", {}))
    rag.setdefault("embedding_model", get_local_model("embedding", profile_name))
    rag.setdefault("embedding_dimension", 1024)
    rag.setdefault("generation_model", get_local_model("chat_primary", profile_name))
    rag.setdefault("chunk_size", 1000)
    rag.setdefault("chunk_overlap", 150)
    rag.setdefault("retrieval_top_k", 10)
    rag.setdefault("rerank_top_n", 5)
    return rag
