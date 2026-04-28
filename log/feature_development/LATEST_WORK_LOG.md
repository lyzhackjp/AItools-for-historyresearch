# 最新工作日志

**更新时间**: 2026-04-25
**日志类型**: 连续模块优化
**当前状态**: 根目录文档与工作流文档重组已完成，继续进入模块优化

---

## 本轮任务

按照用户要求，继续推进 `MODULE_OPTIMIZATION_DESIGN_2026-04-21.md` 中的后续优化步骤。每完成一个优化步骤，自动输出正式优化报告，然后继续下一步。

本轮同时新增根目录文档维护任务:

- 完善 `README.md`
- 新增并维护 `GUIDELINES.md`
- 重组 `WORKFLOW_DESIGN.md`
- 将工作流细节拆分到 `docs/workflow/`

---

## 已完成步骤

### 1. 根目录文档与工作流文档重组

报告:

- `log/feature_development/2026-04-25_根目录文档与工作流文档重组优化.md`

产出:

- `README.md`
- `GUIDELINES.md`
- `WORKFLOW_DESIGN.md`
- `docs/workflow/README.md`
- `docs/workflow/STAGE_PROTOCOL.md`
- `docs/workflow/STAGE_1_3_INGEST_ANALYSIS.md`
- `docs/workflow/STAGE_4_7_WRITING_OUTPUT.md`
- `docs/workflow/PRIVACY_AND_ARTIFACTS.md`

锚点更新:

- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

隐私合规:

- 未读取或记录 `secrets/` 内容。
- 未写入真实密钥、token、cookie 或敏感史料全文。
- 本步骤未生成临时脚本。

### 2. BookCitationOrganizer 统一引用记录优化

报告:

- `log/feature_development/2026-04-25_BookCitationOrganizer统一引用记录优化.md`

产出:

- `modules/book_citation_organizer.py`
- `tests/test_book_citation_organizer_facade.py`

关键结果:

- 保留旧接口，同时新增统一 citation record、后端元数据、置信度、复核标记和 artifact 摘要。
- 默认本地规则优先，LLM API 只作为显式启用的增强后端。
- 新增 `export_records()` 供 workflow 后续阶段复用。

验证:

- `python -m py_compile modules\book_citation_organizer.py tests\test_book_citation_organizer_facade.py`
- `python -m unittest tests.test_book_citation_organizer_facade`
- `python -m unittest tests.test_citation_chain tests.test_citation_normalizer_schema tests.test_stage2_note_chain`
- `py -3.11 -m py_compile modules\book_citation_organizer.py tests\test_book_citation_organizer_facade.py`
- `py -3.11 -m unittest tests.test_book_citation_organizer_facade`
- `py -3.11 -c "from modules.book_citation_organizer import BookCitationOrganizer; from app.app import app; print('book_citation_and_app_import_ok')"`

### 3. DocProcessor 工作流文档包优化

报告:

- `log/feature_development/2026-04-25_DocProcessor工作流文档包优化.md`

产出:

- `modules/doc_processor.py`
- `tests/test_doc_processor_package.py`

关键结果:

- 新增 `extract_document_package()` 与 `extract_document_package_from_bytes()`。
- 补入 `section_tree`、`footnote_map`、`endnote_map`、`revision_hooks`、`workflow_metadata`。
- 标准文档包可供 Stage 5/6/7 逐步消费。

验证:

- `python -m py_compile modules\doc_processor.py tests\test_doc_processor_package.py`
- `python -m unittest tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain`
- `py -3.11 -m py_compile modules\doc_processor.py tests\test_doc_processor_package.py`
- `py -3.11 -m unittest tests.test_doc_processor_package`
- `py -3.11 -m unittest tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain`

限制:

- 默认 `python` 环境缺少 `python-docx`，新增 DocProcessor 单测需使用 `py -3.11` 环境。

### 4. Stage2 书籍元数据引用记录接入优化

报告:

- `log/feature_development/2026-04-25_Stage2书籍元数据引用记录接入优化.md`

产出:

- `tools/workflow/stages/stage2_organize.py`
- `tests/test_stage2_note_chain.py`

关键结果:

- Stage 2 现在可以将 `ResearchProject.book_metadata` 转为统一 `book_citation_records`。
- 书籍引用会扩展进入 `project.formatted_citations`。
- 不完整书籍元数据会进入 review/quality 机制。

验证:

- `python -m py_compile tools\workflow\stages\stage2_organize.py tests\test_stage2_note_chain.py`
- `python -m unittest tests.test_stage2_note_chain`
- `python -m unittest tests.test_book_citation_organizer_facade tests.test_citation_chain tests.test_citation_normalizer_schema`
- `py -3.11 -m py_compile tools\workflow\stages\stage2_organize.py tests\test_stage2_note_chain.py`
- `py -3.11 -m unittest tests.test_stage2_note_chain tests.test_book_citation_organizer_facade`
- `py -3.11 -c "from tools.workflow.stages.stage2_organize import Stage2Organize; from modules.book_citation_organizer import BookCitationOrganizer; print('stage2_book_chain_import_ok')"`

### 5. Stage4/Stage7 统一 Citation Records 贯通优化

报告:

- `log/feature_development/2026-04-25_Stage4_Stage7统一CitationRecords贯通优化.md`

产出:

- `tools/workflow/stages/stage4_examine.py`
- `tools/workflow/stages/stage7_format.py`
- `tests/test_workflow_orchestrator_stage4.py`
- `tests/test_stage7_format_chain.py`

关键结果:

- Stage 4 现在会把 Stage 2 `book_citation_records` 纳入 citation network。
- Stage 7 现在会把 Stage 2 书籍 citation records 合并进最终参考文献。
- 新增测试覆盖只有书籍 citation record、没有 literature 的场景。

验证:

- `python -m py_compile tools\workflow\stages\stage4_examine.py tools\workflow\stages\stage7_format.py tests\test_workflow_orchestrator_stage4.py tests\test_stage7_format_chain.py`
- `python -m unittest tests.test_workflow_orchestrator_stage4 tests.test_stage7_format_chain`
- `python -m unittest tests.test_stage2_note_chain tests.test_book_citation_organizer_facade tests.test_citation_chain tests.test_citation_normalizer_schema tests.test_stage5_stage6_writing_chain`
- `py -3.11 -m py_compile tools\workflow\stages\stage4_examine.py tools\workflow\stages\stage7_format.py tests\test_workflow_orchestrator_stage4.py tests\test_stage7_format_chain.py`
- `py -3.11 -m unittest tests.test_workflow_orchestrator_stage4 tests.test_stage7_format_chain tests.test_stage2_note_chain`

### 6. Stage5 来源快照与 Citation Records 写作链接入优化

报告:

- `log/feature_development/2026-04-25_Stage5来源快照与CitationRecords写作链接入优化.md`

产出:

- `tools/workflow/stages/stage5_write.py`
- `tests/test_stage5_stage6_writing_chain.py`

关键结果:

- Stage 5 现在记录 `source_snapshot`。
- 草稿 metadata 增加统一来源记录、书籍 citation record、note、entity 统计。
- 无来源记录时进入 quality/review 机制。

