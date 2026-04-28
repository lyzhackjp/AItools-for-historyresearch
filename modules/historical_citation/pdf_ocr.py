from __future__ import annotations

import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .docx_parser import clean_text
from .page_mapping import estimate_book_pages_from_scan_page


def safe_int(value: str) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def map_target_page(page: int, local_page_range: Any) -> Optional[int]:
    if isinstance(local_page_range, (list, tuple)) and len(local_page_range) == 2:
        start_page = safe_int(str(local_page_range[0]))
        end_page = safe_int(str(local_page_range[1]))
        if start_page is None or end_page is None or page < start_page or page > end_page:
            return None
        return page - start_page + 1
    return page


def wait_for_pdf_ready(
    pdf_path: str,
    *,
    local_page_range: Any,
    timeout_seconds: int = 45,
    sleep: Callable[[float], None] = time.sleep,
    time_now: Callable[[], float] = time.time,
) -> Dict[str, Any]:
    readiness: Dict[str, Any] = {
        "status": "pending",
        "path": pdf_path,
        "attempts": 0,
        "page_count": None,
        "file_size": None,
    }
    pdf_file = Path(pdf_path)
    deadline = time_now() + timeout_seconds
    previous_size: Optional[int] = None
    while time_now() < deadline:
        readiness["attempts"] += 1
        if not pdf_file.exists():
            sleep(1.0)
            continue
        try:
            file_size = pdf_file.stat().st_size
        except OSError:
            sleep(1.0)
            continue
        readiness["file_size"] = file_size
        if not file_size:
            sleep(1.0)
            continue
        if previous_size is not None and previous_size != file_size:
            previous_size = file_size
            sleep(1.2)
            continue
        previous_size = file_size
        try:
            import fitz

            document = fitz.open(pdf_path)
            try:
                page_count = len(document)
                readiness["page_count"] = page_count
                expected_pages = None
                if isinstance(local_page_range, (list, tuple)) and len(local_page_range) == 2:
                    start_page = safe_int(str(local_page_range[0]))
                    end_page = safe_int(str(local_page_range[1]))
                    if start_page is not None and end_page is not None and end_page >= start_page:
                        expected_pages = end_page - start_page + 1
                if expected_pages and page_count < expected_pages:
                    sleep(1.2)
                    continue
                if page_count >= 1:
                    page = document[0]
                    page.get_text("text")
                    page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
                readiness["status"] = "ready"
                return readiness
            finally:
                document.close()
        except Exception as exc:  # noqa: BLE001
            readiness["status"] = f"waiting:{type(exc).__name__}"
            readiness["last_error"] = str(exc)
            sleep(1.2)
    readiness["status"] = readiness.get("status") or "timeout"
    return readiness


def render_pdf_page(pdf_path: str, *, page_number: int, output_dir: Path) -> Optional[str]:
    try:
        import fitz
    except ImportError:
        return None

    target = output_dir / f"page_{page_number:04d}.png"
    document = fitz.open(pdf_path)
    try:
        page = document[page_number - 1]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
        pixmap.save(str(target))
        return str(target.resolve())
    except Exception:
        return None
    finally:
        document.close()


