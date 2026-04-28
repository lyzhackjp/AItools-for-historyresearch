# 历史研究 AI / History Research AI / 歴史研究AI

面向日本史、日文史料处理与学术写作的本地优先型 AI 工作台。它把 OCR、NER、史料考证、学术笔记、引文核验、论文写作和 agent 自动化收拢到同一个可复核的界面中。

A local-first AI workbench for Japanese history, Japanese-language sources, and scholarly writing. It brings OCR, NER, source criticism, notes, citation checks, writing, and observable agent automation into one reviewable UI.

日本史・日本語史料処理・学術執筆のためのローカル優先AI作業台です。OCR、NER、史料批判、ノート、引用検証、執筆、観察可能なagent自動化を、一つのレビュー可能なUIに統合します。

## 当前版本 / Current Release / 現行リリース

- `v1.1.0`: 后端 + React 前端 + Windows 安装程序已整合。
- `v1.1.0`: Backend, React frontend, and Windows installer are integrated.
- `v1.1.0`: バックエンド、Reactフロントエンド、Windowsインストーラーを統合済み。

下载最新版安装程序 / Download the latest installer / 最新インストーラー:
[GitHub Releases](https://github.com/lyzhackjp/AItools-for-historyresearch/releases/latest)

## 可以用来做什么 / What It Does / できること

| 中文 | English | 日本語 |
| --- | --- | --- |
| 从 PDF、图像和日文史料中抽取文本、版面和实体。 | Extract text, layout, and entities from PDFs, images, and Japanese-language sources. | PDF、画像、日本語史料からテキスト、レイアウト、エンティティを抽出します。 |
| 组织学术笔记、Obsidian vault、引文记录和复核队列。 | Organize scholarly notes, Obsidian vault output, citation records, and review queues. | 学術ノート、Obsidian vault、引用記録、レビュー項目を整理します。 |
| 按七阶段工作流推进材料搜集、整理、抽取、考察、写作、润色和格式化。 | Run a seven-stage workflow from collection and organization to extraction, examination, writing, polishing, and formatting. | 資料収集から整理、抽出、考察、執筆、推敲、整形まで七段階ワークフローで進めます。 |
| 在需要时接入本地模型或远程 API，但保留脱敏状态、质量标记和人工复核。 | Use local models or remote APIs when needed while keeping redacted status, quality flags, and human review. | 必要に応じてローカルモデルや外部APIを使いながら、匿名化状態、品質シグナル、人間レビューを保持します。 |

## UI 工作模式 / UI Modes / UIモード

| 中文界面 | English UI | 日本語UI | 适合场景 |
| --- | --- | --- | --- |
| 全手动经典模式 | Manual classic mode | 手動クラシックモード | 逐项控制 OCR、NER、引用核验、provider、backend 和输出位置。 |
| AI agent solo 模式 | AI agent solo mode | AIエージェントsoloモード | 让 agent 先提出计划，再按授权调用任务，并把高风险步骤交回人工确认。 |
| 七阶段工作流 | Seven-stage workflow | 七段階ワークフロー | 按历史研究流程推进项目，并把 checkpoint 和产物登记到任务中心。 |
| 任务中心 | Task center | タスクセンター | 查看长任务进度、日志、产物、quality flags 和 needs_review 项。 |
| 自由工作流编排 | Free workflow builder | 自由ワークフロー編成 | 把模块目录中的能力组合成自定义研究流程。 |

## 快速安装 / Quick Install / クイックインストール

| 步骤 | 中文 | English | 日本語 |
| --- | --- | --- | --- |
| 1 | 打开 [Releases](https://github.com/lyzhackjp/AItools-for-historyresearch/releases/latest)，下载 `HistoryResearchAI-Setup-1.1.0.exe`。 | Open [Releases](https://github.com/lyzhackjp/AItools-for-historyresearch/releases/latest) and download `HistoryResearchAI-Setup-1.1.0.exe`. | [Releases](https://github.com/lyzhackjp/AItools-for-historyresearch/releases/latest) を開き、`HistoryResearchAI-Setup-1.1.0.exe` をダウンロードします。 |
| 2 | 运行安装程序。首次启动会创建 `.runtime\venv` 并安装 Python 依赖。 | Run the installer. First launch creates `.runtime\venv` and installs Python dependencies. | インストーラーを実行します。初回起動時に `.runtime\venv` を作成し、Python依存関係をインストールします。 |
| 3 | 从开始菜单或桌面快捷方式打开 `History Research AI`。 | Start `History Research AI` from the Start menu or desktop shortcut. | スタートメニューまたはデスクトップショートカットから `History Research AI` を起動します。 |
| 4 | 浏览器会打开 `http://127.0.0.1:5000/`。如提示找不到 Python，请安装 Python 3.11 并勾选 `Add Python to PATH`。 | The browser opens `http://127.0.0.1:5000/`. If Python is missing, install Python 3.11 and enable `Add Python to PATH`. | ブラウザーで `http://127.0.0.1:5000/` が開きます。Python が見つからない場合は Python 3.11 をインストールし、`Add Python to PATH` を有効にしてください。 |

停止本地服务 / Stop the local service / ローカルサービス停止:
开始菜单中的 `Stop History Research AI`，或运行 `scripts\windows\Stop-HistoryResearchAI.cmd`。

## 配置 / Configuration / 設定

- API key、token、NDL 账号等真实凭据只放在本机 `secrets/` 或受控密钥入口；前端只显示脱敏状态。
- Real API keys, tokens, and NDL credentials belong in local `secrets/` or controlled secret entry points; the frontend shows only redacted status.
- 実APIキー、token、NDL認証情報はローカルの `secrets/` または管理された秘密情報入口に置きます。フロントエンドは匿名化状態のみ表示します。

常用配置入口:

- Windows 安装包说明: [docs/deployment/WINDOWS_INSTALLER.md](docs/deployment/WINDOWS_INSTALLER.md)
- 前端使用指南: [docs/guides/FRONTEND_USER_GUIDE.md](docs/guides/FRONTEND_USER_GUIDE.md)
- 工作流设计: [WORKFLOW_DESIGN.md](WORKFLOW_DESIGN.md)
- 工作区规范: [GUIDELINES.md](GUIDELINES.md)
- 详细技术说明: [COMPREHENSIVE_TECHNICAL_GUIDE.md](COMPREHENSIVE_TECHNICAL_GUIDE.md)

## 从源码运行 / Run from Source / ソースから実行

适合开发者或需要修改模块的用户:

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

然后打开 `http://127.0.0.1:5000/`。

## 隐私原则 / Privacy / プライバシー

本工作区默认本地优先。日志、报告、README、截图和示例不得包含真实密钥、cookie、可复原的私密史料全文或敏感路径。所有 AI 结果都应保留 `confidence`、`needs_review`、`quality_flags` 和 artifact 路径，便于人工复核。

This workspace is local-first by default. Logs, reports, README files, screenshots, and examples must not contain real secrets, cookies, recoverable private source text, or sensitive paths. AI outputs should keep `confidence`, `needs_review`, `quality_flags`, and artifact paths for human review.

この作業区は既定でローカル優先です。ログ、報告、README、スクリーンショット、例には実キー、cookie、復元可能な私的史料全文、機微なパスを含めません。AI出力には人間レビューのため `confidence`、`needs_review`、`quality_flags`、artifact パスを残します。
