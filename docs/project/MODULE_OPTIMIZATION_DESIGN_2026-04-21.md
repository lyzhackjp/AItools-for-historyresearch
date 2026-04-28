# 模块级进一步优化设计方案
## 2026-04-25 继续推进记录 - TaskManager 统一任务注册层

- `task_manager.py`: 新增 `TaskRegistryEntry`、`get_task_registry()`、`get_preset_options()`、`get_history_summary()`、`get_capabilities()` 与 `execute_task_package()`，统一暴露任务、alias、adapter、preset、backend、隐私策略和 `task_execution` envelope。
- 后续 API 层、skill、MCP 和小模型 agent 应优先消费任务注册表，不再直接猜测 adapter 方法名或 hardcode backend 选项。
- 后续优化方向: 将 `UnifiedTaskExecutor` 的结果验证、artifact 写入协议和失败摘要进一步收束到同一 package schema，并让 workflow/research project 层自动登记 artifact 与 review 队列。

## 2026-04-25 继续推进记录 - UnifiedTaskExecutor validation/artifact 协议

- `unified_task_executor.py`: 新增 `TaskResult.to_package()`、`UnifiedTaskExecutor.execute_package()`、`write_execution_artifact()` 与通用输出验证摘要。
- 每次成功或失败执行都会在 metadata 中记录 `validation/confidence/needs_review/quality_flags`，便于 API、workflow、artifact manager 和 review queue 统一消费。
- artifact 写入保持显式路径触发，默认不落盘，并拒绝写入 `secrets/`；后续 `ResearchProject` 和 `workflow_orchestrator` 应接管正式 artifact 登记。

## 2026-04-25 继续推进记录 - module_adapters registry 薄封装

- `module_adapters.py`: 新增 `AdapterSpec`、`get_adapter_registry()`、`get_adapter_spec()`、`list_adapter_specs()` 与 `canonical_adapter_type()`。
- `BaseAdapter.get_capabilities()` 现在附带 adapter spec；新增通用 `BaseAdapter.execute_package()`，直接复用 `UnifiedTaskExecutor.execute_package()`。
- 后续 API、workflow 与 agent skill 应优先读取 adapter spec，避免继续 hardcode alias、主方法和输入契约。

## 2026-04-25 继续推进记录 - ResearchProject artifact/review/quality 统一挂载

- `research_project.py`: 新增 `register_package()`、`register_artifact()`、`add_quality_flags()`、`get_artifact_summary()` 与 `get_quality_summary()`。
- `add_artifact()` 和 `add_review_item()` 现在会补充 id/created_at/status，并将 artifact/review id 回写 stage metadata。
- 后续 workflow/orchestrator 应通过这些项目状态方法登记 package 摘要、checkpoint artifact 和人工复核队列，减少阶段内重复逻辑。

## 2026-04-25 继续推进记录 - WorkflowOrchestrator checkpoint/failure package

- `workflow_orchestrator.py`: 成功路径继续登记 checkpoint artifact；最终 checkpoint 也登记为项目 artifact。
- 阶段失败时新增 `workflow_stage_failure` package，统一挂载 failed checkpoint、`stageN_failed` quality flag、review queue item 与 `failure_package` metadata。
- 后续各阶段内部错误摘要可逐步改为 package-first 上报，由 orchestrator 统一收束。

## 2026-04-25 继续推进记录 - Stage3 统一任务层快照与 package 执行

- `stage3_extract.py`: 新增 `task_layer_snapshot`，记录 NER 任务 options、registry 摘要与 TaskManager 脱敏能力摘要。
- NER 调用优先使用 `TaskManager.execute_task_package()`，并将 `task_execution` 摘要写入 Stage 3 package summary；旧 `execute_task()` 保持 fallback。
- 后续 Stage 2/4/5/6/7 可按同一模式迁移到统一任务层能力快照和 package-first 执行。

## 2026-04-25 继续推进记录 - 配置与密钥 facade 脱敏状态统一

- `secure_api_key_manager.py`: `get_status_report()` 默认返回脱敏状态，`key_hash` 和真实 `secrets_path` 只有显式 `include_hashes/include_paths` 时才暴露。
- `config/api_key_manager.py`: legacy facade 新增 `get_status_report()` 与 `get_all_key_status()`，统一委托脱敏状态报告。
- 后续 API、workflow、agent skill 只能消费默认 redacted status，不得把 key hash 或真实 secrets 路径写入日志和报告。

## 2026-04-25 继续推进记录 - API lazy service/app factory

- `app/app.py`: `LazyService` 新增 name/description/status/initialized；集中维护 `LAZY_SERVICES`。
- 新增 `create_app(test_config=None)` 和 `get_service_status()`；新增 `/api/system/status`，用于轻量健康检查和服务初始化状态查询。
- 当前测试环境缺少 Flask 时，API factory 测试按可选依赖规则 skip；后续安装 Flask 后可直接验证端点不初始化重服务。

## 2026-04-25 继续推进记录 - integration/environment/artifact manager

- 新增 `modules/artifact_manager.py`，提供 managed-root artifact manifest 与显式 JSON 写入，拒绝 `secrets/` 和 root 外路径。
- `environment_checker.py` 新增 `get_capabilities()` 与 `build_environment_package()`，环境状态可作为 package 被 agent/workflow/artifact manager 消费。
- 后续 workflow checkpoint、环境检查、优化分支归档均应优先通过 ArtifactManager 或 ResearchProject 的登记协议收束。

## 2026-04-25 继续推进记录 - 优化分支归档 manifest

- 新增 `docs/project/OPTIMIZATION_BRANCH_ARCHIVE_2026-04-25.md` 与 `archive/2026-04-25/OPTIMIZATION_BRANCH_ARCHIVE_MANIFEST.md`。
- 已识别 `optimized/enhanced/integrated` 候选文件，并区分 active integration、documentation 与 branch-style code。
- 因 `paper_polisher_optimized.py` 仍被测试直接引用、`ner_processor_integrated.py` 仍动态连接 optimized NER，本轮执行 manifest 归档，不物理移动代码文件。

## 2026-04-25 继续推进记录 - Stage2 package 统一挂载

- `stage2_organize.py`: academic note package、Obsidian note export package 与 graph package 现在统一调用 `ResearchProject.register_package()`。
- Obsidian vault 目录 artifact 改为 `ResearchProject.register_artifact()`，保留原有 `execution_summary` 结构兼容。
- 后续 Stage 4/5/6/7 应继续按同一项目状态协议登记 package、artifact、quality flags 与 review queue。

## 2026-04-25 继续推进记录 - Stage4 citation/outline package 统一挂载

- `stage4_examine.py`: citation network package 现在通过 `ResearchProject.register_package()` 登记。
- outline review 结果新增 `outline_review` package 包装，并写入项目级 package/review 协议。
- 保留 Stage 4 原有 `execution_summary`，同时让 citation/outline 的 package 级复核项可被统一 review queue 消费。

## 2026-04-25 继续推进记录 - Stage5 draft package 统一挂载

- `stage5_write.py`: 当 explorer 返回 `field_draft` package 时，直接登记到 `ResearchProject.register_package()`。
- Stage 5 现在总会基于 execution_summary 生成 `paper_draft` package，并登记草稿长度、段落、标题、引用占位、来源计数与质量标记。
- 后续 Stage 6/7 应消费 Stage 5 的 `paper_draft` package 与 source snapshot，而不只读取 `project.paper_draft` 字符串。














## 2026-04-25 继续推进记录 - Obsidian vault 安全集成

- `obsidian_integration.py`: 已按最新锚点收口为本地 vault 集成层，新增 `get_capabilities()`、`create_note_package()`、`update_note_package()`、`build_knowledge_graph_package()` 与 `export_notes_to_json_package()`；旧接口继续保留，但读写路径统一通过 vault 边界校验，拒绝路径穿越与 vault 外绝对路径。
- `tools/workflow/stages/stage2_organize.py`: Stage 2 vault 导出已优先消费 `obsidian_note_export/obsidian_graph` package，并把 `confidence/needs_review/quality_flags/export_summary` 写回 `vault_export` 摘要与复核队列。
- 后续优化方向: 将其它文件系统型模块统一补充 managed-root/path-boundary 检查，避免导入导出能力绕过工作区隐私与归档规范。

