# History Citation PDF 全量流程优化方案

日期：2026-04-30

适用模块：history citation / historical citation verifier

适用阶段：两篇 PDF 论文全量运行后的下一轮优化准备

## 1. 目标

本文件用于汇总本轮 PDF 全量流程暴露的问题，并在进入下一轮代码优化前，先按“人工 NDL 检索”的思路，对两篇论文中不同限制类型的史料进行引文--注释匹配尝试。最终目标是把人工可判断、但当前自动流程不稳定的部分，转化为可实现的 resolver、缓存、报告结构和全量 runner 规则。

这里的标准仍以此前 Word 成功范例为基准：

- 报告结构统一使用 Word 成功范例的正式层级。
- NDL Digital Collection 是全文命中、下载判断和 PID 内 snippet 的主入口。
- ndlsearch 只作为补充元数据桥，不作为下载和全文命中的最终证据。
- 不可下载材料不能直接停在未核查；只要有 PID，就应进入 PID 内全文 snippet 和上下文扩展。
- LLM 精核正式流程固定使用 Gemma 系列策略，并记录 provider、model、policy 和 formal review 状态。

## 2. 本轮全量流程暴露的问题

### 2.1 首轮全量检索耗时过长

两篇论文并行首轮都超过 20 分钟。虽然 partial / resume 机制最终能够恢复，但这说明当前 NDL 检索、全文探测、浏览器 fallback、下载和 OCR 的组合仍偏慢。

优化方向：

- 增加统一 batch runner。
- 自动分段运行，不再依赖人工判断 offset。
- 自动发现 partial 是否完整。
- 自动合并 partial 与最终结果。
- 自动对 timeout、download_failed、page_mapping_unavailable 等状态进行分层续跑。

### 2.2 partial 与最终结果边界不够清晰

宗教论文首轮进程退出时没有写出最终 `verification_results.json`，但 partial 实际已经包含完整结果。中途还出现过重复合并风险。

优化方向：

- 增加 finalizer。
- 任意中断后，自动检查 partial 是否已经覆盖全部候选。
- 合并时强制按 `candidate_id + footnote_id + paragraph_index` 去重。
- 若 partial 完整但 final 缺失，应自动生成 canonical final JSON 和报告。

### 2.3 timeout 不是单一失败类型

retry 后，外交论文 timeout 清零；宗教论文从 7 个 timeout 降到 1 个。这说明许多 timeout 不是内容无法验证，而是下载、OCR、网络或页映射阶段临时过慢。

优化方向：

- 把 retry 写入正式流程。
- 首轮下载 / OCR 超时建议 600 秒。
- 仅对 timeout 条目进行 900 秒重试。
- 报告中同时显示“初次状态”和“retry 后当前状态”。
- timeout 事件保留为处理历史，不应覆盖当前最终状态。

### 2.4 页映射是外交论文最大瓶颈

外交论文最终仍有大量 `page_mapping_unavailable`，集中在《日本外交文書》《原敬日記》《山縣有朋意見書》。

优化方向：

- 下载前先用 PID 内全文 snippet 定位页。
- 对连续卷册建立“印刷页码 -> scan/pdf 页码”缓存。
- 对 `日本外交文書`、`原敬日記`、资料集析出文献建立专门 resolver。

### 2.5 报告中“历史事件”和“当前状态”容易混淆

retry 后部分条目已转为 `needs_manual_review` 或 `page_mapping_unavailable`，但 `timeout_events` 仍保留历史 timeout。读者容易误以为这些 timeout 仍然没有处理。

优化方向：

- 报告中拆分“当前状态”和“处理历史”。
- 当前状态只显示最终判断。
- 处理历史显示首次 timeout、retry、候选轮换、LLM 精核等过程。

### 2.6 候选重复仍然存在

宗教论文中部分页段出现重复候选，同一脚注可能被不同段落或分页重复带入。

优化方向：

- PDF parser 输出阶段先去重。
- next-stage 再做二次去重。
- 去重 key 应包括 `paper_id + candidate_id + footnote_id + paragraph_index + normalized_quote + normalized_source_title`。

## 3. 不调用工作区工具的人工模拟匹配尝试

本节不依赖工作区文件读取，不调用模块代码，也不重新读取两篇 PDF 或已有 JSON。它只基于本轮全量运行已暴露的条目类型、报告状态和人工 NDL 检索的一般机制进行模拟。目的不是替代真实全量运行，而是提炼自动流程应当模仿的人工判断顺序。

### 3.1 人工匹配的通用顺序

人工检索时，不会先按“标题相似度”决定结果，而是按以下顺序逐层收窄：

1. 判断脚注来源类型：独立书、合集、合集中的析出文献、日记、外交文书卷册、报刊、法令解释书、现代研究。
2. 解析 host title、contained title、卷册号、年份、出版者、页码、日期、人名、事件关键词。
3. 先找 host 或系列卷册的正确 PID。
4. 对不可下载材料，在目标 PID 内做全文 snippet 检索。
5. 对可下载材料，先用 snippet 或目录定位页，再下载小页窗 OCR。
6. 对日记类材料，以日期、人名、事件作为主定位线索，而不是只用书名和页码。
7. 对现代研究，优先核对书目信息、页码和论点承接，不强行要求史料式全文命中。
8. 最后才让 Gemma 判断论文句子是否被候选上下文支持。

### 3.2 宗教论文：三类限制材料模拟

#### 3.2.1 不可下载合集：日本近代思想大系 5：宗教と国家

限制类型：

- source collection / host volume。
- 可能不可下载或下载受限。
- 但可通过 PID 内全文 snippet 命中 contained title、关键词和上下文。

人工尝试：

1. 先把《日本近代思想大系 5：宗教と国家》识别为 host。
2. 不把其中的文章、谈话、建白、史料标题当成独立图书进行全站搜索。
3. 先进入 host PID。
4. 在 host PID 内检索 contained title。
5. 若 contained title 难命中，则使用正文关键词、人名、制度名、年份组合检索。
6. 命中 snippet 后，扩展上下文判断是否与论文句子有关。

遇到的问题：

- 如果只搜索 contained title，NDL 可能返回另一个相似标题或泛化上下文。
- 如果只搜索 host title，会停留在目录或题名层，无法确认具体引文。
- 如果全站全文检索命中其他 PID，报告会给出看似相关但实际卷册错误的证据。

自行解决的人工策略：

- 固定 host PID 后，只在该 PID 内检索。
- contained title 命中优先级高于 host title 命中。
- 若 contained title 不稳定，则使用 2 至 4 个限定词组合，例如人名 + 制度名 + 事件词。
- 把这类结果标成 `fulltext_only_direct_support`、`fulltext_only_partial_support` 或 `fulltext_lead_only`，不能直接归为未核查。

机制启示：

- 需要 source graph。
- `日本近代思想大系 5：宗教と国家` 应作为固定 host 节点。
- contained title 应作为子节点。
- 子节点只在 host PID 内做 snippet-first 检索。

#### 3.2.2 可下载法令解释书：帝国憲法義解・皇室典範義解

限制类型：

- NDL Digital 可发现可下载版本。
- 需要题名变体检索。
- 一旦确认 PID，应复用下载、OCR 和页映射缓存。

人工尝试：

1. 先列出题名变体：`帝国憲法義解 皇室典範義解`、`帝国憲法義解・皇室典範義解`、`帝國憲法義解`、`皇室典範義解`。
2. 优先寻找 NDL Digital Collection 中可下载 PID。
3. 若找到 PID 1272168 这类可下载版本，进入下载 / 页映射 / OCR 路径。
4. 若脚注页码指向同一书或相邻页，应复用已建立的页偏移。
5. OCR 后再交给 Gemma 判断论文句子是否得到支持。

遇到的问题：

- 标题中点、空格、合刻题名、新旧字体会导致搜索结果排序不稳定。
- 若每条脚注都从零开始下载和页映射，会浪费大量时间。
- 页码映射失败时，系统可能错误停在 `source_found` 或 `download_timeout`。

自行解决的人工策略：

- 先确认 PID，再复用。
- 可下载 PID 的优先级高于 ndlsearch 元数据页。
- 一旦 PID 和页偏移可信，后续同源条目直接使用缓存。

机制启示：

- 增加 source-level cache。
- 缓存内容至少包括 PID、可下载性、OCR 文件、页偏移、已验证页窗、相关脚注列表。
- 相同 PID + 相近页码不应重复执行完整下载流程。

#### 3.2.3 语义歧义史料：大麻 / 神宮大麻相关材料

限制类型：

- 关键词在现代语义中高度歧义。
- 真实语境是神宮大麻、御札、神社行政或流言，而不是现代通用词义。
- 需要限定词组合才能得到正确上下文。

人工尝试：

1. 先从论文语境判断“大麻”属于神宮大麻或御札。
2. 不单独搜索“大麻”。
3. 使用组合词：`神宮大麻`、`皇大神宮`、`神田神社`、`窪田次郎`、`配布`、`流言`、`御札`。
4. 若目标是地方事件，则加地名或机构名。
5. 对 snippet 命中结果检查前后文，确认是否是宗教行政、神道政策或国家祭祀语境。

遇到的问题：

- 单词“大麻”会导致完全错误的语义空间。
- 若 OCR 文本旧字、异体字、片假名混用，单一关键词很容易漏检。
- 报告中 `fulltext_only_not_supported` 可能来自错误上下文，而不是论文句子本身错误。

自行解决的人工策略：

- 把“大麻”归入 special term bucket。
- 自动扩展时必须与神社、皇大神宮、御札、配布等限定词绑定。
- 对包含歧义词的失败项，Gemma 判 `not_supported` 后应自动换一组限定词和候选上下文。

机制启示：

- 增加历史语义词表。
- 增加“歧义词不得单独检索”的规则。
- 报告中应显示触发的 special term bucket。

### 3.3 外交论文：三类限制材料模拟

#### 3.3.1 系列外交文书：日本外交文書

限制类型：

- source collection / volume series。
- 多卷、多年、多册。
- 许多材料可能不可下载或只可 snippet。
- 只有命中“正确卷册 + 正确文书标题 / 日期 / 页码附近”才有证据意义。

人工尝试：

1. 先解析脚注中的卷号、年份、册次、页码。
2. 建立卷册候选，而不是只搜索《日本外交文書》。
3. 在正确卷册 PID 内检索文书题名、人名、日期、政策词。
4. 对门户开放相关条目，组合 `ヘイ`、`米國照會`、`門戸開放`、`機會均等`、`帝國政府回答` 等历史日文词。
5. 若只命中《日本外交文書》书名或目录，不作为支持证据，只作为 lead。

遇到的问题：

- 只搜索系列名会得到大量题名层、目录层、错误卷册结果。
- 人名 John Hay 在日文文书中可能表现为 `ヘイ`、`ヘー`、`米國務卿`、`國務長官` 等，不一定直接出现英文名。
- “门户开放”也可能以 `門戸開放`、`商業上機會均等`、`支那ニ於ケル...` 等长标题出现。

自行解决的人工策略：

- 系列名永远不是最终证据。
- 必须进入卷册 PID。
- 文书题名级查询优先于一般关键词。
- 若无法确认卷册，只能标为 `fulltext_lead_only` 或 `page_mapping_unavailable`。

机制启示：

- 必须建立《日本外交文書》专门 resolver。
- resolver 应包含卷号、年份、册次、PID、可下载性、全文可检性和常见文书题名变体。
- Gemma 判 `not_supported` 时，应先尝试同卷册内其他上下文，而不是立刻终结。

#### 3.3.2 日期型日记：原敬日記

限制类型：

- diary / date-indexed source。
- 题名本身不足以定位内容。
- 页码可能因版本不同而不稳定。

人工尝试：

1. 从脚注或正文中抽取年月日。
2. 若脚注没有日期，则从论文段落事件链中找最近日期。
3. 先定位《原敬日記》的正确卷册或年份范围。
4. 在目标 PID 内搜索日期、人名、事件词。
5. 若日期命中，再向前后扩展上下文。

遇到的问题：

- 只用《原敬日記》+ 页码，容易进入错误卷或页映射失败。
- 日记条目中的人名、地名、政策简称可能与论文现代中文表述不一致。
- 版本不同导致印刷页码和 scan 页码偏移较大。

自行解决的人工策略：

- 对日记类材料，日期优先级高于页码。
- 页码只作为二次校验。
- 若日期缺失，报告应明确提示“需要从正文事件链补抽日期”。

机制启示：

- 增加 date-aware resolver。
- parser 应从正文和脚注共同抽取日期。
- 报告失败项中应显示建议检索日期和事件词。

#### 3.3.3 析出意见书：山縣有朋意見書

限制类型：

- contained document。
- 可能不是独立 NDL 图书。
- 需要先找到 host collection 或文书集。

人工尝试：

1. 不把《山縣有朋意見書》直接当成独立书。
2. 先搜索题名 + 人名 + 年份 / 事件。
3. 如果出现资料集、文書集、全集、传记资料集，则进入 host。
4. 在 host 内搜索 `山縣有朋`、`意見書`、事件关键词。
5. 若只找到题名或目录，标为 lead。
6. 若能进入正文 snippet 并扩展上下文，再做 LLM 精核。

遇到的问题：

- 独立题名路径容易找不到或找到二手引用。
- host title 不明确时，候选排序极不稳定。
- 如果先下载错误 PID，会浪费大量 OCR 时间。

自行解决的人工策略：

- contained-title search 要先找 host。
- 题名命中后必须追问“它收在哪个 host 中”。
- 报告应保留 host 候选列表，不应只显示一个失败源。

机制启示：

- 增加 contained-document resolver。
- 候选结构需要同时保留 `host_title` 与 `contained_title`。
- 对 host 未明确的条目，报告应输出人工检索路径，而不是只输出失败状态。

新增校正（2026-05-01）：

- NDL Digital Collection `item/search` 可直接检到《山県有朋意見書》PID `3025431`（原書房，1966）。
- 因此 resolver 不能把所有“意見書”一律固定为 host-contained 路径；应先检查配置中的已知单独 PID，若存在则走 `known_document_pid_then_host_fallback`，没有单独 PID 时再进入 host discovery。

## 4. 人工机制与当前全量流程的差距

### 4.1 当前流程仍偏“单条候选驱动”

当前流程基本能做到：抽脚注、找源、下载 / snippet、OCR、Gemma 精核。但它对 source family 的理解仍不足，容易把每条脚注当成一个独立检索任务。

人工流程则是 source graph 驱动：

- 先确认 source family。
- 再确认 host / volume / year / PID。
- 最后处理 contained title、页码和引文支持。

需要改进：

- 引入 source graph。
- 把同一 host / PID / 卷册下的多个脚注合并处理。
- source-level 处理结果向 candidate-level 复用。

### 4.2 当前流程对“不可下载但可全文命中”的处理已经改善，但证据分级仍需更细

当前流程已能产生 `fulltext_only_direct_support`、`fulltext_only_partial_support`、`fulltext_only_not_supported`、`fulltext_lead_only` 等状态。

仍需改进：

- `fulltext_lead_only` 要明确说明是命中书名、目录、错误卷册还是泛关键词。
- `not_supported` 前应进行候选轮换。
- 对歧义词和跨语种人名，不能只做一次 query。

### 4.3 当前流程对“卷册型”和“日期型”来源支持不足

《日本外交文書》和《原敬日記》的问题说明，页码映射不应是第一定位手段。

需要改进：

- 卷册型：卷号 / 年份 / 册次 / PID 优先。
- 日期型：日期 / 人名 / 事件优先。
- 页码作为验证信号，而不是唯一入口。

### 4.4 当前流程报告已经可读，但仍缺少“下一步人工路径”

报告目前能显示状态、证据、LLM 结论和部分候选来源，但失败项对读者来说仍不够行动化。

需要改进：

- 每条失败项增加 `manual_search_recipe`。
- 明确建议下一步搜什么、在哪个 PID 内搜、为什么当前证据不足。
- 对 source collection 显示 host / contained / volume / PID 层级。

## 5. 进一步完善后的优化方案

### 5.1 Source Graph

新增 source graph 层，统一表达以下关系：

- `source_family`：如 `日本近代思想大系`、`日本外交文書`、`原敬日記`。
- `host_title`：合集、系列、卷册题名。
- `contained_title`：析出文章、文书、谈话、建白、意见书。
- `volume`：卷号、册次、年份范围。
- `pid`：NDL Digital PID。
- `availability`：downloadable、fulltext-only、metadata-only、unknown。
- `evidence_route`：download_ocr、pid_snippet、metadata_bridge、manual_only。

实现要求：

- parser 输出中保留 host / contained / volume / year。
- next-stage 先聚合 source graph，再处理 candidate。
- 同一 source node 的 PID、可下载性、页映射、OCR 缓存可复用。

### 5.2 专门 Resolver

优先开发三个 resolver：

1. `NihonKindaiShisoTaikeiResolver`
   - 处理《日本近代思想大系 5：宗教と国家》。
   - host PID 固定后，所有 contained title 只在 host PID 内检索。
   - 不可下载时走 PID snippet + 上下文扩展。

2. `NihonGaikoBunshoResolver`
   - 处理《日本外交文書》。
   - 建立卷册 PID 映射表。
   - 支持卷号、年份、册次、文书题名、日期、人名和外交政策词组合。

3. `DiaryDateResolver`
   - 处理《原敬日記》等日记来源。
   - 从脚注和正文共同抽取日期。
   - 日期优先，页码其次。

后续可追加：

- `ContainedDocumentResolver`：处理《山縣有朋意見書》等析出文献。
- `SecondaryScholarshipResolver`：处理现代研究，只核对书目信息、页码和论点承接。
- `SpecialTermResolver`：处理“大麻”等历史语义歧义词。

### 5.3 Query 策略

增加 query bucket：

- `title_bucket`：题名、题名变体、新旧字体。
- `host_bucket`：host title、系列名、卷册名。
- `contained_bucket`：析出题名、文书题名、谈话题名。
- `date_bucket`：年月日、事件日期。
- `person_bucket`：人名中日英变体。
- `policy_bucket`：制度、政策、外交概念。
- `special_term_bucket`：大麻、神宮大麻、御札等需限定语境的词。

规则：

- source collection 不允许只用 host title 作为最终支持证据。
- special term 不允许单独检索。
- date bucket 不允许以“2001年”“明治32年”这类年份单独触发全局全文检索；年份只能和 host/title/contained/policy/person 组合使用。
- contained title 的 PID 内全文检索优先级高于 host + contained 组合；组合查询只能作为第二层收窄手段，不能抢占析出题名本身的首轮检索。
- 跨语种人名必须至少生成日文片假名、汉字职衔和英文原名三类变体。
- `not_supported` 后应自动尝试下一组 bucket，而不是直接终止。

新增问题记录（2026-04-30 优化实现中发现）：

- source graph 接入 NDL 全文 fallback 后，若 query bucket 没有最小特异性约束，泛化年份会触发真实 NDL Digital 全文检索并返回大量无关 PID。
- source collection 场景下，host + contained 组合虽然有助于收窄，但旧有回归要求仍应保持 contained title 首先被检索；否则会降低不可下载合集材料的 snippet 命中稳定性。
- resolver 配置表如果在缺少卷册、年份或日期锚点时直接返回全部 PID，会把“卷册映射”退化为泛化候选池，尤其会伤害《日本外交文書》和《原敬日記》这类连续卷册来源。
- 已采取的实现约束：过滤裸年份全文查询；`contained_title` 在 NDL fulltext fallback 中先于 source graph 组合查询；配置型 PID 映射只有在卷册/年份/日期命中时才启用，除非显式标记为 default。

### 5.4 Snippet-First 页定位

对可下载和不可下载材料都优先 snippet-first：

- 可下载材料：先用 snippet 定位页或附近区间，再下载小页窗 OCR。
- 不可下载材料：snippet 命中后扩展上下文，直接进入 LLM 精核。
- 页码映射失败时，不立即结束；尝试目录、索引、日期和关键词定位。

### 5.5 LLM 精核策略

正式流程：

- 默认模型固定为 Gemma 工作流指定模型。
- 记录 provider、model、policy、formal review allowed。
- qwen 等模型只能作为对照，不进入正式精核结论。

状态转换：

- Gemma `direct_support` -> `fulltext_only_direct_support` 或 `matched`。
- Gemma `partial_support` -> `fulltext_only_partial_support` 或 `needs_manual_review`。
- Gemma `not_supported` -> 先触发候选轮换；轮换结束仍不支持才输出 `fulltext_only_not_supported`。

### 5.6 报告结构

统一使用 Word 成功范例结构：

- 总览。
- 状态细分。
- 不可下载清单。
- 快速索引。
- 逐条脚注详情。
- 候选来源。
- OCR / 全文 / LLM 证据。

新增报告字段：

- `current_status`：当前最终状态。
- `processing_history`：timeout、retry、候选轮换、下载尝试、OCR 尝试。
- `source_graph`：host / contained / volume / PID。
- `manual_search_recipe`：失败项下一步人工检索建议。
- `evidence_level`：download_ocr_strong、fulltext_snippet_weak、metadata_lead、unsupported。

### 5.7 全量 Runner

新增正式 runner：

- 自动分批运行。
- 自动 partial finalizer。
- 自动 retry timeout。
- 自动去重。
- 自动合并 next-stage。
- 自动生成报告包。

新增问题记录（2026-04-30 runner 实现中发现）：

- next-stage 的 `--restricted-download` 必须继承用户显式参数，不能在 runner 内默认强制打开；否则可下载材料也会被迫走受限下载路径，放大耗时和失败概率。
- 已采取的实现约束：base batch 和 next-stage 都只在用户传入 `--restricted-download` 时追加该参数，并补回归测试。

建议阶段：

1. `base_collect`：PDF 解析、脚注结构化、初始 NDL 检索。
2. `source_graph_build`：聚合 host / contained / volume / PID。
3. `evidence_collect`：snippet-first、download、OCR、页映射。
4. `llm_review`：Gemma 精核。
5. `retry`：仅处理 timeout 和可恢复失败。
6. `finalize`：去重、状态归并、报告输出。

## 6. 优先开发任务

P0：

- partial finalizer。
- 去重 key。
- 报告中拆分当前状态和处理历史。
- retry 写入正式 runner。

P1：

- source graph 数据结构。
- 《日本近代思想大系 5：宗教と国家》 resolver。
- 《日本外交文書》卷册 PID 映射 resolver。
- snippet-first 页定位。

P2：

- 《原敬日記》日期型 resolver。
- contained document resolver。
- special term bucket。
- `not_supported` 后候选轮换。

P3：

- secondary scholarship verification mode。
- 报告中的人工检索路径生成。
- 全流程报告包自动发送集成。

## 7. 回归测试建议

宗教论文：

- 《日本近代思想大系 5：宗教と国家》：不可下载，但应能通过 host PID 内 snippet 得到上下文。
- 《帝国憲法義解・皇室典範義解》：应命中可下载 PID，复用 OCR 和页映射。
- 大麻相关材料：不得单独用“大麻”检索，必须触发 special term bucket。

外交论文：

- 《日本外交文書》：不得只以系列名作为支持证据；必须进入卷册 PID 或标为 lead。
- John Hay / 门户开放条目：必须生成文书题名级日文 query。
- 《原敬日記》：必须尝试日期型解析。
- 《山縣有朋意見書》：必须走 contained document 路径。

报告：

- 输出结构必须接近 Word 成功范例。
- 每条失败项应显示人工检索建议路径。
- timeout 历史不应覆盖当前状态。

## 8. 下一轮验收标准

- 两篇 PDF 全量流程无需人工 offset 干预即可完成。
- partial 完整时能自动 finalize。
- retry 后 timeout 状态明确归档。
- 《日本外交文書》条目的 `page_mapping_unavailable` 明显下降。
- 《日本近代思想大系 5：宗教と国家》相关条目不再被错误当作独立题名全站泛搜。
- `not_supported` 条目在报告中能说明是否已经进行候选轮换。
- 报告同时服务机器调试和人工复核：既有状态统计，也有逐条人工检索路径。

