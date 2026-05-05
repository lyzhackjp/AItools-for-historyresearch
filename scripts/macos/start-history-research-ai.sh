#!/usr/bin/env bash
set -euo pipefail

PORT=5050
SKIP_INIT=0
OPEN_BROWSER=1

usage() {
  printf 'Usage: %s [--port PORT] [--skip-init] [--no-open]\n' "$(basename "$0")"
}

while (($#)); do
  case "$1" in
    --port)
      if [[ $# -lt 2 ]]; then
        printf '%s\n' '--port requires a value.' >&2
        exit 2
      fi
      PORT="$2"
      shift 2
      ;;
    --skip-init)
      SKIP_INIT=1
      shift
      ;;
    --no-open)
      OPEN_BROWSER=0
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
SUPPORT_DIR="${HISTORY_RESEARCH_SUPPORT_DIR:-$HOME/Library/Application Support/HistoryResearchAI}"
PID_FILE="$RUNTIME_DIR/backend.pid"
LOG_FILE="$RUNTIME_DIR/backend.log"
VENV_PYTHON="${HISTORY_RESEARCH_VENV_PYTHON:-$ROOT/.runtime/venv/bin/python}"
FRONTEND_INDEX="$ROOT/frontend/dist/index.html"
APP_MODULE="app.app"
URL="http://127.0.0.1:$PORT/"
STATUS_URL="http://127.0.0.1:$PORT/api/system/status"

mkdir -p "$RUNTIME_DIR"
mkdir -p "$RUNTIME_DIR/pycache" "$RUNTIME_DIR/cache"
mkdir -p "$SUPPORT_DIR"

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

export PYTHONPYCACHEPREFIX="$RUNTIME_DIR/pycache"
export XDG_CACHE_HOME="$RUNTIME_DIR/cache"
export HF_HOME="$RUNTIME_DIR/cache/huggingface"

if [[ "$SKIP_INIT" -eq 0 && ! -x "$VENV_PYTHON" ]]; then
  "$SCRIPT_DIR/initialize-history-research-ai.sh"
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
  printf 'Python runtime does not exist. Run scripts/macos/initialize-history-research-ai.sh first.\n' >&2
  exit 1
fi

if [[ ! -f "$FRONTEND_INDEX" ]]; then
  printf 'Warning: frontend/dist/index.html was not found. API will start, but the packaged UI needs npm install && npm run build in frontend/.\n' >&2
fi

if [[ -f "$PID_FILE" ]]; then
  EXISTING_PID="$(head -n 1 "$PID_FILE" || true)"
  if [[ "$EXISTING_PID" =~ ^[0-9]+$ ]] && kill -0 "$EXISTING_PID" >/dev/null 2>&1; then
    printf 'Backend is already running. UI: %s\n' "$URL"
    if [[ "$OPEN_BROWSER" -eq 1 ]]; then
      open "$URL"
    fi
    exit 0
  fi
  rm -f "$PID_FILE"
fi

SELECTED_LLM_PROVIDER="$(printf '%s' "${LOCAL_LLM_PROVIDER:-${LLM_PROVIDER:-}}" | tr '[:upper:]' '[:lower:]')"
if [[ "$SELECTED_LLM_PROVIDER" == "mlx" ]]; then
  case "${MLX_AUTO_START:-0}" in
    1|true|TRUE|yes|YES|on|ON)
      if [[ -n "${MLX_MODEL:-}" ]]; then
        MLX_ARGS=(--model "$MLX_MODEL" --host "${MLX_HOST:-127.0.0.1}" --port "${MLX_PORT:-8080}" --no-smoke)
        if [[ -n "${MLX_PYTHON:-}" ]]; then
          MLX_ARGS+=(--python "$MLX_PYTHON")
        fi
        bash "$SCRIPT_DIR/start-mlx-server.sh" "${MLX_ARGS[@]}"
      else
        printf 'MLX_AUTO_START is enabled, but MLX_MODEL is not set. Skipping MLX server auto-start.\n' >&2
      fi
      ;;
  esac
fi

printf 'Starting backend service: %s\n' "$URL"
(
  cd "$ROOT"
  export HISTORY_RESEARCH_SERVE_FRONTEND=1
  export FLASK_DEBUG=0
  export HOST=127.0.0.1
  export PORT
  nohup "$VENV_PYTHON" -m "$APP_MODULE" > "$LOG_FILE" 2>&1 &
  printf '%s\n' "$!" > "$PID_FILE"
)

BACKEND_PID="$(head -n 1 "$PID_FILE")"

READY=0
for _ in $(seq 1 40); do
  sleep 0.5
  if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    printf 'Backend service failed to start. See log: %s\n' "$LOG_FILE" >&2
    rm -f "$PID_FILE"
    exit 1
  fi
  if curl -fsS "$STATUS_URL" >/dev/null 2>&1; then
    READY=1
    break
  fi
done

if [[ "$READY" -eq 0 ]]; then
  printf 'Warning: backend is still starting. Refresh the browser after a moment if needed.\n' >&2
fi

if [[ "$OPEN_BROWSER" -eq 1 ]]; then
  open "$URL"
fi

printf 'History Research AI started. To stop it, run scripts/macos/stop-history-research-ai.sh.\n'
