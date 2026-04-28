# Historical Citation 模块说明

本目录承接 `HistoricalCitationVerifier` 的核心能力拆分。外部脚本仍可继续使用 `modules.historical_citation_verifier.HistoricalCitationVerifier`，新模块主要用于让各环节可以独立测试、替换和优化。

## 数据流

1. `docx_parser.py` 读取 Word 文档，抽取正文段落、脚注 XML 和引用候选。
2. `footnote_parser.py` 从脚注文本中解析题名、作者、出版社、年份、页码和译文候选。
3. `source_platforms.py` 统一调度线上史料平台适配器，目前内置 NDL、Japan Search、Internet Archive。
4. `ndl_search.py` 生成 NDL 检索关键词/SRU 查询，解析 SRU XML，并按题名、作者、年份、出版社给候选打分。
5. `source_acquisition.py` 选择可下载候选，处理公共 PDF 下载、受限下载页窗计划和下载请求参数。
6. `page_mapping.py` 维护书页到 NDL 扫描页的双开页映射缓存。
7. `pdf_ocr.py` 处理 PDF readiness、页面渲染、双开页切图、OCR 调用和页面文本抽取。
8. `alignment.py` 将中文译文与日文 OCR 段落做候选分段、启发式打分、LLM 选择和片段裁剪。
9. `reporting.py` 渲染可读 Markdown 报告和 checkpoint 汇总。
10. `status.py` 将粗粒度失败状态细分为超时、受限下载失败、同源跳过、线上平台未检出等原因。

## 兼容入口

`modules/historical_citation_verifier.py` 现在主要作为 facade/编排器存在。它仍保留旧方法名，例如：

- `parse_docx`
- `build_candidates`
- `search_ndl_sources`
- `_obtain_source_pdf`
- `_extract_pages_directly`
- `_align_translation`
- `render_markdown_report`

这些方法内部会转发到本目录下的专门模块，保证现有脚本和测试无需改调用方式。

## 当前验证基线

- 单元测试：`py -3.11 -m unittest tests.test_historical_citation_verifier`
- 当前通过数：45
- fullrun 回归：`scripts/resume_historical_citation_verifier.py --report-only`
- 基线结果：32 个候选，5 个 `matched`，6 个 `needs_manual_review`，21 个 `download_failed`

## 后续优化点

- 把 `resume_historical_citation_verifier.py` 和 `batch_resume_historical_citation_verifier.py` 的 runner/checkpoint 逻辑继续拆成正式 runner 模块。
- 为 `source_acquisition.py` 增加“题名明显不匹配时跳过下载”的硬阈值，减少无效受限下载。
- 为 `alignment.py` 增加更稳定的日中跨语种相似度特征，并把 LLM prompt 做成可配置模板。
- 将报告中的失败状态细分与后续重试策略绑定，例如只重试 `download_timeout` 和 `runner_failed`。

## NDL 受限下载恢复策略

`ndl-search/browser_client.py` 和 `modules/workflows/ndl_download.py` 已加入一层浏览器恢复逻辑，用于处理 NDL 受限下载中常见的不稳定行为：

- 登录后页面没有正确显示下载能力时，会在下一次可恢复失败后执行刷新、重新确认登录，并回到目标 `pid` 页面。
- 点击“印刷用ファイルを開く”后，会主动滚动到页面顶部，因为可用 PDF 链接经常显示在页面上方。
- 链接查找不只依赖可见文字，也会扫描所有 `<a>` 的 `href`，并从页面 HTML 中兜底提取带 `Key-Pair-Id`、`X-Amz-Signature`、`/download/` 或 `.pdf` 的预签名链接。
- 对 `download_link_not_found`、`print_dialog_setup_failed`、`download_http_403`、`lambda_http_403`、`presigned_http_403` 等错误，会触发浏览器恢复后重试。

## Source Platform Adapter Layer

