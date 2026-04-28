# 2026-04-21 StyleTransfer 统一任务层门面优化

## 背景

在前几轮已经完成：

- `paper_polisher.py` 的统一任务层门面化
- `reverse_outline_analyzer.py` 的统一协议收口
- Stage 5 / 6 / 7 的 workflow 元数据回写
- 最终引用输出链接入统一 citation record

之后，写作链里还残留一个明显的不一致点：`style_transfer.py` 仍是旧式模块，自己管理 provider / env / API 路径，而 Stage 6 也仍直接跨层调 `TaskManager` 来完成文风调整。这会让写作链三大核心模块的边界风格不一致。

## 本轮目标

1. 先把 `style_transfer.py` 的新增约束补回锚点文档
2. 重写 `modules/style_transfer.py`，让它成为统一任务层门面
3. 让 `Stage6Polish` 正式通过该模块完成 style transfer，而不是直接跨层调 task manager
4. 补正式测试，确保模块本身和 Stage 6/7 回归稳定

## 具体改动

### 1. 锚点文档补充

在 `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md` 中补记：

- `style_transfer.py` 必须与 `paper_polisher.py` 采用同类协议化门面
- 不再自行读取 `.env`
- 不再自行拼 provider config
- Stage 6 应优先通过该模块而不是直接越层调用 task manager

### 2. StyleTransfer 重写

重写 `modules/style_transfer.py`，当前它已经变成统一任务层门面，并保留旧接口名：

- `analyze_style_matrix`
- `transfer_style`
- `few_shot_style_imitation`
- `batch_style_analysis`
- `compare_styles`
- `create_style_transfer`

其中：

- 风格分析部分使用本地稳定启发式
- 文风改写部分通过统一任务层执行 `style_transfer`
- 返回结果统一包含：
  - `rewritten_text`
  - `style_analysis`
  - `target_style`
  - `backend`
  - `provider`
  - `model`
  - `confidence`
  - `needs_review`

### 3. UnifiedTaskExecutor 补齐 style transfer 元数据

更新 `modules/unified_task_executor.py` 中的 `StyleTransferHandler`：

- API 解析路径补齐 `confidence / needs_review`
- script fallback 也补齐 `confidence / needs_review`

这样 style transfer 的输出协议就和前面已经优化过的 paper polish / reverse outline 更一致。

### 4. Stage 6 改为通过模块层执行 style transfer

更新 `tools/workflow/stages/stage6_polish.py`：

- 新增 `_get_style_transfer()`
- `_run_style_transfer()` 改为通过 `modules.style_transfer.StyleTransfer` 执行
- 不再在 Stage 6 内直接跨层调用 `TaskManager.style_transfer(...)`
- 当 style transfer 返回 `needs_review=True` 时，会写入：
  - `stage6_style_transfer_review_needed`
  - `review_queue`

## 测试补充

新增正式测试：

- `tests/test_style_transfer_facade.py`

验证：

- 工厂函数是否可用
- capability discovery 是否正常
- `analyze_style_matrix` 是否返回预期结构
- `transfer_style_result` 是否返回统一元数据

## 验证

以下验证通过：

- `python -m py_compile modules/style_transfer.py modules/unified_task_executor.py tools/workflow/stages/stage6_polish.py tests/test_style_transfer_facade.py`
- `py -3.11 -m py_compile modules/style_transfer.py modules/unified_task_executor.py tools/workflow/stages/stage6_polish.py tests/test_style_transfer_facade.py`
- `python -m unittest tests.test_style_transfer_facade tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain tests.test_citation_normalizer_schema tests.test_citation_chain tests.test_stage2_note_chain tests.test_stage3_workflow_integration tests.test_workflow_orchestrator_stage4 tests.test_unified_framework tests.test_reusable_workflows tests.test_ocr_ner_integration`
- `py -3.11 -m unittest tests.test_style_transfer_facade`
- `py -3.11 -c "from modules.style_transfer import StyleTransfer; print('style transfer ok')"`
- `py -3.11 -c "from tools.workflow.workflow_orchestrator import WorkflowOrchestrator; print('orchestrator ok')"`
- `py -3.11 -c "import app.app; print('app ok')"`

## 工作区规范执行情况

- 未读取或暴露 `secrets/` 中真实密钥内容
- 未新增根目录临时脚本
- 新增测试文件位于 `tests/`
- 新增正式日志位于 `log/feature_development/`
- 本轮未生成需要“先归档后删除”的临时脚本或中间草稿

## 结论

本轮已经把写作链里的 `style_transfer.py` 也收口到统一任务层门面上，使 `paper_polisher.py`、`reverse_outline_analyzer.py`、`style_transfer.py` 三块核心模块的边界终于趋于一致。下一步就可以把重心转向锚点文档中尚未完成系统优化的相邻模块，例如 `book_citation_organizer.py` 或 `doc_processor.py`，继续往外层扩展这套统一协议骨架。
