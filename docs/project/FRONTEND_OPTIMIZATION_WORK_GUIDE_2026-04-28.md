# 前端设计开发与优化工作指导

## 文档定位

- 日期：2026-04-28
- 适用范围：`frontend/`、前端 API 契约、长任务进度反馈、手动工作台、AI agent solo 工作台
- 目标：作为当前线程后续前端开发优化的基本工作指导

本工作区的前端应从“功能入口集合”升级为“历史研究工作台”。后端已有统一任务 package/envelope、七阶段 workflow、artifact、quality flag 与 review queue 等基础能力，前端应优先围绕这些稳定协议组织界面，而不是为每个模块重复创造独立流程。

## 总体架构原则

两种用户模式共享同一套任务内核：

1. 全手动经典模式：用户可以逐项配置、执行、复核每个模块。
2. AI agent 辅助 solo 模式：agent 负责规划、调用、观察和修正，用户负责目标、授权、复核与关键确认。

前端分层如下：

- 任务协议层：统一消费 `/api/tasks/capabilities`、`/api/tasks/execute`、workflow、artifact、review queue。
- 任务状态层：维护前端任务、长任务、阶段进度、心跳、日志、失败、产物与恢复信息。
- 工作台交互层：分别提供手动编排界面与 agent 编排界面。
- 产物复核层：集中展示 artifacts、quality flags、review items、导出记录和人工确认点。

## 阶段一：可运行前端基线

目标是先让 React/Vite 主线干净、可构建、可持续迭代。

- 修复前端中文编码与乱码问题，确保用户界面、源码字符串和文档均可读。
- 明确 React/Vite/Ant Design 为主线，静态 HTML/JS 原型仅作为迁移参考。
- 安装并验证前端依赖，保证 `npm run build` 可以稳定通过。
- 整理 API 类型，建立 `TaskPackage`、`TaskCapability`、`TaskEvent`、`Artifact`、`QualityFlag`、`ReviewItem` 等共享类型。
- 保留旧业务 API 封装，但新增统一 task API，后续优先调用统一任务入口。

验收标准：

- `frontend/src` 中主界面不再出现影响阅读和编译的乱码。
- `npm run build` 通过。
- 首页能清楚表达“手动经典模式”和“AI agent solo 模式”两条路径。

## 阶段二：长任务与进度反馈内核

OCR、NER、远程大模型、workflow、agent 调用都可能长时间运行。前端必须提供稳定、可见、可恢复的反馈体验。

前端先实现统一任务中心：

- 顶部运行状态提示。
- 任务抽屉或任务中心页面。
- 阶段时间线。
- 百分比进度。
- 最近日志与心跳。
- 失败原因、重试、取消、复制摘要。
- 产物列表与复核入口。

后端推荐协议：

- `POST /api/jobs`：提交长任务，立即返回 `job_id`。
- `GET /api/jobs/<id>`：查询状态、阶段、进度、日志、产物。
- `GET /api/jobs/<id>/events`：SSE 事件流。
- `POST /api/jobs/<id>/cancel`：取消任务。
- `POST /api/jobs/<id>/resume`：从 checkpoint 恢复。

在后端 job 协议完全落地前，前端以本地任务状态、轮询和 `/api/tasks/execute` 同步结果作为兼容路径。

验收标准：

- 所有手动和 agent 任务都进入同一个任务中心。
- 任务至少展示状态、进度、当前阶段、耗时、日志和产物摘要。
- 长任务没有“界面静默等待”的体验。

## 阶段三：全手动经典模式

目标是让工作区所有核心功能都能由用户细粒度配置、运行和复核。

核心界面：

- 任务能力中心：动态读取 task registry、preset、backend、provider。
- OCR 工作台：文件、页码、引擎、语言、预处理、批量队列、结果复核。
- NER 工作台：文本来源、实体类型、规则/LLM/本地模型选择、消歧与人工复核。
- 引用与史料考证：DOCX 解析、候选来源、证据链、下载/OCR 开关。
- 七阶段 workflow 编排器：collect、organize、extract、examine、write、polish、format 均可启停和重跑。
- 产物与审阅中心：artifact browser、quality flags、review queue、导出历史。
- Prompt、Provider 与模型设置：可配置、可审计，不暴露 secrets。

2026-04-28 追加要求：

- 手动挡必须提供类似 Dify 的自由编排能力。
- 模块目录需覆盖 TaskManager 任务、七阶段 workflow、package-only 模块三类能力。
- 用户应能自主添加模块节点、调整顺序、配置输入绑定、输出位置、backend、provider、preset 和 review gate。
- 当前前端先生成 workflow blueprint JSON，并把运行请求送入统一任务中心；后端后续应补 `/api/jobs` 或 `/api/workflow/blueprints` 承接真实执行。
- 说明一句：现在 package-only 模块已在前端以“可编排蓝图节点”接合；其中 TaskManager 任务和 workflow 阶段已有较明确执行路径，其他 package-only 模块后续若要真实逐节点执行，最好补一个后端 `/api/jobs` 或 `/api/workflow/blueprints` 执行端点来承接这些 blueprint。

