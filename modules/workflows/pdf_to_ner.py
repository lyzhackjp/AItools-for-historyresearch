from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ._legacy import PROJECT_ROOT, load_legacy_module


@dataclass
class PDFToNERConfig:
    pdf_path: str | Path
    output_dir: str | Path
    start_page: int = 1
    end_page: Optional[int] = None
    dpi: int = 300
    ndlocr_device: str = "cpu"
    run_ocr: bool = True
    run_ner: bool = True
    min_entry_chars: int = 40
    ner_model: str = "qwen3.6-plus"
    ner_chunk_size: int = 3
    max_retries: int = 3
    sleep_between_calls: float = 1.5
    entry_limit_per_page: Optional[int] = None
    confirm_ner_cost: bool = False
    continue_on_error: bool = False


@dataclass
class PDFToNERResult:
    success: bool
    page_numbers: List[int]
    output_dir: str
    image_paths: List[str] = field(default_factory=list)
    entries_jsonl: Optional[str] = None
    entries_csv: Optional[str] = None
    merged_jsonl: Optional[str] = None
    merged_csv: Optional[str] = None
    stage_summaries: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class PDFToNERPipeline:
    def __init__(self, config: PDFToNERConfig, project_root: str | Path | None = None):
        self.config = config
        self.project_root = Path(project_root) if project_root else PROJECT_ROOT
        self.pdf_path = self._resolve_path(config.pdf_path)
        self.output_root = self._resolve_path(config.output_dir)
        self.output_root.mkdir(parents=True, exist_ok=True)

    def _entry_pipeline_module(self):
        return load_legacy_module("scripts/manshu_xml_entry_pipeline.py")

    def _resolve_path(self, path_value: str | Path) -> Path:
        path = Path(path_value)
        if path.is_absolute():
            return path
        return self.project_root / path

    def _page_numbers(self) -> List[int]:
        if self.config.start_page < 1:
            raise ValueError("start_page must be >= 1")
        if self.config.end_page is not None and self.config.end_page < self.config.start_page:
            raise ValueError("end_page must be >= start_page")

        if self.config.end_page is None:
            import fitz

            document = fitz.open(self.pdf_path)
            try:
                end_page = len(document)
            finally:
                document.close()
        else:
            end_page = self.config.end_page

        return list(range(self.config.start_page, end_page + 1))

    def _paths(self) -> Dict[str, Path]:
        return {
            "root": self.output_root,
            "images": self.output_root / "images",
            "split": self.output_root / "split_halves",
            "ocr": self.output_root / "ocr_halves",
            "pages": self.output_root / "pages",
            "ner": self.output_root / "ner",
            "merged": self.output_root / "merged",
            "logs": self.output_root / "logs",
        }

    def _ensure_dirs(self) -> Dict[str, Path]:
        paths = self._paths()
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
        return paths

    def _chunked(self, items: List[Dict[str, Any]], size: int) -> Iterable[List[Dict[str, Any]]]:
        if size <= 0:
            raise ValueError("ner_chunk_size must be positive")
        for index in range(0, len(items), size):
            yield items[index : index + size]

    def convert_pdf(self, page_numbers: List[int], paths: Dict[str, Path]) -> List[str]:
        from modules.pdf_image_converter import convert_pdf_to_images

        expected = [paths["images"] / f"page_{page:04d}.png" for page in page_numbers]
        if all(path.exists() for path in expected):
            return [str(path) for path in expected]

        return convert_pdf_to_images(
            str(self.pdf_path),
            str(paths["images"]),
            dpi=self.config.dpi,
            start_page=page_numbers[0],
            end_page=page_numbers[-1],
        )

    def run_ocr_stage(self, page_numbers: List[int], paths: Dict[str, Path]) -> Dict[str, Any]:
        entry_module = self._entry_pipeline_module()
        results: List[Dict[str, Any]] = []

        for page in page_numbers:
            try:
                entry_module.ensure_halves_ocr(
                    page=page,
                    images_dir=paths["images"],
                    split_dir=paths["split"],
                    ocr_dir=paths["ocr"],
                    run_ocr=self.config.run_ocr,
                    device=self.config.ndlocr_device,
                )
                record = {"page": page, "status": "ok"}
            except Exception as exc:
                record = {"page": page, "status": "error", "error": f"{type(exc).__name__}: {exc}"}
                if not self.config.continue_on_error:
                    raise
            results.append(record)

        summary = {
            "stage": "ocr",
            "total_pages": len(page_numbers),
            "ok_pages": sum(1 for item in results if item["status"] == "ok"),
            "error_pages": sum(1 for item in results if item["status"] != "ok"),
            "pages": results,
        }
        (paths["logs"] / "ocr_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return summary

    def build_entries_stage(self, page_numbers: List[int], paths: Dict[str, Path]) -> Dict[str, Any]:
        entry_module = self._entry_pipeline_module()
        entries_jsonl = paths["merged"] / f"entries_{page_numbers[0]:04d}_{page_numbers[-1]:04d}.jsonl"
        entries_csv = paths["merged"] / f"entries_summary_{page_numbers[0]:04d}_{page_numbers[-1]:04d}.csv"

        if entries_jsonl.exists():
            entries_jsonl.unlink()

        page_summaries: List[Dict[str, Any]] = []
        with entries_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
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

            for page in page_numbers:
                try:
                    page_data = entry_module.reconstruct_page_entries(
                        ocr_dir=paths["ocr"],
                        page=page,
                        block_order=(1, 2),
                        min_entry_chars=self.config.min_entry_chars,
                        layout="halves",
                    )
                    output_info = entry_module.write_page_outputs(page_data, paths["root"])
                    status = "ok"
                    error = None
                except Exception as exc:
                    page_data = {
                        "page": page,
                        "entry_count": 0,
                        "review_count": 0,
                        "carryover_char_count": 0,
                        "entries": [],
                    }
                    output_info = {}
                    status = "error"
                    error = f"{type(exc).__name__}: {exc}"
                    if not self.config.continue_on_error:
                        raise

                for entry in page_data["entries"]:
                    with entries_jsonl.open("a", encoding="utf-8") as handle_jsonl:
                        handle_jsonl.write(json.dumps(entry, ensure_ascii=False) + "\n")
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

                page_summaries.append(
                    {
                        "page": page,
                        "status": status,
                        "entry_count": page_data["entry_count"],
                        "review_count": page_data["review_count"],
                        "carryover_char_count": page_data["carryover_char_count"],
                        "entries_json": output_info.get("json"),
                        "entries_txt": output_info.get("txt"),
                        "error": error,
                    }
                )

        summary = {
            "stage": "entries",
            "entries_jsonl": str(entries_jsonl),
            "entries_csv": str(entries_csv),
            "total_entries": sum(item["entry_count"] for item in page_summaries),
            "pages": page_summaries,
        }
        (paths["logs"] / "entries_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return summary

    def run_ner_stage(self, page_numbers: List[int], paths: Dict[str, Path]) -> Dict[str, Any]:
        if len(page_numbers) > 1 and not self.config.confirm_ner_cost:
            raise RuntimeError("NER over multiple pages requires confirm_ner_cost=True.")

        entry_module = self._entry_pipeline_module()
        api_key = entry_module.load_api_key()
        if not api_key:
            raise RuntimeError("Qwen/DashScope API key not found.")

        page_results: List[Dict[str, Any]] = []
        for page in page_numbers:
            page_json = paths["pages"] / f"page_{page:04d}_entries.json"
            if not page_json.exists():
                raise FileNotFoundError(f"Entries file not found: {page_json}")

            page_data = json.loads(page_json.read_text(encoding="utf-8"))
            entries = [entry for entry in page_data.get("entries", []) if entry.get("char_count", 0) >= self.config.min_entry_chars]
            if self.config.entry_limit_per_page is not None:
                entries = entries[: self.config.entry_limit_per_page]

            ner_page_dir = paths["ner"] / f"page_{page:04d}"
            ner_page_dir.mkdir(parents=True, exist_ok=True)

            persons: List[Dict[str, Any]] = []
            chunk_records: List[Dict[str, Any]] = []
            for chunk_index, entry_chunk in enumerate(self._chunked(entries, self.config.ner_chunk_size), start=1):
                prompt = entry_module.build_ner_prompt(page_data, entries_override=entry_chunk)
                prompt_path = ner_page_dir / f"chunk_{chunk_index:03d}_prompt.md"
                raw_path = ner_page_dir / f"chunk_{chunk_index:03d}_raw.md"
                chunk_json = ner_page_dir / f"chunk_{chunk_index:03d}.json"
                prompt_path.write_text(prompt, encoding="utf-8")

                ok, content = entry_module.call_qwen(api_key, self.config.ner_model, prompt, self.config.max_retries)
                raw_path.write_text(content, encoding="utf-8")

                if not ok:
                    record = {
                        "chunk": chunk_index,
                        "status": "error",
                        "entry_ids": [entry["entry_index"] for entry in entry_chunk],
                        "error": content[:1000],
                    }
                    chunk_records.append(record)
                    if not self.config.continue_on_error:
                        raise RuntimeError(f"NER failed on page {page}, chunk {chunk_index}: {content[:300]}")
                    continue

                parsed = entry_module.extract_json_response(content)
                parsed_page = {"page": page, "persons": parsed.get("persons", [])}
                chunk_json.write_text(json.dumps(parsed_page, ensure_ascii=False, indent=2), encoding="utf-8")
                persons.extend(parsed_page["persons"])
                chunk_records.append(
                    {
                        "chunk": chunk_index,
                        "status": "ok",
                        "entry_ids": [entry["entry_index"] for entry in entry_chunk],
                        "person_count": len(parsed_page["persons"]),
                        "json": str(chunk_json),
                    }
                )
                time.sleep(self.config.sleep_between_calls)

            page_ner = {"page": page, "persons": persons}
            page_json_out = ner_page_dir / f"page_{page:04d}_ner.json"
            page_csv_out = ner_page_dir / f"page_{page:04d}_ner.csv"
            page_json_out.write_text(json.dumps(page_ner, ensure_ascii=False, indent=2), encoding="utf-8")
            entry_module.write_ner_csv(page_ner, page_csv_out)

            page_results.append(
                {
                    "page": page,
                    "status": "ok",
                    "entry_count_sent": len(entries),
                    "person_count": len(persons),
                    "json": str(page_json_out),
                    "csv": str(page_csv_out),
                    "chunks": chunk_records,
                }
            )

        summary = {
            "stage": "ner",
            "model": self.config.ner_model,
            "chunk_size": self.config.ner_chunk_size,
            "total_pages": len(page_results),
            "total_persons": sum(item.get("person_count", 0) for item in page_results),
            "pages": page_results,
        }
        (paths["logs"] / "ner_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return summary

    def merge_ner_outputs(self, page_numbers: List[int], paths: Optional[Dict[str, Path]] = None) -> Dict[str, Any]:
        active_paths = paths or self._ensure_dirs()
        output_jsonl = active_paths["merged"] / f"ner_persons_{page_numbers[0]:04d}_{page_numbers[-1]:04d}.jsonl"
        output_csv = active_paths["merged"] / f"ner_persons_{page_numbers[0]:04d}_{page_numbers[-1]:04d}.csv"

        if output_jsonl.exists():
            output_jsonl.unlink()

        rows: List[Dict[str, Any]] = []
        for page in page_numbers:
            page_json = active_paths["ner"] / f"page_{page:04d}" / f"page_{page:04d}_ner.json"
            if not page_json.exists():
                continue
            data = json.loads(page_json.read_text(encoding="utf-8"))
            for person in data.get("persons", []):
                row = {"page": page, **person}
                rows.append(row)
                with output_jsonl.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")

        with output_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
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
            "person_count": len(rows),
            "jsonl": str(output_jsonl),
            "csv": str(output_csv),
        }
        (active_paths["logs"] / "merge_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return summary

    def run(self) -> PDFToNERResult:
        page_numbers = self._page_numbers()
        paths = self._ensure_dirs()
        errors: List[str] = []
        stage_summaries: Dict[str, Any] = {}

        image_paths = self.convert_pdf(page_numbers, paths)

        try:
            stage_summaries["ocr"] = self.run_ocr_stage(page_numbers, paths)
            stage_summaries["entries"] = self.build_entries_stage(page_numbers, paths)
            if self.config.run_ner:
                stage_summaries["ner"] = self.run_ner_stage(page_numbers, paths)
                stage_summaries["merge"] = self.merge_ner_outputs(page_numbers, paths)
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            return PDFToNERResult(
                success=False,
                page_numbers=page_numbers,
                output_dir=str(paths["root"]),
                image_paths=image_paths,
                entries_jsonl=stage_summaries.get("entries", {}).get("entries_jsonl"),
                entries_csv=stage_summaries.get("entries", {}).get("entries_csv"),
                merged_jsonl=stage_summaries.get("merge", {}).get("jsonl"),
                merged_csv=stage_summaries.get("merge", {}).get("csv"),
                stage_summaries=stage_summaries,
                errors=errors,
            )

        return PDFToNERResult(
            success=True,
            page_numbers=page_numbers,
            output_dir=str(paths["root"]),
            image_paths=image_paths,
            entries_jsonl=stage_summaries.get("entries", {}).get("entries_jsonl"),
            entries_csv=stage_summaries.get("entries", {}).get("entries_csv"),
            merged_jsonl=stage_summaries.get("merge", {}).get("jsonl"),
            merged_csv=stage_summaries.get("merge", {}).get("csv"),
            stage_summaries=stage_summaries,
            errors=errors,
        )
