# Agent Playbooks

Use these short playbooks when a small or local model is driving workspace work.

## Module Optimization

1. Read `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md` only around the target module.
2. Run `python docs/agent_skills/historyresearch-workspace/scripts/inspect_workspace_contracts.py .` when choosing task/API/artifact entry points.
3. Inspect the module, its tests, and the nearest workflow stage.
4. Add or improve `get_capabilities()` and package/envelope methods.
5. Preserve legacy APIs unless the user explicitly approves migration.
6. Add one happy-path test and one degraded/fallback test.
7. Write a report in `log/feature_development/`.
8. Update `README.md`, `GUIDELINES.md`, `WORKFLOW_DESIGN.md`, or `docs/workflow/` only if public behavior changed.

## Task And Artifact Snapshot

1. Prefer `TaskManager.get_task_registry(detailed=False)` for task names, aliases, presets, and backend options.
2. Prefer `/api/tasks/execute` or `TaskManager.execute_task_package()` for agent calls.
3. Treat `task_execution.needs_review` and `quality_flags` as first-class routing signals.
4. Use ArtifactManager only under a managed output root; never write under `secrets/`.
5. Register final outputs back to `ResearchProject.register_artifact()` when working inside workflow stages.

## Local Model Smoke

1. Check `ollama list`.
2. Use provider `ollama`, backend `local_llm`, base URL `http://localhost:11434`.
3. First prompt: `Say OK only.`
4. Use `temperature=0.1`, `max_tokens<=64`.
5. If output is empty, malformed, or length-limited, mark `needs_review=True` and fallback.

## Report Closeout

1. State the target problem.
2. List changed modules and package fields.
3. List tests run and result counts.
4. Confirm no `secrets/` access and no persistent temp files.
5. Add the report path to `log/feature_development/LATEST_WORK_LOG.md`.

## Skill Update

1. Keep `SKILL.md` concise.
2. Put details in `references/`.
3. Put deterministic checks in `scripts/`.
4. Do not add README, changelog, or duplicate documentation inside the skill.
5. Run `python docs/agent_skills/historyresearch-workspace/scripts/validate_workspace_skill.py .` after structural changes.
6. Run `python docs/agent_skills/historyresearch-workspace/scripts/inspect_workspace_contracts.py .` after contract-related skill changes.
