#!/usr/bin/env bash
set -euo pipefail

MODEL="${MLX_MODEL:-}"
HOST="${MLX_HOST:-127.0.0.1}"
PORT="${MLX_PORT:-8080}"
PYTHON_BIN="${MLX_PYTHON:-}"
SMOKE=1

usage() {
  printf 'Usage: %s --model MODEL [--host HOST] [--port PORT] [--python PYTHON] [--no-smoke]\n' "$(basename "$0")"
}

while (($#)); do
  case "$1" in
    --model)
      MODEL="$2"
      shift 2
      ;;
    --host)
      HOST="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --no-smoke)
      SMOKE=0
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
LOG_FILE="$RUNTIME_DIR/mlx-server.log"
PID_FILE="$RUNTIME_DIR/mlx-server.pid"
BASE_URL="http://$HOST:$PORT/v1"

mkdir -p "$RUNTIME_DIR"

if [[ -z "$MODEL" ]]; then
  printf 'MLX model is required. Pass --model or set MLX_MODEL.\n' >&2
  exit 2
fi

if curl -fsS "$BASE_URL/models" >/dev/null 2>&1; then
  printf 'MLX server is already available: %s\n' "$BASE_URL"
  exit 0
fi

python_has_mlx() {
  local candidate="$1"
  "$candidate" -c 'import importlib.util; raise SystemExit(0 if importlib.util.find_spec("mlx_lm") else 1)' >/dev/null 2>&1
}

if [[ -z "$PYTHON_BIN" ]]; then
  for candidate in python3 /opt/anaconda3/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    if command -v "$candidate" >/dev/null 2>&1 && python_has_mlx "$candidate"; then
      PYTHON_BIN="$(command -v "$candidate")"
      break
    elif [[ -x "$candidate" ]] && python_has_mlx "$candidate"; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
fi

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  printf 'Could not find a Python with mlx_lm installed. Set MLX_PYTHON or install mlx-lm in a local Python environment.\n' >&2
  exit 127
fi

printf 'Starting MLX server: %s\n' "$BASE_URL"
nohup "$PYTHON_BIN" -m mlx_lm.server --host "$HOST" --port "$PORT" --model "$MODEL" > "$LOG_FILE" 2>&1 &
printf '%s\n' "$!" > "$PID_FILE"

for _ in $(seq 1 120); do
  sleep 1
  if curl -fsS "$BASE_URL/models" >/dev/null 2>&1; then
    if [[ "$SMOKE" -eq 1 ]]; then
      curl -fsS "$BASE_URL/chat/completions" \
        -H 'Content-Type: application/json' \
        -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Say OK only.\"}],\"max_tokens\":8,\"temperature\":0.1}" >/dev/null
    fi
    printf 'MLX server is ready: %s\n' "$BASE_URL"
    exit 0
  fi
done

printf 'MLX server did not become ready. See log: %s\n' "$LOG_FILE" >&2
exit 1
