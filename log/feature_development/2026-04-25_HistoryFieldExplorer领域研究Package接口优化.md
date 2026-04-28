# HistoryFieldExplorer 领域研究 Package 接口优化报告

## 基本信息

- 日期: 2026-04-25
- 模块: `modules/history_field_explorer.py`
- 工作流: `tools/workflow/stages/stage5_write.py`
- 设计锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

## 优化目标

- 为研究领域探索和草稿生成提供稳定 package 输出。
- 保留旧 `explore()` 与 `draft_paper()` 兼容接口，同时让 Stage 5 可记录草稿 package 摘要。
- 为后续拆分 `FieldSearch`、`FieldSynthesis`、`FieldDrafting` 预留外部契约。

## 主要改动

- `get_capabilities()` 补充 layer、tasks、output_types、supports 和 privacy 字段。
- 新增 `explore_package()`，输出 `field_research` envelope。
- 新增 `draft_paper_package()`，输出 `field_draft` envelope。
- 新增 `_field_report_quality()`，统一记录 literature、core questions、primary sources、warnings 和 review 标记。
- Stage 5 优先消费 `draft_paper_package()`，并记录 `execution_summary.draft_package`。

## 验证结果

- `python -m py_compile modules\history_field_explorer.py tools\workflow\stages\stage5_write.py tests\test_history_field_explorer_facade.py tests\test_stage5_stage6_writing_chain.py`
- `python -m unittest tests.test_history_field_explorer_facade tests.test_stage5_stage6_writing_chain`
- `py -3.11 -m unittest ...` 宽回归集合通过。
- 结果: 7 个目标测试通过，107 个宽回归测试通过。

## 隐私与归档

- 未读取或写入 `secrets/`。
- 测试使用 `test_mode=True` 和本地 dummy explorer，不调用真实 API。
- 未生成需要额外归档删除的临时脚本。

## 后续建议

- 继续把搜索、综合、草稿生成拆为 `FieldSearch`、`FieldSynthesis`、`FieldDrafting`。
- 后续可让 `intelligent_research_assistant/` 作为统一内核吸收该模块能力，但保持 `field_research/field_draft` package schema 不变。
