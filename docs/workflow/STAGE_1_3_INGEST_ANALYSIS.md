# Stage 1-3: 摄入与分析主链

## Stage 1 collect

目标: 根据研究主题搜集候选材料、论文、开源项目或外部书目信息。

当前方向:

- 搜索能力后续逐步收口到统一研究助手或任务层。
- 结果应转为标准 literature record，而不是只保存自由文本。
- 搜索来源、后端、时间和检索词要写入阶段元数据。

## Stage 2 organize

目标: 整理文献、扫描书籍、笔记、引用格式与 Obsidian 输出。

主模块:

- `modules/academic_note_generator.py`
- `modules/obsidian_integration.py`
- `modules/book_citation_organizer.py`
- `modules/citation_normalizer.py`
- `modules/citation_formats.py`

优化方向:

- 书籍元数据、note、citation record 使用可互相转换的 schema。
- vault 输出只负责安全写入、frontmatter、双链和 graph scan，不承担内容生成。
- citation formatter 只做渲染，不混入解析和校验。
- 学术笔记生成应优先消费 `academic_note` package，并把后端、置信度、复核标记和导出摘要写回阶段元数据。

## Stage 3 extract

目标: 对 PDF、图像、OCR 文本或原文材料执行 OCR、NER、实体关系抽取和消歧。

主模块:

- `modules/unified_ocr_processor.py`
- `modules/ner_processor.py`
- `modules/ner_disambiguation.py`

后端选项:

- 本地 OCR / NDL OCR / Tesseract
- 远程视觉模型 OCR
- 规则 NER
- LLM API NER
- 本地 LLM NER
- skill / MCP / hybrid 后端

统一要求:

- OCR 输出页级、块级、文本级结构。
- NER 输出实体、关系、置信度、来源位置和复核标记。
- Stage 3 必须把后端选择和质量摘要写回 `stage_metadata`。

## 2026-04-25 摄入 Artifact 更新

- `modules/pdf_image_converter.py` 现在提供 `convert_range_package()`、`convert_all_package()` 与 `convert_pdf_to_images_package()`。
- Stage 3/OCR 入口后续应优先消费结构化 `pdf_image_conversion` envelope，而不是只读取图片路径列表。
- 每个图片 artifact 应保留 `path/page_number/page_index/dpi/format/width/height/source_page_size`，方便 OCR、版面分析、复核队列和恢复执行对齐同一页。
- 旧的 `convert_pdf_to_images()` 仍可用于兼容脚本，但新工作流不应再把散落路径作为唯一状态。

## 2026-04-25 学术分析 Package 更新

- `modules/academic_summarizer.py` 现在提供 `generate_full_analysis_package()`。
- Stage 2/Stage 3 若需要摘要、问题、概念或方法抽取，应优先记录 `academic_analysis` envelope。
- 该 package 的 `quality_flags` 可直接进入后续 source snapshot 或 review queue，避免短文本、空文本或缺失结构被当作可靠分析结果。

## 2026-04-25 Stage 3 NER Package 更新

- Stage 3 现在在 `stage_metadata.execution_summary.packages` 中记录 `ner_extraction` 摘要。
- 每个摘要包含 `source_kind/source_id/source_title/backend/provider/model/confidence/needs_review/quality_flags/categories`。
- 后续写作和复核阶段应读取该列表，而不是只读取最终合并后的实体集合。
- `modules/ner_processor.py` 已提供同构模块级 package 接口，Stage 3 后续可逐步从阶段内拼装迁移到模块级 package 消费。

## 2026-04-25 OCR Package 更新

- `modules/unified_ocr_processor.py` 现在提供 `process_image_package()` 与 `process_directory_package()`。
- `modules/ocr_processor.py` 也提供底层 `extract_text_from_image_package()`、`extract_text_from_bytes_package()`、`batch_ocr_package()` 与 `llm_ocr_package()`。
- `modules/llm_ocr_processor.py` 提供 `build_pages_package()` 与 `run_package()`，远程大模型 OCR 结果也必须回收为 `ocr_result`。
- `modules/ndlocr_lite.py` 提供 `process_image_package()` 与 `process_directory_package()`，本地 NDL OCR-Lite 结果也必须回收为 `ocr_result/ocr_batch`。
- `modules/ndlkotenocr_lite.py` 提供同构 package 接口，古典 OCR 结果也必须回收为 `ocr_result/ocr_batch`。
- `modules/ndlocr_result_processor.py` 提供 `processed_ocr_result/processed_ocr_batch`，用于记录清洗后的文本、结构和统计。
- `modules/ndl_ocr_batch_processor.py` 提供 `process_batch_package()`，批量 NDL OCR 可输出 `ocr_batch`，且在本地引擎不可用时返回结构化降级结果而不是中断初始化。
- OCR package 类型为 `ocr_result` 或 `ocr_batch`，包含 `source_path/text/pages/structures/artifacts/backend/provider/model/confidence/needs_review/quality_flags`。
- 建议后续 Stage 3 链路按 `pdf_image_conversion.artifacts[] -> ocr_result -> ner_extraction` 串联，而不是在阶段间传递裸路径或裸文本。

