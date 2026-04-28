# AI Agent Skill 完善升级设计方案

## 目标

将 `historyresearch-workspace` 从“规范提示型 skill”升级为“小模型可执行的工作区操作 skill”。升级重点不是增加长篇说明，而是降低 agent 的上下文负担，让参数较小的本地模型也能按固定步骤完成模块优化、接口对齐、报告更新和隐私合规检查。

## 设计原则

1. 渐进披露
   `SKILL.md` 只保留入口流程和索引；细节按 `references/` 分流。

2. 小模型友好
   指令短、步骤明确、输出结构固定；复杂任务拆成 playbook，而不是让 agent 自己推理完整流程。

3. 可执行校验
   提供只读脚本检查工作区锚点、skill 文件、报告目录和隐私目录跳过规则，减少人工巡检。

4. 后端统一
   明确 `script / llm_api / local_llm / skill / mcp / hybrid` 的选择与降级，所有结果回收为 package/envelope。

5. 隐私优先
   Skill 不能读取 `secrets/`，不能把原始敏感史料、密钥或完整私密 prompt 写入日志。

## 实施内容

- 新增 `references/agent_playbooks.md`，提供模块优化、Ollama smoke、报告收尾等短流程。
- 新增 `references/acceptance_checklists.md`，提供可执行前/后验收清单。
- 新增 `scripts/validate_workspace_skill.py`，只读检查工作区与 skill 文件结构。
- 更新 `SKILL.md`，把 playbook、checklist 和校验脚本纳入触发流程。
- 更新 `agents/openai.yaml`，使默认提示强调小模型、本地后端和隐私合规。

## 交付标准

- 小模型 agent 只读取 `SKILL.md` 加一到两个 reference 文件，即可完成常规模块优化。
- 校验脚本不访问 `secrets/`，不修改文件。
- 每次模块优化仍必须写入正式报告、更新锚点或说明无需更新。
- 如果本地模型输出为空、截断或结构不合格，必须触发 fallback。

## 后续方向

- 将校验脚本接入统一任务层，作为 `skill_validation` 或 `workspace_audit` backend。
- 为 OCR、NER、citation、writing 四类任务各补一页极简 playbook。
- 未来如安装到全局 Codex skill 目录，应保持本工作区版本为源码基准。