## 9. 2026-04-30 继续优化实现记录

已完成：

- 增加可复用 `source_resolvers` registry，把《日本外交文書》卷册型、《原敬日記》日期型、《山縣有朋意見書》析出文献型纳入统一 resolver plan。
- resolver plan 输出 `verification_mode`、`pid_scope_strategy`、`source_level_cache_key`、`target_pid_queries`、`global_queries`、`warnings`，并写入候选 artifacts 与报告。
- NDL fulltext fallback 和 PID 内 snippet 探测优先使用 resolver plan 的查询桶，避免只用系列名、书名或裸年份。
- 全量 runner 修正 next-stage 参数继承：`--restricted-download` 只在用户显式开启时传递。
- 新增回归测试覆盖三类史料：`日本外交文書` 卷册 PID 配置映射、`原敬日記` 日期优先策略、`山縣有朋意見書` host discovery 策略。

下一步仍需：

- 补充真实《日本外交文書》《原敬日記》卷册 PID 配置表，而不是只依赖外部配置。
- 将 resolver 的 source-level cache 与 OCR/page-map cache 进一步打通，让同一卷册/同一 PID 的页映射可被后续条目稳定复用。
- 在下一轮小范围运行中观察 resolver warnings 分布，确认哪些失败项是缺 PID 表，哪些是脚注解析仍未抽出日期、卷册或 host。

## 10. 2026-05-01 继续优化实现记录

已完成：

- 新增默认配置 `config/historical_citation_source_resolvers.json`，把官方 NDL Digital Collection 查询确认过的 PID 写入可维护配置。
- 《日本外交文書》第32巻 / 明治32年配置了 `3448126`、`2530174`、`3448128` 三个同卷候选，支持 `第32巻`、`第三十二巻`、`明治32年`、`1899年` 等变体。
- 《原敬日記》配置了福村出版 1965 年版主要卷册 PID；其中 1900 年 / 明治33年会定位到第2卷 `2982135`。
- 《山縣有朋意見書》加入已知单独 PID `3025431`，resolver 改为“已知单独 PID 优先，host discovery 兜底”。
- 配置型 PID 匹配从“完全相等”扩展为“规范化后相等或包含”，避免 `1900年5月12日` 无法命中配置中的 `1900年`。
- 页映射缓存增加 source-level alias：同一 resolver source key 可复用已确认页映射，并在 PID 不一致时明确记录 mismatch，不静默套用。

新增问题记录：

- 默认配置必须避免把“同一系列全卷 PID 表”当成无条件候选池；只有脚注/正文命中卷册、年份、日期或配置 terms 时才返回 PID。
- 页映射是 PID 级事实，但 source-level cache 是文献/卷册级线索；复用时必须校验 alias 中保存的 `ndl_id` 与当前候选 PID 一致。

验证：

- 三类史料窄测试通过：`日本外交文書`、`原敬日記`、`山縣有朋意見書`。
- 完整单测通过：`py -3.11 -X utf8 -m unittest tests.test_historical_citation_verifier`，165 tests OK。

下一步：

- 在小范围真实运行中观察 `source_level_page_mapping_cache_hit`、`source_level_page_mapping_cache_pid_mismatch`、resolver warnings 的分布。
- 如果 `日本外交文書` 仍命中错误同卷 PID，应把配置中的同卷候选加上更细的文书题名、页码区间或册次权重。
- 将 source-level alias 从页映射扩展到下载页窗/OCR 文本摘要缓存，进一步减少同一 PID 的重复 OCR。

## 11. 2026-05-01 Source-Level OCR 缓存实现记录

已完成：

- 新增 `source_level_ocr_cache.json`，以 `source_level_cache_key + ndl_id + ocr_model` 作为复用 key。
- OCR 缓存只在 source key、PID、OCR 模型均一致，且缓存页覆盖本次目标页时命中。
- 缓存命中时记录 `source_level_ocr_cache_hit`，并将命中页写入 candidate artifacts；报告中显示 `Source-level OCR cache: hit`。
- 缓存保存时合并既有页，不覆盖其它页，支持同一卷册后续条目逐步积累 OCR 页文本。
- 若 PID 不一致，记录 `source_level_ocr_cache_pid_mismatch`，不复用缓存。

实现边界：

- 页映射仍是 PID 级事实，OCR 缓存虽然归入 source-level key，但必须绑定同一 `ndl_id`。
- 当前 OCR 缓存复用文本页，不复用 LLM 判定；Gemma 精核仍按当前论文句子重新运行。
- 若同一 PID 的不同版本页窗发生页码偏移，缓存不会直接解决，需要继续依赖页映射和 snippet-first 定位。

验证：

- 新增 source-level OCR cache 回归测试通过。
- 三类史料窄测试继续通过。
- 完整单测通过：`py -3.11 -X utf8 -m unittest tests.test_historical_citation_verifier`，166 tests OK。

下一步：

- 对三类史料做小范围真实运行，观察 `source_level_ocr_cache_hit` 是否减少重复 OCR。
- 若 cache miss 主要来自页不全，应考虑“部分命中 + 缺页补 OCR”的混合策略。
- 若 cache miss 主要来自同卷不同 PID，应在《日本外交文書》配置中增加同卷 PID group 和等价 PID 选择规则。

## 12. 2026-05-01 三类史料真实 Probe 记录

新增工具：

- 新增 `scripts/probe_historical_citation_source_types.py`，围绕三类史料构造最小候选，不依赖两篇 PDF，全程调用 NDL Digital Collection 的 `item/search`、`fulltext/search` 和目标 PID 内 snippet。
- 输出：
  - `source_type_probe_results.json`
  - `source_type_probe_report.md`

本轮真实 probe 输出目录：

- `output/historical_citation_source_type_probe_20260501_final3`

观察结果：

- 《日本外交文書》第32巻 / 门户开放：
  - 全局查询 `日本外交文書 第32巻 門戶開放` 首位命中 `3448128`。
  - 目标 PID 内 `3448128` 对 `門戶開放` 命中 10 条，首条约在 pdf_page 32。
  - `3448126`、`2530174` 也可命中 `門戶開放`，但页位与上下文不同，说明同卷不同 PID / 版本仍需保留 equivalent PID group。
  - 已修正配置排序：门户开放语境下 `3448128` 排到 known PID 首位。

- 《原敬日記》日期型：
  - 配置可将 1900 年 / 明治33年定位到 `2982135`。
  - 但 `原敬日記 1900年5月12日` 全局检索首位仍会命中现代研究，目标 PID 内日期 snippet 也不命中。
  - 结论：日记类不能依赖全文日期命中作为主路径，应使用“日期 -> 卷册 PID -> 页映射/目录/索引 -> OCR”的路径。
  - 已修正：日期裸搜不再进入全局全文检索；等价 PID 组对 diary source 改为 configured PID 严格模式，避免把同题名错误卷或二手研究并入等价组。

- 《山縣有朋意見書》：
  - 全局查询稳定首位命中 `3025431`。
  - PID 内 `山縣有朋意見書` snippet 命中 10 条，首条约在 pdf_page 3。
  - 该条已可作为“已知单独 PID 优先，host discovery 兜底”的正向样本。

新增修正：

- `record_equivalent_pid_group` 会把 resolver 配置中的兄弟 PID 写入等价 PID 组，但 diary source 在已有 configured PID 时只接受 configured PID，不再把同题名错误卷或现代研究并组。
- resolver/config PID 候选排序加入语境词权重，命中 `門戶開放`、`機會均等`、`米國照會` 等词的 PID 排名高于只命中卷册号的 PID。
- resolver 和 source graph 两处都禁止裸日期全局检索；日期只能和题名/host/person/policy 组合，或进入目标 PID 内 snippet。

验证：

- 三类史料 probe 成功生成报告。
- 完整单测通过：`py -3.11 -X utf8 -m unittest tests.test_historical_citation_verifier`，169 tests OK。

下一步：

- 为日记类补充“配置卷册题名 / 年份范围 -> 目标 PID”的更细查询策略，减少 `原敬日記 1900年` 命中错误卷的概率。
- 在真实 PDF next-stage 中记录 probe 同款字段：known PID 排序、equivalent PID group、target PID snippet hit_count。
- 对《日本外交文書》增加文书题名级 fallback：当完整题名 `支那ニ於ケル商業上機會均等及門戸開放` 无命中时，自动降级到 `門戶開放`、`米國照會`、`帝國政府回答` 的组合，而不是判定 source lead。

## 13. 2026-05-01 Claim-Aware Known PID 候选注入记录

本轮新增问题：

- 三类史料 probe 显示，resolver 在带论文句子时已经能把《日本外交文書》第32巻的门户开放语境排序到 `3448128`，但正式 NDL adapter 搜索只接收脚注，不接收论文句子，因此 adapter 候选仍会先排普通卷册 PID `3448126`。
- 这说明“source graph / resolver 已经理解语境”和“正式源检索链路使用语境”之间仍有断点。该问题不应通过报告层修饰解决，而应让 candidate 的 `translation_text` 进入 NDL 候选生成、known PID 排序和 fulltext fallback 查询。

已完成：

- `NDLSourcePlatformAdapter.search` 增加 `claim_text` 参数，并将其传入 `resolve_source`、`build_source_graph_node`、`build_source_query_plan` 和 NDL fulltext fallback。
- resolver 配置中的 known PID 会主动注入 NDL 候选列表，标记为 `search_route=resolver_config_known_pid`、`known_pid_candidate=true`，并记录 resolver、source type、source-level cache key、verification mode 和 `resolver_known_pid_requires_evidence_collection`。
- known PID 候选只代表“应进入该 PID 取证”，不能直接代表引文成立；后续仍需按原流程进入 snippet、下载/OCR、页映射和 Gemma 精核。
- `HistoricalCitationVerifier.verify_docx` 与 `verify_pdf` 调用源搜索时传入 candidate 的 `translation_text`，使论文句子中的人物、政策词、日期和事件词能够参与候选排序。
- `scripts/probe_historical_citation_source_types.py` 新增 `Adapter Candidate Order` 输出，直接显示正式 adapter 中 known PID 与全站检索结果的先后关系。

本轮 probe 输出目录：

- `output/historical_citation_source_type_probe_20260501_claim_aware_adapter`

观察结果：

- 《日本外交文書》第32巻 / 门户开放：adapter 候选第一位已变为 `3448128`，随后是 `3448126`、`2530174`，全站检索返回的《日本外交文書》概要类二手结果被排在 known PID 之后。
- 《原敬日記》日期型：adapter 候选第一位稳定为配置 PID `2982135`，后面才是 NDL SRU 返回的影印本其它卷。目标 PID 内日期 snippet 仍不命中，因此下一步仍需走页映射、目录/索引和 OCR 路径。
- 《山縣有朋意見書》：adapter 候选第一位稳定为已知单独 PID `3025431`，全局与 PID 内 snippet 都能支持该路径。

新增回归测试：

- `test_ndl_adapter_injects_resolver_known_pid_candidates_before_public_results`
- `test_ndl_adapter_uses_claim_text_to_order_configured_volume_pids`

验证：

- 三类史料 claim-aware probe 成功生成报告。
- 完整单测通过：`py -3.11 -X utf8 -m unittest tests.test_historical_citation_verifier`，171 tests OK。

下一步：

- 日记类继续补“日期 -> 卷册 PID -> 页映射/OCR”的正式小页窗路径，降低目标 PID 内日期 snippet 为 0 时的停滞概率。
- 将 `Adapter Candidate Order` 的关键字段纳入真实 PDF next-stage 报告，便于全量运行后直接判断是“候选排序问题”还是“取证/页映射问题”。
- 对《日本外交文書》继续扩展文书题名级 fallback，尤其是完整题名 0 命中时自动降级到 `門戶開放`、`米國照會`、`帝國政府回答` 等组合。

## 14. 2026-05-01 日记类 Known PID 小页窗 fallback 记录

本轮新增问题：

- 《原敬日記》这类日期型史料已经能通过 resolver 将 `1900年5月12日` 定位到卷册 PID `2982135`，但 NDL 目标 PID 内日期 snippet 为 0 时，流程仍可能因为页映射不可得而停在 `page_mapping_unavailable`。
- 这不是候选排序问题，而是“已知卷册 PID 后的取证降级路径”不足。普通 NDL 条目仍必须保留“无页映射不乱下”的保护，但 date-indexed diary source 应允许一个有明确标记的小页窗 OCR 尝试。

已完成：

- 新增 `_known_pid_page_window_fallback_plan`：仅在以下条件同时满足时启用：
  - `source_resolver_plan.source_type == diary`；
  - 当前 NDL match 是 resolver 配置 known PID，或带有 `known_pid_candidate=true`；
  - 脚注存在页码；
  - target-PID snippet 没有提供可用 `pdf_page`，且页映射未推断成功。
- fallback 只下载以脚注页码为中心的小页窗，当前将 `page_window` 上限收紧到 2，避免把诊断路径变成大范围 OCR。
- fallback 写入 `known_pid_page_window_fallback` artifact，记录 `ndl_id`、known PID 列表、引用页码、下载页窗、依据和 `diagnostic_until_ocr_llm_review` 证据等级。
- fallback note 固定为 `diary_known_pid_page_window_fallback_used:book_pages=...`，便于全量报告中识别它不是强证据。
- 普通 NDL 受限下载保护保持不变：非 diary / 非 configured known PID 的条目仍会在无页映射时停为 `page_mapping_required_but_unavailable`。

新增回归测试：

- `test_verifier_uses_diary_known_pid_page_window_when_mapping_and_snippet_missing`
- 继续保留并通过 `test_verifier_skips_restricted_ndl_download_without_page_mapping`，确认没有放宽普通 NDL 下载保护。

本轮 probe 输出目录：

- `output/historical_citation_source_type_probe_20260501_diary_window_fallback`

观察结果：

- 《日本外交文書》第32巻：claim-aware adapter 仍优先 `3448128`，同卷候选组不退化。
- 《原敬日記》日期型：adapter 仍优先配置 PID `2982135`；目标 PID 内日期 snippet 仍为 0，这正是小页窗 fallback 的触发场景。
- 《山縣有朋意見書》：已知单独 PID `3025431` 仍稳定优先。

验证：

- 三类史料 probe 成功生成报告。
- 完整单测通过：`py -3.11 -X utf8 -m unittest tests.test_historical_citation_verifier`，172 tests OK。

下一步：

- 将 `known_pid_page_window_fallback`、`Adapter Candidate Order`、target PID snippet hit_count 纳入真实 PDF next-stage 报告，使全量运行后能区分“已进入诊断 OCR”与“仍卡在页映射”。
- 日记类后续仍应继续开发更强的目录/索引定位，不应长期依赖脚注页码近似扫描页。
- 对 fallback OCR 命中的页面，如果 Gemma 判定不支持，应回到同 PID 的目录/索引和相邻页扩展，而不是直接判定史料不支持。

## 15. 2026-05-01 PDF / next-stage 报告诊断字段补强记录

本轮新增问题：

- 上一轮已经把 claim-aware known PID 排序、target PID snippet 探测、日记类 known PID 小页窗 fallback 打通，但真实 PDF / next-stage 报告只显示最终状态，无法稳定区分三类失败原因：候选 PID 排序失败、目标 PID 内 snippet 无命中、已进入诊断 OCR 但尚未完成 LLM 精核。
- 对《原敬日記》这类 date-indexed diary source，target PID 内 snippet 为 0 本身是重要诊断信息；如果不写入报告，后续阅读者会误以为系统没有尝试目标 PID 内全文探测。

已完成：

- `_probe_target_pid_fulltext_hints` 改为无论 `direct_hit` 还是 `no_direct_hit` 都写入 `ndl_fulltext_probe` artifact，记录 `pid`、`status`、`hit_count`、`specific_hit_count`、`pdf_page_hit_count`、`first_pdf_pages`、`queries_tried` 与 `note`。
- `render_resume_markdown_report` 新增固定诊断行：
  - `Adapter Candidate Order`：显示 source adapter 实际候选顺序、known PID 标记与 search route。
  - `Target PID snippet probe`：显示目标 PID 内全文探测状态和命中数量，即使 hits=0 也可见。
  - `Known PID page-window fallback`：显示日记类小页窗 fallback 的 PID、引用页、扫描页窗与证据等级。
- `_current_evidence_status` 增加 `known_pid_page_window_diagnostic_ocr`，避免这类条目在报告中被误读为普通 `source_found` 或 `page_mapping_blocked`。
- `处理历史` 增加 `known_pid_page_window_fallback` 摘要，保留它只是诊断取证路径而不是强证据。

新增回归测试：

- `test_target_pid_fulltext_probe_records_no_hit_diagnostics`
- `test_resume_report_renders_adapter_probe_and_known_pid_fallback_diagnostics`

验证：

- 编译检查通过：`py -3.11 -X utf8 -m py_compile modules\historical_citation_verifier.py modules\historical_citation\reporting.py tests\test_historical_citation_verifier.py`
- 新增报告/探测测试通过。
- 完整单测通过：`py -3.11 -X utf8 -m unittest tests.test_historical_citation_verifier`，174 tests OK。

下一步：

- 对三类史料继续做真实小范围运行，重点检查报告中 `Adapter Candidate Order` 与 `Target PID snippet probe` 是否足以定位失败环节。
- 若 `Target PID snippet probe` 长期为 `no_direct_hit`，但 OCR 小页窗可以命中，应开发目录/索引辅助定位，而不是扩大下载页窗。
- 若 `Adapter Candidate Order` 已正确但最终仍失败，优先优化页映射、OCR cache 与 LLM 精核输入，不再回到泛化 NDL 全站检索。

## 16. 2026-05-01 PID 分组语义拆分记录

本轮新增问题：

- 三类史料真实 probe 显示，《日本外交文書》第32卷的 configured known PID 已正确排序，但全站全文检索会同时带出其它卷册 PID，例如 `3448132`、`3448130`。这些 PID 是有用线索，但不应出现在“等价 PID 组”中。
- 同类问题也会影响日记类：《原敬日記》目标卷为 `2982135`，但全站检索可能带出 `2982137` 等同题名其它卷。它们只能作为全文 lead 或排错线索，不能作为可直接轮换的等价来源。

已完成：

- `record_equivalent_pid_group` 改为在存在 resolver configured known PID 时启用严格分组：
  - `volume_series`、`diary`、`contained_document` 只把 configured PID 或同源强等价 PID 写入 `equivalent_pid_group`。
  - 同题名但不在 configured PID 列表中的全文检索结果写入 `fulltext_lead_pid_group`，并标记 `scope=global_fulltext_lead_not_equivalent`。
- 报告中把 `等价 PID 组` 改为 `严格等价 PID 组`，并新增 `全文线索 PID 组（非等价）`，避免读者把全站泛命中误判为可替换来源。
- `全文线索 PID 组（非等价）` 增加解释行：这些 PID 只能用于人工回查或二次检索，不能作为自动候选轮换的等价来源。
- `scripts/probe_historical_citation_source_types.py` 修正全站全文结果摘要：保留 `metadata.search_route`，避免 probe 自身在 record -> match 转换时丢失全文线索属性。

新增回归测试：

- `test_pdf_next_stage_separates_configured_equivalents_from_fulltext_leads`
- 扩展 `test_resume_report_renders_adapter_probe_and_known_pid_fallback_diagnostics`，确认报告显示 `全文线索 PID 组（非等价）`。

本轮真实 probe 输出目录：

- `output/historical_citation_source_type_probe_20260501_pid_group_split2`

观察结果：

- 《日本外交文書》第32卷：
  - Strict equivalent PID group: `3448128, 3448126, 2530174`
  - Fulltext lead PID group (not equivalent): `3448132, 3448130`
- 《原敬日記》：
  - Known PID candidate: `2982135`
  - Fulltext lead PID group (not equivalent): `2982137`
- 《山縣有朋意見書》：
  - Known PID candidate: `3025431`
  - 未出现需要分离的非等价全文 lead。

验证：

- 相关回归测试通过。
- 三类史料 probe 成功生成报告。
- 完整单测通过：`py -3.11 -X utf8 -m unittest tests.test_historical_citation_verifier`，175 tests OK。

下一步：

- 在 next-stage 候选轮换中使用 `equivalent_pid_group`，但不能自动轮换 `fulltext_lead_pid_group`；后者只用于人工路径、二次检索或提示“可能搜到了错误卷册”。
- 继续观察 `fulltext_lead_pid_group` 是否足以解释“搜到了错误卷册”的情况；如仍不够，应增加更具体的人工回查 query。
- 若全量报告中同一脚注同时出现 configured PID 与多个 fulltext lead，应优先检查 target PID snippet 和页映射，不应退回全站题名相似度排序。

## 17. 2026-05-01 非等价全文 lead 禁止自动轮换记录

本轮新增问题：

- 第16节已经把 `equivalent_pid_group` 和 `fulltext_lead_pid_group` 拆开，但 verifier 的自动备用来源重试仍主要依据 `candidate.ndl_matches`。如果某个 configured PID OCR / Gemma 精核结果较弱，流程仍可能把同题名的全站全文 lead 当作“可轮换来源”继续下载。
- 这会让《日本外交文書》第32卷之类史料重新落回“题名相似但卷册不等价”的旧问题：例如 configured PID 是 `3448128`，而全站全文 lead `3448132`、`3448130` 只应作为排错和人工回查线索，不应自动替换来源。

已完成：

- 新增严格来源范围判断：
  - `volume_series`、`diary`、`contained_document` 且存在 configured known PID 时，自动取证只允许 known PID / strict equivalent PID。
  - `fulltext_lead_pid_group` 中的 PID，或带有 `claim_fulltext_global_recheck` / `fulltext` route 但不在 strict equivalent 范围内的 PID，会被视为 `non_equivalent_fulltext_lead`。
- `_should_try_alternate_source` 在判断备用来源前先过滤非等价全文 lead；如果剩余候选只剩这些 lead，则不触发自动轮换。
- `_obtain_source_pdf` 在实际下载前再次过滤非等价全文 lead，防止 retry 或排序路径绕过判断层。
- 被过滤的 PID 写入 `non_equivalent_fulltext_lead_skipped_ids`，并记录：
  - `alternate_source_retry_skipped_non_equivalent_fulltext_lead`
  - `source_match_non_equivalent_fulltext_lead_filtered`
- `render_resume_markdown_report` 显示 `非等价全文线索已跳过自动轮换`，让全量报告能解释为什么同题名全文 lead 没有被自动下载。
- `render_resume_markdown_report` 为 `fulltext_lead_pid_group` 增加人工回查建议：先回查 strict known PID，再在目标 PID 内搜索 resolver 的 target queries，最后才把 fulltext lead 当作“是否误入其它卷册”的排错线索。

新增回归测试：

- `test_verifier_blocks_non_equivalent_fulltext_lead_from_alternate_retry`
- `test_verifier_does_not_download_non_equivalent_fulltext_lead`
- 同时保留 `test_verifier_allows_same_title_digital_fallback_after_weak_alignment`，确认普通同题名数字化备选来源没有被误伤。

验证：

- 相关测试通过。
- 完整单测通过：`py -3.11 -X utf8 -m unittest tests.test_historical_citation_verifier`，177 tests OK。

下一步：

- 在三类史料小范围真实运行中观察：备用来源 retry 是否只发生在 strict equivalent PID 内。
- 若人工回查建议仍过粗，应把不同 source_type 的提示模板拆开：volume_series 强调卷册/文书题名，diary 强调日期/目录索引，contained_document 强调 host / contained title。

## 18. 2026-05-01 source_type-aware 全文 lead 人工回查提示记录

本轮新增问题：

