import { useEffect, useState } from 'react';
import { AgentPanel } from './components/AgentPanel';
import { Canvas } from './components/Canvas';
import { ContextBar } from './components/ContextBar';
import { Palette } from './components/Palette';
import { SchemaDialog, type DialogKind } from './components/SchemaDialog';
import { Timeline } from './components/Timeline';
import { Toolbar } from './components/Toolbar';
import { useText } from './i18n';
import { Icon } from './components/chrome';
import { SettingsDialog } from './components/SettingsDialog';
import { Tooltip } from './components/Tooltip';
import { DemoNotice } from './components/DemoNotice';
import { DEMO } from './demo/flag';
import { act, closeProject, refresh, rpc, store, useEditor, view, type Tool } from './store';
export function App() {
  const s = useEditor(), t = useText();
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
  const [settings, setSettings] = useState(false), [panel, setPanel] = useState('canvas');
  // Narrow screens show one docked panel at a time (CSS hides the switch on wide screens).
  const [dock, setDock] = useState<'palette' | 'timeline' | 'agent'>('timeline');
  const track = (e: React.SyntheticEvent) => { const id = (e.target as Element).closest?.('[data-panel]')?.getAttribute('data-panel'); if (id && id !== panel) setPanel(id); };
  const closeMenus = (e: React.MouseEvent) => { for (const d of e.currentTarget.closest('nav')!.querySelectorAll('details[open]')) d.removeAttribute('open'); };
  const validation = s.project?.validation, counts = validation?.counts ?? {};
  const colors = s.project?.palette.colors ?? [], fg = colors[s.foreground];
  return <main className="app-shell" data-active-panel={panel} data-dock={dock} onPointerDownCapture={track} onFocusCapture={track}>
    <nav className="menu-bar" aria-label="CyberSprite">
      <h1 className="brand"><Icon name="tile" /><span>CyberSprite</span></h1>
      <div className="menus">
        <details className="file-menu menu"><summary>{t('file')}</summary><div className="menu-pop">{(['new', 'open', 'import', 'export'] as const).map(kind => <button key={kind} onClick={e => { closeMenus(e); setOp(''); setDialog(kind); }}><Icon name={({ new: 'add', open: 'folder', import: 'sources', export: 'last' } as const)[kind]} /><span>{t(kind)}</span><kbd aria-hidden="true">{({ new: 'Ctrl+N', open: 'Ctrl+O', import: 'Ctrl+I', export: 'Ctrl+E' })[kind]}</kbd></button>)}<hr /><button onClick={e => { closeMenus(e); void act(closeProject); }}><Icon name="remove" /><span>{t('close')}</span></button></div></details>
        <details className="edit-menu menu"><summary>{t('edit')}</summary><div className="menu-pop"><button onClick={e => { closeMenus(e); void act(async () => { await rpc('history.undo'); await refresh(); }); }}><Icon name="undo" /><span>{t('undo')}</span><kbd aria-hidden="true">Ctrl+Z</kbd></button><button onClick={e => { closeMenus(e); void act(async () => { await rpc('history.redo'); await refresh(); }); }}><Icon name="redo" /><span>{t('redo')}</span><kbd aria-hidden="true">Ctrl+Y</kbd></button></div></details>
        {(['sprite', 'layer', 'frame', 'select', 'view', 'agent', 'help'] as const).map(key => <button className="menu-item" key={key} onClick={() => { setOp(''); setDialog('operation'); }}>{t(key)}</button>)}
      </div>
      <label className="op-pick"><Icon name="layer" /><select className="op-menu field mono" aria-label={t('operation')} value="" onChange={e => { setOp(e.target.value); setDialog('operation'); }}><option value="">{t('operation')}…</option>{s.schemas.map(schema => <option key={schema.name}>{schema.name}</option>)}</select></label>
      <div className="menu-right">
        {s.projectPath && <span className="path mono soft" title={s.projectPath}>{s.projectPath}</span>}
        <span className={`conn ${s.connected ? 'on' : 'off'}`}><Icon name={s.connected ? 'agent' : 'error'} />{t(s.connected ? 'connected' : 'disconnected')}</span>
        <button className="pad icon-only" aria-label={t('settings')} data-tip={t('settings')} onClick={() => setSettings(true)}><Icon name="settings" /></button>
      </div>
    </nav>
    {DEMO && <DemoNotice />}
    <ContextBar />
    <div className="workspace"><Palette /><Canvas /><Toolbar /><AgentPanel /></div>
    <div className="dock-switch" role="tablist" aria-label={t('panels')}>{([['palette', 'tile'], ['timeline', 'play'], ['agent', 'agent']] as const).map(([id, icon]) =>
      <button key={id} role="tab" className="dtab-btn" aria-selected={dock === id} onClick={() => setDock(id)}><Icon name={icon} /><span>{t(id)}</span></button>)}</div>
    <Timeline />
    <footer className="status-bar" aria-live="polite">
      <span className="sb"><span className="k">x</span><b className="mono">{s.pointer[0]}</b><span className="k">y</span><b className="mono">{s.pointer[1]}</b></span>
      <span className="sb"><span className="k">{t('color')}</span><span className={`sb-sw ${!fg || fg.endsWith('00') && fg.length === 9 ? 'checker' : ''}`} style={fg && !(fg.length === 9 && fg.endsWith('00')) ? { background: fg.slice(0, 7) } : undefined} /><b className="mono">#{s.foreground}</b></span>
      <span className="sb"><span className="k">{t('size')}</span><b className="mono">{s.project ? `${s.project.summary.width}×${s.project.summary.height}` : '—'}</b></span>
      {s.project?.summary.platform && <span className="sb sb-platform" title={s.project.summary.platform.id}><span className="k">{t('platform')}</span><b className="mono" data-testid="platform-id">{s.project.summary.platform.id}</b></span>}
      <span className="sb"><span className="k">{t('zoomLevel')}</span><b className="mono">{s.zoom * 100}%</b></span>
      <span className="sb"><span className="k">{t('revision')}</span><b className="mono" data-testid="revision">r{s.project?.summary.revision ?? 0}</b></span>
      <button className={`sb sb-valid ${validation ? validation.ok ? 'ok' : 'ng' : ''}`} onClick={() => view({ tab: 'Validate' })}><Icon name={!validation ? 'info' : validation.ok ? (counts.warning ? 'warning' : 'validate-ok') : 'error'} /><span>{t('validation')}: <b>{!validation ? '—' : validation.ok ? t('validOk') : t('validNg')}</b></span>{validation && <span className="mono soft">{counts.error ?? 0}E {counts.warning ?? 0}W</span>}</button>
      <output className="sb sb-status mono" data-testid="status">{s.status}</output>
      <span className="sb sb-error" role="alert">{s.error && <Icon name="error" />}<span className="global-error">{s.error}</span></span>
      <output className="sb job-progress mono">{s.progress ? `${s.progress.method} ${s.progress.percent}%` : ''}</output>
    </footer>
    {dialog && <SchemaDialog key={`${dialog}:${op}`} kind={dialog} initialOp={op || undefined} close={() => setDialog(null)} />}
    {settings && <SettingsDialog close={() => setSettings(false)} />}
    <Tooltip />
  </main>;
}
