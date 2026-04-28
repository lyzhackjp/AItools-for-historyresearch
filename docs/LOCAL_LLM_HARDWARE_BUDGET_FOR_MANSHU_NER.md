# 本地部署大模型用于《满洲绅士录》NER 的性能与预算估算报告

## 一、报告目的

本报告基于当前工作区内对《满洲绅士录》第211页前三个人物条目的多轮测试结果，重新估算本地部署大模型的性能、预算与购买价值。

本次估算不再只考虑 Qwen 系模型，也纳入 DeepSeek、Kimi、GLM、Llama、Mistral、Gemma、gpt-oss 等非 Qwen 系开放权重模型。目标是回答三个实际问题：

- 为当前《满洲绅士录》全书级切分、OCR、清洗、NER 流程购买本地硬件是否划算。
- Mac mini 能否部署足够强的本地模型，以替代或接近 API 模型。
- 如果未来想建立长期历史学本地 AI 实验环境，应选择什么硬件档位。

## 二、当前实测基线

我们此前已经完成三类基线测试：

- 本机 Ollama 小模型 NER 测试。
- DashScope Qwen API 非 `qwen3.6-plus` 模型横评。
- 针对输出内容的人工复核，包括人物边界、履历拆分、时间错补、地点推断、跨条目污染等问题。

当前最有参考价值的 API 基线如下：

| 方案 | 本项目 NER 质量 | 成本估算 | 备注 |
| --- | --- | ---: | --- |
| 本机 Ollama `qwen3:4b` | 能出 JSON，但会错补时间、推断地点 | 免费 | 只能作为草稿 |
| API `qwen3.5-35b-a3b` | 当前性价比最佳之一 | 约 0.008 元 / 3 人 | 可作为主基线 |
| API `qwen3.5-397b-a17b` | 适合疑难复核 | 约 0.021 元 / 3 人 | 质量更强但成本更高 |
| API `qwen3.6-35b-a3b` | 实测强且快 | 价格未可靠定位 | 如果免费额度可用，很值得继续测 |
| API `qwen3.6-flash` | 实测强且快 | 价格未可靠定位 | 可能是 Plus 外的高性价比选择 |

核心判断是：如果只计算当前《满洲绅士录》项目的 NER API 成本，购买本地硬件很难回本。以 `qwen3.5-35b-a3b` 的估算成本看，即使全书按 800-1000 次类似调用计算，NER 主调用成本也很可能只是几十元级别。即使加入重试、复核、prompt 冗余，总成本仍远低于一台 Mac mini 或 Mac Studio。

因此，购买本地硬件的价值不应主要理解为省 API 钱，而应理解为：

- 隐私与数据本地化。
- 可反复实验 prompt、后处理和模型组合。
- 建立长期历史资料处理实验平台。
- 未来可用于更多书籍、档案、OCR、RAG、轻量微调等任务。

## 三、非 Qwen 开放权重模型评估

下面按照本项目 NER 场景，对当前较重要的非 Qwen 系开放权重或开放模型进行估算。这里的“能跑”主要指 4bit 或其他低比特量化推理，不等同于全精度部署。

| 模型家族 | 参数形态 | Mac mini 64GB 可行性 | 对本项目 NER 的预估 |
| --- | --- | --- | --- |
| `GLM-4.5-Air` | 约 106B total / 12B active MoE | 64GB 很紧，128GB 更合理 | 中文能力强，非 Qwen 中最值得测的主力候选 |
| `GLM-4.5` | 约 355B total / 32B active MoE | Mac mini 不合适，建议 256GB+ | 有机会接近强 API，但硬件预算陡增 |
| `DeepSeek-V3/R1` | 约 671B total / 37B active MoE | Mac mini 不合适，256GB 也偏紧，512GB 更现实 | 推理强，但结构化 NER 未必比 Qwen/GLM 省心 |
| `Kimi K2` | 约 1T total / 32B active MoE | Mac mini 不合适，512GB 级别起步 | 强在 agent/code，部署成本过高 |
| `Llama 4 Scout` | 约 109B total / 17B active MoE | 64GB 很紧，128GB 更现实 | 英文/多模态强，日文历史 NER 未必优于 Qwen/GLM |
| `Llama 4 Maverick` | 约 400B total / 17B active MoE | Mac mini 不合适，建议 256GB+ | 强但部署重，NER 性价比不突出 |
| `Mistral Large 2` | 约 123B dense | Mac mini 64GB 不够稳，128GB 合适 | 多语言不错，但 CJK 史料 NER 未必优于 Qwen/GLM |
| `Mistral Small 3.1` / `Magistral Small` | 约 24B dense | Mac mini 64GB 合适 | 可作为非中文模型对照 |
| `Gemma 3 27B` | 约 27B dense | Mac mini 64GB 合适 | 结构化能力可能不错，但 CJK 史料需实测 |
| `gpt-oss-20b` | 约 20B 级开放权重模型 | Mac mini 64GB 合适 | 可作为结构化与推理对照 |
| `gpt-oss-120b` | 约 120B 级开放权重模型 | Mac mini 64GB 不建议，128GB 更稳 | 可测，但未必比 GLM/Qwen 更适合本任务 |

