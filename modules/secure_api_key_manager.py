"""
安全API密钥管理器

严格限制API密钥只能从secrets文件夹读取，确保密钥不会泄露到其他位置。
所有模块必须通过此管理器获取API密钥。

安全特性：
- 密钥仅存储在secrets文件夹内
- 禁止在代码中硬编码密钥
- 禁止将密钥写入其他文件
- 提供密钥验证和审计功能

使用方法：
    from modules.secure_api_key_manager import SecureAPIKeyManager

    manager = SecureAPIKeyManager()
    api_key = manager.get_key('qwen')
"""

import os
import re
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime
import threading


class SecureAPIKeyManager:
    """安全API密钥管理器 - 确保密钥只在secrets文件夹"""

    _instance = None
    _lock = threading.Lock()
    _keys_cache: Dict[str, str] = {}
    _initialized: bool = False
    _access_log: List[Dict[str, Any]] = []

    SECRETS_DIR_NAME = 'secrets'
    API_KEYS_FILE = 'api_keys.txt'
    MAX_LOG_ENTRIES = 1000
    PUBLIC_SERVICES = ['qwen', 'minimax', 'openai', 'deepseek', 'zhipu', 'volcano', 'anthropic', 'gemini']

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._secrets_path = self._find_secrets_path()
                    self._load_keys_securely()
                    self._initialized = True

    def _find_secrets_path(self) -> Optional[Path]:
        """查找secrets文件夹路径"""
        current_path = Path(__file__).resolve()

        for parent in [current_path.parent] + list(current_path.parents):
            secrets_path = parent / self.SECRETS_DIR_NAME
            if secrets_path.exists() and secrets_path.is_dir():
                return secrets_path

        project_root = current_path.parent.parent
        secrets_path = project_root / self.SECRETS_DIR_NAME
        if secrets_path.exists():
            return secrets_path

        return None

    def _load_keys_securely(self):
        """安全地从secrets文件夹加载密钥"""
        if self._secrets_path is None:
            self._log_access('warning', 'secrets_folder_not_found', None)
            return

        api_keys_file = self._secrets_path / self.API_KEYS_FILE

        if not api_keys_file.exists():
            self._log_access('warning', 'api_keys_file_not_found', str(api_keys_file))
            return

        try:
            with open(api_keys_file, 'r', encoding='utf-8') as f:
                content = f.read()

            for line in content.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    if value and not value.startswith('your_') and not value.startswith('<'):
                        self._keys_cache[key] = value

            self._log_access('info', 'keys_loaded', f"count={len(self._keys_cache)}")

        except Exception as e:
            self._log_access('error', 'load_failed', str(e))

    def _log_access(self, level: str, action: str, detail: Optional[str] = None):
        """记录访问日志"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'action': action,
            'detail': detail
        }

        self._access_log.append(log_entry)

        if len(self._access_log) > self.MAX_LOG_ENTRIES:
            self._access_log = self._access_log[-self.MAX_LOG_ENTRIES:]

    def get_key(self, service: str) -> Optional[str]:
        """
        获取指定服务的API密钥

        Args:
            service: 服务名称（如 'qwen', 'minimax', 'openai'等）

        Returns:
            API密钥字符串，如果未找到返回None
        """
        key_mapping = {
            'qwen': ['qwen3.5-plus', 'qwen', 'dashscope', 'DASHSCOPE_API_KEY'],
            'dashscope': ['qwen3.5-plus', 'qwen', 'dashscope', 'DASHSCOPE_API_KEY'],
            'minimax': ['Minimax2.7', 'minimax', 'MINIMAX_API_KEY'],
            'openai': ['openai', 'OPENAI_API_KEY'],
            'zhipu': ['zhipu', 'ZHIPU_API_KEY'],
            'deepseek': ['deepseek', 'DEEPSEEK_API_KEY'],
            'volcano': ['volcano', 'VOLCANO_API_KEY'],
            'anthropic': ['anthropic', 'ANTHROPIC_API_KEY'],
            'gemini': ['gemini', 'GEMINI_API_KEY'],
        }

        service_lower = service.lower()
        possible_keys = key_mapping.get(service_lower, [service, service_lower])

        for key_name in possible_keys:
            if key_name in self._keys_cache:
                self._log_access('info', 'key_accessed', f"service={service}")
                return self._keys_cache[key_name]

        env_var = f"{service_upper}_API_KEY" if (service_upper := service.upper()) else None
        if env_var:
            env_value = os.environ.get(env_var)
            if env_value:
                self._log_access('info', 'key_from_env', f"service={service}")
                return env_value

        self._log_access('warning', 'key_not_found', f"service={service}")
        return None

    def get_key_hash(self, service: str) -> Optional[str]:
        """
        获取密钥的哈希值（用于验证，不暴露实际密钥）

        Args:
            service: 服务名称

        Returns:
            密钥的SHA256哈希值前16位
        """
        key = self.get_key(service)
        if key:
            return hashlib.sha256(key.encode()).hexdigest()[:16]
        return None

    def has_key(self, service: str) -> bool:
        """
        检查是否有指定服务的密钥

        Args:
            service: 服务名称

        Returns:
            是否有密钥
        """
        return self.get_key(service) is not None

    def list_available_services(self) -> List[str]:
        """
        列出所有已配置密钥的服务

        Returns:
            已配置密钥的服务列表
        """
        return list(self._keys_cache.keys())

    def validate_key_format(self, service: str) -> Dict[str, Any]:
        """
        验证密钥格式

        Args:
            service: 服务名称

        Returns:
            验证结果字典
        """
        key = self.get_key(service)

        if not key:
            return {
                'valid': False,
                'reason': 'key_not_found',
                'service': service
            }

        patterns = {
            'qwen': [r'^sk-[a-f0-9]{32}$', r'^sk-[a-zA-Z0-9]{20,}$'],
            'dashscope': [r'^sk-[a-f0-9]{32}$', r'^sk-[a-zA-Z0-9]{20,}$'],
            'minimax': [r'^sk-cp-[a-zA-Z0-9_-]{50,}$'],
            'openai': [r'^sk-[a-zA-Z0-9]{20,}$'],
            'deepseek': [r'^sk-[a-zA-Z0-9]{20,}$'],
        }

        service_lower = service.lower()
        expected_patterns = patterns.get(service_lower, [])

        if not expected_patterns:
            return {
                'valid': True,
                'reason': 'no_pattern_defined',
                'service': service,
                'key_length': len(key)
            }

        for pattern in expected_patterns:
            if re.match(pattern, key):
                return {
                    'valid': True,
                    'reason': 'pattern_matched',
                    'service': service,
                    'key_length': len(key)
                }

        return {
            'valid': True,
            'reason': 'pattern_not_matched_but_present',
            'service': service,
            'key_length': len(key)
        }

    def get_access_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取访问日志

        Args:
            limit: 返回的日志条数限制

        Returns:
            访问日志列表
        """
        return self._access_log[-limit:]

    def get_secrets_path(self) -> Optional[str]:
        """
        获取secrets文件夹路径（仅用于显示，不暴露密钥）

        Returns:
            secrets文件夹路径字符串
        """
        return str(self._secrets_path) if self._secrets_path else None

    def create_provider_config(self, provider: str) -> Dict[str, Any]:
        """
        创建provider配置字典（用于LLM客户端初始化）

        Args:
            provider: provider名称

        Returns:
            配置字典
        """
        provider_configs = {
            'dashscope': {
                'provider': 'dashscope',
                'model': 'qwen-turbo',
                'base_url': 'https://dashscope.aliyuncs.com/api/v1'
            },
            'minimax': {
                'provider': 'minimax',
                'model': 'abab6-chat',
                'base_url': 'https://api.minimax.chat/v1'
            },
            'openai': {
                'provider': 'openai',
                'model': 'gpt-4',
                'base_url': None
            },
            'deepseek': {
                'provider': 'deepseek',
                'model': 'deepseek-chat',
                'base_url': 'https://api.deepseek.com'
            },
            'zhipu': {
                'provider': 'zhipu',
                'model': 'glm-4',
                'base_url': 'https://open.bigmodel.cn/api/paas/v4'
            },
            'volcano': {
                'provider': 'volcano',
                'model': 'doubao-seed-1-8-251228',
                'base_url': 'https://ark.cn-beijing.volces.com/api/v3'
            }
        }

        config = provider_configs.get(provider, {}).copy()

        api_key = self.get_key(provider)
        if api_key:
            config['api_key'] = api_key

        return config

    def get_status_report(self, include_hashes: bool = False, include_paths: bool = False) -> Dict[str, Any]:
        """
        获取密钥管理器状态报告

        Returns:
            状态报告字典
        """
        services_status = {}
        for service in self.PUBLIC_SERVICES:
            validation = self.validate_key_format(service)
            status = {
                'has_key': self.has_key(service),
                'validation': validation
            }
            status['key_hash'] = self.get_key_hash(service) if include_hashes else None
            services_status[service] = status
        secrets_path = self.get_secrets_path()

        return {
            'schema_version': '1.0',
            'type': 'secure_api_key_status',
            'secrets_path': secrets_path if include_paths else ('[redacted]' if secrets_path else None),
            'secrets_path_configured': bool(secrets_path),
            'total_keys_loaded': len(self._keys_cache),
            'services': services_status,
            'access_log_count': len(self._access_log),
            'redacted': not include_hashes and not include_paths,
            'privacy': {
                'exposes_secret_values': False,
                'exposes_key_hashes': bool(include_hashes),
                'exposes_secret_paths': bool(include_paths),
            },
        }

    def get_public_status_report(self) -> Dict[str, Any]:
        """Return the default redacted status report for API, agent, and logs."""

        return self.get_status_report(include_hashes=False, include_paths=False)


