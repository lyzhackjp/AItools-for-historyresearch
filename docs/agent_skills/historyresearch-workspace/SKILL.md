---
name: historyresearch-workspace
description: Use when working inside the AItools-for-historyresearch workspace to optimize modules, align OCR/NER/citation/writing interfaces, preserve privacy rules, update workflow documentation, and produce feature-development reports.
---

# History Research Workspace

## Core Workflow

1. Confirm the workspace root by checking for `README.md`, `GUIDELINES.md`, `modules/`, `tools/workflow/`, and `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`.
2. Read `GUIDELINES.md`, `README.md`, `WORKFLOW_DESIGN.md`, and the module optimization anchor before substantial changes.
3. If a new optimization direction is discovered, write it to `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md` before implementation.
4. Prefer adding stable package/envelope interfaces while preserving legacy public methods.
5. After each optimization step, add a formal report under `log/feature_development/` and update `log/feature_development/LATEST_WORK_LOG.md`.
6. Update root/workflow docs when a change affects module contracts, backend options, artifact handling, or privacy rules.
7. Run focused tests first, then the relevant integration chain. Report any skipped tests honestly.

## Reference Selection

- For secrecy and cleanup rules, read `references/privacy_rules.md`.
- For package/envelope fields and backend metadata, read `references/package_protocol.md`.
- For local small-model/Ollama testing and fallback rules, read `references/local_model_ollama.md`.
- For TaskManager and ArtifactManager discovery snapshots, read `references/task_artifact_snapshots.md`.
- For short task procedures, read `references/agent_playbooks.md`.
- For pre/post acceptance gates, read `references/acceptance_checklists.md`.
- For report, workflow, and documentation updates, read `references/workflow_rules.md`.
- For module families and likely entry points, read `references/module_map.md`.

## Implementation Rules

- Never read or expose files under `secrets/`.
- Do not place temporary scripts in the root. Use `tests/` or `scripts/` only when a persistent artifact is justified.
- Prefer local, offline, deterministic tests unless the user explicitly requests a real API/model run.
- When adding AI/model integration points, expose them as options such as `script`, `llm_api`, `local_llm`, `skill`, `mcp`, or `hybrid`, then normalize results into the same package schema.
- Keep small-model prompts short and direct. Prefer smoke tests such as `Say OK only.` before JSON-heavy tasks.
- Keep stage logic thin: workflow stages should consume module packages and write summaries, artifacts, quality flags, and review queues.
- Prefer `TaskManager.get_task_registry()`, `TaskManager.execute_task_package()`, and ArtifactManager capability snapshots before guessing module internals.
- Do not remove or overwrite unrelated user changes.

## Completion Checklist

- Code compiles.
- Tests cover the new package path and at least one degraded/unavailable backend path.
- Optimization report exists.
- Anchor/design docs reflect new directions or completed work.
- README/workflow/guideline docs are updated if public contracts changed.
- No raw sensitive data, key material, or throwaway scratch files remain.
- For skill structural changes, run `python docs/agent_skills/historyresearch-workspace/scripts/validate_workspace_skill.py .`.
- For agent/API alignment checks, run `python docs/agent_skills/historyresearch-workspace/scripts/inspect_workspace_contracts.py .`.
