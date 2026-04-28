"""
Coordinate-driven cleanup and NER pipeline for 満洲紳士録.

This script reuses the full ndlocr-lite XML output from
ocr_output/full_pages/ocr.  The old three-slice OCR pass preserved complete
vertical text lines better than later top/middle/bottom crops, so the
optimization here is to reconstruct person entries from XML line coordinates
and NDL text-block metadata before sending anything to NER.

NER is intentionally limited to a single source page per run.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import requests
from PIL import Image


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OCR_DIR = BASE_DIR / "ocr_output" / "full_pages" / "ocr"
DEFAULT_OUTPUT_DIR = BASE_DIR / "ocr_output" / "optimized_manshu"
DEFAULT_MODEL = "qwen3.6-plus"
DEFAULT_BLOCK_ORDER = (2, 1, 0)  # Japanese spread reading order: right -> middle -> left.
DEFAULT_IMAGES_DIR = BASE_DIR / "ocr_output" / "full_pages" / "images"
DEFAULT_HALVES_SPLIT_DIR = BASE_DIR / "ocr_output" / "optimized_manshu_halves" / "split"
DEFAULT_HALVES_OCR_DIR = BASE_DIR / "ocr_output" / "optimized_manshu_halves" / "ocr"


FIELD_MARKERS = [
    "【出生】",
    "【生】",
    "【本籍】",
    "【續柄】",
    "【続柄】",
    "【學歴】",
    "【学歴】",
    "【經歴】",
    "【経歴】",
    "【趣味】",
    "【宗教】",
    "【家族】",
    "【住所】",
]

NAME_RE = re.compile(r"^[一-龥々〆ヵヶ]{2,6}$")
LIKELY_NAME_RE = re.compile(r"^[一-龥々〆ヵヶ]{2,6}$")
NUMERAL_CHARS = set("一二三四五六七八九十〇零")
ADDRESS_HINT_RE = re.compile(r"(?:路|街|町|村|區|区|市|縣|県|郡|號|号|番|丁目|胡同|通|電|ノ)")
PLACE_NAME_TOLERANT_ADDRESS_HINT_RE = re.compile(
    r"(?:路|街|町|區|区|縣|県|郡|號|号|番|丁目|胡同|通|電|ノ)"
)
HEADING_HINT_RE = re.compile(
    r"(?:勳|勲|從|従|正|位|等|滿|満|鐵|鉄|電|局|處|処|部|課|係|官|技|師|事|長|主任|"
    r"理事|公社|株|會|社|銀行|醫院|医院|學院|学院|參事|参事|少尉|所長|係長|課長)"
)
FIELD_MARKER_RE = re.compile(r"【[^】]{1,8}】|住所】|家族】|宗教】|趣味】")
NON_PERSON_TITLE_RE = re.compile(
    r"(?:局|部|課|係|處|処|署|廳|庁|府|省|縣|県|市|町|村|社|會|会|銀行|醫院|医院|"
    r"學院|学院|學校|学校|公會|公会|組合|協會|协会|會社|会社)$"
)


@dataclass
class OCRLine:
    text: str
    line_type: str
    order: int
    x: int
    y: int
    width: int
    height: int
    confidence: float
    block_index: int
    textblock_index: int

    @property
    def is_title(self) -> bool:
        compact_text = re.sub(r"\s+", "", self.text.strip())
        if "タイトル" in self.line_type and NAME_RE.match(compact_text):
            return True
        return False


@dataclass
class TextBlock:
    block_index: int
    textblock_index: int
    confidence: float
    lines: List[OCRLine] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines if line.text).strip()

    @property
    def has_title(self) -> bool:
        return any(line.is_title for line in self.lines)


@dataclass
class PersonEntry:
    page: int
    entry_index: int
    name: Optional[str]
    raw_text: str
    normalized_text: str
    source_blocks: List[int]
    line_count: int
    char_count: int
    marker_count: int
    avg_confidence: Optional[float]
    low_confidence_ratio: float
    starts_with_title: bool
    needs_review: bool
    review_reasons: List[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconstruct 満洲紳士録 person entries from ndlocr-lite XML and optionally run one-page NER."
    )
    parser.add_argument("--page", type=int, help="Single page to process. Overrides --start-page/--end-page.")
    parser.add_argument("--start-page", type=int, default=None)
    parser.add_argument("--end-page", type=int, default=None)
    parser.add_argument("--ocr-dir", type=str, default=str(DEFAULT_OCR_DIR))
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--layout",
        choices=["old3", "halves"],
        default="old3",
        help="OCR source layout. old3 reuses full_pages/ocr; halves uses right/left single-page OCR.",
    )
    parser.add_argument("--images-dir", type=str, default=str(DEFAULT_IMAGES_DIR))
    parser.add_argument("--halves-split-dir", type=str, default=str(DEFAULT_HALVES_SPLIT_DIR))
    parser.add_argument("--halves-ocr-dir", type=str, default=str(DEFAULT_HALVES_OCR_DIR))
    parser.add_argument(
        "--run-ocr-halves",
        action="store_true",
        help="For --layout halves, crop right/left pages and run ndlocr-lite when XML is missing.",
    )
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument(
        "--block-order",
        type=str,
        default="2,1,0",
        help="Comma-separated old OCR block order. Default 2,1,0 for right-to-left spread reading.",
    )
    parser.add_argument("--min-entry-chars", type=int, default=40)
    parser.add_argument("--ner", action="store_true", help="Run Qwen NER. Refuses ranges larger than one page.")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument(
        "--ner-entry-limit",
        type=int,
        default=None,
        help="Limit NER to the first N entries of the page. Useful for constrained prompt tests.",
    )
    parser.add_argument(
        "--ner-chunk-size",
        type=int,
        default=6,
        help="Number of entries per Qwen call. The source page is still limited to one page.",
    )
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    return parser.parse_args()


def parse_page_range(args: argparse.Namespace) -> Tuple[int, int]:
    if args.page is not None:
        return args.page, args.page
    if args.start_page is None or args.end_page is None:
        raise ValueError("Provide --page or both --start-page and --end-page.")
    if args.end_page < args.start_page:
        raise ValueError("--end-page must be >= --start-page.")
    return args.start_page, args.end_page


def parse_block_order(value: str) -> Tuple[int, ...]:
    try:
        order = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise ValueError("--block-order must contain integers, e.g. 2,1,0") from exc
    if not order:
        raise ValueError("--block-order cannot be empty.")
    return order


def load_api_key() -> str:
    candidates = [
        BASE_DIR / "secret" / "api_key.txt",
        BASE_DIR / "secrets" / "api_key.txt",
        BASE_DIR / "secrets" / "api_keys.txt",
    ]
    for path in candidates:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue
        if "\n" not in text and len(text) > 20 and " " not in text:
            return text.strip()
        preferred: List[str] = []
        fallback: List[str] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key_l = key.strip().lower()
                value = value.strip().strip("'").strip('"')
                if not value:
                    continue
                if "qwen" in key_l or "dashscope" in key_l:
                    preferred.append(value)
                elif "api" in key_l or "key" in key_l:
                    fallback.append(value)
            elif len(line) > 20:
                fallback.append(line)
        if preferred:
            return preferred[0]
        if fallback:
            return fallback[0]
    return os.environ.get("DASHSCOPE_API_KEY", "").strip()


def parse_int(value: Optional[str], default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(float(value))
    except ValueError:
        return default


def parse_float(value: Optional[str], default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def parse_ocr_xml(xml_path: Path, block_index: int) -> List[TextBlock]:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    textblocks: List[TextBlock] = []

    for tb_idx, elem in enumerate(root.iter("TEXTBLOCK")):
        tb = TextBlock(
            block_index=block_index,
            textblock_index=tb_idx,
            confidence=parse_float(elem.attrib.get("CONF")),
        )
        for line_elem in elem.iter("LINE"):
            text = (line_elem.attrib.get("STRING") or "").strip()
            if not text:
                continue
            line = OCRLine(
                text=text,
                line_type=line_elem.attrib.get("TYPE", ""),
                order=parse_int(line_elem.attrib.get("ORDER")),
                x=parse_int(line_elem.attrib.get("X")),
                y=parse_int(line_elem.attrib.get("Y")),
                width=parse_int(line_elem.attrib.get("WIDTH")),
                height=parse_int(line_elem.attrib.get("HEIGHT")),
                confidence=parse_float(line_elem.attrib.get("CONF")),
                block_index=block_index,
                textblock_index=tb_idx,
            )
            tb.lines.append(line)
        tb.lines.sort(key=lambda line: line.order)
        if tb.lines:
            textblocks.append(tb)
    return textblocks


def load_page_textblocks(ocr_dir: Path, page: int, block_order: Sequence[int]) -> List[TextBlock]:
    page_dir = ocr_dir / f"page_{page:04d}"
    if not page_dir.exists():
        raise FileNotFoundError(f"OCR page directory not found: {page_dir}")

    textblocks: List[TextBlock] = []
    for block_index in block_order:
        xml_path = page_dir / f"page_{page:04d}_block_{block_index}.xml"
        if not xml_path.exists():
            raise FileNotFoundError(f"OCR XML not found: {xml_path}")
        textblocks.extend(parse_ocr_xml(xml_path, block_index))
    return textblocks


def split_double_page_to_halves(image_path: Path, split_dir: Path, page: int) -> Dict[str, Path]:
    if not image_path.exists():
        raise FileNotFoundError(f"Page image not found: {image_path}")
    split_dir.mkdir(parents=True, exist_ok=True)
    image = Image.open(image_path)
    width, height = image.size
    center = width // 2
    outputs = {
        "right": split_dir / f"page_{page:04d}_right.png",
        "left": split_dir / f"page_{page:04d}_left.png",
    }
    if not outputs["right"].exists():
        image.crop((center, 0, width, height)).save(outputs["right"])
    if not outputs["left"].exists():
        image.crop((0, 0, center, height)).save(outputs["left"])
    return outputs


def run_ndlocr(image_path: Path, ocr_dir: Path, device: str) -> None:
    ocr_dir.mkdir(parents=True, exist_ok=True)
    ndlocr_script = BASE_DIR / "ndlocr-lite" / "src" / "ocr.py"
    cmd = [
        os.sys.executable,
        str(ndlocr_script),
        "--sourceimg",
        str(image_path),
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
        timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ndlocr-lite failed for {image_path.name}: {proc.stderr[-1000:]}")


def ensure_halves_ocr(
    page: int,
    images_dir: Path,
    split_dir: Path,
    ocr_dir: Path,
    run_ocr: bool,
    device: str,
) -> None:
    expected = [ocr_dir / f"page_{page:04d}_{side}.xml" for side in ("right", "left")]
    if all(path.exists() for path in expected):
        return
    if not run_ocr:
        missing = ", ".join(str(path) for path in expected if not path.exists())
        raise FileNotFoundError(
            f"Missing half-page OCR XML: {missing}. Re-run with --run-ocr-halves or provide --halves-ocr-dir."
        )
    image_path = images_dir / f"page_{page:04d}.png"
    half_paths = split_double_page_to_halves(image_path, split_dir, page)
    for side in ("right", "left"):
        xml_path = ocr_dir / f"page_{page:04d}_{side}.xml"
        if not xml_path.exists():
            run_ndlocr(half_paths[side], ocr_dir, device)


def load_page_textblocks_halves(ocr_dir: Path, page: int) -> List[TextBlock]:
    textblocks: List[TextBlock] = []
    for block_index, side in enumerate(("right", "left"), start=1):
        xml_path = ocr_dir / f"page_{page:04d}_{side}.xml"
        if not xml_path.exists():
            raise FileNotFoundError(f"Half-page OCR XML not found: {xml_path}")
        textblocks.extend(parse_ocr_xml(xml_path, block_index))
    return textblocks


def normalize_ocr_text(text: str) -> str:
    """Normalize high-frequency OCR noise while preserving original text separately."""
    replacements = [
        ("【生】", "【出生】"),
        ("【出】", "【出生】"),
        ("【玉籍】", "【本籍】"),
        ("玉籍", "本籍"),
        ("【本箱】", "【本籍】"),
        ("本箱", "本籍"),
        ("【住尻", "【住所】"),
        ("【住所", "【住所】"),
        ("住所】", "【住所】"),
        ("【經】", "【經歴】"),
        ("【経】", "【経歴】"),
        ("【經歴", "【經歴】"),
        ("【経歴", "【経歴】"),
        ("經歴】", "【經歴】"),
        ("経歴】", "【経歴】"),
        ("【學】", "【學歴】"),
        ("【学】", "【学歴】"),
        ("【學歴", "【學歴】"),
        ("【学歴", "【学歴】"),
        ("學歴】", "【學歴】"),
        ("学歴】", "【学歴】"),
        ("【趣】", "【趣味】"),
        ("趣味】", "【趣味】"),
        ("宗教】", "【宗教】"),
        ("家族】", "【家族】"),
    ]
    normalized = text
    for old, new in replacements:
        normalized = normalized.replace(old, new)
    normalized = re.sub(r"(?<!【)(出生|本籍|續柄|続柄|續|學歴|学歴|經歴|経歴|經歷|住所|家族|宗教|趣味)】", r"【\1】", normalized)
    normalized = re.sub(r"(?<!【)(住所)(?=[一-龥])", r"【住所】", normalized)
    normalized = re.sub(r"(?<!【)(家族)(?=[妻父母長男長女子])", r"【家族】", normalized)
    normalized = re.sub(r"【(住所|家族|宗教|趣味|經歴|経歴|學歴|学歴)(?!】)", r"【\1】", normalized)
    normalized = re.sub(r"【+([^【】\n]{1,8})】+", r"【\1】", normalized)
    normalized = normalized.replace("【出【生】", "【出生】")
    normalized = normalized.replace("【經歷】", "【經歴】")
    normalized = normalized.replace("【續】", "【續柄】")
    normalized = normalized.replace("【生生", "【出生】")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def is_probable_person_name(text: str, allow_place_name_chars: bool = False) -> bool:
    text = text.strip()
    if not LIKELY_NAME_RE.match(text):
        return False
    address_hint_re = PLACE_NAME_TOLERANT_ADDRESS_HINT_RE if allow_place_name_chars else ADDRESS_HINT_RE
    if address_hint_re.search(text):
        return False
    numeral_count = sum(1 for char in text if char in NUMERAL_CHARS)
    # Names such as 一郎 and 三郎 are common; address strings often contain
    # repeated numerals like 三馬路一一七.
    if numeral_count >= 2 and not text.endswith(("一郎", "二郎", "三郎", "四郎", "五郎", "六郎", "七郎", "八郎", "九郎")):
        trailing_numerals = len(re.search(r"[一二三四五六七八九十〇零]+$", text).group(0)) if re.search(r"[一二三四五六七八九十〇零]+$", text) else 0
        prefix = text[:-trailing_numerals] if trailing_numerals else text
        if not (1 <= trailing_numerals <= 2 and prefix and not any(char in NUMERAL_CHARS for char in prefix)):
            return False
    return True


def is_likely_title_line(line: OCRLine) -> bool:
    text = line.text.strip()
    compact_text = re.sub(r"\s+", "", text)
    if NON_PERSON_TITLE_RE.search(compact_text):
        return False
    # ndlocr-lite's title classifier is more reliable than the address-word
    # guard below. Names such as 市場元, 奥村重直, 松村勇夫, 市川重三郎 would
    # otherwise be rejected because they contain 市/村.
    if line.is_title and is_probable_person_name(compact_text, allow_place_name_chars=True):
        return True
    if line.height >= 150 and line.width <= 70 and is_probable_person_name(compact_text, allow_place_name_chars=True):
        return True
    return False


def is_heading_line(line: OCRLine) -> bool:
    text = line.text.strip()
    if len(text) < 5:
        return False
    if FIELD_MARKER_RE.search(text):
        return bool(
            "【出生】" in text
            and HEADING_HINT_RE.search(text)
            and not re.search(r"(?:住所|家族|妻|長男|長女|母|父|嗣子)", text)
        )
    if re.search(r"(?:住所|其局|其所|社宅|胡同|大街|街|町|番地|電[〇一二三四五六七八九十\d]|[〇一二三四五六七八九十\d]+[-－ノ])", text):
        return False
    if re.search(r"(?:卒|歷|歴|入社|勤務|現職|住所|家族|妻|長男|長女)", text):
        return False
    return bool(HEADING_HINT_RE.search(text))


def pop_trailing_heading_lines(lines: List[OCRLine], max_lines: int = 3) -> Tuple[List[OCRLine], List[OCRLine]]:
    if not lines:
        return [], []
    split_at = len(lines)
    moved = 0
    idx = len(lines) - 1
    while idx >= 0 and moved < max_lines and is_heading_line(lines[idx]):
        split_at = idx
        moved += 1
        idx -= 1
    return lines[:split_at], lines[split_at:]


def split_lines_into_entry_chunks(textblocks: Iterable[TextBlock]) -> Tuple[List[List[OCRLine]], List[OCRLine]]:
    entries: List[List[OCRLine]] = []
    carryover: List[OCRLine] = []
    current: List[OCRLine] = []
    current_has_title = False

    for textblock in textblocks:
        for line in textblock.lines:
            if is_likely_title_line(line):
                previous_lines, heading_lines = pop_trailing_heading_lines(current)
                if current:
                    if current_has_title:
                        if previous_lines:
                            entries.append(previous_lines)
                    else:
                        carryover.extend(previous_lines)
                current = heading_lines + [line]
                current_has_title = True
            else:
                if current_has_title:
                    current.append(line)
                else:
                    carryover.append(line)

    if current:
        if current_has_title:
            entries.append(current)
        else:
            carryover.extend(current)

    return entries, carryover


def entry_from_lines(page: int, entry_index: int, lines: List[OCRLine], min_entry_chars: int) -> PersonEntry:
    raw_text = "\n".join(line.text for line in lines if line.text).strip()
    normalized_text = normalize_ocr_text(raw_text)
    confidences = [line.confidence for line in lines if line.confidence > 0]
    avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else None
    low_conf = sum(1 for conf in confidences if conf < 0.86)
    low_ratio = round(low_conf / len(confidences), 4) if confidences else 0.0
    source_blocks = sorted({line.block_index for line in lines})
    title_lines = [re.sub(r"\s+", "", line.text.strip()) for line in lines if is_likely_title_line(line)]
    name = title_lines[0] if title_lines else None
    marker_count = sum(normalized_text.count(marker) for marker in FIELD_MARKERS)

    reasons: List[str] = []
    if len(normalized_text) < min_entry_chars:
        reasons.append("short_entry")
    if marker_count < 2:
        reasons.append("few_field_markers")
    if low_ratio > 0.25:
        reasons.append("many_low_confidence_lines")
    if not name:
        reasons.append("missing_title_name")
    for core_marker in ("【出生】", "【本籍】", "【經歴】", "【経歴】"):
        if normalized_text.count(core_marker) > 1:
            reasons.append(f"repeated_{core_marker.strip('【】')}")

    return PersonEntry(
        page=page,
        entry_index=entry_index,
        name=name,
        raw_text=raw_text,
        normalized_text=normalized_text,
        source_blocks=source_blocks,
        line_count=len(lines),
        char_count=len(normalized_text),
        marker_count=marker_count,
        avg_confidence=avg_conf,
        low_confidence_ratio=low_ratio,
        starts_with_title=bool(lines and is_likely_title_line(lines[0])),
        needs_review=bool(reasons),
        review_reasons=reasons,
    )


def reconstruct_page_entries(
    ocr_dir: Path,
    page: int,
    block_order: Sequence[int],
    min_entry_chars: int,
    layout: str = "old3",
) -> Dict:
    if layout == "halves":
        textblocks = load_page_textblocks_halves(ocr_dir, page)
        effective_block_order: Sequence[int] = (1, 2)
    else:
        textblocks = load_page_textblocks(ocr_dir, page, block_order)
        effective_block_order = block_order
    entry_chunks, carryover_lines = split_lines_into_entry_chunks(textblocks)
    entries = [
        entry_from_lines(page, idx + 1, lines, min_entry_chars)
        for idx, lines in enumerate(entry_chunks)
    ]

    carryover_text = "\n".join(line.text for line in carryover_lines if line.text).strip()
    summary = {
        "page": page,
        "source": str(ocr_dir / f"page_{page:04d}"),
        "layout": layout,
        "block_order": list(effective_block_order),
        "textblock_count": len(textblocks),
        "entry_count": len(entries),
        "review_count": sum(1 for entry in entries if entry.needs_review),
        "carryover_char_count": len(carryover_text),
        "carryover_preview": normalize_ocr_text(carryover_text)[:500],
        "entries": [asdict(entry) for entry in entries],
    }
    return summary


def build_ner_prompt(page_data: Dict, entries_override: Optional[List[Dict]] = None) -> str:
    source_entries = entries_override if entries_override is not None else page_data["entries"]
    entries = [
        {
            "entry_id": item["entry_index"],
            "name_hint": item["name"],
            "quality": {
                "needs_review_by_precheck": item["needs_review"],
                "review_reasons": item["review_reasons"],
                "avg_confidence": item["avg_confidence"],
                "low_confidence_ratio": item["low_confidence_ratio"],
                "marker_count": item["marker_count"],
            },
            "text": item["normalized_text"],
        }
        for item in source_entries
        if item["char_count"] >= 40
    ]
    input_json = json.dumps(
        {
            "page": page_data["page"],
            "entries": entries,
        },
        ensure_ascii=False,
        indent=2,
    )
    return f"""# Role
