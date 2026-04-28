import argparse
import csv
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests


BASE_DIR = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run NER using strict prompt file + qwen3.6-plus on page blocks."
    )
    parser.add_argument("--start-page", type=int, default=211)
    parser.add_argument("--end-page", type=int, default=220)
    parser.add_argument(
        "--prompt-file",
        type=str,
        default=r"C:\Users\lyzha\Downloads\NER_Prompt_new.md",
    )
    parser.add_argument(
        "--ocr-dir",
        type=str,
        default=str(BASE_DIR / "ocr_output" / "full_pages" / "ocr_layout_aware_211_220"),
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(BASE_DIR / "ocr_output" / "full_pages" / "ner_qwen36_211_220"),
    )
    parser.add_argument("--model", type=str, default="qwen3.6-plus")
    parser.add_argument("--max-retries", type=int, default=4)
    parser.add_argument("--sleep-seconds", type=float, default=1.2)
    parser.add_argument("--skip-existing", action="store_true")
    return parser.parse_args()


def load_prompt(prompt_path: Path) -> str:
    # Keep prompt text exactly from file.
    try:
        return prompt_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return prompt_path.read_text(encoding="utf-8-sig")


def load_api_key() -> str:
    # Priority follows user instruction first.
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

        # 1) whole-file single key
        if "\n" not in text and len(text) > 20 and " " not in text:
            return text.strip()

        # 2) key-value lines, prioritize qwen/dashscope
        lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        priority_hits: List[str] = []
        fallback_hits: List[str] = []
        for ln in lines:
            if "=" in ln:
                k, v = ln.split("=", 1)
                key_name = k.strip().lower()
                value = v.strip().strip("'").strip('"')
                if not value:
                    continue
                if "qwen" in key_name or "dashscope" in key_name:
                    priority_hits.append(value)
                elif "api" in key_name or "key" in key_name:
                    fallback_hits.append(value)
            elif len(ln) > 20:
                fallback_hits.append(ln)

        if priority_hits:
            return priority_hits[0]
        if fallback_hits:
            return fallback_hits[0]

    env_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if env_key:
        return env_key
    return ""


def call_qwen(
    api_key: str,
    model: str,
    system_prompt: str,
    block_text: str,
    max_retries: int,
) -> Tuple[bool, str]:
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": block_text},
        ],
        "temperature": 0.1,
        "max_tokens": 4000,
    }

    for i in range(max_retries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=300)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return True, content
            if resp.status_code in (429, 500, 502, 503, 504):
                wait_s = 6 * (i + 1)
                time.sleep(wait_s)
                continue
            return False, f"HTTP {resp.status_code}: {resp.text[:1000]}"
        except Exception as e:
            if i == max_retries - 1:
                return False, f"{type(e).__name__}: {e}"
            time.sleep(5 * (i + 1))
    return False, "Max retries exceeded"


def extract_fenced_block(text: str, lang: str) -> Optional[str]:
    pattern = rf"```{lang}\s*(.*?)\s*```"
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def extract_json_object_fallback(text: str) -> Optional[str]:
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return None


def parse_response(response_text: str) -> Dict:
    result = {
        "json_data": None,
        "csv_data": None,
        "parse_error": None,
    }

    json_text = extract_fenced_block(response_text, "json")
    if json_text is None:
        json_text = extract_json_object_fallback(response_text)

    if json_text:
        try:
            result["json_data"] = json.loads(json_text)
        except Exception as e:
            result["parse_error"] = f"JSON parse failed: {e}"

    csv_text = extract_fenced_block(response_text, "csv")
    if csv_text:
        result["csv_data"] = csv_text

    return result


def to_flat_row(page: int, block: int, obj: Dict) -> Dict:
    person = obj.get("person_info", {}) if isinstance(obj, dict) else {}
    current = obj.get("current_status", {}) if isinstance(obj, dict) else {}
    traj = obj.get("trajectory_summary", {}) if isinstance(obj, dict) else {}
    return {
        "page": page,
        "block": block,
        "name": person.get("name"),
        "birth_date": person.get("birth_date"),
        "registered_domicile": person.get("registered_domicile"),
        "current_organization": current.get("organization"),
        "current_title": current.get("title"),
        "responsibilities_details": current.get("responsibilities_details"),
        "organization_flow": traj.get("organization_flow"),
        "location_flow": traj.get("location_flow"),
    }


def to_flat_rows(page: int, block: int, json_data) -> List[Dict]:
    if isinstance(json_data, dict):
        return [to_flat_row(page, block, json_data)]
    if isinstance(json_data, list):
        rows: List[Dict] = []
        for item in json_data:
            if isinstance(item, dict):
                rows.append(to_flat_row(page, block, item))
        return rows
    return []