验证:

- `python -m py_compile tools\workflow\stages\stage5_write.py tests\test_stage5_stage6_writing_chain.py`
- `python -m unittest tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain tests.test_workflow_orchestrator_stage4 tests.test_stage2_note_chain`
- `py -3.11 -m unittest tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain tests.test_workflow_orchestrator_stage4 tests.test_stage2_note_chain`

### 7. DataStructurer 轻量 Schema 与导出协议优化

报告:

- `log/feature_development/2026-04-25_DataStructurer轻量Schema与导出协议优化.md`

产出:

- `modules/data_structurer.py`
- `tests/test_data_structurer_schema.py`

关键结果:

- 新增 `validate_schema()`、`normalize_record()`、`normalize_records()`、`build_export_payload()`。
- CSV 导出改为使用所有记录字段并集，避免字段丢失。
- 输出 envelope 包含 `confidence/needs_review/backend/provider/model`。

验证:

- `python -m py_compile modules\data_structurer.py tests\test_data_structurer_schema.py`
- `python -m unittest tests.test_data_structurer_schema`
- `py -3.11 -m unittest tests.test_data_structurer_schema tests.test_stage2_note_chain tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain`

### 8. HistoryFieldExplorer 能力快照与写作 Envelope 优化

报告:

- `log/feature_development/2026-04-25_HistoryFieldExplorer能力快照与写作Envelope优化.md`

产出:

- `modules/history_field_explorer.py`
- `tests/test_history_field_explorer_facade.py`

关键结果:

- 新增 `get_capabilities()`。
- `FieldReport.to_dict()` 现在包含 execution metadata。
- `draft_paper()` 保留旧返回结构，同时新增 `backend/provider/model/confidence/needs_review`。

验证:

- `python -m py_compile modules\history_field_explorer.py tests\test_history_field_explorer_facade.py`
- `python -m unittest tests.test_history_field_explorer_facade tests.test_stage5_stage6_writing_chain`
- `py -3.11 -m unittest tests.test_history_field_explorer_facade tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain`

### 9. PDFProcessor 摄入包与 Artifact 协议优化

报告:

- `log/feature_development/2026-04-25_PDFProcessor摄入包与Artifact协议优化.md`

产出:

- `modules/pdf_processor.py`
- `tests/test_pdf_processor_package.py`

关键结果:

- 新增 `get_pdf_info_package()`、`extract_text_package()`、`convert_to_images_package()`。
- PDF 输出统一包含 page metadata、page text、image artifacts、`confidence/needs_review`。

验证:

- `python -m py_compile modules\pdf_processor.py tests\test_pdf_processor_package.py`
- `py -3.11 -m unittest tests.test_pdf_processor_package tests.test_doc_processor_package tests.test_book_citation_organizer_facade tests.test_stage2_note_chain`

限制:

- 默认 `python` 环境缺少 `fitz`，PDF 专项测试需使用 `py -3.11` 环境。

### 10. EnvironmentChecker 结构化检查与修复建议优化

报告:

- `log/feature_development/2026-04-25_EnvironmentChecker结构化检查与修复建议优化.md`

产出:

- `modules/environment_checker.py`
- `tests/test_environment_checker_structured.py`

关键结果:

- 新增 `check_dependencies_structured()`、`build_repair_hints()`、`get_structured_report()`。
- 新接口无副作用，不自动创建 `.env`，不安装依赖。
- 输出包含 `status/issues/warnings/repair_hints/confidence/needs_review`。

验证:

- `python -m py_compile modules\environment_checker.py tests\test_environment_checker_structured.py`
- `python -m unittest tests.test_environment_checker_structured`
- `py -3.11 -m unittest tests.test_environment_checker_structured tests.test_data_structurer_schema tests.test_pdf_processor_package`

---

## 下一步

继续处理模块级优化，优先选择 Stage 5 写作阶段对统一来源记录和文档包的消费，或进入 Phase 6 清理/归档检查。

### 11. PDFImageConverter 页级 Artifact 映射优化

报告:

- `log/feature_development/2026-04-25_PDFImageConverter页级Artifact映射优化.md`

产出:

- `modules/pdf_image_converter.py`
- `tests/test_pdf_image_converter_package.py`

关键结果:

- 新增 `get_capabilities()`、`convert_range_package()`、`convert_all_package()`、`convert_pdf_to_images_package()`。
- 旧接口继续返回图片路径列表，新接口返回 page/artifact/backend/provider/model/confidence/needs_review。
- 修复旧实现中损坏注释吞掉 `pix` 和 `output_path` 赋值的运行隐患。

验证:

- `python -m py_compile modules\pdf_image_converter.py modules\citation_network_analyzer.py tests\test_pdf_image_converter_package.py tests\test_citation_network_package.py`
- `py -3.11 -m py_compile modules\pdf_image_converter.py modules\citation_network_analyzer.py tests\test_pdf_image_converter_package.py tests\test_citation_network_package.py`
- `py -3.11 -m unittest tests.test_pdf_image_converter_package tests.test_citation_network_package`

### 12. CitationNetworkAnalyzer 工作流 Envelope 优化

报告:

- `log/feature_development/2026-04-25_CitationNetworkAnalyzer工作流Envelope优化.md`

产出:

- `modules/citation_network_analyzer.py`
- `tests/test_citation_network_package.py`

关键结果:

- 新增 `get_capabilities()` 与 `analyze_documents_package()`。
- 引用网络输出统一包含 `records/nodes/edges/graph/summary/backend/provider/model/confidence/needs_review/quality_flags`。
- `graph.metadata.execution` 可被 Stage 4、前端和审计日志稳定读取。

验证:

- `python -m py_compile modules\pdf_image_converter.py modules\citation_network_analyzer.py tests\test_pdf_image_converter_package.py tests\test_citation_network_package.py`
- `py -3.11 -m py_compile modules\pdf_image_converter.py modules\citation_network_analyzer.py tests\test_pdf_image_converter_package.py tests\test_citation_network_package.py`
- `py -3.11 -m unittest tests.test_pdf_image_converter_package tests.test_citation_network_package`

---

## 下一步
继续推进 Stage 3/Stage 4 对上述 package 接口的消费，或进入 `unified_ocr_processor.py` / `academic_summarizer.py` 的多后端能力快照与 envelope 优化。

### 13. Stage4 引用网络 Package 消费优化

报告:

- `log/feature_development/2026-04-25_Stage4引用网络Package消费优化.md`

产出:

- `tools/workflow/stages/stage4_examine.py`
- `tests/test_workflow_orchestrator_stage4.py`

关键结果:

- Stage 4 改为优先消费 `CitationNetworkAnalyzer.analyze_documents_package()`。
- 阶段摘要新增 `backend/provider/confidence/needs_review/quality_flags`。
- 引用网络 package 需要复核时，会写入项目级质量标记和 `citation_network_quality` 复核项。

验证:

- `python -m py_compile tools\workflow\stages\stage4_examine.py tests\test_workflow_orchestrator_stage4.py`
- `py -3.11 -m py_compile tools\workflow\stages\stage4_examine.py tests\test_workflow_orchestrator_stage4.py`
- `py -3.11 -m unittest tests.test_workflow_orchestrator_stage4 tests.test_citation_network_package tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain`

