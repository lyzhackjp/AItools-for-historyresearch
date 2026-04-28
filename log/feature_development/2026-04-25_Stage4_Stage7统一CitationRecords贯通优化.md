# Stage4/Stage7 统一 Citation Records 贯通优化报告

## 基本信息

- 日期: 2026-04-25
- 类型: 工作流引用链贯通优化
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 状态: 已完成

## 优化目标

Stage 2 已能生成 `book_citation_records`，但 Stage 4 与 Stage 7 仍主要消费 `literature`。本步骤将 Stage 2 的统一 citation records 接入史料考察和最终参考文献输出，使书籍史料不会停留在整理阶段。

## 修改范围

- 更新 `tools/workflow/stages/stage4_examine.py`
- 更新 `tools/workflow/stages/stage7_format.py`
- 更新 `tests/test_workflow_orchestrator_stage4.py`
- 更新 `tests/test_stage7_format_chain.py`
- 更新 `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

## 关键结果

1. Stage 4 现在会读取 Stage 2 metadata 中的 `book_citation_records`。
2. Citation network 可由 `literature + book_citation_records` 共同构建。
3. Stage 4 execution summary 记录 `stage2_citation_records` 数量。
4. Stage 7 现在会合并文献记录和 Stage 2 书籍 citation records。
5. Stage 7 会重新按目标格式渲染 Stage 2 records，并保留 `confidence/needs_review`。
6. 新增测试覆盖“没有 literature、只有 Stage 2 book record”的 Stage 4/7 场景。

## 隐私合规

- 未读取或记录 `secrets/` 内容。
- 本步骤不触发远程 API。
- 测试数据为人工构造的最小书目信息，不包含敏感史料原文。
- 未生成临时脚本或持久中间文件。

## 验证结果

- `python -m py_compile tools\workflow\stages\stage4_examine.py tools\workflow\stages\stage7_format.py tests\test_workflow_orchestrator_stage4.py tests\test_stage7_format_chain.py`
- `python -m unittest tests.test_workflow_orchestrator_stage4 tests.test_stage7_format_chain`
- `python -m unittest tests.test_stage2_note_chain tests.test_book_citation_organizer_facade tests.test_citation_chain tests.test_citation_normalizer_schema tests.test_stage5_stage6_writing_chain`
- `py -3.11 -m py_compile tools\workflow\stages\stage4_examine.py tools\workflow\stages\stage7_format.py tests\test_workflow_orchestrator_stage4.py tests\test_stage7_format_chain.py`
- `py -3.11 -m unittest tests.test_workflow_orchestrator_stage4 tests.test_stage7_format_chain tests.test_stage2_note_chain`

## 后续动作

后续可继续让 Stage 5 写作阶段读取统一 citation records 和 DocProcessor 文档包，以便草稿生成时能使用同一套来源结构，而不是只依赖 literature 摘要。
