# 历史研究AI工具 - 前端开发计划

## 文档信息

| 属性 | 内容 |
|------|------|
| 版本 | 1.0.0 |
| 创建日期 | 2026-04-01 |
| 文档性质 | 前端开发实施计划 |
| 关联文档 | [WORKFLOW_DIAGRAM.md](WORKFLOW_DIAGRAM.md) |

---

## 📊 项目现状分析

### 当前架构
- **后端**：Flask REST API（已完成）
- **前端**：暂无（需从零构建）
- **配置系统**：已完善（API Key管理、提示词管理）
- **核心功能**：11个主要模块已就绪

### 关键发现
1. 后端API接口已规范化，前端可直接对接
2. 已有安全的API Key管理机制
3. 提示词系统支持Markdown格式，便于可视化编辑
4. 需要为不同年龄段用户设计差异化交互

---

## 🏗️ 一、架构设计方案

### 1.1 技术栈选择

```
前端框架：React 18 + TypeScript
  理由：类型安全、生态成熟、适合复杂应用

状态管理：Zustand + React Query
  理由：轻量级、学习成本低、适合API密集型应用

UI组件库：Ant Design 5.x（定制主题）
  理由：中文友好、组件丰富、适合企业级应用

构建工具：Vite
  理由：快速开发体验、优秀的TypeScript支持

样式方案：Tailwind CSS + CSS Modules
  理由：快速开发 + 组件样式隔离

图表库：ECharts + React Flow
  理由：引文网络可视化、流程图展示
```

### 1.2 目录结构设计

```
frontend/
├── src/
│   ├── api/                    # API层
│   │   ├── client.ts          # Axios实例配置
│   │   ├── endpoints/         # 各模块API
│   │   │   ├── doc.ts         # 文档处理
│   │   │   ├── ocr.ts         # OCR识别
│   │   │   ├── ner.ts         # 实体识别
│   │   │   └── research.ts    # 研究助手
│   │   └── types.ts           # API类型定义
│   │
│   ├── components/             # 组件库
│   │   ├── common/            # 通用组件
│   │   │   ├── Button/
│   │   │   ├── Form/
│   │   │   ├── Modal/
│   │   │   └── Layout/
│   │   ├── business/          # 业务组件
│   │   │   ├── PromptEditor/  # 提示词编辑器
│   │   │   ├── ApiKeyManager/ # API密钥管理
│   │   │   ├── FileUploader/  # 文件上传
│   │   │   └── ResultViewer/  # 结果展示
│   │   └── features/          # 功能模块组件
│   │       ├── PaperPolisher/
│   │       ├── OcrProcessor/
│   │       ├── NerExtractor/
│   │       └── ResearchAssistant/
│   │
│   ├── pages/                  # 页面
│   │   ├── Home/              # 首页/工作台
│   │   ├── Settings/          # 设置页
│   │   ├── PaperPolish/       # 论文润色
│   │   ├── OcrProcess/        # OCR处理
│   │   ├── EntityRecognition/ # 实体识别
│   │   ├── NoteGenerator/     # 笔记生成
│   │   └── Research/          # 研究助手
│   │
│   ├── stores/                 # 状态管理
│   │   ├── useUserStore.ts    # 用户偏好
│   │   ├── useApiStore.ts     # API配置
│   │   └── useTaskStore.ts    # 任务状态
│   │
│   ├── hooks/                  # 自定义Hooks
│   │   ├── useApi.ts          # API调用封装
│   │   ├── useFileUpload.ts   # 文件上传
│   │   └── useLocalStorage.ts # 本地存储
│   │
│   ├── utils/                  # 工具函数
│   │   ├── format.ts          # 格式化
│   │   ├── validation.ts      # 验证
│   │   └── download.ts        # 文件下载
│   │
│   ├── styles/                 # 全局样式
│   │   ├── theme.ts           # 主题配置
│   │   └── global.css         # 全局样式
│   │
│   └── types/                  # 类型定义
│       ├── api.ts
│       ├── models.ts
│       └── components.ts
│
├── public/                     # 静态资源
├── tests/                      # 测试文件
├── docs/                       # 前端文档
└── config/                     # 配置文件
```

### 1.3 核心设计模式

