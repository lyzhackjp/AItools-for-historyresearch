"""
AI史学工具 - 统一API配置加载器

提供统一的配置管理接口，支持生产环境和测试环境的切换
所有模块应通过此加载器获取配置，确保配置的一致性和可维护性

核心功能：
- 环境切换（生产/测试）
- 配置验证
- 配置缓存
- 环境变量覆盖
- 配置热更新

使用示例：
    from config.api_config_loader import get_config, get_provider_config, load_config

    # 获取配置实例
    config = get_config()

    # 获取特定provider配置
    provider_config = get_provider_config('dashscope')

    # 加载指定环境配置
    test_config = load_config('test')
"""

import os
import json
import copy
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class APIConfigLoader:
    """统一API配置加载器"""

    _instance = None
    _config = None
    _environment = None

    CONFIG_DIR = Path(__file__).parent
    PRODUCTION_CONFIG = "api_config.json"
    TEST_CONFIG = "api_config.test.json"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化配置加载器"""
        if self._config is None:
            self._load_default_config()

    def _load_default_config(self):
        """加载默认配置"""
        environment = os.getenv('API_ENV', 'production')
        self.load_config(environment)

    def load_config(self, environment: str = 'production') -> Dict[str, Any]:
        """
        加载指定环境的配置

        Args:
            environment: 环境名称 ('production' 或 'test')

        Returns:
            dict: 配置字典
        """
        if environment == 'test':
            config_file = self.TEST_CONFIG
        else:
            config_file = self.PRODUCTION_CONFIG

        config_path = self.CONFIG_DIR / config_file

        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(config_path, 'r', encoding='utf-8-sig') as f:
            self._config = json.load(f)

        self._environment = environment

        self._apply_env_overrides()

        self._validate_config()

        return self._config

    def _apply_env_overrides(self):
        """应用环境变量覆盖"""
        if self._config is None:
            return

        # Keep tracked/public config values as env-var names. Secret values are
        # read directly by client creation helpers and must not be copied into
        # the in-memory config, because that config can be exported for review.

        if os.getenv('API_TIMEOUT'):
            self._set_nested_value(
                ['api', 'base_settings', 'timeout'],
                int(os.getenv('API_TIMEOUT'))
            )

        if os.getenv('DEFAULT_PROVIDER'):
            self._set_nested_value(
                ['environment', 'default_provider'],
                os.getenv('DEFAULT_PROVIDER')
            )

    def _set_nested_value(self, path: List[str], value: Any):
        """设置嵌套配置值"""
        if self._config is None:
            return

        config = self._config
        for key in path[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        config[path[-1]] = value

    def _validate_config(self):
        """验证配置有效性"""
        if self._config is None:
            return

        required_sections = ['environment', 'api', 'providers', 'modules']
        for section in required_sections:
            if section not in self._config:
                raise ValueError(f"配置缺少必需部分: {section}")

        required_api_settings = ['base_settings', 'headers', 'authentication']
        for setting in required_api_settings:
            if setting not in self._config.get('api', {}):
                raise ValueError(f"API配置缺少必需设置: {setting}")

    def get_config(self, reload: bool = False) -> Dict[str, Any]:
        """
        获取当前配置

        Args:
            reload: 是否强制重新加载

        Returns:
            dict: 配置字典
        """
        if self._config is None or reload:
            self._load_default_config()

        return copy.deepcopy(self._config)

    def get_environment(self) -> str:
        """获取当前环境名称"""
        return self._environment or 'production'

    def is_production(self) -> bool:
        """检查是否为生产环境"""
        return self.get_environment() == 'production'

    def is_test(self) -> bool:
        """检查是否为测试环境"""
        return self.get_environment() == 'test'

    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """
        获取特定provider的配置

        Args:
            provider: provider名称

        Returns:
            dict: provider配置
        """
        config = self.get_config()
        providers = config.get('providers', {})

        if provider not in providers:
            raise ValueError(f"未知的provider: {provider}")

        return copy.deepcopy(providers[provider])

    def get_module_config(self, module_name: str) -> Dict[str, Any]:
        """
        获取特定模块的配置

        Args:
            module_name: 模块名称

        Returns:
            dict: 模块配置
        """
        config = self.get_config()
        modules = config.get('modules', {})

        if module_name not in modules:
            return {}

        return copy.deepcopy(modules[module_name])

    def get_api_settings(self) -> Dict[str, Any]:
        """获取API通用设置"""
        config = self.get_config()
        return copy.deepcopy(config.get('api', {}))

    def get_timeout(self) -> int:
        """获取请求超时时间"""
        config = self.get_config()
        return config.get('api', {}).get('base_settings', {}).get('timeout', 60)

    def get_max_retries(self) -> int:
        """获取最大重试次数"""
        config = self.get_config()
        return config.get('api', {}).get('base_settings', {}).get('max_retries', 3)

    def get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        config = self.get_config()
        headers = config.get('api', {}).get('headers', {})

        result = {k: v for k, v in headers.items() if not k.startswith('_')}

        return result

    def get_rate_limit_settings(self) -> Dict[str, Any]:
        """获取速率限制设置"""
        config = self.get_config()
        return copy.deepcopy(
            config.get('api', {}).get('rate_limiting', {})
        )

    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        config = self.get_config()
        return copy.deepcopy(config.get('logging', {}))

    def get_monitoring_config(self) -> Dict[str, Any]:
        """获取监控配置"""
        config = self.get_config()
        return copy.deepcopy(config.get('monitoring', {}))

    def is_module_test_mode(self, module_name: str) -> bool:
        """
        检查模块是否处于测试模式

        Args:
            module_name: 模块名称

        Returns:
            bool: 是否测试模式
        """
        module_config = self.get_module_config(module_name)
        return module_config.get('test_mode', False)

    def get_default_provider(self) -> str:
        """获取默认provider"""
        config = self.get_config()
        modules = config.get('modules', {})

        for module_name in ['academic_note_generator', 'academic_summarizer']:
            if module_name in modules:
                return modules[module_name].get('provider', 'dashscope')

        return 'dashscope'

    def get_model_for_provider(self, provider: str) -> str:
        """
        获取provider的默认模型

        Args:
            provider: provider名称

        Returns:
            str: 模型名称
        """
        provider_config = self.get_provider_config(provider)
        return provider_config.get('default_model', 'gpt-4')

    def export_config(self, output_path: Optional[str] = None) -> str:
        """
        导出当前配置（不包含注释）

        Args:
            output_path: 输出文件路径（可选）

        Returns:
            str: JSON格式的配置字符串
        """
        config = self.get_config()

        config_clean = self._remove_comments(config)

        json_str = json.dumps(config_clean, ensure_ascii=False, indent=2)

        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(json_str)

        return json_str

    def _remove_comments(self, obj: Any) -> Any:
        """递归移除配置中的注释字段"""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if not key.startswith('_'):
                    result[key] = self._remove_comments(value)
            return result
        elif isinstance(obj, list):
            return [self._remove_comments(item) for item in obj]
        else:
            return obj

    def validate_api_keys(self) -> Dict[str, bool]:
        """
        验证API密钥是否已配置

        Returns:
            dict: 各provider的密钥配置状态
        """
        validation_results = {}

        providers = ['openai', 'dashscope', 'minimax', 'anthropic', 'gemini', 'deepseek', 'volcano']

        for provider in providers:
            try:
                provider_config = self.get_provider_config(provider)

                if not provider_config.get('enabled', False):
                    validation_results[provider] = None
                    continue

                env_var = provider_config.get('api_key_env')

                if env_var:
                    api_key = os.getenv(env_var)
                    validation_results[provider] = bool(api_key and len(api_key) > 0)
                else:
                    validation_results[provider] = None

            except Exception:
                validation_results[provider] = None

        return validation_results

    def get_environment_info(self) -> Dict[str, Any]:
        """
        获取环境信息

        Returns:
            dict: 环境信息
        """
        config = self.get_config()

        return {
            'environment': self.get_environment(),
            'is_production': self.is_production(),
            'is_test': self.is_test(),
            'debug': config.get('environment', {}).get('debug', False),
            'version': config.get('_version', 'unknown'),
            'created': config.get('_created', 'unknown')
        }


_global_loader = None

def get_config(reload: bool = False) -> Dict[str, Any]:
    """
    获取当前配置的全局函数

    Args:
        reload: 是否强制重新加载

    Returns:
        dict: 配置字典
    """
    global _global_loader

    if _global_loader is None:
        _global_loader = APIConfigLoader()

    return _global_loader.get_config(reload=reload)


def get_provider_config(provider: str) -> Dict[str, Any]:
    """
    获取特定provider配置的全局函数

    Args:
        provider: provider名称

    Returns:
        dict: provider配置
    """
    global _global_loader

    if _global_loader is None:
        _global_loader = APIConfigLoader()

    return _global_loader.get_provider_config(provider)


def load_config(environment: str = 'production') -> Dict[str, Any]:
    """
    加载指定环境配置的全局函数

    Args:
        environment: 环境名称

    Returns:
        dict: 配置字典
    """
    global _global_loader

    if _global_loader is None:
        _global_loader = APIConfigLoader()

    return _global_loader.load_config(environment)


def get_environment() -> str:
    """获取当前环境名称"""
    global _global_loader

    if _global_loader is None:
        _global_loader = APIConfigLoader()

    return _global_loader.get_environment()


def is_test_environment() -> bool:
    """检查是否为测试环境"""
    return get_environment() == 'test'


def is_production_environment() -> bool:
    """检查是否为生产环境"""
    return get_environment() == 'production'


def get_timeout() -> int:
    """获取请求超时时间"""
    return get_config().get('api', {}).get('base_settings', {}).get('timeout', 60)


def get_headers() -> Dict[str, str]:
    """获取请求头"""
    return get_config().get('api', {}).get('headers', {})


def get_max_retries() -> int:
    """获取最大重试次数"""
    return get_config().get('api', {}).get('base_settings', {}).get('max_retries', 3)


def create_llm_config(provider: Optional[str] = None,
                     module_name: Optional[str] = None) -> Dict[str, Any]:
    """
    创建LLM客户端配置

    Args:
        provider: provider名称（可选）
        module_name: 模块名称（可选）

    Returns:
        dict: LLM配置字典
    """
    config = get_config()

    if provider is None:
        if module_name:
            module_config = get_config().get('modules', {}).get(module_name, {})
            provider = module_config.get('provider', 'dashscope')
        else:
            provider = 'dashscope'

    provider_config = get_provider_config(provider)

    env_var = provider_config.get('api_key_env')
    api_key = os.getenv(env_var) if env_var else None

    if module_name:
        module_config = get_config().get('modules', {}).get(module_name, {})
        model = module_config.get('model', provider_config.get('default_model'))
        temperature = module_config.get('temperature', 0.7)
        max_tokens = module_config.get('max_tokens', 2000)
    else:
        model = provider_config.get('default_model')
        temperature = 0.7
        max_tokens = 2000

    base_settings = config.get('api', {}).get('base_settings', {})

    llm_config = {
        'provider': provider,
        'model': model,
        'api_key': api_key,
        'base_url': provider_config.get('base_url'),
        'max_retries': base_settings.get('max_retries', 3),
        'retry_delay': base_settings.get('retry_delay', 1),
        'timeout': base_settings.get('timeout', 60),
        'temperature': temperature,
        'max_tokens': max_tokens,
        'stream': provider_config.get('stream', True)
    }

    return {k: v for k, v in llm_config.items() if v is not None}
