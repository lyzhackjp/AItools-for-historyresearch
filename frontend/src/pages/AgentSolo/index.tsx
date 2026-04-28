import { useMemo, useState } from 'react';
import { Button, Card, Checkbox, Form, Input, Select, Space, Steps, Tabs, Tag, Timeline, Typography } from 'antd';
import { CheckOutlined, PlayCircleOutlined, RobotOutlined } from '@ant-design/icons';
import { useI18n } from '../../i18n';
import { useTaskStore } from '../../stores';
import type { AgentGoal, AgentPlan, AgentPlanStep } from '../../types';
import SkillConfigurator from './SkillConfigurator';

const connectorOptions = [
  { label: 'OpenClaw connector', value: 'openclaw' },
  { label: 'Hermes connector', value: 'hermes' },
  { label: 'Codex skill connector', value: 'codex-skill' },
  { label: 'MCP / vibe coding connector', value: 'mcp-vibe' },
];

const backendOptions = ['script', 'local_llm', 'llm_api', 'mcp', 'skill', 'hybrid'];

function AgentSoloPage() {
  const [form] = Form.useForm<AgentGoal & { connectorId: string }>();
  const [plan, setPlan] = useState<AgentPlan>();
  const { language, t } = useI18n();
  const startTask = useTaskStore((state) => state.startTask);
  const runDemoProgress = useTaskStore((state) => state.runDemoProgress);
  const addQualityFlag = useTaskStore((state) => state.addQualityFlag);
  const addReviewItem = useTaskStore((state) => state.addReviewItem);
  const approvedCount = useMemo(() => plan?.steps.filter((step) => step.status === 'approved').length ?? 0, [plan]);

  const proposePlan = () => {
    const values = form.getFieldsValue();
    setPlan(createAgentPlan(values, language));
  };

  const approveAll = () => {
    setPlan((current) =>
      current ? { ...current, steps: current.steps.map((step) => ({ ...step, status: 'approved' })) } : current,
    );
  };

  const startRun = () => {
    const currentPlan = plan ?? createAgentPlan(form.getFieldsValue(), language);
    if (!plan) {
      setPlan(currentPlan);
    }

    const id = startTask({
      title: `${currentPlan.goal.topic} - agent solo`,
      kind: 'agent',
      mode: 'agent',
      provider: currentPlan.connectorId,
      backend: currentPlan.goal.allowedBackends.join(', '),
      stage: localizedSoloStages(language)[0],
    });

    addQualityFlag(id, {
      level: 'info',
      message:
        language === 'en-US'
          ? 'Solo mode uses human confirmation points before external search, downloads, vault writes, and paid APIs.'
          : language === 'ja-JP'
            ? 'soloモードでは、外部検索、ダウンロード、vault書き込み、有料APIの前に人間確認を置きます。'
            : 'solo 模式启用人工确认点：外部检索、下载、写入 vault 和付费 API 前应暂停确认。',
      source: currentPlan.connectorId,
    });
    addReviewItem(id, {
      title:
        language === 'en-US'
          ? 'Confirm agent plan and permissions'
          : language === 'ja-JP'
            ? 'agent計画と権限を確認'
            : '确认 agent 计划与权限',
      priority: 'high',
      status: 'open',
      summary:
        language === 'en-US'
          ? 'Check connector, allowed backends, material scope, module scope, and expected output.'
          : language === 'ja-JP'
            ? 'connector、allowed backends、資料範囲、モジュール範囲、期待成果物を確認します。'
            : '检查 connector、allowed backends、材料范围、模块范围和期望产物。',
    });
    runDemoProgress(id, localizedSoloStages(language));
  };

  return (
    <div className="page-shell">
      <div className="page-heading">
        <div>
          <div className="page-kicker">{t('agentSoloKicker')}</div>
          <Typography.Title level={2} style={{ margin: 0 }}>
            {t('agentSolo')}
          </Typography.Title>
          <Typography.Paragraph className="muted" style={{ marginTop: 8 }}>
            {t('agentSoloIntro')}
          </Typography.Paragraph>
        </div>
        <Space>
          {localizedSoloTags(language).map((tag) => (
            <Tag color={tag.color} key={tag.label}>
              {tag.label}
            </Tag>
          ))}
        </Space>
      </div>

      <Tabs
        items={[
          {
            key: 'run',
            label: t('soloPlanner'),
            children: (
              <SoloRunPlanner
                approvedCount={approvedCount}
                form={form}
                onApproveAll={approveAll}
                onProposePlan={proposePlan}
                onStartRun={startRun}
                plan={plan}
              />
            ),
          },
          {
            key: 'skill',
            label: t('skillConfig'),
            children: <SkillConfigurator />,
          },
        ]}
      />
    </div>
  );
}

