# Stage3 NER 抽取 Package 摘要优化报告

- 日期: 2026-04-25
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 范围: `tools/workflow/stages/stage3_extract.py`, `tests/test_stage3_workflow_integration.py`

## 优化目标

Stage 3 已经通过统一任务层执行 NER，但阶段摘要仍以计数为主，缺少可追踪的 source/package 级执行记录。本次优化在不改变实体列表与旧返回值的前提下，为每个文本来源补充 `ner_extraction` package 摘要。

## 关键变更

- `_ner_extract()` 的 execution record 新增 `type=ner_extraction`、`source_title`、`confidence`、`needs_review`、`quality_flags`、`categories`、`entity_names`。
- 新增 `_ner_quality_flags()`，标记 `empty_text`、`very_short_text`、`no_entities`、`low_confidence_entities`、`missing_backend_metadata`。
- 新增 `_estimate_ner_confidence()`，基于实体置信度和后端元数据计算 package 级置信度。
- `_summarize_execution_records()` 新增 `packages` 列表，供 `stage_metadata.execution_summary` 稳定读取。
- 更新 Stage 3 集成测试，覆盖 package 结构、低置信度复核标记和后端元数据。

## 隐私与归档

- 未读取 `secrets/`。
- 未生成持久中间脚本。
- 只记录实体名摘要、来源标识、后端元数据和质量标记，不写入完整史料原文。

## 验证

- `python -m py_compile tools\workflow\stages\stage3_extract.py tests\test_stage3_workflow_integration.py`
- `py -3.11 -m py_compile tools\workflow\stages\stage3_extract.py tests\test_stage3_workflow_integration.py`
- `py -3.11 -m unittest tests.test_stage3_workflow_integration tests.test_workflow_orchestrator_stage4 tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain`

结果: 9 个测试通过。

## 后续衔接

- Stage 5 可读取 `stage3.execution_summary.packages`，把实体抽取来源和复核标记纳入 source snapshot。
- 后续 `NERProcessor` 可提供模块级 `recognize_historical_entities_package()`，让 Stage 3 的 package 从阶段内摘要进一步下沉到模块层。
