import { create } from 'zustand';
import type { ApiKeyConfig } from '../types';

interface ApiStore {
  providers: ApiKeyConfig[];
  activeProvider: string;
  setActiveProvider: (provider: string) => void;
  markConfigured: (provider: string, displayName: string) => void;
  loadFromStorage: () => void;
  getActiveKey: () => string | undefined;
}

const STORAGE_KEY = 'historyresearch-api-status';

const defaultProviders: ApiKeyConfig[] = [
  { provider: 'qwen', displayName: '通义千问', configured: false },
  { provider: 'openai', displayName: 'OpenAI', configured: false },
  { provider: 'ollama', displayName: 'Ollama 本地模型', configured: true },
  { provider: 'minimax', displayName: 'MiniMax', configured: false },
];

export const useApiStore = create<ApiStore>((set, get) => ({
  providers: defaultProviders,
  activeProvider: 'ollama',

  setActiveProvider: (provider) => {
    set({ activeProvider: provider });
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ providers: get().providers, activeProvider: provider }));
  },

  markConfigured: (provider, displayName) => {
    set((state) => {
      const providers = state.providers.some((item) => item.provider === provider)
        ? state.providers.map((item) =>
            item.provider === provider
              ? { ...item, configured: true, displayName, updatedAt: Date.now() }
              : item,
          )
        : [...state.providers, { provider, displayName, configured: true, updatedAt: Date.now() }];

      localStorage.setItem(STORAGE_KEY, JSON.stringify({ providers, activeProvider: state.activeProvider }));
      return { providers };
    });
  },

  loadFromStorage: () => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return;
    }

    try {
      const parsed = JSON.parse(raw) as Pick<ApiStore, 'providers' | 'activeProvider'>;
      set({
        providers: parsed.providers ?? defaultProviders,
        activeProvider: parsed.activeProvider ?? 'ollama',
      });
    } catch {
      set({ providers: defaultProviders, activeProvider: 'ollama' });
    }
  },

  getActiveKey: () => undefined,
}));
