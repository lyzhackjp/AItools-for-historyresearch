# citation_normalizer 提示词文档

## 模块说明

引用规范化处理器模块，实现学术引用的规范化处理和批量管理。

### 核心功能
- 格式识别与转换：多格式支持（Chicago, APA, MLA, GB/T 7714等）
- 来源规范化：统一来源格式、版本信息补全
- 引用完整性检查：缺失字段检测、格式错误纠正
- 重复引用识别：自动去重

### 支持的引用格式
- **Chicago**: 芝加哥格式
- **APA**: 美国心理学会格式
- **MLA**: 现代语言协会格式
- **GB/T 7714**: 中国国家标准格式
- **IEEE**: 电气与电子工程师协会格式
- **Harvard**: 哈佛格式

---

## 用户提示词

### [CN_U001] - 引用格式识别提示词

- **描述**: 识别未知格式的引用
- **使用场景**: 处理格式不明确的引用时使用
- **标识符**: CN_U001
- **创建日期**: 2026-03-28

**内容**:

```
请分析以下引用文本，识别其格式类型并提取字段：

引用文本：{citation_text}

可能的格式类型：
- book: 专著
- article: 期刊文章
- dissertation: 学位论文
- conference: 会议论文
- electronic: 电子资源

请以JSON格式输出：
- "detected_format": 检测到的格式类型
- "confidence": 检测置信度 (0-1)
- "fields": 提取的字段对象
```

**模板变量说明**:
- `{citation_text}`: 待分析的引用文本

---

### [CN_U002] - 引用完整性检查提示词

- **描述**: 检查引用字段的完整性
- **使用场景**: 验证引用数据时使用
- **标识符**: CN_U002
- **创建日期**: 2026-03-28

**内容**:

```
请检查以下引用信息的完整性：

引用类型：{citation_type}
已有字段：{existing_fields}

请检查：
1. 是否缺少必填字段
2. 字段格式是否正确
3. 是否有矛盾或错误的信息
4. 是否可以补充缺失信息

必填字段说明：
- book: 作者, 书名, 出版社, 年份
- article: 作者, 文章标题, 期刊名, 年份, 卷号, 页码
- dissertation: 作者, 论文标题, 学位类型, 学校, 年份

请以JSON格式输出：
- "is_complete": 是否完整
- "missing_fields": 缺失字段列表
- "errors": 错误信息列表
- "suggestions": 补充建议
```

**模板变量说明**:
- `{citation_type}`: 引用类型
- `{existing_fields}`: 已有字段

---

### [CN_U003] - 引用格式转换提示词

- **描述**: 将引用转换为目标格式
- **使用场景**: 批量转换引用格式时使用
- **标识符**: CN_U003
- **创建日期**: 2026-03-28

**内容**:

```
请将以下引用信息转换为{target_style}格式：

源格式：{source_format}
引用信息：
- 作者：{author}
- 标题：{title}
- 年份：{year}
- 期刊/出版社：{source}
- 卷号：{volume}
- 期号：{issue}
- 页码：{pages}
- DOI：{doi}
- URL：{url}

{target_style}格式要求：
{format_requirements}

请直接输出转换后的引用文本。
```

**模板变量说明**:
- `{target_style}`: 目标格式名称
- `{source_format}`: 源格式名称
- `{author}`: 作者
- `{title}`: 标题
- `{year}`: 年份
- `{source}`: 来源（期刊名/出版社）
- `{volume}`: 卷号
- `{issue}`: 期号
- `{pages}`: 页码
- `{doi}`: DOI
- `{url}`: URL
- `{format_requirements}`: 目标格式的要求说明

---

## 格式要求说明

### 1. Chicago 格式

**书籍**:
```
Author Last, First. Title in Italic. Place: Publisher, Year.
```

**期刊文章**:
```
Author Last, First. "Article Title." Journal Name, vol. #, no. #, Year, pp. #-#.
```

### 2. APA 格式

**书籍**:
```
Author, A. A. (Year). Title in italics. Publisher.
```

**期刊文章**:
```
Author, A. A. (Year). Article title. Journal Name, Volume(Issue), pages. DOI
```

### 3. GB/T 7714 格式

**书籍**:
```
[序号] 作者. 书名 [M]. 出版地: 出版社, 年份.
```

**期刊文章**:
```
[序号] 作者. 题名 [J]. 刊名, 年, 卷(期): 起止页码.
```

---

## 提示词使用说明

### 使用方法

#### 1. 基础使用

```python
from modules.citation_normalizer import CitationNormalizer
from prompts.prompt_loader import PromptLoader

loader = PromptLoader()
normalizer = CitationNormalizer(style='gb7714')

# 规范化引用列表
citations = [
    "Smith, J. (2020). Research methods. Academic Press.",
    "[1] 张三. 人工智能研究 [J]. 计算机学报, 2020, 40(1): 1-10."
]

normalized = normalizer.normalize(citations)

# 转换格式
converted = normalizer.convert_format(normalized[0], 'apa')

# 验证完整性
report = normalizer.validate(normalized)

# 去重
unique = normalizer.deduplicate(normalized)
```

#### 2. 使用模板渲染

```python
from prompts.prompt_loader import PromptTemplate

template_loader = PromptTemplate()

# 加载格式识别提示词
recognition_prompt = template_loader.load_template(
    'citation_normalizer',
    'CN_U001',
    citation_text='待分析的引用...'
)

# 加载完整性检查提示词
validation_prompt = template_loader.load_template(
    'citation_normalizer',
    'CN_U002',
    citation_type='article',
    existing_fields='作者、标题、年份...'
)

# 加载格式转换提示词
conversion_prompt = template_loader.load_template(
    'citation_normalizer',
    'CN_U003',
    target_style='APA',
    source_format='Chicago',
    author='Smith, John',
    title='Research Methods',
    year='2020',
    source='Academic Press',
    format_requirements='APA格式要求...'
)
```

---

## 版本历史

| 版本 | 日期 | 描述 | 作者 |
|------|------|------|------|
| 1.0 | 2026-03-28 | 初始版本 | AI Assistant |

---

## 维护指南

### 添加新引用格式

1. 在SUPPORTED_STYLES列表中添加新格式
2. 添加格式识别正则表达式
3. 实现格式转换方法
4. 更新格式要求说明文档
5. 添加对应的提示词

### 修改现有提示词

1. 直接编辑对应章节的内容
2. 保持ID不变
3. 更新版本历史中的描述

### 最佳实践

- 所有提示词使用UTF-8编码
- JSON输出格式的提示词必须明确输出格式要求
- 为不同引用类型提供独立的提示词
- 保持格式转换的一致性
