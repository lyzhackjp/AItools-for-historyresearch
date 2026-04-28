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

## Disclaimer

- This project is a research and learning aid for historical research, digital humanities, and scholarly writing. It does not directly provide, host, resell, or proxy any large language model service, NDL Lab / NDL OCR-Lite / NDL Koten OCR-Lite model, NDL search/download service, or third-party data content.
- References to LLM providers, local models, NDL Lab models, NDL search/download tools, or similar capabilities mean that this workspace can connect to or orchestrate them through adapters. Users must obtain, install, configure, and use those services, models, datasets, and source providers under their own licenses, terms of use, account rules, rate limits, and copyright obligations.
- NDL search and download helpers are intended only to help organize search, logging, and download workflows where the user already has lawful access and the relevant institution or content provider permits such use. They must not be used to bypass access controls, perform prohibited bulk scraping, redistribute protected materials, or violate the terms of NDL or other platforms.
- LLM, OCR, NER, citation verification, source criticism, and writing-assistance outputs may contain errors, omissions, misrecognitions, or hallucinations. This project does not replace scholarly judgment, primary-source verification, copyright review, ethics review, legal assessment, or formal publication checks.
- Users are responsible for API costs, account security, rights clearance, citation practice, privacy protection, external-service upload risks, and the academic integrity of final research outputs. This public repository and installer exclude `secrets/`, private sources, logs, caches, and user outputs by default; do not upload unauthorized archives, full texts, or sensitive credentials to remote services.
