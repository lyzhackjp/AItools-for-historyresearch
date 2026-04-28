# 统一任务执行框架使用指南

## 概述

本框架为历史研究AI辅助工具提供统一的任务执行接口，支持两种执行模式：

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| **API模式** | 通过大语言模型API执行任务 | 需要高质量结果、复杂任务 |
| **脚本模式** | 使用传统脚本/正则表达式执行任务 | 快速处理、简单任务、离线环境 |

## 核心特性

- **安全密钥管理**：API密钥仅存储在 `secrets/` 文件夹内，确保安全
- **模式自由切换**：用户可随时在API和脚本模式间切换
- **统一接口**：所有模块使用相同的调用方式
- **自定义提示词**：支持用户提交自定义提示词完成任务

## 快速开始

### 1. 配置API密钥

在 `secrets/api_keys.txt` 文件中配置您的API密钥：

```
# 阿里云通义千问
qwen3.5-plus = QWEN_API_KEY_PLACEHOLDER

# Minimax AI
Minimax2.7 = MINIMAX_API_KEY_PLACEHOLDER
```

### 2. 基本使用

```python
from modules.task_manager import TaskManager

# 创建任务管理器
manager = TaskManager(mode='api', provider='qwen')

# 执行NER任务
result = manager.ner("伊藤博文是明治维新的重要人物。")

# 切换到脚本模式
manager.set_mode('script')
result = manager.ner("伊藤博文是明治维新的重要人物。")
```

### 3. 命令行使用

```bash
# 显示系统信息
python -m modules.task_cli --info

# 使用API模式执行NER任务
python -m modules.task_cli --mode api --task ner --text "伊藤博文是明治维新的重要人物"

# 使用脚本模式执行摘要任务
python -m modules.task_cli --mode script --task summary --text "长文本内容..."

# 进入交互模式
python -m modules.task_cli --interactive
```

## 支持的任务类型

| 任务类型 | 方法名 | 说明 |
|----------|--------|------|
| 命名实体识别 | `ner()` | 识别历史人物、地名、事件等 |
| 学术笔记生成 | `academic_note()` | 生成Obsidian格式笔记 |
| 论文润色 | `paper_polish()` | 智能精简和润色论文 |
| 引用规范化 | `citation_normalize()` | 统一引用格式 |
| OCR校正 | `ocr_correct()` | 校正OCR识别错误 |
| 文本摘要 | `summarize()` | 生成文本摘要 |
| 文风迁移 | `style_transfer()` | 分析和迁移文风 |
| 虚拟人格对话 | `virtual_persona_chat()` | 与虚拟角色对话 |
| 实体消歧 | `entity_disambiguation()` | 解决同名实体歧义 |

## 使用示例

### 命名实体识别

```python
from modules.task_manager import TaskManager

manager = TaskManager(mode='api')

# 基本使用
result = manager.ner("伊藤博文出生于1841年，是明治维新的重要人物。")

# 指定实体类型
result = manager.ner(
    text="伊藤博文出生于1841年...",
    categories=['person', 'date', 'location']
)

# 使用预设配置
result = manager.ner(
    text="...",
    preset='ner_detailed'
)

# 脚本模式（快速处理）
manager.set_mode('script')
result = manager.ner("...")
```

### 学术笔记生成

```python
manager = TaskManager(mode='api')

result = manager.academic_note(
    text="学术论文全文...",
    source="《日本史研究》2024年第1期"
)

if result['success']:
    note_content = result['data']['note_content']
    print(note_content)
```

### 论文润色

```python
manager = TaskManager(mode='api')

# 保守润色
result = manager.paper_polish(
    text="待润色的段落...",
    preset='polish_conservative'
)

# 积极润色
result = manager.paper_polish(
    text="待润色的段落...",
    preset='polish_aggressive'
)
```

### 自定义提示词

```python
manager = TaskManager(mode='api')

custom_prompt = """请分析以下文本的历史背景。

文本: {text}

请输出：
1. 时代背景
2. 主要事件
3. 历史意义
"""

result = manager.execute_with_prompt(
    task_type='text_summary',
    prompt=custom_prompt,
    text="明治维新是日本历史上的重要转折点..."
)
```

