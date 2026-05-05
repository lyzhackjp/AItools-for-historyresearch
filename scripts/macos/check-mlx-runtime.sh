#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SUPPORT_DIR="${HISTORY_RESEARCH_SUPPORT_DIR:-$HOME/Library/Application Support/HistoryResearchAI}"

load_env_file() {
  local env_file="$1"
  if [[ -f "$env_file" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a
  fi
}

load_env_file "$ROOT/.env.local_llm"
load_env_file "$SUPPORT_DIR/local-llm.env"

PYTHON_BIN="${MLX_PYTHON:-}"
MODEL="${MLX_MODEL:-}"

if [[ -z "$PYTHON_BIN" ]]; then
  for candidate in python3 /opt/anaconda3/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      resolved="$(command -v "$candidate")"
      if "$resolved" -c 'import importlib.util; raise SystemExit(0 if importlib.util.find_spec("mlx_lm") else 1)' >/dev/null 2>&1; then
        PYTHON_BIN="$resolved"
        break
      fi
    elif [[ -x "$candidate" ]] && "$candidate" -c 'import importlib.util; raise SystemExit(0 if importlib.util.find_spec("mlx_lm") else 1)' >/dev/null 2>&1; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
fi

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  printf 'FAIL MLX_PYTHON is not executable: %s\n' "${PYTHON_BIN:-<unset>}" >&2
  exit 1
fi

if ! "$PYTHON_BIN" -c 'import importlib.util; raise SystemExit(0 if importlib.util.find_spec("mlx_lm") else 1)' >/dev/null 2>&1; then
  printf 'FAIL mlx_lm is not importable from: %s\n' "$PYTHON_BIN" >&2
  exit 1
fi

if [[ -z "$MODEL" ]]; then
  printf 'FAIL MLX_MODEL is not set.\n' >&2
  exit 1
fi

if [[ "$MODEL" == /* || "$MODEL" == ./* || "$MODEL" == ../* ]]; then
  if [[ ! -d "$MODEL" ]]; then
    printf 'FAIL MLX_MODEL path does not exist: %s\n' "$MODEL" >&2
    exit 1
  fi
  printf 'OK MLX_MODEL path: %s\n' "$MODEL"
else
  printf 'OK MLX_MODEL id: %s\n' "$MODEL"
fi

printf 'OK MLX_PYTHON: %s\n' "$PYTHON_BIN"
printf 'OK mlx_lm module is discoverable.\n'
