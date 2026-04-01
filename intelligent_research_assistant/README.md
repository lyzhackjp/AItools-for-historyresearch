# 智能研究助手模块

## 📖 概述

智能研究助手是一个整合了OpenSourceFinder和LearningModule的统一模块，提供开源项目搜索、学术文献分析、报告生成等一站式服务。

## 🏗️ 目录结构

```
intelligent_research_assistant/
├── core/                           # 核心层
│   ├── __init__.py
│   ├── llm_manager.py              # 统一LLM管理器
│   ├── cache_manager.py            # 统一缓存管理器
│   ├── config_manager.py           # 统一配置管理器
│   └── data_models.py              # 统一数据模型
│
├── search/                         # 搜索层
│   ├── __init__.py
│   ├── project_finder.py           # 项目搜寻器
│   ├── paper_finder.py             # 论文搜寻器
│   ├── document_fetcher.py         # 文档获取器
│   └── adapters/                   # 平台适配器
│       ├── github_adapter.py
│       ├── arxiv_adapter.py
│       └── pwc_adapter.py
│
├── analysis/                       # 分析层
│   ├── __init__.py
│   ├── project_analyzer.py         # 项目分析器
│   ├── paper_analyzer.py           # 论文分析器
│   ├── literature_analyzer.py      # 文献分析器
│   └── trend_analyzer.py           # 趋势分析器
│
├── generation/                     # 生成层
│   ├── __init__.py
│   ├── report_generator.py         # 报告生成器
│   ├── improvement_generator.py    # 改进建议生成器
│   └── summary_generator.py        # 摘要生成器
│
├── storage/                        # 存储层
│   ├── __init__.py
│   ├── document_store.py           # 文档存储
│   ├── report_store.py             # 报告存储
│   └── cache_store.py              # 缓存存储
│
├── utils/                          # 工具层
│   ├── __init__.py
│   ├── data_structurer.py          # 数据结构化
│   ├── pdf_processor.py            # PDF处理
│   └── validators.py               # 数据验证
│
├── config/                         # 配置层
│   ├── __init__.py
│   ├── default_config.json         # 默认配置
│   └── prompts/                    # 提示词库
│       ├── search_prompts.md
│       ├── analysis_prompts.md
│       └── generation_prompts.md
│
├── tests/                          # 测试层
│   ├── __init__.py
│   ├── test_integration.py
│   └── test_workflows.py
│
├── __init__.py                     # 模块初始化
├── intelligent_assistant.py        # 主助手类
└── README.md                       # 本文档
```

## 🚀 快速开始

```python
from intelligent_research_assistant import IntelligentResearchAssistant

# 初始化助手
assistant = IntelligentResearchAssistant(api_provider='qwen')

# 模块优化分析
result = assistant.analyze_module_optimization(
    module_name='ocr_processor',
    context='日文史料OCR识别',
    search_limit=100
)

# 技术趋势分析
trends = assistant.analyze_technology_trends(
    technology='NER',
    time_range='12months'
)

# 竞品分析
competitors = assistant.analyze_competitors(
    product_type='OCR工具',
    features=['日文识别', '古籍处理']
)
```

## 📚 核心功能

### 1. 多平台搜索
- GitHub项目搜索
- arXiv论文搜索
- Papers With Code搜索

### 2. 深度分析
- 项目README分析
- 论文PDF分析
- 学术文献分析
- 技术趋势分析

### 3. 智能生成
- 综合报告生成
- 改进建议生成
- 摘要生成

### 4. 数据管理
- 文档存储
- 报告存储
- 缓存管理

## 🔧 配置

### API配置

```python
# 环境变量配置
export DASHSCOPE_API_KEY='your-qwen-api-key'
export OPENAI_API_KEY='your-openai-api-key'
export MINIMAX_API_KEY='your-minimax-api-key'
```

### 使用配置

```python
assistant = IntelligentResearchAssistant(
    api_provider='qwen',      # API提供商
    test_mode=False,          # 测试模式
    cache_enabled=True,       # 启用缓存
    cache_ttl_days=7          # 缓存有效期
)
```

## 📝 开发状态

- ✅ 阶段1: 准备阶段 - 目录结构创建完成
- 🔄 阶段2: 核心层开发 - 进行中
- ⏳ 阶段3: 搜索层迁移 - 待开始
- ⏳ 阶段4: 分析层整合 - 待开始
- ⏳ 阶段5: 生成层整合 - 待开始
- ⏳ 阶段6: 集成测试 - 待开始
- ⏳ 阶段7: 文档与部署 - 待开始

## 📄 许可

与主项目保持一致。

---

**版本**: 1.0.0
**创建日期**: 2026-04-01
**状态**: 🔄 开发中
