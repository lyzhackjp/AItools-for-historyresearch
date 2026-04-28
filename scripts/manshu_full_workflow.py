"""
Full-book workflow runner for 満洲紳士録.

Stages:
  ocr     Crop each scanned spread into right/left pages and run ndlocr-lite.
  entries Reconstruct cleaned person entries from half-page OCR XML.
  ner     Run Qwen NER in small page-local chunks with resume support.
  merge   Merge per-page NER outputs into JSONL/CSV.

The script is designed for full-book processing, but NER has an explicit
--confirm-ner-cost guard to avoid accidental multi-page API spending.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from scripts.manshu_xml_entry_pipeline import (  # noqa: E402
    DEFAULT_IMAGES_DIR,
    DEFAULT_MODEL,
    build_ner_prompt,
    call_qwen,
    ensure_halves_ocr,
    extract_json_response,
    load_api_key,
    reconstruct_page_entries,
    write_ner_csv,
    write_page_outputs,
)


DEFAULT_OUTPUT_DIR = BASE_DIR / "ocr_output" / "manshu_full_pipeline"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Full-book split -> ndlocr-lite OCR -> cleanup -> Qwen NER workflow for 満洲紳士録."
    )
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--end-page", type=int, default=888)
    parser.add_argument(
        "--stage",
        choices=["ocr", "entries", "ner", "merge", "all"],
        default="entries",
        help="Stage to run. all runs ocr + entries, and runs ner only when --run-ner is also set.",
    )
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--images-dir", type=str, default=str(DEFAULT_IMAGES_DIR))
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument(
        "--run-ocr",
        action="store_true",
        help="Actually run ndlocr-lite for missing half-page XML files. Without this, missing OCR is an error.",
    )
    parser.add_argument(
        "--force-ocr",
        action="store_true",
        help="Re-run half-page OCR even if XML exists.",
    )
    parser.add_argument("--min-entry-chars", type=int, default=40)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--ner-chunk-size", type=int, default=3)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--sleep-between-calls", type=float, default=1.5)
    parser.add_argument(
        "--run-ner",
        action="store_true",
        help="When --stage all is used, include NER after OCR and entries.",
    )
    parser.add_argument(
        "--confirm-ner-cost",
        action="store_true",
        help="Required for NER over more than one page.",
    )
    parser.add_argument(
        "--entry-limit-per-page",
        type=int,
        default=None,
        help="Optional cap for NER entries per page. Mainly useful for page-local tests.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue NER after a page/chunk error and write error JSON.",
    )
    return parser.parse_args()


def validate_page_range(start_page: int, end_page: int) -> None:
    if start_page < 1:
        raise ValueError("--start-page must be >= 1.")
    if end_page < start_page:
        raise ValueError("--end-page must be >= --start-page.")


def page_range(args: argparse.Namespace) -> range:
    validate_page_range(args.start_page, args.end_page)
    return range(args.start_page, args.end_page + 1)


def pipeline_paths(output_dir: Path) -> Dict[str, Path]:
    return {
        "root": output_dir,
        "split": output_dir / "split_halves",
        "ocr": output_dir / "ocr_halves",
        "pages": output_dir / "pages",
        "ner": output_dir / "ner",
        "merged": output_dir / "merged",
        "logs": output_dir / "logs",
    }


def ensure_dirs(paths: Dict[str, Path]) -> None:
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_page_entries(page_json: Path) -> Dict:
    return json.loads(page_json.read_text(encoding="utf-8"))


def chunked(items: List[Dict], size: int) -> Iterable[List[Dict]]:
    if size <= 0:
        raise ValueError("--ner-chunk-size must be positive.")
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]


def remove_existing_half_ocr(paths: Dict[str, Path], page: int) -> None:
    for side in ("right", "left"):
        stem = f"page_{page:04d}_{side}"
        for suffix in (".xml", ".txt", ".json"):
            target = paths["ocr"] / f"{stem}{suffix}"
            if target.exists():
                target.unlink()


def stage_ocr(args: argparse.Namespace, paths: Dict[str, Path]) -> Dict:
    images_dir = Path(args.images_dir)
    pages = list(page_range(args))
    results: List[Dict] = []

    for page in pages:
        if args.force_ocr:
            remove_existing_half_ocr(paths, page)
        try:
            ensure_halves_ocr(
                page=page,
                images_dir=images_dir,
                split_dir=paths["split"],
                ocr_dir=paths["ocr"],
                run_ocr=args.run_ocr or args.force_ocr,
                device=args.device,
            )
            status = "ok"
            error = None
        except Exception as exc:
            status = "error"
            error = f"{type(exc).__name__}: {exc}"
            if not args.continue_on_error:
                raise
        record = {
            "page": page,
            "status": status,
            "right_xml": str(paths["ocr"] / f"page_{page:04d}_right.xml"),
            "left_xml": str(paths["ocr"] / f"page_{page:04d}_left.xml"),
            "error": error,
        }
        results.append(record)
        append_jsonl(paths["logs"] / "ocr_status.jsonl", record)

    summary = {
        "stage": "ocr",
        "start_page": args.start_page,
        "end_page": args.end_page,
        "total_pages": len(pages),
        "ok_pages": sum(1 for item in results if item["status"] == "ok"),
        "error_pages": sum(1 for item in results if item["status"] != "ok"),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "results": results,
    }
    write_json(paths["logs"] / f"ocr_summary_{args.start_page:04d}_{args.end_page:04d}.json", summary)
    return summary


def stage_entries(args: argparse.Namespace, paths: Dict[str, Path]) -> Dict:
    pages = list(page_range(args))
    page_summaries: List[Dict] = []

    entries_jsonl = paths["merged"] / f"entries_{args.start_page:04d}_{args.end_page:04d}.jsonl"
    entries_csv = paths["merged"] / f"entries_summary_{args.start_page:04d}_{args.end_page:04d}.csv"
    if entries_jsonl.exists():
        entries_jsonl.unlink()

    with entries_csv.open("w", encoding="utf-8", newline="") as f_csv:
        writer = csv.writer(f_csv)
        writer.writerow(
            [
                "page",
                "entry_index",
                "name",
                "char_count",
                "marker_count",
                "avg_confidence",
                "low_confidence_ratio",
                "needs_review",
                "review_reasons",
                "text_preview",
            ]
        )

        for page in pages:
            try:
                page_data = reconstruct_page_entries(
                    ocr_dir=paths["ocr"],
                    page=page,
                    block_order=(1, 2),
                    min_entry_chars=args.min_entry_chars,
                    layout="halves",
                )
                write_page_outputs(page_data, paths["root"])
                status = "ok"
                error = None
            except Exception as exc:
                status = "error"
                error = f"{type(exc).__name__}: {exc}"
                page_data = {
                    "page": page,
                    "entry_count": 0,
                    "review_count": 0,
                    "carryover_char_count": None,
                    "entries": [],
                }
                if not args.continue_on_error:
                    raise

            for entry in page_data["entries"]:
                append_jsonl(entries_jsonl, entry)
                writer.writerow(
                    [
                        entry.get("page"),
                        entry.get("entry_index"),
                        entry.get("name"),
                        entry.get("char_count"),
                        entry.get("marker_count"),
                        entry.get("avg_confidence"),
                        entry.get("low_confidence_ratio"),
                        entry.get("needs_review"),
                        ";".join(entry.get("review_reasons") or []),
                        (entry.get("normalized_text") or "")[:120].replace("\n", " "),
                    ]
                )

            record = {
                "page": page,
                "status": status,
                "entry_count": page_data["entry_count"],
                "review_count": page_data["review_count"],
                "carryover_char_count": page_data["carryover_char_count"],
                "entries_json": str(paths["pages"] / f"page_{page:04d}_entries.json"),
                "error": error,
            }
            page_summaries.append(record)
            append_jsonl(paths["logs"] / "entries_status.jsonl", record)

    summary = {
        "stage": "entries",
        "start_page": args.start_page,
        "end_page": args.end_page,
        "total_pages": len(pages),
        "total_entries": sum(item["entry_count"] for item in page_summaries),
        "total_review_entries": sum(item["review_count"] for item in page_summaries),
        "entries_jsonl": str(entries_jsonl),
        "entries_csv": str(entries_csv),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "pages": page_summaries,
    }
    write_json(paths["logs"] / f"entries_summary_{args.start_page:04d}_{args.end_page:04d}.json", summary)
    return summary


def append_jsonl(path: Path, obj: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def existing_chunk_json(ner_page_dir: Path, chunk_index: int) -> Optional[Dict]:
    chunk_json = ner_page_dir / f"chunk_{chunk_index:03d}.json"
    if not chunk_json.exists():
        return None
    return json.loads(chunk_json.read_text(encoding="utf-8"))


def run_ner_page(
    args: argparse.Namespace,
    paths: Dict[str, Path],
    page_data: Dict,
    api_key: str,
) -> Dict:
    page = int(page_data["page"])
    entries = [entry for entry in page_data.get("entries", []) if entry.get("char_count", 0) >= args.min_entry_chars]
    if args.entry_limit_per_page is not None:
        entries = entries[: args.entry_limit_per_page]

    ner_page_dir = paths["ner"] / f"page_{page:04d}"
    ner_page_dir.mkdir(parents=True, exist_ok=True)

    persons: List[Dict] = []
    chunk_records: List[Dict] = []
    for chunk_index, entry_chunk in enumerate(chunked(entries, args.ner_chunk_size), start=1):
        chunk_json = ner_page_dir / f"chunk_{chunk_index:03d}.json"
        prompt_path = ner_page_dir / f"chunk_{chunk_index:03d}_prompt.md"
        raw_path = ner_page_dir / f"chunk_{chunk_index:03d}_raw.md"

        existing = existing_chunk_json(ner_page_dir, chunk_index)
        if existing is not None:
            chunk_persons = existing.get("persons", [])
            persons.extend(chunk_persons)
            chunk_records.append(
                {
                    "chunk": chunk_index,
                    "status": "skipped_existing",
                    "entry_ids": [entry["entry_index"] for entry in entry_chunk],
                    "person_count": len(chunk_persons),
                    "json": str(chunk_json),
                }
            )
            continue

        prompt = build_ner_prompt(page_data, entries_override=entry_chunk)
        prompt_path.write_text(prompt, encoding="utf-8")

        ok, content = call_qwen(api_key, args.model, prompt, args.max_retries)
        raw_path.write_text(content, encoding="utf-8")
        if not ok:
            error_record = {
                "chunk": chunk_index,
                "status": "error",
                "entry_ids": [entry["entry_index"] for entry in entry_chunk],
                "error": content[:1000],
                "prompt": str(prompt_path),
                "raw": str(raw_path),
            }
            write_json(ner_page_dir / f"chunk_{chunk_index:03d}_error.json", error_record)
            if not args.continue_on_error:
                raise RuntimeError(f"NER failed on page {page}, chunk {chunk_index}: {content[:500]}")
            chunk_records.append(error_record)
            continue

        parsed = extract_json_response(content)
        parsed_page = {"page": page, "persons": parsed.get("persons", [])}
        write_json(chunk_json, parsed_page)
        chunk_persons = parsed_page["persons"]
        persons.extend(chunk_persons)
        chunk_records.append(
            {
                "chunk": chunk_index,
                "status": "ok",
                "entry_ids": [entry["entry_index"] for entry in entry_chunk],
                "person_count": len(chunk_persons),
                "prompt": str(prompt_path),
                "raw": str(raw_path),
                "json": str(chunk_json),
            }
        )
        time.sleep(args.sleep_between_calls)

    page_ner = {"page": page, "persons": persons}
    page_json = ner_page_dir / f"page_{page:04d}_ner.json"
    page_csv = ner_page_dir / f"page_{page:04d}_ner.csv"
    write_json(page_json, page_ner)
    write_ner_csv(page_ner, page_csv)

    return {
        "page": page,
        "status": "ok",
        "entry_count_sent": len(entries),
        "person_count": len(persons),
        "json": str(page_json),
        "csv": str(page_csv),
        "chunks": chunk_records,
    }


def stage_ner(args: argparse.Namespace, paths: Dict[str, Path]) -> Dict:
    pages = list(page_range(args))
    if len(pages) > 1 and not args.confirm_ner_cost:
        raise RuntimeError("NER over multiple pages requires --confirm-ner-cost.")
    api_key = load_api_key()
    if not api_key:
        raise RuntimeError("Qwen/DashScope API key not found.")

    page_results: List[Dict] = []
    for page in pages:
        page_json = paths["pages"] / f"page_{page:04d}_entries.json"
        if not page_json.exists():
            raise FileNotFoundError(f"Entries file not found: {page_json}. Run --stage entries first.")
        page_data = load_page_entries(page_json)
        try:
            result = run_ner_page(args, paths, page_data, api_key)
        except Exception as exc:
            result = {
                "page": page,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }
            if not args.continue_on_error:
                raise
        page_results.append(result)
        append_jsonl(paths["logs"] / "ner_status.jsonl", result)

    summary = {
        "stage": "ner",
        "start_page": args.start_page,
        "end_page": args.end_page,
        "model": args.model,
        "chunk_size": args.ner_chunk_size,
        "total_pages": len(page_results),
        "total_persons": sum(item.get("person_count", 0) for item in page_results),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "pages": page_results,
    }
    write_json(paths["logs"] / f"ner_summary_{args.start_page:04d}_{args.end_page:04d}.json", summary)
    return summary


def stage_merge(args: argparse.Namespace, paths: Dict[str, Path]) -> Dict:
    pages = list(page_range(args))
    output_jsonl = paths["merged"] / f"ner_persons_{args.start_page:04d}_{args.end_page:04d}.jsonl"
    output_csv = paths["merged"] / f"ner_persons_{args.start_page:04d}_{args.end_page:04d}.csv"
    if output_jsonl.exists():
        output_jsonl.unlink()

    rows: List[Dict] = []
    for page in pages:
        page_json = paths["ner"] / f"page_{page:04d}" / f"page_{page:04d}_ner.json"
        if not page_json.exists():
            continue
        data = json.loads(page_json.read_text(encoding="utf-8"))
        for person in data.get("persons", []):
            append_jsonl(output_jsonl, {"page": page, **person})
            rows.append({"page": page, **person})

    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "page",
                "entry_id",
                "needs_review",
                "name",
                "birth_date",
                "birth_date_raw",
                "registered_domicile",
                "current_organization",
                "current_title",
                "organization_flow",
                "location_flow",
                "career_trajectory_count",
                "address_raw",
                "review_reason",
            ]
        )
        for row in rows:
            person_info = row.get("person_info") or {}
            current = row.get("current_status") or {}
            summary = row.get("trajectory_summary") or {}
            writer.writerow(
                [
                    row.get("page"),
                    row.get("entry_id"),
                    row.get("needs_review"),
                    person_info.get("name"),
                    person_info.get("birth_date"),
                    person_info.get("birth_date_raw"),
                    person_info.get("registered_domicile"),
                    current.get("organization"),
                    current.get("title"),
                    summary.get("organization_flow"),
                    summary.get("location_flow"),
                    len(row.get("career_trajectory") or []),
                    row.get("address_raw"),
                    row.get("review_reason"),
                ]
            )

    summary = {
        "stage": "merge",
        "start_page": args.start_page,
        "end_page": args.end_page,
        "person_count": len(rows),
        "jsonl": str(output_jsonl),
        "csv": str(output_csv),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(paths["logs"] / f"merge_summary_{args.start_page:04d}_{args.end_page:04d}.json", summary)
    return summary


def main() -> None:
    args = parse_args()
    validate_page_range(args.start_page, args.end_page)
    output_dir = Path(args.output_dir)
    paths = pipeline_paths(output_dir)
    ensure_dirs(paths)

    summaries: List[Dict] = []
    if args.stage == "ocr":
        summaries.append(stage_ocr(args, paths))
    elif args.stage == "entries":
        summaries.append(stage_entries(args, paths))
    elif args.stage == "ner":
        summaries.append(stage_ner(args, paths))
    elif args.stage == "merge":
        summaries.append(stage_merge(args, paths))
    elif args.stage == "all":
        summaries.append(stage_ocr(args, paths))
        summaries.append(stage_entries(args, paths))
        if args.run_ner:
            summaries.append(stage_ner(args, paths))
            summaries.append(stage_merge(args, paths))
    else:
        raise ValueError(f"Unknown stage: {args.stage}")

    final_summary = {
        "output_dir": str(output_dir),
        "stage": args.stage,
        "start_page": args.start_page,
        "end_page": args.end_page,
        "summaries": summaries,
    }
    write_json(paths["logs"] / f"last_run_{args.stage}_{args.start_page:04d}_{args.end_page:04d}.json", final_summary)
    print(json.dumps(final_summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
