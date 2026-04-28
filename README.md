# 历史研究 AI 工具箱

面向日本史、日文史料处理与学术写作的本地优先型 AI 工作区。

本项目的目标不是做通用聊天应用，而是把 OCR、NER、史料整理、引文管理、学术笔记、论文写作、润色与最终格式化串成一条可复核、可归档、可逐步替换后端的研究流水线。

## 当前状态

- 当前优化锚点: [MODULE_OPTIMIZATION_DESIGN_2026-04-21.md](docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md)
- AI agent skill 方案: [AI_AGENT_SKILL_DESIGN_2026-04-25.md](docs/project/AI_AGENT_SKILL_DESIGN_2026-04-25.md)
- 工作区 skill 脚手架: [docs/agent_skills/historyresearch-workspace/SKILL.md](docs/agent_skills/historyresearch-workspace/SKILL.md)
- 工作流总览: [WORKFLOW_DESIGN.md](WORKFLOW_DESIGN.md)
- 工作区规范: [GUIDELINES.md](GUIDELINES.md)
- 详细技术文档: [COMPREHENSIVE_TECHNICAL_GUIDE.md](COMPREHENSIVE_TECHNICAL_GUIDE.md)
- GitHub 上传排除规范: [docs/GITHUB_UPLOAD_EXCLUSION_POLICY.md](docs/GITHUB_UPLOAD_EXCLUSION_POLICY.md)

## 核心能力

| 方向 | 当前主入口 | 说明 |
| --- | --- | --- |
| 统一任务执行 | `modules/task_manager.py`, `modules/unified_task_executor.py` | 管理脚本、本地模型、远程 API、可扩展后端与统一结果元数据 |
| OCR 与摄入 | `modules/unified_ocr_processor.py` | 多 OCR 后端统一入口，面向 PDF、图像、页面级文本与复核标记 |
| NER 与实体处理 | `modules/ner_processor.py`, `modules/ner_disambiguation.py` | 支持规则、LLM、本地模型、skill/MCP 扩展方向与实体消歧 |
| 笔记与知识库 | `modules/academic_note_generator.py`, `modules/obsidian_integration.py` | 生成学术笔记、frontmatter、双链与 vault 输出 |
| 引文与史料考察 | `modules/citation_normalizer.py`, `modules/citation_formats.py`, `modules/citation_network_analyzer.py` | 统一 citation record、格式渲染、引文网络与可信度摘要 |
| 写作与润色 | `modules/paper_polisher.py`, `modules/reverse_outline_analyzer.py`, `modules/style_transfer.py` | 草稿、反向大纲、保守文风迁移、引用格式化与最终输出 |
| 七阶段工作流 | `tools/workflow/` | 从材料搜集到最终论文格式化的阶段化编排 |
| Web/API | `app/app.py` | Flask API，重模块采用 lazy service，避免导入阶段触发重依赖 |

## 七阶段工作流

1. `collect`: 搜集材料
2. `organize`: 整理史料、笔记与引文
3. `extract`: OCR/NER/实体关系抽取
4. `examine`: 引文网络、史料考察与逻辑审视
5. `write`: 论文草稿生成
6. `polish`: 学术润色、文风迁移与反向大纲检查
7. `format`: 引文规范化、最终稿与 Word 输出

详细拆分见 [docs/workflow/README.md](docs/workflow/README.md)。

## 安装与启动

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

后端服务:

```powershell
python app\app.py
```

工作流示例:

```powershell
python run_workflow.py
```

运行测试时优先使用:

```powershell
python -m unittest discover tests
```

如需固定 Python 3.11:

```powershell
py -3.11 -m unittest discover tests
```

## 密钥与隐私

本工作区遵循本地优先和最小泄露原则。

- API key、token、账号凭据只允许放入 `secrets/` 或受控的本地密钥管理入口。
- 不在 README、示例、日志、测试报告中写入真实密钥、cookie、原始私密史料全文或可复原的敏感材料。
- 日志只记录路径、统计、摘要、错误类别、后端元数据与复核标记。
- 临时脚本和中间文件完成报告后应归档或删除，不让根目录继续堆积。

