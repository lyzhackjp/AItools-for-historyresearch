# PDFImageConverter 页级 Artifact 映射优化报告

- 日期: 2026-04-25
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 范围: `modules/pdf_image_converter.py`, `tests/test_pdf_image_converter_package.py`

## 优化目标

将 `pdf_image_converter.py` 从单纯返回图片路径的工具函数，升级为可被工作流读取的页级 artifact 生成器。旧 API 继续返回路径列表，新 API 输出统一 envelope，包含页码映射、DPI、图片尺寸、源 PDF 页面尺寸、后端元数据和复核标记。

## 关键变更

- 保留 `PDFImageConverter.convert_page()`、`convert_range()`、`convert_all()` 与 `convert_pdf_to_images()` 的兼容行为。
- 新增 `get_capabilities()`，声明 `script:pymupdf` 能力、fallback 顺序和可发现能力清单。
- 新增 `convert_range_package()`、`convert_all_package()` 与 `convert_pdf_to_images_package()`。
- 修复旧实现中由损坏注释导致 `pix` 和 `output_path` 未实际赋值的隐患。
- 输出结构统一包含 `backend/provider/model/confidence/needs_review/quality_flags/errors/artifacts`。

## 隐私与归档

- 未读取 `secrets/`。
- 未生成持久中间脚本。
- 单元测试使用 `tempfile.TemporaryDirectory()` 生成临时 PDF 与图片，测试结束自动清理。
- 日志仅记录模块接口和测试结果，不包含史料原文或可复原敏感内容。

## 验证

- `python -m py_compile modules\pdf_image_converter.py modules\citation_network_analyzer.py tests\test_pdf_image_converter_package.py tests\test_citation_network_package.py`
- `py -3.11 -m py_compile modules\pdf_image_converter.py modules\citation_network_analyzer.py tests\test_pdf_image_converter_package.py tests\test_citation_network_package.py`
- `py -3.11 -m unittest tests.test_pdf_image_converter_package tests.test_citation_network_package`

结果: 4 个测试通过。

## 后续衔接

- Stage 3 可直接消费 `artifacts[*].page_number/path/dpi/source_page_size`。
- 后续可将 `unified_ocr_processor.py` 的 OCR 输入改为优先接受该 artifact envelope，而不是散落图片路径。
