import apiClient from '../client';

export const promptApi = {
  list: async () => {
    return apiClient.get<unknown, unknown>('/api/prompts');
  },

  update: async (moduleId: string, promptId: string, content: string) => {
    return apiClient.post<unknown, unknown>('/api/prompts/update', {
      module_id: moduleId,
      prompt_id: promptId,
      content,
    });
  },
};
