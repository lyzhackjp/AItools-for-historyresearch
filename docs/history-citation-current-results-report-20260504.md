# History Citation 引文匹配结果报告（最近全量 + 优化小样本）

生成日期：2026-05-04
报告范围：仅汇总最近一次两篇 PDF 论文全量测试结果，以及随后几轮优化中的问题小样本精核结果。
不含内容：不汇总早期 Word 成功范例，不展开开发日志，不重跑全量。

## 一、状态说明

| 状态 | 含义 | 本报告中的证据等级 |
|---|---|---|
| `source_found` | 已找到可进入后续核查的来源候选；通常尚未完成 OCR/全文上下文/LLM 支持性判断 | 来源定位 |
| `source_mismatch` | 当前自动流程未找到可信来源候选，或候选与脚注不匹配 | 需人工复核或后续 resolver 补强 |
| `fulltext_only_direct_support` | 在目标 NDL PID 内通过全文命中/上下文扩展取得直接支持，Gemma 精核认为支持论文句子 | 弱到中等证据；可作为不可下载材料的自动核验结果 |
| `fulltext_only_partial_support` | 来源和相关上下文正确，但只支持论文句子的部分内容，仍缺少关键限定或完整表述 | 部分支持；需人工复核或扩展查询 |

LLM 精核模型：`gemma4:e4b`。
主要证据入口：NDL Digital Collection 目标 PID 内全文命中、SNIPPET 上下文扩展、IIIF/fulltext-json 可用性记录、清洗后日文上下文。

## 二、最近全量测试总览

最近全量测试目录：`output/historical_citation_pdf_fullrun_20260501_post_strict_pid`

### 1. 《论近代日本〈明治宪法〉中的“信教自由”》

| 项目 | 数值 |
|---|---:|
| PDF 脚注数 | 54 |
| 引文候选数 | 45 |
| `source_found` | 43 |
| `source_mismatch` | 2 |
| `download_failed` / `ocr_failed` / `page_mapping_unavailable` | 0 |

结论：宗教论文全量阶段已经基本完成来源定位，主要剩余问题不是批量失败，而是少数现代研究和析出材料需要单独核查。

### 2. 《一战后日本对美协调外交的形成及其原因》

| 项目 | 数值 |
|---|---:|
| PDF 脚注数 | 51 |
| 引文候选数 | 43 |
| `source_found` | 31 |
| `source_mismatch` | 12 |
| `download_failed` / `ocr_failed` / `page_mapping_unavailable` | 0 |

结论：外交论文全量阶段的主要问题集中在《日本外交文書》卷册 PID 映射、现代研究书目桥接，以及少数日记/资料集材料。后续优化小样本已证明其中部分类型可以通过专门 resolver 改善。

## 三、全量剩余警报索引

### 宗教论文

| 候选 | 脚注 | 来源题名 | 来源类型 | 当前问题 |
|---|---|---|---|---|
| `p3-fp3n7` | `p3n7` | 天皇の祭祀 | secondary scholarship | 现代研究，应按书目信息和页码核对，不宜强套原始史料全文命中 |
| `p4-fp4n8` | `p4n8` | 〈日新新聞〉第二七号の記事 | source collection | 已知 host PID `13260166`，但需在宿主 PID 内继续用析出题名和限定词扩搜 |

### 外交论文

