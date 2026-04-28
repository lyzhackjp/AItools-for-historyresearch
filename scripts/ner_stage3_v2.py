"""
Stage 3: NER processing for 満洲紳士録 pages 221-230
Uses NER_Prompt_new.md format with qwen3.6-plus-2026-04-02
"""
import json
import os
import sys
import re
import csv
from pathlib import Path
from datetime import datetime
import concurrent.futures
import time

# Add project root to path
BASE_DIR = Path(r'C:\Users\lyzha\Desktop\AItools-for-historyresearch')
sys.path.insert(0, str(BASE_DIR))

# API Configuration
API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
API_MODEL = "qwen3.6-plus-2026-04-02"

# Load API key from secrets file
def load_api_key():
    secrets_file = BASE_DIR / 'secrets' / 'api_keys.txt'
    if secrets_file.exists():
        content = secrets_file.read_text(encoding='utf-8')
        for line in content.split('\n'):
            if 'qwen' in line.lower() and '=' in line:
                key = line.split('=', 1)[1].strip()
                if key and not key.startswith('#'):
                    return key
    return os.environ.get("DASHSCOPE_API_KEY", "")

API_KEY = load_api_key()

# Paths
OCR_DIR = BASE_DIR / 'ocr_output' / 'full_pages' / 'ocr_new'
OUTPUT_DIR = BASE_DIR / 'ocr_output' / 'full_pages' / 'ner_results_v2'
PROMPT_FILE = Path(r'C:\Users\lyzha\.openclaw\media\inbound\NER_Prompt_new---c5e98d9d-b084-4df5-af0d-7d23a565b6cf')

# Page range
START_PAGE = 221
END_PAGE = 230

# NER Prompt template
NER_PROMPT = """# Role
你是一个精通近代中日关系史、满洲国历史以及日文历史文献处理的数字人文专家。你的任务是对近代日本出版的人事兴信录/绅士录文本进行命名实体识别（NER）与结构化信息提取，并最终输出适用于数据库管理的 JSON 和 CSV 格式。

# Task
请阅读提供的日文履历文本，提取实体信息，还原其工作单位与地理位置的时空序列，并生成直观的变迁轨迹字符串。最终结果需包含一份 JSON 数据和一份 CSV 数据。

# Extraction Rules (Crucial)
1. 年号补全：将"明、大、昭"等缩写在提取时补全为标准格式（如：明二九・一 -> 明治29年1月）。
2. 地理省略复原：遇到"同糠野目村"中的"同"字，请根据前文语境还原完整的行政区划。
3. 机构简称识别：遇到常见简称，提供全称（如：早大 -> 早稻田大学）。
4. **现职提取**：【經歷】末尾由"現職に就き..."引出的内容为【具体业务范围/管辖说明】，必须完整提取。
5. **职业轨迹与空间调动**：
   - 按严格的**时间顺序（Chronological Order）**切分【經歷】。
   - 必须拆解出具体的"工作单位（机构）"和"工作地点（精确到城市）"。
6. **变迁轨迹生成（Trajectory Generation）**：
   - 基于提取的职业轨迹，生成直观的字符串流。
   - `organization_flow`：使用 " -> " 连接任职过的机构（例如：帝國製麻 -> 奉天製麻 -> 大同土地株)。
   - `location_flow`：使用 " -> " 连接工作过的地点（例如：滋賀縣大津 -> 奉天）。

# 1. JSON Output Schema
请先输出以下 JSON 格式（如某字段未提及填入 null）：

{
  "person_info": {
    "name": "姓名",
    "birth_date": "出生日期",
    "registered_domicile": "本籍地"
  },
  "current_status": {
    "title": "现职头衔",
    "organization": "现职机构",
    "responsibilities_details": "现职具体负责的业务范围或管辖区域（保留原文）"
  },
  "career_trajectory": [
    {
      "time": "时间",
      "organization": "机构",
      "location": "地点",
      "mobility_event": "调度性质（如入社、轉勤、渡滿）"
    }
  ],
  "trajectory_summary": {
    "organization_flow": "机构变迁轨迹字符串",
    "location_flow": "地理移动轨迹字符串"
  }
}

# 2. CSV Output Format
在 JSON 之后，请提供一段符合标准 CSV 格式的纯文本，使用英文逗号分隔。表头定义如下：
姓名,出生日期,本籍地,现职机构,现职头衔,机构变迁轨迹,地理移动轨迹,现职业务详情

# Input Text
{input_text}

# Output Instruction
1. 先输出 JSON 数据，使用 ```json 块包裹。
2. 然后输出 CSV 数据，使用 ```csv 块包裹。
3. 不要输出任何其他的解释性或引导性文本。"""


