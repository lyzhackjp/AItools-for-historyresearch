# 历史研究AI辅助工具 - 详尽技术指南

## 文档信息

| 属性 | 内容 |
|------|------|
| 文档名称 | COMPREHENSIVE_TECHNICAL_GUIDE.md |
| 版本 | 2.0.0 |
| 创建日期 | 2026-03-28 |
| 更新日期 | 2026-03-30 |
| 适用对象 | 开发人员、运维人员、高级用户 |
| 文档性质 | 核心技术参考文档 |
| 关联文档 | [WORKFLOW_DIAGRAM.md](WORKFLOW_DIAGRAM.md) |

### 文档定位与使用说明

本文档作为系统实现的技术参考，与工作流程图（WORKFLOW_DIAGRAM.md）互为补充：
- **本文档**：侧重于实现细节，提供API接口、配置参数与代码示例
- **工作流程图**：侧重于流程可视化，以图表形式展示模块间的调用关系与数据处理路径

### 独立模块文档索引

以下模块已具备独立的技术文档，本文档仅概述其核心功能，详细说明请参阅相应文档：

| 模块名称 | 独立文档路径 | 功能概述 |
|----------|-------------|----------|
| LearningModule | [learning_module/README.md](learning_module/README.md) | 学术资源检索、文献分析、改进建议生成 |
| OpenSourceFinder | [open_source_finder/README.md](open_source_finder/README.md) | GitHub/HuggingFace开源项目搜索与评估 |
| NDL搜索模块 | [ndl-search/docs/README.md](ndl-search/docs/README.md) | 日本国立国会图书馆文献检索与下载 |

---

## 第一部分：工作区概述

### 1.1 项目定位与目标

本项目（AItools-for-historyresearch）是一款专为日本史研究设计的Web后端系统，旨在辅助历史学研究人员处理学术文献、提升写作效率。系统采用Python Flask框架开发，集成多种大语言模型（LLM）接口，支持日文、中文、英文等多语言学术文本处理。

### 1.2 核心应用场景

| 场景 | 说明 |
|------|------|
| 学术论文润色 | 自动修正语法错误、提升学术表达规范度 |
| PDF文献OCR识别 | 将扫描版PDF转换为可编辑文本 |
| 历史专有名词识别 | 自动识别人名、地名、事件、机构等实体 |
| 学术笔记生成 | 生成符合Obsidian格式的阅读笔记 |
| 引用规范化处理 | 统一多种引用格式（Chicago、APA、GB/T 7714等） |
| 数据结构化导出 | 支持JSON/CSV格式导出 |

### 1.3 目标用户群体

| 用户类型 | 使用场景 |
|----------|----------|
| 日本史研究人员 | 处理日文史料、生成学术论文 |
| 历史学专业学生 | 撰写课程论文、毕业论文 |
| 档案管理人员 | 数字化历史文档、建立索引 |
| 学术编辑 | 润色审阅学术稿件 |

---

## 第二部分：环境配置

### 2.1 系统要求

#### 2.1.1 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|----------|----------|
| CPU | 双核处理器 | 四核及以上 |
| 内存 | 4GB RAM | 8GB RAM |
| 硬盘 | 50MB可用空间 | 100MB可用空间 |
| 显示器 | 1024×768 | 1920×1080 |

#### 2.1.2 软件要求

| 软件 | 版本要求 | 说明 |
|------|----------|------|
| Python | 3.8+ | 推荐3.11 |
| Tesseract OCR | 5.0+ | 用于本地OCR识别 |
| 操作系统 | Windows 10+/Linux/macOS | 本工作区主要在Windows环境开发 |

### 2.2 依赖安装

#### 2.2.1 创建虚拟环境（推荐）

```bash
# 进入项目目录
cd AItools-for-historyresearch

# 创建虚拟环境
python -m venv venv

# Windows激活虚拟环境
venv\Scripts\activate

# Linux/macOS激活虚拟环境
source venv/bin/activate
```

#### 2.2.2 安装Python依赖

```bash
# 安装核心依赖
pip install -r requirements.txt
```

#### 2.2.3 安装Tesseract OCR（Windows）

