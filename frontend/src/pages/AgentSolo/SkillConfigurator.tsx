import { useMemo, useState } from 'react';
import { Button, Card, Checkbox, Form, Input, Select, Space, Tag, Typography } from 'antd';
import { SaveOutlined, ToolOutlined } from '@ant-design/icons';
import { ModuleHelpPanel } from '../../components/common';
import { moduleFamilies, workspaceModuleCatalog } from '../../data/moduleCatalog';
import { familyDisplayName, moduleDisplayName, moduleHelpDescription, useI18n } from '../../i18n';
import { useTaskStore } from '../../stores';
import type { AgentSkillConfig, ModuleFamily } from '../../types';

const backendOptions = ['script', 'local_llm', 'llm_api', 'skill', 'mcp', 'hybrid'];

function SkillConfigurator() {
  const { language, t } = useI18n();
  const [family, setFamily] = useState<ModuleFamily | 'all'>('all');
  const [selectedModuleIds, setSelectedModuleIds] = useState<string[]>([
    'task.ner',
    'task.academic_note',
    'task.paper_polish',
  ]);
  const [permissions, setPermissions] = useState({
    readWorkspace: true,
    writeArtifacts: true,
    externalSearch: false,
    downloadSources: false,
    usePaidApi: false,
    writeVault: false,
  });
  const [allowedBackends, setAllowedBackends] = useState(['script', 'local_llm', 'skill']);
  const [systemPrompt, setSystemPrompt] = useState(
    'You are a workspace-safe historical research agent. Prefer local/package-first execution and ask before external or write actions.',
  );
  const startTask = useTaskStore((state) => state.startTask);
  const runDemoProgress = useTaskStore((state) => state.runDemoProgress);
  const addReviewItem = useTaskStore((state) => state.addReviewItem);

  const modules = useMemo(
    () => workspaceModuleCatalog.filter((module) => family === 'all' || module.family === family),
    [family],
  );
  const selectedModules = useMemo(
    () => workspaceModuleCatalog.filter((module) => selectedModuleIds.includes(module.id)),
    [selectedModuleIds],
  );
  const config = useMemo(
    () => buildSkillConfig(selectedModuleIds, allowedBackends, permissions, systemPrompt, language),
    [allowedBackends, language, permissions, selectedModuleIds, systemPrompt],
  );

  const saveSkillConfig = () => {
    const id = startTask({
      title: `${config.name} - ${t('skillConfig')}`,
      kind: 'agent',
      mode: 'agent',
      backend: 'workspace_skill',
      provider: 'codex-skill',
      stage: localizedSkillStages(language)[0],
    });
    addReviewItem(id, {
      title:
        language === 'en-US'
          ? 'Review skill permissions and module scope'
          : language === 'ja-JP'
            ? 'skill権限とモジュール範囲をレビュー'
            : '复核 skill 权限与模块范围',
      priority: 'high',
      status: 'open',
      summary:
        language === 'en-US'
          ? 'Confirm module list, external access, write permissions, and acceptance checklist.'
          : language === 'ja-JP'
            ? 'モジュール一覧、外部アクセス、書き込み権限、acceptance checklistを確認します。'
            : '确认模块清单、外部访问权限、写入权限和 acceptance checklist。',
    });
    runDemoProgress(id, localizedSkillStages(language));
  };

  return (
    <div className="workbench-grid">
      <Card
        title={
          <Space>
            <ToolOutlined />
            {t('skillConfigTitle')}
          </Space>
        }
        extra={
          <Button icon={<SaveOutlined />} onClick={saveSkillConfig} type="primary">
            {language === 'en-US' ? 'Save as task' : language === 'ja-JP' ? 'タスクとして保存' : '保存为任务'}
          </Button>
        }
      >
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Select
            value={family}
            onChange={setFamily}
            options={[
              { label: t('allModules'), value: 'all' },
              ...moduleFamilies.map((item) => ({
                label: familyDisplayName(item.value, language),
                value: item.value,
              })),
            ]}
            style={{ width: '100%' }}
          />
          <Checkbox.Group value={selectedModuleIds} onChange={(values) => setSelectedModuleIds(values as string[])}>
            <Space direction="vertical">
              {modules.map((module) => (
                <Checkbox key={module.id} value={module.id}>
                  <Space wrap>
                    <Typography.Text>{moduleDisplayName(module, language)}</Typography.Text>
                    <Tag>{module.executionTarget}</Tag>
                    <Tag>{module.privacy}</Tag>
                  </Space>
                  <Typography.Text className="muted" style={{ display: 'block', marginTop: 2 }}>
                    {moduleHelpDescription(module, language)}
                  </Typography.Text>
                </Checkbox>
              ))}
            </Space>
          </Checkbox.Group>
          <Form layout="vertical">
            <Form.Item label={t('backend')}>
              <Checkbox.Group
                options={backendOptions.map((value) => ({ label: value, value }))}
                value={allowedBackends}
                onChange={(values) => setAllowedBackends(values as string[])}
              />
            </Form.Item>
            <Form.Item label={language === 'en-US' ? 'System prompt' : language === 'ja-JP' ? 'システムプロンプト' : '系统提示词'}>
              <Input.TextArea
                autoSize={{ minRows: 4, maxRows: 8 }}
                value={systemPrompt}
                onChange={(event) => setSystemPrompt(event.target.value)}
              />
            </Form.Item>
          </Form>
          <PermissionSwitches permissions={permissions} onChange={setPermissions} />
        </Space>
      </Card>

      <Space direction="vertical" size={16}>
        {selectedModules[0] && <ModuleHelpPanel compact module={selectedModules[0]} />}
        <Card title={t('skillDraft')}>
          <pre className="task-log">{config.generatedSkillMarkdown}</pre>
        </Card>
        <Card title={t('skillJson')}>
          <pre className="task-log">{JSON.stringify(config, null, 2)}</pre>
        </Card>
      </Space>
    </div>
  );
}

