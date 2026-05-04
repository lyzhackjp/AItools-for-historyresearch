from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.historical_citation.fullrun import (
    finalize_partial_file,
    load_json_payload,
    merge_result_payloads,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run PDF historical citation verification in resumable batches and finalize partial results."
    )
    parser.add_argument("pdf_path", help="Path to the input PDF paper")
    parser.add_argument("--output-dir", default="output/historical_citation_pdf_fullrun")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--max-search-results", type=int, default=3)
    parser.add_argument("--page-window", type=int, default=4)
    parser.add_argument("--ocr-model", default="ndlocr_lite")
    parser.add_argument("--platform", action="append", default=["ndl"])
    parser.add_argument("--restricted-download", action="store_true")
    parser.add_argument("--download-source", action="store_true")
    parser.add_argument("--skip-ndl-fulltext", action="store_true")
    parser.add_argument("--review-model", default="gemma4:e4b")
    parser.add_argument("--review-timeout-seconds", type=int, default=300)
    parser.add_argument(
        "--candidate-id",
        action="append",
        default=[],
        help="Restrict next-stage processing to one or more candidate_id values. May be repeated or comma-separated.",
    )
    parser.add_argument(
        "--footnote-id",
        action="append",
        default=[],
        help="Restrict next-stage processing to one or more footnote_id values. May be repeated or comma-separated.",
    )
    parser.add_argument("--no-next-stage", action="store_true")
    parser.add_argument("--next-stage-timeout", type=int, default=600)
    parser.add_argument("--retry-timeout", type=int, default=900)
    parser.add_argument("--finalize-partial", help="Only finalize an existing verification_results.partial.json")
    return parser


def _run(cmd: List[str]) -> None:
    subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True)


def _load_candidate_count(pdf_path: str, output_dir: Path, args: argparse.Namespace) -> int:
    parse_dir = output_dir / "parse"
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "run_historical_citation_pdf_verifier.py"),
        pdf_path,
        "--parse-only",
        "--output-dir",
        str(parse_dir),
        "--ocr-model",
        args.ocr_model,
    ]
    if args.skip_ndl_fulltext:
        cmd.append("--skip-ndl-fulltext")
    _run(cmd)
    payload = load_json_payload(parse_dir / "pdf_parse_package.json")
    return int((payload.get("summary") or {}).get("candidate_count") or 0)


def _run_base_batches(pdf_path: str, output_dir: Path, total: int, args: argparse.Namespace) -> List[Dict[str, Any]]:
    payloads: List[Dict[str, Any]] = []
    batch_size = max(1, int(args.batch_size or 1))
    for offset in range(0, total, batch_size):
        batch_dir = output_dir / f"base_{offset:04d}_{min(offset + batch_size, total):04d}"
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "run_historical_citation_pdf_verifier.py"),
            pdf_path,
            "--output-dir",
            str(batch_dir),
            "--max-search-results",
            str(args.max_search_results),
            "--page-window",
            str(args.page_window),
            "--ocr-model",
            args.ocr_model,
            "--offset",
            str(offset),
            "--limit",
            str(batch_size),
            "--review-model",
            args.review_model,
        ]
        for platform in args.platform or []:
            cmd.extend(["--platform", platform])
        if args.download_source:
            cmd.append("--download-source")
        if args.restricted_download:
            cmd.append("--restricted-download")
        if args.skip_ndl_fulltext:
            cmd.append("--skip-ndl-fulltext")
        _run(cmd)
        final_json = batch_dir / "verification_results.json"
        partial_json = batch_dir / "verification_results.partial.json"
        if final_json.exists():
            payloads.append(load_json_payload(final_json))
        elif partial_json.exists():
            payloads.append(finalize_partial_file(partial_json, output_dir=batch_dir))
    return payloads


def _write_combined(output_dir: Path, payload: Dict[str, Any]) -> Path:
    combined_dir = output_dir / "combined"
    combined_dir.mkdir(parents=True, exist_ok=True)
    path = combined_dir / "verification_results.combined.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _run_next_stage(pdf_path: str, combined_json: Path, output_dir: Path, args: argparse.Namespace) -> None:
    if args.no_next_stage:
        return
    next_stage_dir = output_dir / "next_stage"
    cache_dir = output_dir / "download_ocr_cache"
    base_cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "refine_historical_citation_pdf_next_stage.py"),
        pdf_path,
        "--combined-json",
        str(combined_json),
        "--output-dir",
        str(next_stage_dir),
        "--download-cache-dir",
        str(cache_dir),
        "--max-search-results",
        str(args.max_search_results),
        "--page-window",
        str(args.page_window),
        "--ocr-model",
        args.ocr_model,
        "--download-timeout-seconds",
        str(args.next_stage_timeout),
        "--review-model",
        args.review_model,
        "--review-timeout-seconds",
        str(args.review_timeout_seconds),
        "--no-resume",
    ]
    if args.restricted_download:
        base_cmd.append("--restricted-download")
    if args.platform:
        base_cmd.extend(["--platform-names", *args.platform])
    for candidate_id in getattr(args, "candidate_id", []) or []:
        base_cmd.extend(["--candidate-id", candidate_id])
    for footnote_id in getattr(args, "footnote_id", []) or []:
        base_cmd.extend(["--footnote-id", footnote_id])
    _run(base_cmd)
    retry_cmd = [part for part in base_cmd if part != "--no-resume"]
    retry_cmd.extend(["--retry-download-timeouts", "--download-timeout-seconds", str(args.retry_timeout)])
    _run(retry_cmd)


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.finalize_partial:
        finalized = finalize_partial_file(args.finalize_partial, output_dir=output_dir, require_complete=False)
        print(json.dumps(finalized.get("artifacts") or {}, ensure_ascii=False, indent=2))
        return 0

    total = _load_candidate_count(args.pdf_path, output_dir, args)
    payloads = _run_base_batches(args.pdf_path, output_dir, total, args)
    combined = merge_result_payloads(payloads, paper_id=args.pdf_path)
    combined_json = _write_combined(output_dir, combined)
    _run_next_stage(args.pdf_path, combined_json, output_dir, args)
    print(json.dumps({"combined_json": str(combined_json.resolve()), "total_candidates": total}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