1. 访问 [Tesseract OCR下载页面](https://github.com/UB-Mannheim/tesseract/wiki)
2. 下载并运行安装程序
3. 安装时勾选以下语言包：
   - Chinese Simplified（简体中文）
   - Japanese（日语）
   - English（英语）
   - Korean（韩语）
4. 记录安装路径，默认路径为：`C:\Program Files\Tesseract-OCR\tesseract.exe`

### 2.3 环境变量配置

#### 2.3.1 配置文件位置

环境变量配置文件位于：`config/api_config.json`（生产环境）和 `config/api_config.test.json`（测试环境）。

#### 2.3.2 API密钥配置

创建或编辑 `.env` 文件，配置您的API密钥：

```env
# ==================== API密钥配置 ====================

# OpenAI配置（GPT系列）
OPENAI_API_KEY=sk-your-openai-api-key-here

# 阿里云通义千问配置
DASHSCOPE_API_KEY=sk-your-dashscope-api-key-here

# 智谱AI配置（GLM）
ZHIPU_API_KEY=your-zhipu-api-key-here

# MiniMax配置
MINIMAX_API_KEY=your-minimax-api-key-here

# 火山引擎配置
VOLCANO_API_KEY=your-volcano-api-key-here

# DeepSeek配置
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here

# ==================== 本地模型配置 ====================

# Ollama本地部署配置
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2

# ==================== 系统路径配置 ====================

# Tesseract OCR路径（Windows示例）
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe

# ==================== 默认参数配置 ====================

# 默认LLM服务商
LLM_PROVIDER=openai

# 默认模型
LLM_MODEL=gpt-4

# 默认OCR语言
OCR_LANGUAGE=zh

# PDF处理DPI设置
PDF_DPI=300

# PDF输出格式
PDF_FORMAT=PNG

# API环境设置（production/test）
API_ENV=production
```

### 2.4 验证环境配置

运行以下命令验证环境配置是否正确：

```python
from config.config_helpers import print_config_status, validate_environment

# 打印配置状态
print_config_status()

# 验证环境配置
results = validate_environment()
print(results)
```

---

## 第三部分：文件结构与功能

### 3.1 顶层目录结构

```
AItools-for-historyresearch/
├── app/                          # Flask应用主目录
│   ├── app.py                    # Flask应用入口
│   └── config.py                 # 应用配置
├── modules/                      # 核心功能模块
│   ├── llm_client.py            # LLM客户端（多服务商支持）
│   ├── doc_processor.py         # Word文档处理
│   ├── pdf_processor.py         # PDF处理
│   ├── ocr_processor.py         # OCR识别（Tesseract）
│   ├── unified_ocr_processor.py # 统一OCR处理器（NDL系列）
│   ├── ndl_ocr_batch_processor.py   # NDL OCR批量处理
│   ├── ndl_ocr_monitor.py       # NDL OCR心跳监控
│   ├── llm_ocr_processor.py     # LLM OCR处理器（通义千问VL）
│   ├── ner_processor.py         # 命名实体识别
│   ├── ner_disambiguation.py    # 实体消歧（同形异义词）
│   ├── academic_note_generator.py   # 学术笔记生成
│   ├── academic_summarizer.py   # 学术摘要生成
│   ├── paper_polisher.py        # 论文润色
│   ├── paper_polisher_enhanced.py   # 论文润色增强版
│   ├── reverse_outline_analyzer.py  # 逆向大纲分析
│   ├── citation_normalizer.py   # 引用规范化
│   ├── citation_network_analyzer.py # 引文网络分析
│   ├── style_transfer.py        # 文风分析与迁移
│   ├── virtual_persona_chatbot.py   # 虚拟人格对话
│   ├── embedding_manager.py     # 嵌入模型管理
│   ├── obsidian_integration.py  # Obsidian集成
│   ├── data_structurer.py       # 数据结构化
│   ├── environment_checker.py   # 环境检查
│   ├── setup_assistant.py       # 环境配置助手
│   └── prompts/                 # 提示词目录
├── learning_module/              # 学习模块
│   ├── src/
│   │   ├── research_analyzer.py    # 学术资源检索
│   │   ├── literature_analyzer.py  # 文献分析
│   │   ├── improvement_generator.py # 改进建议生成
│   │   └── prompts.py             # 提示词管理
│   └── README.md
├── open_source_finder/           # 开源模块搜索器
│   ├── src/
│   │   └── open_source_finder.py  # GitHub/HF搜索
│   └── README.md
├── config/                       # 配置目录
│   ├── api_config.json          # 生产环境API配置
│   ├── api_config.test.json     # 测试环境API配置
│   ├── api_config_loader.py     # 配置加载器
│   ├── api_key_manager.py       # API密钥管理
│   └── config_helpers.py        # 配置辅助工具
├── data/                         # 数据目录
│   ├── dictionaries/            # 词典数据
│   │   ├── historical_entities.json  # 历史实体词典
│   │   └── historical_entities_manager.py
│   ├── input/                   # 输入数据
│   ├── output/                  # 输出数据
│   └── logs/                    # 执行日志
├── external/                     # 外部集成
│   └── ndlkotenocr-lite/        # NDL古典籍OCR工具
├── ndl-search/                   # NDL搜索模块
│   ├── config/                  # 配置目录
│   │   ├── __init__.py
│   │   └── settings.py          # NDL配置管理
│   ├── core/                    # 核心模块
│   │   ├── __init__.py
│   │   └── dl_searcher.py       # NDL搜索器核心
│   ├── utils/                   # 工具模块
│   │   ├── __init__.py
│   │   └── helpers.py           # 辅助工具
│   ├── tests/                   # 测试模块
│   │   ├── __init__.py
│   │   └── test_searcher.py     # 单元测试
│   ├── docs/                    # 文档
│   │   └── README.md
│   ├── downloads/               # 下载目录
│   ├── __init__.py
│   └── execute_ndl_search.py    # 执行脚本
├── docs/                         # 文档目录
├── archive/                      # 归档目录（废弃文件）
└── README.md                    # 项目说明
```

### 3.2 核心模块详解

#### 3.2.1 LLM客户端模块（llm_client.py）

**功能描述**：统一接口调用多种大语言模型服务商

**支持的服务商**：

| 服务商 | 模型 | API格式 |
|--------|------|---------|
| OpenAI | GPT-3.5/GPT-4 | OpenAI API |
| 阿里云通义千问 | qwen-turbo | REST API |
| 智谱AI | GLM-4 | REST API |
| MiniMax | abab6-chat | REST API |
| 火山引擎 | volcengine-m2 | REST API |
| DeepSeek | deepseek-chat | REST API |
| Ollama | llama2等 | OpenAI兼容API |

**核心方法**：

```python
from modules.llm_client import LLMClient

# 初始化客户端
client = LLMClient({
    'provider': 'dashscope',
    'api_key': 'your-api-key',
    'model': 'qwen-turbo'
})

# 学术润色
result = client.academic_polish("待润色的文本", language='zh')

# 冗余内容删除
result = client.remove_redundancy("待处理的文本")

# OCR结果校正
result = client.ocr_correction("OCR识别结果", language='ja')
```

#### 3.2.2 文档处理模块（doc_processor.py）

**功能描述**：Word文档的解析与生成，支持.docx格式

**核心能力**：

| 能力 | 说明 |
|------|------|
| 文档解析 | 提取标题、段落、表格、样式、页眉页脚 |
| 格式保留 | 保持原文档的格式和样式 |
| 文档生成 | 创建新的Word文档 |
| 元数据提取 | 提取作者、创建时间等信息 |

**使用示例**：

```python
from modules.doc_processor import DocProcessor

processor = DocProcessor()

# 解析文档
doc_data = processor.extract_text("input.docx")
print(doc_data['title'])
print(doc_data['paragraphs'])
print(doc_data['tables'])

# 创建新文档
processor.create_document({
    'title': '新文档标题',
    'paragraphs': [{'text': '内容', 'style': 'Normal'}],
    'tables': []
}, 'output.docx')
```

#### 3.2.3 PDF处理模块（pdf_processor.py）

**功能描述**：PDF文件转换为图片，并进行版面分析

**核心能力**：

| 能力 | 说明 |
|------|------|
| PDF转图片 | 将PDF页面转换为PNG/JPEG图片 |
| 版面分析 | 识别文本区域、图像区域、表格区域 |
| 区域提取 | 按区域提取文本内容 |
| DPI控制 | 可调节输出图片分辨率 |

#### 3.2.4 OCR处理模块（ocr_processor.py）

**功能描述**：多种OCR引擎的文字识别

**支持的OCR引擎**：

| 引擎 | 语言支持 | 说明 |
|------|----------|------|
| Tesseract | 中/日/英/韩 | 本地运行，需安装语言包 |
| NDL Lab OCR | 日文 | 日本国立国会图书馆模型 |
| LLM辅助OCR | 多语言 | 使用大模型辅助识别校正 |
| 通义千问VL OCR | 多语言 | 阿里云视觉语言模型，高精度文档识别 |

**支持的语言代码**：

| 代码 | 语言 |
|------|------|
| zh | 简体中文 |
| ja | 日语 |
| en | 英语 |
| ko | 韩语 |
| zh-tw | 繁体中文 |

**使用示例**：

```python
from modules.ocr_processor import OCRProcessor

# 初始化（指定Tesseract路径）
processor = OCRProcessor(tesseract_path='C:\\Program Files\\Tesseract-OCR\\tesseract.exe')

# 从图片识别文字
result = processor.extract_text_from_image('page1.png', language='ja')
print(result['text'])

# 从字节流识别
result = processor.extract_text_from_bytes(image_bytes, language='zh')
```

#### 3.2.4.1 LLM OCR处理器模块（llm_ocr_processor.py）

**功能描述**：使用通义千问VL OCR模型进行PDF OCR识别，支持数据清洗和优化处理

**核心功能**：

| 功能 | 说明 |
|------|------|
| PDF转图片 | 将PDF页面转换为PNG图片 |
| LLM OCR识别 | 调用通义千问VL OCR API进行文字识别 |
| 水印去除 | 彻底清除PDF水印文本（支持多种变体格式） |
| 页码识别 | 识别并还原PDF中的原书页码（支持汉字数字） |
| 页眉页脚处理 | 检测并记录页眉页脚变更 |
| HTML标签清理 | 移除OCR输出中的HTML标签和代码块 |

**支持的OCR模型**：

| 模型名称 | 说明 |
|----------|------|
| qwen-vl-ocr-latest | 最新版本，始终与最新快照版能力相同 |
| qwen-vl-ocr-2025-11-20 | 基于Qwen3-VL架构，大幅提升文档解析能力 |
| qwen-vl-ocr-2025-08-28 | 又称qwen-vl-ocr-0828 |
| qwen-vl-ocr-2025-04-13 | 又称qwen-vl-ocr-0413 |

**API配置**：

```python
API密钥配置方式：
1. 环境变量：DASHSCOPE_API_KEY
2. 配置文件：config/api_config.json 中的 dashscope.api_key
3. 初始化参数：直接传入 api_key 参数

API端点：https://dashscope.aliyuncs.com/compatible-mode/v1
```

**使用示例**：

```python
from modules.llm_ocr_processor import QwenVLOCRProcessor

processor = QwenVLOCRProcessor(
    api_key='your-dashscope-api-key',
    model='qwen-vl-ocr-latest'
)

results = processor.process_pdf(
    pdf_path='input.pdf',
    start_page=1,
    end_page=20,
    language='ja',
    output_dir='./output'
)

print(f"处理页数: {len(results)}")
print(f"总字符数: {sum(r.text_length for r in results)}")
```

**数据清洗流程**：

```python
处理流程：
1. clean_html_tags()    - 清理HTML标签和代码块标记
2. remove_all_watermarks() - 彻底清除水印变体
3. clean_text()         - 文本规范化处理
4. fix_ocr_errors()     - 修复常见OCR错误
5. extract_page_number() - 识别原书页码
6. detect_header_footer() - 检测页眉页脚变更
```

**输出格式**：

| 格式 | 文件 | 说明 |
|------|------|------|
| JSON | .json | 结构化元数据，包含页眉页脚变更记录 |
| TXT | .txt | 格式化文本输出，标注页眉变更和原书页码 |
| CSV | .csv | 表格格式输出，便于数据分析 |

**水印去除模式**：

```python
WATERMARK_PATTERNS = [
    r'E\d{8,}\s*LI\s*YUAN\s*Z?\s*H?\s*E?\s*N?\s*\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}',
    r'E\d{8,}\s*LIYUAN\s*[A-Z]*\s*\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}',
    r'E\d{8,}\s*LI\s*YUAN\s*[A-Z\s]*\d{4}/\d{2}/\d{2}',
    r'E\d+\s+LI\s*YUAN.*\d{4}/\d{2}/\d{2}.*',
    r'E\d{8,}.*LI.*YUAN.*\d{4}.*',
]
```

**图片压缩机制**：

```python
当图片超过API限制（10MB）时自动压缩：
1. 质量压缩：从quality=85逐步降低到quality=20
2. 尺寸压缩：从max_dimension=2000逐步降低到800
3. 最终保障：强制压缩到800x800，quality=50
```

#### 3.2.5 学术笔记生成模块（academic_note_generator.py）

**功能描述**：从学术文献自动生成符合Obsidian格式的结构化阅读笔记

**核心功能**：

| 功能 | 说明 |
|------|------|
| 双向链接 | 生成带 [[双向链接]] 的笔记 |
| 实体提取 | 提取人名、地名、事件、概念、文献五类实体 |
| 知识图谱 | 构建知识图谱节点数据 |
| 笔记模板 | 预设Obsidian格式模板 |

**输出格式**：

```markdown
---
type: reading_note
tags:
  - #文献笔记
  - #日本史
created: 2026-03-28
source: 伊藤博文伝
---

# 标题

## 📋 总体摘要

[[人物]]在[[地点]]发生了[[事件]]...

## 🔗 核心图谱节点提取

- [[人物A]]
- [[人物B]]
- [[地点]]
- [[事件]]
```

#### 3.2.6 命名实体识别模块（ner_processor.py）

**功能描述**：从日文史料中识别和分类历史专有名词

**实体类型**：

| 类型 | 说明 | 示例 |
|------|------|------|
| person | 历史人物 | 伊藤博文、西乡隆盛 |
| location | 地理位置 | 东京、京都、萨摩 |
| organization | 机构组织 | 幕府、内务省、贵族院 |
| event | 历史事件 | 明治维新、大政奉还 |
| date | 历史年代 | 1868年、幕末 |
| work | 著作文献 | 《日本国宪法》 |
| concept | 思想概念 | 君主立宪、开国进取 |

**使用示例**：

```python
from modules.ner_processor import NERProcessor

processor = NERProcessor(api_provider='qwen', test_mode=False)

entities = processor.recognize_historical_entities(
    "伊藤博文出生于1841年，在明治维新时期发挥了重要作用。",
    categories=['person', 'event', 'date']
)

for entity in entities:
    print(f"{entity['text']} -> {entity['category']}")
```

#### 3.2.7 论文润色模块（paper_polisher.py）

**功能描述**：智能精简学术论文内容，删除冗余论述，采用Word原生修订追踪模式

**核心功能**：

| 功能 | 说明 |
|------|------|
| 智能精简 | 删除逻辑冗余的论述，精简20%-40% |
| Word原生修订追踪 | 使用w:del和w:ins元素实现专业修订模式 |
| 脚注引用保护 | 自动提取并恢复脚注引用元素 |
| 术语保护 | 保护历史专有名词和学术术语 |

**修订模式技术实现**：

| 元素 | 说明 |
|------|------|
| w:del | 删除标记，包含原文内容和删除元数据 |
| w:ins | 插入标记，包含润色后内容和插入元数据 |
| w:footnoteReference | 脚注引用元素，在修订后自动恢复 |
| w:trackRevisions | 文档修订追踪设置 |

**使用示例**：

```python
from modules.paper_polisher import create_paper_polisher

# 创建润色器（优先使用通义千问）
polisher = create_paper_polisher('qwen')

# 处理文档（启用修订追踪模式）
result = polisher.process_document(
    'input.docx',
    'output.docx',
    enable_track_changes=True
)

# 查看处理结果
print(f"总段落: {result['total_paragraphs']}")
print(f"修改内容: {result['total_deletions']}")
```

**脚注引用保护机制**：

处理流程会自动：
1. 提取段落中的所有脚注引用元素（w:footnoteReference）
2. 清空段落并添加修订标记
3. 将脚注引用元素恢复到修订后的段落中

**输出文档特性**：
- 可在Word中通过"审阅"→"修订"查看所有修改
- 双击脚注引用可跳转到对应脚注内容
- 支持接受/拒绝单个修订

#### 3.2.8 逆向大纲分析模块（reverse_outline_analyzer.py）

**功能描述**：分析论文草稿的逻辑链、各部分比重

**分析维度**：

| 维度 | 说明 |
|------|------|
| 篇幅分析 | 各部分字数统计、比例失衡检测 |
| 逻辑链分析 | 论点提取、逻辑关系识别、断层检测 |
| 注意力分析 | 核心论点识别、偏离检测 |
| 修订建议 | 综合分析生成改进建议 |

#### 3.2.9 引用规范化模块（citation_normalizer.py）

**功能描述**：学术引用的规范化处理和批量管理，根据WORKFLOW_DIAGRAM.md中的6.1引用格式转换流程优化实现

**支持的引用格式**：

| 格式 | 说明 | 适用场景 |
|------|------|----------|
| Chicago | 芝加哥格式 | 人文社科 |
| APA | 美国心理学会格式 | 心理学、教育学 |
| MLA | 现代语言协会格式 | 文学、语言学 |
| GB/T 7714 | 中国国家标准 | 中国学术期刊 |
| IEEE | 工程技术格式 | 工程、计算机 |
| Harvard | 哈佛格式 | 广泛使用 |

**工作流程（对应WORKFLOW_DIAGRAM.md 6.1）**：

1. **输入引用列表** → parse_citation解析
2. **识别格式类型** → 自动检测Chicago/APA/GB7714/MLA/IEEE/Harvard格式
3. **应用正则模式** → 根据识别的格式应用相应的正则表达式
4. **validate_fields验证** → 字段完整性检查、格式验证、关联性验证
5. **规范化字段** → 标准化作者名、标题、年份等字段格式
6. **convert_format转换** → 转换为目标格式输出

**核心优化特性**：

1. **智能格式检测器**：自动识别引用格式类型，基于多模式匹配评分算法
2. **格式特定解析**：为每种格式（Chicago、APA、MLA、GB7714、IEEE、Harvard）设计专用正则表达式
3. **增强验证逻辑**：
   - 必填字段验证（author、title、year）
   - 字段格式验证（DOI、页码、年份范围）
   - 字段关联性验证（文章类型与期刊名、图书与出版社的对应关系）
   - 引用完整度评分（0.0-1.0）
4. **LLM辅助识别**：整合大语言模型辅助复杂引用解析，支持外部资料搜集
5. **批量处理能力**：支持批量规范化、去重、元数据提取

**API接口**：

```python
from modules.citation_normalizer import CitationNormalizer

# 初始化规范化器
normalizer = CitationNormalizer(style='gb7714', use_llm=True)

# 规范化引用列表
citations = [
    "[序号] Smith J. [J]. Journal of Testing, 2020, 10(1): 1-10",
    "[序号] Johnson A. [M]. Computer Science Basics. MIT Press, 2019"
]
normalized = normalizer.normalize(citations)

# 转换为其他格式
for citation in normalized:
    if citation.get('parsed'):
        apa_format = normalizer.convert_format(citation, 'apa')
        chicago_format = normalizer.convert_format(citation, 'chicago')
        print(f"APA: {apa_format}")
        print(f"Chicago: {chicago_format}")

# 验证引用完整性
validation_report = normalizer.validate(normalized)
print(f"完整引用数: {validation_report['valid']}")
print(f"缺失引用数: {validation_report['invalid']}")

# 规范化字段
normalized_citations = normalizer.normalize_fields(citation)

# 去重处理
unique_citations = normalizer.deduplicate(normalized)
```

**新增方法**：

| 方法 | 说明 |
|------|------|
| `detect_format()` | 自动识别引用格式类型 |
| `normalize_fields()` | 规范化引用字段 |
| `normalize_batch()` | 批量规范化字段 |
| `_parse_with_format()` | 格式特定解析 |
| `_parse_generic()` | 通用解析 |
| `_parse_with_llm()` | LLM辅助识别 |
| `_validate_doi_format()` | DOI格式验证 |
| `_validate_pages_format()` | 页码格式验证 |
| `_validate_field_consistency()` | 字段关联性验证 |
| `_calculate_completeness_score()` | 完整度评分 |

#### 3.2.10 学术摘要生成模块（academic_summarizer.py）

**功能描述**：智能生成学术文献摘要

**摘要类型**：

| 类型 | 说明 |
|------|------|
| 抽取式摘要 | 从原文抽取关键句子 |
| 生成式摘要 | 使用LLM生成新摘要 |
| 研究问题提取 | 识别核心研究问题 |
| 概念方法提取 | 批量抽取核心概念和方法论 |
| 相关度评估 | 评估文献与研究主题的相关性 |

#### 3.2.11 统一OCR处理器（unified_ocr_processor.py）

**功能描述**：统一接口调用NDL OCR系列模型，支持近代现代文献和古典籍文献识别

**支持的OCR模型**：

| 模型 | 用途 | 说明 |
|------|------|------|
| ndlocr_lite | 近代现代文献 | 识别近代现代日本印刷体文献 |
| ndlkotenocr_lite | 古典籍文献 | 识别江戸期以前的和古書、清代以前的漢籍 |

**使用示例**：

```python
from modules.unified_ocr_processor import UnifiedOCRProcessor

processor = UnifiedOCRProcessor()

# 使用NDL OCR（近代现代文献）
result = processor.process_image('page.png', model_type='ndlocr_lite')

# 使用NDL古典籍OCR（古典草书字文献）
result = processor.process_image('koten.png', model_type='ndlkotenocr_lite')

# 获取识别文本
text = result.merge_all_text()
```

#### 3.2.12 NDL OCR批量处理器（ndl_ocr_batch_processor.py）

**功能描述**：批量调用NDL OCR模型进行图片识别

**核心功能**：

| 功能 | 说明 |
|------|------|
| 批量处理 | 支持批量图片OCR识别 |
| 进度追踪 | 实时追踪处理进度 |
| 错误处理 | 自动重试和错误记录 |
| 结果汇总 | 汇总所有识别结果 |

#### 3.2.13 NDL OCR心跳监控（ndl_ocr_monitor.py）

**功能描述**：监控NDL OCR服务的可用性和运行状态

**核心功能**：

| 功能 | 说明 |
|------|------|
| 心跳检测 | 定期检测服务可用性 |
| 自动重试 | 失败后自动重试 |
| 告警提示 | 服务异常时发出告警 |
| 状态统计 | 统计服务运行状态 |

#### 3.2.14 LLM OCR处理器（llm_ocr_processor.py）

**功能描述**：使用通义千问VL OCR模型进行PDF OCR识别，支持数据清洗和优化处理

**核心功能**：

| 功能 | 说明 |
|------|------|
| PDF转图片 | 将PDF页面转换为PNG图片 |
| LLM OCR识别 | 调用通义千问VL OCR API进行文字识别 |
| 水印去除 | 彻底清除PDF水印文本（支持多种变体格式） |
| 页码识别 | 识别并还原PDF中的原书页码（支持汉字数字） |
| 页眉页脚处理 | 检测并记录页眉页脚变更 |

**支持的OCR模型**：

| 模型名称 | 说明 |
|----------|------|
| qwen-vl-ocr-latest | 最新版本，始终与最新快照版能力相同 |
| qwen-vl-ocr-2025-11-20 | 基于Qwen3-VL架构，大幅提升文档解析能力 |
| qwen-vl-ocr-2025-08-28 | 又称qwen-vl-ocr-0828 |
| qwen-vl-ocr-2025-04-13 | 又称qwen-vl-ocr-0413 |

**API调用方式**：

```python
from llm_ocr_processor import QwenVLOCRProcessor

processor = QwenVLOCRProcessor(
    pdf_path='path/to/pdf',
    output_dir='path/to/output',
    api_key='your-dashscope-api-key'
)

result = processor.run(start_page=41, end_page=60)
```

**API请求格式**：

```python
url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

data = {
    'model': 'qwen-vl-ocr-latest',
    'input': {
        'messages': [
            {
                'role': 'user',
                'content': [
                    {'image': 'data:image/png;base64,<base64_image>'},
                    {'text': '识别提示词'}
                ]
            }
        ]
    }
}
```

**语言提示词**：

| 语言 | 提示词 |
|------|--------|
| 日语 | この画像は日本語の歴史文書です。画像内のすべてのテキストを正確に認識し、元のレイアウトと構造を維持して出力してください。 |
| 中文 | 这是一张中文历史文献图片。请准确识别图片中的所有文字，保持原有的版面结构和格式输出。 |
| 英文 | This is a historical document image. Please accurately recognize all text in the image, maintaining the original layout and structure. |

**处理流程**：

1. **PDF转图片**：使用PyMuPDF将PDF页面转换为PNG图片（默认DPI=300）
2. **图片编码**：将图片转换为Base64编码
3. **API调用**：调用通义千问VL OCR API进行识别
4. **异步轮询**：如果返回异步任务ID，轮询获取结果
5. **数据清洗**：应用水印去除、页码识别、页眉页脚处理
6. **结果输出**：输出JSON/TXT/CSV三种格式

**输出数据结构**：

```json
{
  "metadata": {
    "processing_date": "2026-03-30T19:00:00",
    "ocr_method": "qwen-vl-ocr-latest",
    "total_pages": 20,
    "total_characters": 16739
  },
  "header_footer_changes": [...],
  "pages": [...]
}
```

#### 3.2.15 OCR结果优化处理器（ocr_optimized_processor.py）

**功能描述**：OCR结果后处理优化，包括水印去除、页码识别、页眉页脚处理

**核心功能**：

| 功能 | 说明 |
|------|------|
| 水印去除 | 彻底清除PDF水印文本（支持多种变体格式） |
| 页码识别 | 识别并还原PDF中的原书页码（支持汉字数字） |
| 页眉检测 | 检测章节标题等页眉信息 |
| 页脚检测 | 检测页码等页脚信息 |
| 变更记录 | 仅在页眉页脚首次变化时记录 |

**水印去除支持的格式**：

| 格式类型 | 示例 |
|----------|------|
| 标准格式 | E13658663 LI YUANZHEN 2025/07/06 16:41:41 |
| 变体格式 | E13658663 LIYUAN IEN 2025/07/06 16:41:42 |
| 空格变体 | E13658663 LI YUAN Z HEN 2025/07/06 16:41:41 |

**水印去除正则模式**：

```python
WATERMARK_PATTERNS = [
    r'E\d{8,}\s*LI\s*YUAN\s*Z?\s*H?\s*E?\s*N?\s*\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}',
    r'E\d{8,}\s*LIYUAN\s*[A-Z]*\s*\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}',
    r'E\d{8,}\s*LI\s*YUAN\s*[A-Z\s]*\d{4}/\d{2}/\d{2}',
    r'E\d+\s+LI\s*YUAN.*\d{4}/\d{2}/\d{2}.*',
    r'E\d{8,}.*LI.*YUAN.*\d{4}.*',
]
```

**页码识别支持的格式**：

| 格式类型 | 示例 |
|----------|------|
| 阿拉伯数字 | 123 |
| 汉字数字 | 一二三 |
| 带横线 | -123- |
| 汉字十位 | 二十三、五十六 |

**汉字数字转换规则**：

```python
KANJI_NUM_MAP = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    '二十': 20, '三十': 30, '四十': 40, '五十': 50,
    '六十': 60, '七十': 70, '八十': 80, '九十': 90, '百': 100
}
```

**页眉检测模式**：

```python
HEADER_PATTERNS = [
    r'^第[一二三四五六七八九十百千]+編.+',
    r'^第[一二三四五六七八九十百千]+章.+',
    r'^第[一二三四五六七八九十百千]+節.+',
    r'^[一二三四五六七八九十]+、.+',
]
```

**使用示例**：

```python
from ocr_optimized_processor import OCROptimizedProcessor

processor = OCROptimizedProcessor(ocr_output_dir, final_output_dir)
result = processor.run()

# 输出包含:
# - 彻底清除水印的文本
# - 识别到的原书页码
# - 页眉页脚变更记录
# - JSON/TXT/CSV三种格式输出
```

**输出数据结构**：

```json
{
  "metadata": {
    "processing_date": "2026-03-30T18:45:15",
    "total_pages": 20,
    "total_characters": 16739
  },
  "header_footer_changes": [
    {
      "pdf_page": 41,
      "ocr_page": null,
      "header": "第十五編西南戰爭時代 第二章內政の整理",
      "footer": "第十五編西南戰爭時代第二章内政の整理"
    }
  ],
  "pages": [
    {
      "pdf_page_number": 41,
      "ocr_page_number": null,
      "ocr_page_number_text": "",
      "header": "...",
      "footer": "...",
      "text": "正文内容...",
      "text_length": 824
    }
  ]
}
```

**处理流程说明**：

1. **水印去除阶段**：
   - 遍历所有水印正则模式
   - 逐个替换匹配的水印文本
   - 清理残留的水印片段（E数字、LIYUAN等）
   - 清理多余的空行

2. **页码识别阶段**：
   - 从页面末尾开始扫描
   - 匹配阿拉伯数字或汉字数字格式
   - 转换汉字数字为阿拉伯数字
   - 从正文中移除页码文本

3. **页眉页脚检测阶段**：
   - 检测前3行是否匹配页眉模式
   - 检测后4行是否匹配页脚模式
   - 与上一页比较判断是否为首次出现
   - 仅在首次出现时记录变更

**数据类定义**：

```python
@dataclass
class PageHeaderFooter:
    """页眉页脚信息"""
    header: str = ""
    footer: str = ""
    page_number: Optional[int] = None
    page_number_text: str = ""

@dataclass
class ProcessedPage:
    """处理后的页面数据"""
    pdf_page_number: int
    ocr_page_number: Optional[int] = None
    ocr_page_number_text: str = ""
    header: str = ""
    footer: str = ""
    header_is_new: bool = False
    footer_is_new: bool = False
    text: str = ""
    text_length: int = 0
    raw_text: str = ""
```

#### 3.2.16 实体消歧模块（ner_disambiguation.py）

**功能描述**：日文历史实体中同形异义词的消歧功能

**支持的消歧实体**：

| 实体 | 可能含义 | 消歧依据 |
|------|----------|----------|
| 江戸 | 城市/幕府 | 上下文关键词匹配 |
| 薩摩 | 地名/藩名 | 上下文关键词匹配 |
| 長州 | 地名/藩名 | 上下文关键词匹配 |
| 会津 | 地名/藩名 | 上下文关键词匹配 |

**使用示例**：

```python
from modules.ner_disambiguation import EntityDisambiguator

disambiguator = EntityDisambiguator()
context = "江戸幕府が終焉を迎えた"
result = disambiguator.disambiguate("江戸", context)
# 返回: {'type': 'organization', 'meaning': '德川幕府'}
```

#### 3.2.17 文风分析与迁移模块（style_transfer.py）

**功能描述**：四维度文风矩阵分析和文本风格迁移

**文风分析维度**：

| 维度 | 说明 |
|------|------|
| 句法结构 | 句子长度、复杂度、从句使用 |
| 词汇深度与选择 | 学术词汇比例、术语使用 |
| 语气与叙事声音 | 客观性、立场表达方式 |
| 学术修辞机制 | 论证方式、引用风格 |

**使用示例**：

```python
from modules.style_transfer import StyleTransfer

transfer = StyleTransfer(api_provider='qwen')

# 分析文风矩阵
matrix = transfer.analyze_style_matrix("待分析的学术文本...")

# 文风迁移
result = transfer.transfer_style_with_matrix(
    text="待迁移文本",
    target_matrix=target_style_matrix
)

# 少样本文风模仿
result = transfer.few_shot_style_transfer(
    text="待迁移文本",
    examples=[("原文1", "目标文1"), ("原文2", "目标文2")]
)
```

#### 3.2.16 虚拟人格对话系统（virtual_persona_chatbot.py）

**功能描述**：预设历史人物人格的学术对话系统

**预设人格**：

| 人格 | 身份 | 特点 |
|------|------|------|
| 福泽谕吉 | 明治启蒙思想家 | 启蒙思想、文明开化、实学主义 |
| 丸山真男 | 战后政治思想史学家 | 政治思想史、日本近代化分析 |
| 涩泽荣一 | 近代实业家 | 实业思想、道德经济合一论 |

**使用示例**：

```python
from modules.virtual_persona_chatbot import VirtualPersonaChatbot

chatbot = VirtualPersonaChatbot(persona='fukuzawa')

# 学术咨询
response = chatbot.consult("关于明治维新的历史意义...")

# 历史事件评论
comment = chatbot.comment_on_history("大政奉还", "1867年")

# 开始角色扮演对话
chatbot.start_conversation()
```

#### 3.2.17 引文网络分析模块（citation_network_analyzer.py）

**功能描述**：分析和可视化学术文献的引文网络

**核心功能**：

| 功能 | 说明 |
|------|------|
| 引用提取 | 从文献中提取引用关系 |
| 网络构建 | 构建引文网络图谱 |
| 流派识别 | 识别学术流派及其分支 |
| 演进分析 | 分析理论演进脉络 |
| 边缘发现 | 发现边缘但有启发性的研究 |

**使用示例**：

```python
from modules.citation_network_analyzer import CitationNetworkAnalyzer

analyzer = CitationNetworkAnalyzer()

# 构建引文网络
graph = analyzer.build_citation_graph(documents)

# 识别学术流派
schools = analyzer.identify_academic_schools()

# 分析理论演进
evolution = analyzer.trace_theory_evolution()
```

#### 3.2.18 嵌入模型管理模块（embedding_manager.py）

**功能描述**：管理和配置多种嵌入模型，支持向量数据库构建和语义检索

**支持的嵌入模型**：

| 模型 | 提供商 | 特点 |
|------|--------|------|
| BGE-M3 | 智源研究院 | 稠密/稀疏/多向量检索 |
| Qwen3-Embedding | 阿里云 | 长文本处理、跨语言检索 |
| Voyage-3-large | Voyage AI | MRL、量化感知训练 |
| text-embedding-3-large | OpenAI | 维度截断、高性能 |
| Ollama本地模型 | 本地部署 | 隐私保护、离线使用 |

**使用示例**：

```python
from modules.embedding_manager import EmbeddingManager

manager = EmbeddingManager(default_model='bge-m3')

# 构建向量索引
manager.build_index(documents)

# 语义检索
results = manager.search(query_text, top_k=10)
```

#### 3.2.19 Obsidian集成模块（obsidian_integration.py）

**功能描述**：与Obsidian笔记系统深度集成

**核心功能**：

| 功能 | 说明 |
|------|------|
| Vault管理 | 创建和管理Obsidian vault |
| 双向链接 | 生成 [[双向链接]] 语法 |
| 模板应用 | 应用自定义Eta模板 |
| Zotero同步 | 同步Zotero批注到Obsidian |
| 知识图谱 | 构建知识图谱数据 |

#### 3.2.20 论文润色增强模块（paper_polisher_enhanced.py）

**功能描述**：论文润色的增强版本，支持多种润色策略

**润色策略**：

| 策略 | 说明 |
|------|------|
| 段落润色 | 整段润色（默认） |
| 逐句润色 | 逐句精简处理 |
| 修订模式 | 启用修订追踪，显示删减 |

**增强功能**：

- 脚注引用重建机制
- 完善脚注处理
- 修订追踪功能
- 学术严谨性保障

#### 3.2.21 环境配置助手（setup_assistant.py）

**功能描述**：自动化环境配置工具

**核心功能**：

| 功能 | 说明 |
|------|------|
| GitHub插件下载 | 自动下载.xpi格式插件 |
| Ollama检查 | 检查Ollama安装状态 |
| API配置 | 配置本地模型环境 |
| 网络检查 | 验证API连接 |

#### 3.2.22 历史实体词典管理器（historical_entities_manager.py）

**功能描述**：历史实体词典的版本管理和维护

**核心功能**：

| 功能 | 说明 |
|------|------|
| 版本管理 | 追踪词典的变更历史 |
| 自动备份 | 保存词典的历史版本 |
| 增量更新 | 支持增量添加新实体 |
| 版本回滚 | 支持回滚到历史版本 |
| 统计报告 | 提供词典统计信息 |

#### 3.2.23 NDL搜索模块（ndl-search/）

**功能描述**：日本国立国会图书馆（NDL）文献搜索与PDF下载模块

**模块结构**：

| 文件 | 功能 |
|------|------|
| core/dl_searcher.py | 核心搜索器和下载器 |
| config/settings.py | 配置管理（单例模式） |
| utils/helpers.py | 文件/文本/验证工具 |
| tests/test_searcher.py | 单元测试 |
| execute_ndl_search.py | 命令行执行脚本 |

**核心类**：

| 类名 | 功能 |
|------|------|
| NDLSearcher | 主搜索器，整合搜索和下载 |
| NDLAPIClient | SRU/OpenSearch API客户端 |
| SeleniumDownloader | Selenium浏览器下载器 |
| SmartWait | 智能等待机制 |
| ProgressDisplay | 进度显示 |
| NDLLogger | 日志记录器 |

**数据类**：

| 类名 | 用途 |
|------|------|
| SearchResult | 搜索结果封装 |
| DownloadResult | 下载结果封装 |
| ExecutionLog | 执行日志封装 |
| NDLConfig | 配置数据类 |

**支持的API**：

| API | 用途 |
|------|------|
| NDL SRU API | 结构化搜索（推荐） |
| NDL OpenSearch | 开放搜索接口 |

**使用示例**：

```python
from ndl_search.core import NDLSearcher
from ndl_search.config import ConfigManager

# 获取配置
config = ConfigManager.get_config()

# 初始化搜索器
searcher = NDLSearcher(
    output_dir='./downloads',
    headless=True,
    config=config
)

# 搜索并下载
result = searcher.search_and_download(
    keyword='井上哲次郎 倫理新説',
    max_attempts=5,
    use_api=True
)

# 检查结果
if result.status == DownloadStatus.SUCCESS:
    print(f'下载成功: {result.file_path}')
    print(f'文件大小: {result.file_size / 1024 / 1024:.2f}MB')
    print(f'校验和: {result.checksum}')
```

**命令行使用**：

```bash
# 基本搜索
python execute_ndl_search.py "井上哲次郎 倫理新説"

# 指定输出目录和重试次数
python execute_ndl_search.py "夏目漱石" -o ./downloads -a 3

# 禁用API搜索（仅浏览器）
python execute_ndl_search.py "明治時代" --no-api

# 详细输出
python execute_ndl_search.py "关键词" -v
```

**智能等待机制**：

| 方法 | 功能 |
|------|------|
| wait_for_condition | 等待条件满足 |
| wait_for_element | 等待元素出现 |
| wait_for_page_load | 等待页面加载完成 |
| adaptive_wait | 自适应等待（根据网络调整） |
| random_delay | 随机延迟（避免检测） |

**PDF验证功能**：

| 检查项 | 说明 |
|------|------|
| 文件存在性 | 检查文件是否存在 |
| 文件大小 | 检查文件大小是否大于0 |
| 文件头 | 检查是否以%PDF-开头 |
| 文件尾 | 检查是否包含%%EOF |
| MD5校验 | 计算文件MD5校验和 |

**配置项**：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| BASE_URL | https://dl.ndl.go.jp | NDL基础URL |
| API_URL | https://ndlsearch.ndl.go.jp/api/sru | SRU API地址 |
| OPTIMAL_WAIT | 3.0 | 最优等待时间（秒） |
| RETRY_ATTEMPTS | 3 | 重试次数 |
| PAGE_LOAD_TIMEOUT | 30 | 页面加载超时（秒） |
| DOWNLOAD_TIMEOUT | 120 | 下载超时（秒） |

#### 3.2.24 史料发言识别与年代提取模块（historical_speech_extractor.py）

**功能描述**：从OCR处理后的史料文本中识别发言内容、提取年代信息，并集成NER实体识别

**核心功能**：

| 功能 | 说明 |
|------|------|
| 发言识别 | 识别史料中的对话、书信、公文等发言内容 |
| 年代提取 | 从文本中提取年代信息（年号、西历、月日等） |
| NER集成 | 调用NER模块识别历史实体 |
| 出版年代推断 | 根据文本内容推断文献出版年代 |
| 多格式支持 | 支持JSON/CSV/TXT三种OCR结果格式输入 |
| 结构化输出 | 生成JSON/CSV/Markdown三种格式输出 |

**数据来源类型**：

| 类型 | 说明 |
|------|------|
| JSON格式 | LLM OCR处理后的JSON结果（推荐） |
| CSV格式 | CSV格式的OCR结果 |
| TXT格式 | TXT格式的OCR结果 |

**年代来源类型**：

| 类型 | 说明 |
|------|------|
| text_internal | 文本内明确提到的年代（如"明治十年一月四日"） |
| document_date | 文献本身的年代（如书信日期） |
| publication_date | 书籍出版年代 |
| inferred_date | 根据上下文推断的年代 |

**发言识别模式**：

| 模式 | 正则表达式 | 示例 |
|------|------------|------|
| 直接引语 | 「([^」]+)」 | 「明治維新は...」 |
| 引用文献 | 『([^』]+)』 | 『西洋事情』 |
| 括号注释 | （([^）]+)） | （福澤諭吉） |
| 古文陈述 | 候文模式匹配 | ...と申候 |

**年代识别模式**：

| 模式 | 正则表达式 | 示例 |
|------|------------|------|
| 年号完整日期 | (明治\|大正\|...)(\d+)\|元)年(\d+)月(\d+)日 | 明治十年一月四日 |
| 年号年份 | (明治\|大正\|...)(\d+)\|元)年 | 明治十年 |
| 西历日期 | (\d{4})年(\d{1,2})月(\d{1,2})日 | 1877年1月4日 |
| 汉字月日 | ([一二三四五六七八九十]+)月([一二三四五六七八九十]+)日 | 十二月二十六日 |