完整规范见 [GUIDELINES.md](GUIDELINES.md)。

## 后端扩展原则

后续模块优化允许使用多种后端，但必须回收为统一协议:

- `script`: 纯规则或本地脚本
- `llm_api`: 远程大模型 API
- `local_llm`: 本地部署模型
- `skill`: Codex skill 或同类工作流能力
- `mcp`: MCP 工具或连接器
- `hybrid`: 多后端组合

无论采用哪类后端，结果都应尽量包含:

- `backend`
- `provider`
- `model`
- `confidence`
- `needs_review`
- `capabilities`
- `artifacts`

## 项目结构

```text
app/                  Flask API 与配置层
modules/              OCR、NER、引用、写作、知识库等模块
tools/workflow/        七阶段研究工作流
docs/                 设计文档、指南与案例
docs/workflow/         拆分后的工作流说明
log/feature_development/ 优化报告与阶段日志
tests/                单元测试与集成测试
secrets/              本地密钥与敏感配置，禁止公开
output/               正式输出产物
temp/ tmp/ cache/      临时与缓存目录，使用后应清理
```

## 当前优化方式

所有后续优化都以 `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md` 为锚点推进。若工作中发现新的优化方向，先补写到该文件，再进入实现；每完成一个优化步骤，写入 `log/feature_development/` 下的正式报告，并继续下一步。

## 2026-04-25 Package/Envelope 进展

- `TaskManager.get_task_registry()` / `get_capabilities()` / `execute_task_package()`: 统一任务层现在可输出任务注册表、preset/backend 能力快照与 `task_execution` envelope，供 API、skill、MCP、小模型 agent 以同一协议调用。
- `UnifiedTaskExecutor.execute_package()` / `TaskResult.to_package()` / `write_execution_artifact()`: 底层执行器现在会记录 validation 元数据，并在显式给出路径时写出 `task_execution` JSON artifact；默认不落盘，且拒绝写入 `secrets/`。
- `module_adapters.get_adapter_registry()` / `get_adapter_spec()` / `BaseAdapter.execute_package()`: adapter 层现在公开 alias、主方法、输入契约和 package 入口，减少 API/workflow/agent 对内部方法名的硬编码。
- `ResearchProject.register_package()` / `register_artifact()` / `get_quality_summary()`: 项目状态层现在可统一挂载 package artifacts、quality flags、review queue 与 stage metadata。
- `WorkflowOrchestrator`: 成功 checkpoint 继续登记 artifact；失败阶段现在通过 `workflow_stage_failure` package 统一写入 checkpoint artifact、quality flag、review queue 与 stage metadata。
- `Stage3Extract`: NER 阶段现在保存 `task_layer_snapshot`，并优先通过 `TaskManager.execute_task_package()` 获取 `task_execution` 摘要，旧 `execute_task()` 仍保留兼容 fallback。
- `SecureAPIKeyManager.get_status_report()` / `APIKeyManager.get_status_report()`: 默认输出脱敏状态快照，不暴露真实 key、key hash 或 secrets 绝对路径；内部诊断需显式开启。
- `app.create_app()` / `/api/system/status`: API 层现在提供 app factory 和 lazy service 状态端点，可查看服务初始化状态而不触发 OCR/LLM 等重对象加载。
- `ArtifactManager` / `EnvironmentChecker.build_environment_package()`: 新增托管 root 内 JSON artifact 写入与环境 package 快照；默认不写文件，拒绝 `secrets/` 和 root 外路径。
- `docs/project/OPTIMIZATION_BRANCH_ARCHIVE_2026-04-25.md`: 优化分支归档已完成 manifest 化；仍被测试或动态导入引用的分支文件暂不物理移动。
- `Stage2Organize`: academic note、Obsidian note export 和 graph package 现在会通过 `ResearchProject.register_package()` 登记，vault artifact 走 `register_artifact()`。
- `Stage4Examine`: citation network 与 outline review 结果现在通过 `ResearchProject.register_package()` 登记，review queue 可追踪 package 级复核项。
- `Stage5Write`: field draft package 和统一 `paper_draft` package 会登记到项目状态，source snapshot 与草稿质量标记可被后续 Stage 6/7 消费。
- `Stage6Polish`: `paper_polish`、`style_transfer`、`outline_review` package 现在会通过 `ResearchProject.register_package()` 登记到项目状态，并在 `package_protocol` 中保留注册摘要，便于 API、agent skill 与 Stage 7 继续消费。
- `Stage7Format`: `citation_formatting` package 和 Word 导出 artifact 现在分别通过 `ResearchProject.register_package()` / `register_artifact()` 登记，并在 `package_protocol`、`artifact_protocol` 中保留交接摘要。
- `WorkflowOrchestrator`: checkpoint JSON 现在通过 `ArtifactManager.write_json_artifact()` 写入托管输出根目录，项目层继续登记 `workflow_checkpoint` artifact，便于恢复、审计与 agent 调用。
- `/api/tasks/execute`: API 任务入口现在返回 `TaskManager.execute_task_package()` 生成的 `task_execution` envelope，供前端、MCP、skill 和小模型 agent 使用同一响应结构。
- `optimized/enhanced/integrated` 分支归档：已完成退出准备清单；因仍有测试和动态导入引用，暂不物理移动，详见 `docs/project/OPTIMIZATION_BRANCH_EXIT_PREP_2026-04-25.md`。
- `historyresearch-workspace` skill: 新增 TaskManager/ArtifactManager 只读契约快照脚本，帮助小模型 agent 先读取任务/产物能力摘要，再调用统一 package 接口。