`source_platforms.py` 为线上公开史料库提供平台边界。核对器现在通过 `SourcePlatformRegistry` 调用 `search_sources()`；NDL 是默认适配器之一，而不是主流程里的硬编码假设。

当前内置适配器：

- `ndl`: 使用 NDL SRU/检索与既有受限下载流程，仍是日本近现代书籍史料的主入口。
- `japan_search`: 通过 Japan Search 公共 SPARQL 端点检索元数据；目前用于发现跨机构馆藏线索，暂不直接下载 PDF。
- `internet_archive`: 通过 Internet Archive advanced search/metadata API 检索公共文本，并在存在 `_text.pdf` 时下载 PDF；默认过滤低分误配，避免报纸、期刊等弱相关结果污染脚注匹配。

CLI 可用 `--platform` 限定平台；不指定时使用默认平台集合。例如只跑 NDL：`--platform ndl`；扩大搜索：不传 `--platform` 或显式重复传入 `--platform ndl --platform japan_search --platform internet_archive`。

长文档或外审材料建议先用轻量检索模式：`--no-ndl-browser-fallback` 可避免 NDL 公共 API 无结果时反复启动浏览器兜底搜索；`resume_historical_citation_verifier.py --search-only --stop-after N` 可分批写入 checkpoint。这样先获得平台覆盖率和未命中清单，再对少数关键脚注补跑受限下载、截图、OCR 和段落对齐。若 OCR 子进程在大上下文窗口下超时，可先用 `--ocr-page-window 1` 完成闭环并保留 PDF，再逐步扩大上下文。

新增平台适配器应实现 `SourcePlatformAdapter`：

- `name`: 稳定的平台 ID，例如 `ndl`、`jstage` 或 `university_repo`。
- `search(footnote, max_results=5)`: 返回标准化的 `NDLSearchMatch` 对象。类名为兼容旧流程保留，但对象现在包含 `platform` 与 `platform_item_id`。
- `download_public_pdf(match, output_dir=...)`: 平台暴露公共 PDF 时，下载并返回本地 PDF 路径。
- `build_restricted_download_requests(...)`: 公共 PDF 不可用时，返回平台专用浏览器/下载任务。没有受限下载流程的平台可返回空列表。
- `select_preferred_match(matches)`: 在本平台候选中选择最适合进入下载/OCR 的记录。

NDL 严格过滤会把明显元数据误配标为 `metadata["source_mismatch"] = True`。如果某条脚注返回的候选全部被过滤器拒绝，核对器会报告 `source_mismatch`，并跳过下载/OCR。

建议的新增平台工作流：

1. 增加一个实现 `SourcePlatformAdapter` 的小型适配器。
2. 将远端检索结果标准化为 `NDLSearchMatch(platform="<new-platform>", platform_item_id="<remote-id>", ...)`。
3. 复用现有 PDF/OCR/对齐/报告模块，不复制下游逻辑。
4. 使用合成数据编写测试，不放入真实论文文本、史料片段、账号数据或下载材料。

## NDL 凭据提供方式

NDL 账号密码不得写入模块源码、测试文件、报告或可提交配置。受限下载流程统一通过 `modules.workflows.ndl_credentials` 读取由使用者在模块外部提供的凭据，支持以下方式：

- 环境变量：`NDL_USERNAME` 或 `NDL_CARD_ID`，配合 `NDL_PASSWORD`。
- 环境变量指定文件：`NDL_CREDENTIALS_FILE` 指向本机私有凭据文件。
- 本地忽略目录：`secrets/ndl_credentials.txt` 或 `secret/ndl_credentials.txt`，格式为 `username=...` 和 `password=...`。

`secrets/` 与 `secret/` 均已列入 `.gitignore`，运行材料、下载文件、OCR 输出和报告继续放在被忽略的 `output/` 等目录中。

## 进度事件与前端可视化预留

长流程脚本现在支持 JSONL 进度事件，方便 CLI 观察，也方便后续前端接入进度条、当前阶段、心跳状态和候选详情。

