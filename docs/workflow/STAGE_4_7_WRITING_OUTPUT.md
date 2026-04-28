# Stage 4-7: 考察、写作与输出链

## Stage 4 examine

目标: 对实体、引文和材料关系进行史料考察、引文网络分析和逻辑审视。

主模块:

- `modules/citation_network_analyzer.py`
- `modules/reverse_outline_analyzer.py`

输出要求:

- 标准 `nodes/edges/records/summary/confidence`。
- 关键来源、孤立节点、低置信关系进入复核队列。
- 不把规则判断包装成确定结论，必须保留置信度。

## Stage 5 write

目标: 根据项目状态生成论文草稿。

要求:

- 草稿应引用前序阶段的 notes、entities、citations 和 key sources。
- 中英/中日双语输出必须保留原始论证结构，不应让翻译覆盖源段落。
- 生成结果需要写回 `paper_draft` 与阶段摘要。

## Stage 6 polish

目标: 学术润色、保守文风迁移、反向大纲检查。

主模块:

- `modules/paper_polisher.py`
- `modules/style_transfer.py`
- `modules/reverse_outline_analyzer.py`

要求:

- `StyleTransfer` 优先输出可复核建议或保守改写，不强行改写史学术语和论证结构。
- `PaperPolisher` 优先输出 `paper_polish` package，保留旧段落和 DOCX 接口兼容。
- 低置信度润色或风格迁移结果写入 `review_queue`。
- 阶段摘要包含压缩率、修改数、风格后端、逻辑问题数量。

## Stage 7 format

目标: 引文规范化、最终稿、Word 输出。

主模块:

- `modules/citation_normalizer.py`
- `modules/citation_formats.py`
- `tools/workflow/word_exporter.py`

要求:

- 引文解析、校验、规范化、渲染职责分开。
- 输出目标格式包括 Chicago、APA、GB/T 7714、MLA、IEEE、Harvard 等。
- 最终稿 artifact 必须记录路径、格式、生成时间和复核状态。

## 2026-04-25 引用网络 Envelope 更新

- `modules/citation_network_analyzer.py` 现在提供 `analyze_documents_package()`。
- Stage 4 后续应优先读取该 package 的 `records/nodes/edges/graph/summary/confidence/needs_review/quality_flags`。
- 若出现 `no_documents`、`no_citation_edges`、`all_documents_isolated` 或 `low_average_edge_confidence`，应写入 `stage_metadata` 与 `review_queue`，不应被当作确定结论进入写作阶段。
- 如后续接入 LLM API、本地大模型、skill 或 MCP 引文抽取服务，必须回收为同一 envelope。

## 2026-04-25 Stage 5 Source Snapshot 更新

- Stage 5 的 `source_snapshot` 现在会读取 Stage 3 `ner_extraction` packages。
- 新增字段包括 `ner_package_count`、`ner_packages_needing_review`、`ner_backends`、`ner_quality_flags`。
- 写作和润色阶段后续应使用这些字段判断实体来源是否可靠，避免低置信度实体未经复核进入确定性论述。

## 2026-04-25 Stage 6 Paper Polish Package 更新

- `modules/paper_polisher.py` 现在提供 `polish_text_package()`、`polish_paragraph_package()` 与 `process_document_package()`。
- `paper_polish` package 包含 `polished_text/revision_notes/backend/provider/model/confidence/needs_review/quality_flags/statistics`。
- Stage 6 现在优先消费 `polish_text_package()`，并在 `stage_metadata.execution_summary.paper_polish` 中记录 `package_type` 与 `quality_flags`。
- 后续 `style_transfer.py` 与 `reverse_outline_analyzer.py` 应继续对齐该写作链 package 协议。

## 2026-04-25 Stage 6 Reverse Outline Package 更新

- `modules/reverse_outline_analyzer.py` 现在提供 `analyze_package()`。
- `outline_review` package 包含 `section_word_counts/section_ratios/logical_gaps/deviation_flags/suggestions/backend/provider/model/confidence/needs_review/quality_flags`。
- Stage 6 现在优先消费 `outline_review` package，并在 `stage_metadata.execution_summary.reverse_outline` 中记录 `package_type` 与 `quality_flags`。
- 短草稿、缺失章节、结构失衡、fallback 后端或低置信度审校必须进入复核链。

