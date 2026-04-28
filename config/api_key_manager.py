"""Compatibility wrapper around the secure API key manager."""

import os
from typing import Dict, Optional

from modules.secure_api_key_manager import get_secure_key_manager


class APIKeyManager:
    """Backwards-compatible adapter that delegates to SecureAPIKeyManager."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._manager = get_secure_key_manager()
        return cls._instance

    def get_key(self, service: str) -> Optional[str]:
        return self._manager.get_key(service)

    def get_all_keys(self) -> Dict[str, str]:
        return dict(self._manager._keys_cache)

    def has_key(self, service: str) -> bool:
        return self._manager.has_key(service)

    def get_status_report(self) -> Dict[str, object]:
        return self._manager.get_public_status_report()

    def get_all_key_status(self) -> Dict[str, object]:
        return self.get_status_report()

    def set_environment_variables(self):
        for key, value in self.get_all_keys().items():
            env_key = f"{key.upper().replace('.', '_')}_API_KEY"
            os.environ[env_key] = value


def get_api_key(service: str) -> Optional[str]:
    return APIKeyManager().get_key(service)


def load_all_api_keys():
    APIKeyManager().set_environment_variables()
