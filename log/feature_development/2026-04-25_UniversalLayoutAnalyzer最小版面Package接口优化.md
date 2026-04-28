# UniversalLayoutAnalyzer 最小版面 Package 接口优化报告

## 基本信息

- 日期: 2026-04-25
- 模块: `modules/universal_layout_analyzer.py`
- 测试: `tests/test_universal_layout_analyzer_package.py`
- 设计锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

## 优化目标

- 为实验性的通用版面分析模块定义最小可用输出协议。
- 让小模型 agent、skill、MCP 可以先读取能力和生成 metadata-only package，而不触发 ONNX/PDF/图像重依赖。
- 为后续 `book/diary/newspaper` 版面分析、OCR 与训练样本准备链路提供稳定中间结构。

## 主要改动

- 新增 `get_capabilities()`，声明输入格式、输出 package、支持文档类型、可选依赖、缺失模型和隐私边界。
- 新增 `analyze_page_package()`，输出 `layout_page` envelope，支持 `use_models=False` 的页面尺寸/状态登记路径。
- 新增 `analyze_document_package()`，输出 `layout_document` envelope，支持 metadata-only 文档登记和真实模型分析两种路径。
- 将 `fitz/numpy/PIL` 改为可选导入，避免模块导入阶段因重依赖缺失失败。

## 验证结果

- `python -m py_compile modules\universal_layout_analyzer.py tests\test_universal_layout_analyzer_package.py`
- `python -m unittest tests.test_universal_layout_analyzer_package`
- `py -3.11 -m unittest tests.test_universal_layout_analyzer_package tests.test_historical_citation_verifier tests.test_citation_formats_package tests.test_history_field_explorer_facade tests.test_stage5_stage6_writing_chain tests.test_ner_disambiguation_package tests.test_embedding_manager_package tests.test_historical_speech_extractor_package tests.test_obsidian_integration_package tests.test_style_transfer_package tests.test_style_transfer_facade tests.test_reverse_outline_package tests.test_paper_polisher_package tests.test_academic_note_generator_package tests.test_stage2_note_chain tests.test_llm_client_ollama tests.test_unified_framework tests.test_ndl_ocr_batch_processor_package tests.test_ndlocr_result_processor_package tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package tests.test_llm_ocr_processor_package tests.test_ocr_processor_package tests.test_unified_ocr_package tests.test_ocr_ner_integration tests.test_ner_processor_package tests.test_stage3_workflow_integration tests.test_stage7_format_chain tests.test_pdf_image_converter_package tests.test_pdf_processor_package tests.test_citation_network_package tests.test_workflow_orchestrator_stage4 tests.test_academic_summarizer_package tests.test_data_structurer_schema tests.test_book_citation_organizer_facade tests.test_doc_processor_package tests.test_citation_chain tests.test_citation_normalizer_schema`
- 结果: 4 个定向测试通过；161 个宽回归测试通过，2 个旧可选依赖用例跳过。

## 隐私与归档

- 未读取或写入 `secrets/`。
- 测试使用合成 fake image 和 metadata-only 路径，不调用真实 OCR、ONNX 模型、PDF 或外部 API。
- 未生成需要额外归档删除的临时脚本。

## 后续建议

- Stage 3 或训练准备链路后续可按 `pdf_image_conversion -> layout_page -> ocr_result -> training_sample` 串联。
- 若新增本地大模型、skill 或 MCP 版面分析后端，仍应回收到 `layout_page/layout_document` envelope。
