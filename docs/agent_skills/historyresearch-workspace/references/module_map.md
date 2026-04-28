# Module Map

Core/task layer:

- `modules/llm_client.py`
- `modules/task_manager.py`
- `modules/unified_task_executor.py`
- `modules/module_adapters.py`
- `modules/environment_checker.py`

Ingest/OCR layer:

- `modules/pdf_processor.py`
- `modules/pdf_image_converter.py`
- `modules/ocr_processor.py`
- `modules/unified_ocr_processor.py`
- `modules/llm_ocr_processor.py`
- `modules/ndlocr_lite.py`
- `modules/ndlkotenocr_lite.py`
- `modules/ndl_ocr_batch_processor.py`
- `modules/ndlocr_result_processor.py`

Analysis layer:

- `modules/ner_processor.py`
- `modules/ner_disambiguation.py`
- `modules/citation_normalizer.py`
- `modules/citation_network_analyzer.py`
- `modules/history_field_explorer.py`
- `modules/academic_summarizer.py`

Writing/workflow layer:

- `modules/academic_note_generator.py`
- `modules/paper_polisher.py`
- `modules/reverse_outline_analyzer.py`
- `modules/style_transfer.py`
- `tools/workflow/research_project.py`
- `tools/workflow/workflow_orchestrator.py`
- `tools/workflow/stages/`
