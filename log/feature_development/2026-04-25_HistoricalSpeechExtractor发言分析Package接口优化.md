# HistoricalSpeechExtractor 发言分析 Package 接口优化报告

## 基本信息

- 日期: 2026-04-25
- 模块: `modules/historical_speech_extractor.py`
- 设计锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

## 优化目标

- 为历史发言识别、日期解析和实体附着建立统一 package 输出。
- 先稳定外部契约，避免后续拆分内部组件时影响 Stage 3、agent、skill 或 MCP 调用方。
- 将空页、无发言、无日期、无实体等质量问题转为结构化复核标记。

## 主要改动

- 新增 `get_capabilities()`，声明 `speech_segmentation/date_resolution/entity_attach/ocr_speech_analysis` 能力。
- 新增 `process_ocr_result_package()`，输出 `historical_speech_analysis` envelope。
- 新增 `analyze_text_package()`，用于单页或单段文本快速接入。
- 新增 `_record_to_dict()` 与 `_package_confidence()`，统一记录 statistics、source summary、confidence 和 quality flags。

## 验证结果

- `python -m py_compile modules\historical_speech_extractor.py tests\test_historical_speech_extractor_package.py`
- `python -m unittest tests.test_historical_speech_extractor_package`
- `py -3.11 -m unittest ...` 宽回归集合通过。
- 结果: 3 个目标测试通过，95 个宽回归测试通过。

## 隐私与归档

- 未读取或写入 `secrets/`。
- 测试使用 stub extractor，不调用真实 API，不记录真实史料全文。
- 未生成需要额外归档删除的临时脚本。

## 后续建议

- 继续把内部规则拆分为 `SpeechSegmenter`、`DateResolver`、`EntityAttach`。
- 后续 Stage 3 可把 `historical_speech_analysis` 写入 `stage_metadata.execution_summary.packages`。
