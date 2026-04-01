# IntelligentResearchAssistant API 文档

## 概述

`IntelligentResearchAssistant` 是一个整合了开源项目搜索、学术文献分析和报告生成的智能研究助手模块。它整合了 `open_source_finder` 和 `learning_module` 的功能，提供统一的对外接口。

## 安装

```bash
# 确保Python版本 >= 3.7
python --version

# 安装依赖
pip install requests
```

## 快速开始

```python
from intelligent_research_assistant import IntelligentResearchAssistant

# 初始化助手
assistant = IntelligentResearchAssistant(
    api_provider='qwen',
    test_mode=False
)

# 搜索项目
projects = assistant.search_projects('machine learning', limit=10)

# 搜索论文
papers = assistant.search_papers('deep learning', limit=10)

# 分析项目
analysis = assistant.analyze_project(projects[0])

# 生成报告
report = assistant.generate_report(projects, [analysis])
```

---

## 核心类

### IntelligentResearchAssistant

主助手类，整合所有功能。

#### 初始化参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `api_provider` | str | 'qwen' | API提供商 ('qwen', 'openai', 'minimax', 'zhipu', 'deepseek', 'ollama') |
| `model` | str | None | 模型名称（可选） |
| `test_mode` | bool | False | 测试模式，不调用真实API |
| `cache_enabled` | bool | True | 是否启用缓存 |
| `cache_ttl_days` | int | 7 | 缓存有效期（天） |

#### 示例

```python
# 使用通义千问
assistant = IntelligentResearchAssistant(
    api_provider='qwen',
    model='qwen-max'
)

# 使用OpenAI
assistant = IntelligentResearchAssistant(
    api_provider='openai',
    model='gpt-4'
)

# 测试模式
assistant = IntelligentResearchAssistant(
    api_provider='qwen',
    test_mode=True
)
```

---

## 搜索功能

### search_projects()

搜索开源项目。

#### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `query` | str | 必填 | 搜索查询 |
| `platforms` | List[str] | None | 平台列表（默认所有平台） |
| `limit` | int | 50 | 结果数量限制 |

#### 返回值

`List[SearchResult]`: 搜索结果列表

#### 示例

```python
# 基本搜索
projects = assistant.search_projects('machine learning')

# 指定平台
projects = assistant.search_projects(
    query='deep learning',
    platforms=['github'],
    limit=20
)

# 遍历结果
for project in projects:
    print(f"标题: {project.title}")
    print(f"URL: {project.url}")
    print(f"评分: {project.score}")
```

### search_papers()

搜索学术论文。

#### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `query` | str | 必填 | 搜索查询 |
| `sources` | List[str] | None | 数据源列表（默认所有源） |
| `limit` | int | 50 | 结果数量限制 |

#### 返回值

`List[SearchResult]`: 搜索结果列表

#### 示例

```python
# 搜索论文
papers = assistant.search_papers('transformer architecture')

# 指定数据源
papers = assistant.search_papers(
    query='BERT',
    sources=['arxiv'],
    limit=30
)

# 遍历结果
for paper in papers:
    print(f"标题: {paper.title}")
    print(f"作者: {paper.metadata.get('authors', [])}")
    print(f"发表时间: {paper.metadata.get('published', '')}")
```

---

## 分析功能

### analyze_project()

分析开源项目。

#### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `result` | SearchResult | 必填 | 搜索结果 |
| `analysis_depth` | str | 'deep' | 分析深度 ('shallow', 'medium', 'deep') |

#### 返回值

`AnalysisResult`: 分析结果

#### 示例

```python
# 分析项目
analysis = assistant.analyze_project(projects[0])

print(f"概述: {analysis.summary}")
print(f"关键发现: {analysis.key_findings}")
print(f"技术要点: {analysis.technical_points}")
print(f"建议: {analysis.recommendations}")
print(f"置信度: {analysis.confidence}")
```

### analyze_paper()

分析学术论文。

#### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `result` | SearchResult | 必填 | 搜索结果 |
| `analysis_depth` | str | 'deep' | 分析深度 |

#### 返回值