**支持的年号**：

| 年号 | 西历范围 |
|------|----------|
| 明治 | 1868-1912 |
| 大正 | 1912-1926 |
| 昭和 | 1926-1989 |
| 平成 | 1989-2019 |
| 令和 | 2019-至今 |
| 慶応/慶應 | 1865-1868 |
| 元治 | 1864-1865 |
| 文久 | 1861-1864 |
| 安政 | 1854-1860 |
| 嘉永 | 1848-1854 |

**数据类定义**：

```python
@dataclass
class SpeechSegment:
    """发言片段"""
    text: str
    speaker: str = ""
    speech_type: str = ""
    position: Tuple[int, int] = (0, 0)
    confidence: float = 0.0

@dataclass
class DateInfo:
    """年代信息"""
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    era_name: Optional[str] = None
    era_year: Optional[int] = None
    date_type: str = ""
    original_text: str = ""
    confidence: float = 0.0

@dataclass
class HistoricalSpeechRecord:
    """史料发言记录"""
    page_number: int
    original_page_number: Optional[int] = None
    text: str = ""
    speeches: List[SpeechSegment] = field(default_factory=list)
    dates: List[DateInfo] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    publication_info: Dict[str, Any] = field(default_factory=dict)
```

**使用示例**：

```python
from modules.historical_speech_extractor import create_speech_extractor

# 创建处理器
extractor = create_speech_extractor(
    api_provider="qwen",
    test_mode=False
)

# 加载OCR结果（支持JSON/CSV/TXT）
ocr_data = extractor.load_ocr_result("ocr_result.json")

# 处理数据
records = extractor.process_ocr_result(ocr_data)

# 导出结果
extractor.export_results(records, "output.json", format='json')
extractor.export_results(records, "output.csv", format='csv')
extractor.export_results(records, "output.md", format='markdown')
```

