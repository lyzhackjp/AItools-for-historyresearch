"""Read-only validation for the historyresearch-workspace skill.

This script intentionally skips secrets/ and does not modify files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REQUIRED_ROOT_FILES = [
    "README.md",
    "GUIDELINES.md",
    "WORKFLOW_DESIGN.md",
    "docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md",
    "modules",
    "tools/workflow",
    "log/feature_development",
]

REQUIRED_SKILL_FILES = [
    "docs/agent_skills/historyresearch-workspace/SKILL.md",
    "docs/agent_skills/historyresearch-workspace/agents/openai.yaml",
    "docs/agent_skills/historyresearch-workspace/references/privacy_rules.md",
    "docs/agent_skills/historyresearch-workspace/references/package_protocol.md",
    "docs/agent_skills/historyresearch-workspace/references/workflow_rules.md",
    "docs/agent_skills/historyresearch-workspace/references/module_map.md",
    "docs/agent_skills/historyresearch-workspace/references/local_model_ollama.md",
    "docs/agent_skills/historyresearch-workspace/references/task_artifact_snapshots.md",
    "docs/agent_skills/historyresearch-workspace/references/agent_playbooks.md",
    "docs/agent_skills/historyresearch-workspace/references/acceptance_checklists.md",
    "docs/agent_skills/historyresearch-workspace/scripts/inspect_workspace_contracts.py",
]


def exists(root: Path, relative: str) -> bool:
    return (root / relative).exists()


def validate(root: Path) -> dict:
    missing_root = [item for item in REQUIRED_ROOT_FILES if not exists(root, item)]
    missing_skill = [item for item in REQUIRED_SKILL_FILES if not exists(root, item)]
    report_dir = root / "log" / "feature_development"
    report_count = len(list(report_dir.glob("2026-04-25_*.md"))) if report_dir.exists() else 0

    return {
        "ok": not missing_root and not missing_skill,
        "root": str(root),
        "missing_root": missing_root,
        "missing_skill": missing_skill,
        "report_count_2026_04_25": report_count,
        "secrets_policy": "skipped_by_design",
    }


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd().resolve()
    result = validate(root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
