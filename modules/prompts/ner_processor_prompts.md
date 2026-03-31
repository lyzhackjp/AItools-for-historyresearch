# ner_processor 提示词文档

## 模块说明

命名实体识别处理器模块，专门用于从日文/中文史料中识别和提取命名实体。

### 核心功能
- 从日文/中文史料中识别命名实体
- 实体类型分类
- 实体关系分析
- 知识图谱节点提取

### 支持的实体类型
- **PERSON**: 人名（历史人物、学者、官员等）
- **LOCATION**: 地名（国家、城市、地区、地理名称）
- **EVENT**: 事件（历史事件、会议、战争等）
- **ORGANIZATION**: 组织（政府机构、团体、企业等）
- **WORK**: 作品（书籍、文献、艺术作品等）
- **DATE**: 日期（历史年代、具体日期）
- **TITLE**: 职衔（官职、爵位、称号等）

---

## 系统提示词

### [NER_G001] - 日本历史NER专家角色设定

- **描述**: 设定LLM为日本历史NER专家
- **使用场景**: _call_llm方法内部使用
- **标识符**: NER_G001
- **创建日期**: 2026-03-28

**内容**:

```
你是一位专精于日本历史的名实体识别专家。
```

---

## 用户提示词

### [NER_U001] - 命名实体识别提示词

- **描述**: 从日文/中文史料中识别命名实体
- **使用场景**: 调用recognize_entities方法时使用
- **标识符**: NER_U001
- **创建日期**: 2026-03-28

**内容**:

```
请从以下日文/中文史料中识别并标注命名实体。

【实体类型定义】
- PERSON（人名）：历史人物、学者、官员、艺术家等
- LOCATION（地名）：国家、城市、地区、山川河流等
- EVENT（事件）：历史事件、会议、战争、改革等
- ORGANIZATION（组织）：政府机构、团体、企业、学校等
- WORK（作品）：书籍、文献、诗歌、艺术品等
- DATE（日期）：历史年代、具体日期、年号等
- TITLE（职衔）：官职、爵位、称号、尊称等

【待识别文本】
{text}

【识别要求】
1. 只识别明确存在的实体，不要推测或创造实体
2. 保持原文的书写方式（日文汉字保持原样）
3. 对于模糊的实体，选择最可能的类型
4. 同一实体在不同上下文可能有不同类型

【输出格式】
请以JSON格式输出，包含以下字段：
- "entities": 实体列表，每项包含：
  - "text": 实体文本
  - "type": 实体类型
  - "start_pos": 在原文中的起始位置
  - "end_pos": 在原文中的结束位置
- "entity_count": 各类型实体的数量统计
```

**模板变量说明**:
- `{text}`: 待识别的日文/中文史料

---

### [NER_U002] - 关系分析提示词

- **描述**: 分析实体之间的关系
- **使用场景**: 调用analyze_relations方法时使用
- **标识符**: NER_U002
- **创建日期**: 2026-03-28

**内容**:

```
请分析以下文本中实体之间的关系。

【已识别实体】
{entities}

【待分析文本】
{text}

【关系类型定义】
- BELONG_TO: 归属关系（属于）
- PART_OF: 部分关系（是...的一部分）
- LOCATED_IN: 位置关系（位于）
- PARTICIPATED_IN: 参与关系（参与）
- CREATED: 创造关系（创作）
- LED_BY: 领导关系（领导）
- OPPOSED_TO: 对立关系（反对）
- ALLIED_WITH: 联盟关系（结盟）
- BEFORE/AFTER: 时间先后关系
- CAUSED: 因果关系（导致）

【分析要求】
1. 只分析明确存在的关系，不要推测
2. 考虑实体在文本中的上下文
3. 优先识别紧密关联的关系

【输出格式】
请以JSON格式输出：
- "relations": 关系列表，每项包含：
  - "entity1": 实体1文本
  - "entity2": 实体2文本
  - "relation_type": 关系类型
  - "description": 关系描述
  - "confidence": 置信度（high/medium/low）
```

**模板变量说明**:
- `{entities}`: 已识别的实体列表
- `{text}`: 原始文本内容

---

## 实体识别扩展

### [NER_U003] - 嵌套实体识别提示词

- **描述**: 识别嵌套的复杂实体
- **使用场景**: 识别包含修饰语的复杂实体时使用
- **标识符**: NER_U003
- **创建日期**: 2026-03-28

**内容**:

```
请识别以下文本中的嵌套实体。

【嵌套实体示例】
- "德川幕府的将军" → 嵌套：将军（核心）+ 德川幕府（限定）
- "明治维新的政治家" → 嵌套：政治家（核心）+ 明治维新（限定）
- "京都大学的教授" → 嵌套：教授（核心）+ 京都大学（所属）

【待识别文本】
{text}

【输出格式】
请以JSON格式输出嵌套实体：
- "nested_entities": 嵌套实体列表，每项包含：
  - "head_entity": 核心实体
  - "modifier": 修饰语
  - "full_entity": 完整实体
  - "type": 实体类型
```

**模板变量说明**:
- `{text}`: 待识别的文本

---

### [NER_U004] - 实体消歧提示词

- **描述**: 对同名实体进行消歧
- **使用场景**: 存在多个同名实体需要区分时使用
- **标识符**: NER_U004
- **创建日期**: 2026-03-28

**内容**:

```
请对以下同名实体进行消歧。

【待消歧实体】
{entity}

【出现上下文】
{contexts}

【消歧要求】
1. 根据上下文信息区分不同实体
2. 提取区分特征（时间、地点、职位等）
3. 为每个实体添加唯一标识符

【输出格式】
请以JSON格式输出：
- "disambiguated_entities": 消歧后的实体列表，每项包含：
  - "entity": 实体文本
  - "identifier": 唯一标识符
  - "distinguishing_features": 区分特征
  - "context": 所在上下文
```

**模板变量说明**:
- `{entity}`: 待消歧的实体名称
- `{contexts}`: 实体出现的上下文列表

---

## 历史特定实体识别

### [NER_U005] - 日本历史特定实体识别

- **描述**: 识别日本历史特有的实体类型
- **使用场景**: 处理日本历史文献时使用
- **标识符**: NER_U005
- **创建日期**: 2026-03-28

**内容**:

```
请从以下日本历史文献中识别特定实体。

【日本历史特有实体类型】
- ERA: 年号（明治、大正昭和等）
- KOKUGO: 国号（大和、奈良、平安等）
- BAKUMU: 幕末特定词汇
- BUKESHO: 武家职名
- KAZOKU: 华族家族名
- ZAISHO: 在所（领地）
- GAKKO: 学校（私塾、江户末期学校等）

【待识别文本】
{text}

【输出格式】
请以JSON格式输出，包含所有实体类型。
```

**模板变量说明**:
- `{text}`: 日本历史文献内容

---

## 提示词使用说明

### 使用方法

#### 1. 基础使用

```python
from modules.ner_processor import NERProcessor
from prompts.prompt_loader import PromptLoader

loader = PromptLoader()
ner = NERProcessor()

# 加载系统提示词
system_prompt = loader.load_prompt('ner_processor', 'NER_G001')

# 识别实体
entities = ner.recognize_entities(
    text="德川家康是江户幕府的开创者..."
)

# 分析关系
relations = ner.analyze_relations(
    entities=entities,
    text="德川家康是江户幕府的开创者..."
)
```

#### 2. 使用模板渲染

```python
from prompts.prompt_loader import PromptTemplate

template_loader = PromptTemplate()

# 加载NER提示词
ner_prompt = template_loader.load_template(
    'ner_processor',
    'NER_U001',
    text='待识别的文本内容...'
)

# 加载关系分析提示词
relation_prompt = template_loader.load_template(
    'ner_processor',
    'NER_U002',
    entities='实体列表JSON...',
    text='原始文本...'
)
```

#### 3. 批量处理

```python
from modules.ner_processor import NERProcessor
from prompts.prompt_loader import PromptLoader

loader = PromptLoader()
ner = NERProcessor()

# 批量识别
texts = ['文本1...', '文本2...', '文本3...']

for text in texts:
    entities = ner.recognize_entities(text)
    print(f"文本: {text[:50]}...")
    print(f"识别实体数: {len(entities)}")
```

---

## 版本历史

| 版本 | 日期 | 描述 | 作者 |
|------|------|------|------|
| 1.0 | 2026-03-28 | 初始版本 | AI Assistant |

---

## 维护指南

### 添加新实体类型

1. 在NER_U001中添加新的实体类型定义
2. 更新实体类型映射
3. 测试新实体类型的识别效果

### 修改现有提示词

1. 直接编辑对应提示词的内容
2. 保持ID不变
3. 更新版本历史

### 最佳实践

- 所有提示词使用UTF-8编码
- 注意日文和中文的实体书写差异
- 保持实体类型的互斥性
- 为复杂实体提供消歧机制
- 考虑历史文献的特殊性
