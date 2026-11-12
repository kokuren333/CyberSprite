import { useEffect, useState } from 'react';
import { AgentPanel } from './components/AgentPanel';
import { Canvas } from './components/Canvas';
import { ContextBar } from './components/ContextBar';
import { Palette } from './components/Palette';
import { SchemaDialog, type DialogKind } from './components/SchemaDialog';
import { Timeline } from './components/Timeline';
import { Toolbar } from './components/Toolbar';
import { useLanguage, useText } from './i18n';
import { act, closeProject, refresh, rpc, store, useEditor, view, type Tool } from './store';
export function App() {
  const s = useEditor(), t = useText(), language = useLanguage();
  const [dialog, setDialog] = useState<DialogKind | null>(null), [op, setOp] = useState('');
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement || document.querySelector('dialog[open]')) return;
      const at = store.getState(), ctrl = e.ctrlKey || e.metaKey;
      if (ctrl) {
        const k = e.key.toLowerCase();
        if (['s', 'z', 'y', 'n', 'o', 'e', 'i', 'a', 'd', "'"].includes(k)) e.preventDefault();
        if (k === 's') view({ status: `${t('saved')} (r${at.project?.summary.revision ?? 0})` });
        if (k === 'z' || k === 'y') void act(async () => { await rpc(k === 'y' || e.shiftKey ? 'history.redo' : 'history.undo'); await refresh(); });
        if (k === 'n') setDialog('new'); if (k === 'o') setDialog('open'); if (k === 'e') setDialog('export'); if (k === 'i') setDialog('import');
        if (k === "'") view({ grid: !at.grid });
        if (k === 'a') view({ selection: { type: 'all' } }); if (k === 'd') view({ selection: { type: 'all' } });
        return;
      }
      const tool = ({ b: 'pencil', e: 'eraser', l: 'line', u: e.shiftKey ? 'ellipse' : 'rect', g: 'fill', i: 'eyedropper', m: 'select', v: 'move', z: 'zoom' } as Record<string, Tool>)[e.key.toLowerCase()];
      if (tool) view({ tool });
      if (/^[1-6]$/.test(e.key)) view({ zoom: +e.key });
      if (e.key === 'F3') { e.preventDefault(); view({ onion: !at.onion }); }
      if (e.key === 'F4') { e.preventDefault(); view({ tab: 'Activity' }); }
      if (e.key === 'Enter') view({ playing: !at.playing });
      if (e.key === 'x') view({ foreground: at.background, background: at.foreground });
      if (e.key === '[' || e.key === ']') view({ brush: { ...at.brush, size: Math.max(1, Math.min(64, at.brush.size + (e.key === '[' ? -1 : 1))) }, pixelPerfect: false });
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') view({ frame: Math.max(0, Math.min((at.project?.frames.length ?? 1) - 1, at.frame + (e.key === 'ArrowLeft' ? -1 : 1))) });
    };
    window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key);
  }, [t]);
  return <main className="app-shell"><h1>CyberSprite</h1>
    <nav className="menu-bar" aria-label="CyberSprite"><details className="file-menu"><summary>{t('file')}</summary>{(['new', 'open', 'import', 'export'] as const).map(kind => <button key={kind} onClick={() => { setOp(''); setDialog(kind); }}>{t(kind)}</button>)}<button onClick={() => void act(closeProject)}>{t('close')}</button></details>
      <details className="edit-menu"><summary>{t('edit')}</summary><button onClick={() => void act(async () => { await rpc('history.undo'); await refresh(); })}>{t('undo')}</button><button onClick={() => void act(async () => { await rpc('history.redo'); await refresh(); })}>{t('redo')}</button></details>
      {(['sprite', 'layer', 'frame', 'select', 'view', 'agent', 'help'] as const).map(key => <button key={key} onClick={() => { setOp(''); setDialog('operation'); }}>{t(key)}</button>)}
      <select className="op-menu" aria-label={t('operation')} value="" onChange={e => { setOp(e.target.value); setDialog('operation'); }}><option value="">{t('operation')}</option>{s.schemas.map(schema => <option key={schema.name}>{schema.name}</option>)}</select>
      <label>{t('language')}<select value={language.language} onChange={e => { language.setLanguage(e.target.value as 'ja' | 'en'); void act(() => rpc('prefs.set', { language: e.target.value })); }}><option value="ja">日本語</option><option value="en">English</option></select></label>
    </nav>
    <ContextBar /><div className="workspace"><Palette /><Canvas /><Toolbar /><AgentPanel /></div><Timeline />
    <footer className="status-bar" aria-live="polite"><span>{t(s.connected ? 'connected' : 'disconnected')}</span> / {s.pointer.join(', ')} / {t('color')} {s.foreground} / {s.project?.summary.width}×{s.project?.summary.height} / {s.zoom}× / <span data-testid="revision">r{s.project?.summary.revision ?? 0}</span> / <button onClick={() => view({ tab: 'Validate' })}>{t('validation')}: {String(s.project?.validation.ok ?? '')}</button> / <output data-testid="status">{s.status}</output><span role="alert" className="global-error">{s.error}</span><output className="job-progress">{s.progress?.method} {s.progress?.percent}</output></footer>
    {dialog && <SchemaDialog key={`${dialog}:${op}`} kind={dialog} initialOp={op || undefined} close={() => setDialog(null)} />}
  </main>;
}
