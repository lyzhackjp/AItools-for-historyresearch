# paper_polisher 提示词文档

## 模块说明

学术论文智能精简处理模块，专为日本史学术论文设计的智能内容精简工具。

### 核心功能
- 智能内容精简：自动识别并删除逻辑冗余的论述
- 专业文档处理：正确区分正文与脚注内容
- 修订追踪功能：启用修订模式，清晰显示所有删减和修改
- 学术严谨性保障：保护历史专有名词和学术术语

### 技术架构
- 文档处理：基于 python-docx 库处理 .docx 文档
- AI处理：集成阿里通义千问 / 次要支持 Minimax
- 修订追踪：实现 Track Changes 功能

---

## 系统提示词

### [PP_G001] - 日本史学术论文编辑系统提示词

- **描述**: 设定LLM为日本史学术论文编辑专家
- **使用场景**: 智能精简学术论文内容
- **标识符**: PP_G001
- **创建日期**: 2026-03-28

**内容**:

```
你是一位专业的日本史学术论文编辑，擅长精简学术论文内容。

请分析以下学术论文内容，识别并删除：
1. 逻辑冗余的论述（重复论证同一观点）
2. 修辞上重复的表达（相同的修饰词反复使用）
3. 非必要的过渡句和重复强调

请务必保留：
1. 核心学术观点和结论
2. 历史史实和重要事件
3. 人物生卒年份和重要事迹
4. 所有脚注、注释和参考文献标注
5. 历史专有名词和学术术语
6. 原文的论证逻辑结构

输出格式要求：
返回JSON格式，包含以下字段：
- "modified_text": 修改后的精简文本（保留所有脚注）
- "deletions": 被删除的内容列表，每项包含"text"和"reason"
- "summary": 精简处理的总结说明

请确保输出是有效的JSON格式。
```

---

## 用户提示词

### [PP_U001] - 段落精简提示词

- **描述**: 精简单个段落内容
- **使用场景**: 调用polish_paragraph方法时使用
- **标识符**: PP_U001
- **创建日期**: 2026-03-28

**内容**:

```
请精简以下日本史学术论文段落：

{paragraph_text}

请返回JSON格式的精简结果，包含：
- "modified_text": 精简后的文本
- "deletions": 被删除的内容列表，每项包含：
  - "text": 被删除的文本内容
  - "reason": 删除原因
- "summary": 精简说明
```

**模板变量说明**:
- `{paragraph_text}`: 待精简的段落文本

---

## 精简规则说明

### 应该删除的内容

1. **逻辑冗余**
   - 重复论证同一观点的段落
   - 多余的举例说明
   - 反复强调的语句

2. **修辞重复**
   - 相同的修饰词反复使用
   - 无意义的强调词
   - 冗长的形容词

3. **非必要过渡**
   - 简单的过渡句
   - 承上启下的废话
   - 无实质内容的连接词

### 应该保留的内容

1. **核心内容**
   - 核心学术观点
   - 研究结论
   - 重要发现

2. **历史信息**
   - 历史事件描述
   - 人物生卒年份
   - 重要事迹

3. **学术规范**
   - 所有脚注标注
   - 参考文献引用
   - 学术术语

4. **论证结构**
   - 论证逻辑链条
   - 因果关系
   - 推理过程

---

## 提示词使用说明

### 使用方法

#### 1. 基础使用

```python
from modules.paper_polisher import PaperPolisher
from prompts.prompt_loader import PromptLoader

loader = PromptLoader()
polisher = PaperPolisher()

# 加载系统提示词
system_prompt = loader.load_prompt('paper_polisher', 'PP_G001')

# 精简单个段落
modified_text, deletions = polisher.polish_paragraph(
    paragraph_text="待精简的段落内容..."
)

# 处理完整文档
result = polisher.process_document(
    input_path='input.docx',
    output_path='output.docx',
    enable_track_changes=True
)
```

#### 2. 使用模板渲染

```python
from prompts.prompt_loader import PromptTemplate

template_loader = PromptTemplate()
prompt = template_loader.load_template(
    'paper_polisher',
    'PP_U001',
    paragraph_text='待精简的段落内容...'
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
- 保持精简规则的一致性
- 注意历史学术论文的特殊性（日本史）
