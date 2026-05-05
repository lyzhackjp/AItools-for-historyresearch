#!/usr/bin/env bash
set -euo pipefail

RUNTIME_BACKEND="ollama"
TIER="core"
SKIP_PULL=0
SKIP_CREATE=0
SMOKE=1
MLX_AUTO_START=0
SKIP_START=0
MLX_MODEL="${MLX_MODEL:-mlx-local-model}"
MLX_HOST="${MLX_HOST:-127.0.0.1}"
MLX_PORT="${MLX_PORT:-8080}"
MLX_BASE_URL="${MLX_BASE_URL:-http://$MLX_HOST:$MLX_PORT/v1}"
MLX_PYTHON="${MLX_PYTHON:-}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--ollama|--mlx] [--core|--full] [--skip-pull] [--skip-create] [--no-smoke]
       $(basename "$0") --mlx --mlx-model MODEL [--mlx-base-url URL] [--mlx-auto-start] [--skip-start] [--mlx-python PYTHON]
EOF
}

while (($#)); do
  case "$1" in
    --ollama)
      RUNTIME_BACKEND="ollama"
      shift
      ;;
    --mlx)
      RUNTIME_BACKEND="mlx"
      shift
      ;;
    --runtime)
      RUNTIME_BACKEND="$2"
      shift 2
      ;;
    --core)
      TIER="core"
      shift
      ;;
    --full)
      TIER="full"
      shift
      ;;
    --skip-pull)
      SKIP_PULL=1
      shift
      ;;
    --skip-create)
      SKIP_CREATE=1
      shift
      ;;
    --no-smoke)
      SMOKE=0
      shift
      ;;
    --mlx-model)
      MLX_MODEL="$2"
      shift 2
      ;;
    --mlx-base-url)
      MLX_BASE_URL="${2%/}"
      shift 2
      ;;
    --mlx-host)
      MLX_HOST="$2"
      MLX_BASE_URL="http://$MLX_HOST:$MLX_PORT/v1"
      shift 2
      ;;
    --mlx-port)
      MLX_PORT="$2"
      MLX_BASE_URL="http://$MLX_HOST:$MLX_PORT/v1"
      shift 2
      ;;
    --mlx-python)
      MLX_PYTHON="$2"
      shift 2
      ;;
    --mlx-auto-start)
      MLX_AUTO_START=1
      shift
      ;;
    --skip-start)
      SKIP_START=1
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

case "$RUNTIME_BACKEND" in
  ollama|mlx) ;;
  *)
    printf 'Unsupported runtime: %s\n' "$RUNTIME_BACKEND" >&2
    exit 2
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RUNTIME_DIR="${HISTORY_RESEARCH_RUNTIME_DIR:-$ROOT/.runtime}"
SUPPORT_DIR="${HISTORY_RESEARCH_SUPPORT_DIR:-$HOME/Library/Application Support/HistoryResearchAI}"
ENV_FILE="$ROOT/.env.local_llm"
APP_ENV_FILE="$SUPPORT_DIR/local-llm.env"

mkdir -p "$RUNTIME_DIR" "$SUPPORT_DIR"

write_env_files() {
  local content="$1"
  printf '%s\n' "$content" > "$ENV_FILE"
  printf '%s\n' "$content" > "$APP_ENV_FILE"
  printf 'Environment files written:\n'
  printf '  %s\n' "$ENV_FILE"
  printf '  %s\n' "$APP_ENV_FILE"
}

env_line() {
  local key="$1"
  local value="${2:-}"
  printf '%s=%q\n' "$key" "$value"
}

setup_mlx() {
  local auto_start_text="0"
  if [[ "$MLX_AUTO_START" -eq 1 ]]; then
    auto_start_text="1"
  fi

  write_env_files "$(cat <<EOF
$(env_line LOCAL_LLM_PROFILE m5_pro_48gb_mlx_history_research)
$(env_line LOCAL_LLM_PROVIDER mlx)
$(env_line LLM_PROVIDER mlx)
$(env_line LLM_BASE_URL "$MLX_BASE_URL")
$(env_line MLX_BASE_URL "$MLX_BASE_URL")
$(env_line MLX_HOST "$MLX_HOST")
$(env_line MLX_PORT "$MLX_PORT")
$(env_line MLX_MODEL "$MLX_MODEL")
$(env_line MLX_AUTO_START "$auto_start_text")
$(env_line MLX_PYTHON "$MLX_PYTHON")
$(env_line LOCAL_LLM_PRIMARY_MODEL "$MLX_MODEL")
$(env_line LOCAL_LLM_REASONING_MODEL "$MLX_MODEL")
$(env_line LOCAL_LLM_FAST_MODEL "$MLX_MODEL")
$(env_line LOCAL_LLM_EMBED_MODEL bge-m3)
EOF
)"

  if [[ "$MLX_AUTO_START" -eq 1 && "$SKIP_START" -eq 0 ]]; then
    MLX_ARGS=(--model "$MLX_MODEL" --host "$MLX_HOST" --port "$MLX_PORT")
    if [[ -n "$MLX_PYTHON" ]]; then
      MLX_ARGS+=(--python "$MLX_PYTHON")
    fi
    if [[ "$SMOKE" -eq 0 ]]; then
      MLX_ARGS+=(--no-smoke)
    fi
    bash "$SCRIPT_DIR/start-mlx-server.sh" "${MLX_ARGS[@]}"
  elif [[ "$MLX_AUTO_START" -eq 1 ]]; then
    printf '\nMLX auto-start config written; startup was skipped for this setup run.\n'
  elif [[ "$SMOKE" -eq 1 ]]; then
    printf '\n==> Smoke test: MLX endpoint %s\n' "$MLX_BASE_URL"
    curl -fsS "$MLX_BASE_URL/models" >/dev/null
  fi

  printf '\nLocal MLX setup complete.\n'
  printf 'To use it in this shell: set -a; source %s; set +a\n' "$ENV_FILE"
}