`AnalysisResult`: 分析结果

#### 示例

```python
# 分析论文
analysis = assistant.analyze_paper(papers[0])

print(f"概述: {analysis.summary}")
print(f"研究方法: {analysis.technical_points}")
print(f"创新点: {analysis.key_findings}")
```

### analyze_literature()

分析文献内容。

#### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `summary` | str | 必填 | 文献摘要 |
| `key_findings` | List[str] | None | 关键发现列表 |
| `context` | str | '' | 上下文信息 |

#### 返回值

`AnalysisResult`: 分析结果

#### 示例

```python
# 分析文献
analysis = assistant.analyze_literature(
    summary='BERT是一种预训练语言模型...',
    key_findings=['双向编码', '预训练-微调范式'],
    context='NLP研究'
)
```

---

## 生成功能

### generate_report()

生成综合报告。

#### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `search_results` | List[SearchResult] | 必填 | 搜索结果列表 |
| `analysis_results` | List[AnalysisResult] | 必填 | 分析结果列表 |
| `title` | str | '综合分析报告' | 报告标题 |

#### 返回值

`Report`: 生成的报告

#### 示例

```python
# 生成报告
report = assistant.generate_report(
    search_results=projects + papers,
    analysis_results=analyses,
    title='深度学习研究报告'
)

# 保存报告
report.save('report.md')

# 访问报告内容
print(report.content)
print(report.sections)
```

### generate_improvements()

生成改进建议。

#### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `module_name` | str | 必填 | 模块名称 |
| `context` | str | 必填 | 应用上下文 |
| `research_findings` | Dict | None | 研究发现 |
| `literature_insights` | Dict | None | 文献洞察 |

#### 返回值

`ImprovementSuggestion`: 改进建议

#### 示例

```python
# 生成改进建议
suggestion = assistant.generate_improvements(
    module_name='ner_recognizer',
    context='日文史料实体识别',
    research_findings={
        'summary': 'BERT在NER任务中表现优异',
        'key_findings': ['预训练效果显著']
    }
)

print(f"短期建议: {suggestion.short_term}")
print(f"中期建议: {suggestion.medium_term}")
print(f"长期建议: {suggestion.long_term}")
print(f"优先级: {suggestion.priority}")
```

---

## 高级功能

### analyze_module_optimization()

模块优化分析 - 一站式服务。

#### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `module_name` | str | 必填 | 模块名称 |
| `context` | str | 必填 | 应用上下文 |
| `search_limit` | int | 50 | 搜索数量限制 |
| `analysis_depth` | str | 'deep' | 分析深度 |

#### 返回值

`Dict`: 完整的分析结果，包含搜索结果、分析结果、报告和改进建议

#### 示例

```python
# 一站式模块优化分析
result = assistant.analyze_module_optimization(
    module_name='ner_recognizer',
    context='日文史料实体识别',
    search_limit=30,
    analysis_depth='deep'
)

# 访问结果
projects = result['search_results']['projects']
papers = result['search_results']['papers']
report = result['report']
suggestion = result['improvement_suggestion']

# 保存报告
with open('optimization_report.md', 'w', encoding='utf-8') as f:
    f.write(report['content'])
```

---

## 数据模型

### SearchResult

搜索结果数据模型。

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `id` | str | 唯一标识符 |
| `title` | str | 标题 |
| `source` | str | 来源平台 |
| `url` | str | URL链接 |
| `description` | str | 描述 |
| `score` | float | 评分 |
| `metadata` | Dict | 元数据 |

#### 方法

- `to_dict()`: 转换为字典
- `from_dict(data)`: 从字典创建

### AnalysisResult

分析结果数据模型。

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `source_id` | str | 来源ID |
| `analysis_type` | str | 分析类型 |
| `summary` | str | 概述 |
| `key_findings` | List[str] | 关键发现 |
| `technical_points` | List[str] | 技术要点 |
| `recommendations` | List[str] | 建议 |
| `confidence` | float | 置信度 |
| `metadata` | Dict | 元数据 |

### Report