- 第17节已经让报告显示 `fulltext_lead_pid_group` 与 skipped IDs，但人工回查建议仍是通用句式，不能充分指导不同类型史料的下一步检索。
- 三类史料的人工路径不同：
  - 《日本外交文書》这类 `volume_series` 要先核对卷册、年份、文书题名，防止同题名错卷。
  - 《原敬日記》这类 `diary` 要先确认日期对应卷册；若日期 snippet 为 0，应走目录/索引和小页窗 OCR。
  - 《山縣有朋意見書》这类 `contained_document` 要先确认 host / contained title，只在 host 或严格 PID 内搜析出文献。

已完成：

- `_format_fulltext_lead_manual_hint` 改为 source_type-aware：
  - `volume_series`：提示“先核对卷册/年份/文书题名，避免同题名错卷”。
  - `diary`：提示“先确认日期对应卷册；若日期 snippet 为 0，改查目录/索引和小页窗 OCR”。
  - `contained_document` / `source_collection`：提示“先确认 host 与 contained title，只在 host/严格 PID 内搜析出文献”。
- `scripts/probe_historical_citation_source_types.py` 接入同一 hint 函数，使三类史料 probe 报告也能观察正式报告提示逻辑。
- probe 报告格式去掉重复列表符号，避免出现 `Fulltext lead manual hint: - ...`。

新增回归测试：

- `test_fulltext_lead_manual_hint_uses_source_type_templates`
- 扩展 `test_resume_report_renders_adapter_probe_and_known_pid_fallback_diagnostics`，确认日记型报告出现日期/目录索引提示。

本轮真实 probe 输出目录：

- `output/historical_citation_source_type_probe_20260501_source_type_hint3`

观察结果：

- 《日本外交文書》第32卷：报告提示 `volume_series: 先核对卷册/年份/文书题名`，并列出 strict PID `3448128, 3448126, 2530174` 与 target PID 内查询词。
- 《原敬日記》：报告提示 `diary: 先确认日期对应卷册；若日期 snippet 为 0，改查目录/索引和小页窗 OCR`，并把 `2982137` 标成只用于判断是否误入其它卷册。
- 《山縣有朋意見書》：本轮未出现 fulltext lead，因此人工 lead 提示为 `n/a`，符合预期。

下一步：

- 继续观察真实全量报告中 `fulltext_lead_manual_hint` 是否足以指导人工复核。
- 若 `contained_document` 在真实失败项中出现 fulltext lead，应重点检查 host title 与 contained title 是否来自 PDF parser，避免析出文献被当成独立书检索。
- 若 `volume_series` 的完整文书题名仍 0 命中，应把文书题名 fallback 拆成更细的政策词、发文机关、人名、回答/照会类词组。

## 19. 2026-05-01 卷册型史料全文查询平衡策略记录

本轮新增问题：

- 第18节提出《日本外交文書》这类 `volume_series` 在完整文书题名 0 命中时，需要拆成政策词、发文机关、人名、回答/照会类词组。
- 真实小 probe 进一步显示：全站 `global_queries` 已能找到正确 strict PID，但目标 PID 内 `target_pid_queries` 的前几条仍被完整文书题名和新旧字形变体占满，导致短关键词还没有进入小范围 snippet 探测。
- 这会复现人工检索中常见的问题：书名、卷号、完整文书题名都正确，但 NDL 全文 OCR 对长题名不稳定，反而是 `門戶開放`、`門戸開放`、`米國照會`、`帝國政府回答` 等短词更容易定位正文。

已完成：

- `NihonGaikoBunshoResolver` 增强 John Hay / 门户开放类查询词：
  - 文书题名层：`支那ニ於ケル商業上機會均等及門戸開放` 及新字体变体。
  - 政策短词层：`門戶開放`、`門戸開放`、`商業上機會均等`。
  - 照会/回答层：`米國照會`、`米國政府照會`、`米國國務長官照會`、`帝國政府回答`、`各國回答` 等。
- `SourceQueryPlan.global_fulltext_queries` 和 resolver `global_queries` 改为卷册型平衡排序：
  - 前部保留 `日本外交文書 + 卷号 + 文书题名/短关键词`。
  - 同时把短政策词、照会词、回答词作为 standalone fulltext lead 早放入查询序列。
  - 这样既能找到 strict PID，也能避免长题名 0 命中时整个检索链空转。
- `target_pid_queries` 同步使用同一平衡策略：
  - 第一条仍保留完整文书题名。
  - 第二、三条优先放入 `門戶開放` / `門戸開放`，让目标 PID 内 snippet 更快定位正文。
- `_claim_fulltext_queries` 放宽返回上限到 50，防止新增的跨语种政策词把 `帝國政府回答` 等关键词挤出正式候选。

新增/扩展回归测试：

- 扩展 `test_source_graph_models_gaiko_bunsho_volume_series_with_document_queries`：确认 global queries 中短词和照会词进入前列。
- 扩展 `test_source_resolver_uses_configured_gaiko_bunsho_volume_pid`：确认 target PID queries 前三条为“完整题名 + 门户开放双写法”。
- 扩展 `test_pdf_next_stage_claim_fulltext_recheck_uses_volume_and_claim_terms`：确认 next-stage 查询使用新的 `日本外交文書 第32巻 門戶開放`。

本轮真实 probe 输出目录：

- `output/historical_citation_source_type_probe_20260501_target_query_balance`

观察结果：

- 《日本外交文書》第32卷：
  - `日本外交文書 第32巻 支那ニ於ケル商業上機会均等及門戸開放` -> 0 records。
  - `日本外交文書 第32巻 門戶開放` -> 1 record，first PID=`3448128`。
  - PID `3448128` 内：
    - `門戶開放` -> 10 hits，page=32。
    - `門戸開放` -> 10 hits，page=32。
- 《原敬日記》：
  - 仍显示日期 0 hit、书名 hit 的情况，说明下一步仍需目录/索引和小页窗 OCR 兜底。
  - `2982137` 继续作为非等价 fulltext lead，不自动轮换。
- 《山縣有朋意見書》：
  - strict PID `3025431` 稳定，题名 query 可直接命中。

验证：

- 相关小测试通过。
- 完整单测通过：`py -3.11 -X utf8 -m unittest tests.test_historical_citation_verifier`，178 tests OK。
- 三类史料小 probe 通过：`--max-results 1 --max-queries 3 --max-known-pids 1`。

下一步：

- 继续优化 `diary` 类型：当日期 snippet 为 0、书名或错误卷册有 hit 时，应自动生成“目录/索引 + 小页窗 OCR”的诊断计划，而不是只停留在 fulltext lead 提示。
- 对 `contained_document` 类型继续观察全量失败项：若出现 host 缺失，应优先补 PDF parser 的 host/contained 抽取，不应扩大到全站题名相似度。

## 20. 2026-05-01 日记型日期 0 hit 诊断计划记录

本轮新增问题：

- 第19节 probe 显示《原敬日記》目标 strict PID `2982135` 内，`1900年5月12日` 和 `1900年` 都是 0 hits，但 `原敬日記` 书名可命中卷首/说明页。
- 这说明流程已经找对卷册，但日期并未被 NDL 全文 snippet 直接暴露。此时不应继续把错误卷册全文 lead 当作候选，也不应仅写“人工回查”；应明确进入“目录/索引 + 小页窗 OCR”诊断路径。

已完成：

- verifier 新增 `diary_date_lookup_diagnostic` artifact：
  - 记录 strict PID、known PID candidates、date queries、date hit count、title hit count。
  - 当 `date_hit_count=0` 且 `title_hit_count>0` 时，标记 `recommended_action=toc_index_then_small_page_window_ocr`。
  - 若脚注有页码，自动生成小页窗计划：`cited_book_pages`、`start_page`、`end_page`、`page_window=2`。
  - 记录 note：`diary_date_lookup_needs_index_or_page_window_ocr`。
- 报告新增 `Diary date lookup diagnostic` 行，显示：
  - PID
  - date hits / title hits
  - date queries
  - 下一步 `toc/index + small page-window OCR`
  - cited pages 与 scan window。
- `scripts/probe_historical_citation_source_types.py` 接入同一诊断格式，使三类史料 probe 能提前暴露日记型失败机制。

新增/扩展回归测试：

- `test_diary_target_pid_probe_records_date_lookup_diagnostic`
- 保留并复测 `test_verifier_uses_diary_known_pid_page_window_when_mapping_and_snippet_missing`，确认新增诊断不会破坏既有日记小页窗下载 fallback。

本轮真实 probe 输出目录：

- `output/historical_citation_source_type_probe_20260501_diary_lookup_diag`

观察结果：

- 《原敬日記》：
  - Strict PID: `2982135`
  - `1900年5月12日` -> 0 hits
  - `1900年` -> 0 hits
  - `原敬日記` -> 4 hits
  - 诊断输出：`date_hits=0 | title_hits=4 | next=toc/index + small page-window OCR | cited_pages=84 | scan_window=82-86`
- 《日本外交文書》第32卷：
  - 本轮仍稳定显示 `日本外交文書 第32巻 門戶開放` 找到 PID `3448128`，目标 PID 内 page 32 命中。
- 《山縣有朋意見書》：
  - strict PID `3025431` 仍稳定命中。

验证：

- 新增相关测试通过。
- 三类史料小 probe 通过：`--max-results 1 --max-queries 3 --max-known-pids 1`。

下一步：

- 将 `diary_date_lookup_diagnostic` 与正式下载/OCR阶段的 `known_pid_page_window_fallback` 在报告中进一步合并展示，避免读者以为它们是两条互不相关的路径。
- 对 `contained_document` 进行同样的失败机制显化：当有 known document PID 且 title hit 存在时，报告应明确“先单独 PID，再 host fallback”，并列出 host 缺失与否。

## 21. 2026-05-01 析出/单独文献 known PID 诊断计划记录

本轮新增问题：

- 第20节提出 `contained_document` 也需要失败机制显化。《山縣有朋意見書》这种材料在当前配置中已有单独 NDL Digital PID `3025431`，但脚注可能没有 host title。
- 如果报告只写“host missing”或只显示题名命中，读者仍不清楚流程应先核验单独 PID，还是先去找 host collection。

已完成：

- verifier 新增 `contained_document_lookup_diagnostic` artifact：
  - 记录 strict PID、known PID candidates、contained title、host title / host missing、title hit count。
  - 推荐路径固定为 `known_document_pid_first_then_host_fallback`。
  - 记录 note：`contained_document_known_pid_first_then_host_fallback`。
- 报告新增 `Contained document lookup diagnostic` 行，显示：
  - PID / known PIDs
  - contained title
  - host 是否缺失
  - title hits
  - 下一步 `known document PID first, then host fallback`
- `scripts/probe_historical_citation_source_types.py` 接入同一诊断格式，使三类史料 probe 中可直接观察析出文献路径。

新增/扩展回归测试：

- `test_contained_document_target_pid_probe_records_known_pid_diagnostic`

本轮真实 probe 输出目录：

- `output/historical_citation_source_type_probe_20260501_contained_diag`

观察结果：

- 《山縣有朋意見書》：
  - Strict PID: `3025431`
  - `山縣有朋意見書` -> 10 hits，page=3
  - 诊断输出：`known_pids=3025431 | contained=山縣有朋意見書 | host=missing | title_hits=10 | next=known document PID first, then host fallback`
- 《日本外交文書》第32卷：
  - 仍稳定通过 `日本外交文書 第32巻 門戶開放` 找到 PID `3448128`，目标 PID 内 page 32 命中。
- 《原敬日記》：
  - 仍稳定输出 date 0 hit 诊断与小页窗建议。

验证：

- 新增相关测试通过。
- 三类史料小 probe 通过：`--max-results 1 --max-queries 3 --max-known-pids 1`。

下一步：

- 完整单测后，可进入下一轮小范围流程验证：三类史料分别覆盖 `volume_series`、`diary`、`contained_document` 的“strict PID -> target snippet -> fallback diagnostic”链条。
- 若继续优化，应优先把这些 diagnostic 在正式 next-stage report 的逐条详情中与当前状态、处理历史合并展示，减少读者在多个段落之间来回对照。

## 22. 2026-05-01 source-type 诊断摘要合并展示记录

本轮新增问题：

- 第21节之后，正式报告中已有 `Target PID snippet probe`、`Known PID page-window fallback`、`Diary date lookup diagnostic`、`Contained document lookup diagnostic` 等行。
- 但这些信息分散在逐条详情中，读者仍需自行拼接：strict PID 是否正确、目标 PID 内 snippet 是否命中、是否进入小页窗 OCR、非等价全文 lead 是否已跳过。

已完成：

- `render_resume_markdown_report` 新增 `Source-type diagnostic summary` 单行摘要：
  - 显示 `source_type` 与 strict PID。
  - 合并目标 PID snippet 状态：`target_snippet=<status>/hits=<n>/specific=<n>`。
  - 对 `diary` 合并日期诊断、小页窗 OCR 下一步和 `page_window`。
  - 对 `contained_document` 合并 contained title、host 是否缺失、title hits 与 known PID first 路径。
  - 显示已跳过的非等价全文 lead，避免误以为它们仍会自动轮换。
- 保留原有详细行，摘要只用于快速判断，不替代证据细节。

新增/扩展回归测试：

- 扩展 `test_resume_report_renders_adapter_probe_and_known_pid_fallback_diagnostics`：
  - 确认报告出现 `Source-type diagnostic summary: source_type=diary`。
  - 确认同一行可见 `target_snippet=no_direct_hit/hits=0/specific=0`、`diary_date_hits=0/title_hits=4`、`page_window=82-86`、`skipped_fulltext_leads=14077946`。
- 扩展 `test_contained_document_target_pid_probe_records_known_pid_diagnostic`：
  - 确认 contained-document 摘要显示 `contained=山縣有朋意見書`、`host=missing`、`next=known PID first, then host fallback`。

本轮真实 probe 输出目录：

- `output/historical_citation_source_type_probe_20260501_summary_diag`

观察结果：

- 三类史料 probe 未退化：
  - 《日本外交文書》第32卷仍通过 `日本外交文書 第32巻 門戶開放` 找到 strict PID `3448128`，目标 PID 内 page 32 命中。
  - 《原敬日記》仍输出 date 0 hit 与 `scan_window=82-86`。
  - 《山縣有朋意見書》仍输出 `known_pids=3025431 | host=missing | title_hits=10`。

验证：

- 三类史料小 probe 通过：`--max-results 1 --max-queries 3 --max-known-pids 1`。
- 完整单测通过：`py -3.11 -X utf8 -m unittest tests.test_historical_citation_verifier`，180 tests OK。

下一步：

- 可进入下一轮小范围流程验证，把三类史料分别放进正式 next-stage/resume report，确认摘要在真实报告结构中足够靠前、可读。
- 若下一轮仍出现阅读负担，应进一步把 `Source-type diagnostic summary` 提升到“未覆盖或需复核”列表中，让失败项索引也直接显示卡点。

## 23. 2026-05-01 报告索引层 source-type 卡点摘要记录

本轮新增问题：

- 第22节已经在逐条详情中加入 `Source-type diagnostic summary`，但全量报告阅读时，用户往往先看“已处理候选”或“未覆盖或需复核”索引。
- 如果索引行只显示状态和题名，仍需要跳入详情才能知道卡在 `target snippet`、`diary date 0 hit`、`known PID page window` 还是 `host fallback`。

已完成：

- `render_resume_markdown_report` 的“已处理候选”索引行新增 `diag=...`：
  - 复用同一 source-type 诊断摘要，但压缩为单行。
  - 显示 `source_type`、strict PID、target snippet 状态、fallback / next action、已跳过的非等价 fulltext lead。
- `render_verification_markdown_report` 的“未覆盖或需复核”索引行也新增 `diag=...`，让非 resume 报告保持同一阅读逻辑。
- 保留逐条详情中的完整 `Source-type diagnostic summary`，索引只作快速扫描。

新增/扩展回归测试：

- 扩展 `test_resume_report_renders_adapter_probe_and_known_pid_fallback_diagnostics`，确认报告同时包含：
  - 详情层 `Source-type diagnostic summary: source_type=diary`
  - 索引层 `diag=source_type=diary`

验证：

- 相关报告测试通过。
- 完整单测通过：`py -3.11 -X utf8 -m unittest tests.test_historical_citation_verifier`，180 tests OK。

下一步：

- 下一轮可以开始正式的小范围 next-stage/resume 报告验证：只选三类史料样本，检查索引层 diag、详情层 diagnostic、严格 PID/全文 lead 分组、LLM 精核字段是否共同工作。
- 若样本报告已稳定，再进入两篇论文全量前的最后一次流程确认。

## 24. 2026-05-01 三类史料同一 resume 报告索引验证记录

本轮新增问题：

- 第23节把 `diag=...` 加入索引层后，还需要确认三种史料类型在同一份正式 resume report 中不会互相覆盖或混淆。
- 真实全量报告会同时出现 `volume_series`、`diary`、`contained_document`，因此测试不能只覆盖单条日记样本。

已完成：

- 新增三类同报回归测试：
  - `volume_series`：《日本外交文書》第32卷，strict PID `3448128`，target snippet direct hit。
  - `diary`：《原敬日記》，strict PID `2982135`，date 0 hit + 小页窗 OCR。
  - `contained_document`：《山縣有朋意見書》，strict PID `3025431`，host missing + known PID first。
- 同一份 `render_resume_markdown_report` 中确认：
  - 索引层出现 `diag=source_type=volume_series` 与 `target_snippet=direct_hit/hits=10/specific=10`。
  - 索引层出现 `diag=source_type=diary` 与 `diary_date_hits=0/title_hits=4`。
  - 索引层出现 `diag=source_type=contained_document` 与 `next=known PID first, then host fallback`。

新增回归测试：

- `test_resume_report_indexes_three_source_type_diagnostics`

验证：

- 三类同报测试通过。
- 完整单测通过：`py -3.11 -X utf8 -m unittest tests.test_historical_citation_verifier`，181 tests OK。

下一步：

- 进入两篇论文全量前的最后一次流程确认：
  - 确认正式 next-stage 默认仍使用 Gemma 精核。
  - 确认三类史料 source-type resolver 与报告 diag 不影响 Word 成功范例格式。
  - 确认全量 runner / partial / retry 的流程说明与当前代码一致。

## 25. 2026-05-01 全量前流程默认参数确认记录

本轮新增问题：

- 两篇论文全量前必须再次确认正式 workflow 没有偏离既定要求：
  - LLM 精核必须默认 Gemma。
  - fullrun 必须执行首轮 next-stage 与 timeout retry。
  - partial finalizer 必须能把 partial 写成正式 JSON/Markdown 报告。

已完成：

- 新增/扩展 CLI 默认参数回归测试：
  - `refine_historical_citation_pdf_next_stage.py` 默认 `prefer_ollama_review=True`。
  - next-stage 默认 `review_model=gemma4:e4b`，并确认默认模型名不含 `qwen`。
  - `run_historical_citation_pdf_fullrun.py` 默认 `review_model=gemma4:e4b`。
  - fullrun 默认 `next_stage_timeout=600`、`retry_timeout=900`。
- 扩展 fullrun next-stage 调用测试：
  - 首轮命令包含 `--review-model gemma4:e4b`。
  - retry 命令包含 `--retry-download-timeouts` 与 `900` 秒 timeout。
  - `--restricted-download` 仅在用户显式指定时加入首轮和 retry 命令。
- 复测 partial finalizer：
  - `verification_results.partial.json` 可产出正式 `verification_results.json` 与 `verification_report.md`。

新增/扩展回归测试：

- `test_pdf_next_stage_defaults_to_formal_gemma_review`
- 扩展 `test_fullrun_next_stage_respects_restricted_download_flag`
- 复测 `test_partial_finalizer_writes_canonical_json_and_report`

验证：

- 相关流程默认参数测试通过。
- 完整单测通过：`py -3.11 -X utf8 -m unittest tests.test_historical_citation_verifier`，182 tests OK。

下一步：

- 当前已经具备进入两篇论文全量前的小范围人工流程确认条件。
- 建议下一轮只做一次三类史料正式小范围运行，检查真实输出报告的索引层 diag、详情层 diagnostic、Gemma 精核字段、strict PID / fulltext lead 分组是否全部可读；如果通过，再启动两篇论文全量。

## 26. 2026-05-01 三类史料正式小样本 strict PID probe 修正记录

本轮新增问题：

- 三类史料正式 next-stage 小样本首次真实运行后发现，单测虽然覆盖了独立诊断，但真实 recheck 中全站 fulltext lead 仍可能覆盖目标 PID probe。
- 具体表现：
  - 《原敬日記》strict PID 应为 `2982135`，但详情层一度显示为非等价 lead PID `14077924`。
  - 《山縣有朋意見書》strict PID 应为 `3025431`，但 contained-document diagnostic 一度被非等价 lead PID `3363125` 覆盖。
  - 《日本外交文書》第32卷虽然配置中把人工确认的 `3448128` 放在首位，但 recheck 排序后先探测了同卷备用 PID `3448126`，导致报告与人工路径不完全一致。

原因判断：

- `_rerank_matches_for_candidate_fulltext` 原先按 adapter 排序逐个处理候选。
- 当某个候选已经带有全站 fulltext hint 时，代码可能跳过 strict known PID 的目标 probe。
- 非等价 fulltext lead 的目标 probe 会写入同一个 `ndl_fulltext_probe` 字段，从而覆盖 strict PID 的目标诊断。
- strict known PID 的探测顺序没有完全遵循 resolver plan 中的 `known_pid_candidates` 顺序。

已完成：

- strict resolver 类型（`volume_series`、`diary`、`contained_document`）改为优先按 resolver plan 的 `known_pid_candidates` 顺序探测。
- 对 strict known PID，即使已有全站 fulltext hint，也强制执行一次目标 PID probe。
- 非等价 fulltext lead 不再覆盖 `ndl_fulltext_probe`、日记日期诊断或 contained-document 诊断。
- 新增 `target_pid_fulltext_probes`，保留实际目标 PID probe 记录。
- 若未来确实探测了非等价 lead，则只能进入 `non_equivalent_fulltext_probes`，不能作为目标证据。

新增回归测试：

- `test_strict_resolver_forces_known_pid_probe_even_when_fulltext_hints_exist`
- `test_strict_resolver_does_not_let_fulltext_lead_overwrite_target_probe`

正式小样本复测：

- 输出目录：`output/historical_citation_next_stage_three_source_types_20260501`
- 《日本外交文書》第32卷：
  - index 层：`target_snippet=direct_hit/hits=10/specific=10`
  - detail 层：`Target PID snippet probe: pid=3448128`
- 《原敬日記》：
  - index 层：`strict_pid=2982135`
  - detail 层：`Target PID snippet probe: pid=2982135`
  - `Diary date lookup diagnostic: PID=2982135`
- 《山縣有朋意見書》：
  - index 层：`strict_pid=3025431`
  - detail 层：`Target PID snippet probe: pid=3025431`
  - `Contained document lookup diagnostic: PID=3025431`
- next-stage 执行字段确认：
  - `prefer_ollama_review=True`
  - `review_model=gemma4:e4b`
  - `force_ndl_fulltext=True`

下一步：

- 跑完整单测确认无回归。
- 若通过，可进入两篇论文全量前的最后确认：使用当前 runner 默认参数，不再改变主流程，只在全量中观察 timeout、partial finalizer、retry 和最终 Gemma 精核是否按预期工作。

## 27. 2026-05-01 两篇论文全量回归后的阶段统计修正记录

本轮全量输出目录：
- `output/historical_citation_pdf_fullrun_20260501_post_strict_pid`

运行结果概况：
- 宗教论文：combined 45 条，`source_found=43`，`source_mismatch=2`，`source_not_found=0`；next-stage 当前无 timeout。
- 外交论文：combined 43 条，`source_found=31`，`source_mismatch=12`；retry 后 next-stage 当前无 timeout。
- 两篇论文均使用 `review_model=gemma4:e4b`，并保持 `force_ndl_fulltext=True`。

