import en from './en.json';
import ja from './ja.json';
import { create } from 'zustand';
export type TextKey = keyof typeof en;
export const useLanguage = create<{ language: 'ja' | 'en'; setLanguage: (value: 'ja' | 'en') => void }>(set => ({
  language: navigator.language.startsWith('ja') ? 'ja' : 'en',
  setLanguage: language => { document.documentElement.lang = language; set({ language }); },
}));
export function useText() {
  const language = useLanguage(s => s.language);
  return (key: TextKey) => (language === 'ja' ? ja : en)[key];
}
