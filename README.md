# 历史研究 AI

语言: 中文 | [English](README.en-US.md) | [日本語](README.ja-JP.md)

面向日本史、日文史料处理与学术写作的本地优先型 AI 工作台。它把 OCR、NER、史料考证、学术笔记、引文核验、论文写作和 agent 自动化收拢到同一个可复核的界面中。

## 当前版本

`v1.1.0` 已整合后端、React 前端和 Windows 安装程序。

下载最新版安装程序: [GitHub Releases](https://github.com/lyzhackjp/AItools-for-historyresearch/releases/latest)

## 可以用来做什么

| 方向 | 说明 |
| --- | --- |
| 史料摄入 | 从 PDF、图像和日文史料中抽取文本、版面和实体。 |
| 笔记与知识库 | 组织学术笔记、Obsidian vault、引文记录和复核队列。 |
| 七阶段研究流程 | 从材料搜集、整理、抽取、考证，到写作、润色和最终格式化。 |
| 可复核 AI | 接入本地模型或远程 API 时，保留脱敏状态、质量标记和人工复核入口。 |

## UI 工作模式

| 界面 | 适合场景 |
| --- | --- |
| 全手动经典模式 | 逐项控制 OCR、NER、引用核验、provider、backend 和输出位置。 |
| AI agent solo 模式 | 让 agent 先提出计划，再按授权调用任务，并把高风险步骤交回人工确认。 |
| 七阶段工作流 | 按历史研究流程推进项目，并把 checkpoint 和产物登记到任务中心。 |
| 任务中心 | 查看长任务进度、日志、产物、quality flags 和 needs_review 项。 |
| 自由工作流编排 | 把模块目录中的能力组合成自定义研究流程。 |

## 快速安装

1. 打开 [Releases](https://github.com/lyzhackjp/AItools-for-historyresearch/releases/latest)，下载 `HistoryResearchAI-Setup-1.1.0.exe`。
2. 运行安装程序。
3. 从开始菜单或桌面快捷方式打开 `History Research AI`。
4. 首次启动会创建 `.runtime\venv` 并安装 Python 依赖；浏览器会打开 `http://127.0.0.1:5000/`。

如提示找不到 Python，请安装 Python 3.11，并在安装时勾选 `Add Python to PATH`。

停止本地服务: 开始菜单中的 `Stop History Research AI`，或运行 `scripts\windows\Stop-HistoryResearchAI.cmd`。

## 配置

API key、token、NDL 账号等真实凭据只放在本机 `secrets/`、环境变量或受控密钥入口；前端只显示脱敏状态。

常用入口:

- Windows 安装包说明: [docs/deployment/WINDOWS_INSTALLER.md](docs/deployment/WINDOWS_INSTALLER.md)
- 前端使用指南: [docs/guides/FRONTEND_USER_GUIDE.md](docs/guides/FRONTEND_USER_GUIDE.md)
- 工作流设计: [WORKFLOW_DESIGN.md](WORKFLOW_DESIGN.md)
- 工作区规范: [GUIDELINES.md](GUIDELINES.md)
- 详细技术说明: [COMPREHENSIVE_TECHNICAL_GUIDE.md](COMPREHENSIVE_TECHNICAL_GUIDE.md)

## 从源码运行

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

## 隐私原则

本工作区默认本地优先。日志、报告、README、截图和示例不得包含真实密钥、cookie、可复原的私密史料全文或敏感路径。所有 AI 结果都应保留 `confidence`、`needs_review`、`quality_flags` 和 artifact 路径，便于人工复核。

## 免责声明

- 本项目仅是面向历史研究、数字人文学习与学术写作的辅助工具，不直接提供、托管、转售或代理任何大模型服务、NDL Lab / NDL OCR-Lite / NDL 古典籍 OCR-Lite 模型、NDL 检索下载服务或第三方数据内容。
- README、代码和界面中出现的大模型 provider、本地模型、NDL Lab 模型、NDL 检索下载工具等名称，只表示本工作区可与这些外部能力形成适配或工作流连接；用户需要自行取得、安装、配置并遵守相应服务、模型、数据集和资料提供方的许可、使用条款、账号规则、频率限制与版权要求。
- NDL 搜索与下载相关工具仅用于在用户已经具备访问权限、且符合相关机构和资料提供方规则的前提下，辅助组织检索、记录和下载流程；不得用于绕过访问控制、批量抓取、再分发受保护材料或违反 NDL 及其他平台的使用条件。
- 大模型、OCR、NER、引文核验、史料考证和写作辅助结果都可能包含错误、遗漏、误识别或生成性幻觉。本项目不能替代研究者的学术判断、原始史料复核、版权审查、伦理审查、法律判断或正式出版规范检查。
- 用户应自行负责 API 费用、账号安全、资料权利清理、引用标注、隐私保护、外部服务上传风险和最终研究成果的学术诚信。本公开仓库和安装包默认排除 `secrets/`、私密史料、日志、缓存和用户输出；请不要把未获授权的档案、全文材料或敏感凭据上传到远程服务。
