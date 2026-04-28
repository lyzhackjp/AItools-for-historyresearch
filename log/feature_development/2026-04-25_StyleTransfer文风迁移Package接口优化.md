# StyleTransfer 文风迁移 Package 接口优化

## 背景

最新版 `MODULE_OPTIMIZATION_DESIGN_2026-04-21.md` 要求 `style_transfer.py` 与 `paper_polisher.py` 保持同类协议化接口，不再直接读取 env 或自行组装 provider config；Stage 6 应优先通过该模块消费 `style_transfer` 能力，而不是跨过模块直接调用任务层。

## 本次变更

- `modules/style_transfer.py`
  - `get_capabilities()` 增加模块级能力快照、legacy 方法、fallback 顺序和质量信号。
  - 新增 `transfer_style_package()`，输出 `style_transfer` envelope。
  - 保留 `analyze_style_matrix()`、`transfer_style()`、`transfer_style_result()` 与 `few_shot_style_imitation()` 兼容接口。
  - 空输入、空输出、fallback 后端、低置信度、长度异常和激进改写风险进入 `quality_flags`。

- `tools/workflow/stages/stage6_polish.py`
  - Stage 6 优先消费 `transfer_style_package()`。
  - `execution_summary.style_transfer` 现在记录 `package_type` 与 `quality_flags`。
  - 旧 `transfer_style_result()` 兼容路径保留。

- `tests/test_style_transfer_package.py`
  - 覆盖脚本后端 package、空输入复核标记、Stage 6 package 元数据写回。

## Package 字段

`style_transfer` 包含:

- `type/schema_version/created_at`
- `original_text/rewritten_text/style_analysis/target_style`
- `backend/provider/model/confidence/needs_review/quality_flags`
- `statistics`
- `capabilities`

## 验证

- `python -m py_compile modules\style_transfer.py tools\workflow\stages\stage6_polish.py tests\test_style_transfer_package.py tests\test_style_transfer_facade.py tests\test_stage5_stage6_writing_chain.py`
- `python -m unittest tests.test_style_transfer_package tests.test_style_transfer_facade tests.test_stage5_stage6_writing_chain tests.test_reverse_outline_package tests.test_paper_polisher_package`
- `py -3.11 -m unittest tests.test_style_transfer_package tests.test_style_transfer_facade tests.test_reverse_outline_package tests.test_paper_polisher_package tests.test_stage5_stage6_writing_chain tests.test_academic_note_generator_package tests.test_stage2_note_chain tests.test_llm_client_ollama tests.test_unified_framework tests.test_ndl_ocr_batch_processor_package tests.test_ndlocr_result_processor_package tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package tests.test_llm_ocr_processor_package tests.test_ocr_processor_package tests.test_unified_ocr_package tests.test_ocr_ner_integration tests.test_ner_processor_package tests.test_stage3_workflow_integration tests.test_stage7_format_chain tests.test_pdf_image_converter_package tests.test_pdf_processor_package tests.test_citation_network_package tests.test_workflow_orchestrator_stage4 tests.test_academic_summarizer_package tests.test_data_structurer_schema tests.test_book_citation_organizer_facade tests.test_doc_processor_package tests.test_citation_chain tests.test_citation_normalizer_schema`

结果: StyleTransfer/Stage6 14 个测试通过；宽回归集合 88 个测试通过。

## 隐私与归档

本次未访问 `secrets/`，未调用真实远程 API，未生成临时测试脚本或中间文件。
