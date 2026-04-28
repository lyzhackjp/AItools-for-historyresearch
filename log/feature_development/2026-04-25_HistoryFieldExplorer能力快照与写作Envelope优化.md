# HistoryFieldExplorer 能力快照与写作 Envelope 优化报告

## 基本信息

- 日期: 2026-04-25
- 类型: 研究入口模块门面级优化
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 状态: 已完成

## 优化目标

`modules/history_field_explorer.py` 是研究起始和 Stage 5 写作的重要入口，但搜索、综合、实体提取、报告生成、论文草稿生成耦合较深。本步骤不强行拆文件，而是先补齐能力快照和统一结果 envelope，为后续拆成 `FieldSearch / FieldSynthesis / FieldDrafting` 做安全铺垫。

## 修改范围

- 更新 `modules/history_field_explorer.py`
- 新增 `tests/test_history_field_explorer_facade.py`
- 更新 `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

## 关键结果

1. 新增 `get_capabilities()`，声明 `field_search / field_synthesis / field_drafting / llm_enhancement / ner` 能力。
2. `FieldReport.to_dict()` 的 metadata 现在包含 `execution` 快照。
3. `explore()` 完成后会写入 paper/project/entity/source hint 数量、后端、provider、confidence、needs_review。
4. `draft_paper()` 保留旧返回结构，同时新增 `backend/provider/model/confidence/needs_review`。
5. 草稿 metadata 新增 quality 摘要，包含章节数、字符数、引用标记数、质量标记。
6. Stage 5 现有调用不需要变更，兼容原工作流。

## 隐私合规

- 测试使用 `test_mode=True`，不读取真实密钥，不调用外部 API。
- 报告不记录搜索结果正文或敏感材料。
- 未生成临时脚本或持久中间文件。

## 验证结果

- `python -m py_compile modules\history_field_explorer.py tests\test_history_field_explorer_facade.py`
- `python -m unittest tests.test_history_field_explorer_facade tests.test_stage5_stage6_writing_chain`
- `py -3.11 -m unittest tests.test_history_field_explorer_facade tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain`

## 后续动作

后续可继续把该模块内部拆为搜索、综合、写作三类服务，或将 `draft_paper()` 接入统一任务层写作后端。
