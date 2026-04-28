import { useMemo, useState } from 'react';
import { Button, Card, Checkbox, Col, Form, Input, Row, Select, Space, Tag, Timeline, Typography } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { workflowStageModules } from '../../data/moduleCatalog';
import { moduleDisplayName, useI18n } from '../../i18n';
import { useTaskStore } from '../../stores';

function WorkflowPage() {
  const [selectedStages, setSelectedStages] = useState<number[]>([1, 2, 3, 4, 5, 6, 7]);
  const { language, t } = useI18n();
  const startTask = useTaskStore((state) => state.startTask);
  const runDemoProgress = useTaskStore((state) => state.runDemoProgress);
  const addReviewItem = useTaskStore((state) => state.addReviewItem);
  const workflowStages = useMemo(
    () =>
      workflowStageModules.map((module, index) => ({
        id: index + 1,
        key: module.stage ?? module.taskType,
        title: module.stage ?? module.title,
        displayName: moduleDisplayName(module, language),
        description: workflowStageDescription(module.id, language),
      })),
    [language],
  );

  const runWorkflow = (values: { topic?: string; language?: string; citationFormat?: string }) => {
    const selectedLabels = workflowStages
      .filter((stage) => selectedStages.includes(stage.id))
      .map((stage) => `${stage.id}.${stage.title}`);
    const id = startTask({
      title: `${values.topic || fallbackWorkflowTopic(language)} - ${t('workflow')}`,
      kind: 'workflow',
      mode: 'manual',
      backend: 'workflow_orchestrator',
      provider: values.language ?? 'zh',
      stage: localizedWorkflowRunStages(language)[0],
    });

    addReviewItem(id, {
      title:
        language === 'en-US'
          ? 'Check workflow checkpoints'
          : language === 'ja-JP'
            ? 'workflow checkpointを確認'
            : '检查 workflow checkpoint',
      priority: 'high',
      status: 'open',
      summary:
        language === 'en-US'
          ? 'Confirm stage artifacts, quality flags, review queue, and final export path.'
          : language === 'ja-JP'
            ? '段階成果物、quality flags、review queue、最終出力先を確認します。'
            : '确认阶段产物、quality flags、review queue 和最终导出路径。',
    });
    runDemoProgress(id, [localizedWorkflowRunStages(language)[0], ...selectedLabels, ...localizedWorkflowRunStages(language).slice(1)]);
  };

  return (
    <div className="page-shell">
      <div className="page-heading">
        <div>
          <div className="page-kicker">{t('workflowPageKicker')}</div>
          <Typography.Title level={2} style={{ margin: 0 }}>
            {t('workflowPageTitle')}
          </Typography.Title>
          <Typography.Paragraph className="muted" style={{ marginTop: 8 }}>
            {t('workflowPageIntro')}
          </Typography.Paragraph>
        </div>
      </div>

      <div className="workbench-grid">
        <Card title={t('taskConfig')}>
          <Form
            initialValues={{ language: 'zh', citationFormat: 'chicago' }}
            layout="vertical"
            onFinish={runWorkflow}
          >
            <Form.Item label={t('researchGoal')} name="topic">
              <Input
                placeholder={
                  language === 'en-US'
                    ? 'Enter this workflow research topic'
                    : language === 'ja-JP'
                      ? 'このworkflowの研究テーマを入力'
                      : '输入本次 workflow 的研究主题'
                }
              />
            </Form.Item>
            <Form.Item label={t('language')} name="language">
              <Select
                options={[
                  { label: '中文', value: 'zh' },
                  { label: '日本語', value: 'ja' },
                  { label: 'English', value: 'en' },
                ]}
              />
            </Form.Item>
            <Form.Item label={language === 'en-US' ? 'Citation style' : language === 'ja-JP' ? '引用形式' : '引用格式'} name="citationFormat">
              <Select
                options={[
                  { label: 'Chicago', value: 'chicago' },
                  { label: 'GB/T 7714', value: 'gb7714' },
                  { label: 'APA', value: 'apa' },
                  { label: 'MLA', value: 'mla' },
                ]}
              />
            </Form.Item>
            <Form.Item label={language === 'en-US' ? 'Stages to run' : language === 'ja-JP' ? '実行段階' : '运行阶段'}>
              <Checkbox.Group value={selectedStages} onChange={(values) => setSelectedStages(values as number[])}>
                <Space direction="vertical">
                  {workflowStages.map((stage) => (
                    <Checkbox key={stage.id} value={stage.id}>
                      {stage.displayName} - {stage.description}
                    </Checkbox>
                  ))}
                </Space>
              </Checkbox.Group>
            </Form.Item>
            <Button block htmlType="submit" icon={<PlayCircleOutlined />} type="primary">
              {t('runWorkflow')}
            </Button>
          </Form>
        </Card>

        <Space direction="vertical" size={16}>
          <Card title={t('stageStatus')}>
            <Row gutter={[12, 12]}>
              {workflowStages.map((stage) => (
                <Col key={stage.id} xs={24} md={12}>
                  <Card size="small" title={stage.displayName}>
                    <Space direction="vertical" size={8}>
                      <Typography.Text>{stage.description}</Typography.Text>
                      <Tag color={selectedStages.includes(stage.id) ? 'processing' : 'default'}>
                        {selectedStages.includes(stage.id) ? runThisTimeLabel(language) : skipLabel(language)}
                      </Tag>
                    </Space>
                  </Card>
                </Col>
              ))}
            </Row>
          </Card>

          <Card title={t('checkpointReview')}>
            <Timeline
              items={localizedCheckpointItems(language).map((children) => ({ children }))}
            />
          </Card>
        </Space>
      </div>
    </div>
  );
}

