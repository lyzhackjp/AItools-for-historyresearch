"""
Obsidian vault integration helpers.

This module is intentionally focused on filesystem-safe vault operations,
wiki-link scanning, and lightweight export utilities.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ObsidianIntegration:
    """Manage vault structure and note IO for Obsidian-compatible exports."""

    DEFAULT_VAULT_SETTINGS = {
        "plugins": {
            "daily_notes": False,
            "templates": False,
            "graph_view": True,
        }
    }

    def __init__(self, vault_path: Optional[str] = None):
        self.vault_path = Path(vault_path).resolve() if vault_path else None
        self.current_vault = self.vault_path.name if self.vault_path else None
        self.settings: Dict[str, Any] = {}
        if self.vault_path:
            self._ensure_vault_structure()

    def create_vault(self, vault_name: str, vault_root: Optional[str] = None) -> bool:
        """Create a new vault with the expected directory structure."""

        base_path = Path(vault_root).resolve() if vault_root else Path.cwd().resolve()
        vault_path = base_path / vault_name
        self.vault_path = vault_path
        self.current_vault = vault_name
        self._ensure_vault_structure()

        self.settings = {
            "name": vault_name,
            "path": str(vault_path),
            "created": datetime.now().isoformat(timespec="seconds"),
            **self.DEFAULT_VAULT_SETTINGS,
        }
        settings_file = vault_path / ".obsidian" / "vault.json"
        settings_file.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2), encoding="utf-8")
        return True

    def open_vault(self, vault_path: str) -> bool:
        """Open an existing vault path."""

        path = Path(vault_path).resolve()
        if not path.exists():
            return False
        self.vault_path = path
        self.current_vault = path.name
        self._ensure_vault_structure()

        settings_file = path / ".obsidian" / "vault.json"
        if settings_file.exists():
            self.settings = json.loads(settings_file.read_text(encoding="utf-8"))
        else:
            self.settings = {
                "name": self.current_vault,
                "path": str(path),
                **self.DEFAULT_VAULT_SETTINGS,
            }
        return True

    def create_bidirectional_links(self, text: str, entities: Dict[str, List[str]]) -> str:
        """Wrap entities with Obsidian wiki links."""

        linked_text = text
        all_entities = sorted({item for values in entities.values() for item in values}, key=len, reverse=True)
        for entity in all_entities:
            if not entity or f"[[{entity}]]" in linked_text:
                continue
            linked_text = re.sub(rf"(?<!\[\[){re.escape(entity)}(?!\]\])", f"[[{entity}]]", linked_text)
        return linked_text

    def apply_eta_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Compatibility helper that renders simple Markdown templates."""

        title = context.get("title", template_name)
        summary = context.get("summary", "")
        return f"# {title}\n\n{summary}\n"

    def get_capabilities(self) -> Dict[str, Any]:
        """Return a machine-readable capability snapshot for workflow routing."""

        return {
            "module": "obsidian_integration",
            "layer": "analysis_vault_integration",
            "backend": "filesystem",
            "provider": "obsidian",
            "model": None,
            "tasks": [
                "vault_safe_write",
                "note_create",
                "note_update",
                "frontmatter_write",
                "graph_scan",
                "markdown_import",
                "json_export",
            ],
            "output_types": ["obsidian_note_export", "obsidian_graph"],
            "vault_initialized": self.vault_path is not None,
            "vault_path": str(self.vault_path) if self.vault_path else "",
            "supports": {
                "safe_write": True,
                "frontmatter": True,
                "bidirectional_links": True,
                "knowledge_graph_scan": True,
                "external_ai_backend": False,
            },
            "privacy": {
                "scope": "local_vault_only",
                "path_traversal_guard": True,
                "secrets_required": False,
            },
        }

    def create_note(
        self,
        title: str,
        content: str,
        note_type: str = "note",
        folder: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Create a note inside the vault and return the final path."""

        if self.vault_path is None:
            return False, "vault not initialized"

        note_folder = self._resolve_vault_path(folder or "Notes")
        if note_folder is None:
            return False, "path outside vault"
        note_folder.mkdir(parents=True, exist_ok=True)
        safe_title = self._sanitize_filename(title)
        path = note_folder / f"{safe_title}.md"
        counter = 1
        while path.exists():
            path = note_folder / f"{safe_title}_{counter}.md"
            counter += 1

        frontmatter = [
            "---",
            f"type: {note_type}",
            f"created: {datetime.now().strftime('%Y-%m-%d')}",
            "---",
            "",
        ]
        path.write_text("\n".join(frontmatter) + content, encoding="utf-8")
        return True, str(path)

    def create_note_package(
        self,
        title: str,
        content: str,
        note_type: str = "note",
        folder: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a note and return a workflow-friendly package envelope."""

        quality_flags = []
        if not str(title or "").strip():
            quality_flags.append("empty_title")
        if not str(content or "").strip():
            quality_flags.append("empty_content")

        success, result = self.create_note(
            title=title or "Untitled",
            content=content or "",
            note_type=note_type,
            folder=folder,
        )
        if not success:
            quality_flags.append(result.replace(" ", "_"))

        relative_path = ""
        artifacts = []
        if success and self.vault_path is not None:
            note_path = Path(result).resolve()
            try:
                relative_path = str(note_path.relative_to(self.vault_path))
            except ValueError:
                quality_flags.append("path_outside_vault")
                success = False
            else:
                artifacts.append(
                    {
                        "type": "markdown_note",
                        "path": str(note_path),
                        "relative_path": relative_path,
                    }
                )

        return {
            "type": "obsidian_note_export",
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "title": title,
            "note_type": note_type,
            "folder": folder or "Notes",
            "path": result if success else "",
            "relative_path": relative_path,
            "vault_path": str(self.vault_path) if self.vault_path else "",
            "backend": "filesystem",
            "provider": "obsidian",
            "model": None,
            "confidence": self._package_confidence(success, quality_flags),
            "needs_review": (not success) or bool(quality_flags),
            "quality_flags": quality_flags,
            "artifacts": artifacts,
            "export_summary": {
                "note_created": bool(success),
                "relative_path": relative_path,
                "error": "" if success else result,
            },
            "capabilities": self.get_capabilities(),
            "error": "" if success else result,
        }

    def read_note(self, note_path: str) -> Tuple[bool, str]:
        """Read note content."""

        if self.vault_path is None:
            return False, "vault not initialized"
        path = self._resolve_vault_path(note_path)
        if path is None:
            return False, "path outside vault"
        if not path.exists():
            return False, "note does not exist"
        if not path.is_file():
            return False, "note path is not a file"
        return True, path.read_text(encoding="utf-8")

    def update_note(self, note_path: str, new_content: str) -> bool:
        """Overwrite note content."""

        success, _ = self.read_note(note_path)
        if not success:
            return False
        path = self._resolve_vault_path(note_path)
        if path is None:
            return False
        path.write_text(new_content, encoding="utf-8")
        return True

    def update_note_package(self, note_path: str, new_content: str) -> Dict[str, Any]:
        """Update a note and return a structured package envelope."""

        quality_flags = []
        if not str(new_content or "").strip():
            quality_flags.append("empty_content")
        success = self.update_note(note_path, new_content or "")
        if not success:
            quality_flags.append("update_failed")
        resolved = self._resolve_vault_path(note_path) if self.vault_path is not None else None
        relative_path = ""
        if resolved is not None and self.vault_path is not None:
            try:
                relative_path = str(resolved.relative_to(self.vault_path))
            except ValueError:
                quality_flags.append("path_outside_vault")

        return {
            "type": "obsidian_note_export",
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "operation": "update",
            "path": str(resolved) if success and resolved is not None else "",
            "relative_path": relative_path,
            "vault_path": str(self.vault_path) if self.vault_path else "",
            "backend": "filesystem",
            "provider": "obsidian",
            "model": None,
            "confidence": self._package_confidence(success, quality_flags),
            "needs_review": (not success) or bool(quality_flags),
            "quality_flags": quality_flags,
            "artifacts": [
                {"type": "markdown_note", "path": str(resolved), "relative_path": relative_path}
            ]
            if success and resolved is not None
            else [],
            "export_summary": {"note_updated": bool(success), "relative_path": relative_path},
            "capabilities": self.get_capabilities(),
            "error": "" if success else "update failed",
        }

    def search_notes(self, query: str, search_type: str = "content") -> List[Dict[str, Any]]:
        """Search notes by title or content."""

        if self.vault_path is None:
            return []
        results = []
        for md_file in self.vault_path.rglob("*.md"):
            if ".obsidian" in str(md_file):
                continue
            if search_type == "title":
                if query.lower() in md_file.stem.lower():
                    results.append({"path": str(md_file.relative_to(self.vault_path)), "title": md_file.stem, "type": "title_match"})
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception:  # noqa: BLE001
                continue
            if query.lower() in content.lower():
                results.append(
                    {
                        "path": str(md_file.relative_to(self.vault_path)),
                        "title": md_file.stem,
                        "type": "content_match",
                        "match_count": content.lower().count(query.lower()),
                    }
                )
        return results

    def get_backlinks(self, note_title: str) -> List[Dict[str, str]]:
        """Return notes that link to the given title."""

        if self.vault_path is None:
            return []
        backlinks = []
        pattern = re.compile(rf"\[\[{re.escape(note_title)}\]\]")
        for md_file in self.vault_path.rglob("*.md"):
            if ".obsidian" in str(md_file) or md_file.stem == note_title:
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception:  # noqa: BLE001
                continue
            matches = pattern.findall(content)
            if matches:
                backlinks.append(
                    {
                        "source": str(md_file.relative_to(self.vault_path)),
                        "source_title": md_file.stem,
                        "link_count": len(matches),
                    }
                )
        return backlinks

    def build_knowledge_graph_data(self) -> Dict[str, Any]:
        """Scan the vault and return note/link graph data."""

        if self.vault_path is None:
            return {}

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        seen_nodes = set()
        link_pattern = re.compile(r"\[\[([^\]]+)\]\]")

        for md_file in self.vault_path.rglob("*.md"):
            if ".obsidian" in str(md_file):
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception:  # noqa: BLE001
                continue

            if md_file.stem not in seen_nodes:
                nodes.append(
                    {
                        "id": md_file.stem,
                        "label": md_file.stem,
                        "type": "note",
                        "path": str(md_file.relative_to(self.vault_path)),
                    }
                )
                seen_nodes.add(md_file.stem)

            for target in link_pattern.findall(content):
                edges.append({"source": md_file.stem, "target": target, "type": "links_to"})
                if target not in seen_nodes:
                    nodes.append({"id": target, "label": target, "type": "linked_note", "exists": False})
                    seen_nodes.add(target)

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "notes_with_links": len({edge["source"] for edge in edges}),
            },
        }

    def build_knowledge_graph_package(self) -> Dict[str, Any]:
        """Return graph scan data as a structured workflow package."""

        graph_data = self.build_knowledge_graph_data()
        success = bool(graph_data or self.vault_path is not None)
        quality_flags = []
        if self.vault_path is None:
            quality_flags.append("vault_not_initialized")
        stats = graph_data.get("stats", {}) if graph_data else {}
        if success and stats.get("total_nodes", 0) == 0:
            quality_flags.append("empty_vault_graph")

        return {
            "type": "obsidian_graph",
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "vault_path": str(self.vault_path) if self.vault_path else "",
            "backend": "filesystem",
            "provider": "obsidian",
            "model": None,
            "confidence": self._package_confidence(success, quality_flags),
            "needs_review": (not success) or bool(quality_flags),
            "quality_flags": quality_flags,
            "nodes": graph_data.get("nodes", []) if graph_data else [],
            "edges": graph_data.get("edges", []) if graph_data else [],
            "stats": stats,
            "export_summary": {
                "nodes": stats.get("total_nodes", 0),
                "edges": stats.get("total_edges", 0),
                "notes_with_links": stats.get("notes_with_links", 0),
            },
            "capabilities": self.get_capabilities(),
            "error": "" if success else "vault not initialized",
        }

    def sync_zotero_annotations(self, annotations: List[Dict[str, Any]], parent_note: str) -> bool:
        """Create an annotation note from Zotero-like annotation payloads."""

        lines = [f"# {parent_note} - Annotations", "", f"Count: {len(annotations)}", "", "---", ""]
        for index, annotation in enumerate(annotations, start=1):
            lines.append(f"### Annotation {index}")
            if annotation.get("page"):
                lines.append(f"- Page: {annotation['page']}")
            if annotation.get("color"):
                lines.append(f"- Color: {annotation['color']}")
            lines.append(f"> {annotation.get('text', '')}")
            lines.append("")
        success, _ = self.create_note(
            f"Annotations - {parent_note}",
            "\n".join(lines),
            note_type="annotations",
            folder="Annotations",
        )
        return success

    def import_markdown_files(self, source_dir: str, target_folder: Optional[str] = None) -> Dict[str, Any]:
        """Bulk import Markdown files into the vault."""

        if self.vault_path is None:
            return {"success": False, "error": "vault not initialized"}

        source_path = Path(source_dir).resolve()
        if not source_path.exists():
            return {"success": False, "error": "source directory does not exist"}

        imported = []
        failed = []
        target = self._resolve_vault_path(target_folder or "Imported")
        if target is None:
            return {"success": False, "error": "path outside vault"}
        target.mkdir(parents=True, exist_ok=True)

        for md_file in source_path.rglob("*.md"):
            try:
                shutil.copy2(md_file, target / md_file.name)
                imported.append(md_file.name)
            except Exception as exc:  # noqa: BLE001
                failed.append({"file": md_file.name, "error": str(exc)})
        return {
            "success": True,
            "imported_count": len(imported),
            "failed_count": len(failed),
            "imported_files": imported,
            "failed_files": failed,
        }

    def export_notes_to_json(self, output_path: str) -> bool:
        """Export vault note metadata and content into JSON."""

        if self.vault_path is None:
            return False

        notes = []
        for md_file in self.vault_path.rglob("*.md"):
            if ".obsidian" in str(md_file):
                continue
            try:
                notes.append(
                    {
                        "title": md_file.stem,
                        "path": str(md_file.relative_to(self.vault_path)),
                        "content": md_file.read_text(encoding="utf-8"),
                    }
                )
            except Exception:  # noqa: BLE001
                continue

        output = self._resolve_vault_path(output_path)
        if output is None:
            return False
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"notes": notes}, ensure_ascii=False, indent=2), encoding="utf-8")
        return True

    def export_notes_to_json_package(self, output_path: str = "Exports/obsidian_notes.json") -> Dict[str, Any]:
        """Export vault notes to JSON and return package metadata."""

        success = self.export_notes_to_json(output_path)
        resolved = self._resolve_vault_path(output_path) if self.vault_path is not None else None
        quality_flags = [] if success else ["json_export_failed"]
        relative_path = ""
        if resolved is not None and self.vault_path is not None:
            try:
                relative_path = str(resolved.relative_to(self.vault_path))
            except ValueError:
                quality_flags.append("path_outside_vault")
        return {
            "type": "obsidian_note_export",
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "operation": "json_export",
            "path": str(resolved) if success and resolved is not None else "",
            "relative_path": relative_path,
            "vault_path": str(self.vault_path) if self.vault_path else "",
            "backend": "filesystem",
            "provider": "obsidian",
            "model": None,
            "confidence": self._package_confidence(success, quality_flags),
            "needs_review": (not success) or bool(quality_flags),
            "quality_flags": quality_flags,
            "artifacts": [
                {"type": "json_export", "path": str(resolved), "relative_path": relative_path}
            ]
            if success and resolved is not None
            else [],
            "export_summary": {"json_exported": bool(success), "relative_path": relative_path},
            "capabilities": self.get_capabilities(),
            "error": "" if success else "json export failed",
        }

    def _ensure_vault_structure(self) -> None:
        """Create the minimal folder structure expected by exports."""

        if self.vault_path is None:
            return
        self.vault_path.mkdir(parents=True, exist_ok=True)
        (self.vault_path / ".obsidian").mkdir(exist_ok=True)
        for folder in ("Notes", "Literature Notes", "Attachments", "Templates", "Scripts", "Daily", "Imported", "Annotations"):
            (self.vault_path / folder).mkdir(exist_ok=True)

    def _sanitize_filename(self, value: str) -> str:
        cleaned = re.sub(r'[<>:"/\\|?*]+', "_", value).strip()
        return cleaned or "untitled"

    def _resolve_vault_path(self, value: str) -> Optional[Path]:
        """Resolve a relative or absolute path and ensure it stays inside the vault."""

        if self.vault_path is None:
            return None
        path = Path(value)
        if not path.is_absolute():
            path = self.vault_path / path
        resolved = path.resolve()
        try:
            resolved.relative_to(self.vault_path)
        except ValueError:
            return None
        return resolved

    def _package_confidence(self, success: bool, quality_flags: List[str]) -> float:
        if not success:
            return 0.0
        if not quality_flags:
            return 1.0
        if quality_flags == ["empty_content"]:
            return 0.75
        return 0.6


def create_obsidian_integration(vault_path: Optional[str] = None) -> ObsidianIntegration:
    """Compatibility factory helper."""

    return ObsidianIntegration(vault_path=vault_path)