你是一个精通近代中日关系史、满洲国历史以及日文历史文献处理的数字人文专家。你的任务是对近代日本出版的人事兴信录/绅士录文本进行命名实体识别（NER）与结构化信息提取。

# Task
下面是一页《満洲紳士録》经过 ndlocr-lite OCR 和坐标重建后得到的人物条目。请逐条提取实体信息，还原其工作单位与地理位置的时空序列，并生成直观的变迁轨迹字符串。

# Extraction Rules (Crucial)
1. 年号补全：将“明、大、昭、康德/康徳、同”等缩写在提取时补全为标准格式。例：明三九・九 -> 明治39年9月；“同十四年”必须根据前一个年号上下文还原。
2. 地理省略复原：遇到“同上”“同縣”“同市”等省略时，根据同一条目上文还原；不能还原时保留原文并在 normalized 字段填 null。
3. 机构简称识别：常见简称应给出全称或规范名。例：滿鐵 -> 南滿洲鐵道株式會社；早大 -> 早稻田大学。
4. 现职提取：姓名前后紧邻的头衔、机构、职位，以及【經歴】末尾由“現職に就く/現官職に就く/現本官職に就く”等引出的现职信息必须尽量完整提取。
5. 职业轨迹与空间调动：按严格时间顺序切分【經歴】；必须拆解“工作单位/机构”“职位”“工作地点”。若地点隐含在机构名中，也要提取到 location。
6. 变迁轨迹生成：organization_flow 使用 " -> " 连接机构；location_flow 使用 " -> " 连接地点。
7. 质量控制：如果 OCR 条目明显混入两个人、字段残缺、乱码严重，请仍尽量抽取可确定部分，同时设置 needs_review=true 并说明 review_reason。
8. 证据约束：所有抽取均必须来自输入文本；不要补造读音、亲属名、学校名、机构名。evidence_text 只给短证据片段。

