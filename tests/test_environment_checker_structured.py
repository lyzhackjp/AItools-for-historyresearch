import unittest
import tempfile
from pathlib import Path

from modules.artifact_manager import ArtifactManager
from modules.environment_checker import EnvironmentChecker


class TestEnvironmentCheckerStructured(unittest.TestCase):
    def test_dependency_check_is_structured_and_non_destructive(self):
        checker = EnvironmentChecker()
        result = checker.check_dependencies_structured({
            "json": "standard json module",
            "definitely_missing_package_for_test": "missing fixture",
        })

        self.assertEqual(result["type"], "dependency_check")
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["missing"], 1)
        self.assertTrue(result["needs_review"])
        missing = [item for item in result["checks"] if not item["installed"]][0]
        self.assertIn("pip install", missing["repair_hint"])

    def test_structured_report_includes_repair_hints(self):
        checker = EnvironmentChecker()
        checker.results["dependencies"] = {
            "fitz": {
                "installed": False,
                "description": "PyMuPDF PDF processing",
            }
        }
        checker.results["issues"].append("missing dependency")

        report = checker.get_structured_report()

        self.assertEqual(report["status"], "needs_repair")
        self.assertEqual(report["issue_count"], 1)
        self.assertEqual(report["repair_hints"][0]["target"], "fitz")
        self.assertFalse(report["repair_hints"][0]["automatic"])

    def test_environment_package_and_artifact_manager_are_path_bound(self):
        checker = EnvironmentChecker()
        package = checker.build_environment_package()
        self.assertEqual(package["type"], "environment_report")
        self.assertIn("capabilities", package)
        self.assertFalse(package["capabilities"]["privacy"]["writes_by_default"])

        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = ArtifactManager(root_dir=tmp_dir)
            artifact = manager.write_json_artifact(package, "reports/environment.json", source="unit-test")
            self.assertTrue(Path(artifact["path"]).exists())
            self.assertEqual(manager.package_manifest()["artifact_count"], 1)
            with self.assertRaises(ValueError):
                manager.write_json_artifact(package, "../outside.json")
            with self.assertRaises(ValueError):
                manager.write_json_artifact(package, "secrets/environment.json")


if __name__ == "__main__":
    unittest.main()
