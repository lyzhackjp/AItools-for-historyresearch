import json

with open('open_source_finder/storage/reports/openclaw_all_20260401_175938.json', encoding='utf-8') as f:
    data = json.load(f)

print(f"论文数量: {len(data['papers'])}")
print(f"项目数量: {len(data['projects'])}")
