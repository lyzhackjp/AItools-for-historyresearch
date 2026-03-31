# llm_client 提示词文档

## 模块说明

大语言模型API调用接口模块，支持多种LLM服务商，包括国内模型。

### 支持的提供商
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- 阿里通义千问 (DashScope)
- MiniMax
- 智谱AI (Zhipu)
- 火山引擎 (Volcano)
- DeepSeek
- Ollama (本地部署)

### 核心功能
- 学术性润色（多语言）
- 冗余内容删减
- OCR结果校正
- 文本结构化

---

## 用户提示词

### [LC_U001] - 学术性润色提示词（多语言）

- **描述**: 学术性润色接口，支持中文、日文、英文
- **使用场景**: 调用academic_polish方法时使用
- **标识符**: LC_U001
- **创建日期**: 2026-03-28

**中文版本内容**:

```
你是一位专业的中国历史学学术论文编辑，请对以下文本进行学术性润色，修正语法错误，提升学术表达规范度，删除冗余内容，保持原意。仅输出润色后的文本，不要添加任何解释或评论。
```

**日文版本内容**:

```
あなたは専門の歴史学学術論文編集者として、以下のテキストを学術的に校訂し、文法エラーを修正し、学術表現の規範性を高め、冗長な内容を削除し、元の意味を保つてください。校訂後のテキストのみを出力し、説明やコメントは追加しないでください。
```

**英文版本内容**:

```
As a professional academic paper editor specializing in history, please polish the following text for academic quality, correct grammatical errors, improve academic expression standards, remove redundant content, and maintain the original meaning. Only output the polished text without any explanations or comments.
```

---

### [LC_U002] - 冗余内容删减提示词

- **描述**: 删除文本中的冗余内容
- **使用场景**: 调用remove_redundancy方法时使用
- **标识符**: LC_U002
- **创建日期**: 2026-03-28

**内容**:

```
你是一位专业的学术编辑，请删除以下文本中的冗余内容，包括：
1. 重复的表达
2. 无意义的填充词
3. 过度解释的语句
4. 与主题无关的内容

仅输出处理后的文本，不要添加任何解释。
```

---

### [LC_U003] - OCR结果校正提示词（多语言）

- **描述**: 校正OCR识别结果，支持中文、日文、英文
- **使用场景**: 调用ocr_correction方法时使用
- **标识符**: LC_U003
- **创建日期**: 2026-03-28

**中文版本内容**:

```
你是一位专业的中文OCR结果校正专家，请修正以下OCR识别文本中的错误，包括但不限于：错别字、漏字、多余字符、格式错误等。保持原文的结构和格式，仅输出校正后的文本。
```

**日文版本内容**:

```
あなたは專業的な日本語OCR結果校正專門家です。以下のOCR認識テキストのエラーを修正してください。誤字、脱字、余分な文字、フォーマットエラーなどを含みます。原文の構造とフォーマットを維持し、校正後のテキストのみを出力してください。
```

**英文版本内容**:

```
You are a professional English OCR result correction expert. Please correct errors in the following OCR recognized text, including but not limited to: typos, missing characters, extra characters, formatting errors, etc. Maintain the original structure and format, and only output the corrected text.
```

---

### [LC_U004] - 文本结构化提示词

- **描述**: 将文本转换为结构化数据
- **使用场景**: 调用text_to_structure方法时使用
- **标识符**: LC_U004
- **创建日期**: 2026-03-28

**通用结构化提示词**:

```
请将以下文本转换为JSON格式的结构化数据，保持原文的层次结构。
```

**表格数据提取提示词**:

```
请从以下文本中提取表格数据，输出为JSON数组格式。
```

**键值对提取提示词**:

```
请从以下文本中提取键值对数据，输出为JSON对象格式。
```

**时间线提取提示词**:

```
请从以下文本中提取时间线数据，输出为JSON数组格式，每项包含时间和事件描述。
```

---

## 提示词变体映射

### 语言代码映射

| 语言代码 | 语言名称 | academic_polish | ocr_correction |
|---------|---------|----------------|----------------|
| zh | 中文 | ✅ | ✅ |
| ja | 日文 | ✅ | ✅ |
| en | 英文 | ✅ | ✅ |

### 结构类型映射

| 结构类型 | 提示词 | 输出格式 |
|---------|--------|---------|
| general | 通用结构化 | JSON对象 |
| table | 表格数据 | JSON数组 |
| key_value | 键值对 | JSON对象 |
| timeline | 时间线 | JSON数组 |

---

## 提示词使用说明

### 使用方法

#### 1. 基础使用

```python
from modules.llm_client import LLMClient
from prompts.prompt_loader import PromptLoader

loader = PromptLoader()
client = LLMClient()

# 学术性润色（中文）
polish_prompt = loader.load_prompt('llm_client', 'LC_U001')
polished_text = client.academic_polish(text, language='zh')

# 冗余内容删减
redundancy_prompt = loader.load_prompt('llm_client', 'LC_U002')
cleaned_text = client.remove_redundancy(text)

# OCR校正（日文）
ocr_prompt = loader.load_prompt('llm_client', 'LC_U003')
corrected_text = client.ocr_correction(ocr_text, language='ja')

# 文本结构化
structure_prompt = loader.load_prompt('llm_client', 'LC_U004')
structured_data = client.text_to_structure(text, structure_type='general')
```

#### 2. 获取多语言提示词

```python
from prompts.prompt_loader import PromptLoader

loader = PromptLoader()

# 获取所有提示词
all_prompts = loader.get_all_prompts('llm_client')

# 获取特定提示词
zh_polish = all_prompts.get('LC_U001_zh', '')
ja_polish = all_prompts.get('LC_U001_ja', '')
en_polish = all_prompts.get('LC_U001_en', '')
```

#### 3. 自定义提示词加载

```python
from prompts.prompt_loader import PromptTemplate

template_loader = PromptTemplate()

# 根据语言动态加载提示词
language = 'ja'
if language == 'zh':
    prompt = template_loader.load_template('llm_client', 'LC_U001_zh')
elif language == 'ja':
    prompt = template_loader.load_template('llm_client', 'LC_U001_ja')
else:
    prompt = template_loader.load_template('llm_client', 'LC_U001_en')
```

---

## 版本历史

| 版本 | 日期 | 描述 | 作者 |
|------|------|------|------|
| 1.0 | 2026-03-28 | 初始版本 | AI Assistant |

---

## 维护指南

### 添加新语言支持

1. 在LC_U001和LC_U003中添加新的语言版本
2. 更新语言代码映射表
3. 测试新语言版本

### 修改现有提示词

1. 直接编辑对应语言版本的内容
2. 保持ID命名规范（如LC_U001_zh）
3. 更新版本历史

### 最佳实践

- 所有提示词使用UTF-8编码
- 为每种语言维护独立的提示词版本
- 注意不同语言的表达习惯和学术规范
- 保持提示词的简洁性，避免冗长指令
