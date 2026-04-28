from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


DOWNLOAD_RANGE_INDEX_FILENAME = "download_range_index.json"


def parse_ndl_range_pdf_name(path: Path) -> Optional[Dict[str, Any]]:
    match = re.search(r"^ndl_(?P<ndl_id>[^_]+)_p(?P<start>\d+)-p(?P<end>\d+)$", path.stem)
    if not match:
        return None
    return {
        "ndl_id": match.group("ndl_id"),
        "start_page": int(match.group("start")),
        "end_page": int(match.group("end")),
        "path": str(path),
        "name": path.name,
        "size": path.stat().st_size if path.exists() else 0,
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        if path.exists()
        else None,
    }


def build_download_range_index(output_dir: Path) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = []
    for pdf_path in sorted(output_dir.glob("ndl_*_p*-p*.pdf")):
        parsed = parse_ndl_range_pdf_name(pdf_path)
        if parsed:
            records.append(parsed)
    return {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "records": records,
    }


def save_download_range_index(output_dir: Path, index: Dict[str, Any]) -> Path:
    path = output_dir / DOWNLOAD_RANGE_INDEX_FILENAME
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def refresh_download_range_index(output_dir: Path) -> Dict[str, Any]:
    index = build_download_range_index(output_dir)
    save_download_range_index(output_dir, index)
    return index


def load_download_range_index(output_dir: Path) -> Dict[str, Any]:
    path = output_dir / DOWNLOAD_RANGE_INDEX_FILENAME
    if not path.exists():
        return refresh_download_range_index(output_dir)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return refresh_download_range_index(output_dir)
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        return refresh_download_range_index(output_dir)
    return payload


def find_cached_range_pdf(
    output_dir: Path,
    *,
    ndl_id: Optional[str],
    start_page: int,
    end_page: int,
    is_usable_pdf: Callable[[str], bool],
) -> Optional[Tuple[Path, int, int]]:
    if not ndl_id:
        return None
    index = refresh_download_range_index(output_dir)
    best: Optional[Tuple[Path, int, int]] = None
    best_span: Optional[int] = None
    for record in index.get("records", []):
        if str(record.get("ndl_id")) != str(ndl_id):
            continue
        cached_start = int(record.get("start_page") or 0)
        cached_end = int(record.get("end_page") or 0)
        if cached_start > start_page or cached_end < end_page:
            continue
        path = Path(str(record.get("path") or ""))
        if not is_usable_pdf(str(path)):
            continue
        span = cached_end - cached_start
        if best is None or best_span is None or span < best_span:
            best = (path, cached_start, cached_end)
            best_span = span
    return best