## 2026-04-25 继续推进记录 - HistoricalSpeechExtractor Package 收口

- `historical_speech_extractor.py`: 已新增 `get_capabilities()`、`process_ocr_result_package()` 与 `analyze_text_package()`，把历史发言识别、日期解析和实体附着统一回收为 `historical_speech_analysis` envelope。
- 新接口记录 `backend/provider/model/confidence/needs_review/quality_flags/statistics/source_summary`，为 Stage 3 后续消费和 AI agent 小模型调用提供稳定契约。
- 后续优化方向: 在不改变 package 外部 schema 的前提下，继续拆分内部 `SpeechSegmenter`、`DateResolver`、`EntityAttach` 三个组件，并把真实规则命中率纳入质量统计。

## 2026-04-25 继续推进记录 - EmbeddingManager 轻量检索 Package

- `embedding_manager.py`: 已新增 `get_capabilities()`、`create_vector_index_package()` 与 `semantic_search_package()`，统一输出 `embedding_index/semantic_search` envelope。
- 默认 `auto_load_models=False`，建索引时使用确定性 mock embedding，避免小模型 agent 或无依赖环境调用时自动触发重模型加载、外网下载或 API 初始化。
- `numpy` 已改为可选依赖；无 `numpy` 环境下仍支持纯 Python mock 向量、余弦相似度、索引统计和语义检索 smoke。
- 后续优化方向: 将真实本地 embedding、远程 API embedding、Ollama embedding 收口为 provider registry，并把缓存键、模型维度和费用/隐私标记纳入统一 metadata。

## 2026-04-25 继续推进记录 - NERDisambiguation 后处理 Package

- `ner_disambiguation.py`: 已新增 `get_capabilities()`、`batch_disambiguate_package()`、`disambiguate_package()` 与 `resolve_relations_package()`，统一输出 `entity_disambiguation/entity_relation_resolution` envelope。
- Stage 3 已优先消费 `disambiguate_package()`，并把 `confidence/needs_review/quality_flags/summary` 写入 `execution_summary.disambiguation_packages`。
- 当前仍保持本地规则优先，先稳定规范名、类型变化、未知规则和低置信复核信号；后续可接入别名库、本地模型或 MCP 知识库，但外部调用方不需要改变 package schema。

## 2026-04-25 继续推进记录 - HistoryFieldExplorer 领域研究 Package

- `history_field_explorer.py`: 已新增 `explore_package()` 与 `draft_paper_package()`，统一输出 `field_research/field_draft` envelope。
- Stage 5 已优先消费 `field_draft` package，并将 `confidence/needs_review/quality_flags/export_summary` 写入 `execution_summary.draft_package`。
- 该步骤先稳定外部契约，后续可继续把内部搜索、综合、写作拆分为 `FieldSearch`、`FieldSynthesis`、`FieldDrafting`，并逐步吸收进统一研究助手内核。

## 2026-04-25 继续推进记录 - CitationFormatter 格式渲染 Package

- `citation_formats.py`: 已新增 `get_capabilities()`、`format_record_package()` 与 `format_batch_package()`，统一输出 `citation_formatting` envelope。
- Stage 7 已记录 `execution_summary.citation_format_package`，承载渲染数量、目标格式、缺失字段质量标记和格式层置信度。
- 格式层继续保持纯渲染职责，不承担 citation 解析、字段规范化或外部 API 调用；这些职责保留在 `citation_normalizer.py` 与上游数据结构中。

## 2026-04-25 继续推进记录 - HistoricalCitationVerifier 引文核验 Package

- `historical_citation_verifier.py`: 已新增 `get_capabilities()`、`parse_docx_package()` 与 `verify_docx_package()`，统一输出 `historical_citation_parse/historical_citation_verification` envelope。
- 新接口将 DOCX 脚注解析、候选构建、来源检索、下载/OCR/对齐执行元数据和 artifacts 包装为稳定 package，便于小模型 agent、skill 或 MCP 在不理解内部复杂流程的情况下调用。
- 默认解析接口保持纯本地离线；外部检索、受限下载和 OCR 必须由调用方显式开启，并通过 `quality_flags/needs_review` 回写 source mismatch、source not found、download failed 等复核信号。

## 2026-04-25 继续推进记录 - UniversalLayoutAnalyzer 最小版面 Package

- `universal_layout_analyzer.py`: 已新增 `get_capabilities()`、`analyze_page_package()` 与 `analyze_document_package()`，统一输出 `layout_page/layout_document` envelope。
- `fitz/numpy/PIL` 已改为可选依赖；metadata-only package 路径不加载 ONNX 模型或 PDF/图像重依赖，适合小模型 agent、skill、MCP 先做能力探测和页面级状态登记。
- 后续训练准备链路可按 `pdf_image_conversion -> layout_page -> ocr_result -> training_sample` 串联，真实模型分析再显式开启 `use_models=True` 并回收质量标记。

## 2026-04-25 继续推进记录 - PDFDateMatcher 训练样本 Package

- `pdf_date_matcher.py`: 已新增 `get_capabilities()`、`parse_annotation_dates_package()`、`match_dates_package()` 与 `generate_training_data_package()`，统一输出 `date_extraction/date_match_pairs/training_samples` envelope。
- 默认初始化不读取本地配置密钥文件；远程 Qwen-VL 日期识别必须由调用方显式传入 `api_key` 或启用 `auto_load_api_key=True`，以符合工作区隐私规范。
- 后续古典籍 OCR 训练准备链路可按 `pdf_image_conversion -> layout_page -> date_match_pairs -> training_samples` 串联，且把无日期、无匹配、未保存 artifact 等情况写入 `quality_flags`。

## 2026-04-25 继续推进记录 - ClassicalOCRTrainingWorkflow 训练总线 Package

- `classical_ocr_training_workflow.py`: 已新增 `get_capabilities()`、`build_summary_package()` 与 `build_training_samples_package()`，统一输出 `training_workflow_summary/training_samples` envelope。
- 该模块继续保留长流程兼容入口，但训练准备总线后续应优先协调 `layout_page/date_match_pairs/training_samples` package，不再把内部实验流程结果作为唯一状态来源。
- `fitz/numpy/PIL` 已改为可选导入；真实 PDF/图像处理缺依赖时返回结构化失败结果，能力探测和 package 包装不加载重模型。

## 2026-04-25 继续推进记录 - BiographyExtractor 人物传记 Package

- `biography_extractor.py`: 已新增 `get_capabilities()`、`extract_entities_package()` 与 `process_ocr_results_package()`，统一输出 `biography_entities/biography_batch` envelope。
- 默认初始化不再读取 `secrets/api_keys.txt`；PDF 转图、NDL OCR 与 Qwen-VL OCR 均改为延迟加载，适合小模型 agent、skill、MCP 先做能力探测和文本级结构化。
- 后续 `biographical_ner.py` 与 `biography_pipeline.py` 应逐步收束为该主模块的规则库/薄封装，人物结构化结果统一回收到 `persons/summary/confidence/needs_review/quality_flags`。

## 2026-04-25 继续推进记录 - BiographicalNER 离线规则库 Package

- `biographical_ner.py`: 已修复 `WorkExperience.position` 语法错误，并新增 `get_capabilities()`、`process_text_blocks_package()` 与 `extract_biographical_entities_package()`，统一输出 `biography_entities` envelope。
- 该模块定位为人物传记专属规则库，只负责本地姓名、本籍、学历、工作经历和和历日期规则，不读取文件、不调用 OCR/LLM、不写出 artifact。
- 后续应由 `biography_extractor.py` 或统一任务层编排 OCR/LLM/skill/MCP 后端，再把结构化人物结果回收到同一 package schema。

## 2026-04-25 继续推进记录 - BiographyPipeline 薄封装 Package

- `biography_pipeline.py`: 已新增 `get_capabilities()`、`process_ocr_results_package()` 与 `build_summary_package()`，统一输出 `biography_batch/biography_pipeline_summary` envelope。
- PDF 转图改为延迟导入，导入和 OCR-result package 处理不再依赖 `fitz`；该模块定位为薄工作流封装，不再维护并行人物实体 schema。
- 后续完整人物传记流程应由 `BiographyExtractor/BiographicalNER` 维护实体规则，由该 pipeline 只负责阶段协调、导出和摘要。

