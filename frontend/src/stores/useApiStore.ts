import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { ApiKeyConfig, UserPreferences } from '../types';

interface ApiStore {
  apiKeys: Record<string, ApiKeyConfig>;
  activeProvider: string;
  providers: Array<{
    id: string;
    name: string;
    recommended: boolean;
  }>;

  setApiKey: (provider: string, key: string) => void;
  removeApiKey: (provider: string) => void;
  switchProvider: (provider: string) => void;
  getActiveKey: () => string | null;
  hasKey: (provider: string) => boolean;
  loadFromStorage: () => void;
  saveToStorage: () => void;
}

export const useApiStore = create<ApiStore>()(
  persist(
    (set, get) => ({
      apiKeys: {},
      activeProvider: 'qwen',
      providers: [
        { id: 'qwen', name: '通义千问', recommended: true },
        { id: 'openai', name: 'OpenAI', recommended: false },
        { id: 'zhipu', name: '智谱AI', recommended: false },
        { id: 'minimax', name: 'MiniMax', recommended: false },
      ],

      setApiKey: (provider, key) =>
        set((state) => ({
          apiKeys: {
            ...state.apiKeys,
            [provider]: {
              key,
              createdAt: Date.now(),
            },
          },
        })),

      removeApiKey: (provider) =>
        set((state) => {
          const newKeys = { ...state.apiKeys };
          delete newKeys[provider];
          return { apiKeys: newKeys };
        }),

      switchProvider: (provider) => set({ activeProvider: provider }),

      getActiveKey: () => {
        const state = get();
        const keyConfig = state.apiKeys[state.activeProvider];
        return keyConfig ? keyConfig.key : null;
      },

      hasKey: (provider) => {
        const state = get();
        return provider in state.apiKeys;
      },

      loadFromStorage: () => {
        const stored = localStorage.getItem('api-config');
        if (stored) {
          try {
            const data = JSON.parse(stored);
            set({
              apiKeys: data.apiKeys || {},
              activeProvider: data.activeProvider || 'qwen',
            });
          } catch (error) {
            console.error('Failed to load API config from storage:', error);
          }
        }
      },

      saveToStorage: () => {
        const state = get();
        localStorage.setItem(
          'api-config',
          JSON.stringify({
            apiKeys: state.apiKeys,
            activeProvider: state.activeProvider,
          })
        );
      },
    }),
    {
      name: 'api-config',
    }
  )
);
