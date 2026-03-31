# 提示词清单文档

## 概述

本文档记录了项目中所有识别的提示词，为后续的提示词管理优化提供基础清单。

---

## 1. academic_note_generator.py (学术笔记生成器)

### 1.1 系统提示词

#### AN_G001 - 学术研究助理系统提示词
- **文件位置**: `modules/academic_note_generator.py:43`
- **行数**: 第43-67行
- **描述**: 设定LLM为专业学术研究助理和知识管理专家
- **用途**: 生成Obsidian格式的阅读笔记
- **状态**: ✅ 已识别

```python
DEFAULT_SYSTEM_PROMPT = """你是一位专业的学术研究助理和知识管理专家，精通复杂文本分析与Obsidian知识图谱（Knowledge Graph）的构建。

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
"""
```

### 1.2 笔记模板

#### AN_T001 - Obsidian阅读笔记模板
- **文件位置**: `modules/academic_note_generator.py:69`
- **行数**: 第69-84行
- **描述**: 定义Obsidian阅读笔记的标准模板
- **用途**: 标准化笔记输出格式

### 1.3 用户提示词

#### AN_U001 - 笔记生成用户提示词
- **文件位置**: `modules/academic_note_generator.py:370`
- **函数**: `_build_generation_prompt()`
- **描述**: 动态构建的笔记生成提示词
- **输入**: 学术文献文本和元数据

#### AN_U002 - 实体提取提示词
- **文件位置**: `modules/academic_note_generator.py:197`
- **描述**: 从文本中提取指定类型的实体
- **用途**: 实体识别和分类

---

## 2. academic_summarizer.py (学术摘要生成器)

### 2.1 系统提示词

#### AS_G001 - 学术研究助手系统提示词
- **文件位置**: `modules/academic_summarizer.py:40`
- **行数**: 第40-52行
- **描述**: 设定LLM为资深学术研究助手
- **用途**: 学术文献分析与摘要生成
- **状态**: ✅ 已识别

```python
DEFAULT_SYSTEM_PROMPT = """你是一位资深的学术研究助手，专精于学术文献的分析与摘要生成。

你的专长包括：
1. 快速把握学术论文的核心论点
2. 识别研究问题和创新点
3. 提取关键概念和方法论
4. 评估文献的学术价值
5. 判断文献与特定研究主题的相关性

请严格按照JSON格式输出分析结果。"""
```

### 2.2 用户提示词

#### AS_U001 - 抽象式摘要生成提示词
- **文件位置**: `modules/academic_summarizer.py:132`
- **函数**: `generate_abstractive_summary()`
- **描述**: 生成指定长度和风格的抽象式摘要
- **参数**: max_length, style (academic/simple/bullet_points)

#### AS_U002 - 核心研究问题提取提示词
- **文件位置**: `modules/academic_summarizer.py:191`
- **函数**: `extract_research_questions()`
- **描述**: 从文献中提取核心研究问题
- **输出格式**: JSON数组

#### AS_U003 - 核心概念提取提示词
- **文件位置**: `modules/academic_summarizer.py:234`
- **函数**: `extract_core_concepts()`
- **描述**: 提取并分类核心概念
- **用途**: 概念图谱构建

#### AS_U004 - 研究方法提取提示词
- **文件位置**: `modules/academic_summarizer.py:274`
- **函数**: `extract_research_methods()`
- **描述**: 提取文献使用的研究方法
- **输出格式**: JSON格式

#### AS_U005 - 相关性评估提示词
- **文件位置**: `modules/academic_summarizer.py:436`
- **函数**: `evaluate_relevance()`
- **描述**: 评估文献与研究主题的相关度
- **输出格式**: JSON格式

#### AS_U006 - 相关原因分析提示词
- **文件位置**: `modules/academic_summarizer.py:461`
- **函数**: `analyze_relevance()`
- **描述**: 分析文献与研究主题的相关原因

---

## 3. paper_polisher.py (论文精简处理器)

### 3.1 系统提示词

#### PP_G001 - 日本史学术论文编辑系统提示词
- **文件位置**: `modules/paper_polisher.py:41`
- **行数**: 第41-60行
- **描述**: 设定LLM为日本史学术论文编辑专家
- **用途**: 智能精简学术论文内容
- **状态**: ✅ 已识别

