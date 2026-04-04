# 历史研究论文全流程工作流模块 — 设计规划

> 版本：v0.2 | 日期：2026-04-04 | 状态：**Phase 1~4 全部完成**

---

## 一、背景与目标

### 现有能力盘点

| 阶段 | 已有模块 | 功能 |
|------|----------|------|
| **搜集材料** | `HistoryFieldExplorer`, `PaperFinder` | 学术论文/文献搜索 |
| | `CrossRefAdapter`（新增） | CrossRef API 学术期刊搜索 |
| | `ndl_ocr_batch_processor` | NDL 图书馆批量 OCR |
| **整理史料** | `BookCitationOrganizer` | 扫描书元数据提取 + 引用格式生成 |
| | `CitationFormatter` | Chicago/APA/GB7714/MLA 引用格式 |
| | `AcademicNoteGenerator` | 从文献生成 Obsidian 格式结构化笔记 |
| **提取信息** | `NERProcessor` (+ `_integrated`, `_optimized`) | 历史专有名词识别 |
| | `UnifiedOCRProcessor` | 多引擎 OCR（Qwen VL / ndlocr-lite / Tesseract）|
| | `NERDisambiguation` | 实体消歧 |
| **史料考察** | `CitationNetworkAnalyzer` | 引文网络分析（谁是核心文献/孤证）|
| | `ReverseOutlineAnalyzer` | 论文逻辑链逆向审视 |
| **撰写论文** | `HistoryFieldExplorer.draft_paper()` | 生成研究论文（含双语）|
| | `AcademicSummarizer` | 学术文献摘要生成 |
| **论文修改** | `PaperPolisher` (含 `_enhanced`, `_optimized`) | 冗余内容精简、Track Changes |
| | `StyleTransfer` | 文风分析与迁移（少样本模仿）|
| **注释格式** | `CitationFormatter` | 多种引用格式输出 |
| | `CitationNormalizer` | 引用格式标准化 |

### 缺失能力（待新增）

- **阶段间数据传递**：各模块输出格式不统一，难以直接对接
- **工作流编排层**：`unified_task_executor.py` 是单任务执行器，缺多步骤串联能力
- **史料验证层**：无专门的历史事实核查（fact-checking）模块
- **论文校对层**：无拼写/语法校对模块

---

## 二、工作流总体设计

### 2.1 七阶段流水线

```
[Stage 1] 搜集材料
    输入：研究主题关键词
    输出：文献列表（标题/作者/年份/摘要/URL）
         ↓
[Stage 2] 整理史料
    输入：文献列表 + （可选）扫描书/PDF
    输出：结构化元数据CSV、Obsidian格式笔记、引用格式化数据
         ↓
[Stage 3] 提取信息
    输入：史料原文（PDF/扫描件/文本）
    输出：实体列表（人名/地名/事件/概念）、关系图谱
         ↓
[Stage 4] 史料考察
    输入：实体列表 + 文献引用关系
    输出：引文网络图、关键文献标注、可信度评估
         ↓
[Stage 5] 撰写论文
    输入：实体 + 笔记 + 文献元数据
    输出：论文草稿（中英双语，含章节结构）
         ↓
[Stage 6] 论文修改润色
    输入：论文草稿
    输出：精简版（去冗余）、文风调整版、逻辑审视报告
         ↓
[Stage 7] 注释格式修改
    输入：含注释的论文草稿 + 目标格式（Chicago/APA/GB7714）
    输出：格式规范化的最终论文
```

### 2.2 双语处理规则

- **主要语言** = 研究对象国/主要研究者语言（英文研究→English；日文研究→日本語）
- **辅助语言** = 学术级中文翻译（`bilingual=True` 时，每段附中文翻译）
- 实现：`HistoryFieldExplorer.draft_paper(bilingual=True)` → 每段自动附中译

---

## 三、核心数据结构设计

### 3.1 研究项目（ResearchProject）

```python
@dataclass
class ResearchProject:
    """一个研究项目的完整生命周期数据"""
    id: str                           # UUID
    topic: str                        # 研究主题
    language: str                     # 主要语言 (en/ja/zh)
    bilingual: bool                  # 是否生成双语

    # Stage 1 产出
    literature: List[PaperRecord]    # 搜集到的文献

    # Stage 2 产出
    book_metadata: List[BookMetadata]    # 图书元数据
    notes: List[ObsidianNote]             # Obsidian格式笔记
    citations: List[Citation]              # 格式化引用

    # Stage 3 产出
    entities: List[HistoricalEntity]  # 识别的历史实体
    entity_relations: List[Relation]  # 实体关系

    # Stage 4 产出
    citation_network: CitationNetwork # 引文网络
    key_sources: List[str]           # 关键文献ID列表

    # Stage 5 产出
    paper_draft: str                  # 论文草稿（Markdown）

    # Stage 6 产出
    polished_draft: str              # 精简后草稿
    style_transfered: str            # 文风调整版
    outline_review: OutlineReview    # 逻辑审视报告

    # Stage 7 产出
    final_paper: str                 # 最终论文
    citation_format: str             # 目标引用格式

    metadata: Dict[str, Any]         # 杂项元数据
```

