"""Check whether local research materials could be uploaded to GitHub.

The script intentionally focuses on repository hygiene. It does not delete or
modify files; it only reports tracked high-risk paths and untracked files that
are not covered by .gitignore.
"""

from __future__ import annotations

import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

HIGH_RISK_ROOTS = (
    "secrets/",
    "output/",
    "ocr_output/",
    "workflow_output/",
    "training_workflow_output/",
    "cache/",
    "tmp/",
    "temp/",
    "downloads/",
    "test_downloads/",
    "organized_books/",
    "local_research_data/",
    "research_data/",
    "private_data/",
    "input_documents/",
    "reference_documents/",
    "materials/",
    "sources/",
    "corpus/",
    "ndl-search/",
    "ndlocr-lite/",
)

HIGH_RISK_GLOBS = (
    "*.pdf",
    "*.docx",
    "*.doc",
    "*.xlsx",
    "*.xls",
    "*.pptx",
    "*.ppt",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.tif",
    "*.tiff",
    "*.csv",
    "*.jsonl",
    "*.bak",
    "*.pem",
    "*.key",
    ".env",
    ".env.*",
    "*cid_state*.png",
    "*checkpoint*.json",
    "*_checkpoint.json",
    "page_mapping_cache.json",
    "verification_results.json",
    "verification_report.md",
    "partial_resume_report.md",
    "resume_checkpoint.json",
    "tmp_ndl_response.xml",
    "cookies*.json",
    "session*.json",
    "storage_state*.json",
)

TRACKED_CONFIG_REVIEW = (
    "config/api_config.json",
    "config/current_environment.json",
    "config/external_config.json",
)

SENSITIVE_KEY_RE = re.compile(
    r"(api[_-]?key|token|secret|password|passwd|pwd|credential|cookie|session|account|login|username)",
    re.IGNORECASE,
)
SAFE_ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|ID|FILE|USER|USERNAME)?$")
WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")
SECRET_VALUE_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{12,}|AKIA[0-9A-Z]{12,}|xox[baprs]-[A-Za-z0-9-]{10,}|eyJ[A-Za-z0-9_-]{20,}\.)"
)
NDL_CREDENTIAL_ASSIGNMENT_RE = re.compile(
    r"(NDL_(?:USERNAME|CARD_ID|PASSWORD|LOGIN|ACCOUNT)|ndl[_\-. ]{0,20}(?:username|user|account|login|password|passwd|credential|card_id))"
    r"\s*[:=]\s*[\"']?([^\"'\s#<>]+)",
    re.IGNORECASE,
)
PLACEHOLDER_VALUE_RE = re.compile(
    r"^(?:your_|example|placeholder|change_me|changeme|xxx+|\$\{|env:|none|null|false|true|NDL_|[A-Z][A-Z0-9_]*_PLACEHOLDER)",
    re.IGNORECASE,
)
TEXT_SCAN_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".csv",
    ".ps1",
    ".bat",
    ".sh",
    ".env",
    "",
}


def git_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=ROOT,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
    )
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def is_high_risk(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if any(normalized.startswith(root) for root in HIGH_RISK_ROOTS):
        return True
    name = normalized.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(normalized, pattern) for pattern in HIGH_RISK_GLOBS)


def _is_env_reference(key_path: str, value: str) -> bool:
    key = key_path.rsplit(".", 1)[-1].lower()
    if key.endswith("_env") or key in {"env_var", "api_key_env", "group_id_env", "endpoint_id_env"}:
        return bool(SAFE_ENV_KEY_RE.match(value))
    if value.startswith("${") and value.endswith("}"):
        return True
    return False


def _is_absolute_or_private_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return (
        bool(WINDOWS_ABSOLUTE_PATH_RE.match(value))
        or normalized.startswith("/home/")
        or normalized.startswith("/Users/")
        or "/Users/" in normalized
        or normalized.startswith("~/")
    )


def review_tracked_config(path: str) -> list[str]:
    config_path = ROOT / path
    reasons: list[str] = []
    try:
        data = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        return [f"cannot_parse_json:{type(exc).__name__}"]

    def walk(value, key_path: str = "") -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                walk(nested, f"{key_path}.{key}" if key_path else str(key))
            return
        if isinstance(value, list):
            for index, nested in enumerate(value):
                walk(nested, f"{key_path}[{index}]")
            return
        if not isinstance(value, str):
            return

        stripped = value.strip()
        if not stripped:
            return
        if _is_absolute_or_private_path(stripped):
            reasons.append(f"private_or_absolute_path:{key_path}")
        if SECRET_VALUE_RE.search(stripped):
            reasons.append(f"secret_like_value:{key_path}")
        if SENSITIVE_KEY_RE.search(key_path) and not _is_env_reference(key_path, stripped):
            safe_literals = {
                "environment_variable",
                "environment variables",
                "secrets/",
                "local_rules",
                "script",
                "public",
                "private",
            }
            if stripped not in safe_literals and not stripped.startswith("Optional "):
                reasons.append(f"sensitive_key_value_not_env_reference:{key_path}")

    walk(data)
    return sorted(set(reasons))


def scan_content_secrets(path: str) -> list[str]:
    normalized = path.replace("\\", "/")
    if any(normalized.startswith(root) for root in HIGH_RISK_ROOTS):
        return []
    config_path = ROOT / path
    if config_path.suffix.lower() not in TEXT_SCAN_EXTENSIONS:
        return []
    try:
        text = config_path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return [f"cannot_scan_text:{type(exc).__name__}"]

    reasons: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if SECRET_VALUE_RE.search(line):
            reasons.append(f"{path}:{line_number}:secret_like_value")
        for match in NDL_CREDENTIAL_ASSIGNMENT_RE.finditer(line):
            value = match.group(2).strip()
            if value and not PLACEHOLDER_VALUE_RE.match(value):
                reasons.append(f"{path}:{line_number}:ndl_credential_assignment")
    return reasons


def print_section(title: str, paths: list[str]) -> None:
    print(f"\n{title}: {len(paths)}")
    for path in paths[:200]:
        print(f"  {path}")
    if len(paths) > 200:
        print(f"  ... {len(paths) - 200} more")


def main() -> int:
    tracked = git_lines("ls-files")
    untracked_not_ignored = git_lines("ls-files", "--others", "--exclude-standard")

    tracked_high_risk = [path for path in tracked if path not in TRACKED_CONFIG_REVIEW and is_high_risk(path)]
    tracked_config_review_required = []
    for path in tracked:
        if path in TRACKED_CONFIG_REVIEW:
            reasons = review_tracked_config(path)
            if reasons:
                tracked_config_review_required.append(f"{path} ({'; '.join(reasons[:5])})")
    content_secret_review_required = []
    for path in [*tracked, *untracked_not_ignored]:
        content_secret_review_required.extend(scan_content_secrets(path))
    untracked_high_risk = [path for path in untracked_not_ignored if is_high_risk(path)]

    print("GitHub upload safety check")
    print(f"Repository: {ROOT}")
    print_section("TRACKED HIGH RISK", tracked_high_risk)
    print_section("TRACKED CONFIG REVIEW REQUIRED", tracked_config_review_required)
    print_section("CONTENT SECRET REVIEW REQUIRED", content_secret_review_required)
    print_section("UNTRACKED NOT IGNORED HIGH RISK", untracked_high_risk)

    if tracked_high_risk or tracked_config_review_required or content_secret_review_required or untracked_high_risk:
        print("\nResult: REVIEW REQUIRED")
        return 1

    print("\nResult: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
