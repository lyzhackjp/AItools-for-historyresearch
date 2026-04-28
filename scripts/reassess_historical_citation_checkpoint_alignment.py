from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
from dataclasses import fields
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Type, TypeVar

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.historical_citation.models import CitationCandidate, NDLSearchMatch, ParsedFootnote
from modules.historical_citation.reporting import build_artifact_summary, render_resume_markdown_report
from modules.historical_citation_verifier import HistoricalCitationVerifier


T = TypeVar("T")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reassess alignment for selected checkpoint candidates using existing OCR text. "
            "This does not download sources or rerun OCR."
        )
    )
    parser.add_argument("checkpoint_file", help="Existing resume_checkpoint.json.")
    parser.add_argument("--docx-path", help="Private DOCX used to refresh citation units.", default=None)
    parser.add_argument("--output-dir", help="Report output directory. Defaults to checkpoint parent.", default=None)
    parser.add_argument("--candidate-id", action="append", default=[], help="Candidate id to reassess. May repeat.")
    parser.add_argument("--footnote-id", action="append", default=[], help="Footnote id to reassess. May repeat.")
    parser.add_argument("--all", action="store_true", help="Reassess every checkpoint result that has OCR text.")
    parser.add_argument("--enable-llm-review", action="store_true", help="Also run configured LLM precision review.")
    parser.add_argument("--dry-run", action="store_true", help="Do not modify checkpoint.")
    return parser


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def dataclass_from_dict(cls: Type[T], payload: Dict[str, Any]) -> T:
    allowed = {field.name for field in fields(cls)}
    return cls(**{key: value for key, value in dict(payload or {}).items() if key in allowed})


def hydrate_checkpoint_candidate(
    result: Dict[str, Any],
    *,
    current_candidate: Optional[CitationCandidate] = None,
) -> CitationCandidate:
    if current_candidate is not None:
        candidate = copy.deepcopy(current_candidate)
    else:
        footnote = dataclass_from_dict(ParsedFootnote, result.get("footnote") or {})
        candidate = CitationCandidate(
            candidate_id=str(result.get("candidate_id") or ""),
            paragraph_index=int(result.get("paragraph_index") or 0),
            paragraph_text=str(result.get("paragraph_text") or ""),
            translation_text=str(result.get("translation_text") or ""),
            footnote_id=str(result.get("footnote_id") or footnote.id),
            footnote=footnote,
        )
    candidate.ndl_matches = [
        dataclass_from_dict(NDLSearchMatch, item)
        for item in (result.get("ndl_matches") or [])
        if isinstance(item, dict)
    ]
    candidate.verification_status = str(result.get("verification_status") or candidate.verification_status)
    candidate.matched_japanese = str(result.get("matched_japanese") or "")
    candidate.matched_page = result.get("matched_page")
    candidate.confidence = result.get("confidence")
    candidate.support_status = str(result.get("support_status") or candidate.support_status)
    candidate.support_reason = str(result.get("support_reason") or "")
    candidate.evidence_scope = str(result.get("evidence_scope") or "")
    candidate.notes = list(result.get("notes") or [])
    candidate.artifacts = copy.deepcopy(result.get("artifacts") or {})
    if current_candidate is not None:
        candidate.artifacts["citation_unit"] = copy.deepcopy(current_candidate.artifacts.get("citation_unit") or {})
        if result.get("translation_text") != current_candidate.translation_text:
            candidate.artifacts["previous_translation_text"] = result.get("translation_text")
            candidate.artifacts["translation_text_refreshed_from_citation_unit"] = True
            stale_note = "translation_text_refreshed_from_citation_unit"
            if stale_note not in candidate.notes:
                candidate.notes.append(stale_note)
    return candidate


def extracted_pages_from_artifacts(artifacts: Dict[str, Any]) -> List[Tuple[int, str]]:
    extracted_pages: List[Tuple[int, str]] = []
    for entry in artifacts.get("extracted_page_texts") or []:
        if not isinstance(entry, dict):
            continue
        try:
            page_number = int(entry.get("page"))
        except (TypeError, ValueError):
            continue
        page_text = str(entry.get("text") or entry.get("cleaned_text") or "")
        if page_text.strip():
            extracted_pages.append((page_number, page_text))
    return extracted_pages


