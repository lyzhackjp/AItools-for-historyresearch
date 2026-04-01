import apiClient from '../client';
import { OCRResult } from '../types';

export const ocrApi = {
  extractText: async (
    file: File,
    engine: string,
    options?: {
      language?: string;
      dpi?: number;
      removeWatermark?: boolean;
    }
  ): Promise<OCRResult> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('engine', engine);

    if (options) {
      if (options.language) formData.append('language', options.language);
      if (options.dpi) formData.append('dpi', options.dpi.toString());
      if (options.removeWatermark !== undefined) {
        formData.append('remove_watermark', options.removeWatermark.toString());
      }
    }

    const response = await apiClient.post('/api/ocr/extract', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response as OCRResult;
  },

  getModels: async () => {
    return apiClient.get('/api/ocr/models');
  },

  getModelStatus: async (modelId: string) => {
    return apiClient.get(`/api/ocr/models/${modelId}/status`);
  },

  compareModels: async (file: File, models: string[]) => {
    const formData = new FormData();
    formData.append('file', file);
    models.forEach((model) => formData.append('models', model));

    return apiClient.post('/api/ocr/model/compare', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
};
