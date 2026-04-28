# API lazy service app factory optimization

Date: 2026-04-25

## Goal

Make API health and capability checks observable without initializing heavyweight OCR, LLM, PDF, download, or verifier services.

## Changes

- Added `LazyService.name`, `description`, `initialized`, and `status()`.
- Added centralized `LAZY_SERVICES` and `get_service_status()`.
- Added `create_app(test_config=None)`.
- Added `/api/system/status` for lightweight redacted service status.
- Added an API factory test that skips cleanly when Flask is unavailable.

## Validation

- `python -m py_compile app\app.py tests\test_api_app_factory.py`
- `python -m unittest tests.test_api_app_factory`
- Result: 1 test skipped because Flask is not installed in the current environment.

## Privacy

- No secret files were read.
- The status endpoint reports initialization state only and does not expose secret values.
- No temporary script or intermediate file was left behind.

## Next Task

Continue with integration, environment, and artifact manager convergence.
