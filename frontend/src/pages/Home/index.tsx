import { Button, Card, Col, Progress, Row, Space, Statistic, Tag, Typography } from 'antd';
import {
  AppstoreOutlined,
  BranchesOutlined,
  DashboardOutlined,
  RobotOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useTaskStore } from '../../stores';
import { useI18n } from '../../i18n';

function HomePage() {
  const navigate = useNavigate();
  const { language, t } = useI18n();
  const tasks = useTaskStore((state) => state.tasks);
  const activeTasks = tasks.filter((task) => ['queued', 'running', 'waiting_review'].includes(task.state));
  const completedTasks = tasks.filter((task) => task.state === 'completed');
  const averageProgress =
    activeTasks.length === 0
      ? 0
      : Math.round(activeTasks.reduce((sum, task) => sum + task.progress, 0) / activeTasks.length);
  const modeSuffix = language === 'en-US' ? '' : language === 'ja-JP' ? '種' : '种';
  const manualTags =
    language === 'en-US'
      ? ['OCR', 'NER', 'Citation criticism', 'Notes', 'Academic polish']
      : language === 'ja-JP'
        ? ['OCR', 'NER', '引用検証', 'ノート', '論文推敲']
        : ['OCR', 'NER', '引用考证', '笔记', '写作润色'];
  const nextSteps =
    language === 'en-US'
      ? [
          'Route every long task through the task center.',
          'Consume the backend task registry dynamically in manual mode.',
          'Keep plan, authorization, observation, and review links visible in agent mode.',
        ]
      : language === 'ja-JP'
        ? [
            'すべての長時間タスクをタスクセンターで受けます。',
            '手動モードで backend task registry を動的に利用します。',
            'agent モードでは計画、承認、観察、レビューの流れを残します。',
          ]
        : [
            '以任务中心承接所有长任务反馈。',
            '手动模式动态消费后端 task registry。',
            'agent 模式保留计划、授权、观察和复核链路。',
          ];

  return (
    <div className="page-shell">
      <div className="page-heading">
        <div>
          <div className="page-kicker">{t('home')}</div>
          <Typography.Title level={2} style={{ margin: 0 }}>
            {t('welcomeTitle')}
          </Typography.Title>
          <Typography.Paragraph className="muted" style={{ marginTop: 8, maxWidth: 820 }}>
            {t('welcomeBody')}
          </Typography.Paragraph>
        </div>
        <Space>
          <Button icon={<DashboardOutlined />} onClick={() => navigate('/tasks')}>
            {t('taskCenter')}
          </Button>
          <Button icon={<ThunderboltOutlined />} onClick={() => navigate('/manual')} type="primary">
            {t('startManual')}
          </Button>
        </Space>
      </div>

      <div className="status-strip">
        <Space size={24} wrap>
          <Statistic title={t('runningTasks')} value={activeTasks.length} />
          <Statistic title={t('completedTasks')} value={completedTasks.length} />
          <Statistic title={t('workModes')} value={2} suffix={modeSuffix} />
        </Space>
        <Space direction="vertical" style={{ minWidth: 220 }}>
          <Typography.Text className="muted">{t('currentProgress')}</Typography.Text>
          <Progress percent={averageProgress} size="small" />
        </Space>
      </div>

      <div className="mode-grid">
        <Card
          actions={[
            <Button key="manual" onClick={() => navigate('/manual')} type="primary">
              {t('enterManual')}
            </Button>,
          ]}
          title={
            <Space>
              <AppstoreOutlined />
              {t('manual')}
            </Space>
          }
        >
          <Space direction="vertical" size={12}>
            <Typography.Paragraph>
              {t('manualBody')}
            </Typography.Paragraph>
            <Space wrap>
              {manualTags.map((tag) => (
                <Tag key={tag}>{tag}</Tag>
              ))}
            </Space>
          </Space>
        </Card>

        <Card
          actions={[
            <Button key="agent" onClick={() => navigate('/agent-solo')} type="primary">
              {t('enterAgent')}
            </Button>,
          ]}
          title={
            <Space>
              <RobotOutlined />
              {t('agentSolo')}
            </Space>
          }
        >
          <Space direction="vertical" size={12}>
            <Typography.Paragraph>
              {t('agentBody')}
            </Typography.Paragraph>
            <Space wrap>
              <Tag color="blue">OpenClaw</Tag>
              <Tag color="blue">Hermes</Tag>
              <Tag color="blue">Codex skill</Tag>
              <Tag color="blue">MCP</Tag>
            </Space>
          </Space>
        </Card>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title={t('nextSteps')}>
            <Space direction="vertical">
              {nextSteps.map((step, index) => (
                <Typography.Text key={step}>
                  {index + 1}. {step}
                </Typography.Text>
              ))}
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card
            title={
              <Space>
                <BranchesOutlined />
                {t('workflow')}
              </Space>
            }
          >
            <Typography.Paragraph>
              collect, organize, extract, examine, write, polish, format
            </Typography.Paragraph>
            <Button onClick={() => navigate('/workflow')}>{t('workflowOpen')}</Button>
          </Card>
        </Col>
      </Row>
    </div>
  );
}

export default HomePage;
