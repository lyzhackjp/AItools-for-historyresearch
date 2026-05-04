# History Citation GitHub 上传准备说明

日期：2026-05-04

## 本次建议纳入版本库的内容

### 源码与配置

- `modules/historical_citation_verifier.py`
- `modules/historical_citation/fullrun.py`
- `modules/historical_citation/pdf_paper_parser.py`
- `modules/historical_citation/source_graph.py`
- `modules/historical_citation/source_resolvers.py`
- `modules/historical_citation/*.py` 中与 PDF、NDL、报告、LLM 精核、source graph 相关的修改
- `config/historical_citation_source_resolvers.json`
- `scripts/run_historical_citation_pdf_verifier.py`
- `scripts/run_historical_citation_pdf_fullrun.py`
- `scripts/refine_historical_citation_pdf_next_stage.py`
- `scripts/probe_historical_citation_source_types.py`
- `tests/test_historical_citation_verifier.py`

### 文档

- `docs/history-citation-module-development-report-20260428.md`
- `docs/history-citation-current-results-report-20260504.md`
- `docs/history-citation-fullrun-optimization-plan-20260430.md`
- `docs/history-citation-github-upload-prep-20260504.md`

### 仓库卫生

- `.gitattributes`：固定常见文本文件 LF 行尾，并把 PDF/图片/Office 文件标记为 binary。

## 不应上传的中间产物

以下目录和文件类型已由 `.gitignore` 覆盖，保留在本地即可：

- `output/`
- `ocr_output/`
- `cache/`
- `tmp/`
- `temp/`
- `downloads/`
- `secrets/`
- PDF、DOCX、PPTX、XLSX 等研究材料和渲染文件
- `verification_results.json`
- `verification_report.md`
- `partial_resume_report.md`
- `page_mapping_cache.json`
- `*.jsonl`

## 本次整理动作

- 将根目录阶段性报告移动到 `docs/`：
  - `history_citation_current_results_report_20260504.md` -> `docs/history-citation-current-results-report-20260504.md`
  - `history_citation_fullrun_optimization_plan_20260430.md` -> `docs/history-citation-fullrun-optimization-plan-20260430.md`
- 更新模块开发报告中的 CLI 入口与阶段性文档索引。
- 修复 next-stage 慢路径报告的小错误：当 `source_mismatch_recheck` 等候选级阶段本身耗时但没有 worker 子阶段时，slow-event summary 现在显示 `source_mismatch_recheck_total`，不再出现空的 `longest_subphase`。
- 增加回归测试覆盖该慢路径 fallback。

## 上传前验证

### 语法检查

命令：

```powershell
python -m compileall modules\historical_citation modules\historical_citation_verifier.py scripts\run_historical_citation_pdf_verifier.py scripts\run_historical_citation_pdf_fullrun.py scripts\refine_historical_citation_pdf_next_stage.py scripts\probe_historical_citation_source_types.py
```

结果：通过。

### 单元测试

命令：

```powershell
python -m unittest tests.test_historical_citation_verifier
```

结果：`Ran 251 tests in 271.413s OK (skipped=5)`。

### GitHub 安全检查

命令：

```powershell
python scripts\check_github_upload_safety.py
```

当前结论：运行产物、私有论文、OCR 输出、登录信息和缓存均未进入待上传集合。

## 建议提交说明

建议 commit message：

```text
Improve historical citation PDF verification workflow
```

建议 PR 摘要：

- Add PDF paper parsing and full-run/next-stage CLI paths for historical citation verification.
- Add source graph and source resolver support for NDL volume series, source collections, diaries, contained documents, and secondary scholarship.
- Add multi-hit NDL fulltext context expansion with Gemma review.
- Align PDF reports with the Word successful report structure.
- Add regression coverage for NDL PID routing, fulltext-only evidence, slow-event diagnostics, and formal Gemma review policy.
