#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RUNTIME_DIR="${HISTORY_RESEARCH_RUNTIME_DIR:-$ROOT/.runtime}"
PID_FILE="$RUNTIME_DIR/backend.pid"

if [[ ! -f "$PID_FILE" ]]; then
  printf 'No backend service record was found.\n'
  exit 0
fi

PID_VALUE="$(head -n 1 "$PID_FILE" || true)"
if [[ ! "$PID_VALUE" =~ ^[0-9]+$ ]]; then
  rm -f "$PID_FILE"
  printf 'Invalid runtime record cleaned.\n'
  exit 0
fi

if kill -0 "$PID_VALUE" >/dev/null 2>&1; then
  kill "$PID_VALUE"
  printf 'Stopped backend service: PID %s\n' "$PID_VALUE"
else
  printf 'Backend service is not running. Runtime record cleaned.\n'
fi

rm -f "$PID_FILE"