### 3.2 各阶段输入/输出（I/O）规范

| 阶段 | 输入类型 | 输出类型 |
|------|----------|----------|
| Stage 1 | `str`（关键词）| `List[PaperRecord]` |
| Stage 2 | `List[PaperRecord]` + `List[BookFile]` | `List[ObsidianNote]` + `List[Citation]` |
| Stage 3 | `List[Document]`（PDF/文本）| `List[HistoricalEntity]` |
| Stage 4 | `List[HistoricalEntity]` + `List[Citation]` | `CitationNetwork` |
| Stage 5 | `ResearchProject` | `str`（论文草稿）|
| Stage 6 | `str`（草稿）| `str`（精简/润色版）|
| Stage 7 | `str` + `str`（目标格式）| `str`（格式化终稿）|

---

## 四、新增模块：WorkflowOrchestrator

### 4.1 定位

```
WorkflowOrchestrator
├── 基于现有 unified_task_executor.py（任务执行）
├── 基于现有 module_adapters.py（模块适配）
└── 新增：StageOrchestrator（阶段编排器）
```

### 4.2 核心接口

```python
class WorkflowOrchestrator:
    """
    历史研究论文全流程工作流编排器

    使用方法：
        from tools.workflow.workflow_orchestrator import WorkflowOrchestrator

        wf = WorkflowOrchestrator(
            topic="Tudor England",
            language="en",
            bilingual=True
        )

        # 全自动模式
        result = wf.run_all()

        # 单阶段执行
        wf.run_stage(1)   # 搜集材料
        wf.run_stage(2)   # 整理史料
        wf.run_stage(3)   # 提取信息
        ...
    """

    STAGES = [
        "collect",    # Stage 1: 搜集材料
        "organize",   # Stage 2: 整理史料
        "extract",    # Stage 3: 提取信息
        "examine",    # Stage 4: 史料考察
        "write",      # Stage 5: 撰写论文
        "polish",     # Stage 6: 论文修改润色
        "format",     # Stage 7: 注释格式修改
    ]

    def __init__(
        self,
        topic: str,
        language: str = "en",
        bilingual: bool = True,
        citation_format: str = "chicago",
        output_dir: str = "./output",
    ):
        ...

    def run_all(self) -> ResearchProject:
        """全自动执行所有阶段"""
        ...

    def run_stage(self, stage: int, **kwargs) -> Any:
        """执行单个阶段"""
        ...

    def get_output(self, stage: int) -> Any:
        """获取指定阶段的产出"""
        ...

    def export(self, format: str = "markdown") -> str:
        """导出最终论文（markdown / docx / pdf）"""
        ...
```

### 4.3 各阶段实现方案

#### Stage 1：搜集材料（collect）
- **模块**：`HistoryFieldExplorer`
- **调用**：`explore(topic, search_limit=60)`
- **配置**：`sources=['arxiv', 'paperswithcode', 'crossref']`（英语）
- **输出**：`report.literature`（论文列表）

#### Stage 2：整理史料（organize）
- **模块**：`AcademicNoteGenerator` → 从论文摘要生成 Obsidian 笔记
- **模块**：`BookCitationOrganizer` → 扫描书元数据提取
- **模块**：`CitationFormatter` → 引用格式化
- **输出**：`notes[]`, `citations[]`

#### Stage 3：提取信息（extract）
- **模块**：`NERProcessor`（日文）/ 英文 NER 旁路 + LLM
- **模块**：`UnifiedOCRProcessor`（扫描史料数字化）
- **输出**：`entities[]`, `entity_relations[]`

#### Stage 4：史料考察（examine）
- **模块**：`CitationNetworkAnalyzer` → 构建引文网络，识别核心文献
- **模块**：`ReverseOutlineAnalyzer` → 论文逻辑审视
- **输出**：`citation_network`, `key_sources[]`

#### Stage 5：撰写论文（write）
- **模块**：`HistoryFieldExplorer.draft_paper()`
- **配置**：`language=en, bilingual=True`
- **输出**：`paper_draft`（中英双语 Markdown）

#### Stage 6：论文修改润色（polish）
- **模块**：`PaperPolisher` → 冗余内容精简 + Track Changes
- **模块**：`StyleTransfer` → 目标文风迁移（可选）
- **模块**：`ReverseOutlineAnalyzer` → 逻辑审视报告
- **输出**：`polished_draft`, `outline_review`

#### Stage 7：注释格式修改（format）
- **模块**：`CitationFormatter` → 目标格式（Chicago/APA/GB7714/MLA）
- **模块**：`CitationNormalizer` → 引用标准化
- **输出**：`final_paper`

---

## 五、文件结构设计

```
tools/
└── workflow/
    ├── __init__.py
    ├── workflow_orchestrator.py   # 主编排器
    ├── research_project.py        # ResearchProject 数据类
    ├── stages/
    │   ├── __init__.py
    │   ├── stage1_collect.py      # 搜集材料
    │   ├── stage2_organize.py    # 整理史料
    │   ├── stage3_extract.py     # 提取信息
    │   ├── stage4_examine.py     # 史料考察
    │   ├── stage5_write.py       # 撰写论文
    │   ├── stage6_polish.py      # 论文修改润色
    │   └── stage7_format.py       # 注释格式修改
    └── adapters/
        ├── __init__.py
        └── workflow_adapter.py   # UnifiedTaskExecutor 适配
```

