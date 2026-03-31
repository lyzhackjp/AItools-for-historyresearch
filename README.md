# 历史研究AI辅助工具

## 文档信息

| 属性 | 内容 |
|------|------|
| 版本 | 2.0.0 |
| 更新日期 | 2026年3月31日 |
| 技术文档 | [COMPREHENSIVE_TECHNICAL_GUIDE.md](COMPREHENSIVE_TECHNICAL_GUIDE.md) |
| 工作流程图 | [WORKFLOW_DIAGRAM.md](WORKFLOW_DIAGRAM.md) |

---

## 这是什么？

一个专为**日本史研究人员**打造的AI工具箱，帮助你处理日文史料、润色学术论文、管理研究文献。

### 你是否为这些问题困扰？

- 日文PDF文献识别困难？
- 学术论文润色耗时费力？
- 历史人名、地名难以整理？
- 参考文献格式不统一？

**这款工具正是为你设计的！**

---

## 适用人群

| 群体 | 使用场景 |
|------|----------|
| 日本史研究生 | 撰写课程论文、毕业论文 |
| 专职研究员 | 处理大量日文史料 |
| 学术编辑 | 润色审阅学术稿件 |
| 档案管理人员 | 数字化历史文档 |

---

## 核心功能

### 1. 学术论文润色
自动修正语法错误，提升学术表达规范度，保留历史专有名词。支持多种润色策略（段落/逐句/修订模式），采用Word原生修订追踪技术。

### 2. PDF文献OCR识别
将扫描版日文PDF转换为可编辑文本，支持JSON/CSV/TXT导出。支持多种OCR引擎：
- **Tesseract OCR**：本地运行，支持中/日/英/韩多语言
- **NDL OCR-Lite**：近代现代日本印刷体文献（需单独下载模型）
- **NDL古典籍OCR-Lite**：古典草书字文献（需单独下载模型）
- **通义千问VL OCR**：高精度文档识别，支持水印去除、页码识别

### 3. 历史实体识别
自动识别人名、地名、事件、机构等历史专有名词，支持同形异义词消歧（如"江戸"、"薩摩"等）。

### 4. 学术笔记生成
生成符合Obsidian格式的阅读笔记，自动构建知识图谱，支持双向链接。

### 5. 引用格式规范化
统一参考文献格式（支持Chicago、APA、GB/T 7714、MLA、IEEE、Harvard等）。

### 6. 文风分析与迁移
四维度文风矩阵分析（句法结构、词汇深度、语气叙事、学术修辞），支持少样本文风模仿。

### 7. 虚拟人格对话系统
预设历史人物人格（福泽谕吉、丸山真男、涩泽荣一），支持学术咨询和历史事件评论。

### 8. 引文网络分析
构建引文网络图谱，分析理论演进脉络，识别学术流派及其分支。

### 9. 史料发言识别与年代提取
从OCR处理后的史料文本中识别发言内容、提取年代信息，支持年号转换和出版年代推断。

### 10. NDL文献检索与下载
日本国立国会图书馆（NDL）文献搜索与PDF下载，支持SRU API和Selenium浏览器两种方式。

### 11. 学习模块
自动检索学术资源、分析文献、生成模块改进建议。

### 12. 开源模块搜索器
在GitHub和HuggingFace上搜索相关开源模块，评估质量和适用性。

---

## 重要说明：NDL OCR模型

### 模型获取方式

本工作区中的NDL OCR相关模块（`ndlocr_lite.py`、`ndlkotenocr_lite.py`、`unified_ocr_processor.py`）**仅提供接口脚本**，实际使用需要单独下载对应的模型文件：

| 模型 | 用途 | 下载地址 |
|------|------|----------|
| NDL OCR-Lite | 近代现代文献 | https://github.com/ndl-lab/ndlocr-lite |
| NDL古典籍OCR-Lite | 古典籍文献 | https://github.com/ndl-lab/ndlkotenocr-lite |

### 安装步骤

