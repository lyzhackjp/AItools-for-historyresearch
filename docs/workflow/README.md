# 工作流文档导航

本目录承接根目录 `WORKFLOW_DESIGN.md` 的详细内容，避免单个文件过长。

## 阅读顺序

1. [STAGE_PROTOCOL.md](STAGE_PROTOCOL.md): 先看统一阶段协议。
2. [STAGE_1_3_INGEST_ANALYSIS.md](STAGE_1_3_INGEST_ANALYSIS.md): 再看材料摄入与分析主链。
3. [STAGE_4_7_WRITING_OUTPUT.md](STAGE_4_7_WRITING_OUTPUT.md): 最后看写作、润色与输出链。
4. [PRIVACY_AND_ARTIFACTS.md](PRIVACY_AND_ARTIFACTS.md): 任何自动化、日志、归档改动都要对照此文件。

## 实现位置

- `tools/workflow/research_project.py`: 项目状态、阶段元数据、artifact、复核队列。
- `tools/workflow/workflow_orchestrator.py`: 编排层、checkpoint 与阶段生命周期。
- `tools/workflow/stages/`: 具体阶段业务。
- `modules/task_manager.py`: 统一任务入口。
- `modules/unified_task_executor.py`: 后端执行与结果标准化。

## 优化原则

- 阶段只做编排，不把后端选择硬写死。
- 模块可以有多个后端，但必须回收到统一结果协议。
- 每个阶段都应写回摘要、质量标记、artifact 索引和复核项。
- 正式报告进入 `log/feature_development/`。
