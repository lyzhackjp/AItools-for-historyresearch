# Stage3 task layer snapshot package execution optimization

Date: 2026-04-25

## Goal

Move Stage 3 NER execution closer to the unified task layer so API, skill, MCP, and small-model agents can inspect the same capability contract.

## Changes

- Added `task_layer_snapshot` metadata with NER options, task registry summary, and redacted TaskManager capabilities.
- Stage 3 now prefers `TaskManager.execute_task_package()` when available.
- Stage 3 execution summaries now include a compact `task_package` summary for each NER extraction record.
- Legacy `execute_task()` fallback remains compatible.

## Validation

- `python -m py_compile tools\workflow\stages\stage3_extract.py tests\test_stage3_workflow_integration.py`
- `python -m unittest tests.test_stage3_workflow_integration`
- Result: 2 tests passed.

## Privacy

- No secret files were read.
- Task layer snapshots include only backend/provider/model/status metadata and declared privacy flags.
- No temporary script or intermediate file was left behind.

## Next Task

Continue with redacted configuration and key-status facade convergence.