**命令行测试**：

```bash
# 第一次测试：使用已有OCR结果
python tests/test_historical_speech_extractor.py --test 1 --test-mode

# 第二次测试：从PDF从头执行完整流程
python tests/test_historical_speech_extractor.py --test 2 --test-mode
```

**输出数据结构**：

```json
{
  "metadata": {
    "processing_date": "2026-03-30T20:22:06",
    "total_pages": 20,
    "total_speeches": 299,
    "total_dates": 18,
    "total_entities": 95
  },
  "records": [
    {
      "page_number": 41,
      "original_page_number": null,
      "text": "页面文本内容...",
      "speeches": [
        {
          "text": "右御回答旁勿々如此",
          "speaker": "",
          "speech_type": "古文陈述",
          "position": [14, 24],
          "confidence": 0.6
        }
      ],
      "dates": [
        {
          "year": null,
          "month": 12,
          "day": 26,
          "era_name": null,
          "era_year": null,
          "date_type": "text_internal",
          "original_text": "十二月二十六日",
          "confidence": 0.7
        }
      ],
      "entities": [
        {
          "entity": "東京",
          "category": "location",
          "start_pos": 100,
          "end_pos": 102,
          "confidence": 1.0,
          "source": "dictionary"
        }
      ],
      "publication_info": {
        "inferred_year": 1878,
        "era": "明治",
        "confidence": 0.8,
        "evidence": ["年号推断年份: 1878年"]
      }
    }
  ]
}
```

**处理流程说明**：

1. **数据加载阶段**：
   - 根据文件扩展名选择加载方法
   - JSON格式：直接解析页面数据
   - CSV格式：按行解析并按页码分组
   - TXT格式：按分隔符分割页面

2. **出版年代推断阶段**：
   - 遍历所有页面提取日期
   - 取最大年份作为推断的出版年代
   - 检查页眉是否包含年号信息
   - 全文扫描年号年份模式

3. **发言识别阶段**：
   - 遍历所有发言模式进行匹配
   - 提取发言文本和位置信息
   - 从上下文推断发言者
   - 计算置信度分数

4. **年代提取阶段**：
   - 遍历所有日期模式进行匹配
   - 解析年号、年份、月、日
   - 转换年号为西历年份
   - 转换汉字数字为阿拉伯数字

5. **实体识别阶段**：
   - 加载历史实体词典
   - 在文本中查找实体匹配
   - 记录实体类型和位置

**依赖模块**：

| 模块 | 用途 |
|------|------|
| ner_processor.py | NER实体识别 |
| llm_client.py | LLM API调用（可选增强） |
| historical_entities.json | 历史实体词典 |

**输出目录**：

```
data/output/speech_extraction/
├── speech_result_YYYYMMDD_HHMMSS.json
├── speech_result_YYYYMMDD_HHMMSS.csv
└── speech_result_YYYYMMDD_HHMMSS.md
```

---

## 第四部分：API调用方式

### 4.1 Flask应用启动

```python
# app/app.py
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/api/doc/parse', methods=['POST'])
def parse_document():
    # 处理文档解析请求
    pass

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

启动服务：

```bash
python app.py
```

服务启动后访问 http://localhost:5000 查看API文档。

### 4.2 文档处理接口

#### 4.2.1 解析Word文档

```
POST /api/doc/parse
Content-Type: multipart/form-data

参数：
  - file: Word文档文件(.docx)

响应示例：
{
  "success": true,
  "data": {
    "title": "文档标题",
    "paragraphs": [...],
    "tables": [...],
    "styles": {...},
    "metadata": {...}
  }
}
```

#### 4.2.2 学术论文润色

```
POST /api/doc/polish
Content-Type: application/json

参数：
{
  "text": "待润色的文本",
  "language": "zh"
}

响应示例：
{
  "success": true,
  "original": "原文",
  "polished": "润色后文本"
}
```

#### 4.2.3 生成Word文档

```
POST /api/doc/generate
Content-Type: application/json

