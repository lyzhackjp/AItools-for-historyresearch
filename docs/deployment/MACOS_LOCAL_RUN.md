# macOS 本地运行说明

本文档说明如何在 macOS 上以源码工作区方式运行 History Research AI。当前适配目标是“最小改动、直接可用”，不包含 `.app`、`.dmg`、签名或公证流程。

## 系统要求

- macOS 12 或更新版本。
- Python 3.8-3.11，推荐 Python 3.11。
- Node.js 18+，仅在需要重新构建前端时使用。
- 可选外部工具：
  - Tesseract OCR: `brew install tesseract`
  - Poppler: `brew install poppler`
  - MLX-LM: 已有本地 MLX 部署时直接配置端点即可
  - Ollama: `brew install ollama`

## 配置本地大模型

macOS 优先使用本机 MLX-LM 部署。若 MLX 服务已经在 `http://127.0.0.1:8080/v1` 这类 OpenAI-compatible 端点运行：

```bash
bash scripts/macos/setup-local-llm.sh --mlx --mlx-model "你的MLX模型ID" --mlx-base-url http://127.0.0.1:8080/v1
```

若希望源码启动或 `.app` 启动时自动尝试拉起 MLX server：

```bash
bash scripts/macos/setup-local-llm.sh --mlx --mlx-model "你的MLX模型ID" --mlx-auto-start --no-smoke
```

如果模型是本机目录，或 `mlx_lm` 安装在单独 venv 中，可以直接传入路径；脚本会自动转义 `Application Support` 这类带空格路径：

```bash
bash scripts/macos/setup-local-llm.sh --mlx \
  --mlx-model "/path/to/mlx-model-dir" \
  --mlx-python "/path/to/mlx-venv/bin/python" \
  --mlx-auto-start --skip-start --no-smoke
bash scripts/macos/check-mlx-runtime.sh
```

Ollama 仍可作为后备：

```bash
bash scripts/macos/setup-local-llm.sh --ollama --core
```

详见 [本地大模型部署说明](LOCAL_LLM_OLLAMA_SETUP.md)。

## 初始化 Python 运行时

在仓库根目录运行：

```bash
bash scripts/macos/initialize-history-research-ai.sh
```

脚本会创建并复用：

```text
.runtime/venv
.runtime/install.ok
.runtime/cache
.runtime/pycache
```

如果你希望指定 Python，可使用：

```bash
HISTORY_RESEARCH_PYTHON=/opt/homebrew/bin/python3.11 bash scripts/macos/initialize-history-research-ai.sh
```

若需要重新安装依赖：

```bash
bash scripts/macos/initialize-history-research-ai.sh --force
```

macOS 初始化会自动使用 [requirements-macos.txt](../../requirements-macos.txt) 作为约束文件，以减少依赖解析回溯并规避 Apple 系统 Python 常见的缓存与兼容性警告。

## 构建前端

如果 `frontend/dist/index.html` 不存在，后端仍可启动 API，但根路径不会返回 React UI。构建方式：

```bash
bash scripts/macos/build-frontend.sh
```

如果脚本提示找不到 `npm`，请安装 Node.js 18+，或设置 `NPM=/path/to/npm` 后重试。

## 启动本地 UI

```bash
bash scripts/macos/start-history-research-ai.sh
```

默认端口是 `5050`，避开 macOS AirPlay/AirTunes 常见占用的 `5000`。启动后打开：

```text
http://127.0.0.1:5050/
```

指定端口：

```bash
bash scripts/macos/start-history-research-ai.sh --port 5050
```

只启动服务、不自动打开浏览器：

```bash
bash scripts/macos/start-history-research-ai.sh --no-open
```

启动日志写入：

```text
.runtime/backend.log
```

启动脚本会自动读取：

```text
.env.local_llm
~/Library/Application Support/HistoryResearchAI/local-llm.env
```

因此用 `setup-local-llm.sh --mlx` 写入配置后，不需要每次手动 `source` 环境变量。

## 停止服务

```bash
bash scripts/macos/stop-history-research-ai.sh
```

脚本会读取 `.runtime/backend.pid`，停止对应后端进程并清理 PID 文件。

## 常见问题

### Python 版本不兼容

脚本只接受 Python 3.8-3.11。若系统默认 `python3` 是 3.12 或更新版本，请安装 Python 3.11，并用 `HISTORY_RESEARCH_PYTHON` 指定解释器。

### 依赖安装失败

`requirements.txt` 包含 PyTorch、ONNX、OCR、RAG 等较重依赖。macOS 首次安装失败时，优先查看具体失败包，并确认 Python 版本和芯片架构支持情况。

如果你已经初始化过环境，但本仓库更新了 macOS 依赖约束，请运行：

```bash
bash scripts/macos/initialize-history-research-ai.sh --force
```

### 页面 404

确认是否已经构建前端：

```bash
test -f frontend/dist/index.html
```

若不存在，按“构建前端”步骤运行。

## 打包为 macOS App

本地测试用 app bundle 可通过以下命令生成：

```bash
bash scripts/macos/package-app.sh
```

详见 [macOS 应用打包路线](MACOS_APP_PACKAGING.md)。

### OCR 工具不可用

Tesseract、Poppler、NDL OCR-Lite、NDL 古典籍 OCR-Lite 都属于外部能力。macOS 启动脚本不会自动安装它们，避免静默改动系统环境。请按具体功能文档配置路径和模型。
