# GitHub Upload Exclusion Policy

This workspace separates clean code modules from local research materials. The code, tests, and reusable documentation may be committed. Source papers, downloaded literature, OCR outputs, browser screenshots, checkpoints, and generated reports must stay local.

## Never Upload

- User-supplied papers or reference documents, including Word, PDF, spreadsheet, slide, and scanned-image files.
- NDL downloads, restricted-download files, IIIF images, page screenshots, browser/OpenClaw session files, cookies, and storage state.
- OCR outputs and intermediate data, including page images, XML, TXT, JSON checkpoints, CSV tables, JSONL exports, and merged OCR text.
- Historical-citation run outputs, including `partial_resume_report.md`, `resume_checkpoint.json`, `page_mapping_cache.json`, `page_map_*`, `spread_scan_*`, and `ocr_page_*`.
- API keys, secrets, local environment files, account state, cookies, and local config backups.
- Local research folders such as `output/`, `ocr_output/`, `workflow_output/`, `local_research_data/`, `research_data/`, `materials/`, `sources/`, and `corpus/`.

## Allowed

- Pure Python modules under `modules/`, reusable workflow code under `tools/` and `scripts/`, and unit tests that use synthetic fixtures.
- Documentation about architecture, usage, or development plans, as long as it does not contain copied paper text, downloaded source passages, account state, or run outputs.
- Small synthetic examples that are clearly invented and cannot reconstruct a user-supplied document or restricted source.

## Current Guardrails

- `.gitignore` blocks common research-material extensions and local output directories.
- `scripts/check_github_upload_safety.py` checks tracked files and untracked non-ignored files against this policy.
- If the checker reports a tracked high-risk file, do not push until it is either intentionally retained after review or removed from Git tracking with a separate cleanup decision.

## Pre-Push Check

Run:

```powershell
py -3.11 scripts\check_github_upload_safety.py
```

Treat `TRACKED HIGH RISK` as a stop sign. Treat `UNTRACKED NOT IGNORED HIGH RISK` as a `.gitignore` gap that should be fixed before committing.