```python
DEFAULT_SYSTEM_PROMPT = """你是一位专业的日本史学术论文编辑，擅长精简学术论文内容。

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

请确保输出是有效的JSON格式。"""
```

### 3.2 用户提示词

#### PP_U001 - 段落精简提示词
- **文件位置**: `modules/paper_polisher.py:106`
- **函数**: `polish_paragraph()`
- **描述**: 精简单个段落内容
- **输出格式**: JSON格式

---

## 4. style_transfer.py (文风分析与迁移)

### 4.1 系统提示词

#### ST_G001 - 文风迁移专家系统提示词
- **文件位置**: `modules/style_transfer.py:52`
- **行数**: 第52-58行
- **描述**: 设定LLM为文本风格迁移顶级学术写作助手
- **用途**: 文风矩阵分析和迁移
- **状态**: ✅ 已识别

```python
DEFAULT_SYSTEM_PROMPT = """你是一位精通文本风格迁移的顶级学术写作助手。

你的专长包括：
1. 深度分析文章风格矩阵
2. 识别作者的写作习惯和特征
3. 精确模仿特定作者的文风
4. 进行高质量的文风迁移

请严格按照要求输出分析结果。"""
```

### 4.2 用户提示词

#### ST_U001 - 文风矩阵分析提示词
- **文件位置**: `modules/style_transfer.py:136`
- **函数**: `analyze_style_matrix()`
- **描述**: 四维度文风矩阵分析
- **分析维度**:
  - 句法结构
  - 词汇深度与选择
  - 语气与叙事声音
  - 学术修辞机制
- **输出格式**: JSON格式

#### ST_U002 - 基于文风矩阵的文本改写提示词
- **文件位置**: `modules/style_transfer.py:434`
- **函数**: `transfer_style_with_matrix()`
- **描述**: 根据文风矩阵进行文本改写

#### ST_U003 - 少样本文风模仿提示词
- **文件位置**: `modules/style_transfer.py:471`
- **函数**: `few_shot_style_transfer()`
- **描述**: 基于示例的文风模仿

---

## 5. virtual_persona_chatbot.py (虚拟人格对话系统)

### 5.1 人格配置数据

#### VP_P001 - 福泽谕吉人格配置
- **文件位置**: `modules/virtual_persona_chatbot.py:35`
- **键值**: `PRESET_PERSONAS['fukuzawa']`
- **描述**: 明治启蒙思想家人格设定
- **包含**: 姓名、身份、核心特征、说话风格、词汇等
- **状态**: ✅ 已识别

#### VP_P002 - 丸山真男人格配置
- **文件位置**: `modules/virtual_persona_chatbot.py:86`
- **键值**: `PRESET_PERSONAS['maruyama']`
- **描述**: 战后政治思想史学家人格设定

#### VP_P003 - 涩泽荣一人格配置
- **文件位置**: `modules/virtual_persona_chatbot.py:135`
- **键值**: `PRESET_PERSONAS['shibusawa']`
- **描述**: 近代实业家人格设定

### 5.2 系统提示词生成

#### VP_G001 - 动态人格系统提示词生成器
- **文件位置**: `modules/virtual_persona_chatbot.py:434`
- **函数**: `_generate_persona_system_prompt()`
- **描述**: 根据人格配置动态生成系统提示词
- **用途**: 为每次对话设定角色

### 5.3 用户提示词

#### VP_U001 - 学术咨询对话提示词
- **文件位置**: `modules/virtual_persona_chatbot.py:311`
- **函数**: `consult()`
- **描述**: 以虚拟人格身份进行学术问题咨询

#### VP_U002 - 历史事件评论提示词
- **文件位置**: `modules/virtual_persona_chatbot.py:330`
- **函数**: `comment_on_history()`
- **描述**: 以虚拟人格视角评论历史事件

#### VP_U003 - 角色扮演开始提示词
- **文件位置**: `modules/virtual_persona_chatbot.py:423`
- **函数**: `start_conversation()`
- **描述**: 启动沉浸式角色扮演对话

---

## 6. llm_client.py (LLM客户端)

### 6.1 语言处理提示词

#### LC_U001 - 学术性润色提示词（多语言）
- **文件位置**: `modules/llm_client.py:120`
- **函数**: `academic_polish()`
- **描述**: 学术性润色接口
- **支持语言**: zh（中文）、ja（日文）、en（英文）
- **状态**: ✅ 已识别

