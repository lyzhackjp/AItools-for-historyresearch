"""
提示词加载器模块

提供统一的提示词加载和管理接口
支持从Markdown文件中提取提示词

核心功能：
- 加载指定模块的提示词
- 按标识符提取单个提示词
- 获取模块所有提示词
- 提示词格式验证
- 缓存管理

使用示例：
    from prompts.prompt_loader import PromptLoader
    
    loader = PromptLoader()
    system_prompt = loader.load_prompt('academic_note_generator', 'AN_G001')
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, Optional, List, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PromptFileNotFoundError(FileNotFoundError):
    """提示词文件未找到异常"""
    pass


class PromptNotFoundError(Exception):
    """提示词未找到异常"""
    pass


class PromptFormatError(Exception):
    """提示词格式错误异常"""
    pass


class PromptLoader:
    """提示词加载器"""
    
    DEFAULT_PROMPTS_DIR = "modules/prompts"
    
    PROMPT_ID_PATTERN = re.compile(r'###?\s*\[([A-Z_0-9]+)\]')
    CONTENT_BLOCK_PATTERN = re.compile(r'\n```\s*[\w]*\s*\n(.*?)```', re.DOTALL)
    
    def __init__(self, prompts_dir: Optional[str] = None):
        """
        初始化提示词加载器
        
        Args:
            prompts_dir: 提示词文件目录路径，默认为 modules/prompts
        """
        self.prompts_dir = Path(prompts_dir) if prompts_dir else Path(self.DEFAULT_PROMPTS_DIR)
        self._cache: Dict[str, Dict[str, str]] = {}
        self._cache_enabled = True
        
        if not self.prompts_dir.exists():
            logger.warning(f"提示词目录不存在: {self.prompts_dir}")
    
    def load_prompt(self, module_name: str, prompt_id: str, use_cache: bool = True) -> str:
        """
        加载指定模块的单个提示词
        
        Args:
            module_name: 模块名称（对应文件名，如 'academic_note_generator'）
            prompt_id: 提示词唯一标识符（如 'AN_G001'）
            use_cache: 是否使用缓存
            
        Returns:
            str: 提示词内容
            
        Raises:
            PromptFileNotFoundError: 提示词文件不存在
            PromptNotFoundError: 指定的提示词未找到
            PromptFormatError: 提示词格式错误
        """
        cache_key = f"{module_name}:{prompt_id}"
        
        if use_cache and self._cache_enabled and cache_key in self._cache:
            logger.debug(f"从缓存加载提示词: {cache_key}")
            return self._cache[cache_key]
        
        prompts = self.get_all_prompts(module_name, use_cache=False)
        
        if prompt_id not in prompts:
            raise PromptNotFoundError(
                f"未找到提示词 '{prompt_id}' 在模块 '{module_name}' 中。"
                f"可用提示词: {list(prompts.keys())}"
            )
        
        prompt_content = prompts[prompt_id]
        
        if self._cache_enabled:
            self._cache[cache_key] = prompt_content
        
        return prompt_content
    
    def get_all_prompts(self, module_name: str, use_cache: bool = True) -> Dict[str, str]:
        """
        获取模块的所有提示词
        
        Args:
            module_name: 模块名称
            use_cache: 是否使用缓存
            
        Returns:
            Dict[str, str]: 提示词字典，键为提示词ID，值为提示词内容
        """
        cache_key = f"{module_name}:all"
        
        if use_cache and self._cache_enabled and cache_key in self._cache:
            logger.debug(f"从缓存加载所有提示词: {module_name}")
            return self._cache[cache_key]
        
        md_file = self._get_module_prompt_file(module_name)
        
        if not md_file.exists():
            raise PromptFileNotFoundError(
                f"模块 '{module_name}' 的提示词文件不存在: {md_file}"
            )
        
        prompts = self._parse_prompt_file(md_file)
        
        if self._cache_enabled:
            self._cache[cache_key] = prompts
            
            for prompt_id, content in prompts.items():
                self._cache[f"{module_name}:{prompt_id}"] = content
        
        return prompts
    
    def get_prompt_metadata(self, module_name: str, prompt_id: str) -> Dict[str, Any]:
        """
        获取提示词的元数据信息
        
        Args:
            module_name: 模块名称
            prompt_id: 提示词ID
            
        Returns:
            Dict: 包含描述、使用场景等元数据的字典
        """
        md_file = self._get_module_prompt_file(module_name)
        
        if not md_file.exists():
            raise PromptFileNotFoundError(f"提示词文件不存在: {md_file}")
        
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        pattern = rf'###\s*\[{prompt_id}\].*?(?=\n###|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            raise PromptNotFoundError(f"未找到提示词 '{prompt_id}' 的元数据")
        
        section = match.group(0)
        
        metadata = {}
        
        desc_match = re.search(r'\*\*描述\*\*:\s*(.+)', section)
        if desc_match:
            metadata['description'] = desc_match.group(1).strip()
        
        scenario_match = re.search(r'\*\*使用场景\*\*:\s*(.+)', section)
        if scenario_match:
            metadata['use_case'] = scenario_match.group(1).strip()
        
        content_match = self.CONTENT_BLOCK_PATTERN.search(section)
        if content_match:
            metadata['content'] = content_match.group(1).strip()
        
        return metadata
    
    def reload_prompts(self, module_name: Optional[str] = None):
        """
        重新加载提示词缓存
        
        Args:
            module_name: 模块名称，如果为None则重新加载所有模块
        """
        if module_name:
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{module_name}:")]
            for key in keys_to_remove:
                del self._cache[key]
            logger.info(f"已重新加载模块 '{module_name}' 的提示词")
        else:
            self._cache.clear()
            logger.info("已重新加载所有提示词")
    
    def list_available_modules(self) -> List[str]:
        """
        列出所有可用的模块
        
        Returns:
            List[str]: 可用模块名称列表
        """
        if not self.prompts_dir.exists():
            return []
        
        modules = []
        for file in self.prompts_dir.glob("*_prompts.md"):
            module_name = file.stem.replace('_prompts', '')
            modules.append(module_name)
        
        return sorted(modules)
    
    def validate_prompt_format(self, prompt: str) -> bool:
        """
        验证提示词格式
        
        Args:
            prompt: 提示词内容
            
        Returns:
            bool: 格式是否有效
        """
        if not prompt or not isinstance(prompt, str):
            return False
        
        if len(prompt.strip()) == 0:
            return False
        
        return True
    
    def _get_module_prompt_file(self, module_name: str) -> Path:
        """
        获取模块对应的提示词文件路径
        
        Args:
            module_name: 模块名称
            
        Returns:
            Path: 提示词文件路径
        """
        filename = f"{module_name}_prompts.md"
        return self.prompts_dir / filename
    
    def _parse_prompt_file(self, file_path: Path) -> Dict[str, str]:
        """
        解析提示词Markdown文件
        
        Args:
            file_path: 提示词文件路径
            
        Returns:
            Dict[str, str]: 提示词字典
            
        Raises:
            PromptFormatError: 文件格式错误
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            raise PromptFileNotFoundError(f"无法读取提示词文件: {e}")
        
        prompts = {}
        
        sections = re.split(r'\n(?=## )', content)
        
        for section in sections:
            id_match = self.PROMPT_ID_PATTERN.search(section)
            if not id_match:
                continue
            
            prompt_id = id_match.group(1)
            
            content_match = self.CONTENT_BLOCK_PATTERN.search(section)
            if content_match:
                prompt_text = content_match.group(1).strip()
                prompts[prompt_id] = prompt_text
        
        if not prompts:
            logger.warning(f"在文件 {file_path} 中未找到有效提示词")
        
        return prompts
    
    def enable_cache(self):
        """启用缓存"""
        self._cache_enabled = True
        logger.info("提示词缓存已启用")
    
    def disable_cache(self):
        """禁用缓存"""
        self._cache_enabled = False
        self._cache.clear()
        logger.info("提示词缓存已禁用")


