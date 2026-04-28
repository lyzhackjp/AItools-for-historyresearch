# ClassicalOCRTrainingWorkflow 训练总线 Package 接口优化报告

## 基本信息

- 日期: 2026-04-25
- 模块: `modules/classical_ocr_training_workflow.py`
- 测试: `tests/test_classical_ocr_training_workflow_package.py`
- 设计锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

## 优化目标

- 将古典籍 OCR 训练准备总线从长流程脚本入口收口为可被 agent/skill/MCP 探测和包装的协调层。
- 保留旧流程兼容，同时补充 `training_workflow_summary/training_samples` package 输出。
- 避免模块导入阶段因 PDF、图像或模型依赖缺失而失败。

## 主要改动

- 新增 `get_capabilities()`，声明训练准备层、输出类型、fallback 顺序、可选依赖和缺失模型。
- 新增 `build_summary_package()`，将已有 `ProcessingResult` 列表包装为 `training_workflow_summary` envelope。
- 新增 `build_training_samples_package()`，将已有训练样本包装为 `training_samples` envelope，默认不写 artifact。
- `fitz/numpy/PIL` 改为可选导入；真实 PDF/图像处理缺依赖时返回结构化失败结果。

## 验证结果

- `python -m py_compile modules\classical_ocr_training_workflow.py tests\test_classical_ocr_training_workflow_package.py`
- `python -m unittest tests.test_classical_ocr_training_workflow_package`
- `py -3.11 -m unittest tests.test_classical_ocr_training_workflow_package tests.test_pdf_date_matcher_package tests.test_universal_layout_analyzer_package tests.test_historical_citation_verifier tests.test_citation_formats_package tests.test_history_field_explorer_facade tests.test_stage5_stage6_writing_chain tests.test_ner_disambiguation_package tests.test_embedding_manager_package tests.test_historical_speech_extractor_package tests.test_obsidian_integration_package tests.test_style_transfer_package tests.test_style_transfer_facade tests.test_reverse_outline_package tests.test_paper_polisher_package tests.test_academic_note_generator_package tests.test_stage2_note_chain tests.test_llm_client_ollama tests.test_unified_framework tests.test_ndl_ocr_batch_processor_package tests.test_ndlocr_result_processor_package tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package tests.test_llm_ocr_processor_package tests.test_ocr_processor_package tests.test_unified_ocr_package tests.test_ocr_ner_integration tests.test_ner_processor_package tests.test_stage3_workflow_integration tests.test_stage7_format_chain tests.test_pdf_image_converter_package tests.test_pdf_processor_package tests.test_citation_network_package tests.test_workflow_orchestrator_stage4 tests.test_academic_summarizer_package tests.test_data_structurer_schema tests.test_book_citation_organizer_facade tests.test_doc_processor_package tests.test_citation_chain tests.test_citation_normalizer_schema`
- 结果: 3 个定向测试通过；168 个宽回归测试通过，2 个旧可选依赖用例跳过。

## 隐私与归档

- 未读取或写入 `secrets/`。
- 测试使用内存中的 `ProcessingResult` 与 `TrainingSample`，不调用真实 PDF、ONNX 模型或外部 API。
- 未生成需要额外归档删除的临时脚本。

## 后续建议

- 后续可让该总线直接消费 `UniversalLayoutAnalyzer` 的 `layout_page` 和 `PDFDateMatcher` 的 `date_match_pairs/training_samples` package。
- 若接入本地大模型、skill 或 MCP 的训练样本筛选后端，仍应回收到同一 package schema。
