# Workflow Rules

Before implementation:

- Use `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md` as the optimization anchor.
- Add newly discovered optimization directions to that anchor first.
- Check existing tests and package interfaces before adding new abstractions.

During implementation:

- Preserve old APIs unless there is a deliberate migration.
- Add capability discovery for multi-backend modules.
- Prefer structured degraded results over import-time or initialization-time crashes.
- Do not hard-code backend selection inside workflow stages when a module/task facade can own it.

After implementation:

- Add a report under `log/feature_development/YYYY-MM-DD_<topic>.md`.
- Update `log/feature_development/LATEST_WORK_LOG.md`.
- Update `README.md`, `GUIDELINES.md`, `WORKFLOW_DESIGN.md`, or `docs/workflow/` when public behavior changes.
- Run targeted tests and relevant chain tests.
- Remove or archive any temporary scripts after reporting.
