# 历史研究AI辅助工具

## 🎯 这是什么？

一个专为**日本史研究人员**打造的AI工具箱，帮助你处理日文史料、润色学术论文、管理研究文献。

### 你是否为这些问题困扰？

- 📄 日文PDF文献识别困难？
- ✍️ 学术论文润色耗时费力？
- 🔍 历史人名、地名难以整理？
- 📚 参考文献格式不统一？

**这款工具正是为你设计的！**

---

## 👥 适用人群

| 群体 | 使用场景 |
|------|----------|
| 🎓 日本史研究生 | 撰写课程论文、毕业论文 |
| 📚 专职研究员 | 处理大量日文史料 |
| ✏️ 学术编辑 | 润色审阅学术稿件 |
| 🏛️ 档案管理人员 | 数字化历史文档 |

---

## ✨ 核心功能

### 1. 学术论文润色 ✍️
自动修正语法错误，提升学术表达规范度，保留历史专有名词。支持多种润色策略（段落/逐句/修订模式）。

### 2. PDF文献OCR识别 📄
将扫描版日文PDF转换为可编辑文本，支持JSON/CSV导出。支持NDL OCR（近代现代文献）和NDL古典籍OCR（古典草书字文献）。

### 3. 历史实体识别 🔍
自动识别人名、地名、事件、机构等历史专有名词，支持同形异义词消歧（如"江戸"、"薩摩"等）。

### 4. 学术笔记生成 📝
生成符合Obsidian格式的阅读笔记，自动构建知识图谱，支持双向链接。

### 5. 引用格式规范化 📚
统一参考文献格式（支持Chicago、APA、GB/T 7714、MLA、IEEE、Harvard等）。

### 6. 文风分析与迁移 🎭
四维度文风矩阵分析（句法结构、词汇深度、语气叙事、学术修辞），支持少样本文风模仿。

### 7. 虚拟人格对话系统 💬
预设历史人物人格（福泽谕吉、丸山真男、涩泽荣一），支持学术咨询和历史事件评论。

### 8. 引文网络分析 🕸️
构建引文网络图谱，分析理论演进脉络，识别学术流派及其分支。

### 9. 多语言支持 🌏
中文、日文、英文、韩文等多种语言处理。

---

## 🚀 快速开始

### 第一步：安装依赖

```bash
# 克隆项目
git clone <repository-url>
cd AItools-for-historyresearch

# 创建虚拟环境（推荐）
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS

# 安装Python依赖
pip install -r requirements.txt
```

### 第二步：配置API密钥

创建 `.env` 文件，添加你的API密钥：

```env
# 至少配置一个LLM服务商即可！

# 方案A：阿里云通义千问（推荐，国内直连）
DASHSCOPE_API_KEY=sk-your-key-here

# 方案B：OpenAI（需要代理）
OPENAI_API_KEY=sk-your-key-here

# 方案C：智谱AI
ZHIPU_API_KEY=your-key-here
```

### 第三步：安装Tesseract OCR（可选）

如需本地OCR识别，下载并安装 [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)，安装时勾选中文、日文语言包。

### 第四步：启动服务

```bash
python app.py
```

访问 http://localhost:5000 开始使用！

---

## 💡 快速示例

### 示例1：一键润色论文

```python
from modules.llm_client import LLMClient

client = LLMClient({'provider': 'dashscope', 'api_key': 'your-key'})

# 润色日文学术论文
result = client.academic_polish(
    "伊藤博文氏ハ明治維新ノ前後ニ於テ...", 
    language='ja'
)
print(result['content'])
```

### 示例2：OCR识别日文PDF

```python
from modules.ocr_processor import OCRProcessor

processor = OCRProcessor(tesseract_path='C:\\Program Files\\Tesseract-OCR\\tesseract.exe')

# 识别日文图片
result = processor.extract_text_from_image('page1.png', language='ja')
print(result['text'])
```

### 示例3：生成学术笔记

```python
from modules.academic_note_generator import AcademicNoteGenerator

generator = AcademicNoteGenerator(api_provider='qwen')
note = generator.generate(paper_text, metadata={'title': '伊藤博文研究'})
print(note)
```

### 示例4：识别历史实体

```python
from modules.ner_processor import NERProcessor

processor = NERProcessor(api_provider='qwen')
entities = processor.recognize_historical_entities(
    "1868年，伊藤博文在东京建立了新政府。",
    categories=['person', 'event', 'date']
)
print(entities)
```

### 示例5：使用学习模块优化NER功能

```python
from learning_module import LearningModule

learner = LearningModule(api_provider='qwen')
result = learner.analyze_and_suggest(
    module_name='ner_processor',
    context='日文史料历史实体识别',
    research_topic='Japanese historical NER'
)

# 获取改进建议
for suggestion in result['improvement_suggestions']['short_term_improvements']:
    print(f"- {suggestion}")
```

### 示例6：文风分析与迁移

```python
from modules.style_transfer import StyleTransfer

transfer = StyleTransfer(api_provider='qwen')

# 分析文风矩阵
matrix = transfer.analyze_style_matrix("待分析的学术文本...")
print(f"句法结构: {matrix['syntax_structure']}")
print(f"词汇深度: {matrix['vocabulary_depth']}")

# 文风迁移
result = transfer.transfer_style_with_matrix(
    text="待迁移文本",
    target_matrix=target_style_matrix
)
```

