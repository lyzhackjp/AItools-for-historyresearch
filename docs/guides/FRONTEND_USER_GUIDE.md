# 前端使用指南 / Frontend User Guide / フロントエンド利用ガイド

本指南面向希望直接使用 UI 的研究者，尤其是不想手动配置后端、命令行和依赖的用户。安装、启动和基本配置请先看 README；这里说明打开界面后如何完成历史研究任务。

## 1. 启动 UI

Windows 安装版:

1. 从 [GitHub Releases](https://github.com/lyzhackjp/AItools-for-historyresearch/releases/latest) 下载并运行安装程序。
2. 从开始菜单打开 `History Research AI`。
3. 首次启动会初始化 Python runtime；完成后浏览器会打开 `http://127.0.0.1:5000/`。
4. 结束工作时，从开始菜单运行 `Stop History Research AI`。

源码运行:

如果是 freshly cloned source，请先按 README 中的源码方式安装依赖并构建 `frontend/dist`，再启动本地服务。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Start-HistoryResearchAI.ps1
```

## 2. 主要界面

| 中文界面 | English UI | 日本語UI | 用法 |
| --- | --- | --- | --- |
| 工作台首页 | Home | ホーム | 查看当前工作模式、后端状态和下一步入口。 |
| 全手动经典模式 | Manual classic mode | 手動クラシックモード | 适合逐项控制 OCR、NER、引用核验、provider、backend 和输出位置。 |
| AI agent solo 模式 | AI agent solo mode | AIエージェントsoloモード | 适合让 agent 先提计划，再在授权范围内调用模块；高风险步骤仍需人工确认。 |
| 七阶段工作流 | Seven-stage workflow | 七段階ワークフロー | 适合完整研究项目，从搜集材料推进到最终输出。 |
| 任务中心 | Task center | タスクセンター | 查看运行中和已完成任务的进度、日志、产物与复核项。 |
| 模块目录 | Module catalog | モジュールカタログ | 查看可用能力，并把模块加入手动任务或自由工作流。 |
| 可视化帮助 | Visual help | 可視化ヘルプ | 查看输入、执行、复核、导出的操作规则。 |
| 系统设置 | Settings | システム設定 | 设置界面语言、字体、显示密度和脱敏 provider 状态。 |

## 3. 推荐工作方式

### A. 处理 PDF、图像或日文史料

1. 进入“全手动经典模式”。
2. 在“模块目录”选择 OCR、版面分析或 NER 相关模块。
3. 指定文件、页码、输出位置和 backend。
4. 点击“加入任务中心并运行”。
5. 在“任务中心”查看 `confidence`、`needs_review`、`quality_flags` 和 artifact 路径。

适合场景: 批量 OCR、人物/地名/组织抽取、版面结构整理、古典籍 OCR 训练准备。

### B. 按七阶段推进研究项目

1. 打开“七阶段工作流”。
2. 先确定材料范围、研究目标和输出目录。
3. 从 `collect` 到 `format` 逐阶段运行；每个阶段完成后检查 checkpoint 和复核项。
4. 低置信、缺引用、疑似误识别或外部访问相关结果应先人工确认，再交给下一阶段。

适合场景: 从资料搜集到论文草稿、润色和 Word 输出的完整研究流程。

### C. 让 agent 提出执行计划

1. 进入“AI agent solo 模式”。
2. 写清研究目标、材料范围、允许调用的模块和不允许访问的内容。
3. 先点击“生成计划”，检查计划是否越界。
4. 批准后再运行；运行中持续观察任务中心。
5. 对外部检索、下载、写入文件、调用远程 API 等步骤保持人工确认。

适合场景: 已经知道研究目标，但希望由 agent 协调多个模块。

## 4. 配置与隐私

- 前端只保存必要状态和脱敏设置，不保存真实 API key。
- 真实密钥、NDL 凭据、私密史料和敏感路径应放在 `secrets/`、环境变量或后端受控入口。
- UI 中看到“未配置”不代表功能损坏，通常表示相关 provider 没有密钥或本地依赖尚未启用。
- 远程 API、外部检索和下载类能力必须显式启用，不应默认读取私密材料。
- 把 AI 结果用于论文前，请检查原始史料、页码、引文格式和 `needs_review` 项。

## 5. 常见问题

| 问题 | 处理方式 |
| --- | --- |
| 打开快捷方式后浏览器没有出现 | 等 30 秒后访问 `http://127.0.0.1:5000/`；若仍失败，运行 `Stop History Research AI` 后重新启动。 |
| 提示找不到 Python | 安装 Python 3.11，并在安装器中勾选 `Add Python to PATH`。 |
| 首次启动很慢 | 首次启动会创建 `.runtime\venv` 并安装依赖，网络较慢时需要等待。 |
| 某些 provider 显示未配置 | 到本地 `secrets/` 或环境变量中配置相应密钥；前端只显示脱敏状态。 |
| 任务结果低置信或需要复核 | 打开任务中心，检查 `quality_flags`、错误摘要、原始 artifact 和输入材料。 |
| 需要重新打包安装程序 | 参考 [docs/deployment/WINDOWS_INSTALLER.md](../deployment/WINDOWS_INSTALLER.md)。 |

## 6. 术语与三语对齐

前端、README 和本文档采用同一组术语:

| 中文 | English | 日本語 | 说明 |
| --- | --- | --- | --- |
| 数字人文 | Digital Humanities | デジタル・ヒューマニティーズ | 指数字工具、数据与人文学术问题之间的互动，不等同于“把人文学科简单电脑化”。 |
| OCR / 光学字符识别 | OCR / optical character recognition | OCR / 光学文字認識 | 用于从图像或扫描 PDF 中生成可检索文本。 |
| NER / 命名实体识别 | NER / named entity recognition | NER / 固有表現認識（固有表現抽出） | 用于识别人名、地名、组织、日期等实体。 |
| 史料考证 / 史料批判 | source criticism | 史料批判 | 用于判断史料真伪、来源、可靠性、偏见和内容准确性。 |
| 统一任务协议 | unified task protocol | 統一タスクプロトコル | 本工作区让 UI、API、workflow 和 agent 共用的任务输入输出约定。 |
| 任务中心 | Task center | タスクセンター | 长任务的统一观察、日志、产物和复核入口。 |

术语参考:

- Digital Humanities: [UWM Libraries](https://uwm.edu/libraries/digital-humanities/dh-lab-resources/what-are-digital-humanities/), [Duke Digital Humanities](https://digitalhumanities.duke.edu/about-digital-humanities)
- OCR: [NDL ラボ OCRテキスト化事業](https://lab.ndl.go.jp/data_set/ocr/r3_text/)
- NER: [Microsoft Learn: Named entity recognition](https://learn.microsoft.com/en-us/azure/ai-services/language-service/named-entity-recognition/overview), [Microsoft Learn 日本語: 固有表現認識](https://learn.microsoft.com/ja-jp/azure/ai-services/language-service/named-entity-recognition/overview)
- Source criticism: [University of Connecticut: Historical Research](https://researchbasics.education.uconn.edu/historical_research/)

## 7. 进一步阅读

- 项目 README: [../../README.md](../../README.md)
- 工作流设计: [../../WORKFLOW_DESIGN.md](../../WORKFLOW_DESIGN.md)
- 工作区规范: [../../GUIDELINES.md](../../GUIDELINES.md)
- Windows 安装包: [../deployment/WINDOWS_INSTALLER.md](../deployment/WINDOWS_INSTALLER.md)
- 统一任务框架: [UNIFIED_TASK_FRAMEWORK_GUIDE.md](UNIFIED_TASK_FRAMEWORK_GUIDE.md)