新增发现的问题：

1. `rechecked_download_ocr_alignment` 被混入普通 `download_ocr_alignment_results`。
   - 宗教论文实际为普通下载/OCR 34 条、source mismatch recheck 后再下载/OCR 1 条，但报告中显示 download 总数 35。
   - 外交论文实际为普通下载/OCR 23 条、source mismatch recheck 后再下载/OCR 9 条，但报告中显示 download 总数 32。
   - 这不会直接改变逐条最终证据，但会误导流程瓶颈判断，尤其看不出哪些结果来自“先修正来源，再进入下载/OCR/Gemma 精核”。

2. retry 后的 `execution` 只记录最后一次运行参数。
   - 当前 JSON 只显示 `download_timeout_seconds=900`、`retry_download_timeouts=true`，不能看出首轮是 600 秒。
   - 后续应增加 `execution_runs` 或 `run_history`，明确首轮、retry、resume 的参数和时间。

3. 慢路径没有被单独标记。
   - 虽然 timeout 已清零，但仍有多条候选耗时超过 240 秒。
   - 后续应在 JSON/report 中增加 `slow_events`，记录阶段、candidate_id、footnote_id、状态、elapsed_seconds、PID 和页窗。

4. 外交论文仍暴露卷册/文书题名级定位瓶颈。
   - `日本外交文書`、`原敬日記`、`山縣有朋意見書` 类材料虽然已经比最初稳定，但 `fulltext_lead_only` 和 `page_mapping` 型弱结果仍偏多。
   - 后续优化仍应围绕 source graph：卷册 PID、日期型脚注、析出文献 host/contained 关系和文书题名扩展。

已完成的修正：

- next-stage JSON 新增 `rechecked_download_ocr_alignment_results`。
- summaries 新增 `rechecked_download_ocr_alignment`，普通 `download_ocr_alignment` 只统计首轮 source_found 下载/OCR。
- Markdown checkpoint 新增 `rechecked_download_ocr_alignment_count`。
- resume 读取旧 JSON 时，会自动把带有 `download_after_source_recheck` note 的旧混入结果迁移到 rechecked 阶段。
- rechecked 阶段写入时强制保留 `download_after_source_recheck` note，避免后续 resume 再次混入普通下载阶段。

下一步优化方向：

- 用现有全量输出重写 next-stage 报告，确认宗教论文为 `download=34 + rechecked_download=1`，外交论文为 `download=23 + rechecked_download=9`。
- 增加 `slow_events` 正式字段，不改变主流程，只在报告中显式标记超过阈值的慢候选。
- 增加 `execution_runs`，保留首轮、retry、resume 的参数与时间，避免“当前状态”和“处理历史”混淆。
- 继续围绕三类史料类型推进通用 resolver：`volume_series`、`diary`、`contained_document`。

## 28. 2026-05-01 慢路径显式记录修正

本轮新增问题：
- timeout 清零后，报告读者仍无法判断哪些条目虽然完成但代价过高。
- 这些慢路径往往对应下载/OCR、全文 lead 轮换、页窗判断或 rechecked download，因此应被视为流程优化对象，而不是普通成功项。

已完成：
- next-stage CLI 新增 `--slow-event-threshold-seconds`，默认 240 秒。
- 从 `next_stage_progress.jsonl` 的 `candidate_started` / `candidate_completed` 事件自动计算 `elapsed_seconds`。
- JSON 新增 `slow_events`，summary 新增 `summaries.slow_events.total`。
- Markdown 报告末尾新增 `处理慢路径` 小节，列出 phase、脚注、candidate_id、最终状态和耗时。
- 这一步只读取 progress 日志，不改变检索、下载、OCR、Gemma 精核结果。

回灌两篇全量报告后的观察：
- 宗教论文：普通下载/OCR 34 条，rechecked 下载/OCR 1 条，slow events 5 条，timeout 0。
- 外交论文：普通下载/OCR 23 条，rechecked 下载/OCR 9 条，slow events 10 条，timeout 0。
- 最慢项集中于外交论文的 `rechecked_download_ocr_alignment`，说明 source mismatch 修正后进入二次下载/OCR 的材料仍是下一轮性能优化重点。

下一步：
- 增加 `execution_runs`，记录首轮 600 秒、retry 900 秒、resume 报告迁移等不同运行阶段。
- 对 slow events 增加更细原因分类：download wait、page mapping、OCR、fulltext lead rotation、Gemma review。
- 对外交论文慢路径优先检查《日本外交文書》卷册 PID、文书题名级查询和错误卷册 lead 的轮换规则。

## 29. 2026-05-01 运行历史显式记录修正

本轮新增问题：
- `execution` 字段只能代表最后一次 next-stage 调用，无法区分首轮、retry、resume 和报告迁移。
- 当 retry 成功清零 timeout 后，读者容易误以为全程都是 900 秒 timeout，而看不到首轮 600 秒和后续 retry 的关系。

已完成：
- next-stage JSON 新增 `execution_runs`。
- 每次运行会追加一条 run record，记录 `started_at`、`mode`、`download_timeout_seconds`、`retry_download_timeouts`、`resume`、`review_model`、`force_ndl_fulltext` 和慢路径阈值。
- 旧 JSON 没有 `execution_runs` 时，会把既有 `execution` 转成 `legacy_next_stage_run`，再追加当前运行。
- Markdown 报告末尾新增 `运行历史` 小节，显示最近运行的 timeout、retry 和模型。

回灌两篇全量报告后的观察：
- 宗教论文：`execution_runs=2`，最后一次为 `retry_or_resume:900`。
- 外交论文：`execution_runs=2`，最后一次为 `retry_or_resume:900`。
- 由于这是对旧报告的迁移，历史中无法反推出最早的 600 秒首轮；但之后从头跑 fullrun 时，首轮与 retry 会分别落入 `execution_runs`。

下一步：
- 对 `slow_events` 增加原因分类，优先从 artifacts 判断是否卡在 page mapping、fulltext lead rotation、OCR 或 Gemma review。
- 对外交论文的 `volume_series` resolver 继续强化文书题名级查询，减少错误卷册 lead 和 rechecked 下载/OCR 的慢路径。

## 30. 2026-05-01 多命中并列扩搜与可读图像路径修正

本轮新增问题：
- NDL Digital PID 内全文搜索在关键词较短或未精确命中时，会返回多个 hit；旧流程只扩展第一个 hit，容易把目录、题名页、索引或泛化上下文误当证据。
- 宗教论文中 `p4n9` 曾经能命中正确正文句，但新一轮被较短的 `神宮大麻 流言` 上下文覆盖，退化为 partial。
- 外交论文中《日本外交文書》仍容易被全站全文 lead 或错误卷册带偏，尤其《巴黎讲和会议经过概要》《ワシントン会議/軍備制限問題》类文书题名需要先进入严格卷册 PID。
- 《帝国憲法義解・皇室典範義解》PID `1272168` 没有普通公开 PDF 时，仍有 IIIF manifest 和 NDL Lab fulltext-json 可读，不应仅停在 `source_pdf_not_available`。

已完成：
- 新增多上下文候选精核接口：每条 fulltext hit 扩展后形成 `fulltext_context_candidates`，保留 `context_id`、PID、query、pdf_page、lead category、score、score reasons 和清洗后上下文。
- `_mark_fulltext_only_hit_if_possible` 改为 top 5 并列上下文择优，不再默认使用第一条 SNIPPET。
- 新增上下文候选评分：
  - 奖励析出题名/目标 PID 查询、核心动作词、较长上下文、扩展 evidence count、页码提示。
  - 惩罚 `toc_or_index`、`title_or_series_only`、`wrong_pid`、`short_or_unexpanded`。
- Gemma 精核改为接收 3-5 个并列上下文，输出 `best_context_id`、`best_sentence_index`、decision、reason 和各候选不足说明；没有正式模型时保留启发式择优，不改变主流程。
- `source_collection` 和 `downloadable_monograph` 纳入 strict PID scope：
  - 日本近代思想大系固定 PID `13260166`。
  - 伊藤博文合刻本固定 PID `1272168`。
- 《日本外交文書》resolver 增加文书题名级词表：
  - `大正期追補 / 巴里講和会議経過概要 / 巴黎讲和会议经过概要 / 牧野`
  - `ワシントン会議 / 華盛頓會議 / 軍備制限問題 / 海軍軍備制限問題 / 主力艦`
- resolver config 增加严格 PID：
  - `11923430`: `日本外交文書 大正期 追補 [1] 巴里講和会議経過概要`
  - `11927523`: `日本外交文書 ワシントン会議 上`
- 伊藤博文 `DownloadableMonographResolver` 对信教/宗教/自由类脚注新增 PID 内查询词：
  - `信仰`、`信仰歸依`、`内部ニ於ケル信`、`外部ニ於ケル禮拜`、`臣民ノ義務`、`法憲` 等。
- 新增 `iiif_image_ocr_available` 状态与 artifact：
  - 检测 `https://dl.ndl.go.jp/api/iiif/{pid}/manifest.json`
  - 检测 `https://lab.ndl.go.jp/dl/api/book/fulltext-json/{pid}`
  - 无 PDF 但有 IIIF/fulltext-json 时，标记为可继续 OCR/全文 JSON 路径，不再只写 `source_pdf_not_available`。
- Markdown 报告新增：
  - `全文上下文候选 Top N`
  - `fulltext_selected_context_id`
  - 每个候选的清洗后上下文、score reasons、lead category
  - IIIF/fulltext-json 可读路径说明。

新增回归测试：
- `test_fulltext_only_hit_scores_parallel_contexts_before_selecting_best`
- `test_source_resolver_maps_paris_peace_supplement_pid`
- `test_source_resolver_maps_washington_conference_pid_before_fulltext_leads`
- `test_verifier_records_iiif_image_ocr_availability_for_imperial_gikai`
- 报告结构测试同步覆盖 `全文上下文候选 Top N`。

当前小范围测试结果：
- 新增五项回归通过。
- 旧的 fulltext lead、source graph、外交文书第32卷、NDL fulltext page fallback、page mapping block 相关 8 项回归通过。
- 完整 `tests.test_historical_citation_verifier` 191 项通过，5 项按原逻辑跳过。

实网小样本新增观察：
- `p4n9` 严格 PID `13260166` 验证通过：
  - top context 选中 `静岡県で大麻につき流言`。
  - 扩展上下文已包含 `水火ニ投ズル`、`河流ニ投ジ`、`大麻ノ神ノ字ガ蝶ニ化スル`、`時疫ニ死絶`。
  - Gemma `gemma4:e4b` 判为 `fulltext_only_direct_support`。
- 初始实网脚本一次性跑四个样本时超过 6 分钟；瓶颈来自多 hit 扩展与 Gemma 串行。
- 因此默认扩展策略从 top 5 收紧为 top 3 expanded contexts；报告仍保留 Top N 结构，后续可按失败项单独提高扩展上限。
- Gemma 对中文输入偶发误读为 question marks；已加入 `question marks / input empty` 误读检测。若发生误读，回退到多上下文评分；只有正文候选且核心动作词覆盖强时才允许 fallback direct。
- 外交 `p4n5` 严格 PID `11923430` 的快速 probe 已确认：
  - 第一条命中是第 3 页题名页 `巴里講和会議経過概要`。
  - 后续命中才出现第 9 页 `帝國主張説明(牧野男)` 等正文线索。
  - 已新增规则：`pdf_page<=8` 且 snippet 等于 query 或极短时，降级为 `title_or_series_only`，不得覆盖正文候选。

下一步：
- 继续用严格 PID 小样本补测外交 `p4n5` / Washington 与伊藤 `1272168`，但逐条运行，避免再次触发 6 分钟串行超时。
- 外交论文 `p4n5` / Washington：应优先进入 `11923430` / `11927523`，全站 lead 仅保留为人工回查线索。
- 伊藤博文 PID `1272168`：无 PDF 时应记录 IIIF/fulltext-json，并继续 PID 内全文上下文与 Gemma 精核。
- 若逐条样本仍慢，下一步应增加 source-level fulltext-context cache：同一 PID/query/page 的扩展上下文跨脚注复用。

## 31. 2026-05-01 strict PID 三类小样本扩搜排序与缓存修正

本轮新增确认的问题：
- NDL Digital 的 PID 内全文命中不仅会把题名页、目录页放在前面，也会把卷末版权页/刊记页放在前面。例如 `11923430` 中 `巴里講和会議経過概要` 同时命中第 3 页题名页和第 668 页刊记页。
- 即使扩搜了 Top 3，旧评分仍可能把“牧野 + 講和會議 + 山東”这类泛化正文排在 `帝國主張説明(牧野男)` 前面，导致 `p4n5` 接近正确句子却没有选中最合适上下文。
- `ワシントン会議` 这类短而泛的会议名会把题名/索引/导言页误当成实质证据；真正有用的是 `軍備制限問題`、`海軍軍備制限`、`主力艦` 等文书主题词。
- 多 hit 扩搜耗时仍高：`p4n9` 单条真实 Gemma 精核约 125 秒，一次串行跑四条样本会超过 6 分钟。

已完成的修正：
- 新增 source-level fulltext context cache：同一 verifier 实例内，按 `PID + query + cid/content_index/page + page_basis + snippet` 复用 `expand_ndl_snippet_context` 结果。
- `_ordered_fulltext_hints_for_candidate` 在扩搜前先按 lead category 排序：`body_candidate` 优先，`short_or_unexpanded` 次之，`title_or_series_only`、`toc_or_index`、`wrong_pid` 后置。
- `fulltext_hint_lead_category` 增强：
  - 题名页/目录页/索引页继续降级；
  - 含 `不許複製`、`印刷`、`発行/發行`、`Published` 且只命中题名的刊记页降级；
  - 早期页只命中 host/contained title、且没有实质主题词时降级。
- `hint_has_claim_snippet_evidence` 不再把 `講和会議`、`ワシントン会議`、`大正期追補`、host title、contained title 等泛化标题词当成 claim evidence。
- 上下文评分新增 `specific_targets` 奖励：只有 `target_pid_queries` / `query_buckets` 中的实质目标词进入清洗后上下文时加分，例如 `帝國主張説明`、`軍備制限問題`、`海軍軍備制限`、`内部ニ於ケル信`、`臣民ノ義務`。

真实 strict PID 小样本观察：
- `11923430`（巴黎讲和会议经过概要）：
  - PID 内直接命中 13 条。
  - 排序修正后扩搜 Top 3 中第 9 页 `帝國主張説明(牧野男)` 排到第一；第 35 页山東/膠州湾上下文保留为并列候选，但不再压过 p4n5 的目标句。
- `11927523`（ワシントン会議 上）：
  - PID 内直接命中 40 条。
  - 扩搜第一候选进入第 8 页 `海軍軍備制限問題` 正文；`ワシントン会議` 泛命中仍保留为候选，但低于军备限制主题词。
- `1272168`（帝国憲法義解・皇室典範義解）：
  - PID 内直接命中第 39 页。
  - 扩搜 Top 3 均为同页正文，覆盖 `信仰歸依`、`内部ニ於ケル信`、`臣民ノ義務`、`外部ニ於ケル禮拜`、`法律規則`。

新增/扩展回归测试：
- `test_fulltext_context_expansion_cache_reuses_same_pid_hit`
- 扩展 `test_fulltext_context_penalizes_early_gaiko_title_page_hit`：确认题名页降级后，正文 hit 在扩搜前排序中优先。

下一步：
- 运行完整单测确认无回归。
- 若全量中仍有外交文书误判，应继续把 `specific_targets` 从静态词表升级为文书题名级 query bucket：每个 `日本外交文書` 卷册按“卷册题名、文书题名、人物、主题词、页码附近词”分层加权。
- 若耗时仍高，再把当前内存 cache 扩展为可选磁盘 cache，键中保留 PID、cid、page、snippet hash，避免跨 resume 重复扩搜。

## 32. 2026-05-01 外交文书 query bucket 分层与扩搜磁盘缓存

本轮新增问题：
- 上一轮已经有 `specific_targets`，但仍偏静态词表：`日本外交文書` 的卷册题名、文书题名、人物、主题词、页码附近词没有分层，导致 `講和会議`、`ワシントン会議` 这类泛题名仍可能和真正正文标题竞争。
- next-stage 子进程或 resume 后会重新实例化 verifier，上一轮的内存 fulltext context cache 不能跨进程/跨 resume 复用。

已完成的修正：
- `NihonGaikoBunshoResolver` 新增分层 query bucket：
  - `document_title`：卷册/文书题名，如 `巴里講和会議経過概要`、`ワシントン会議`。
  - `document_heading`：正文文书题名或页内标题，如 `帝國主張説明`、`牧野男`、`海軍軍備制限`、`軍備制限問題`、`主力艦`。
  - `policy/person/date` 继续保留为独立层。
- `target_pid_queries` 的平衡策略升级：
  - 门户开放类仍保持旧成功范例：`支那ニ於ケル商業上機會均等及門戸開放` 排首位，随后是 `門戶開放`、`門戸開放`。
  - 巴黎/华盛顿类优先正文文书题名与主题词，避免卷册题名压过正文命中。
- 全文上下文评分升级：
  - `document_heading` 权重最高；
  - `policy/theme/page_near` 次之；
  - `document_title` 只作为较弱加权，且泛卷册题名仍不能单独变成强证据。
- fulltext context cache 扩展为可选磁盘缓存：
  - 文件名：`fulltext_context_expansion_cache.json`。
  - key 保留 `PID + query + cid/content_index/page + page_basis + snippet_hash`。
  - next-stage / subprocess / resume 重新实例化 verifier 后可以复用已扩出的上下文。

新增/扩展回归测试：
- 扩展 `test_source_resolver_maps_paris_peace_supplement_pid`：确认 `document_title` 与 `document_heading` 分层。
- 扩展 `test_source_resolver_maps_washington_conference_pid_before_fulltext_leads`：确认华盛顿会议进入 `document_title`，军备限制进入 `document_heading`。
- 扩展 `test_fulltext_context_penalizes_early_gaiko_title_page_hit`：确认正文上下文评分记录 `document_heading` 命中。
- 新增 `test_fulltext_context_expansion_disk_cache_reuses_across_verifiers`：确认第二个 verifier 实例不再调用 NDL 扩搜，直接读取磁盘 cache。

真实 strict PID 轻量复测：
- `11923430` 巴黎讲和：
  - resolver 首批 query 已变为 `帝国主張説明`、`帝國主張説明`、`牧野男`。
  - PID 内命中 36 条，Top 1 为第 9 页 `帝國主張説明(牧野男)` 正文。
- `11927523` 华盛顿会议：
  - resolver 首批 query 为 `海軍軍備制限`、`軍備制限問題`、`海軍軍備制限問題`。
  - PID 内命中 51 条，Top 1/2 均为第 8 页海军军备限制正文。
- `1272168` 帝国憲法義解：
  - 仍稳定命中第 39 页，Top 3 覆盖 `外部ニ於ケル禮拜`、`内部ニ於ケル信`、`臣民ノ義務`。

验证：
- 完整单测通过：`193 tests OK (skipped=5)`。

下一步：
- 用这版重新跑三类史料小样本的正式 next-stage（含 Gemma）确认报告层字段可读。
- 若正式小样本稳定，再进入两篇论文全量重跑。
- 全量后重点检查外交论文中 `日本外交文書` 的 `fulltext_context_candidates` 是否显示分层原因；若仍有误判，再为具体卷册增加 `page_near` 词和文书题名映射表。

## 33. 2026-05-02 外交文书复合证据包与 direct 判定上下文补齐

本轮新增问题：
- `日本外交文書` 中的复合事实经常分散在多个相邻或互补 hit 中，例如 p2n1 的“美国/海伊提出门户开放”与“日本政府承诺该原则”分别落在不同全文上下文。
- 只把 Top N 上下文并列送 Gemma 仍不够稳定：模型可能只选中其中一个上下文并给出 `partial_support`，也可能判为 `direct_support` 但 `supporting_context_ids` 只写单一上下文，导致报告看起来像单片段支持了完整复合主张。
- 小样本复跑时发现仅靠 `mismatch_start_index` 选择样本不可靠：完整 combined 与三类史料 combined 的排序不同，容易误跑到 p1n1。后续 batch runner 应支持按 `candidate_id` / `footnote_id` 精确选择。

已完成的修正：
- 新增 `fulltext_compound_evidence_packet`：
  - 当前先针对 `volume_series` 中的门户开放类外交文书主张启用；
  - 分为 `us_proposal`、`open_door_principle`、`japan_acceptance` 三个 required facet；
  - 每个 facet 记录命中的 `context_id`、页码、query、matched terms 和短摘录；
  - 当所有 required facet 覆盖时，报告显示 `complete=True`。
- `build_multi_context_review_prompt` / `review_context_candidates_with_llm` 增加 `compound_evidence_packet` 输入，提示 Gemma 对同一来源内的 facet 进行组合阅读。
- 对 `direct_support` 增加确定性补齐：
  - 如果 Gemma 判 direct，但 `supporting_context_ids` 未覆盖复合证据包的 required facets，系统自动补入最小必要上下文；
  - 报告新增 `LLM 复合证据补齐`，显示补入的 contexts 与 facets；
  - `fulltext_llm_review_basis` 升级为 `ndl_expanded_snippet_context_candidates_plus_compound_packet`。
- 对 `partial_support` / `not_supported` 增加复核缺口标记：
  - 如果复合证据包 complete，但最终精核仍未判 direct，写入 `fulltext_compound_evidence_review_gap`；
  - notes 追加 `fulltext_compound_evidence_requires_manual_review`，防止这类条目被误当成普通 partial。
- 报告新增“复合证据包”段落，和“全文上下文候选 Top N”并列展示。

真实 p2n1 formal 小样本验证：
- 使用三类史料 combined 精确复跑 p2n1：
  - 输出目录：`output/historical_citation_next_stage_three_source_types_20260502_compound_packet_p2n1_augmented`。
  - 结果：`fulltext_only_direct_support`，matched page = 34。
  - Gemma：`gemma4:e4b`，`direct_support`，confidence = 0.95。
  - 复合证据包：`complete=True`。
  - facet 覆盖：
    - `us_proposal`: `ctx2@p32` 命中 `合衆國ノ提議`；
    - `open_door_principle`: `ctx1@p34`、`ctx2@p32` 等命中 `門戶開放`；
    - `japan_acceptance`: `ctx1@p34` 命中 `日本國政府ハ`、`承諾シタル`。
  - 报告显示：`LLM 组合上下文: ctx1, ctx2`，`LLM 复合证据补齐: contexts=ctx2`。

新增/扩展回归测试：
- `test_multi_context_review_allows_combined_direct_support`：确认 prompt 带入 compound packet。
- `test_gaiko_open_door_compound_packet_groups_split_facets`：确认 p2n1 式分散 facet 能被打包，且 partial 时产生 review gap。
- `test_gaiko_open_door_direct_review_adds_missing_compound_contexts`：确认 direct 判定会补齐缺失的 facet 上下文。

验证：
- 针对性回归通过：5 tests OK。
- 完整单测通过：`198 tests OK (skipped=5)`。

下一步：
- 将复合证据包从门户开放类推广为通用 `volume_series` 机制：按 source resolver 的 `query_buckets` 自动生成 required / optional facets，而不是只写门户开放专案。
- 为 next-stage / fullrun runner 增加 `--candidate-id`、`--footnote-id` 精确选择参数，避免小样本回归因 offset 漂移误跑。
- 对外交论文全量中的 `日本外交文書` 条目，重点检查 direct 判定的 `supporting_context_ids` 是否覆盖主张中的所有 required facets；若未覆盖，应列入 regression/manual review 清单。

## 34. 2026-05-02 精确小样本选择与通用 volume_series facet