def main() -> None:
    args = parse_args()
    prompt_path = Path(args.prompt_file)
    ocr_dir = Path(args.ocr_dir)
    output_dir = Path(args.output_dir)
    raw_dir = output_dir / "raw_responses"
    parsed_dir = output_dir / "parsed_blocks"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    parsed_dir.mkdir(parents=True, exist_ok=True)

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    prompt_text = load_prompt(prompt_path)

    api_key = load_api_key()
    if not api_key:
        raise RuntimeError("API key not found. Expected secret/api_key.txt or secrets/api_keys.txt.")

    summary_pages: List[Dict] = []
    flat_rows: List[Dict] = []
    total_calls = 0
    total_success = 0
    total_failed = 0

    print(f"[INFO] Prompt file: {prompt_path}")
    print(f"[INFO] OCR dir: {ocr_dir}")
    print(f"[INFO] Output dir: {output_dir}")
    print(f"[INFO] Pages: {args.start_page}-{args.end_page}")
    print(f"[INFO] Model: {args.model}")

    for page in range(args.start_page, args.end_page + 1):
        page_result = {
            "page": page,
            "blocks": [],
            "missing_blocks": [],
            "errors": [],
        }
        print(f"[INFO] Processing page_{page:04d}")

        for block in range(1, 7):
            stem = f"page_{page:04d}_block_{block}"
            txt_path = ocr_dir / f"{stem}.txt"
            raw_path = raw_dir / f"{stem}.md"
            parsed_path = parsed_dir / f"{stem}.json"

            if not txt_path.exists():
                page_result["missing_blocks"].append(block)
                continue

            if args.skip_existing and parsed_path.exists() and raw_path.exists():
                parsed_obj = json.loads(parsed_path.read_text(encoding="utf-8"))
                page_result["blocks"].append(parsed_obj)
                if parsed_obj.get("ok") and parsed_obj.get("json_data") is not None:
                    flat_rows.extend(to_flat_rows(page, block, parsed_obj["json_data"]))
                continue

            block_text = txt_path.read_text(encoding="utf-8", errors="replace").strip()
            user_input = f"<page_{page:04d}_block_{block}>\n{block_text}\n</page_{page:04d}_block_{block}>"

            total_calls += 1
            ok, content_or_error = call_qwen(
                api_key=api_key,
                model=args.model,
                system_prompt=prompt_text,
                block_text=user_input,
                max_retries=args.max_retries,
            )

            if ok:
                total_success += 1
                raw_path.write_text(content_or_error, encoding="utf-8")
                parsed = parse_response(content_or_error)
                block_result = {
                    "page": page,
                    "block": block,
                    "ok": True,
                    "source_txt": str(txt_path),
                    "raw_response": str(raw_path),
                    "json_data": parsed["json_data"],
                    "csv_data": parsed["csv_data"],
                    "parse_error": parsed["parse_error"],
                }
                if parsed["json_data"] is not None:
                    flat_rows.extend(to_flat_rows(page, block, parsed["json_data"]))
            else:
                total_failed += 1
                block_result = {
                    "page": page,
                    "block": block,
                    "ok": False,
                    "source_txt": str(txt_path),
                    "error": content_or_error,
                }
                page_result["errors"].append({"block": block, "error": content_or_error})

            parsed_path.write_text(
                json.dumps(block_result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            page_result["blocks"].append(block_result)
            time.sleep(args.sleep_seconds)

        # Save per-page merged NER JSON
        page_json_path = output_dir / f"page_{page:04d}_ner.json"
        page_payload = {
            "page": page,
            "blocks": page_result["blocks"],
            "missing_blocks": page_result["missing_blocks"],
            "errors": page_result["errors"],
        }
        page_json_path.write_text(json.dumps(page_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        summary_pages.append(page_payload)

    # Save consolidated JSON
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    all_json = output_dir / f"ner_blocks_pages_{args.start_page:04d}_{args.end_page:04d}_{timestamp}.json"
    all_json.write_text(json.dumps(summary_pages, ensure_ascii=False, indent=2), encoding="utf-8")

    # Save consolidated CSV from parsed JSON
    csv_path = output_dir / f"ner_blocks_pages_{args.start_page:04d}_{args.end_page:04d}_{timestamp}.csv"
    csv_headers = [
        "page",
        "block",
        "name",
        "birth_date",
        "registered_domicile",
        "current_organization",
        "current_title",
        "responsibilities_details",
        "organization_flow",
        "location_flow",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        writer.writeheader()
        for row in flat_rows:
            writer.writerow(row)

    run_summary = {
        "start_page": args.start_page,
        "end_page": args.end_page,
        "model": args.model,
        "prompt_file": str(prompt_path),
        "ocr_dir": str(ocr_dir),
        "output_dir": str(output_dir),
        "total_calls": total_calls,
        "total_success": total_success,
        "total_failed": total_failed,
        "rows_in_csv": len(flat_rows),
        "all_json": str(all_json),
        "all_csv": str(csv_path),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    summary_path = output_dir / f"run_summary_{args.start_page:04d}_{args.end_page:04d}_{timestamp}.json"
    summary_path.write_text(json.dumps(run_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[INFO] NER finished.")
    print(f"[INFO] total_calls={total_calls}, success={total_success}, failed={total_failed}")
    print(f"[INFO] summary={summary_path}")


if __name__ == "__main__":
    main()