2026-04-28 追加要求：多语言与可视化帮助：

- 前端界面提供中文、英文、日文三种显示语言。
- 中文界面中，所有模块和功能默认显示中文名称，并在括号中保留英文名称。
- 日文界面中，所有模块和功能默认显示日文名称，并在括号中保留英文名称；日文术语优先采用通行学术译法，例如 OCR 光学文字認識、NER 固有表現抽出、引用ネットワーク、セマンティック検索、文体変換、アーティファクト等。
- 每个模块和功能入口都应接上可视化使用帮助，帮助内容对照 `GUIDELINES`、`WORKFLOW` 和 workspace skill 的核心规范，覆盖输入定位、执行参数、长任务进度、package/envelope、quality flags、review queue、artifact 登记和权限确认。

设计要求：

- 界面风格偏工作台，信息密集但清晰。
- 每个模块都要有输入、配置、执行、进度、结果、复核、导出。
- 高风险动作明确确认，例如外部检索、下载、写入 vault、覆盖文件、付费 API。

## 阶段四：AI agent 辅助 solo 模式

solo 模式的目标不是黑箱自动化，而是“可观察、可授权、可复核的自动研究助手”。

核心界面：

- Agent 选择器：OpenClaw、Hermes、Codex skill、MCP agent、vibe coding agent 等通过统一 connector 接入。
- 目标输入：研究主题、材料范围、期望产物、时间预算、允许的后端。
- 计划面板：agent 先生成计划，用户可批准、编辑、锁定阶段或禁止动作。
- 运行观察面板：展示 agent 当前动作、调用任务、backend/provider、阶段结果和 artifacts。
- 人工确认点：外部访问、下载、写入、覆盖、进入下一阶段、使用付费 API 前确认。
- 可回放日志：保留决策摘要、任务输入摘要、任务结果摘要和失败恢复路径。

2026-04-28 追加要求：

- solo 模式必须提供 workspace skill 配置器。
- 用户应能自主选择 agent 可调用的模块范围、allowed backends、外部检索、下载、写入 artifact、写入 vault、付费 API 等权限。
- 前端应能生成 `SKILL.md` 草案和配置 JSON，作为 agent 调用工作区的可复核边界。
- skill 配置变更同样进入任务中心和 review queue，而不是静默生效。

推荐前端接口：

```ts
interface AgentConnector {
  id: string;
  name: string;
  capabilities(): Promise<AgentCapability[]>;
  proposePlan(goal: AgentGoal): Promise<AgentPlan>;
  startRun(plan: AgentPlan): Promise<JobHandle>;
  observe(jobId: string): AsyncIterable<AgentEvent>;
  stop(jobId: string): Promise<void>;
}
```

验收标准：

- solo 模式可以生成计划并进入任务中心。
- 用户能看到 agent 正在做什么、为什么做、下一步是什么。
- 用户可以暂停、取消、确认或要求重试。

## 阶段五：视觉与交互优化

推荐布局：

- 左侧：模式切换、模块导航、项目列表。
- 顶部：当前项目、运行状态、任务中心、设置。
- 主区：当前模块配置与结果。
- 右侧或抽屉：任务进度、日志、产物、复核队列。

视觉原则：

- 保持安静、清晰、适合长时间工作。
- 避免营销式首页和装饰性布局。
- 以扫描、比较、重复操作为核心。
- 重要状态使用标签、进度条、时间线和表格。
- 长文本不挤压按钮和卡片，所有控件在桌面和移动视口都应可用。

## 实施优先级

1. 修复编码、依赖和构建基线。
2. 建立统一任务类型、API 封装和任务中心。
3. 实现首页模式分流与全局布局。
4. 实现手动经典模式的模块编排。
5. 实现 agent solo 模式的计划、观察、确认与日志。
6. 补齐设置、产物复核和工作流页面。
7. 构建验证、交互检查、文档更新。

## 当前线程执行约定

- 后续前端开发以本文件为指导。
- 遇到编码、构建、类型、样式和接口兼容问题，优先自行修复。
- 任何长任务相关能力都必须进入统一任务中心。
- 新增界面优先复用现有 React、TypeScript、Ant Design、Zustand 和 React Query 技术栈。
- 不把 secrets、真实私密史料全文或可复原敏感数据写入前端、日志或文档。