| 候选 | 脚注 | 来源题名 | 来源类型 | 当前问题 |
|---|---|---|---|---|
| `p2-fp2n3` | `p2n3` | 日本外交文書 | volume series | 第 38 卷第 1 册卷册 PID 映射缺失 |
| `p2-fp2n6` | `p2n6` | 日本外交文書 | volume series | 第 42 卷第 1 册卷册 PID 映射缺失 |
| `p3-fp3n4` | `p3n4` | 日本外交文書 | volume series | 大正三年第 3 册卷册 PID 映射缺失 |
| `p3-fp3n5` | `p3n5` | 日本外交文書 | volume series | 日本外交文書卷册/文书题名级定位不足 |
| `p3-fp3n8` | `p3n8` | 日本外交文書 | volume series | 日本外交文書卷册/文书题名级定位不足 |
| `p4-fp4n4` | `p4n4` | 原内閣成立後自第一回至第七回／第五回 | monograph | 资料题名复杂，需资料集/会议笔记类 resolver |
| `p4-fp4n5` | `p4n5` | 日本外交文書 | volume series | 全量时 source mismatch；优化小样本已改进，见下文 |
| `p5-fp5n3` | `p5n3` | 日本外交文書 | volume series | 大正八年第 3 册上卷卷册 PID 映射缺失 |
| `p6-fp6n1` | `p6n1` | 翠雨庄日记：临时外交调查委员会会议笔记等 | monograph | 书目候选存在，但自动匹配分数不足，需元数据桥接 |
| `p6-fp6n2` | `p6n2` | 日本外交文書 | volume series | 大正九年第 2 册上卷卷册 PID 映射缺失 |
| `p7-fp7n2` | `p7n2` | 日米関係史：摩擦と協調の一四〇年 | monograph | 现代研究书目，NDL 自动命中弱 |
| `p8-fp8n3` | `p8n3` | 踌躇的霸权：美国崛起后的身份困惑与秩序追求 | monograph | 中文现代研究，NDL 不适合作为主要自动全文来源 |

## 四、优化小样本精核总览

### 宗教论文小样本

输出目录：`output/historical_citation_next_stage_religion_problem_samples_goal_20260504`

| 候选 | 脚注 | 来源 | PID | 精核状态 | Gemma best context |
|---|---|---|---|---|---|
| `p3-fp3n1` | `p3n1` | 帝国憲法義解・皇室典範義解 | `1272168` | `fulltext_only_direct_support` | `ctx2` |
| `p4-fp4n5` | `p4n5` | 奈良県における大麻問題 | `13260166` | `fulltext_only_direct_support` | `ctx1` |
| `p4-fp4n9` | `p4n9` | 静岡県で大麻につき流言 | `13260166` | `fulltext_only_direct_support` | `ctx2` |

本组结论：三条均恢复或超过优化前效果，尤其是用户指出曾退化的 `p4n5`、`p4n9` 已重新命中正文上下文。

### 外交论文小样本

输出目录：`output/historical_citation_next_stage_diplomacy_problem_samples_goal_20260504`

| 候选 | 脚注 | 来源 | PID | 精核状态 | Gemma best context |
|---|---|---|---|---|---|
| `p2-fp2n8` | `p2n8` | 山縣有朋意見書 | `3025431` | `fulltext_only_partial_support` | `ctx1` |
| `p6-fp6n6` | `p6n6` | 日本外交文書：华盛顿会议军备限制问题 | `11927523` | `fulltext_only_partial_support` | `ctx2` |
| `p4-fp4n5` | `p4n5` | 日本外交文書：巴黎讲和会议经过概要 | `11923430` | `fulltext_only_partial_support` | `ctx1` |

本组结论：三条均从泛命中/错误路径推进到目标 PID 内上下文精核，但 Gemma 均判为部分支持，说明来源方向正确，论文句子仍有部分限定需要更多上下文或人工复核。

## 五、逐条引文匹配详情

### A. 宗教论文

#### `p3-fp3n1` / `p3n1`

| 字段 | 内容 |
|---|---|
| 论文句子 | 良心之自由和正理之伸张 |
| 脚注 | ［日］伊藤博文：《帝国憲法義解 · 皇室典範義解》，丸善 1935 年，第 52 页 |
| 目标 PID | `1272168` |
| 精核状态 | `fulltext_only_direct_support` |
| LLM | `gemma4:e4b` |
| 页/上下文 | NDL fulltext 定位到 pdf page 39 |

清洗后日文证据：

```text
本心ノ自由ト正理ノ伸長ハ數百年間沈淪茫味ノ境界ヲ經過シテ繼ニ光輝ヲ發揚スルノ今日ニ達シタリ
```

Gemma 判断：`本心ノ自由ト正理ノ伸長` 与论文句子的“良心之自由和正理之伸张”直接对应。
报告结论：支持。

#### `p4-fp4n5` / `p4n5`

| 字段 | 内容 |
|---|---|
| 论文句子 | 土真宗信徒不设神棚，不接受伊势神宫大麻 |
| 脚注 | 《奈良県における大麻問題》，《日本近代思想大系 5：宗教と国家》，第 184 页 |
| 目标 PID | `13260166` |
| 精核状态 | `fulltext_only_direct_support` |
| LLM | `gemma4:e4b` |
| 页/上下文 | NDL fulltext 定位到 pdf page 100 |

