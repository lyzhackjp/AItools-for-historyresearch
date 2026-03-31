# academic_summarizer 提示词文档

## 模块说明

学术内容智能摘要模块，智能生成学术文献摘要，提取核心研究问题和概念。

### 核心功能
- 生成抽取式/生成式摘要
- 提取核心研究问题
- 批量抽取核心概念和研究方法
- 评估文献与研究主题的相关度
- 支持多种API提供商

---

## 系统提示词

### [AS_G001] - 学术研究助手系统提示词

- **描述**: 设定LLM为资深学术研究助手
- **使用场景**: 学术文献分析与摘要生成
- **标识符**: AS_G001
- **创建日期**: 2026-03-28

**内容**:

```
你是一位资深的学术研究助手，专精于学术文献的分析与摘要生成。

你的专长包括：
1. 快速把握学术论文的核心论点
2. 识别研究问题和创新点
3. 提取关键概念和方法论
4. 评估文献的学术价值
5. 判断文献与特定研究主题的相关性

请严格按照JSON格式输出分析结果。
```

---

## 用户提示词

### [AS_U001] - 抽象式摘要生成提示词

- **描述**: 生成指定长度和风格的抽象式摘要
- **使用场景**: 调用generate_abstractive_summary方法时使用
- **标识符**: AS_U001
- **创建日期**: 2026-03-28

**内容**:

```
请为以下学术文献生成{max_length}字左右的摘要。

摘要风格要求：{style_instruction}

文献内容：
{text}

请直接输出摘要内容，不要包含其他说明。
```

**模板变量说明**:
- `{max_length}`: 摘要最大长度（字数）
- `{style_instruction}`: 摘要风格要求（academic/simple/bullet_points）
- `{text}`: 文献内容

**风格指令映射**:
- `academic`: 使用正式学术语言，客观陈述
- `simple`: 使用通俗易懂的语言，简明扼要
- `bullet_points`: 使用要点列表形式，每点一句话

---

### [AS_U002] - 核心研究问题提取提示词

- **描述**: 从文献中提取核心研究问题
- **使用场景**: 调用extract_research_questions方法时使用
- **标识符**: AS_U002
- **创建日期**: 2026-03-28

**内容**:

```
请从以下学术文献中提取核心研究问题。

文献内容：
{text}

请以JSON数组格式输出，每个元素包含：
- "type": 问题类型 ("main_question", "sub_question", "methodology_question")
- "description": 问题描述
- "chapter": 出现的章节
- "importance": 重要性评级 (high/medium/low)
```

**模板变量说明**:
- `{text}`: 学术文献内容

---

### [AS_U003] - 核心概念提取提示词

- **描述**: 提取并分类核心概念
- **使用场景**: 调用extract_core_concepts方法时使用
- **标识符**: AS_U003
- **创建日期**: 2026-03-28

**内容**:

```
请从以下学术文献中提取核心概念，并按类型分类。

文献内容：
{text}

请以JSON格式输出，包含：
- "theories": 理论概念列表
- "methods": 方法论概念列表
- "terms": 专业术语列表
- "frameworks": 理论框架列表
```

**模板变量说明**:
- `{text}`: 学术文献内容

---

### [AS_U004] - 研究方法提取提示词

- **描述**: 提取文献使用的研究方法
- **使用场景**: 调用extract_research_methods方法时使用
- **标识符**: AS_U004
- **创建日期**: 2026-03-28

**内容**:

```
请从以下学术文献中提取使用的研究方法。

文献内容：
{text}

请以JSON格式输出，包含：
- "primary_methods": 主要研究方法列表
- "data_sources": 数据来源列表
- "analysis_techniques": 分析技术列表
- "methodology_description": 方法论描述
```

**模板变量说明**:
- `{text}`: 学术文献内容

---

### [AS_U005] - 相关性评估提示词

- **描述**: 评估文献与研究主题的相关度
- **使用场景**: 调用evaluate_relevance方法时使用
- **标识符**: AS_U005
- **创建日期**: 2026-03-28

**内容**:

```
请评估以下文献与研究主题的相关度。

研究主题：{research_topic}
主题描述：{topic_description}

文献内容：
{text}

请以JSON格式输出：
- "relevance_score": 相关度评分 (0-10)
- "relevance_level": 相关等级 (high/medium/low)
- "main_reasons": 主要相关原因列表
- "key_connections": 关键关联点列表
```

**模板变量说明**:
- `{research_topic}`: 研究主题
- `{topic_description}`: 主题详细描述
- `{text}`: 文献内容

---

### [AS_U006] - 相关原因分析提示词

- **描述**: 分析文献与研究主题的相关原因
- **使用场景**: 调用analyze_relevance方法时使用
- **标识符**: AS_U006
- **创建日期**: 2026-03-28

**内容**:

```
请分析以下文献与研究主题的相关原因。

研究主题：{research_topic}

文献内容：
{text}

请以JSON格式输出：
- "direct_relevance": 直接相关性说明
- "indirect_relevance": 间接相关性说明
- "potential_applications": 潜在应用场景
- "limitations": 局限性分析
```

**模板变量说明**:
- `{research_topic}`: 研究主题
- `{text}`: 文献内容

---

## 提示词使用说明

### 使用方法

#### 1. 基础使用

```python
from modules.academic_summarizer import AcademicSummarizer
from prompts.prompt_loader import PromptLoader

loader = PromptLoader()
summarizer = AcademicSummarizer()

# 生成抽象式摘要
system_prompt = loader.load_prompt('academic_summarizer', 'AS_G001')
summary = summarizer.generate_abstractive_summary(
    text="学术文献内容...",
    max_length=500,
    style='academic'
)

# 提取研究问题
questions = summarizer.extract_research_questions(text)

# 评估相关性
relevance = summarizer.evaluate_relevance(text, '研究主题')
```

#### 2. 使用模板渲染

```python
from prompts.prompt_loader import PromptTemplate

template_loader = PromptTemplate()
prompt = template_loader.load_template(
    'academic_summarizer',
    'AS_U001',
    max_length=500,
    style_instruction='使用正式学术语言，客观陈述',
    text='文献内容...'
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

1. 在适当位置添加新的 `### [ID]` 章节
2. 包含描述、使用场景、标识符等信息
3. 使用 ``` 包裹提示词内容
4. 更新版本历史

### 修改现有提示词

1. 直接编辑对应章节的内容
2. 保持ID不变
3. 更新版本历史中的描述

### 最佳实践

- 所有提示词使用UTF-8编码
- JSON输出格式的提示词必须明确输出格式要求
- 为复杂提示词提供模板变量说明
- 保持提示词的独立性和可复用性