本轮新增问题：
- 上一轮 p2n1 formal 复跑时，完整 combined 与三类史料 combined 的排序不同，`mismatch_start_index=0` 在完整 combined 中实际跑到了 p1n1。说明 offset 只能用于全量分段，不适合作为回归样本定位手段。
- 门户开放专门 facet 已能解决 p2n1，但后续 `日本外交文書` 其他卷册仍会出现“文书题名 / 人物 / 政策词 / 页码附近词分散在多个 context”的情况，需要有可复用机制。

已完成的修正：
- `refine_historical_citation_pdf_next_stage.py` 新增精确选择参数：
  - `--candidate-id`：可重复，也可逗号分隔；
  - `--footnote-id`：可重复，也可逗号分隔；
  - 选择顺序为：先按原状态选集，再用 candidate/footnote 收窄，最后才应用 start index 与 max limit。
- `run_historical_citation_pdf_fullrun.py` 透传 `--candidate-id` / `--footnote-id` 到 next-stage，便于全量 runner 中复跑单条回归。
- next-stage `execution` / `execution_runs` 记录 `candidate_ids`、`footnote_ids`，报告可追踪小样本选择依据。
- 新增通用 `volume_series_query_bucket_compound_claim`：
  - 从 resolver 的 `query_buckets` 自动生成 facet；
  - `document_heading`、`policy`、`theme`、`page_near`、`contained`、`special_term` 默认 required；
  - `person`、`date`、`document_title` 默认 optional；
  - 若只有一个强 required facet，但存在 `person` 或 `date`，会提升其为 required；
  - required facet 少于两个时不启用 packet，避免把单一命中误包装成复合证据。
- 门户开放类仍保留专门 packet：`volume_series_open_door_compound_claim`。这是目前已经实测有效的高价值特例，不被通用规则覆盖掉。

轻量 CLI smoke test：
- 命令使用三类史料 combined，并指定 `--candidate-id p2-fp2n1`，同时跳过下载/检索。
- 输出目录：`output/historical_citation_next_stage_selection_smoke_20260502`。
- 结果确认：
  - `execution.candidate_ids = ["p2-fp2n1"]`
  - `download_selection_count = 0`
  - `mismatch_selection_count = 1`
  - 说明小样本选择已经不依赖 offset。

新增/扩展回归测试：
- `test_pdf_next_stage_filters_selection_by_candidate_and_footnote`
- 扩展 `test_fullrun_next_stage_respects_restricted_download_flag`：确认 fullrun 透传 candidate/footnote。
- `test_volume_series_generic_compound_packet_uses_query_buckets`：确认 `document_heading + person` 可生成通用 packet，并覆盖 required facets。

验证：
- targeted tests 通过。
- 完整单测通过：`200 tests OK (skipped=5)`。

下一步：
- 用 `--candidate-id` 精确复跑三类史料中的另外两类样本：
  - `原敬日記`：确认 diary 路径没有受 volume_series packet 影响；
  - `山縣有朋意見書`：确认 contained_document 路径仍按 host/contained PID 逻辑走。
- 然后用精确参数分别复跑外交论文中的一个巴黎讲和/华盛顿会议样本，观察通用 `volume_series_query_bucket_compound_claim` 是否实际进入报告；若没有进入，说明 resolver bucket 还需要把人物/日期/主题词拆得更稳定。
- 全量前保留本轮 smoke output 和 p2n1 augmented output 作为回归基准。

## 35. 2026-05-02 三类史料精确复测与 contained title-only 降级

精确复测结果：
- `原敬日記`：
  - 输出目录：`output/historical_citation_next_stage_three_source_types_20260502_exact_hara_diary`。
  - 使用 `--candidate-id p4-fp4n1`。
  - `execution.candidate_ids = ["p4-fp4n1"]`，`mismatch_selection_count = 1`。
  - source graph 仍为 `diary`，最终状态为 `fulltext_lead_only`。
  - 未生成 `fulltext_compound_evidence_packet`，说明 volume_series packet 未误侵入 diary 路径。
- `山縣有朋意見書`：
  - 第一轮精确复测输出：`output/historical_citation_next_stage_three_source_types_20260502_exact_yamagata_contained`。
  - source graph 为 `contained_document`，严格 PID 为 `3025431`。
  - 发现问题：全文候选虽然进入了 PID，但 Top contexts 主要是 `山縣有朋意見書` 题名串联或目录/前言附近内容；claim terms 没有命中，`specific_hits=0`。
  - 旧逻辑把这类片段标为 `body_candidate`，随后 Gemma 判 `not_supported`。语义上更准确的状态应是 `fulltext_lead_only`，因为它只是题名线索，不应进入正式精核。

已完成的修正：
- `contained_document` 的全文 lead category 新增降级规则：
  - 若上下文只命中 `contained_title` / title；
  - 且没有 substantive core terms；
  - 且没有 claim snippet evidence；
  - 则标为 `title_or_series_only`，不再视为正文候选。
- `title_like_terms` 纳入 `contained_title`，避免析出题名本身被当成实质证据。

修正后复测：
- 输出目录：`output/historical_citation_next_stage_three_source_types_20260502_exact_yamagata_contained_titlelead`。
- 结果从 `fulltext_only_not_supported` 改为 `fulltext_lead_only`。
- Top contexts 均显示 `title_or_series_only`，并带有 `title_or_series_only_penalty`。
- `进入 LLM 精核 = 0`，避免让 Gemma 对题名线索做最终否定。

新增回归测试：
- `test_contained_document_title_only_fulltext_hit_is_lead`

验证：
- targeted tests 通过。
- 完整单测通过：`201 tests OK (skipped=5)`。

下一步：
- `山縣有朋意見書` 的真正改进不应是强行精核题名线索，而是增强 contained_document 的 claim-term 定位：
  - 使用脚注页码 `306` 和 known PID `3025431`，优先尝试页窗/全文 JSON 的页码附近定位；
  - 对中文 claim 生成更可靠的日文历史关键词，例如 `日本ト俄國`、`滿洲`、`東三省`、`共同經營`、`復仇心`、`親密`；
  - 若 claim terms 无命中，报告保持 `fulltext_lead_only` 并显示“题名命中但主张未定位”的下一步人工检索路径。
- 继续用 `--candidate-id` 精确复跑巴黎讲和/华盛顿会议样本，观察通用 `volume_series_query_bucket_compound_claim` 在真实报告中的触发情况。

## 36. 2026-05-03 巴黎讲和 / 华盛顿会议精确复测与 formal review 防退化

本轮继续只使用三类史料小样本中的 `volume_series` 路径，不扩大到全量。重点检查用户指出的两个问题：一是全文多命中时容易只取第一个命中，二是 Gemma 未完成时启发式结果不应伪装成正式 direct。

巴黎讲和样本 `p4n5`：
- 第一轮输出：`output/historical_citation_next_stage_gaiko_paris_p4n5_exact_20260502`。
- 发现问题：通用 compound packet 把 `1971年` 这样的出版年误提升为 required date facet，导致证据包“不完整”，实际不应把现代刊行年当成文书事实日期。
- 已修正：generic volume_series packet 只在日期含月/日时提升为 required date；纯出版年不再作为 required facet。
- 修正后输出：`output/historical_citation_next_stage_gaiko_paris_p4n5_exact_pubyear_fix_20260502`。
- 当前结果：`fulltext_only_partial_support`，Gemma `gemma4:e4b` 正式精核成功，置信度约 0.8。
- 内容判断：上下文已命中第 9 页 `帝國主張説明(牧野男)` 等正文线索，但还没有明确覆盖论文主张中的“接受会议决定/达成目标”这一动作层。因此 partial 是保守且合理的，不应强行升为 direct。

华盛顿会议样本 `p6n6`：
- 初始问题：Top contexts 被 `海軍軍備制限問題` 等前置命中占满，`ヒューズ`、`比率`、`主力艦比率`、`六割` 等更关键片段没有稳定进入并列候选。
- 已修正：
  - `volume_series` 全文扩搜上限从 6 提高到 8；
  - 新增 query diversity，避免第一个查询独占 Top N；
  - resolver 增加华盛顿会议军备限制词组，如 `ヒューズ國務長官`、`主力艦比率`、`十對六`、`六割`；
  - 新增 `volume_series_washington_naval_limitation_compound_claim`，把军备限制议题、Hughes/美国发言者、主力舰比例拆成 required facets。
- 输出目录：`output/historical_citation_next_stage_gaiko_washington_p6n6_packet_gemma600_20260502`。
- 当前结果：`fulltext_only_partial_support`，Gemma `gemma4:e4b` 正式精核成功，`review_timeout_seconds=600`。
- 复合证据包：`complete=True`，已覆盖 `naval_limitation_proposal`、`hughes_or_us_speaker`、`capital_ship_ratio`。
- 内容判断：证据包能说明“华盛顿会议/海军军备限制/Hughes/比例”方向，但现有并列上下文没有明确给出论文句子所需的精确 `10:10:6` 关系。因此 Gemma 判 partial 是合理结果，应列入人工复核或继续扩搜，而不是升为 direct。

formal review 防退化：
- 曾出现 `review_timeout_seconds=300` 时 Gemma 超时，启发式 fallback 给出 direct 的情况。
- 已修正：若 `llm_review_failed=True` 且 `llm_review_fallback_heuristic=True`，启发式 direct 不得晋升为正式 `fulltext_only_direct_support`。
- 现在会降级为 `fulltext_only_partial_support`，并记录 `formal_review_failed_direct_downgraded` / `formal_review_failed_heuristic_direct_not_promoted`，避免报告把模型超时后的启发式判断写成正式精核结论。

新增/扩展回归测试：
- `test_volume_series_generic_packet_does_not_require_publication_year`
- `test_volume_series_hint_expansion_diversifies_queries`
- `test_washington_naval_limitation_packet_groups_ratio_and_speaker`
- `test_failed_formal_review_does_not_promote_heuristic_direct_support`

验证：
- targeted tests 通过：5 tests OK。
- 完整 `tests.test_historical_citation_verifier` 通过：`205 tests OK (skipped=5)`。

下一步：
- `p6n6` 若要从 partial 推进到 direct，不能只继续扩大泛化上下文，而要专门寻找精确比例句：优先查询 `十対六`、`十對六`、`米国案ノ十対六`、`米國案ノ十對六`、`主力艦比率` 以及第 160-170 页附近的相邻页。
- `p4n5` 若要从 partial 推进到 direct，应补充动作/结果层关键词，如 `決定`、`受諾`、`目的`、`講和會議`、`帝國主張`、`牧野` 的组合，并继续避免让题名页、刊记页或卷册标题页覆盖正文页。
- 在进入两篇论文全量前，保持 exact selection + Gemma formal review 作为小样本回归入口；任何正式 direct 必须来自 Gemma 成功或可解释的 OCR/全文强证据，不得来自 timeout 后的启发式 fallback。

## 37. 2026-05-03 strict PID 注入、p6n6 direct 修复与 p4n5 主题收紧

本轮新增发现：
- 完整 diplomacy combined 中，`p6n6` 并不总是走 `source_mismatch_recheck`；有时会先进入 `source_found` 的下载/OCR 分支。
- 该分支如果候选中只有全站全文 lead，而没有 resolver strict PID match，会在 `target_pid_probe_skipped_non_equivalent_fulltext_lead` 后退回错误卷册或泛化 `日本外交文書 1974年` 命中。
- 这说明 strict PID 修复不能只放在 mismatch recheck，也必须覆盖 source_found/download 路径。

已完成修正：
- `_rerank_matches_for_candidate_fulltext` 在 resolver/source graph 已给出 strict PID、但当前 `ndl_matches` 没有任何 strict PID 时，自动注入首个 strict PID 候选。
- 注入仅限“没有 strict PID 候选”的情况；若已有 strict PID，不再额外注入同组其它 known PID，避免扩大下载面。
- `volume_series` 扩搜新增 critical hint group：
  - 华盛顿会议精确比例：`米国案ノ十対六`、`十対六`、`十對六` 等；
  - Hughes 发言者；
  - 海军军备限制主题；
  - 巴黎讲和的南洋/委任统治/会议决定组；
  - 牧野相关组。
- 华盛顿会议 packet 拆出 `exact_ten_ten_six_ratio` required facet。若论文句子写明 `10:10:6`，只有泛化 `比率` 不再足够。
- 巴黎讲和 resolver 收紧：
  - 南洋/委任统治词只在 claim 本身涉及赤道、南洋、太平洋、委任、托管、既定目标时加入；
  - 山东/膠州/還附词只在 claim 本身涉及山东、胶州或归还时加入；
  - 避免 `p4n5` 被山东相关页误带偏。

真实小样本结果：
- `p6n6` 完整 combined source_found 路径复跑：
  - 输出目录：`output/historical_citation_next_stage_gaiko_washington_p6n6_exact_ratio_strict_sourcefound_20260503`。
  - strict PID 自动注入：`11927523`。
  - Top contexts 包含第 143 页 `米国案ノ十対六ノ比率`。
  - packet：`volume_series_washington_naval_limitation_compound_claim`，`complete=True`。
  - Gemma `gemma4:e4b` 正式精核成功，判定 `fulltext_only_direct_support`，confidence `0.95`。
- `p4n5` 主题收紧后复跑：
  - 输出目录：`output/historical_citation_next_stage_gaiko_paris_p4n5_mandate_focused_20260503`。
  - Top contexts 转向第 32/39/178 页的 `独領南洋`、`赤道以北`、`委任統治`、牧野内谈。
  - 山东/還附片段下降为次要候选，不再压过南洋委任统治上下文。
  - Gemma 仍判 `fulltext_only_partial_support`。原因是当前上下文能支持“南洋/委任统治/牧野相关讨论”，但没有直接说明“牧野决定接受会议决定并达成第一个目标”。这应视为内容证据缺口，而不是流程失败。
- 非 volume_series 回归：
  - `原敬日記`：`output/historical_citation_next_stage_three_source_types_20260503_hara_diary_regression`，仍为 `fulltext_lead_only`，未误触发 packet。
  - `山縣有朋意見書`：`output/historical_citation_next_stage_three_source_types_20260503_yamagata_contained_regression`，仍为 `fulltext_lead_only`，未误触发 packet。

新增/扩展回归测试：
- `test_strict_resolver_injects_known_pid_when_only_fulltext_lead_exists`
- `test_washington_exact_ratio_packet_incomplete_without_exact_ratio`
- 扩展 `test_washington_naval_limitation_packet_groups_ratio_and_speaker`
- 扩展 `test_volume_series_hint_expansion_diversifies_queries`
- 扩展 `test_source_resolver_maps_paris_peace_supplement_pid`

验证：
- targeted tests 通过。
- 完整 `tests.test_historical_citation_verifier` 通过：`207 tests OK (skipped=5)`。

下一步：
- 两篇论文全量前，优先把这轮 source_found strict PID 注入逻辑用于全量 runner 的 retry/resume 场景，重点观察外交论文中原先 `source_found + fulltext_lead_only` 的条目是否回到 strict PID。
- `p4n5` 不应硬升 direct。后续若要继续尝试，应定位“牧野接受会议决定/南洋委任统治确定”这类更精确日文动作句；若 PID 内仍找不到，则报告应保持 partial 并把“缺直接动作句”写入人工检索建议。
- 对 `diary` / `contained_document`，strict PID 注入当前只改善候选入口，不改变证据等级；下一步仍应分别开发日期页窗和析出文献 claim-term 定位。

## 38. 2026-05-03 第38卷第1册卷册误判与桂-塔夫脱小样本修复

外交论文全量 next-stage 重跑时发现新问题：
- `p2n3` 脚注明确是《日本外交文書》第38卷第1册，第450-452页。
- 旧 PDF combined JSON 中 `ndl_keyword` 残留了错误的 `第1巻/明治1年`，原因是 parser 过去把 `第1册` 也派生成卷号。
- 这导致全站 query 一度变成 `日本外交文書 第1巻 1905年`，并引入错误卷册、错误图书，最终在重下载/OCR 阶段退化为 `fulltext_only_not_supported`。

已完成修正：
- `extract_volume_terms` 区分卷/巻与册/冊：
  - `第38卷` 生成 `第38巻/第三十八巻/明治38年`；
  - `第1册` 只保留 `第1冊/第1册`，不再生成 `第1巻/明治1年`。
- 为兼容旧 combined JSON，若同一文本中出现 `第38卷第1册` 这类卷册成对结构，会过滤册号派生出的伪卷号。
- `nihon_gaiko_bunsho` resolver 配置新增第38卷第1册映射：
  - `3448160`：优先 PID，NDL 全文命中 `桂「タフト」了解 THE TAFT-KATSURA AGREEMENT`；
  - `2530367`：同卷备用 PID，用于南满洲铁路/满铁相关上下文。
- 外交文書 claim-term 扩展新增：
  - 中文触发词：`塔夫脱`、`哈里曼`、`南满铁路`、`共同管理`、`桂太郎`；
  - 日文/历史 OCR 查询词：`タフト`、`タフト陸軍長官`、`桂・タフト`、`桂・タフト協定`、`ハリマン`、`満鉄`、`南満洲鉄道`、`共同経営` 等。
- `volume_series` critical hint group 新增 `gaiko_katsura_taft_harriman`，保证 `タフト/ハリマン/南満洲鉄道` 这类核心命中能并列扩搜，而不是只扩日期页或目录页。

真实小样本结果：
- 卷册修复检索样本：
  - 输出目录：`output/historical_citation_next_stage_gaiko_p2n3_pid3448160_20260503`。
  - known PID 顺序：`3448160,2530367`。
  - 首位 query：`日本外交文書 第38巻 桂・タフト`。
  - Top hint 明确含 `THE TAFT-KATSURA AGREEMENT`。
- 完整扩搜/Gemma 样本：
  - 输出目录：`output/historical_citation_next_stage_gaiko_p2n3_pid3448160_download_20260503`。
  - 最终状态：`fulltext_only_direct_support`。
  - Gemma `gemma4:e4b` 正式精核成功，选择 `ctx3`。
  - exact sentence：`比島、極東ノ平和、韓國ノ諸問題ニ關スル桂「タフト」了解 THE TAFT-KATSURA AGREEMENT.`

同时确认：
- 之前一度怀疑 `p2n3` citation unit 过宽。重新解析 PDF 后发现 parser 当前能稳定给出 `p2n3` 的近邻句，即“桂太郎与塔夫脱达成桂塔夫脱备忘录...”，因此本轮核心问题不是 claim 切分，而是旧卷册派生残留和 strict PID 过窄。
- `2530367` 不应作为唯一 strict PID；否则会排除真正命中桂-塔夫脱正文的 `3448160`。

新增/扩展回归测试：
- `test_footnote_parser_keeps_gaiko_volume_ahead_of_fascicle`
- `test_gaiko_claim_fulltext_recheck_translates_katsura_taft_harriman_terms`

验证：
- targeted tests 通过。

下一步：
- 重跑外交论文全量 next-stage 时，重点观察：
  - `p2n3` 是否保持 `fulltext_only_direct_support`；
  - 第38卷第1册相邻条目是否不再出现 `第1巻` lead；
  - `p6n6` 是否继续保持 `fulltext_only_direct_support`；
  - `p4n5` 是否保持合理 partial，而不是被山东/题名页带偏。
- 若全量仍有 `日本外交文書` 误判，继续把卷册 PID 配置升级为“同卷多版本 PID 组”：每个 PID 标明适合的文书题名/页段/主题词，而不是一卷只保留一个 strict PID。

## 39. 2026-05-03 外交论文全量 next-stage 重跑结果

本轮在卷/册解析、strict PID 注入、桂-塔夫脱/哈里曼查询扩展之后，重跑外交论文全量 next-stage：
- 输出目录：`output/historical_citation_next_stage_fullrun_20260503_post_volume_fascicle_fix/diplomacy`。
- 外层 shell 等待超过 2 小时后超时，但子进程继续运行并正常写出最终 `next_stage_refinement.json` 和报告。
- 模块内部 `timeout_events` 为空；`slow_events` 为 19。说明这轮主要问题不再是失败型 timeout，而是全量耗时仍偏高。

状态概览：
- `download_ocr_alignment`：23 条，其中 direct 4、partial 4、not_supported 6、lead_only 9。
- `rechecked_download_ocr_alignment`：9 条，其中 direct 1、partial 3、not_supported 4、lead_only 1。
- `source_mismatch_recheck`：12 条，其中 source_found 9、source_mismatch 3。

关键回归项：
- `p2n3` 桂-塔夫脱：保持 `fulltext_only_direct_support`，PID `3448160`，matched page 231，Gemma `gemma4:e4b` 选择 `ctx3`，exact sentence 为 `桂「タフト」了解 THE TAFT-KATSURA AGREEMENT`。
- `p6n6` 华盛顿会议 10:10:6：保持 `fulltext_only_direct_support`，matched page 143，Gemma `gemma4:e4b` 确认 `米国案ノ十対六ノ比率`。
- `p4n5` 巴黎讲和/南洋委任统治：保持 `fulltext_only_partial_support`。Gemma 判断现有上下文能支持牧野、南洋、委任统治相关讨论，但不能直接支持“接受会议决定并达成第一个目标”。这应继续作为证据缺口，而不是强行升 direct。

仍需处理的问题：
- 旧 combined JSON 中部分展示字段仍残留过时 `ndl_keyword`，例如 `第38卷第1册` 的显示串里还可见 `第1巻`。当前 source graph 已能过滤该伪卷号并走正确 PID，但报告可读性上仍容易误导，后续应让 next-stage 刷新结构化脚注时同步覆盖展示用 `ndl_keyword`。
- 剩余 `source_mismatch` 主要不是 `日本外交文書` 卷册 resolver 本身：
  - `p4n4` 更接近亚洲历史资料中心/JACAR Ref 路径；
  - `p6n1` 为《翠雨庄日记：临时外交调查委员会会议笔记等》一类现代整理材料；
  - `p8n3` 为现代中文研究书。它们需要按非 NDL Digital 原始史料路径分层报告。
- 仍有 10 条左右 `fulltext_lead_only` 和 10 条左右 `fulltext_only_not_supported`。下一步不能简单扩大泛搜，应继续把 `日本外交文書` 的 resolver 升级为“卷册 PID + 文书题名/人物/主题词/page bucket”的分层 query bucket。

下一步：
- 宗教论文全量复跑后，对照观察《日本近代思想大系 5：宗教と国家》、`帝国憲法義解・皇室典範義解`、神宫大麻相关条目是否存在类似的展示字段残留、PID 版本漂移或上下文扩搜停止过早问题。
- 将“外层命令超时但内部正常完成”的情况纳入 batch runner/finalizer 设计：全量运行应按阶段写心跳、最终自动汇总 partial/final，并在报告里区分处理历史和当前最终状态。

## 40. 2026-05-03 宗教论文全量复跑、大麻条目退化与目录命中降权

本轮在卷/册解析、strict PID 注入和外交文書查询扩展之后，重跑宗教论文全量 next-stage：
- 输出目录：`output/historical_citation_next_stage_fullrun_20260503_post_volume_fascicle_fix/religion`。
- `download_ocr_alignment`：34 条，其中 direct 6、partial 9、not_supported 16、lead_only 3。
- `rechecked_download_ocr_alignment`：1 条，not_supported 1。
- `source_mismatch_recheck`：2 条，其中 source_found 1、source_mismatch 1。
- `slow_events`：1 条，集中在 `p4n8` 〈日新新聞〉第二七号の記事，说明该条更像非 NDL Digital / 报刊路径问题，而不是主流程 timeout。

正向结果：
- 《帝国憲法義解・皇室典範義解》`p3n1` 保持 `fulltext_only_direct_support`，PID 能回到 `1272168`，matched page 39，Gemma `gemma4:e4b` 正式精核成功。
- 《日本近代思想大系 5：宗教と国家》内的部分条目能稳定进入 host PID 内上下文，例如 `p2n3` page 28、`p5n1` page 291。
- 《諸宗説教要義》相关条目 `p6n4/p6n5` 保持 direct，说明 source_collection / host 内全文路径没有整体退化。