# Output Instruction
只输出一个合法 JSON 对象，不要输出 Markdown，不要输出 CSV。CSV 会由程序根据 JSON 生成。

# JSON Schema
{{
  "page": 页码,
  "persons": [
    {{
      "entry_id": 输入条目编号,
      "needs_review": false,
      "review_reason": null,
      "person_info": {{
        "name": "姓名",
        "birth_date": "出生日期，按最新prompt补全年号后的形式",
        "birth_date_raw": "出生日期原文",
        "registered_domicile": "本籍地，尽量复原同上/同縣",
        "registered_domicile_raw": "本籍原文"
      }},
      "current_status": {{
        "title": "现职头衔/职位",
        "organization": "现职机构",
        "responsibilities_details": "现职具体负责的业务范围或管辖区域，保留原文；没有则 null",
        "evidence_text": "现职证据片段"
      }},
      "education": [
        {{
          "time": "时间或 null",
          "school": "学校/科系",
          "status": "卒/修/中退等或 null",
          "evidence_text": "证据片段"
        }}
      ],
      "career_trajectory": [
        {{
          "time": "时间，尽量补全年号；没有则 null",
          "organization": "机构",
          "position": "职位或 null",
          "location": "地点，尽量精确到城市/县/工厂所在地",
          "mobility_event": "调度性质，如入社、轉勤、就任、歴任、渡滿、任等",
          "evidence_text": "证据片段"
        }}
      ],
      "trajectory_summary": {{
        "organization_flow": "机构变迁轨迹字符串",
        "location_flow": "地理移动轨迹字符串"
      }},
      "family_raw": "家族字段原文或 null",
      "address_raw": "住所字段原文或 null",
      "hobbies_raw": "趣味字段原文或 null",
      "religion_raw": "宗教字段原文或 null"
    }}
  ]
}}

