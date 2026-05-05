#!/usr/bin/env bash
set -euo pipefail

APP_NAME="History Research AI"
PORT=5050
SKIP_FRONTEND=0
SKIP_INIT=0
INCLUDE_LOCAL_LLM_ENV=0

usage() {
  cat <<'EOF'
Usage: package-app.sh [--app-name NAME] [--port PORT] [--skip-frontend] [--skip-init] [--include-local-llm-env]

Builds a first-pass macOS .app bundle in dist-macos/.
The bundle is unsigned and intended for local testing before a later DMG,
code signing, and notarization workflow.
EOF
}

while (($#)); do
  case "$1" in
    --app-name)
      APP_NAME="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --skip-frontend)
      SKIP_FRONTEND=1
      shift
      ;;
    --skip-init)
      SKIP_INIT=1
      shift
      ;;
    --include-local-llm-env)
      INCLUDE_LOCAL_LLM_ENV=1
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
DIST_DIR="$ROOT/dist-macos"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
CONTENTS_DIR="$APP_BUNDLE/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
APP_RESOURCE_DIR="$RESOURCES_DIR/app"

if [[ "$SKIP_INIT" -eq 0 ]]; then
  "$SCRIPT_DIR/initialize-history-research-ai.sh"
fi

if [[ "$SKIP_FRONTEND" -eq 0 ]]; then
  "$SCRIPT_DIR/build-frontend.sh"
fi

if [[ ! -x "$ROOT/.runtime/venv/bin/python" ]]; then
  printf 'Packaged Python runtime was not found. Run scripts/macos/initialize-history-research-ai.sh first.\n' >&2
  exit 1
fi

if [[ ! -f "$ROOT/frontend/dist/index.html" ]]; then
  printf 'frontend/dist/index.html was not found. Build the frontend before packaging the app UI.\n' >&2
  exit 1
fi

rm -rf "$APP_BUNDLE"
mkdir -p "$MACOS_DIR" "$APP_RESOURCE_DIR"

rsync -a "$ROOT/" "$APP_RESOURCE_DIR/" \
  --exclude '.git/' \
  --exclude '.runtime/' \
  --exclude 'dist-macos/' \
  --exclude 'dist-windows/' \
  --exclude 'frontend/node_modules/' \
  --exclude 'secrets/' \
  --exclude 'config/api_config.json' \
  --exclude 'config/current_environment.json' \
  --exclude 'config/external_config.json' \
  --exclude 'config/*.local.json' \
  --exclude '.env' \
  --exclude '.env.*' \
  --exclude '*.log' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/'

mkdir -p "$APP_RESOURCE_DIR/.runtime"
rsync -a "$ROOT/.runtime/venv/" "$APP_RESOURCE_DIR/.runtime/venv/"

if [[ "$INCLUDE_LOCAL_LLM_ENV" -eq 1 && -f "$ROOT/.env.local_llm" ]]; then
  mkdir -p "$RESOURCES_DIR/defaults"
  cp "$ROOT/.env.local_llm" "$RESOURCES_DIR/defaults/local-llm.env"
fi

cat > "$CONTENTS_DIR/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleExecutable</key>
  <string>HistoryResearchAI</string>
  <key>CFBundleIdentifier</key>
  <string>jp.lyzhack.historyresearchai</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>$APP_NAME</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.1.0</string>
  <key>CFBundleVersion</key>
  <string>1.1.0</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
</dict>
</plist>
EOF

cat > "$MACOS_DIR/HistoryResearchAI" <<EOF
#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")/../Resources/app" && pwd)"
SUPPORT_DIR="\${HOME}/Library/Application Support/HistoryResearchAI"
mkdir -p "\$SUPPORT_DIR"

DEFAULT_LOCAL_LLM_ENV="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")/../Resources" && pwd)/defaults/local-llm.env"
if [[ ! -f "\$SUPPORT_DIR/local-llm.env" && -f "\$DEFAULT_LOCAL_LLM_ENV" ]]; then
  cp "\$DEFAULT_LOCAL_LLM_ENV" "\$SUPPORT_DIR/local-llm.env"
fi

export HISTORY_RESEARCH_RUNTIME_DIR="\$SUPPORT_DIR/runtime"
export HISTORY_RESEARCH_VENV_PYTHON="\$APP_ROOT/.runtime/venv/bin/python"
export HISTORY_RESEARCH_SUPPORT_DIR="\$SUPPORT_DIR"

exec bash "\$APP_ROOT/scripts/macos/start-history-research-ai.sh" --port "${PORT}"
EOF

chmod +x "$MACOS_DIR/HistoryResearchAI"

printf 'macOS app bundle created: %s\n' "$APP_BUNDLE"
printf 'This bundle is unsigned. Use codesign/notarization before public distribution.\n'
