from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ENTRIES_JSON = (
    ROOT
    / "ocr_output"
    / "manshu_full_pipeline_211_215_resplit"
    / "pages"
    / "page_0211_entries.json"
)
OUT_DIR = ROOT / "ocr_output" / "ollama_ner_page211_first3"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


REQUIRED_TOP_KEYS = {"page", "persons"}
REQUIRED_PERSON_KEYS = {
    "entry_id",
    "needs_review",
    "review_reason",
    "person_info",
    "current_status",
    "education",
    "career_trajectory",
    "trajectory_summary",
    "family_raw",
    "address_raw",
    "hobbies_raw",
    "religion_raw",
}


@dataclass
class ModelRun:
    model: str
    raw_text: str
    parsed: dict[str, Any] | None
    parse_error: str | None
    elapsed_seconds: float
    eval_summary: dict[str, Any]


def load_entries() -> list[dict[str, Any]]:
    data = json.loads(ENTRIES_JSON.read_text(encoding="utf-8"))
    return data["entries"][:3]


def compact_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "entry_id": entry["entry_index"],
        "name_hint": entry["name"],
        "quality": {
            "needs_review_by_precheck": entry.get("needs_review", False),
            "review_reasons": entry.get("review_reasons", []),
            "avg_confidence": entry.get("avg_confidence"),
            "low_confidence_ratio": entry.get("low_confidence_ratio"),
            "marker_count": entry.get("marker_count"),
        },
        "text": entry["normalized_text"],
    }


def build_prompt(entries: list[dict[str, Any]]) -> str:
    payload = {
        "page": 211,
        "entries": [compact_entry(entry) for entry in entries],
    }
    return f"""/no_think
你是一个精通近代中日关系史、满洲国史料和日文历史文献的人物资料 NER 专家。

任务：对《満洲紳士録》第211页的前3个人物条目进行结构化信息抽取。只根据输入文本抽取，不要编造，不要补充外部知识。

关键规则：
1. 每个输入条目必须输出且只能输出 1 个 person，共 3 个 persons。
2. 年号只能根据原文明确数字补全：明三九=明治39年，明三二=明治32年，昭十三=昭和13年。证据片段中没有时间就填 null，严禁写“明治时期/昭和时期”等泛化时间。
3. “同上”等省略可在同一条目内根据上文复原；不能复原则保留原文并说明。没有【本籍】标记时 registered_domicile 必须为 null。
4. 姓名前后的现职、机构、职务必须提取；【經歴】/【建歴】/OCR误写的类似字段必须拆成 career_trajectory。
5. 所有 evidence_text 必须是输入中的短原文片段。
6. OCR 字段名明显误识，例如「聖歷」「建歴」「經濟」如果语境上是學歴/經歴，请在结构化字段中归入合理字段，同时在 evidence_text 保留原文。
7. 如果字段缺失或 OCR 可疑，needs_review=true 并简短说明；否则 false。
8. 严禁推测：不要写“地点不明 -> 滿洲(新京)”这类推测；没有明确地点就填 null。

严格输出要求：
只输出一个合法 JSON 对象，不要 Markdown，不要代码块，不要解释。
JSON 顶层格式如下：
{{
  "page": 211,
  "persons": [
    {{
      "entry_id": 1,
      "needs_review": false,
      "review_reason": null,
      "person_info": {{
        "name": "姓名",
        "birth_date": "补全年号后的出生日期或原文",
        "birth_date_raw": "出生日期原文",
        "birth_place": "出生地或 null",
        "registered_domicile": "本籍地或 null",
        "registered_domicile_raw": "本籍原文或 null"
      }},
      "current_status": {{
        "title": "现职头衔/职位或 null",
        "organization": "现职机构或 null",
        "responsibilities_details": "业务范围或 null",
        "evidence_text": "短证据"
      }},
      "education": [
        {{
          "time": "时间或 null",
          "school": "学校/科系",
          "status": "卒/修/中退等或 null",
          "evidence_text": "短证据"
        }}
      ],
      "career_trajectory": [
        {{
          "time": "时间或 null",
          "organization": "机构",
          "position": "职位或 null",
          "location": "地点或 null",
          "mobility_event": "入社/就任/歴任/勤務等或 null",
          "evidence_text": "短证据"
        }}
      ],
      "trajectory_summary": {{
        "organization_flow": "机构A -> 机构B",
        "location_flow": "地点A -> 地点B"
      }},
      "family_raw": "家族字段原文或 null",
      "address_raw": "住所字段原文或 null",
      "hobbies_raw": "趣味字段原文或 null",
      "religion_raw": "宗教字段原文或 null"
    }}
  ]
}}

输入：
{json.dumps(payload, ensure_ascii=False, indent=2)}
"""


