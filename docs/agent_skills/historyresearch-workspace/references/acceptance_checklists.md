# Acceptance Checklists

## Before Editing

- Workspace root has `README.md`, `GUIDELINES.md`, `modules/`, `tools/workflow/`, and the optimization anchor.
- Target module is listed or newly added in the optimization anchor.
- No need to read `secrets/`.
- Existing tests for the module or adjacent workflow are identified.

## Package Interface

- Package has `type`, `schema_version`, `created_at`, `backend`, `provider`, `model`, `confidence`, `needs_review`, and `quality_flags`.
- Capability snapshot lists supported backends and fallback order.
- Task-layer callers can discover the task through `TaskManager.get_task_registry()` or `/api/tasks/capabilities`.
- Task-layer execution returns a `task_execution` package when called through `execute_task_package()` or `/api/tasks/execute`.
- Legacy public methods still work.
- Degraded backend behavior returns structured results or falls back.

## Artifact Manager

- Generated JSON/checkpoint artifacts stay inside the managed root.
- `ArtifactManager.write_json_artifact()` is used for orchestrated checkpoint writes.
- Workflow stages register user-facing outputs with `ResearchProject.register_artifact()`.
- No artifact path points under `secrets/`.

## Small Model

- Prompt is short and single-purpose.
- Smoke uses `Say OK only.` before complex tasks.
- Empty content, truncation, and malformed JSON are not counted as reliable success.
- Attempted backend chain is recorded.

## Documentation

- Optimization report exists.
- `LATEST_WORK_LOG.md` is updated.
- Anchor file is updated when new direction or completed protocol matters.
- Root/workflow docs are updated only for public contract changes.

## Privacy

- No `secrets/` files were opened.
- No real keys, cookies, private source text, or full prompts in logs.
- No temporary scripts remain outside `tests/`, `scripts/`, or approved skill scripts.