function SoloRunPlanner({
  approvedCount,
  form,
  onApproveAll,
  onProposePlan,
  onStartRun,
  plan,
}: {
  approvedCount: number;
  form: ReturnType<typeof Form.useForm<AgentGoal & { connectorId: string }>>[0];
  onApproveAll: () => void;
  onProposePlan: () => void;
  onStartRun: () => void;
  plan?: AgentPlan;
}) {
  const { language, t } = useI18n();

  return (
    <div className="workbench-grid">
      <Card title={t('goalAndPermission')}>
        <Form
          form={form}
          initialValues={{
            connectorId: 'codex-skill',
            allowedBackends: ['script', 'local_llm', 'skill'],
            timeBudget: language === 'en-US' ? '30 minutes' : language === 'ja-JP' ? '30分' : '30 分钟',
          }}
          layout="vertical"
        >
          <Form.Item label="Agent connector" name="connectorId">
            <Select options={connectorOptions} />
          </Form.Item>
          <Form.Item label={t('researchGoal')} name="topic">
            <Input placeholder={localizedPlannerPlaceholders(language).topic} />
          </Form.Item>
          <Form.Item label={t('materialScope')} name="materialScope">
            <Input.TextArea autoSize={{ minRows: 3, maxRows: 6 }} placeholder={localizedPlannerPlaceholders(language).scope} />
          </Form.Item>
          <Form.Item label={t('expectedOutput')} name="expectedOutput">
            <Input placeholder={localizedPlannerPlaceholders(language).output} />
          </Form.Item>
          <Form.Item label={t('timeBudget')} name="timeBudget">
            <Input />
          </Form.Item>
          <Form.Item label={t('backend')} name="allowedBackends">
            <Checkbox.Group options={backendOptions.map((value) => ({ label: value, value }))} />
          </Form.Item>
          <Space>
            <Button icon={<RobotOutlined />} onClick={onProposePlan}>
              {t('proposePlan')}
            </Button>
            <Button disabled={!plan} icon={<CheckOutlined />} onClick={onApproveAll}>
              {t('approvePlan')}
            </Button>
            <Button icon={<PlayCircleOutlined />} onClick={onStartRun} type="primary">
              {t('startSolo')}
            </Button>
          </Space>
        </Form>
      </Card>
      <SoloObservationPanel approvedCount={approvedCount} plan={plan} />
    </div>
  );
}

function SoloObservationPanel({ approvedCount, plan }: { approvedCount: number; plan?: AgentPlan }) {
  const { language, t } = useI18n();

  return (
    <Space direction="vertical" size={16}>
      <Card title={t('planPanel')}>
        {plan ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Typography.Text className="muted">
              Connector: {plan.connectorId} · {t('connectorApproved')} {approvedCount}/{plan.steps.length}
            </Typography.Text>
            <Steps
              direction="vertical"
              items={plan.steps.map((step) => ({
                title: step.title,
                description: `${step.owner === 'user' ? userOwnerLabel(language) : agentOwnerLabel(language)} · ${step.description}`,
                status: step.status === 'approved' ? 'finish' : 'wait',
              }))}
            />
          </Space>
        ) : (
          <Typography.Text className="muted">
            {language === 'en-US' ? 'Fill in the goal to generate a plan.' : language === 'ja-JP' ? '目標を入力すると計画を生成できます。' : '填写目标后生成计划。'}
          </Typography.Text>
        )}
      </Card>

      <Card title={t('observePanel')}>
        <Timeline
          items={localizedObservationItems(language).map((children) => ({ children }))}
        />
      </Card>
    </Space>
  );
}

