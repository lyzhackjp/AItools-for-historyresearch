# NERDisambiguation 实体消歧 Package 接口优化报告

## 基本信息

- 日期: 2026-04-25
- 模块: `modules/ner_disambiguation.py`
- 工作流: `tools/workflow/stages/stage3_extract.py`
- 设计锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

## 优化目标

- 将实体消歧、规范名、类型变化和低置信复核信号统一为 package。
- 保持旧 `disambiguate()` 列表接口兼容，同时让 Stage 3 记录消歧摘要。
- 为后续别名库、本地模型、skill 或 MCP 知识库接入预留统一输出协议。

## 主要改动

- 新增 `EntityDisambiguator.get_capabilities()`。
- 新增 `batch_disambiguate_package()`，输出 `entity_disambiguation` envelope。
- 新增 `NERDisambiguation.disambiguate_package()`，保留 Stage 3 旧字段形态。
- 新增 `EntityRelationResolver.resolve_relations_package()`，输出 `entity_relation_resolution` envelope。
- Stage 3 优先消费 `disambiguate_package()`，并写入 `execution_summary.disambiguation_packages`。

## 验证结果

- `python -m py_compile modules\ner_disambiguation.py tools\workflow\stages\stage3_extract.py tests\test_ner_disambiguation_package.py`
- `python -m unittest tests.test_ner_disambiguation_package tests.test_stage3_workflow_integration`
- `py -3.11 -m unittest ...` 宽回归集合通过。
- 结果: 6 个目标测试通过，102 个宽回归测试通过。

## 隐私与归档

- 未读取或写入 `secrets/`。
- 测试使用本地规则与 fake task manager，不调用真实 API。
- 未生成需要额外归档删除的临时脚本。

## 后续建议

- 引入可维护的实体别名库，记录规范名、别名、时代和地理范围。
- 将本地小模型或 MCP 知识库作为可选增强后端，但必须继续回收为 `entity_disambiguation` package。