Top context：

| context | query | lead/body | score |
|---|---|---|---:|
| `ctx1` | 従前宗門ニ寄、神棚ヲ不設 | body_candidate | 24.6944 |
| `ctx2` | 宗門ニ寄、神棚ヲ不設 | body_candidate | 24.5833 |
| `ctx3` | 従前宗門ニ寄 | body_candidate | 24.4167 |

清洗后日文证据：

```text
従前宗門ニ寄、神棚ヲ不設、神宮大麻等不受者共モ有之候得共
```

Gemma 判断：直接出现“不设神棚”和“不受神宫大麻”等核心内容。
报告结论：支持。

#### `p4-fp4n9` / `p4n9`

| 字段 | 内容 |
|---|---|
| 论文句子 | 大麻的神符会化为蝴蝶，其时该户将遭时疫，故要在化蝶前焚毁、冲走大麻 |
| 脚注 | 《静岡県で大麻につき流言》，《日本近代思想大系 5：宗教と国家》，第 90 页 |
| 目标 PID | `13260166` |
| 精核状态 | `fulltext_only_direct_support` |
| LLM | `gemma4:e4b` |
| 页/上下文 | NDL fulltext 定位到 pdf page 103 |

Top context：

| context | query | lead/body | score |
|---|---|---|---:|
| `ctx1` | 静岡県で大麻につき流言 | body_candidate | 23.8611 |
| `ctx2` | 大麻ヲ水火ニ投ズ | body_candidate | 23.6944 |
| `ctx3` | 伊勢皇太神ノ大麻 | body_candidate | 23.6944 |

清洗后日文证据：

```text
大麻ノ神ノ字ガ蝶ニ化スルコトアリ、然ル時ハ挙家時疫ニ死絶ルトゾ。所詮蝶ニ化サヌ前ニ焼ケヨ流セヨ
```

Gemma 判断：直接对应“化蝶”“时疫”“焚毁/流走”的核心表述。
报告结论：支持。

### B. 外交论文

#### `p2-fp2n8` / `p2n8`

| 字段 | 内容 |
|---|---|
| 论文句子 | 两国与其相互竞争排挤，不如敞开胸襟共同经营中国东北；日本应与俄国发展亲密交情，缓和其复仇之心 |
| 脚注 | 大山梓编：《山县有朋意见书》，东京：原书房 1965 年，第 306 页 |
| 目标 PID | `3025431` |
| 精核状态 | `fulltext_only_partial_support` |
| LLM | `gemma4:e4b` |
| 页/上下文 | NDL fulltext 定位到 pdf page 199 |

Top context：

| context | query | lead/body | score |
|---|---|---|---:|
| `ctx1` | 復讐 | body_candidate | 9.9611 |
| `ctx2` | 提携 | body_candidate | 5.8611 |
| `ctx3` | 提携 | body_candidate | 5.3611 |

清洗后日文证据：

```text
戰後ニ於テ必然起ルヘキ露國ノ復讐ニ備エサル可ラサルノミナラス...支那ノ門戶開放ニ托シテ...我ハ露國...ト協商シテ小康ヲ保チ
```

Gemma 判断：上下文支持“俄国复仇”“日俄协商”“中国问题相关”的方向，但没有完整支持“敞开胸襟共同经营中国东北”和“发展亲密交情”的全部表述。
报告结论：部分支持；来源定位正确，但需要继续扩展动作词和同页邻近上下文。

#### `p6-fp6n6` / `p6n6`

| 字段 | 内容 |
|---|---|
| 论文句子 | 美国国务卿休斯在首次发言中提出限制海军军备提案，规定美、英、日主力舰比例为 10:10:6 |
| 脚注 | 外务省编：《日本外交文書》华盛顿会议军备限制问题，东京：外务省 1974 年，第 73-75、82-83、89、98-99 页 |
| 目标 PID | `11927523` |
| 精核状态 | `fulltext_only_partial_support` |
| LLM | `gemma4:e4b` |

Top context：

| context | query | lead/body | score |
|---|---|---|---:|
| `ctx1` | 海軍勢力比 | body_candidate | 18.5778 |
| `ctx2` | 米国案ノ十対六 | body_candidate | 18.5556 |
| `ctx3` | 海軍軍備制限問題 | front_matter_body_lead | 14.9444 |

