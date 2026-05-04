# history-citation 模块开发报告

日期：2026-04-28

## 1. 开发目标

`history-citation` 模块的目标，是为 Word 论文中的历史学注释建立一条可复用的核验流程：从 `.docx` 中抽取正文、脚注和引用单位，解析脚注中的日文史料题名、作者、页码和平台线索，优先在 NDL 等线上资源中定位原始史料，再通过下载、截图、OCR、全文命中、段落对齐和大模型复核，产出中文论文侧文本与日文原始史料之间的证据对照。

当前阶段重点面向 NDL Digital Collection，尤其是近现代日文史料、受限下载史料、可全文检索但不可直接下载的史料，以及“析出文献”场景。模块必须同时满足两个约束：

- 私密性：论文原文、下载史料、OCR 文本、账号密码、checkpoint 和报告不得进入 GitHub。
- 可扩展性：NDL 逻辑不能写死在主流程里，后续要能接入 J-STAGE、CiNii、JACAR、国会会议录、法令数据等公开平台。

## 2. 开发过程

### 2.1 初始 Word 论文解析与脚注抽取

早期工作集中在 `.docx` 解析、正文段落抽取、脚注 XML 解析和引用候选生成。模块将正文段落、脚注 ID、脚注文本、脚注页码、引文或脚注前句子组织为 `CitationCandidate`，并保留段落索引、脚注上下文和候选状态。

随后增加了“脚注到句子/段落”的映射逻辑。原因是历史学论文常常不是每个引文后立即加脚注，而是在一段末尾统一注释。因此模块从“脚注前最近一句”扩展到“脚注所在段落中的 citation unit”，并标记 `citation_unit` 类型、置信度和来源说明。

### 2.2 NDL 检索与候选筛选

模块最初通过 NDL Search / SRU / 既有下载模块搜索题名。后来发现单纯题名匹配容易误选：

- 作者题名存在旧字、新字、中文转写差异。
- NDL 搜索结果会返回期刊、评论、广告页、相关书目。
- 有些脚注题名并不是可下载书名，而是宿主书中的章节、演说、论文。

因此后续引入 `source_platforms.py`，将 NDL、Japan Search、Internet Archive 等检索封装为平台适配器。NDL 适配器中加入元数据相似度评分、候选去重、明显误配过滤、可下载 PID 优先、候选尝试记录和报告可视化。

### 2.3 受限下载与浏览器操作层

NDL 受限下载流程遇到多个实际问题：

- 登录后页面偶尔不显示下载能力，需要刷新或重新登录。
- 点击“印刷用ファイルを開く”后，下载链接会出现在页面顶部，必须回到上方查找。
- 下载链接可能不是可见按钮，而是预签名 URL 或隐藏在 HTML 中。
- 部分来源为 `remote_copy_only_no_print`，可检索但不可当前下载。

解决方式是增强 `ndl-search/browser_client.py` 和工作流下载器：登录失败后刷新恢复、点击后回到页面顶部、扫描 `<a href>` 与 HTML 中的预签名链接、记录失败类型、生成不可下载清单，并在报告中将平台权限问题与模块漏检区分开。

### 2.4 页码映射、双开页与 OCR

NDL 的 PDF 页码与史料原书页码经常不一致，且许多扫描件是左右双开页。早期直接按脚注页码下载导致大量 OCR 文本与论文引文不匹配。后来建立了页码映射流程：

- 先下载或 OCR 前部目录/正文起始页。
- 识别可见原书页码与 NDL 扫描页之间的偏移。
- 对双开页进行左右页切分。
- 对多栏、多框、田字型版面进行更细的版面处理。
- 对脚注页码使用前后页窗，保留上下文。

OCR 层优先使用 `ndlocr`，因为它对当前日文近代史料效果明显优于通用 OCR。对古典影印或近世材料，则保留 `ndlkotenocr` 作为可切换后端。

### 2.5 段落对齐与大模型精核

早期启发式对齐能找到粗略片段，但面对复合中文句、脚注段落化、OCR 噪声和跨页材料时容易误判。后续加入：

- 日中证据线索表 `evidence_cues.default.json`。
- 可配置证据线索。
- `page_span` 分类，区分单页、连续多页、多页分隔式注释。
- 对多页分隔式脚注按 claim 分解，每个 claim 对应局部页窗。
- 大模型 review 环节，判断 OCR 片段是否真正支撑论文侧句子或引文。
- 本地 Ollama 模型评估，包括较小模型与 Qwen 系模型作为对照。