## 2026-04-25 继续推进记录

- `pdf_image_converter.py`: 已从路径列表工具升级为页级 artifact envelope，新增 `get_capabilities()`、`convert_range_package()`、`convert_all_package()` 与 `convert_pdf_to_images_package()`；旧路径列表 API 保持兼容。后续 Stage 3/OCR 输入应优先消费该 envelope。
- `citation_network_analyzer.py`: 已新增工作流 package 输出 `analyze_documents_package()`，统一记录 `backend/provider/model/confidence/needs_review/quality_flags`，并将执行元数据写入 `graph.metadata.execution`。后续 Stage 4 应改用该接口回写复核队列。
- `tools/workflow/stages/stage4_examine.py`: 已改为优先消费 `CitationNetworkAnalyzer.analyze_documents_package()`，并把 package 的 `confidence/needs_review/quality_flags` 写入阶段摘要、项目质量标记和复核队列。
- `academic_summarizer.py`: 已新增 `get_capabilities()` 与 `generate_full_analysis_package()`，旧摘要分析能力可包装为 `academic_analysis` envelope，后续可接入 LLM API、本地大模型、skill 或 MCP 摘要服务。
- `tools/workflow/stages/stage3_extract.py`: 已新增 `ner_extraction` package 摘要，Stage 3 现在会把每个来源的 `backend/provider/model/confidence/needs_review/quality_flags/categories` 写入 `stage_metadata.execution_summary.packages`。
- `ner_processor.py`: 已新增模块级 `recognize_historical_entities_package()` 与 `batch_process_documents_package()`，并让 `get_capabilities()` 记录多后端 fallback 顺序。后续 optimized/integrated 分支应吸收到该主接口或归档。
- `unified_ocr_processor.py`: 已新增 `UnifiedOCRResult.to_package()`、`process_image_package()` 与 `process_directory_package()`，OCR 层现在可以输出统一 `ocr_result/ocr_batch` envelope，承接 PDF 图片 artifact 并传递给 Stage 3/NER。
- `tools/workflow/stages/stage5_write.py`: Source snapshot 已消费 Stage 3 `ner_extraction` packages，记录 `ner_package_count/ner_packages_needing_review/ner_backends/ner_quality_flags`，写作链路可感知实体抽取质量。
- `ocr_processor.py`: 已新增底层 `ocr_result/ocr_batch` package 包装方法，并将 `pytesseract/Pillow/numpy` 改为可选依赖，轻量环境也可导入模块和读取能力快照。
- `llm_ocr_processor.py`: 已新增 `get_capabilities()`、`build_pages_package()` 与 `run_package()`，远程 Qwen-VL OCR 分支可以回收为统一 `ocr_result` envelope；`fitz/Pillow` 改为可选导入。
- `ndlocr_lite.py`: 已新增 `NDLOCRLiteResult.to_package()`、`get_capabilities()`、`process_image_package()` 与 `process_directory_package()`，本地 NDL OCR-Lite 分支可回收为 `ocr_result/ocr_batch` envelope。
- `ndlkotenocr_lite.py`: 已按同一协议新增 `NDLKotenOCRLiteResult.to_package()`、`get_capabilities()`、`process_image_package()` 与 `process_directory_package()`，古典 OCR 分支可回收为统一 envelope。
- `ndlocr_result_processor.py`: 已新增 `process_result_package()` 与 `batch_process_package()`，OCR 清洗/结构化后处理可输出 `processed_ocr_result/processed_ocr_batch` envelope。

## 文档信息

- 日期: 2026-04-21
- 适用范围: `modules/`、`tools/workflow/`、`intelligent_research_assistant/`、`app/`
- 目标: 在不偏离最初“日本史研究全流程工具箱”构想的前提下，为当前工作区的各模块制定下一阶段的系统优化设计
- 约束: 全流程遵守工作区隐秘性规范、日志规范、归档规范

---

## 一、总目标

本轮优化设计遵循以下四条硬约束：

1. 项目定位不变。
   必须继续服务于日本史研究、日文史料处理、学术笔记、引文管理、论文写作与知识库沉淀，而不是演化为泛用聊天系统。
2. 本地优先不变。
   OCR、文档处理、缓存、日志、研究材料管理优先走本地链路；外部 API 仅作为可替换增强层。
3. 隐秘性规范不变。
   密钥只允许走 `secrets/`，日志不记录原始敏感材料，不让中间产物在根目录和无关目录扩散。
4. 工作流中心化不变。
   后续模块都要围绕统一任务执行层、统一工作流编排层和统一数据模型收口。

---

## 二、当前共性问题

### 1. 模块并行分叉过多

当前存在大量 `主文件 + optimized + enhanced + integrated` 并行版本。它们不是稳定的多实现策略，而是历史阶段产物并存，导致：

- 维护成本高
- 行为不一致
- 测试覆盖被摊薄
- API 和 CLI 很难知道该调用哪一个版本

### 2. 核心基础设施尚未完全统一

虽然 `llm_client` 与安全密钥入口已完成第一轮修复，但仍然存在：

- 环境检测与环境管理并行
- 统一任务执行框架与传统模块直调并行
- `app`、`tools/workflow`、`modules` 三套入口并行

### 3. OCR 到研究分析的链路还不够闭环

当前 OCR、版面分析、NER、引文抽取、笔记生成、论文写作之间更多是“可串联”，还不是“天然闭环”。主要缺失：

- 稳定的统一中间数据模型
- 可复用的页面/段落/实体级元数据
- 面向史料场景的置信度与人工复核机制

### 4. 模块质量标准不统一

不少模块只是“设计完成”或“初步可跑”，但还未达到可持续优化的标准：

- 输入输出模式不稳定
- 测试模式与真实模式分叉严重
- 错误处理只做打印，不做结构化上报
- 缺少可度量的验收指标

### 5. 归档规范还未转化为工程机制

当前已有日志和归档规范，但还没有变成统一执行机制。后续必须明确：

- 测试脚本只落在 `tests/` 或 `scripts/`
- 中间报告只落在 `docs/archives/` 或 `archive/`
- 临时产物必须在完成日志与正式报告后归档并从工作根部移除

### 6. 多后端能力仍停留在局部流程，尚未上升为统一协议

当前“多选项后端”主要体现在少数具体流程和脚本中，还没有上升为全局统一协议，导致：

- 同一任务在不同模块中的后端选项命名不一致
- OCR、NER、工作流和 API 各自维护一套后端选择逻辑
- skill、MCP、本地模型、远程 API 难以进入同一调度层
- 前端和工作流无法稳定发现“某个任务当前到底有哪些可用后端”

因此，后续优化必须把“能力发现、后端选择、回退顺序、执行元数据”统一纳入执行层和任务层。

### 7. 工作流阶段仍缺少可追溯的能力快照与复核承载结构

即使统一任务层已经具备能力发现与多后端执行协议，`tools/workflow/` 里的阶段对象如果不把这些选择结果写回项目状态，后续仍会出现：

- 阶段结果可复现性不足，不知道某一轮实体抽取到底用了哪个 backend/provider/model
- `needs_review`、低置信度结果、降级执行结果缺少统一挂载位置
- 工作流恢复、前端展示、日志审计无法稳定读取阶段级元数据

因此，后续需要把“阶段能力快照、执行摘要、复核队列、artifact 索引”纳入 `ResearchProject` 的正式结构。

### 8. 编排层与阶段层的生命周期职责仍然重叠

当前 `WorkflowOrchestrator` 与各个 `Stage*` 对象都可能直接修改 `mark_stage_start/mark_stage_done`，这会造成：

- 阶段状态写入点分散，难以统一恢复与审计
- 编排层难以稳定插入 checkpoint、artifact 记录与失败摘要
- 后续阶段级 API/UI 展示时，无法确认真正的生命周期控制点

因此，后续需要明确“阶段负责业务执行，编排层负责调用记录、checkpoint、artifact 登记与统一异常摘要”的边界。

---

## 三、目标架构

后续模块优化以五层架构为准：

1. Core 层
   包括 `llm_client`、安全密钥、配置、缓存、环境管理、统一错误模型、统一数据模型。
2. Ingest 层
   包括 PDF、Word、图像、OCR、版面分析、日期抽取、训练数据准备。
