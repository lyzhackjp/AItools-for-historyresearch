from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.historical_citation.cross_validation import (
    cross_validate_fulltext_ocr_cases,
    render_cross_validation_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-validate NDL fulltext snippets with local OCR results.")
    parser.add_argument("--cases", required=True, type=Path, help="Private JSON case config")
    parser.add_argument("--output", required=True, type=Path, help="Markdown report path")
    parser.add_argument("--json-output", type=Path, help="Raw JSON result path")
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise ValueError("--cases must be a JSON list")
    results = cross_validate_fulltext_ocr_cases(cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_cross_validation_markdown(results), encoding="utf-8")
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
