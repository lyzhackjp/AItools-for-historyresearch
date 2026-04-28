from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
ENTRIES_JSON = (
    ROOT
    / "ocr_output"
    / "manshu_full_pipeline_211_215_resplit"
    / "pages"
    / "page_0211_entries.json"
)
OUT_DIR = ROOT / "ocr_output" / "qwen_api_model_ner_page211_first3"
MODELS_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/models"
CHAT_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

EXCLUDED_MODELS = {
    "qwen3.6-plus",
    "qwen3.6-plus-2026-04-02",
}

# Canonical text-generation candidates for this NER task. Date snapshots,
# image/audio/TTS/embedding/realtime/deep-research/translation/coder-only
# variants are intentionally excluded unless they are the current stable text
# alias or a notable open/general model.
CANDIDATE_MODELS = [
    "qwen3.6-35b-a3b",
    "qwen3.6-flash",
    "qwen3.5-plus",
    "qwen3.5-flash",
    "qwen3.5-397b-a17b",
    "qwen3.5-122b-a10b",
    "qwen3.5-35b-a3b",
    "qwen3.5-27b",
    "qwen3-max",
    "qwen-max",
    "qwen-plus",
    "qwen-flash",
    "qwen-turbo",
    "qwen-long",
    "qwen3-next-80b-a3b-instruct",
    "qwen3-235b-a22b-instruct-2507",
    "qwen3-235b-a22b",
    "qwen3-32b",
    "qwen3-30b-a3b-instruct-2507",
    "qwen3-30b-a3b",
    "qwen3-14b",
    "qwen3-8b",
    "qwen3-4b",
    "qwen2.5-72b-instruct",
    "qwen2.5-32b-instruct",
    "qwen2.5-14b-instruct",
    "qwen2.5-14b-instruct-1m",
    "qwen2.5-7b-instruct",
    "qwen2.5-7b-instruct-1m",
    "qwen2.5-3b-instruct",
    "qwen2.5-1.5b-instruct",
    "qwen2.5-0.5b-instruct",
    "qwen2-57b-a14b-instruct",
    "qwen1.5-110b-chat",
    "qwen1.5-72b-chat",
    "qwen1.5-32b-chat",
    "qwen1.5-14b-chat",
    "qwen1.5-7b-chat",
]

# Prices are RMB / million tokens for the low-token tier in the official model
# list as of 2026-04-17. This script calls dashscope.aliyuncs.com, so prices
# here follow the China mainland endpoint where documented. Unknown/new aliases
# are left out and reported as null.
PRICE_RMB_PER_MTOK = {
    "qwen3-max": {"input": 2.5, "output": 10.0},
    "qwen-max": {"input": 2.4, "output": 9.6},
    "qwen3.5-plus": {"input": 0.8, "output": 4.8},
    "qwen-plus": {"input": 0.8, "output": 2.0},
    "qwen3.5-flash": {"input": 0.2, "output": 2.0},
    "qwen-flash": {"input": 0.15, "output": 1.5},
    "qwen3.5-397b-a17b": {"input": 1.2, "output": 7.2},
    "qwen3.5-122b-a10b": {"input": 0.8, "output": 6.4},
    "qwen3.5-27b": {"input": 0.6, "output": 4.8},
    "qwen3.5-35b-a3b": {"input": 0.4, "output": 3.2},
    "qwen3-next-80b-a3b-instruct": {"input": 1.0, "output": 4.0},
    "qwen3-235b-a22b-instruct-2507": {"input": 2.0, "output": 8.0},
    "qwen3-235b-a22b": {"input": 2.0, "output": 8.0},
    "qwen3-32b": {"input": 2.0, "output": 8.0},
    "qwen3-30b-a3b-instruct-2507": {"input": 0.75, "output": 3.0},
    "qwen3-30b-a3b": {"input": 0.75, "output": 3.0},
    "qwen3-14b": {"input": 1.0, "output": 4.0},
    "qwen3-8b": {"input": 0.5, "output": 2.0},
    "qwen3-4b": {"input": 0.3, "output": 1.2},
}

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
class RunResult:
    model: str
    ok: bool
    raw_text: str
    parsed: dict[str, Any] | None
    error: str | None
    elapsed_seconds: float
    usage: dict[str, Any]
    eval_summary: dict[str, Any]


