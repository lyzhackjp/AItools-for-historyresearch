import { Button, Drawer, Empty, List, Progress, Space, Tag, Typography } from 'antd';
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  DeleteOutlined,
  PauseCircleOutlined,
} from '@ant-design/icons';
import { useI18n } from '../../i18n';
import { useTaskStore } from '../../stores';
import type { TaskState, WorkspaceTask } from '../../types';

const stateColors: Record<TaskState, string> = {
  queued: 'default',
  running: 'processing',
  waiting_review: 'warning',
  completed: 'success',
  failed: 'error',
  cancelled: 'default',
};

function TaskCenterPanel() {
  const { language, t } = useI18n();
  const tasks = useTaskStore((state) => state.tasks);
  const taskCenterOpen = useTaskStore((state) => state.taskCenterOpen);
  const setTaskCenterOpen = useTaskStore((state) => state.setTaskCenterOpen);
  const cancelTask = useTaskStore((state) => state.cancelTask);
  const removeTask = useTaskStore((state) => state.removeTask);

  return (
    <Drawer
      open={taskCenterOpen}
      onClose={() => setTaskCenterOpen(false)}
      title={t('taskCenter')}
      width={520}
    >
      {tasks.length === 0 ? (
        <Empty
          description={
            language === 'en-US'
              ? 'No tasks yet. Manual, workflow, and agent solo runs will appear here.'
              : language === 'ja-JP'
                ? 'まだタスクがありません。手動、workflow、agent solo の実行後にここへ表示されます。'
                : '暂无任务。手动模式、workflow 和 agent solo 运行后都会出现在这里。'
          }
        />
      ) : (
        <List
          dataSource={tasks}
          renderItem={(task) => (
            <List.Item
              actions={[
                ['queued', 'running', 'waiting_review'].includes(task.state) ? (
                  <Button key="cancel" icon={<PauseCircleOutlined />} onClick={() => cancelTask(task.id)} size="small">
                    {language === 'en-US' ? 'Cancel' : language === 'ja-JP' ? 'キャンセル' : '取消'}
                  </Button>
                ) : (
                  <Button key="remove" icon={<DeleteOutlined />} onClick={() => removeTask(task.id)} size="small">
                    {t('remove')}
                  </Button>
                ),
              ]}
            >
              <TaskListItem task={task} />
            </List.Item>
          )}
        />
      )}
    </Drawer>
  );
}

function TaskListItem({ task }: { task: WorkspaceTask }) {
  const { language, t } = useI18n();
  const recentLogs = task.logs.slice(-3);

  return (
    <Space direction="vertical" size={8} style={{ width: '100%' }}>
      <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
        <Space>
          {stateIcon(task.state)}
          <Typography.Text strong>{task.title}</Typography.Text>
        </Space>
        <Tag color={stateColors[task.state]}>{taskStateLabel(task.state, language)}</Tag>
      </Space>
      <Progress percent={task.progress} size="small" status={task.state === 'failed' ? 'exception' : undefined} />
      <Typography.Text className="muted">
        {t('currentStage')}: {task.stage}
      </Typography.Text>
      {task.artifacts.length > 0 && (
        <Typography.Text className="muted">
          {language === 'en-US' ? 'Artifacts' : language === 'ja-JP' ? '成果物' : '产物'}: {task.artifacts.length}
        </Typography.Text>
      )}
      {recentLogs.length > 0 && (
        <pre className="task-log">
          {recentLogs.map((log) => `[${new Date(log.timestamp).toLocaleTimeString()}] ${log.message}`).join('\n')}
        </pre>
      )}
    </Space>
  );
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

function stateIcon(state: TaskState) {
  if (state === 'completed') {
    return <CheckCircleOutlined style={{ color: '#12b76a' }} />;
  }
  if (state === 'failed') {
    return <CloseCircleOutlined style={{ color: '#f04438' }} />;
  }
  return <ClockCircleOutlined style={{ color: '#1f6feb' }} />;
}

export default TaskCenterPanel;