## 2026-04-25 Stage 6 Style Transfer Package 更新

- `modules/style_transfer.py` 现在提供 `transfer_style_package()`。
- `style_transfer` package 包含 `original_text/rewritten_text/style_analysis/target_style/backend/provider/model/confidence/needs_review/quality_flags/statistics`。
- Stage 6 现在优先消费 `style_transfer` package，并在 `stage_metadata.execution_summary.style_transfer` 中记录 `package_type` 与 `quality_flags`。
- 文风迁移必须保持保守；空输出、长度异常、fallback 后端、低置信或激进改写风险必须进入复核链。

## 2026-04-25 Stage 6 Project Package Registry Update

- Stage 6 registers `paper_polish`, `style_transfer`, and `outline_review` envelopes through `ResearchProject.register_package()`.
- `stage_metadata.package_protocol` records `registry`, `registered_package_count`, and compact `registered_packages` summaries.
- Low-confidence polish, style transfer, and reverse-outline results therefore enter the same quality/review queue contract used by Stage 2, Stage 4, and Stage 5.

## 2026-04-25 Field Draft Package 更新

- `modules/history_field_explorer.py` 现在提供 `explore_package()` 与 `draft_paper_package()`。
- package 类型为 `field_research` 与 `field_draft`，统一记录 `backend/provider/model/confidence/needs_review/quality_flags/export_summary`。
- Stage 5 在可用时优先消费 `field_draft` package，并把摘要写入 `stage_metadata.execution_summary.draft_package`。
- 后续拆分 `FieldSearch`、`FieldSynthesis`、`FieldDrafting` 时，应保持 package schema 稳定，避免写作阶段绑定内部实现。

## 2026-04-25 Citation Formatting Package 更新

- `modules/citation_formats.py` 现在提供 `get_capabilities()`、`format_record_package()` 与 `format_batch_package()`。
- package 类型为 `citation_formatting`，统一记录 `rendered/summary/backend/provider/model/style/confidence/needs_review/quality_flags`。
- Stage 7 在规范化 citation record 后记录 `execution_summary.citation_format_package`，用于审计引用格式渲染数量、缺失字段和目标格式。
- 格式层只做渲染，不做解析和规范化校验；解析和校验仍由 `citation_normalizer.py` 承担。

## 2026-04-25 Stage 7 Project Registry Update

- Stage 7 now registers the `citation_formatting` package through `ResearchProject.register_package()`.
- Word export outputs are registered through `ResearchProject.register_artifact()` instead of ad-hoc artifact appends.
- `stage_metadata.package_protocol` and `artifact_protocol` keep compact handoff summaries for final-output auditing.

## 2026-04-25 Historical Citation Verifier Package 更新

- `modules/historical_citation_verifier.py` 现在提供 `get_capabilities()`、`parse_docx_package()` 与 `verify_docx_package()`。
- package 类型为 `historical_citation_parse` 与 `historical_citation_verification`，统一记录 `document/footnotes/candidates/results/artifacts/backend/provider/model/confidence/needs_review/quality_flags`。
- 默认 `parse_docx_package()` 只执行本地 DOCX 脚注解析和候选构建，不触发外部检索、下载或 OCR。
- Stage 4 后续接入历史引文核验时，应由调用方显式决定是否启用 NDL/Japan Search/Internet Archive 检索、受限下载或 OCR，并把 source mismatch、source not found、download failed 等质量标记写入复核链。

## 2026-04-28 Historical Citation Workspace Interface 更新

- 不再直接扩写 `modules/historical_citation/` 或 `modules/historical_citation_verifier.py` 作为工作区集成层；新增集成只走 `modules/historical_citation_workspace.py`。
- 统一任务层新增 `historical_citation` / `history_citation`，输出 `historical_citation_workspace_package`，并保留原模块的 `historical_citation_parse/historical_citation_verification` 作为 `data`。
- API 新增 `/api/doc/historical-citation-package`，默认 `action=parse`、`search_ndl=false`、`download_source=false`、`restricted_download=false`，适合前端、skill、MCP 和小模型 agent 先做离线能力闭环。
- 工作流 Stage 4 若要进行史料出处核验，应优先登记 workspace package 的 `confidence/needs_review/quality_flags/privacy/options`，再把原 verifier 结果作为内部数据消费；不得让受限下载或外部平台检索在未显式授权时自动启动。
