# PaperPolisher 写作润色 Package 接口优化

## 背景

最新版 `MODULE_OPTIMIZATION_DESIGN_2026-04-21.md` 要求 `paper_polisher.py` 不再直接绑定单一远程 LLM 路径，而是升级为统一任务层门面；旧接口继续保留，但输出必须统一回传 `polished_text / revision_notes / backend / provider / model / confidence / needs_review`。

## 本次变更

- `modules/paper_polisher.py`
  - `get_capabilities()` 增加模块级能力快照、legacy 方法、fallback 顺序和质量信号。
  - 新增 `polish_paragraph_package()`。
  - 新增 `polish_text_package()`，输出 `paper_polish` envelope。
  - 新增 `process_document_package()`，输出 `paper_polish_document` envelope。
  - 新增统一 `quality_flags` 与 `confidence` 计算。
  - 保留 `polish_paragraph()`、`polish_text()`、`process_document()` 旧接口兼容。

- `tools/workflow/stages/stage6_polish.py`
  - Stage 6 优先消费 `polish_text_package()`。
  - `execution_summary.paper_polish` 现在记录 `package_type` 与 `quality_flags`。
  - 可继续保留旧 polisher 兼容路径。

- `tests/test_paper_polisher_package.py`
  - 覆盖文本 package、短段落 package、Stage 6 package 元数据写回。

## Package 字段

`paper_polish` 包含:

- `type/schema_version/created_at`
- `original_text/polished_text/revision_notes`
- `backend/provider/model/confidence/needs_review/quality_flags`
- `statistics`
- `backend_chain`
- `capabilities`

## 验证

- `python -m py_compile modules\paper_polisher.py tools\workflow\stages\stage6_polish.py tests\test_paper_polisher_package.py tests\test_stage5_stage6_writing_chain.py`
- `python -m unittest tests.test_paper_polisher_package tests.test_stage5_stage6_writing_chain`
- `py -3.11 -m unittest tests.test_paper_polisher_package tests.test_stage5_stage6_writing_chain tests.test_academic_note_generator_package tests.test_stage2_note_chain tests.test_llm_client_ollama tests.test_unified_framework tests.test_ndl_ocr_batch_processor_package tests.test_ndlocr_result_processor_package tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package tests.test_llm_ocr_processor_package tests.test_ocr_processor_package tests.test_unified_ocr_package tests.test_ocr_ner_integration tests.test_ner_processor_package tests.test_stage3_workflow_integration tests.test_stage7_format_chain tests.test_pdf_image_converter_package tests.test_pdf_processor_package tests.test_citation_network_package tests.test_workflow_orchestrator_stage4 tests.test_academic_summarizer_package tests.test_data_structurer_schema tests.test_book_citation_organizer_facade tests.test_doc_processor_package tests.test_citation_chain tests.test_citation_normalizer_schema`

结果: PaperPolisher/Stage6 5 个测试通过；宽回归集合 79 个测试通过。

## 隐私与归档

本次未访问 `secrets/`，未调用真实远程 API，未生成临时测试脚本或中间文件。
