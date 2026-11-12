import { useEffect, useState } from 'react';
/** One shared tooltip for every [data-tip] element: shown on hover and on keyboard focus
 * (SPEC §14.7: tool bar and timeline icons show name and shortcut). Placed to the left of
 * the vertical tool bar, below everything else. Positions are integers. */
export function Tooltip() {
  const [tip, setTip] = useState<{ text: string; x: number; y: number; side: 'left' | 'below' } | null>(null);
  useEffect(() => {
    const show = (e: Event) => {
      const el = (e.target as Element | null)?.closest?.('[data-tip]');
      if (!el) { if (e.type === 'pointerover') setTip(null); return; }
      if (e.type === 'focusin' && !(el as HTMLElement).matches(':focus-visible')) return;
      const r = el.getBoundingClientRect(), shell = document.querySelector('.app-shell')!, scale = shell.getBoundingClientRect().width / (shell as HTMLElement).offsetWidth || 1;
      const side = el.closest('.toolbar') ? 'left' : 'below';
      setTip({ text: el.getAttribute('data-tip')!, side, x: Math.round((side === 'left' ? r.left - 8 : r.left + r.width / 2) / scale), y: Math.round((side === 'left' ? r.top + r.height / 2 : r.bottom + 6) / scale) });
    };
    const hide = () => setTip(null);
    document.addEventListener('pointerover', show); document.addEventListener('focusin', show);
    document.addEventListener('focusout', hide); document.addEventListener('pointerdown', hide); document.addEventListener('keydown', hide);
    return () => {
      document.removeEventListener('pointerover', show); document.removeEventListener('focusin', show);
      document.removeEventListener('focusout', hide); document.removeEventListener('pointerdown', hide); document.removeEventListener('keydown', hide);
    };
  }, []);
  if (!tip) return null;
  return <div className={`tooltip ${tip.side}`} role="tooltip" style={{ left: tip.x, top: tip.y }}>{tip.text.split('  ').map((part, i) => i ? <kbd key={i}>{part}</kbd> : <span key={i}>{part}</span>)}</div>;
}
