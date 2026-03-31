"""
提示词管理模块

提供统一的提示词加载和管理接口
支持从Markdown文件中提取提示词

主要功能：
- 统一的提示词加载接口
- 支持按模块和ID加载提示词
- 提示词缓存管理
- 模板渲染支持
- 异常处理机制

使用示例：
    from prompts import PromptLoader, load_prompt, get_all_prompts
    
    # 方式1：使用类
    loader = PromptLoader()
    prompt = loader.load_prompt('module_name', 'PROMPT_ID')
    
    # 方式2：使用快捷函数
    prompt = load_prompt('module_name', 'PROMPT_ID')
"""

from .prompt_loader import (
    PromptLoader,
    PromptTemplate,
    PromptFileNotFoundError,
    PromptNotFoundError,
    PromptFormatError,
    create_prompt_loader,
    get_global_loader,
    load_prompt,
    get_all_prompts
)

__version__ = '1.0.0'
__all__ = [
    'PromptLoader',
    'PromptTemplate',
    'PromptFileNotFoundError',
    'PromptNotFoundError',
    'PromptFormatError',
    'create_prompt_loader',
    'get_global_loader',
    'load_prompt',
    'get_all_prompts',
]