class PromptTemplate:
    """提示词模板管理器"""
    
    def __init__(self, loader: Optional[PromptLoader] = None):
        """
        初始化提示词模板管理器
        
        Args:
            loader: PromptLoader实例
        """
        self.loader = loader or PromptLoader()
        self._templates: Dict[str, str] = {}
    
    def load_template(self, module_name: str, template_id: str, **kwargs) -> str:
        """
        加载并渲染提示词模板
        
        Args:
            module_name: 模块名称
            template_id: 模板ID
            **kwargs: 模板变量
            
        Returns:
            str: 渲染后的提示词
        """
        template = self.loader.load_prompt(module_name, template_id)
        
        for key, value in kwargs.items():
            placeholder = f"{{{key}}}"
            template = template.replace(placeholder, str(value))
        
        return template
    
    def add_template(self, template_id: str, template: str):
        """
        添加自定义模板
        
        Args:
            template_id: 模板ID
            template: 模板内容
        """
        self._templates[template_id] = template
    
    def render(self, template_id: str, **kwargs) -> str:
        """
        渲染已添加的模板
        
        Args:
            template_id: 模板ID
            **kwargs: 模板变量
            
        Returns:
            str: 渲染后的内容
        """
        if template_id not in self._templates:
            raise PromptNotFoundError(f"模板 '{template_id}' 不存在")
        
        template = self._templates[template_id]
        
        for key, value in kwargs.items():
            placeholder = f"{{{key}}}"
            template = template.replace(placeholder, str(value))
        
        return template


def create_prompt_loader(prompts_dir: Optional[str] = None) -> PromptLoader:
    """
    创建提示词加载器的工厂函数
    
    Args:
        prompts_dir: 提示词目录路径
        
    Returns:
        PromptLoader: 提示词加载器实例
    """
    return PromptLoader(prompts_dir)


_global_loader: Optional[PromptLoader] = None


def get_global_loader() -> PromptLoader:
    """
    获取全局提示词加载器实例
    
    Returns:
        PromptLoader: 全局加载器实例
    """
    global _global_loader
    if _global_loader is None:
        _global_loader = PromptLoader()
    return _global_loader


def load_prompt(module_name: str, prompt_id: str) -> str:
    """
    快捷函数：加载指定提示词
    
    Args:
        module_name: 模块名称
        prompt_id: 提示词ID
        
    Returns:
        str: 提示词内容
    """
    return get_global_loader().load_prompt(module_name, prompt_id)


def get_all_prompts(module_name: str) -> Dict[str, str]:
    """
    快捷函数：获取模块所有提示词
    
    Args:
        module_name: 模块名称
        
    Returns:
        Dict[str, str]: 提示词字典
    """
    return get_global_loader().get_all_prompts(module_name)
