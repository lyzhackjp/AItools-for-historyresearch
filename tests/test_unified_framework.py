import unittest
from unittest.mock import Mock, patch

from config.api_key_manager import APIKeyManager
from modules.module_adapters import create_adapter, get_adapter_registry, get_adapter_spec
from modules.secure_api_key_manager import SecureAPIKeyManager
from modules.task_manager import TaskManager
from modules.unified_task_executor import TaskConfig, TaskType, UnifiedTaskExecutor


class TestKeyManagerCompatibility(unittest.TestCase):
    def test_secure_manager_status_report_shape(self):
        status = SecureAPIKeyManager().get_status_report()
        self.assertIn("services", status)
        self.assertIn("total_keys_loaded", status)
        self.assertIsInstance(status["services"], dict)
        self.assertTrue(status["redacted"])
        self.assertFalse(status["privacy"]["exposes_secret_values"])
        self.assertTrue(all(item.get("key_hash") is None for item in status["services"].values()))

    def test_legacy_key_manager_delegates(self):
        legacy = APIKeyManager()
        secure = SecureAPIKeyManager()
        self.assertEqual(legacy.has_key("qwen"), secure.has_key("qwen"))

    def test_legacy_key_manager_exposes_redacted_status(self):
        legacy = APIKeyManager()
        status = legacy.get_status_report()
        self.assertEqual(status["type"], "secure_api_key_status")
        self.assertTrue(status["redacted"])
        self.assertFalse(status["privacy"]["exposes_key_hashes"])


class TestUnifiedTaskExecutor(unittest.TestCase):
    def test_script_mode_ner(self):
        executor = UnifiedTaskExecutor()
        executor.set_mode("script")
        result = executor.execute("ner", text="伊藤博文出生于1841年，是明治维新的重要人物。")
        self.assertTrue(result.success)
        self.assertEqual(result.mode, "script")
        self.assertIn("entities", result.data)
        self.assertEqual(result.metadata.get("backend"), "script")

    def test_statistics_are_recorded(self):
        executor = UnifiedTaskExecutor()
        executor.set_mode("script")
        executor.execute("text_summary", text="这是一段用于测试摘要功能的长文本。" * 5)
        stats = executor.get_statistics()
        self.assertGreaterEqual(stats["total_executions"], 1)

    def test_capability_discovery_returns_multiple_backends(self):
        executor = UnifiedTaskExecutor()
        capability = executor.get_task_capability("ner")
        backend_names = {item["name"] for item in capability["backends"]}
        self.assertIn("script", backend_names)
        self.assertIn("llm_api", backend_names)
        self.assertIn("local_llm", backend_names)

    def test_local_llm_empty_content_falls_back_to_script(self):
        executor = UnifiedTaskExecutor(default_mode="auto")
        fake_client = Mock()
        fake_client._call_llm.return_value = {
            "content": "",
            "needs_review": True,
            "quality_flags": ["empty_content"],
        }
        config = TaskConfig(
            task_type=TaskType.TEXT_SUMMARY,
            provider="ollama",
            model="gemma4:e4b",
            backend="local_llm",
            fallback_backends=["script"],
            cache_enabled=False,
        )

        with patch("modules.llm_client.create_llm_client", return_value=fake_client):
            result = executor.execute(
                "text_summary",
                config=config,
                text="明治维新改变了日本近代国家建设。",
            )

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["backend"], "script")
        self.assertIn("local_llm", result.metadata["attempted_backends"])

    def test_execute_package_includes_validation_and_artifact_policy(self):
        executor = UnifiedTaskExecutor(default_mode="script")
        package = executor.execute_package(
            "text_summary",
            text="明治维新改变了日本近代国家建设，也影响了东亚政治秩序。",
        )
        self.assertEqual(package["type"], "task_execution")
        self.assertTrue(package["success"])
        self.assertEqual(package["backend"], "script")
        self.assertIn("validation", package)
        self.assertIn("quality_flags", package)
        self.assertFalse(package["artifact_policy"]["writes_by_default"])

    def test_execute_package_writes_artifact_only_when_requested(self):
        import tempfile
        from pathlib import Path

        executor = UnifiedTaskExecutor(default_mode="script")
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_path = Path(tmp_dir) / "task_execution.json"
            package = executor.execute_package(
                "text_summary",
                text="史料整理需要保留来源、页码和复核状态。",
                artifact_path=artifact_path,
            )
            self.assertTrue(artifact_path.exists())
            self.assertEqual(package["artifacts"][0]["path"], str(artifact_path))
            self.assertTrue(package["artifacts"][0]["written"])

    def test_execution_artifact_rejects_secrets_path(self):
        executor = UnifiedTaskExecutor(default_mode="script")
        with self.assertRaises(ValueError):
            executor.write_execution_artifact({"type": "task_execution"}, "secrets/task_execution.json")