参数：
{
  "content": {
    "title": "标题",
    "paragraphs": [...],
    "tables": [...]
  },
  "filename": "output.docx"
}
```

### 4.3 PDF处理接口

#### 4.3.1 PDF转图片

```
POST /api/pdf/convert
Content-Type: multipart/form-data

参数：
  - file: PDF文件
  - dpi: 分辨率（可选，默认300）
  - format: 输出格式（可选，默认PNG）
```

#### 4.3.2 版面分析

```
POST /api/pdf/analyze-layout
Content-Type: multipart/form-data

参数：
  - file: PDF文件
```

### 4.4 OCR接口

#### 4.4.1 文字识别

```
POST /api/ocr/extract
Content-Type: multipart/form-data

参数：
  - file: 图片文件
  - language: 识别语言（可选，默认zh）
```

#### 4.4.2 LLM辅助OCR

```
POST /api/ocr/llm
Content-Type: multipart/form-data

参数：
  - file: 图片文件
  - language: 图像语言（可选，默认zh）
```

#### 4.4.3 批量OCR

```
POST /api/ocr/batch
Content-Type: multipart/form-data

参数：
  - files: 图片文件列表
  - language: 识别语言
  - method: tesseract/llm
```

### 4.5 数据处理接口

#### 4.5.1 数据结构化

```
POST /api/data/structure
Content-Type: application/json

参数：
{
  "text": "文本内容",
  "type": "general/table/key_value/timeline"
}
```

#### 4.5.2 导出结构化数据

```
POST /api/data/export
Content-Type: application/json

参数：
{
  "content": {...},
  "format": "json/csv"
}
```

### 4.6 完整处理流程

#### 4.6.1 文档处理流程

```
POST /api/doc/pipeline
Content-Type: multipart/form-data

参数：
  - file: Word文档
  - language: 处理语言

功能：自动解析→LLM润色→生成新文档
```

#### 4.6.2 PDF OCR流程

```
POST /api/pdf/ocr/pipeline
Content-Type: multipart/form-data

参数：
  - file: PDF文件
  - language: 内容语言
  - method: tesseract/llm
  - output: json/csv

功能：PDF转图→版面分析→OCR识别→数据结构化
```

#### 4.6.3 NDL搜索流程

```
POST /api/ndl/search
Content-Type: application/json

参数：
{
  "keyword": "搜索关键词",
  "use_api": true,
  "max_results": 20
}

响应示例：
{
  "success": true,
  "results": [
    {
      "title": "倫理新説",
      "author": "井上哲次郎",
      "ndl_id": "000000421888",
      "url": "https://dl.ndl.go.jp/pid/000000421888"
    }
  ],
  "total": 5
}
```

#### 4.6.4 NDL下载流程

```
POST /api/ndl/download
Content-Type: application/json

参数：
{
  "ndl_id": "000000421888",
  "output_dir": "./downloads",
  "max_attempts": 5
}

响应示例：
{
  "success": true,
  "file_path": "./downloads/倫理新説.pdf",
  "file_size": 12345678,
  "checksum": "abc123..."
}
```

---

## 第五部分：提示词设计原则

### 5.1 提示词架构

本项目采用结构化的提示词管理架构，提示词存储在 `modules/prompts/` 目录下：

```
modules/prompts/
├── llm_client_prompts.md           # LLM客户端提示词
├── academic_note_generator_prompts.md  # 学术笔记生成
├── academic_summarizer_prompts.md  # 学术摘要生成
├── citation_normalizer_prompts.md   # 引用规范化
├── ner_processor_prompts.md        # 命名实体识别
├── paper_polisher_prompts.md       # 论文润色
├── reverse_outline_analyzer_prompts.md # 逆向大纲分析
├── style_transfer_prompts.md       # 风格转换
└── virtual_persona_chatbot_prompts.md  # 虚拟人物对话
```

### 5.2 提示词分类

| 类别 | 标识 | 用途 |
|------|------|------|
| 系统提示词 | *_G001 | 定义AI角色和能力 |
| 模板提示词 | *_T001 | 定义输出格式模板 |
| 用户提示词 | *_U001, *_U002 | 具体任务指令 |

### 5.3 提示词设计原则

#### 5.3.1 角色定义原则

```
你是一位专业的[领域]学术[职务]，精通[技能1]、[技能2]...
请严格按照要求输出...
```

#### 5.3.2 任务明确原则

- 明确输入内容
- 明确输出格式
- 明确约束条件
- 提供示例参考

#### 5.3.3 语言适配原则

| 语言 | 提示词语言 | 示例 |
|------|------------|------|
| 中文 | 简体中文 | 你是一位专业的中国历史学学术论文编辑 |
| 日文 | 日语 | あなたは専門の歴史学学術論文編集者です |
| 英文 | 英语 | As a professional academic paper editor specializing in history |

### 5.4 提示词加载方式

```python
from prompts.prompt_loader import PromptLoader, PromptTemplate

# 加载单个提示词
loader = PromptLoader()
system_prompt = loader.load_prompt('academic_note_generator', 'AN_G001')

# 使用模板
template = PromptTemplate(loader)
rendered = template.render('academic_note_generator', 'AN_T001', {
    'title': '文档标题',
    'content': '文档内容'
})
```

---

## 第六部分：工作流程详解

### 6.1 文档处理完整流程

```
输入Word文档 (.docx)
    ↓
DocProcessor.extract_text() 解析文档
    ↓
LLMClient.academic_polish() 学术润色
    ↓
DocProcessor.create_document() 生成新文档
    ↓
输出润色后文档 (.docx)
```

### 6.2 PDF OCR完整流程

```
输入PDF文件
    ↓
PDFProcessor.convert_to_images() PDF转图片
    ↓
OCRProcessor.extract_text_from_image() OCR识别
    ↓
LLMClient.ocr_correction() OCR结果校正
    ↓
DataStructurer.structure() 数据结构化
    ↓
输出结构化数据 (JSON/CSV)
```

### 6.3 学术笔记生成流程

```
输入学术文献
    ↓
AcademicSummarizer.generate_summary() 生成摘要
    ↓
NERProcessor.recognize_entities() 实体识别
    ↓
AcademicNoteGenerator.generate() 生成笔记
    ↓
ObsidianIntegration.save() 保存到Obsidian
    ↓
输出Obsidian格式笔记 (.md)
```

### 6.4 NDL搜索与下载流程

```
输入检索关键词
    ↓
NDLSearcher.search() 执行NDL搜索
    ↓
SeleniumDownloader.download() Selenium下载PDF
    ↓
PDFProcessor.process() 处理PDF
    ↓
输出处理结果
```

---

## 第七部分：配置管理系统

### 7.1 配置加载器使用

```python
from config.api_config_loader import (
    get_config,
    get_provider_config,
    load_config,
    get_environment,
    get_timeout,
    get_headers,
    get_max_retries,
    create_llm_config
)

# 获取当前配置
config = get_config()

# 获取特定provider配置
dashscope_config = get_provider_config('dashscope')

# 加载指定环境配置
test_config = load_config('test')

# 获取当前环境
env = get_environment()  # 'production' 或 'test'

# 创建LLM配置
llm_config = create_llm_config(
    provider='dashscope',
    module_name='academic_note_generator'
)
```

### 7.2 环境切换

```python
from config.config_helpers import switch_environment

# 切换到测试环境
switch_environment('test')

# 切换到生产环境
switch_environment('production')
```

或在终端设置环境变量：

```bash
# Windows
set API_ENV=test

# Linux/macOS
export API_ENV=test
```

### 7.3 辅助函数

```python
from config.config_helpers import (
    print_config_status,
    validate_environment,
    create_client_with_config
)

# 打印配置状态
print_config_status()

# 验证环境
results = validate_environment()

# 创建客户端
client = create_client_with_config(provider='dashscope')
```

---

## 第八部分：日志管理

### 8.1 日志目录结构

```
log/
├── feature_development/           # 功能开发日志
├── debugging/                      # 调试日志
├── file_reorganization/           # 文件整理日志
├── templates/                      # 日志模板
│   ├── feature_development_template.md
│   ├── debugging_template.md
│   └── file_reorganization_template.md
└── workflow_logger.py             # 日志管理模块
```

### 8.2 必须创建日志的活动

| 活动类型 | 说明 | 日志目录 |
|----------|------|----------|
| 开发新功能 | 开发新模块、新工具、新特性 | feature_development/ |
| 调试旧功能 | 修复Bug、优化性能、解决技术问题 | debugging/ |
| 文件整理 | 重构代码、重组目录、迁移文件 | file_reorganization/ |

### 8.3 日志创建方式

```python
from log.workflow_logger import (
    create_feature_log,
    create_debug_log,
    create_reorganize_log
)

# 开发新功能
log_path = create_feature_log(
    task_name="用户认证模块开发",
    description="开发基于JWT的用户认证系统",
    tasks=[
        {"content": "创建用户模型", "status": "pending"},
        {"content": "实现登录接口", "status": "pending"}
    ]
)

# 调试问题
log_path = create_debug_log(
    task_name="登录失败问题排查",
    description="用户反馈登录失败",
    details={"错误信息": "Authentication failed"}
)

# 文件整理
log_path = create_reorganize_log(
    task_name="模块重组",
    description="重组项目目录结构"
)
```

---

## 第九部分：故障排除

### 9.1 常见问题与解决方案

#### 9.1.1 API密钥配置错误

**症状**：调用LLM接口时返回认证错误

**解决方案**：
1. 检查 `.env` 文件中的API密钥是否正确
2. 确认环境变量已正确加载
3. 验证API密钥是否有足够额度

#### 9.1.2 Tesseract OCR无法识别

**症状**：OCR接口返回空结果或错误

**解决方案**：
1. 确认已安装Tesseract OCR
2. 检查 `TESSERACT_PATH` 配置是否正确
3. 确保已下载对应语言的数据文件

#### 9.1.3 PDF转换图片失败

**症状**：PDF转图片接口返回错误

**解决方案**：
1. 确认PDF文件未损坏
2. 检查是否安装了PyMuPDF：`pip install PyMuPDF`
3. 尝试降低DPI值（如设置为150）

#### 9.1.4 中文/日文识别效果差

**症状**：OCR识别准确率低

**解决方案**：
1. 使用LLM辅助OCR替代Tesseract
2. 提高PDF分辨率（设置DPI=400）
3. 预处理图片（去噪、增强对比度）

#### 9.1.5 内存不足

**症状**：处理大文件时系统崩溃

**解决方案**：
1. 增加系统虚拟内存
2. 分批处理大文件
3. 减少并发请求数

### 9.2 网络问题处理

#### 使用代理（可选）

如果在国内访问OpenAI API遇到问题，可以配置代理：

```python
import os
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'
```

---

## 第十部分：最佳实践

### 10.1 开发规范

1. **模块独立性**：每个模块应独立可测试
2. **配置外置**：敏感配置不硬编码
3. **日志记录**：关键操作需记录日志
4. **错误处理**：异常情况需捕获并处理

### 10.2 性能优化

| 优化项 | 建议 |
|--------|------|
| 使用本地OCR | 处理大量图片时使用Tesseract或Ollama本地模型 |
| 调整DPI | 印刷质量好的文档使用150-200 DPI |
| 批量处理 | 使用批量OCR接口减少网络请求 |
| 缓存结果 | 重复处理时考虑缓存中间结果 |

### 10.3 安全建议

1. **API密钥保护**：不将密钥提交到版本控制系统
2. **环境隔离**：开发和生产环境使用不同配置
3. **输入验证**：对用户输入进行验证和清洗
4. **日志脱敏**：敏感信息在日志中脱敏处理

---

## 附录

### 附录A：环境检查模块

```python
from modules.environment_checker import run_environment_check

# 运行环境检查
passed = run_environment_check("PDF处理任务")
```

### 附录B：NDL OCR心跳监控

```python
from modules.ndl_ocr_monitor import NDLOCRHeartbeatMonitor

monitor = NDLOCRHeartbeatMonitor()
monitor.start_monitoring(interval=300)  # 5分钟心跳

# 执行任务...

monitor.stop_monitoring()
```

### 附录C：批量处理

```python
from modules.ndl_ocr_batch_processor import create_batch_processor

processor = create_batch_processor()
results = processor.process_batch(
    image_dir="test Images",
    output_dir="ocr_output",
    max_pages=20
)
```

---

## 第十一部分：学习模块（LearningModule）

> **详细文档**：[learning_module/README.md](learning_module/README.md)

### 11.1 模块概述

学习模块是本项目的智能学习与研究辅助组件，旨在为其他模块提供自动化的学术资源检索、文献分析和功能改进建议生成能力。通过整合最新的研究成果和最佳实践，帮助开发者和研究人员持续优化模块功能。

### 11.2 核心组件

| 组件 | 类名 | 功能 |
|------|------|------|
| 学术资源检索 | ResearchAnalyzer | 自动检索技术领域的最新研究成果 |
| 文献分析 | LiteratureAnalyzer | 深入分析文献核心内容和技术要点 |
| 改进建议生成 | ImprovementGenerator | 基于研究成果生成针对性优化建议 |

### 11.3 快速使用

```python
from learning_module import LearningModule