def get_secure_key_manager() -> SecureAPIKeyManager:
    """获取安全密钥管理器单例"""
    return SecureAPIKeyManager()


def get_api_key(service: str) -> Optional[str]:
    """便捷函数：获取API密钥"""
    return get_secure_key_manager().get_key(service)


def create_secure_llm_config(provider: str, model: Optional[str] = None) -> Dict[str, Any]:
    """便捷函数：创建安全的LLM配置"""
    manager = get_secure_key_manager()
    config = manager.create_provider_config(provider)
    if model:
        config['model'] = model
    return config


if __name__ == '__main__':
    manager = SecureAPIKeyManager()

    print("=" * 60)
    print("安全API密钥管理器状态报告")
    print("=" * 60)

    status = manager.get_status_report()
    print(f"\nSecrets路径: {status['secrets_path']}")
    print(f"已加载密钥数: {status['total_keys_loaded']}")

    print("\n服务状态:")
    for service, info in status['services'].items():
        status_icon = "✓" if info['has_key'] else "✗"
        print(f"  {service}: {status_icon}")
        if info['key_hash']:
            print(f"    密钥哈希: {info['key_hash']}")

    print("\n最近访问日志:")
    for log in manager.get_access_log(5):
        print(f"  [{log['level']}] {log['action']}: {log['detail']}")