清洗后日文证据：

```text
米国案ノ主力艦隊制限ノ基礎...米国案ノ十対六ノ比率ハ其根拠奈辺ニアルヤ
```

Gemma 判断：`米国案ノ十対六` 支持“美国方案中的十对六比例”，但上下文未同时出现休斯及完整 10:10:6 的三国比例绑定。
报告结论：部分支持；已避免把 page 8 纲目页作为主要证据。

#### `p4-fp4n5` / `p4n5`

| 字段 | 内容 |
|---|---|
| 论文句子 | 日本代表牧野伸显决定接受会议决定，从而使日本达成了第一个既定目标 |
| 脚注 | 外务省编：《日本外交文書》巴黎讲和会议经过概要，东京：外务省 1971 年，第 67-68、205-206、58-59 页 |
| 目标 PID | `11923430` |
| 精核状态 | `fulltext_only_partial_support` |
| LLM | `gemma4:e4b` |

Top context：

| context | query | lead/body | score |
|---|---|---|---:|
| `ctx1` | 牧野男 | body_candidate | 15.5333 |
| `ctx2` | 委任統治 | body_candidate | 15.0889 |
| `ctx3` | 牧野委員 | body_candidate | 13.9889 |

清洗后日文证据：

```text
英國ノ委任統治案ニ關シ一月二十九日ノ會議終了後牧野男ト「ロイド、ジョージ」トノ内談要領
```

Gemma 判断：上下文涉及牧野与英国委任统治案的会谈，能支持事件背景和谈判方向，但没有直接出现“决定接受会议决定”或“第一个既定目标达成”的完整表述。
报告结论：部分支持；全量中的 `source_mismatch` 已在小样本中修正为目标 PID 内部分支持。

## 六、运行质量与剩余风险

### 已改善项

| 问题 | 当前结果 |
|---|---|
| PDF 输入后可下载/不可下载材料混乱 | 小样本已能区分 downloadable monograph、source collection、volume series、contained document |
| NDL 入口错误 | 小样本均以 NDL Digital PID 内全文命中为核心证据 |
| 多个全文命中只取第一条 | 小样本已保留 Top N 上下文，并由 Gemma 选择 best context |
| 目录/纲目误判正文 | `p6-fp6n6` 中 page 8 已降为 `front_matter_body_lead` |
| 宗教论文 `p4n5/p4n9` 退化 | 已恢复为 `fulltext_only_direct_support` |
| 伊藤博文《帝国憲法義解・皇室典範義解》PID 误选 | 已稳定使用 PID `1272168` |

### 仍需注意

| 类型 | 说明 |
|---|---|
| 《日本外交文書》卷册映射 | 全量中仍有多条卷册 PID 缺失；小样本证明专门配置有效，但尚需把更多卷册补入映射表 |
| 现代研究 | `天皇の祭祀`、`日米関係史`、中文现代研究等不应强制按原始史料 OCR 标准判断 |
| 部分支持项 | 外交小样本三条均为 partial support，需要继续加入文书题名级 query bucket 和中日关键词转换 |
| 下载依赖 | 样本中多次记录 `restricted_download_dependency_missing: selenium`；但 NDL fulltext/IIIF 证据仍可用于不可下载或无 PDF 的材料 |

## 七、结论

最近全量测试显示，两篇 PDF 论文的基础来源定位已经可以批量运行：宗教论文 45 条候选中 43 条 `source_found`，外交论文 43 条候选中 31 条 `source_found`。主要瓶颈已从“PDF 流程整体不可用”转为“特定史料类型的 PID 映射和上下文择优”。

优化后的小样本结果显示，模块已经能在三类问题史料上稳定复用：

- 可下载/可全文图像材料：`帝国憲法義解・皇室典範義解`，PID `1272168`，直接支持。
- 宿主资料集析出材料：《日本近代思想大系 5：宗教と国家》，PID `13260166`，两条大麻相关引文均直接支持。
- 卷册型外交文书/析出文献：`日本外交文書` 与 `山縣有朋意見書` 已能进入目标 PID 和正文上下文，但多为部分支持，下一步重点应是扩大卷册 PID 表、文书题名级查询和中日关键词扩展。

本报告对应的程序验证结果：`Ran 251 tests in 262.268s OK (skipped=5)`。
