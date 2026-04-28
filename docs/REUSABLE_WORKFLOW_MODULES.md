# Reusable Workflow Modules

This repository now has two reusable workflow entry points that wrap the older
prototype scripts without deleting or rewriting them in place.

## 1. NDL download

Recommended imports:

```python
from modules.ndl_download_workflow import NDLDownloadModule, NDLDownloadRequest
```

Example:

```python
downloader = NDLDownloadModule()

result = downloader.download(
    NDLDownloadRequest(
        keyword="井上哲次郎 倫理新説",
        output_dir="output/ndl_downloads",
        use_api=True,
        headless=True,
    )
)
```

Behavior:

- `use_api=True` uses the legacy `ndl-search/core/dl_searcher.py` adapter.
- `restricted=True` uses the authenticated browser workflow in
  `ndl-search/browser_client.py`.
- `result_index` is supported through the browser workflow so a caller can pick
  a specific search result instead of always accepting the first match.

## 2. PDF to NER full pipeline

Recommended imports:

```python
from modules.pdf_to_ner_workflow import PDFToNERConfig, PDFToNERPipeline
```

Example:

```python
pipeline = PDFToNERPipeline(
    PDFToNERConfig(
        pdf_path="data/input/book.pdf",
        output_dir="output/pdf_to_ner_run",
        start_page=1,
        end_page=5,
        run_ocr=True,
        run_ner=False,
    )
)

result = pipeline.run()
```

Behavior:

- The pipeline reuses the stable parts of `scripts/manshu_xml_entry_pipeline.py`.
- Stages are normalized into:
  - `images`
  - `split_halves`
  - `ocr_halves`
  - `pages`
  - `ner`
  - `merged`
  - `logs`
- `run_ner=False` stops after structured entry reconstruction.
- Multi-page NER requires `confirm_ner_cost=True`.

## Notes

- These modules are wrappers around legacy code, so they preserve the existing
  OCR and NDL logic while exposing cleaner import paths.
- The old scripts remain available for experiments and one-off runs.
- The new unit tests live in `tests/test_reusable_workflows.py`.

## API integration

The Flask app now exposes:

- `POST /api/ndl/search`
- `POST /api/ndl/download`
- `POST /api/pdf/ner/pipeline`
- `POST /api/pdf/ocr/pipeline` with `pipeline_type=pdf_to_ner`

## CLI integration

Recommended CLI entry points:

- `python scripts/run_ndl_download_workflow.py "井上哲次郎 倫理新説" --use-api`
- `python scripts/run_pdf_to_ner_workflow.py data/input/book.pdf --start-page 1 --end-page 3 --skip-ner`
