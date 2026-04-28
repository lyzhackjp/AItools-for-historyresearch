# 2026-04-21 citation schema 统一化优化

## 背景

在 Stage 2 / Stage 3 / Stage 4 逐步完成 workflow 元数据收口之后，citation 主链仍有三个明显短板：

1. `citation_network_analyzer.py` 同时承担抽取、建图、统计、学派识别等多重职责，但输出协议不稳定
2. `citation_formats.py` 仍偏向单一书目场景，无法直接消费统一 citation record
3. `Stage4Examine` 仍在 stage 内部保留一套本地 citation network 构造逻辑，没有真正复用 citation 模块

这些问题会影响：

- Stage 4 与写作链之间的数据衔接
- 后续 citation normalizer / formatter / analyzer 的复用
- graph summary 和 confidence 的统一展示

## 本轮目标

1. 先把 citation schema 新方向写回 `MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
2. 重构 `CitationNetworkAnalyzer`，使其成为统一 graph 协议中心
3. 让 `Stage4Examine` 直接消费 analyzer 输出
4. 增强 `CitationFormatter`，让其支持渲染统一 citation record
5. 增加正式测试覆盖 citation 主链的新行为

## 具体改动

### 1. 锚点文档补充

在 `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md` 中新增了：

- `citation_network_analyzer.py` 的新增约束
- `citation_normalizer.py` 的新增约束
- `citation_formats.py` 的新增约束

明确要求 citation 主链逐步统一到：

- citation record schema
- graph node schema
- graph edge schema
- summary / confidence 输出

### 2. CitationNetworkAnalyzer 重构

重写 `modules/citation_network_analyzer.py`，核心变化如下：

- 新增 `normalize_document`
- 新增 `analyze_documents`
- 统一输出：
  - `graph`
  - `records`
  - `summary`
- graph 中的节点和边包含更稳定的字段：
  - node: `id/title/authors/year/type/is_core/citation_count/cited_by_count/confidence`
  - edge: `source/target/type/confidence/evidence`
- summary 中统一给出：
  - `total_nodes`
  - `total_edges`
  - `key_source_count`
  - `orphan_count`
  - `average_edge_confidence`

### 3. Stage4Examine 接入 analyzer

更新 `tools/workflow/stages/stage4_examine.py`：

- 不再在 stage 内部手工构造 citation network
- 改为通过 `CitationNetworkAnalyzer.analyze_documents(...)` 获取 graph 和 summary
- 继续将统一后的结果写入：
  - `project.citation_network`
  - `project.key_source_ids`
  - `project.stage_metadata["stage4"]`

### 4. CitationFormatter 增强

更新 `modules/citation_formats.py`：

- 新增 `format_record`
- 新增 `format_batch`

使 formatter 可以直接接收统一 citation record，而不仅限于特定书目参数组合。

### 5. 测试补充

新增 `tests/test_citation_chain.py`，验证：

- analyzer 是否返回统一 summary
- Stage 4 是否消费 analyzer 的统一输出
- formatter 是否可以格式化统一 citation record

## 验证

以下验证通过：

- `python -m py_compile modules/citation_network_analyzer.py modules/citation_formats.py tools/workflow/stages/stage4_examine.py tests/test_citation_chain.py`
- `python -m unittest tests.test_citation_chain tests.test_stage2_note_chain tests.test_stage3_workflow_integration tests.test_workflow_orchestrator_stage4 tests.test_unified_framework tests.test_reusable_workflows tests.test_ocr_ner_integration`
- `py -3.11 -c "from modules.citation_network_analyzer import CitationNetworkAnalyzer; print('citation analyzer ok')"`
- `py -3.11 -c "from modules.citation_formats import CitationFormatter; print('citation formatter ok')"`
- `py -3.11 -c "from tools.workflow.stages.stage4_examine import Stage4Examine; print('stage4 ok')"`

## 工作区规范执行情况

- 未读取或暴露 `secrets/` 中真实密钥内容
- 未新增根目录临时脚本
- 新增测试文件位于 `tests/`
- 新增正式日志位于 `log/feature_development/`
- 本轮没有产生需要归档后删除的临时脚本或中间草稿

## 结论

本轮已经把 citation 主链从“局部工具模块”推进到“统一 graph 协议 + workflow 直接消费”的状态。下一步可以继续推进 `citation_normalizer.py` 和写作链模块，让引用规范化、citation graph 与论文润色共用同一套引用数据基础。