def load_api_key() -> str:
    candidates = [
        ROOT / "secret" / "api_key.txt",
        ROOT / "secrets" / "api_key.txt",
        ROOT / "secrets" / "api_keys.txt",
    ]
    for path in candidates:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue
        if "\n" not in text and len(text) > 20 and " " not in text:
            return text.strip()
        priority_hits: list[str] = []
        fallback_hits: list[str] = []
        for line in [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]:
            if "=" in line:
                key_name, value = line.split("=", 1)
                key_name = key_name.strip().lower()
                value = value.strip().strip("'").strip('"')
                if not value:
                    continue
                if "qwen" in key_name or "dashscope" in key_name:
                    priority_hits.append(value)
                elif "api" in key_name or "key" in key_name:
                    fallback_hits.append(value)
            elif len(line) > 20:
                fallback_hits.append(line)
        if priority_hits:
            return priority_hits[0]
        if fallback_hits:
            return fallback_hits[0]
    return os.environ.get("DASHSCOPE_API_KEY", "").strip()


def headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def fetch_model_ids(api_key: str) -> list[str]:
    response = requests.get(MODELS_URL, headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
    response.raise_for_status()
    return [item["id"] for item in response.json().get("data", []) if isinstance(item, dict) and item.get("id")]


def select_candidates(model_ids: list[str]) -> list[str]:
    available = set(model_ids)
    return [model for model in CANDIDATE_MODELS if model in available and model not in EXCLUDED_MODELS]


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
    payload = {"page": 211, "entries": [compact_entry(entry) for entry in entries]}
    return f"""
你是一个精通近代中日关系史、满洲国史料和日文历史文献的人物资料 NER 专家。

任务：对《满洲紳士録》第211页的前3个人物条目进行结构化信息抽取。只根据输入文本抽取，不要编造，不要补充外部知识。

关键规则：
1. 每个输入条目必须输出且只能输出 1 个 person，共 3 个 persons。
2. 年号只能根据原文明确数字补全：明三九=明治39年，明三二=明治32年，昭十三=昭和13年。证据片段中没有时间就填 null，严禁写“明治时期”“昭和时期”等泛化时间。
3. “同上”等省略只可在同一条目内根据上文复原；不能复原则保留原文并说明。没有【本籍】标记时 registered_domicile 必须为 null。
4. 姓名前后的现职、机构、职务必须提取；【經歴】、【建歴】、【聖歴】等 OCR 误写的类似字段必须按语境拆入 education 或 career_trajectory。
5. 所有 evidence_text 必须是输入中的短原文片段，不能整段粘贴。
6. OCR 字段名明显误识，例如「聖應」「建歴」「續柄」等，如果语境上是学历或履历，请在结构化字段中归入合理字段，同时在 evidence_text 保留原文。
7. 如果字段缺失或 OCR 可疑，needs_review=true 并简短说明；否则 false。
8. 严禁推测：不要写“地点不明 -> 满洲(新京)”这类推测；没有明确地点就填 null。
9. 严禁跨人物条目串项。每个 person 只能使用对应 entry_id 的文本。

严格输出要求：只输出一个合法 JSON 对象，不要 Markdown，不要代码块，不要解释。JSON 顶层格式如下：
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
          "mobility_event": "入社/就任/历任/勤務等或 null",
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
""".strip()


def call_chat(api_key: str, model: str, prompt: str, max_tokens: int, timeout: int) -> tuple[str, dict[str, Any]]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "top_p": 0.8,
        "max_tokens": max_tokens,
        "enable_thinking": False,
    }
    response = requests.post(CHAT_URL, headers=headers(api_key), json=payload, timeout=timeout)
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:1000]}")
    data = response.json()
    message = data["choices"][0]["message"]
    content = message.get("content") or ""
    if not content and message.get("reasoning_content"):
        content = message["reasoning_content"]
    return content, data.get("usage", {})


