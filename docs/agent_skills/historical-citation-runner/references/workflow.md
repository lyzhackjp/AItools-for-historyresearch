# Historical Citation Module Workflow Reference

## Stable Entrypoints

- `scripts/resume_historical_citation_verifier.py`: main checkpointed runner for DOCX parsing, source search, page mapping, restricted download, OCR, alignment, and report generation.
- `scripts/probe_ndl_fulltext_context.py`: target-PID NDL fulltext snippet probing and snippet-edge context expansion.
- `scripts/cross_validate_ndl_fulltext_ocr.py`: cross-validate checkpoint OCR text against NDL fulltext snippets.
- `modules.historical_citation_verifier.HistoricalCitationVerifier`: facade for Python callers.
- `modules.historical_citation.cross_validation`: reusable Python API for fulltext/OCR cross-validation.
- `modules.historical_citation.ndl_fulltext_context`: reusable Python API for NDL fulltext probes.

## Private Data Rules

- Use `output/` for all run products.
- Use `secrets/` or environment variables for NDL credentials.
- Keep paper-specific contained-source mappings outside Git via `HISTORICAL_CITATION_CONTAINED_SOURCE_CONFIG`.
- Run `py -3.11 scripts\check_github_upload_safety.py` after substantial work.

## Contained Works

The parser can infer common host-volume relations from footnotes and from configured mappings. Search order should prefer host volume for acquisition while preserving contained title for fulltext queries.

Expected metadata fields:

- `host_title`: downloadable/searchable host source.
- `contained_title`: article/speech/section named in the footnote.
- `source_relation`: usually `contained_in_host`.

## NDL Fulltext

Use target PID `SNIPPET` hits as weak page evidence. Use `CONTENT` only when available; restricted items often return SNIPPET but not CONTENT. Fulltext PDF pages are scan/PDF pages, not automatically cited book pages.

Use snippet-edge expansion only as a context window. It must keep `pid`, `cid`, and `pdf_page` visible and must not be described as OCR or complete paragraph evidence.

## Cross-Validation Case JSON

Use private JSON under `output/`.

```json
[
  {
    "label": "short case label",
    "paper_label": "paper label",
    "checkpoint": "output/run/resume_checkpoint.json",
    "candidate_id": "p5-f4",
    "pid": "1234567",
    "mode": "downloadable_ocr",
    "queries": ["exact source phrase", "fallback phrase"]
  }
]
```

Modes:

- `downloadable_ocr`: requires a checkpoint candidate with `source_pdf`, `downloaded_page_range`, and `matched_japanese`.
- `fulltext_only`: for download failures or unavailable PDFs where NDL fulltext snippets still return page hints.

## Recommended Run Pattern

1. Search-only across the document.
2. Inspect report and choose a small batch of candidates.
3. Run download/OCR for selected candidates.
4. Probe NDL fulltext for download failures or suspicious OCR matches.
5. Cross-validate selected OCR/fulltext pairs.
6. Generate or update final local Markdown report.
