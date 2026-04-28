import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import cv2


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from scripts.layout_aware_page_splitter import LayoutAwarePageSplitter  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Layout-aware split + ndlocr-lite OCR + merged text output."
    )
    parser.add_argument("--start-page", type=int, default=211)
    parser.add_argument("--end-page", type=int, default=220)
    parser.add_argument(
        "--images-dir",
        type=str,
        default=str(BASE_DIR / "ocr_output" / "full_pages" / "images"),
    )
    parser.add_argument(
        "--split-dir",
        type=str,
        default=str(BASE_DIR / "ocr_output" / "full_pages" / "split_layout_aware_211_220"),
    )
    parser.add_argument(
        "--ocr-dir",
        type=str,
        default=str(BASE_DIR / "ocr_output" / "full_pages" / "ocr_layout_aware_211_220"),
    )
    parser.add_argument(
        "--merged-dir",
        type=str,
        default=str(BASE_DIR / "ocr_output" / "full_pages" / "merged_layout_aware_211_220"),
    )
    parser.add_argument(
        "--layout-meta-dir",
        type=str,
        default=str(BASE_DIR / "ocr_output" / "full_pages" / "layout_meta_211_220"),
    )
    parser.add_argument("--rows-per-page", type=int, default=3)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--skip-existing-ocr", action="store_true")
    return parser.parse_args()