需要特别注意的是，MoE 模型的 active 参数只代表每 token 激活计算量，不代表部署时只需要加载 active 参数。实际本地推理通常仍需要让大量权重常驻内存，或者依赖复杂的 offload 策略。因此，`Kimi K2`、`DeepSeek-V3/R1`、`Llama 4 Maverick` 这类总参数极大的模型，虽然 active 参数看起来不夸张，但并不适合 Mac mini 64GB。

## 四、硬件档位与预算估算

### 1. 继续使用 API

| 项目 | 估算 |
| --- | --- |
| 硬件投入 | 0 元 |
| 模型能力 | 可使用 `qwen3.5-35b-a3b`、`qwen3.5-397b-a17b`、`qwen3.6-*` 等 |
| 成本 | 当前 NER 主流程可能几十元级别 |
| 优点 | 质量高，部署成本低，维护少 |
| 缺点 | 数据离开本地，依赖额度、网络和平台政策 |

这是当前项目最理性的选择。

### 2. Mac mini M4 Pro 64GB

| 项目 | 估算 |
| --- | --- |
| 推荐配置 | M4 Pro / 64GB 统一内存 / 1TB 或 2TB SSD |
| 预算 | 约 1.8-2.2 万元，具体取决于渠道和存储配置 |
| 舒适模型 | 20B-35B Q4/Q5，Gemma 27B，Mistral 24B，gpt-oss-20B |
| 勉强模型 | 70B Q4，部分 100B MoE 低比特 |
| 不建议模型 | DeepSeek 671B、Kimi K2、Llama 4 Maverick、Qwen3-235B 全量低比特 |

Mac mini 64GB 的价值是本地实验，而不是稳定替代强 API。它适合跑中型模型、做隐私草稿、批量预处理和 prompt/后处理实验。如果购买，应明确它是“历史 AI 实验机”，不是“强 API 替代机”。

### 3. Mac Studio M4 Max 128GB

| 项目 | 估算 |
| --- | --- |
| 推荐配置 | M4 Max / 128GB 统一内存 / 2TB SSD |
| 预算 | 约 3-4 万元级 |
| 舒适模型 | 30B、32B、70B Q4/Q5 |
| 可实验模型 | GLM-4.5-Air、Mistral Large 2、gpt-oss-120B 低比特 |
| 优点 | 真正有意义的本地大模型入门主力 |
| 缺点 | 仍不适合 Kimi K2、DeepSeek 671B 等巨型 MoE |

如果目标是长期本地化、希望明显强于 Mac mini，128GB Mac Studio 是更合理的起点。

### 4. Mac Studio M3 Ultra 256GB 或更高

| 项目 | 估算 |
| --- | --- |
| 推荐配置 | M3 Ultra / 256GB 或更高统一内存 |
| 预算 | 约 5-8 万元级，随配置大幅变化 |
| 舒适模型 | 70B、100B、120B 低比特 |
| 可实验模型 | 235B、355B 级低比特或部分 offload |
| 不足 | 对 DeepSeek 671B、Kimi K2 仍未必舒适 |

这个档位已经从“做项目”转向“做本地大模型研究平台”。如果只是为了《满洲绅士录》NER，不建议。

### 5. 512GB 级 Mac Studio 或多 GPU 工作站

| 项目 | 估算 |
| --- | --- |
| 预算 | 10 万元级或更高 |
| 可运行方向 | DeepSeek 671B、Kimi K2、Llama 4 Maverick 等低比特部署 |
| 优点 | 能真正探索巨型开放权重模型 |
| 缺点 | 远超当前项目需求，维护、功耗、成本都高 |

不建议为当前项目单独购买。

## 五、本地性能预估

| 机器 | 20B-30B Q4 | 32B-35B Q4 | 70B Q4 | 100B+ MoE/Q4 |
| --- | --- | --- | --- | --- |
| Mac mini M4 Pro 64GB | 舒服 | 可用 | 勉强或受上下文限制 | 不推荐 |
| Mac Studio M4 Max 128GB | 很舒服 | 很舒服 | 可用 | 部分可用 |
| Mac Studio M3 Ultra 256GB | 很舒服 | 很舒服 | 很舒服 | 可实验 |
| 512GB 级机器 | 很舒服 | 很舒服 | 很舒服 | 才比较现实 |

对当前 NER 任务，本地模型的质量排序大概率不是“参数越大越好”，而是：

1. 是否能稳定保持人物边界。
2. 是否严格遵守 evidence_text 必须来自原文。
3. 是否避免把出生年、学历年、家庭成员年份错补到履历事件。
4. 是否避免把日文旧字体、机构名、年号擅自现代化。
5. 是否能处理 OCR 字段名误识，例如 `聖應`、`建歴`、`續柄` 等。

