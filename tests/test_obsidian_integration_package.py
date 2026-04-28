import tempfile
import unittest
from pathlib import Path

from modules.obsidian_integration import ObsidianIntegration


class ObsidianIntegrationPackageTest(unittest.TestCase):
    def test_create_note_package_writes_inside_vault(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = ObsidianIntegration(vault_path=temp_dir)

            package = vault.create_note_package(
                title="Tokugawa Governance",
                content="# Tokugawa Governance\n\n[[Edo]] institutions.",
                note_type="reading_note",
                folder="Literature Notes",
            )

            note_path = Path(package["path"])
            self.assertEqual(package["type"], "obsidian_note_export")
            self.assertEqual(package["backend"], "filesystem")
            self.assertEqual(package["provider"], "obsidian")
            self.assertFalse(package["needs_review"])
            self.assertTrue(note_path.exists())
            self.assertTrue(note_path.resolve().is_relative_to(Path(temp_dir).resolve()))
            self.assertEqual(package["artifacts"][0]["type"], "markdown_note")

    def test_create_note_package_rejects_folder_traversal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = ObsidianIntegration(vault_path=temp_dir)

            package = vault.create_note_package(
                title="Unsafe",
                content="content",
                folder="../outside",
            )

            self.assertTrue(package["needs_review"])
            self.assertIn("path_outside_vault", package["quality_flags"])
            self.assertFalse(package["path"])

    def test_read_and_update_reject_paths_outside_vault(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as outside_dir:
            vault = ObsidianIntegration(vault_path=temp_dir)
            outside_file = Path(outside_dir) / "outside.md"
            outside_file.write_text("original", encoding="utf-8")

            read_ok, read_result = vault.read_note(str(outside_file))
            update_ok = vault.update_note(str(outside_file), "changed")

            self.assertFalse(read_ok)
            self.assertEqual(read_result, "path outside vault")
            self.assertFalse(update_ok)
            self.assertEqual(outside_file.read_text(encoding="utf-8"), "original")

    def test_build_knowledge_graph_package_scans_wiki_links(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = ObsidianIntegration(vault_path=temp_dir)
            vault.create_note("Source Note", "# Source\n\nLinks to [[Target Note]].")

            package = vault.build_knowledge_graph_package()

            self.assertEqual(package["type"], "obsidian_graph")
            self.assertFalse(package["needs_review"])
            self.assertGreaterEqual(package["stats"]["total_nodes"], 2)
            self.assertEqual(package["stats"]["total_edges"], 1)
            self.assertEqual(package["export_summary"]["edges"], 1)


if __name__ == "__main__":
    unittest.main()
