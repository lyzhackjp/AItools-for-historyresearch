# PDFProcessor 摄入包与 Artifact 协议优化报告

## 基本信息

- 日期: 2026-04-25
- 类型: PDF 摄入层协议优化
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 状态: 已完成

## 优化目标

`modules/pdf_processor.py` 原先提供 PDF 转图片、页面信息、区域文本提取和论文结构解析等工具函数，但缺少统一 workflow package。本步骤保留旧接口，新增 info/text/image 三类稳定输出包，供 OCR 和文档摄入链复用。

## 修改范围

- 更新 `modules/pdf_processor.py`
- 新增 `tests/test_pdf_processor_package.py`
- 更新 `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

## 关键结果

1. 新增 `get_pdf_info_package()`，返回页数、metadata、页级尺寸/text length、后端元数据和质量标记。
2. 新增 `extract_text_package()`，返回页级文本、全文、页码范围、置信度和复核标记。
3. 新增 `convert_to_images_package()`，返回图片 artifact 列表和 page mapping。
4. 保留原有 `pdf_to_images()`、`get_page_info()`、`extract_text_by_region()` 等接口。
5. 输出统一包含 `backend/provider/model/confidence/needs_review/quality_flags`。

## 隐私合规

- 未读取或记录 `secrets/` 内容。
- 测试 PDF 为临时生成的最小文件，不包含敏感材料。
- 图片测试产物位于 `tempfile.TemporaryDirectory()`，测试结束自动清理。

## 验证结果

- `python -m py_compile modules\pdf_processor.py tests\test_pdf_processor_package.py`
- `py -3.11 -m unittest tests.test_pdf_processor_package tests.test_doc_processor_package tests.test_book_citation_organizer_facade tests.test_stage2_note_chain`

补充说明:

- 默认 `python` 环境缺少 PyMuPDF 的 `fitz`，因此 `python -m unittest tests.test_pdf_processor_package` 无法运行；`py -3.11` 环境验证通过。

## 后续动作

后续可让 `unified_ocr_processor.py`、`pdf_to_ner_workflow.py` 和 Stage 3 优先消费这些 PDF package，逐步统一 OCR 前处理和 artifact 记录。
