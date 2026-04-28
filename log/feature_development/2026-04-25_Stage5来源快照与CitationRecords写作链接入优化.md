# Stage5 来源快照与 Citation Records 写作链接入优化报告

## 基本信息

- 日期: 2026-04-25
- 类型: 写作阶段元数据与审计能力优化
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 状态: 已完成

## 优化目标

Stage 5 原先主要记录草稿长度、段落、标题和引用占位符数量，但没有明确记录草稿生成时可用的统一来源记录。本步骤补入 source snapshot，使写作阶段能被审计，并为后续将 citation records/doc package 直接传入写作后端打基础。

## 修改范围

- 更新 `tools/workflow/stages/stage5_write.py`
- 更新 `tests/test_stage5_stage6_writing_chain.py`
- 更新 `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

## 关键结果

1. Stage 5 启动时写入 `source_snapshot`。
2. 草稿 metadata 增加 `source_record_count`、`book_citation_record_count`、`note_count`、`entity_count`。
3. `source_snapshot` 汇总 literature、Stage 2 book citation records、notes、entities、relations、formatted citations。
4. 若没有任何统一来源记录，会加入 `stage5_no_source_records` 质量标记和 review item。
5. 保持实际草稿生成路径不变，避免破坏当前写作后端。

## 隐私合规

- 未读取或记录 `secrets/` 内容。
- source snapshot 只记录数量、少量标题样例和结构化元数据，不记录敏感史料全文。
- 本步骤未生成临时脚本或持久中间文件。

## 验证结果

- `python -m py_compile tools\workflow\stages\stage5_write.py tests\test_stage5_stage6_writing_chain.py`
- `python -m unittest tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain tests.test_workflow_orchestrator_stage4 tests.test_stage2_note_chain`
- `py -3.11 -m unittest tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain tests.test_workflow_orchestrator_stage4 tests.test_stage2_note_chain`

## 后续动作

后续若继续增强写作后端，可把 `source_snapshot` 扩展为 source dossier，并传入 `HistoryFieldExplorer` 或统一任务层写作能力，让草稿生成直接使用统一 citation records、document packages 与 review flags。
