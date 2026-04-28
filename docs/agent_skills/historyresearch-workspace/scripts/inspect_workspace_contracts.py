"""Print read-only TaskManager and ArtifactManager contract snapshots.

This script skips secrets/ and does not write files. It is intended for small
models and agents that need a compact workspace capability summary.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict


def _repo_root(argv: list[str]) -> Path:
    return Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd().resolve()


def _task_snapshot(root: Path) -> Dict[str, Any]:
    sys.path.insert(0, str(root))
    try:
        from modules.task_manager import TaskManager

        manager = TaskManager(mode="script")
        registry = manager.get_task_registry(detailed=False)
        capabilities = manager.get_capabilities()
        return {
            "available": True,
            "task_count": len(registry.get("tasks", {})),
            "tasks": sorted(registry.get("tasks", {}).keys()),
            "default_mode": manager.mode,
            "default_provider": manager.provider,
            "execute_task_package": hasattr(manager, "execute_task_package"),
            "backend_types": capabilities.get("backend_types", []),
        }
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}


def _artifact_snapshot(root: Path) -> Dict[str, Any]:
    sys.path.insert(0, str(root))
    try:
        from modules.artifact_manager import ArtifactManager

        workflow_output = root / "workflow_output"
        snapshot = {
            "available": True,
            "class": "ArtifactManager",
            "managed_root_probe": str(workflow_output),
            "managed_root_exists": workflow_output.exists(),
            "methods": [
                name
                for name in ["get_capabilities", "register_manifest", "write_json_artifact", "package_manifest"]
                if hasattr(ArtifactManager, name)
            ],
        }
        if workflow_output.exists():
            manager = ArtifactManager(workflow_output)
            snapshot["capabilities"] = manager.get_capabilities()
        return snapshot
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}


def main(argv: list[str]) -> int:
    root = _repo_root(argv)
    result = {
        "ok": True,
        "root": str(root),
        "secrets_policy": "not_read",
        "task_manager": _task_snapshot(root),
        "artifact_manager": _artifact_snapshot(root),
    }
    result["ok"] = bool(result["task_manager"].get("available") and result["artifact_manager"].get("available"))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
