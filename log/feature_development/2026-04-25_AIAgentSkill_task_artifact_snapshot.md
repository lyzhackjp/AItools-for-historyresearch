# AI Agent Skill Task And Artifact Snapshot Report

Date: 2026-04-25

## Scope

Upgraded the workspace AI-agent skill so small/local models can discover task and artifact contracts before choosing module, API, or workflow entry points.

## Changes

- `docs/agent_skills/historyresearch-workspace/SKILL.md`
  - Points agents to TaskManager/ArtifactManager snapshots.
  - Adds contract inspection to the completion checklist.

- `docs/agent_skills/historyresearch-workspace/references/task_artifact_snapshots.md`
  - Documents `task_execution` fields, ArtifactManager rules, and workflow project handoff.

- `docs/agent_skills/historyresearch-workspace/scripts/inspect_workspace_contracts.py`
  - Prints a read-only JSON summary of TaskManager tasks and ArtifactManager capability methods.
  - Does not read `secrets/` and does not write files.

- `docs/agent_skills/historyresearch-workspace/scripts/validate_workspace_skill.py`
  - Now requires the new snapshot reference and inspection script.

## Validation

- `python docs\agent_skills\historyresearch-workspace\scripts\validate_workspace_skill.py .`
- `python docs\agent_skills\historyresearch-workspace\scripts\inspect_workspace_contracts.py .`
- `python -m py_compile docs\agent_skills\historyresearch-workspace\scripts\validate_workspace_skill.py docs\agent_skills\historyresearch-workspace\scripts\inspect_workspace_contracts.py`

Result: OK. The contract snapshot reported 10 TaskManager tasks and ArtifactManager managed-root capabilities.

## Cleanup

- Removed generated `docs/agent_skills/historyresearch-workspace/scripts/__pycache__/`.
- No temporary scripts or files remain from this step.

## Privacy

- No secret files were read.
- The inspection script reports capability metadata only, not key values or private source text.
