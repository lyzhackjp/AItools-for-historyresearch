# macOS 应用打包路线

本文档记录将源码工作区打包为 macOS `.app` 的路线。当前阶段提供本地测试用的未签名 app bundle；面向公开分发前，还需要补齐签名、公证和 DMG 安装包。

## 当前脚手架

本仓库提供：

```bash
bash scripts/macos/package-app.sh
```

生成结果：

```text
dist-macos/History Research AI.app
```

打包脚本会：

- 初始化 `.runtime/venv`。
- 构建 `frontend/dist`。
- 复制必要源码、前端构建产物和 Python venv 到 app bundle。
- 默认不复制个人 `.env.local_llm`，避免把本机路径写进分发包。需要制作本机专用包时可加 `--include-local-llm-env`，首次启动时会写入 `~/Library/Application Support/HistoryResearchAI/local-llm.env`。
- 生成 `Contents/Info.plist` 和 `Contents/MacOS/HistoryResearchAI` 启动器。
- 将运行日志、PID 和缓存放到 `~/Library/Application Support/HistoryResearchAI/runtime`。

## 本地测试

```bash
bash scripts/macos/package-app.sh
open "dist-macos/History Research AI.app"
```

默认端口为 `5050`，可用以下方式覆盖：

```bash
bash scripts/macos/package-app.sh --port 5060
```

## 本地 MLX 配置

macOS 包不会内置模型权重。推荐在打包前先写入本机 MLX 配置：

```bash
bash scripts/macos/setup-local-llm.sh --mlx --mlx-model "你的MLX模型ID" --mlx-base-url http://127.0.0.1:8080/v1 --no-smoke
bash scripts/macos/package-app.sh --include-local-llm-env
```

如果目标机器已经安装 `mlx-lm`，并希望 app 启动时自动拉起服务：

```bash
bash scripts/macos/setup-local-llm.sh --mlx --mlx-model "你的MLX模型ID" --mlx-auto-start --skip-start --no-smoke
bash scripts/macos/check-mlx-runtime.sh
```

使用 `--include-local-llm-env` 打包后，首次打开 `.app` 时，launcher 会把 bundle 内的默认配置复制到：

```text
~/Library/Application Support/HistoryResearchAI/local-llm.env
```

后续更新 app 时不会覆盖这个用户配置文件。

## 分发前仍需完成

1. 图标资源：添加 `.icns` 并写入 `CFBundleIconFile`。
2. 代码签名：使用 Apple Developer ID 对 app bundle 签名。
3. 公证：通过 Apple notarization，避免 Gatekeeper 拦截。
4. DMG：生成拖拽安装用 `.dmg`。
5. 外部能力策略：明确 Tesseract、Poppler、MLX-LM、Ollama、NDL OCR 模型是否内置、首次启动下载，或保持用户自行安装。
6. 体积控制：PyTorch、ChromaDB、ONNX、OCR 模型会显著增大包体，需要拆分“基础版”和“研究增强版”。

## 重要限制

- 当前 `.app` 是未签名本地测试包，不适合作为公开发布物。
- 打包出的 venv 与构建机器的 CPU 架构相关。Apple Silicon 和 Intel Mac 应分别构建。
- 私密数据、`.env`、`secrets/`、日志和缓存不会被复制进 bundle。
