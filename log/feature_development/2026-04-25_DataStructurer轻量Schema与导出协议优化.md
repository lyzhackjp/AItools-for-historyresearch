# DataStructurer 轻量 Schema 与导出协议优化报告

## 基本信息

- 日期: 2026-04-25
- 类型: 通用数据结构化工具优化
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 状态: 已完成

## 优化目标

`modules/data_structurer.py` 原先主要提供文本清洗、表格/键值/时间线提取和 JSON/CSV 导出，但缺少 schema 校验、统一 envelope 和批量质量摘要。本步骤将其增强为 OCR/NER/引用结果可复用的轻量结构检查工具。

## 修改范围

- 更新 `modules/data_structurer.py`
- 新增 `tests/test_data_structurer_schema.py`
- 更新 `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

## 关键结果

1. 新增 `validate_schema()`，支持必填字段、可选字段、缺失字段、额外字段、置信度和复核标记。
2. 新增 `normalize_record()`，把单条记录包装为统一 envelope。
3. 新增 `normalize_records()`，支持批量记录标准化。
4. 新增 `build_export_payload()`，输出记录数量、复核数量、平均置信度、后端元数据。
5. 改进 `to_csv()`，使用所有 dict 行字段的并集，避免后续行字段丢失。

## 隐私合规

- 未读取或记录 `secrets/` 内容。
- 测试数据为人工构造的最小结构化记录，不包含敏感史料原文。
- 未生成临时脚本或持久中间文件。

## 验证结果

- `python -m py_compile modules\data_structurer.py tests\test_data_structurer_schema.py`
- `python -m unittest tests.test_data_structurer_schema`
- `py -3.11 -m unittest tests.test_data_structurer_schema tests.test_stage2_note_chain tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain`

## 后续动作

后续可让 OCR/NER/citation workflow adapters 在写入 artifact 前调用 `build_export_payload()`，统一产生 `confidence/needs_review` 和 schema validation 摘要。