setup_ollama() {
  OLLAMA_BIN="${OLLAMA_BIN:-}"
  if [[ -z "$OLLAMA_BIN" ]]; then
    if command -v ollama >/dev/null 2>&1; then
      OLLAMA_BIN="$(command -v ollama)"
    elif [[ -x "$RUNTIME_DIR/bin/ollama" ]]; then
      OLLAMA_BIN="$RUNTIME_DIR/bin/ollama"
    fi
  fi

  if [[ -z "$OLLAMA_BIN" || ! -x "$OLLAMA_BIN" ]]; then
    printf 'Ollama CLI was not found.\n' >&2
    printf 'Install Ollama for macOS first, or place the CLI at %s/bin/ollama, then rerun this script.\n' "$RUNTIME_DIR" >&2
    exit 127
  fi

  export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
  export OLLAMA_MODELS="${OLLAMA_MODELS:-$RUNTIME_DIR/ollama-models}"
  export HOME="${OLLAMA_HOME:-$RUNTIME_DIR/ollama-home}"

  mkdir -p "$OLLAMA_MODELS" "$HOME"

  OLLAMA_URL="${OLLAMA_BASE_URL:-}"
  if [[ -z "$OLLAMA_URL" ]]; then
    if [[ "$OLLAMA_HOST" == http://* || "$OLLAMA_HOST" == https://* ]]; then
      OLLAMA_URL="$OLLAMA_HOST"
    else
      OLLAMA_URL="http://$OLLAMA_HOST"
    fi
  fi
  OLLAMA_URL="${OLLAMA_URL%/}"

  ensure_ollama_server() {
    if curl -fsS "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
      return 0
    fi

    printf 'Starting Ollama server at %s ...\n' "$OLLAMA_URL"
    nohup "$OLLAMA_BIN" serve > "$RUNTIME_DIR/ollama.log" 2>&1 &

    for _ in $(seq 1 30); do
      sleep 1
      if curl -fsS "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
        return 0
      fi
    done

    printf 'Ollama server did not become ready. See %s/ollama.log\n' "$RUNTIME_DIR" >&2
    return 1
  }

  pull_model() {
    local model="$1"
    printf '\n==> Pulling %s\n' "$model"
    "$OLLAMA_BIN" pull "$model"
  }

  create_model() {
    local name="$1"
    local modelfile="$2"
    printf '\n==> Creating %s from %s\n' "$name" "$modelfile"
    "$OLLAMA_BIN" create "$name" -f "$modelfile"
  }

  ensure_ollama_server

  CORE_MODELS=(
    "qwen3.6:27b"
    "bge-m3"
  )

  FULL_MODELS=(
    "qwen3.6:27b"
    "gemma4:31b"
    "gemma4:e4b"
    "bge-m3"
    "qwen3-embedding:0.6b"
  )

  if [[ "$SKIP_PULL" -eq 0 ]]; then
    if [[ "$TIER" == "full" ]]; then
      for model in "${FULL_MODELS[@]}"; do
        pull_model "$model"
      done
    else
      for model in "${CORE_MODELS[@]}"; do
        pull_model "$model"
      done
    fi
  fi

  if [[ "$SKIP_CREATE" -eq 0 ]]; then
    create_model "qwen36-27b-academic" "$ROOT/models/ollama/Modelfile.qwen36-27b-academic"
    if [[ "$TIER" == "full" ]]; then
      create_model "gemma4-31b-reason" "$ROOT/models/ollama/Modelfile.gemma4-31b-reason"
      create_model "gemma4-e4b-fast" "$ROOT/models/ollama/Modelfile.gemma4-e4b-fast"
    fi
  fi

  write_env_files "$(cat <<EOF
$(env_line LOCAL_LLM_PROFILE m5_pro_48gb_history_research)
$(env_line LOCAL_LLM_PROVIDER ollama)
$(env_line LLM_PROVIDER ollama)
$(env_line LLM_BASE_URL "$OLLAMA_URL")
$(env_line OLLAMA_BASE_URL "$OLLAMA_URL")
$(env_line OLLAMA_HOST "$OLLAMA_HOST")
$(env_line OLLAMA_MODELS "$OLLAMA_MODELS")
$(env_line OLLAMA_MODEL qwen36-27b-academic)
$(env_line LOCAL_LLM_PRIMARY_MODEL qwen36-27b-academic)
$(env_line LOCAL_LLM_REASONING_MODEL gemma4-31b-reason)
$(env_line LOCAL_LLM_FAST_MODEL gemma4:e4b)
$(env_line OLLAMA_EMBED_MODEL bge-m3)
$(env_line LOCAL_LLM_EMBED_MODEL bge-m3)
EOF
)"

  if [[ "$SMOKE" -eq 1 ]]; then
    printf '\n==> Smoke test: qwen36-27b-academic\n'
    "$OLLAMA_BIN" run qwen36-27b-academic "Say OK only."
  fi

  printf '\nLocal Ollama setup complete.\n'
  printf 'To use it in this shell: set -a; source %s; set +a\n' "$ENV_FILE"
}

if [[ "$RUNTIME_BACKEND" == "mlx" ]]; then
  setup_mlx
else
  setup_ollama
fi