3. Analysis 层
   包括 NER、实体消歧、引文网络、历史发言提取、研究探索、摘要、笔记、Obsidian 集成。
4. Writing 层
   包括论文润色、逆向大纲、文风迁移、引用格式化、书籍元数据整理、人格对话。
5. Workflow/API 层
   包括 `unified_task_executor`、`task_manager`、`module_adapters`、`tools/workflow`、`app`、前端接口。

所有优化后的模块都必须明确属于某一层，并减少跨层直接耦合。

---

## 四、模块处置原则

所有模块按照四种处置方式处理：

- 保留为主实现: 后续继续增强，成为唯一稳定入口。
- 合并吸收: 作为增强分支，其有效逻辑并入主实现。
- 保留薄封装: 只保留导出和兼容接口，不承载业务逻辑。
- 归档候选: 不再继续并行维护，待主实现吸收后进入归档。

---

## 五、模块级优化矩阵

### A. 核心基础设施模块

| 模块 | 当前判断 | 主要问题 | 优化设计 | 优先级 | 归宿 |
|------|------|------|------|------|------|
| `llm_client.py` | 主实现候选，已完成第一轮修复 | 仍缺 provider 级路由、统一异常模型、缓存接入 | 重构为 `ProviderAdapter + ResponseNormalizer + RetryPolicy`，对外只保留 `chat/_call_llm` | P0 | 保留为主实现 |
| `llm_client_optimized.py` | 优化分支 | 与主实现重复 | 仅提取其中可验证的重试/降级/统计能力，吸收到 `llm_client.py` | P1 | 合并后归档 |
| `secure_api_key_manager.py` | 主实现 | 仍有日志与状态接口未和全局配置层完全联动 | 新增 `ConfigFacade` 统一向 API、任务、前端暴露脱敏状态 | P0 | 保留为主实现 |
| `environment_checker.py` | 可用但偏报告型 | 检查结果不够结构化，可执行修复能力弱 | 拆为 `DependencyCheck`、`ModelCheck`、`ConfigCheck`、`RepairHints` | P1 | 保留为主实现 |
| `environment_manager.py` | 与 `integration_manager.py` 重叠 | 单例环境管理重复实现 | 保留轻量路径与环境探测，其他能力并入整合管理器 | P1 | 合并吸收 |
| `integration_manager.py` | 更完整的整合候选 | 过大、职责偏杂 | 拆成 `WorkspacePaths`、`DependencyRuntime`、`CleanupPolicy`、`ArtifactManager` | P1 | 保留为主实现 |
| `setup_assistant.py` | 设计充分但偏安装向导 | GitHub 插件、API 配置、Ollama 检查混杂 | 拆为独立任务卡，接入统一任务执行层和环境检测结果 | P2 | 保留为主实现 |
| `data_structurer.py` | 基础能力可复用 | 结构化能力偏弱，缺 schema 约束 | 升级为全局轻量数据清洗与导出工具，服务 OCR/NER/引用结果标准化 | P1 | 保留为主实现 |
| `task_cli.py` | 入口层 | 仅是命令行壳，任务与输出协议不统一 | 只保留为 `task_manager` CLI 入口，统一 JSON 输出与错误码 | P2 | 保留薄封装 |
| `task_manager.py` | 统一入口候选 | 过度依赖适配器，预设与真实执行未分层 | 重构为 `TaskRegistry + PresetStore + TaskFacade` | P0 | 保留为主实现 |
| `module_adapters.py` | 兼容层必要 | 适配器数量多且逻辑重复 | 用注册机制替代手工适配器列表，只保留 I/O 适配职责 | P1 | 保留为主实现 |
| `unified_task_executor.py` | 核心编排候选 | 任务实现内嵌过多，脚本模式与 API 模式重复 | 拆为 `TaskSpec`、`ExecutionBackend`、`ResultValidator`、`ArtifactWriter` | P0 | 保留为主实现 |

### B. 文档/OCR/版面分析模块

| 模块 | 当前判断 | 主要问题 | 优化设计 | 优先级 | 归宿 |
|------|------|------|------|------|------|
| `pdf_image_converter.py` | 小而稳定 | 仅做转换，缺页面元信息 | 增加页面映射、尺寸、dpi、裁切元数据输出 | P1 | 保留为主实现 |
| `pdf_processor.py` | 主 PDF 层候选 | 功能基础但粒度过粗 | 细化为 `info/convert/extract/layout hooks` 四类接口 | P1 | 保留为主实现 |
| `pdf_processor_optimized.py` | 优化分支 | 与主实现重复 | 抽取性能优化、异常恢复逻辑并入 `pdf_processor.py` | P2 | 合并后归档 |
| `doc_processor.py` | 主 Word 处理候选 | 结构提取能力可用，但和写作链路衔接不足 | 增加 footnote map、section tree、revision hooks | P1 | 保留为主实现 |
| `word_processor_optimized.py` | 优化分支 | 与 `doc_processor.py` 目标重叠 | 抽取增强逻辑并入 `doc_processor.py` 或 `word_exporter` | P2 | 合并后归档 |
| `ocr_processor.py` | 通用 OCR 入口候选 | 仍偏工具式封装，缺结果规范化 | 只保留统一入口与结果协议，模型细节下沉 | P0 | 保留为主实现 |
| `ocr_processor_optimized.py` | 优化分支 | 与主实现重复 | 吸收性能和容错逻辑 | P2 | 合并后归档 |
| `llm_ocr_processor.py` | 远程 OCR 主实现 | 外部 API 依赖强，版面与结构信息不足 | 增加页级块级返回格式、成本确认、缓存键 | P1 | 保留为主实现 |
| `ndlocr_lite.py` | 本地 OCR 实现 | 模型加载与失败提示需更稳定 | 标准化状态检查、版本检查、错误分级 | P1 | 保留为主实现 |
| `ndlkotenocr_lite.py` | 本地古典籍 OCR 实现 | 与 NDL OCR-Lite 逻辑重复 | 抽象共同基类，减少重复配置与 subprocess 控制 | P1 | 保留为主实现 |
| `ndlocr_result_processor.py` | 结果清洗层 | 与 `data_structurer` 职责交叠 | 仅保留 OCR 专属结构化，如行块页、置信度、版面映射 | P1 | 保留为主实现 |
| `ndl_ocr_batch_processor.py` | 稳定批处理候选 | 缺统一 artifact 清单 | 接入 `ArtifactManager`，输出批次级日志和恢复点 | P1 | 保留为主实现 |
| `ndl_ocr_monitor.py` | 运维模块 | 心跳逻辑与批处理割裂 | 变为独立监测服务，只输出健康状态与恢复建议 | P2 | 保留为主实现 |
| `unified_ocr_processor.py` | 总入口候选 | 还只是模型切换器，不是统一结果中心 | 升级为 OCR 门面层，统一所有 OCR 返回结构 | P0 | 保留为主实现 |
| `unified_ocr_processor.py` 新增约束 | 本轮新增方向 | 现阶段只覆盖 NDL 系模型，尚未纳入 Tesseract、LLM OCR 与混合后处理 | 升级为 `OCREngineRegistry + OCRResultNormalizer + OCRCapabilityDiscovery`，统一声明 `local_engine / remote_llm / hybrid_postprocess` | P0 | 并入主实现 |
| `universal_layout_analyzer.py` | 潜力大但实验性强 | 模型化设计好，尚未进入主工作流 | 先定义最小可用输出协议，只支持 `book/diary/newspaper` 三类 | P1 | 保留为主实现 |
| `pdf_date_matcher.py` | 专用训练数据模块 | 与版面分析和 OCR 训练链路耦合过深 | 作为训练准备层组件，输出标准化配对样本 | P2 | 保留为主实现 |
| `classical_ocr_training_workflow.py` | 训练准备总线 | 流程长且实验性强 | 与 `universal_layout_analyzer`、`pdf_date_matcher` 组成独立训练子系统 | P2 | 保留为主实现 |
| `biography_ocr_pipeline.py` | 专用 OCR 管道 | 与通用 OCR 管线重复 | 下沉为特定模板流程，不再直接暴露成通用模块 | P2 | 保留为专用流程 |
| `biography_extractor.py` | 专用人物提取主模块 | 和 `biography_pipeline.py`、`biographical_ner.py` 有重叠 | 统一成“人物传记结构化”主模块 | P1 | 保留为主实现 |
| `biographical_ner.py` | 传记 NER 辅助模块 | 与主 NER 分叉 | 只保留人物传记专属规则库和 post-process | P2 | 合并吸收 |
| `biography_pipeline.py` | 专用流程包装 | 与 `biography_extractor.py` 重叠 | 只保留为薄工作流封装 | P3 | 保留薄封装 |

