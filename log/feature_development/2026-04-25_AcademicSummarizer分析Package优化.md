# AcademicSummarizer 分析 Package 优化报告

- 日期: 2026-04-25
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 范围: `modules/academic_summarizer.py`, `tests/test_academic_summarizer_package.py`

## 优化目标

在保留旧摘要/问题/概念/方法抽取接口的基础上，为 `AcademicSummarizer` 增加统一能力快照和 workflow envelope，使后续 Stage 2、Stage 4、Stage 5 能稳定读取摘要分析结果及复核信号。

## 关键变更

- 新增 `get_capabilities()`，声明摘要、问题抽取、概念识别、方法抽取、相关度评分等能力。
- 新增 `generate_full_analysis_package()`，包装旧 `generate_full_analysis()` 结果。
- 输出统一包含 `backend/provider/model/confidence/needs_review/quality_flags/created_at`。
- 分析结果内部新增 `workflow_metadata`，便于被后续阶段和 API 层直接展示。
- 新增质量标记: `empty_text`、`very_short_text`、`missing_abstractive_summary`、`missing_extractive_summary`、`no_research_questions`、`no_core_concepts`、`no_research_methods`。
- 对带质量标记的结果压低置信度上限，避免短文本在 mock/test 模式下被误判为高可信。

## 隐私与归档

- 未读取 `secrets/`。
- 未生成持久中间脚本。
- 测试文本为短模拟材料，未写入真实史料全文。
- 报告仅记录接口结构、质量标记和测试结果。

## 验证

- `python -m py_compile modules\academic_summarizer.py tests\test_academic_summarizer_package.py`
- `py -3.11 -m py_compile modules\academic_summarizer.py tests\test_academic_summarizer_package.py`
- `python -m unittest tests.test_academic_summarizer_package`
- `py -3.11 -m unittest tests.test_academic_summarizer_package tests.test_workflow_orchestrator_stage4 tests.test_citation_network_package`

结果: 新增 2 个单元测试通过；联动 7 个测试通过。

## 后续衔接

- Stage 2 可用该 package 生成文献摘要与笔记前置分析。
- Stage 5 可将 `analysis.workflow_metadata` 和 `quality_flags` 纳入 source snapshot。
- 后续若接入 LLM API、本地大模型、skill 或 MCP 摘要服务，应回收为同一 `academic_analysis` envelope。
