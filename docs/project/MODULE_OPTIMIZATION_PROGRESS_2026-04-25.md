# 模块优化进度报告

## 基本信息

- 日期: 2026-04-25
- 锚点文件: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`
- 最新工作日志: `log/feature_development/LATEST_WORK_LOG.md`
- 当前回归基线: 178 个测试通过，2 个旧可选依赖用例跳过

## 当前总体判断

本轮优化已经完成“主链 package/envelope 协议化”的大半部分。OCR、NER、笔记、Obsidian、写作润色、引用网络、引用格式化、历史引文核验、版面分析、古典籍训练准备、人物传记结构化等关键链路都已经有可被小模型 agent、skill、MCP 或统一任务层调用的稳定 envelope。

当前仍未结束的工作不主要是“能否调用”，而是三个更深层问题:

- 统一任务层、配置层、环境层、API 层还需要进一步收束。
- 若干优化分支和兼容薄封装还需要合并、冻结或归档。
- 已 package 化的模块还有一部分内部拆分、provider registry、artifact manager、缓存和前端 API schema 工作要继续推进。

## 已完成的关键范围

- 根目录文档与工作流文档已重组: `README.md`、`GUIDELINES.md`、`WORKFLOW_DESIGN.md`、`docs/workflow/`。
- AI agent 工作区 skill 已设计和升级: `docs/agent_skills/historyresearch-workspace/`。
- 本地 Ollama 小模型路径已接入并测试: `llm_client.py`、`unified_task_executor.py`、`TaskManager` smoke preset。
- OCR/PDF 主链已 package 化: `pdf_image_converter.py`、`pdf_processor.py`、`ocr_processor.py`、`llm_ocr_processor.py`、`unified_ocr_processor.py`、`ndlocr_lite.py`、`ndlkotenocr_lite.py`、`ndlocr_result_processor.py`、`ndl_ocr_batch_processor.py`。
- NER 与后处理链已 package 化: `ner_processor.py`、`ner_disambiguation.py`、Stage 3 摘要。
- 笔记与知识库链已 package 化: `academic_note_generator.py`、`obsidian_integration.py`、Stage 2 摘要。
- 写作和润色链已 package 化: `history_field_explorer.py`、`paper_polisher.py`、`reverse_outline_analyzer.py`、`style_transfer.py`、Stage 5/6 摘要。
- 引文链已 package 化: `book_citation_organizer.py`、`citation_normalizer.py`、`citation_network_analyzer.py`、`citation_formats.py`、`historical_citation_verifier.py`、Stage 4/7 摘要。
- 专用训练与人物链已 package 化: `universal_layout_analyzer.py`、`pdf_date_matcher.py`、`classical_ocr_training_workflow.py`、`biography_extractor.py`、`biographical_ner.py`、`biography_pipeline.py`。

## 剩余工作量估算

按当前锚点矩阵粗略估计，剩余工作约 30-35 个优化步骤。

如果只追求“模块都能被 agent 通过 package/envelope 稳定调用”，还剩约 15-18 个步骤。

如果追求“主实现合并、优化分支归档、任务层/API/前端统一、artifact manager 完整落地”，还剩约 30+ 个步骤。

## 下一批优先级

P0/P1 优先继续:

- `task_manager.py`: 收束为 `TaskRegistry + PresetStore + TaskFacade`，统一多后端能力发现。
- `unified_task_executor.py`: 继续拆出 `TaskSpec/ExecutionBackend/ResultValidator/ArtifactWriter`，承接 package 结果验证。
- `module_adapters.py`: 从手工适配器列表改为注册机制，减少重复 glue code。
- `tools/workflow/research_project.py`: 强化 `artifacts/review_queue/quality_flags/stage_metadata` 的统一挂载。
- `tools/workflow/workflow_orchestrator.py`: 由编排层统一 checkpoint、artifact 登记和异常摘要。
- `tools/workflow/stages/stage3_extract.py`: 逐步从阶段内硬编码后端迁移到统一任务层。
- `secure_api_key_manager.py` 与配置层: 形成脱敏状态 facade，服务 API、任务层和前端。
- `app/app.py`: app factory 与 lazy service 继续收束，禁止导入阶段初始化重模块。

P1/P2 可随后推进:

- `integration_manager.py` / `environment_manager.py`: 拆出 workspace paths、dependency runtime、cleanup policy、artifact manager。
- `setup_assistant.py`: 从安装向导拆成独立任务卡，消费环境检测和配置 facade。
- `ndl_ocr_monitor.py`: 独立为 OCR 运维健康状态和恢复建议输出。
- `biography_ocr_pipeline.py`: 下沉为专用模板流程，避免与通用 OCR/person package 重复。
- `task_cli.py`: 保留为统一任务层 CLI，输出标准 JSON 与错误码。
- `virtual_persona_chatbot.py`: 若保留，应限制为学术角色工具并加入事实约束和引文模式。

归档/合并清理:

- `*_optimized.py`、`*_enhanced.py`、`*_integrated.py` 分支需要逐个判定是否还有可吸收逻辑。
- `llm_client_optimized.py`、`ocr_processor_optimized.py`、`pdf_processor_optimized.py`、`academic_*_optimized.py`、`paper_polisher_*`、`ner_processor_*`、`word_processor_optimized.py` 等应进入“吸收后归档”队列。
- 根目录旧测试脚本和实验入口应继续向 `tests/`、`scripts/` 或归档位置收束。

## 当前风险

- 许多模块已具备 package 外壳，但内部 provider registry 尚未完全统一。
- 任务层与 workflow stage 之间仍有局部硬编码，后续若不收束，会影响多后端切换。
- 旧优化分支较多，不清理会继续增加维护噪声。
- API 层和前端若直接追随实验模块，而不是统一 schema，会再次出现接口漂移。

## 建议下一步

建议下一步优先处理统一任务层和编排层，而不是继续扩散到更多专用模块。推荐顺序:

1. `task_manager.py`
2. `unified_task_executor.py`
3. `module_adapters.py`
4. `ResearchProject` artifact/review 挂载
5. `workflow_orchestrator.py`

这五步完成后，已有 package 模块就能被统一任务层稳定发现、调度、验证和登记，后续清理优化分支会更安全。
