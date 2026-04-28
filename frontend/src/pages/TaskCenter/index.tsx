import { Button, Card, Empty, List, Progress, Space, Tag, Typography } from 'antd';
import { DeleteOutlined, PauseCircleOutlined } from '@ant-design/icons';
import { useI18n } from '../../i18n';
import { useTaskStore } from '../../stores';
import type { TaskState, WorkspaceTask } from '../../types';
import { formatDuration } from '../../utils';

function TaskCenterPage() {
  const { language, t } = useI18n();
  const tasks = useTaskStore((state) => state.tasks);
  const clearFinished = useTaskStore((state) => state.clearFinished);
  const cancelTask = useTaskStore((state) => state.cancelTask);
  const removeTask = useTaskStore((state) => state.removeTask);

  return (
    <div className="page-shell">
      <div className="page-heading">
        <div>
          <div className="page-kicker">
            {language === 'en-US' ? 'Long-task feedback core' : language === 'ja-JP' ? '長時間タスクフィードバック' : '长任务反馈内核'}
          </div>
          <Typography.Title level={2} style={{ margin: 0 }}>
            {t('taskCenter')}
          </Typography.Title>
          <Typography.Paragraph className="muted" style={{ marginTop: 8 }}>
            {t('taskCenterIntro')}
          </Typography.Paragraph>
        </div>
        <Button icon={<DeleteOutlined />} onClick={clearFinished}>
          {t('clearFinishedTasks')}
        </Button>
      </div>

      {tasks.length === 0 ? (
        <Card>
          <Empty description={t('noTasks')} />
        </Card>
      ) : (
        <List
          dataSource={tasks}
          grid={{ gutter: 16, xs: 1, md: 2, xl: 3 }}
          renderItem={(task) => (
            <List.Item>
              <TaskCard onCancel={cancelTask} onRemove={removeTask} task={task} />
            </List.Item>
          )}
        />
      )}
    </div>
  );
}

function TaskCard({
  onCancel,
  onRemove,
  task,
}: {
  onCancel: (id: string) => void;
  onRemove: (id: string) => void;
  task: WorkspaceTask;
}) {
  const { language, t } = useI18n();
  const active = ['queued', 'running', 'waiting_review'].includes(task.state);
  const action = active ? (
    <Button key="cancel" icon={<PauseCircleOutlined />} onClick={() => onCancel(task.id)} type="text">
      {cancelLabel(language)}
    </Button>
  ) : (
    <Button key="remove" icon={<DeleteOutlined />} onClick={() => onRemove(task.id)} type="text">
      {t('remove')}
    </Button>
  );
  const stateColor = task.state === 'completed' ? 'success' : task.state === 'failed' ? 'error' : 'processing';

  return (
    <Card actions={[action]} title={task.title}>
      <Space direction="vertical" size={10} style={{ width: '100%' }}>
        <Space wrap>
          <Tag>{task.mode === 'manual' ? t('manual') : 'agent'}</Tag>
          <Tag color={stateColor}>{taskStateLabel(task.state, language)}</Tag>
          <Tag>{task.kind}</Tag>
        </Space>
        <Progress percent={task.progress} status={task.state === 'failed' ? 'exception' : undefined} />
        <Typography.Text>
          {t('currentStage')}: {task.stage}
        </Typography.Text>
        <Typography.Text className="muted">
          {durationLabel(language)}: {formatDuration(task.startedAt, task.finishedAt)}
        </Typography.Text>
        <Typography.Text className="muted">
          {artifactLabel(language)}: {task.artifacts.length} · {reviewItemLabel(language)}: {task.reviewItems.length}
        </Typography.Text>
        <pre className="task-log">
          {task.logs
            .slice(-5)
            .map((log) => `[${new Date(log.timestamp).toLocaleTimeString()}] ${log.message}`)
            .join('\n')}
        </pre>
      </Space>
    </Card>
  );
}

function cancelLabel(language: ReturnType<typeof useI18n>['language']) {
  return language === 'en-US' ? 'Cancel' : language === 'ja-JP' ? 'キャンセル' : '取消';
}

function durationLabel(language: ReturnType<typeof useI18n>['language']) {
  return language === 'en-US' ? 'Duration' : language === 'ja-JP' ? '所要時間' : '耗时';
}

function artifactLabel(language: ReturnType<typeof useI18n>['language']) {
  return language === 'en-US' ? 'Artifacts' : language === 'ja-JP' ? '成果物' : '产物';
}

function reviewItemLabel(language: ReturnType<typeof useI18n>['language']) {
  return language === 'en-US' ? 'Review items' : language === 'ja-JP' ? 'レビュー項目' : '复核项';
}

function taskStateLabel(state: TaskState, language: ReturnType<typeof useI18n>['language']) {
  const labels: Record<TaskState, Record<string, string>> = {
    queued: { 'zh-CN': '排队中', 'en-US': 'Queued', 'ja-JP': '待機中' },
    running: { 'zh-CN': '运行中', 'en-US': 'Running', 'ja-JP': '実行中' },
    waiting_review: { 'zh-CN': '等待复核', 'en-US': 'Waiting review', 'ja-JP': 'レビュー待ち' },
    completed: { 'zh-CN': '已完成', 'en-US': 'Completed', 'ja-JP': '完了' },
    failed: { 'zh-CN': '失败', 'en-US': 'Failed', 'ja-JP': '失敗' },
    cancelled: { 'zh-CN': '已取消', 'en-US': 'Cancelled', 'ja-JP': 'キャンセル済み' },
  };
  return labels[state][language];
}

export default TaskCenterPage;
