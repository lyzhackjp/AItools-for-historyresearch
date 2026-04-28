# Stage5 SourceSnapshot 消费 NER Package 优化报告

- 日期: 2026-04-25
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 范围: `tools/workflow/stages/stage5_write.py`, `tests/test_stage5_stage6_writing_chain.py`

## 优化目标

Stage 5 已有 source snapshot，但此前主要记录文献、书籍 citation record、笔记与实体总数。本次优化让写作阶段能够读取 Stage 3 的 `ner_extraction` packages，从而知道实体抽取来自哪些来源、后端和质量状态。

## 关键变更

- `_build_source_snapshot()` 读取 `stage3.execution_summary.packages`。
- Source snapshot 新增 `ner_package_count`、`ner_packages_needing_review`、`ner_backends`、`ner_quality_flags`。
- 更新 Stage 5/6 写作链测试，覆盖 NER package 消费。
- 草稿生成行为、返回值和旧 source snapshot 字段保持兼容。

## 隐私与归档

- 未读取 `secrets/`。
- 未生成持久中间脚本。
- Source snapshot 只记录后端、计数与质量标记，不写入完整史料原文。

## 验证

- `python -m py_compile tools\workflow\stages\stage5_write.py tests\test_stage5_stage6_writing_chain.py`
- `py -3.11 -m py_compile tools\workflow\stages\stage5_write.py tests\test_stage5_stage6_writing_chain.py`
- `py -3.11 -m unittest tests.test_stage5_stage6_writing_chain tests.test_stage3_workflow_integration tests.test_stage7_format_chain`

结果: 6 个测试通过。

## 后续衔接

- Stage 5 后续可把 `ner_quality_flags` 纳入 prompt 前置约束，提醒写作阶段避免过度依赖低置信度实体。
- Stage 6/7 可继续读取 source snapshot 中的 NER package 质量摘要，决定是否追加复核提示。
