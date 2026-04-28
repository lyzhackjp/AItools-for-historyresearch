# AI Agent Skill 设计方案

## 目标

为本工作区提供一个可被 AI agent 调用的专属 skill，使 agent 不必每次从零理解项目，而能稳定遵守本工作区的隐私规范、模块优化锚点、package/envelope 协议、测试与报告流程。

## 初始形态

- Skill 源码位置: `docs/agent_skills/historyresearch-workspace/`
- 主文件: `SKILL.md`
- 细节引用: `references/privacy_rules.md`、`references/package_protocol.md`、`references/workflow_rules.md`、`references/module_map.md`
- UI 元数据: `agents/openai.yaml`

该目录先作为工作区内可审查脚手架；确认稳定后，可安装到本地 Codex skill 目录并由后续 agent 自动触发。

## 触发场景

- 优化 `modules/`、`tools/workflow/`、`app/` 或相关测试。
- 接入本地模型、远程 API、skill、MCP 或 hybrid 后端。
- 需要更新 `MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`、README、GUIDELINES、workflow 文档或优化报告。
- 需要检查是否违反隐私、日志、临时文件和归档规则。

## 设计原则

- `SKILL.md` 只保留核心流程和分流规则。
- 详细规范放入 `references/`，由 agent 按需读取。
- 不在 skill 中嵌入密钥、私密路径、真实史料全文或临时实验输出。
- 所有后端选项必须回收为统一 package/envelope。
- 每次完成模块优化都必须有测试、报告、文档更新和清理确认。
- 针对参数较小的本地模型，skill 必须提供短提示词、低 token、可降级的调用规则。

## 2026-04-25 Ollama 小模型接入补充

- 新增 `references/local_model_ollama.md`，记录 Ollama 本地模型 smoke、URL 归一、提示词约束和 fallback 规则。
- 当前实测本地 Ollama 模型 `gemma4:e4b` 可通过 `LLMClient` 完成 `Say OK only.` smoke。
- TaskManager 层新增 `summary_local_small` preset，优先尝试 `local_llm`，空输出时降级到 `script`。
- 小模型 agent 后续应先跑 smoke，再执行 JSON 或复杂历史研究任务。

## 后续增强

- 增加一个只读检查脚本，用于扫描是否缺少报告、测试或 package 字段。
- 为 OCR/NER/citation/writing 四类任务补充更细的参考页。
- 在统一任务层成熟后，把 `skill` 后端作为可发现能力之一接入 task registry。
