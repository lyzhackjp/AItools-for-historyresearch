# history-citation 模块使用流程图

## 总体流程

```mermaid
flowchart TD
    A["输入 Word 论文 (.docx)"] --> B["解析正文、脚注、段落"]
    B --> C["生成 CitationCandidate"]
    C --> D["解析脚注题名、作者、页码"]
    D --> E{"是否析出文献?"}
    E -- "是" --> F["记录 contained_title / host_title"]
    E -- "否" --> G["普通题名检索"]
    F --> H["平台适配器检索"]
    G --> H
    H --> I["NDL / Japan Search / IA 等候选"]
    I --> J["元数据评分、候选过滤、source trial 记录"]
    J --> K{"候选是否可下载?"}
    K -- "可下载" --> L["页码映射与页窗计划"]
    L --> M["公共下载或受限浏览器下载"]
    M --> N["PDF/截图/OCR"]
    N --> O["中文译文与日文 OCR 对齐"]
    O --> P["LLM review / 证据线索复核"]
    P --> Q["matched / needs_manual_review / download_failed"]
    K -- "不可下载或下载失败" --> R["NDL 全文 SNIPPET 探测"]
    R --> S{"目标 PID 内命中?"}
    S -- "是" --> T["记录 PDF 页、cid、snippet_expanded"]
    S -- "否" --> U["全站候选线索 same_pid / different_pid"]
    T --> V["fulltext_only_hit 或待下载页窗线索"]
    U --> V
    Q --> W["OCR/全文交叉验证"]
    V --> W
    W --> X["Markdown/JSON 报告写入 output/"]
    X --> Y["隐私与 GitHub 上传安全检查"]
```

## NDL 全文命中证据流

```mermaid
flowchart TD
    A["输入 PID + 查询词"] --> B["获取 NDL item detail"]
    B --> C["提取 bundle ids 与 cid->PDF页映射"]
    C --> D["fulltext/search SNIPPET"]
    D --> E{"是否有目标 PID 命中?"}
    E -- "有" --> F["direct_hit"]
    F --> G["记录 query / snippet / PDF页 / cid"]
    G --> H["同一 cid 边缘词接龙"]
    H --> I["snippet_expanded 上下文窗口"]
    E -- "无" --> J["全站 item/search + SNIPPET"]
    J --> K["标记 same_pid 或 different_pid"]
    K --> L["作为弱线索，不替代 OCR"]
```

## OCR 与全文交叉验证

```mermaid
flowchart TD
    A["checkpoint candidate"] --> B{"是否已有 source_pdf 和 matched_japanese?"}
    B -- "有" --> C["downloadable_ocr 模式"]
    B -- "无" --> D["fulltext_only 模式"]
    C --> E["读取 downloaded_page_range"]
    C --> F["目标 PID 全文命中"]
    F --> G{"全文 PDF 页是否在下载页窗内?"}
    G -- "是" --> H["计算 OCR/全文相似度"]
    H --> I{"相似度足够?"}
    I -- "是" --> J["cross_validated"]
    I -- "否" --> K["page_cross_validated_text_needs_review"]
    G -- "否" --> L["needs_review"]
    D --> M["目标 PID 全文命中"]
    M --> N{"是否有 SNIPPET?"}
    N -- "是" --> O["fulltext_only_hit"]
    N -- "否" --> P["no_fulltext_hit"]
```

## 小模型安全调用流程

```mermaid
flowchart TD
    A["用户给 DOCX 或 checkpoint"] --> B["使用 historical-citation-runner skill"]
    B --> C["先 search-only"]
    C --> D["阅读 partial report"]
    D --> E["少量 only-candidate-id 续跑"]
    E --> F["必要时 probe fulltext"]
    F --> G["必要时 cross_validate"]
    G --> H["输出本地报告路径和状态摘要"]
    H --> I["运行 GitHub safety check"]
```

## 证据等级

| 等级 | 状态 | 说明 |
| --- | --- | --- |
| 强 | `matched`, `cross_validated` | 已下载/OCR，且全文或对齐证据支持 |
| 中 | `page_cross_validated_text_needs_review` | 页窗一致，但 OCR/全文文本仍需人工看版面 |
| 弱 | `fulltext_only_hit` | NDL 全文片段能定位 PDF 页，但未下载/OCR |
| 线索 | `same_pid` / `different_pid` global candidate | 全站全文搜索线索，不能代替目标书证据 |
| 未定 | `source_unavailable`, `source_not_found`, `page_mapping_unavailable` | 平台或页码条件不足，需补查 |
