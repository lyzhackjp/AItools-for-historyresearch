# NDLOCRBatchProcessor 批量 OCR Package 接口优化

## 背景

`MODULE_OPTIMIZATION_DESIGN_2026-04-21.md` 将 `ndl_ocr_batch_processor.py` 标记为需要接入统一 artifact 与批次级恢复点的 OCR 批处理模块。此前该模块在初始化阶段会因本地 NDL OCR 缺失直接抛错，不利于工作流、AI agent 或多后端调度层先做能力发现再选择 fallback。

## 本次变更

- `NDLOCRBatchProcessor.__init__()` 新增 `strict` 参数，默认不再因本地引擎缺失中断初始化。
- 新增 `get_capabilities()`，声明本地 NDL OCR 批处理能力、可用性、输入格式、输出类型、fallback 顺序和质量信号。
- 新增 `process_batch_package()`，输出统一 `ocr_batch` envelope。
- 新增批次级统计、页级结果、artifact 映射、`confidence`、`needs_review`、`quality_flags` 与结构化错误摘要。
- `process_image()` 在引擎不可用时返回结构化失败信息，旧接口仍保留。
- 修复无图片结果时平均耗时输出的除零风险。

## 统一协议

新增 package 关键字段:

- `type`: `ocr_batch`
- `backend`: `local_engine`
- `provider`: `ndlocr_batch`
- `model`: `ndlocr-lite`
- `statistics`: `total/success/failed/total_chars/avg_chars/success_rate`
- `pages`: 页级文本、来源图片、成功状态、置信度和复核标记
- `artifacts`: 页级 OCR 输出目录
- `quality_flags`: `engine_unavailable/no_images/page_failures/no_successful_pages/empty_text/batch_error`

## 验证

- `python -m py_compile modules\ndl_ocr_batch_processor.py tests\test_ndl_ocr_batch_processor_package.py`
- `python -m unittest tests.test_ndl_ocr_batch_processor_package tests.test_ndlocr_result_processor_package`
- `py -3.11 -m unittest tests.test_ndl_ocr_batch_processor_package tests.test_ndlocr_result_processor_package tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package tests.test_unified_ocr_package tests.test_ocr_processor_package tests.test_llm_ocr_processor_package tests.test_ocr_ner_integration tests.test_ner_processor_package tests.test_stage3_workflow_integration tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain`
- `py -3.11 -m unittest tests.test_ndl_ocr_batch_processor_package tests.test_ndlocr_result_processor_package tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package tests.test_llm_ocr_processor_package tests.test_ocr_processor_package tests.test_unified_ocr_package tests.test_ocr_ner_integration tests.test_ner_processor_package tests.test_stage3_workflow_integration tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain tests.test_pdf_image_converter_package tests.test_pdf_processor_package tests.test_citation_network_package tests.test_workflow_orchestrator_stage4 tests.test_academic_summarizer_package tests.test_data_structurer_schema tests.test_book_citation_organizer_facade tests.test_doc_processor_package tests.test_stage2_note_chain tests.test_citation_chain tests.test_citation_normalizer_schema`

结果: 最宽回归集合 59 个测试通过。

## 隐私与归档

本次测试未调用真实 NDL OCR subprocess、未访问 `secrets/`、未产生持久临时脚本或中间文件。