#### 状态管理架构
```typescript
// stores/useApiStore.ts
interface ApiStore {
  // API配置状态
  apiKeys: Record<string, ApiKeyConfig>;
  activeProvider: string;
  
  // 操作方法
  setApiKey: (provider: string, key: string) => void;
  removeApiKey: (provider: string) => void;
  switchProvider: (provider: string) => void;
  
  // 持久化
  loadFromStorage: () => void;
  saveToStorage: () => void;
}

// 使用Zustand实现
export const useApiStore = create<ApiStore>()(
  persist(
    (set, get) => ({
      apiKeys: {},
      activeProvider: 'qwen',
      
      setApiKey: (provider, key) => set((state) => ({
        apiKeys: { ...state.apiKeys, [provider]: { key, createdAt: Date.now() } }
      })),
      
      // ... 其他方法
    }),
    { name: 'api-config' }
  )
);
```

#### 组件化设计原则
```typescript
// 组件分层：基础组件 → 业务组件 → 页面组件

// 1. 基础组件：高度可复用
<BaseButton variant="primary" size="large">
  开始润色
</BaseButton>

// 2. 业务组件：封装业务逻辑
<PromptEditor
  moduleId="academic_note_generator"
  promptId="AN_G001"
  onSave={handleSave}
  readOnly={false}
/>

// 3. 页面组件：组合业务组件
<PaperPolishPage>
  <FileUploader />
  <PolishOptions />
  <ResultViewer />
</PaperPolishPage>
```

---

## 🎨 二、用户体验设计

### 2.1 用户画像与需求矩阵

| 用户群体 | 核心需求 | 痛点 | 设计策略 |
|---------|---------|------|---------|
| **中年研究者**<br>(45-60岁) | - 操作简单直观<br>- 字体大、对比度高<br>- 步骤清晰明确 | - 技术学习成本高<br>- 害怕误操作<br>- 视力下降 | - 大按钮、大字体<br>- 向导式流程<br>- 醒目的确认提示<br>- 一键操作模式 |
| **老年研究者**<br>(60岁以上) | - 极简操作<br>- 语音/视频引导<br>- 容错性强 | - 数字鸿沟<br>- 记忆力下降<br>- 操作缓慢 | - 极简模式（3步内完成）<br>- 内嵌视频教程<br>- 撤销/重做功能<br>- 自动保存 |
| **青年工作者**<br>(25-45岁) | - 高效快捷<br>- 批量处理<br>- 自定义配置 | - 不想配置环境<br>- 需要快速验证<br>- 追求效率 | - 快捷键支持<br>- 批量操作<br>- 模板系统<br>- 历史记录 |

### 2.2 核心交互流程设计

#### 论文润色流程（3步完成）
```
┌─────────────────────────────────────────────────────┐
│  Step 1: 上传文档                                    │
│  ┌───────────────────────────────────────────────┐  │
│  │  📄 拖拽文件到此处，或点击选择                   │  │
│  │     支持 .docx 格式                            │  │
│  └───────────────────────────────────────────────┘  │
│                       ↓                             │
│  Step 2: 选择润色策略                                │
│  ○ 快速润色（推荐新手）                              │
│  ○ 深度润色（保留原文风格）                          │
│  ○ 自定义（高级用户）                                │
│                       ↓                             │
│  Step 3: 查看结果                                    │
│  ┌───────────────────────────────────────────────┐  │
│  │  ✅ 润色完成！发现 23 处改进建议                 │  │
│  │  [预览对比] [下载文档] [继续润色]               │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

#### API Key管理界面
```
┌─────────────────────────────────────────────────────┐
│  🔑 API密钥管理                                      │
├─────────────────────────────────────────────────────┤
│  当前服务商：通义千问 ⭐推荐                         │
│                                                      │
│  已配置的服务：                                       │
│  ┌──────────────────────────────────────────────┐  │
│  │ ✅ 通义千问    sk-****1234    [测试] [删除]   │  │
│  │ ⚪ OpenAI      未配置          [添加]         │  │
│  │ ⚪ 智谱AI      未配置          [添加]         │  │
│  └──────────────────────────────────────────────┘  │
│                                                      │
│  💡 提示：至少配置一个服务商即可使用全部功能          │
│  [添加新密钥]                                        │
└─────────────────────────────────────────────────────┘
```

#### Prompt可视化编辑器
```
┌─────────────────────────────────────────────────────┐
│  📝 提示词编辑器 - 学术笔记生成                      │
├─────────────────────────────────────────────────────┤
│  模板选择：[预设模板 ▼]  [我的模板 ▼]  [导入 ▼]     │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │ 你是一位专业的学术笔记整理专家。                │  │
│  │                                                │  │
│  │ 请根据以下文献内容生成笔记：                    │  │
│  │ - 文献标题：{{title}}                          │  │
│  │ - 作者：{{author}}                             │  │
│  │ - 关键词：{{keywords}}                         │  │
│  │                                                │  │
│  │ 输出格式要求：                                 │  │
│  │ 1. 核心观点（3-5条）                           │  │
│  │ 2. 研究方法                                    │  │
│  │ 3. 创新点                                      │  │
│  └──────────────────────────────────────────────┘  │
│                                                      │
│  变量说明：                                          │
│  {{title}} - 自动提取文献标题                       │
│  {{author}} - 自动提取作者信息                      │
│                                                      │
│  [预览效果] [保存模板] [重置]                        │
└─────────────────────────────────────────────────────┘
```

### 2.3 无障碍设计要点

```css
/* 适老化设计 */
.senior-mode {
  /* 字体放大 */
  font-size: 18px;
  
  /* 行高增加 */
  line-height: 1.8;
  
  /* 按钮加大 */
  --button-height: 48px;
  
  /* 对比度提升 */
  --primary-color: #1890ff;
  --text-color: #000000;
  
  /* 点击区域扩大 */
  --click-area: 44px;
}