```bash
# 1. 创建外部目录
mkdir external
cd external

# 2. 克隆NDL OCR仓库
git clone https://github.com/ndl-lab/ndlocr-lite.git
git clone https://github.com/ndl-lab/ndlkotenocr-lite.git

# 3. 下载模型文件（从GitHub Release页面下载）
# 放置到对应目录：
# external/ndlocr-lite/src/model/
# external/ndlkotenocr-lite/src/model/

# 4. 安装依赖
cd ndlocr-lite && pip install -r requirements.txt
cd ../ndlkotenocr-lite && pip install -r requirements.txt
```

### 验证安装

```python
from modules.ndlocr_lite import NDLOCRInterface

interface = NDLOCRInterface()
validation = interface.validate_setup()
print(f"NDL OCR可用: {validation['all_valid']}")
```

详细配置请参考 [NDLoCR接入指南](docs/ndlocr_integration_guide.md)。

---

## 快速开始

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

### 第四步：下载NDL OCR模型（可选）

如需使用NDL OCR功能，请按照上方"重要说明：NDL OCR模型"章节的步骤操作。

### 第五步：启动服务

```bash
python app.py
```

访问 http://localhost:5000 开始使用！

---

## 快速示例

### 示例1：一键润色论文

```python
from modules.llm_client import LLMClient

client = LLMClient({'provider': 'dashscope', 'api_key': 'your-key'})

result = client.academic_polish(
    "伊藤博文氏ハ明治維新ノ前後ニ於テ...", 
    language='ja'
)
print(result['content'])
```

### 示例2：OCR识别日文PDF（通义千问VL）

```python
from modules.llm_ocr_processor import QwenVLOCRProcessor

processor = QwenVLOCRProcessor(api_key='your-dashscope-key')

results = processor.process_pdf(
    pdf_path='input.pdf',
    start_page=1,
    end_page=20,
    language='ja'
)

print(f"处理页数: {len(results)}")
```

### 示例3：使用NDL OCR（需先下载模型）

```python
from modules.unified_ocr_processor import UnifiedOCRProcessor

processor = UnifiedOCRProcessor()

# 检查模型可用性
models = processor.get_available_models()
for model in models:
    print(f"{model['type']}: 可用={model['available']}")

# 使用NDL古典籍OCR
result = processor.process_image('koten.png', model_type='ndlkotenocr_lite')
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

### 示例5：史料发言识别与年代提取

```python
from modules.historical_speech_extractor import create_speech_extractor

extractor = create_speech_extractor(api_provider='qwen')

# 加载OCR结果
ocr_data = extractor.load_ocr_result("ocr_result.json")

# 处理数据
records = extractor.process_ocr_result(ocr_data)

# 导出结果
extractor.export_results(records, "output.json", format='json')
```

### 示例6：NDL文献检索

```python
from ndl_search.core import NDLSearcher

searcher = NDLSearcher(output_dir='./downloads')

result = searcher.search_and_download(
    keyword='井上哲次郎 倫理新説',
    max_attempts=5
)

if result.status == 'success':
    print(f'下载成功: {result.file_path}')
