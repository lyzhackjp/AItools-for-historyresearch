# style_transfer 提示词文档

## 模块说明

文风分析与迁移模块，分析特定作者的写作风格，实现文风迁移与模仿。

### 核心功能
- 构建文风矩阵分析
- 句法结构分析
- 词汇选择分析
- 语气与叙事声音分析
- 学术修辞机制分析
- 基于文风矩阵的文本改写
- 少样本文风模仿

### 文风矩阵四维度
1. **句法结构**: 节奏剖析、语态频率、句式习惯
2. **词汇深度与选择**: 术语偏好、词源倾向、选词特点
3. **语气与叙事声音**: 叙事视角、情感色彩、批判性
4. **学术修辞机制**: 修辞偏好、逻辑关节、论证模式

---

## 系统提示词

### [ST_G001] - 文风迁移专家系统提示词

- **描述**: 设定LLM为文本风格迁移顶级学术写作助手
- **使用场景**: 文风矩阵分析和迁移
- **标识符**: ST_G001
- **创建日期**: 2026-03-28

**内容**:

```
你是一位精通文本风格迁移的顶级学术写作助手。

你的专长包括：
1. 深度分析文章风格矩阵
2. 识别作者的写作习惯和特征
3. 精确模仿特定作者的文风
4. 进行高质量的文风迁移

请严格按照要求输出分析结果。
```

---

## 用户提示词

### [ST_U001] - 文风矩阵分析提示词

- **描述**: 四维度文风矩阵分析
- **使用场景**: 调用analyze_style_matrix方法时使用
- **标识符**: ST_U001
- **创建日期**: 2026-03-28

**内容**:

```
请分析以下文本的文风矩阵，从四个维度进行深度分析：

【分析维度】
1. 句法结构（Sentence structure）
   - 节奏剖析：长短句交替的起伏节奏
   - 语态频率：主动语态vs被动语态
   - 句式习惯：复杂句式、从句嵌套等

2. 词汇深度与选择（Vocabulary choices）
   - 术语偏好：高频学术术语
   - 词源倾向：古汉语词、日文借词、文言句式
   - 选词特点：书面语vs口语

3. 语气与叙事声音（Tone and narrative voice）
   - 叙事视角：客观抽离vs主观介入
   - 情感色彩：冷峻vs热情
   - 批判性：强烈批判vs温和建议

【目标作者】
{author_name}

【分析文本】
{text}

请以JSON格式输出：
{{
    "sentence_structure": {{
        "rhythm_analysis": "节奏分析描述",
        "voice_frequency": {{"active": 百分比, "passive": 百分比}},
        "sentence_patterns": ["句式特征列表"],
        "examples": ["原文例句"]
    }},
    "vocabulary_choices": {{
        "term_preferences": ["高频术语"],
        "etymology_tendency": "词源倾向描述",
        "register": "语域描述",
        "examples": ["原文例句"]
    }},
    "tone_narrative": {{
        "narrative_perspective": "叙事视角描述",
        "emotional_color": "情感色彩描述",
        "critical_stance": "批判立场描述",
        "examples": ["原文例句"]
    }},
    "rhetorical_patterns": {{
        "rhetorical_preferences": ["修辞偏好"],
        "logical_connectors": ["逻辑连接词"],
        "argumentation_mode": "论证模式描述",
        "examples": ["原文例句"]
    }},
    "overall_style_summary": "整体风格画像（100-200字）"
}}
```

**模板变量说明**:
- `{author_name}`: 作者名称（可选）
- `{text}`: 待分析的文本（建议5000字以内）

---

### [ST_U002] - 基于文风矩阵的文本改写提示词

- **描述**: 根据文风矩阵进行文本改写
- **使用场景**: 调用transfer_style_with_matrix方法时使用
- **标识符**: ST_U002
- **创建日期**: 2026-03-28

**内容**:

