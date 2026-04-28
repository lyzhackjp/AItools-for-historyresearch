# ObsidianIntegration 安全 Vault Package 接口优化报告

## 基本信息

- 日期: 2026-04-25
- 模块: `modules/obsidian_integration.py`
- 工作流: `tools/workflow/stages/stage2_organize.py`
- 设计锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

## 优化目标

- 将 Obsidian 集成层收口为本地 vault 文件系统集成层。
- 保留旧接口兼容，同时提供 `obsidian_note_export` 与 `obsidian_graph` package。
- 阻断路径穿越和 vault 外绝对路径读写，符合工作区隐秘性与 artifact 规范。
- 让 Stage 2 优先消费 vault package，并回写质量标记和复核摘要。

## 主要改动

- 新增 `get_capabilities()`，声明 filesystem/obsidian 后端、支持任务、隐私边界和 path traversal guard。
- 新增 `create_note_package()`、`update_note_package()`、`build_knowledge_graph_package()` 与 `export_notes_to_json_package()`。
- `create_note()`、`read_note()`、`update_note()`、`import_markdown_files()`、`export_notes_to_json()` 统一通过 vault 边界解析，拒绝 vault 外路径。
- Stage 2 Obsidian 导出优先调用 `create_note_package()` 和 `build_knowledge_graph_package()`，并记录 `vault_export.vault_packages` 与 `graph_package`。
- 对导出失败、路径越界、空内容等情况写入 `needs_review/quality_flags`，不静默成功。

## 验证结果

- `python -m py_compile modules\obsidian_integration.py tools\workflow\stages\stage2_organize.py tests\test_obsidian_integration_package.py`
- `python -m unittest tests.test_obsidian_integration_package tests.test_stage2_note_chain`
- `py -3.11 -m unittest ...` 宽回归集合通过。
- 结果: 7 个目标测试通过，92 个宽回归测试通过。

## 隐私与归档

- 未读取或写入 `secrets/`。
- 未在报告中记录原始敏感史料或密钥。
- 本轮新增测试使用 `tempfile.TemporaryDirectory()`，测试结束后自动清理临时 vault 与外部路径样本。
- 未生成需要额外归档删除的中间脚本。

## 后续建议

- 将 managed-root/path-boundary 检查推广到其它导入导出型模块。
- 后续可让 AI agent skill 读取 `get_capabilities()`，自动判断 vault 模块只能做安全写入和 graph scan，不承担内容生成。
