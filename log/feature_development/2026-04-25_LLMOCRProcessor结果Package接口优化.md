# LLMOCRProcessor 结果 Package 接口优化报告

- 日期: 2026-04-25
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 范围: `modules/llm_ocr_processor.py`, `tests/test_llm_ocr_processor_package.py`

## 优化目标

`llm_ocr_processor.py` 面向 DashScope/Qwen-VL OCR 的远程大模型 OCR 流程，原本只在完整运行后导出 JSON/TXT/CSV。本次优化新增内存级 package 构建能力，使远程 OCR 分支也能回收为统一 `ocr_result` envelope，供 Stage 3 和后续复核链读取。

## 关键变更

- 新增 `get_capabilities()`，声明 `pdf_to_images`、`vision_ocr`、`watermark_cleanup`、`header_footer_detection`、`page_number_extraction`、`json_txt_csv_export`。
- 新增 `build_pages_package()`，将 `ProcessedPage` 列表包装为 `ocr_result` envelope。
- 新增 `run_package()`，在完整运行后返回 package。
- 将 `fitz`、`Pillow` 改为可选导入，轻量环境可导入模块并运行 package 测试。
- Package 包含 `text/pages/statistics/backend/provider/model/confidence/needs_review/quality_flags/metadata`。

## 隐私与归档

- 未读取 `secrets/`。
- 未实例化真实处理器读取 API 配置。
- 未调用远程 API。
- 测试只使用内存中的 `ProcessedPage`，不写入真实 OCR 文本或图片。

## 验证

- `python -m py_compile modules\llm_ocr_processor.py tests\test_llm_ocr_processor_package.py`
- `python -m unittest tests.test_llm_ocr_processor_package tests.test_ocr_processor_package tests.test_unified_ocr_package`
- `py -3.11 -m unittest tests.test_llm_ocr_processor_package tests.test_ocr_processor_package tests.test_unified_ocr_package tests.test_ocr_ner_integration`

结果: 默认 Python 8 个测试通过；Python 3.11 环境 12 个测试通过。

## 后续衔接

- 远程 LLM OCR、底层 OCR、统一 OCR 门面现在都可以回收为 `ocr_result` schema。
- 后续可继续处理 `ndlocr_lite.py`、`ndlkotenocr_lite.py` 和 `ndlocr_result_processor.py`，让 NDL 本地 OCR 分支也输出同构 package。
