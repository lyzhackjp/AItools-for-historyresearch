from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.historical_citation.reporting import build_artifact_summary, render_resume_markdown_report
from modules.historical_citation.source_trials import source_trials_from_legacy
from modules.historical_citation_verifier import HistoricalCitationVerifier


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migrate historical citation checkpoint metadata without re-downloading sources."
    )
    parser.add_argument("docx_path", help="Private input DOCX used to rebuild citation_unit metadata.")
    parser.add_argument(
        "--checkpoint-file",
        required=True,
        help="Existing resume_checkpoint.json to migrate.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for regenerated report. Defaults to checkpoint parent.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute migration summary without modifying the checkpoint.",
    )
    return parser


def load_checkpoint(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_checkpoint(path: Path, checkpoint: Dict[str, Any]) -> None:
    path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")


def migrate_checkpoint(
    *,
    docx_path: Path,
    checkpoint_path: Path,
    output_dir: Path,
    dry_run: bool = False,
) -> Dict[str, Any]:
    verifier = HistoricalCitationVerifier()
    parsed = verifier.parse_docx(str(docx_path))
    candidates = verifier.build_candidates(parsed["paragraphs"], parsed["footnotes"])
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    checkpoint = load_checkpoint(checkpoint_path)

    summary = {
        "checkpoint": str(checkpoint_path.resolve()),
        "dry_run": dry_run,
        "total_results": len(checkpoint.get("results", {})),
        "citation_units_added": 0,
        "stale_translation_texts_flagged": 0,
        "source_trials_added": 0,
        "missing_candidates": [],
    }

    for candidate_id, result in checkpoint.get("results", {}).items():
        candidate = candidate_by_id.get(candidate_id)
        if candidate is None:
            summary["missing_candidates"].append(candidate_id)
            continue
        artifacts = result.setdefault("artifacts", {})
        current_citation_unit = candidate.artifacts.get("citation_unit")
        if current_citation_unit and artifacts.get("citation_unit") != current_citation_unit:
            artifacts["citation_unit"] = current_citation_unit
            summary["citation_units_added"] += 1
        if candidate.translation_text and result.get("translation_text") != candidate.translation_text:
            artifacts["current_citation_unit_text"] = candidate.translation_text
            artifacts["translation_text_stale_after_citation_unit_refresh"] = True
            summary["stale_translation_texts_flagged"] += 1
            notes = result.setdefault("notes", [])
            stale_note = "translation_text_stale_after_citation_unit_refresh"
            if stale_note not in notes:
                notes.append(stale_note)

        current = {
            "selected_source_match": artifacts.get("selected_source_match"),
            "downloaded_page_range": artifacts.get("downloaded_page_range"),
            "source_pdf": artifacts.get("source_pdf"),
            "matched_japanese": result.get("matched_japanese"),
            "confidence": result.get("confidence"),
            "support_status": result.get("support_status"),
            "verification_status": result.get("verification_status"),
        }
        before = len(artifacts.get("source_trials") or [])
        artifacts["source_trials"] = source_trials_from_legacy(artifacts, current=current)
        summary["source_trials_added"] += max(0, len(artifacts["source_trials"]) - before)

    checkpoint["document"] = parsed["document"]
    checkpoint["schema_migrations"] = list(checkpoint.get("schema_migrations") or [])
    checkpoint["schema_migrations"].append(
        {
            "name": "citation_unit_and_source_trials_v1",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "dry_run": dry_run,
        }
    )
    checkpoint["artifacts"] = build_artifact_summary(output_dir)
    checkpoint["updated_at"] = datetime.now().isoformat(timespec="seconds")

    output_dir.mkdir(parents=True, exist_ok=True)
    if not dry_run:
        backup_path = checkpoint_path.with_suffix(
            checkpoint_path.suffix + f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        shutil.copy2(checkpoint_path, backup_path)
        save_checkpoint(checkpoint_path, checkpoint)
        summary["backup"] = str(backup_path.resolve())
        report_path = output_dir / "partial_resume_report.md"
        report_path.write_text(
            render_resume_markdown_report(
                document=parsed["document"],
                checkpoint=checkpoint,
                total_candidates=len(candidates),
                output_dir=output_dir,
            ),
            encoding="utf-8",
        )
        summary["report"] = str(report_path.resolve())

    summary_path = output_dir / "checkpoint_migration_summary_20260428.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["summary_path"] = str(summary_path.resolve())
    return summary


def main() -> int:
    args = build_parser().parse_args()
    checkpoint_path = Path(args.checkpoint_file)
    output_dir = Path(args.output_dir) if args.output_dir else checkpoint_path.parent
    summary = migrate_checkpoint(
        docx_path=Path(args.docx_path),
        checkpoint_path=checkpoint_path,
        output_dir=output_dir,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