def detect_spread_gutter_x(image: Any) -> int:
    grayscale = image.convert("L")
    width, height = grayscale.size
    band_left = int(width * 0.35)
    band_right = max(band_left + 1, int(width * 0.65))
    band = grayscale.crop((band_left, 0, band_right, height))
    if band.size[0] <= 8:
        return width // 2

    reduced_height = max(16, min(240, band.size[1] // 8 or 16))
    resized = band.resize((band.size[0], reduced_height))
    pixels = resized.load()
    darkness_scores = []
    for x in range(resized.size[0]):
        darkness = 0.0
        for y in range(resized.size[1]):
            darkness += 255.0 - float(pixels[x, y])
        darkness_scores.append(darkness / max(1, resized.size[1]))

    smoothed_scores = []
    for index in range(len(darkness_scores)):
        window = darkness_scores[max(0, index - 4) : min(len(darkness_scores), index + 5)]
        smoothed_scores.append(sum(window) / max(1, len(window)))

    gutter_offset = min(range(len(smoothed_scores)), key=smoothed_scores.__getitem__)
    gutter_x = band_left + gutter_offset
    return max(int(width * 0.2), min(int(width * 0.8), gutter_x))


def split_double_page_image(
    image_path: str,
    *,
    scan_page_number: int,
    output_dir: Path,
) -> Dict[str, str]:
    try:
        from PIL import Image
    except Exception:
        return {}

    split_dir = output_dir / "split_pages"
    split_dir.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(image_path) as source_image:
            image = source_image.convert("RGB")
            width, height = image.size
            if width < 600 or height < 600:
                return {}
            gutter_x = detect_spread_gutter_x(image)
            margin = max(8, int(width * 0.01))
            right_start = min(width - 1, gutter_x + margin // 2)
            left_end = max(1, gutter_x - margin // 2)
            if right_start >= width - 20 or left_end <= 20:
                gutter_x = width // 2
                right_start = min(width - 1, gutter_x)
                left_end = max(1, gutter_x)

            right_image = image.crop((right_start, 0, width, height))
            left_image = image.crop((0, 0, left_end, height))
            if right_image.size[0] < width * 0.2 or left_image.size[0] < width * 0.2:
                return {}

            right_path = split_dir / f"scan_{scan_page_number:04d}_right.png"
            left_path = split_dir / f"scan_{scan_page_number:04d}_left.png"
            right_image.save(right_path)
            left_image.save(left_path)
    except Exception:
        return {}

    return {"right": str(right_path), "left": str(left_path)}


def _grid_for_panel_count(panel_count: int, width: int, height: int) -> Tuple[int, int]:
    if panel_count == 8:
        return (4, 2) if width >= height else (2, 4)
    if panel_count == 4:
        return (2, 2)
    columns = max(1, round((panel_count * max(1, width) / max(1, height)) ** 0.5))
    rows = max(1, (panel_count + columns - 1) // columns)
    while columns * rows < panel_count:
        columns += 1
    return columns, rows


def split_multi_panel_image(
    image_path: str,
    *,
    scan_page_number: int,
    panel_count: int,
    output_dir: Path,
) -> List[str]:
    """Split facsimile scans that contain several reduced book pages.

    Some NDL scans are not merely facing pages: each facing page can contain a
    2x2 grid of facsimile frames. In those cases a single scan may represent
    4 or 8 cited pages. OCRing the whole scan and assigning the same text to all
    cited pages mixes unrelated frames, so we crop each panel first.
    """

    try:
        from PIL import Image
    except Exception:
        return []

    if panel_count < 3:
        return []

    panel_dir = output_dir / "multi_panel_pages"
    panel_dir.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(image_path) as source_image:
            image = source_image.convert("RGB")
            width, height = image.size
            if width < 600 or height < 600:
                return []

            columns, rows = _grid_for_panel_count(int(panel_count), width, height)
            margin_x = int(width * 0.035)
            margin_y = int(height * 0.04)
            left = margin_x
            right = width - margin_x
            top = margin_y
            bottom = height - margin_y
            if right <= left or bottom <= top:
                left, top, right, bottom = 0, 0, width, height
            cell_width = (right - left) / columns
            cell_height = (bottom - top) / rows
            overlap = max(12, int(min(cell_width, cell_height) * 0.025))

            ordered_cells: List[Tuple[int, int]] = []
            for row in range(rows):
                for column in reversed(range(columns)):
                    ordered_cells.append((column, row))

            paths: List[str] = []
            for panel_index, (column, row) in enumerate(ordered_cells[:panel_count], start=1):
                x0 = int(left + column * cell_width) - overlap
                x1 = int(left + (column + 1) * cell_width) + overlap
                y0 = int(top + row * cell_height) - overlap
                y1 = int(top + (row + 1) * cell_height) + overlap
                crop = image.crop((max(0, x0), max(0, y0), min(width, x1), min(height, y1)))
                if crop.size[0] < width * 0.12 or crop.size[1] < height * 0.20:
                    continue
                panel_path = panel_dir / f"scan_{scan_page_number:04d}_panel_{panel_index:02d}.png"
                crop.save(panel_path)
                paths.append(str(panel_path))
    except Exception:
        return []

    return paths


def ocr_image_text(
    image_path: str,
    *,
    output_dir: Path,
    ocr_model: str,
    ocr_processor_getter: Callable[[], Any],
) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        ocr_result = ocr_processor_getter().process_image(
            image_path,
            model_type=ocr_model,
            output_dir=str(output_dir),
            language="ja",
            fallback_models=["tesseract"],
        )
        ocr_text = getattr(ocr_result, "text", "") if getattr(ocr_result, "success", False) else ""
        if len(clean_text(ocr_text)) >= 20:
            return ocr_text
    except Exception:
        pass
    fallback_text = _ocr_image_with_tesseract_variants(image_path)
    if len(clean_text(fallback_text)) >= 20:
        return fallback_text

    try:
        from modules.unified_ocr_processor import UnifiedOCRConfig, UnifiedOCRProcessor

        retry_processor = UnifiedOCRProcessor(
            UnifiedOCRConfig(default_model=ocr_model, fallback_models=["tesseract"])
        )
        retry_result = retry_processor.process_image(
            image_path,
            model_type=ocr_model,
            output_dir=str(output_dir),
            language="ja",
            fallback_models=["tesseract"],
        )
        retry_text = getattr(retry_result, "text", "") if getattr(retry_result, "success", False) else ""
        if len(clean_text(retry_text)) >= 20:
            return retry_text
    except Exception:
        pass
    return ""


def _detect_tesseract_path() -> Optional[str]:
    candidates = [
        os.environ.get("TESSERACT_CMD"),
        os.environ.get("TESSERACT_PATH"),
        shutil.which("tesseract"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))
    return None


def _ocr_image_with_tesseract_variants(image_path: str) -> str:
    try:
        import pytesseract
        from PIL import Image
    except Exception:
        return ""

    tesseract_path = _detect_tesseract_path()
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path

    variants = [
        ("jpn", "--psm 6"),
        ("jpn", "--psm 11"),
        ("jpn_vert", "--psm 5"),
        ("jpn_vert", "--psm 6"),
        ("script/Japanese", "--psm 6"),
        ("script/Japanese_vert", "--psm 5"),
    ]
    best_text = ""
    try:
        with Image.open(image_path) as source_image:
            image = source_image.convert("L")
            for language, config in variants:
                try:
                    text = pytesseract.image_to_string(image, lang=language, config=config) or ""
                except Exception:
                    continue
                if len(clean_text(text)) > len(clean_text(best_text)):
                    best_text = text
                if len(clean_text(best_text)) >= 80:
                    break
    except Exception:
        return best_text
    return best_text


def extract_pdf_page_text(
    pdf_path: str,
    *,
    page_number: int,
    output_dir: Path,
    ocr_model: str,
    pdf_processor_getter: Callable[[], Any],
    ocr_processor_getter: Callable[[], Any],
    render_page: Callable[[str, int, Path], Optional[str]] = lambda path, page, out: render_pdf_page(
        path,
        page_number=page,
        output_dir=out,
    ),
) -> str:
    direct_text = ""
    try:
        direct_text = pdf_processor_getter().extract_text_by_region(pdf_path, page_number)
    except Exception:
        direct_text = ""

    if len(clean_text(direct_text)) >= 80:
        return direct_text

    image_path = render_page(pdf_path, page_number, output_dir)
    if not image_path:
        return direct_text
    ocr_text = ocr_image_text(
        image_path,
        output_dir=output_dir / f"ocr_page_{page_number:04d}_{uuid.uuid4().hex[:8]}",
        ocr_model=ocr_model,
        ocr_processor_getter=ocr_processor_getter,
    )
    return ocr_text or direct_text


def extract_pdf_spread_page_texts(
    pdf_path: str,
    *,
    page_number: int,
    scan_page_number: int,
    book_page_numbers: Sequence[int],
    output_dir: Path,
    ocr_model: str,
    ocr_image: Callable[[str, Path, str], str],
    render_page: Callable[[str, int, Path], Optional[str]] = lambda path, page, out: render_pdf_page(
        path,
        page_number=page,
        output_dir=out,
    ),
    split_image: Callable[[str, int, Path], Dict[str, str]] = lambda image, scan, out: split_double_page_image(
        image,
        scan_page_number=scan,
        output_dir=out,
    ),
) -> List[Tuple[int, str]]:
    if len(book_page_numbers) < 2:
        return []
    image_path = render_page(pdf_path, page_number, output_dir)
    if not image_path:
        return []
    split_paths = split_image(image_path, scan_page_number, output_dir)
    if not split_paths:
        return []

    extracted_pages: List[Tuple[int, str]] = []
    ordered_sides = [("right", book_page_numbers[0]), ("left", book_page_numbers[1])]
    for side_name, book_page in ordered_sides:
        image_side_path = split_paths.get(side_name)
        if not image_side_path:
            continue
        page_text = ocr_image(
            image_side_path,
            output_dir / f"spread_scan_{scan_page_number:04d}_{side_name}",
            ocr_model,
        )
        if clean_text(page_text):
            extracted_pages.append((book_page, page_text))
    return extracted_pages


def extract_pdf_multi_panel_page_texts(
    pdf_path: str,
    *,
    page_number: int,
    scan_page_number: int,
    book_page_numbers: Sequence[int],
    output_dir: Path,
    ocr_model: str,
    ocr_image: Callable[[str, Path, str], str],
    render_page: Callable[[str, int, Path], Optional[str]] = lambda path, page, out: render_pdf_page(
        path,
        page_number=page,
        output_dir=out,
    ),
    split_image: Callable[[str, int, int, Path], List[str]] = lambda image, scan, count, out: split_multi_panel_image(
        image,
        scan_page_number=scan,
        panel_count=count,
        output_dir=out,
    ),
) -> List[Tuple[int, str]]:
    if len(book_page_numbers) < 3:
        return []
    image_path = render_page(pdf_path, page_number, output_dir)
    if not image_path:
        return []
    panel_paths = split_image(image_path, scan_page_number, len(book_page_numbers), output_dir)
    if len(panel_paths) < len(book_page_numbers):
        return []

    extracted_pages: List[Tuple[int, str]] = []
    for book_page, panel_path in zip(book_page_numbers, panel_paths):
        page_text = ocr_image(
            panel_path,
            output_dir / f"multi_scan_{scan_page_number:04d}_book_{book_page}",
            ocr_model,
        )
        if clean_text(page_text):
            extracted_pages.append((book_page, page_text))
    return extracted_pages


def extract_pages_directly(
    pdf_path: str,
    *,
    pages: Sequence[int],
    local_page_range: Any,
    output_dir: Path,
    ocr_model: str,
    extract_page_text: Callable[[str, int, Path, str], str],
    extract_spread_page_texts: Callable[[str, int, int, Sequence[int], Path, str], List[Tuple[int, str]]],
    extract_multi_panel_page_texts: Optional[
        Callable[[str, int, int, Sequence[int], Path, str], List[Tuple[int, str]]]
    ] = None,
    page_mapping: Optional[Dict[str, Any]] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Tuple[List[Tuple[int, str]], str]:
    extracted_pages: List[Tuple[int, str]] = []
    page_label_mode = "scan"
    for page in pages:
        pdf_page_number = map_target_page(page, local_page_range)
        if pdf_page_number is None:
            continue
        if page_mapping:
            spread_book_pages = estimate_book_pages_from_scan_page(page_mapping, page)
            pages_per_scan = int(page_mapping.get("pages_per_scan") or 2)
            if pages_per_scan == 2:
                spread_pages = extract_spread_page_texts(
                    pdf_path,
                    pdf_page_number,
                    page,
                    spread_book_pages,
                    output_dir,
                    ocr_model,
                )
                if spread_pages:
                    extracted_pages.extend(spread_pages)
                    page_label_mode = "book"
                    continue
            elif spread_book_pages:
                if pages_per_scan > 2 and extract_multi_panel_page_texts is not None:
                    panel_pages = extract_multi_panel_page_texts(
                        pdf_path,
                        pdf_page_number,
                        page,
                        spread_book_pages,
                        output_dir,
                        ocr_model,
                    )
                    if panel_pages:
                        extracted_pages.extend(panel_pages)
                        page_label_mode = "book"
                        continue
                page_text = ""
                for attempt in range(3):
                    page_text = extract_page_text(pdf_path, pdf_page_number, output_dir, ocr_model)
                    if clean_text(page_text):
                        break
                    sleep(0.8 * (attempt + 1))
                if page_text:
                    extracted_pages.extend((book_page, page_text) for book_page in spread_book_pages)
                    page_label_mode = "book"
                    continue
        page_text = ""
        for attempt in range(3):
            page_text = extract_page_text(pdf_path, pdf_page_number, output_dir, ocr_model)
            if clean_text(page_text):
                break
            sleep(0.8 * (attempt + 1))
        if page_text:
            extracted_pages.append((page, page_text))
    return extracted_pages, page_label_mode
