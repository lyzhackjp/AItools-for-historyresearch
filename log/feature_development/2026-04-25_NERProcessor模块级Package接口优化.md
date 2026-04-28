# NERProcessor 模块级 Package 接口优化报告

- 日期: 2026-04-25
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 范围: `modules/ner_processor.py`, `tests/test_ner_processor_package.py`

## 优化目标

在 Stage 3 已经记录 `ner_extraction` package 摘要之后，将同类 envelope 能力下沉到 `NERProcessor` 模块本身，避免后续在 workflow 阶段重复拼装 NER 元数据，并为 script、LLM API、本地 LLM、skill、MCP、hybrid 后端预留统一入口。

## 关键变更

- `get_capabilities()` 现在补充 `module`、`fallback_order`、`active_backend`、`provider`、`model`、`test_mode`。
- 新增 `recognize_historical_entities_package()`，返回 `ner_extraction` envelope。
- 新增 `_package_quality_flags()` 与 `_package_confidence()`。
- 新增 `batch_process_documents_package()`，返回 `ner_batch` envelope。
- 保留旧 `recognize_historical_entities()` 与 `batch_process_documents()` 行为。

## 隐私与归档

- 未读取 `secrets/`。
- 未生成持久中间脚本。
- 测试使用短模拟文本，不写入真实史料全文。
- Package 记录实体摘要、来源元数据与质量标记，不记录完整敏感原文。

## 验证

- `python -m py_compile modules\ner_processor.py tests\test_ner_processor_package.py`
- `py -3.11 -m py_compile modules\ner_processor.py tests\test_ner_processor_package.py`
- `python -m unittest tests.test_ner_processor_package tests.test_stage3_workflow_integration`

结果: 4 个测试通过。

## 后续衔接

- Stage 3 可逐步改为直接调用 `NERProcessor.recognize_historical_entities_package()` 或通过统一任务层返回同构 package。
- 后续 `ner_processor_optimized.py`、`ner_processor_integrated.py` 的可用逻辑应吸收到该 package 接口或归档，不再并行维护。
