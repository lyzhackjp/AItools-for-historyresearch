import { create } from 'zustand';
import type {
  ArtifactSummary,
  QualityFlag,
  ReviewItem,
  TaskKind,
  TaskLogEntry,
  TaskState,
  WorkspaceMode,
  WorkspaceTask,
} from '../types';

interface StartTaskInput {
  title: string;
  kind: TaskKind;
  mode: WorkspaceMode;
  stage?: string;
  provider?: string;
  backend?: string;
}

interface TaskStore {
  tasks: WorkspaceTask[];
  selectedTaskId?: string;
  taskCenterOpen: boolean;
  startTask: (input: StartTaskInput) => string;
  updateTask: (id: string, updates: Partial<WorkspaceTask>) => void;
  appendLog: (id: string, message: string, level?: TaskLogEntry['level']) => void;
  addArtifact: (id: string, artifact: Omit<ArtifactSummary, 'id' | 'createdAt'>) => void;
  addQualityFlag: (id: string, flag: Omit<QualityFlag, 'id'>) => void;
  addReviewItem: (id: string, item: Omit<ReviewItem, 'id'>) => void;
  completeTask: (id: string, result?: unknown) => void;
  failTask: (id: string, error: string) => void;
  cancelTask: (id: string) => void;
  removeTask: (id: string) => void;
  clearFinished: () => void;
  selectTask: (id?: string) => void;
  setTaskCenterOpen: (open: boolean) => void;
  getTask: (id: string) => WorkspaceTask | undefined;
  runDemoProgress: (id: string, stages: string[]) => void;
}

const makeId = (prefix: string) => `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const createLog = (message: string, level: TaskLogEntry['level'] = 'info'): TaskLogEntry => ({
  id: makeId('log'),
  timestamp: Date.now(),
  level,
  message,
});

export const useTaskStore = create<TaskStore>((set, get) => ({
  tasks: [],
  selectedTaskId: undefined,
  taskCenterOpen: false,

  startTask: (input) => {
    const id = makeId('task');
    const now = Date.now();
    const task: WorkspaceTask = {
      id,
      title: input.title,
      kind: input.kind,
      mode: input.mode,
      state: 'queued',
      progress: 0,
      stage: input.stage ?? '等待调度',
      createdAt: now,
      updatedAt: now,
      provider: input.provider,
      backend: input.backend,
      logs: [createLog('任务已加入任务中心。')],
      artifacts: [],
      qualityFlags: [],
      reviewItems: [],
    };

    set((state) => ({
      tasks: [task, ...state.tasks],
      selectedTaskId: id,
      taskCenterOpen: true,
    }));

    return id;
  },

  updateTask: (id, updates) =>
    set((state) => ({
      tasks: state.tasks.map((task) =>
        task.id === id ? { ...task, ...updates, updatedAt: Date.now() } : task,
      ),
    })),

  appendLog: (id, message, level = 'info') =>
    set((state) => ({
      tasks: state.tasks.map((task) =>
        task.id === id
          ? {
              ...task,
              logs: [...task.logs, createLog(message, level)],
              updatedAt: Date.now(),
            }
          : task,
      ),
    })),

  addArtifact: (id, artifact) =>
    set((state) => ({
      tasks: state.tasks.map((task) =>
        task.id === id
          ? {
              ...task,
              artifacts: [...task.artifacts, { ...artifact, id: makeId('artifact'), createdAt: Date.now() }],
              updatedAt: Date.now(),
            }
          : task,
      ),
    })),

  addQualityFlag: (id, flag) =>
    set((state) => ({
      tasks: state.tasks.map((task) =>
        task.id === id
          ? {
              ...task,
              qualityFlags: [...task.qualityFlags, { ...flag, id: makeId('flag') }],
              updatedAt: Date.now(),
            }
          : task,
      ),
    })),

  addReviewItem: (id, item) =>
    set((state) => ({
      tasks: state.tasks.map((task) =>
        task.id === id
          ? {
              ...task,
              reviewItems: [...task.reviewItems, { ...item, id: makeId('review') }],
              updatedAt: Date.now(),
            }
          : task,
      ),
    })),

  completeTask: (id, result) =>
    get().updateTask(id, {
      state: 'completed',
      progress: 100,
      stage: '完成',
      finishedAt: Date.now(),
      result,
    }),

  failTask: (id, error) =>
    get().updateTask(id, {
      state: 'failed',
      stage: '失败',
      finishedAt: Date.now(),
      error,
    }),

  cancelTask: (id) =>
    get().updateTask(id, {
      state: 'cancelled',
      stage: '已取消',
      finishedAt: Date.now(),
    }),

  removeTask: (id) =>
    set((state) => ({
      tasks: state.tasks.filter((task) => task.id !== id),
      selectedTaskId: state.selectedTaskId === id ? undefined : state.selectedTaskId,
    })),

  clearFinished: () =>
    set((state) => ({
      tasks: state.tasks.filter(
        (task) => !['completed', 'failed', 'cancelled'].includes(task.state),
      ),
    })),

  selectTask: (id) => set({ selectedTaskId: id, taskCenterOpen: true }),
  setTaskCenterOpen: (open) => set({ taskCenterOpen: open }),
  getTask: (id) => get().tasks.find((task) => task.id === id),

  runDemoProgress: (id, stages) => {
    const task = get().getTask(id);
    if (!task || task.state === 'cancelled') {
      return;
    }

    get().updateTask(id, {
      state: 'running',
      startedAt: task.startedAt ?? Date.now(),
      stage: stages[0] ?? '运行中',
      progress: Math.max(task.progress, 8),
    });
    get().appendLog(id, '开始执行，任务中心将持续刷新进度。');

    let step = 0;
    const timer = window.setInterval(() => {
      const current = get().getTask(id);
      if (!current || ['completed', 'failed', 'cancelled'].includes(current.state)) {
        window.clearInterval(timer);
        return;
      }

      step += 1;
      const nextProgress = Math.min(96, current.progress + 12 + Math.round(Math.random() * 8));
      const stageIndex = Math.min(stages.length - 1, Math.floor((nextProgress / 100) * stages.length));
      const nextStage = stages[stageIndex] ?? '运行中';

      get().updateTask(id, {
        progress: nextProgress,
        stage: nextStage,
        state: nextProgress > 78 && current.reviewItems.length > 0 ? 'waiting_review' : 'running',
      });
      get().appendLog(id, `${nextStage}：进度 ${nextProgress}%`);

      if (step >= 7 || nextProgress >= 94) {
        get().addArtifact(id, {
          name: `${current.title} 摘要`,
          type: 'task_execution',
          path: 'output/task_execution_preview.json',
        });
        get().completeTask(id, { summary: '前端任务模拟已完成，可替换为后端 job 事件流。' });
        get().appendLog(id, '任务完成，产物已登记。', 'success');
        window.clearInterval(timer);
      }
    }, 900);
  },
}));

export const taskStateLabels: Record<TaskState, string> = {
  queued: '排队中',
  running: '运行中',
  waiting_review: '等待复核',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
};
