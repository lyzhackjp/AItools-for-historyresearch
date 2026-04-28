# Historical Citation Verifier Optimization Plan

Last updated: 2026-04-26

## Goal

Improve the historical citation verifier so it can safely handle Word-paper citation checks against NDL and future online historical-source platforms without mixing private test documents, downloaded sources, or output reports into repository code.

## Current Focus

The implemented 2026-04-26 improvement targets NDL Search candidates that only provide an NDL Search detail-page URL and no direct `dl.ndl.go.jp` PID.

Implemented behavior:

- Resolve `ndlsearch.ndl.go.jp/books/...` detail pages before restricted download.
- Accept only PIDs explicitly embedded in the detail page.
- Record `no_digital_pid` when a page is metadata-only or physical-holding-only.
- Preserve related NDL Search book IDs as diagnostics, but do not treat them as downloadable replacements.
- Reuse the same resolver for fresh searches and checkpoint-resume runs.
- Keep restricted download conservative: no explicit PID means no browser download attempt.

## Modular Direction

1. `ndl_search.py`
   Owns NDL metadata search, scoring helpers, and detail-page PID resolution.

2. `source_platforms.py`
   Owns platform adapters. Each future source platform should expose search, preferred-match selection, public download, and restricted-download request construction.

3. `historical_citation_verifier.py`
   Remains the facade and orchestration layer while smaller modules are stabilized.

4. `source_acquisition.py`
   Owns page-window plans, preferred source selection, and PDF acquisition helpers.

5. `page_mapping.py`
   Owns book-page to scan-page mapping and persistent mapping/failure caches.

6. `pdf_ocr.py`
   Owns PDF page extraction, double-spread handling, OCR dispatch, and readiness checks.

7. `reporting.py`
   Owns Markdown/JSON report rendering from checkpoint data.

## Next Platform Adapter Template

For additional public historical-source platforms, implement:

- Metadata search from title, author, year, and publisher anchors.
- Detail-page resolver that turns a landing-page URL into a stable item ID or download URL.
- Availability probe that can distinguish public PDF, account-gated PDF, metadata-only record, and remote-copy-only record.
- Page-window download builder with deterministic filenames.
- Source-specific failure notes that map into shared statuses.

## Safety Rules

- Private papers, footnotes, OCR text, downloaded PDFs, screenshots, and reports stay under ignored output directories.
- Repository code and docs must not contain paper text, source excerpts, credentials, or generated comparison reports.
- URL-only NDL Search candidates must not trigger broad keyword downloads unless a resolver finds an explicit PID.
- Related-item IDs may be stored as diagnostics, but must not be used as replacements without a platform-specific relationship check.

## Verification

Required before handoff:

```powershell
py -3.11 -m unittest tests.test_historical_citation_verifier
py -3.11 scripts\check_github_upload_safety.py
git check-ignore -v output\historical_citation_huazu_20260425\resume_checkpoint.json output\historical_citation_huazu_20260425\partial_resume_report.md
```
