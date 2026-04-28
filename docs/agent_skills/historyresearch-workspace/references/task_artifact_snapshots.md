# Task And Artifact Snapshots

Use this reference when an agent needs to call workspace functions without guessing internal module methods.

## TaskManager

- Discover tasks with `TaskManager.get_task_registry(detailed=False)`.
- Discover backend/provider options with `TaskManager.get_capabilities()` or `/api/tasks/capabilities`.
- Execute through `TaskManager.execute_task_package()` or `/api/tasks/execute`.
- Treat `task_execution` as the stable response shape.

Required `task_execution` fields:

- `type`
- `schema_version`
- `task_type`
- `requested_task_type`
- `preset`
- `success`
- `mode`
- `backend`
- `provider`
- `model`
- `confidence`
- `needs_review`
- `quality_flags`
- `data`
- `result`
- `task_options`
- `artifacts`

## ArtifactManager

- Use `ArtifactManager.write_json_artifact()` for orchestrated JSON/checkpoint writes.
- Keep all writes inside the managed root.
- Do not write under `secrets/` or outside the selected root.
- Use `ArtifactManager.package_manifest()` to summarize managed artifacts.

## Workflow Project Handoff

- Workflow modules should register packages with `ResearchProject.register_package()`.
- User-facing outputs should register with `ResearchProject.register_artifact()`.
- Stage metadata should keep compact `package_protocol` and `artifact_protocol` summaries when these registries are used.

## Small-Model Rule

Small/local models should read the snapshot first, choose a task/preset/backend, and call the stable envelope. They should not infer private adapter names from implementation files unless the registry lacks the needed route.
