# BiographicalNER 离线规则库 Package 接口优化报告

## 基本信息

- 日期: 2026-04-25
- 模块: `modules/biographical_ner.py`
- 测试: `tests/test_biographical_ner_package.py`
- 设计锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

## 优化目标

- 修复人物传记专属 NER 规则库的导入语法错误。
- 将该模块定位为离线规则库，只负责文本块到人物实体的结构化。
- 为 `BiographyExtractor`、薄 pipeline、skill 或 MCP 后端提供统一 `biography_entities` package。

## 主要改动

- 修复 `WorkExperience.position` 字段缺少默认值导致的语法错误。
- 新增 `get_capabilities()`，声明离线规则后端、输出类型、fallback 顺序和隐私边界。
- 新增 `process_text_blocks_package()` 与 `extract_biographical_entities_package()`。
- 姓名提取放宽为逐行 2-5 字匹配，避免多行人物块漏识别姓名。

## 验证结果

- `python -m py_compile modules\biographical_ner.py tests\test_biographical_ner_package.py`
- `python -m unittest tests.test_biographical_ner_package`
- `py -3.11 -m unittest tests.test_biographical_ner_package tests.test_biography_extractor_package tests.test_classical_ocr_training_workflow_package tests.test_pdf_date_matcher_package tests.test_universal_layout_analyzer_package tests.test_historical_citation_verifier tests.test_citation_formats_package tests.test_history_field_explorer_facade tests.test_stage5_stage6_writing_chain tests.test_ner_disambiguation_package tests.test_embedding_manager_package tests.test_historical_speech_extractor_package tests.test_obsidian_integration_package tests.test_style_transfer_package tests.test_style_transfer_facade tests.test_reverse_outline_package tests.test_paper_polisher_package tests.test_academic_note_generator_package tests.test_stage2_note_chain tests.test_llm_client_ollama tests.test_unified_framework tests.test_ndl_ocr_batch_processor_package tests.test_ndlocr_result_processor_package tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package tests.test_llm_ocr_processor_package tests.test_ocr_processor_package tests.test_unified_ocr_package tests.test_ocr_ner_integration tests.test_ner_processor_package tests.test_stage3_workflow_integration tests.test_stage7_format_chain tests.test_pdf_image_converter_package tests.test_pdf_processor_package tests.test_citation_network_package tests.test_workflow_orchestrator_stage4 tests.test_academic_summarizer_package tests.test_data_structurer_schema tests.test_book_citation_organizer_facade tests.test_doc_processor_package tests.test_citation_chain tests.test_citation_normalizer_schema`
- 结果: 3 个定向测试通过；175 个宽回归测试通过，2 个旧可选依赖用例跳过。

## 隐私与归档

- 未读取或写入 `secrets/`。
- 定向测试使用内存文本块，不调用 OCR、LLM、PDF 或外部 API。
- 未生成需要额外归档删除的临时脚本。

## 后续建议

- `biography_pipeline.py` 后续应作为薄封装消费 `BiographyExtractor` 或 `BiographicalNER` package，不再维护并行实体 schema。
- 若需要更强的人物实体抽取，可在统一任务层接入本地大模型、skill 或 MCP，然后回收到 `biography_entities`。
