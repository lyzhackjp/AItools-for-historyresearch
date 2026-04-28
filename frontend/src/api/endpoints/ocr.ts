import apiClient from '../client';

export const ocrApi = {
  extractText: async (file: File, engine: string, options: Record<string, string | number | boolean> = {}) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('engine', engine);
    Object.entries(options).forEach(([key, value]) => formData.append(key, String(value)));

    return apiClient.post<unknown, unknown>('/api/ocr/extract', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  getModels: async () => {
    return apiClient.get<unknown, unknown>('/api/ocr/models');
  },

  compareModels: async (file: File, models: string[]) => {
    const formData = new FormData();
    formData.append('file', file);
    models.forEach((model) => formData.append('models', model));

    return apiClient.post<unknown, unknown>('/api/ocr/model/compare', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};
