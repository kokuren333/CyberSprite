import { useEffect, useRef, useState } from 'react';
import { useText } from '../i18n';
import { fileUrl } from '../api/files';
import { act, apply, openProject, rpc, useEditor, view, type OpSchema } from '../store';
import { Icon, Notch } from './chrome';
export type DialogKind = 'new' | 'open' | 'import' | 'export' | 'operation';
function defaults(schema: OpSchema | undefined) {
  const props = schema?.inputSchema.properties ?? {};
  return Object.fromEntries(Object.entries<any>(props).filter(([key, value]) => !['project', 'preview', 'expect_revision', 'idempotency_key', 'dry_run'].includes(key) && 'default' in value).map(([key, value]) => [key, value.default]));
}
function media(value: any, key = ''): { path: string; label: string }[] {
  if (Array.isArray(value)) return value.flatMap(v => media(v, key));
  if (value && typeof value === 'object') return Object.entries(value).flatMap(([k, v]) => media(v, k));
  if (typeof value === 'string' && /\.(png|gif|webp|jpg|jpeg)$/i.test(value) && /path|file|stage/.test(key)) return [{ path: value, label: key }];
  return [];
}
export function SchemaDialog({ kind, initialOp, close }: { kind: DialogKind; initialOp?: string; close: () => void }) {
  const s = useEditor(), t = useText(), dialog = useRef<HTMLDialogElement>(null);
  const candidates = s.schemas.filter(op => kind === 'new' ? op.name === 'new_project' : kind === 'import' ? op.name === 'import_image' : kind === 'export' ? op.name.startsWith('export_') : true);
  const [name, setName] = useState(initialOp ?? candidates[0]?.name ?? ''), [project, setProject] = useState(kind === 'new' ? 'untitled.csprite' : s.projectPath), [force, setForce] = useState(false), [preview, setPreview] = useState<any>(null), [accepted, setAccepted] = useState(false), [busy, setBusy] = useState(false);
  const schema = candidates.find(c => c.name === name);
  const [args, setArgs] = useState(JSON.stringify({ ...defaults(schema), ...(kind === 'new' ? { width: 32, height: 32 } : {}) }, null, 2));
  useEffect(() => { dialog.current?.showModal(); return () => dialog.current?.close(); }, []);
  const change = (text: string) => { setArgs(text); setPreview(null); setAccepted(false); };
  async function execute(dry = false) {
    setBusy(true);
    try {
      if (kind === 'open') { await openProject(project); close(); return; }
      const values = JSON.parse(args);
      if (kind === 'import') {
        const value = await rpc(dry ? 'pipeline.preview' : 'import.commit', { project, ...values });
        setPreview(value);
        if (!dry) { view({ delta: value.validation }); await openProject(project); }
      } else if (kind === 'export') {
        setPreview(await rpc('export.run', { project, op: name, ...values, force }));
      } else if (schema?.kind === 'query') setPreview(await rpc('op.apply', { project, op: name, args: values }));
      else { const value = await apply(name, values, project); setPreview(value); if (kind === 'new') close(); }
    } finally { setBusy(false); }
  }
  const icon = ({ new: 'add', open: 'folder', import: 'sources', export: 'last', operation: 'layer' } as const)[kind];
  return <dialog ref={dialog} className="schema-dialog panel" onCancel={close} aria-labelledby="dlg-title"><Notch />
    <header className="ph"><Icon name={icon} /><h2 className="ph-title" id="dlg-title"><span className="ph-name">{kind === 'operation' ? t('operation') : t(kind)}</span></h2></header>
    <div className="dlg-body">
      <label className="frow"><span className="lbl">{t('project')}</span><input className="field mono" aria-label={t('project')} value={project} onChange={e => setProject(e.target.value)} /></label>
      {kind !== 'open' && <><label className="frow"><span className="lbl">{t('operation')}</span><select className="field mono" aria-label={t('operation')} value={name} onChange={e => { setName(e.target.value); change(JSON.stringify(defaults(candidates.find(c => c.name === e.target.value)), null, 2)); }}>{candidates.map(op => <option key={op.name}>{op.name}</option>)}</select></label>
        {!schema && <p className="note warn" role="status"><Icon name="warning" />{t('notAvailable')}</p>}
        {schema?.description && <p className="soft op-desc">{schema.description}</p>}
        <details className="op-schema"><summary>{t('schema')}</summary><pre className="mono">{JSON.stringify(schema?.inputSchema, null, 2)}</pre></details>
        <label className="frow col"><span className="lbl">{t('arguments')}</span><textarea className="field mono" aria-label={t('arguments')} rows={10} cols={60} spellCheck={false} value={args} onChange={e => change(e.target.value)} /></label>
      </>}
      {kind === 'export' && <><pre className="export-plan mono">{s.project?.summary.width}×{s.project?.summary.height}{'\n'}{args}</pre><label className="chk"><input type="checkbox" checked={force} onChange={e => setForce(e.target.checked)} />{t('force')}</label></>}
      <p className="dialog-error" role="alert">{s.error && <><Icon name="error" />{s.error}</>}</p>
      {preview && <pre className="operation-result mono">{JSON.stringify(preview, null, 2)}</pre>}
      {media(preview).map(({ path, label }, i) => <figure key={i}><img className="stage-image checker" src={fileUrl(path)} alt={label} /><figcaption className="mono soft">{label}: {path}</figcaption></figure>)}
    </div>
    <footer className="dlg-actions">
      {kind === 'import' && <><button className="pad" disabled={busy || !schema} onClick={() => void act(() => execute(true))}>{t('preview')}</button><label className="chk"><input type="checkbox" disabled={!preview} checked={accepted} onChange={e => setAccepted(e.target.checked)} />{t('previewOk')}</label></>}
      <span className="grow" />
      <button className="pad" onClick={close}>{t('cancel')}</button>
      <button className="pad primary" disabled={busy || (kind !== 'open' && !schema) || (kind === 'import' && !accepted)} onClick={() => void act(() => execute())}>{t('apply')}</button>
    </footer>
  </dialog>;
}
