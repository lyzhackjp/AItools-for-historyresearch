"""
统一配置管理器

提供统一的配置管理接口，支持配置加载、验证、更新
"""

import os
import json
from pathlib import Path
from typing import Optional, Any, Dict, List

try:
    from config.local_llm_config import get_local_model, get_ollama_base_url
except Exception:  # pragma: no cover
    def get_local_model(role: str = "chat_primary") -> str:
        return "qwen36-27b-academic"

    def get_ollama_base_url() -> str:
        return "http://localhost:11434"


class ConfigManager:
    """
    统一配置管理器 - 单例模式
    
    功能：
    - 统一配置加载
    - 配置验证
    - 配置更新
    - 支持多种配置源
    """
    
    _instance = None
    _initialized = False
    
    @classmethod
    def get_instance(cls, config_file: str = None):
        """
        获取单例实例
        
        Args:
            config_file: 配置文件路径
            
        Returns:
            ConfigManager: 单例实例
        """
        if cls._instance is None:
            cls._instance = cls(config_file)
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """重置单例实例（用于测试）"""
        cls._instance = None
        cls._initialized = False
    
    def __init__(self, config_file: str = None):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径
        """
        if self._initialized:
            return
        
        self.config_file = config_file or self._get_default_config_file()
        self.config = self._load_config()
        self._initialized = True
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键（支持点号分隔的路径）
            default: 默认值
            
        Returns:
            Any: 配置值
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any, save: bool = True):
        """
        设置配置值
        
        Args:
            key: 配置键
            value: 配置值
            save: 是否保存到文件
        """
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        
        if save:
            self._save_config()
    
    def get_api_config(self, provider: str) -> Dict[str, Any]:
        """
        获取API配置
        
        Args:
            provider: API提供商
            
        Returns:
            dict: API配置
        """
        return self.get(f'api_providers.{provider}', {})
    
    def get_search_config(self, platform: str) -> Dict[str, Any]:
        """
        获取搜索配置
        
        Args:
            platform: 搜索平台
            
        Returns:
            dict: 搜索配置
        """
        return self.get(f'search_platforms.{platform}', {})
    
    def get_cache_config(self) -> Dict[str, Any]:
        """
        获取缓存配置
        
        Returns:
            dict: 缓存配置
        """
        return self.get('cache', {})
    
    def get_analysis_config(self) -> Dict[str, Any]:
        """
        获取分析配置
        
        Returns:
            dict: 分析配置
        """
        return self.get('analysis', {})
    
    def get_generation_config(self) -> Dict[str, Any]:
        """
        获取生成配置
        
        Returns:
            dict: 生成配置
        """
        return self.get('generation', {})
    
    def list_providers(self) -> List[str]:
        """
        列出所有API提供商
        
        Returns:
            List[str]: 提供商列表
        """
        return list(self.get('api_providers', {}).keys())
    
    def list_platforms(self) -> List[str]:
        """
        列出所有搜索平台
        
        Returns:
            List[str]: 平台列表
        """
        return list(self.get('search_platforms', {}).keys())
    
    def is_provider_enabled(self, provider: str) -> bool:
        """
        检查API提供商是否启用
        
        Args:
            provider: API提供商
            
        Returns:
            bool: 是否启用
        """
        config = self.get_api_config(provider)
        return config.get('enabled', False)
    
    def is_platform_enabled(self, platform: str) -> bool:
        """
        检查搜索平台是否启用
        
        Args:
            platform: 搜索平台
            
        Returns:
            bool: 是否启用
        """
        config = self.get_search_config(platform)
        return config.get('enabled', False)
    
    def get_all_config(self) -> Dict[str, Any]:
        """
        获取所有配置
        
        Returns:
            dict: 所有配置
        """
        return self.config.copy()
    
    def update_config(self, updates: Dict[str, Any], save: bool = True):
        """
        批量更新配置
        
        Args:
            updates: 更新字典
            save: 是否保存到文件
        """
        def deep_update(base_dict, update_dict):
            for key, value in update_dict.items():
                if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                    deep_update(base_dict[key], value)
                else:
                    base_dict[key] = value
        
        deep_update(self.config, updates)
        
        if save:
            self._save_config()
    
    def validate_config(self) -> Dict[str, Any]:
        """
        验证配置
        
        Returns:
            dict: 验证结果
        """
        errors = []
        warnings = []
        
        if not self.get('api_providers'):
            errors.append("缺少 api_providers 配置")
        
        if not self.get('search_platforms'):
            warnings.append("缺少 search_platforms 配置")
        
        if not self.get('cache'):
            warnings.append("缺少 cache 配置")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def _load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            dict: 配置字典
        """
        if not os.path.exists(self.config_file):
            print(f"[ConfigManager] 配置文件不存在，使用默认配置")
            return self._get_default_config()
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            print(f"[ConfigManager] 已加载配置文件: {self.config_file}")
            return config
            
        except Exception as e:
            print(f"[ConfigManager] 加载配置文件失败: {e}，使用默认配置")
            return self._get_default_config()
    
    def _save_config(self):
        """保存配置文件"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            
            print(f"[ConfigManager] 已保存配置文件: {self.config_file}")
            
        except Exception as e:
            print(f"[ConfigManager] 保存配置文件失败: {e}")
    
    def _get_default_config_file(self) -> str:
        """
        获取默认配置文件路径
        
        Returns:
            str: 配置文件路径
        """
        return os.path.join(
            os.path.dirname(__file__),
            '..',
            'config',
            'default_config.json'
        )
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        获取默认配置
        
        Returns:
            dict: 默认配置
        """
        return {
            'api_providers': {
                'qwen': {
                    'provider': 'dashscope',
                    'model': 'qwen-plus',
                    'api_key_env': 'DASHSCOPE_API_KEY',
                    'enabled': True,
                    'max_tokens': 2000,
                    'temperature': 0.7
                },
                'openai': {
                    'provider': 'openai',
                    'model': 'gpt-4',
                    'api_key_env': 'OPENAI_API_KEY',
                    'enabled': True,
                    'max_tokens': 2000,
                    'temperature': 0.7
                },
                'minimax': {
                    'provider': 'minimax',
                    'model': 'abab6-chat',
                    'api_key_env': 'MINIMAX_API_KEY',
                    'enabled': False,
                    'max_tokens': 2000,
                    'temperature': 0.7
                },
                'zhipu': {
                    'provider': 'zhipu',
                    'model': 'glm-4',
                    'api_key_env': 'ZHIPU_API_KEY',
                    'enabled': False,
                    'max_tokens': 2000,
                    'temperature': 0.7
                },
                'deepseek': {
                    'provider': 'deepseek',
                    'model': 'deepseek-chat',
                    'api_key_env': 'DEEPSEEK_API_KEY',
                    'enabled': False,
                    'max_tokens': 2000,
                    'temperature': 0.7
                },
                'ollama': {
                    'provider': 'ollama',
                    'model': get_local_model('chat_primary'),
                    'base_url': get_ollama_base_url(),
                    'enabled': True,
                    'max_tokens': 4096,
                    'temperature': 0.35
                }
            },
            'search_platforms': {
                'github': {
                    'enabled': True,
                    'base_url': 'https://api.github.com',
                    'rate_limit': 60,
                    'timeout': 30
                },
                'arxiv': {
                    'enabled': True,
                    'base_url': 'http://export.arxiv.org/api/query',
                    'rate_limit': 30,
                    'timeout': 30
                },
                'paperswithcode': {
                    'enabled': True,
                    'base_url': 'https://paperswithcode.com/api/v1',
                    'rate_limit': 30,
                    'timeout': 30
                },
                'crossref': {
                    'enabled': True,
                    'base_url': 'https://api.crossref.org',
                    'rate_limit': 50,
                    'timeout': 25
                }
            },
            'cache': {
                'enabled': True,
                'ttl_days': 7,
                'max_size_mb': 100,
                'auto_cleanup': True
            },
            'analysis': {
                'default_depth': 'deep',
                'max_retries': 3,
                'timeout': 60
            },
            'generation': {
                'default_format': 'markdown',
                'include_metadata': True,
                'max_length': 10000
            },
            'storage': {
                'documents_dir': 'storage/documents',
                'reports_dir': 'storage/reports',
                'cache_dir': 'storage/cache'
            }
        }
    
    def __repr__(self):
        return f"ConfigManager(providers={len(self.list_providers())}, platforms={len(self.list_platforms())})"


def test_config_manager():
    """测试配置管理器"""
    print("\n=== 测试配置管理器 ===\n")
    
    config = ConfigManager.get_instance()
    
    print(f"1. 初始化: {config}")
    
    api_config = config.get_api_config('qwen')
    print(f"\n2. API配置 (qwen): {api_config}")
    
    search_config = config.get_search_config('github')
    print(f"\n3. 搜索配置 (github): {search_config}")
    
    providers = config.list_providers()
    print(f"\n4. API提供商: {providers}")
    
    platforms = config.list_platforms()
    print(f"\n5. 搜索平台: {platforms}")
    
    validation = config.validate_config()
    print(f"\n6. 验证结果: {validation}")
    
    all_config = config.get_all_config()
    print(f"\n7. 所有配置键: {list(all_config.keys())}")
    
    print("\n✅ 测试完成")


if __name__ == '__main__':
    test_config_manager()