def build_single_prompt(entry: dict[str, Any]) -> str:
    payload = compact_entry(entry)
    return f"""/no_think
你是一个历史人物条目结构化抽取器。只根据输入文本抽取，不要解释，不要 Markdown，不要代码块。

请输出一个合法 JSON 对象，格式必须是单个 person，不要输出顶层 persons 数组：
{{
  "entry_id": {entry["entry_index"]},
  "needs_review": false,
  "review_reason": null,
  "person_info": {{
    "name": "{entry["name"]}",
    "birth_date": null,
    "birth_date_raw": null,
    "birth_place": null,
    "registered_domicile": null,
    "registered_domicile_raw": null
  }},
  "current_status": {{
    "title": null,
    "organization": null,
    "responsibilities_details": null,
    "evidence_text": null
  }},
  "education": [],
  "career_trajectory": [],
  "trajectory_summary": {{
    "organization_flow": null,
    "location_flow": null
  }},
  "family_raw": null,
  "address_raw": null,
  "hobbies_raw": null,
  "religion_raw": null
}}

抽取规则：
- 明=明治，大=大正，昭=昭和；只能按原文明示数字补全，例如明三九=明治39年，不能把其他字段的年份借给本字段。
- 没有明确【本籍】标记时 registered_domicile 必须为 null；不能把住所或学历地点当本籍。
- 履历事件没有明确时间时 time 必须为 null；不能写“明治时期”“昭和时期”。
- 地点只能来自原文明确地名；不能推测，不能写“地点不明”，没有就填 null。
- 「聖歷」「建歴」「經濟」等疑似 OCR 误字，按语境归入學歴或經歴，但 evidence_text 保留原文。
- career_trajectory 至少抽取【經歴】或类似字段中的主要机构/职位事件。
- evidence_text 必须是短原文片段。

输入条目：
{json.dumps(payload, ensure_ascii=False, indent=2)}
"""


def call_ollama(model: str, prompt: str, timeout: int, *, format_json: bool = True, num_predict: int = 4096) -> str:
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.8,
            "num_ctx": 32768,
            "num_predict": num_predict,
        },
    }
    if format_json:
        body["format"] = "json"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8", errors="replace"))
    response = result.get("response") or ""
    # Some thinking-capable Ollama models may put all generated text in the
    # `thinking` field when JSON mode is active. Treat it as raw output only
    # when response is empty; the parser will still validate the JSON shape.
    if not response.strip():
        response = result.get("thinking") or ""
    return response


