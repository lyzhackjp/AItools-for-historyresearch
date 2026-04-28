# NDLOCRLite 本地 OCR Package 接口优化报告

- 日期: 2026-04-25
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 范围: `modules/ndlocr_lite.py`, `tests/test_ndlocr_lite_package.py`

## 优化目标

将本地 NDL OCR-Lite 分支回收为统一 `ocr_result/ocr_batch` envelope，使其与 `OCRProcessor`、`LLMOCRProcessor`、`UnifiedOCRProcessor` 的输出结构一致，并为后续 NDL/古典 OCR 分支合并提供稳定模板。

## 关键变更

- `NDLOCRLiteResult` 新增 `to_package()`。
- `NDLOCRLiteProcessor` 新增 `get_capabilities()`。
- 新增 `process_image_package()` 与 `process_directory_package()`。
- 未安装 NDL OCR-Lite 时，也能返回结构化失败 package，而不是只依赖控制台错误。
- Package 包含 `backend=local_engine`、`provider=ndlocr_lite`、`model=ndlocr-lite`、`confidence/needs_review/quality_flags`。

## 隐私与归档

- 未读取 `secrets/`。
- 未启动 NDL OCR-Lite subprocess。
- 未生成持久中间脚本。
- 测试只验证内存结果与未安装状态的 envelope，不写入真实 OCR 文本。

## 验证

- `python -m py_compile modules\ndlocr_lite.py tests\test_ndlocr_lite_package.py`
- `python -m unittest tests.test_ndlocr_lite_package tests.test_llm_ocr_processor_package tests.test_ocr_processor_package tests.test_unified_ocr_package`
- `py -3.11 -m unittest tests.test_ndlocr_lite_package tests.test_llm_ocr_processor_package tests.test_ocr_processor_package tests.test_unified_ocr_package tests.test_ocr_ner_integration`

结果: 默认 Python 11 个测试通过；Python 3.11 环境 15 个测试通过。

## 后续衔接

- 下一步可按同一模式处理 `ndlkotenocr_lite.py`。
- `UnifiedOCRProcessor` 后续可优先消费 `NDLOCRLiteResult.to_package()`，减少重复字段映射。
