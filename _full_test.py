"""
完整工作流测试脚本（含 API Key + 所有优化）
"""
import os, sys
sys.path.insert(0, r'C:\Users\lyzha\Desktop\AItools-for-historyresearch')
os.chdir(r'C:\Users\lyzha\Desktop\AItools-for-historyresearch')
os.environ.setdefault('DASHSCOPE_API_KEY', 'DASHSCOPE_API_KEY_PLACEHOLDER')

import time
import requests

BASE = os.getenv('MM_BASE_URL', 'http://localhost:8065')
TOKEN = os.getenv('MM_TOKEN', 'MM_TOKEN_PLACEHOLDER')
CHANNEL_ID = os.getenv('MM_CHANNEL_ID', 'MM_CHANNEL_ID_PLACEHOLDER')

def mm_attach(filepath, message):
    """上传附件并发送消息"""
    filename = os.path.basename(filepath)
    ext = filename.rsplit('.', 1)[-1].lower()
    mime = {
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'md': 'text/markdown; charset=utf-8',
        'txt': 'text/plain; charset=utf-8',
    }.get(ext, 'application/octet-stream')

    with open(filepath, 'rb') as f:
        r = requests.post(f'{BASE}/api/v4/files',
                         headers={'Authorization': f'Bearer {TOKEN}'},
                         data={'channel_id': CHANNEL_ID},
                         files={'files': (filename, f, mime)}, timeout=60)
    if r.status_code != 201:
        print(f"  上传失败 {filename}: {r.status_code}")
        return False
    file_id = r.json()['file_infos'][0]['id']
    r2 = requests.post(f'{BASE}/api/v4/posts',
                       headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
                       json={'channel_id': CHANNEL_ID, 'message': message, 'file_ids': [file_id]}, timeout=30)
    print(f"  发送 {filename}: {r2.status_code}")
    return r2.status_code == 201

# ── 测试完整工作流 ──────────────────────────────────────────
print("=" * 60)
print("完整工作流测试 | Tudor England | Stage 1→7")
print("=" * 60)

from tools.workflow import WorkflowOrchestrator

wf = WorkflowOrchestrator(
    topic="Tudor England",
    language="en",
    bilingual=False,
    citation_format="chicago",
    output_dir="./workflow_output"
)

t0 = time.time()
result = wf.run_all()
elapsed = time.time() - t0

print(f"\n完成！耗时 {elapsed:.0f}s")
print(wf.project.summary())

# ── 发送摘要报告 ───────────────────────────────────────────
summary_file = "./workflow_output/final_summary.txt"
with open(summary_file, 'w', encoding='utf-8') as f:
    f.write(f"7-Stage Workflow Full Test Results\n")
    f.write(f"{'='*50}\n\n")
    f.write(f"Topic: Tudor England\n")
    f.write(f"Language: English (single language)\n")
    f.write(f"Citation format: Chicago\n")
    f.write(f"Elapsed time: {elapsed:.0f}s\n\n")
    f.write(wf.project.summary())
    f.write("\n\n=== Stage Results ===\n")
    for stage in range(1, 8):
        status = getattr(wf.project, f'stage{stage}_status').value
        f.write(f"Stage {stage}: {status}\n")
    f.write(f"\n=== Paper Preview (first 3000 chars) ===\n")
    paper = wf.project.final_paper or wf.project.paper_draft
    f.write(paper[:3000] if paper else "N/A")
    f.write(f"\n\n=== Entities ({len(wf.project.entities)}) ===\n")
    for e in wf.project.entities[:10]:
        f.write(f"  [{e.category}] {e.name} (conf: {e.confidence:.2f})\n")

print(f"\n发送附件...")
mm_attach(summary_file, "📊 完整工作流测试结果 | Tudor England Stage 1-7")

# 发送 Word 文档
if os.path.exists("./workflow_output/Tudor_England_final.docx"):
    mm_attach("./workflow_output/Tudor_England_final.docx",
               "📄 论文 Word 文档 | Tudor England")
elif os.path.exists("./workflow_output/final_paper.md"):
    mm_attach("./workflow_output/final_paper.md",
               "📝 论文 Markdown | Tudor England")

# 发送 Obsidian vault 打包（如果有）
vault_dir = "./workflow_output/obsidian_vault"
if os.path.exists(vault_dir):
    import zipfile
    zip_path = "./workflow_output/obsidian_vault.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(vault_dir):
            for file in files:
                fp = os.path.join(root, file)
                zf.write(fp, os.path.relpath(fp, vault_dir))
    mm_attach(zip_path, "📦 Obsidian Vault 笔记库 | Tudor England")

print("\n全部完成！")