### C. 研究分析与知识整理模块

| 模块 | 当前判断 | 主要问题 | 优化设计 | 优先级 | 归宿 |
|------|------|------|------|------|------|
| `academic_note_generator.py` | 主实现候选 | Prompt 重、输出不稳定、实体链接和章节结构耦合 | 拆为 `NoteExtractor + NoteRenderer + ObsidianLinkResolver` | P0 | 保留为主实现 |
| `academic_note_generator.py` 新增约束 | 本轮新增方向 | 仍保留旧式直连 LLM 与环境变量路径，且返回结构与 workflow 假设不稳定 | 改为通过统一任务层执行 `academic_note`，统一返回 `markdown/entities/backend/provider/model/needs_review` | P0 | 并入主实现 |
| `academic_note_generator_optimized.py` | 优化分支 | 与主实现分叉 | 仅吸收稳定的缓存、模板或批处理逻辑 | P2 | 合并后归档 |
| `academic_summarizer.py` | 主实现候选 | 摘要、概念、相关度评估耦合 | 拆为 `Summarize/QuestionExtract/RelevanceScore` 三类能力 | P1 | 保留为主实现 |
| `academic_summarizer_optimized.py` | 优化分支 | 与主实现重复 | 提炼性能与提示词策略后并回主实现 | P2 | 合并后归档 |
| `embedding_manager.py` | 设计价值高但当前不稳 | 模型加载会触发重依赖和外网阻塞 | 拆为 provider registry，本地嵌入与远程嵌入分层管理 | P1 | 保留为主实现 |
| `history_field_explorer.py` | 研究起始总入口候选 | 体量过大、搜索/分析/写作混在一起 | 拆为 `FieldSearch`、`FieldSynthesis`、`FieldDrafting` | P0 | 保留为主实现 |
| `historical_speech_extractor.py` | 场景模块 | 发言识别、日期提取、NER 集成三件事耦合 | 分离 `SpeechSegmenter`、`DateResolver`、`EntityAttach` | P1 | 保留为主实现 |
| `obsidian_integration.py` | 关键集成层 | 与笔记生成器职责边界不清 | 只负责 vault 输出、双链、frontmatter、回写策略 | P1 | 保留为主实现 |
| `obsidian_integration.py` 新增约束 | 本轮新增方向 | 当前承担过多模板和内容职责，且 vault 初始化与导出稳定性不足 | 收口为文件系统与 vault 集成层，只负责 safe write、graph scan、frontmatter/vault 结构维护 | P1 | 并入主实现 |
| `citation_network_analyzer.py` | 主分析候选 | 规则抽取为主，缺统一图模型 | 引入标准 node/edge schema 与可信度 | P1 | 保留为主实现 |
| `citation_network_analyzer.py` 新增约束 | 本轮新增方向 | 当前抽取、图构建、学派识别混在一起，且节点/边字段未与 workflow schema 对齐 | 收口为 `CitationRecordNormalizer + CitationGraphBuilder + CitationGraphSummary`，统一输出 `nodes/edges/records/summary/confidence` | P0 | 并入主实现 |
| `citation_normalizer.py` | 已部分优化 | 功能多但过重，LLM 辅助与规则转换耦合 | 拆为 `Parse/Validate/Normalize/Format` 四段 | P0 | 保留为主实现 |
| `citation_normalizer.py` 新增约束 | 本轮新增方向 | 现有 `normalize` 返回结构与 Stage/formatter 难以直接复用 | 统一返回 citation record schema，供 Stage 2/4/写作链共享 | P1 | 并入主实现 |
| `citation_formats.py` | 基础格式化层 | 与 `citation_normalizer.py` 关系未界定 | 只保留纯格式渲染，不做解析和校验 | P1 | 保留为主实现 |
| `citation_formats.py` 新增约束 | 本轮新增方向 | 仍偏向单一书目场景，缺少对统一 citation record 的直接渲染入口 | 新增 `format_record`/`format_batch`，仅负责把规范化 record 渲染成目标格式 | P1 | 并入主实现 |
| `book_citation_organizer.py` | 专用书籍整理模块 | OCR、元数据提取、命名、CSV 导出耦合 | 拆为 `BookScanMeta + RenamePolicy + CitationExport` | P1 | 保留为主实现 |
| `ner_processor.py` | 主 NER 候选 | 输出稳定性、词典、批量处理、层级实体不足 | 设计为“规则词典 + LLM + 结构校验”的混合识别器 | P0 | 保留为主实现 |
| `ner_processor.py` 新增约束 | 本轮新增方向 | 旧实现仍停留在 `test_mode + provider` 二分法，缺少真正的多后端发现与回退 | 升级为 `NERBackendRegistry + NERResultNormalizer + ReviewFlagger`，统一接入 `script / llm_api / local_llm / skill / mcp / hybrid` | P0 | 并入主实现 |
| `ner_processor_integrated.py` | 集成分支 | 可能包含可用整合思路，但不应并行保留 | 提取可复用 glue code | P2 | 合并后归档 |
| `ner_processor_optimized.py` | 优化分支 | 与主实现分叉 | 吸收改进点后归并 | P2 | 合并后归档 |
| `ner_disambiguation.py` | 必要后处理 | 规则和上下文能力偏弱 | 建立实体规范名、别名、置信度合并机制 | P1 | 保留为主实现 |

### D. 写作、润色与输出模块

| 模块 | 当前判断 | 主要问题 | 优化设计 | 优先级 | 归宿 |
|------|------|------|------|------|------|
| `paper_polisher.py` | 主实现候选 | 只偏“删冗”，学术结构反馈不足 | 升级为段落级润色内核，保持与 Word 修订接口兼容 | P0 | 保留为主实现 |
| `paper_polisher_enhanced.py` | 增强分支 | 策略多但与主实现脱节 | 吸收脚注重建与修订策略，保留少量高级模式 | P1 | 合并吸收 |
| `paper_polisher_optimized.py` | 优化分支 | 与主实现重复 | 提炼稳定性能逻辑 | P2 | 合并后归档 |
| `reverse_outline_analyzer.py` | 主分析候选 | 已接近可用，但缺统一写作评估协议 | 输出统一的 `OutlineReview` 数据模型 | P1 | 保留为主实现 |
| `style_transfer.py` | 场景价值高但风险大 | 文风迁移容易破坏史学术语和论证结构 | 改为“保守迁移”，优先输出建议而非强制改写 | P2 | 保留为主实现 |
| `virtual_persona_chatbot.py` | 创意模块 | 与研究助手边界模糊，风险在“拟人化偏离学术” | 保留为受限学术角色工具，加入事实约束和引文模式 | P3 | 保留为特定场景模块 |

### E. 工作流、包装与兼容模块

| 模块 | 当前判断 | 主要问题 | 优化设计 | 优先级 | 归宿 |
|------|------|------|------|------|------|
| `ndl_download_workflow.py` | 兼容薄封装 | 无业务逻辑问题 | 保持轻量导出，不向内生长逻辑 | P3 | 保留薄封装 |
| `pdf_to_ner_workflow.py` | 兼容薄封装 | 无业务逻辑问题 | 保持轻量导出，不向内生长逻辑 | P3 | 保留薄封装 |

### F. 跨目录核心模块