/* 高对比度模式 */
.high-contrast {
  --bg-color: #ffffff;
  --text-color: #000000;
  --border-color: #000000;
}
```

---

## 📅 三、开发阶段规划

### 阶段A：架构搭建与基础组件开发（3周）

#### Week 1：项目初始化
```bash
# 技术准备
□ 创建React项目
□ 配置TypeScript
□ 集成Ant Design
□ 配置Vite构建
□ 设置ESLint + Prettier
□ 配置Git工作流
```

#### Week 2-3：基础组件开发
```typescript
// 组件开发清单

// 1. 布局组件
□ AppLayout          // 整体布局
□ Sidebar            // 侧边导航
□ Header             // 顶部栏
□ Footer             // 底部信息

// 2. 通用组件
□ BaseButton         // 按钮组件
□ BaseInput          // 输入框
□ BaseSelect         // 下拉选择
□ BaseModal          // 弹窗
□ BaseTable          // 表格
□ BaseCard           // 卡片
□ LoadingSpinner     // 加载动画
□ ErrorMessage       // 错误提示

// 3. 表单组件
□ FormBuilder        // 表单构建器
□ FormField          // 表单字段
□ FormValidator      // 表单验证

// 4. 文件组件
□ FileUploader       // 文件上传
□ FilePreview        // 文件预览
□ FileDownloader     // 文件下载

// 5. 反馈组件
□ Toast              // 轻提示
□ ConfirmDialog      // 确认对话框
□ ProgressIndicator  // 进度指示器
```

**组件开发示例：**
```tsx
// components/common/FileUploader/FileUploader.tsx
interface FileUploaderProps {
  accept: string[];
  maxSize: number;
  multiple?: boolean;
  onUpload: (files: File[]) => void;
  onError: (error: string) => void;
  disabled?: boolean;
}

export const FileUploader: React.FC<FileUploaderProps> = ({
  accept,
  maxSize,
  multiple = false,
  onUpload,
  onError,
  disabled = false
}) => {
  const [isDragging, setIsDragging] = useState(false);
  
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = Array.from(e.dataTransfer.files);
    const validFiles = validateFiles(files, accept, maxSize);
    
    if (validFiles.length > 0) {
      onUpload(validFiles);
    }
  }, [accept, maxSize, onUpload]);
  
  return (
    <div
      className={cn(styles.uploader, { [styles.dragging]: isDragging })}
      onDrop={handleDrop}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
    >
      <UploadIcon className={styles.icon} />
      <p className={styles.text}>
        拖拽文件到此处，或<span className={styles.link}>点击选择</span>
      </p>
      <p className={styles.hint}>
        支持 {accept.join(', ')} 格式，最大 {maxSize}MB
      </p>
    </div>
  );
};
```

---

### 阶段B：核心功能开发（6周）

#### Week 4-5：API层与状态管理
```typescript
// API客户端配置
// api/client.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json'
  }
});

