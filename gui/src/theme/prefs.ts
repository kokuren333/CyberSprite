import { create } from 'zustand';
/** Display-only preferences (no project data). Stored in localStorage and applied as
 * attributes on <html> so tokens.css / app.css can switch with plain selectors. */
export type Contrast = 'auto' | 'normal' | 'high';
export type Motion = 'auto' | 'reduce';
export type TextSize = 12 | 13 | 14;
export type UiScale = 1 | 2 | 3;
type Prefs = { contrast: Contrast; motion: Motion; text: TextSize; scale: UiScale };
const KEY = 'cybersprite.gui.display';
const defaults: Prefs = { contrast: 'auto', motion: 'auto', text: 13, scale: 1 };
function load(): Prefs {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? '{}');
    return {
      contrast: ['auto', 'normal', 'high'].includes(v.contrast) ? v.contrast : defaults.contrast,
      motion: ['auto', 'reduce'].includes(v.motion) ? v.motion : defaults.motion,
      text: [12, 13, 14].includes(v.text) ? v.text : defaults.text,
      scale: [1, 2, 3].includes(v.scale) ? v.scale : defaults.scale,
    };
  } catch { return defaults; }
}
const highQuery = typeof matchMedia === 'function' ? matchMedia('(prefers-contrast: more)') : null;
function applyToDocument(p: Prefs) {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  root.dataset.contrast = p.contrast === 'high' || (p.contrast === 'auto' && highQuery?.matches) ? 'high' : 'normal';
  root.dataset.motion = p.motion;
  root.dataset.text = String(p.text);
  root.dataset.scale = String(p.scale);
}
export const useDisplay = create<Prefs & { set: (patch: Partial<Prefs>) => void }>((setState, get) => ({
  ...load(),
  set: patch => {
    setState(patch);
    const { set: _, ...value } = get();
    try { localStorage.setItem(KEY, JSON.stringify(value)); } catch { /* storage may be unavailable */ }
    applyToDocument(value);
  },
}));
export function initDisplay() {
  const { set: _, ...value } = useDisplay.getState();
  applyToDocument(value);
  highQuery?.addEventListener('change', () => { const { set: __, ...now } = useDisplay.getState(); applyToDocument(now); });
}
