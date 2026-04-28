# 工作区协作与隐秘性规范

## 2026-04-25 Vault 与文件系统边界补充

- 文件系统、vault、导入导出类模块必须显式声明托管根目录，并拒绝读取或写入根目录之外的路径。
- Obsidian/vault 输出层只负责本地安全写入、frontmatter、双链与 graph scan，不承担内容生成或外部 AI 调度。
- 路径穿越、vault 外绝对路径、空内容写入等情况必须进入 `needs_review` 或结构化错误摘要，不得静默成功。

本文是根目录级工作规范。所有模块优化、测试、报告和归档都必须遵循。

## 1. 项目边界

- 本工作区定位为历史研究 AI 工具箱，优先服务日本史、日文史料、学术笔记、引文管理和论文写作。
- 不把核心方向扩展成泛用聊天系统；新增能力必须能回到研究工作流或模块能力矩阵。
- 所有优化以 `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md` 为锚点。

## 2. 隐秘性与密钥

- 真实 API key、token、cookie、账号凭据只允许进入 `secrets/` 或受控本地密钥管理入口。
- 禁止把真实密钥写入代码、README、测试、日志、报告、截图、示例输出。
- 日志只允许记录脱敏摘要、统计信息、路径、错误类别、后端名、模型名和复核标记。
- 不在报告中粘贴可复原的敏感史料全文；需要说明时使用短摘要、哈希、页码、段落编号或本地路径。
- tracked 配置只能保存模板值、环境变量名和相对路径；`config/api_config.json`、`config/current_environment.json`、`config/external_config.json` 不得写入本机绝对路径、真实 API key、NDL 登录名或密码。
- NDL 账号、密码、登录名仅允许通过 `NDL_USERNAME`/`NDL_CARD_ID`、`NDL_PASSWORD`、`NDL_CREDENTIALS_FILE` 或被忽略的 `secrets/` 文件提供；报告和测试只能记录“已配置/未配置”的脱敏状态。

## 3. 文件与归档

- 根目录只保留稳定入口文件。长文档进入 `docs/`，阶段报告进入 `log/feature_development/`。
- 中间脚本优先放入 `scripts/` 或 `tests/`，不要散落在根目录。
- 临时文件放入 `temp/`、`tmp/`、`cache/` 或任务专属输出目录。
- 临时脚本和中间文件完成正式报告后，应归档到 `archive/`、`archives/` 或删除。
- 不清理无法确认归属的用户文件；如有冲突，先停止并说明风险。

## 4. 模块优化流程

每个优化步骤都按以下顺序执行:

1. 阅读当前代码、测试和相关设计文档。
2. 若发现新方向，先更新 `MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`。
3. 修改模块，优先接入统一任务层、统一数据协议和工作流阶段元数据。
4. 补充或更新测试。
5. 运行最小必要验证，能跑集成测试时优先跑。
6. 写入 `log/feature_development/` 正式优化报告。
7. 更新 `log/feature_development/LATEST_WORK_LOG.md`。

## 5. 多后端接入规范

允许同一能力支持多种后端:

- `script`: 本地规则或脚本
- `llm_api`: 远程大模型 API
- `local_llm`: 本地部署模型
- `skill`: skill 工作流能力
- `mcp`: MCP 工具或连接器
- `hybrid`: 组合后端

但模块对外必须尽量统一返回:

- `backend`
- `provider`
- `model`
- `confidence`
- `needs_review`
- `capabilities`
- `artifacts`
- `errors` 或结构化错误摘要

本地小模型接入额外要求:

- 先用短 smoke 验证连接，再进入复杂任务。
- 空输出、截断、JSON 解析失败或低置信度不得视为可靠成功。
- 必须记录 fallback 链，例如 `local_llm -> script`。

## 6. 测试与报告

- 新增能力必须有测试或可复现的 smoke 验证。
- 测试不得依赖真实密钥；需要外部服务时必须可跳过或使用 mock。
- 报告应包含目标、修改范围、验证结果、隐私合规情况、后续风险。
- 报告不记录敏感原文和密钥。

## 7. AI Agent Skill 使用规范

- 工作区专属 skill 脚手架位于 `docs/agent_skills/historyresearch-workspace/`。
- 后续 AI agent 执行模块优化前，应优先使用该 skill 对齐项目锚点、隐私规则、package 协议、测试和报告流程。
- Skill 目前是工作区内可审查设计，不自动读取 `secrets/`，也不替代正式测试和优化报告。
- 如将 skill 安装到全局 Codex skill 目录，必须保持其中引用的隐私规则与本文件一致。

## 8. Git 与协作

- 不随意回滚他人或历史未提交修改。
- 不使用破坏性命令清理工作区。
- 修改前先观察当前状态，修改后只说明本轮实际触碰的文件。
- 若发现用户文件和当前任务冲突，停止并请求确认。

## 9. Unified Task Layer

- 新增或改造面向 agent/API/MCP 的任务入口时，优先暴露可序列化能力快照、任务注册表和 package/envelope 结果。
- 调用方应先读取 `TaskManager.get_task_registry()` 或模块级 `get_capabilities()`，再选择 `script`、`local_llm`、`llm_api`、`skill` 或 `mcp` backend。
- 能力快照只允许包含 provider/model/backend/status 等脱敏元数据，不得包含真实 API key、token、cookie 或可复原敏感材料。