learner = LearningModule(api_provider='qwen', test_mode=False)
result = learner.analyze_and_suggest(
    module_name='ner_processor',
    context='日文史料历史实体识别',
    research_topic='Japanese historical NER'
)
```

### 11.4 与其他模块的协同

学习模块可与OpenSourceFinder协同工作，实现学术研究与开源资源的综合评估：
- **LearningModule**：检索学术研究资源，分析文献，生成改进建议
- **OpenSourceFinder**：搜索开源代码和模型，评估质量，生成整合建议

---

## 第十二部分：开源模块搜索器（OpenSourceFinder）

> **详细文档**：[open_source_finder/README.md](open_source_finder/README.md)

### 12.1 模块概述

开源模块搜索器（OpenSourceFinder）用于在GitHub和HuggingFace上搜索相关的开源模块，评估其质量和适用性，生成优化整合报告。

### 12.2 核心功能

| 功能 | 说明 |
|------|------|
| GitHub仓库搜索 | 关键词搜索Python项目，获取README、Stars、Forks等元数据 |
| HuggingFace模型搜索 | 搜索预训练模型，获取Downloads、Likes等信息 |
| 智能评分系统 | GitHub: Stars 40%, Forks 20%, Watchers 15%, Issues 10%, Topics 15% |
| 整合报告生成 | LLM驱动的智能分析，生成优先级行动计划 |

### 12.3 快速使用

```python
from open_source_finder import OpenSourceFinder

finder = OpenSourceFinder(api_provider='qwen')
result = finder.search_all(
    module_name='ocr_processor',
    context='日文OCR识别',
    keywords=['japanese ocr', 'ndl ocr']
)
report = finder.generate_integration_report(result)
```

---

## 第十三部分：NDL搜索模块

> **详细文档**：[ndl-search/docs/README.md](ndl-search/docs/README.md)

### 13.1 模块概述

NDL搜索模块（ndl-search）是专门用于访问日本国立国会图书馆（National Diet Library, NDL）数字资源的搜索和下载模块。该模块支持通过SRU API和浏览器自动化两种方式进行文献检索，并提供PDF下载功能。

### 13.2 核心组件

| 组件 | 类名 | 功能 |
|------|------|------|
| 主搜索器 | NDLSearcher | 整合搜索和下载功能 |
| API客户端 | NDLAPIClient | SRU/OpenSearch API调用 |
| 浏览器下载器 | SeleniumDownloader | Selenium自动化下载 |
| 智能等待 | SmartWait | 替代固定sleep的自适应等待 |

### 13.3 快速使用

```python
from ndl_search.core import NDLSearcher

searcher = NDLSearcher(output_dir='./downloads')
result = searcher.search_and_download(
    keyword='井上哲次郎 倫理新説',
    max_attempts=5
)
```

### 13.4 与其他模块的集成

| 集成方式 | 说明 |
|----------|------|
| OCR处理 | 下载的PDF可通过ocr_processor进行文字识别 |
| 学术笔记 | 识别后的文本可通过academic_note_generator生成笔记 |
| 实体识别 | 文本可通过ner_processor提取历史实体 |
| 引用规范化 | 引用信息可通过citation_normalizer规范化 |

---

## 第十四部分：优化规划与路线图

### 14.1 文档优化规划

#### 14.1.1 已完成的优化项

| 优化项 | 实施日期 | 优化内容 | 效果 |
|--------|----------|----------|------|
| 文档元数据标准化 | 2026-03-30 | 添加版本号、创建日期、更新日期、关联文档 | 提升文档可追溯性 |
| 独立模块文档索引 | 2026-03-30 | 创建独立模块文档索引表 | 减少冗余，提升维护效率 |
| 冗余内容消除 | 2026-03-30 | 简化LearningModule、OpenSourceFinder、NDL搜索模块内容 | 文档长度减少约40% |
| 交叉引用建立 | 2026-03-30 | 在两个核心文档间建立双向链接 | 提升文档导航效率 |
| **模块优化v2.0.0** | 2026-03-30 | 完成所有模块的优化版本开发 | 全面提升系统性能 |

#### 14.1.2 待实施的优化项

| 优化项 | 优先级 | 预计工作量 | 预期效果 |
|--------|--------|------------|----------|
| API文档自动生成 | 中 | 2周 | 从代码注释自动生成API文档 |
| 多语言文档支持 | 低 | 4周 | 提供英文版本文档 |
| 文档版本控制系统 | 中 | 1周 | 使用Git管理文档变更历史 |
| 交互式文档站点 | 低 | 3周 | 使用MkDocs或Docusaurus构建文档站点 |

### 14.2 模块优化规划

#### 14.2.1 第一阶段优化（高优先级）- ✅ 已完成

| 模块 | 优化文件 | 优化内容 | 完成状态 |
|------|----------|----------|----------|
| NER处理器 | `modules/ner_processor_optimized.py` | 1. 扩展实体词典 2. 优化提示词 3. 添加后处理规则 4. 词典匹配功能 | ✅ 已完成 |
| OCR处理器 | `modules/ocr_processor_optimized.py` | 1. 多引擎对比(Tesseract/NDL/LLM) 2. 图像预处理(降噪/二值化/倾斜校正) 3. 结构化输出 | ✅ 已完成 |
| 论文润色模块 | `modules/paper_polisher_optimized.py` | 1. 日本史领域术语库 2. 优化润色提示词 3. 修改建议解释 4. 多种润色模式 | ✅ 已完成 |

#### 14.2.2 第二阶段优化（中优先级）- ✅ 已完成

| 模块 | 优化文件 | 优化内容 | 完成状态 |
|------|----------|----------|----------|
| 学术笔记生成器 | `modules/academic_note_generator_optimized.py` | 1. Markdown模板系统 2. 自定义模板支持 3. 标签系统 4. 多种笔记类型 | ✅ 已完成 |
| 学术摘要生成器 | `modules/academic_summarizer_optimized.py` | 1. 优化摘要结构 2. 关键句提取 3. 多语言摘要(中/英/日) 4. 多种摘要类型 | ✅ 已完成 |
| LLM客户端 | `modules/llm_client_optimized.py` | 1. 指数退避重试机制 2. 服务降级策略 3. 超时处理优化 4. 请求统计监控 | ✅ 已完成 |

#### 14.2.3 第三阶段优化（低优先级）- ✅ 已完成

| 模块 | 优化文件 | 优化内容 | 完成状态 |
|------|----------|----------|----------|
| PDF处理器 | `modules/pdf_processor_optimized.py` | 1. 分块处理 2. 内存优化管理 3. 流式处理支持 4. 多引擎支持 | ✅ 已完成 |
| Word文档处理器 | `modules/word_processor_optimized.py` | 1. 完整样式解析 2. 表格处理 3. 图片链接保留 4. 批注/修订提取 | ✅ 已完成 |

### 14.3 技术债务清理规划

| 债务类型 | 当前状态 | 清理计划 | 优先级 | 完成状态 |
|----------|----------|----------|--------|----------|
| 代码注释缺失 | 部分模块缺少详细注释 | 按模块逐步补充docstring | 中 | ✅ 已完成 |
| 单元测试覆盖率低 | 核心模块测试覆盖率约60% | 提升至80%以上 | 高 | 待实施 |
| 配置文件分散 | 配置项分布在多个文件中 | 统一到config目录 | 低 | 待实施 |
| 日志格式不统一 | 各模块日志格式不一致 | 统一日志格式和级别 | 中 | ✅ 已完成 |

### 14.4 新增优化模块索引

#### 14.4.1 优化版模块文件列表

| 模块名称 | 文件路径 | 主要特性 |
|----------|----------|----------|
| NER处理器优化版 | `modules/ner_processor_optimized.py` | 词典匹配、后处理规则、置信度评分 |
| OCR处理器优化版 | `modules/ocr_processor_optimized.py` | 多引擎对比、图像预处理、OCRResult数据类 |
| 论文润色优化版 | `modules/paper_polisher_optimized.py` | 领域术语库、多润色模式、修改报告生成 |
| 学术笔记生成器优化版 | `modules/academic_note_generator_optimized.py` | Markdown模板、标签系统、自定义模板 |
| 学术摘要生成器优化版 | `modules/academic_summarizer_optimized.py` | 关键句提取、多语言支持、摘要类型选择 |
| LLM客户端优化版 | `modules/llm_client_optimized.py` | 重试机制、降级策略、请求统计 |
| PDF处理器优化版 | `modules/pdf_processor_optimized.py` | 分块处理、流式处理、内存管理 |
| Word处理器优化版 | `modules/word_processor_optimized.py` | 样式解析、表格处理、图片信息提取 |
| 统一日志模块 | `utils/logger.py` | 统一格式、多输出目标、彩色输出 |

#### 14.4.2 优化版模块使用示例

```python
# NER处理器优化版
from modules.ner_processor_optimized import create_ner_processor_optimized
ner = create_ner_processor_optimized(api_provider='qwen')
entities = ner.recognize_historical_entities(text, use_dictionary=True)

# OCR处理器优化版
from modules.ocr_processor_optimized import create_ocr_processor_optimized
ocr = create_ocr_processor_optimized(enable_preprocessing=True)
results = ocr.compare_engines('image.png', language='ja')

# 论文润色优化版
from modules.paper_polisher_optimized import create_paper_polisher_optimized
polisher = create_paper_polisher_optimized('qwen')
result = polisher.process_document('input.docx', 'output.docx', mode='simplify')

# 学术笔记生成器优化版
from modules.academic_note_generator_optimized import create_academic_note_generator_optimized
generator = create_academic_note_generator_optimized()
note = generator.generate_note(content, note_type='reading_note')

# 学术摘要生成器优化版
from modules.academic_summarizer_optimized import create_academic_summarizer_optimized
summarizer = create_academic_summarizer_optimized()
summary = summarizer.generate_summary(content, language='zh')

# LLM客户端优化版
from modules.llm_client_optimized import create_llm_client_optimized, RetryConfig
client = create_llm_client_optimized({
    'provider': 'dashscope',
    'retry_config': RetryConfig(max_retries=3)
})

# PDF处理器优化版
from modules.pdf_processor_optimized import create_pdf_processor_optimized
pdf = create_pdf_processor_optimized(chunk_size=50)
for chunk in pdf.extract_text_streaming('document.pdf'):
    print(f"Chunk {chunk.chunk_id}: {chunk.char_count} chars")

# Word处理器优化版
from modules.word_processor_optimized import create_word_processor_optimized
word = create_word_processor_optimized()
result = word.process_document('document.docx')

# 统一日志模块
from utils.logger import setup_logging, get_logger
setup_logging(level='INFO', log_file='logs/app.log')
logger = get_logger(__name__)
```

### 14.4 外部集成规划

#### 14.4.1 LearningModule集成计划

| 集成目标 | 实施方式 | 预期效果 |
|----------|----------|----------|
| 自动化模块优化建议 | 定期调用LearningModule分析各模块 | 持续获得改进建议 |
| 学术资源库建设 | 收集相关领域的最新研究成果 | 建立知识库支持决策 |
| 提示词优化 | 使用LearningModule优化各模块提示词 | 提升LLM调用效果 |

#### 14.4.2 OpenSourceFinder集成计划

| 集成目标 | 实施方式 | 预期效果 |
|----------|----------|----------|
| 开源组件评估 | 定期搜索相关开源项目 | 发现可复用的解决方案 |
| 模型资源整合 | 搜索HuggingFace相关模型 | 扩展模型选择范围 |
| 最佳实践借鉴 | 分析优质开源项目架构 | 改进系统设计 |

### 14.5 资源需求评估

| 资源类型 | 当前状态 | 需求量 | 获取方式 |
|----------|----------|--------|----------|
| 开发时间 | 兼职开发 | 每周10-15小时 | 内部调配 |
| API调用额度 | 基础额度 | 增加50% | 申请升级 |
| 测试数据 | 少量样本 | 扩充至100+文档 | 公开数据集 |
| 计算资源 | 本地开发 | 云端测试环境 | 云服务部署 |

### 14.6 风险评估与缓解措施

| 风险类型 | 风险描述 | 缓解措施 |
|----------|----------|----------|
| API服务不稳定 | LLM API可能存在限流或中断 | 实现多服务商降级机制 |
| 数据隐私 | 用户上传的学术文献可能包含敏感信息 | 添加数据脱敏功能 |
| 依赖更新 | 第三方库版本更新可能引入兼容性问题 | 建立依赖版本锁定机制 |
| 文档滞后 | 代码更新后文档可能未及时同步 | 建立文档更新检查清单 |

---

## 第十五部分：古典籍OCR训练数据准备工作流

### 15.1 模块概述

古典籍OCR训练数据准备工作流模块（`modules/classical_ocr_training_workflow.py`）是专门为古典籍史料PDF处理设计的核心组件，集成了版面分析、内容分类、日期解析和训练数据生成功能。

### 15.2 核心组件

#### 15.2.1 数据类定义

| 类名 | 用途 | 关键属性 |
|------|------|----------|
| ContentType | 内容类型枚举 | printed_date, printed_weather, printed_quote, handwritten, unknown |
| ProcessingStage | 处理阶段枚举 | INITIALIZED, PDF_LOADED, LAYOUT_ANALYZED, CONTENT_CLASSIFIED, DATE_EXTRACTED, TRAINING_DATA_GENERATED, COMPLETED, FAILED |
| LayoutRegion | 版面区域 | box, content_type, confidence, text, ocr_text |
| DateInfo | 日期信息 | era, era_year, year, month, day, date_key |
| TrainingSample | 训练样本 | image_path, annotation_text, source_page, date_key, box, confidence |

#### 15.2.2 核心处理器

| 类名 | 功能 | 主要方法 |
|------|------|----------|
| KanjiNumberConverter | 汉字数字转换 | to_number(kanji: str) -> int |
| ONNXModelManager | ONNX模型管理 | load_detector(), load_recognizer(), run_detection(), run_recognition() |
| LayoutDetector | 版面检测 | detect_lines(), classify_content(), parse_date_from_text() |
| AnnotationExtractor | 标注提取 | extract_dates_from_pdf(), extract_text_from_page() |
| ClassicalOCRTrainingWorkflow | 主工作流 | run_full_workflow(), process_source_pdf(), match_with_annotation() |

### 15.3 使用方法

#### 15.3.1 完整工作流

```python
from modules.classical_ocr_training_workflow import (
    ClassicalOCRTrainingWorkflow, create_default_config
)