```
请将以下文本改写成目标文风。

【目标文风】
{style_description}

【待改写文本】
{text}

请直接输出改写后的文本，保持：
1. 原意不变
2. 核心信息完整
3. 学术严谨性
4. 仅改变文风特征
```

**模板变量说明**:
- `{style_description}`: 目标文风描述（来自文风矩阵分析）
- `{text}`: 待改写的文本

---

### [ST_U003] - 少样本文风模仿提示词

- **描述**: 基于示例的文风模仿
- **使用场景**: 调用few_shot_style_transfer方法时使用
- **标识符**: ST_U003
- **创建日期**: 2026-03-28

**内容**:

```
请参考以下示例，学习并模仿目标文风来改写文本。

【示例文本1】
{sample_1}

【示例文本2】
{sample_2}

【目标文风特征】
{style_features}

【待改写文本】
{text}

请模仿示例的文风特征进行改写，保持：
1. 原意不变
2. 核心信息完整
3. 学术严谨性
4. 模仿示例的：
   - 句式结构
   - 词汇选择
   - 语气语调
   - 修辞手法

请直接输出改写后的文本。
```

**模板变量说明**:
- `{sample_1}`: 示例文本1
- `{sample_2}`: 示例文本2
- `{style_features}`: 目标文风特征描述
- `{text}`: 待改写的文本

---

## 文风矩阵维度说明

### 1. 句法结构分析

**评估指标**:
- **句长分布**: 平均句长、最长句、最短句
- **句式多样性**: 陈述句、疑问句、感叹句比例
- **从句使用**: 定语从句、状语从句频率
- **语态偏好**: 主动语态vs被动语态比例

**示例输出**:
```json
{
    "sentence_structure": {
        "avg_sentence_length": 25,
        "max_sentence_length": 80,
        "sentence_patterns": ["复杂句", "并列句", "从句嵌套"],
        "voice_frequency": {"active": 70, "passive": 30}
    }
}
```

### 2. 词汇深度与选择

**评估指标**:
- **术语密度**: 学术术语出现频率
- **词源构成**: 古汉语词、日语词、外来语比例
- **语域层次**: 正式/非正式词汇比例
- **修辞词汇**: 比喻、象征等修辞手法词汇

### 3. 语气与叙事声音

**评估指标**:
- **叙事视角**: 第一/第二/第三人称
- **情感强度**: 客观描述vs主观评价
- **批判程度**: 温和/中立/激进
- **读者意识**: 是否面向特定读者群体

### 4. 学术修辞机制

**评估指标**:
- **论证模式**: 归纳法vs演绎法
- **逻辑连接**: 转折、因果、递进词使用
- **修辞手法**: 比喻、排比、对比使用
- **引用风格**: 直接引用vs间接引用

---

## 提示词使用说明

### 使用方法

#### 1. 基础使用

```python
from modules.style_transfer import StyleTransfer
from prompts.prompt_loader import PromptLoader

loader = PromptLoader()
style_transfer = StyleTransfer()

# 分析文风矩阵
system_prompt = loader.load_prompt('style_transfer', 'ST_G001')
style_matrix = style_transfer.analyze_style_matrix(
    text="待分析文本...",
    author_name="作者名"
)

# 基于文风矩阵改写
transferred_text = style_transfer.transfer_style_with_matrix(
    text="待改写文本...",
    style_matrix=style_matrix
)
```

#### 2. 少样本学习

```python
from modules.style_transfer import StyleTransfer
from prompts.prompt_loader import PromptTemplate

template_loader = PromptTemplate()

# 加载少样本提示词
few_shot_prompt = template_loader.load_template(
    'style_transfer',
    'ST_U003',
    sample_1='示例文本1...',
    sample_2='示例文本2...',
    style_features='目标文风特征...',
    text='待改写文本...'
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
- 保持文风分析维度的完整性
- 注意不同语言（日文/中文/英文）的文风差异
