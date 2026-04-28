# UnifiedOCRProcessor 结果 Package 接口优化报告

- 日期: 2026-04-25
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 范围: `modules/unified_ocr_processor.py`, `tests/test_unified_ocr_package.py`

## 优化目标

`UnifiedOCRProcessor` 已经具备多 OCR engine registry 和 fallback chain，但结果仍主要依赖 `UnifiedOCRResult` 对象。本次优化新增统一 package 输出，使 PDF 图片 artifact 可以稳定进入 OCR 层，并把 OCR 结果、后端信息、置信度与复核标记传递给后续 Stage 3/NER。

## 关键变更

- `UnifiedOCRResult` 新增 `to_package()`。
- `UnifiedOCRProcessor` 新增 `process_image_package()` 与 `process_directory_package()`。
- OCR package 统一包含 `type/source_path/success/text/pages/structures/artifacts/backend/provider/model/confidence/needs_review/quality_flags/error/metadata/created_at`。
- 成功结果会基于页级 confidence 或文本存在情况估算置信度。
- 失败、无文本、无页级结果、有错误的情况会进入 `quality_flags` 并触发 `needs_review`。

## 隐私与归档

- 未读取 `secrets/`。
- 未生成持久中间脚本。
- 测试使用内存中的 fake OCR result，不写入真实 OCR 文本或图片。
- Package 记录结构化摘要与路径，不要求写入完整敏感原文。

## 验证

- `python -m py_compile modules\unified_ocr_processor.py tests\test_unified_ocr_package.py`
- `py -3.11 -m py_compile modules\unified_ocr_processor.py tests\test_unified_ocr_package.py`
- `python -m unittest tests.test_unified_ocr_package tests.test_ner_processor_package tests.test_stage3_workflow_integration`

结果: 7 个测试通过。

## 后续衔接

- Stage 3/OCR 输入可优先消费 `PDFImageConverter` 的图片 artifact，再调用 `UnifiedOCRProcessor.process_image_package()`。
- 后续 `ocr_processor_optimized.py`、`llm_ocr_processor.py`、`ndlocr_lite.py` 等分支应尽量回收为该 package schema。
