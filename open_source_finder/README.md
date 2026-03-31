# OpenSourceFinder 模块

## 📖 概述

OpenSourceFinder 是一个智能的开源模块搜索与优化整合工具，专门设计用于在 GitHub 和 HuggingFace 上搜索相关的开源项目，评估其质量和适用性，生成优化整合报告，并支持自动化的优化执行工作。

## ✨ 核心功能

### 1. 多平台搜索

- **GitHub 仓库搜索**
  - 支持关键词搜索 Python 项目
  - 自动获取 README 内容
  - 获取 stars、forks、issues 等元数据

- **HuggingFace 模型搜索**
  - 搜索相关的预训练模型
  - 获取下载量、点赞数等信息
  - 支持 pipeline_tag 等详细信息

### 2. 智能评分系统

- **GitHub 仓库评分**（权重分配）
  - ⭐ Stars: 40%
  - 🍴 Forks: 20%
  - 👁 Watchers: 15%
  - 🐛 Issues: 10%
  - 🏷 Topics: 15%

- **HuggingFace 模型评分**
  - 📥 Downloads: 50%
  - ❤️ Likes: 30%
  - 🏷 Tags: 20%

### 3. 过滤与排序

- 自定义最小阈值
- 自动去重处理
- 综合评分排序

### 4. 智能报告生成

- LLM 驱动的智能分析
- GitHub 仓库推荐
- HuggingFace 模型推荐
- 整合建议
- 优先级行动计划
- 工作量估算

### 5. 优化执行

- 生成优化计划
- 文件备份机制
- 可选的自动应用

## 🏗️ 目录结构

```
open_source_finder/
├── src/                          # 源代码目录
│   ├── __init__.py
│   ├── open_source_finder.py     # 主模块文件（1200+行）
│   └── open_source_finder_example.py  # 示例代码
├── tests/                         # 测试目录
│   ├── test_ocr_optimization.py  # OCR优化测试
│   ├── integration_report.json
│   ├── ocr_optimization_integration_report.json
│   ├── ocr_optimization_report.json
│   ├── ocr_optimization_search.json
│   ├── ocr_optimization_search_results.json
│   └── search_results.json
├── docs/                         # 文档目录
│   ├── OPEN_SOURCE_FINDER_SUMMARY.md  # 功能总结
│   ├── QUICK_REFERENCE.md       # 快速参考卡
│   └── FINAL_REPORT.md          # 最终报告
├── __init__.py                   # 模块初始化
├── open_source_quick_start.py    # 快速启动脚本
└── README.md                     # 本文档
```

## 🚀 快速开始

### 一行命令快速启动

```bash
cd open_source_finder
python open_source_quick_start.py
```

### 三行代码快速使用

```python
from open_source_finder import OpenSourceFinder

finder = OpenSourceFinder(test_mode=True)
results = finder.search_all('ocr_processor', '日文OCR识别')
```

### 完整工作流

```python
from open_source_finder import OpenSourceFinder

finder = OpenSourceFinder(test_mode=True)

# 1. 搜索
results = finder.search_all('ocr_processor', '日文OCR识别')

# 2. 过滤
filtered = finder.rank_and_filter(results, min_stars=50)

# 3. 生成报告
report = finder.generate_integration_report(filtered, 'ocr_processor', '日文OCR')

# 4. 保存
finder.save_report(report, 'optimization_report.json')

# 5. 优化
optimization = finder.execute_optimization(report, 'modules/ocr_processor.py')
```

## 📚 核心组件

### OpenSourceFinder

主类，提供完整的开源模块搜索和优化功能。

```python
from open_source_finder import OpenSourceFinder

finder = OpenSourceFinder(
    api_provider='qwen',     # LLM API服务商
    test_mode=True,          # 测试模式
    github_token=None        # GitHub Token（可选）
)
```

### 主要方法

#### search_all()

统一搜索 GitHub 和 HuggingFace。

```python
results = finder.search_all(
    module_name='ocr_processor',
    context='日文OCR识别',
    keywords=['ocr', 'japanese ocr']
)
```

#### search_github()

仅搜索 GitHub 仓库。

```python
repos = finder.search_github(
    query='easyocr python',
    limit=10,
    language='python'
)
```

#### search_huggingface()

仅搜索 HuggingFace 模型。

```python
models = finder.search_huggingface(
    query='japanese ocr',
    limit=10
)
```

#### rank_and_filter()

过滤和排序搜索结果。

```python
filtered = finder.rank_and_filter(
    results,
    min_stars=100,
    min_downloads=5000
)
```

#### generate_integration_report()

生成优化整合报告。

```python
report = finder.generate_integration_report(
    results,
    module_name='ocr_processor',
    context='日文OCR识别'
)
```

#### execute_optimization()

执行优化工作。

```python
optimization = finder.execute_optimization(
    report,
    target_module_path='modules/ocr_processor.py',
    apply_changes=False  # True=自动应用
)
```

## 🎯 使用场景

### 场景 1: OCR 模块优化