### 14. AcademicSummarizer 分析 Package 优化

报告:

- `log/feature_development/2026-04-25_AcademicSummarizer分析Package优化.md`

产出:

- `modules/academic_summarizer.py`
- `tests/test_academic_summarizer_package.py`

关键结果:

- 新增 `get_capabilities()` 与 `generate_full_analysis_package()`。
- 学术摘要分析结果统一包装为 `academic_analysis` envelope。
- 短文本、空文本和缺失结构会进入 `quality_flags/needs_review`，且置信度上限被压低。

验证:

- `python -m py_compile modules\academic_summarizer.py tests\test_academic_summarizer_package.py`
- `py -3.11 -m py_compile modules\academic_summarizer.py tests\test_academic_summarizer_package.py`
- `python -m unittest tests.test_academic_summarizer_package`
- `py -3.11 -m unittest tests.test_academic_summarizer_package tests.test_workflow_orchestrator_stage4 tests.test_citation_network_package`

### 15. Stage3 NER 抽取 Package 摘要优化

报告:

- `log/feature_development/2026-04-25_Stage3_NER抽取Package摘要优化.md`

产出:

- `tools/workflow/stages/stage3_extract.py`
- `tests/test_stage3_workflow_integration.py`

关键结果:

- Stage 3 的每个 NER 来源现在会形成 `ner_extraction` package 摘要。
- 摘要包含 `backend/provider/model/confidence/needs_review/quality_flags/categories`。
- 低置信度实体会在 package 级别标记 `low_confidence_entities`，方便后续 source snapshot 和 review queue 消费。

验证:

- `python -m py_compile tools\workflow\stages\stage3_extract.py tests\test_stage3_workflow_integration.py`
- `py -3.11 -m py_compile tools\workflow\stages\stage3_extract.py tests\test_stage3_workflow_integration.py`
- `py -3.11 -m unittest tests.test_stage3_workflow_integration tests.test_workflow_orchestrator_stage4 tests.test_stage5_stage6_writing_chain tests.test_stage7_format_chain`

### 16. NERProcessor 模块级 Package 接口优化

报告:

- `log/feature_development/2026-04-25_NERProcessor模块级Package接口优化.md`

产出:

- `modules/ner_processor.py`
- `tests/test_ner_processor_package.py`

关键结果:

- 新增 `recognize_historical_entities_package()` 与 `batch_process_documents_package()`。
- `get_capabilities()` 补充模块名、fallback 顺序、当前后端、provider/model/test_mode。
- 旧 NER API 保持兼容，新 package 接口可被 Stage 3 或统一任务层逐步消费。

验证:

- `python -m py_compile modules\ner_processor.py tests\test_ner_processor_package.py`
- `py -3.11 -m py_compile modules\ner_processor.py tests\test_ner_processor_package.py`
- `python -m unittest tests.test_ner_processor_package tests.test_stage3_workflow_integration`

### 17. UnifiedOCRProcessor 结果 Package 接口优化

报告:

- `log/feature_development/2026-04-25_UnifiedOCRProcessor结果Package接口优化.md`

产出:

- `modules/unified_ocr_processor.py`
- `tests/test_unified_ocr_package.py`

关键结果:

- 新增 `UnifiedOCRResult.to_package()`、`process_image_package()`、`process_directory_package()`。
- OCR 结果统一输出 `ocr_result/ocr_batch` envelope。
- OCR 失败、无文本、无页级结果或有错误时会进入 `quality_flags/needs_review`。

验证:

- `python -m py_compile modules\unified_ocr_processor.py tests\test_unified_ocr_package.py`
- `py -3.11 -m py_compile modules\unified_ocr_processor.py tests\test_unified_ocr_package.py`
- `python -m unittest tests.test_unified_ocr_package tests.test_ner_processor_package tests.test_stage3_workflow_integration`

### 18. Stage5 SourceSnapshot 消费 NER Package 优化

报告:

- `log/feature_development/2026-04-25_Stage5_SourceSnapshot消费NERPackage优化.md`

产出:

- `tools/workflow/stages/stage5_write.py`
- `tests/test_stage5_stage6_writing_chain.py`

关键结果:

- Stage 5 `source_snapshot` 现在读取 Stage 3 `ner_extraction` packages。
- 新增 `ner_package_count/ner_packages_needing_review/ner_backends/ner_quality_flags`。
- 写作阶段可以感知实体抽取质量，而不是只读取合并后的实体总数。

验证:

- `python -m py_compile tools\workflow\stages\stage5_write.py tests\test_stage5_stage6_writing_chain.py`
- `py -3.11 -m py_compile tools\workflow\stages\stage5_write.py tests\test_stage5_stage6_writing_chain.py`
- `py -3.11 -m unittest tests.test_stage5_stage6_writing_chain tests.test_stage3_workflow_integration tests.test_stage7_format_chain`

### 19. OCRProcessor 底层 Package 与可选依赖优化

报告:

- `log/feature_development/2026-04-25_OCRProcessor底层Package与可选依赖优化.md`

产出:

- `modules/ocr_processor.py`
- `tests/test_ocr_processor_package.py`

关键结果:

- 新增 `get_capabilities()`、`extract_text_from_image_package()`、`extract_text_from_bytes_package()`、`batch_ocr_package()`、`llm_ocr_package()`。
- 底层 OCR dict 结果可统一包装为 `ocr_result/ocr_batch` envelope。
- `pytesseract/Pillow/numpy` 改为可选导入，轻量环境可导入模块并运行结构化测试。

验证:

- `python -m py_compile modules\ocr_processor.py tests\test_ocr_processor_package.py`
- `python -m unittest tests.test_ocr_processor_package tests.test_unified_ocr_package tests.test_ocr_ner_integration`
- `py -3.11 -m unittest tests.test_ocr_processor_package tests.test_unified_ocr_package tests.test_ocr_ner_integration`

### 20. LLMOCRProcessor 结果 Package 接口优化

报告:

- `log/feature_development/2026-04-25_LLMOCRProcessor结果Package接口优化.md`

产出:

- `modules/llm_ocr_processor.py`
- `tests/test_llm_ocr_processor_package.py`

关键结果:

- 新增 `get_capabilities()`、`build_pages_package()`、`run_package()`。
- 远程 Qwen-VL OCR 分支可回收为统一 `ocr_result` envelope。
- `fitz/Pillow` 改为可选导入，轻量环境可导入模块并运行 package 测试。

验证:

- `python -m py_compile modules\llm_ocr_processor.py tests\test_llm_ocr_processor_package.py`
- `python -m unittest tests.test_llm_ocr_processor_package tests.test_ocr_processor_package tests.test_unified_ocr_package`
- `py -3.11 -m unittest tests.test_llm_ocr_processor_package tests.test_ocr_processor_package tests.test_unified_ocr_package tests.test_ocr_ner_integration`

### 21. NDLOCRLite 本地 OCR Package 接口优化

报告:

- `log/feature_development/2026-04-25_NDLOCRLite本地OCRPackage接口优化.md`

产出:

- `modules/ndlocr_lite.py`
- `tests/test_ndlocr_lite_package.py`

关键结果:

- 新增 `NDLOCRLiteResult.to_package()`、`get_capabilities()`、`process_image_package()`、`process_directory_package()`。
- 本地 NDL OCR-Lite 分支可回收为统一 `ocr_result/ocr_batch` envelope。
- 未安装 NDL OCR-Lite 时也能返回结构化失败 package。

验证:

- `python -m py_compile modules\ndlocr_lite.py tests\test_ndlocr_lite_package.py`
- `python -m unittest tests.test_ndlocr_lite_package tests.test_llm_ocr_processor_package tests.test_ocr_processor_package tests.test_unified_ocr_package`
- `py -3.11 -m unittest tests.test_ndlocr_lite_package tests.test_llm_ocr_processor_package tests.test_ocr_processor_package tests.test_unified_ocr_package tests.test_ocr_ner_integration`

### 22. NDLKotenOCRLite 古典 OCR Package 接口优化

报告:

- `log/feature_development/2026-04-25_NDLKotenOCRLite古典OCRPackage接口优化.md`

产出:

- `modules/ndlkotenocr_lite.py`
- `tests/test_ndlkotenocr_lite_package.py`

关键结果:

- 新增 `NDLKotenOCRLiteResult.to_package()`、`get_capabilities()`、`process_image_package()`、`process_directory_package()`。
- 古典 OCR-Lite 分支可回收为统一 `ocr_result/ocr_batch` envelope。

验证:

- `python -m py_compile modules\ndlkotenocr_lite.py tests\test_ndlkotenocr_lite_package.py`
- `python -m unittest tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package`
- `py -3.11 -m unittest tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package tests.test_unified_ocr_package`

### 23. NDLOCRResultProcessor 后处理 Package 接口优化

报告:

- `log/feature_development/2026-04-25_NDLOCRResultProcessor后处理Package接口优化.md`

产出:

- `modules/ndlocr_result_processor.py`
- `tests/test_ndlocr_result_processor_package.py`

关键结果:

- 新增 `process_result_package()` 与 `batch_process_package()`。
- OCR 清洗/结构化结果可回收为 `processed_ocr_result/processed_ocr_batch` envelope。
- 失败、无文本、无页级结果、有错误时自动进入 `quality_flags/needs_review`。

验证:

- `python -m py_compile modules\ndlocr_result_processor.py tests\test_ndlocr_result_processor_package.py`
- `python -m unittest tests.test_ndlocr_result_processor_package tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package`
- `py -3.11 -m unittest tests.test_ndlocr_result_processor_package tests.test_ndlkotenocr_lite_package tests.test_ndlocr_lite_package tests.test_unified_ocr_package`

### 24. NDLOCRBatchProcessor 批量 OCR Package 接口优化

报告:

- `log/feature_development/2026-04-25_NDLOCRBatchProcessor批量OCRPackage接口优化.md`

产出:

- `modules/ndl_ocr_batch_processor.py`
- `tests/test_ndl_ocr_batch_processor_package.py`

关键结果:

- 新增 `get_capabilities()` 与 `process_batch_package()`。
- 批量 NDL OCR 结果可回收为 `ocr_batch` envelope。
- 默认初始化不再因本地 NDL OCR 缺失而硬失败，工作流可先做能力发现再选择 fallback。

验证:

- `python -m py_compile modules\ndl_ocr_batch_processor.py tests\test_ndl_ocr_batch_processor_package.py`
- `python -m unittest tests.test_ndl_ocr_batch_processor_package tests.test_ndlocr_result_processor_package`
- `py -3.11 -m unittest ...` 宽回归集合 59 个测试通过

### 25. AI Agent 工作区 Skill 初始设计

报告/方案:

- `log/feature_development/2026-04-25_AIAgent工作区Skill初始设计.md`
- `docs/project/AI_AGENT_SKILL_DESIGN_2026-04-25.md`

产出:

- `docs/agent_skills/historyresearch-workspace/SKILL.md`
- `docs/agent_skills/historyresearch-workspace/references/privacy_rules.md`
- `docs/agent_skills/historyresearch-workspace/references/package_protocol.md`
- `docs/agent_skills/historyresearch-workspace/references/workflow_rules.md`
- `docs/agent_skills/historyresearch-workspace/references/module_map.md`
- `docs/agent_skills/historyresearch-workspace/agents/openai.yaml`

关键结果:

- 为后续 AI agent 提供工作区专属流程、隐私规范、package 协议、报告规范与模块地图。
- 先作为工作区内可审查脚手架，暂不直接写入全局 Codex skill 目录。

### 26. Ollama 小模型本地 LLM 接入优化

报告:

- `log/feature_development/2026-04-25_Ollama小模型本地LLM接入优化.md`

产出:

- `modules/llm_client.py`
- `modules/unified_task_executor.py`
- `modules/task_manager.py`
- `tests/test_llm_client_ollama.py`
- `tests/test_unified_framework.py`
- `docs/agent_skills/historyresearch-workspace/references/local_model_ollama.md`

关键结果:

- Ollama `/v1` base URL 可归一到原生 `/api/chat`。
- `LLMClient` 真实调用本地 `gemma4:e4b` 完成 `Say OK only.` smoke。
- 本地模型空输出会触发 `needs_review/quality_flags`，任务层可自动降级到 `script`。
- 工作区 skill 增加小模型/Ollama 调用规范。

验证:

- `python -m py_compile modules\llm_client.py modules\unified_task_executor.py modules\task_manager.py tests\test_llm_client_ollama.py tests\test_unified_framework.py`
- `python -m unittest tests.test_llm_client_ollama tests.test_unified_framework`
- `py -3.11 -m unittest ...` 宽回归集合 73 个测试通过

### 27. AI Agent 工作区 Skill 完善升级

报告/方案:

- `log/feature_development/2026-04-25_AIAgent工作区Skill完善升级.md`
- `docs/project/AI_AGENT_SKILL_UPGRADE_DESIGN_2026-04-25.md`

产出:

- `docs/agent_skills/historyresearch-workspace/references/agent_playbooks.md`
- `docs/agent_skills/historyresearch-workspace/references/acceptance_checklists.md`
- `docs/agent_skills/historyresearch-workspace/scripts/validate_workspace_skill.py`

关键结果:

- Skill 现在包含小模型友好的操作 playbook、验收清单和只读结构校验脚本。
- 校验脚本确认工作区锚点与 skill 结构完整，并跳过 `secrets/`。

验证:

- `python docs\agent_skills\historyresearch-workspace\scripts\validate_workspace_skill.py .`
- `python -m py_compile docs\agent_skills\historyresearch-workspace\scripts\validate_workspace_skill.py`
- `py -3.11 -m unittest ...` 宽回归集合 76 个测试通过

### 28. AcademicNoteGenerator 笔记 Package 接口优化

报告:

- `log/feature_development/2026-04-25_AcademicNoteGenerator笔记Package接口优化.md`

产出:

- `modules/academic_note_generator.py`
- `tools/workflow/stages/stage2_organize.py`
- `tests/test_academic_note_generator_package.py`
- `tests/test_stage2_note_chain.py`