function createAgentPlan(
  values: Partial<AgentGoal & { connectorId: string }>,
  language: ReturnType<typeof useI18n>['language'],
): AgentPlan {
  const defaults = localizedPlanDefaults(language);
  const goal: AgentGoal = {
    topic: values.topic || defaults.topic,
    materialScope: values.materialScope || defaults.materialScope,
    expectedOutput: values.expectedOutput || defaults.expectedOutput,
    timeBudget: values.timeBudget || defaults.timeBudget,
    allowedBackends: values.allowedBackends || ['script', 'local_llm'],
  };
  return {
    id: `plan-${Date.now()}`,
    connectorId: values.connectorId || 'codex-skill',
    goal,
    steps: createDefaultSteps(language),
    createdAt: Date.now(),
  };
}

function localizedPlanDefaults(language: ReturnType<typeof useI18n>['language']) {
  if (language === 'en-US') {
    return {
      topic: 'Untitled research topic',
      materialScope: 'Current workspace materials',
      expectedOutput: 'Research summary and reviewable artifacts',
      timeBudget: '30 minutes',
    };
  }
  if (language === 'ja-JP') {
    return {
      topic: '無題の研究テーマ',
      materialScope: '現在の作業区資料',
      expectedOutput: '研究要約とレビュー可能な成果物',
      timeBudget: '30分',
    };
  }
  return {
    topic: '未命名研究主题',
    materialScope: '当前工作区材料',
    expectedOutput: '研究摘要与可复核产物',
    timeBudget: '30 分钟',
  };
}

function createDefaultSteps(language: ReturnType<typeof useI18n>['language']): AgentPlanStep[] {
  if (language === 'en-US') {
    return [
      { id: 'scope', title: 'Read goal and boundaries', owner: 'agent', status: 'approved', description: 'Confirm topic, material scope, privacy boundary, and allowed backends.' },
      { id: 'capabilities', title: 'Discover workspace capabilities', owner: 'agent', status: 'approved', description: 'Read task registry, workflow stages, and providers.' },
      { id: 'skill', title: 'Load skill configuration', owner: 'agent', status: 'planned', description: 'Limit callable modules and permissions according to user configuration.' },
      { id: 'execute', title: 'Run stage tasks', owner: 'agent', status: 'planned', description: 'Call OCR, NER, citation, writing, or workflow nodes.' },
      { id: 'review', title: 'Register review items', owner: 'user', status: 'planned', description: 'Confirm quality flags, needs_review, and artifacts.' },
      { id: 'handoff', title: 'Generate handoff summary', owner: 'agent', status: 'planned', description: 'Output next steps, artifacts, and recovery paths.' },
    ];
  }
  if (language === 'ja-JP') {
    return [
      { id: 'scope', title: '目標と境界を読む', owner: 'agent', status: 'approved', description: '研究テーマ、資料範囲、プライバシー境界、許可backendを確認します。' },
      { id: 'capabilities', title: '作業区能力を発見', owner: 'agent', status: 'approved', description: 'task registry、workflow段階、providerを読みます。' },
      { id: 'skill', title: 'skill設定を読み込む', owner: 'agent', status: 'planned', description: 'ユーザー設定に従い、呼び出せるモジュールと権限を制限します。' },
      { id: 'execute', title: '段階タスクを実行', owner: 'agent', status: 'planned', description: 'OCR、NER、引用、執筆、workflowノードを呼び出します。' },
      { id: 'review', title: 'レビュー項目を登録', owner: 'user', status: 'planned', description: 'quality flags、needs_review、artifactsを確認します。' },
      { id: 'handoff', title: '引き継ぎ要約を生成', owner: 'agent', status: 'planned', description: '次の手順、成果物、失敗時の復旧経路を出力します。' },
    ];
  }
  return [
    { id: 'scope', title: '读取目标与边界', owner: 'agent', status: 'approved', description: '确认研究主题、材料范围、隐私边界和允许后端。' },
    { id: 'capabilities', title: '发现工作区能力', owner: 'agent', status: 'approved', description: '读取 task registry、workflow 阶段和 provider。' },
    { id: 'skill', title: '加载 skill 配置', owner: 'agent', status: 'planned', description: '按用户配置限制可调用模块和权限。' },
    { id: 'execute', title: '执行阶段任务', owner: 'agent', status: 'planned', description: '调用 OCR、NER、引用、写作或 workflow 节点。' },
    { id: 'review', title: '登记复核项', owner: 'user', status: 'planned', description: '对 quality flags、needs_review 和 artifacts 进行确认。' },
    { id: 'handoff', title: '生成交接摘要', owner: 'agent', status: 'planned', description: '输出下一步建议、产物和失败恢复路径。' },
  ];
}

