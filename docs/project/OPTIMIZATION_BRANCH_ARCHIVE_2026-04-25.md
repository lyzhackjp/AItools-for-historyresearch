# Optimization Branch Archive Plan

Date: 2026-04-25

## Scope

This plan covers visible `optimized`, `enhanced`, and `integrated` branch-style files in the active workspace. It does not move code automatically because several candidates still have direct tests or dynamic imports.

## Archive Decision

- `modules/academic_note_generator_optimized.py`: candidate for archival after `academic_note_generator.py` package/facade coverage is confirmed as complete.
- `modules/academic_summarizer_optimized.py`: candidate for archival after `academic_summarizer.py` package output remains the canonical summary entry.
- `modules/llm_client_optimized.py`: candidate for archival after `modules/llm_client.py` Ollama/API fallback and redacted metadata coverage is confirmed as canonical.
- `modules/ner_processor_optimized.py`: candidate for staged archival only after `ner_processor.py`, `TaskManager`, and Stage 3 package paths fully absorb dictionary validation behavior.
- `modules/ner_processor_integrated.py`: keep temporarily; it dynamically bridges optimized NER behavior and should be retired only after Stage 3 no longer needs compatibility.
- `modules/ocr_processor_optimized.py`: candidate for archival after `ocr_processor.py` and `unified_ocr_processor.py` package paths are accepted as canonical.
- `modules/paper_polisher_enhanced.py`: candidate for archival after Stage 6 uses package-first `PaperPolisher` and style/outline modules.
- `modules/paper_polisher_optimized.py`: keep temporarily; existing tests still import it directly.
- `modules/pdf_processor_optimized.py`: candidate for archival after `pdf_processor.py` and `pdf_image_converter.py` package paths remain canonical.
- `modules/word_processor_optimized.py`: candidate for archival after document/Word export package path is checked.
- `modules/prompts/ner_processor_prompts_optimized.md`: candidate for prompt archive after NER prompt ownership is documented.

## Non-Archive Items

- `modules/integration_manager.py`: active integration layer, not an optimization branch solely by name.
- `modules/obsidian_integration.py`: active vault integration module, not an optimization branch.
- `modules/docs/classical_ocr_training_workflow_integration.md`: documentation, not a code branch.
- `modules/history_field_explorer.py`: contains "Enhanced Edition" in description but is the active module.

## Execution Rule

Code files are not moved until all of the following are true:

- No active tests import the branch file.
- No active module dynamically imports the branch file.
- Canonical package/facade replacement has coverage.
- A rollback note is written in the archive manifest.

## Current Result

Archive execution is complete at the manifest level. Physical code movement is intentionally deferred for safety.

## 2026-04-25 Exit Prep Update

The current exit-prep scan keeps physical movement deferred. Active references remain:

- `tests/test_paper_polisher_optimized.py` imports `modules.paper_polisher_optimized` directly.
- `modules/ner_processor_integrated.py` dynamically imports `modules.ner_processor_optimized` when `use_optimized=True`.

Archive candidates without direct active imports in the latest scan:

- `modules/academic_note_generator_optimized.py`
- `modules/academic_summarizer_optimized.py`
- `modules/llm_client_optimized.py`
- `modules/ocr_processor_optimized.py`
- `modules/paper_polisher_enhanced.py`
- `modules/pdf_processor_optimized.py`
- `modules/word_processor_optimized.py`
- `modules/prompts/ner_processor_prompts_optimized.md`

Exit criteria before physical movement:

- Add or confirm canonical package/facade tests for each replacement module.
- Retire or rewrite direct optimized test imports.
- Remove the dynamic optimized NER bridge or mark it as a stable compatibility facade.
- Keep rollback notes in this manifest before any file move.
