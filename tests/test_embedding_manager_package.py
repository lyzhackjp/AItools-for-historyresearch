import unittest
from unittest.mock import Mock, patch

from modules.embedding_manager import EmbeddingManager, create_embedding_manager


class NoAutoLoadEmbeddingManager(EmbeddingManager):
    def __init__(self):
        super().__init__(default_model="bge-m3", auto_load_models=False)
        self.load_called = False

    def load_embedding_model(self, model_name="bge-m3"):
        self.load_called = True
        raise AssertionError("load_embedding_model should not be called by safe default")


class EmbeddingManagerPackageTest(unittest.TestCase):
    def test_create_vector_index_package_uses_safe_mock_default(self):
        manager = NoAutoLoadEmbeddingManager()
        documents = [
            {"text": "Tokugawa governance in Edo", "metadata": {"id": "a"}},
            {"text": "Meiji political reform", "metadata": {"id": "b"}},
        ]

        package = manager.create_vector_index_package(documents)

        self.assertEqual(package["type"], "embedding_index")
        self.assertTrue(package["index"]["initialized"])
        self.assertEqual(package["index"]["document_count"], 2)
        self.assertIn("mock_embedding_used", package["quality_flags"])
        self.assertTrue(package["needs_review"])
        self.assertFalse(manager.load_called)
        self.assertEqual(package["model"], "mock:bge-m3")

    def test_semantic_search_package_returns_ranked_results(self):
        manager = create_embedding_manager(default_model="bge-m3")
        manager.create_vector_index_package(
            [
                {"text": "Edo urban administration", "metadata": {"title": "Edo"}},
                {"text": "Qing fiscal history", "metadata": {"title": "Qing"}},
            ]
        )

        package = manager.semantic_search_package("Edo administration", top_k=1)

        self.assertEqual(package["type"], "semantic_search")
        self.assertEqual(package["search_summary"]["result_count"], 1)
        self.assertEqual(package["results"][0]["rank"], 1)
        self.assertFalse(package["error"])

    def test_semantic_search_without_index_needs_review(self):
        manager = create_embedding_manager()

        package = manager.semantic_search_package("query")

        self.assertTrue(package["needs_review"])
        self.assertIn("index_not_initialized", package["quality_flags"])
        self.assertEqual(package["confidence"], 0.0)

    def test_ollama_embedding_uses_local_embed_endpoint(self):
        manager = create_embedding_manager(default_model="ollama-local")
        with patch.dict("os.environ", {"OLLAMA_EMBED_MODEL": "bge-m3", "OLLAMA_BASE_URL": "http://localhost:11434"}):
            self.assertTrue(manager.load_embedding_model("ollama-local"))

            response = Mock()
            response.raise_for_status.return_value = None
            response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}

            with patch("modules.embedding_manager.requests.post", return_value=response) as post:
                vector = manager._get_embedding("Edo administration")

        self.assertEqual(post.call_args.args[0], "http://localhost:11434/api/embed")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "bge-m3")
        self.assertEqual(vector.tolist() if hasattr(vector, "tolist") else vector, [0.1, 0.2, 0.3])


if __name__ == "__main__":
    unittest.main()