// 请求拦截器：添加API Key
apiClient.interceptors.request.use((config) => {
  const apiKey = useApiStore.getState().getActiveKey();
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey;
  }
  return config;
});

// 响应拦截器：统一错误处理
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      message.error('API密钥无效，请检查配置');
    }
    return Promise.reject(error);
  }
);
```

#### Week 6-7：核心功能模块开发

**模块1：论文润色**
```tsx
// pages/PaperPolish/index.tsx
export const PaperPolishPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [strategy, setStrategy] = useState<'quick' | 'deep' | 'custom'>('quick');
  const [result, setResult] = useState<PolishResult | null>(null);
  
  const polishMutation = usePolishDocument();
  
  const handlePolish = async () => {
    if (!file) return;
    
    const result = await polishMutation.mutateAsync({
      file,
      strategy,
      language: 'ja'
    });
    
    setResult(result);
  };
  
  return (
    <PageLayout title="学术论文润色">
      <StepIndicator current={file ? 2 : 1} total={3} />
      
      <Section title="1. 上传文档">
        <FileUploader
          accept={['.docx']}
          maxSize={10}
          onUpload={(files) => setFile(files[0])}
        />
      </Section>
      
      {file && (
        <Section title="2. 选择润色策略">
          <RadioGroup value={strategy} onChange={setStrategy}>
            <Radio value="quick">快速润色（推荐新手）</Radio>
            <Radio value="deep">深度润色（保留原文风格）</Radio>
            <Radio value="custom">自定义（高级用户）</Radio>
          </RadioGroup>
        </Section>
      )}
      
      {file && (
        <Section title="3. 开始润色">
          <Button
            type="primary"
            size="large"
            loading={polishMutation.isLoading}
            onClick={handlePolish}
          >
            开始润色
          </Button>
        </Section>
      )}
      
      {result && (
        <Section title="润色结果">
          <ResultViewer result={result} />
        </Section>
      )}
    </PageLayout>
  );
};
```

**模块2：OCR处理**
```tsx
// pages/OcrProcess/index.tsx
export const OcrProcessPage: React.FC = () => {
  const [files, setFiles] = useState<File[]>([]);
  const [ocrEngine, setOcrEngine] = useState<OCREngine>('ndlocr-lite');
  const [results, setResults] = useState<OCRResult[]>([]);
  
  return (
    <PageLayout title="PDF文献OCR识别">
      <Row gutter={24}>
        <Col span={12}>
          <FileUploader
            accept={['.pdf', '.png', '.jpg']}
            multiple
            maxSize={50}
            onUpload={setFiles}
          />
          
          <OCREngineSelector
            value={ocrEngine}
            onChange={setOcrEngine}
            options={[
              { value: 'ndlocr-lite', label: 'NDL OCR-Lite ⭐推荐', desc: '近代现代文献' },
              { value: 'ndlkotenocr-lite', label: 'NDL古典籍OCR-Lite', desc: '古典籍文献' },
              { value: 'tesseract', label: 'Tesseract OCR', desc: '本地运行' }
            ]}
          />
        </Col>
        
        <Col span={12}>
          <OCRResultViewer results={results} />
        </Col>
      </Row>
    </PageLayout>
  );
};
```

**模块3：API Key管理**
```tsx
// components/business/ApiKeyManager/ApiKeyManager.tsx
export const ApiKeyManager: React.FC = () => {
  const { apiKeys, activeProvider, setApiKey, removeApiKey, switchProvider } = useApiStore();
  const [showAddModal, setShowAddModal] = useState(false);
  
  const providers = [
    { id: 'qwen', name: '通义千问', recommended: true },
    { id: 'openai', name: 'OpenAI', recommended: false },
    { id: 'zhipu', name: '智谱AI', recommended: false }
  ];
  
  return (
    <Card title="API密钥管理">
      <Alert
        type="info"
        message="至少配置一个服务商即可使用全部功能"
        showIcon
      />
      
      <List
        dataSource={providers}
        renderItem={(provider) => (
          <List.Item
            actions={[
              apiKeys[provider.id] ? (
                <>
                  <Button size="small" onClick={() => testConnection(provider.id)}>
                    测试
                  </Button>
                  <Button size="small" danger onClick={() => removeApiKey(provider.id)}>
                    删除
                  </Button>
                </>
              ) : (
                <Button size="small" type="primary" onClick={() => setShowAddModal(true)}>
                  添加
                </Button>
              )
            ]}
          >
            <List.Item.Meta
              avatar={
                apiKeys[provider.id] ? (
                  <CheckCircleFilled style={{ color: '#52c41a' }} />
                ) : (
                  <MinusCircleFilled style={{ color: '#d9d9d9' }} />
                )
              }
              title={
                <>
                  {provider.name}
                  {provider.recommended && <Tag color="blue">推荐</Tag>}
                </>
              }
              description={
                apiKeys[provider.id]
                  ? `sk-****${apiKeys[provider.id].key.slice(-4)}`
                  : '未配置'
              }
            />
          </List.Item>
        )}
      />
      
      <AddApiKeyModal
        visible={showAddModal}
        onClose={() => setShowAddModal(false)}
        onSubmit={(provider, key) => {
          setApiKey(provider, key);
          setShowAddModal(false);
        }}
      />
    </Card>
  );
};
```

**模块4：Prompt编辑器**
```tsx
// components/business/PromptEditor/PromptEditor.tsx
export const PromptEditor: React.FC<PromptEditorProps> = ({
  moduleId,
  promptId,
  onSave,
  readOnly = false
}) => {
  const [content, setContent] = useState('');
  const [variables, setVariables] = useState<string[]>([]);
  
  const { data: prompt, isLoading } = usePrompt(moduleId, promptId);
  
  useEffect(() => {
    if (prompt) {
      setContent(prompt.content);
      setVariables(extractVariables(prompt.content));
    }
  }, [prompt]);
  
  const handleSave = () => {
    onSave({ moduleId, promptId, content });
  };
  
  return (
    <Card title="提示词编辑器">
      <Row gutter={16}>
        <Col span={18}>
          <MonacoEditor
            value={content}
            onChange={setContent}
            language="markdown"
            height="400px"
            options={{ readOnly }}
          />
        </Col>
        
        <Col span={6}>
          <Card size="small" title="变量说明">
            {variables.map((v) => (
              <Tag key={v} color="blue">{`{{${v}}}`}</Tag>
            ))}
          </Card>
          
          <Card size="small" title="模板库" style={{ marginTop: 16 }}>
            <Button block onClick={() => loadTemplate('academic')}>
              学术笔记模板
            </Button>
            <Button block style={{ marginTop: 8 }} onClick={() => loadTemplate('summary')}>
              文献摘要模板
            </Button>
          </Card>
        </Col>
      </Row>
      
      {!readOnly && (
        <div style={{ marginTop: 16, textAlign: 'right' }}>
          <Button style={{ marginRight: 8 }} onClick={() => setContent(prompt?.content || '')}>
            重置
          </Button>
          <Button type="primary" onClick={handleSave}>
            保存模板
          </Button>
        </div>
      )}
    </Card>
  );
};
```

#### Week 8-9：其他功能模块
```
开发清单：
□ 实体识别模块
  - 文本输入/文件上传
  - 实体类型选择
  - 结果可视化展示
  - 导出功能