def ensure_dirs(*dirs: Path) -> None:
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def split_to_6_blocks(
    image_path: Path,
    split_dir: Path,
    layout_meta_dir: Path,
    rows_per_page: int,
) -> List[Path]:
    splitter = LayoutAwarePageSplitter(image_path)
    result = splitter.split(rows_per_page=rows_per_page)

    page_stem = image_path.stem
    right_rows = result["images"]["right_rows"]
    left_rows = result["images"]["left_rows"]

    if len(right_rows) != 3 or len(left_rows) != 3:
        raise ValueError(
            f"{page_stem}: expected 3 rows on each page, got right={len(right_rows)}, left={len(left_rows)}"
        )

    block_images = right_rows + left_rows
    block_paths: List[Path] = []
    for i, block_img in enumerate(block_images, start=1):
        block_path = split_dir / f"{page_stem}_block_{i}.png"
        ok = cv2.imwrite(str(block_path), block_img)
        if not ok:
            raise RuntimeError(f"Failed to write block image: {block_path}")
        block_paths.append(block_path)

    # Save layout metadata with explicit block mapping for reproducibility.
    right_page_x = int(result["right_page"]["rect_in_book"]["x"])
    block_map: Dict[str, Dict] = {}
    for i, row in enumerate(result["right_page"]["rows"], start=1):
        block_map[f"block_{i}"] = {
            "side": "right",
            "row_index": i,
            "row_rect_in_page": row,
            "row_rect_in_book": {
                "x": int(right_page_x + row["x"]),
                "y": int(row["y"]),
                "w": int(row["w"]),
                "h": int(row["h"]),
            },
        }
    for i, row in enumerate(result["left_page"]["rows"], start=4):
        block_map[f"block_{i}"] = {
            "side": "left",
            "row_index": i - 3,
            "row_rect_in_page": row,
            "row_rect_in_book": {
                "x": int(row["x"]),
                "y": int(row["y"]),
                "w": int(row["w"]),
                "h": int(row["h"]),
            },
        }

    meta = {
        "source_image": str(image_path),
        "book_rect": result["book_rect"],
        "gutter_x_in_book": result["gutter_x_in_book"],
        "block_order_rule": "block_1-3=right_page_top_to_bottom, block_4-6=left_page_top_to_bottom",
        "blocks": block_map,
    }
    with open(layout_meta_dir / f"{page_stem}_layout.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return block_paths


def run_ndlocr(block_path: Path, ocr_dir: Path, device: str) -> Tuple[bool, str]:
    ndlocr_script = BASE_DIR / "ndlocr-lite" / "src" / "ocr.py"
    cmd = [
        sys.executable,
        str(ndlocr_script),
        "--sourceimg",
        str(block_path),
        "--output",
        str(ocr_dir),
        "--device",
        device,
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode == 0:
        return True, ""
    return False, proc.stderr[-800:]


def merge_page_text(page_num: int, ocr_dir: Path, merged_dir: Path) -> Dict:
    page_stem = f"page_{page_num:04d}"
    merged_parts: List[str] = []
    merged_marked_parts: List[str] = []
    missing_blocks: List[int] = []

    for block_num in range(1, 7):
        txt_path = ocr_dir / f"{page_stem}_block_{block_num}.txt"
        if not txt_path.exists():
            missing_blocks.append(block_num)
            continue
        text = txt_path.read_text(encoding="utf-8", errors="replace").strip()
        if text:
            merged_parts.append(text)
            merged_marked_parts.append(f"<block_{block_num}>\n{text}\n</block_{block_num}>")

    merged_text = "\n\n".join(merged_parts).strip()
    merged_marked_text = "\n\n".join(merged_marked_parts).strip()

    merged_path = merged_dir / f"{page_stem}_merged.txt"
    merged_marked_path = merged_dir / f"{page_stem}_merged_with_blocks.txt"
    merged_path.write_text(merged_text, encoding="utf-8")
    merged_marked_path.write_text(merged_marked_text, encoding="utf-8")

    return {
        "page": page_num,
        "merged_txt": str(merged_path),
        "merged_marked_txt": str(merged_marked_path),
        "missing_blocks": missing_blocks,
        "char_count": len(merged_text),
    }


def main() -> None:
    args = parse_args()
    images_dir = Path(args.images_dir)
    split_dir = Path(args.split_dir)
    ocr_dir = Path(args.ocr_dir)
    merged_dir = Path(args.merged_dir)
    layout_meta_dir = Path(args.layout_meta_dir)

    ensure_dirs(split_dir, ocr_dir, merged_dir, layout_meta_dir)

    all_pages_report: List[Dict] = []
    total_blocks = 0
    ocr_success = 0
    ocr_failed = 0

    print(f"[INFO] Page range: {args.start_page}-{args.end_page}")
    print(f"[INFO] Images dir: {images_dir}")
    print(f"[INFO] Split dir: {split_dir}")
    print(f"[INFO] OCR dir: {ocr_dir}")
    print(f"[INFO] Merged dir: {merged_dir}")

    for page_num in range(args.start_page, args.end_page + 1):
        page_stem = f"page_{page_num:04d}"
        image_path = images_dir / f"{page_stem}.png"

        if not image_path.exists():
            print(f"[WARN] Missing image: {image_path}")
            all_pages_report.append(
                {"page": page_num, "status": "missing_image", "ocr_errors": [], "missing_blocks": [1, 2, 3, 4, 5, 6]}
            )
            continue

        print(f"[INFO] Splitting {page_stem} ...")
        block_paths = split_to_6_blocks(
            image_path=image_path,
            split_dir=split_dir,
            layout_meta_dir=layout_meta_dir,
            rows_per_page=args.rows_per_page,
        )
        total_blocks += len(block_paths)

        page_errors: List[Dict] = []
        for block_path in block_paths:
            txt_out = ocr_dir / f"{block_path.stem}.txt"
            if args.skip_existing_ocr and txt_out.exists():
                ocr_success += 1
                continue

            ok, err = run_ndlocr(block_path, ocr_dir, args.device)
            if ok:
                ocr_success += 1
            else:
                ocr_failed += 1
                page_errors.append({"block": block_path.name, "error": err})
                print(f"[ERROR] OCR failed: {block_path.name}")

        merge_info = merge_page_text(page_num, ocr_dir, merged_dir)
        all_pages_report.append(
            {
                "page": page_num,
                "status": "done",
                "split_blocks": [p.name for p in block_paths],
                "ocr_errors": page_errors,
                **merge_info,
            }
        )

    combined_lines: List[str] = []
    for page_num in range(args.start_page, args.end_page + 1):
        page_stem = f"page_{page_num:04d}"
        merged_path = merged_dir / f"{page_stem}_merged.txt"
        if not merged_path.exists():
            continue
        text = merged_path.read_text(encoding="utf-8", errors="replace").strip()
        if text:
            combined_lines.append(f"===== {page_stem} =====\n{text}")
    (merged_dir / f"pages_{args.start_page:04d}_{args.end_page:04d}_merged.txt").write_text(
        "\n\n".join(combined_lines),
        encoding="utf-8",
    )

    summary = {
        "start_page": args.start_page,
        "end_page": args.end_page,
        "images_dir": str(images_dir),
        "split_dir": str(split_dir),
        "ocr_dir": str(ocr_dir),
        "merged_dir": str(merged_dir),
        "layout_meta_dir": str(layout_meta_dir),
        "total_split_blocks": total_blocks,
        "ocr_success": ocr_success,
        "ocr_failed": ocr_failed,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "pages": all_pages_report,
    }
    summary_path = merged_dir / f"run_summary_{args.start_page:04d}_{args.end_page:04d}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("[INFO] Done.")
    print(f"[INFO] Total split blocks: {total_blocks}")
    print(f"[INFO] OCR success: {ocr_success}")
    print(f"[INFO] OCR failed: {ocr_failed}")
    print(f"[INFO] Summary: {summary_path}")


if __name__ == "__main__":
    main()
