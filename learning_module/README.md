# 学习模块 (Learning Module)

## 📖 概述

学习模块是本项目的一个智能学习与研究辅助组件，旨在为其他模块提供自动化的学术资源检索、文献分析和功能改进建议生成能力。通过整合最新的研究成果和最佳实践，帮助开发者和研究人员持续优化模块功能。

## ✨ 核心功能

### 1. 学术资源自动检索与信息提取

自动检索指定技术领域的学术资源，提取关键信息：
- 研究背景与现状概述
- 关键技术方法和原理
- 最新研究进展（近3年）
- 主要应用场景和案例
- 发展趋势与未来方向

### 2. 研究文献分析与技术要点提取

深入分析研究文献的核心内容：
- 核心技术和方法论识别
- 可借鉴的实现建议提取
- 最佳实践和经验总结
- 局限性和注意事项归纳

### 3. 模块功能改进建议生成

基于研究成果和文献分析，生成针对性的改进建议：
- 短期改进（快速实现）
- 中期改进（需要开发周期）
- 长期改进（架构重构）
- 具体代码示例
- 优先级排序

## 🏗️ 目录结构

```
learning_module/
├── src/                          # 源代码目录
│   ├── __init__.py
│   ├── research_analyzer.py      # 学术资源检索分析器
│   ├── literature_analyzer.py    # 文献分析器
│   ├── improvement_generator.py  # 改进建议生成器
│   └── prompts.py               # 提示词集合
├── tests/                        # 测试目录
│   ├── test_learning_module.py
│   ├── test_learning_module_v2.py
│   ├── learning_test_results.json
│   ├── learning_test_results_v2.json
│   ├── ner_optimization_research.py
│   ├── ner_optimization_with_api.py
│   ├── direct_api_test.py
│   ├── quick_test.py
│   ├── simple_api_test.py
│   ├── simple_api_test_secured.py
│   ├── test_run.py
│   ├── run_api_test.bat
│   └── run_test.ps1
├── docs/                         # 文档目录
│   ├── DEVELOPMENT_REPORT.md
│   ├── example_usage.py
│   └── quick_start.py
├── __init__.py                   # 模块初始化
└── README.md                     # 本文档
```

## 🚀 快速开始

### 基本使用

```python
from learning_module import LearningModule

# 初始化学习模块
learner = LearningModule(api_provider='qwen', test_mode=False)

# 综合分析和生成改进建议
result = learner.analyze_and_suggest(
    module_name='ner_processor',
    context='日文史料中的历史实体识别',
    research_topic='Japanese historical NER'
)

print(result)
```

### 测试模式

```python
from learning_module import LearningModule

# 使用测试模式（不调用真实API）
learner = LearningModule(api_provider='qwen', test_mode=True)

result = learner.analyze_and_suggest(
    module_name='ocr_processor',
    context='日文OCR识别'
)

print(result)
```

## 📚 核心组件

### ResearchAnalyzer

学术资源检索分析器，用于自动检索学术研究资源。

```python
from learning_module import ResearchAnalyzer

analyzer = ResearchAnalyzer(api_provider='qwen', test_mode=False)

findings = analyzer.search_research(
    topic='Japanese NER',
    focus_areas=['技术原理', '最新进展', '应用案例']
)

print(findings)
```

### LiteratureAnalyzer

文献分析器，用于深入分析研究文献。

```python
from learning_module import LiteratureAnalyzer

analyzer = LiteratureAnalyzer(api_provider='qwen', test_mode=False)

analysis = analyzer.analyze_literature(
    summary='研究摘要...',
    key_findings=['发现1', '发现2']
)

print(analysis)
```

### ImprovementGenerator

改进建议生成器，用于生成模块改进建议。

```python
from learning_module import ImprovementGenerator

generator = ImprovementGenerator(api_provider='qwen', test_mode=False)

improvements = generator.generate_improvements(
    module_name='ner_processor',
    context='日文史料处理',
    research_findings={'summary': '...', 'trends': [...]},
    literature_insights={'technical_points': [...], 'impl_suggestions': [...]}
)

print(improvements)
```