function localizedSoloTags(language: ReturnType<typeof useI18n>['language']) {
  if (language === 'en-US') {
    return [
      { label: 'Observable', color: 'blue' },
      { label: 'Authorization required', color: 'warning' },
      { label: 'Reviewable', color: 'success' },
    ];
  }
  if (language === 'ja-JP') {
    return [
      { label: '観察可能', color: 'blue' },
      { label: '承認必要', color: 'warning' },
      { label: 'レビュー可能', color: 'success' },
    ];
  }
  return [
    { label: '可观察', color: 'blue' },
    { label: '需授权', color: 'warning' },
    { label: '可复核', color: 'success' },
  ];
}

function localizedPlannerPlaceholders(language: ReturnType<typeof useI18n>['language']) {
  if (language === 'en-US') {
    return {
      topic: 'For example: organize a batch of modern Japanese biography materials',
      scope: 'Describe folders, PDFs, note vaults, or the current workspace material scope.',
      output: 'For example: OCR summary, entity table, citation verification report, Obsidian notes',
    };
  }
  if (language === 'ja-JP') {
    return {
      topic: '例：日本近代人物伝記資料の一群を整理',
      scope: 'フォルダ、PDF、ノートvault、または現在の作業区資料範囲を説明します。',
      output: '例：OCR要約、エンティティ表、引用検証レポート、Obsidianノート',
    };
  }
  return {
    topic: '例如：整理某一批日本近代人物传记材料',
    scope: '说明文件夹、PDF、笔记库或当前工作区材料范围。',
    output: '例如：OCR 摘要、实体表、引用核验报告、Obsidian 笔记',
  };
}

function localizedSoloStages(language: ReturnType<typeof useI18n>['language']) {
  if (language === 'en-US') {
    return ['Read goal', 'Discover capabilities', 'Propose plan', 'Execute tasks', 'Register artifacts', 'Wait for review', 'Generate handoff summary'];
  }
  if (language === 'ja-JP') {
    return ['目標を読み込み', '能力を発見', '計画を生成', 'タスクを実行', '成果物を登録', 'レビュー待ち', '引き継ぎ要約を生成'];
  }
  return ['读取目标', '发现能力', '生成计划', '执行任务', '登记产物', '等待复核', '生成交接摘要'];
}

function localizedObservationItems(language: ReturnType<typeof useI18n>['language']) {
  if (language === 'en-US') {
    return [
      'The agent reads the goal, skill configuration, and permission boundaries.',
      'The agent discovers the task registry, workflow stages, package modules, and providers.',
      'All execution actions are routed into the unified task center.',
      'External access, downloads, writes, and paid APIs pause for confirmation.',
    ];
  }
  if (language === 'ja-JP') {
    return [
      'agent が目標、skill設定、権限境界を読み込みます。',
      'agent が task registry、workflow段階、packageモジュール、providerを発見します。',
      'すべての実行動作は統一タスクセンターへ送られます。',
      '外部アクセス、ダウンロード、書き込み、有料APIの前に確認で停止します。',
    ];
  }
  return [
    'agent 读取目标、skill 配置和权限边界。',
    'agent 发现 task registry、workflow、package 模块与 provider。',
    '所有执行动作进入统一任务中心。',
    '外部访问、下载、写入和付费 API 前暂停确认。',
  ];
}

function userOwnerLabel(language: ReturnType<typeof useI18n>['language']) {
  return language === 'en-US' ? 'User confirmation' : language === 'ja-JP' ? 'ユーザー確認' : '用户确认';
}

function agentOwnerLabel(language: ReturnType<typeof useI18n>['language']) {
  return language === 'en-US' ? 'Agent execution' : language === 'ja-JP' ? 'agent実行' : 'agent 执行';
}

export default AgentSoloPage;
