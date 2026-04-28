# EnvironmentChecker 结构化检查与修复建议优化报告

## 基本信息

- 日期: 2026-04-25
- 类型: 环境检查模块协议优化
- 锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 状态: 已完成

## 优化目标

`modules/environment_checker.py` 原先偏向终端报告和文件输出，并且部分流程可能自动创建配置文件。此步骤新增非破坏性的结构化检查接口，让 API、setup assistant 或工作流可以读取机器可读结果，而不是解析终端文本。

## 修改范围

- 更新 `modules/environment_checker.py`
- 新增 `tests/test_environment_checker_structured.py`
- 更新 `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

## 关键结果

1. 新增 `check_dependencies_structured()`，可对指定依赖做无副作用 import availability 检查。
2. 新增 `build_repair_hints()`，从当前检查结果生成结构化修复建议。
3. 新增 `get_structured_report()`，输出 status、issues、warnings、repair_hints、backend/provider/model、confidence、needs_review。
4. 新增接口不写文件、不创建 `.env`、不安装依赖，适合被 API 和测试调用。

## 隐私合规

- 未读取或记录 `secrets/` 内容。
- 新增测试不调用 `check_all()`，不会触发旧流程中的 `.env` 创建逻辑。
- 修复建议只给出命令文本，`automatic=False`，不会自动执行。

## 验证结果

- `python -m py_compile modules\environment_checker.py tests\test_environment_checker_structured.py`
- `python -m unittest tests.test_environment_checker_structured`
- `py -3.11 -m unittest tests.test_environment_checker_structured tests.test_data_structurer_schema tests.test_pdf_processor_package`

## 后续动作

后续可让 `setup_assistant.py` 和 API 层优先使用 `get_structured_report()`，逐步减少终端文本解析和隐式文件修改。