这意味着一些通用推理很强的大模型，在本任务中未必比 Qwen/GLM 更好。尤其是 DeepSeek、Kimi、Llama、Mistral 等模型，可能需要更强 prompt 和后处理约束，才能避免字段现代化、解释化或过度推理。

## 六、推荐的本地模型测试优先级

如果未来购入 Mac mini M4 Pro 64GB，推荐按以下顺序测试非 Qwen 模型：

| 优先级 | 模型 | 理由 |
| --- | --- | --- |
| 1 | `GLM-4.5-Air` | 中文能力强，可能是非 Qwen 中最适合历史 NER 的候选 |
| 2 | `Gemma 3 27B` | Mac mini 64GB 可承受，结构化输出可能稳定 |
| 3 | `Mistral Small 3.1 24B` / `Magistral Small` | 非中文模型对照，检验跨语种史料能力 |
| 4 | `gpt-oss-20b` | 本地成本低，可做结构化与推理对照 |
| 5 | `Llama 4 Scout` | 需要更大内存更合理，Mac mini 64GB 不优雅 |

如果是 Mac Studio 128GB，则可增加：

- `GLM-4.5-Air` 高质量量化版本。
- `Mistral Large 2` 低比特版本。
- `gpt-oss-120b`。
- 70B 级 Llama 或 Qwen 对照模型。

如果是 256GB 以上机器，才考虑：

- `GLM-4.5`。
- `Qwen3-235B`。
- 更大规模 MoE 低比特实验。

DeepSeek 671B、Kimi K2、Llama 4 Maverick 这类模型，应放在 512GB 级或多 GPU 工作站预算下考虑。

## 七、购买建议

### 如果只服务当前《满洲绅士录》项目

不建议为了 NER 质量购买 Mac mini。

更理性的方案是：

1. 用 `qwen3.5-35b-a3b` 做全书 NER 初稿。
2. 对自动质检标记出的高风险条目，用 `qwen3.5-397b-a17b` 或 `qwen3.6-35b-a3b` / `qwen3.6-flash` 复核。
3. 继续加强规则后处理，重点检查时间错补、跨人物串项、地点推断、证据过长、字段现代化。

这个方案成本远低于硬件采购，且质量更可靠。

### 如果想建设长期本地历史 AI 实验环境

可以考虑购买 Mac mini M4 Pro 64GB，但请把它定位为实验机：

- 用于本地草稿。
- 用于隐私敏感材料的初步处理。
- 用于比较不同开源模型。
- 用于 OCR 后处理、规则质检、RAG、小规模结构化任务。

不要期待它稳定替代强 API。

### 如果目标是本地替代强 API

跳过 Mac mini，至少考虑 Mac Studio 128GB。

如果目标包括 DeepSeek、Kimi、Llama 4 Maverick、GLM-4.5 全量低比特等巨型模型，则应直接考虑 256GB-512GB 级设备或多 GPU 工作站。但从当前项目收益看，这一档位不划算。

## 八、最终倾向

我的最终建议是：

1. 短期不要急着购买 Mac mini。
2. 先用 `qwen3.5-35b-a3b` 跑 211-215 页或更大样本，建立真实全流程成本和质量基准。
3. 如果 API 成本和质量都可接受，就继续使用 API 主流程，把硬件预算保留。
4. 如果你确实希望长期做本地历史 AI 实验，再购买 Mac mini M4 Pro 64GB / 1TB 或 2TB。
5. 如果未来目标升级为强本地模型平台，再考虑 Mac Studio 128GB 起步。

一句话总结：

当前项目层面，API 更划算；长期实验层面，Mac mini 64GB 可买；强模型替代层面，Mac Studio 128GB 起步。

## 九、参考信息

- Apple 官方 Mac mini 技术规格：M4 Pro 款最高 64GB 统一内存，273GB/s 内存带宽。
- Apple 官方 Mac Studio 技术规格：M4 Max / M3 Ultra 支持更高统一内存与更高带宽，M3 Ultra 可上探至 512GB 级统一内存。
- DeepSeek 官方资料：DeepSeek-V3/R1 系列为约 671B total、37B active 的 MoE 模型。
- Kimi K2 模型资料：约 1T total、32B active MoE。
- GLM-4.5 模型资料：约 355B total、32B active；GLM-4.5-Air 约 106B total、12B active。
- Google Gemma 3 资料：Gemma 3 包含 1B、4B、12B、27B 规模，部分模型支持长上下文。
- Mistral Large 2 资料：约 123B dense，低比特部署仍需要较大显存/统一内存。
- OpenAI gpt-oss 资料：`gpt-oss-20b` 面向较小设备，`gpt-oss-120b` 面向更高显存设备。
- Meta Llama 4 / 相关部署资料：Scout、Maverick 为 MoE 架构，总参数与部署内存需求显著高于 active 参数直观数字。
