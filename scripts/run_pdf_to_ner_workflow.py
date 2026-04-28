from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from modules.pdf_to_ner_workflow import PDFToNERConfig, PDFToNERPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reusable PDF to NER workflow entry point.")
    parser.add_argument("pdf_path")
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "output" / "pdf_to_ner_runs"))
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--end-page", type=int)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--ndlocr-device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--skip-ocr", action="store_true")
    parser.add_argument("--skip-ner", action="store_true")
    parser.add_argument("--min-entry-chars", type=int, default=40)
    parser.add_argument("--ner-model", default="qwen3.6-plus")
    parser.add_argument("--ner-chunk-size", type=int, default=3)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--sleep-between-calls", type=float, default=1.5)
    parser.add_argument("--entry-limit-per-page", type=int)
    parser.add_argument("--confirm-ner-cost", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pipeline = PDFToNERPipeline(
        PDFToNERConfig(
            pdf_path=args.pdf_path,
            output_dir=args.output_dir,
            start_page=args.start_page,
            end_page=args.end_page,
            dpi=args.dpi,
            ndlocr_device=args.ndlocr_device,
            run_ocr=not args.skip_ocr,
            run_ner=not args.skip_ner,
            min_entry_chars=args.min_entry_chars,
            ner_model=args.ner_model,
            ner_chunk_size=args.ner_chunk_size,
            max_retries=args.max_retries,
            sleep_between_calls=args.sleep_between_calls,
            entry_limit_per_page=args.entry_limit_per_page,
            confirm_ner_cost=args.confirm_ner_cost,
            continue_on_error=args.continue_on_error,
        ),
        project_root=PROJECT_ROOT,
    )
    result = pipeline.run()
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
