#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FRONTEND_DIR="$ROOT/frontend"
NPM_CACHE_DIR="${HISTORY_RESEARCH_NPM_CACHE_DIR:-$ROOT/.runtime/npm-cache}"

usage() {
  printf 'Usage: %s\n' "$(basename "$0")"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

NPM_BIN="${NPM:-}"
if [[ -z "$NPM_BIN" ]]; then
  if command -v npm >/dev/null 2>&1; then
    NPM_BIN="$(command -v npm)"
  else
    printf 'npm was not found. Install Node.js 18+ from https://nodejs.org/ or set NPM=/path/to/npm.\n' >&2
    exit 1
  fi
fi

if [[ "$NPM_BIN" != /* ]]; then
  NPM_BIN="$ROOT/$NPM_BIN"
fi

if [[ ! -x "$NPM_BIN" ]]; then
  printf 'npm is not executable: %s\n' "$NPM_BIN" >&2
  exit 1
fi

if [[ ! -f "$FRONTEND_DIR/package.json" ]]; then
  printf 'frontend/package.json was not found: %s\n' "$FRONTEND_DIR/package.json" >&2
  exit 1
fi

mkdir -p "$NPM_CACHE_DIR"
export npm_config_cache="$NPM_CACHE_DIR"
export PATH="$(dirname "$NPM_BIN"):$PATH"

cd "$FRONTEND_DIR"

if [[ -f package-lock.json ]]; then
  "$NPM_BIN" ci
else
  "$NPM_BIN" install
fi

"$NPM_BIN" run build

printf 'Frontend build complete: %s\n' "$FRONTEND_DIR/dist"
