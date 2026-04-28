import apiClient from '../client';

export const researchApi = {
  ask: async (message: string, context: string[] = []) => {
    return apiClient.post<unknown, unknown>('/api/tasks/execute', {
      task_type: 'field_research',
      input: { message, context },
    });
  },

  runWorkflow: async (payload: Record<string, unknown>) => {
    return apiClient.post<unknown, unknown>('/api/workflow/run', payload);
  },
};