def call_qwen_api(text: str, max_retries: int = 3) -> dict:
    """Call Qwen API for NER extraction."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # Replace placeholder in prompt
    prompt_content = NER_PROMPT.replace("{input_text}", text)

    payload = {
        "model": API_MODEL,
        "messages": [
            {"role": "user", "content": prompt_content}
        ],
        "temperature": 0.1,
        "max_tokens": 4000
    }

    for attempt in range(max_retries):
        try:
            import requests
            response = requests.post(API_URL, headers=headers, json=payload, timeout=300)

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "content": result["choices"][0]["message"]["content"],
                    "usage": result.get("usage", {})
                }
            elif response.status_code == 400:
                return {"success": False, "error": "Bad request - possibly rate limited"}
            elif response.status_code == 429:
                wait_time = (attempt + 1) * 30
                print(f"  Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            print(f"  API error: {e}")
            time.sleep(5)

    return {"success": False, "error": "Max retries exceeded"}


def parse_ner_response(response_text: str) -> dict:
    """Parse JSON and CSV from NER response."""
    result = {
        "json_data": None,
        "csv_data": None,
        "raw_response": response_text
    }

    # Extract JSON
    json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if json_match:
        try:
            result["json_data"] = json.loads(json_match.group(1))
        except json.JSONDecodeError as e:
            print(f"  JSON parse error: {e}")

    # Extract CSV
    csv_match = re.search(r'```csv\s*(.*?)\s*```', response_text, re.DOTALL)
    if csv_match:
        result["csv_data"] = csv_match.group(1).strip()

    return result


def split_into_person_entries(block_text: str) -> list:
    """
    Split block text into individual person entries.
    Each person entry starts with a name pattern and continues until the next name.
    """
    # Pattern: Name appears at the start of a line or after 【 markers
    # Names are typically 2-4 kanji characters
    lines = block_text.split('\n')

    entries = []
    current_entry = []

    for line in lines:
        # Check if line starts with a name (2-4 kanji at beginning)
        name_match = re.match(r'^([一-龥]{2,4})\s*$', line)
        if name_match and len(current_entry) > 0:
            # Save previous entry
            entries.append('\n'.join(current_entry))
            current_entry = [line]
        else:
            current_entry.append(line)

    # Don't forget the last entry
    if current_entry:
        entries.append('\n'.join(current_entry))

    return entries


def process_page(page_num: int, output_dir: Path) -> dict:
    """Process all blocks for a single page."""
    page_results = {
        "page": page_num,
        "persons": [],
        "errors": 0
    }

    # Collect all block texts in order (block_1 to block_6)
    all_texts = []
    for block_num in range(1, 7):
        block_path = OCR_DIR / f"page_{page_num:04d}_block_{block_num}.txt"
        if block_path.exists():
            text = block_path.read_text(encoding='utf-8')
            all_texts.append(f"<block_{block_num}>\n{text}\n</block_{block_num}>")

    # Combine all blocks
    full_text = "\n".join(all_texts)
    print(f"  Page {page_num}: {len(full_text)} chars across {len(all_texts)} blocks")

    # Split into individual person entries
    # Simple heuristic: each entry starts with a name (2+ kanji characters)
    lines = full_text.split('\n')
    person_texts = []
    current_person = []

    name_pattern = re.compile(r'^([一-龥]{2,4})[\s【\n]')

    for line in lines:
        # Check if this line starts with a potential name
        if name_pattern.match(line) and len(current_person) > 5:
            # Save previous person
            person_texts.append('\n'.join(current_person))
            current_person = []
        current_person.append(line)

    if current_person:
        person_texts.append('\n'.join(current_person))

    print(f"  Detected ~{len(person_texts)} person entries")

    # Process each person
    for i, person_text in enumerate(person_texts):
        if len(person_text.strip()) < 20:  # Skip very short entries
            continue

        print(f"  Processing person {i+1}/{len(person_texts)}...")

        # Call NER API
        api_result = call_qwen_api(person_text)

        if api_result["success"]:
            parsed = parse_ner_response(api_result["content"])
            if parsed["json_data"]:
                parsed["json_data"]["_page"] = page_num
                parsed["json_data"]["_block_index"] = i
                page_results["persons"].append(parsed["json_data"])
            else:
                page_results["errors"] += 1
        else:
            print(f"    API error: {api_result.get('error')}")
            page_results["errors"] += 1

    return page_results


def main():
    print("=" * 60)
    print("満洲紳士録 NER - qwen3.6-plus-2026-04-02 (NER_Prompt_new)")
    print(f"Pages: {START_PAGE}-{END_PAGE}")
    print("=" * 60)

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_results = []
    total_persons = 0
    total_errors = 0

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Process each page
    for page_num in range(START_PAGE, END_PAGE + 1):
        print(f"\n[{page_num}/{END_PAGE}]")
        page_result = process_page(page_num, OUTPUT_DIR)
        all_results.append(page_result)
        total_persons += len(page_result["persons"])
        total_errors += page_result["errors"]

    # Save JSON results
    json_output = OUTPUT_DIR / f"ner_results_pages{START_PAGE}-{END_PAGE}_{timestamp}.json"
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    # Generate CSV
    csv_output = OUTPUT_DIR / f"ner_results_pages{START_PAGE}-{END_PAGE}_{timestamp}.csv"

    with open(csv_output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            '姓名', '出生日期', '本籍地', '现职机构', '现职头衔',
            '机构变迁轨迹', '地理移动轨迹', '现职业务详情', '页码'
        ])

        for page_result in all_results:
            for person in page_result.get("persons", []):
                person_info = person.get("person_info", {})
                current = person.get("current_status", {})
                trajectory = person.get("trajectory_summary", {})

                writer.writerow([
                    person_info.get("name", ""),
                    person_info.get("birth_date", ""),
                    person_info.get("registered_domicile", ""),
                    current.get("organization", ""),
                    current.get("title", ""),
                    trajectory.get("organization_flow", ""),
                    trajectory.get("location_flow", ""),
                    current.get("responsibilities_details", ""),
                    page_result.get("page", "")
                ])

    print("\n" + "=" * 60)
    print(f"--- Complete ---")
    print(f"  Total persons extracted: {total_persons}")
    print(f"  Total errors: {total_errors}")
    print(f"  JSON: {json_output}")
    print(f"  CSV: {csv_output}")
    print("=" * 60)

    return {
        "total_persons": total_persons,
        "total_errors": total_errors,
        "csv_path": str(csv_output),
        "json_path": str(json_output)
    }


if __name__ == "__main__":
    result = main()