function PermissionSwitches({
  onChange,
  permissions,
}: {
  onChange: (next: AgentSkillConfig['permissions']) => void;
  permissions: AgentSkillConfig['permissions'];
}) {
  const { language } = useI18n();
  const items: Array<[keyof AgentSkillConfig['permissions'], string]> = [
    ['readWorkspace', permissionLabel('readWorkspace', language)],
    ['writeArtifacts', permissionLabel('writeArtifacts', language)],
    ['externalSearch', permissionLabel('externalSearch', language)],
    ['downloadSources', permissionLabel('downloadSources', language)],
    ['usePaidApi', permissionLabel('usePaidApi', language)],
    ['writeVault', permissionLabel('writeVault', language)],
  ];

  return (
    <Space direction="vertical">
      <Typography.Text strong>{language === 'en-US' ? 'Permission boundary' : language === 'ja-JP' ? '権限境界' : '权限边界'}</Typography.Text>
      <Space wrap>
        {items.map(([key, label]) => (
          <Checkbox
            key={key}
            checked={permissions[key]}
            onChange={(event) => onChange({ ...permissions, [key]: event.target.checked })}
          >
            {label}
          </Checkbox>
        ))}
      </Space>
    </Space>
  );
}

function buildSkillConfig(
  selectedModuleIds: string[],
  allowedBackends: string[],
  permissions: AgentSkillConfig['permissions'],
  systemPrompt: string,
  language: ReturnType<typeof useI18n>['language'],
): AgentSkillConfig {
  const selectedModules = workspaceModuleCatalog.filter((module) => selectedModuleIds.includes(module.id));
  const moduleLines = selectedModules.map(
    (module) => `- ${moduleDisplayName(module, language)}: ${module.taskType} via ${module.executionTarget}; outputs ${module.packageTypes.join(', ')}`,
  );
  const permissionLines = Object.entries(permissions).map(([key, value]) => `- ${key}: ${value ? 'allowed' : 'ask first'}`);
  const defaultChecklist = localizedSkillChecklist(language);
  const markdown = [
    '---',
    'name: configurable-historyresearch-agent',
    'description: Configurable workspace skill for historical research module orchestration.',
    '---',
    '',
    '# Configurable History Research Agent',
    '',
    '## System Prompt',
    systemPrompt,
    '',
    '## Allowed Backends',
    ...allowedBackends.map((backend) => `- ${backend}`),
    '',
    '## Module Scope',
    ...moduleLines,
    '',
    '## Permissions',
    ...permissionLines,
    '',
    '## Acceptance Checklist',
    ...defaultChecklist.map((item) => `- ${item}`),
  ].join('\n');

  return {
    id: 'configurable-historyresearch-agent',
    name: 'configurable-historyresearch-agent',
    description: 'Configurable workspace skill for module orchestration.',
    selectedModuleIds,
    allowedBackends,
    permissions,
    systemPrompt,
    acceptanceChecklist: defaultChecklist,
    generatedSkillMarkdown: markdown,
    updatedAt: Date.now(),
  };
}

