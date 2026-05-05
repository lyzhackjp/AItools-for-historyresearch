# 本地大模型部署：MLX / Ollama

本文档是本仓库的本地大模型配置入口，面向 48GB 统一内存的 Apple Silicon 机器。macOS 优先推荐已有 MLX-LM 部署；Ollama 仍作为跨平台本地后备。

## MLX 优先配置

如果本机已经用 MLX-LM 部署了聊天模型，并暴露 OpenAI-compatible 服务，推荐写入 MLX 配置：

```bash
bash scripts/macos/setup-local-llm.sh --mlx --mlx-model "你的MLX模型ID" --mlx-base-url http://127.0.0.1:8080/v1
```

如果服务尚未启动，但当前 shell 能找到安装了 `mlx_lm` 的 Python，可以让启动脚本自动拉起 MLX server：

```bash
bash scripts/macos/setup-local-llm.sh --mlx --mlx-model "你的MLX模型ID" --mlx-auto-start --no-smoke
```

如果 `mlx_lm` 装在单独 venv，或模型路径位于 `Application Support` 这类带空格目录，直接传入完整路径即可：

```bash
bash scripts/macos/setup-local-llm.sh --mlx \
  --mlx-model "/path/to/mlx-model-dir" \
  --mlx-python "/path/to/mlx-venv/bin/python" \
  --mlx-auto-start --skip-start --no-smoke
bash scripts/macos/check-mlx-runtime.sh
```

这会同时写入：

```text
.env.local_llm
~/Library/Application Support/HistoryResearchAI/local-llm.env
```

源码启动和打包后的 `.app` 都会自动读取这些本地配置。常用环境变量：

```bash
LOCAL_LLM_PROFILE=m5_pro_48gb_mlx_history_research
LOCAL_LLM_PROVIDER=mlx
LLM_PROVIDER=mlx
MLX_BASE_URL=http://127.0.0.1:8080/v1
MLX_MODEL=你的MLX模型ID
MLX_AUTO_START=0
MLX_PYTHON=/path/to/mlx-venv/bin/python
```

可从 [config/local-llm.mlx.example.env](../../config/local-llm.mlx.example.env) 复制一份起步配置，再把 `MLX_MODEL` 改成本机实际模型 ID。

单独启动 MLX server：

```bash
bash scripts/macos/start-mlx-server.sh --model "你的MLX模型ID" --port 8080
```

## Ollama 模型组合

| 用途 | 仓库内模型名 | Ollama 基座 | 默认上下文 |
|---|---|---|---:|
| 中文学术主力 | `qwen36-27b-academic` | `qwen3.6:27b` | 32768 |
| 英文/推理/图表副主力 | `gemma4-31b-reason` | `gemma4:31b` | 32768 |
| 快速本地备用 | `gemma4:e4b` | `gemma4:e4b` | 16384 |
| RAG embedding | `bge-m3` | `bge-m3` | 8192 |
| 长文本 embedding 备选 | `qwen3-embedding:0.6b` | `qwen3-embedding:0.6b` | 32768 |

配置画像在 [config/local_llm_profiles.json](../../config/local_llm_profiles.json)，Python 代码通过 [config/local_llm_config.py](../../config/local_llm_config.py) 读取。常用环境变量：

```bash
LOCAL_LLM_PROFILE=m5_pro_48gb_history_research
LOCAL_LLM_PROVIDER=ollama
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen36-27b-academic
OLLAMA_EMBED_MODEL=bge-m3
OLLAMA_BASE_URL=http://localhost:11434
```

## Ollama 一键配置

先安装 Ollama，然后在仓库根目录运行：

```bash
bash scripts/macos/setup-local-llm.sh --ollama --core
```

`--core` 会拉取中文主力模型和 embedding 模型，并创建 `qwen36-27b-academic`。完整双主力组合：

```bash
bash scripts/macos/setup-local-llm.sh --ollama --full
```

脚本会生成 `.env.local_llm` 和 app 支持目录下的 `local-llm.env`，并执行一次 `Say OK only.` smoke test。

## 推荐使用方式

日常中文论文、读书笔记、文献综述和润色使用 `qwen36-27b-academic`。英文论文结构分析、代码推理、图表或图片材料理解、交叉审读使用 `gemma4-31b-reason`。RAG 不建议硬塞超长 PDF，默认使用 1000 字符左右分块、150 overlap、top_k 10。

48GB 统一内存机器不建议同时常驻两个 27B/31B 大模型。若响应变慢，优先把上下文降到 16384，或只保留当前工作模型。

## 仓库接入点

- Flask 后端默认本地优先：`app/config.py`
- 统一任务层本地后端：`modules/unified_task_executor.py`
- 任务预设：`modules/task_manager.py`
- MLX/Ollama 客户端：`modules/llm_client.py`
- RAG 本地配置：`rag_module/core/config.py`
- Ollama embedding：`modules/embedding_manager.py`

远程 API 仍然可用。设置 `LOCAL_LLM_ENABLED=false` 或显式设置 `LLM_PROVIDER=dashscope/openai/deepseek` 即可切回远程提供商。
