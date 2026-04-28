# 2026-04-28 Historical Citation 工作区接入与隐私加固报告

## 目标

- 在不修改 `modules/historical_citation/` 与 `modules/historical_citation_verifier.py` 原始模块文件的前提下，将阶段性优化完成的 history-citation 能力接入工作区整体调用体系。
- 处理整仓安全脚本对 `config/api_config.json`、`config/current_environment.json`、`config/external_config.json` 的 tracked 配置提示。
- 检查工作区内是否存在 NDL 账号、密码、登录名等隐私信息，并修复可提交区域内的风险项。

## 完成内容

- 新增 `modules/historical_citation_workspace.py`，作为工作区安全外壳调用既有 verifier 的 `parse_docx_package()` 与 `verify_docx_package()`。
- `modules/module_adapters.py` 新增 `HistoricalCitationAdapter`，注册 `historical_citation`、`history_citation`、`historical_citation_verifier` alias。
- `modules/task_manager.py` 新增 `historical_citation` 任务、离线解析 preset 与元数据检索能力，统一返回 `historical_citation_workspace_package`。
- `app/app.py` 新增 `/api/doc/historical-citation-package`，默认 `action=parse`、不启用外部检索、下载或受限下载；旧 `/api/doc/verify-historical-citations` 保持兼容。
- 三个 tracked 配置文件已改为公共模板，只保留环境变量名、相对路径和禁用状态，不含本机绝对路径或真实凭据。
- `scripts/check_github_upload_safety.py` 已从固定拦截三份配置，升级为解析配置内容并扫描 secret-like 值、NDL 凭据赋值和本机路径。
- 修复旧 `_full_test.py` 中硬编码的 API key、消息服务 token、内网地址类隐私风险，改为环境变量读取。
- 将文档中的 `sk-...` 示例改为不会被误认为真实 key 的占位符。
- `tests/test_ndl_credentials.py` 改为 `NDL_*_TEST` 合成值，避免测试 fixture 被安全扫描误判。

## 隐私扫描结果

- 扫描范围: tracked 文件与未忽略文件；跳过 `secrets/`、输出目录、缓存目录、私有材料目录和归档目录。
- 扫描文本文件: 543。
- 高风险命中: 0。
- 说明性引用: 142，均为 NDL 环境变量、凭据加载流程说明、测试 fixture 名称或文档术语引用。
- `secrets/` 目录存在，但按工作区规范未读取其中内容；该目录继续作为本地私有凭据存放边界。

## 验证结果

- `python -m unittest tests.test_historical_citation_workspace tests.test_ndl_credentials`: 9 tests OK。
- `python -m unittest tests.test_historical_citation_workspace tests.test_reusable_workflows tests.test_ndl_credentials`: 12 tests OK。
- `python -m unittest discover tests`: 292 tests OK, skipped=13。
- `python scripts/check_github_upload_safety.py`: clean。
- `git diff --check`: 仅剩 Git 的 LF/CRLF 工作区换行提示，无 whitespace error。
- `py_compile`: 新增/修改的接口、配置 loader、安全脚本和测试均通过。

## 清理

- 删除本轮测试生成且仅包含 `sample.docx` 的根目录临时目录。
- 未读取、复制或输出 `secrets/` 中的任何真实值。

## 后续建议

- Stage 4 后续如接入历史引文核验，应优先调用 `TaskManager.execute_task_package("historical_citation", ...)` 或 `/api/doc/historical-citation-package`。
- 只有在调用方明确设置 `search_ndl=true`、`download_source=true` 或 `restricted_download=true` 时，才允许进入外部平台检索、下载、OCR 或受限 NDL 流程。
- 若未来确需优化原 verifier 内部算法，应单独立项；工作区/API/agent 集成层继续保持在 `historical_citation_workspace.py`。
