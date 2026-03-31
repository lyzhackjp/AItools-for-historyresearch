# reverse_outline_analyzer 提示词文档

## 模块说明

逆向大纲审视器模块，用于分析论文草稿的逻辑链、各部分比重等，实现逆向审视。

### 核心功能
- 篇幅分析：各部分字数统计、比例失衡检测
- 逻辑链分析：论点提取、逻辑关系识别、断层检测
- 注意力集中度分析：核心论点识别、偏离检测
- 修订建议生成：综合分析结果生成改进建议

### 技术架构
- 文本处理：基于正则表达式的结构解析
- AI处理：集成阿里通义千问 / 次要支持 Minimax
- 分析引擎：多维度论文分析

---

## 系统提示词

### [ROA_G001] - 学术论文审稿专家系统提示词

- **描述**: 设定LLM为资深学术论文审稿专家
- **使用场景**: 逆向分析论文结构、逻辑、论证质量
- **标识符**: ROA_G001
- **创建日期**: 2026-03-28

**内容**:

```
你是一位资深的学术论文审稿专家，擅长分析论文的结构、逻辑和论证质量。

你的专长包括：
1. 识别论文的核心论点和支持论点
2. 分析论文各部分的篇幅分布
3. 检测逻辑断层和论证漏洞
4. 评估论述的集中度和连贯性
5. 提供具体的修订建议

请严格按照JSON格式输出分析结果。
```

---

## 用户提示词

### [ROA_U001] - 逻辑问题分析提示词

- **描述**: 分析论文大纲的逻辑问题
- **使用场景**: 调用check_logic_gaps方法时使用
- **标识符**: ROA_U001
- **创建日期**: 2026-03-28

**内容**:

```
请分析以下论文大纲的逻辑问题：

{outline_summary}

请识别：
1. 论证链是否完整
2. 各部分衔接是否顺畅
3. 是否有遗漏的重要论证环节

请以JSON格式输出发现的逻辑问题列表，每个问题包含：
- "severity": 问题严重程度 (high/medium/low)
- "message": 问题描述
- "suggestion": 修订建议
```

**模板变量说明**:
- `{outline_summary}`: 论文大纲摘要

---

### [ROA_U002] - 修订建议生成提示词

- **描述**: 基于论文大纲生成修订建议
- **使用场景**: 调用suggest_revisions方法时使用
- **标识符**: ROA_U002
- **创建日期**: 2026-03-28

**内容**:

```
基于以下论文大纲，请提供具体的修订建议：

{outline_summary}

请分析：
1. 篇幅分配的合理性
2. 章节结构的完整性
3. 论述逻辑的连贯性
4. 核心论点的突出程度

请以JSON数组格式输出修订建议列表，每条建议不超过50字。
```

**模板变量说明**:
- `{outline_summary}`: 论文大纲摘要

---

### [ROA_U003] - 论证深度评估提示词

- **描述**: 评估论文论证的深度和完整性
- **使用场景**: LLM深度分析时使用
- **标识符**: ROA_U003
- **创建日期**: 2026-03-28

**内容**:

```
请评估以下论文章节的论证深度：

章节：{section_name}
内容：{section_content}

请评估：
1. 论点是否清晰明确
2. 论据是否充分有力
3. 论证逻辑是否严密
4. 是否存在论证漏洞

请以JSON格式输出评估结果：
- "clarity": 论点清晰度 (1-10)
- "evidence": 论据充分度 (1-10)
- "logic": 论证严密性 (1-10)
- "weakness": 主要论证漏洞
- "improvement": 改进建议
```

**模板变量说明**:
- `{section_name}`: 章节名称
- `{section_content}`: 章节内容

---

## 分析维度说明

### 1. 篇幅分析

**评估指标**:
- 总字数分布
- 各章节字数占比
- 段落平均长度
- 章节平衡度

**判断标准**:
- 引言：10-15%
- 文献综述：20-25%
- 方法论：15-20%
- 分析/结果：30-35%
- 讨论：15-20%
- 结论：5-10%

### 2. 逻辑链分析

**评估维度**:
- 核心论点识别
- 论点层级关系
- 论证支撑关系
- 逻辑断层检测

**常见问题**:
- 论点分散
- 论证跳跃
- 证据不足
- 逻辑混乱

### 3. 注意力集中度

**评估方法**:
- 核心论点出现频率
- 次要论点占比
- 偏离主线内容检测

---

## 提示词使用说明

### 使用方法

#### 1. 基础使用

```python
from modules.reverse_outline_analyzer import ReverseOutlineAnalyzer
from prompts.prompt_loader import PromptLoader

loader = PromptLoader()
analyzer = ReverseOutlineAnalyzer(test_mode=True)

# 加载系统提示词
system_prompt = loader.load_prompt('reverse_outline_analyzer', 'ROA_G001')

# 全面分析论文
result = analyzer.analyze(paper_text)

# 提取大纲
outline = analyzer.extract_outline(paper_text)

# 检测失衡
issues = analyzer.detect_imbalance(outline)

# 检查逻辑
gaps = analyzer.check_logic_gaps(outline)

# 生成建议
suggestions = analyzer.suggest_revisions(outline, issues, gaps)
```

#### 2. 使用模板渲染

```python
from prompts.prompt_loader import PromptTemplate

template_loader = PromptTemplate()

# 加载逻辑分析提示词
logic_prompt = template_loader.load_template(
    'reverse_outline_analyzer',
    'ROA_U001',
    outline_summary='论文大纲摘要...'
)

# 加载修订建议提示词
revision_prompt = template_loader.load_template(
    'reverse_outline_analyzer',
    'ROA_U002',
    outline_summary='论文大纲摘要...'
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
- 为复杂分析提供分步骤指导
- 保持分析维度的完整性
