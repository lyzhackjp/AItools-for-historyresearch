# History Research AI

Language: [中文](README.md) | English | [日本語](README.ja-JP.md)

A local-first AI workbench for Japanese history, Japanese-language sources, and scholarly writing. It brings OCR, NER, source criticism, scholarly notes, citation checks, writing, and observable agent automation into one reviewable UI.

## Current Release

`v1.1.0` integrates the backend, React frontend, and Windows installer.

Download the latest installer: [GitHub Releases](https://github.com/lyzhackjp/AItools-for-historyresearch/releases/latest)

## What It Does

| Area | Description |
| --- | --- |
| Source ingestion | Extract text, layout, and entities from PDFs, images, and Japanese-language sources. |
| Notes and knowledge base | Organize scholarly notes, Obsidian vault output, citation records, and review queues. |
| Seven-stage research workflow | Move from collection, organization, extraction, and examination to writing, polishing, and final formatting. |
| Reviewable AI | Use local models or remote APIs while keeping redacted status, quality flags, and human review points. |

## UI Modes

| UI | Best for |
| --- | --- |
| Manual classic mode | Fine-grained control over OCR, NER, citation checks, providers, backends, and output locations. |
| AI agent solo mode | Letting the agent propose a plan, call authorized tasks, and return high-risk steps for human confirmation. |
| Seven-stage workflow | Running a historical research project while registering checkpoints and artifacts in the task center. |
| Task center | Watching long-running task progress, logs, artifacts, quality flags, and needs_review items. |
| Free workflow builder | Combining module catalog capabilities into a custom research workflow. |

## Quick Install

1. Open [Releases](https://github.com/lyzhackjp/AItools-for-historyresearch/releases/latest) and download `HistoryResearchAI-Setup-1.1.0.exe`.
2. Run the installer.
3. Start `History Research AI` from the Start menu or desktop shortcut.
4. First launch creates `.runtime\venv`, installs Python dependencies, and opens `http://127.0.0.1:5000/`.

If Python is missing, install Python 3.11 and enable `Add Python to PATH`.

To stop the local service, use `Stop History Research AI` from the Start menu or run `scripts\windows\Stop-HistoryResearchAI.cmd`.

## Configuration

Real API keys, tokens, and NDL credentials belong only in local `secrets/`, environment variables, or controlled secret entry points. The frontend shows only redacted status.

Useful links:

- Windows installer guide: [docs/deployment/WINDOWS_INSTALLER.md](docs/deployment/WINDOWS_INSTALLER.md)
- Frontend user guide: [docs/guides/FRONTEND_USER_GUIDE.md](docs/guides/FRONTEND_USER_GUIDE.md)
- Workflow design: [WORKFLOW_DESIGN.md](WORKFLOW_DESIGN.md)
- Workspace guidelines: [GUIDELINES.md](GUIDELINES.md)
- Technical guide: [COMPREHENSIVE_TECHNICAL_GUIDE.md](COMPREHENSIVE_TECHNICAL_GUIDE.md)

## Run from Source

For developers or users who need to modify modules:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
$env:HISTORY_RESEARCH_SERVE_FRONTEND = "1"
py -3.11 -m app.app
```

Then open `http://127.0.0.1:5000/`.

## Privacy

This workspace is local-first by default. Logs, reports, README files, screenshots, and examples must not contain real secrets, cookies, recoverable private source text, or sensitive paths. AI outputs should keep `confidence`, `needs_review`, `quality_flags`, and artifact paths for human review.
