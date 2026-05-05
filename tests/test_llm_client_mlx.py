import unittest
from unittest.mock import Mock, patch

from modules.llm_client import create_llm_client


class LLMClientMLXTests(unittest.TestCase):
    def test_mlx_chat_uses_openai_compatible_endpoint_without_sdk(self):
        client = create_llm_client(
            {
                "provider": "mlx",
                "model": "mlx-community/local-qwen-4bit",
                "base_url": "http://127.0.0.1:8080",
                "timeout": 1,
            }
        )

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "OK"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
        }

        with patch("modules.llm_client.requests.post", return_value=response) as post:
            result = client.chat(
                [{"role": "user", "content": "Say OK only."}],
                max_tokens=8,
                temperature=0.1,
                timeout=2,
            )

        self.assertEqual(post.call_args.args[0], "http://127.0.0.1:8080/v1/chat/completions")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "mlx-community/local-qwen-4bit")
        self.assertEqual(payload["max_tokens"], 8)
        self.assertEqual(result["provider"], "mlx")
        self.assertEqual(result["backend"], "local_llm")
        self.assertEqual(result["content"], "OK")
        self.assertFalse(result["needs_review"])

    def test_mlx_capabilities_are_local(self):
        client = create_llm_client({"provider": "mlx", "model": "mlx-local-model"})

        capabilities = client.get_capabilities()

        self.assertEqual(capabilities["backend"], "local_llm")
        self.assertFalse(capabilities["api_key_required"])
        self.assertTrue(capabilities["small_model_friendly"])
        self.assertEqual(capabilities["base_url"], "http://127.0.0.1:8080/v1")


if __name__ == "__main__":
    unittest.main()
