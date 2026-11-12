import en from './en.json';
import ja from './ja.json';
import { create } from 'zustand';
export type TextKey = keyof typeof en;
type Language = 'ja' | 'en';
const KEY = 'cybersprite.gui.language';
function initial(): Language {
  try { const saved = localStorage.getItem(KEY); if (saved === 'ja' || saved === 'en') return saved; } catch { /* no storage */ }
  return navigator.language.startsWith('ja') ? 'ja' : 'en';
}
const first = initial();
if (typeof document !== 'undefined') document.documentElement.lang = first;
export const useLanguage = create<{ language: Language; setLanguage: (value: Language) => void }>(set => ({
  language: first,
  setLanguage: language => {
    document.documentElement.lang = language;
    try { localStorage.setItem(KEY, language); } catch { /* no storage */ }
    set({ language });
  },
}));
export function useText() {
  const language = useLanguage(s => s.language);
  return (key: TextKey) => (language === 'ja' ? ja : en)[key];
}