当前新增或贯通的结构化接口包括:

- `PDFImageConverter.convert_range_package()` / `convert_pdf_to_images_package()`: 输出页级图片 artifact、DPI、尺寸、源页映射和复核标记。
- `CitationNetworkAnalyzer.analyze_documents_package()`: 输出引用网络 `records/nodes/edges/summary` 与后端执行元数据。
- `Stage4Examine`: 已优先消费引用网络 package，并回写 `confidence/needs_review/quality_flags`。
- `AcademicSummarizer.generate_full_analysis_package()`: 输出 `academic_analysis` envelope，供摘要、问题、概念和方法抽取链路复用。
- `UnifiedOCRProcessor.process_image_package()`: 输出 `ocr_result` envelope，承接 PDF 图片 artifact。
- `UniversalLayoutAnalyzer.analyze_page_package()` / `analyze_document_package()`: 输出 `layout_page/layout_document`，支持 metadata-only 轻量路径，模型和 PDF 依赖只在显式分析时加载。
- `PDFDateMatcher.parse_annotation_dates_package()` / `match_dates_package()` / `generate_training_data_package()`: 输出 `date_extraction/date_match_pairs/training_samples`，默认离线且不读取配置密钥文件。
- `ClassicalOCRTrainingWorkflow.build_summary_package()` / `build_training_samples_package()`: 古典籍 OCR 训练总线输出 `training_workflow_summary/training_samples`，负责协调版面、日期匹配和样本导出状态。
- `BiographyExtractor.extract_entities_package()` / `process_ocr_results_package()`: 人物传记结构化输出 `biography_entities/biography_batch`，默认离线且不读取 `secrets/`。
- `BiographicalNER.process_text_blocks_package()`: 人物传记专属规则库输出 `biography_entities`，修复导入问题并作为主提取器的轻量规则后端。
- `BiographyPipeline.process_ocr_results_package()` / `build_summary_package()`: 人物传记流程包装层输出 `biography_batch/biography_pipeline_summary`，定位为薄工作流封装。
- `OCRProcessor.extract_text_from_image_package()` / `batch_ocr_package()`: 底层 Tesseract/LLM OCR 兼容入口也输出 OCR envelope。
- `LLMOCRProcessor.build_pages_package()` / `run_package()`: 远程 Qwen-VL OCR 分支回收为 OCR envelope。
- `NDLOCRLiteProcessor.process_image_package()` / `process_directory_package()`: 本地 NDL OCR-Lite 分支回收为 OCR envelope。
- `NDLKotenOCRLiteProcessor.process_image_package()` / `process_directory_package()`: 古典 OCR-Lite 分支回收为 OCR envelope。
- `NDLOCRResultProcessor.process_result_package()` / `batch_process_package()`: OCR 后处理结果回收为 `processed_ocr_result` envelope。
- `NDLOCRBatchProcessor.process_batch_package()`: 批量 NDL OCR 入口输出 `ocr_batch`，并在引擎不可用时结构化降级。
- `LLMClient(provider="ollama")`: 本地 Ollama 接入已支持 `/v1` URL 归一、短 smoke、空输出质量标记和 `local_llm` 元数据。
- `TaskManager` 的 `summary_local_small` preset: 用于小参数 Ollama 模型的低 token 摘要 smoke，并支持 `local_llm -> script` 降级。
- `AcademicNoteGenerator.generate_reading_note_package()` / `batch_process_package()`: 学术笔记输出 `academic_note/academic_note_batch`，Stage 2 已记录 note package 摘要。
- `ObsidianIntegration.create_note_package()` / `build_knowledge_graph_package()`: vault 输出收口为本地文件系统安全写入、frontmatter、双链与 graph scan，Stage 2 已记录 vault package 摘要。
- `HistoricalSpeechExtractor.process_ocr_result_package()` / `analyze_text_package()`: 历史发言、日期与实体附着输出 `historical_speech_analysis`，便于 OCR/NER 后续闭环消费。
- `EmbeddingManager.create_vector_index_package()` / `semantic_search_package()`: 嵌入检索默认走轻量 mock fallback，避免小模型/agent 调用时触发重依赖或外网模型加载。
- `HistoryFieldExplorer.explore_package()` / `draft_paper_package()`: 研究入门与草稿生成输出 `field_research/field_draft`，Stage 5 已记录 field draft package 摘要。
- `CitationFormatter.format_record_package()` / `format_batch_package()`: 引用格式层输出 `citation_formatting`，Stage 7 已记录 citation format package 摘要。
- `HistoricalCitationVerifier.parse_docx_package()` / `verify_docx_package()`: 历史引文核验输出 `historical_citation_parse/historical_citation_verification`，默认解析离线，外部检索和下载需显式开启。
- `HistoricalCitationWorkspaceInterface` / `HistoricalCitationAdapter`: 在不修改原历史引文模块的前提下，新增工作区安全外壳与统一任务入口 `historical_citation`；默认只做离线 DOCX 解析，`search_ndl/download_source/restricted_download` 必须显式开启，返回路径已脱敏的 `historical_citation_workspace_package`。
- `/api/doc/historical-citation-package`: 面向前端、MCP、skill 和小模型 agent 的历史引文统一 package 端点；旧 `/api/doc/verify-historical-citations` 保留兼容，不改变原返回结构。
- `PaperPolisher.polish_text_package()` / `polish_paragraph_package()`: 写作润色输出 `paper_polish`，Stage 6 已记录 package 类型与质量标记。
- `ReverseOutlineAnalyzer.analyze_package()`: 反向大纲审校输出 `outline_review`，Stage 6 已记录 package 类型与质量标记。
- `StyleTransfer.transfer_style_package()`: 保守文风迁移输出 `style_transfer`，Stage 6 已记录 package 类型与质量标记。
- `NERProcessor.recognize_historical_entities_package()`: 输出 `ner_extraction` envelope，支持后续 script/LLM/local/skill/MCP 统一回收。
- `NERDisambiguation.disambiguate_package()` / `EntityDisambiguator.batch_disambiguate_package()`: NER 后处理输出 `entity_disambiguation`，Stage 3 已记录规范名、类型变化、低置信和未知规则摘要。
- `Stage3Extract` 与 `Stage5Write`: 已把 NER package 写入阶段摘要，并由写作阶段 source snapshot 消费。

这些接口均保留旧 API 兼容层；新 workflow 实现应优先消费 package/envelope，并把质量标记写入 `stage_metadata`、`quality_flags` 或 `review_queue`。
