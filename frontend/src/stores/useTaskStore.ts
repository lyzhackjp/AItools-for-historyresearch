import { create } from 'zustand';
import { TaskStatus } from '../types';

interface TaskStore {
  tasks: TaskStatus[];
  addTask: (task: Omit<TaskStatus, 'id' | 'createdAt' | 'updatedAt'>) => string;
  updateTask: (id: string, updates: Partial<TaskStatus>) => void;
  removeTask: (id: string) => void;
  getTask: (id: string) => TaskStatus | undefined;
  clearCompleted: () => void;
}

export const useTaskStore = create<TaskStore>((set, get) => ({
  tasks: [],

  addTask: (task) => {
    const id = `task-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const now = Date.now();

    set((state) => ({
      tasks: [
        ...state.tasks,
        {
          ...task,
          id,
          createdAt: now,
          updatedAt: now,
        },
      ],
    }));

    return id;
  },

  updateTask: (id, updates) =>
    set((state) => ({
      tasks: state.tasks.map((task) =>
        task.id === id
          ? { ...task, ...updates, updatedAt: Date.now() }
          : task
      ),
    })),

  removeTask: (id) =>
    set((state) => ({
      tasks: state.tasks.filter((task) => task.id !== id),
    })),

  getTask: (id) => {
    return get().tasks.find((task) => task.id === id);
  },

  clearCompleted: () =>
    set((state) => ({
      tasks: state.tasks.filter(
        (task) => task.status !== 'completed' && task.status !== 'failed'
      ),
    })),
}));
