"""
提示词加载器单元测试

测试提示词加载器的各项功能
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from prompts.prompt_loader import (
    PromptLoader,
    PromptFileNotFoundError,
    PromptNotFoundError,
    PromptTemplate,
    load_prompt,
    get_all_prompts
)


class TestPromptLoader:
    """测试PromptLoader类"""
    
    @pytest.fixture
    def temp_prompts_dir(self):
        """创建临时提示词目录"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def sample_prompt_file(self, temp_prompts_dir):
        """创建示例提示词文件"""
        content = """# academic_note_generator 提示词文档

## 模块说明
学术笔记生成器模块，用于生成Obsidian格式的阅读笔记

## 系统提示词

### [AN_G001] - 学术研究助理系统提示词
- **描述**: 设定LLM为专业学术研究助理和知识管理专家
- **使用场景**: 生成Obsidian格式的阅读笔记时使用

```
你是一位专业的学术研究助理和知识管理专家，精通复杂文本分析与Obsidian知识图谱（Knowledge Graph）的构建。
请分析以下学术文章，严格按照要求输出Markdown格式的阅读笔记。
```

## 用户提示词

### [AN_U001] - 笔记生成用户提示词
- **描述**: 动态构建的笔记生成提示词
- **使用场景**: 调用generate_reading_note方法时使用

```
请为以下学术文献生成结构化的Obsidian阅读笔记。
```

### [AN_U002] - 实体提取提示词
- **描述**: 从文本中提取指定类型的实体
- **使用场景**: 调用extract_entities方法时使用

```
请从以下文本中提取指定的实体类型。
```
"""
        
        file_path = temp_prompts_dir / "academic_note_generator_prompts.md"
        file_path.write_text(content, encoding='utf-8')
        return file_path
    
    def test_load_existing_prompt(self, temp_prompts_dir, sample_prompt_file):
        """测试加载已存在的提示词"""
        loader = PromptLoader(prompts_dir=str(temp_prompts_dir))
        
        prompt = loader.load_prompt('academic_note_generator', 'AN_G001')
        
        assert prompt is not None
        assert '学术研究助理' in prompt
        assert len(prompt) > 0
    
    def test_load_nonexistent_prompt(self, temp_prompts_dir, sample_prompt_file):
        """测试加载不存在的提示词"""
        loader = PromptLoader(prompts_dir=str(temp_prompts_dir))
        
        with pytest.raises(PromptNotFoundError) as exc_info:
            loader.load_prompt('academic_note_generator', 'NONEXISTENT')
        
        assert 'NONEXISTENT' in str(exc_info.value)
    
    def test_load_nonexistent_module(self, temp_prompts_dir):
        """测试加载不存在的模块"""
        loader = PromptLoader(prompts_dir=str(temp_prompts_dir))
        
        with pytest.raises(PromptFileNotFoundError):
            loader.get_all_prompts('nonexistent_module')
    
    def test_get_all_prompts(self, temp_prompts_dir, sample_prompt_file):
        """测试获取模块所有提示词"""
        loader = PromptLoader(prompts_dir=str(temp_prompts_dir))
        
        prompts = loader.get_all_prompts('academic_note_generator')
        
        assert isinstance(prompts, dict)
        assert len(prompts) >= 2
        assert 'AN_G001' in prompts
        assert 'AN_U001' in prompts
        assert 'AN_U002' in prompts
    
    def test_cache_functionality(self, temp_prompts_dir, sample_prompt_file):
        """测试缓存功能"""
        loader = PromptLoader(prompts_dir=str(temp_prompts_dir))
        
        prompt1 = loader.load_prompt('academic_note_generator', 'AN_G001')
        prompt2 = loader.load_prompt('academic_note_generator', 'AN_G001')
        
        assert prompt1 == prompt2
        
        assert 'academic_note_generator:AN_G001' in loader._cache
    
    def test_cache_disable(self, temp_prompts_dir, sample_prompt_file):
        """测试禁用缓存"""
        loader = PromptLoader(prompts_dir=str(temp_prompts_dir))
        loader.disable_cache()
        
        loader.load_prompt('academic_note_generator', 'AN_G001')
        
        assert len(loader._cache) == 0
        
        loader.enable_cache()
    
    def test_reload_prompts(self, temp_prompts_dir, sample_prompt_file):
        """测试重新加载提示词"""
        loader = PromptLoader(prompts_dir=str(temp_prompts_dir))
        
        loader.load_prompt('academic_note_generator', 'AN_G001')
        assert 'academic_note_generator:AN_G001' in loader._cache
        
        loader.reload_prompts('academic_note_generator')
        assert 'academic_note_generator:AN_G001' not in loader._cache
    
    def test_list_available_modules(self, temp_prompts_dir, sample_prompt_file):
        """测试列出可用模块"""
        loader = PromptLoader(prompts_dir=str(temp_prompts_dir))
        
        modules = loader.list_available_modules()
        
        assert 'academic_note_generator' in modules
    
    def test_validate_prompt_format(self, temp_prompts_dir):
        """测试提示词格式验证"""
        loader = PromptLoader(prompts_dir=str(temp_prompts_dir))
        
        assert loader.validate_prompt_format("valid prompt") is True
        assert loader.validate_prompt_format("") is False
        assert loader.validate_prompt_format("   ") is False
        assert loader.validate_prompt_format(None) is False
    
    def test_get_prompt_metadata(self, temp_prompts_dir, sample_prompt_file):
        """测试获取提示词元数据"""
        loader = PromptLoader(prompts_dir=str(temp_prompts_dir))
        
        metadata = loader.get_prompt_metadata('academic_note_generator', 'AN_G001')
        
        assert 'description' in metadata or 'content' in metadata
        if 'description' in metadata:
            assert '学术研究助理' in metadata['description']


