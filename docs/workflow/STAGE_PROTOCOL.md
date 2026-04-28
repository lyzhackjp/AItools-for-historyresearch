# 阶段协议

## 统一阶段结果

每个 stage 的执行结果应尽量包含:

```python
{
    "stage": "extract",
    "status": "success",
    "summary": {},
    "artifacts": [],
    "backend": "script",
    "provider": "local",
    "model": None,
    "confidence": 0.0,
    "needs_review": False,
    "quality_flags": [],
    "review_items": [],
    "errors": []
}
```

## 项目状态写回

阶段产物不应只保存在局部变量中，应写回 `ResearchProject`:

- `stage_metadata`: 阶段执行摘要、后端快照、统计、耗时。
- `artifacts`: 正式产物路径与说明。
- `quality_flags`: 低置信度、降级执行、缺失字段、格式不一致等标记。
- `review_queue`: 需要人工复核的实体、引文、段落、页码或输出项。

## 后端元数据

所有支持多后端的模块都应暴露或记录:

- `backend`: `script` / `llm_api` / `local_llm` / `skill` / `mcp` / `hybrid`
- `provider`: 如 `dashscope`、`openai`、`ollama`、`local_rules`
- `model`: 实际模型名或规则集名
- `capabilities`: 当前后端能力清单
- `fallback_order`: 失败时的回退顺序

## 失败处理

- 外部 API 失败不应直接中断全流程，除非该阶段没有任何可用回退。
- 降级结果必须设置 `needs_review=True` 或写入 `quality_flags`。
- 错误报告记录错误类别和调用位置，不记录密钥或敏感原文。

## Artifact 记录

artifact 记录至少包含:

- `path`: 本地路径
- `type`: `json` / `csv` / `markdown` / `docx` / `image` / `cache`
- `stage`: 产生阶段
- `description`: 脱敏说明
- `created_at`: 创建时间

临时产物不应长期留在根目录。

## 2026-04-25 Package 接口补充

- 摄入类 artifact package 示例: `pdf_image_conversion`，必须包含 `artifacts[]` 与页级映射字段。
- OCR 类 package 示例: `ocr_result` / `ocr_batch`，必须包含页级文本、OCR 后端元数据、置信度和复核标记。
- 分析类 graph package 示例: `citation_network`，必须包含 `records/nodes/edges/summary` 与执行元数据。
- 抽取类 package 示例: `ner_extraction`，必须包含来源标识、实体数量、后端元数据、置信度和复核标记。
- 包装接口可以与旧 API 并存，但 workflow 新实现应优先使用 package 接口，并只把旧 API 作为兼容层。

## 2026-04-25 Project Package Registry Requirement

- Workflow stages that receive a module package/envelope should call `ResearchProject.register_package(package, stage=..., source=...)` before finishing.
- Stage metadata should keep a compact protocol snapshot such as `package_protocol.registry`, `registered_package_count`, and `registered_packages`.
- The package registry is the shared handoff for artifacts, quality flags, review items, API responses, and AI-agent skill calls; execution summaries alone are not enough for new stage work.

## 2026-04-25 Checkpoint Artifact Manager Requirement

- Workflow checkpoint JSON should be written through `ArtifactManager.write_json_artifact()` so path validation, managed-root constraints, and manifest summaries remain consistent.
- `ResearchProject.save(path)` remains available for compatibility and manual exports, but orchestrated checkpoint writes should use the artifact manager path.
- Checkpoint paths may still be registered back to `ResearchProject.register_artifact()` for stage-level recovery metadata.
