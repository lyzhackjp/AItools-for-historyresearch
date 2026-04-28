import sys, os
sys.path.insert(0, r'C:\Users\lyzha\Desktop\AItools-for-historyresearch')
os.chdir(r'C:\Users\lyzha\Desktop\AItools-for-historyresearch')

from tools.workflow import WorkflowOrchestrator

wf = WorkflowOrchestrator(
    topic="Tudor England",
    language="en",
    bilingual=False,
    citation_format="chicago",
    output_dir="./workflow_output"
)

result = wf.run_all()

print("FINAL SUMMARY:")
print(wf.project.summary())
print(f"\nPaper draft: {len(wf.project.paper_draft)} chars")
print(f"Final paper: {len(wf.project.final_paper)} chars")

os.makedirs("./workflow_output", exist_ok=True)
summary_path = "./workflow_output/run_summary.txt"
with open(summary_path, "w", encoding="utf-8") as f:
    f.write("7-Stage Workflow Run Summary\n")
    f.write("=" * 50 + "\n\n")
    f.write(f"Topic: Tudor England\n")
    f.write(f"Language: en (single language, non-bilingual)\n")
    f.write(f"Citation format: Chicago\n\n")
    f.write(wf.project.summary())
    f.write("\n\n=== Paper Draft (first 3000 chars) ===\n")
    f.write(wf.project.paper_draft[:3000] if wf.project.paper_draft else "N/A")
    if wf.project.final_paper:
        f.write("\n\n=== Final Paper (first 3000 chars) ===\n")
        f.write(wf.project.final_paper[:3000])

print(f"\nSummary saved to {summary_path}")
