import { useEffect, useRef, useState } from 'react';
import { useText } from '../i18n';
import { fileUrl } from '../api/files';
import { act, apply, openProject, rpc, useEditor, view, type OpSchema } from '../store';
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
  return <dialog ref={dialog} className="schema-dialog" onCancel={close}><h2>{kind === 'operation' ? t('operation') : t(kind)}</h2>
    <label>{t('project')}<input aria-label={t('project')} value={project} onChange={e => setProject(e.target.value)} /></label>
    {kind !== 'open' && <><label>{t('operation')}<select aria-label={t('operation')} value={name} onChange={e => { setName(e.target.value); change(JSON.stringify(defaults(candidates.find(c => c.name === e.target.value)), null, 2)); }}>{candidates.map(op => <option key={op.name}>{op.name}</option>)}</select></label>
      {!schema && <p role="status">{t('notAvailable')}</p>}
      <details className="op-schema"><summary>{t('schema')}</summary><pre>{JSON.stringify(schema?.inputSchema, null, 2)}</pre></details>
      <label>{t('arguments')}<textarea aria-label={t('arguments')} rows={12} cols={60} value={args} onChange={e => change(e.target.value)} /></label>
    </>}
    {kind === 'import' && <><button disabled={busy || !schema} onClick={() => void act(() => execute(true))}>{t('preview')}</button><label><input type="checkbox" disabled={!preview} checked={accepted} onChange={e => setAccepted(e.target.checked)} />{t('preview')} OK</label></>}
    {kind === 'export' && <><pre className="export-plan">{s.project?.summary.width}×{s.project?.summary.height}{'\n'}{args}</pre><label><input type="checkbox" checked={force} onChange={e => setForce(e.target.checked)} />{t('force')}</label></>}
    <button disabled={busy || (kind !== 'open' && !schema) || (kind === 'import' && !accepted)} onClick={() => void act(() => execute())}>{t('apply')}</button><button onClick={close}>{t('cancel')}</button>
    <p className="dialog-error" role="alert">{s.error}</p><pre className="operation-result">{JSON.stringify(preview, null, 2)}</pre>
    {media(preview).map(({ path, label }, i) => <figure key={i}><img className="stage-image" src={fileUrl(path)} alt={label} /><figcaption>{label}: {path}</figcaption></figure>)}
  </dialog>;
}