def remove_old_alignment_state(candidate: CitationCandidate) -> None:
    transient_artifact_keys = {
        "alignment_scope",
        "citation_priority_pages",
        "cited_extracted_pages",
        "context_alignment_preview",
        "context_alignment_selected",
        "matched_scan_page",
        "matched_book_pages",
        "page_distance_from_citation",
        "review_context",
        "review_context_window",
        "llm_review",
        "llm_review_runtime",
    }
    for key in transient_artifact_keys:
        candidate.artifacts.pop(key, None)

    transient_note_prefixes = tuple(
        list(HistoricalCitationVerifier.TRANSIENT_VERIFICATION_NOTE_PREFIXES)
        + [
            "context_alignment_selected_over_weak_cited_page:",
            "translation_text_refreshed_from_citation_unit",
        ]
    )
    preserved_notes = [
        note
        for note in candidate.notes
        if not str(note).startswith(transient_note_prefixes)
    ]
    if candidate.artifacts.get("translation_text_refreshed_from_citation_unit"):
        preserved_notes.append("translation_text_refreshed_from_citation_unit")
    candidate.notes = preserved_notes


def select_candidate_ids(
    checkpoint: Dict[str, Any],
    *,
    candidate_ids: Sequence[str],
    footnote_ids: Sequence[str],
    select_all: bool = False,
) -> List[str]:
    explicit = [item for item in candidate_ids if item]
    if select_all:
        return list(checkpoint.get("results", {}).keys())
    selected: List[str] = []
    for candidate_id, result in checkpoint.get("results", {}).items():
        if explicit and candidate_id in explicit:
            selected.append(candidate_id)
            continue
        if footnote_ids and str(result.get("footnote_id")) in {str(item) for item in footnote_ids}:
            selected.append(candidate_id)
    return selected


def rebuild_current_candidates(docx_path: Optional[Path]) -> Dict[str, CitationCandidate]:
    if docx_path is None:
        return {}
    verifier = HistoricalCitationVerifier(enable_llm_review=False)
    parsed = verifier.parse_docx(str(docx_path))
    candidates = verifier.build_candidates(parsed["paragraphs"], parsed["footnotes"])
    return {candidate.candidate_id: candidate for candidate in candidates}


def reassess_candidate(
    verifier: HistoricalCitationVerifier,
    candidate: CitationCandidate,
    extracted_pages: Sequence[Tuple[int, str]],
    *,
    page_window: int,
) -> Dict[str, Any]:
    remove_old_alignment_state(candidate)
    best_page, best_japanese, confidence, note = verifier._align_translation_with_citation_priority(
        candidate,
        extracted_pages,
    )
    candidate.matched_page = best_page
    candidate.matched_japanese = best_japanese
    candidate.confidence = confidence

    page_mapping = candidate.artifacts.get("page_mapping")
    if best_page is not None and page_mapping:
        if candidate.artifacts.get("page_label_mode") == "book":
            candidate.artifacts["matched_book_pages"] = [best_page]
            matched_scan_page = verifier._estimate_scan_page_for_book_page(page_mapping, best_page)
            if matched_scan_page is not None:
                candidate.artifacts["matched_scan_page"] = matched_scan_page
        else:
            candidate.artifacts["matched_scan_page"] = best_page
            matched_book_pages = verifier._estimate_book_pages_from_scan_page(page_mapping, best_page)
            if matched_book_pages:
                candidate.artifacts["matched_book_pages"] = matched_book_pages

    page_distance = verifier._measure_page_distance_from_citation(candidate)
    if page_distance is not None:
        candidate.artifacts["page_distance_from_citation"] = page_distance
        if page_distance > 1:
            candidate.notes.append(f"page_distance_from_citation:{page_distance}")
    if note:
        candidate.notes.append(note)
    candidate.verification_status = "matched" if best_japanese else "needs_manual_review"
    verifier._review_precise_alignment(candidate)
    verifier._set_support_assessment(candidate)
    candidate.artifacts["review_context_window"] = page_window
    candidate.artifacts["review_context"] = verifier._build_review_context(
        candidate,
        extracted_pages=extracted_pages,
        context_radius=max(2, page_window),
    )
    return candidate.to_dict()