# 创建配置
config = create_default_config()

# 初始化工作流
workflow = ClassicalOCRTrainingWorkflow(config)

# 运行完整工作流
result = workflow.run_full_workflow(
    source_pdf="path/to/source.pdf",        # 原始史料PDF
    annotation_pdf="path/to/annotation.pdf", # 翻刻版PDF
    output_dir="path/to/output",            # 输出目录
    start_page=1,                           # 起始页码
    end_page=10,                            # 结束页码
    target_era_year=36                      # 目标明治年份
)

# 检查结果
if result['success']:
    print(f"训练样本数: {result['source_result']['data']['total_training_samples']}")
    print(f"处理时间: {result['duration_seconds']:.2f}秒")
```

#### 15.3.2 分步处理

```python
# 仅处理原始史料PDF
source_result = workflow.process_source_pdf(
    pdf_path="path/to/source.pdf",
    output_dir="path/to/output",
    start_page=1,
    end_page=10,
    target_era_year=36
)

# 日期匹配
match_result = workflow.match_with_annotation(
    source_dates=source_result.data['dates'],
    annotation_pdf_path="path/to/annotation.pdf",
    target_era_year=36
)
```

### 15.4 输出文件结构

```
output_dir/
├── handwritten_images/          # 手写文本行图像
│   ├── page_0001/
│   │   ├── line_0000.png
│   │   ├── line_0001.png
│   │   └── ...
│   └── ...
├── analysis/                    # 页面分析结果
│   ├── page_0001.json
│   └── ...
├── training_samples.json        # 训练样本数据
├── workflow_summary.json        # 工作流摘要
└── final_workflow_result.json   # 最终结果
```

### 15.5 技术参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| detector_input_size | 1024 | 检测模型输入尺寸 |
| recognizer_input_size | (384, 32) | 识别模型输入尺寸 |
| conf_threshold | 0.3 | 检测置信度阈值 |
| target_image_size | (384, 32) | 输出图像尺寸 |

---

## 第十六部分：通用板式分析模块

### 16.1 模块概述

通用板式分析模块（`modules/universal_layout_analyzer.py`）是一个可扩展的模块化组件，支持多种文档类型的板式分析需求，包括古典日记、报纸、书籍、手稿、公文、信函等。

### 16.2 核心组件

#### 16.2.1 枚举类型

| 枚举名 | 值 | 说明 |
|--------|-----|------|
| DocumentType | CLASSICAL_DIARY | 古典日记 |
|  | NEWSPAPER | 报纸 |
|  | BOOK | 书籍 |
|  | MANUSCRIPT | 手稿 |
|  | OFFICIAL_DOCUMENT | 公文 |
|  | LETTER | 信函 |
| RegionType | TITLE, BODY_TEXT, HEADER, FOOTER | 区域类型 |
|  | MARGINALIA, DATE, SIGNATURE | 边注、日期、签名 |
|  | TABLE, FIGURE, HANDWRITTEN, PRINTED | 表格、图片、手写、印刷 |
| TextOrientation | HORIZONTAL, VERTICAL, MIXED | 文本方向 |

#### 16.2.2 数据类

| 类名 | 用途 | 关键属性 |
|------|------|----------|
| LayoutRegion | 版面区域 | box, region_type, confidence, text, orientation, language, metadata, children |
| PageLayout | 页面布局 | page_number, width, height, orientation, regions, metadata |
| DocumentLayout | 文档布局 | document_type, pages, metadata |

#### 16.2.3 分析器类

| 类名 | 功能 | 支持文档类型 |
|------|------|--------------|
| ONNXLayoutAnalyzer | ONNX模型版面分析 | 所有类型 |
| RegionClassifier | 区域类型分类 | 所有类型 |
| TextRecognizer | 文本识别 | 所有类型 |
| DocumentTypeDetector | 文档类型检测 | 所有类型 |
| UniversalLayoutAnalyzer | 统一分析接口 | 所有类型 |

### 16.3 使用方法

#### 16.3.1 基本使用

```python
from modules.universal_layout_analyzer import (
    UniversalLayoutAnalyzer, create_layout_config
)

# 创建配置
config = create_layout_config()

# 初始化分析器
analyzer = UniversalLayoutAnalyzer(config)

# 分析PDF文档
document = analyzer.analyze_document(
    pdf_path="path/to/document.pdf",
    start_page=1,
    end_page=10
)

# 输出结果
print(f"文档类型: {document.document_type}")
print(f"分析页数: {len(document.pages)}")

# 导出结果
analyzer.export_results(document, "output.json", format='json')
```

#### 16.3.2 提取特定类型区域

```python
# 提取所有日期区域
date_regions = analyzer.extract_regions_by_type(
    document, 
    region_type="date"
)

# 提取所有手写区域
handwritten_regions = analyzer.extract_regions_by_type(
    document,
    region_type="handwritten"
)

for region in handwritten_regions:
    print(f"页码: {region.metadata.get('page_number')}")
    print(f"文本: {region.text}")
    print(f"边界框: {region.box}")
```

#### 16.3.3 命令行使用

```bash
python -m modules.universal_layout_analyzer \
    --pdf path/to/document.pdf \
    --output output.json \
    --start-page 1 \
    --end-page 10 \
    --format json
```

### 16.4 扩展开发

#### 16.4.1 自定义区域分类器

```python
from modules.universal_layout_analyzer import RegionClassifier, RegionType

class CustomRegionClassifier(RegionClassifier):
    @classmethod
    def classify(cls, text, box, page_height, page_width):
        # 自定义分类逻辑
        if "特定关键词" in text:
            return "custom_type"
        return super().classify(text, box, page_height, page_width)
```

#### 16.4.2 自定义文档类型检测器

```python
from modules.universal_layout_analyzer import DocumentTypeDetector, DocumentType

class CustomDocumentTypeDetector(DocumentTypeDetector):
    CUSTOM_INDICATORS = ['自定义指标1', '自定义指标2']
    
    @classmethod
    def detect(cls, text_samples):
        all_text = ' '.join(text_samples)
        
        # 自定义检测逻辑
        custom_score = sum(1 for ind in cls.CUSTOM_INDICATORS if ind in all_text)
        
        if custom_score > 2:
            return "custom_type"
        
        return super().detect(text_samples)
```

### 16.5 支持的文档类型

| 文档类型 | 检测指标 | 典型特征 |
|----------|----------|----------|
| 古典日记 | 日記、日誌、記録、明治、大正、昭和 | 日期标题、天气记录、手写内容 |
| 报纸 | 新聞、報知、朝日、毎日、読売、号 | 多栏布局、标题、日期 |
| 公文 | 令、達、伺、届、報告、申請 | 正式格式、签名、日期 |
| 信函 | 拝啓、敬具、様、殿、貴殿 | 称呼、正文、署名 |

---

## 第十七部分：统一LLM API集成框架

### 17.1 框架概述

统一LLM API集成框架为所有模块提供标准化的LLM API调用能力，支持API模式和脚本/正则表达式模式的双模式运行。用户可根据需求自由切换执行模式，实现灵活的任务处理。

**核心组件**：

| 组件 | 文件路径 | 功能说明 |
|------|----------|----------|
| 安全API密钥管理器 | `modules/secure_api_key_manager.py` | 安全管理API密钥，确保密钥仅存储在secrets文件夹 |
| 统一任务执行器 | `modules/unified_task_executor.py` | 提供统一任务执行接口，支持双模式切换 |
| 模块适配器 | `modules/module_adapters.py` | 为现有模块提供统一的适配器接口 |
| 任务管理器 | `modules/task_manager.py` | 用户友好的任务管理入口 |
| 命令行工具 | `modules/task_cli.py` | 命令行任务执行工具 |

### 17.2 双模式执行机制

#### 17.2.1 API模式

API模式通过调用大语言模型API执行任务，适用于需要语义理解、上下文分析的复杂任务。

**特点**：
- 支持多种LLM服务商（通义千问、智谱AI、DeepSeek、OpenAI等）
- 自动从`secrets/api_keys.txt`读取API密钥
- 支持自定义提示词模板
- 结果缓存机制

#### 17.2.2 脚本模式

脚本模式使用传统脚本/正则表达式执行任务，适用于规则明确、处理速度要求高的任务。

**特点**：
- 无需API调用，本地执行
- 处理速度快
- 支持正则表达式模式匹配
- 词典匹配功能

#### 17.2.3 模式切换

```python
from modules.task_manager import TaskManager

# 创建任务管理器（默认API模式）
manager = TaskManager(mode='api', provider='qwen')

# 切换到脚本模式
manager.set_mode('script')

# 切换回API模式
manager.set_mode('api')

# 查看当前模式
print(manager.mode)  # 'api' 或 'script'
```

### 17.3 API密钥安全管理

#### 17.3.1 密钥存储位置

API密钥必须存储在`secrets/api_keys.txt`文件中，格式如下：

```
# API密钥配置文件
# 格式: 服务商名称=API密钥

qwen=sk-your-qwen-api-key
deepseek=sk-your-deepseek-api-key
zhipu=your-zhipu-api-key
openai=sk-your-openai-api-key
```

#### 17.3.2 安全管理器使用

```python
from modules.secure_api_key_manager import SecureAPIKeyManager

# 获取管理器实例（单例模式）
manager = SecureAPIKeyManager()

# 检查密钥状态报告
report = manager.get_status_report()
print(report['services'])
# 输出: {'qwen': {'has_key': True, ...}, 'deepseek': {'has_key': False, ...}, ...}

# 获取密钥（仅在内存中使用，不会存储到其他位置）
api_key = manager.get_key('qwen')

# 检查密钥是否已配置
if manager.has_key('qwen'):
    print("通义千问API密钥已配置")
```

#### 17.3.3 安全保障机制

| 安全措施 | 说明 |
|----------|------|
| 密钥隔离 | API密钥仅存储在secrets文件夹内 |
| 单例模式 | 全局唯一管理器实例，防止密钥泄露 |
| 访问日志 | 记录所有密钥访问行为 |
| 内存安全 | 密钥仅在内存中使用，不写入其他文件 |

### 17.4 模块LLM API集成详解

#### 17.4.1 命名实体识别（NER）模块

**API模式提示词模板**：

```
你是一位专业的日本史研究专家，精通历史文献中的实体识别。
请从以下文本中识别所有历史实体，包括：
- 人物（person）：历史人物姓名
- 地点（location）：地理位置、行政区划
- 组织（organization）：机构、藩国、幕府等
- 事件（event）：历史事件名称
- 年代（date）：年号、年份、日期
- 著作（work）：文献、书籍名称
- 概念（concept）：思想、制度、术语

输入文本：
{text}

请以JSON格式输出，格式如下：
{
  "entities": [
    {"text": "实体文本", "category": "实体类型", "confidence": 0.95}
  ]
}
```

**使用示例**：

```python
from modules.task_manager import TaskManager

manager = TaskManager(mode='api', provider='qwen')

# API模式识别
result = manager.ner(
    text="伊藤博文出生于1841年，是明治维新的重要人物。",
    categories=['person', 'event', 'date']
)

# 脚本模式识别（使用正则表达式和词典）
manager.set_mode('script')
result = manager.ner(
    text="伊藤博文出生于1841年，是明治维新的重要人物。"
)
```

**输出格式**：

```json
{
  "success": true,
  "data": {
    "entities": [
      {"text": "伊藤博文", "category": "person", "confidence": 0.98},
      {"text": "1841年", "category": "date", "confidence": 0.95},
      {"text": "明治维新", "category": "event", "confidence": 0.97}
    ]
  },
  "mode": "api",
  "execution_time": 1.23
}
```

#### 17.4.2 学术笔记生成模块

**API模式提示词模板**：

```
你是一位专业的学术笔记撰写专家，精通Obsidian笔记格式。
请根据以下学术文献内容，生成结构化的阅读笔记。

