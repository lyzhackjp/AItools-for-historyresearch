# 工作区协作、隐私与发布规范

本文是根目录级规范，适用于后端、前端、Windows 安装包、文档、测试报告和 GitHub 发布。详细工作流规则见 [WORKFLOW_DESIGN.md](WORKFLOW_DESIGN.md)，面向用户的 UI 说明见 [docs/guides/FRONTEND_USER_GUIDE.md](docs/guides/FRONTEND_USER_GUIDE.md)。

## 1. 项目边界

- 本工作区定位为历史研究 AI 工具箱，优先服务日本史、日文史料处理、学术笔记、引文管理和论文写作。
- 不把核心方向扩展成泛用聊天系统；新增能力必须能回到研究工作流、模块能力矩阵或 UI 操作场景。
- 面向非代码用户的入口必须优先走 Windows 安装程序和 React UI；开发者入口保留源码运行方式。
- 所有优化以 `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md` 为锚点。

## 2. 隐私、密钥与史料边界

- 真实 API key、token、cookie、NDL 账号、密码和登录名只允许进入 `secrets/`、环境变量或受控本地密钥管理入口。
- 禁止把真实密钥写入代码、README、测试、日志、报告、截图、示例输出或安装包。
- 私密史料全文、可复原的 OCR 原文、未公开档案图片和敏感路径不得出现在公开文档、GitHub issue、release note 或构建日志中。
- 日志只允许记录脱敏摘要、统计信息、相对路径、错误类别、后端名、模型名、`confidence`、`needs_review` 和 `quality_flags`。
- tracked 配置只能保存模板值、环境变量名和相对路径；`config/api_config.json`、`config/current_environment.json`、`config/external_config.json` 不得写入本机绝对路径或真实凭据。
- NDL 凭据只能通过 `NDL_USERNAME`/`NDL_CARD_ID`、`NDL_PASSWORD`、`NDL_CREDENTIALS_FILE` 或被忽略的 `secrets/` 文件提供；报告和测试只记录“已配置/未配置”的脱敏状态。

## 3. 前端与用户体验

- 前端文案必须与 `frontend/src/i18n/translations.ts` 对齐；核心术语包括“全手动经典模式 / Manual classic mode / 手動クラシックモード”、“AI agent solo 模式 / AI agent solo mode / AIエージェントsoloモード”、“七阶段工作流 / Seven-stage workflow / 七段階ワークフロー”和“任务中心 / Task center / タスクセンター”。
- UI 面向文科学者和非代码用户，说明应短、直观、可操作；详细解释放到 `docs/guides/`，不要把 README 写成开发日志。
- 前端只保存必要状态和脱敏配置；真实密钥、私密史料和敏感路径继续留在后端或本地安全入口。
- 所有长任务应进入任务中心，展示进度、日志、产物和复核项；不要让用户在没有反馈的状态下等待。
- 新增 UI 能力时必须考虑中文、英文、日文三语文案；学术术语优先采用可靠来源和前端既有译名。

## 4. 后端与统一任务层

- 新增或改造面向 UI、agent、API、MCP 的任务入口时，优先暴露可序列化能力快照、任务注册表和 package/envelope 结果。
- 调用方应先读取 `TaskManager.get_task_registry()` 或模块级 `get_capabilities()`，再选择 `script`、`local_llm`、`llm_api`、`skill`、`mcp` 或 `hybrid` backend。
- 模块对外结果应尽量包含 `backend`、`provider`、`model`、`confidence`、`needs_review`、`quality_flags`、`artifacts`、`errors` 或结构化错误摘要。
- 本地小模型后端必须先用短 smoke 验证连接；空输出、截断、JSON 解析失败或低置信度不得视为可靠成功。
- 文件系统、vault、导入导出类模块必须声明托管根目录，并拒绝读取或写入根目录之外的路径。

## 5. Windows 安装包与发布

- 安装包只包含后端源码、构建后的 `frontend/dist`、配置模板、文档和启动脚本。
- 安装包必须排除 `.git`、`.runtime`、`.venv`、`frontend/node_modules`、`.env*`、`secrets/`、缓存、日志、输出、模型、数据目录、PDF/PPTX 等可能包含用户材料或体积过大的文件。
- 安装版通过 `scripts/windows/Start-HistoryResearchAI.ps1` 启动本地 Flask 服务，并设置 `HISTORY_RESEARCH_SERVE_FRONTEND=1` 托管 React UI。
- 首次启动会创建 `.runtime\venv` 并安装 Python 依赖；如未找到 Python 3.8-3.11，应提示用户安装 Python 3.11 并启用 `Add Python to PATH`。
- 生成 release 前应记录安装包路径、版本、SHA256 和验证结果；release asset 不应包含 secrets 或用户史料。

## 6. 文件、归档与文档

- 根目录只保留稳定入口文件。长文档进入 `docs/`，阶段报告进入 `log/feature_development/`。
- 面向用户的指南进入 `docs/guides/`；部署与安装包说明进入 `docs/deployment/`；工作流协议进入 `docs/workflow/`。
- 临时文件放入 `temp/`、`tmp/`、`cache/` 或任务专属输出目录；正式报告生成后应归档或删除。
- 不清理无法确认归属的用户文件；如有冲突，先停止并说明风险。
- README 应保持简洁、三语友好、面向用户；详细技术细节通过链接引导。

## 7. 测试与报告

- 新增能力必须有测试、构建验证或可复现 smoke；前端改动优先运行 `npm run build`。
- 测试不得依赖真实密钥；需要外部服务时必须可跳过或使用 mock。
- 报告应包含目标、修改范围、验证结果、隐私合规情况和后续风险。
- 报告不记录敏感原文和密钥。

## 8. GitHub 上传与协作

- 修改前先观察 `git status`；不要回滚用户或他人的未提交修改。
- 不使用破坏性命令清理工作区。
- 提交前运行 `scripts/check_github_upload_safety.py`；若脚本阻断上传，先修复根因。
- 只 stage 本轮实际触碰且应公开的文件；忽略安装包产物、缓存、日志、输出和用户史料。
- 推送或发布后，在最终说明中列出 commit、验证结果和 GitHub 链接。