function workflowStageDescription(moduleId: string, language: ReturnType<typeof useI18n>['language']) {
  const descriptions: Record<string, Record<string, string>> = {
    'workflow.collect': {
      'zh-CN': '搜集材料与来源线索',
      'en-US': 'Collect materials and source leads',
      'ja-JP': '資料と出典手がかりを収集',
    },
    'workflow.organize': {
      'zh-CN': '整理史料、笔记与引用',
      'en-US': 'Organize sources, notes, and citations',
      'ja-JP': '史料、ノート、引用を整理',
    },
    'workflow.extract': {
      'zh-CN': 'OCR、NER 与实体关系抽取',
      'en-US': 'Run OCR, NER, and entity relation extraction',
      'ja-JP': 'OCR、NER、エンティティ関係抽出',
    },
    'workflow.examine': {
      'zh-CN': '引用网络、史料考察与逻辑审视',
      'en-US': 'Review citation networks, source criticism, and argument logic',
      'ja-JP': '引用ネットワーク、史料検討、論理確認',
    },
    'workflow.write': {
      'zh-CN': '论文草稿生成',
      'en-US': 'Generate paper drafts',
      'ja-JP': '論文草稿を生成',
    },
    'workflow.polish': {
      'zh-CN': '学术润色、文风迁移与反向大纲',
      'en-US': 'Academic polish, style transfer, and reverse outline',
      'ja-JP': '論文推敲、文体変換、リバースアウトライン',
    },
    'workflow.format': {
      'zh-CN': '引用格式化与最终 Word 输出',
      'en-US': 'Citation formatting and final Word export',
      'ja-JP': '引用フォーマットと最終Word出力',
    },
  };
  return descriptions[moduleId][language];
}

function fallbackWorkflowTopic(language: ReturnType<typeof useI18n>['language']) {
  return language === 'en-US' ? 'Untitled research' : language === 'ja-JP' ? '無題の研究' : '未命名研究';
}

function localizedWorkflowRunStages(language: ReturnType<typeof useI18n>['language']) {
  if (language === 'en-US') {
    return ['Create project', 'Register checkpoint', 'Generate handoff summary'];
  }
  if (language === 'ja-JP') {
    return ['プロジェクトを作成', 'checkpointを登録', '引き継ぎ要約を生成'];
  }
  return ['创建项目', '登记 checkpoint', '生成交接摘要'];
}

function runThisTimeLabel(language: ReturnType<typeof useI18n>['language']) {
  return language === 'en-US' ? 'This run' : language === 'ja-JP' ? '今回実行' : '本次运行';
}

function skipLabel(language: ReturnType<typeof useI18n>['language']) {
  return language === 'en-US' ? 'Skip' : language === 'ja-JP' ? 'スキップ' : '跳过';
}

function localizedCheckpointItems(language: ReturnType<typeof useI18n>['language']) {
  if (language === 'en-US') {
    return [
      'Register packages and artifacts after each successful stage.',
      'Generate a workflow_stage_failure package on failure.',
      'Use quality flags and the review queue for frontend review.',
      'Final artifacts enter the unified artifact browsing and export flow.',
    ];
  }
  if (language === 'ja-JP') {
    return [
      '各段階の成功後にpackageとartifactsを登録します。',
      '失敗時は workflow_stage_failure package を生成します。',
      'quality flags と review queue をフロントエンドレビューに使います。',
      '最終成果物は統一された成果物閲覧・出力フローへ入ります。',
    ];
  }
  return [
    '每阶段成功后登记 package 和 artifacts。',
    '失败时生成 workflow_stage_failure package。',
    'quality flags 与 review queue 用于前端复核。',
    '最终产物进入统一产物浏览与导出流程。',
  ];
}

export default WorkflowPage;
