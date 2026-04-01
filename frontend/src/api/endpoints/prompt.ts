import apiClient from '../client';
import { PromptTemplate } from '../types';

export const promptApi = {
  getPrompt: async (moduleId: string, promptId: string): Promise<PromptTemplate> => {
    const response = await apiClient.get(`/api/prompts/${moduleId}/${promptId}`);
    return response as PromptTemplate;
  },

  getModulePrompts: async (moduleId: string): Promise<PromptTemplate[]> => {
    const response = await apiClient.get(`/api/prompts/${moduleId}`);
    return response as PromptTemplate[];
  },

  updatePrompt: async (
    moduleId: string,
    promptId: string,
    content: string
  ): Promise<PromptTemplate> => {
    const response = await apiClient.put(`/api/prompts/${moduleId}/${promptId}`, {
      content,
    });
    return response as PromptTemplate;
  },

  getTemplates: async (category?: string): Promise<PromptTemplate[]> => {
    const params = category ? { category } : {};
    const response = await apiClient.get('/api/prompts/templates', { params });
    return response as PromptTemplate[];
  },

  createTemplate: async (template: Partial<PromptTemplate>): Promise<PromptTemplate> => {
    const response = await apiClient.post('/api/prompts/templates', template);
    return response as PromptTemplate;
  },

  deleteTemplate: async (templateId: string): Promise<void> => {
    await apiClient.delete(`/api/prompts/templates/${templateId}`);
  },
};