# Input
{input_json}
"""


def call_qwen(api_key: str, model: str, prompt: str, max_retries: int) -> Tuple[bool, str]:
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.05,
        "max_tokens": 12000,
    }
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=360)
            if response.status_code == 200:
                data = response.json()
                return True, data["choices"][0]["message"]["content"]
            if response.status_code in {429, 500, 502, 503, 504}:
                time.sleep(8 * (attempt + 1))
                continue
            return False, f"HTTP {response.status_code}: {response.text[:1200]}"
        except Exception as exc:
            if attempt == max_retries - 1:
                return False, f"{type(exc).__name__}: {exc}"
            time.sleep(6 * (attempt + 1))
    return False, "Max retries exceeded"


def extract_json_response(text: str) -> Dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        return json.loads(fenced.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("No JSON object found in response.")


def chunked(items: List[Dict], size: int) -> Iterable[List[Dict]]:
    if size <= 0:
        raise ValueError("--ner-chunk-size must be positive.")
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]


def run_ner_for_page(
    page_data: Dict,
    output_dir: Path,
    model: str,
    max_retries: int,
    entry_limit: Optional[int],
    chunk_size: int,
) -> Dict:
    api_key = load_api_key()
    if not api_key:
        raise RuntimeError("DASHSCOPE/Qwen API key not found in secrets or environment.")

    ner_dir = output_dir / "ner"
    ner_dir.mkdir(parents=True, exist_ok=True)

    page = int(page_data["page"])
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = ner_dir / f"page_{page:04d}_ner_{timestamp}.json"
    csv_path = ner_dir / f"page_{page:04d}_ner_{timestamp}.csv"

    ner_entries = [entry for entry in page_data["entries"] if entry["char_count"] >= 40]
    if entry_limit is not None:
        ner_entries = ner_entries[:entry_limit]

    merged = {"page": page, "persons": []}
    calls: List[Dict] = []
    for chunk_index, entry_chunk in enumerate(chunked(ner_entries, chunk_size), start=1):
        prompt = build_ner_prompt(page_data, entries_override=entry_chunk)
        prompt_path = ner_dir / f"page_{page:04d}_chunk_{chunk_index:02d}_prompt_{timestamp}.md"
        raw_path = ner_dir / f"page_{page:04d}_chunk_{chunk_index:02d}_raw_{timestamp}.md"
        prompt_path.write_text(prompt, encoding="utf-8")

        ok, content = call_qwen(api_key, model, prompt, max_retries)
        raw_path.write_text(content, encoding="utf-8")
        call_info = {
            "chunk": chunk_index,
            "entry_ids": [entry["entry_index"] for entry in entry_chunk],
            "prompt": str(prompt_path),
            "raw_response": str(raw_path),
            "ok": ok,
        }
        if not ok:
            call_info["error"] = content[:500]
            calls.append(call_info)
            raise RuntimeError(f"Qwen NER failed on chunk {chunk_index}: {content[:500]}")

        parsed_chunk = extract_json_response(content)
        persons = parsed_chunk.get("persons", []) if isinstance(parsed_chunk, dict) else []
        merged["persons"].extend(persons)
        call_info["person_count"] = len(persons)
        calls.append(call_info)
        time.sleep(1.0)

    json_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    write_ner_csv(merged, csv_path)

    return {
        "ok": True,
        "model": model,
        "json": str(json_path),
        "csv": str(csv_path),
        "entry_count_sent": len(ner_entries),
        "chunk_size": chunk_size,
        "calls": calls,
        "person_count": len(merged.get("persons", [])),
    }


def write_ner_csv(parsed: Dict, csv_path: Path) -> None:
    persons = parsed.get("persons", []) if isinstance(parsed, dict) else []
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "page",
                "entry_id",
                "needs_review",
                "name",
                "birth_date",
                "birth_date_raw",
                "registered_domicile_raw",
                "registered_domicile",
                "current_organization",
                "current_title",
                "organization_flow",
                "location_flow",
                "career_trajectory_count",
                "address_raw",
                "review_reason",
            ]
        )
        for person in persons:
            info = person.get("person_info") or {}
            current = person.get("current_status") or {}
            writer.writerow(
                [
                    parsed.get("page"),
                    person.get("entry_id"),
                    person.get("needs_review"),
                    info.get("name"),
                    info.get("birth_date") or info.get("birth_date_normalized"),
                    info.get("birth_date_raw"),
                    info.get("registered_domicile_raw"),
                    info.get("registered_domicile") or info.get("registered_domicile_normalized"),
                    current.get("organization") or current.get("organization_raw"),
                    current.get("title") or current.get("title_raw"),
                    (person.get("trajectory_summary") or {}).get("organization_flow"),
                    (person.get("trajectory_summary") or {}).get("location_flow"),
                    len(person.get("career_trajectory") or person.get("career_events") or []),
                    person.get("address_raw"),
                    person.get("review_reason"),
                ]
            )


def write_page_outputs(page_data: Dict, output_dir: Path) -> Dict:
    pages_dir = output_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    page = int(page_data["page"])
    json_path = pages_dir / f"page_{page:04d}_entries.json"
    txt_path = pages_dir / f"page_{page:04d}_entries.txt"
    json_path.write_text(json.dumps(page_data, ensure_ascii=False, indent=2), encoding="utf-8")

    chunks: List[str] = []
    for entry in page_data["entries"]:
        chunks.append(
            f"===== page_{page:04d} entry_{entry['entry_index']:03d} "
            f"name={entry.get('name') or ''} review={entry['needs_review']} =====\n"
            f"{entry['normalized_text']}"
        )
    txt_path.write_text("\n\n".join(chunks), encoding="utf-8")
    return {"json": str(json_path), "txt": str(txt_path)}


def main() -> None:
    args = parse_args()
    start_page, end_page = parse_page_range(args)
    if args.ner and start_page != end_page:
        raise ValueError("NER is limited to exactly one source page per run. Use --page for NER.")

    ocr_dir = Path(args.halves_ocr_dir) if args.layout == "halves" else Path(args.ocr_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    block_order = parse_block_order(args.block_order)
    images_dir = Path(args.images_dir)
    halves_split_dir = Path(args.halves_split_dir)

    all_pages: List[Dict] = []
    page_outputs: List[Dict] = []
    for page in range(start_page, end_page + 1):
        if args.layout == "halves":
            ensure_halves_ocr(
                page=page,
                images_dir=images_dir,
                split_dir=halves_split_dir,
                ocr_dir=ocr_dir,
                run_ocr=args.run_ocr_halves,
                device=args.device,
            )
        page_data = reconstruct_page_entries(
            ocr_dir=ocr_dir,
            page=page,
            block_order=block_order,
            min_entry_chars=args.min_entry_chars,
            layout=args.layout,
        )
        page_outputs.append({"page": page, **write_page_outputs(page_data, output_dir)})
        all_pages.append(page_data)
        time.sleep(args.sleep_seconds)

    ner_result = None
    if args.ner:
        ner_result = run_ner_for_page(
            page_data=all_pages[0],
            output_dir=output_dir,
            model=args.model,
            max_retries=args.max_retries,
            entry_limit=args.ner_entry_limit,
            chunk_size=args.ner_chunk_size,
        )

    summary = {
        "start_page": start_page,
        "end_page": end_page,
        "ocr_dir": str(ocr_dir),
        "output_dir": str(output_dir),
        "layout": args.layout,
        "block_order": list(block_order),
        "total_pages": len(all_pages),
        "total_entries": sum(page["entry_count"] for page in all_pages),
        "total_review_entries": sum(page["review_count"] for page in all_pages),
        "pages": [
            {
                "page": page["page"],
                "entry_count": page["entry_count"],
                "review_count": page["review_count"],
                "carryover_char_count": page["carryover_char_count"],
            }
            for page in all_pages
        ],
        "page_outputs": page_outputs,
        "ner_result": ner_result,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    summary_path = output_dir / f"run_summary_{start_page:04d}_{end_page:04d}.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
