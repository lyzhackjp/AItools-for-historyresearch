import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MACOS_SCRIPT_DIR = ROOT / "scripts" / "macos"


class TestMacOSLaunchScripts(unittest.TestCase):
    def test_launcher_scripts_exist(self):
        expected = {
            "initialize-history-research-ai.sh",
            "check-mlx-runtime.sh",
            "setup-local-llm.sh",
            "start-history-research-ai.sh",
            "start-mlx-server.sh",
            "stop-history-research-ai.sh",
        }
        actual = {path.name for path in MACOS_SCRIPT_DIR.glob("*.sh")}
        self.assertTrue(expected.issubset(actual))

    def test_start_script_preserves_packaged_ui_environment(self):
        start_script = MACOS_SCRIPT_DIR / "start-history-research-ai.sh"
        content = start_script.read_text(encoding="utf-8")

        self.assertIn("HISTORY_RESEARCH_SERVE_FRONTEND=1", content)
        self.assertIn("FLASK_DEBUG=0", content)
        self.assertIn("HOST=127.0.0.1", content)
        self.assertIn("PORT=5050", content)
        self.assertIn(".runtime", content)
        self.assertIn("backend.pid", content)
        self.assertIn("PYTHONPYCACHEPREFIX", content)
        self.assertIn("XDG_CACHE_HOME", content)
        self.assertIn("HF_HOME", content)
        self.assertIn(".env.local_llm", content)
        self.assertIn("local-llm.env", content)
        self.assertIn("MLX_AUTO_START", content)

    def test_package_script_carries_local_llm_default_for_app(self):
        package_script = MACOS_SCRIPT_DIR / "package-app.sh"
        content = package_script.read_text(encoding="utf-8")

        self.assertIn(".env.local_llm", content)
        self.assertIn("--include-local-llm-env", content)
        self.assertIn("defaults/local-llm.env", content)
        self.assertIn("HISTORY_RESEARCH_SUPPORT_DIR", content)
        self.assertIn("config/api_config.json", content)

    @unittest.skipIf(shutil.which("bash") is None, "bash is not available")
    def test_scripts_are_valid_bash(self):
        for script in MACOS_SCRIPT_DIR.glob("*.sh"):
            with self.subTest(script=script.name):
                result = subprocess.run(
                    ["bash", "-n", str(script)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
