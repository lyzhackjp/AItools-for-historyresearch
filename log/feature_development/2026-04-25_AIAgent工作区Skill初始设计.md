# AI Agent 工作区 Skill 初始设计

## 背景

用户提出希望为本工作区开发 AI agent 可用的专属 skill，用来协助处理模块优化、接口对齐、隐私合规、测试、报告与文档更新，减少每次手动对齐工作区规范的成本。

## 本次变更

- 新增 `docs/project/AI_AGENT_SKILL_DESIGN_2026-04-25.md`，记录 skill 目标、触发场景、设计原则与后续增强方向。
- 新增 `docs/agent_skills/historyresearch-workspace/SKILL.md`，作为工作区内可审查的 skill 主文件。
- 新增 `references/privacy_rules.md`、`references/package_protocol.md`、`references/workflow_rules.md`、`references/module_map.md`，按需加载细节，避免 `SKILL.md` 过长。
- 新增 `agents/openai.yaml`，提供 UI 元数据草案。
- 更新 `README.md`、`GUIDELINES.md`、`WORKFLOW_DESIGN.md`、`docs/workflow/STAGE_1_3_INGEST_ANALYSIS.md` 与优化锚点，记录 skill 的使用位置和约束。

## 设计取舍

- 本次先将 skill 放在工作区 `docs/agent_skills/` 下，作为可审查源码，不直接写入全局 Codex skill 目录。
- Skill 不包含密钥、私密路径、真实史料全文或临时实验输出。
- Skill 将 `script / llm_api / local_llm / skill / mcp / hybrid` 作为可接入后端类型，但要求所有结果回收为统一 package/envelope。

## 验证

- 与本次 NDLOCRBatchProcessor 优化一起运行宽回归集合。
- 结果: `py -3.11` 下 59 个相关测试通过。

## 隐私与归档

本次未访问 `secrets/`。未生成临时脚本。新增文件均为正式设计、skill 脚手架或优化报告。
