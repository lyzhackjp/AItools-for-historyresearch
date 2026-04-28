from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Sequence


SCHEMA_VERSION = "1.0"
MODULE_NAME = "historical_citation_workspace"
ORIGINAL_MODULE = "historical_citation_verifier"


class HistoricalCitationWorkspaceInterface:
    """Workspace-safe facade for the historical citation verifier.

    The optimized verifier remains the source of truth. This wrapper only adds
    task-layer metadata, safe defaults, and path redaction so API/workflow/agent
    callers do not need to know the verifier internals.
    """

    def __init__(self, verifier: Optional[Any] = None, workspace_root: Optional[str | Path] = None):
        self._verifier = verifier
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()

    def _resolve_verifier(self) -> Any:
        if self._verifier is None:
            from modules.historical_citation_verifier import HistoricalCitationVerifier

            self._verifier = HistoricalCitationVerifier()
        return self._verifier

    def get_capabilities(self) -> Dict[str, Any]:
        verifier_capabilities: Dict[str, Any] = {}
        try:
            verifier_capabilities = dict(self._resolve_verifier().get_capabilities())
        except Exception as exc:  # noqa: BLE001
            verifier_capabilities = {
                "available": False,
                "error_type": type(exc).__name__,
            }

        source_platforms = verifier_capabilities.get(
            "source_platforms",
            ["ndl", "japan_search", "internet_archive"],
        )
        return {
            "type": "historical_citation_workspace_capabilities",
            "schema_version": SCHEMA_VERSION,
            "module": MODULE_NAME,
            "original_module": ORIGINAL_MODULE,
            "actions": ["parse", "verify"],
            "input_formats": ["docx"],
            "output_types": ["historical_citation_parse", "historical_citation_verification"],
            "source_platforms": source_platforms,
            "backend_options": ["script", "llm_api", "local_llm", "skill", "mcp"],
            "fallback_order": ["script", "public_api", "restricted_download", "ocr", "llm_review", "manual_review"],
            "defaults": {
                "action": "parse",
                "search_ndl": False,
                "download_source": False,
                "restricted_download": False,
                "include_unquoted": False,
            },
            "privacy": {
                "default_parse_is_offline": True,
                "external_search_requires_explicit_flag": True,
                "restricted_download_requires_explicit_flag": True,
                "redacts_absolute_paths": True,
                "does_not_read_secret_values": True,
            },
            "verifier": verifier_capabilities,
        }

    def parse_docx_package(self, file_path: str, *, include_unquoted: bool = False) -> Dict[str, Any]:
        return self.build_package(
            file_path=file_path,
            action="parse",
            include_unquoted=include_unquoted,
        )

    def verify_docx_package(
        self,
        file_path: str,
        *,
        search_ndl: bool = False,
        download_source: bool = False,
        restricted_download: bool = False,
        max_search_results: int = 5,
        page_window: int = 4,
        ocr_model: str = "ndlocr_lite",
        output_dir: Optional[str] = None,
        platform_names: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        return self.build_package(
            file_path=file_path,
            action="verify",
            search_ndl=search_ndl,
            download_source=download_source,
            restricted_download=restricted_download,
            max_search_results=max_search_results,
            page_window=page_window,
            ocr_model=ocr_model,
            output_dir=output_dir,
            platform_names=platform_names,
        )

    def build_package(
        self,
        *,
        file_path: str,
        action: str = "parse",
        include_unquoted: bool = False,
        search_ndl: bool = False,
        download_source: bool = False,
        restricted_download: bool = False,
        max_search_results: int = 5,
        page_window: int = 4,
        ocr_model: str = "ndlocr_lite",
        output_dir: Optional[str] = None,
        platform_names: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        path = Path(file_path)
        normalized_action = (action or "parse").strip().lower()
        if normalized_action not in {"parse", "verify"}:
            return self._error_package(
                action=normalized_action,
                file_path=file_path,
                error="Unsupported historical citation action.",
                quality_flags=["unsupported_action"],
            )
        if path.suffix.lower() != ".docx":
            return self._error_package(
                action=normalized_action,
                file_path=file_path,
                error="Historical citation workspace interface only accepts DOCX input.",
                quality_flags=["unsupported_input_format"],
            )
        if not path.exists():
            return self._error_package(
                action=normalized_action,
                file_path=file_path,
                error="DOCX input file does not exist.",
                quality_flags=["source_path_missing"],
            )

        started = datetime.now()
        try:
            verifier = self._resolve_verifier()
            if normalized_action == "parse":
                package = verifier.parse_docx_package(str(path), include_unquoted=include_unquoted)
            else:
                package = verifier.verify_docx_package(
                    str(path),
                    search_ndl=search_ndl,
                    download_source=download_source,
                    restricted_download=restricted_download,
                    max_search_results=max_search_results,
                    page_window=page_window,
                    ocr_model=ocr_model,
                    output_dir=output_dir,
                    platform_names=platform_names,
                )
        except Exception as exc:  # noqa: BLE001
            return self._error_package(
                action=normalized_action,
                file_path=file_path,
                error=str(exc),
                error_type=type(exc).__name__,
                quality_flags=["historical_citation_execution_failed"],
                started_at=started,
            )

        return self._wrap_success_package(
            package,
            action=normalized_action,
            file_path=file_path,
            include_unquoted=include_unquoted,
            search_ndl=search_ndl,
            download_source=download_source,
            restricted_download=restricted_download,
            max_search_results=max_search_results,
            page_window=page_window,
            ocr_model=ocr_model,
            output_dir=output_dir,
            platform_names=platform_names,
            started_at=started,
        )

    def _wrap_success_package(self, package: Dict[str, Any], *, started_at: datetime, **metadata: Any) -> Dict[str, Any]:
        sanitized = self._sanitize_payload(copy.deepcopy(package))
        quality_flags = list(sanitized.get("quality_flags", []) or [])
        return {
            "type": "historical_citation_workspace_package",
            "schema_version": SCHEMA_VERSION,
            "module": MODULE_NAME,
            "original_module": ORIGINAL_MODULE,
            "success": True,
            "action": metadata["action"],
            "backend": sanitized.get("backend", "script"),
            "provider": sanitized.get("provider", "local_rules"),
            "model": sanitized.get("model"),
            "confidence": float(sanitized.get("confidence", 0.0) or 0.0),
            "needs_review": bool(sanitized.get("needs_review", False)),
            "quality_flags": quality_flags,
            "source": self._source_summary(metadata["file_path"]),
            "execution_time": (datetime.now() - started_at).total_seconds(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "privacy": {
                "absolute_paths_redacted": True,
                "external_search_enabled": bool(metadata.get("search_ndl")),
                "download_enabled": bool(metadata.get("download_source")),
                "restricted_download_enabled": bool(metadata.get("restricted_download")),
            },
            "options": {
                key: value
                for key, value in metadata.items()
                if key
                in {
                    "include_unquoted",
                    "search_ndl",
                    "download_source",
                    "restricted_download",
                    "max_search_results",
                    "page_window",
                    "ocr_model",
                    "output_dir",
                    "platform_names",
                }
            },
            "data": sanitized,
        }

    def _error_package(
        self,
        *,
        action: str,
        file_path: str,
        error: str,
        quality_flags: Sequence[str],
        error_type: str = "ValueError",
        started_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        started = started_at or datetime.now()
        return {
            "type": "historical_citation_workspace_package",
            "schema_version": SCHEMA_VERSION,
            "module": MODULE_NAME,
            "original_module": ORIGINAL_MODULE,
            "success": False,
            "action": action,
            "backend": "script",
            "provider": "local_rules",
            "model": None,
            "confidence": 0.0,
            "needs_review": True,
            "quality_flags": list(quality_flags),
            "error": error,
            "error_type": error_type,
            "source": self._source_summary(file_path),
            "execution_time": (datetime.now() - started).total_seconds(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "privacy": {
                "absolute_paths_redacted": True,
                "external_search_enabled": False,
                "download_enabled": False,
                "restricted_download_enabled": False,
            },
            "data": {},
        }

    def _source_summary(self, file_path: str) -> Dict[str, Any]:
        path = Path(file_path)
        return {
            "name": path.name,
            "suffix": path.suffix.lower(),
            "exists": path.exists(),
            "path": self._redact_path(path),
        }

    def _sanitize_payload(self, payload: Any) -> Any:
        if isinstance(payload, dict):
            return {key: self._sanitize_payload(value) for key, value in payload.items()}
        if isinstance(payload, list):
            return [self._sanitize_payload(item) for item in payload]
        if isinstance(payload, str):
            return self._redact_path_string(payload)
        return payload

    def _redact_path_string(self, value: str) -> str:
        try:
            path = Path(value)
            if path.is_absolute():
                return self._redact_path(path)
        except (OSError, ValueError):
            return value
        return value

    def _redact_path(self, path: Path) -> str:
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError):
            return path.name
        try:
            return resolved.relative_to(self.workspace_root).as_posix()
        except ValueError:
            return f"<local_path_redacted>/{resolved.name}"


def get_historical_citation_workspace_interface(
    verifier: Optional[Any] = None,
    workspace_root: Optional[str | Path] = None,
) -> HistoricalCitationWorkspaceInterface:
    return HistoricalCitationWorkspaceInterface(verifier=verifier, workspace_root=workspace_root)