### 示例7：虚拟人格对话

```python
from modules.virtual_persona_chatbot import VirtualPersonaChatbot

chatbot = VirtualPersonaChatbot(persona='fukuzawa')

# 学术咨询
response = chatbot.consult("关于明治维新的历史意义...")

# 历史事件评论
comment = chatbot.comment_on_history("大政奉还", "1867年")
```

### 示例8：引文网络分析

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

### 示例9：统一OCR处理

```python
from modules.unified_ocr_processor import UnifiedOCRProcessor

processor = UnifiedOCRProcessor()

# 使用NDL OCR（近代现代文献）
result = processor.process_image('page.png', model_type='ndlocr_lite')

# 使用NDL古典籍OCR（古典草书字文献）
result = processor.process_image('koten.png', model_type='ndlkotenocr_lite')
```

---

## 📚 学习模块

学习模块是项目的智能学习与研究辅助组件，为其他模块提供自动化的功能优化能力。

### 核心功能

| 功能 | 说明 |
|------|------|
| 学术资源检索 | 自动检索技术领域的最新研究成果 |
| 文献分析 | 深入分析文献核心内容和技术要点 |
| 改进建议生成 | 基于研究成果生成针对性优化建议 |

### 使用场景

- **NER模块优化**：获取日文历史实体识别的最新技术建议
- **提示词优化**：自动分析和优化模块提示词
- **测试用例生成**：为模块生成全面的测试用例

详细使用说明请参考 [learning_module/README.md](learning_module/README.md)。

---

## � 开源模块搜索器

开源模块搜索器（OpenSourceFinder）用于在GitHub和HuggingFace上搜索相关的开源模块，评估其质量和适用性。

### 核心功能

| 功能 | 说明 |
|------|------|
| GitHub仓库搜索 | 搜索并评估GitHub仓库质量 |
| HuggingFace模型搜索 | 搜索并评估HuggingFace模型 |
| 质量评分算法 | 基于Stars/Forks/Downloads等指标评分 |
| 整合报告生成 | LLM辅助生成优化整合建议 |

### 使用示例

```python
from open_source_finder import OpenSourceFinder

finder = OpenSourceFinder(api_provider='qwen')
result = finder.search_all(
    module_name='ocr_processor',
    context='日文OCR识别',
    keywords=['japanese ocr', 'ndl ocr']
)

# 获取整合报告
report = finder.generate_integration_report(result)
print(report.summary)
```

详细使用说明请参考 [open_source_finder/README.md](open_source_finder/README.md)。

---

## �� 项目结构

```
AItools-for-historyresearch/
├── app/                          # Flask应用
├── modules/                      # 核心功能模块
│   ├── llm_client.py            # LLM客户端（多服务商支持）
│   ├── doc_processor.py         # Word文档处理
│   ├── pdf_processor.py         # PDF处理
│   ├── ocr_processor.py         # OCR识别（Tesseract）
│   ├── unified_ocr_processor.py # 统一OCR处理器（NDL系列）
│   ├── ndl_ocr_batch_processor.py   # NDL OCR批量处理
│   ├── ndl_ocr_monitor.py       # NDL OCR心跳监控
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
│   ├── api_config.json          # API配置
│   ├── api_config_loader.py     # 配置加载器
│   ├── api_key_manager.py       # API密钥管理
│   └── config_helpers.py        # 配置辅助工具
├── data/                         # 数据目录
│   ├── dictionaries/            # 词典数据
│   │   ├── historical_entities.json  # 历史实体词典
│   │   └── historical_entities_manager.py
│   ├── input/                   # 输入数据
│   └── output/                  # 输出数据
├── external/                     # 外部工具
│   └── ndlkotenocr-lite/        # NDL古典籍OCR模型
├── docs/                         # 文档目录
└── archive/                      # 归档目录
```

---

## 🔧 支持的LLM服务商

| 服务商 | 特点 | 推荐场景 |
|--------|------|----------|
| 阿里云通义千问 | 国内直连，速度快 | **首选** |
| OpenAI GPT-4 | 效果最好 | 有代理环境 |
| 智谱AI | 国内可用 | 备选方案 |
| DeepSeek | 性价比高 | 成本敏感 |
| Ollama | 本地部署 | 离线使用 |

---

## ❓ 常见问题

### Q: API调用失败怎么办？
**A:** 检查API密钥是否正确配置，确认网络连接，或查看详细错误日志。

### Q: 日文OCR识别不准？
**A:** 尝试使用LLM辅助OCR（`method='llm'`），或提高PDF分辨率（DPI=400）。

### Q: 如何切换LLM服务商？
**A:** 修改 `.env` 中的 `LLM_PROVIDER` 或在代码中指定 `provider` 参数。

---

## � 更多资源

- 📘 **详细技术文档**：[COMPREHENSIVE_TECHNICAL_GUIDE.md](COMPREHENSIVE_TECHNICAL_GUIDE.md)
- 🗺️ **工作流程图**：[WORKFLOW_DIAGRAM.md](WORKFLOW_DIAGRAM.md)
- 🔍 **API使用文档**：启动服务后访问 http://localhost:5000

---

## 🤝 一起完善

欢迎提交Issue和Pull Request！

---

**版本**：1.1.0  
**更新日期**：2026年3月29日
