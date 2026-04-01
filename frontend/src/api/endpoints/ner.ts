import apiClient from '../client';
import { NERResult, Entity } from '../types';

export const nerApi = {
  extractEntities: async (
    text: string,
    entityTypes?: string[],
    language?: 'zh' | 'ja'
  ): Promise<NERResult> => {
    const response = await apiClient.post('/api/ner/extract', {
      text,
      entity_types: entityTypes,
      language,
    });

    return response as NERResult;
  },

  extractFromFile: async (
    file: File,
    entityTypes?: string[]
  ): Promise<NERResult> => {
    const formData = new FormData();
    formData.append('file', file);
    if (entityTypes) {
      entityTypes.forEach((type) => formData.append('entity_types', type));
    }

    const response = await apiClient.post('/api/ner/extract-file', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response as NERResult;
  },

  disambiguateEntity: async (entity: Entity, context: string) => {
    return apiClient.post('/api/ner/disambiguate', {
      entity,
      context,
    });
  },

  getHistoricalEntities: async () => {
    return apiClient.get('/api/ner/historical-entities');
  },
};