新增发现：
- `p4n5` 奈良県大麻问题在本轮全量中一度退化为 `fulltext_only_not_supported`。原因不是 PID 错误，而是目标 PID 内全文命中首先返回目录/解题页；旧评分把长题名命中和过宽动作词 `焼` 当成强证据，导致目录页压过正文页。
- `p4n9` 静岡県大麻流言在本轮全量中只到 `fulltext_only_partial_support`。原因是上下文扩搜在 page 102/103 附近停得过早，没有稳定把 `大麻ノ神ノ字ガ蝶ニ化スル`、`時疫ニ死絶`、`水火ニ投ズル` 等核心句纳入同一高分候选。
- `source_collection` 和 `contained_document` 在证据评价上应当一致处理：只命中析出题名、目录页、索引页，不能直接作为正文证据。
- 旧 combined JSON 中若 `ndl_keyword` 残留过时结构，报告展示字段仍可能误导。next-stage 在重新解析脚注后必须覆盖 stale `ndl_keyword`，而不是只在内部 source graph 使用新结构。

已完成修正：
- 神宫大麻类 claim 查询新增日文/历史 OCR 变体：
  - `伊勢皇大神宮大麻`、`伊勢皇太神ノ大麻`、`皇大神宮大麻`、`神宮大麻`、`神棚ヲ不設`、`従前宗門ニ寄、神棚ヲ不設`；
  - `玉串ヲ焼捨`、`河流ニ投ジ`、`大麻ヲ水火ニ投ズ`、`大麻ノ神ノ字ガ蝶`、`蝶ニ化スル`、`時疫`、`妄伝浮説` 等。
- fulltext hint 分类中将 `source_collection` 按 `contained_document` 同等处理；长题名/析出题名命中若缺少 substantive core terms，降为 `title_or_series_only`。
- 新增目录/索引页识别：当上下文出现大量 `（一〇二）`、`(102)` 这类目录页码标记时，标为 `toc_or_index`，不得压过正文命中。
- 收窄动作词：不再把单字 `焼` 作为强动作词，改为 `焼捨`、`焼捨て`、`焼却` 等更具体词，避免目录中无关条目误提权。
- next-stage 重新结构化脚注时，若解析出更可靠的 source signals / volume hints，会覆盖旧 `ndl_keyword`，并记录 `pdf_next_stage_ndl_keyword_refreshed`。

真实小样本回归：
- 输出目录：`output/historical_citation_next_stage_religion_taima_regression_fix_20260503`。
- `p4n5` 修复后回到 `fulltext_only_direct_support`，matched page 100。证据句包含 `従前宗門ニ寄、神棚ヲ不設、神宮大麻等不受者共モ有之候`，Gemma 判断直接支持“真宗信徒不设神棚、不接受神宫大麻”。
- `p4n9` 修复后回到 `fulltext_only_direct_support`，matched page 103。证据句包含 `大麻ノ神ノ字ガ蝶ニ化スル`、`時疫ニ死絶` 等核心信息，Gemma 判断直接支持流言内容。

新增/扩展回归测试：
- `test_claim_fulltext_recheck_translates_shingu_taima_terms`
- `test_source_collection_toc_hit_is_not_body_evidence`
- `test_pdf_next_stage_refresh_replaces_stale_ndl_keyword`

验证：
- targeted tests 通过。
- 完整 `tests.test_historical_citation_verifier` 通过：`212 tests OK (skipped=5)`。

下一步：
- 重跑宗教论文全量 next-stage，确认 `p4n5/p4n9` 在全量环境下也保持 direct，并观察目录降权是否影响其它 source_collection 条目。
- 对 `p3n2` 这类同源《帝国憲法義解・皇室典範義解》条目，复用已确认 PID `1272168` 和页映射缓存，避免同一 source 的相邻脚注一条 direct、一条 lead_only。
- 对 `p4n8` 〈日新新聞〉第二七号の記事，后续应按 periodical / non-NDL Digital source path 单独建 resolver，而不是继续让 NDL Digital 图书流程耗时扩搜。

## 41. 2026-05-03 target PID query 优先级与《帝国憲法義解》同源相邻条目修复

宗教论文复核时发现：
- `p3n1`《帝国憲法義解・皇室典範義解》已经能进入 PID `1272168`，并在 matched page 39 上得到 direct。
- 但同源同页附近的 `p3n2` 仍为 `fulltext_lead_only`，只命中题名页。
- 新增“政权/教权/疆域”日文查询后，小样本仍未改善。进一步查看 probe 记录发现，target PID 探测只取前 10 个 query，而《帝国憲法義解・皇室典範義解》的题名变体过多，quote-level claim 日文词被挤到查询额度之外。

已完成修正：
- `_probe_target_pid_fulltext_hints` 改为分层排序 query：
  - 先保留少量 source-title anchor；
  - 再优先放 resolver query bucket、人物/文书题名/page-near 和 claim fulltext queries；
  - 最后才追加剩余题名变体和普通脚注关键词。
- 对 strict known PID 的目标探测，query limit 从 10 提升到 24，避免在已经锁定 PID 的情况下因题名变体过多而漏掉正文 claim 查询。
- 《帝国憲法義解》claim 查询新增：
  - 触发词：`政权/政權`、`教权/教權`、`相互界定`、`疆域`、`宪法所裁定` 等；
  - 日文/OCR 查询：`政權ト教權`、`政権ト教権`、`相分界スルノ域`、`憲法ノ裁定スル所`、`憲法ノ認定スル所` 等。
- core action terms 同步加入 `政權ト教權`、`相分界`、`憲法ノ裁定スル所`，让这些命中在多候选排序中压过题名页。

真实小样本结果：
- 输出目录：`output/historical_citation_next_stage_religion_gikai_boundary_p3n2_query_priority_20260503`。
- `p3n2` 从 `fulltext_lead_only` 升为 `fulltext_only_direct_support`。
- matched page 39，Gemma `gemma4:e4b` 正式精核成功。
- 证据上下文包含 `此レ憲法ノ裁定スル所ニシテ...界域ナリ`，直接对应论文句子“此乃宪法所裁定之准则，亦为政权与教权相互界定之疆域”。

新增回归测试：
- `test_claim_fulltext_recheck_translates_imperial_gikai_boundary_terms`

下一步：
- 宗教论文全量重跑时重点确认：
  - `p3n1/p3n2` 都保持 direct；
  - `p4n5/p4n9` 仍保持 direct；
  - query 优先级调整没有让其它 source_collection 条目被过度 claim 化。
- 如果全量耗时显著增加，再把 strict PID 的 24 query limit 与磁盘 cache 结合，避免 resume 时重复探测相同 PID/query。

## 42. 2026-05-03 神宫大麻子类型拆分与同源不同析出条目排序修复

三条宗教核心回归一起跑时发现：
- `p4n5`、`p4n9` 单独跑都能 direct。
- 但与 `p4n5` 同批时，`p4n9` 一度退回 partial，并错误选择了 page 100 的“神棚ヲ不設 / 神宮大麻等不受者”上下文。
- 查看 fulltext hints 可见，`p4n9` 的正确 page 103 命中其实已经存在，包括 `大麻ノ神ノ字ガ蝶`、`時疫`、`水火ニ投ズル`。失败原因是“大麻”作为过宽类型同时触发了“神棚/不受大麻”和“流言/蝶化/水火投弃”两组词，排序把更长的 page 100 查询提到了前面。

已完成修正：
- 将神宫大麻相关查询拆成两个可复用子类型：
  - `taima_acceptance/shrine_shelf`：`伊勢皇大神宮大麻`、`皇大神宮大麻`、`神棚ヲ不設`、`神宮大麻等`、`宗門ニ寄、神棚ヲ不設`；
  - `taima_rumor/disposal`：`伊勢皇太神ノ大麻`、`大麻ヲ水火ニ投ズ`、`玉串ヲ焼捨`、`河流ニ投ジ`、`大麻ノ神ノ字ガ蝶`、`蝶ニ化スル`、`時疫`、`妄伝浮説`。
- `_fulltext_core_action_terms` 不再只要看到“大麻”就加入所有相关词；而是按 claim focus 判断：
  - claim 涉及不设神棚/不受大麻/土真宗时，加入 `神棚`、`宗門`、`神宮大麻等`、`不受者`；
  - claim 涉及流言/蝴蝶/时疫/焚毁/冲走/水火时，加入 `流言`、`妄伝`、`水火`、`焼捨`、`河流`、`時疫`、`蝶`、`死絶`；
  - 无明确 focus 时才保留宽泛 fallback。

真实小样本回归：
- 输出目录：`output/historical_citation_next_stage_religion_core_regression_taima_split_20260503`。
- `p3n2`：`fulltext_only_direct_support`，matched page 39。
- `p4n5`：`fulltext_only_direct_support`，matched page 100，命中 `神棚ヲ不設`、`神宮大麻等不受者`。
- `p4n9`：`fulltext_only_direct_support`，matched page 103，命中 `大麻ノ神ノ字ガ蝶ニ化スル`、`挙家時疫ニ死絶`。

新增回归测试：
- `test_claim_fulltext_recheck_keeps_taima_rumor_terms_distinct`

下一步：
- 宗教论文全量重跑时，重点观察同一 host PID 内不同 contained title 是否还能稳定各取自己的正文上下文。
- 若其它 source_collection 也出现“同主词、不同事件”的误排序，应按同样方式继续把 claim focus 拆成子类型，而不是增加更大的通用词表。

## 43. 2026-05-03 析出题名正文识别、PDF 页眉 claim 修复与神田神社回归

宗教论文全量刷新后新增发现：
- 核心修复有效：`p3n2`、`p4n5`、`p4n6`、`p4n9` 在全量中保持 direct。
- 但 `p4n3`、`p5n1` 一度退成 `fulltext_lead_only`。进一步检查发现，NDL 已经给出了正确 PID 内命中，但模块把“析出题名 + 正文开头”误判为 `title_or_series_only`，导致正文扩展没有展开。
- `p5n1` 另有 PDF claim 切分问题：论文页眉 `宗教世界 文化2026 年第2期 THE WORLD RELIGIOUS CULTURES` 被拼进 citation unit，系统据此搜索 `2026 年`，LLM 也在核查页眉碎片。

已完成修正：
- `source_collection/contained_document` 的全文命中分类调整：
  - TOC/索引页仍优先识别并降权；
  - 如果析出题名之后紧接足够正文，则标为 `body_candidate`，允许扩展；
  - 如果题名位于片段末尾、之后没有正文，例如《山縣有朋意見書》题名 lead，仍保持 `title_or_series_only`。
- next-stage 入口新增 PDF running header claim repair：
  - 移除 `宗教世界 文化YYYY年第N期 THE WORLD RELIGIOUS CULTURES` 这类页眉；
  - 若移除后只剩短的断裂引文尾巴，则追加 `following_unfootnoted_context` 的第一句，避免把页眉当成论文侧 claim。
- 神田神社类 claim 查询新增日文/历史词：
  - `平将門`、`神田神社`、`神田明神`、`神田祭`、`祭神ノ座`、`摂社/攝社`、`朝廷に対する反逆者` 等。

真实小样本结果：
- 输出目录：`output/historical_citation_next_stage_religion_pdf_claim_repair_20260503`。
- `p5n1` 从 lead/partial 回到 `fulltext_only_direct_support`，matched page 104。query 不再是 `2026 年`，而是 `神田神社の祭神問題`、`平将門` 等。
- `p4n3` 能稳定进入 page 102 正文，但 Gemma `gemma4:e4b` 判 `fulltext_only_not_supported`。该上下文谈固定金额、每年初穗等，并未支持论文句子中的“纳金没有定额 / 敬神税”，因此保留 not_supported 更合理。
- 核心四项同批小样本 `p3n2/p4n5/p4n9/p5n1` 全部 direct。

新增/扩展回归测试：
- `test_source_collection_contained_title_with_body_text_is_expandable`
- `test_pdf_next_stage_repairs_running_header_orphaned_claim`
- 扩展 `test_contained_document_title_only_fulltext_hit_is_lead` 边界保护。

验证：
- 完整 `tests.test_historical_citation_verifier` 通过：`216 tests OK (skipped=5)`。

下一步：
- 用当前修复重新刷新宗教论文全量报告，使最终报告包含 `p5n1` 的页眉修复结果。
- 之后再对外交论文做一次小范围回归，确认 contained-title body 规则没有把《山縣有朋意見書》这类 title lead 误升为正文证据。

## 44. 2026-05-03 claim 查询优先级退化修复：防止题名正文命中挤出精确引文

宗教论文全量刷新后新增退化：
- `p6n5`《諸宗説教要義》在旧版曾为 `fulltext_only_direct_support`，但当前全量中退为 `fulltext_only_not_supported`。
- 人工检查发现，NDL 已经返回了正确命中：`阴不害阳`、`恶不妨善` 两个 query 都定位到 PID `12223083` 的 page 140，snippet 含 `只中和ヲ得ハ陰不害陽惡不妨善`。
- 失败原因不是源获取，而是 top N 上下文选择：题名 query `諸宗説教要義` 的正文页因为命中了 contained title，被排在前三；真正由 claim/译文 query 触发的 page 140 上下文没有进入 Gemma 精核候选。

已完成修正：
- `_hint_has_claim_snippet_evidence` 新增“claim-origin query”规则：
  - 若 hit 的 `query` 与 `_claim_fulltext_queries(candidate)` 中的非题名、非合集、非泛化卷册 query 完全一致，则视为 claim evidence；
  - 即使简体中文 query 与旧字日文 snippet 不能通过普通 normalize 直接相含，也不再丢失其 claim 证据身份；
  - 仍排除书名、host title、contained title、`日本外交文書`、`日本近代思想大系` 等 title-like terms，避免把题名查询误升为 claim。
- 该规则适用于 `contained_document/source_collection/volume_series/diary` 等所有类型，不绑定 `p6n5` 或固定 PID。
- 排序结果中 claim-origin hit 会获得 `_fulltext_hint_specificity_score` 的 claim bonus，从而优先进入多候选扩搜和 Gemma 精核。

真实小样本回归：
- 输出目录：`output/historical_citation_next_stage_religion_p6n5_claim_query_priority_20260503`。
- `p6n5` 修复后回到 `fulltext_only_direct_support`，matched page 140。
- top contexts：
  - `ctx1` query=`阴不害阳`，score=`8.1389`，`claim_evidence=true`；
  - `ctx2` query=`恶不妨善`，score=`8.1389`，`claim_evidence=true`；
  - `ctx3` query=`諸宗説教要義`，score=`5.2333`，`claim_evidence=false`。
- Gemma `gemma4:e4b` 选择 `ctx1`，exact sentence 为 `只中和ヲ得ハ陰不害陽惡不妨善`。

新增回归测试：
- `test_claim_query_hit_is_prioritized_over_contained_title_body_hit`

验证：
- targeted test 通过。
- 完整 `tests.test_historical_citation_verifier` 通过：`217 tests OK (skipped=5)`。

全量刷新记录：
- 输出目录：`output/historical_citation_next_stage_fullrun_20260503_religion_claim_repair_final`。
- 该轮在本修复前启动，因此仍记录 `p6n5=fulltext_only_not_supported`；修复后的小样本已证明这是排序退化，不是内容失败。
- 全量汇总：37 条结果，`fulltext_only_direct_support=11`、`fulltext_only_partial_support=7`、`fulltext_only_not_supported=11`、`fulltext_lead_only=6`、`source_found=1`、`source_mismatch=1`，slow events=3。

下一步：
- 若需要正式宗教全量报告，应基于当前代码再刷新一轮，至少确认 `p6n5` 被纳入 direct 后的汇总。
- 对外交论文继续沿用这一规则，重点检查：claim/person/document-title query 是否能压过 `日本外交文書` 题名/目录命中；若仍误判，再把 specific_targets 从静态词表升级为文书题名级 query bucket。

## 45. 2026-05-03 外交小回归：claim-origin 规则的泛化短语降权

外交论文三类小回归：
- 输出目录：`output/historical_citation_next_stage_diplomacy_claim_query_priority_regression_20260503`。
- `p2n8`《山縣有朋意見書》保持 `fulltext_lead_only`。三个候选均为 `title_or_series_only`，没有被第 43 节的“析出题名 + 正文开头”规则误升，说明边界保护有效。
- `p6n6`《日本外交文書》华盛顿会议军备限制问题保持 `fulltext_only_direct_support`，matched page 143。Gemma 选择含 `米国案ノ十対六`、`十対六`、`比率` 的上下文，证明多候选并列扩搜对外交文书仍有效。
- `p4n5`《日本外交文書》巴黎讲和会议经过概要仍为 `fulltext_only_partial_support`。候选中已经出现 `牧野男`、`委任統治`、`赤道以北`、`獨領南洋`、`會議ノ決定` 等，但 Gemma 判断尚不能直接支持“牧野决定接受会议决定并实现第一目标”的完整链条。

新增问题：
- 第 44 节的 claim-origin query 规则如果不加边界，会把 `會議ノ決定` 这类泛化短语也标为强 claim evidence。
- `p4n5` 中该 query 命中的 page 255 实际是投票权/敌国债务议题，不属于南洋委任统治核心段落。虽然 Gemma 没有误判，但排序层面给了过高分，后续可能扩大外交误判。

已完成修正：
- 新增 `_generic_fulltext_claim_terms`，将以下短语视为泛化 claim query：`会議/會議`、`会議ノ決定/會議ノ決定`、`会议决定`、`決定/决定`、`方針`、`政策`、`提案`、`提議` 等。
- `_hint_has_claim_snippet_evidence` 中，claim-origin query 若属于泛化短语，不再直接获得 claim evidence 身份。
- `_score_fulltext_context_candidate` 的 core term 计算也过滤这些泛化短语，避免 `core_terms=会議ノ決定` 抬高无关会议段落。
- 精确 claim query 不受影响：`p6n5` 的 `阴不害阳/恶不妨善` 仍优先进入 top contexts 并保持 direct。

新增回归测试：
- `test_generic_claim_query_is_not_strong_claim_evidence`

验证：
- targeted tests 通过。
- 完整 `tests.test_historical_citation_verifier` 通过：`218 tests OK (skipped=5)`。

下一步外交优化方向：
- `p4n5` 不应再靠单个泛化 query 推进，应升级为 compound evidence：
  - facet A：南洋/赤道以北/獨領南洋；
  - facet B：委任統治/受任國/英国案；
  - facet C：牧野/日本委員/受諾或接受相关动作；
  - facet D：会議决定仅作为弱辅助，必须与 A-C 同页或相邻上下文共现才可升权。
- 对《日本外交文書》继续建立文书题名级 query bucket，而不是只用“日本外交文書 + 主题词”。每个 bucket 应区分 `document_heading`、`person`、`territory/topic`、`decision/action`，并在报告中说明哪个 facet 缺失。

## 46. 2026-05-03 巴黎讲和会议南洋委任统治 compound packet

第 45 节提出的 `p4n5` compound evidence 已实现为专门 packet：
- packet type：`volume_series_paris_mandate_compound_claim`。
- 触发条件收紧为：
  - 论文/脚注侧包含巴黎、巴里、パリ、講和、牧野等语境；
  - 同时 resolver/query bucket 中包含委任、南洋、赤道以北、獨領南洋、南洋群島等 mandate 语境；
  - 单独出现“牧野 + 会议决定”不会触发该专门 packet，仍走 generic packet 或保持无 packet。

facet 设计：
- `mandate_territory`：赤道以北、獨領南洋、南洋群島、太平洋群島。
- `mandate_system`：委任統治、受任國、統治受任國、英國/英国ノ委任統治案。
- `japanese_actor_makino`：牧野男、牧野委員、牧野伸顕、日本委員、帝國委員。
- `decision_acceptance_action`：決定ヲ受諾、受入、承諾、同意、異議ナシ/異議ナキ。
- `goal_or_outcome`：目標、目的ヲ達成、達成、要求ヲ貫徹、主張ヲ貫徹。
- `weak_meeting_decision_lead`：會議ノ決定/会議ノ決定 等，只作为 optional weak lead，不能覆盖 acceptance action。

真实 `p4n5` 回归：
- 输出目录：`output/historical_citation_next_stage_diplomacy_p4n5_paris_compound_20260503`。
- 状态仍为 `fulltext_only_partial_support`，matched page 178。
- packet 覆盖：
  - `mandate_territory=true`；
  - `mandate_system=true`；
  - `japanese_actor_makino=true`。
- packet 缺失：
  - `decision_acceptance_action=false`；
  - `goal_or_outcome=false`。
- Gemma `gemma4:e4b` 结论与 packet 一致：材料能支持南洋委任统治/牧野相关讨论，但未直接说明“牧野决定接受会议决定并达成第一个既定目标”。因此保留 partial 是内容层面的谨慎判断。

新增回归测试：
- `test_paris_mandate_packet_requires_acceptance_action_not_weak_decision_lead`
- `test_paris_mandate_packet_complete_when_acceptance_action_is_present`
- 旧边界 `test_volume_series_generic_packet_does_not_require_publication_year` 继续保护：无 mandate 语境时不误触发 Paris packet。

验证：
- targeted tests 通过。
- 完整 `tests.test_historical_citation_verifier` 通过：`220 tests OK (skipped=5)`。

下一步：
- 外交文书的后续优化应转向更多文书类型的 packet/facet，而不是提高单关键词权重。
- 尤其是 John Hay/门户开放、原敬日记日期型、山縣有朋意見書析出文献，应分别维持自己的 resolver 与 packet，不共享 Paris mandate 的 acceptance/goal 规则。

## 47. 2026-05-04 known PID 页窗兜底、日记出版年误判与下载依赖结构化

本轮继续按三类史料小样本推进：
- `p2n8`《山縣有朋意見書》：析出/单独 PID 文献。
- `p4n1`《原敬日記》第 2 卷：日记日期型但脚注无日记日期。
- `p4n5`《日本外交文書》巴黎讲和会议经过概要：volume-series + compound packet。

新增发现：
- `p2n8` 已锁定正确 PID `3025431`，但之前被 PID 内 `pdf_page=3/5/12` 的题名/目录类 fulltext hint 抢先，导致没有走引文页 306 的小窗。
- `p4n1` 的 `DiaryDateResolver` 把脚注出版年 `1981年` 误当成日记日期，使 `原敬日記 第二巻 1981年` 这类书目信息 query 被误标为 specific evidence。
- `p4n1` 即使改走 known PID 页窗，也暴露出书页 325 大于 PID `2982135` 的 scan 总页数 219，说明日记卷册不能直接假定“书页码 = scan 页码”，必须建立页码偏移/目录映射。
- 受限下载依赖缺失时，旧报告只有裸 note `No module named 'selenium'`，且还保留 `downloaded_page_range`，容易误读为已经下载成功。

已完成修正：
- known PID 小窗兜底从 `diary` 扩展到 `contained_document`，并保持严格条件：必须是 resolver 已知 PID 或 `known_pid_candidate`。
- 对分散页码增加保护：如 `51, 163, 287` 这类跨度过大的页码，不再自动拼成巨大下载窗口，而记录 `known_pid_page_window_fallback_skipped`。
- 下载阶段顺序调整：
  - 强 specific fulltext hint 仍优先；
  - 若只有 title/toc lead，而已有 known PID + 引文页码，则先走 known PID 小窗；
  - 只有没有 known PID 小窗时，才允许非 specific fulltext `pdf_page` 兜底。
- `DiaryDateResolver` 过滤脚注出版年：`1981年版` 不再进入 `dates`、`target_pid_queries` 或 source-level cache key；保留 `publication_year_removed_from_diary_dates` warning。
- fulltext specificity 降权：
  - `title/host/volume/blocked_standalone` bucket 不再作为 specific evidence；
  - 单独年份和“题名 + 卷册/出版年”的书目 locator 不再作为 strong fulltext evidence；
  - 完整日期（如 `1900年5月12日`）仍可作为日记定位线索。
