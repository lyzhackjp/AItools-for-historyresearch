"""
NER Resume Script - Continue from page 222
"""
import json
import os
import sys
import re
import csv
import time
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(r'C:\Users\lyzha\Desktop\AItools-for-historyresearch')
sys.path.insert(0, str(BASE_DIR))

API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
API_MODEL = "qwen3.6-plus-2026-04-02"

def load_api_key():
    secrets_file = BASE_DIR / 'secrets' / 'api_keys.txt'
    if secrets_file.exists():
        content = secrets_file.read_text(encoding='utf-8')
        for line in content.split('\n'):
            if 'qwen' in line.lower() and '=' in line:
                key = line.split('=', 1)[1].strip()
                if key and not key.startswith('#'):
                    return key
    return ""

API_KEY = load_api_key()
print(f"API Key loaded: {'Yes' if API_KEY else 'No'}")

OCR_DIR = BASE_DIR / 'ocr_output' / 'full_pages' / 'ocr_new'
OUTPUT_DIR = BASE_DIR / 'ocr_output' / 'full_pages' / 'ner_results_v2'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

NER_PROMPT_TEMPLATE = """你是满洲国人物信息提取专家。从日文履历文本中提取信息，输出JSON格式。

规则：
1. 年号补全：明=明治，大正=大正，昭=昭和，康徳=康徳
2. 地理省略复原："同"开头需还原完整地名
3. 机构简称补全

输出JSON格式（无其他内容）：
{
  "person_info": {
    "name": "姓名",
    "birth_date": "出生日期（明治XX年X月）",
    "registered_domicile": "本籍地"
  },
  "current_status": {
    "title": "现职头衔",
    "organization": "现职机构",
    "responsibilities_details": "具体业务"
  },
  "career_trajectory": [
    {"time": "时间", "organization": "机构", "location": "地点", "mobility_event": "调度性质"}
  ],
  "trajectory_summary": {
    "organization_flow": "机构1 -> 机构2 -> 机构3",
    "location_flow": "地点1 -> 地点2 -> 地点3"
  }
}

文本：{input_text}"""

def call_api(text, max_retries=2):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    prompt = NER_PROMPT_TEMPLATE.replace("{input_text}", text)

    payload = {
        "model": API_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 2000
    }

    for attempt in range(max_retries):
        try:
            import requests
            resp = requests.post(API_URL, headers=headers, json=payload, timeout=180)
            if resp.status_code == 200:
                result = resp.json()
                return {"success": True, "content": result["choices"][0]["message"]["content"]}
            elif resp.status_code == 429:
                time.sleep(30)
            else:
                return {"success": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            time.sleep(5)
            return {"success": False, "error": str(e)}
    return {"success": False, "error": "Max retries"}

def parse_response(content):
    if '"person_info"' in content:
        start = content.find('"person_info"')
        start = content.rfind('{', 0, start)
        brace_count = 0
        end = start
        for i, c in enumerate(content[start:], start):
            if c == '{':
                brace_count += 1
            elif c == '}':
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break
        if brace_count == 0 and start < end:
            try:
                return json.loads(content[start:end])
            except:
                pass
    return None

def extract_person_entries(block_texts):
    full_text = '\n'.join(block_texts)
    lines = full_text.split('\n')
    entries = []
    current = []
    name_pattern = re.compile(r'^([一-龥]{2,4})\s*$')

    for line in lines:
        if name_pattern.match(line) and len(current) > 3:
            entries.append('\n'.join(current))
            current = []
        current.append(line)

    if current:
        entries.append('\n'.join(current))

    return entries

def process_page(page_num):
    print(f"\n=== Page {page_num} ===")

    blocks = []
    for b in range(1, 7):
        block_path = OCR_DIR / f"page_{page_num:04d}_block_{b}.txt"
        if block_path.exists():
            text = block_path.read_text(encoding='utf-8')
            blocks.append(text)

    if not blocks:
        print(f"  No blocks found!")
        return []

    print(f"  Loaded {len(blocks)} blocks, {sum(len(t) for t in blocks)} chars")

    entries = extract_person_entries(blocks)
    print(f"  Detected {len(entries)} entries")

    results = []
    for i, entry in enumerate(entries):
        if len(entry.strip()) < 15:
            continue

        print(f"  [{i+1}/{len(entries)}] Calling API...", end="", flush=True)

        api_result = call_api(entry)

        if api_result["success"]:
            parsed = parse_response(api_result["content"])
            if parsed:
                parsed["_page"] = page_num
                parsed["_entry_idx"] = i
                results.append(parsed)
                print(" OK")
            else:
                print(" Parse failed")
        else:
            print(f" API failed: {api_result.get('error')}")

        time.sleep(1)

    print(f"  Extracted {len(results)} persons")
    return results

def main():
    print("=" * 50)
    print("NER Resume - Pages 222-230")
    print("=" * 50)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    all_results = []

    # Load checkpoint 221 first
    checkpoint_221 = OUTPUT_DIR / "checkpoint_221.json"
    if checkpoint_221.exists():
        data = json.loads(checkpoint_221.read_text(encoding='utf-8'))
        all_results.extend(data.get("persons", []))
        print(f"Loaded {len(data.get('persons', []))} persons from checkpoint_221")

    # Process pages 222-230
    for page_num in range(222, 231):
        # Check if checkpoint exists
        checkpoint_file = OUTPUT_DIR / f"checkpoint_{page_num}.json"
        if checkpoint_file.exists():
            print(f"\n=== Page {page_num} - loading existing checkpoint ===")
            data = json.loads(checkpoint_file.read_text(encoding='utf-8'))
            all_results.extend(data.get("persons", []))
            print(f"  Loaded {len(data.get('persons', []))} persons from checkpoint")
            continue

        results = process_page(page_num)
        all_results.extend(results)

        # Save checkpoint
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump({"page": page_num, "persons": results, "timestamp": timestamp}, f, ensure_ascii=False, indent=2)

    # Save final JSON
    json_file = OUTPUT_DIR / f"final_results_221-230_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    # Save CSV
    csv_file = OUTPUT_DIR / f"final_results_221-230_{timestamp}.csv"
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['姓名', '出生日期', '本籍地', '现职机构', '现职头衔',
                        '机构变迁轨迹', '地理移动轨迹', '现职业务详情', '页码'])

        for person in all_results:
            p_info = person.get("person_info", {})
            curr = person.get("current_status", {})
            traj = person.get("trajectory_summary", {})
            writer.writerow([
                p_info.get("name", ""),
                p_info.get("birth_date", ""),
                p_info.get("registered_domicile", ""),
                curr.get("organization", ""),
                curr.get("title", ""),
                traj.get("organization_flow", ""),
                traj.get("location_flow", ""),
                curr.get("responsibilities_details", ""),
                person.get("_page", "")
            ])

    print("\n" + "=" * 50)
    print(f"DONE! Extracted {len(all_results)} persons")
    print(f"CSV: {csv_file}")
    print(f"JSON: {json_file}")
    print("=" * 50)

    return str(csv_file), str(json_file)

if __name__ == "__main__":
    csv_path, json_path = main()