def reassess_checkpoint(
    *,
    checkpoint_path: Path,
    output_dir: Path,
    docx_path: Optional[Path],
    candidate_ids: Sequence[str],
    footnote_ids: Sequence[str],
    select_all: bool,
    enable_llm_review: bool,
    dry_run: bool,
) -> Dict[str, Any]:
    checkpoint = load_json(checkpoint_path)
    selected_ids = select_candidate_ids(
        checkpoint,
        candidate_ids=candidate_ids,
        footnote_ids=footnote_ids,
        select_all=select_all,
    )
    current_candidates = rebuild_current_candidates(docx_path)
    verifier = HistoricalCitationVerifier(enable_llm_review=enable_llm_review, prefer_ollama_review=enable_llm_review)
    reassessed: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for candidate_id in selected_ids:
        result = checkpoint.get("results", {}).get(candidate_id)
        if not isinstance(result, dict):
            skipped.append({"candidate_id": candidate_id, "reason": "missing_result"})
            continue
        extracted_pages = extracted_pages_from_artifacts(result.get("artifacts") or {})
        if not extracted_pages:
            skipped.append({"candidate_id": candidate_id, "reason": "missing_extracted_pages"})
            continue
        candidate = hydrate_checkpoint_candidate(
            result,
            current_candidate=current_candidates.get(candidate_id),
        )
        before = {
            "matched_page": result.get("matched_page"),
            "confidence": result.get("confidence"),
            "support_status": result.get("support_status"),
            "alignment_scope": (result.get("artifacts") or {}).get("alignment_scope"),
        }
        updated_result = reassess_candidate(
            verifier,
            candidate,
            extracted_pages,
            page_window=int((result.get("artifacts") or {}).get("review_context_window") or 4),
        )
        checkpoint["results"][candidate_id] = updated_result
        after = {
            "matched_page": updated_result.get("matched_page"),
            "confidence": updated_result.get("confidence"),
            "support_status": updated_result.get("support_status"),
            "alignment_scope": (updated_result.get("artifacts") or {}).get("alignment_scope"),
        }
        reassessed.append({"candidate_id": candidate_id, "before": before, "after": after})

    summary = {
        "checkpoint": str(checkpoint_path.resolve()),
        "dry_run": dry_run,
        "selected": selected_ids,
        "reassessed": reassessed,
        "skipped": skipped,
        "docx_refreshed": docx_path is not None,
        "llm_review_enabled": enable_llm_review,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    if not dry_run:
        backup_path = checkpoint_path.with_suffix(
            checkpoint_path.suffix + f".bak_align_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        shutil.copy2(checkpoint_path, backup_path)
        checkpoint["updated_at"] = datetime.now().isoformat(timespec="seconds")
        checkpoint["schema_migrations"] = list(checkpoint.get("schema_migrations") or [])
        checkpoint["schema_migrations"].append(
            {
                "name": "targeted_alignment_reassessment_v1",
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "candidate_ids": selected_ids,
            }
        )
        checkpoint["artifacts"] = build_artifact_summary(output_dir)
        save_json(checkpoint_path, checkpoint)
        summary["backup"] = str(backup_path.resolve())

        document = checkpoint.get("document") or {}
        total_candidates = int(document.get("candidate_count") or len(checkpoint.get("results", {})))
        report_path = output_dir / "partial_resume_report.md"
        report_path.write_text(
            render_resume_markdown_report(
                document=document,
                checkpoint=checkpoint,
                total_candidates=total_candidates,
                output_dir=output_dir,
            ),
            encoding="utf-8",
        )
        summary["report"] = str(report_path.resolve())

    summary_path = output_dir / "targeted_alignment_reassessment_summary_20260428.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["summary_path"] = str(summary_path.resolve())
    return summary


def main() -> int:
    args = build_parser().parse_args()
    checkpoint_path = Path(args.checkpoint_file)
    output_dir = Path(args.output_dir) if args.output_dir else checkpoint_path.parent
    summary = reassess_checkpoint(
        checkpoint_path=checkpoint_path,
        output_dir=output_dir,
        docx_path=Path(args.docx_path) if args.docx_path else None,
        candidate_ids=args.candidate_id,
        footnote_ids=args.footnote_id,
        select_all=args.all,
        enable_llm_review=args.enable_llm_review,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