```python
from open_source_finder import OpenSourceFinder

finder = OpenSourceFinder(test_mode=True)

results = finder.search_all(
    'ocr_processor',
    '日文史料OCR识别',
    keywords=['ocr', 'easyocr', 'japanese ocr']
)

report = finder.generate_integration_report(
    results,
    'ocr_processor',
    '日文OCR'
)

finder.save_report(report, 'ocr_optimization_report.json')
```

### 场景 2: NER 模块优化

```python
from open_source_finder import OpenSourceFinder

finder = OpenSourceFinder(test_mode=True)

results = finder.search_all(
    'ner_processor',
    '日文命名实体识别',
    keywords=['ner', 'japanese ner', 'entity extraction']
)

report = finder.generate_integration_report(
    results,
    'ner_processor',
    '日文NER'
)

finder.save_report(report, 'ner_optimization_report.json')
```

### 场景 3: 自定义搜索

```python
from open_source_finder import OpenSourceFinder

finder = OpenSourceFinder(test_mode=True)

# 仅搜索 GitHub
repos = finder.search_github('japanese deep learning ocr', limit=15)

# 仅搜索 HuggingFace
models = finder.search_huggingface('japanese text recognition', limit=15)
```

## 📊 评分算法详解

### GitHub 仓库评分公式

```
score = (min(stars/1000, 1.0) × 40)
      + (min(forks/200, 1.0) × 20)
      + (min(watchers/500, 1.0) × 15)
      + (issues_score × 10)
      + (min(len(topics)/5, 1.0) × 15)
```

### HuggingFace 模型评分公式

```
score = (min(downloads/100000, 1.0) × 50)
      + (min(likes/1000, 1.0) × 30)
      + (min(len(tags)/10, 1.0) × 20)
```

## 🔧 API 配置

### 支持的 API 提供商

- `qwen`: 阿里云通义千问（默认）
- `openai`: OpenAI GPT 系列
- `zhipu`: 智谱 AI
- `deepseek`: DeepSeek
- `ollama`: Ollama 本地模型

### GitHub Token 配置

提供 GitHub Token 可提高 API 调用限制：

```python
import os

github_token = os.getenv('GITHUB_TOKEN')
finder = OpenSourceFinder(github_token=github_token)
```

## 📖 相关文档

- [功能总结](docs/OPEN_SOURCE_FINDER_SUMMARY.md) - 详细的功能说明和技术架构
- [快速参考卡](docs/QUICK_REFERENCE.md) - 常用命令和参数速查
- [最终报告](docs/FINAL_REPORT.md) - 开发完成报告

## 🧪 测试

### 运行示例

```bash
# 运行所有示例
cd src
python open_source_finder_example.py

# 运行 OCR 优化测试
cd tests
python test_ocr_optimization.py
```

### 快速测试

```bash
# 快速启动
python open_source_quick_start.py
```

## 🔍 与 LearningModule 的关系

本模块（OpenSourceFinder）专注于开源项目的搜索和整合。

如需进行学术资源检索和文献分析，请使用独立的 **LearningModule** 模块：

```python
# 使用 LearningModule 进行学术研究
from learning_module import LearningModule

learner = LearningModule(api_provider='qwen', test_mode=False)
result = learner.analyze_and_suggest(
    module_name='ocr_processor',
    context='日文OCR识别'
)
```

详见 [LearningModule 文档](../learning_module/README.md)

## 📝 注意事项

1. **API 限制**: GitHub API 有调用频率限制，建议提供 GitHub Token
2. **测试模式**: 使用 `test_mode=True` 进行开发测试，避免消耗 API 配额
3. **数据准确性**: 建议人工审核生成的优化建议
4. **备份**: 执行优化前建议备份原文件

## 🐛 常见问题

### Q: 如何提高搜索质量？

使用更具体的关键词：
```python
keywords = [
    'easyocr',                    # 具体的库名
    'japanese ocr',               # 具体语言
    'handwriting recognition'      # 具体任务
]
```

### Q: API 限制怎么处理？

设置 GitHub Token 提高限制：
```python
finder = OpenSourceFinder(github_token='your-token')
```

### Q: LLM 不可用时怎么办？

模块会自动切换到基础评分模式，生成简化的报告。

### Q: 如何评估推荐质量？

查看每个推荐项的：
- 综合评分（score）
- 整合难度（integration_difficulty）
- 相关性（与应用场景的匹配度）

## 🎨 整合难度标识

| 标识 | 含义 | GitHub Stars | HuggingFace Downloads |
|------|------|-------------|----------------------|
| 🟢 easy | 易于整合 | >5000 | >50000 |
| 🟡 medium | 中等难度 | 1000-5000 | 10000-50000 |
| 🔴 hard | 较难整合 | <1000 | <10000 |

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

## 📄 许可

与主项目保持一致。

## 📞 联系方式

如有问题，请查阅相关文档或提交 Issue。

---

**版本**: 1.0.0
**创建日期**: 2026-03-29
**状态**: ✅ 生产就绪
