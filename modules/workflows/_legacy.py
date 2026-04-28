from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _module_name(key: str) -> str:
    normalized = key.replace("\\", "_").replace("/", "_").replace(".", "_").replace("-", "_")
    return f"_legacy_{normalized}"


@lru_cache(maxsize=None)
def load_legacy_module(relative_path: str) -> ModuleType:
    module_path = PROJECT_ROOT / relative_path
    if not module_path.exists():
        raise FileNotFoundError(f"Legacy module not found: {module_path}")

    parent = str(module_path.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    name = _module_name(relative_path)
    spec = importlib.util.spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to create import spec for: {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate
