# Package Protocol

Every optimized module should keep legacy APIs where practical and add package/envelope APIs for workflow use.

Recommended common fields:

- `type`: stable package kind, such as `ocr_result`, `ocr_batch`, `ner_extraction`, `citation_records`, `academic_analysis`, or `processed_ocr_result`.
- `schema_version`: date-like protocol version.
- `created_at`: local timestamp.
- `source_path` or `source_id`: non-sensitive source reference.
- `backend`: one of `script`, `local_engine`, `llm_api`, `local_llm`, `skill`, `mcp`, or `hybrid`.
- `provider`: implementation provider, such as `tesseract`, `ndlocr_lite`, `qwen`, `rule_based`, or `workspace_skill`.
- `model`: model or rule set name.
- `confidence`: numeric confidence in `[0, 1]` when possible.
- `needs_review`: boolean derived from quality flags, missing data, fallback execution, or low confidence.
- `quality_flags`: short machine-readable flags.
- `needs_review`: should be true when small/local models return empty content, malformed structure, length-limited output, fallback output, or low confidence.
- `capabilities`: capability snapshot or backend discovery result when useful.
- `artifacts`: generated files with `kind`, `path`, and source mapping.
- `error`: structured failure summary, not a raw traceback unless needed for local debugging.

Workflow stages should store compact summaries in `stage_metadata`, `quality_flags`, `review_queue`, and artifact indexes rather than copying full private content into logs.
