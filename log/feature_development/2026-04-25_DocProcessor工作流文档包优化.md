# DocProcessor 工作流文档包优化报告

## 基本信息

- 日期: 2026-04-25
- 类型: Word 文档处理链优化
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 状态: 已完成

## 优化目标

`modules/doc_processor.py` 已能解析和生成 docx，但旧接口主要返回段落、表格、脚注等分散结构，尚未形成 Stage 5/6/7 可直接消费的工作流文档包。本步骤在保留旧接口的基础上，新增标准化出口和质量摘要。

## 修改范围

- 更新 `modules/doc_processor.py`
- 新增 `tests/test_doc_processor_package.py`
- 更新 `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

## 关键结果

1. 新增 `extract_document_package(file_path)`。
2. 新增 `extract_document_package_from_bytes(file_bytes, source_name)`。
3. 在旧解析结果中补入 `section_tree`、`footnote_map`、`endnote_map`、`revision_hooks`、`workflow_metadata`。
4. 标准文档包包含 `plain_text`、`backend/provider/model`、`confidence`、`needs_review`、`quality_flags`、`artifacts` 和 `summary`。
5. 长段落、缺少标题结构、缺少正文等情况会进入质量标记，便于后续润色和人工复核。

## 隐私合规

- 未读取或记录 `secrets/` 内容。
- 测试只生成临时 docx，使用 `tempfile.TemporaryDirectory()` 自动清理。
- 报告未包含任何敏感正文或真实用户文档内容。

## 验证结果

- `python -m py_compile modules\doc_processor.py tests\test_doc_processor_package.py`
- `python -m unittest tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain`
- `py -3.11 -m py_compile modules\doc_processor.py tests\test_doc_processor_package.py`
- `py -3.11 -m unittest tests.test_doc_processor_package`
- `py -3.11 -m unittest tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain`

补充说明:

- 默认 `python` 环境缺少 `python-docx`，因此 `python -m unittest tests.test_doc_processor_package` 无法运行；`py -3.11` 环境验证通过。

## 后续动作

后续可让 Stage 5/6/7 优先消费 `extract_document_package()`，把 Word 原稿、脚注、章节树与修订建议连接到同一套 workflow artifact 和 review queue 机制。
