import apiClient from '../client';

export const docApi = {
  polishText: async (text: string, strategy: string) => {
    return apiClient.post<unknown, unknown>('/api/doc/polish', { text, strategy });
  },

  generateDocument: async (payload: Record<string, unknown>) => {
    return apiClient.post<unknown, unknown>('/api/doc/generate', payload);
  },

  verifyHistoricalCitations: async (payload: Record<string, unknown>) => {
    return apiClient.post<unknown, unknown>('/api/doc/historical-citation-package', payload);
  },
};
