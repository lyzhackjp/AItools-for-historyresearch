from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.historical_citation_verifier import HistoricalCitationVerifier


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify Chinese quotations in a Word paper against cited Japanese historical sources from NDL."
    )
    parser.add_argument("docx_path", help="Path to the input .docx paper")
    parser.add_argument(
        "--output-dir",
        default="output/historical_citation_verification_cli",
        help="Directory for JSON/Markdown reports and downloaded artifacts",
    )
    parser.add_argument(
        "--no-search",
        action="store_true",
        help="Only parse the paper and extract quote-footnote candidates without querying NDL",
    )
    parser.add_argument(
        "--download-source",
        action="store_true",
        help="Try to download the cited source and extract Japanese page text",
    )
    parser.add_argument(
        "--restricted-download",
        action="store_true",
        help="Allow browser-based restricted NDL download when credentials are configured",
    )
    parser.add_argument(
        "--max-search-results",
        type=int,
        default=5,
        help="Maximum number of NDL candidates to keep per citation",
    )
    parser.add_argument(
        "--page-window",
        type=int,
        default=4,
        help="How many pages around the cited page to inspect and keep as OCR context",
    )
    parser.add_argument(
        "--ocr-model",
        default="ndlocr_lite",
        help="OCR model to use when page text must be extracted from images",
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
        help="Use NDL public API only during metadata search; skip slow Selenium/browser fallback search.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    verifier = HistoricalCitationVerifier(
        allow_external_ndl_fallback=not args.no_ndl_browser_fallback,
    )
    result = verifier.verify_docx(
        args.docx_path,
        search_ndl=not args.no_search,
        download_source=args.download_source,
        restricted_download=args.restricted_download,
        max_search_results=args.max_search_results,
        page_window=args.page_window,
        ocr_model=args.ocr_model,
        output_dir=args.output_dir,
        platform_names=args.platform or None,
    )

    print(json.dumps(result["document"], ensure_ascii=False, indent=2))
    print(f"results: {len(result['results'])}")
    print(f"output: {result['artifacts']['output_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