□ 学术笔记生成
  - 文献信息提取
  - 笔记模板选择
  - Obsidian格式导出

□ 引用格式规范化
  - 参考文献输入
  - 格式选择
  - 批量转换

□ 研究助手模块
  - 对话界面
  - 历史记录
  - 结果导出
```

---

### 阶段C：测试与部署（2周）

#### Week 10：测试
```typescript
// 单元测试示例
// tests/components/FileUploader.test.tsx
describe('FileUploader', () => {
  it('should accept valid files', async () => {
    const onUpload = jest.fn();
    render(<FileUploader accept={['.pdf']} maxSize={10} onUpload={onUpload} />);
    
    const file = new File(['content'], 'test.pdf', { type: 'application/pdf' });
    const input = screen.getByRole('button');
    
    await userEvent.upload(input, file);
    
    expect(onUpload).toHaveBeenCalledWith([file]);
  });
  
  it('should reject invalid files', async () => {
    const onError = jest.fn();
    render(<FileUploader accept={['.pdf']} maxSize={10} onUpload={() => {}} onError={onError} />);
    
    const file = new File(['content'], 'test.txt', { type: 'text/plain' });
    const input = screen.getByRole('button');
    
    await userEvent.upload(input, file);
    
    expect(onError).toHaveBeenCalledWith('不支持的文件格式');
  });
});