- 下载失败结构化：
  - `No module named 'selenium'` 归类为 `download_dependency_missing`；
  - 报告写入 `download_exception`、`source_availability.reason=download_dependency_missing`；
  - 未成功下载时，把 `downloaded_page_range` 改为 `download_planned_page_range`。
- known PID 页窗超出 scan 总页数时，新增 `known_pid_page_window_requires_page_mapping`，说明这是页码映射问题，而不是简单资料不可用。
- IIIF/fulltext-json 可读性探测扩展到 `contained_document` 与 `diary`，为后续图像页 OCR 留入口。

真实小样本结果：
- 输出目录：`output/historical_citation_next_stage_diplomacy_known_pid_window_p2n8_p4n1_structured_20260504`。
- `p2n8`：
  - 走入 `contained_document_known_pid_page_window_fallback_used:book_pages=306`；
  - planned range 为 `304-308`；
  - 因当前环境缺 `selenium`，未生成 OCR PDF；
  - 当前状态仍为 `fulltext_lead_only`，但失败原因已结构化为 `download_dependency_missing`，不再误显为“已下载”。
- `p4n1`：
  - 出版年不再作为日记日期；
  - 走入 `diary_known_pid_page_window_fallback_used:book_pages=325`；
  - 发现 planned scan window `323-327` 超出 total scan pages `219`；
  - 当前状态为 `fulltext_lead_only/page_mapping_unavailable` 路线，下一步应做日记卷册页码映射，而不是继续全文 lead。
- 输出目录：`output/historical_citation_next_stage_diplomacy_p4n5_packet_after_locator_filter_20260504`。
- `p4n5`：
  - 保持 `fulltext_only_partial_support`，matched page 178；
  - Gemma `gemma4:e4b` 正式精核；
  - packet 仍覆盖 `mandate_territory/mandate_system/japanese_actor_makino`，缺 `decision_acceptance_action/goal_or_outcome`，说明本轮书目信息降权没有破坏外交文书 packet 判断。

新增回归测试：
- `test_contained_document_known_pid_page_window_fallback_uses_cited_page`
- `test_known_pid_page_window_precedes_title_only_fulltext_page_hint`
- `test_known_pid_page_window_fallback_skips_wide_distributed_pages`
- `test_diary_resolver_removes_publication_year_from_diary_dates`
- `test_diary_bibliographic_terms_are_not_specific_fulltext_evidence`
- `test_download_dependency_missing_is_structured_when_selenium_unavailable`
- `test_known_pid_page_window_out_of_scan_range_requires_page_mapping`

验证：
- targeted tests 通过。
- 完整 `tests.test_historical_citation_verifier` 通过：`227 tests OK (skipped=5)`。

下一步：
- 给日记类建立“书页码 -> scan 页码”偏移映射：优先使用目录/页码 OCR 样本，不再把 cited book page 直接当 scan page。
- 给受限下载环境增加依赖预检：缺 `selenium` 时，在 runner 开头直接记录 `download_dependency_missing`，避免每条都进入下载子进程后才失败。
- `p2n8` 的下一步不是继续全文 title lead，而是在依赖可用或 IIIF OCR 通道可用后，对 PID `3025431` 的 planned range `304-308` 做 OCR 和 Gemma 精核。
- `p4n5` 耗时仍高，应继续做 fulltext/Gemma cache；但内容判断已稳定，不应通过提高单词权重强行升为 direct。
## 48. 2026-05-04 受限下载依赖预检与日记日期窗口收窄

本轮继续按三类史料小样本验证，新增两个可复用优化：

1. **受限下载依赖预检**
   - 问题：缺少 `selenium` 时，旧流程仍会为每个受限下载候选启动下载 worker，最后才在子进程里失败。
   - 修改：`HistoricalCitationVerifier` 增加 `restricted_download_dependency_status()`；next-stage runner 在启动 worker 前先检查依赖。若缺依赖，则改为主进程内快速执行全文/snippet 路径，并写入：
     - `download_worker_bypassed`
     - `download_dependency_check`
     - `download_planned_page_range`
     - `source_availability.reason = download_dependency_missing`
   - 验证：`p2n8 山縣有朋意見書` 保留 PID `3025431`、计划页窗 `[304, 308]`，不再进入 browser request；状态为 `fulltext_lead_only`，而不是超时或无结构失败。

2. **日记类正文日期上下文收窄**
   - 问题：日记类脚注没有日期时，如果把整段正文都交给 resolver，会把同一段中的多个年份全部加入日期桶，导致 `原敬日記 p4n1` 同时出现 `1918/1908/1914/1916/1917/1919` 等不相关日期。
   - 修改：新增 `candidate_source_claim_context()`，仅对 `DiaryDateResolver` 使用“译文附近局部窗口”；优先取译文前最近日期，并先做 NFKC 归一化，避免全角年份 `１９０８年` 识别失败。
   - 验证：`p4n1 原敬日記` 的 `source_resolver_plan.dates` 收窄为 `['1908年']`，`target_pid_queries` 为 `['1908年', '原敬日記']`。该条当前仍为 `fulltext_lead_only`，原因不是日期解析，而是引用页码 `325` 对 PID `2982135` 的扫描页范围 `323-327` 超出总扫描页 `219`，应按“版本/页码体系不一致，需要日期/目录/索引型页映射”继续处理。

3. **next-stage artifact 刷新**
   - 问题：combined JSON 中可能保留旧的 `source_resolver_plan`，即使新 resolver 已改进，next-stage 报告仍会显示旧 artifact。
   - 修改：next-stage 在下载/OCR 和 source mismatch recheck 入口重新执行 `attach_source_graph_artifacts()`，确保报告中的 resolver、manual recipe、query buckets 与当前代码一致。

4. **回归结果**
   - `宗教 p4n5`：恢复为 `fulltext_only_direct_support`，Gemma 模型 `gemma4:e4b`，并列上下文候选数为 3。
   - `宗教 p4n9`：恢复为 `fulltext_only_direct_support`，Gemma 模型 `gemma4:e4b`，并列上下文候选数为 3。
   - `外交 p2n8`：受限下载依赖缺失被结构化记录，保留可复用计划页窗。
   - `外交 p4n1`：日期解析明显改善；下一步重点不是再放宽全文命中，而是开发日记/版本页码映射兜底。

下一步优化方向：

- 对日记类材料建立“日期 -> 卷册 -> 目录/索引 -> 扫描页”的 resolver，不再把现代再版页码直接假定为 NDL scan page。
- 对 `download_dependency_missing` 的环境问题，提供可选安装/检查指引，但主流程必须继续保留全文/snippet-only 证据，不因缺浏览器依赖中断。
- 对 source graph artifact 增加版本号或 `resolver_refreshed_at`，便于全量报告判断是否仍使用旧 combined artifact。

## 49. 2026-05-04 日记日期页提示路由与年号变体

本轮继续处理《原敬日记》这类“日记日期型 + 现代再版页码不等于 NDL 扫描页”的材料。核心原则保持不变：日期全文命中只能作为下载/OCR 路由，不直接升级为支持证据；是否支持论文句子仍交给 OCR/全文上下文和 Gemma `gemma4:e4b` 精核。

新增问题：
- `p4n1` 的脚注页码为现代再版页 `325`，PID `2982135` 的扫描页总数只有 `219`，不能再走“book page = scan page”的 known PID 小页窗。
- 正文可抽取的日期是 `1908年`，但 NDL 日记正文更常见的表达是 `明治41年` 或 `明治四十一年`。只搜西历会漏掉更可用的正文命中。
- 虽然 `1981年` 已从 `DiaryDateResolver.dates` 中移除，但它仍可能经由脚注书目信息混入 target PID 全文 probe，造成出版年噪音。

已完成修改：
- 新增日记日期查询变体生成：
  - `1908年` 自动扩展为 `明治41年`、`明治四十一年`；
  - 若含月日，也保留年号 + 月日形式；
  - 出版年-only 查询继续排除，不进入日记日期候选。
- 在 NDL target PID fulltext probe 中插入日记年号变体，并过滤日记脚注出版年查询，例如 `1981年`、`原敬日記 第2巻 1981年`。
- 新增 `diary_date_pdf_page_fallback`：
  - 仅适用于 `source_type=diary`；
  - 只使用同一 PID 内带 `pdf_page` 的日期命中；
  - 将 top candidates 并列记录，包括 `pdf_page`、query、snippet、lead_category、match_scope、score；
  - 证据等级固定为 `routing_only_until_ocr_llm_review`，不当作 direct/partial support。
- 下载阶段顺序调整为：
  1. specific fulltext page hint；
  2. diary date page hint；
  3. OCR page mapping；
  4. known PID book-page fallback；
  5. non-specific fulltext fallback。

真实小样本结果：
- 输出目录：`output/historical_citation_next_stage_diplomacy_diary_p4n1_date_route_20260504`
- `p4n1` 不再走 `323-327 / total=219` 的越界页窗。
- 系统使用 `明治四十一年` 命中 PID `2982135`，生成 `diary_date_pdf_page_fallback`：
  - selected pdf page：`148`
  - planned range：`144-152`
  - top candidates 中包含 page `148`、`153`、`154`、`156`、`161` 等多个正文日期命中。
- 当前环境仍缺 `selenium`，因此下载未执行，状态结构化为 `download_dependency_missing`，并保留 `download_planned_page_range=[144,152]`。
- Gemma `gemma4:e4b` 对全文上下文判为 `fulltext_only_not_supported`：当前日期上下文只说明明治四十一年初的政治事件，尚未命中“美国经济活力/未来世界影响”的具体句子。这个结论是内容层面的谨慎判断，不再是页码越界或流程失败。

新增回归测试：
- `test_diary_date_queries_add_japanese_era_year_variants`
- `test_diary_target_pid_probe_filters_publication_year_keywords`
- `test_diary_date_pdf_page_hint_routes_before_book_page_window`

下一步优化方向：
- 日记类 source resolver 继续从“年”升级到“日期 + 人名/事件词”复合路由；只有年度命中时，应优先列多个正文候选，而不急于给出强支持。
- 对日记正文中的中文 claim（如“美国经济不景气”“世界影响”）增加日文历史词扩展，例如 `米国`、`不景気`、`経済`、`世界`、`影響`、`将来`，并作为日期命中后的二级 query bucket。
- 若下载依赖可用，应对 `diary_date_pdf_page_fallback` 的 planned range 执行 OCR，并把 OCR 清洗上下文与 snippet 候选并列送 Gemma。

## 50. 2026-05-04 日记 claim facets 二级检索

第 49 节解决了“1908年 -> 明治41年/明治四十一年”的日期路由，但真实 `p4n1` 回归显示：只按年度命中会得到明治四十一年初的政治流水账，仍然离论文句子太远。因此本轮把日记类材料从“date-only routing”推进到“date + claim/event facets routing”。

新增机制：
- `DiaryDateResolver` 下的 target PID probe 会根据中文/英文 claim 自动生成日文历史词组：
  - 美国：`米国`、`米國`
  - 经济/景气：`経済`、`經濟`、`景気`、`景氣`、`不景気`、`不景氣`、`資本`
  - 将来/影响：`将来`、`將來`、`世界`、`影響`、`前途`
  - 活力：`活気`、`活氣`、`活力`
- 生成 query 时优先绑定日记年号日期，例如：
  - `明治41年 米国 経済`
  - `明治41年 米国 将来`
  - `明治四十一年 米国 不景気`
- 由于 NDL fulltext search 近似 OR，query 命中本身不直接升权；新增 `diary_claim_facet_packet`，只在上下文/片段本身覆盖 facets 时加权。
- `diary_date_pdf_page_fallback` 下载路由也同步使用 claim facets，避免 route 仍选择第一个泛命中页。
- `source_type=diary` 的 fulltext context expansion limit 从 3 提升到 5，以便保留并列候选。

真实小样本结果：
- 输出目录：`output/historical_citation_next_stage_diplomacy_diary_p4n1_claim_facets_route_20260504`
- `p4n1` target PID probe 进入 `明治41年 + 米国/経済/不景気/将来/世界` 组合查询。
- `diary_date_pdf_page_fallback` 从旧的 page `16` 泛命中，改为选择 page `30`：
  - selected query：`明治41年 米国 将来`
  - selected pdf page：`30`
  - planned range：`26-34`
  - top candidate facets：`economy + future_influence + us`
- 全文上下文候选中，`ctx1` 抓到：
  - `米國資本家`
  - `將來日本に投資することに關し大影響あるべし`
- Gemma `gemma4:e4b` 精核结论由上一轮 `fulltext_only_not_supported` 进步为 `fulltext_only_partial_support`。
- Gemma 的理由是：该上下文支持“美国相关资本/将来影响”部分，但没有直接出现“经济不景气”和“前景十分光明”，因此不能升为 direct support。这个判断符合人工谨慎标准。

新增回归测试：
- `test_diary_claim_queries_add_us_economy_future_terms`
- `test_diary_claim_facets_prioritize_claim_hint_over_date_only`
- `test_diary_date_pdf_page_route_prefers_claim_facets`

下一步优化方向：
- 将 diary claim facets 做成更通用的可配置词表，而不是只覆盖美国经济类；后续应加入人物、地名、事件、政策等 facet 类型。
- 对 `query_only` 命中的 route candidate，报告中必须继续显示 `routing_only_until_ocr_llm_review`，避免用户误以为 query 组合本身就是证据。
- 若安装下载依赖或启用 IIIF OCR，优先 OCR `26-34` 页窗，检查 page 30 的 snippet 扩展是否能被 OCR 清洗上下文进一步确认。

## 51. 2026-05-04 日记页路由证据的报告显式化

第 50 节已经让《原敬日记》p4n1 从单纯日期命中推进到“日期 + claim facets”路由，但报告层仍有一个可读性问题：正式报告只在 note 里留下 `diary_date_pdf_page_fallback_used:pdf_page=30`，读者很难判断这到底是证据、下载计划，还是已经完成 OCR 后的核查结论。

已完成修改：
- 新增报告格式化项 `Diary date PDF-page route fallback`，在逐条详情里单独显示：
  - PID；
  - selected pdf page；
  - planned scan window；
  - selected query；
  - match scope / lead category；
  - claim facets；
  - evidence level。
- `Source-type diagnostic summary` 中同步加入 `diary_pdf_route=pX/window=A-B` 和 `route_evidence=routing_only_until_ocr_llm_review`，便于快速索引阶段识别该条是“路由证据”，不是 direct/partial support。
- 处理历史中新增 `diary_date_pdf_page_fallback` 行，并保留 `diary_date_pdf_page_fallback_used:*` note，便于追踪该页窗为何被选择。
- 报告测试中加入回归断言，确保 route fallback 不会再次被隐藏到 note 或 fulltext context 之后。

验证：
- targeted report test 通过。
- diary route / claim facets targeted tests 通过。

下一步优化方向：
- 若后续恢复浏览器下载或 IIIF OCR，可在同一报告块下继续追加 `ocr_status`、`cleaned_ocr_context`、`ocr_llm_review_status`，形成完整的“路由 -> OCR -> Gemma 精核”链条。
- 对其它需要先定位页再下载的 source type，可复用该报告模式，但必须保持 evidence level 与 support status 分离，避免把 locator 当作内容证据。

## 52. 2026-05-04 日记 claim facets 配置化与年号变体交错 query

第 50 节的 diary claim facets 先解决了《原敬日记》p4n1 的“美国/经济/未来影响”场景，但如果继续把词表写死在 verifier 里，后续遇到中国、朝鲜、俄国、英国、政策、条约、内阁等日记史料时仍然需要改主流程。本轮把它改为可复用配置机制。

已完成修改：
- 在 `config/historical_citation_source_resolvers.json` 的 `hara_takashi_diary` 下新增 `claim_facets`：
  - anchor 类：`us`、`china`、`korea`、`russia`、`britain`；
  - theme/institution 类：`economy`、`future_influence`、`vitality`、`diplomacy_policy`、`cabinet_government`。
- `HistoricalCitationVerifier` 新增配置读取：
  - 有配置时读取 `claim_facets`；
  - 无配置时回退到内置默认规则，避免外部配置缺失导致流程中断。
- `_diary_claim_term_buckets()` 不再固定写死美国经济规则，而是按每个 facet 的 `trigger_terms` / `trigger_patterns` 激活日文检索词。
- `_diary_claim_fulltext_queries()` 改为通用的 `anchor + theme + date` 组合：
  - country/person/place/institution 等 role 作为 anchor；
  - economy/policy/future 等 role 作为 theme；
  - 若没有 anchor，则退化为 date + claim terms。
- 修复配置化后出现的新问题：词表变长时，前 18 条 query 容易被第一个年号变体占满，导致 `明治四十一年` 这类汉数字年号又被挤出。现在改为按“theme -> 年号变体 -> anchor”交错生成，并限制每轮 anchor 数量，保证多个年号变体都能进入候选。
- `_diary_claim_facet_packet()` 的加分逻辑也改为通用 role 判断：anchor + 多个 theme 可获得额外路由加权；旧的 `us + economy + future_influence` 强组合继续保留，保护 p4n1 回归。
- 真实 p4n1 回归中发现的新退化：配置化后，整段背景里的“外交、英国、俄国、内阁”等宽词触发了过多 facets，使 page 16 一度抢在 page 30 前面。修复方式：
  - diary claim facets 只用 `translation_text` 触发；
  - 只有译文缺失时才退到 `candidate_source_claim_context`；
  - 脚注书名、脚注书目信息和整段背景不再触发 claim facets；
  - 报告新增 `diary_claim_scope=translation_text`，便于确认触发范围。

新增回归测试：
- `test_diary_claim_facets_can_be_loaded_from_resolver_config`
- `test_diary_claim_facets_ignore_broad_paragraph_background`

验证：
- diary claim/query targeted tests 通过。
- diary routing/report targeted tests 通过。
- 真实 p4n1 回归通过：`diary_pdf_route=p30/window=26-34`，Top N 的 `ctx1` 为 page 30，Gemma `gemma4:e4b` 继续判为 `fulltext_only_partial_support`。

下一步优化方向：
- 对日记类继续加入“人物名抽取 -> 日文姓名/旧字体变体”的 facet 生成，尤其是外交论文中人名音译/汉字名不稳定的条目。
- 把外交文书的文书题名级 query bucket 与 diary claim facets 的 role 体系对齐，形成统一的 `anchor/theme/action/date` 打分接口。
## 53. 2026-05-04 volume-series 全文优先、strict PID 注入与 wrong PID 上下文隔离

本轮继续按三类史料小样本验证：`p2n8`（析出文献/山縣有朋意見書）、`p4n5`（日本外交文書/巴黎讲和会议南洋委任统治）、`p6n6`（日本外交文書/华盛顿会议海军军备限制）。

新增问题：
- `p4n5` 在 source recheck 后已经有目标 PID `11923430` 的 62 条全文命中，但仍进入受限下载/OCR worker。由于正式 Gemma 精核 timeout 为 300 秒，而外层 download worker 原先只有 180 秒，先发生外层误杀；将 worker 提升到 390 秒后，又暴露出下载/OCR 本身仍会耗尽时间。
- `p6n6` 初始 download/OCR 阶段没有进入 source recheck，因此没有使用“全文优先”保护，仍发生 390 秒 `download_timeout`。
- 更重要的是，`p6n6` 的 NDL 候选中出现 `外交史料館報` 等全站全文 lead。旧逻辑在 strict PID 没有被注入时，会把这些 wrong PID 的“日本外交文書 1974年”泛命中扩成上下文，形成明显误导。

已完成修改：
- next-stage 的正式 Gemma review worker timeout 策略改为：若 `prefer_ollama_review=True`，实际 worker timeout 至少为 `HISTORICAL_CITATION_REVIEW_TIMEOUT_SECONDS + 90`，并写入 `download_worker_timeout_policy`。
- 对 `source_type=volume_series` 增加“受限下载前全文优先”：在 download/OCR 前先尝试目标 PID 内全文命中、Top N 上下文扩展与 Gemma 精核；若得到 `fulltext_only_*` 或 `fulltext_lead_only`，不再继续进入受限下载。
- 下载前全文扩展收窄：复用已有 `target_pid_fulltext_probes`；最多扩展 3 个 hit、保留 5 个候选，每个 hit 只做 1 轮上下文接龙。
- strict PID 保护：`_mark_fulltext_only_hit_if_possible()` 开始时执行 `_rerank_matches_for_candidate_fulltext()`，自动注入 resolver known PID；存在 strict PID 时，只允许 strict PID 内的 fulltext hints 进入上下文候选，wrong PID 只保留为 NDL 候选/lead 诊断。

真实小样本结果：
- `p4n5`：输出目录 `output/historical_citation_next_stage_diplomacy_three_source_check_p4n5_fulltext_probe_reuse_20260504`；状态由 `download_timeout` 改为 `fulltext_only_partial_support`；目标 PID `11923430`，`target_snippet=direct_hit/hits=62/specific=62`；Gemma `gemma4:e4b` 成功精核。
- `p6n6`：输出目录 `output/historical_citation_next_stage_diplomacy_three_source_check_p6n6_strict_fulltext_20260504`；状态由 `download_timeout` / wrong PID lead 改为 `fulltext_only_partial_support`；strict PID `11927523` 被自动注入并置顶；`target_snippet=direct_hit/hits=137/specific=137`；Gemma `gemma4:e4b` 成功精核。
- `p2n8`：当前仍为 `fulltext_lead_only`。这是内容/来源结构问题，不是 timeout：PID `3025431` 内当前命中多为题名或目录线索，`specific_hits=0`；下一步应做 host discovery 或在可用 OCR/IIIF 通道下处理 planned range `304-308`。

新增回归测试：
- `test_pdf_next_stage_keeps_worker_timeout_for_formal_review_when_dependency_missing`
- `test_pdf_next_stage_uses_volume_series_fulltext_before_rechecked_download`
- `test_pdf_next_stage_stops_volume_series_lead_before_initial_download`

验证：
- 上述 targeted tests 通过。
- 真实 p4n5、p6n6 小样本均无 timeout，并使用 Gemma `gemma4:e4b` 正式精核。

下一步优化方向：
- `p2n8` 类型应升级为 contained-document resolver：先 host discovery，再进入 host/known PID 内按析出题名、引用页码、正文关键词组合检索；不应把题名页或目录页作为正文证据。
- `p4n5`、`p6n6` 的耗时仍主要在 NDL fulltext probe/Gemma 上，应继续做磁盘 cache 与 source-level cache，避免全量 resume 时重复扩展同一 PID/hit。
- 对 volume-series 建立更细的文书题名级 query bucket：`document_heading/person/theme/action/date/page_near`，并让 compound packet 明确列出缺失 facet，避免通过提高单词权重误升为 direct。
## 54. 2026-05-04 contained-document 配置化 claim terms 与 p2n8 正文命中

第 53 节之后，`p2n8` 仍停在 `fulltext_lead_only`。进一步检查发现，问题不是 PID 错误：resolver 已锁定 `3025431`，但目标 PID 查询主要是题名、出版年和中文 claim，导致命中集中在题名页、目录页或解题页。人工检索会把中文论点转换成日文史料词，例如 `露國`、`日露`、`滿洲`、`協商`、`復讐心`，而旧流程没有这层转换。

已完成修改：
- `contained_documents.documents` 配置项扩展为可携带 claim-term buckets：
  - `person_terms`
  - `theme_terms`
  - `action_terms`
  - `page_near_terms`
- `ContainedDocumentResolver` 自动读取这些配置，并写入：
  - `query_buckets.person/theme/action/page_near`
  - `target_pid_queries`
