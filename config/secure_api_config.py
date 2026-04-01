# API密钥安全配置模块
# 此文件用于安全地加载和管理API密钥

import os
import json
from pathlib import Path
from typing import Dict, Optional

class SecureApiKeyManager:
    _instance = None
    _keys: Dict[str, str] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_keys()
        return cls._instance
    
    def _load_keys(self):
        secrets_path = Path(__file__).parent.parent / 'secrets' / 'api_keys.txt'
        if secrets_path.exists():
            with open(secrets_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key_name, key_value = line.split('=', 1)
                        key_name = key_name.strip().lower().replace('.', '_')
                        key_value = key_value.strip()
                        if key_value:
                            self._keys[key_name] = key_value
    
    def get_key(self, provider: str) -> Optional[str]:
        provider = provider.lower().replace('-', '_').replace('.', '_')
        return self._keys.get(provider)
    
    def has_key(self, provider: str) -> bool:
        return self.get_key(provider) is not None
    
    def get_all_providers(self) -> list:
        return list(self._keys.keys())

api_key_manager = SecureApiKeyManager()

def get_api_key(provider: str) -> Optional[str]:
    return api_key_manager.get_key(provider)

def has_api_key(provider: str) -> bool:
    return api_key_manager.has_key(provider)
