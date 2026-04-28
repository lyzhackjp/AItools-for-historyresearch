from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from modules.ndl_download_workflow import NDLDownloadModule, NDLDownloadRequest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reusable NDL download workflow entry point.")
    parser.add_argument("keyword", help="NDL search keyword")
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "output" / "ndl_downloads"))
    parser.add_argument("--filename")
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--use-api", action="store_true", default=False)
    parser.add_argument("--no-api", action="store_true")
    parser.add_argument("--headless", action="store_true", default=False)
    parser.add_argument("--restricted", action="store_true")
    parser.add_argument("--result-index", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    use_api = True if args.use_api else not args.no_api
    module = NDLDownloadModule(project_root=PROJECT_ROOT)
    outcome = module.download(
        NDLDownloadRequest(
            keyword=args.keyword,
            output_dir=args.output_dir,
            filename=args.filename,
            max_results=args.max_results,
            max_attempts=args.max_attempts,
            use_api=use_api,
            headless=args.headless,
            restricted=args.restricted,
            result_index=args.result_index,
        )
    )
    print(json.dumps(asdict(outcome), ensure_ascii=False, indent=2))
    return 0 if outcome.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