// 集成测试示例
// tests/integration/paper-polish.test.tsx
describe('Paper Polish Flow', () => {
  it('should complete polish workflow', async () => {
    render(<PaperPolishPage />);
    
    // Step 1: Upload file
    const file = new File(['content'], 'paper.docx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    });
    await userEvent.upload(screen.getByText(/拖拽文件/), file);
    
    // Step 2: Select strategy
    await userEvent.click(screen.getByText('快速润色'));
    
    // Step 3: Start polish
    await userEvent.click(screen.getByText('开始润色'));
    
    // Verify result
    await waitFor(() => {
      expect(screen.getByText('润色完成')).toBeInTheDocument();
    });
  });
});
```

#### Week 11：部署
```yaml
# 部署配置示例
# docker-compose.yml
version: '3.8'

services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    environment:
      - VITE_API_BASE_URL=http://backend:5000
    depends_on:
      - backend
  
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "5000:5000"
    volumes:
      - ./config:/app/config
      - ./secrets:/app/secrets
```

---

## 📦 四、交付物清单

### 4.1 代码交付物
```
frontend/
├── src/                    # 完整源代码
├── dist/                   # 构建产物
├── tests/                  # 测试文件
│   ├── unit/              # 单元测试
│   ├── integration/       # 集成测试
│   └── e2e/               # 端到端测试
├── docs/                   # 文档
│   ├── API.md             # API文档
│   ├── COMPONENTS.md      # 组件文档
│   └── DEPLOYMENT.md      # 部署文档
└── README.md              # 项目说明
```

### 4.2 文档交付物
```
docs/
├── 用户手册/
│   ├── 快速开始指南.pdf
│   ├── 功能操作手册.pdf
│   └── 常见问题解答.pdf
│
├── 管理员指南/
│   ├── 系统部署手册.pdf
│   ├── 配置管理指南.pdf
│   └── 故障排查手册.pdf
│
└── 开发文档/
    ├── 架构设计文档.pdf
    ├── API接口文档.pdf
    └── 组件开发规范.pdf
```

### 4.3 测试交付物
```
tests/
├── 测试报告/
│   ├── 单元测试报告.pdf
│   ├── 集成测试报告.pdf
│   └── 用户验收测试报告.pdf
│
└── 测试数据/
    ├── 测试用例.xlsx
    └── 测试数据集/
```

---

## 🎯 五、质量保障措施

### 5.1 代码质量
```json
// .eslintrc.json
{
  "extends": [
    "eslint:recommended",
    "plugin:react/recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react-hooks/recommended"
  ],
  "rules": {
    "complexity": ["error", 10],
    "max-lines-per-function": ["error", 100],
    "no-any": "warn"
  }
}
```

### 5.2 测试覆盖率
```
目标覆盖率：
- 语句覆盖率：≥ 70%
- 分支覆盖率：≥ 65%
- 函数覆盖率：≥ 75%
- 行覆盖率：≥ 70%
```

### 5.3 性能指标
```
性能目标：
- 首屏加载时间：< 3秒
- 交互响应时间：< 100ms
- 文件上传速度：支持10MB/s
- 内存占用：< 200MB
```

---

## 📊 六、项目时间表

```
总工期：11周（约3个月）

Week 1-3   ████████░░░░░░░░░░░░  架构搭建与基础组件
Week 4-9   ░░░░░░░░██████████░░  核心功能开发
Week 10-11 ░░░░░░░░░░░░░░░░████  测试与部署

关键里程碑：
✓ Week 3  - 基础组件库完成
✓ Week 7  - 核心功能开发完成50%
✓ Week 9  - 核心功能开发完成100%
✓ Week 11 - 系统上线
```

---

## 🚀 七、风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| 后端API变更 | 高 | 建立API版本管理机制 |
| 用户需求变更 | 中 | 采用敏捷开发，快速迭代 |
| 性能问题 | 中 | 提前进行性能测试和优化 |
| 浏览器兼容性 | 低 | 使用Polyfill和渐进增强 |
| 团队协作问题 | 中 | 建立清晰的代码规范和Review流程 |

---

## 💡 八、后续迭代建议

### V1.1版本（3个月后）
- 添加批量处理功能
- 实现历史记录管理
- 增加数据统计分析
- 优化移动端适配
- 添加快捷键支持

### V1.2版本（6个月后）
- 支持多语言界面（日语/英语）
- 添加协作功能（多人编辑）
- 集成更多LLM服务商
- 实现离线模式
- 添加数据导出API

### V2.0版本（1年后）
- 桌面客户端（Electron）
- 移动端APP（React Native）
- AI辅助配置向导
- 智能推荐系统
- 插件生态系统

### 功能增强路线图

#### 短期优化（1-3个月）
```
□ 性能优化
  - 虚拟滚动优化大列表
  - 图片懒加载
  - 代码分割优化
  
□ 用户体验
  - 添加操作引导
  - 优化错误提示
  - 增加快捷键
  
□ 功能完善
  - 批量文件处理
  - 历史记录管理
  - 模板系统增强
```

#### 中期规划（3-6个月）
```
□ 高级功能
  - 自定义工作流
  - 数据可视化增强
  - 导出格式扩展
  
□ 协作功能
  - 项目共享
  - 评论系统
  - 版本控制
  
□ 集成扩展
  - 第三方存储集成
  - API开放平台
  - Webhook支持
```

#### 长期愿景（6-12个月）
```
□ 智能化
  - AI辅助写作
  - 智能推荐
  - 自动化工作流
  
□ 平台化
  - 插件市场
  - 开发者API
  - 社区生态
  
□ 企业级
  - 团队管理
  - 权限系统
  - 审计日志
```

---

## 📝 九、开发规范

### 9.1 代码规范
```typescript
// 命名规范
// 组件：PascalCase
export const PaperPolishPage: React.FC = () => {};

// 函数：camelCase
const handleSubmit = () => {};

// 常量：UPPER_SNAKE_CASE
const MAX_FILE_SIZE = 10 * 1024 * 1024;

// 文件命名
// 组件文件：PascalCase.tsx
// 工具文件：camelCase.ts
// 样式文件：kebab-case.css
```

### 9.2 Git提交规范
```
feat: 新功能
fix: 修复bug
docs: 文档更新
style: 代码格式调整
refactor: 重构
test: 测试相关
chore: 构建/工具相关

示例：
feat: 添加论文润色模块
fix: 修复文件上传组件的拖拽bug
docs: 更新API文档
```

### 9.3 分支管理
```
main        - 生产分支
develop     - 开发分支
feature/*   - 功能分支
bugfix/*    - 修复分支
release/*   - 发布分支
```

---

## 🔒 十、安全规范

### 10.1 API密钥管理
```typescript
// 前端不直接存储API密钥
// 通过后端代理转发请求

// 错误做法 ❌
const apiKey = 'sk-xxxxx'; // 硬编码

// 正确做法 ✅
const apiKey = useApiStore.getState().getActiveKey();
// 密钥存储在localStorage，并加密处理
```

### 10.2 XSS防护
```typescript
// 使用DOMPurify清理用户输入
import DOMPurify from 'dompurify';

const sanitizeInput = (input: string) => {
  return DOMPurify.sanitize(input);
};
```

### 10.3 CSRF防护
```typescript
// 请求携带CSRF Token
apiClient.interceptors.request.use((config) => {
  const csrfToken = getCsrfToken();
  if (csrfToken) {
    config.headers['X-CSRF-Token'] = csrfToken;
  }
  return config;
});
```

---

## 📚 十一、技术文档索引

### 相关文档
- [后端API文档](docs/ARCHITECTURE_DESIGN.md)
- [工作流程图](WORKFLOW_DIAGRAM.md)
- [技术指南](COMPREHENSIVE_TECHNICAL_GUIDE.md)
- [API配置说明](config/api_config.json)

### 外部资源
- [React官方文档](https://react.dev/)
- [TypeScript手册](https://www.typescriptlang.org/docs/)
- [Ant Design组件库](https://ant.design/)
- [Vite构建工具](https://vitejs.dev/)

---

## 📞 十二、联系方式

如有技术问题或建议，请通过以下方式联系：

- 项目仓库：[GitHub Repository]
- 问题反馈：[GitHub Issues]
- 技术讨论：[GitHub Discussions]

---

**文档版本历史**

| 版本 | 日期 | 修改内容 | 作者 |
|------|------|---------|------|
| 1.0.0 | 2026-04-01 | 初始版本 | AI Assistant |

---

*本文档遵循保密协议，不得泄露敏感信息。API密钥管理严格遵循 `secrets/api_keys.txt` 配置。*
