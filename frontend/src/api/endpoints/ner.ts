import apiClient from '../client';

export const nerApi = {
  recognize: async (text: string, entityTypes: string[]) => {
    return apiClient.post<unknown, unknown>('/api/tasks/execute', {
      task_type: 'ner_extraction',
      input: { text, entity_types: entityTypes },
    });
  },
};
