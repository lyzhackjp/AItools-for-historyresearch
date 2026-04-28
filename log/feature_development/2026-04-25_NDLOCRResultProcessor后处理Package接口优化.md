# NDLOCRResultProcessor 后处理 Package 接口优化报告

- 日期: 2026-04-25
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 范围: `modules/ndlocr_result_processor.py`, `tests/test_ndlocr_result_processor_package.py`

## 优化目标

将 NDL OCR 后处理结果从普通结构化 dict 升级为可被工作流传递的 `processed_ocr_result/processed_ocr_batch` envelope，记录清洗后的文本、结构、统计、后处理置信度和复核标记。

## 关键变更

- 新增 `process_result_package()`。
- 新增 `_package_quality_flags()` 与 `_package_confidence()`。
- 新增 `batch_process_package()`。
- 后处理 package 包含 `text/structured_data/pages/statistics/metadata/backend/provider/model/confidence/needs_review/quality_flags`。
- 失败、无清洗文本、无页级结果、有错误时自动进入复核标记。

## 隐私与归档

- 未读取 `secrets/`。
- 未生成持久中间脚本。
- 测试使用内存 OCR 结果，不写入真实史料全文。

## 验证

- `python -m py_compile modules\ndlocr_result_processor.py tests\test_ndlocr_result_processor_package.py`
- `python -m unittest tests.test_ndlocr_result_processor_package tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package`
- `py -3.11 -m unittest tests.test_ndlocr_result_processor_package tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package tests.test_unified_ocr_package`

结果: 默认 Python 9 个测试通过；Python 3.11 环境 12 个测试通过。

## 后续衔接

- Stage 3 OCR ingestion 后续可选择消费原始 `ocr_result` 或清洗后的 `processed_ocr_result`。
- 后续 `ndl_ocr_batch_processor.py` 可把批处理恢复点、artifact 清单与该后处理 package 合并。