- NDL target PID probe 的 bucket 扫描扩展到 `theme`、`action`、`special_term`，使配置化 claim terms 能进入目标 PID 全文检索。
- fulltext context scoring 新增 `action` bucket 权重，避免“共同经营/提携/复讐心”这类动作词只被当作普通低权重词。

真实小样本结果：
- 输出目录：`output/historical_citation_next_stage_diplomacy_three_source_check_p2n8_contained_terms_20260504`
- 状态由 `fulltext_lead_only` 改为 `fulltext_only_partial_support`。
- strict PID `3025431` 内 `target_snippet=direct_hit/hits=144/specific=134`。
- Top context 命中 page `199`，query=`復讐`，上下文包含 `露國ノ復讐`、`支那ノ門戶開放`、`露國...協商`。
- Gemma `gemma4:e4b` 正式精核成功，结论为 partial support：材料支持“对俄复仇风险、对俄协商、中国问题重要性”等核心背景，但尚未完全覆盖中文句子的“敞开胸襟/亲密交情/共同经营中国东北”。

新增回归测试：
- `test_contained_document_resolver_adds_configured_claim_terms`

验证：
- targeted resolver tests 通过。
- 三类小样本当前状态：
  - `p2n8`: `fulltext_only_partial_support`
  - `p4n5`: `fulltext_only_partial_support`
  - `p6n6`: `fulltext_only_partial_support`

下一步优化方向：
- contained-document 的配置化 buckets 可继续泛化为 `anchor/theme/action/date/page_near` 通用 schema，与 volume-series 和 diary facets 对齐。
- `p2n8` 仍缺 OCR/IIIF 清洗正文：当前是 NDL SNIPPET 扩展弱证据。后续若下载依赖或 IIIF OCR 可用，应对 page `199` 附近窗口做 OCR，并与 snippet context 并列交给 Gemma。
- 报告的人工检索建议还停在 `query=山縣有朋意見書 山縣有朋意見書`，下一步应把配置化 claim terms 也显示到 manual recipe，便于人类复核时直接看到推荐搜索词。

## 55. 2026-05-04 manual recipe 分层词桶可见化

第 54 节留下的报告问题已经处理：`contained-document` 虽然能用配置化 claim terms 找到正文线索，但最终 Markdown 的人工检索建议仍只显示第一个泛化 query，读者看不到真正起作用的 `theme/action/page_near` 等检索词。这会让人工复核重新回到“题名 -> 目录”路径，和模块实际的有效路径脱节。

已完成修改：
- `build_manual_search_recipe()` 现在输出：
  - `target_pid_queries`
  - `global_queries`
  - `query_buckets`
- `query_buckets` 会合并 source query plan 和 resolver 原始 buckets，保留 `document_title`、`document_heading`、`contained`、`host`、`volume`、`date`、`person`、`theme`、`action`、`policy`、`page_near`、`special_term` 等分层信息。
- 报告生成从“只显示第一个 query”改为显示：
  - strict PID；
  - top suggested query；
  - top target PID queries；
  - 最高优先级 buckets。
- 这样报告中弱证据/失败项的人工路径会更接近真实人工 NDL 检索：先确认 PID/host，再按文书题名、人物、主题、动作词、页码附近词逐层检索。

新增回归测试：
- `test_contained_document_resolver_adds_configured_claim_terms` 增加 manual recipe 断言，确保 `theme/action/page_near` 不只停在 resolver，而是进入人工检索 recipe。
- `test_resume_report_indexes_three_source_type_diagnostics` 增加报告断言，确保报告中能看到 `pid_query=復讐心, 共同經營, 滿洲`、`theme=滿洲`、`action=共同經營, 復讐心`。

验证：
- targeted tests 通过。
- 完整单测通过：`Ran 242 tests in 276.351s OK (skipped=5)`。

下一步优化方向：
- 对 volume-series 的 `document_heading/person/theme/action/page_near` 进一步统一到同一 schema，尤其处理《日本外交文書》中“文书题名 + 人物 + 主题动作”的组合。
- 若全量耗时仍高，继续把 fulltext probe、expanded context、Gemma review 的缓存状态显式写入报告，方便判断慢点来自网络、上下文扩展还是 LLM 精核。

## 56. 2026-05-04 volume-series 通用 schema 对齐

第 55 节解决了报告可见性，但《日本外交文書》内部仍主要依赖旧桶：`document_title`、`document_heading`、`person`、`policy`。这些桶适合日本外交文书专案，却不利于把 resolver 扩展到其它卷册型史料。为便于后续通用化，本轮在保留旧桶的基础上同步生成统一 schema。

已完成修改：
- `NihonGaikoBunshoResolver` 新增兼容 buckets：
  - `anchor`：文书题名、人名、会议名等定位锚点；
  - `theme`：委任统治、海军军备、主力舰比率、门户开放、机会均等等主题词；
  - `action`：受诺、承诺、回答、照会、提议、宣言、共同经营、协定、限制等动作词；
  - `page_near`：帝国主张说明、赤道以北、米国案十对六、合众国提议等页内近邻词。
- 旧桶不删除：`document_title/document_heading/person/policy` 仍用于既有排序、回归和报告。
- `_build_global_queries()` 补入 `anchor` 与 `action`，修复此前 `action` 虽可评分却未进入全站 query 构造的问题。
- target PID probe 的 bucket scan 识别 `anchor`。
- fulltext context scoring 增加 `anchor` 权重，避免 anchor 词只作为普通 query 存在而不进入上下文候选加分。
- 报告的 manual recipe bucket 优先级中加入 `anchor`，让读者能看到文书题名/人物定位锚点与主题、动作词并列。

新增回归测试：
- `test_source_resolver_maps_paris_peace_supplement_pid` 增加 `anchor/theme/action/page_near` 断言。
- `test_source_resolver_maps_washington_conference_pid_before_fulltext_leads` 增加 `anchor/theme/action/page_near` 断言。

验证：
- 两个 volume-series targeted tests 通过。
- 完整单测通过：`Ran 242 tests in 274.250s OK (skipped=5)`。

下一步优化方向：
- 将 `anchor/theme/action/page_near` 从日本外交文书专用映射继续抽象成配置项，允许其它 volume-series/source-collection 史料通过 JSON 配置扩展，而不是改 Python 词表。
- 小样本复跑时重点观察 `p4n5`、`p6n6` 的 Top N 上下文排序是否保持或改善，不能因新增 anchor 宽词导致题名页/目录页重新上浮。

## 57. 2026-05-04 volume-series 真实回归后的 timeout guard 与主题贴合排序

按第 56 节要求复跑 `p4n5`、`p6n6` 后，发现两个单测没有暴露的新问题。

新增问题：
- `p4n5` 在真实 next-stage 中进入 `rechecked_download_ocr_alignment` 后，外层 worker 仍按 `review_timeout + 90 = 390s` 保护。该条先做 target PID snippet 接龙扩展，约四分钟后才进入 Gemma，结果外层在 Gemma 完成前误杀，状态退化为 `download_timeout`。
- `p4n5` 修复 timeout 后，Top N 第一位一度被“牧野 + 決定”带到山东/胶州湾上下文。该上下文有人名与“决 定”词，但缺少本条 claim 的主题 `委任統治/南洋/赤道以北`，不应排在主题贴合上下文前面。
- `p6n6` 中 `米国案ノ十対六` 原先只归入 `page_near`，没有归入 `theme`，导致主题缺失降权误打到真正关键的比例上下文。

已完成修改：
- 正式 Gemma review 的外层 worker guard 改为默认 `review_timeout + 300s`，并通过 `HISTORICAL_CITATION_FORMAL_REVIEW_WORKER_OVERHEAD_SECONDS` 可配置。
- `download_worker_timeout_policy` 新增 `worker_overhead_seconds`，报告/JSON 可直接看到实际保护策略。
- volume-series scoring 新增主题贴合约束：若 resolver 有 `theme` bucket，而候选上下文没有命中任何 theme，则降权并记录 `missing_volume_series_theme`。
- 将 `十対六`、`十對六`、`米国案`、`米國案` 纳入日本外交文书 theme marker，避免华盛顿会议比例上下文被误判为缺主题。

真实小样本结果：
- `p4n5`：输出目录 `output/historical_citation_next_stage_diplomacy_three_source_check_p4n5_schema_guard_20260504`；最终 `fulltext_only_partial_support`；`download_worker_timeout_policy.effective_timeout_seconds=600`；`volume_series_fulltext_review_before_download.phase=rechecked_download_ocr_alignment`；Top N 中 `牧野男 + 委任統治` 升为 `ctx1`，山东/胶州湾上下文因 `missing_volume_series_theme` 降为 `ctx3`。
- `p6n6`：输出目录 `output/historical_citation_next_stage_diplomacy_three_source_check_p6n6_schema_guard_20260504`；最终 `fulltext_only_partial_support`；strict PID `11927523`；`米国案ノ十対六` 上下文升为 `ctx2`，Gemma `gemma4:e4b` 选择 `ctx2` 为 best context，判定仍为 partial，理由是缺少 Hughes 与完整 `10:10:6` 绑定。

新增/更新回归测试：
- `test_pdf_next_stage_keeps_worker_timeout_for_formal_review_when_dependency_missing`：外层 guard 期望改为 600 秒，并断言 `worker_overhead_seconds=300`。
- `test_volume_series_context_missing_theme_is_demoted`：同样包含“牧野/决定”时，缺主题的上下文必须低于包含 `委任統治/南洋` 主题的上下文。
- `test_source_resolver_maps_washington_conference_pid_before_fulltext_leads`：断言 `米国案ノ十対六` 同时进入 `theme` 和 `page_near`。

验证：
- targeted tests 通过。
- 完整单测通过：`Ran 243 tests in 265.995s OK (skipped=5)`。

下一步优化方向：
- 给 next-stage 子 worker 增加阶段内 heartbeat：至少区分 `target_pid_probe_reused`、`snippet_context_expansion_started/completed`、`gemma_review_started/completed`，否则全量时很难判断是在网络接龙、OCR 还是 LLM 精核阶段耗时。
- 继续把 `anchor/theme/action/page_near` 抽到 JSON 配置，先让《日本外交文書》的巴黎、华盛顿、门户开放三个子类型可配置，再推广到其它 volume-series。

## 58. 2026-05-04 next-stage 子 worker 细粒度 heartbeat

第 57 节指出的耗时定位问题已经处理到可用于全量监控的程度。此前全量日志只能看到某个 candidate 长时间处在 `download_ocr_alignment` 或 `volume_series_fulltext_review`，无法判断到底卡在 NDL target PID 检索、SNIPPET 上下文接龙，还是 Gemma 精核。

已完成修改：
- `ProgressReporter.event()` 修正 state/payload 合并方式，避免 state 中已有 `status/subphase` 时被重复关键字打断。
- next-stage download worker 现在会把主进程的 `progress_path` 传入子进程；子进程打开同一个 JSONL，启动 heartbeat，并记录：
  - `worker_started`
  - `source_graph_attach`
  - `volume_series_fulltext_review`
  - `download_ocr_enrichment`
  - `worker_completed`
- `HistoricalCitationVerifier` 新增可选 `_progress_event_callback`。verifier 本身不依赖 `ProgressReporter`，但可在 next-stage 中临时挂接 callback，调用结束后恢复。
- 通过该 callback，volume-series 的全文复核内部现在会记录：
  - `target_pid_fulltext_probe` started/completed/failed/reused；
  - `snippet_context_expansion` started/completed；
  - `llm_context_review` started/completed/failed。
- `volume_series_fulltext_review` completion metrics 增加 `context_count`、`target_probe_status`、`cache_hits`、`disk_cache_hits`，便于区分网络接龙、缓存命中和 LLM 精核耗时。

真实小样本结果：
- 输出目录：`output/historical_citation_next_stage_diplomacy_p6n6_fine_progress_20260504`
- 样本：外交论文 `p6-fp6n6`。
- 最终状态：`fulltext_only_partial_support`。
- 进度日志显示：
  - `target_pid_fulltext_probe`：PID `11927523`，`direct_hit`，`hit_count=137`，`specific_hit_count=137`。
  - `snippet_context_expansion`：扩展 `3` 个 hint，得到 `3` 个 context。
  - `llm_context_review`：`provider=ollama`，`model=gemma4:e4b`，`best_context_id=ctx2`，`decision=partial_support`。
- 报告中 Top N 保持并列展示：`ctx1=海軍勢力比`，`ctx2=米国案ノ十対六(selected)`，`ctx3=勢力比`；Gemma 选择 `ctx2`，但因缺少 Hughes 与完整 `10:10:6` 绑定，仍判 partial support。

新增/更新回归测试：
- `test_pdf_next_stage_worker_progress_reports_fulltext_subphases`：验证 next-stage 能从 worker/verifier 内部 relay `snippet_context_expansion`。
- `test_fulltext_context_expansion_emits_progress_callback`：验证 SNIPPET 上下文扩展会发出 started/completed 与 context metrics。
- `test_fulltext_context_selection_emits_llm_review_progress`：验证 LLM/Gemma 多上下文择优会发出 started/completed，并记录 `model=gemma4:e4b` 与 `best_context_id`。

验证：
- 细粒度 progress targeted tests 通过。
- timeout guard、volume-series resolver、progress reporter、fulltext cache 相关 targeted tests 通过。
- 完整单测通过：`Ran 246 tests in 254.098s OK (skipped=5)`。

下一步优化方向：
- 将 `target_pid_fulltext_probe` 的 repeated `direct_hit -> reused` 合并为更清楚的单条阶段摘要，避免全量报告读起来像重复搜索。
- 把这些 progress events 纳入 slow-event summary：当一个 candidate 超过阈值时，报告应显示最耗时的最后 subphase，而不只显示候选整体耗时。
- 继续推进第 57 节的 JSON 配置化：先把外交文书的 `anchor/theme/action/page_near` 子类型配置移出 Python，再把同一 schema 用到 source collection 和 diary。

## 59. 2026-05-04 slow-event 叶子阶段摘要与外交文书 facet 配置化

第 58 节完成了细粒度 heartbeat，但 slow-event summary 仍只显示 candidate 总耗时。本轮把这些细粒度事件真正接入全量诊断，并开始把《日本外交文書》的子类型词桶移到 JSON 配置。

已完成修改：
- `build_slow_events_from_progress()` 现在解析 `worker_stage_started/completed/failed`：
  - 保留候选整体 `elapsed_seconds`；
  - 新增 `subphase_durations`；
  - 新增 `last_subphase/last_subphase_status`；
  - 新增 `longest_subphase/longest_subphase_seconds`。
- slow-event 的“最后/最长阶段”优先使用叶子阶段，避免外层 wrapper `volume_series_fulltext_review` 抢走摘要。真实 p6n6 中现在显示 `longest=llm_context_review`，而不是笼统的 volume-series 总阶段。
- `next_stage_refinement_report.md` 的“处理慢路径”行新增：
  - `last=<subphase>/<status>`
  - `longest=<subphase>/<seconds>s`
- `source_resolvers.py` 新增通用 `claim_facets` 配置读取器：
  - 支持 `buckets` 写入 `anchor/theme/action/page_near/person/policy/document_title/document_heading/special_term`；
  - 支持 `target_pid_required_terms`，只把明确声明的精确词强制保留在 target PID 查询中；
  - 支持 `pid_match_terms`，只用明确声明的卷册定位词辅助 PID 匹配。
- `config/historical_citation_source_resolvers.json` 中为《日本外交文書》新增三个可配置子类型：
  - `paris_mandate`
  - `washington_naval_limitation`
  - `open_door_hay`

本轮发现并修复的新问题：
- 初版配置化把所有 configured bucket terms 都用于 PID 匹配，导致 `協定` 这种短动作词误撞到《日本外交文書》第38巻桂・タフト相关 PID `3448160`。
- 修复方式：PID 匹配只读取 `pid_match_terms`，不再把 `theme/action/page_near` 的短词直接用于卷册 PID 匹配。
- 同时保留 `target_pid_required_terms`，保证 `米国案ノ十対六`、`委任統治`、`米國照會` 这类精确词不会被宽泛标题词挤出目标 PID 查询。

真实小样本结果：
- 输出目录：`output/historical_citation_next_stage_diplomacy_p6n6_config_pidmatch_20260504`
- 样本：外交论文 `p6-fp6n6`。
- 最终状态：`fulltext_only_partial_support`。
- `known_pid_candidates` 从误带 `11927523, 3448160` 收紧为 `11927523`。
- target PID queries 以 `十対六`、`十對六`、`米国案ノ十対六`、`米國案ノ十對六`、`ヒューズ` 开头。
- Top N 中 `ctx2=米国案ノ十対六` 仍被 Gemma `gemma4:e4b` 选为 `best_context_id`。
- slow-event 摘要显示：`last=llm_context_review/partial_support; longest=llm_context_review/188.0s`。

新增/更新回归测试：
- `test_pdf_next_stage_records_slow_events_from_progress`：断言 slow-event 记录叶子 subphase、最长阶段和 subphase metrics。
- `test_source_resolver_uses_configured_gaiko_claim_facets`：断言 JSON `claim_facets` 可写入 buckets、target PID 查询和 PID 匹配。
- `test_source_resolver_maps_washington_conference_pid_before_fulltext_leads`：断言华盛顿会议不再误带桂・タフト PID `3448160`。

验证：
- slow-event targeted test 通过。
- progress callback、timeout guard、volume-series resolver、contained-document、diary targeted tests 通过。
- 真实 p6n6 小样本通过。
- 完整单测通过：`Ran 247 tests in 255.823s OK (skipped=5)`。

下一步优化方向：
- 继续把 `claim_facets` schema 推广到 source collection 和 diary，优先处理：
  - 日本近代思想大系中的 contained-title + 神宮大麻限定词；
  - 原敬日記中的 date + person/theme/action；
  - 山縣有朋意見書中的 contained document claim facets。
- 对 p6n6 的 `ctx3=海軍軍備制限問題@p8` 继续做 lead/body 精细分类：它未被 Gemma 选中，但 page 8 可能更接近目录/纲目，需要后续判断是否应降为 lead。

## 60. 2026-05-04 source collection/diary/contained facets 推广与问题小样本收口

本轮按用户要求先报告剩余进度，再在不重跑两篇论文全量的前提下，把第 59 节剩余优化一次性收口。当前 Codex 会话未暴露独立的 `goal` 工具或技能，因此使用任务计划闭环执行；过程仍按第 59 节的目标逐项完成。

已完成修改：
- `source_resolvers.py` 将 JSON `claim_facets` schema 从《日本外交文書》继续推广到：
  - source collection：《日本近代思想大系 5：宗教と国家》；
  - diary：《原敬日記》；
  - contained document：《山縣有朋意見書》。
- claim facet 合并逻辑改为通用 `_merge_configured_query_buckets()`，配置词桶可以叠加到 resolver 自身解析出的 `anchor/theme/action/page_near/person/policy/document_title/document_heading/special_term/institution`。
- `target_pid_required_terms` 继续只用于目标 PID 内查询保留，不直接参与全局 PID 排序；`pid_match_terms` 继续作为卷册 PID 匹配的窄入口，避免短词误撞错误卷册。
- `config/historical_citation_source_resolvers.json` 新增《日本近代思想大系》中的 `jingu_taima_distribution` facet：
  - 用 `神宮大麻/皇大神宮大麻/御札/神棚` 约束“大麻”语义；
  - 加入 `神棚ヲ不設`、`大麻ヲ水火ニ投ズ`、`大麻ノ神ノ字ガ蝶`、`伊勢皇大神宮大麻` 等可定位正文的短语；
  - 阻止裸 `大麻` 被当作现代语义或目录题名泛搜。
- volume-series lead/body 分类新增 `front_matter_body_lead`：
  - 对早期页码中类似 `経緯/概要/問題/会議開催` 的纲目性上下文降级；
  - 但保留 `米国案ノ十対六/ヒューズ/委任統治/赤道以北/決定ヲ受諾/米國照會/帝國政府回答` 等高精度正文 marker。
- `build_slow_events_from_progress()` 新增无 worker 子阶段时的 fallback：若 source mismatch 这类候选阶段本身超过阈值，也会显示 `source_mismatch_recheck_total`，不再在报告里留下空的 `longest_subphase`。

本轮发现并修复的新问题：
- 外交小样本 `p4-fp4n5` 的 `source_mismatch_recheck` 阶段耗时 198 秒，但该阶段没有 worker 子阶段事件，导致 `slow_events` 中出现 `longest_subphase=None`。
- 修复后，现有样本报告不重跑 NDL/LLM，只根据 progress JSONL 重建 slow-event 摘要，显示：
  - `p4-fp4n5 | source_mismatch_recheck_total | 198.0s`
  - `p4-fp4n5 | llm_context_review | 154.0s`
  - `p6-fp6n6 | llm_context_review | 136.0s`
  - `p2-fp2n8 | download_ocr_enrichment | 205.0s`

真实小样本结果（未重跑全量）：
- 宗教论文输出目录：`output/historical_citation_next_stage_religion_problem_samples_goal_20260504`
  - `p3-fp3n1`：《帝国憲法義解・皇室典範義解》，known PID `1272168`，`fulltext_only_direct_support`，Gemma `gemma4:e4b`，Top N 为 `本心ノ自由ト正理ノ伸長/正理/本心`，没有退回错误 PID。
  - `p4-fp4n5`：《奈良県における大麻問題》，known PID `13260166`，`fulltext_only_direct_support`，Top N 命中 `従前宗門ニ寄、神棚ヲ不設`，恢复并优于前次退化结果。
  - `p4-fp4n9`：《静岡県で大麻につき流言》，known PID `13260166`，`fulltext_only_direct_support`，Top N 命中 `静岡県で大麻につき流言`、`大麻ヲ水火ニ投ズ`、`伊勢皇太神ノ大麻`，恢复到正确正文页。
- 外交论文输出目录：`output/historical_citation_next_stage_diplomacy_problem_samples_goal_20260504`
  - `p2-fp2n8`：《山縣有朋意見書》，source type `contained_document`，known PID `3025431`，`fulltext_only_partial_support`；Gemma 选 `ctx1=復讐`，能支持日俄/满洲相关方向，但不足以完全支撑论文句子的具体表述。
  - `p6-fp6n6`：华盛顿会议比例问题，known PID `11927523`，`fulltext_only_partial_support`；Top N 中 `ctx2=米国案ノ十対六` 被 Gemma 选为 best context，`ctx3=海軍軍備制限問題@p8` 已降为 `front_matter_body_lead`。
  - `p4-fp4n5`：巴黎和会/委任统治问题，mismatch recheck 后 known PID `11923430`，`fulltext_only_partial_support`；Top N 为 `牧野男`、`委任統治`、`牧野委員`，没有停在全站泛命中。

新增/更新回归测试：
- `test_source_resolver_diary_adds_configured_claim_facets_to_plan`
- `test_source_resolver_kindai_taima_uses_configured_facets`
- `test_volume_series_early_general_context_is_front_matter_body_lead`
- `test_pdf_next_stage_slow_events_fallback_to_phase_total`

验证：
- 本轮新增 targeted tests 通过：`Ran 5 tests in 0.244s OK`。
- 完整单测通过：`Ran 251 tests in 262.268s OK (skipped=5)`。
- 宗教/外交问题小样本均已完成；未重跑两篇论文全量。

下一步优化方向：
- 外交文书仍应继续把静态 `claim_facets` 升级为文书题名级 query bucket，尤其是门户开放/John Hay 这类中英文人名与日文文书题名之间不直接对应的情况。
- `p2-fp2n8` 这类 contained document 当前已能进入目标 PID，但仍需要更强的“论文句子动作词 -> 史料日文表达”扩展，例如 `復讐/協商/共同經營/満洲` 之间的组合权重。
- 对 source mismatch 阶段增加更细粒度的 progress：目前只有 candidate 级别耗时，后续应区分元数据检索、候选排序、source_found 写入三段，便于全量时定位慢点。