关键结果:

- 新增 `get_capabilities()`、`generate_reading_note_package()` 与 `batch_process_package()`。
- Stage 2 优先消费 `academic_note` package，并记录 `execution_summary.note_packages`。
- 失败路径统一回收为 `note_generation_fallback_used` 与 `script/fallback`。

验证:

- `python -m py_compile modules\academic_note_generator.py tools\workflow\stages\stage2_organize.py tests\test_academic_note_generator_package.py tests\test_stage2_note_chain.py`
- `python -m unittest tests.test_academic_note_generator_package tests.test_stage2_note_chain`
- `py -3.11 -m unittest ...` 宽回归集合 76 个测试通过

### 29. PaperPolisher 写作润色 Package 接口优化

报告:

- `log/feature_development/2026-04-25_PaperPolisher写作润色Package接口优化.md`

产出:

- `modules/paper_polisher.py`
- `tools/workflow/stages/stage6_polish.py`
- `tests/test_paper_polisher_package.py`

关键结果:

- 新增 `polish_text_package()`、`polish_paragraph_package()` 与 `process_document_package()`。
- Stage 6 优先消费 `paper_polish` package，并记录 `package_type/quality_flags`。
- 旧润色与 DOCX 接口保持兼容。

验证:

- `python -m py_compile modules\paper_polisher.py tools\workflow\stages\stage6_polish.py tests\test_paper_polisher_package.py tests\test_stage5_stage6_writing_chain.py`
- `python -m unittest tests.test_paper_polisher_package tests.test_stage5_stage6_writing_chain`
- `py -3.11 -m unittest ...` 宽回归集合 79 个测试通过

### 30. ReverseOutlineAnalyzer 审校 Package 接口优化

报告:

- `log/feature_development/2026-04-25_ReverseOutlineAnalyzer审校Package接口优化.md`

产出:

- `modules/reverse_outline_analyzer.py`
- `tools/workflow/stages/stage6_polish.py`
- `tests/test_reverse_outline_package.py`

关键结果:

- 新增 `analyze_package()`，输出 `outline_review` envelope。
- Stage 6 优先消费 `outline_review` package，并记录 `package_type/quality_flags`。
- 短草稿、缺失章节、结构失衡、fallback 和低置信度会进入质量标记。

验证:

- `python -m py_compile modules\reverse_outline_analyzer.py tools\workflow\stages\stage6_polish.py tests\test_reverse_outline_package.py tests\test_stage5_stage6_writing_chain.py`
- `python -m unittest tests.test_reverse_outline_package tests.test_stage5_stage6_writing_chain tests.test_paper_polisher_package`
- `py -3.11 -m unittest ...` 宽回归集合 82 个测试通过

### 31. StyleTransfer 文风迁移 Package 接口优化

报告:

- `log/feature_development/2026-04-25_StyleTransfer文风迁移Package接口优化.md`

产出:

- `modules/style_transfer.py`
- `tools/workflow/stages/stage6_polish.py`
- `tests/test_style_transfer_package.py`

关键结果:

- 新增 `transfer_style_package()`，输出 `style_transfer` envelope。
- Stage 6 优先消费 `style_transfer` package，并记录 `package_type/quality_flags`。
- 空输入、空输出、fallback、低置信、长度异常和激进改写风险进入质量标记。

验证:

- `python -m py_compile modules\style_transfer.py tools\workflow\stages\stage6_polish.py tests\test_style_transfer_package.py tests\test_style_transfer_facade.py tests\test_stage5_stage6_writing_chain.py`
- `python -m unittest tests.test_style_transfer_package tests.test_style_transfer_facade tests.test_stage5_stage6_writing_chain tests.test_reverse_outline_package tests.test_paper_polisher_package`
- `py -3.11 -m unittest ...` 宽回归集合 88 个测试通过

### 32. ObsidianIntegration 安全 Vault Package 接口优化

报告:

- `log/feature_development/2026-04-25_ObsidianIntegration安全VaultPackage接口优化.md`

产出:

- `modules/obsidian_integration.py`
- `tools/workflow/stages/stage2_organize.py`
- `tests/test_obsidian_integration_package.py`

关键结果:

- 新增 `get_capabilities()`、`create_note_package()`、`update_note_package()`、`build_knowledge_graph_package()` 与 `export_notes_to_json_package()`。
- 旧 vault 读写接口统一通过托管 vault 边界解析，拒绝路径穿越与 vault 外绝对路径。
- Stage 2 vault 导出优先消费 `obsidian_note_export/obsidian_graph` package，并记录 `vault_packages/graph_package` 摘要。

验证:

- `python -m py_compile modules\obsidian_integration.py tools\workflow\stages\stage2_organize.py tests\test_obsidian_integration_package.py`
- `python -m unittest tests.test_obsidian_integration_package tests.test_stage2_note_chain`
- `py -3.11 -m unittest ...` 宽回归集合 92 个测试通过

### 33. HistoricalSpeechExtractor 发言分析 Package 接口优化

报告:

- `log/feature_development/2026-04-25_HistoricalSpeechExtractor发言分析Package接口优化.md`

产出:

- `modules/historical_speech_extractor.py`
- `tests/test_historical_speech_extractor_package.py`

关键结果:

- 新增 `get_capabilities()`、`process_ocr_result_package()` 与 `analyze_text_package()`。
- 历史发言识别、日期解析和实体附着统一输出 `historical_speech_analysis` envelope。
- 空页、无发言、无日期、无实体等情况进入 `needs_review/quality_flags`。

验证:

- `python -m py_compile modules\historical_speech_extractor.py tests\test_historical_speech_extractor_package.py`
- `python -m unittest tests.test_historical_speech_extractor_package`
- `py -3.11 -m unittest ...` 宽回归集合 95 个测试通过

### 34. EmbeddingManager 轻量检索 Package 接口优化

报告:

- `log/feature_development/2026-04-25_EmbeddingManager轻量检索Package接口优化.md`

产出:

- `modules/embedding_manager.py`
- `tests/test_embedding_manager_package.py`

关键结果:

- 新增 `get_capabilities()`、`create_vector_index_package()` 与 `semantic_search_package()`。
- 默认 `auto_load_models=False`，未显式加载模型时使用确定性 mock embedding，避免自动触发重依赖或外网模型下载。
- `numpy` 改为可选依赖，无 `numpy` 环境下仍可导入、建索引和执行语义检索 smoke。

验证:

- `python -m py_compile modules\embedding_manager.py tests\test_embedding_manager_package.py`
- `python -m unittest tests.test_embedding_manager_package`
- `py -3.11 -m unittest ...` 宽回归集合 98 个测试通过

### 35. NERDisambiguation 实体消歧 Package 接口优化

报告:

- `log/feature_development/2026-04-25_NERDisambiguation实体消歧Package接口优化.md`

产出:

- `modules/ner_disambiguation.py`
- `tools/workflow/stages/stage3_extract.py`
- `tests/test_ner_disambiguation_package.py`

关键结果:

