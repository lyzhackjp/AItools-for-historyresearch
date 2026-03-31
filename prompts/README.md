# 提示词管理模块

## 简介

本模块提供统一的提示词管理和加载系统，支持从Markdown文件中提取和组织AI提示词。

## 功能特性

- ✅ 统一的提示词加载接口
- ✅ 支持按模块和ID加载提示词
- ✅ 提示词缓存管理
- ✅ 模板渲染支持
- ✅ 异常处理机制
- ✅ 向后兼容

## 快速开始

### 基础使用

```python
from prompts.prompt_loader import PromptLoader

loader = PromptLoader()

# 加载单个提示词
system_prompt = loader.load_prompt('academic_note_generator', 'AN_G001')

# 获取模块所有提示词
all_prompts = loader.get_all_prompts('academic_note_generator')

# 列出所有可用模块
modules = loader.list_available_modules()
```

### 使用模板

```python
from prompts.prompt_loader import PromptTemplate

template_manager = PromptTemplate()

# 加载并渲染模板
rendered_prompt = template_manager.load_template(
    'module_name',
    'TEMPLATE_ID',
    variable1='value1',
    variable2='value2'
)
```

### 在模块中使用

```python
from modules.academic_note_generator import AcademicNoteGenerator

generator = AcademicNoteGenerator()

# 自动使用提示词加载器
result = generator.generate_reading_note(
    text="学术文献内容...",
    metadata={'title': '标题'}
)
```

## 可用模块

| 模块名称 | 提示词数量 | 描述 |
|---------|----------|------|
| academic_note_generator | 2+ | 学术笔记生成器 |
| academic_summarizer | 2+ | 学术摘要生成器 |
| paper_polisher | 2+ | 论文精简处理器 |
| style_transfer | 2+ | 文风分析与迁移 |
| virtual_persona_chatbot | 2+ | 虚拟人格对话系统 |
| llm_client | 1+ | LLM客户端 |
| ner_processor | 4+ | 命名实体识别处理器 |

## 目录结构

```
prompts/
├── __init__.py              # 模块初始化
├── prompt_loader.py         # 提示词加载器核心
├── test_prompt_loader.py   # 单元测试
└── README.md               # 本文档

modules/prompts/            # 各模块提示词文件
├── academic_note_generator_prompts.md
├── academic_summarizer_prompts.md
├── paper_polisher_prompts.md
├── style_transfer_prompts.md
├── virtual_persona_chatbot_prompts.md
├── llm_client_prompts.md
└── ner_processor_prompts.md
```

## 测试

```bash
# 运行单元测试
python -m pytest prompts/test_prompt_loader.py -v

# 运行集成测试
python test_prompt_integration.py
```

## 文档

- [详细指南](PROMPTS_MANAGEMENT_GUIDE.md) - 完整的提示词管理指南
- [提示词清单](PROMPTS_INVENTORY.md) - 所有提示词的完整清单
- [实施计划](PROMPT_MANAGEMENT_PLAN.md) - 优化实施计划

## 版本要求

- Python 3.8+
- 无外部依赖（仅使用标准库）

## 许可证

与项目主许可证一致
