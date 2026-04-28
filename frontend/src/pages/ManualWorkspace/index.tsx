import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Button,
  Card,
  Form,
  Input,
  List,
  Select,
  Space,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import { taskApi } from '../../api';
import { FileUploader, ModuleHelpPanel, ResultViewer } from '../../components/common';
import { moduleFamilies, taskManagerModules, workspaceModuleCatalog } from '../../data/moduleCatalog';
import { familyDisplayName, moduleDisplayName, moduleHelpDescription, useI18n } from '../../i18n';
import { useTaskStore } from '../../stores';
import type { TaskExecutionPackage } from '../../types/api';
import type { ModuleFamily, TaskCapability, TaskKind, WorkspaceModule } from '../../types';
import WorkflowBuilder from './WorkflowBuilder';

const fallbackCapabilities: TaskCapability[] = taskManagerModules.map((module) => ({
  taskType: module.taskType,
  title: module.title,
  description: module.description,
  presets: module.presets ?? [],
  backends: module.backends,
  providers: ['local', 'ollama', 'qwen', 'openai'],
  privacyLevel: module.privacy === 'local_first' || module.privacy === 'managed_root' ? 'local' : 'mixed',
}));

const taskKindMap: Record<string, TaskKind> = {
  ner: 'ner',
  academic_note: 'note',
  paper_polish: 'polish',
  citation_normalize: 'citation',
  historical_citation: 'citation',
  ocr_correction: 'ocr',
  text_summary: 'analysis',
  reverse_outline: 'writing',
  style_transfer: 'writing',
  virtual_persona: 'agent',
  entity_disambiguation: 'ner',
};

