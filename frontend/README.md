# 历史研究AI工具 - 前端

一个专为日本史研究人员打造的现代化前端界面，基于 React 18 + TypeScript + Ant Design 构建。

## 🚀 快速开始

### 环境要求

- Node.js >= 18.0.0
- npm >= 9.0.0 或 yarn >= 1.22.0

### 安装依赖

```bash
cd frontend
npm install
```

### 开发模式

```bash
npm run dev
```

访问 http://localhost:3000

### 构建生产版本

```bash
npm run build
```

### 预览生产版本

```bash
npm run preview
```

## 📁 项目结构

```
frontend/
├── src/
│   ├── api/              # API接口层
│   ├── components/       # 组件库
│   │   ├── common/      # 通用组件
│   │   ├── business/    # 业务组件
│   │   └── layout/      # 布局组件
│   ├── pages/           # 页面组件
│   ├── stores/          # 状态管理
│   ├── hooks/           # 自定义Hooks
│   ├── utils/           # 工具函数
│   ├── types/           # 类型定义
│   └── styles/          # 样式文件
├── public/              # 静态资源
└── tests/               # 测试文件
```

## 🛠️ 技术栈

- **框架**: React 18 + TypeScript
- **构建工具**: Vite
- **UI组件库**: Ant Design 5.x
- **状态管理**: Zustand
- **数据请求**: @tanstack/react-query + Axios
- **样式方案**: Tailwind CSS + CSS Modules
- **代码规范**: ESLint + Prettier

## 📦 核心功能

### 1. 论文润色
- 支持 .docx 文件上传
- 三种润色策略：快速、深度、自定义
- 支持中日英三语润色
- 实时预览修改建议

### 2. OCR识别
- 支持 PDF、图片格式
- 四种OCR引擎可选
- 水印自动去除
- 批量处理支持

### 3. 实体识别
- 自动识别人名、地名、事件等
- 支持文本输入和文件上传
- 结果可视化展示
- 导出为JSON/CSV格式

### 4. 笔记生成
- 自动生成学术笔记
- 支持Obsidian格式
- 实体自动提取
- 知识图谱构建

### 5. 研究助手
- AI智能对话
- 文献分析
- 历史记录保存
- 多轮对话支持

### 6. 提示词编辑器
- 可视化编辑提示词
- 模板管理
- 变量提示
- 预览功能

## 🎨 设计原则

### 用户体验
- **简约设计**: 界面简洁，操作直观
- **响应式布局**: 适配桌面和移动设备
- **无障碍支持**: 支持大字体、高对比度模式
- **快速响应**: 优化加载速度，提升用户体验

### 代码质量
- **TypeScript**: 类型安全，减少运行时错误
- **组件化**: 高度可复用的组件设计
- **模块化**: 清晰的代码结构，易于维护
- **测试覆盖**: 单元测试和集成测试

## 🔧 配置说明

### API配置

前端默认连接到 `http://localhost:5000`，可通过环境变量修改：

```bash
# .env.local
VITE_API_BASE_URL=http://your-api-server:5000
```

### API密钥管理

API密钥存储在浏览器本地存储中，支持以下服务商：
- 通义千问（推荐）
- OpenAI
- 智谱AI
- MiniMax

## 📝 开发规范

### Git提交规范

```
feat: 新功能
fix: 修复bug
docs: 文档更新
style: 代码格式调整
refactor: 重构
test: 测试相关
chore: 构建/工具相关
```

### 代码规范

- 使用 ESLint + Prettier 进行代码格式化
- 遵循 TypeScript 最佳实践
- 组件命名使用 PascalCase
- 函数命名使用 camelCase
- 常量命名使用 UPPER_SNAKE_CASE

## 🧪 测试

```bash
# 运行测试
npm run test

# 测试覆盖率
npm run test:coverage

# 测试UI
npm run test:ui
```

## 📚 相关文档

- [前端开发计划](../FRONTEND_DEVELOPMENT_PLAN.md)
- [后端API文档](../docs/ARCHITECTURE_DESIGN.md)
- [工作流程图](../WORKFLOW_DIAGRAM.md)

## 🔒 安全说明

- API密钥仅存储在本地浏览器中
- 所有API请求通过后端代理
- 不在代码中硬编码敏感信息
- 遵循OWASP安全最佳实践

## 📄 License

MIT License

## 👥 贡献

欢迎提交 Issue 和 Pull Request！

---

**版本**: 1.0.0  
**更新日期**: 2026-04-01
