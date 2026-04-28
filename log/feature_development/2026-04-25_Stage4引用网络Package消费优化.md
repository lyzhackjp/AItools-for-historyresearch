# Stage4 引用网络 Package 消费优化报告

- 日期: 2026-04-25
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 范围: `tools/workflow/stages/stage4_examine.py`, `tests/test_workflow_orchestrator_stage4.py`

## 优化目标

让 Stage 4 不再只调用旧的 `analyze_documents()` 局部结果，而是优先消费 `CitationNetworkAnalyzer.analyze_documents_package()`，把引用网络分析的后端能力、置信度、复核标记与质量问题写回项目状态。

## 关键变更

- Stage 4 `capability_snapshot.citation_analysis` 改为读取 `CitationNetworkAnalyzer.get_capabilities()`。
- `analyze_citation_network()` 改用 `analyze_documents_package()`。
- `CitationNetwork.edges` 现在保留边级 `confidence`。
- Stage 4 citation summary 新增 `backend/provider/confidence/needs_review/quality_flags`。
- 若引用网络 package 需要复核，会写入项目级 `quality_flags`，并追加 `citation_network_quality` 复核项。
- `run()` 的返回结果新增 `citation_package` 摘要，供上层编排或 API 展示。

## 隐私与归档

- 未读取 `secrets/`。
- 未生成持久中间脚本。
- 测试样例为短模拟文本，未写入真实史料全文。
- 质量标记只记录问题类别，不记录敏感材料内容。

## 验证

- `python -m py_compile tools\workflow\stages\stage4_examine.py tests\test_workflow_orchestrator_stage4.py`
- `py -3.11 -m py_compile tools\workflow\stages\stage4_examine.py tests\test_workflow_orchestrator_stage4.py`
- `py -3.11 -m unittest tests.test_workflow_orchestrator_stage4 tests.test_citation_network_package tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain`

结果: 9 个测试通过。

## 后续衔接

- Stage 4 已具备对引文图 package 的正式消费能力。
- 后续可继续把 Stage 3 OCR/NER、Stage 5 source snapshot 与 Stage 7 citation formatting 接入同类 package 摘要。
