from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.historical_citation.llm_review import (
    DEFAULT_OLLAMA_MODEL_POLICY_PATH,
    OllamaChatClient,
    evaluate_review_client,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate local Ollama models for historical citation precision review."
    )
    parser.add_argument(
        "--model",
        action="append",
        default=[],
        help="Ollama model to evaluate. May be repeated. Defaults to installed models.",
    )
    parser.add_argument(
        "--output-dir",
        default="output/historical_citation_llm_model_evaluation_20260428",
        help="Ignored output directory for JSON/Markdown evaluation reports.",
    )
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument(
        "--minimum-score",
        type=float,
        default=0.67,
        help="Minimum exact decision score required for a model to enter the generated allowlist.",
    )
    parser.add_argument(
        "--install-policy",
        action="store_true",
        help=(
            "Also write the generated allowlist to config/historical_citation_ollama_model_policy.json. "
            "That local policy file is ignored by Git."
        ),
    )
    return parser


def list_ollama_models(base_url: str = "http://127.0.0.1:11434") -> List[str]:
    import requests

    response = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=10)
    response.raise_for_status()
    return [item.get("name", "") for item in response.json().get("models", []) if item.get("name")]


def render_markdown(results: Dict[str, Any]) -> str:
    lines = [
        "# 历史引文核对本地 LLM 精核评估",
        "",
        f"- 生成时间: {results.get('created_at')}",
        f"- 模型数: {len(results.get('models', []))}",
        "",
        "## 总览",
        "",
    ]
    for item in results.get("models", []):
        lines.append(
            f"- `{item.get('model')}` | score={item.get('score')} | "
            f"passed={item.get('passed')} | preferred_family={item.get('preferred_model_family')} | "
            f"formal_allowed={item.get('formal_review_allowed')} | "
            f"latency_ms={item.get('latency_ms')}"
        )
    lines.extend(["", "## 分项", ""])
    for item in results.get("models", []):
        lines.append(f"### {item.get('model')}")
        lines.append("")
        for case in item.get("cases", []):
            lines.append(
                f"- {case.get('case_id')} | expected={case.get('expected_decision')} "
                f"| actual={case.get('actual_decision')} | decision_ok={case.get('decision_ok')} "
                f"| exact_ok={case.get('exact_ok')} | error={case.get('llm_error') or 'none'}"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    models = args.model or list_ollama_models()
    payload: Dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "models": [],
    }
    for model in models:
        client = OllamaChatClient(model=model, timeout=args.timeout)
        result = evaluate_review_client(client, minimum_score=args.minimum_score)
        payload["models"].append(result)

    json_path = output_dir / "llm_model_evaluation.json"
    md_path = output_dir / "llm_model_evaluation.md"
    policy_path = output_dir / "model_policy.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")

    allowed = [
        item.get("model")
        for item in payload["models"]
        if item.get("passed") and item.get("preferred_model_family")
    ]
    policy = {
        "created_at": payload["created_at"],
        "allowlist": allowed,
        "blocklist": [],
        "minimum_score": args.minimum_score,
        "evaluated_models": [
            {
                "model": item.get("model"),
                "score": item.get("score"),
                "passed": item.get("passed"),
                "preferred_model_family": item.get("preferred_model_family"),
            }
            for item in payload["models"]
        ],
        "note": "Models not in allowlist should be treated as contrast-only unless explicitly overridden.",
    }
    policy_path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")
    installed_policy = None
    if args.install_policy:
        DEFAULT_OLLAMA_MODEL_POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_OLLAMA_MODEL_POLICY_PATH.write_text(
            json.dumps(policy, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        installed_policy = str(DEFAULT_OLLAMA_MODEL_POLICY_PATH.resolve())
    print(
        json.dumps(
            {
                "json": str(json_path.resolve()),
                "markdown": str(md_path.resolve()),
                "policy": str(policy_path.resolve()),
                "installed_policy": installed_policy,
                "allowed": allowed,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