---

## 六、实现优先级

### Phase 1 ✅ 完成（2026-04-03）
- [x] `research_project.py` — 统一数据结构
- [x] `WorkflowOrchestrator` 骨架
- [x] Stage 1 + Stage 5 打通（搜集→论文草稿）
- [x] `HistoryFieldExplorer` 整合

### Phase 2 ✅ 完成（2026-04-04）
- [x] Stage 2（笔记生成 + 引用格式化）
- [x] Stage 3（NER + OCR）
- [x] Stage 4（引文网络 + 逻辑审视）

### Phase 3 ✅ 完成（2026-04-04）
- [x] Stage 6（润色 + 文风调整）
- [x] Stage 7（引用格式转换 + Word 导出）
- [x] Word 导出（`python-docx` + 脚注支持）

### Phase 4 ✅ 完成（2026-04-04）
- [x] Web UI（`app.py` 集成工作流 API）
- [x] 断点续做（`ResearchProject.save/load`）
- [x] Flask REST API 端点

---

### 已知问题 / 待优化（2026-04-04）

| 问题 | 原因 | 状态 |
|------|------|------|
| Stage 3 实体检索 0 | 文献摘要为空（PaperFinder fallback 数据缺陷）；LLM 提取逻辑需加强 | 待修复 |
| Stage 6 文风迁移失败 | `ReverseOutlineAnalyzer._call_llm` 使用 `.chat()` 接口与 `LLMClient._call_llm()` 不匹配 | ✅ 已修复（commit 4a44be6） |
| Obsidian Vault 链接提取失败 | `ObsidianIntegration` 返回非预期数据结构的兜底处理 | ✅ 已修复（commit 4a44be6） |
| EmbeddingManager 初始化阻塞 | `EmbeddingManager.__init__` 内部 import transformers 触发 HuggingFace 连接 | ✅ 已用 LLM 重排替代 |
| PapersWithCode 超时 | huggingface.co 网络不通（国内环境） | 已知局限，fallback 到 PaperFinder |

---

### Word 文档导出（含脚注）

**文件**：`tools/workflow/word_exporter.py`

**功能**：
- Markdown → Word 转换（标题、加粗、斜体、引用块、列表）
- 脚注引用 `[^n]` → Word 原生脚注
- 参考文献列表 → Word 脚注（学术规范）

**使用方式**：
```python
from tools.workflow.word_exporter import export_paper_to_word, export_paper_with_footnotes

# Markdown → Word
path = export_paper_to_word(
    paper_text,
    output_path="paper.docx",
    language="en",
    title="论文标题",
    citation_format="chicago"
)

# 带脚注的 Word
path = export_paper_with_footnotes(
    paper_text,
    footnotes=[{"id": "1", "text": "引用内容..."}, ...],
    output_path="paper_with_footnotes.docx"
)
```

**Stage 7 集成**：运行 Stage 7 后自动导出：
- `workflow_output/{topic}_{date}.docx`（Markdown 格式）
- `workflow_output/{topic}_{date}_footnotes.docx`（脚注格式）

---

## 七、关键设计决策

### 7.1 为什么需要 WorkflowOrchestrator 而不是直接用 unified_task_executor？

`unified_task_executor` 是**单任务**执行器（输入一段文本，输出一个结果）。
`WorkflowOrchestrator` 是**多阶段流水线**编排器：
- 管理跨阶段的**状态传递**（Stage 3 的实体 → Stage 5 的论文）
- 支持**条件分支**（如无扫描书则跳过 OCR）
- 支持**断点续做**（保存/加载 ResearchProject）

### 7.2 为什么不用 LangChain / AutoGen 等现成框架？

- 这是一个**领域专用**工具（日语/英语历史研究）
- 现有模块（NERProcessor, CitationFormatter 等）已深度适配历史研究场景
- 引入 LangChain 会增加不必要的复杂度

### 7.3 双语处理在哪里做？

**Stage 5（撰写论文）时由 `HistoryFieldExplorer.draft_paper(bilingual=True)` 统一处理**。
Stage 6 的润色只需处理主要语言版本，中文翻译保持不变。

### 7.4 引用格式转换的时机

在 **Stage 7** 一次性转换，避免 Stage 6 润色时引用格式不一致。

---

## 八、待解决问题

1. **Stage 3 NER 对英文支持弱** — 当前 `NERProcessor` 主要针对日语，需要为英语/汉语增加专用 NER
2. **引文网络分析** — `CitationNetworkAnalyzer` 尚未测试（无实际调用）
3. **OCR 引擎网络问题** — HuggingFace 超时，ndlocr-lite 需本地部署
4. **Word 导出** — `PaperPolisher` 使用 `python-docx`，但其他模块无 DocX 输出能力
