from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class ArtifactManager:
    """Small, path-bound artifact manager for workflow and agent integrations."""

    def __init__(self, root_dir: Union[str, Path] = "workflow_output"):
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._artifacts: List[Dict[str, Any]] = []

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "type": "artifact_manager_capabilities",
            "schema_version": "1.0",
            "module": "artifact_manager",
            "root_dir": str(self.root_dir),
            "capabilities": ["register_manifest", "write_json_artifact", "package_manifest"],
            "privacy": {
                "path_bound_to_root": True,
                "forbidden_roots": ["secrets"],
                "writes_by_default": False,
                "exposes_secret_values": False,
            },
        }

    def _resolve_output_path(self, output_path: Union[str, Path]) -> Path:
        path = Path(output_path)
        target = path.resolve() if path.is_absolute() else (self.root_dir / path).resolve()
        if "secrets" in {part.lower() for part in target.parts}:
            raise ValueError("Refusing to write artifact under secrets/")
        try:
            target.relative_to(self.root_dir)
        except ValueError as exc:
            raise ValueError("Artifact path must stay inside the managed root") from exc
        return target

    def register_manifest(
        self,
        artifact_type: str,
        *,
        path: Optional[Union[str, Path]] = None,
        stage: Optional[int] = None,
        source: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        written: bool = False,
    ) -> Dict[str, Any]:
        artifact = {
            "type": artifact_type,
            "stage": stage,
            "path": str(path) if path is not None else None,
            "source": source,
            "metadata": metadata or {},
            "written": written,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        artifact = {key: value for key, value in artifact.items() if value is not None}
        self._artifacts.append(artifact)
        return artifact

    def write_json_artifact(
        self,
        payload: Dict[str, Any],
        output_path: Union[str, Path],
        *,
        artifact_type: str = "json_artifact",
        stage: Optional[int] = None,
        source: str = "",
    ) -> Dict[str, Any]:
        target = self._resolve_output_path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return self.register_manifest(
            artifact_type,
            path=target,
            stage=stage,
            source=source,
            metadata={"format": "json"},
            written=True,
        )

    def package_manifest(self) -> Dict[str, Any]:
        return {
            "type": "artifact_manifest",
            "schema_version": "1.0",
            "root_dir": str(self.root_dir),
            "artifacts": list(self._artifacts),
            "artifact_count": len(self._artifacts),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