- `scripts/resume_historical_citation_verifier.py --progress-json --progress-interval 30`
- `scripts/review_historical_citation_checkpoint.py --progress-json --progress-interval 30`

事件包括 `resume_started`、`candidate_started`、`source_search_started`、`page_mapping_started`、`download_ocr_alignment_started`、`candidate_finished`、`llm_review_started`、`candidate_review_started`、`candidate_review_finished` 和周期性 `progress_heartbeat`。前端可直接按 `event`、`phase`、`current`、`total`、`candidate_id`、`footnote_id`、`title` 渲染状态。

## 可配置证据线索表

日中异写但同义的证据线索已从硬编码逻辑拆出，默认配置位于 `modules/historical_citation/evidence_cues.default.json`。如需针对其它史料主题或其它线上平台调整术语，可设置：

```powershell
$env:HISTORICAL_CITATION_CUE_CONFIG='C:\path\to\cue_config.json'
```

配置格式为：

```json
{
  "cue_groups": [
    ["華族令", "华族令"],
    ["会館", "會館", "会馆"]
  ]
}
```

每组表示一组可互认的主题线索。模块会在 OCR/LLM 精核阶段把它作为辅助证据，尤其用于避免复合中文句被误判为完全无关。

## NDL 页窗 PDF 复用索引

`output_dir` 下会自动维护 `download_range_index.json`，记录形如 `ndl_{pid}_p{start}-p{end}.pdf` 的本地页窗 PDF。批量跑时，如果新的请求页窗被已有 PDF 覆盖，模块会直接复用本地文件，并在报告的“来源候选尝试记录”和“NDL 页窗 PDF 复用索引”中显示。

报告还会单列 `remote_copy_only_no_print` 等“可检索但当前不可下载”来源，避免把 NDL 权限限制误解为模块漏检。

## NDL 全文命中上下文探测

`ndl_fulltext_context.py` 用于处理 NDL Digital Collection 的全文命中片段。它把证据分成两层：

- 目标 PID 内 `SNIPPET` 命中：可标记 PDF 页码和 `cid`，适合作为不可下载或暂不 OCR 条目的弱上下文证据。
- 全站全文候选：只能作为搜索线索；若 PID 与目标书不同，不能替代目标书内证据。

对只有片段、没有 `CONTENT` 内容接口的受限条目，可用 SNIPPET 接龙扩展上下文窗口。该窗口由同一 PID、同一 `cid` 或 PDF 页内的边缘词反复检索拼接而成，报告中标记为 `snippet_expanded`，不等同于完整 OCR 段落。示例：

```powershell
py -3.11 scripts\probe_ndl_fulltext_context.py `
  --pid 2983729 `
  --keyword 国体訓蒙 `
  --keyword 國體訓蒙 `
  --expand `
  --context-keyword "上一段候选=教育の維新は" `
  --context-keyword "下一段候选=既に見てきたように" `
  --output output\ndl_fulltext_context_probe.md
```

后续接入其它平台时，可复用这一证据分级：平台内确证命中优先，全站松散命中仅作线索，片段接龙必须保留页码、命中词和证据等级。

## OCR 与 NDL 全文命中交叉验证

`cross_validation.py` 将已下载/OCR 的 checkpoint 候选与 NDL 全文片段进行交叉验证。它不会替代 OCR，而是检查：

- 目标 PID 的全文命中 PDF 页是否落在已下载页窗内。
- OCR 命中片段与 NDL SNIPPET 接龙上下文是否有可见文本重合。
- 下载失败候选是否至少可获得 `fulltext_only_hit` 弱证据。

CLI 示例：

```powershell
py -3.11 scripts\cross_validate_ndl_fulltext_ocr.py `
  --cases output\run\cross_validation_cases.json `
  --output output\run\cross_validation_report.md `
  --json-output output\run\cross_validation_report.json
```

`cases` 文件应放在 `output/` 或其它被忽略目录中，避免把论文题名、候选 ID 组合、OCR 证据和私有运行路径提交到 Git。
