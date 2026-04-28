import unittest
from unittest.mock import Mock, patch

from modules.llm_client import create_llm_client


class LLMClientOllamaTests(unittest.TestCase):
    def test_ollama_native_chat_strips_openai_v1_suffix(self):
        client = create_llm_client(
            {
                "provider": "ollama",
                "model": "gemma4:e4b",
                "base_url": "http://localhost:11434/v1",
                "timeout": 1,
            }
        )

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "message": {"content": "{\"ok\": true}"},
            "prompt_eval_count": 5,
            "eval_count": 4,
        }

        with patch("modules.llm_client.requests.post", return_value=response) as post:
            result = client.chat(
                [{"role": "user", "content": "Return JSON only."}],
                max_tokens=32,
                temperature=0.1,
                timeout=2,
            )

        self.assertEqual(
            post.call_args.args[0],
            "http://localhost:11434/api/chat",
        )
        self.assertEqual(result["provider"], "ollama")
        self.assertEqual(result["backend"], "local_llm")
        self.assertEqual(result["usage"]["total_tokens"], 9)
        self.assertFalse(result["needs_review"])

    def test_ollama_empty_content_is_flagged(self):
        client = create_llm_client({"provider": "ollama", "model": "gemma4:e4b"})

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "message": {"content": ""},
            "done_reason": "length",
            "prompt_eval_count": 5,
            "eval_count": 4,
        }

        with patch("modules.llm_client.requests.post", return_value=response):
            result = client.chat([{"role": "user", "content": "Hello"}])

        self.assertTrue(result["needs_review"])
        self.assertIn("empty_content", result["quality_flags"])
        self.assertIn("length_limited", result["quality_flags"])

    def test_ollama_capabilities_are_small_model_friendly(self):
        client = create_llm_client(
            {
                "provider": "ollama",
                "model": "gemma4:e4b",
                "base_url": "http://localhost:11434",
            }
        )

        capabilities = client.get_capabilities()

        self.assertEqual(capabilities["backend"], "local_llm")
        self.assertFalse(capabilities["api_key_required"])
        self.assertTrue(capabilities["small_model_friendly"])
        self.assertEqual(capabilities["recommended_smoke"]["max_tokens"], 64)
        self.assertEqual(capabilities["recommended_smoke"]["prompt"], "Say OK only.")


if __name__ == "__main__":
    unittest.main()
