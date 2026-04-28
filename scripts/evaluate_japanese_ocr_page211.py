from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = BASE_DIR / "ocr_output" / "japanese_ocr_model_eval_0211"
DEFAULT_INPUTS = [
    BASE_DIR / "ocr_output" / "manshu_full_pipeline_211_215_resplit" / "split_halves" / "page_0211_right.png",
    BASE_DIR / "ocr_output" / "manshu_full_pipeline_211_215_resplit" / "split_halves" / "page_0211_left.png",
]
DEFAULT_ENTRIES = (
    BASE_DIR
    / "ocr_output"
    / "manshu_full_pipeline_211_215_resplit"
    / "pages"
    / "page_0211_entries.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate local Japanese OCR engines on page 211 only.")
    parser.add_argument("--engine", choices=["rapidocr", "easyocr", "paddleocr"], required=True)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--entries-json", default=str(DEFAULT_ENTRIES))
    parser.add_argument("--gpu", action="store_true", help="Use GPU for EasyOCR if available.")
    return parser.parse_args()


def box_key(box: Iterable[Iterable[float]]) -> Tuple[float, float]:
    points = list(box)
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    # Japanese vertical pages read right-to-left, then top-to-bottom.
    return (-sum(xs) / len(xs), sum(ys) / len(ys))


def serializable_box(box: Iterable[Iterable[float]]) -> List[List[float]]:
    return [[float(value) for value in point] for point in box]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def load_expected_names(path: Path) -> List[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [entry["name"] for entry in data.get("entries", []) if entry.get("name")]


def evaluate_text(text: str, expected_names: List[str]) -> Dict[str, Any]:
    compact = normalize_text(text)
    found_names = [name for name in expected_names if name in compact]
    markers = ["出生", "本籍", "續柄", "学歴", "學歴", "經歴", "経歴", "家族", "住所"]
    return {
        "char_count": len(compact),
        "expected_name_count": len(expected_names),
        "found_name_count": len(found_names),
        "found_names": found_names,
        "missing_names": [name for name in expected_names if name not in found_names],
        "field_marker_hits": {marker: compact.count(marker) for marker in markers},
    }


def run_rapidocr(image_paths: List[Path]) -> Tuple[List[Dict[str, Any]], float]:
    from rapidocr_onnxruntime import RapidOCR

    ocr = RapidOCR()
    all_items: List[Dict[str, Any]] = []
    start = time.time()
    for image_path in image_paths:
        result, elapsed = ocr(str(image_path))
        if not result:
            continue
        for item in result:
            box, text, score = item[0], item[1], float(item[2])
            all_items.append(
                {
                    "image": image_path.name,
                    "box": serializable_box(box),
                    "text": text,
                    "score": score,
                    "engine_elapsed": elapsed,
                }
            )
    return all_items, time.time() - start


def run_easyocr(image_paths: List[Path], gpu: bool) -> Tuple[List[Dict[str, Any]], float]:
    import easyocr

    reader = easyocr.Reader(["ja", "en"], gpu=gpu)
    all_items: List[Dict[str, Any]] = []
    start = time.time()
    for image_path in image_paths:
        result = reader.readtext(str(image_path), detail=1, paragraph=False)
        for box, text, score in result:
            all_items.append(
                {
                    "image": image_path.name,
                    "box": serializable_box(box),
                    "text": text,
                    "score": float(score),
                }
            )
    return all_items, time.time() - start


def run_paddleocr(image_paths: List[Path]) -> Tuple[List[Dict[str, Any]], float]:
    from paddleocr import PaddleOCR

    # The mobile PP-OCRv5 pair is the lightest practical PaddleOCR option for
    # this page-level benchmark. It is intentionally kept separate from the
    # main environment and should be run via .venv_ocr_eval.
    ocr = PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="PP-OCRv5_mobile_rec",
    )
    all_items: List[Dict[str, Any]] = []
    start = time.time()
    for image_path in image_paths:
        results = ocr.predict(str(image_path))
        for result in results:
            rec_texts = result.get("rec_texts", [])
            rec_scores = result.get("rec_scores", [])
            rec_polys = result.get("rec_polys", result.get("dt_polys", []))
            for box, text, score in zip(rec_polys, rec_texts, rec_scores):
                all_items.append(
                    {
                        "image": image_path.name,
                        "box": serializable_box(box),
                        "text": text,
                        "score": float(score),
                    }
                )
    return all_items, time.time() - start


def write_outputs(engine: str, output_dir: Path, items: List[Dict[str, Any]], elapsed: float, expected_names: List[str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    items = sorted(items, key=lambda item: (item["image"], box_key(item["box"])))
    text = "\n".join(item["text"] for item in items)
    summary = {
        "engine": engine,
        "elapsed_seconds": round(elapsed, 3),
        "box_count": len(items),
        "avg_score": round(sum(item["score"] for item in items) / len(items), 4) if items else None,
        **evaluate_text(text, expected_names),
        "sample_first_80_lines": [item["text"] for item in items[:80]],
    }
    (output_dir / f"{engine}_page_0211_items.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / f"{engine}_page_0211.txt").write_text(text, encoding="utf-8")
    (output_dir / f"{engine}_page_0211_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    image_paths = DEFAULT_INPUTS
    for image_path in image_paths:
        if not image_path.exists():
            raise FileNotFoundError(image_path)
    expected_names = load_expected_names(Path(args.entries_json))
    if args.engine == "rapidocr":
        items, elapsed = run_rapidocr(image_paths)
    elif args.engine == "easyocr":
        items, elapsed = run_easyocr(image_paths, gpu=args.gpu)
    else:
        items, elapsed = run_paddleocr(image_paths)
    write_outputs(args.engine, output_dir, items, elapsed, expected_names)


if __name__ == "__main__":
    main()