## 2026-04-25 Layout Package 更新

- `modules/universal_layout_analyzer.py` 现在提供 `get_capabilities()`、`analyze_page_package()` 与 `analyze_document_package()`。
- package 类型为 `layout_page/layout_document`，统一记录 `pages/regions/document_type/backend/provider/model/confidence/needs_review/quality_flags`。
- metadata-only 路径不加载 ONNX、PDF 或图像重依赖，便于小模型 agent 先探测能力和页面尺寸；真实模型分析必须显式 `use_models=True`。
- 后续 OCR/训练准备链路应按 `pdf_image_conversion -> layout_page -> ocr_result` 串联，避免版面分析结果只存在于临时脚本或散落 JSON。

## 2026-04-25 PDF Date Matcher Package 更新

- `modules/pdf_date_matcher.py` 现在提供 `get_capabilities()`、`parse_annotation_dates_package()`、`match_dates_package()` 与 `generate_training_data_package()`。
- package 类型为 `date_extraction/date_match_pairs/training_samples`，统一记录 `dates/matched_pairs/samples/backend/provider/model/confidence/needs_review/quality_flags`。
- 默认初始化不读取 `config/api_key.txt` 或 `config/api_config.json`，只在调用方显式 `auto_load_api_key=True` 或传入 `api_key` 时进入远程 LLM 日期识别路径。
- 后续古典籍训练准备链路应按 `pdf_image_conversion -> layout_page -> date_match_pairs -> training_samples` 串联，并把无日期、无匹配、未保存 artifact 等情况写入复核链。

## 2026-04-25 Classical OCR Training Workflow Package 更新

- `modules/classical_ocr_training_workflow.py` 现在提供 `get_capabilities()`、`build_summary_package()` 与 `build_training_samples_package()`。
- package 类型为 `training_workflow_summary/training_samples`，统一记录 `results/samples/current_stage/backend/provider/model/confidence/needs_review/quality_flags`。
- 该模块定位为训练准备总线，后续应优先协调 `layout_page`、`date_match_pairs` 与 `training_samples` package，而不是让长流程直接成为唯一状态来源。
- `fitz/numpy/PIL` 已改为可选导入；真实 PDF/图像处理缺依赖时返回结构化失败结果，导入和能力探测不应失败。

## 2026-04-25 Biography Extractor Package 更新

- `modules/biography_extractor.py` 现在提供 `get_capabilities()`、`extract_entities_package()` 与 `process_ocr_results_package()`。
- package 类型为 `biography_entities/biography_batch`，统一记录 `persons/summary/backend/provider/model/confidence/needs_review/quality_flags`。
- 默认初始化不读取 `secrets/`，且 PDF 转图、NDL OCR、LLM OCR 均延迟到真实执行时加载。
- 后续人物传记链路应按 `ocr_result -> biography_batch` 串联；若接入本地大模型、skill 或 MCP 做人物结构化，仍必须回收到同一 package schema。

## 2026-04-25 Biographical NER Package 更新

- `modules/biographical_ner.py` 现在提供 `get_capabilities()`、`process_text_blocks_package()` 与 `extract_biographical_entities_package()`。
- 该模块定位为人物传记专属离线规则库，输出 `biography_entities` package，供 `BiographyExtractor` 或薄 pipeline 调用。
- 已修复 `WorkExperience.position` 语法问题，并放宽姓名提取到逐行 2-5 字匹配，避免多行传记块漏识别姓名。
- 后续不应在该规则库内引入 OCR、LLM 或文件导出逻辑；多后端能力应由主提取器或统一任务层负责。

## 2026-04-25 Biography Pipeline Package 更新

