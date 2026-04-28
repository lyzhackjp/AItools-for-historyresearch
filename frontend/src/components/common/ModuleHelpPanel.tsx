import {
  AuditOutlined,
  ExportOutlined,
  FileSearchOutlined,
  PlayCircleOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { Alert, Card, Descriptions, Space, Steps, Tag, Typography } from 'antd';
import { familyDisplayName, moduleDisplayName, moduleHelpDescription, useI18n } from '../../i18n';
import type { ExecutionTarget, ModulePrivacy, WorkspaceModule } from '../../types';

interface ModuleHelpPanelProps {
  module: WorkspaceModule;
  compact?: boolean;
}

const executionLabels: Record<ExecutionTarget, Record<string, string>> = {
  task_manager: {
    'zh-CN': '统一任务入口',
    'en-US': 'Unified task entry',
    'ja-JP': '統一タスク入口',
  },
  workflow_stage: {
    'zh-CN': 'workflow 阶段',
    'en-US': 'Workflow stage',
    'ja-JP': 'workflow段階',
  },
  package_module: {
    'zh-CN': '可编排 package 节点',
    'en-US': 'Composable package node',
    'ja-JP': '編成可能なpackageノード',
  },
  agent_skill: {
    'zh-CN': 'agent skill 能力',
    'en-US': 'Agent skill capability',
    'ja-JP': 'agent skill能力',
  },
};

const privacyLabels: Record<ModulePrivacy, Record<string, string>> = {
  local_first: {
    'zh-CN': '本地优先',
    'en-US': 'Local-first',
    'ja-JP': 'ローカル優先',
  },
  mixed: {
    'zh-CN': '本地/外部混合',
    'en-US': 'Mixed local/external',
    'ja-JP': 'ローカル/外部併用',
  },
  external_optional: {
    'zh-CN': '外部访问需显式确认',
    'en-US': 'External access requires confirmation',
    'ja-JP': '外部アクセスは明示確認',
  },
  managed_root: {
    'zh-CN': '受管理根目录',
    'en-US': 'Managed root',
    'ja-JP': 'managed root管理',
  },
};

const packageOnlyNotes = {
  'zh-CN': '该模块当前已作为可编排 blueprint 节点接合；真实逐节点执行建议由后端 /api/jobs 或 /api/workflow/blueprints 承接。',
  'en-US': 'This module is currently connected as a composable blueprint node; real per-node execution should be handled by /api/jobs or /api/workflow/blueprints.',
  'ja-JP': 'このモジュールは現在、編成可能なblueprintノードとして接合されています。実際のノード単位実行は /api/jobs または /api/workflow/blueprints で受けるのが望ましいです。',
};

function ModuleHelpPanel({ compact = false, module }: ModuleHelpPanelProps) {
  const { language, t } = useI18n();
  const reviewText = module.reviewRequired ? t('needsReview') : t('unchecked');

  return (
    <Card size={compact ? 'small' : 'default'} title={t('moduleUsageHelp')}>
      <Space direction="vertical" size={compact ? 10 : 14} style={{ width: '100%' }}>
        <Space direction="vertical" size={4}>
          <Typography.Text strong>{moduleDisplayName(module, language)}</Typography.Text>
          <Typography.Text className="muted">{moduleHelpDescription(module, language)}</Typography.Text>
        </Space>

        <Descriptions bordered column={1} size="small">
          <Descriptions.Item label={t('taskModule')}>{module.modulePath}</Descriptions.Item>
          <Descriptions.Item label={t('moduleCatalog')}>
            <Space wrap>
              <Tag color="blue">{familyDisplayName(module.family, language)}</Tag>
              <Tag>{executionLabels[module.executionTarget][language]}</Tag>
              <Tag color={module.reviewRequired ? 'warning' : 'success'}>{reviewText}</Tag>
              <Tag>{privacyLabels[module.privacy][language]}</Tag>
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label={t('helpInputsOutputs')}>
            <Space direction="vertical" size={6}>
              <TagGroup title={t('input')} values={module.inputs} />
              <TagGroup title={t('output')} values={module.outputs} />
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label={t('packageType')}>
            <Space wrap>
              {module.packageTypes.map((value) => (
                <Tag key={value}>{value}</Tag>
              ))}
            </Space>
          </Descriptions.Item>
        </Descriptions>

        <Steps
          direction="vertical"
          size="small"
          items={[
            { icon: <FileSearchOutlined />, title: t('helpStepInputTitle'), description: t('helpStepInput') },
            { icon: <SettingOutlined />, title: t('helpStepConfigureTitle'), description: t('helpStepConfigure') },
            { icon: <PlayCircleOutlined />, title: t('helpStepRunTitle'), description: t('helpStepRun') },
            { icon: <AuditOutlined />, title: t('helpStepReviewTitle'), description: t('helpStepReview') },
            { icon: <ExportOutlined />, title: t('helpStepExportTitle'), description: t('helpStepExport') },
          ]}
        />

        <Alert
          showIcon
          type={module.privacy === 'local_first' && !module.reviewRequired ? 'info' : 'warning'}
          message={t('helpRules')}
          description={
            <Space direction="vertical" size={4}>
              <Typography.Text>{t('helpAlert')}</Typography.Text>
              {module.executionTarget === 'package_module' && (
                <Typography.Text>{packageOnlyNotes[language]}</Typography.Text>
              )}
            </Space>
          }
        />
      </Space>
    </Card>
  );
}

function TagGroup({ title, values }: { title: string; values: string[] }) {
  return (
    <Space direction="vertical" size={4}>
      <Typography.Text strong>{title}</Typography.Text>
      <Space wrap>
        {values.map((value) => (
          <Tag key={value}>{value}</Tag>
        ))}
      </Space>
    </Space>
  );
}

export default ModuleHelpPanel;
