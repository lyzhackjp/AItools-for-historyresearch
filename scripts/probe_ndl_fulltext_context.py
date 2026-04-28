from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.historical_citation.ndl_fulltext_context import (
    expand_ndl_snippet_context,
    fetch_ndl_digital_item,
    probe_ndl_fulltext_context,
)


def _shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def render_probe_markdown(payload: Dict[str, Any], *, context_limit: int = 2400) -> str:
    probe = payload["probe"]
    lines: List[str] = [
        "# NDL 全文命中上下文探测报告",
        "",
        f"- PID: {probe.get('pid')}",
        f"- 题名: {probe.get('title') or 'n/a'}",
        f"- 状态: {probe.get('status')}",
        f"- 尝试关键词: {', '.join(probe.get('queries_tried') or [])}",
        f"- 说明: {probe.get('note') or ''}",
        "",
        "## 目标 PID 内命中",
    ]
    hits = probe.get("hits") or []
    if not hits:
        lines.append("")
        lines.append("未发现目标 PID 内 SNIPPET 命中。")
    for index, hit in enumerate(hits, start=1):
        lines.extend(
            [
                "",
                f"### 命中 {index}",
                "",
                f"- PDF 页码: {hit.get('pdf_page') or 'n/a'}",
                f"- cid: {hit.get('cid') or 'n/a'}",
                f"- query: {hit.get('query') or ''}",
                "",
                "```text",
                _shorten(hit.get("snippet") or "", context_limit),
                "```",
            ]
        )
    expanded = payload.get("expanded_contexts") or []
    if expanded:
        lines.extend(["", "## SNIPPET 接龙上下文"])
    for index, context in enumerate(expanded, start=1):
        lines.extend(
            [
                "",
                f"### 上下文窗口 {index}",
                "",
                f"- PDF 页码: {context.get('pdf_page') or 'n/a'}",
                f"- cid: {context.get('cid') or 'n/a'}",
                f"- 状态: {context.get('status')}",
                f"- 说明: {context.get('note')}",
                f"- 接龙证据数: {len(context.get('evidence_hits') or [])}",
                "",
                "```text",
                _shorten(context.get("context_text") or "", context_limit),
                "```",
            ]
        )
    context_windows = payload.get("context_keyword_windows") or []
    if context_windows:
        lines.extend(["", "## 辅助上下文窗口"])
    for item in context_windows:
        context = item.get("context") or {}
        seed_hit = item.get("seed_hit") or {}
        lines.extend(
            [
                "",
                f"### {item.get('label') or item.get('keyword')}",
                "",
                f"- keyword: {item.get('keyword') or ''}",
                f"- PDF 页码: {context.get('pdf_page') or seed_hit.get('pdf_page') or 'n/a'}",
                f"- cid: {context.get('cid') or seed_hit.get('cid') or 'n/a'}",
                f"- 说明: 辅助锚词生成的 SNIPPET 接龙窗口，供判断上下段落，不等同于 OCR 段落。",
                "",
                "```text",
                _shorten(context.get("context_text") or seed_hit.get("snippet") or "", context_limit),
                "```",
            ]
        )
    global_candidates = probe.get("global_candidates") or []
    if global_candidates:
        lines.extend(["", "## 全站全文候选线索"])
    for item in global_candidates:
        lines.extend(
            [
                "",
                f"- {item.get('title') or 'n/a'} | PID {item.get('pid') or 'n/a'} | {item.get('relation_to_target_pid')}",
            ]
        )
        hints = item.get("fulltext_hints") or []
        for hint in hints[:3]:
            lines.append(
                f"  - PDF {hint.get('pdf_page') or 'n/a'}: {_shorten(hint.get('snippet') or '', 180)}"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe NDL Digital fulltext snippets inside one PID.")
    parser.add_argument("--pid", required=True, help="NDL Digital Collection PID")
    parser.add_argument("--keyword", action="append", required=True, help="Keyword variant; can repeat")
    parser.add_argument("--global-query", action="append", default=[], help="Optional global fulltext fallback query")
    parser.add_argument("--max-global-results", type=int, default=8)
    parser.add_argument("--expand", action="store_true", help="Expand direct hits by snippet-edge chaining")
    parser.add_argument("--max-expand-hits", type=int, default=3)
    parser.add_argument(
        "--context-keyword",
        action="append",
        default=[],
        help="Auxiliary context anchor as LABEL=KEYWORD; can repeat",
    )
    parser.add_argument("--output", type=Path, help="Write markdown report to this path")
    parser.add_argument("--json-output", type=Path, help="Write raw JSON payload to this path")
    args = parser.parse_args()

    probe = probe_ndl_fulltext_context(
        args.pid,
        args.keyword,
        global_queries=args.global_query,
        max_global_results=args.max_global_results,
    )
    item_payload = fetch_ndl_digital_item(args.pid)
    expanded_contexts = []
    if args.expand:
        for hit in probe.hits[: max(0, args.max_expand_hits)]:
            expanded_contexts.append(
                expand_ndl_snippet_context(
                    args.pid,
                    hit,
                    item_payload=item_payload,
                ).to_dict()
            )
    context_keyword_windows = []
    for raw_item in args.context_keyword:
        label, separator, keyword = raw_item.partition("=")
        if not separator:
            label = raw_item
            keyword = raw_item
        sub_probe = probe_ndl_fulltext_context(args.pid, [keyword])
        if not sub_probe.hits:
            context_keyword_windows.append({"label": label, "keyword": keyword, "status": "no_direct_hit"})
            continue
        seed_hit = sub_probe.hits[0]
        expanded = expand_ndl_snippet_context(
            args.pid,
            seed_hit,
            item_payload=item_payload,
        )
        context_keyword_windows.append(
            {
                "label": label,
                "keyword": keyword,
                "status": "direct_hit",
                "seed_hit": seed_hit.to_dict(),
                "context": expanded.to_dict(),
            }
        )
    payload = {
        "probe": probe.to_dict(),
        "expanded_contexts": expanded_contexts,
        "context_keyword_windows": context_keyword_windows,
    }
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = render_probe_markdown(payload)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
