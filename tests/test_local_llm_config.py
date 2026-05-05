import os
import unittest
from contextlib import contextmanager

from config.local_llm_config import (
    build_mlx_llm_config,
    build_ollama_llm_config,
    get_local_base_url,
    get_local_model,
    get_local_provider,
    get_mlx_base_url,
    get_model_role_for_task,
    get_ollama_base_url,
    get_rag_defaults,
)


LOCAL_ENV_KEYS = [
    "LOCAL_LLM_PROFILE",
    "LOCAL_LLM_PROVIDER",
    "LOCAL_LLM_PRIMARY_MODEL",
    "LOCAL_LLM_REASONING_MODEL",
    "LOCAL_LLM_FAST_MODEL",
    "LOCAL_LLM_EMBED_MODEL",
    "MLX_BASE_URL",
    "MLX_MODEL",
    "OLLAMA_MODEL",
    "OLLAMA_EMBED_MODEL",
    "OLLAMA_BASE_URL",
    "OLLAMA_HOST",
    "LLM_PROVIDER",
    "LLM_BASE_URL",
]


@contextmanager
def cleared_local_llm_env():
    previous = {key: os.environ.pop(key, None) for key in LOCAL_ENV_KEYS}
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class LocalLLMConfigTests(unittest.TestCase):
    def test_profile_defaults_are_history_research_models(self):
        with cleared_local_llm_env():
            self.assertEqual(get_local_model("chat_primary"), "qwen36-27b-academic")
            self.assertEqual(get_local_model("reasoning_multimodal"), "gemma4-31b-reason")
            self.assertEqual(get_local_model("embedding"), "bge-m3")
            self.assertEqual(get_local_provider(), "ollama")
            self.assertEqual(get_ollama_base_url(), "http://localhost:11434")

    def test_task_routing_and_rag_defaults(self):
        with cleared_local_llm_env():
            self.assertEqual(get_model_role_for_task("reverse_outline"), "reasoning_multimodal")
            rag = get_rag_defaults()
            self.assertEqual(rag["embedding_model"], "ollama-local")
            self.assertEqual(rag["embedding_ollama_model"], "bge-m3")
            self.assertEqual(rag["generation_model"], "qwen36-27b-academic")
            self.assertEqual(rag["retrieval_top_k"], 10)

    def test_env_override_wins_for_primary_model(self):
        with cleared_local_llm_env():
            os.environ["LOCAL_LLM_PRIMARY_MODEL"] = "custom-local"
            config = build_ollama_llm_config("chat_primary")
            self.assertEqual(config["provider"], "ollama")
            self.assertEqual(config["model"], "custom-local")

    def test_mlx_profile_uses_openai_compatible_local_endpoint(self):
        with cleared_local_llm_env():
            os.environ["LOCAL_LLM_PROFILE"] = "m5_pro_48gb_mlx_history_research"
            os.environ["MLX_MODEL"] = "mlx-community/local-qwen-4bit"
            self.assertEqual(get_local_provider(), "mlx")
            self.assertEqual(get_mlx_base_url(), "http://127.0.0.1:8080/v1")
            self.assertEqual(get_local_base_url(provider="mlx"), "http://127.0.0.1:8080/v1")
            config = build_mlx_llm_config("chat_primary")
            self.assertEqual(config["provider"], "mlx")
            self.assertEqual(config["model"], "mlx-community/local-qwen-4bit")
            self.assertEqual(config["base_url"], "http://127.0.0.1:8080/v1")

    def test_mlx_env_base_url_override_wins_when_provider_selected(self):
        with cleared_local_llm_env():
            os.environ["LLM_PROVIDER"] = "mlx"
            os.environ["LLM_BASE_URL"] = "http://127.0.0.1:18080/v1"
            self.assertEqual(get_local_provider(), "mlx")
            self.assertEqual(get_mlx_base_url(), "http://127.0.0.1:18080/v1")


if __name__ == "__main__":
    unittest.main()