开发中发现本地小模型容易把主题相近误判为不支持，也可能忽视复合句中的局部对应关系。因此报告中保留 LLM 判定、置信度和理由，但不让它覆盖底层证据。

### 2.6 析出文献查询

一个关键问题是“脚注题名并非宿主书名”。例如某些演说、论文或章节在 NDL 中作为全文命中对象出现，但实际可下载的是宿主书。为此新增 `contained_sources.py`：

- `contained_title` 记录脚注中被引用的析出文献题名。
- `host_title` 记录实际应检索、下载或定位的宿主书名。
- `source_relation` 标记 `contained_in_host`。
- 默认只保留少量公开、可复用映射。
- 项目私有映射通过 `HISTORICAL_CITATION_CONTAINED_SOURCE_CONFIG` 或被忽略的本地配置提供。

NDL 检索顺序随之调整：下载/馆藏发现优先宿主书；全文命中可优先析出文献题名；报告同时显示二者，避免把“搜不到析出文献”误判为史料不存在。

### 2.7 NDL 全文命中与片段接龙

进一步研究 NDL Digital Collection 前端后，确认其全文能力至少分为两层：

- `item/search`：全站全文检索，可返回相关 PID。
- `fulltext/search` 的 `SNIPPET` 模式：可在目标 PID 内返回片段、`cid`、内容索引和 PDF 页码。
- `CONTENT` 模式：仅部分公开条目可用，受限条目常常返回空。

因此新增 `ndl_fulltext_context.py`：

- 在目标 PID 内搜索关键词变体。
- 区分 `direct_hit`、`no_direct_hit`、全站候选 `same_pid` / `different_pid`。
- 将 `cid/index` 映射为 PDF 页码。
- 对不能下载或暂不 OCR 的条目生成弱证据。
- 用同一 PID、同一 `cid` / PDF 页的片段边缘词进行 SNIPPET 接龙，扩展上下文窗口。

此处特别处理了一个编码陷阱：PowerShell 直接传日文参数时可能变成 `????`。后续真实探测应优先使用 JSON 配置、文件输入或 Unicode escape。

### 2.8 OCR 与全文命中交叉验证

最新阶段将全文命中用于交叉验证，而不是替代 OCR。新增 `cross_validation.py` 和 `scripts/cross_validate_ndl_fulltext_ocr.py`：

- 对可下载/OCR样本，检查 NDL 全文命中 PDF 页是否落在已下载页窗内。
- 计算 OCR 片段与全文片段的规范化相似度。
- 对不可下载但可全文命中的样本，输出 `fulltext_only_hit`，并说明这是弱证据。
- 报告中明确显示 PID、PDF 页、`cid`、查询词、OCR 片段、全文片段、页码检查和结论。

此功能已经被抽为模块 API，可由 CLI、runner、前端或 skill 调用。

## 3. 开发中遇到的问题与解决方式

| 问题 | 表现 | 解决方式 |
| --- | --- | --- |
| 脚注与引文不是一对一紧邻 | 同一中文译文被配到多个日文片段 | 建立 `citation_unit`，支持最近句、整段、复合句和段末注释 |
| NDL 页码不等于原书页码 | 严格下载脚注页码却不匹配 | 增加目录/前页 OCR、可见页码映射、页窗扩展 |
| 双开页和多框版面 | OCR 混入左右页或田字版面 | 增加左右切分、多面板提取、页窗上下文 |
| 受限下载不稳定 | 登录后无下载按钮，下载链接在顶部 | 增强浏览器恢复、刷新登录、顶部链接扫描、隐藏链接扫描 |
| 候选过多且误配 | NDL 返回广告、评论、相关文献 | 元数据评分、可下载 PID 优先、source trial 记录 |
| 析出文献不可直接下载 | 题名搜不到可下载 PID | 加 `host_title` / `contained_title`，宿主书下载、析出题名全文命中 |
| 大模型误判 | 主题相近或复合句被判不支持 | LLM review 只作辅助，保留证据线索、置信度和人工核验状态 |
| 全文接口能力不一致 | SNIPPET 有结果，CONTENT 无结果 | 将 SNIPPET 定义为弱证据，CONTENT 不作为必要前提 |
| 全站全文检索松散匹配 | 多关键词 OR 式命中污染结果 | 目标 PID 内 direct hit 优先，全站候选标明 same/different PID |
| 编码问题 | 日文查询词变成 `????` | 使用 JSON/UTF-8 文件或 Unicode escape，不信任问号结果 |
| 隐私风险 | 论文、账号、OCR 可能误入 Git | `output/`、`secrets/`、私有配置忽略，安全检查脚本兜底 |

