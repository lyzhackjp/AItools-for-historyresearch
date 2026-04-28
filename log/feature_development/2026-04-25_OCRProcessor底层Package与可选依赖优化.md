# OCRProcessor 底层 Package 与可选依赖优化报告

- 日期: 2026-04-25
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 范围: `modules/ocr_processor.py`, `tests/test_ocr_processor_package.py`

## 优化目标

`OCRProcessor` 是 Tesseract/LLM/NDL OCR 的底层兼容入口，但此前存在导入期硬依赖问题，并且只返回旧式 dict/list 结果。本次优化在不破坏旧 API 的基础上，补齐 workflow package 输出，并让 `pytesseract`、`Pillow`、`numpy` 降级为可选依赖。

## 关键变更

- 新增 `get_capabilities()`。
- 新增 `_result_to_package()`，统一包装底层 OCR dict。
- 新增 `_ocr_quality_flags()`、`_estimate_package_confidence()`、`_word_average_confidence()`。
- 新增 `extract_text_from_image_package()`、`extract_text_from_bytes_package()`、`batch_ocr_package()`、`llm_ocr_package()`。
- `pytesseract`、`Pillow`、`numpy` 改为可选导入，模块可在轻量环境正常导入。
- 缺少 OCR 依赖时，实际调用会返回结构化失败结果，并由 package 标记 `ocr_failed/no_text/has_error`。

## 隐私与归档

- 未读取 `secrets/`。
- 未生成持久中间脚本。
- 测试使用 monkeypatch 和内存结果，不调用真实 OCR 或外部 API。
- Package 可承载 OCR 文本，但本报告和测试不写入真实史料全文。

## 验证

- `python -m py_compile modules\ocr_processor.py tests\test_ocr_processor_package.py`
- `python -m unittest tests.test_ocr_processor_package tests.test_unified_ocr_package tests.test_ocr_ner_integration`
- `py -3.11 -m unittest tests.test_ocr_processor_package tests.test_unified_ocr_package tests.test_ocr_ner_integration`

结果: 默认 Python 与 Python 3.11 环境均通过 10 个 OCR/NER 相关测试。

## 后续衔接

- `UnifiedOCRProcessor` 可继续将底层 `OCRProcessor` 结果回收为同一 `ocr_result` envelope。
- 后续 `llm_ocr_processor.py`、`ndlocr_lite.py`、`ndlkotenocr_lite.py` 应继续向相同 package schema 收口。