class TestPromptTemplate:
    """测试PromptTemplate类"""
    
    @pytest.fixture
    def template_loader(self):
        """创建模板加载器"""
        loader = PromptLoader()
        template_manager = PromptTemplate(loader)
        return template_manager
    
    def test_add_and_render_template(self, template_loader):
        """测试添加和渲染模板"""
        template_loader.add_template(
            'test_template',
            'Hello, {name}! You are {age} years old.'
        )
        
        result = template_loader.render('test_template', name='Alice', age=25)
        
        assert result == 'Hello, Alice! You are 25 years old.'
    
    def test_render_nonexistent_template(self, template_loader):
        """测试渲染不存在的模板"""
        with pytest.raises(PromptNotFoundError):
            template_loader.render('nonexistent', name='test')


class TestGlobalFunctions:
    """测试全局快捷函数"""
    
    def test_module_structure(self):
        """测试模块结构"""
        from prompts import prompt_loader
        
        assert hasattr(prompt_loader, 'PromptLoader')
        assert hasattr(prompt_loader, 'PromptTemplate')
        assert hasattr(prompt_loader, 'load_prompt')
        assert hasattr(prompt_loader, 'get_all_prompts')


class TestEdgeCases:
    """测试边界情况"""
    
    @pytest.fixture
    def temp_prompts_dir(self):
        """创建临时提示词目录"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    def test_empty_prompt_file(self, temp_prompts_dir):
        """测试空提示词文件"""
        file_path = temp_prompts_dir / "empty_module_prompts.md"
        file_path.write_text("# Empty Module\n", encoding='utf-8')
        
        loader = PromptLoader(prompts_dir=str(temp_prompts_dir))
        prompts = loader.get_all_prompts('empty_module')
        
        assert prompts == {}
    
    def test_multiline_prompt(self, temp_prompts_dir):
        """测试多行提示词"""
        content = """# multiline_test 提示词文档

## 用户提示词

### [ML_U001] - 多行提示词测试
- **描述**: 测试多行提示词
- **使用场景**: 测试用

```
第一行内容
第二行内容
第三行内容
包含空行的内容

最后一行
```
"""
        
        file_path = temp_prompts_dir / "multiline_test_prompts.md"
        file_path.write_text(content, encoding='utf-8')
        
        loader = PromptLoader(prompts_dir=str(temp_prompts_dir))
        prompt = loader.load_prompt('multiline_test', 'ML_U001')
        
        assert '第一行内容' in prompt
        assert '第三行内容' in prompt
        assert '\n\n' in prompt
        assert '最后一行' in prompt
    
    def test_special_characters_in_prompt(self, temp_prompts_dir):
        """测试特殊字符提示词"""
        content = """# special_chars 提示词文档

## 用户提示词

### [SC_U001] - 特殊字符提示词
- **描述**: 测试特殊字符
- **使用场景**: 测试用

```
包含特殊字符：{{双大括号}}、{{variable}}、\\n换行符、\\t制表符
```
"""
        
        file_path = temp_prompts_dir / "special_chars_prompts.md"
        file_path.write_text(content, encoding='utf-8')
        
        loader = PromptLoader(prompts_dir=str(temp_prompts_dir))
        prompt = loader.load_prompt('special_chars', 'SC_U001')
        
        assert '特殊字符' in prompt or '{{' in prompt


def run_tests():
    """运行所有测试"""
    pytest.main([__file__, '-v', '--tb=short'])


if __name__ == '__main__':
    run_tests()
