---
name: historical-citation-runner
description: Run the AItools-for-historyresearch historical citation module for private Japanese historical-source citation checks. Use when Codex needs to process .docx papers, parse footnotes, search NDL including contained works, download/OCR cited pages, use NDL fulltext snippets, cross-validate OCR against fulltext hits, resume checkpoints, or produce local reports under ignored output/ without exposing paper content or credentials.
---

# Historical Citation Runner

## Core Rule

Keep private inputs, OCR text, checkpoints, reports, PDFs, screenshots, and credentials out of Git. Put run artifacts under `output/`. Put NDL credentials only in environment variables or ignored `secrets/`.

## Workflow

1. Confirm workspace root is `AItools-for-historyresearch`.
2. If a `.docx` path is supplied, run a lightweight search first:

```powershell
py -3.11 scripts\resume_historical_citation_verifier.py "<DOCX>" --output-dir output\<RUN_ID> --search-only --no-ndl-browser-fallback --progress-json
```

3. Review `output\<RUN_ID>\partial_resume_report.md` and identify candidates worth downloading/OCR.
4. Resume selected candidates with NDL/OCR:

```powershell
py -3.11 scripts\resume_historical_citation_verifier.py "<DOCX>" --output-dir output\<RUN_ID> --only-candidate-id <CID> --ocr-model ndlocr_lite --page-window 4 --ocr-page-window 2 --progress-json
```

5. For contained works, rely on parsed `host_title`/`contained_title`. If needed, add private mappings through `HISTORICAL_CITATION_CONTAINED_SOURCE_CONFIG`; do not edit source code with paper-specific mappings.
6. For sources that cannot be downloaded but have NDL fulltext hits, probe target PID snippets:

```powershell
py -3.11 scripts\probe_ndl_fulltext_context.py --pid <PID> --keyword "<TERM>" --expand --output output\<RUN_ID>\ndl_fulltext_probe_<CID>.md
```

7. For OCR/fulltext cross-validation, create a private cases JSON in `output/` and run:

```powershell
py -3.11 scripts\cross_validate_ndl_fulltext_ocr.py --cases output\<RUN_ID>\cross_validation_cases.json --output output\<RUN_ID>\cross_validation_report.md --json-output output\<RUN_ID>\cross_validation_report.json
```

## Evidence Labels

- `matched` or `cross_validated`: OCR/download evidence and NDL fulltext agree enough for strong support.
- `page_cross_validated_text_needs_review`: page agrees, text needs manual review.
- `fulltext_only_hit`: NDL fulltext provides PDF-page weak evidence, but no OCR/download proof.
- `source_unavailable`, `source_not_found`, `page_mapping_unavailable`: report as unresolved; do not force a match.

## Small Model Guardrails

- Prefer exact commands over inventing new code.
- Process a few candidates at a time with `--only-candidate-id`.
- Never paste full paper text into chat. Summarize statuses and point to local report paths.
- If search text becomes `????`, rerun using JSON/config files or Unicode escapes; do not trust the result.
- If NDL PDF pages and cited book pages disagree, treat NDL pages as scan/PDF pages until page mapping confirms otherwise.

For more detail, read `references/workflow.md`.
