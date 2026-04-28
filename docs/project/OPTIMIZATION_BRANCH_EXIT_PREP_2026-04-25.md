# Optimization Branch Exit Prep

Date: 2026-04-25

## Decision

Do not physically move `optimized`, `enhanced`, or `integrated` files in this step. The workspace still contains active references that make a pure archive move risky.

## Active References

- `tests/test_paper_polisher_optimized.py` imports `modules.paper_polisher_optimized` directly.
- `modules/ner_processor_integrated.py` dynamically imports `modules.ner_processor_optimized` when `use_optimized=True`.

## Candidate Archive Files

- `modules/academic_note_generator_optimized.py`
- `modules/academic_summarizer_optimized.py`
- `modules/llm_client_optimized.py`
- `modules/ocr_processor_optimized.py`
- `modules/paper_polisher_enhanced.py`
- `modules/pdf_processor_optimized.py`
- `modules/word_processor_optimized.py`
- `modules/prompts/ner_processor_prompts_optimized.md`

## Temporary Keep Files

- `modules/paper_polisher_optimized.py`: kept because a test imports it directly.
- `modules/ner_processor_optimized.py`: kept because `ner_processor_integrated.py` dynamically imports it.
- `modules/ner_processor_integrated.py`: kept as a compatibility bridge until the canonical NER package path fully replaces it.

## Required Follow-Up

- Replace direct optimized tests with canonical package/facade tests.
- Decide whether `ner_processor_integrated.py` is still a compatibility facade or should be absorbed into `ner_processor.py`.
- Only after the above, move branch files to a dated archive directory with a rollback note.

## Privacy And Cleanup

- No secrets were read.
- No files were moved or deleted.
- No temporary scripts were created.