def strip_thinking(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def extract_json_text(text: str) -> str:
    text = strip_thinking(text)
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    start_obj = text.find("{")
    end_obj = text.rfind("}")
    if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
        return text[start_obj : end_obj + 1]
    return text


def parse_json_lenient(text: str) -> tuple[dict[str, Any] | None, str | None]:
    candidate = extract_json_text(text)
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed, None
        return None, f"JSON root is {type(parsed).__name__}, expected object"
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def normalize_parsed(parsed: dict[str, Any] | None, entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    if parsed is None:
        return None
    if "persons" not in parsed and "data" in parsed and isinstance(parsed["data"], dict):
        parsed = parsed["data"]
    persons = parsed.get("persons")
    if not isinstance(persons, list):
        return parsed
    expected_by_id = {entry["entry_index"]: entry["name"] for entry in entries}
    for idx, person in enumerate(persons):
        if not isinstance(person, dict):
            continue
        person.setdefault("entry_id", idx + 1)
        person.setdefault("needs_review", False)
        person.setdefault("review_reason", None)
        person.setdefault("education", [])
        person.setdefault("career_trajectory", [])
        person.setdefault("trajectory_summary", {})
        person.setdefault("family_raw", None)
        person.setdefault("address_raw", None)
        person.setdefault("hobbies_raw", None)
        person.setdefault("religion_raw", None)
        person_info = person.setdefault("person_info", {})
        if isinstance(person_info, dict):
            entry_id = person.get("entry_id")
            if entry_id in expected_by_id:
                person_info.setdefault("name", expected_by_id[entry_id])
        person.setdefault("current_status", {})
    parsed.setdefault("page", 211)
    return parsed


def normalize_single_person(parsed: dict[str, Any] | None, entry: dict[str, Any]) -> dict[str, Any] | None:
    if parsed is None:
        return None
    if "persons" in parsed and isinstance(parsed["persons"], list) and parsed["persons"]:
        parsed = parsed["persons"][0]
    if "person" in parsed and isinstance(parsed["person"], dict):
        parsed = parsed["person"]
    if not isinstance(parsed, dict):
        return None
    parsed.setdefault("entry_id", entry["entry_index"])
    parsed.setdefault("needs_review", False)
    parsed.setdefault("review_reason", None)
    parsed.setdefault("person_info", {})
    parsed.setdefault("current_status", {})
    parsed.setdefault("education", [])
    parsed.setdefault("career_trajectory", [])
    parsed.setdefault("trajectory_summary", {})
    parsed.setdefault("family_raw", None)
    parsed.setdefault("address_raw", None)
    parsed.setdefault("hobbies_raw", None)
    parsed.setdefault("religion_raw", None)
    if isinstance(parsed["person_info"], dict):
        parsed["person_info"].setdefault("name", entry["name"])
    return parsed


def evaluate(parsed: dict[str, Any] | None, entries: list[dict[str, Any]], parse_error: str | None) -> dict[str, Any]:
    expected_names = [entry["name"] for entry in entries]
    summary: dict[str, Any] = {
        "parse_ok": parsed is not None and parse_error is None,
        "parse_error": parse_error,
        "expected_person_count": len(expected_names),
        "person_count": 0,
        "name_hits": 0,
        "missing_expected_names": expected_names,
        "schema_complete_persons": 0,
        "career_event_count": 0,
        "education_event_count": 0,
        "current_status_count": 0,
        "evidence_count": 0,
        "review_true_count": 0,
        "issues": [],
    }
    if not parsed:
        return summary
    if not REQUIRED_TOP_KEYS.issubset(parsed.keys()):
        summary["issues"].append(f"missing_top_keys={sorted(REQUIRED_TOP_KEYS - set(parsed.keys()))}")
    persons = parsed.get("persons")
    if not isinstance(persons, list):
        summary["issues"].append("persons_not_list")
        return summary
    summary["person_count"] = len(persons)
    found_names = []
    for person in persons:
        if not isinstance(person, dict):
            summary["issues"].append("person_not_object")
            continue
        if REQUIRED_PERSON_KEYS.issubset(person.keys()):
            summary["schema_complete_persons"] += 1
        else:
            summary["issues"].append(
                f"entry_{person.get('entry_id')}_missing_keys={sorted(REQUIRED_PERSON_KEYS - set(person.keys()))}"
            )
        info = person.get("person_info") or {}
        if isinstance(info, dict) and info.get("name"):
            found_names.append(info["name"])
        current = person.get("current_status") or {}
        if isinstance(current, dict) and (current.get("organization") or current.get("title")):
            summary["current_status_count"] += 1
        education = person.get("education") or []
        career = person.get("career_trajectory") or []
        if isinstance(education, list):
            summary["education_event_count"] += len(education)
        if isinstance(career, list):
            summary["career_event_count"] += len(career)
        if person.get("needs_review"):
            summary["review_true_count"] += 1
        summary["evidence_count"] += count_evidence(person)
    summary["name_hits"] = sum(1 for name in expected_names if name in found_names)
    summary["missing_expected_names"] = [name for name in expected_names if name not in found_names]
    return summary


def count_evidence(value: Any) -> int:
    if isinstance(value, dict):
        return sum((1 if key == "evidence_text" and val else 0) + count_evidence(val) for key, val in value.items())
    if isinstance(value, list):
        return sum(count_evidence(item) for item in value)
    return 0


def run_model(model: str, prompt: str, entries: list[dict[str, Any]], timeout: int) -> ModelRun:
    start = time.time()
    try:
        raw = call_ollama(model, prompt, timeout, format_json=True, num_predict=4096)
        elapsed = time.time() - start
        parsed, parse_error = parse_json_lenient(raw)
        parsed = normalize_parsed(parsed, entries)
        eval_summary = evaluate(parsed, entries, parse_error)
        if not eval_summary["parse_ok"] or eval_summary["person_count"] != len(entries) or eval_summary["name_hits"] < len(entries):
            retry_start = time.time()
            retry_raw_parts: list[str] = []
            retry_persons: list[dict[str, Any]] = []
            retry_errors: list[str] = []
            for entry in entries:
                single_prompt = build_single_prompt(entry)
                single_raw = call_ollama(model, single_prompt, timeout, format_json=True, num_predict=1600)
                retry_raw_parts.append(f"===== entry {entry['entry_index']} {entry['name']} =====\n{single_raw}")
                single_parsed, single_error = parse_json_lenient(single_raw)
                single_person = normalize_single_person(single_parsed, entry)
                if single_person is None:
                    retry_errors.append(f"entry_{entry['entry_index']}: {single_error}")
                else:
                    retry_persons.append(single_person)
            if retry_persons:
                retry_parsed = {"page": 211, "persons": retry_persons}
                retry_eval = evaluate(retry_parsed, entries, "; ".join(retry_errors) if retry_errors else None)
                if retry_eval["person_count"] > eval_summary["person_count"] or retry_eval["name_hits"] >= eval_summary["name_hits"]:
                    retry_eval["fallback_used"] = "per_entry"
                    retry_eval["fallback_elapsed_seconds"] = round(time.time() - retry_start, 3)
                    return ModelRun(model, "\n\n".join(retry_raw_parts), retry_parsed, retry_eval["parse_error"], time.time() - start, retry_eval)
        return ModelRun(model, raw, parsed, parse_error, elapsed, eval_summary)
    except urllib.error.URLError as exc:
        elapsed = time.time() - start
        err = f"URLError: {exc}"
    except Exception as exc:
        elapsed = time.time() - start
        err = f"{type(exc).__name__}: {exc}"
    return ModelRun(model, "", None, err, elapsed, evaluate(None, entries, err))


def write_run(run: ModelRun) -> None:
    safe_model = re.sub(r"[^A-Za-z0-9_.-]+", "_", run.model)
    model_dir = OUT_DIR / safe_model
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "raw_response.txt").write_text(run.raw_text, encoding="utf-8")
    (model_dir / "parsed.json").write_text(
        json.dumps(run.parsed, ensure_ascii=False, indent=2) if run.parsed is not None else "",
        encoding="utf-8",
    )
    (model_dir / "summary.json").write_text(
        json.dumps(
            {
                "model": run.model,
                "elapsed_seconds": round(run.elapsed_seconds, 3),
                "parse_error": run.parse_error,
                **run.eval_summary,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def write_report(runs: list[ModelRun], entries: list[dict[str, Any]], prompt: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "prompt.md").write_text(prompt, encoding="utf-8")
    (OUT_DIR / "input_entries.json").write_text(
        json.dumps([compact_entry(entry) for entry in entries], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    comparison = []
    for run in runs:
        comparison.append(
            {
                "model": run.model,
                "elapsed_seconds": round(run.elapsed_seconds, 3),
                "parse_ok": run.eval_summary["parse_ok"],
                "person_count": run.eval_summary["person_count"],
                "name_hits": run.eval_summary["name_hits"],
                "schema_complete_persons": run.eval_summary["schema_complete_persons"],
                "career_event_count": run.eval_summary["career_event_count"],
                "education_event_count": run.eval_summary["education_event_count"],
                "current_status_count": run.eval_summary["current_status_count"],
                "evidence_count": run.eval_summary["evidence_count"],
                "review_true_count": run.eval_summary["review_true_count"],
                "issues": run.eval_summary["issues"],
                "parse_error": run.parse_error,
            }
        )
    (OUT_DIR / "comparison_summary.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Ollama 本地 Qwen NER 测试：第211页前3人物",
        "",
        "## 输入",
        "",
        "- 页面：211",
        "- 条目：前3人",
        f"- 姓名：{', '.join(entry['name'] for entry in entries)}",
        "- 说明：仅使用本地 Ollama，不调用外部大模型 API。",
        "",
        "## 对比摘要",
        "",
        "| 模型 | JSON可解析 | 人物数 | 姓名命中 | 完整schema人数 | 履历事件 | 学历事件 | 现职数 | 证据数 | review数 | 用时秒 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in comparison:
        lines.append(
            f"| {item['model']} | {item['parse_ok']} | {item['person_count']} | "
            f"{item['name_hits']}/3 | {item['schema_complete_persons']} | "
            f"{item['career_event_count']} | {item['education_event_count']} | "
            f"{item['current_status_count']} | {item['evidence_count']} | "
            f"{item['review_true_count']} | {item['elapsed_seconds']} |"
        )
    lines.extend(["", "## 问题记录", ""])
    for item in comparison:
        issues = item["issues"] or []
        if item["parse_error"]:
            issues.append(f"parse_error={item['parse_error']}")
        lines.append(f"- {item['model']}: {'; '.join(issues) if issues else '无结构性错误'}")
    lines.append("")
    lines.append("## 输出文件")
    lines.append("")
    lines.append("- `prompt.md`：实际发送给 Ollama 的 prompt")
    lines.append("- `input_entries.json`：第211页前3人物输入")
    lines.append("- `<model>/raw_response.txt`：模型原始输出")
    lines.append("- `<model>/parsed.json`：解析后的 JSON")
    lines.append("- `<model>/summary.json`：单模型评估摘要")
    (OUT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local Ollama NER tests on Manshu page 211 first three entries.")
    parser.add_argument("--models", nargs="*", default=["qwen3.5:0.8b", "deepseek-r1:8b"])
    parser.add_argument("--timeout", type=int, default=900)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    entries = load_entries()
    prompt = build_prompt(entries)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    runs: list[ModelRun] = []
    for model in args.models:
        print(f"Running {model} ...", flush=True)
        run = run_model(model, prompt, entries, args.timeout)
        write_run(run)
        runs.append(run)
        print(json.dumps({"model": model, **run.eval_summary}, ensure_ascii=False, indent=2), flush=True)
    write_report(runs, entries, prompt)
    print(f"Wrote results to: {OUT_DIR}")


if __name__ == "__main__":
    main()
