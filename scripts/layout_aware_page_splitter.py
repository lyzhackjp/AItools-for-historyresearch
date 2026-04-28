import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np


@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int

    def as_xyxy(self) -> Tuple[int, int, int, int]:
        return self.x, self.y, self.x + self.w, self.y + self.h


class LayoutAwarePageSplitter:
    def __init__(self, image_path: Path):
        self.image_path = Path(image_path)
        self.image = cv2.imread(str(self.image_path))
        if self.image is None:
            raise FileNotFoundError(f"Cannot read image: {self.image_path}")

    def split(self, rows_per_page: int = 3) -> dict:
        page_rect = self._detect_book_region(self.image)
        book = self._crop(self.image, page_rect)

        gutter_x = self._detect_gutter_x(book)
        left_page = book[:, :gutter_x]
        right_page = book[:, gutter_x:]

        left_rows = self._split_page_rows(left_page, rows_per_page)
        right_rows = self._split_page_rows(right_page, rows_per_page)

        return {
            "source_image": str(self.image_path),
            "book_rect": self._rect_to_dict(page_rect),
            "gutter_x_in_book": int(gutter_x),
            "left_page": {
                "rect_in_book": {"x": 0, "y": 0, "w": int(left_page.shape[1]), "h": int(left_page.shape[0])},
                "rows": [self._rect_to_dict(r) for r in left_rows],
            },
            "right_page": {
                "rect_in_book": {
                    "x": int(gutter_x),
                    "y": 0,
                    "w": int(right_page.shape[1]),
                    "h": int(right_page.shape[0]),
                },
                "rows": [self._rect_to_dict(r) for r in right_rows],
            },
            "images": {
                "book": book,
                "left_page": left_page,
                "right_page": right_page,
                "left_rows": [self._crop(left_page, r) for r in left_rows],
                "right_rows": [self._crop(right_page, r) for r in right_rows],
            },
        }

    @staticmethod
    def _rect_to_dict(rect: Rect) -> dict:
        return {"x": int(rect.x), "y": int(rect.y), "w": int(rect.w), "h": int(rect.h)}

    @staticmethod
    def _crop(img: np.ndarray, rect: Rect) -> np.ndarray:
        x1, y1, x2, y2 = rect.as_xyxy()
        return img[y1:y2, x1:x2]

    def _detect_book_region(self, img: np.ndarray) -> Rect:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if np.mean(th) < 127:
            th = cv2.bitwise_not(th)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (35, 35))
        mask = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return Rect(0, 0, img.shape[1], img.shape[0])

        contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(contour)

        h_img, w_img = img.shape[:2]
        min_w = int(w_img * 0.55)
        min_h = int(h_img * 0.55)
        if w < min_w or h < min_h:
            return Rect(0, 0, w_img, h_img)

        padx = max(int(w * 0.01), 4)
        pady = max(int(h * 0.01), 4)

        x = max(0, x - padx)
        y = max(0, y - pady)
        w = min(w_img - x, w + 2 * padx)
        h = min(h_img - y, h + 2 * pady)

        return Rect(x, y, w, h)

    def _detect_gutter_x(self, book_img: np.ndarray) -> int:
        gray = cv2.cvtColor(book_img, cv2.COLOR_BGR2GRAY)
        bw = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15
        )

        profile = bw.sum(axis=0).astype(np.float32)
        smooth = cv2.GaussianBlur(profile.reshape(1, -1), (1, 51), 0).reshape(-1)

        w = book_img.shape[1]
        left = int(w * 0.35)
        right = int(w * 0.65)
        if right <= left:
            return w // 2

        central = smooth[left:right]
        gutter = int(np.argmin(central) + left)

        gutter = max(int(w * 0.2), min(int(w * 0.8), gutter))
        return gutter

    def _split_page_rows(self, page_img: np.ndarray, rows_per_page: int) -> List[Rect]:
        h, w = page_img.shape[:2]
        gray = cv2.cvtColor(page_img, cv2.COLOR_BGR2GRAY)
        bw = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15
        )

        needed = rows_per_page - 1
        separators = self._separators_by_target_valley(bw, needed)

        if len(separators) != needed:
            return self._force_equal_rows(h, w, rows_per_page)

        boundaries = [0] + separators + [h]
        rows: List[Rect] = []
        for i in range(len(boundaries) - 1):
            y1, y2 = boundaries[i], boundaries[i + 1]
            if y2 - y1 < 24:
                continue

            band = bw[y1:y2, :]
            x1_rel, x2_rel = self._foreground_span(band, axis=0, ratio=0.015)
            y1_rel, y2_rel = self._foreground_span(band, axis=1, ratio=0.03)

            x1 = x1_rel
            x2 = x2_rel
            y1_abs = y1 + y1_rel
            y2_abs = y1 + y2_rel

            if x2 - x1 < 50 or y2_abs - y1_abs < 24:
                rows.append(Rect(0, y1, w, y2 - y1))
            else:
                rows.append(Rect(x1, y1_abs, x2 - x1, y2_abs - y1_abs))

        if len(rows) != rows_per_page:
            rows = self._force_equal_rows(h, w, rows_per_page)

        return rows

    @staticmethod
    def _separators_by_target_valley(bw: np.ndarray, needed: int) -> List[int]:
        h, _ = bw.shape
        if needed <= 0:
            return []

        profile = (bw > 0).sum(axis=1).astype(np.float32)
        smooth = cv2.GaussianBlur(profile.reshape(-1, 1), (1, 101), 0).reshape(-1)

        separators: List[int] = []
        for i in range(needed):
            target = int((i + 1) * h / (needed + 1))
            win = max(40, int(h * 0.18))
            low = max(int(h * 0.08), target - win)
            high = min(int(h * 0.92), target + win)
            if high <= low:
                continue

            y = int(low + np.argmin(smooth[low:high]))
            separators.append(y)

        # Ensure strictly increasing and not too close.
        deduped: List[int] = []
        min_gap = max(30, h // (needed + 2) // 2)
        for y in sorted(separators):
            if not deduped or y - deduped[-1] >= min_gap:
                deduped.append(y)
            else:
                deduped[-1] = (deduped[-1] + y) // 2

        return deduped

    @staticmethod
    def _foreground_span(bw: np.ndarray, axis: int, ratio: float) -> Tuple[int, int]:
        if axis == 0:
            profile = (bw > 0).sum(axis=0)
            length = bw.shape[1]
            cross = bw.shape[0]
        else:
            profile = (bw > 0).sum(axis=1)
            length = bw.shape[0]
            cross = bw.shape[1]

        threshold = max(3, int(cross * ratio))
        idx = np.where(profile > threshold)[0]
        if len(idx) == 0:
            return 0, length

        if axis == 0:
            start = int(np.floor(np.percentile(idx, 1)))
            end = int(np.ceil(np.percentile(idx, 99)))
        else:
            start, end = LayoutAwarePageSplitter._largest_contiguous_span(idx)

        pad = max(2, int(length * 0.005))
        start = max(0, start - pad)
        end = min(length, end + pad + 1)
        return int(start), int(end)

    @staticmethod
    def _largest_contiguous_span(idx: np.ndarray) -> Tuple[int, int]:
        if len(idx) == 0:
            return 0, 0

        splits = np.where(np.diff(idx) > 1)[0]
        starts = np.r_[0, splits + 1]
        ends = np.r_[splits, len(idx) - 1]

        best_start = int(idx[0])
        best_end = int(idx[-1])
        best_len = -1
        for s, e in zip(starts, ends):
            s_i = int(idx[s])
            e_i = int(idx[e])
            seg_len = e_i - s_i + 1
            if seg_len > best_len:
                best_len = seg_len
                best_start, best_end = s_i, e_i
        return best_start, best_end

    @staticmethod
    def _force_equal_rows(h: int, w: int, rows_per_page: int) -> List[Rect]:
        rows: List[Rect] = []
        step = h / rows_per_page
        for i in range(rows_per_page):
            y1 = int(round(i * step))
            y2 = int(round((i + 1) * step))
            rows.append(Rect(0, y1, w, y2 - y1))
        return rows


def write_outputs(result: dict, output_dir: Path, save_debug: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    images = result["images"]
    cv2.imwrite(str(output_dir / "book.png"), images["book"])
    cv2.imwrite(str(output_dir / "left_page.png"), images["left_page"])
    cv2.imwrite(str(output_dir / "right_page.png"), images["right_page"])

    for idx, row in enumerate(images["left_rows"], 1):
        cv2.imwrite(str(output_dir / f"left_row_{idx}.png"), row)
    for idx, row in enumerate(images["right_rows"], 1):
        cv2.imwrite(str(output_dir / f"right_row_{idx}.png"), row)

    meta = {k: v for k, v in result.items() if k != "images"}
    with open(output_dir / "layout.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    if save_debug:
        debug = images["book"].copy()

        gx = int(result["gutter_x_in_book"])
        cv2.line(debug, (gx, 0), (gx, debug.shape[0] - 1), (0, 0, 255), 2)

        for page_key, color, x_offset in [
            ("left_page", (0, 180, 255), 0),
            ("right_page", (80, 255, 80), result["right_page"]["rect_in_book"]["x"]),
        ]:
            for row in result[page_key]["rows"]:
                x = int(row["x"] + x_offset)
                y = int(row["y"])
                w = int(row["w"])
                h = int(row["h"])
                cv2.rectangle(debug, (x, y), (x + w, y + h), color, 2)

        cv2.imwrite(str(output_dir / "debug_layout.png"), debug)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Layout-aware splitter for scanned double-page historical documents."
    )
    parser.add_argument("image", help="Path to input image (e.g., page_0100.png)")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output directory. Default: <image_dir>/<image_stem>_layout_split",
    )
    parser.add_argument(
        "--rows-per-page",
        type=int,
        default=3,
        help="Expected number of horizontal blocks per single page.",
    )
    parser.add_argument(
        "--no-debug",
        action="store_true",
        help="Disable saving debug overlay image.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    image_path = Path(args.image)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    output_dir = Path(args.output) if args.output else image_path.parent / f"{image_path.stem}_layout_split"

    splitter = LayoutAwarePageSplitter(image_path)
    result = splitter.split(rows_per_page=args.rows_per_page)
    write_outputs(result, output_dir, save_debug=not args.no_debug)

    print(f"[OK] Split finished: {image_path}")
    print(f"[OK] Output dir: {output_dir}")


if __name__ == "__main__":
    main()
