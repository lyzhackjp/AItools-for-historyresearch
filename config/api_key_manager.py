"""
API密钥管理工具

安全地管理API密钥，只从配置文件读取，不在代码中硬编码。
"""

import os
import re
from pathlib import Path
from typing import Optional, Dict


class APIKeyManager:
    """API密钥管理器"""
    
    _instance = None
    _keys_cache = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._keys_cache:
            self._load_keys()
    
    def _find_config_path(self) -> Optional[Path]:
        """查找API密钥配置文件路径"""
        project_root = Path(__file__).parent.parent
        
        config_paths = [
            project_root / 'secrets' / 'api_keys.txt',
            project_root / 'config' / 'api_key.txt',
            Path(__file__).parent / 'api_key.txt',
        ]
        
        for path in config_paths:
            if path.exists():
                return path
        return None
    
    def _load_keys(self):
        """从配置文件加载密钥"""
        config_path = self._find_config_path()
        
        if not config_path:
            print("警告：API密钥配置文件不存在")
            print("请创建 secrets/api_keys.txt 文件（可参考 secrets/api_keys.example.txt）")
            return
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        if value and not value.startswith('your_'):
                            self._keys_cache[key] = value
                            
                            env_key = f"{key.upper().replace('.', '_')}_API_KEY"
                            if not os.environ.get(env_key):
                                os.environ[env_key] = value
                            
        except Exception as e:
            print(f"警告：无法加载API密钥配置文件: {e}")
    
    def get_key(self, service: str) -> Optional[str]:
        """
        获取API密钥
        
        Args:
            service: 服务名称，如 'qwen', 'minimax', 'openai'
            
        Returns:
            Optional[str]: API密钥，如果未找到返回None
        """
        key_mapping = {
            'qwen': ['qwen3.5-plus', 'dashscope', 'DASHSCOPE_API_KEY'],
            'minimax': ['Minimax2.7', 'minimax', 'MINIMAX_API_KEY'],
            'openai': ['openai', 'OPENAI_API_KEY'],
            'zhipu': ['zhipu', 'ZHIPU_API_KEY'],
            'deepseek': ['deepseek', 'DEEPSEEK_API_KEY'],
        }
        
        mappings = key_mapping.get(service.lower(), [])
        
        for key_name in mappings:
            if key_name in self._keys_cache:
                return self._keys_cache[key_name]
        
        env_key = f"{service.upper()}_API_KEY"
        return os.environ.get(env_key)
    
    def get_all_keys(self) -> Dict[str, str]:
        """
        获取所有已加载的密钥
        
        Returns:
            Dict[str, str]: 所有密钥的字典
        """
        return self._keys_cache.copy()
    
    def has_key(self, service: str) -> bool:
        """
        检查是否有指定服务的密钥
        
        Args:
            service: 服务名称
            
        Returns:
            bool: 是否有密钥
        """
        return self.get_key(service) is not None
    
    def set_environment_variables(self):
        """将所有密钥设置为环境变量"""
        for key, value in self._keys_cache.items():
            env_key = f"{key.upper().replace('.', '_')}_API_KEY"
            os.environ[env_key] = value


def get_api_key(service: str) -> Optional[str]:
    """
    便捷函数：获取API密钥
    
    Args:
        service: 服务名称
        
    Returns:
        Optional[str]: API密钥
    """
    manager = APIKeyManager()
    return manager.get_key(service)


def load_all_api_keys():
    """便捷函数：加载所有API密钥并设置环境变量"""
    manager = APIKeyManager()
    manager.set_environment_variables()


if __name__ == '__main__':
    manager = APIKeyManager()
    
    print("已加载的API密钥:")
    for key, value in manager.get_all_keys().items():
        masked_value = value[:10] + '...' if len(value) > 10 else '***'
        print(f"  {key}: {masked_value}")
    
    print("\n检查密钥可用性:")
    print(f"  Qwen: {'✓' if manager.has_key('qwen') else '✗'}")
    print(f"  Minimax: {'✓' if manager.has_key('minimax') else '✗'}")