### 批量处理

```python
manager = TaskManager(mode='script')

texts = [
    {"text": "第一段文本..."},
    {"text": "第二段文本..."},
    {"text": "第三段文本..."},
]

results = manager.batch_execute('ner', texts)
```

## 预设配置

| 预设名称 | 任务类型 | 说明 |
|----------|----------|------|
| `ner_quick` | NER | 快速实体识别 |
| `ner_detailed` | NER | 详细实体识别 |
| `note_standard` | 学术笔记 | 标准笔记生成 |
| `polish_conservative` | 论文润色 | 保守润色 |
| `polish_aggressive` | 论文润色 | 积极润色 |
| `summary_short` | 摘要 | 简短摘要 |
| `summary_detailed` | 摘要 | 详细摘要 |
| `ocr_correct` | OCR校正 | OCR文本校正 |
| `citation_gb` | 引用规范化 | GB/T 7714格式 |

## API提供商支持

| 提供商 | 标识符 | 说明 |
|--------|--------|------|
| 阿里云通义千问 | `qwen` | 推荐，支持日文处理 |
| MiniMax | `minimax` | 备选 |
| OpenAI | `openai` | GPT系列 |
| DeepSeek | `deepseek` | 国产模型 |
| 智谱AI | `zhipu` | GLM系列 |
| 火山引擎 | `volcano` | 豆包系列 |

## 安全说明

1. **API密钥安全**：所有密钥仅存储在 `secrets/api_keys.txt` 中
2. **密钥不会泄露**：框架不会将密钥写入其他文件或日志
3. **密钥验证**：可通过 `get_api_key_status()` 检查密钥状态

```python
from modules.secure_api_key_manager import SecureAPIKeyManager

manager = SecureAPIKeyManager()
status = manager.get_status_report()

# 检查密钥状态
for service, info in status['services'].items():
    print(f"{service}: {'已配置' if info['has_key'] else '未配置'}")
```

## 交互模式

```bash
python -m modules.task_cli --interactive
```

交互模式命令：
- `help` - 显示帮助
- `status` - 显示当前状态
- `stats` - 显示执行统计
- `mode api/script` - 切换模式
- `provider <name>` - 切换提供商
- `quit` - 退出

## 模块适配器

如果需要更细粒度的控制，可以直接使用模块适配器：

```python
from modules.module_adapters import NERAdapter, AcademicNoteAdapter

# 创建NER适配器
ner = NERAdapter(mode='api', provider='qwen')
result = ner.recognize("伊藤博文是明治维新的重要人物。")

# 创建学术笔记适配器
note_gen = AcademicNoteAdapter(mode='api')
result = note_gen.generate(text="...", source="...")
```

## 文件结构

```
modules/
├── secure_api_key_manager.py  # 安全API密钥管理器
├── unified_task_executor.py   # 统一任务执行框架
├── module_adapters.py         # 模块适配器
├── task_manager.py            # 任务管理器
└── task_cli.py               # 命令行接口

secrets/
└── api_keys.txt              # API密钥配置文件（仅此位置）
```

## 常见问题

### Q: 如何判断使用哪种模式？

- **使用API模式**：需要高质量结果、复杂任务、需要理解语义
- **使用脚本模式**：快速处理、简单任务、离线环境、批量处理

### Q: API调用失败怎么办？

框架会自动记录错误信息，可以通过结果中的 `error` 字段查看：

```python
result = manager.ner("...")
if not result['success']:
    print(f"错误: {result['error']}")
```

### Q: 如何添加新的预设配置？

```python
from modules.task_manager import TaskPreset

manager = TaskManager()
preset = TaskPreset(
    name='my_custom_ner',
    task_type='ner',
    provider='qwen',
    temperature=0.2,
    max_tokens=3000,
    description='自定义NER配置'
)
manager.add_preset(preset)
```
