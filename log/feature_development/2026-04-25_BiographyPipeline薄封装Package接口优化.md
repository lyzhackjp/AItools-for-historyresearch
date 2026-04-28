# BiographyPipeline 薄封装 Package 接口优化报告

## 基本信息

- 日期: 2026-04-25
- 模块: `modules/biography_pipeline.py`
- 测试: `tests/test_biography_pipeline_package.py`
- 设计锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

## 优化目标

- 将人物传记流程包装层收口为薄工作流封装。
- 让 OCR result 能直接回收到 `biography_batch` package。
- 避免导入阶段因 PDF 转图依赖 `fitz` 而失败。

## 主要改动

- 新增 `get_capabilities()`，声明薄封装定位、fallback 顺序和隐私边界。
- 新增 `process_ocr_results_package()`，将 OCR result 转为文本块并委托 `BiographicalNER` package。
- 新增 `build_summary_package()`，输出 `biography_pipeline_summary`。
- `convert_pdf_to_images` 改为 `run()` 内延迟导入。

## 验证结果

- `python -m py_compile modules\biography_pipeline.py tests\test_biography_pipeline_package.py`
- `python -m unittest tests.test_biography_pipeline_package`
- `py -3.11 -m unittest tests.test_biography_pipeline_package tests.test_biographical_ner_package tests.test_biography_extractor_package tests.test_classical_ocr_training_workflow_package tests.test_pdf_date_matcher_package tests.test_universal_layout_analyzer_package tests.test_historical_citation_verifier tests.test_citation_formats_package tests.test_history_field_explorer_facade tests.test_stage5_stage6_writing_chain tests.test_ner_disambiguation_package tests.test_embedding_manager_package tests.test_historical_speech_extractor_package tests.test_obsidian_integration_package tests.test_style_transfer_package tests.test_style_transfer_facade tests.test_reverse_outline_package tests.test_paper_polisher_package tests.test_academic_note_generator_package tests.test_stage2_note_chain tests.test_llm_client_ollama tests.test_unified_framework tests.test_ndl_ocr_batch_processor_package tests.test_ndlocr_result_processor_package tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package tests.test_llm_ocr_processor_package tests.test_ocr_processor_package tests.test_unified_ocr_package tests.test_ocr_ner_integration tests.test_ner_processor_package tests.test_stage3_workflow_integration tests.test_stage7_format_chain tests.test_pdf_image_converter_package tests.test_pdf_processor_package tests.test_citation_network_package tests.test_workflow_orchestrator_stage4 tests.test_academic_summarizer_package tests.test_data_structurer_schema tests.test_book_citation_organizer_facade tests.test_doc_processor_package tests.test_citation_chain tests.test_citation_normalizer_schema`
- 结果: 3 个定向测试通过；178 个宽回归测试通过，2 个旧可选依赖用例跳过。

## 隐私与归档

- 未读取或写入 `secrets/`。
- 定向测试使用内存 OCR result，不调用真实 PDF、OCR、LLM 或外部 API。
- 未生成需要额外归档删除的临时脚本。

## 后续建议

- 后续完整人物传记流程应按 `ocr_result -> biography_batch -> export` 串联。
- `BiographyPipeline` 不应继续扩张实体规则，实体 schema 应由 `BiographyExtractor/BiographicalNER` 维护。
