# HistoricalCitationVerifier 引文核验 Package 接口优化报告

## 基本信息

- 日期: 2026-04-25
- 模块: `modules/historical_citation_verifier.py`
- 测试: `tests/test_historical_citation_verifier.py`
- 设计锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

## 优化目标

- 为历史引文核验器补充小模型 agent、skill、MCP 可发现的能力快照。
- 将 DOCX 脚注解析、候选构建和完整核验结果包装为统一 package。
- 保持旧接口兼容，同时让默认解析路径不触发外部检索、下载或 OCR。

## 主要改动

- 新增 `get_capabilities()`，声明输入格式、输出 package、来源平台、fallback 顺序和隐私边界。
- 新增 `parse_docx_package()`，输出 `historical_citation_parse` envelope，包含 document、paragraphs、footnotes、candidates、summary 与质量标记。
- 新增 `verify_docx_package()`，包装旧 `verify_docx()` 结果为 `historical_citation_verification` envelope，记录 execution 参数、artifacts 与复核信号。
- 测试中旧版 NDL browser client 用例在缺少 `selenium` 时改为跳过，以适配轻量开发环境。

## 验证结果

- `python -m py_compile modules\historical_citation_verifier.py tests\test_historical_citation_verifier.py`
- `python -m unittest tests.test_historical_citation_verifier`
- `py -3.11 -m unittest tests.test_historical_citation_verifier tests.test_citation_formats_package tests.test_history_field_explorer_facade tests.test_stage5_stage6_writing_chain tests.test_ner_disambiguation_package tests.test_embedding_manager_package tests.test_historical_speech_extractor_package tests.test_obsidian_integration_package tests.test_style_transfer_package tests.test_style_transfer_facade tests.test_reverse_outline_package tests.test_paper_polisher_package tests.test_academic_note_generator_package tests.test_stage2_note_chain tests.test_llm_client_ollama tests.test_unified_framework tests.test_ndl_ocr_batch_processor_package tests.test_ndlocr_result_processor_package tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package tests.test_llm_ocr_processor_package tests.test_ocr_processor_package tests.test_unified_ocr_package tests.test_ocr_ner_integration tests.test_ner_processor_package tests.test_stage3_workflow_integration tests.test_stage7_format_chain tests.test_pdf_image_converter_package tests.test_pdf_processor_package tests.test_citation_network_package tests.test_workflow_orchestrator_stage4 tests.test_academic_summarizer_package tests.test_data_structurer_schema tests.test_book_citation_organizer_facade tests.test_doc_processor_package tests.test_citation_chain tests.test_citation_normalizer_schema`
- 结果: 48 个定向测试通过，其中 3 个可选依赖用例因当前环境缺少 `selenium/PIL` 跳过；157 个宽回归测试通过，其中 2 个旧可选依赖用例跳过。

## 隐私与归档

- 未读取或写入 `secrets/`。
- 新增 package 测试使用本地合成 DOCX 与 dummy source adapter，不调用真实外部 API。
- 未生成需要额外归档删除的临时脚本。

## 后续建议

- Stage 4 后续可优先消费 `historical_citation_parse` 做本地候选审计，再由用户或任务层显式决定是否开启外部来源检索。
- 若引入 LLM API、本地大模型、skill 或 MCP 辅助对齐，仍应回收到 `historical_citation_verification` envelope。
