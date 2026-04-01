import apiClient from '../client';
import { PolishResult } from '../types';

export const docApi = {
  parseDocument: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    return apiClient.post('/api/doc/parse', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },

  polishDocument: async (
    file: File,
    strategy: 'quick' | 'deep' | 'custom',
    language: 'zh' | 'ja' | 'en'
  ): Promise<PolishResult> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('strategy', strategy);
    formData.append('language', language);

    const response = await apiClient.post('/api/doc/polish', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response as PolishResult;
  },

  generateDocument: async (content: string, template?: string) => {
    return apiClient.post('/api/doc/generate', {
      content,
      template,
    });
  },

  downloadDocument: async (fileId: string) => {
    return apiClient.get(`/api/doc/download/${fileId}`, {
      responseType: 'blob',
    });
  },
};
