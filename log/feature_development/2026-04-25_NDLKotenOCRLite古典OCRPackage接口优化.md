# NDLKotenOCRLite 古典 OCR Package 接口优化报告

- 日期: 2026-04-25
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 范围: `modules/ndlkotenocr_lite.py`, `tests/test_ndlkotenocr_lite_package.py`

## 优化目标

将古典籍 NDL OCR-Lite 分支与现代 NDL OCR-Lite 分支对齐，统一输出 `ocr_result/ocr_batch` envelope，避免本地 OCR 分支继续维护互不兼容的返回结构。

## 关键变更

- `NDLKotenOCRLiteResult` 新增 `to_package()`。
- `NDLKotenOCRLiteProcessor` 新增 `get_capabilities()`。
- 新增 `process_image_package()` 与 `process_directory_package()`。
- Package 明确 `provider=ndlkotenocr_lite`、`model=ndlkotenocr-lite`、`backend=local_engine`。
- 未安装工具或输入缺失时返回结构化失败 package。

## 隐私与归档

- 未读取 `secrets/`。
- 未启动本地 OCR subprocess。
- 测试只使用未安装状态和内存结果，不写入真实 OCR 文本。

## 验证

- `python -m py_compile modules\ndlkotenocr_lite.py tests\test_ndlkotenocr_lite_package.py`
- `python -m unittest tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package`
- `py -3.11 -m unittest tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package tests.test_unified_ocr_package`

结果: 默认 Python 6 个测试通过；Python 3.11 环境 9 个测试通过。

## 后续衔接

- `UnifiedOCRProcessor` 可进一步减少对 NDL/古典 OCR 结果的重复字段映射。
- OCR 结果后处理层可统一消费现代/古典 OCR package。