function ManualWorkspacePage() {
  const [form] = Form.useForm();
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [selectedFamily, setSelectedFamily] = useState<ModuleFamily | 'all'>('all');
  const [selectedModuleId, setSelectedModuleId] = useState(workspaceModuleCatalog[0].id);
  const { language, t } = useI18n();
  const startTask = useTaskStore((state) => state.startTask);
  const updateTask = useTaskStore((state) => state.updateTask);
  const appendLog = useTaskStore((state) => state.appendLog);
  const addArtifact = useTaskStore((state) => state.addArtifact);
  const addQualityFlag = useTaskStore((state) => state.addQualityFlag);
  const addReviewItem = useTaskStore((state) => state.addReviewItem);
  const completeTask = useTaskStore((state) => state.completeTask);
  const failTask = useTaskStore((state) => state.failTask);

  const capabilitiesQuery = useQuery({
    queryKey: ['task', 'capabilities'],
    queryFn: taskApi.getCapabilities,
  });

  const capabilities = useMemo(() => {
    const data = capabilitiesQuery.data?.data?.tasks;
    if (Array.isArray(data)) {
      return data.map((value) => normalizeCapability(undefined, value));
    }
    if (data && typeof data === 'object') {
      return Object.entries(data).map(([taskType, value]) => normalizeCapability(taskType, value));
    }
    return fallbackCapabilities;
  }, [capabilitiesQuery.data?.data?.tasks]);

  const selectedCapability = Form.useWatch('taskType', form) ?? capabilities[0]?.taskType;
  const activeCapability = capabilities.find((item) => item.taskType === selectedCapability) ?? capabilities[0];
  const selectedModule = workspaceModuleCatalog.find((item) => item.id === selectedModuleId);
  const visibleModules = workspaceModuleCatalog.filter(
    (module) => selectedFamily === 'all' || module.family === selectedFamily,
  );

  const runTask = async () => {
    if (!activeCapability) {
      message.warning(localizedManualMessage('noCapability', language));
      return;
    }

    const values = form.getFieldsValue();
    const id = startTask({
      title: `${capabilityDisplayName(activeCapability, language)} - ${t('manual')}`,
      kind: taskKindMap[activeCapability.taskType] ?? 'system',
      mode: 'manual',
      provider: values.provider,
      backend: values.backend,
      stage: localizedManualStages(language)[0],
    });

    if (activeCapability.privacyLevel !== 'local') {
      addQualityFlag(id, {
        level: 'warning',
        message: localizedManualMessage('externalProvider', language),
        source: activeCapability.taskType,
      });
    }

    addReviewItem(id, {
      title: localizedManualMessage('reviewTitle', language),
      priority: 'medium',
      status: 'open',
      summary: localizedManualMessage('reviewSummary', language),
    });

    updateTask(id, {
      state: 'running',
      startedAt: Date.now(),
      stage: localizedManualStages(language)[1],
      progress: 18,
    });
    appendLog(id, localizedManualMessage('backendSubmit', language));

    try {
      const payload = {
        task_type: activeCapability.taskType,
        preset: values.preset,
        backend: values.backend,
        provider: values.provider,
        input: buildTaskInput(values, selectedFiles),
      };
      updateTask(id, { stage: localizedManualStages(language)[2], progress: 42 });
      const result = await taskApi.executeTask(payload);
      registerExecutionPackage(id, result, {
        addArtifact,
        addQualityFlag,
        addReviewItem,
      });
      updateTask(id, { stage: localizedManualStages(language)[3], progress: 84 });
      appendLog(id, localizedManualMessage('backendDone', language), result.success ? 'success' : 'warning');

      if (result.success) {
        completeTask(id, result);
      } else {
        failTask(id, result.error || localizedManualMessage('backendFailed', language));
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : localizedManualMessage('backendFailed', language);
      appendLog(id, errorMessage, 'error');
      failTask(id, errorMessage);
    }
  };

  return (
    <div className="page-shell">
      <div className="page-heading">
        <div>
          <div className="page-kicker">{t('manualKicker')}</div>
          <Typography.Title level={2} style={{ margin: 0 }}>
            {t('manual')}
          </Typography.Title>
          <Typography.Paragraph className="muted" style={{ marginTop: 8 }}>
            {t('manualIntro')}
          </Typography.Paragraph>
        </div>
        <Button icon={<ReloadOutlined />} onClick={() => capabilitiesQuery.refetch()}>
          {t('refreshCapabilities')}
        </Button>
      </div>

      <Tabs
        items={[
          {
            key: 'task',
            label: t('taskRun'),
            children: (
              <TaskRunner
                activeCapability={activeCapability}
                capabilities={capabilities}
                form={form}
                onFilesSelected={setSelectedFiles}
                onRun={runTask}
                selectedFiles={selectedFiles}
              />
            ),
          },
          {
            key: 'builder',
            label: t('freeWorkflow'),
            children: <WorkflowBuilder selectedModuleId={selectedModuleId} />,
          },
          {
            key: 'catalog',
            label: t('moduleCatalog'),
            children: (
              <ModuleCatalog
                modules={visibleModules}
                selectedFamily={selectedFamily}
                selectedModule={selectedModule}
                onFamilyChange={setSelectedFamily}
                onSelect={setSelectedModuleId}
              />
            ),
          },
        ]}
      />
    </div>
  );
}

function TaskRunner({
  activeCapability,
  capabilities,
  form,
  onFilesSelected,
  onRun,
  selectedFiles,
}: {
  activeCapability?: TaskCapability;
  capabilities: TaskCapability[];
  form: ReturnType<typeof Form.useForm>[0];
  onFilesSelected: (files: File[]) => void;
  onRun: () => void;
  selectedFiles: File[];
}) {
  const { language, t } = useI18n();
  const activeModule = activeCapability ? moduleForTaskType(activeCapability.taskType) : undefined;
  const capabilityTitle = activeCapability ? capabilityDisplayName(activeCapability, language) : t('capabilityDetail');
  const capabilityDescription = activeModule
    ? moduleHelpDescription(activeModule, language)
    : activeCapability?.description;
  const presets = activeCapability?.presets ?? [];
  const backends = activeCapability?.backends ?? [];
  const providers = activeCapability?.providers ?? [];
  const privacyLevel = activeCapability?.privacyLevel ?? 'mixed';

  return (
    <div className="workbench-grid">
      <Card title={t('taskConfig')}>
        <Form
          form={form}
          initialValues={{
            taskType: fallbackCapabilities[0].taskType,
            preset: fallbackCapabilities[0].presets[0],
            backend: fallbackCapabilities[0].backends[0],
            provider: fallbackCapabilities[0].providers[0],
          }}
          layout="vertical"
        >
          <Form.Item label={t('taskModule')} name="taskType">
            <Select options={capabilities.map((item) => ({ label: capabilityDisplayName(item, language), value: item.taskType }))} />
          </Form.Item>
          <Form.Item label="Preset" name="preset">
            <Select options={presets.map((value) => ({ label: value, value }))} />
          </Form.Item>
          <Form.Item label="Backend" name="backend">
            <Select options={backends.map((value) => ({ label: value, value }))} />
          </Form.Item>
          <Form.Item label="Provider" name="provider">
            <Select options={providers.map((value) => ({ label: value, value }))} />
          </Form.Item>
          <Form.Item label={t('textInput')} name="text">
            <Input.TextArea autoSize={{ minRows: 5, maxRows: 12 }} placeholder={t('textPlaceholder')} />
          </Form.Item>
          <FileUploader accept=".pdf,.png,.jpg,.jpeg,.docx,.txt,.json" multiple onFilesSelected={onFilesSelected} />
          <Button block icon={<PlayCircleOutlined />} onClick={onRun} style={{ marginTop: 16 }} type="primary">
            {t('runTask')}
          </Button>
        </Form>
      </Card>

      <Space direction="vertical" size={16}>
        <Card title={capabilityTitle}>
          <Space direction="vertical" size={12}>
            <Typography.Paragraph>{capabilityDescription}</Typography.Paragraph>
            <Space wrap>
              <Tag color={privacyLevel === 'local' ? 'success' : 'warning'}>{privacyLevel}</Tag>
              {backends.map((backend) => (
                <Tag key={backend}>{backend}</Tag>
              ))}
            </Space>
            <Typography.Text className="muted">
              {t('selectedFiles')}: {selectedFiles.length}
            </Typography.Text>
          </Space>
        </Card>
        {activeModule && <ModuleHelpPanel compact module={activeModule} />}
        <ResultViewer
          result={{ selectedFiles: selectedFiles.map((file) => file.name), activeCapability }}
          tags={['task_manager', 'package-first', 'manual']}
        />
      </Space>
    </div>
  );
}

function ModuleCatalog({
  modules,
  onFamilyChange,
  onSelect,
  selectedFamily,
  selectedModule,
}: {
  modules: WorkspaceModule[];
  onFamilyChange: (family: ModuleFamily | 'all') => void;
  onSelect: (moduleId: string) => void;
  selectedFamily: ModuleFamily | 'all';
  selectedModule?: WorkspaceModule;
}) {
  const { language, t } = useI18n();

  return (
    <div className="workbench-grid">
      <Card title={t('moduleInventory')}>
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Select
            value={selectedFamily}
            onChange={onFamilyChange}
            options={[
              { label: t('allModules'), value: 'all' },
              ...moduleFamilies.map((family) => ({
                label: familyDisplayName(family.value, language),
                value: family.value,
              })),
            ]}
            style={{ width: '100%' }}
          />
          <List
            dataSource={modules}
            renderItem={(module) => (
              <List.Item onClick={() => onSelect(module.id)} style={{ cursor: 'pointer' }}>
                <List.Item.Meta
                  title={
                    <Space wrap>
                      <Typography.Text strong>{moduleDisplayName(module, language)}</Typography.Text>
                      <Tag>{familyDisplayName(module.family, language)}</Tag>
                      <Tag color={module.executionTarget === 'task_manager' ? 'success' : 'processing'}>
                        {module.executionTarget}
                      </Tag>
                    </Space>
                  }
                  description={moduleHelpDescription(module, language)}
                />
              </List.Item>
            )}
          />
        </Space>
      </Card>

      <Card title={selectedModule ? moduleDisplayName(selectedModule, language) : t('selectModule')}>
        {selectedModule && (
          <Space direction="vertical" size={14} style={{ width: '100%' }}>
            <Typography.Paragraph>{moduleHelpDescription(selectedModule, language)}</Typography.Paragraph>
            <Typography.Text code>{selectedModule.modulePath}</Typography.Text>
            <Space wrap>
              <Tag color="blue">{familyDisplayName(selectedModule.family, language)}</Tag>
              <Tag>{selectedModule.executionTarget}</Tag>
              <Tag color={selectedModule.reviewRequired ? 'warning' : 'success'}>
                {selectedModule.reviewRequired ? t('needsReview') : t('unchecked')}
              </Tag>
              <Tag>{selectedModule.privacy}</Tag>
            </Space>
            <ModuleFields title={t('input')} values={selectedModule.inputs} />
            <ModuleFields title={t('output')} values={selectedModule.outputs} />
            <ModuleFields title={t('packageType')} values={selectedModule.packageTypes} />
            <ModuleFields title={t('backend')} values={selectedModule.backends} />
            <ModuleHelpPanel compact module={selectedModule} />
          </Space>
        )}
      </Card>
    </div>
  );
}

function moduleForTaskType(taskType: string) {
  return workspaceModuleCatalog.find((module) => module.taskType === taskType);
}

function normalizeCapability(taskTypeHint: string | undefined, value: unknown): TaskCapability {
  const raw = isRecord(value) ? value : {};
  const taskType = String(raw.taskType ?? raw.task_type ?? raw.name ?? taskTypeHint ?? 'unknown_task');
  const module = moduleForTaskType(taskType);
  const backends = normalizeOptionNames(raw.backends ?? raw.backend_options ?? getNested(raw, 'capabilities', 'backend_options'));
  const providers = normalizeOptionNames(raw.providers ?? raw.provider_options);
  const presets = normalizeOptionNames(raw.presets ?? raw.preset_details);

  return {
    taskType,
    title: String(raw.title ?? raw.label ?? raw.name ?? module?.title ?? taskType),
    description: String(raw.description ?? module?.description ?? ''),
    presets: presets.length > 0 ? presets : module?.presets ?? [],
    backends: backends.length > 0 ? backends : module?.backends ?? ['script'],
    providers: providers.length > 0 ? providers : ['local', 'qwen', 'openai', 'ollama'],
    privacyLevel: inferPrivacyLevel(raw, module),
  };
}

function normalizeOptionNames(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => {
      if (typeof item === 'string') {
        return item;
      }
      if (isRecord(item)) {
        return item.name ?? item.id ?? item.value ?? item.label;
      }
      return undefined;
    })
    .filter((item): item is string => typeof item === 'string' && item.length > 0);
}