- 新增 `get_capabilities()`、`batch_disambiguate_package()`、`disambiguate_package()` 与 `resolve_relations_package()`。
- NER 后处理统一输出 `entity_disambiguation/entity_relation_resolution` envelope。
- Stage 3 优先记录 `execution_summary.disambiguation_packages`，承载规范名、类型变化、低置信和未知规则摘要。

验证:

- `python -m py_compile modules\ner_disambiguation.py tools\workflow\stages\stage3_extract.py tests\test_ner_disambiguation_package.py`
- `python -m unittest tests.test_ner_disambiguation_package tests.test_stage3_workflow_integration`
- `py -3.11 -m unittest ...` 宽回归集合 102 个测试通过

### 36. HistoryFieldExplorer 领域研究 Package 接口优化

报告:

- `log/feature_development/2026-04-25_HistoryFieldExplorer领域研究Package接口优化.md`

产出:

- `modules/history_field_explorer.py`
- `tools/workflow/stages/stage5_write.py`
- `tests/test_history_field_explorer_facade.py`
- `tests/test_stage5_stage6_writing_chain.py`

关键结果:

- 新增 `explore_package()` 与 `draft_paper_package()`，输出 `field_research/field_draft` envelope。
- `get_capabilities()` 补充 layer、tasks、output_types、supports 和 privacy 字段。
- Stage 5 优先消费 `field_draft` package，并记录 `execution_summary.draft_package`。

验证:

- `python -m py_compile modules\history_field_explorer.py tools\workflow\stages\stage5_write.py tests\test_history_field_explorer_facade.py tests\test_stage5_stage6_writing_chain.py`
- `python -m unittest tests.test_history_field_explorer_facade tests.test_stage5_stage6_writing_chain`
- `py -3.11 -m unittest ...` 宽回归集合 107 个测试通过

### 37. CitationFormatter 格式渲染 Package 接口优化

报告:

- `log/feature_development/2026-04-25_CitationFormatter格式渲染Package接口优化.md`

产出:

- `modules/citation_formats.py`
- `tools/workflow/stages/stage7_format.py`
- `tests/test_citation_formats_package.py`
- `tests/test_stage7_format_chain.py`

关键结果:

- 新增 `get_capabilities()`、`format_record_package()` 与 `format_batch_package()`。
- 引用格式层统一输出 `citation_formatting` envelope。
- Stage 7 记录 `execution_summary.citation_format_package`，承载渲染数量、目标格式、缺失字段和质量标记。

验证:

- `python -m py_compile modules\citation_formats.py tools\workflow\stages\stage7_format.py tests\test_citation_formats_package.py tests\test_stage7_format_chain.py`
- `python -m unittest tests.test_citation_formats_package tests.test_stage7_format_chain tests.test_citation_chain`
- `py -3.11 -m unittest ...` 宽回归集合 109 个测试通过

### 38. HistoricalCitationVerifier 引文核验 Package 接口优化

报告:

- `log/feature_development/2026-04-25_HistoricalCitationVerifier引文核验Package接口优化.md`

产出:

- `modules/historical_citation_verifier.py`
- `tests/test_historical_citation_verifier.py`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `docs/workflow/STAGE_4_7_WRITING_OUTPUT.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- 新增 `get_capabilities()`、`parse_docx_package()` 与 `verify_docx_package()`。
- 引文核验链路统一输出 `historical_citation_parse/historical_citation_verification` envelope。
- 默认解析保持离线；外部检索、下载和 OCR 由调用方显式开启，并通过 `quality_flags` 回收复核信号。

验证:

- `python -m py_compile modules\historical_citation_verifier.py tests\test_historical_citation_verifier.py`
- `python -m unittest tests.test_historical_citation_verifier`
- `py -3.11 -m unittest ...` 宽回归集合 157 个测试通过，2 个旧可选依赖用例跳过

### 39. UniversalLayoutAnalyzer 最小版面 Package 接口优化

报告:

- `log/feature_development/2026-04-25_UniversalLayoutAnalyzer最小版面Package接口优化.md`

产出:

- `modules/universal_layout_analyzer.py`
- `tests/test_universal_layout_analyzer_package.py`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `docs/workflow/STAGE_1_3_INGEST_ANALYSIS.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- 新增 `get_capabilities()`、`analyze_page_package()` 与 `analyze_document_package()`。
- 版面分析统一输出 `layout_page/layout_document` envelope。
- `fitz/numpy/PIL` 改为可选依赖，metadata-only 路径不加载 ONNX 或 PDF/图像重依赖。

验证:

- `python -m py_compile modules\universal_layout_analyzer.py tests\test_universal_layout_analyzer_package.py`
- `python -m unittest tests.test_universal_layout_analyzer_package`
- `py -3.11 -m unittest ...` 宽回归集合 161 个测试通过，2 个旧可选依赖用例跳过

### 40. PDFDateMatcher 训练样本 Package 接口优化

报告:

- `log/feature_development/2026-04-25_PDFDateMatcher训练样本Package接口优化.md`

产出:

- `modules/pdf_date_matcher.py`
- `tests/test_pdf_date_matcher_package.py`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `docs/workflow/STAGE_1_3_INGEST_ANALYSIS.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- 新增 `get_capabilities()`、`parse_annotation_dates_package()`、`match_dates_package()` 与 `generate_training_data_package()`。
- 训练准备链路统一输出 `date_extraction/date_match_pairs/training_samples` envelope。
- 默认不读取本地配置密钥文件；远程 LLM 日期识别必须显式开启。

验证:

- `python -m py_compile modules\pdf_date_matcher.py tests\test_pdf_date_matcher_package.py`
- `python -m unittest tests.test_pdf_date_matcher_package`
- `py -3.11 -m unittest ...` 宽回归集合 165 个测试通过，2 个旧可选依赖用例跳过

### 41. ClassicalOCRTrainingWorkflow 训练总线 Package 接口优化

报告:

- `log/feature_development/2026-04-25_ClassicalOCRTrainingWorkflow训练总线Package接口优化.md`

产出:

- `modules/classical_ocr_training_workflow.py`
- `tests/test_classical_ocr_training_workflow_package.py`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `docs/workflow/STAGE_1_3_INGEST_ANALYSIS.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- 新增 `get_capabilities()`、`build_summary_package()` 与 `build_training_samples_package()`。
- 训练总线统一输出 `training_workflow_summary/training_samples` envelope。
- `fitz/numpy/PIL` 改为可选依赖，真实 PDF/图像处理缺依赖时返回结构化失败结果。

验证:

- `python -m py_compile modules\classical_ocr_training_workflow.py tests\test_classical_ocr_training_workflow_package.py`
- `python -m unittest tests.test_classical_ocr_training_workflow_package`
- `py -3.11 -m unittest ...` 宽回归集合 168 个测试通过，2 个旧可选依赖用例跳过

### 42. BiographyExtractor 人物传记 Package 接口优化

报告:

- `log/feature_development/2026-04-25_BiographyExtractor人物传记Package接口优化.md`

产出:

- `modules/biography_extractor.py`
- `tests/test_biography_extractor_package.py`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `docs/workflow/STAGE_1_3_INGEST_ANALYSIS.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- 新增 `get_capabilities()`、`extract_entities_package()` 与 `process_ocr_results_package()`。
- 人物传记结构化统一输出 `biography_entities/biography_batch` envelope。
- 默认不读取 `secrets/`；PDF 转图、NDL OCR、LLM OCR 均延迟到真实执行时加载。

验证:

- `python -m py_compile modules\biography_extractor.py tests\test_biography_extractor_package.py`
- `python -m unittest tests.test_biography_extractor_package`
- `py -3.11 -m unittest ...` 宽回归集合 172 个测试通过，2 个旧可选依赖用例跳过

### 43. BiographicalNER 离线规则库 Package 接口优化

报告:

- `log/feature_development/2026-04-25_BiographicalNER离线规则库Package接口优化.md`

产出:

- `modules/biographical_ner.py`
- `tests/test_biographical_ner_package.py`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `docs/workflow/STAGE_1_3_INGEST_ANALYSIS.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- 修复 `WorkExperience.position` 语法错误。
- 新增 `get_capabilities()`、`process_text_blocks_package()` 与 `extract_biographical_entities_package()`。
- 人物传记规则库统一输出 `biography_entities` envelope，并保持纯本地离线职责。

验证:

- `python -m py_compile modules\biographical_ner.py tests\test_biographical_ner_package.py`
- `python -m unittest tests.test_biographical_ner_package`
- `py -3.11 -m unittest ...` 宽回归集合 175 个测试通过，2 个旧可选依赖用例跳过

### 44. BiographyPipeline 薄封装 Package 接口优化

报告:

- `log/feature_development/2026-04-25_BiographyPipeline薄封装Package接口优化.md`

产出:

- `modules/biography_pipeline.py`
- `tests/test_biography_pipeline_package.py`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `docs/workflow/STAGE_1_3_INGEST_ANALYSIS.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- 新增 `get_capabilities()`、`process_ocr_results_package()` 与 `build_summary_package()`。
- 人物传记流程包装层统一输出 `biography_batch/biography_pipeline_summary` envelope。
- PDF 转图改为延迟导入，该模块定位为薄工作流封装。

验证:

- `python -m py_compile modules\biography_pipeline.py tests\test_biography_pipeline_package.py`
- `python -m unittest tests.test_biography_pipeline_package`
- `py -3.11 -m unittest ...` 宽回归集合 178 个测试通过，2 个旧可选依赖用例跳过

### 45. 模块优化总体进度报告

报告:

- `docs/project/MODULE_OPTIMIZATION_PROGRESS_2026-04-25.md`

关键结果:

- 当前 package/envelope 主链已覆盖 OCR、NER、笔记、Obsidian、写作、引用、版面、训练准备与人物传记。
- 估算剩余优化工作约 30-35 个步骤；若只追求 package 调用闭环，则约 15-18 个步骤。
- 建议下一阶段优先处理 `task_manager.py`、`unified_task_executor.py`、`module_adapters.py`、`ResearchProject` 与 `workflow_orchestrator.py`。

### 46. TaskManager 统一任务注册层 Package 优化

报告:

- `log/feature_development/2026-04-25_TaskManager_unified_task_registry_package.md`

产出:

- `modules/task_manager.py`
- `tests/test_unified_framework.py`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `GUIDELINES.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- 新增 `TaskRegistryEntry`、`get_task_registry()`、`get_preset_options()`、`get_history_summary()` 与 `get_capabilities()`。
- 新增 `execute_task_package()`，统一输出 `task_execution` envelope，供 API、skill、MCP 与小模型 agent 调用。
- 现有 adapter 调度和 legacy 方法保持兼容。

验证:

- `python -m py_compile modules\task_manager.py tests\test_unified_framework.py`
- `python -m unittest tests.test_unified_framework`
- 14 个测试通过。

### 47. UnifiedTaskExecutor validation/artifact 协议优化

报告:

- `log/feature_development/2026-04-25_UnifiedTaskExecutor_validation_artifact_protocol.md`

产出:

- `modules/unified_task_executor.py`
- `tests/test_unified_framework.py`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- 新增 `TaskResult.to_package()` 与 `UnifiedTaskExecutor.execute_package()`。
- 每次执行结果记录 `validation/confidence/needs_review/quality_flags`。
- 新增显式 `write_execution_artifact()`，默认不写文件，且拒绝写入 `secrets/`。

验证:

- `python -m py_compile modules\unified_task_executor.py tests\test_unified_framework.py`
- `python -m unittest tests.test_unified_framework`
- 17 个测试通过。

### 48. module_adapters registry 薄封装优化

报告:

- `log/feature_development/2026-04-25_module_adapters_registry_package.md`

产出:

- `modules/module_adapters.py`
- `tests/test_unified_framework.py`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- 新增 `AdapterSpec` 与 adapter registry/spec 查询函数。
- `BaseAdapter.get_capabilities()` 附带 adapter spec。
- 新增 `BaseAdapter.execute_package()`，adapter 层可直接输出 `task_execution` envelope。

验证:

- `python -m py_compile modules\module_adapters.py tests\test_unified_framework.py`
- `python -m unittest tests.test_unified_framework`
- 19 个测试通过。

### 49. ResearchProject artifact/review/quality 统一挂载优化

报告:

- `log/feature_development/2026-04-25_ResearchProject_artifact_review_quality_mount.md`

产出:

- `tools/workflow/research_project.py`
- `tests/test_research_project_artifact_manager.py`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- 新增 `register_package()`、`register_artifact()`、`add_quality_flags()`、`get_artifact_summary()` 与 `get_quality_summary()`。
- artifact 和 review item 自动补充 id/timestamp，并将 id 回写到 stage metadata。
- package 的 artifacts、quality flags、needs_review 可统一挂载到项目状态。

验证:

- `python -m py_compile tools\workflow\research_project.py tests\test_research_project_artifact_manager.py`
- `python -m unittest tests.test_research_project_artifact_manager tests.test_stage3_workflow_integration tests.test_workflow_orchestrator_stage4`
- 7 个测试通过。

### 50. WorkflowOrchestrator checkpoint/failure package 优化

报告:

- `log/feature_development/2026-04-25_WorkflowOrchestrator_checkpoint_failure_package.md`

产出:

- `tools/workflow/workflow_orchestrator.py`
- `tests/test_workflow_orchestrator_stage4.py`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- 成功 checkpoint 继续以项目 artifact 登记，final checkpoint 也进入 artifact 列表。
- 阶段失败统一登记 `workflow_stage_failure` package。
- 失败 package 会写入 failed checkpoint artifact、`stageN_failed` quality flag、review queue 与 `failure_package` metadata。

验证:

- `python -m py_compile tools\workflow\workflow_orchestrator.py tests\test_workflow_orchestrator_stage4.py`
- `python -m unittest tests.test_workflow_orchestrator_stage4 tests.test_research_project_artifact_manager`
- 6 个测试通过。

### 51. Stage3 统一任务层快照与 package 执行优化

报告:

- `log/feature_development/2026-04-25_Stage3_task_layer_snapshot_package_execution.md`

产出:

- `tools/workflow/stages/stage3_extract.py`
- `tests/test_stage3_workflow_integration.py`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- Stage 3 新增 `task_layer_snapshot`，记录 NER options、registry 和脱敏能力摘要。
- NER 调用优先使用 `TaskManager.execute_task_package()`，旧 `execute_task()` 自动 fallback。
- Stage 3 package summary 现在包含 `task_package` 摘要。

