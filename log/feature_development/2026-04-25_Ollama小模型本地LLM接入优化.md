# Ollama 小模型本地 LLM 接入优化

## 背景

用户要求继续推进未完成模块优化，同时使用 Ollama 本地部署大模型进行测试，并把 AI agent 工作区 skill 优化到参数较小的大模型也能轻松完成调用和对接。

## 本次变更

- `modules/llm_client.py`
  - Ollama 默认模型支持 `OLLAMA_MODEL` 环境变量。
  - Ollama base URL 自动归一: 即使传入 `http://localhost:11434/v1`，原生调用仍会走 `http://localhost:11434/api/chat`。
  - `_chat_ollama()` 增加低温度、低 `num_predict` 参数传递。
  - 返回 `backend=local_llm`、`done_reason`、`needs_review` 与 `quality_flags`。
  - 空输出与长度截断会进入质量标记。
  - 新增 `get_capabilities()`，输出小模型友好的 provider 能力快照。

- `modules/unified_task_executor.py`
  - `local_llm` 默认 base URL 改为 `http://localhost:11434`。
  - 本地模型返回 `empty_content` 时不再视为成功，而是触发后端失败并进入 fallback 链。

- `modules/task_manager.py`
  - 新增 `summary_local_small` preset。
  - 默认使用 `provider=ollama`、`backend=local_llm`、低温度、低 token 与短提示词。

- `tests/test_llm_client_ollama.py`
  - 覆盖 `/v1` URL 归一、Ollama usage 标准化、空输出质量标记和小模型能力快照。

- `tests/test_unified_framework.py`
  - 覆盖 `summary_local_small` preset。
  - 覆盖 `local_llm` 空输出时自动降级到 `script`。

## Ollama 实测

本机检测到模型:

- `gemma4:e4b`

真实 smoke:

- `LLMClient(provider="ollama", model="gemma4:e4b", base_url="http://localhost:11434/v1")`
- Prompt: `Say OK only.`
- Result: `content='OK'`
- Metadata: `backend=local_llm`, `done_reason=stop`, `needs_review=False`

TaskManager 层实测:

- `summary_local_small` 成功先尝试 `local_llm`。
- 当小模型返回空内容时，任务层触发 `local_llm -> script` 降级，并在 metadata 记录 attempted backends。

## 验证

- `python -m py_compile modules\llm_client.py modules\unified_task_executor.py modules\task_manager.py tests\test_llm_client_ollama.py tests\test_unified_framework.py`
- `python -m unittest tests.test_llm_client_ollama tests.test_unified_framework`
- `py -3.11 -m unittest tests.test_llm_client_ollama tests.test_unified_framework tests.test_ndl_ocr_batch_processor_package tests.test_ndlocr_result_processor_package tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package tests.test_llm_ocr_processor_package tests.test_ocr_processor_package tests.test_unified_ocr_package tests.test_ocr_ner_integration tests.test_ner_processor_package tests.test_stage3_workflow_integration tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain tests.test_pdf_image_converter_package tests.test_pdf_processor_package tests.test_citation_network_package tests.test_workflow_orchestrator_stage4 tests.test_academic_summarizer_package tests.test_data_structurer_schema tests.test_book_citation_organizer_facade tests.test_doc_processor_package tests.test_stage2_note_chain tests.test_citation_chain tests.test_citation_normalizer_schema`

结果: 本地 LLM/任务层 14 个测试通过；宽回归集合 73 个测试通过。

## 隐私与归档

本次 Ollama 测试只使用非敏感短 prompt，未访问 `secrets/`，未调用远程 API，未生成持久临时脚本或中间文件。
