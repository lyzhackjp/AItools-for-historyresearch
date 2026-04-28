import { create } from 'zustand';
import type { UserPreferences } from '../types';

interface UserStore {
  preferences: UserPreferences;
  updatePreferences: (updates: Partial<UserPreferences>) => void;
}

export const useUserStore = create<UserStore>((set) => ({
  preferences: {
    fontSize: 'normal',
    highContrast: false,
    language: 'zh-CN',
    compactDensity: false,
  },
  updatePreferences: (updates) =>
    set((state) => ({
      preferences: { ...state.preferences, ...updates },
    })),
}));
