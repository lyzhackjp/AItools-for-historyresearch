# academic_note_generator 提示词文档

## 模块说明

学术笔记智能生成模块，基于大语言模型从学术文献中自动生成符合Obsidian格式的结构化阅读笔记。

### 核心功能
- 生成带双向链接的学术笔记
- 提取五类核心实体（人名、地名、事件、概念、文献）
- 构建知识图谱节点数据
- 支持多种API提供商（通义千问、MiniMax等）

### 实体类型
- **person**: 历史人物、学者、思想家等
- **location**: 国家、城市、地区等
- **event**: 历史事件、会议、运动等
- **concept**: 学术术语、理论、主义等
- **literature**: 著作、论文、史料等

---

## 系统提示词

### [AN_G001] - 学术研究助理系统提示词

- **描述**: 设定LLM为专业学术研究助理和知识管理专家
- **使用场景**: 生成Obsidian格式的阅读笔记时使用
- **标识符**: AN_G001
- **创建日期**: 2026-03-28

**内容**:

```
你是一位专业的学术研究助理和知识管理专家，精通复杂文本分析与Obsidian知识图谱（Knowledge Graph）的构建。

请分析以下学术文章，严格按照要求输出Markdown格式的阅读笔记。

【核心任务】
1. 提取五类核心实体并使用Obsidian双向链接语法 [[实体名称]] 包裹
2. 生成结构化的章节脉络
3. 构建知识图谱节点数据

【实体类型定义】
- 人名 (Person)：历史人物、学者等
- 地名 (Location)：国家、城市、地区等
- 事件 (Event)：历史事件、会议、运动等
- 概念/术语 (Concept)：学术术语、理论、主义等
- 引用文献 (Literature)：著作、论文、史料等

【输出格式要求】
1. 在"总体摘要"和"章节脉络"的正文中，只要实体出现，就必须加上 [[ ]] 
2. 绝对不要使用普通的Markdown超链接格式 [文本](链接)
3. 只能使用 [[文本]] 格式
```

---

## 笔记模板

### [AN_T001] - Obsidian阅读笔记模板

- **描述**: 定义Obsidian阅读笔记的标准模板
- **使用场景**: 生成笔记时作为输出格式参考
- **标识符**: AN_T001
- **创建日期**: 2026-03-28

**内容**:

```
---
type: reading_note
tags:
  - #文献笔记
  - #{subject_tag}
created: {created_date}
source: {source_title}
---

# {title}

## 📋 总体摘要

{summary}

## 📑 章节核心论点

{chapter_outline}

## 🔗 核心图谱节点提取

{knowledge_graph}

---

**元数据**
- 作者：{authors}
- 发表年份：{year}
- 关键词：{keywords}
```

**模板变量说明**:
- `{created_date}`: 笔记创建日期
- `{source_title}`: 文献标题
- `{title}`: 笔记标题
- `{summary}`: 总体摘要内容
- `{chapter_outline}`: 章节脉络
- `{knowledge_graph}`: 知识图谱节点
- `{authors}`: 文献作者
- `{year}`: 发表年份
- `{keywords}`: 关键词
- `{subject_tag}`: 学科标签

---

## 用户提示词

### [AN_U001] - 笔记生成用户提示词

- **描述**: 动态构建的笔记生成提示词
- **使用场景**: 调用generate_reading_note方法时使用
- **标识符**: AN_U001
- **创建日期**: 2026-03-28

**内容**:

```
请为以下学术文献生成结构化的Obsidian阅读笔记。

文献标题：{title}
作者：{authors}
发表年份：{year}
关键词：{keywords}

文献内容：
{text}

请按照以下格式输出：
1. 总体摘要（150-300字）
2. 章节核心论点（提取3-5个主要论点）
3. 核心图谱节点提取（列出识别到的所有实体）
```

**模板变量说明**:
- `{title}`: 文献标题
- `{authors}`: 作者信息
- `{year}`: 发表年份
- `{keywords}`: 关键词
- `{text}`: 文献正文内容

---

### [AN_U002] - 实体提取提示词

- **描述**: 从文本中提取指定类型的实体
- **使用场景**: 调用extract_entities方法时使用
- **标识符**: AN_U002
- **创建日期**: 2026-03-28

**内容**:

```
请从以下文本中提取指定的实体类型。

实体类型说明：
- person: 历史人物、学者、思想家等
- location: 国家、城市、地区等
- event: 历史事件、会议、运动等
- concept: 学术术语、理论、主义等
- literature: 著作、论文、史料等

待分析文本：
{text}

请提取以下类型的实体：
{entity_types}

请以JSON格式输出：
{{
    "person": ["实体列表"],
    "location": ["实体列表"],
    "event": ["实体列表"],
    "concept": ["实体列表"],
    "literature": ["实体列表"]
}}
```

**模板变量说明**:
- `{text}`: 待分析的文本
- `{entity_types}`: 要提取的实体类型列表

---

## 提示词使用说明

### 使用方法

#### 1. 基础使用（使用默认提示词）

```python
from modules.academic_note_generator import AcademicNoteGenerator
from prompts.prompt_loader import PromptLoader

loader = PromptLoader()
generator = AcademicNoteGenerator()

# 加载系统提示词
system_prompt = loader.load_prompt('academic_note_generator', 'AN_G001')

# 生成笔记
result = generator.generate_reading_note(
    text="学术文献内容...",
    metadata={'title': '文献标题'}
)
```

#### 2. 使用模板渲染

```python
from prompts.prompt_loader import PromptTemplate

template_loader = PromptTemplate()
template_loader.loader = PromptLoader()

# 渲染笔记生成提示词
prompt = template_loader.load_template(
    'academic_note_generator',
    'AN_U001',
    title='示例标题',
    authors='作者',
    year='2024',
    keywords='关键词',
    text='文献内容'
)
```

#### 3. 获取笔记模板

```python
from prompts.prompt_loader import PromptLoader

loader = PromptLoader()
template = loader.load_prompt('academic_note_generator', 'AN_T001')

# 填充模板变量
filled_template = template.format(
    created_date='2024-01-01',
    source_title='文献标题',
    title='笔记标题',
    summary='摘要内容',
    chapter_outline='章节脉络',
    knowledge_graph='图谱数据',
    authors='作者',
    year='2024',
    keywords='关键词',
    subject_tag='日本史'
)
```

---

## 版本历史

| 版本 | 日期 | 描述 | 作者 |
|------|------|------|------|
| 1.0 | 2026-03-28 | 初始版本 | AI Assistant |

---

## 维护指南

### 添加新提示词

1. 在适当的位置添加新的 `### [ID]` 章节
2. 包含描述、使用场景、标识符等信息
3. 使用 ``` 包裹提示词内容
4. 更新版本历史

### 修改现有提示词

1. 直接编辑对应章节的内容
2. 保持ID不变
3. 更新版本历史中的描述

### 最佳实践

- 所有提示词使用UTF-8编码
- 避免在提示词中使用硬编码的路径或配置
- 为复杂提示词提供模板变量说明
- 保持提示词的独立性和可复用性
