from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.historical_citation_verifier import HistoricalCitationVerifier


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify Chinese PDF paper citations against cited Japanese historical sources."
    )
    parser.add_argument("pdf_path", help="Path to the input .pdf paper")
    parser.add_argument(
        "--output-dir",
        default="output/historical_citation_pdf_verification_cli",
        help="Directory for JSON/Markdown reports and downloaded artifacts",
    )
    parser.add_argument(
        "--parse-only",
        action="store_true",
        help="Only parse the PDF and extract citation candidates without querying source platforms.",
    )
    parser.add_argument(
        "--download-source",
        action="store_true",
        help="Try to download the cited source and extract Japanese page text.",
    )
    parser.add_argument(
        "--restricted-download",
        action="store_true",
        help="Allow browser-based restricted NDL download when credentials are configured.",
    )
    parser.add_argument(
        "--max-search-results",
        type=int,
        default=5,
        help="Maximum number of source candidates to keep per citation.",
    )
    parser.add_argument(
        "--page-window",
        type=int,
        default=4,
        help="How many pages around the cited page to inspect and keep as OCR context.",
    )
    parser.add_argument(
        "--ocr-model",
        default="ndlocr_lite",
        help="OCR model to use when page text must be extracted from images.",
    )
    parser.add_argument(
        "--platform",
        action="append",
        default=[],
        help="Source platform to search. May be repeated. Defaults to all configured platforms.",
    )
    parser.add_argument(
        "--no-ndl-browser-fallback",
        action="store_true",
        help="Use public APIs only during metadata search; skip slow browser fallback search.",
    )
    parser.add_argument(
        "--skip-ndl-fulltext",
        action="store_true",
        help="Skip NDL fulltext hit probing during the source-search pass for faster batch scans.",
    )
    parser.add_argument(
        "--quoted-only",
        action="store_true",
        help="Only build candidates from explicit quoted text. By default PDF mode also keeps unquoted sentence claims.",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Start verification from this zero-based citation candidate offset.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Verify at most this many citation candidates in the current batch.",
    )
    parser.add_argument(
        "--prefer-ollama-review",
        action="store_true",
        default=True,
        help="Use the local Ollama review client for the final LLM citation-support check.",
    )
    parser.add_argument(
        "--no-ollama-review",
        dest="prefer_ollama_review",
        action="store_false",
        help="Use the configured non-Ollama review client instead of the formal local Gemma workflow.",
    )
    parser.add_argument(
        "--review-model",
        default="gemma4:e4b",
        help="Ollama model name for final LLM review. Formal workflow default: gemma4:e4b.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.review_model:
        os.environ["HISTORICAL_CITATION_REVIEW_MODEL"] = args.review_model
    verifier = HistoricalCitationVerifier(
        allow_external_ndl_fallback=not args.no_ndl_browser_fallback,
        prefer_ollama_review=args.prefer_ollama_review,
    )
    if args.skip_ndl_fulltext:
        os.environ["HISTORICAL_CITATION_SKIP_NDL_FULLTEXT"] = "1"
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.parse_only:
        package = verifier.parse_pdf_package(
            args.pdf_path,
            include_unquoted=not args.quoted_only,
            output_dir=str(output_dir),
            ocr_model=args.ocr_model,
        )
        json_path = output_dir / "pdf_parse_package.json"
        json_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(package["document"], ensure_ascii=False, indent=2))
        print(f"candidates: {package['summary']['candidate_count']}")
        print(f"output: {json_path.resolve()}")
        return 0

    result = verifier.verify_pdf_package(
        args.pdf_path,
        search_ndl=True,
        download_source=args.download_source,
        restricted_download=args.restricted_download,
        max_search_results=args.max_search_results,
        page_window=args.page_window,
        ocr_model=args.ocr_model,
        output_dir=str(output_dir),
        platform_names=args.platform or None,
        include_unquoted=not args.quoted_only,
        candidate_offset=args.offset,
        candidate_limit=args.limit,
    )

    print(json.dumps(result["document"], ensure_ascii=False, indent=2))
    print(f"results: {len(result['results'])}")
    if result.get("candidate_batch"):
        print(json.dumps(result["candidate_batch"], ensure_ascii=False, indent=2))
    print(f"output: {result['artifacts']['output_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
