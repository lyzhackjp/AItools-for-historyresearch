import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { UserPreferences } from '../types';

interface UserStore {
  preferences: UserPreferences;
  setFontSize: (size: UserPreferences['fontSize']) => void;
  toggleHighContrast: () => void;
  setLanguage: (lang: UserPreferences['language']) => void;
  resetPreferences: () => void;
}

const defaultPreferences: UserPreferences = {
  fontSize: 'normal',
  highContrast: false,
  language: 'zh-CN',
};

export const useUserStore = create<UserStore>()(
  persist(
    (set) => ({
      preferences: defaultPreferences,

      setFontSize: (size) =>
        set((state) => ({
          preferences: { ...state.preferences, fontSize: size },
        })),

      toggleHighContrast: () =>
        set((state) => ({
          preferences: {
            ...state.preferences,
            highContrast: !state.preferences.highContrast,
          },
        })),

      setLanguage: (lang) =>
        set((state) => ({
          preferences: { ...state.preferences, language: lang },
        })),

      resetPreferences: () => set({ preferences: defaultPreferences }),
    }),
    {
      name: 'user-preferences',
    }
  )
);