class TestTaskManager(unittest.TestCase):
    def test_mode_switch_and_script_task(self):
        manager = TaskManager(mode="script")
        self.assertEqual(manager.mode, "script")
        manager.set_mode("api")
        self.assertEqual(manager.mode, "api")
        manager.set_mode("script")
        result = manager.paper_polish("这个研究非常非常重要，基本上基本上可以说明问题。")
        self.assertTrue(result.get("success"))

    def test_custom_prompt_script_mode(self):
        manager = TaskManager(mode="script")
        result = manager.execute_with_prompt(
            task_type="text_summary",
            prompt="请分析以下文本的情感倾向：{text}",
            text="这个产品非常好用，我很满意。",
        )
        self.assertTrue(result.get("success"))

    def test_task_options_include_backend_choices(self):
        manager = TaskManager(mode="script")
        options = manager.get_task_options("ner")
        backend_names = {item["name"] for item in options["backends"]}
        self.assertIn("script", backend_names)
        self.assertIn("llm_api", backend_names)

    def test_task_registry_exposes_aliases_presets_and_backends(self):
        manager = TaskManager(mode="script")
        registry = manager.get_task_registry(detailed=True)
        summary = registry["tasks"]["text_summary"]
        self.assertIn("summary", summary["aliases"])
        self.assertIn("summary_short", summary["presets"])
        self.assertIn("script", summary["backends"])
        self.assertIn("capability", summary)

    def test_capabilities_are_serializable_and_redacted(self):
        manager = TaskManager(mode="script")
        capabilities = manager.get_capabilities()
        self.assertEqual(capabilities["module"], "task_manager")
        self.assertIn("ner", capabilities["tasks"])
        self.assertFalse(capabilities["privacy"]["exposes_secret_values"])

        import json

        payload = json.dumps(capabilities, ensure_ascii=False)
        self.assertNotIn("sk-", payload)

    def test_local_small_preset_declares_ollama_backend(self):
        manager = TaskManager(mode="auto")
        preset = manager.get_presets()["summary_local_small"]
        self.assertEqual(preset.provider, "ollama")
        self.assertEqual(preset.backend, "local_llm")
        self.assertLessEqual(preset.max_tokens, 256)
        self.assertIn("{text}", preset.custom_prompt)

    def test_execute_task_respects_explicit_backend(self):
        manager = TaskManager(mode="auto")
        result = manager.execute_task(
            "ner",
            text="伊藤博文是明治维新的重要人物。",
            backend="script",
        )
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("backend"), "script")

    def test_execute_task_package_wraps_script_result(self):
        manager = TaskManager(mode="script")
        package = manager.execute_task_package(
            "summary",
            text="明治维新改变了日本近代国家建设，也影响了东亚政治秩序。",
            backend="script",
        )
        self.assertEqual(package["type"], "task_execution")
        self.assertEqual(package["task_type"], "text_summary")
        self.assertTrue(package["success"])
        self.assertEqual(package["backend"], "script")
        self.assertIn("data", package)
        self.assertIn("task_options", package)


class TestModuleAdapters(unittest.TestCase):
    def test_adapter_registry_exposes_aliases_and_specs(self):
        registry = get_adapter_registry(detailed=True)
        self.assertIn("text_summary", registry["adapters"])
        self.assertEqual(registry["aliases"]["summary"], "text_summary")
        spec = get_adapter_spec("summary")
        self.assertEqual(spec["task_type"], "text_summary")
        self.assertEqual(spec["primary_method"], "summarize")

    def test_adapter_execute_package_uses_unified_executor(self):
        adapter = create_adapter("summary", mode="script")
        package = adapter.execute_package(
            text="史料整理需要保留来源、页码和复核状态。",
            max_length=50,
        )
        self.assertEqual(package["type"], "task_execution")
        self.assertEqual(package["task_type"], "text_summary")
        self.assertTrue(package["success"])
        self.assertEqual(package["backend"], "script")
        self.assertIn("adapter", adapter.get_capabilities())


if __name__ == "__main__":
    unittest.main()