报告数据模型。

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `title` | str | 标题 |
| `content` | str | 内容 |
| `format` | str | 格式 |
| `sections` | List[Dict] | 章节 |
| `metadata` | Dict | 元数据 |

#### 方法

- `save(filepath)`: 保存到文件
- `to_dict()`: 转换为字典
- `from_dict(data)`: 从字典创建

### ImprovementSuggestion

改进建议数据模型。

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `module_name` | str | 模块名称 |
| `context` | str | 应用上下文 |
| `short_term` | List[str] | 短期建议 |
| `medium_term` | List[str] | 中期建议 |
| `long_term` | List[str] | 长期建议 |
| `code_examples` | List[str] | 代码示例 |
| `priority` | str | 优先级 |
| `confidence` | float | 置信度 |

---

## 配置

### 环境变量

```bash
# API密钥
export DASHSCOPE_API_KEY="your-qwen-api-key"
export OPENAI_API_KEY="your-openai-api-key"
export MINIMAX_API_KEY="your-minimax-api-key"
export ZHIPU_API_KEY="your-zhipu-api-key"
export DEEPSEEK_API_KEY="your-deepseek-api-key"

# GitHub Token（可选，用于提高API限制）
export GITHUB_TOKEN="your-github-token"
```

### 配置文件

配置文件位于 `intelligent_research_assistant/config/settings.yaml`。

```yaml
llm:
  default_provider: qwen
  providers:
    qwen:
      model: qwen-max
      temperature: 0.7
    openai:
      model: gpt-4
      temperature: 0.7

cache:
  enabled: true
  ttl_days: 7
  max_size: 1000

search:
  default_limit: 50
  timeout: 30
```

---

## 错误处理

```python
from intelligent_research_assistant import IntelligentResearchAssistant
from intelligent_research_assistant.core.exceptions import APIError, SearchError

assistant = IntelligentResearchAssistant()

try:
    results = assistant.search_projects('test')
except SearchError as e:
    print(f"搜索错误: {e}")
except APIError as e:
    print(f"API错误: {e}")
except Exception as e:
    print(f"未知错误: {e}")
```

---

## 最佳实践

### 1. 使用缓存

```python
# 启用缓存（默认）
assistant = IntelligentResearchAssistant(cache_enabled=True)

# 禁用缓存
assistant = IntelligentResearchAssistant(cache_enabled=False)
```

### 2. 批量处理

```python
# 批量分析
projects = assistant.search_projects('ml', limit=20)

analyses = []
for project in projects:
    analysis = assistant.analyze_project(project, analysis_depth='shallow')
    analyses.append(analysis)
```

### 3. 选择合适的分析深度

```python
# 快速分析（shallow）- 适合大量数据
quick_analysis = assistant.analyze_project(project, analysis_depth='shallow')

# 深度分析（deep）- 适合重要项目
deep_analysis = assistant.analyze_project(project, analysis_depth='deep')
```

### 4. 合理设置搜索限制

```python
# 小规模搜索
results = assistant.search_projects('test', limit=10)

# 中等规模
results = assistant.search_projects('test', limit=50)

# 大规模（注意API限制）
results = assistant.search_projects('test', limit=100)
```

---

## 常见问题

### Q: 如何选择API提供商？

A: 根据您的需求和预算选择：
- **通义千问 (qwen)**: 性价比高，中文支持好
- **OpenAI**: 效果好，价格较高
- **智谱AI (zhipu)**: 国产替代，性价比高
- **DeepSeek**: 新兴选择，价格实惠

### Q: 如何提高搜索速度？

A: 
1. 启用缓存
2. 减少搜索限制
3. 使用较浅的分析深度
4. 并发处理多个查询

### Q: 如何处理大量数据？

A: 
1. 分批处理
2. 使用缓存
3. 定期清理缓存
4. 监控内存使用

---

## 更新日志

### v1.0.0 (2024-01)
- 初始版本
- 整合open_source_finder和learning_module
- 统一API接口
- 添加缓存支持
- 完善测试覆盖

---

## 联系方式

如有问题或建议，请提交Issue或Pull Request。