```python
language_prompts = {
    'zh': '你是一位专业的中国历史学学术论文编辑，请对以下文本进行学术性润色，'
          '修正语法错误，提升学术表达规范度，删除冗余内容，保持原意。'
          '仅输出润色后的文本，不要添加任何解释或评论。',
    'ja': 'あなたは専門の歴史学学術論文編集者として、以下のテキストを学術的に校訂し、'
          '文法エラーを修正し、学術表現の規範性を高め、冗長な内容を削除し、'
          '元の意味を保つてください。校訂後のテキストのみを出力し、説明やコメントは追加しないでください。',
    'en': 'As a professional academic paper editor specializing in history, '
          'please polish the following text for academic quality, correct grammatical errors, '
          'improve academic expression standards, remove redundant content, and maintain the original meaning. '
          'Only output the polished text without any explanations or comments.'
}
```

#### LC_U002 - 冗余内容删减提示词
- **文件位置**: `modules/llm_client.py:147`
- **函数**: `remove_redundancy()`
- **描述**: 删除文本中的冗余内容
- **状态**: ✅ 已识别

```python
prompt = """你是一位专业的学术编辑，请删除以下文本中的冗余内容，包括：
1. 重复的表达
2. 无意义的填充词
3. 过度解释的语句
4. 与主题无关的内容

仅输出处理后的文本，不要添加任何解释。"""
```

#### LC_U003 - OCR结果校正提示词（多语言）
- **文件位置**: `modules/llm_client.py:169`
- **函数**: `ocr_correction()`
- **描述**: 校正OCR识别结果
- **支持语言**: zh（中文）、ja（日文）、en（英文）
- **状态**: ✅ 已识别

#### LC_U004 - 文本结构化提示词
- **文件位置**: `modules/llm_client.py:198`
- **函数**: `text_to_structure()`
- **描述**: 将文本转换为结构化数据
- **支持类型**: general, table, key_value, timeline
- **状态**: ✅ 已识别

---

## 7. ner_processor.py (命名实体识别处理器)

### 7.1 用户提示词

#### NER_U001 - 命名实体识别提示词
- **文件位置**: `modules/ner_processor.py:140`
- **函数**: `recognize_entities()`
- **描述**: 从日文/中文史料中识别命名实体
- **实体类型**: 人名、地名、事件等
- **状态**: ✅ 已识别

```python
prompt = f"""请从以下日文/中文史料中识别并标注命名实体。
...
"""
```

#### NER_U002 - 关系分析提示词
- **文件位置**: `modules/ner_processor.py:219`
- **函数**: `analyze_relations()`
- **描述**: 分析实体之间的关系
- **用途**: 构建知识图谱

### 7.2 系统提示词片段

#### NER_G001 - NER专家角色设定
- **文件位置**: `modules/ner_processor.py:426`
- **函数**: `_call_llm()`
- **描述**: 设定LLM为日本历史NER专家

```python
full_prompt = f"你是一位专精于日本历史的名实体识别专家。\n\n{prompt}"
```

---

## 提示词统计汇总

### 按模块分布

| 模块名称 | 系统提示词 | 用户提示词 | 总计 |
|---------|----------|----------|------|
| academic_note_generator.py | 1 | 2 | 3 |
| academic_summarizer.py | 1 | 5 | 6 |
| paper_polisher.py | 1 | 1 | 2 |
| style_transfer.py | 1 | 3 | 4 |
| virtual_persona_chatbot.py | 3人格配置 + 1生成器 | 3 | 7+ |
| llm_client.py | 0 | 4 (多语言) | 4+ |
| ner_processor.py | 1 | 2 | 3 |
| **总计** | **8+** | **20+** | **28+** |

### 按提示词类型

- **系统提示词**: 8个
- **用户提示词**: 20+个
- **模板定义**: 1个
- **人格配置**: 3个完整人格设定

---

## 提示词管理优化建议

### 优先级排序

1. **高优先级** - 被多个模块共用的提示词（llm_client.py）
2. **中优先级** - 核心业务逻辑依赖的提示词
3. **低优先级** - 辅助功能的提示词

### 优化策略

1. 建立统一的提示词加载接口
2. 实现提示词的版本控制
3. 添加提示词有效性验证
4. 支持提示词的动态更新
5. 建立提示词性能监控

---

*创建日期：2026-03-28*
*最后更新：2026-03-28*
