import tempfile
import shutil
import unittest
from pathlib import Path

from modules.historical_citation_workspace import HistoricalCitationWorkspaceInterface
from modules.module_adapters import create_adapter, get_adapter_spec
from modules.task_manager import TaskManager


class FakeHistoricalCitationVerifier:
    def get_capabilities(self):
        return {
            "module": "historical_citation_verifier",
            "source_platforms": ["ndl", "example"],
            "output_types": ["historical_citation_parse", "historical_citation_verification"],
        }

    def parse_docx_package(self, file_path, *, include_unquoted=False):
        return {
            "type": "historical_citation_parse",
            "backend": "script",
            "provider": "local_rules",
            "model": None,
            "confidence": 0.91,
            "needs_review": False,
            "quality_flags": [],
            "document": {
                "title": "synthetic",
                "file_path": str(Path(file_path).resolve()),
            },
            "summary": {
                "candidate_count": 1,
                "include_unquoted": include_unquoted,
            },
        }

    def verify_docx_package(self, file_path, **kwargs):
        return {
            "type": "historical_citation_verification",
            "backend": "script",
            "provider": "local_rules",
            "model": None,
            "confidence": 0.62,
            "needs_review": True,
            "quality_flags": ["source_not_found"],
            "document": {
                "title": "synthetic",
                "file_path": str(Path(file_path).resolve()),
            },
            "summary": {"search_ndl": kwargs.get("search_ndl")},
        }


class TestHistoricalCitationWorkspaceInterface(unittest.TestCase):
    def _docx_path(self) -> Path:
        tmpdir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        path = tmpdir / "sample.docx"
        path.write_bytes(b"synthetic")
        return path

    def test_parse_package_wraps_existing_verifier_and_redacts_paths(self):
        path = self._docx_path()
        interface = HistoricalCitationWorkspaceInterface(
            verifier=FakeHistoricalCitationVerifier(),
            workspace_root=Path.cwd(),
        )

        package = interface.parse_docx_package(str(path), include_unquoted=True)

        self.assertTrue(package["success"])
        self.assertEqual(package["type"], "historical_citation_workspace_package")
        self.assertEqual(package["action"], "parse")
        self.assertEqual(package["confidence"], 0.91)
        self.assertTrue(package["privacy"]["absolute_paths_redacted"])
        self.assertFalse(Path(package["data"]["document"]["file_path"]).is_absolute())
        self.assertTrue(package["data"]["summary"]["include_unquoted"])

    def test_missing_file_returns_reviewable_error_package(self):
        interface = HistoricalCitationWorkspaceInterface(verifier=FakeHistoricalCitationVerifier())

        package = interface.parse_docx_package("missing.docx")

        self.assertFalse(package["success"])
        self.assertTrue(package["needs_review"])
        self.assertIn("source_path_missing", package["quality_flags"])

    def test_adapter_registry_exposes_historical_citation(self):
        spec = get_adapter_spec("history_citation")
        adapter = create_adapter("historical_citation", verifier=FakeHistoricalCitationVerifier())

        self.assertEqual(spec["task_type"], "historical_citation")
        self.assertIn("file_path", spec["required_inputs"])
        self.assertIn("parse", adapter.get_capabilities()["actions"])

    def test_task_manager_executes_historical_citation_package(self):
        path = self._docx_path()
        manager = TaskManager(mode="script", provider="qwen")
        manager._adapters["historical_citation"].interface = HistoricalCitationWorkspaceInterface(
            verifier=FakeHistoricalCitationVerifier(),
            workspace_root=Path.cwd(),
        )

        package = manager.execute_task_package("history_citation", file_path=str(path), action="parse")

        self.assertTrue(package["success"])
        self.assertEqual(package["task_type"], "historical_citation")
        self.assertEqual(package["data"]["type"], "historical_citation_workspace_package")
        self.assertIn("historical_citation_parse", package["data"]["data"]["type"])


if __name__ == "__main__":
    unittest.main()