function localizedSkillChecklist(language: ReturnType<typeof useI18n>['language']) {
  if (language === 'en-US') {
    return [
      'Confirm no secrets are read or exposed',
      'Prefer TaskManager registry and ArtifactManager capability snapshots',
      'Ask before external search, downloads, vault writes, or paid APIs',
      'Collect every result as package/envelope and register quality_flags plus review queue',
    ];
  }
  if (language === 'ja-JP') {
    return [
      'secretsを読んだり露出したりしていないことを確認',
      'TaskManager registry と ArtifactManager 能力スナップショットを優先',
      '外部検索、ダウンロード、vault書き込み、有料APIの前に確認',
      'すべての結果をpackage/envelopeとして回収し、quality_flagsとreview queueを登録',
    ];
  }
  return [
    '确认未读取或暴露 secrets',
    '优先读取 TaskManager registry 和 ArtifactManager 能力快照',
    '外部检索、下载、写入 vault、付费 API 前请求确认',
    '所有结果回收为 package/envelope，并登记 quality_flags 与 review queue',
  ];
}

function localizedSkillStages(language: ReturnType<typeof useI18n>['language']) {
  if (language === 'en-US') {
    return ['Generate SKILL.md draft', 'Validate module scope', 'Register permission boundary', 'Wait for human review'];
  }
  if (language === 'ja-JP') {
    return ['SKILL.md草案を生成', 'モジュール範囲を検証', '権限境界を登録', '人間レビュー待ち'];
  }
  return ['生成 SKILL.md 草案', '校验模块范围', '登记权限边界', '等待人工复核'];
}

function permissionLabel(key: keyof AgentSkillConfig['permissions'], language: ReturnType<typeof useI18n>['language']) {
  const labels: Record<keyof AgentSkillConfig['permissions'], Record<string, string>> = {
    readWorkspace: { 'zh-CN': '读取工作区', 'en-US': 'Read workspace', 'ja-JP': '作業区を読む' },
    writeArtifacts: { 'zh-CN': '写入 artifact', 'en-US': 'Write artifacts', 'ja-JP': 'アーティファクトを書き込む' },
    externalSearch: { 'zh-CN': '外部检索', 'en-US': 'External search', 'ja-JP': '外部検索' },
    downloadSources: { 'zh-CN': '下载来源', 'en-US': 'Download sources', 'ja-JP': '資料をダウンロード' },
    usePaidApi: { 'zh-CN': '付费 API', 'en-US': 'Paid API', 'ja-JP': '有料API' },
    writeVault: { 'zh-CN': '写入 vault', 'en-US': 'Write vault', 'ja-JP': 'vaultへ書き込み' },
  };
  return labels[key][language];
}

export default SkillConfigurator;
