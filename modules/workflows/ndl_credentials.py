from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NDL_CREDENTIALS_FILE = PROJECT_ROOT / "secrets" / "ndl_credentials.txt"
ALTERNATE_NDL_CREDENTIALS_FILES = (PROJECT_ROOT / "secret" / "ndl_credentials.txt",)


class NDLCredentialError(RuntimeError):
    """Raised when NDL credentials are not provided or malformed."""


@dataclass(frozen=True)
class NDLCredentials:
    username: str
    password: str
    source: str = "unknown"

    def as_dict(self) -> Dict[str, str]:
        return {"username": self.username, "password": self.password}


def _read_key_value_file(path: Path) -> Dict[str, str]:
    payload: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        payload[key.strip().lower()] = value.strip()
    return payload


def _read_credentials_file(path: Path) -> Dict[str, str]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    if text.startswith("{"):
        data = json.loads(text)
        return {str(key).lower(): str(value) for key, value in data.items() if value is not None}
    return _read_key_value_file(path)


def _pick(payload: Dict[str, str], *keys: str) -> Optional[str]:
    for key in keys:
        value = payload.get(key.lower())
        if value:
            return value
    return None


def load_ndl_credentials(
    credentials_file: str | Path | None = None,
    *,
    allow_env: bool = True,
) -> NDLCredentials:
    """Load NDL credentials from caller-provided env vars or local secret file.

    Resolution order:
    1. Environment variables: `NDL_USERNAME`/`NDL_PASSWORD`, or
       `NDL_CARD_ID`/`NDL_PASSWORD`.
    2. `NDL_CREDENTIALS_FILE` environment variable.
    3. Explicit `credentials_file` argument.
    4. Local ignored file: `secrets/ndl_credentials.txt`.
    """

    if allow_env:
        username = os.environ.get("NDL_USERNAME") or os.environ.get("NDL_CARD_ID")
        password = os.environ.get("NDL_PASSWORD")
        if username and password:
            return NDLCredentials(username=username, password=password, source="environment")

    env_file = os.environ.get("NDL_CREDENTIALS_FILE") if allow_env else None
    if env_file or credentials_file:
        candidate_paths = [Path(env_file or credentials_file)]
    else:
        candidate_paths = [DEFAULT_NDL_CREDENTIALS_FILE, *ALTERNATE_NDL_CREDENTIALS_FILES]

    path = None
    for candidate_path in candidate_paths:
        resolved = candidate_path.expanduser()
        if not resolved.is_absolute():
            resolved = (PROJECT_ROOT / resolved).resolve()
        if resolved.exists():
            path = resolved
            break

    if path is None:
        raise NDLCredentialError(
            "NDL credentials are not configured. Provide NDL_USERNAME/NDL_PASSWORD, "
            "set NDL_CREDENTIALS_FILE, or create secrets/ndl_credentials.txt "
            "(secret/ndl_credentials.txt is also supported)."
        )

    payload = _read_credentials_file(path)
    username = _pick(payload, "username", "card_id", "cardId", "ndl_username", "ndl_card_id")
    password = _pick(payload, "password", "passwd", "ndl_password")
    if not username or not password:
        raise NDLCredentialError(
            "NDL credentials file must contain username=... and password=... "
            "or JSON keys with equivalent names."
        )
    return NDLCredentials(username=username, password=password, source=str(path))


def load_ndl_credentials_dict(credentials_file: str | Path | None = None) -> Dict[str, str]:
    return load_ndl_credentials(credentials_file).as_dict()