要求：
1. 使用Markdown格式
2. 包含双向链接 [[链接]] 语法
3. 提取核心实体作为知识图谱节点
4. 生成摘要和关键观点

输入内容：
{content}

请按以下格式输出：
---
type: reading_note
tags:
  - #文献笔记
  - #日本史
created: {date}
source: {source}
---

# {title}

## 📋 总体摘要
[摘要内容]

## 🔑 核心观点
- 观点1
- 观点2

## 🔗 核心图谱节点提取
- [[人物A]]
- [[地点B]]
- [[事件C]]
```

**使用示例**：

```python
from modules.task_manager import TaskManager

manager = TaskManager(mode='api')

# 生成学术笔记
result = manager.academic_note(
    content="文献内容...",
    title="伊藤博文传",
    note_type='reading_note'
)

# 使用自定义提示词
custom_prompt = """
请分析以下历史文献的学术价值：
{content}

重点关注：
1. 史料来源
2. 研究方法
3. 学术贡献
"""

result = manager.execute_with_prompt(
    task_type='academic_note',
    prompt=custom_prompt,
    content="文献内容..."
)
```

#### 17.4.3 论文润色模块

**API模式提示词模板**：

```
你是一位专业的学术论文编辑，精通日本史研究领域。
请对以下学术论文段落进行润色，要求：

1. 删除冗余论述，保持学术严谨性
2. 修正语法错误和表达不当之处
3. 保持原文的核心观点和论证逻辑
4. 使用规范的学术表达

原文：
{text}

请输出润色后的文本，并说明主要修改内容。
```

**使用示例**：

```python
from modules.task_manager import TaskManager

manager = TaskManager(mode='api', provider='qwen')

# 论文润色
result = manager.paper_polish(
    text="待润色的论文段落...",
    mode='simplify',  # 简化模式
    preserve_terms=True  # 保留专业术语
)

# 文档级润色
result = manager.paper_polish_document(
    input_path='input.docx',
    output_path='output.docx',
    enable_track_changes=True
)
```

#### 17.4.4 引用规范化模块

**API模式提示词模板**：

```
你是一位学术引用规范专家，精通多种引用格式。
请将以下引用信息转换为{target_format}格式。

支持的格式：
- Chicago格式
- APA格式
- GB/T 7714格式
- 日本史学会格式

输入引用：
{citation}

目标格式：{target_format}

请输出规范化后的引用格式。
```

**使用示例**：

```python
from modules.task_manager import TaskManager

manager = TaskManager(mode='api')

# 单条引用规范化
result = manager.citation_normalize(
    citation="伊藤博文. 伊藤博文伝. 春亩公追颂会, 1940.",
    target_format='chicago'
)

# 批量规范化
citations = [
    "引用1...",
    "引用2...",
]
result = manager.citation_normalize_batch(
    citations=citations,
    target_format='gbt7714'
)
```

#### 17.4.5 OCR结果校正模块

**API模式提示词模板**：

```
你是一位专业的OCR结果校正专家，精通日文历史文献。
请校正以下OCR识别结果，修正以下类型的错误：

1. 字符识别错误（如：力→カ、口→ロ）
2. 断句错误
3. 标点符号错误
4. 漏字、多字问题

原始OCR结果：
{ocr_text}

语言：{language}

请输出校正后的文本。
```

**使用示例**：

```python
from modules.task_manager import TaskManager

manager = TaskManager(mode='api')

# OCR结果校正
result = manager.ocr_correction(
    ocr_text="OCR识别的原始文本...",
    language='ja'
)
```

#### 17.4.6 文本摘要模块

**API模式提示词模板**：

```
你是一位专业的学术摘要撰写专家。
请为以下文本生成摘要，要求：

1. 保留核心观点和关键信息
2. 控制在{max_length}字以内
3. 使用学术规范的表达方式
4. 保持逻辑清晰

输入文本：
{text}

请输出摘要内容。
```

**使用示例**：

```python
from modules.task_manager import TaskManager

manager = TaskManager(mode='api')

# 生成摘要
result = manager.summarize(
    text="长文本内容...",
    max_length=200,
    language='zh'
)

# 多语言摘要
result = manager.summarize(
    text="文本内容...",
    output_languages=['zh', 'en', 'ja']
)
```

#### 17.4.7 实体消歧模块

**API模式提示词模板**：

```
你是一位日本史研究专家，精通历史实体的消歧分析。
请根据上下文判断以下实体的具体含义。

实体：{entity}
上下文：{context}

可能的含义：
{possible_meanings}

请分析上下文中的关键词，判断实体在此语境下的准确含义。
输出格式：
{
  "meaning": "具体含义",
  "confidence": 0.95,
  "evidence": "判断依据"
}
```

**使用示例**：

```python
from modules.task_manager import TaskManager

manager = TaskManager(mode='api')

# 实体消歧
result = manager.disambiguate_entity(
    entity="江戸",
    context="江戸幕府が終焉を迎えた",
    possible_meanings=["城市", "幕府机构"]
)
```

#### 17.4.8 文风分析与迁移模块

**API模式提示词模板**：

```
你是一位学术写作风格分析专家。
请分析以下文本的文风特征，从四个维度进行评估：

1. 句法结构：句子长度、复杂度、从句使用
2. 词汇深度：学术词汇比例、术语使用
3. 语气声音：客观性、立场表达方式
4. 修辞机制：论证方式、引用风格

输入文本：
{text}

请输出文风矩阵分析结果。
```

**使用示例**：

```python
from modules.task_manager import TaskManager

manager = TaskManager(mode='api')

# 文风分析
result = manager.analyze_style(
    text="待分析的学术文本..."
)

# 文风迁移
result = manager.transfer_style(
    text="待迁移文本...",
    target_style="目标风格描述"
)
```

#### 17.4.9 史料发言识别模块

**API模式提示词模板**：

```
你是一位日本古典文献研究专家。
请从以下史料文本中识别所有发言内容，包括：

1. 直接引语：「...」
2. 书信内容
3. 公文陈述
4. 对话记录

同时提取文本中的年代信息：
- 年号日期（明治十年一月四日）
- 西历日期（1877年1月4日）
- 汉字数字日期

输入文本：
{text}

请以JSON格式输出识别结果。
```

**使用示例**：

```python
from modules.task_manager import TaskManager

manager = TaskManager(mode='api')

# 发言识别
result = manager.extract_speeches(
    text="史料文本内容..."
)

# 年代提取
result = manager.extract_dates(
    text="史料文本内容..."
)
```

#### 17.4.10 版面分析模块

**API模式提示词模板**：

```
你是一位文档版面分析专家。
请分析以下文档的结构，识别以下区域类型：

1. 标题区域（title）
2. 正文区域（body_text）
3. 页眉（header）
4. 页脚（footer）
5. 边注（marginalia）
6. 日期区域（date）
7. 表格（table）
8. 图片（figure）

文档类型：{document_type}
文本样本：
{text_samples}

请输出版面分析结果。
```

**使用示例**：

```python
from modules.task_manager import TaskManager

manager = TaskManager(mode='api')

# 版面分析
result = manager.analyze_layout(
    pdf_path="document.pdf",
    document_type="classical_diary"
)
```

### 17.5 自定义提示词执行

#### 17.5.1 基本用法

```python
from modules.task_manager import TaskManager

manager = TaskManager(mode='api')

# 使用自定义提示词执行任务
result = manager.execute_with_prompt(
    task_type='text_analysis',
    prompt="""
    请分析以下历史文献的史料价值：
    {text}
    
    评估维度：
    1. 史料来源可靠性
    2. 内容完整程度
    3. 学术参考价值
    """,
    text="文献内容..."
)
```

#### 17.5.2 提示词模板变量

| 变量名 | 说明 | 使用示例 |
|--------|------|----------|
| {text} | 输入文本 | 待处理的文本内容 |
| {content} | 文档内容 | 完整文档内容 |
| {language} | 语言代码 | zh/ja/en |
| {target_format} | 目标格式 | chicago/apa |
| {max_length} | 最大长度 | 200 |
| {document_type} | 文档类型 | classical_diary |

#### 17.5.3 预设配置管理

```python
from modules.task_manager import TaskManager, TaskPreset

manager = TaskManager(mode='api')

# 创建预设配置
preset = TaskPreset(
    name='high_quality_ner',
    task_type='ner',
    temperature=0.1,
    max_tokens=4000,
    description='高质量NER识别配置'
)
manager.add_preset(preset)

# 使用预设配置
result = manager.ner(
    text="文本内容...",
    preset='high_quality_ner'
)
```

### 17.6 命令行使用

#### 17.6.1 显示系统信息

```bash
python -m modules.task_cli --info
```

#### 17.6.2 执行任务

```bash
# API模式执行NER任务
python -m modules.task_cli --mode api --task ner --text "伊藤博文是明治维新的重要人物"

# 脚本模式执行摘要任务
python -m modules.task_cli --mode script --task summarize --text "长文本内容..."

# 使用自定义提示词
python -m modules.task_cli --mode api --task custom --prompt "请分析：{text}" --text "内容"
```

#### 17.6.3 交互模式

```bash
python -m modules.task_cli --interactive
```

### 17.7 批量处理

```python
from modules.task_manager import TaskManager

manager = TaskManager(mode='api')

# 批量NER处理
texts = ["文本1", "文本2", "文本3"]
results = manager.batch_process(
    task_type='ner',
    items=texts,
    parallel=True,
    max_workers=3
)

# 批量摘要生成
results = manager.batch_summarize(
    texts=texts,
    max_length=200
)
```

### 17.8 执行统计与监控

```python
from modules.task_manager import TaskManager

manager = TaskManager(mode='api')

# 执行多个任务...
manager.ner("文本1")
manager.summarize("文本2")

# 获取执行统计
stats = manager.get_statistics()
print(f"总任务数: {stats['total_tasks']}")
print(f"成功率: {stats['success_rate']:.2%}")
print(f"平均执行时间: {stats['avg_execution_time']:.2f}秒")
```

### 17.9 错误处理与重试

```python
from modules.task_manager import TaskManager

manager = TaskManager(mode='api')

# 自动重试配置
result = manager.ner(
    text="文本内容...",
    retry_count=3,
    retry_delay=1.0
)

# 错误处理
if not result['success']:
    print(f"错误: {result['error']}")
    # 自动降级到脚本模式
    manager.set_mode('script')
    result = manager.ner(text="文本内容...")
```

### 17.10 与现有模块的集成

统一LLM API集成框架与现有模块完全兼容，可通过适配器模式无缝集成：

```python
from modules.module_adapters import (
    NERAdapter, AcademicNoteAdapter, PaperPolishAdapter,
    CitationAdapter, OCRAdapter, SummaryAdapter,
    create_adapter
)

# 使用适配器
adapter = create_adapter('ner', mode='api', provider='qwen')
result = adapter.recognize("文本内容...")

# 切换模式
adapter.set_mode('script')
result = adapter.recognize("文本内容...")
```

### 17.11 最佳实践

#### 17.11.1 模式选择建议

| 任务类型 | 推荐模式 | 原因 |
|----------|----------|------|
| 复杂语义理解 | API | 需要上下文分析能力 |
| 规则明确的任务 | 脚本 | 处理速度快，无需API调用 |
| 大批量处理 | 脚本 | 避免API限流和成本问题 |
| 高精度要求 | API | LLM语义理解能力更强 |
| 离线环境 | 脚本 | 无需网络连接 |

#### 17.11.2 API密钥管理建议

1. **定期轮换**：建议每3-6个月更换API密钥
2. **权限最小化**：仅授予必要的API权限
3. **监控使用量**：定期检查API调用统计
4. **备份密钥**：安全存储密钥备份

#### 17.11.3 性能优化建议

1. **使用缓存**：启用结果缓存避免重复调用
2. **批量处理**：合并多个请求减少API调用次数
3. **异步执行**：使用异步模式提高并发性能
4. **合理超时**：设置合适的超时时间

---

## 文档结束

本技术指南涵盖了AItools-for-historyresearch工作区的所有核心功能和使用方法。如有任何疑问，请查阅相关模块的源代码或提交Issue。

**文档版本**：2.3.0  
**更新日期**：2026年3月31日

**本次更新内容**：
- 新增 第十七部分：统一LLM API集成框架
- 添加双模式执行机制说明
- 添加各模块LLM API提示词模板
- 添加API密钥安全管理机制
- 添加命令行和批量处理使用方法

**历史更新内容**：
- 新增 第十五部分：古典籍OCR训练数据准备工作流
- 新增 第十六部分：通用板式分析模块
- 添加工作流使用方法和技术参数说明
- 添加模块扩展开发指南
- 新增 LLM OCR处理器模块（llm_ocr_processor.py）文档
- 集成通义千问VL OCR API支持
- 添加HTML标签清理、水印去除、页码识别等数据清洗功能
- 更新系统架构图，纳入LLM OCR处理器
