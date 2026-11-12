import { useState } from 'react';
import { useText } from '../i18n';
import { fileUrl } from '../api/files';
import { act, rpc, useEditor, view, refresh } from '../store';
export function AgentPanel() {
  const s = useEditor(), t = useText(), [from, setFrom] = useState(0), [to, setTo] = useState(0), [source, setSource] = useState<any>(null);
  async function compare(a: number, b: number) {
    const result = await rpc('op.apply', { op: 'diff_preview', args: { from_revision: a, to_revision: b, inline: true } });
    view({ diff: result.result, tab: 'Diff', change: { changed: { frames: result.result.frames } } });
  }
  async function restore(revision: number) {
    await rpc('history.undo', { to_revision: revision, expect_revision: s.project!.summary.revision });
    await refresh();
  }
  return <aside className="agent-panel" aria-label={t('agent')}><div className="agent-tabs" role="tablist">{(['Activity', 'Validate', 'Diff', 'Sources'] as const).map(tab => <button id={`tab-${tab}`} role="tab" aria-selected={s.tab === tab} aria-controls={`panel-${tab}`} key={tab} onClick={() => view({ tab })}>{t(tab)}</button>)}</div>
    <section className={`agent-content agent-${s.tab.toLowerCase()}`} role="tabpanel" aria-labelledby={`tab-${s.tab}`} id={`panel-${s.tab}`}>
      {s.tab === 'Activity' && <ol className="activity-list">{s.project?.history.entries.map((entry: any) => <li key={entry.revision}>
        <button className="activity-entry" onClick={() => void act(() => compare(Math.max(0, entry.revision - 1), entry.revision))}>r{entry.revision} {entry.actor} {entry.label} {entry.ops.join(', ')} {JSON.stringify(entry.changed)}</button>
        <button disabled={entry.revision >= s.project!.summary.revision} onClick={() => void act(() => restore(entry.revision))}>{t('restore')}</button>
      </li>)}</ol>}
      {s.tab === 'Validate' && <><button onClick={() => void act(async () => { const value = await rpc('validate.run'); if (s.project) view({ project: { ...s.project, validation: value.result } }); })}>{t('refresh')}</button><ul className="validation-issues">{s.project?.validation.issues.map((issue: any, i: number) => <li key={i}><button onClick={() => view({ frame: issue.where?.frame ?? s.frame, layer: issue.where?.layer ?? s.layer, selection: issue.where?.bbox ? { type: 'rect', ...issue.where.bbox } : s.selection })}>{issue.severity}: {issue.rule ?? issue.code} {issue.message} {JSON.stringify(issue.where)}</button></li>)}</ul><pre className="validation-metrics">{JSON.stringify(s.project?.validation.metrics, null, 2)}</pre><pre className="validation-delta">{JSON.stringify(s.delta, null, 2)}</pre></>}
      {s.tab === 'Diff' && <><label>{t('from')}<input type="number" min="0" value={from} onChange={e => setFrom(Math.trunc(+e.target.value))} /></label><label>{t('to')}<input type="number" min="0" value={to} onChange={e => setTo(Math.trunc(+e.target.value))} /></label><button onClick={() => void act(() => compare(from, to))}>{t('compare')}</button>{s.diff?.images?.map((image: string, i: number) => <img className="diff-image" key={i} src={`data:image/png;base64,${image}`} alt={`${t('Diff')} ${i}`} />)}<pre>{JSON.stringify(s.diff?.frames, null, 2)}</pre></>}
      {s.tab === 'Sources' && <><button onClick={() => void act(async () => view({ sources: await rpc('sources.list') }))}>{t('refresh')}</button><button onClick={() => view({ underlay: null })}>{t('clear')}</button><ul className="sources-list">{(s.sources?.result?.sources ?? s.sources?.sources ?? s.project?.sources.sources ?? []).map((entry: any) => <li key={entry.id}><button onClick={() => void act(async () => setSource(await rpc('sources.get', { id: entry.id })))}>{entry.id}: {entry.provider} ({entry.license})</button></li>)}</ul><pre>{JSON.stringify(source, null, 2)}</pre>{(source?.result ?? source)?.files?.map((file: any) => <figure key={file.path}><img className="source-image" src={fileUrl(file.path)} alt={t('source')} /><figcaption>{file.path}</figcaption><button onClick={() => view({ underlay: file.path })}>{t('underlay')}</button></figure>)}</>}
    </section>
  </aside>;
}