- `modules/biography_pipeline.py` 现在提供 `get_capabilities()`、`process_ocr_results_package()` 与 `build_summary_package()`。
- package 类型为 `biography_batch/biography_pipeline_summary`，统一记录 `persons/source_package/summary/backend/provider/model/confidence/needs_review/quality_flags`。
- 该模块定位为薄工作流封装，PDF 转图改为延迟导入，导入和 package 处理不依赖 `fitz`。
- 后续完整人物传记流程应按 `ocr_result -> biography_batch -> export` 串联；实体 schema 由 `BiographyExtractor/BiographicalNER` 维护。

## 2026-04-25 AI Agent Skill 更新

- 工作区已新增 `docs/agent_skills/historyresearch-workspace/` 作为 AI agent 专属 skill 脚手架。
- 后续 agent 在优化模块前应先读取该 skill 的核心流程，并按需读取隐私、package、workflow 与模块映射参考。
- Skill 目前先作为工作区内可审查设计；确认稳定后再安装到本地 Codex skill 目录。
- Skill 已补充 playbook、acceptance checklist 与只读校验脚本，便于小模型 agent 按固定流程执行。

## 2026-04-25 Stage 2 Note Package 更新

- `modules/academic_note_generator.py` 现在提供 `generate_reading_note_package()` 与 `batch_process_package()`。
- Stage 2 现在优先消费 `academic_note` package，并在 `stage_metadata.execution_summary.note_packages` 中记录每篇笔记的后端、模型、置信度、复核状态、质量标记和导出摘要。
- 后续 Obsidian/vault 输出应继续消费规范化 note 记录，避免直接绑定某个 LLM 后端的原始输出。

## 2026-04-25 Stage 2 Obsidian Vault Package 更新

- `modules/obsidian_integration.py` 现在提供 `create_note_package()`、`update_note_package()`、`build_knowledge_graph_package()` 与 `export_notes_to_json_package()`。
- Stage 2 现在优先消费 `obsidian_note_export` package，并在 `vault_export.vault_packages` 中记录每篇笔记的路径、后端、置信度、复核状态、质量标记和导出摘要。
- vault 集成层只负责本地安全写入、frontmatter、双链扫描和 graph scan；内容生成仍由上游 note/LLM/skill 模块负责。
- 所有 vault 读写路径必须解析到托管 vault 内部；路径穿越或 vault 外绝对路径进入复核标记，不得被当作成功写入。

## 2026-04-25 Historical Speech Package 更新

- `modules/historical_speech_extractor.py` 现在提供 `get_capabilities()`、`process_ocr_result_package()` 与 `analyze_text_package()`。
- package 类型为 `historical_speech_analysis`，统一承载 `records/statistics/publication_info/source_summary/backend/provider/model/confidence/needs_review/quality_flags`。
- 该接口先稳定外部契约，后续可继续把内部实现拆为 `SpeechSegmenter`、`DateResolver` 与 `EntityAttach`，不影响 Stage 3 或 agent 调用方。
- 若 OCR 页为空、未检测到发言、日期或实体，结果会进入复核标记，而不是被当作完整分析。

## 2026-04-25 Embedding Package 更新

- `modules/embedding_manager.py` 现在提供 `get_capabilities()`、`create_vector_index_package()` 与 `semantic_search_package()`。
- package 类型为 `embedding_index` 与 `semantic_search`，统一记录 `backend/provider/model/confidence/needs_review/quality_flags/index/search_summary`。
- 默认 `auto_load_models=False`，建索引时使用确定性 mock embedding，不自动触发 sentence-transformers、OpenAI、Ollama 或其它重依赖加载。
- 若需要真实本地模型或远程 API，调用方必须显式 `load_embedding_model()` 或在 package 接口中设置 `force_load_model=True`。

## 2026-04-25 NER Disambiguation Package 更新

- `modules/ner_disambiguation.py` 现在提供 `get_capabilities()`、`batch_disambiguate_package()`、`disambiguate_package()` 与 `resolve_relations_package()`。
- package 类型为 `entity_disambiguation`，统一记录 `entities/summary/backend/provider/model/confidence/needs_review/quality_flags`。
- Stage 3 在语言非英文且实体消歧可用时优先记录 `execution_summary.disambiguation_packages`，供后续复核和写作阶段识别规范名、类型变化、未知规则和低置信结果。
- 消歧层保持本地规则优先，不调用外部 API；后续可接入别名库、本地模型或 MCP 知识库，但仍需回收为同一 package。