function inferPrivacyLevel(raw: Record<string, unknown>, module?: WorkspaceModule): TaskCapability['privacyLevel'] {
  if (module?.privacy === 'local_first' || module?.privacy === 'managed_root') {
    return 'local';
  }
  if (module?.privacy === 'external_optional') {
    return 'external';
  }

  const backends = normalizeOptionNames(raw.backends ?? raw.backend_options);
  return backends.some((backend) => ['llm_api', 'mcp', 'skill'].includes(backend)) ? 'mixed' : 'local';
}

function buildTaskInput(values: Record<string, unknown>, files: File[]) {
  const text = typeof values.text === 'string' ? values.text : '';
  const input: Record<string, unknown> = {
    text,
    note: text,
    language: 'zh',
    max_length: 300,
  };

  if (files.length > 0) {
    input.selected_files = files.map((file) => ({
      name: file.name,
      size: file.size,
      type: file.type,
    }));
  }

  return input;
}

function registerExecutionPackage(
  taskId: string,
  result: TaskExecutionPackage,
  actions: {
    addArtifact: ReturnType<typeof useTaskStore.getState>['addArtifact'];
    addQualityFlag: ReturnType<typeof useTaskStore.getState>['addQualityFlag'];
    addReviewItem: ReturnType<typeof useTaskStore.getState>['addReviewItem'];
  },
) {
  actions.addArtifact(taskId, {
    name: `${result.task_type ?? 'task'} execution package`,
    type: result.package_type ?? result.type ?? 'task_execution',
    path: result.created_at ? `backend:${result.created_at}` : undefined,
  });

  const flags = Array.isArray(result.quality_flags) ? result.quality_flags : result.metadata?.quality_flags ?? [];
  flags.forEach((flag) => {
    const message = typeof flag === 'string' ? flag : flag.message;
    actions.addQualityFlag(taskId, {
      level: typeof flag === 'string' ? 'warning' : flag.level ?? 'warning',
      message,
      source: result.task_type,
    });
  });

  if (result.needs_review || result.metadata?.needs_review) {
    actions.addReviewItem(taskId, {
      title: '后端标记需要人工复核',
      priority: 'high',
      status: 'open',
      summary: `confidence: ${result.confidence ?? result.metadata?.confidence ?? 0}`,
    });
  }
}