## 4. 当前最终呈现方式

### 4.1 模块入口

- `modules.historical_citation_verifier.HistoricalCitationVerifier`
- `modules.historical_citation.source_platforms`
- `modules.historical_citation.contained_sources`
- `modules.historical_citation.ndl_fulltext_context`
- `modules.historical_citation.cross_validation`
- `modules.historical_citation.reporting`

### 4.2 CLI 入口

- `scripts/resume_historical_citation_verifier.py`
- `scripts/review_historical_citation_checkpoint.py`
- `scripts/run_historical_citation_pdf_verifier.py`
- `scripts/run_historical_citation_pdf_fullrun.py`
- `scripts/refine_historical_citation_pdf_next_stage.py`
- `scripts/probe_historical_citation_source_types.py`
- `scripts/probe_ndl_fulltext_context.py`
- `scripts/cross_validate_ndl_fulltext_ocr.py`
- `scripts/migrate_historical_citation_checkpoint.py`
- `scripts/check_github_upload_safety.py`

### 4.3 报告产物

所有运行产物应输出到 `output/`。当前报告主要包括：

- checkpoint JSON
- partial/full Markdown report
- NDL fulltext probe report
- OCR/fulltext cross-validation report
- LLM review report
- source trial / unavailable source list

整理后的阶段性文档保存在 `docs/`：

- `docs/history-citation-current-results-report-20260504.md`
- `docs/history-citation-fullrun-optimization-plan-20260430.md`

### 4.4 Skill 产物

新增小模型可用 skill：

- `docs/agent_skills/historical-citation-runner/SKILL.md`
- `docs/agent_skills/historical-citation-runner/references/workflow.md`

该 skill 约束小模型按固定命令工作，避免自由改源码或泄露私有文本。

## 5. 下一步改进方向

1. 将全文命中交叉验证嵌入 resume runner 的候选结束阶段，使每个已 OCR 候选自动记录 `cross_validation_status`。
2. 为 `fulltext_only_hit` 增加页码映射推断：用目录、可见页码或上下文页窗估计脚注页码与 NDL PDF 页码关系。
3. 增加 NDL fulltext 查询词自动生成器，从中文引文、脚注题名、OCR 命中、证据线索中提取日文候选词。
4. 扩展析出文献 schema，统一到平台无关的 `contained_work` / `host_item` / `trial` 模型。
5. 将 `source_unavailable_attempts` 与 `source_attempts` 合并为平台无关 source trial schema。
6. 加入前端进度可视化：搜索、下载、页码映射、OCR、LLM review、全文命中、交叉验证各阶段独立显示。
7. 扩展 J-STAGE、CiNii、JACAR、国会会议录、法令数据等平台适配器，并复用同一证据等级模型。
8. 建立本地小模型评估基线，区分“可用于摘要/流程执行”的模型与“可用于证据判断”的模型。
9. 对安全检查脚本提示的既有 tracked 高风险配置文件进行单独清理或迁移。
10. 在报告中加入证据等级图例，让人工核验者快速区分 OCR 证据、全文弱证据、候选线索和不可判断状态。

## 6. PDF 输入扩展边界

PDF 扩展只新增输入解析和最小 CLI 入口，不另建独立报告体系。PDF 论文解析后必须复用既有 Word 路径的候选、下载/OCR、NDL 全文、LLM 精核和 `partial_resume_report.md` 信息层级。

输出要求：

- 正式 Markdown 报告统一采用 Word 成功范例的结构：总览、状态细分、不可下载清单、快速索引、逐条脚注详情、候选来源、OCR/全文/LLM 证据。
- NDL Digital Collection (`dl.ndl.go.jp`) 是全文命中和下载判断的主入口；`ndlsearch.ndl.go.jp` 只作为补充元数据桥接。
- `remote_copy_only_no_print`、`download_failed`、`source_unavailable`、`page_mapping_unavailable` 等不可下载状态必须继续尝试目标 PID 的 NDL fulltext SNIPPET。成功时标为 `fulltext_only_hit`，并在报告中显示 PID、PDF 页、`cid`、查询词、SNIPPET 和接龙上下文。
- 正式 LLM 精核固定使用 Ollama `gemma4:e4b`；Qwen 系模型只能作为对照测试，不得作为正式证据判断模型。