| 模块 | 当前判断 | 主要问题 | 优化设计 | 优先级 | 归宿 |
|------|------|------|------|------|------|
| `tools/workflow/workflow_orchestrator.py` | 主工作流总线候选 | 阶段可跑，但阶段间契约仍不够严格 | 用 `ResearchProject` 统一 stage I/O、artifact、恢复点 | P0 | 保留为主实现 |
| `tools/workflow/workflow_orchestrator.py` 新增约束 | 本轮新增方向 | 仍可能在 stage 内部直接耦合具体模块实现，不利于多后端任务发现与切换 | 后续通过统一任务层请求 OCR/NER/摘要等能力，不再在 stage 中硬编码后端选择 | P0 | 并入主实现 |
| `tools/workflow/workflow_orchestrator.py` 新增约束2 | 本轮新增方向 | 编排层与阶段层都在改写阶段状态，且 checkpoint/artifact 缺少统一登记点 | 由 orchestrator 统一记录调用时间、checkpoint 路径、导出产物与异常摘要，stage 只负责业务执行 | P0 | 并入主实现 |
| `tools/workflow/stages/stage4_examine.py` 新增约束 | 本轮新增方向 | 仍停留在局部规则分析，缺少阶段级执行摘要、质量标记与 artifact 回收 | 输出 citation/outlining 的摘要统计、质量标记与 review 信号，并写回 `stage_metadata` | P1 | 并入主实现 |
| `tools/workflow/research_project.py` | 核心数据模型 | 还需增加 artifact 索引与审计字段 | 增加 `artifacts`, `quality_flags`, `review_queue` | P0 | 保留为主实现 |
| `tools/workflow/research_project.py` 新增约束 | 本轮新增方向 | 现有数据结构难以保存阶段能力快照、后端选择、复核项与轻量审计信息 | 增加 `stage_metadata`，并让 `artifacts/review_queue/quality_flags` 成为工作流统一挂载位 | P0 | 并入主实现 |
| `tools/workflow/stages/*` | 阶段实现层 | 与模块层耦合较深 | 每个阶段只编排，不再承载复杂业务逻辑 | P1 | 保留为主实现 |
| `tools/workflow/stages/stage2_organize.py` 新增约束 | 本轮新增方向 | 笔记生成与 vault 导出链未接入统一任务层，也缺少阶段级摘要和 review 标记 | 将学术笔记生成、vault 导出、citation 输出摘要写回 `stage_metadata`，并记录导出 artifact | P1 | 并入主实现 |
| `tools/workflow/stages/stage3_extract.py` 新增约束 | 本轮新增方向 | 当前仍在阶段内部硬编码 NER/LLM 选择逻辑，且未回写执行元数据 | 改为通过 `TaskManager` 发现并执行 NER 能力，并把 backend/provider/model/capabilities/review flags 写回项目 | P0 | 并入主实现 |
| `intelligent_research_assistant/` | 中长期统一研究层 | 文档完整但实际开发尚未完全收束 | 后续作为搜索/分析/生成统一内核，逐步吸收 `history_field_explorer` 能力 | P1 | 保留为主实现 |
| `app/app.py` | API 主入口 | 仍有直接实例化、重初始化和启动时重负载问题 | 改为 app factory，重模块延迟初始化 | P1 | 保留为主实现 |
| `app/app.py` 新增约束 | 本轮新增方向 | OCR、LLM、PDF 等重模块仍可能在导入阶段初始化，导致导入时就触发模型检查和环境噪声 | 增加 API 层统一 lazy service 包装，禁止在模块导入阶段直接实例化重模块 | P1 | 并入主实现 |
| `frontend/` | 前端工作台 | 已有结构，但需要严格绑定后端稳定接口 | 以后端统一 API schema 为准，不再追随实验模块 | P2 | 保留为主实现 |

---

## 六、阶段性实施路线

### Phase 1: 核心收口

目标:
- 固定唯一核心实现
- 让安全、配置、任务执行、工作流中心线稳定

范围:
- `llm_client.py`
- `secure_api_key_manager.py`
- `task_manager.py`
- `module_adapters.py`
- `unified_task_executor.py`
- `tools/workflow/*`
- `app/config.py` / `app/app.py`

交付标准:
- 所有主入口只走一套配置和密钥链路
- 主工作流和 API 使用同一套数据模型
- `optimized/integrated` 分支不再被直接调用

### Phase 2: OCR 与文档摄入稳定化

目标:
- 建立统一 OCR 结果协议
- 建立页面级、块级、文本级 artifact 体系

范围:
- `pdf_processor.py`
- `pdf_image_converter.py`
- `ocr_processor.py`
- `llm_ocr_processor.py`
- `ndlocr_lite.py`
- `ndlkotenocr_lite.py`
- `ndlocr_result_processor.py`
- `unified_ocr_processor.py`
- `universal_layout_analyzer.py`

交付标准:
- 所有 OCR 引擎输出统一结构
- 版面分析与 OCR 可组合
- 失败页可重试，批次可恢复
- OCR 能力可被统一发现，并明确区分 `local_engine`、`remote_llm`、`hybrid_postprocess`

### Phase 3: 史料分析主链打通

目标:
- 把 OCR、NER、发言提取、引文、笔记形成闭环

范围:
- `ner_processor.py`
- `ner_disambiguation.py`
- `historical_speech_extractor.py`
- `citation_network_analyzer.py`
- `citation_normalizer.py`
- `citation_formats.py`
- `academic_note_generator.py`
- `obsidian_integration.py`

交付标准:
- 实体、引用、笔记共用统一 schema
- 所有模块都能输出置信度和复核标记
- Obsidian 输出稳定
- NER 能力可统一接入 `script / llm_api / local_llm / skill / mcp / hybrid`
- 工作流阶段能够持久化能力快照、执行摘要、人工复核队列
- 学术笔记链能够统一输出 `markdown/entities/export_summary/backend/provider/model`
- Orchestrator 能够统一登记 checkpoint、导出产物与阶段异常摘要

### 新增实施约束: 多后端任务的统一接入规则

从本轮开始，凡是具备多后端可能性的模块，都必须满足以下额外要求：

1. 后端发现统一化
   模块不能只暴露“执行”方法，还必须能返回当前可用后端列表、可用 provider、默认回退顺序和是否需要外部依赖。
2. 后端结果统一化
   无论来自规则、本地模型、远程 API、skill 还是 MCP，结果都必须回收到同一结构，至少包含 `backend`、`provider`、`model`、`confidence`、`needs_review` 等元数据。
3. 工作流接入统一化
   `tools/workflow/` 后续不得直接把多后端逻辑写死在具体 stage 中，而应通过统一任务层请求能力并选择后端。
4. OCR 与 NER 要优先完成协议化
   这是当前最关键的主链，因此 `unified_ocr_processor.py` 与 `ner_processor.py` 要先成为协议中心，再逐步吸收旧模块逻辑。

### Phase 4: 写作与润色链路重构

目标:
- 形成“草稿 - 审视 - 润色 - 引用格式化 - Word 导出”稳定闭环

范围:
- `paper_polisher.py`
- `reverse_outline_analyzer.py`
- `style_transfer.py`
- `doc_processor.py`
- `book_citation_organizer.py`

交付标准:
- 润色结果可追踪
- 逻辑审视输出结构化报告
- Word 与 Markdown 互通

### Phase 5: 专用场景与训练子系统

目标:
- 让人物传记、古典籍 OCR 训练等高价值专用模块独立成子系统

范围:
- `biography_*`
- `biographical_ner.py`
- `pdf_date_matcher.py`
- `classical_ocr_training_workflow.py`

交付标准:
- 与通用主链解耦
- 有明确输入、输出和评估标准

### Phase 6: 合并、归档与清理

目标:
- 清除平行分支
- 恢复结构清晰度

范围:
- `*_optimized.py`
- `*_integrated.py`
- 历史 wrapper 和实验脚本

交付标准:
- 所有历史增强版只保留可证明有效的差异
- 根目录与 `modules/` 不再堆积平行实现
- 完成归档日志

---

## 七、统一工程规范

后续具体优化时，所有模块都必须满足以下工程标准：

1. 输入输出标准化
   每个模块必须显式定义输入结构、输出结构、错误结构。
2. 测试标准化
   测试脚本只允许进入 `tests/` 或 `scripts/`；完成后生成日志，必要时归档到 `archive/`。
3. Artifact 标准化
   中间产物只能落到 `output/`、`temp/`、`cache/`、`workflow_output/` 等受控目录。
4. 日志标准化
   日志只记录状态、路径、摘要、统计和错误类型，不记录密钥和敏感正文。
5. 归档标准化
   优化完成后，临时报告、临时测试脚本、中间脚本必须在正式日志和报告落地后统一归档并从非归档位置移除。

---

## 八、下一轮实施建议

建议按以下顺序开始实做：