验证:

- `python -m py_compile tools\workflow\stages\stage3_extract.py tests\test_stage3_workflow_integration.py`
- `python -m unittest tests.test_stage3_workflow_integration`
- 2 个测试通过。

### 52. KeyManager 脱敏状态 facade 优化

报告:

- `log/feature_development/2026-04-25_KeyManager_redacted_status_facade.md`

产出:

- `modules/secure_api_key_manager.py`
- `config/api_key_manager.py`
- `tests/test_unified_framework.py`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- `SecureAPIKeyManager.get_status_report()` 默认返回 redacted 状态。
- key hash 与真实 secrets 路径必须显式参数开启。
- legacy `APIKeyManager` 也提供统一脱敏状态入口。

验证:

- `python -m py_compile modules\secure_api_key_manager.py config\api_key_manager.py tests\test_unified_framework.py`
- `python -m unittest tests.test_unified_framework`
- 20 个测试通过。

### 53. API lazy service/app factory 优化

报告:

- `log/feature_development/2026-04-25_API_lazy_service_app_factory.md`

产出:

- `app/app.py`
- `tests/test_api_app_factory.py`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- `LazyService` 新增可观测状态字段。
- 新增 `LAZY_SERVICES`、`get_service_status()`、`create_app()` 与 `/api/system/status`。
- API 状态端点不会初始化重服务。

验证:

- `python -m py_compile app\app.py tests\test_api_app_factory.py`
- `python -m unittest tests.test_api_app_factory`
- 1 个测试因当前环境缺少 Flask 按可选依赖规则跳过。

### 54. ArtifactManager/environment package 优化

报告:

- `log/feature_development/2026-04-25_ArtifactManager_environment_package.md`

产出:

- `modules/artifact_manager.py`
- `modules/environment_checker.py`
- `tests/test_environment_checker_structured.py`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- 新增 managed-root `ArtifactManager`。
- 环境检查器新增 capabilities 与 `environment_report` package。
- artifact 写入默认关闭，显式写入也拒绝 `secrets/` 与托管 root 外路径。

验证:

- `python -m py_compile modules\artifact_manager.py modules\environment_checker.py tests\test_environment_checker_structured.py`
- `python -m unittest tests.test_environment_checker_structured`
- 3 个测试通过。

### 55. 优化分支归档 manifest

报告:

- `log/feature_development/2026-04-25_optimization_branch_archive_manifest.md`

产出:

- `docs/project/OPTIMIZATION_BRANCH_ARCHIVE_2026-04-25.md`
- `archive/2026-04-25/OPTIMIZATION_BRANCH_ARCHIVE_MANIFEST.md`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- 已扫描 optimized/enhanced/integrated 候选分支文件。
- 由于仍存在直接测试引用和动态导入，本轮只执行 manifest 归档，不移动代码。
- 后续物理归档条件已写入归档计划。

验证:

- 引用扫描确认 `paper_polisher_optimized.py` 与 NER optimized/integrated 链路仍需保留。
- 未执行删除、移动或破坏性命令。

### 56. 连续任务层优化队列完成总结

报告:

- `docs/project/MODULE_OPTIMIZATION_PROGRESS_2026-04-25_TASK_LAYER_COMPLETION.md`
- `log/feature_development/2026-04-25_task_layer_completion_summary.md`

关键结果:

- 统一任务层、API lazy service、artifact manager、ResearchProject package 挂载、workflow failure package、Stage 3 task layer snapshot、密钥状态脱敏与优化分支归档 manifest 均已完成。
- 优化分支物理移动因仍有测试/动态导入引用而安全延后。

验证:

- targeted: 32 tests passed, 1 skipped.
- wide regression: 194 tests passed, 2 skipped.
- `git diff --check`: 无空白错误，仅 CRLF 提示。

### 57. Stage2 package 项目状态挂载优化

报告:

- `log/feature_development/2026-04-25_Stage2_package_project_mount.md`

产出:

- `tools/workflow/stages/stage2_organize.py`
- `tests/test_stage2_note_chain.py`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- academic note package、Obsidian note export package 和 graph package 进入 `ResearchProject.register_package()`。
- Obsidian vault artifact 改用 `ResearchProject.register_artifact()`。
- 原有 execution_summary 结构保持兼容。

验证:

- `python -m py_compile tools\workflow\stages\stage2_organize.py tests\test_stage2_note_chain.py`
- `python -m unittest tests.test_stage2_note_chain tests.test_research_project_artifact_manager`
- 5 个测试通过。

### 58. Stage4 citation/outline package 项目状态挂载优化

报告:

- `log/feature_development/2026-04-25_Stage4_package_project_mount.md`

产出:

- `tools/workflow/stages/stage4_examine.py`
- `tests/test_workflow_orchestrator_stage4.py`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- citation network package 进入 `ResearchProject.register_package()`。
- outline review 新增 package 包装并进入项目级 package/review 协议。
- execution_summary 保持兼容。

验证:

- `python -m py_compile tools\workflow\stages\stage4_examine.py tests\test_workflow_orchestrator_stage4.py`
- `python -m unittest tests.test_workflow_orchestrator_stage4`
- 4 个测试通过。

### 59. Stage5 draft package 项目状态挂载优化

报告:

- `log/feature_development/2026-04-25_Stage5_draft_package_project_mount.md`

产出:

- `tools/workflow/stages/stage5_write.py`
- `tests/test_stage5_stage6_writing_chain.py`
- `README.md`
- `WORKFLOW_DESIGN.md`
- `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

关键结果:

- `field_draft` package 现在进入 `ResearchProject.register_package()`。
- Stage 5 会生成并登记统一 `paper_draft` package。
- source snapshot 与 execution_summary 保持兼容。

验证:

- `python -m py_compile tools\workflow\stages\stage5_write.py tests\test_stage5_stage6_writing_chain.py`
- `python -m unittest tests.test_stage5_stage6_writing_chain`
- 3 个测试通过。

### 60. Historical Citation 工作区接入与隐私加固

报告:

- `log/feature_development/2026-04-28_HistoricalCitationWorkspaceIntegration_PrivacyHardening.md`

产出:

- `modules/historical_citation_workspace.py`
- `modules/module_adapters.py`
- `modules/task_manager.py`
- `app/app.py`
- `scripts/check_github_upload_safety.py`
- `config/api_config.json`
- `config/current_environment.json`
- `config/external_config.json`
- `tests/test_historical_citation_workspace.py`

关键结果:

- history-citation 原始模块文件未改动；工作区统一调用通过安全外壳、adapter、TaskManager 和 API 端点完成。
- 三份 tracked 配置已隐私化为公共模板，安全脚本改为内容级配置审查与 secret-like 扫描。
- NDL 账号、密码、登录名扫描高风险命中为 0；旧脚本硬编码 key/token 风险已替换为环境变量读取。

验证:

- `python -m unittest discover tests`
- 292 tests OK, skipped=13。
- `python scripts/check_github_upload_safety.py`
- Result: clean。
