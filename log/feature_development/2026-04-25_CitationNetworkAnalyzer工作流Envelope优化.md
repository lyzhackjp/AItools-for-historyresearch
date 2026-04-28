# CitationNetworkAnalyzer 工作流 Envelope 优化报告

- 日期: 2026-04-25
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 范围: `modules/citation_network_analyzer.py`, `tests/test_citation_network_package.py`

## 优化目标

将引用网络分析结果从局部 `graph/records/summary` 返回值，补齐为 Stage 4 和后续写作链路可复用的统一 envelope，使引用网络也能表达后端能力、置信度、复核标记和质量问题。

## 关键变更

- 新增 `get_capabilities()`，声明 `citation_record_normalization`、`citation_graph_building`、`citation_graph_summary` 与 `review_flagging`。
- 新增 `analyze_documents_package()`，在原 `analyze_documents()` 基础上输出 `type/language/records/nodes/edges/graph/summary`。
- 新增质量标记: `no_documents`、`no_citation_edges`、`all_documents_isolated`、`low_average_edge_confidence`。
- 将执行元数据写入 `graph.metadata.execution`，便于 Stage 4、前端和日志审计读取。
- 保持原 `analyze_documents()`、`build_citation_graph()` 与导出方法兼容。

## 隐私与归档

- 未读取 `secrets/`。
- 未生成持久中间脚本。
- 测试文本为短模拟样例，仅用于图边构造验证。
- 输出报告只记录接口结构与测试结果，不记录真实研究材料全文。

## 验证

- `python -m py_compile modules\pdf_image_converter.py modules\citation_network_analyzer.py tests\test_pdf_image_converter_package.py tests\test_citation_network_package.py`
- `py -3.11 -m py_compile modules\pdf_image_converter.py modules\citation_network_analyzer.py tests\test_pdf_image_converter_package.py tests\test_citation_network_package.py`
- `py -3.11 -m unittest tests.test_pdf_image_converter_package tests.test_citation_network_package`

结果: 4 个测试通过。

## 后续衔接

- Stage 4 可改为优先消费 `analyze_documents_package()`，并将 `quality_flags` 与 `needs_review` 写回 `ResearchProject.stage_metadata/review_queue`。
- 后续可以接入 LLM/API/MCP 引文抽取服务作为 fallback，但必须回收为同一 envelope。
