#!/usr/bin/env bash
set -euo pipefail

FORCE=0

usage() {
  printf 'Usage: %s [--force]\n' "$(basename "$0")"
}

while (($#)); do
  case "$1" in
    --force)
      FORCE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RUNTIME_DIR="${HISTORY_RESEARCH_RUNTIME_DIR:-$ROOT/.runtime}"
VENV_DIR="$RUNTIME_DIR/venv"
VENV_PYTHON="$VENV_DIR/bin/python"
STAMP_FILE="$RUNTIME_DIR/install.ok"
REQUIREMENTS="$ROOT/requirements.txt"
MACOS_CONSTRAINTS="$ROOT/requirements-macos.txt"
FRONTEND_INDEX="$ROOT/frontend/dist/index.html"

mkdir -p "$RUNTIME_DIR"
mkdir -p "$RUNTIME_DIR/pip-cache" "$RUNTIME_DIR/pycache" "$RUNTIME_DIR/cache"

export PIP_CACHE_DIR="$RUNTIME_DIR/pip-cache"
export PYTHONPYCACHEPREFIX="$RUNTIME_DIR/pycache"
export XDG_CACHE_HOME="$RUNTIME_DIR/cache"
export HF_HOME="$RUNTIME_DIR/cache/huggingface"

if [[ -f "$STAMP_FILE" && "$FORCE" -eq 0 ]]; then
  printf 'Runtime is already initialized.\n'
  exit 0
fi

if [[ ! -f "$REQUIREMENTS" ]]; then
  printf 'requirements.txt was not found: %s\n' "$REQUIREMENTS" >&2
  exit 1
fi

if [[ ! -f "$FRONTEND_INDEX" ]]; then
  printf 'Warning: frontend/dist/index.html was not found. Build the frontend with npm before using packaged UI serving.\n' >&2
fi

test_python_candidate() {
  local candidate="$1"
  "$candidate" -c 'import sys; raise SystemExit(0 if (3, 8) <= sys.version_info[:2] <= (3, 11) else 1)' >/dev/null 2>&1
}

get_python_candidate() {
  if [[ -n "${HISTORY_RESEARCH_PYTHON:-}" ]]; then
    if test_python_candidate "$HISTORY_RESEARCH_PYTHON"; then
      printf '%s\n' "$HISTORY_RESEARCH_PYTHON"
      return 0
    fi
    printf 'HISTORY_RESEARCH_PYTHON is not Python 3.8-3.11: %s\n' "$HISTORY_RESEARCH_PYTHON" >&2
    return 1
  fi

  local candidate
  for candidate in python3.11 python3.10 python3.9 python3.8 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && test_python_candidate "$candidate"; then
      command -v "$candidate"
      return 0
    fi
  done

  printf 'Python 3.8-3.11 was not found. Install Python 3.11 or set HISTORY_RESEARCH_PYTHON.\n' >&2
  return 1
}

PYTHON_BIN="$(get_python_candidate)"

if [[ ! -x "$VENV_PYTHON" ]]; then
  printf 'Creating Python virtual environment: %s\n' "$VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

printf 'Installing/updating Python dependencies. First run may take a while.\n'
"$VENV_PYTHON" -m pip install --upgrade pip
if [[ "$(uname -s)" == "Darwin" && -f "$MACOS_CONSTRAINTS" ]]; then
  "$VENV_PYTHON" -m pip install -r "$REQUIREMENTS" -c "$MACOS_CONSTRAINTS"
else
  "$VENV_PYTHON" -m pip install -r "$REQUIREMENTS"
fi

{
  printf '{\n'
  printf '  "initialized_at": "%s",\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf '  "python": "%s",\n' "$VENV_PYTHON"
  printf '  "macos_constraints": "%s"\n' "$MACOS_CONSTRAINTS"
  printf '}\n'
} > "$STAMP_FILE"

printf 'Initialization complete.\n'