```

---

## 项目结构

```
AItools-for-historyresearch/
├── app/                          # Flask应用
│   ├── app.py                    # Flask应用入口
│   └── config.py                 # 应用配置
├── modules/                      # 核心功能模块
│   ├── llm_client.py            # LLM客户端（多服务商支持）
│   ├── doc_processor.py         # Word文档处理
│   ├── pdf_processor.py         # PDF处理
│   ├── ocr_processor.py         # OCR识别（Tesseract）
│   ├── llm_ocr_processor.py     # LLM OCR处理器（通义千问VL）
│   ├── unified_ocr_processor.py # 统一OCR处理器（NDL系列）
│   ├── ndl_ocr_batch_processor.py   # NDL OCR批量处理
│   ├── ndl_ocr_monitor.py       # NDL OCR心跳监控
│   ├── ndlocr_lite.py           # NDL OCR-Lite接口
│   ├── ndlkotenocr_lite.py      # NDL古典籍OCR-Lite接口
│   ├── ner_processor.py         # 命名实体识别
│   ├── ner_disambiguation.py    # 实体消歧
│   ├── historical_speech_extractor.py  # 史料发言识别
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
│   │   └── improvement_generator.py # 改进建议生成
│   └── README.md
├── open_source_finder/           # 开源模块搜索器
│   ├── src/
│   │   └── open_source_finder.py  # GitHub/HF搜索
│   └── README.md
├── ndl-search/                   # NDL搜索模块
│   ├── core/
│   │   └── dl_searcher.py       # NDL搜索器核心
│   ├── config/
│   │   └── settings.py          # NDL配置管理
│   └── docs/
│       └── README.md
├── config/                       # 配置目录
│   ├── api_config.json          # API配置
│   ├── api_config_loader.py     # 配置加载器
│   ├── api_key_manager.py       # API密钥管理
│   └── ndlocr_interface_config.json  # NDLoCR接口配置
├── data/                         # 数据目录
│   └── dictionaries/
│       ├── historical_entities.json  # 历史实体词典
│       └── historical_entities_manager.py
├── external/                     # 外部工具（需单独下载）
│   ├── ndlocr-lite/             # NDL OCR-Lite模型
│   └── ndlkotenocr-lite/        # NDL古典籍OCR-Lite模型
├── docs/                         # 文档目录
│   ├── guides/                  # 使用指南
│   ├── integration/             # 集成文档
│   └── ndlocr_integration_guide.md  # NDLoCR接入指南
├── log/                          # 日志目录
├── tests/                        # 测试目录
├── tools/                        # 工具脚本
│   ├── batch_processing/        # 批量处理工具
│   ├── debug/                   # 调试工具
│   └── ndl_downloader/          # NDL下载工具
├── COMPREHENSIVE_TECHNICAL_GUIDE.md  # 详尽技术指南
├── WORKFLOW_DIAGRAM.md           # 工作流程图
└── requirements.txt              # Python依赖
```

---

## 支持的LLM服务商

| 服务商 | 特点 | 推荐场景 |
|--------|------|----------|
| 阿里云通义千问 | 国内直连，速度快 | **首选** |
| OpenAI GPT-4 | 效果最好 | 有代理环境 |
| 智谱AI | 国内可用 | 备选方案 |
| DeepSeek | 性价比高 | 成本敏感 |
| Ollama | 本地部署 | 离线使用 |

---

## 局限性与已知问题

### 重要限制

#### 1. NDL OCR模型不包含在工作区内

本工作区中与NDL OCR相关的模块（`ndlocr_lite.py`、`ndlkotenocr_lite.py`、`unified_ocr_processor.py`）**仅提供接口脚本和调用逻辑**，实际的OCR模型文件需要用户自行从官方仓库下载：

- **NDL OCR-Lite**: https://github.com/ndl-lab/ndlocr-lite
- **NDL古典籍OCR-Lite**: https://github.com/ndl-lab/ndlkotenocr-lite

模型文件较大（约数百MB），且可能涉及许可限制，因此未包含在本工作区中。

#### 2. API密钥需自行申请

本工具依赖大语言模型API，用户需要自行申请API密钥：
- 阿里云通义千问：https://dashscope.console.aliyun.com/
- OpenAI：https://platform.openai.com/
- 智谱AI：https://open.bigmodel.cn/

#### 3. 网络环境要求

- 使用OpenAI API需要稳定的国际网络连接
- 使用通义千问等国内API需要国内网络环境
- NDL文献下载需要能够访问日本国立国会图书馆网站

### 已知问题

#### 1. OCR识别精度

- **Tesseract OCR**：对日文古籍、手写体识别效果有限
- **NDL OCR-Lite**：仅适用于近代现代印刷体，对古典籍效果不佳
- **NDL古典籍OCR-Lite**：比NDL古典籍OCR ver.3精度稍低约2%
- **通义千问VL OCR**：对复杂版面、多栏排版可能识别不准确

#### 2. 历史实体识别

- 实体词典覆盖范围有限，可能遗漏部分历史人物和地名
- 同形异义词消歧依赖上下文关键词匹配，可能存在误判
- 年号转换仅支持主要日本年号，部分冷门年号可能无法识别

#### 3. 论文润色

- 润色结果依赖LLM输出质量，可能存在过度修改或遗漏问题
- 脚注引用保护机制在复杂文档结构中可能失效
- 修订追踪功能仅在Microsoft Word中完全支持

#### 4. NDL文献下载

- 部分文献可能因版权限制无法下载
- Selenium下载方式依赖浏览器环境，可能因网站更新而失效
- 下载速度受网络环境影响较大

#### 5. 虚拟人格对话

- 人格设定基于历史文献和研究成果，可能存在主观解读
- 对话内容仅供参考，不构成学术结论

### 性能限制

| 功能 | 限制说明 |
|------|----------|
| PDF OCR处理 | 大文件（>100页）处理时间较长，建议分批处理 |
| LLM API调用 | 受API速率限制，批量处理时需注意配额 |
| NDL文献下载 | 单次下载建议不超过10个文件，避免触发反爬机制 |
| 嵌入向量构建 | 大规模文档集合（>10000篇）需要较长索引时间 |

### 兼容性说明

| 环境 | 支持情况 |
|------|----------|
| Windows 10+ | 完全支持（主要开发环境） |
| macOS | 基本支持，部分路径配置需调整 |
| Linux | 基本支持，需安装系统依赖 |
| Python 3.8 | 最低版本 |
| Python 3.11+ | 推荐版本 |

---

## 常见问题

### Q: API调用失败怎么办？
**A:** 检查API密钥是否正确配置，确认网络连接，或查看详细错误日志。

### Q: 日文OCR识别不准？
**A:** 
- 近代现代文献：推荐使用NDL OCR-Lite或通义千问VL OCR
- 古典籍文献：推荐使用NDL古典籍OCR-Lite
- 通用场景：可尝试LLM辅助OCR校正

### Q: NDL OCR模型如何下载？
**A:** 请参考上方"重要说明：NDL OCR模型"章节，从GitHub Release页面下载模型文件。

### Q: 如何切换LLM服务商？
**A:** 修改 `.env` 中的 `LLM_PROVIDER` 或在代码中指定 `provider` 参数。

### Q: 脚注引用在润色后丢失？
**A:** 确保使用 `paper_polisher_enhanced.py` 或启用修订追踪模式，该版本包含脚注引用保护机制。

---

## 更多资源

- **详尽技术指南**：[COMPREHENSIVE_TECHNICAL_GUIDE.md](COMPREHENSIVE_TECHNICAL_GUIDE.md)
- **工作流程图**：[WORKFLOW_DIAGRAM.md](WORKFLOW_DIAGRAM.md)
- **NDLoCR接入指南**：[docs/ndlocr_integration_guide.md](docs/ndlocr_integration_guide.md)
- **学习模块文档**：[learning_module/README.md](learning_module/README.md)
- **开源搜索器文档**：[open_source_finder/README.md](open_source_finder/README.md)
- **NDL搜索模块文档**：[ndl-search/docs/README.md](ndl-search/docs/README.md)

---

## 一起完善

欢迎提交Issue和Pull Request！

### 贡献指南

1. Fork本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

### 代码规范

- 遵循PEP 8 Python代码风格
- 添加必要的注释和文档字符串
- 编写单元测试覆盖新功能
- 更新相关文档

---

## 许可证

本项目仅供学术研究使用。使用NDL OCR模型时，请遵守日本国立国会图书馆的使用条款。

---

## 致谢

- [NDL OCR-Lite](https://github.com/ndl-lab/ndlocr-lite) - 日本国立国会图书馆
- [NDL古典籍OCR-Lite](https://github.com/ndl-lab/ndlkotenocr-lite) - 日本国立国会图书馆
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) - Google
- 阿里云通义千问、OpenAI、智谱AI等LLM服务商
