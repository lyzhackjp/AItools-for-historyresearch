"""
AI史学工具 - 配置辅助工具

提供配置相关的辅助函数和工具类
用于简化配置的使用和维护

使用示例：
    from config.config_helpers import create_client_with_config, validate_environment

    # 创建配置验证的客户端
    client = create_client_with_config('academic_note_generator')

    # 验证环境配置
    validate_environment()
"""

import os
from typing import Dict, Any, Optional
from pathlib import Path


def create_client_with_config(module_name: Optional[str] = None,
                              provider: Optional[str] = None) -> 'LLMClient':
    """
    使用统一配置创建LLM客户端

    Args:
        module_name: 模块名称（可选）
        provider: provider名称（可选）

    Returns:
        LLMClient: 配置好的客户端实例
    """
    try:
        from config.api_config_loader import create_llm_config
        config = create_llm_config(provider=provider, module_name=module_name)
        return create_llm_client(config)
    except ImportError:
        print("警告: 无法导入配置加载器，使用默认配置")
        return None


def validate_environment() -> Dict[str, Any]:
    """
    验证运行环境配置

    Returns:
        dict: 验证结果
    """
    results = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'info': {}
    }

    config_dir = Path(__file__).parent
    production_config = config_dir / 'api_config.json'
    test_config = config_dir / 'api_config.test.json'

    if not production_config.exists():
        results['valid'] = False
        results['errors'].append(f"生产环境配置文件不存在: {production_config}")

    if not test_config.exists():
        results['warnings'].append(f"测试环境配置文件不存在: {test_config}")

    environment = os.getenv('API_ENV', 'production')
    results['info']['environment'] = environment

    api_key_vars = [
        'OPENAI_API_KEY',
        'DASHSCOPE_API_KEY',
        'MINIMAX_API_KEY',
        'ANTHROPIC_API_KEY'
    ]

    configured_keys = []
    missing_keys = []

    for var in api_key_vars:
        if os.getenv(var):
            configured_keys.append(var)
        else:
            missing_keys.append(var)

    results['info']['configured_api_keys'] = configured_keys
    results['info']['missing_api_keys'] = missing_keys

    if not configured_keys:
        results['warnings'].append("未配置任何API密钥，请设置环境变量或配置文件")

    return results


def print_config_status():
    """打印配置状态"""
    print("=" * 60)
    print("AI史学工具 - 配置状态")
    print("=" * 60)
    print()

    validation = validate_environment()

    print(f"环境: {validation['info'].get('environment', 'unknown')}")
    print()

    print("已配置的API密钥:")
    if validation['info'].get('configured_api_keys'):
        for key in validation['info']['configured_api_keys']:
            print(f"  ✓ {key}")
    else:
        print("  ✗ 无")
    print()

    print("未配置的API密钥:")
    if validation['info'].get('missing_api_keys'):
        for key in validation['info']['missing_api_keys']:
            print(f"  - {key}")
    print()

    if validation['errors']:
        print("错误:")
        for error in validation['errors']:
            print(f"  ✗ {error}")
        print()

    if validation['warnings']:
        print("警告:")
        for warning in validation['warnings']:
            print(f"  ⚠ {warning}")
        print()

    print("=" * 60)


def get_config_file_path(environment: str = 'production') -> Path:
    """
    获取配置文件路径

    Args:
        environment: 环境名称

    Returns:
        Path: 配置文件路径
    """
    config_dir = Path(__file__).parent

    if environment == 'test':
        return config_dir / 'api_config.test.json'
    else:
        return config_dir / 'api_config.json'


def switch_environment(environment: str) -> bool:
    """
    切换运行环境

    Args:
        environment: 环境名称 ('production' 或 'test')

    Returns:
        bool: 是否切换成功
    """
    if environment not in ['production', 'test']:
        print(f"错误: 无效的环境名称 '{environment}'")
        return False

    os.environ['API_ENV'] = environment

    print(f"环境已切换为: {environment}")

    if environment == 'test':
        print("注意: 测试环境使用模拟数据，不会调用真实API")
    else:
        print("注意: 生产环境将调用真实API，请确保已配置API密钥")

    return True


def list_available_providers() -> list:
    """
    列出所有可用的provider

    Returns:
        list: provider列表
    """
    try:
        from config.api_config_loader import get_config
        config = get_config()
        providers = config.get('providers', {})

        available = []
        for name, settings in providers.items():
            if settings.get('enabled', False):
                available.append({
                    'name': name,
                    'default_model': settings.get('default_model', 'N/A'),
                    'base_url': settings.get('base_url', 'N/A')
                })

        return available
    except Exception as e:
        print(f"获取provider列表失败: {e}")
        return []


def print_provider_info():
    """打印provider信息"""
    print("=" * 60)
    print("AI史学工具 - 可用AI服务提供商")
    print("=" * 60)
    print()

    providers = list_available_providers()

    if not providers:
        print("未找到可用的provider")
        return

    for i, provider in enumerate(providers, 1):
        print(f"{i}. {provider['name'].upper()}")
        print(f"   默认模型: {provider['default_model']}")
        print(f"   API地址: {provider['base_url']}")
        print()

    print("=" * 60)


def setup_environment_variables_from_file(file_path: str) -> bool:
    """
    从文件设置环境变量

    Args:
        file_path: 包含环境变量的文件路径

    Returns:
        bool: 是否设置成功
    """
    env_file = Path(file_path)

    if not env_file.exists():
        print(f"错误: 文件不存在 {file_path}")
        return False

    loaded_count = 0

    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()

                if not line or line.startswith('#'):
                    continue

                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    if value and not value.startswith('#'):
                        os.environ[key] = value
                        loaded_count += 1

        print(f"成功加载 {loaded_count} 个环境变量")
        return True

    except Exception as e:
        print(f"加载环境变量失败: {e}")
        return False


def create_env_file_from_template(template_path: Optional[str] = None,
                                  output_path: str = '.env') -> bool:
    """
    从模板创建.env文件

    Args:
        template_path: 模板文件路径
        output_path: 输出文件路径

    Returns:
        bool: 是否创建成功
    """
    if template_path is None:
        config_dir = Path(__file__).parent
        template_path = config_dir / 'api_config.json'
    else:
        template_path = Path(template_path)

    if not template_path.exists():
        print(f"错误: 模板文件不存在 {template_path}")
        return False

    try:
        import json

        with open(template_path, 'r', encoding='utf-8-sig') as f:
            config = json.load(f)

        env_vars = []

        for provider_name, provider_config in config.get('providers', {}).items():
            api_key_env = provider_config.get('api_key_env')
            if api_key_env:
                env_vars.append(f"{api_key_env}=")

        env_vars.append("")
        env_vars.append("# API设置")
        env_vars.append(f"API_ENV={config.get('environment', {}).get('name', 'production')}")

        env_vars.append("")
        env_vars.append("# LLM设置")
        env_vars.append(f"DEFAULT_PROVIDER={config.get('modules', {}).get('academic_note_generator', {}).get('provider', 'dashscope')}")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(env_vars))

        print(f"成功创建 .env 文件: {output_path}")
        print("请编辑文件填入您的API密钥")
        return True

    except Exception as e:
        print(f"创建.env文件失败: {e}")
        return False


from modules.llm_client import create_llm_client, LLMClient
