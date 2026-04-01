import apiClient from '../client';
import { Note, ResearchMessage } from '../types';

export const researchApi = {
  generateNote: async (
    sourceText: string,
    options?: {
      template?: string;
      format?: 'markdown' | 'obsidian';
      extractEntities?: boolean;
    }
  ): Promise<Note> => {
    const response = await apiClient.post('/api/note/generate', {
      source_text: sourceText,
      ...options,
    });

    return response as Note;
  },

  sendMessage: async (
    message: string,
    conversationId?: string,
    context?: string[]
  ): Promise<ResearchMessage> => {
    const response = await apiClient.post('/api/research/chat', {
      message,
      conversation_id: conversationId,
      context,
    });

    return response as ResearchMessage;
  },

  getConversationHistory: async (conversationId: string) => {
    return apiClient.get(`/api/research/conversations/${conversationId}`);
  },

  searchPapers: async (query: string, limit?: number) => {
    return apiClient.post('/api/research/search-papers', {
      query,
      limit: limit || 10,
    });
  },

  analyzeLiterature: async (text: string) => {
    return apiClient.post('/api/research/analyze', {
      text,
    });
  },
};
