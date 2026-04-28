# BookCitationOrganizer 统一引用记录优化报告

## 基本信息

- 日期: 2026-04-25
- 类型: Stage 2 史料整理模块优化
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 状态: 已完成

## 优化目标

`modules/book_citation_organizer.py` 原先把 PDF 文本抽取、元数据识别、文件命名、CSV 导出和多格式引文渲染耦合在同一条旧式流程里。此步骤将其收口为 Stage 2 可复用门面，同时保留旧接口。

## 修改范围

- 重写 `modules/book_citation_organizer.py`
- 新增 `tests/test_book_citation_organizer_facade.py`
- 更新 `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

## 关键结果

1. 保留兼容接口: `process_single_file`、`process_all`、`export_csv`、`get_summary`、`create_book_citation_organizer`。
2. 新增统一 citation record: `BookMetadata.to_citation_record()` 输出 `type/title/authors/year/publisher/confidence/needs_review/backend/provider/model` 等字段。
3. 新增质量协议: 每条结果包含 `confidence`、`needs_review`、`review_notes`、`capabilities`、`extraction_summary` 和 `artifacts`。
4. 新增后端能力声明: `get_capabilities()` 暴露本地规则后端和可选 LLM API 后端。
5. 默认本地规则优先；LLM 仅在显式启用或提供 API key 时作为增强后端，避免默认外传材料。
6. 新增 `export_records()`，可将规范化 citation records 输出为 JSON 供 workflow 后续阶段复用。

## 隐私合规

- 未读取或记录 `secrets/` 内容。
- 默认不调用远程 LLM，避免史料文本默认外传。
- LLM 提示只在显式启用时使用，并且报告中不记录原始 OCR 文本。
- 本步骤未生成临时脚本；测试使用 `tempfile.TemporaryDirectory()`，运行后自动清理。

## 验证结果

- `python -m py_compile modules\book_citation_organizer.py tests\test_book_citation_organizer_facade.py`
- `python -m unittest tests.test_book_citation_organizer_facade`
- `python -m unittest tests.test_citation_chain tests.test_citation_normalizer_schema tests.test_stage2_note_chain`
- `py -3.11 -m py_compile modules\book_citation_organizer.py tests\test_book_citation_organizer_facade.py`
- `py -3.11 -m unittest tests.test_book_citation_organizer_facade`
- `py -3.11 -c "from modules.book_citation_organizer import BookCitationOrganizer; from app.app import app; print('book_citation_and_app_import_ok')"`

补充说明:

- 默认 `python` 解释器导入 `app.app` 时缺少 Flask，`py -3.11` 环境导入成功。该限制属于当前默认解释器依赖状态，不是本次模块改造导致。

## 后续动作

后续可把 Stage 2 中的书籍元数据处理进一步接入 `ResearchProject.stage_metadata`，并让 `BookCitationOrganizer` 的 JSON citation records 与 `CitationNormalizer`、`CitationFormatter` 的格式化链完全共享。
