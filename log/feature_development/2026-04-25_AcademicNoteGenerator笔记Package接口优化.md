# AcademicNoteGenerator 笔记 Package 接口优化

## 背景

`MODULE_OPTIMIZATION_DESIGN_2026-04-21.md` 将 `academic_note_generator.py` 标记为 P0，并要求其通过统一任务层执行 `academic_note`，统一返回 `markdown/entities/backend/provider/model/needs_review`。此前模块虽已通过任务层生成笔记，但缺少正式 package/envelope 接口和 Stage 2 级 package 摘要。

## 本次变更

- `modules/academic_note_generator.py`
  - 新增 `get_capabilities()`。
  - 新增 `generate_reading_note_package()`，输出 `academic_note` envelope。
  - 新增 `batch_process_package()`，输出 `academic_note_batch` envelope。
  - 新增 `export_summary`、`confidence`、`quality_flags` 与小模型/skill/MCP 后端能力声明。
  - 失败路径统一标记为 `note_generation_fallback_used`，并明确回收为 `script/fallback`。

- `tools/workflow/stages/stage2_organize.py`
  - Stage 2 现在优先调用 `generate_reading_note_package()`。
  - 阶段元数据新增 `execution_summary.note_packages`，记录每篇笔记的 `backend/provider/model/confidence/needs_review/quality_flags/export_summary`。
  - 旧 note 记录和 Obsidian 导出路径保持兼容。

- `tests/test_academic_note_generator_package.py`
  - 覆盖成功 package、降级 package、批量 package。

- `tests/test_stage2_note_chain.py`
  - 覆盖 Stage 2 记录 `academic_note` package 摘要。

## 验证

- `python -m py_compile modules\academic_note_generator.py tools\workflow\stages\stage2_organize.py tests\test_academic_note_generator_package.py tests\test_stage2_note_chain.py`
- `python -m unittest tests.test_academic_note_generator_package tests.test_stage2_note_chain`
- `python -m unittest tests.test_academic_note_generator_package tests.test_stage2_note_chain tests.test_llm_client_ollama tests.test_unified_framework`
- `py -3.11 -m unittest ...` 宽回归集合

结果: AcademicNote/Stage2 6 个测试通过；本地相关测试 20 个通过；宽回归集合 76 个测试通过。

## 隐私与归档

本次未访问 `secrets/`，未调用真实远程 API，未生成临时测试脚本或中间文件。
