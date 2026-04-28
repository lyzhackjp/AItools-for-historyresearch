# AI Agent 工作区 Skill 完善升级

## 背景

用户要求为刚起草的工作区 AI agent skill 制定完善升级方案并实施。目标是让参数较小的本地模型也能按明确 playbook 完成工作区模块优化、报告更新、隐私合规和后端接入，而不是依赖一次性读取大量文档。

## 本次变更

- 新增 `docs/project/AI_AGENT_SKILL_UPGRADE_DESIGN_2026-04-25.md`。
- 新增 `references/agent_playbooks.md`，提供模块优化、本地模型 smoke、报告收尾和 skill 更新流程。
- 新增 `references/acceptance_checklists.md`，提供编辑前、package 接口、小模型、文档和隐私验收清单。
- 新增 `scripts/validate_workspace_skill.py`，只读检查工作区锚点、skill 文件和报告目录。
- 更新 `SKILL.md`，纳入 playbook、checklist 和结构校验脚本。
- 更新 `agents/openai.yaml`，强调小模型友好、validation checks 和隐私合规。

## 校验结果

执行:

- `python docs\agent_skills\historyresearch-workspace\scripts\validate_workspace_skill.py .`
- `python -m py_compile docs\agent_skills\historyresearch-workspace\scripts\validate_workspace_skill.py`
- `python -m unittest tests.test_academic_note_generator_package tests.test_stage2_note_chain tests.test_llm_client_ollama tests.test_unified_framework`
- `py -3.11 -m unittest ...` 宽回归集合

结果:

- `ok=true`
- 缺失根文件: 0
- 缺失 skill 文件: 0
- `secrets_policy=skipped_by_design`
- 本地相关测试 20 个通过
- 宽回归集合 76 个测试通过

## 隐私与归档

校验脚本只读运行，设计上不遍历 `secrets/`。本次未生成临时脚本；新增脚本为正式 skill 资源。