1. `task_manager.py` / `unified_task_executor.py` / `module_adapters.py`
2. `app/app.py` 延迟初始化与统一 schema
3. `unified_ocr_processor.py` 统一 OCR 返回结构
4. `ner_processor.py` + `ner_disambiguation.py`
5. `academic_note_generator.py` + `obsidian_integration.py`
6. `paper_polisher.py` + `reverse_outline_analyzer.py`

---

## 九、本轮归档说明

本轮仅产出正式优化设计文档与正式工作日志，未新增中间测试脚本或临时脚本，因此没有额外归档删除动作。

后续进入模块实做阶段时，严格执行：

- 先产生日志与正式报告
- 再统一归档中间文件
- 最后从工作根部和非归档目录删除中间脚本
---

## 十、2026-04-21 增量约束补记

本轮继续推进时，新增以下约束，并作为后续实作的直接锚点：

1. `citation_normalizer.py`
   必须从“返回解析碎片”升级为“返回统一 citation record”。
   统一 record 至少包含 `raw_text / normalized_citation / type / title / authors / year / journal_or_publisher / pages / volume / issue / doi / url / confidence / needs_review / backend / provider / model`。
   同时保留批处理与旧接口兼容能力，供 Stage 7 与引用格式化链共享。

2. `paper_polisher.py`
   不再直接绑定单一远程 LLM 路径，而是升级为统一任务层门面。
   对外仍保留 `polish_paragraph`、`process_document` 等旧接口，但内部要能声明并消费 `script / llm_api / local_llm / skill / mcp` 等后端能力。
   输出必须统一回传 `polished_text / revision_notes / backend / provider / model / confidence / needs_review`。

3. `reverse_outline_analyzer.py`
   必须从“独立启发式分析器”升级为“统一写作审校协议门面”。
   本地启发式分析仍作为稳定 fallback，但同时要支持通过统一任务层接入远程模型或本地模型。
   统一输出至少包含 `section_word_counts / section_ratios / logical_gaps / deviation_flags / suggestions / confidence / needs_review / backend / provider / model`。

4. `tools/workflow/stages/stage5_write.py`
   Stage 5 不再只写入 `paper_draft` 并结束。
   必须补齐草稿长度、结构快照、引用占位统计、来源使用摘要，并写回 `stage_metadata`。
   如草稿过短、无章节结构或缺失参考文献占位，需要进入 `review_queue` 或 `quality_flags`。

5. `tools/workflow/stages/stage6_polish.py`
   Stage 6 必须通过统一协议消费润色、逆向大纲、文风调整结果，而不是在 stage 内部各自硬编码后端逻辑。
   需要写回 `capability_snapshot / execution_summary / review_queue / quality_flags`，并优先基于润色后的文本重新做 outline review。
   任何失败都要可降级，不允许因为单个后端不可用而中断整段写作链。
7. `tools/workflow/stages/stage7_format.py`
   Stage 7 蹇呴』姝ｅ紡娑堣垂缁熶竴 citation record锛岃€屼笉鍐嶇淮鎸佸眬閮ㄧ殑 reference string 鎵嬪啓閫昏緫銆?
   闇€瑕佺粺涓€鍐欏洖 `normalized_citation_records / formatted_reference_count / records_needing_review / output_artifacts / execution_summary`锛屽苟瀵?Word 瀵煎嚭缁撴灉杩涜 artifact 鐧昏銆?
   Stage 7 鐨勮緭鍏ユ枃鏈簲浼樺厛浣跨敤 `style_transferred_draft -> polished_draft -> paper_draft` 锛屼互淇濊瘉鏈€缁堣緭鍑洪摼涓庡啓浣滄鼎鑹查摼淇濇寔涓€鑷淬€?
8. `modules/style_transfer.py`
   `style_transfer.py` 蹇呴』鍜?`paper_polisher.py` 淇濇寔鍚岀被鍨嬪崗璁寲鏀跺彛锛屼笉鍐嶇洿鎺ヨ嚜宸辫鍙?env 鍜岀粍瑁?provider config銆?
   瀵瑰浠嶄繚鐣?`analyze_style_matrix`銆乣transfer_style`銆乣few_shot_style_imitation` 绛夋棫鎺ュ彛锛屼絾鍐呴儴瑕佷紭鍏堥€氳繃缁熶竴浠诲姟灞傛秷璐?`style_transfer` 鑳藉姏銆?
   Stage 6 搴斾紭鍏堥€氳繃璇ユā鍧楄€屼笉鏄洿鎺ヨ法杩?task manager锛屼互淇濇寔鍐欎綔閾惧唴閮ㄧ殑妯″潡杈圭晫涓€鑷淬€?
<!-- 2026-04-25 addendum: environment_checker.py now exposes non-destructive structured checks through check_dependencies_structured, build_repair_hints, and get_structured_report. These outputs include status, issue/warning counts, backend/provider/model, confidence, needs_review, and repair hints without automatically changing .env or installing packages. -->

<!-- 2026-04-25 addendum: pdf_processor.py now keeps legacy conversion/extraction methods while adding get_pdf_info_package, extract_text_package, and convert_to_images_package. These packages expose backend/provider/model, confidence, needs_review, quality_flags, page metadata, page text, and image artifacts so OCR and document-ingest stages can consume PDF outputs through a stable protocol. -->

<!-- 2026-04-25 addendum: history_field_explorer.py now exposes get_capabilities() and records execution metadata in FieldReport.to_dict(). draft_paper keeps the legacy return shape while adding backend/provider/model/confidence/needs_review and quality metadata. This is the first safe facade-level split toward FieldSearch/FieldSynthesis/FieldDrafting without breaking Stage 5. -->

<!-- 2026-04-25 addendum: data_structurer.py now provides lightweight schema validation and workflow-friendly envelopes through validate_schema, normalize_record(s), and build_export_payload. CSV export should preserve the union of dict fields instead of only the first row keys. Future OCR/NER/citation adapters can reuse this for low-risk structural checks before writing artifacts. -->

<!-- 2026-04-25 addendum: Stage 5 now records a source_snapshot before and after draft generation. The snapshot summarizes literature records, Stage 2 book_citation_records, notes, entities, relations, formatted citations, review counts, and sample titles. Draft metadata should include source_record_count/book_citation_record_count so generated papers can be audited against available sources. -->

<!-- 2026-04-25 addendum: Stage 4 and Stage 7 now consume Stage 2 book_citation_records in addition to literature records. Stage 4 should build citation-network nodes from unified records; Stage 7 should merge literature-derived records and Stage 2 records into the final reference list, preserving needs_review/confidence metadata. -->

<!-- 2026-04-25 addendum: tools/workflow/stages/stage2_organize.py now consumes ResearchProject.book_metadata through the upgraded BookCitationOrganizer contract. Stage 2 should write book_citation_records into stage metadata, extend formatted_citations with rendered book references, and send incomplete book metadata to review_queue/quality_flags. -->

<!-- 2026-04-25 addendum: doc_processor.py now keeps legacy extract/create methods but also exposes extract_document_package/extract_document_package_from_bytes for workflow use. The package contract includes plain_text, section_tree, footnote_map, endnote_map, revision_hooks, backend/provider/model, confidence, needs_review, quality_flags, artifacts, and summary. Future writing-stage modules should consume this package instead of ad-hoc paragraph dictionaries when possible. -->

<!-- 2026-04-25 addendum: book_citation_organizer.py has been upgraded as the Stage 2 book metadata facade. It must keep legacy process_all/export_csv compatibility while returning normalized citation records, backend/provider/model metadata, confidence, needs_review, review notes, capabilities, and artifact summaries. LLM/API/local-model/skill/MCP enhancements should remain optional backends and must be folded back into the same record schema. -->

<!-- 2026-04-25 addendum: root documents and workflow docs were reorganized as an execution constraint. README.md is now a short navigation entry, WORKFLOW_DESIGN.md is a workflow index, GUIDELINES.md is the root privacy/collaboration rulebook, and detailed workflow notes live under docs/workflow/. Future module optimization reports should link back to these files when they change backend protocol, artifact handling, privacy rules, or workflow stage behavior. -->

<!-- 2026-04-25 addendum: ndl_ocr_batch_processor.py now exposes get_capabilities() and process_batch_package(). The default constructor no longer hard-fails when the local NDL OCR script is absent; workflows and agents should read available/capabilities first, then choose local_engine, unified OCR, LLM OCR, skill, MCP, or hybrid fallback. The package output is ocr_batch with page artifacts, statistics, confidence, needs_review, and quality_flags. -->