def canary_model(api_key: str, model: str, timeout: int) -> dict[str, Any]:
    start = time.time()
    try:
        content, usage = call_chat(
            api_key,
            model,
            '只输出 {"ok":true}，不要解释。',
            max_tokens=32,
            timeout=timeout,
        )
        return {
            "model": model,
            "available": True,
            "elapsed_seconds": round(time.time() - start, 3),
            "content": content[:200],
            "usage": usage,
            "error": None,
        }
    except Exception as exc:
        return {
            "model": model,
            "available": False,
            "elapsed_seconds": round(time.time() - start, 3),
            "content": "",
            "usage": {},
            "error": f"{type(exc).__name__}: {exc}",
        }


def strip_thinking(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()


def extract_json_text(text: str) -> str:
    text = strip_thinking(text)
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def parse_json_lenient(text: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(extract_json_text(text))
        if isinstance(value, dict):
            return value, None
        return None, f"JSON root is {type(value).__name__}, expected object"
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def normalize_parsed(parsed: dict[str, Any] | None, entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    if parsed is None:
        return None
    if "persons" not in parsed and "data" in parsed and isinstance(parsed["data"], dict):
        parsed = parsed["data"]
    persons = parsed.get("persons")
    if isinstance(persons, list):
        expected_by_id = {entry["entry_index"]: entry["name"] for entry in entries}
        for index, person in enumerate(persons):
            if not isinstance(person, dict):
                continue
            person.setdefault("entry_id", index + 1)
            person.setdefault("needs_review", False)
            person.setdefault("review_reason", None)
            person.setdefault("person_info", {})
            person.setdefault("current_status", {})
            person.setdefault("education", [])
            person.setdefault("career_trajectory", [])
            person.setdefault("trajectory_summary", {})
            person.setdefault("family_raw", None)
            person.setdefault("address_raw", None)
            person.setdefault("hobbies_raw", None)
            person.setdefault("religion_raw", None)
            if isinstance(person["person_info"], dict) and person.get("entry_id") in expected_by_id:
                person["person_info"].setdefault("name", expected_by_id[person["entry_id"]])
    parsed.setdefault("page", 211)
    return parsed


def count_evidence(value: Any) -> int:
    if isinstance(value, dict):
        return sum((1 if key == "evidence_text" and val else 0) + count_evidence(val) for key, val in value.items())
    if isinstance(value, list):
        return sum(count_evidence(item) for item in value)
    return 0


def strings_in_value(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(strings_in_value(v) for v in value.values())
    if isinstance(value, list):
        return "\n".join(strings_in_value(v) for v in value)
    if value is None:
        return ""
    return str(value)


def evaluate(parsed: dict[str, Any] | None, entries: list[dict[str, Any]], parse_error: str | None) -> dict[str, Any]:
    expected_names = [entry["name"] for entry in entries]
    entry_text_by_id = {entry["entry_index"]: entry["normalized_text"] for entry in entries}
    summary: dict[str, Any] = {
        "parse_ok": parsed is not None and parse_error is None,
        "parse_error": parse_error,
        "person_count": 0,
        "name_hits": 0,
        "schema_complete_persons": 0,
        "career_event_count": 0,
        "education_event_count": 0,
        "current_status_count": 0,
        "evidence_count": 0,
        "review_true_count": 0,
        "quality_score": 100,
        "quality_flags": [],
    }
    if parsed is None:
        summary["quality_score"] = 0
        return summary
    if not REQUIRED_TOP_KEYS.issubset(parsed.keys()):
        missing = sorted(REQUIRED_TOP_KEYS - set(parsed.keys()))
        summary["quality_flags"].append(f"missing_top_keys={missing}")
        summary["quality_score"] -= 20
    persons = parsed.get("persons")
    if not isinstance(persons, list):
        summary["quality_flags"].append("persons_not_list")
        summary["quality_score"] = 0
        return summary
    summary["person_count"] = len(persons)
    if len(persons) != len(entries):
        summary["quality_flags"].append(f"wrong_person_count={len(persons)}")
        summary["quality_score"] -= 35

    found_names: list[str] = []
    cross_tokens = {
        1: ["久保義雄", "稻田文治", "廣島高師", "大阪高工", "藤田經營", "小坂鑛山", "久原鑛業"],
        2: ["森常太郎", "稻田文治", "京都府山城", "延吉神社", "大阪高工", "藤田經營", "小坂鑛山", "久原鑛業", "滿洲鑛山設立"],
        3: ["森常太郎", "久保義雄", "滿鮮印刷", "新東炭礦", "亮兵臺農場", "延吉神社", "廣島高師", "京大文學部", "港灣協會"],
    }
    birth_year_tokens = {
        1: ["明治25", "明治二五", "明二五", "明25"],
        2: ["明治19", "明治一九", "明一九", "明19"],
        3: ["明治17", "明治一七", "明一七", "明17"],
    }
    for person in persons:
        if not isinstance(person, dict):
            summary["quality_flags"].append("person_not_object")
            summary["quality_score"] -= 20
            continue
        entry_id = person.get("entry_id")
        if REQUIRED_PERSON_KEYS.issubset(person.keys()):
            summary["schema_complete_persons"] += 1
        else:
            missing = sorted(REQUIRED_PERSON_KEYS - set(person.keys()))
            summary["quality_flags"].append(f"entry_{entry_id}_missing_keys={missing}")
            summary["quality_score"] -= 10

        person_text = strings_in_value(person)
        for token in cross_tokens.get(entry_id, []):
            if token in person_text:
                summary["quality_flags"].append(f"entry_{entry_id}_cross_token={token}")
                summary["quality_score"] -= 15
                break

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
            for event in career:
                if not isinstance(event, dict):
                    continue
                event_time = str(event.get("time") or "")
                evidence = str(event.get("evidence_text") or "")
                for token in birth_year_tokens.get(entry_id, []):
                    if token and token in event_time and token not in evidence:
                        summary["quality_flags"].append(f"entry_{entry_id}_suspect_birth_year_as_career_time={event_time}")
                        summary["quality_score"] -= 5
                        break
                location = event.get("location")
                if location and location != "null" and isinstance(location, str):
                    source_text = entry_text_by_id.get(entry_id, "")
                    if location not in source_text and location not in evidence:
                        summary["quality_flags"].append(f"entry_{entry_id}_location_not_in_source={location}")
                        summary["quality_score"] -= 3
                if len(evidence) > 90:
                    summary["quality_flags"].append(f"entry_{entry_id}_long_evidence")
                    summary["quality_score"] -= 2
        if person.get("needs_review"):
            summary["review_true_count"] += 1
        summary["evidence_count"] += count_evidence(person)

    summary["name_hits"] = sum(1 for name in expected_names if name in found_names)
    if summary["name_hits"] != len(expected_names):
        summary["quality_score"] -= 25
    if summary["education_event_count"] < 3:
        summary["quality_flags"].append("education_missing_or_underextracted")
        summary["quality_score"] -= (3 - summary["education_event_count"]) * 5
    if summary["current_status_count"] < 3:
        summary["quality_flags"].append("current_status_missing_or_underextracted")
        summary["quality_score"] -= (3 - summary["current_status_count"]) * 5
    if summary["career_event_count"] < 6:
        summary["quality_flags"].append("career_underextracted")
        summary["quality_score"] -= (6 - summary["career_event_count"]) * 4
    if summary["evidence_count"] < 9:
        summary["quality_flags"].append("evidence_underprovided")
        summary["quality_score"] -= (9 - summary["evidence_count"]) * 2
    summary["quality_score"] = max(0, min(100, int(round(summary["quality_score"]))))
    return summary


def estimate_cost(model: str, usage: dict[str, Any]) -> dict[str, Any]:
    prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
    completion_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or 0
    price = PRICE_RMB_PER_MTOK.get(model)
    if not price:
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": usage.get("total_tokens") or prompt_tokens + completion_tokens,
            "price_known": False,
            "estimated_rmb": None,
        }
    estimated = (prompt_tokens / 1_000_000 * price["input"]) + (
        completion_tokens / 1_000_000 * price["output"]
    )
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": usage.get("total_tokens") or prompt_tokens + completion_tokens,
        "price_known": True,
        "input_rmb_per_mtok": price["input"],
        "output_rmb_per_mtok": price["output"],
        "estimated_rmb": round(estimated, 6),
    }


def safe_model_name(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", model)


def run_model(api_key: str, model: str, prompt: str, entries: list[dict[str, Any]], timeout: int) -> RunResult:
    start = time.time()
    try:
        raw_text, usage = call_chat(api_key, model, prompt, max_tokens=4096, timeout=timeout)
        parsed, parse_error = parse_json_lenient(raw_text)
        parsed = normalize_parsed(parsed, entries)
        eval_summary = evaluate(parsed, entries, parse_error)
        eval_summary["cost"] = estimate_cost(model, usage)
        return RunResult(
            model=model,
            ok=parse_error is None,
            raw_text=raw_text,
            parsed=parsed,
            error=parse_error,
            elapsed_seconds=time.time() - start,
            usage=usage,
            eval_summary=eval_summary,
        )
    except Exception as exc:
        elapsed = time.time() - start
        err = f"{type(exc).__name__}: {exc}"
        eval_summary = evaluate(None, entries, err)
        eval_summary["cost"] = estimate_cost(model, {})
        return RunResult(model, False, "", None, err, elapsed, {}, eval_summary)


def write_model_run(run: RunResult) -> None:
    model_dir = OUT_DIR / safe_model_name(run.model)
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "raw_response.txt").write_text(run.raw_text, encoding="utf-8")
    (model_dir / "parsed.json").write_text(
        json.dumps(run.parsed, ensure_ascii=False, indent=2) if run.parsed is not None else "",
        encoding="utf-8",
    )
    summary = {
        "model": run.model,
        "ok": run.ok,
        "elapsed_seconds": round(run.elapsed_seconds, 3),
        "error": run.error,
        "usage": run.usage,
        **run.eval_summary,
    }
    (model_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def write_reports(canary_results: list[dict[str, Any]], runs: list[RunResult], selected_models: list[str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    comparison: list[dict[str, Any]] = []
    for run in runs:
        cost = run.eval_summary.get("cost", {})
        estimated_rmb = cost.get("estimated_rmb")
        score = run.eval_summary.get("quality_score", 0)
        score_per_fen = None
        if estimated_rmb and estimated_rmb > 0:
            score_per_fen = round(score / (estimated_rmb * 100), 3)
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
                "quality_score": score,
                "quality_flags": run.eval_summary["quality_flags"],
                "prompt_tokens": cost.get("prompt_tokens"),
                "completion_tokens": cost.get("completion_tokens"),
                "estimated_rmb": estimated_rmb,
                "score_per_fen": score_per_fen,
                "price_known": cost.get("price_known"),
                "error": run.error,
            }
        )
    comparison.sort(key=lambda item: (item["quality_score"], item["score_per_fen"] or -1), reverse=True)
    (OUT_DIR / "canary_results.json").write_text(json.dumps(canary_results, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "selected_models.json").write_text(json.dumps(selected_models, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "comparison_summary.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# DashScope Qwen API NER 横评：第211页前三个人物",
        "",
        "## 范围",
        "",
        "- 输入：第211页前三个人物，森常太郎、久保義雄、稻田文治。",
        "- 排除：`qwen3.6-plus` 与 `qwen3.6-plus-2026-04-02`。",
        "- 筛选：仅测试适合文本 NER 的 Qwen chat/text-generation 候选模型；不含图像、ASR、TTS、embedding、realtime、deep-research、翻译、纯 coder 等模型。",
        "- 方式：先 canary 检查可调用/额度，再对可调用模型跑同一 NER prompt。",
        "",
        "## 模型结果",
        "",
        "| 模型 | 质量分 | JSON | 人物 | 姓名 | 履历 | 学历 | 现职 | evidence | 用时秒 | 估算元 | 分/分钱 | 主要问题 |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in comparison:
        flags = "; ".join(item["quality_flags"][:3])
        if len(item["quality_flags"]) > 3:
            flags += f"; +{len(item['quality_flags']) - 3} more"
        lines.append(
            f"| `{item['model']}` | {item['quality_score']} | {item['parse_ok']} | "
            f"{item['person_count']} | {item['name_hits']}/3 | {item['career_event_count']} | "
            f"{item['education_event_count']} | {item['current_status_count']} | {item['evidence_count']} | "
            f"{item['elapsed_seconds']} | {item['estimated_rmb'] if item['estimated_rmb'] is not None else '未知'} | "
            f"{item['score_per_fen'] if item['score_per_fen'] is not None else '未知'} | {flags or '无明显结构问题'} |"
        )
    lines.extend(
        [
            "",
            "## 文件",
            "",
            "- `canary_results.json`：每个候选模型的极小请求可用性检查。",
            "- `comparison_summary.json`：正式 NER 横评汇总。",
            "- `<model>/raw_response.txt`：模型原始响应。",
            "- `<model>/parsed.json`：解析后的 JSON。",
            "- `<model>/summary.json`：单模型指标、用量、估算成本。",
        ]
    )
    (OUT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test non-qwen3.6-plus Qwen API models on page 211 first 3 entries.")
    parser.add_argument("--models", nargs="*", default=None, help="Optional explicit model list.")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--sleep-seconds", type=float, default=0.8)
    parser.add_argument("--skip-canary", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    api_key = load_api_key()
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY not found in env or secrets files.")
    entries = load_entries()
    prompt = build_prompt(entries)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "prompt.md").write_text(prompt, encoding="utf-8")
    (OUT_DIR / "input_entries.json").write_text(
        json.dumps([compact_entry(entry) for entry in entries], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    model_ids = fetch_model_ids(api_key)
    all_candidates = args.models or select_candidates(model_ids)
    selected_models = [model for model in all_candidates if model not in EXCLUDED_MODELS]
    print(f"Selected candidates: {len(selected_models)}", flush=True)

    canary_results: list[dict[str, Any]] = []
    if args.skip_canary:
        available_models = selected_models
    else:
        available_models = []
        for model in selected_models:
            print(f"Canary {model} ...", flush=True)
            result = canary_model(api_key, model, args.timeout)
            canary_results.append(result)
            if result["available"]:
                available_models.append(model)
            else:
                print(f"  unavailable: {result['error']}", flush=True)
            time.sleep(args.sleep_seconds)
    print(f"Available after canary: {len(available_models)}", flush=True)

    runs: list[RunResult] = []
    for model in available_models:
        print(f"Running NER {model} ...", flush=True)
        run = run_model(api_key, model, prompt, entries, args.timeout)
        write_model_run(run)
        runs.append(run)
        print(
            json.dumps(
                {
                    "model": model,
                    "quality_score": run.eval_summary.get("quality_score"),
                    "parse_ok": run.eval_summary.get("parse_ok"),
                    "error": run.error,
                    "cost": run.eval_summary.get("cost"),
                    "flags": run.eval_summary.get("quality_flags", [])[:5],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        time.sleep(args.sleep_seconds)
    write_reports(canary_results, runs, selected_models)
    print(f"Wrote results to: {OUT_DIR}")


if __name__ == "__main__":
    main()
