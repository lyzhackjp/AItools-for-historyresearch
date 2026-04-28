# EmbeddingManager 轻量检索 Package 接口优化报告

## 基本信息

- 日期: 2026-04-25
- 模块: `modules/embedding_manager.py`
- 设计锚点: `docs/project/MODULE_OPTIMIZATION_DESIGN_2026-04-21.md`

## 优化目标

- 避免建索引默认触发重依赖、外网模型下载或远程 API 初始化。
- 为向量索引和语义检索提供统一 package 输出。
- 支持小模型 agent 在缺少 `numpy`、sentence-transformers、OpenAI SDK 等依赖时仍可导入和执行 smoke。

## 主要改动

- 新增 `auto_load_models` 参数，默认 `False`；未显式加载模型时使用确定性 mock embedding。
- 新增 `get_capabilities()`，声明支持模型、可用模型、安全默认值、懒加载和隐私标记。
- 新增 `create_vector_index_package()`，输出 `embedding_index` envelope。
- 新增 `semantic_search_package()`，输出 `semantic_search` envelope。
- 将 `numpy` 改为可选依赖；无 `numpy` 时使用纯 Python 随机向量、归一化、余弦相似度和内存估算。

## 验证结果

- `python -m py_compile modules\embedding_manager.py tests\test_embedding_manager_package.py`
- `python -m unittest tests.test_embedding_manager_package`
- `py -3.11 -m unittest ...` 宽回归集合通过。
- 结果: 3 个目标测试通过，98 个宽回归测试通过。

## 隐私与归档

- 未读取或写入 `secrets/`。
- 测试不调用真实模型、远程 API 或外部网络。
- 未生成需要额外归档删除的临时脚本。

## 后续建议

- 继续抽象 `EmbeddingProviderRegistry`，将 local/API/Ollama embedding 统一到 provider adapter。
- 后续可把嵌入索引 package 写入研究项目 artifact，用于 RAG、领域探索和相似史料检索。
