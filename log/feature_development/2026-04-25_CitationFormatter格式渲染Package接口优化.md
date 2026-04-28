# CitationFormatter 格式渲染 Package 接口优化报告

## 基本信息

- 日期: 2026-04-25
- 模块: `modules/citation_formats.py`
- 工作流: `tools/workflow/stages/stage7_format.py`
- 设计锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

## 优化目标

- 将引用格式层收口为纯渲染层，不承担解析和规范化校验职责。
- 为单条和批量 citation record 渲染提供统一 package 输出。
- 让 Stage 7 记录引用格式渲染摘要，方便审计目标格式、渲染数量和缺失字段质量标记。

## 主要改动

- 新增 `get_capabilities()`，声明支持格式、纯本地模板后端和 package 输出能力。
- 新增 `format_record_package()`，输出单条 `citation_formatting` envelope。
- 新增 `format_batch_package()`，输出批量 `citation_formatting` envelope。
- Stage 7 新增 `execution_summary.citation_format_package`，记录格式层执行摘要。

## 验证结果

- `python -m py_compile modules\citation_formats.py tools\workflow\stages\stage7_format.py tests\test_citation_formats_package.py tests\test_stage7_format_chain.py`
- `python -m unittest tests.test_citation_formats_package tests.test_stage7_format_chain tests.test_citation_chain`
- `py -3.11 -m unittest tests.test_citation_formats_package tests.test_history_field_explorer_facade tests.test_stage5_stage6_writing_chain tests.test_ner_disambiguation_package tests.test_embedding_manager_package tests.test_historical_speech_extractor_package tests.test_obsidian_integration_package tests.test_style_transfer_package tests.test_style_transfer_facade tests.test_reverse_outline_package tests.test_paper_polisher_package tests.test_academic_note_generator_package tests.test_stage2_note_chain tests.test_llm_client_ollama tests.test_unified_framework tests.test_ndl_ocr_batch_processor_package tests.test_ndlocr_result_processor_package tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package tests.test_llm_ocr_processor_package tests.test_ocr_processor_package tests.test_unified_ocr_package tests.test_ocr_ner_integration tests.test_ner_processor_package tests.test_stage3_workflow_integration tests.test_stage7_format_chain tests.test_pdf_image_converter_package tests.test_pdf_processor_package tests.test_citation_network_package tests.test_workflow_orchestrator_stage4 tests.test_academic_summarizer_package tests.test_data_structurer_schema tests.test_book_citation_organizer_facade tests.test_doc_processor_package tests.test_citation_chain tests.test_citation_normalizer_schema`
- 结果: 7 个目标测试通过；109 个宽回归测试通过。

## 隐私与归档

- 未读取或写入 `secrets/`。
- 测试使用本地 citation record，不调用真实 API。
- 未生成需要额外归档删除的临时脚本。

## 后续建议

- Stage 2 与 Stage 7 后续都应优先传递统一 citation record，再由 `citation_formats.py` 负责目标格式渲染。
- `citation_normalizer.py` 可继续承担解析、字段补全、校验和 review 标记，不应回流到格式层。