<!-- 2026-04-25 addendum: a workspace-specific AI agent skill scaffold now lives at docs/agent_skills/historyresearch-workspace/. Future agents should use it to align privacy rules, package/envelope contracts, optimization-anchor updates, testing, report generation, and cleanup. Once reviewed, it can be installed into the local Codex skill directory and exposed as a skill backend option in the unified task layer. -->

<!-- 2026-04-25 addendum: llm_client.py and unified_task_executor.py now include a tested Ollama local_llm path for small-model agent use. Ollama base URLs ending in /v1 are normalized for native /api/chat calls; empty local model output is flagged and treated as backend failure so TaskManager can fall back to script backends. TaskManager now includes summary_local_small as a low-token Ollama smoke preset. -->

<!-- 2026-04-25 addendum: the historyresearch-workspace skill has been upgraded with small-model playbooks, acceptance checklists, and a read-only validation script at docs/agent_skills/historyresearch-workspace/scripts/validate_workspace_skill.py. Future agents should use these resources before and after module optimization work. -->

<!-- 2026-04-25 addendum: academic_note_generator.py now exposes get_capabilities(), generate_reading_note_package(), and batch_process_package(). Stage 2 now prefers academic_note packages and stores compact note package summaries in stage_metadata.execution_summary.note_packages, including backend/provider/model/confidence/needs_review/quality_flags/export_summary. -->

<!-- 2026-04-25 addendum: paper_polisher.py now exposes polish_text_package(), polish_paragraph_package(), and process_document_package(). Stage 6 prefers paper_polish packages and records package_type plus quality_flags in stage_metadata.execution_summary.paper_polish while preserving legacy polish_paragraph/polish_text/process_document compatibility. -->

<!-- 2026-04-25 addendum: reverse_outline_analyzer.py now exposes analyze_package() as an outline_review envelope. Stage 6 prefers outline_review packages and records package_type plus quality_flags in stage_metadata.execution_summary.reverse_outline while preserving legacy analyze/extract_outline/detect_imbalance/check_logic_gaps/suggest_revisions compatibility. -->

<!-- 2026-04-25 addendum: style_transfer.py now exposes transfer_style_package() as a style_transfer envelope. Stage 6 prefers style_transfer packages and records package_type plus quality_flags in stage_metadata.execution_summary.style_transfer while preserving legacy analyze_style_matrix/transfer_style/transfer_style_result/few_shot_style_imitation compatibility. -->

<!-- 2026-04-25 addendum: historical_citation_verifier.py now exposes get_capabilities(), parse_docx_package(), and verify_docx_package(). The parse package is offline by default; source search, restricted download, OCR, and LLM/local_llm/skill/MCP alignment helpers must be explicitly selected and folded back into historical_citation_verification with confidence, needs_review, quality_flags, execution parameters, and artifact paths. -->

<!-- 2026-04-25 addendum: universal_layout_analyzer.py now exposes get_capabilities(), analyze_page_package(), and analyze_document_package(). fitz/numpy/PIL are optional at import time, metadata-only package generation does not load ONNX models, and future book/diary/newspaper layout backends must return layout_page/layout_document envelopes before OCR or training-sample preparation consumes them. -->

<!-- 2026-04-25 addendum: pdf_date_matcher.py now exposes get_capabilities(), parse_annotation_dates_package(), match_dates_package(), and generate_training_data_package(). API key file loading is disabled by default; LLM/API date recognition must be explicitly selected, and training-prep results should flow through date_extraction/date_match_pairs/training_samples envelopes. -->

<!-- 2026-04-25 addendum: classical_ocr_training_workflow.py now exposes get_capabilities(), build_summary_package(), and build_training_samples_package(). fitz/numpy/PIL are optional at import time, long-running PDF/model work reports structured dependency failures, and the training bus should coordinate layout_page/date_match_pairs/training_samples packages rather than expose ad-hoc long-flow state as the only contract. -->

<!-- 2026-04-25 addendum: biography_extractor.py now exposes get_capabilities(), extract_entities_package(), and process_ocr_results_package(). It no longer reads secrets/api_keys.txt by default, PDF conversion plus NDL/LLM OCR are lazy-loaded, and biography entities should flow through biography_entities/biography_batch envelopes for future script/local_llm/skill/MCP backends. -->

<!-- 2026-04-25 addendum: biographical_ner.py now imports successfully, fixes the WorkExperience.position field, and exposes get_capabilities(), process_text_blocks_package(), and extract_biographical_entities_package(). It is scoped as an offline rule library only; OCR/LLM/skill/MCP orchestration belongs to biography_extractor.py or the unified task layer. -->

<!-- 2026-04-25 addendum: biography_pipeline.py now exposes get_capabilities(), process_ocr_results_package(), and build_summary_package(). It lazy-loads PDF conversion, acts as a thin workflow wrapper, and delegates entity schema to biographical_ner/biography_extractor while returning biography_batch/biography_pipeline_summary envelopes. -->

<!-- 2026-04-25 addendum: Stage 6 now registers paper_polish, style_transfer, and outline_review packages through ResearchProject.register_package(). stage_metadata.package_protocol records the project-level registry handoff so Stage 7, API endpoints, and AI-agent skills can consume polish/review quality flags without scraping execution_summary. -->

<!-- 2026-04-25 addendum: Stage 7 now registers citation_formatting packages through ResearchProject.register_package() and Word export artifacts through ResearchProject.register_artifact(). stage_metadata.package_protocol and artifact_protocol are the final-output audit handoff for API, workflow checkpoints, and AI-agent skills. -->

<!-- 2026-04-25 addendum: WorkflowOrchestrator checkpoint JSON writes now go through ArtifactManager.write_json_artifact() within the managed output root. ResearchProject.to_dict() provides the shared serializable snapshot used by both compatibility save() and managed checkpoint artifacts. -->

<!-- 2026-04-25 addendum: /api/tasks/execute now returns TaskManager.execute_task_package() task_execution envelopes instead of the legacy execute_task result. API, frontend, MCP, skill, and small-model agents should consume task_type/schema_version/task_options/confidence/needs_review/quality_flags from this shared envelope. -->

<!-- 2026-04-25 addendum: optimized/enhanced/integrated branch exit prep is complete at the manifest level. Physical moves remain deferred because paper_polisher_optimized is directly imported by tests and ner_processor_integrated dynamically imports ner_processor_optimized. Future archive moves must first replace those references with canonical package/facade coverage and add rollback notes. -->

<!-- 2026-04-25 addendum: the historyresearch-workspace skill now includes a read-only inspect_workspace_contracts.py script and task_artifact_snapshots.md reference. Small-model agents should use these snapshots to discover TaskManager tasks, execute_task_package availability, and ArtifactManager managed-root capabilities before choosing API/workflow/module entry points. -->

<!-- 2026-04-25 addendum: the current task-layer/API/artifact/Stage 2-7 registry queue has completed wide regression with python -m unittest discover tests: 197 tests OK, 10 skipped. Optional dependency tests for python-docx and PyMuPDF/fitz now skip cleanly when those libraries are absent instead of failing during import. -->

<!-- 2026-04-28 addendum: history-citation workspace integration is now anchored outside the original module files. modules/historical_citation_workspace.py wraps the optimized verifier package methods with path redaction, explicit external-search/download flags, and historical_citation_workspace_package output. module_adapters/TaskManager expose historical_citation and history_citation aliases; app/app.py exposes /api/doc/historical-citation-package. Future improvements to workspace integration should extend this wrapper/API/task layer first, not modules/historical_citation/ or modules/historical_citation_verifier.py, unless the verifier itself is the explicit optimization target. -->

<!-- 2026-04-28 addendum: tracked config privacy has been tightened. config/api_config.json, config/current_environment.json, and config/external_config.json are public templates only: environment variable names, relative paths, and disabled optional integrations. scripts/check_github_upload_safety.py now parses these tracked configs and fails only if they contain unparsable JSON, private/absolute paths, secret-like values, or sensitive fields that are not env-var references. NDL account/password/login values remain restricted to env vars or ignored secrets/ paths. -->
