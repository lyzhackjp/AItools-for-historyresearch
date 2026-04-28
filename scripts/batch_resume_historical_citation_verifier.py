from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.historical_citation_verifier import HistoricalCitationVerifier


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run resumable historical citation verification one candidate at a time."
    )
    parser.add_argument("docx_path", help="Path to the input .docx paper")
    parser.add_argument(
        "--output-dir",
        default="output/historical_citation_resume",
        help="Directory for checkpoint, reports, and downloaded artifacts",
    )
    parser.add_argument(
        "--checkpoint-file",
        default=None,
        help="Optional explicit checkpoint JSON path",
    )
    parser.add_argument("--max-search-results", type=int, default=3)
    parser.add_argument("--page-window", type=int, default=4)
    parser.add_argument(
        "--ocr-page-window",
        type=int,
        default=None,
        help="Optional smaller page window for OCR/context extraction. Defaults to --page-window.",
    )
    parser.add_argument(
        "--download-max-attempts",
        type=int,
        default=3,
        help="Maximum restricted-download attempts per request.",
    )
    parser.add_argument("--ocr-model", default="ndlocr_lite")
    parser.add_argument(
        "--platform",
        action="append",
        default=[],
        help="Source platform to search. May be repeated.",
    )
    parser.add_argument(
        "--no-ndl-browser-fallback",
        action="store_true",
        help="Use NDL public API only during metadata search; skip slow browser fallback search.",
    )
    parser.add_argument(
        "--ignore-download-failure-cache",
        action="store_true",
        help="Retry downloads even when this candidate/page window is already cached as failed.",
    )
    parser.add_argument(
        "--candidate-timeout",
        type=int,
        default=900,
        help="Seconds allowed for each candidate before it is marked as blocking.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=None,
        help="Process at most this many remaining candidates in this batch.",
    )
    parser.add_argument(
        "--start-after",
        default=None,
        help="Skip remaining candidates until after this candidate id.",
    )
    return parser


def load_checkpoint(path: Path) -> Dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"results": {}, "processed_order": []}


def kill_process_tree(pid: int) -> None:
    if sys.platform != "win32":
        return
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def run_resume_command(
    command: List[str],
    *,
    timeout: int,
    log_path: Path,
) -> int:
    with log_path.open("w", encoding="utf-8", errors="replace") as log_handle:
        process = subprocess.Popen(
            command,
            cwd=str(PROJECT_ROOT),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_process_tree(process.pid)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=15)
            return 124


def mark_skipped(
    *,
    resume_script: Path,
    docx_path: Path,
    output_dir: Path,
    checkpoint_file: Optional[Path],
    candidate_id: str,
    reason: str,
) -> int:
    command = [
        sys.executable,
        str(resume_script),
        str(docx_path),
        "--output-dir",
        str(output_dir),
        "--skip-candidate-id",
        candidate_id,
        "--skip-reason",
        reason,
        "--report-only",
    ]
    if checkpoint_file is not None:
        command.extend(["--checkpoint-file", str(checkpoint_file)])
    completed = subprocess.run(command, cwd=str(PROJECT_ROOT), text=True)
    return completed.returncode


def main() -> int:
    args = build_parser().parse_args()
    docx_path = Path(args.docx_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = Path(args.checkpoint_file) if args.checkpoint_file else output_dir / "resume_checkpoint.json"
    resume_script = PROJECT_ROOT / "scripts" / "resume_historical_citation_verifier.py"
    log_dir = output_dir / "batch_resume_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    verifier = HistoricalCitationVerifier()
    parsed = verifier.parse_docx(str(docx_path))
    candidates = verifier.build_candidates(parsed["paragraphs"], parsed["footnotes"])

    checkpoint = load_checkpoint(checkpoint_path)
    processed_ids = set(checkpoint.get("results", {}))
    remaining = [candidate for candidate in candidates if candidate.candidate_id not in processed_ids]
    if args.start_after:
        seen_start = False
        filtered = []
        for candidate in remaining:
            if seen_start:
                filtered.append(candidate)
            elif candidate.candidate_id == args.start_after:
                seen_start = True
        remaining = filtered
    if args.max_candidates is not None:
        remaining = remaining[: args.max_candidates]

    print(
        json.dumps(
            {
                "started_at": datetime.now().isoformat(timespec="seconds"),
                "checkpoint": str(checkpoint_path.resolve()),
                "remaining_in_batch": [candidate.candidate_id for candidate in remaining],
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )

    for candidate in remaining:
        log_path = log_dir / f"{candidate.candidate_id}.log"
        command = [
            sys.executable,
            str(resume_script),
            str(docx_path),
            "--output-dir",
            str(output_dir),
            "--only-candidate-id",
            candidate.candidate_id,
            "--page-window",
            str(args.page_window),
            "--max-search-results",
            str(args.max_search_results),
            "--ocr-model",
            args.ocr_model,
            "--download-max-attempts",
            str(args.download_max_attempts),
            "--stop-after",
            "1",
        ]
        if args.ocr_page_window is not None:
            command.extend(["--ocr-page-window", str(args.ocr_page_window)])
        for platform in args.platform:
            command.extend(["--platform", platform])
        if args.no_ndl_browser_fallback:
            command.append("--no-ndl-browser-fallback")
        if args.ignore_download_failure_cache:
            command.append("--ignore-download-failure-cache")
        if checkpoint_path:
            command.extend(["--checkpoint-file", str(checkpoint_path)])

        print(
            json.dumps(
                    {
                        "candidate_id": candidate.candidate_id,
                        "footnote_id": candidate.footnote_id,
                        "status": "started",
                        "log": str(log_path.resolve()),
                    },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return_code = run_resume_command(command, timeout=args.candidate_timeout, log_path=log_path)
        checkpoint = load_checkpoint(checkpoint_path)
        if candidate.candidate_id in checkpoint.get("results", {}):
            result = checkpoint["results"][candidate.candidate_id]
            print(
                json.dumps(
                    {
                        "candidate_id": candidate.candidate_id,
                        "status": result.get("verification_status"),
                        "return_code": return_code,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            continue

        reason = (
            f"batch_controller_timeout_after_{args.candidate_timeout}s"
            if return_code == 124
            else f"batch_controller_resume_exit_{return_code}"
        )
        mark_skipped(
            resume_script=resume_script,
            docx_path=docx_path,
            output_dir=output_dir,
            checkpoint_file=checkpoint_path,
            candidate_id=candidate.candidate_id,
            reason=reason,
        )
        print(
            json.dumps(
                {
                    "candidate_id": candidate.candidate_id,
                    "status": "download_failed",
                    "reason": reason,
                    "return_code": return_code,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    print(json.dumps({"finished_at": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