## 🔧 API 配置

### 支持的 API 提供商

- `qwen`: 阿里云通义千问（默认）
- `openai`: OpenAI GPT 系列
- `zhipu`: 智谱 AI
- `deepseek`: DeepSeek
- `ollama`: Ollama 本地模型

### 环境变量配置

```bash
# 阿里云通义千问
export DASHSCOPE_API_KEY='your-dashscope-api-key'

# OpenAI
export OPENAI_API_KEY='your-openai-api-key'

# 智谱AI
export ZHIPU_API_KEY='your-zhipu-api-key'
```

## 📋 测试

### 运行测试

```bash
# 运行所有测试
cd tests
python test_learning_module.py

# 运行测试v2
python test_learning_module_v2.py
```

### 批量测试

```bash
# Windows
run_test.ps1

# Linux/Mac
bash run_test.sh
```

## 📖 相关文档

- [开发报告](docs/DEVELOPMENT_REPORT.md) - 模块开发历程和技术细节
- [使用示例](docs/example_usage.py) - 详细的使用示例代码
- [快速启动](docs/quick_start.py) - 快速启动脚本

## 🎯 使用场景

### 场景 1: NER 模块优化

```python
from learning_module import LearningModule

learner = LearningModule(api_provider='qwen', test_mode=False)

result = learner.analyze_and_suggest(
    module_name='ner_processor',
    context='日文史料中的历史实体识别',
    research_topic='Japanese historical NER'
)

# 获取改进建议
improvements = result['improvements']
print(f"短期改进: {improvements['short_term_improvements']}")
print(f"中期改进: {improvements['medium_term_improvements']}")
print(f"长期改进: {improvements['long_term_improvements']}")
```

### 场景 2: OCR 模块优化

```python
from learning_module import LearningModule

learner = LearningModule(api_provider='qwen', test_mode=False)

result = learner.analyze_and_suggest(
    module_name='ocr_processor',
    context='日文古籍OCR识别',
    research_topic='Japanese OCR handwriting recognition'
)

print(result)
```

### 场景 3: 提示词优化

```python
from learning_module import LearningModule

learner = LearningModule(api_provider='qwen', test_mode=False)

optimization = learner.suggest_prompt_optimization(
    current_prompt='请提取文本中的人名和地名',
    task_type='命名实体识别'
)

print(optimization)
```

## 🔍 与 OpenSourceFinder 的关系

本模块（LearningModule）专注于学术资源检索和文献分析。

如需在 GitHub 和 HuggingFace 上搜索开源项目，请使用独立的 **OpenSourceFinder** 模块：

```python
# 使用 OpenSourceFinder 搜索开源解决方案
from open_source_finder import OpenSourceFinder

finder = OpenSourceFinder(api_provider='qwen', test_mode=False)
results = finder.search_all('ocr_processor', '日文OCR')
report = finder.generate_integration_report(results, 'ocr_processor', '日文OCR')
```

详见 [OpenSourceFinder 文档](../open_source_finder/README.md)

## 📝 注意事项

1. **API 配额**: 使用真实 API 时注意配额限制，建议使用 `test_mode=True` 进行开发测试
2. **网络连接**: 学术资源检索需要稳定的网络连接
3. **数据准确性**: 建议人工审核生成的改进建议
4. **版本兼容性**: 确保 LLM API 版本兼容

## 🐛 常见问题

### Q: 如何切换 API 提供商？

```python
learner = LearningModule(api_provider='openai', test_mode=False)
```

### Q: 测试模式与真实模式的区别？

- **测试模式**: 使用模拟数据，不调用真实 API
- **真实模式**: 调用真实 API，获取真实研究结果

### Q: 如何处理 API 调用失败？

模块内置了重试机制和错误处理，如遇问题请检查：
1. 网络连接
2. API 密钥配置
3. API 配额

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

## 📄 许可

与主项目保持一致。

## 📞 联系方式

如有问题，请查阅相关文档或提交 Issue。

---

**版本**: 1.0.0
**创建日期**: 2026-03-28
**最后更新**: 2026-03-29
**状态**: ✅ 生产就绪