function isRecord(value: unknown): value is Record<string, any> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function getNested(source: Record<string, unknown>, ...keys: string[]) {
  let current: unknown = source;
  for (const key of keys) {
    if (!isRecord(current)) {
      return undefined;
    }
    current = current[key];
  }
  return current;
}

function capabilityDisplayName(capability: TaskCapability, language: ReturnType<typeof useI18n>['language']) {
  const module = moduleForTaskType(capability.taskType);
  return module ? moduleDisplayName(module, language) : capability.title;
}

function localizedManualStages(language: ReturnType<typeof useI18n>['language']) {
  if (language === 'en-US') {
    return ['Read configuration', 'Prepare input', 'Call unified task entry', 'Register package', 'Write artifact summary', 'Wait for human review'];
  }
  if (language === 'ja-JP') {
    return ['設定を読み込み', '入力を準備', '統一タスク入口を呼び出し', 'packageを登録', '成果物要約を書き込み', '人間レビュー待ち'];
  }
  return ['读取配置', '准备输入', '调用统一任务入口', '登记 package', '写入产物摘要', '等待人工复核'];
}

function localizedManualMessage(
  key:
    | 'noCapability'
    | 'externalProvider'
    | 'reviewTitle'
    | 'reviewSummary'
    | 'backendSubmit'
    | 'backendDone'
    | 'backendFailed',
  language: ReturnType<typeof useI18n>['language'],
) {
  const messages = {
    noCapability: {
      'zh-CN': '没有可运行的任务能力。',
      'en-US': 'No runnable capability is available.',
      'ja-JP': '実行可能な能力がありません。',
    },
    externalProvider: {
      'zh-CN': '该任务可能使用外部 provider，运行前应确认材料脱敏和授权范围。',
      'en-US': 'This task may use an external provider. Confirm de-identification and authorization before running.',
      'ja-JP': 'このタスクは外部providerを使う可能性があります。実行前に匿名化と権限範囲を確認してください。',
    },
    reviewTitle: {
      'zh-CN': '人工复核输出摘要',
      'en-US': 'Review output summary',
      'ja-JP': '出力要約をレビュー',
    },
    reviewSummary: {
      'zh-CN': '任务完成后检查 confidence、needs_review、quality_flags 与产物路径。',
      'en-US': 'After completion, check confidence, needs_review, quality_flags, and artifact paths.',
      'ja-JP': '完了後に confidence、needs_review、quality_flags、アーティファクトパスを確認します。',
    },
    backendSubmit: {
      'zh-CN': '已提交到后端统一任务入口 /api/tasks/execute。',
      'en-US': 'Submitted to the backend unified task endpoint /api/tasks/execute.',
      'ja-JP': 'バックエンド統一タスク入口 /api/tasks/execute へ送信しました。',
    },
    backendDone: {
      'zh-CN': '后端返回任务执行 package，已登记到任务中心。',
      'en-US': 'The backend returned a task execution package and it has been registered.',
      'ja-JP': 'バックエンドがタスク実行packageを返し、タスクセンターへ登録しました。',
    },
    backendFailed: {
      'zh-CN': '后端任务执行失败。',
      'en-US': 'Backend task execution failed.',
      'ja-JP': 'バックエンドのタスク実行に失敗しました。',
    },
  };
  return messages[key][language];
}

function ModuleFields({ title, values }: { title: string; values: string[] }) {
  return (
    <Space direction="vertical" size={6}>
      <Typography.Text strong>{title}</Typography.Text>
      <Space wrap>
        {values.map((value) => (
          <Tag key={value}>{value}</Tag>
        ))}
      </Space>
    </Space>
  );
}

export default ManualWorkspacePage;
