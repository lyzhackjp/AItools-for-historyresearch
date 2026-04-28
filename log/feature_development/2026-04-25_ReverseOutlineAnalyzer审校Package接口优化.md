# ReverseOutlineAnalyzer 审校 Package 接口优化

## 背景

最新版 `MODULE_OPTIMIZATION_DESIGN_2026-04-21.md` 要求 `reverse_outline_analyzer.py` 从独立启发式分析器升级为统一写作审校协议门面。本地启发式分析仍作为稳定 fallback，但要支持统一任务层、本地模型、远程模型、skill 或 MCP 后端，并统一输出结构化审校数据。

## 本次变更

- `modules/reverse_outline_analyzer.py`
  - `get_capabilities()` 增加模块级能力快照、legacy 方法、fallback 顺序和质量信号。
  - 新增 `analyze_package()`，输出 `outline_review` envelope。
  - 统一输出 `section_word_counts/section_ratios/logical_gaps/deviation_flags/suggestions/confidence/needs_review/backend/provider/model`。
  - 短草稿、缺失章节、结构失衡、fallback 后端和低置信度都会进入 `quality_flags`。

- `tools/workflow/stages/stage6_polish.py`
  - Stage 6 优先消费 `analyze_package()`。
  - `execution_summary.reverse_outline` 现在记录 `package_type` 与 `quality_flags`。
  - 旧 `analyze()` 兼容路径保留。

- `tests/test_reverse_outline_package.py`
  - 覆盖启发式 package、短草稿复核标记、Stage 6 package 元数据写回。

## Package 字段

`outline_review` 包含:

- `type/schema_version/created_at`
- `section_word_counts/section_ratios/logical_gaps/deviation_flags/suggestions`
- `outline/imbalance_issues/summary`
- `backend/provider/model/confidence/needs_review/quality_flags`
- `statistics`
- `capabilities`

## 验证

- `python -m py_compile modules\reverse_outline_analyzer.py tools\workflow\stages\stage6_polish.py tests\test_reverse_outline_package.py tests\test_stage5_stage6_writing_chain.py`
- `python -m unittest tests.test_reverse_outline_package tests.test_stage5_stage6_writing_chain tests.test_paper_polisher_package`
- `py -3.11 -m unittest tests.test_reverse_outline_package tests.test_paper_polisher_package tests.test_stage5_stage6_writing_chain tests.test_academic_note_generator_package tests.test_stage2_note_chain tests.test_llm_client_ollama tests.test_unified_framework tests.test_ndl_ocr_batch_processor_package tests.test_ndlocr_result_processor_package tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package tests.test_llm_ocr_processor_package tests.test_ocr_processor_package tests.test_unified_ocr_package tests.test_ocr_ner_integration tests.test_ner_processor_package tests.test_stage3_workflow_integration tests.test_stage7_format_chain tests.test_pdf_image_converter_package tests.test_pdf_processor_package tests.test_citation_network_package tests.test_workflow_orchestrator_stage4 tests.test_academic_summarizer_package tests.test_data_structurer_schema tests.test_book_citation_organizer_facade tests.test_doc_processor_package tests.test_citation_chain tests.test_citation_normalizer_schema`

结果: ReverseOutline/Stage6 8 个测试通过；宽回归集合 82 个测试通过。

## 隐私与归档

本次未访问 `secrets/`，未调用真实远程 API，未生成临时测试脚本或中间文件。
