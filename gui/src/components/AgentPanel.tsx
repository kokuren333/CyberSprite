import { useState } from 'react';
import { useText, type TextKey } from '../i18n';
import { fileUrl } from '../api/files';
import { act, rpc, useEditor, view, refresh } from '../store';
import { Icon, Notch, PanelHead, type IconName } from './chrome';
const isAgent = (actor: string) => actor.startsWith('agent');
const clock = (time?: string) => time ? new Date(time).toTimeString().slice(0, 5) : '';
const levelIcon: Record<string, IconName> = { error: 'error', warning: 'warning', info: 'info' };
function frameRange(frames: number[]) {
  if (!frames.length) return '';
  const sorted = [...new Set(frames)].sort((a, b) => a - b), contiguous = sorted.at(-1)! - sorted[0] === sorted.length - 1;
  return sorted.length === 1 ? `f${sorted[0]}` : contiguous ? `f${sorted[0]}–${sorted.at(-1)}` : sorted.map(f => `f${f}`).join(',');
}
export function AgentPanel() {
  const s = useEditor(), t = useText(), [from, setFrom] = useState(0), [to, setTo] = useState(0), [source, setSource] = useState<any>(null), [picked, setPicked] = useState<number | null>(null);
  async function compare(a: number, b: number, tab: 'Diff' | 'Activity' = 'Diff') {
    const result = await rpc('op.apply', { op: 'diff_preview', args: { from_revision: a, to_revision: b, inline: true } });
    view({ diff: result.result, tab, change: { changed: { frames: result.result.frames } } });
  }
  async function restore(revision: number) {
    await rpc('history.undo', { to_revision: revision, expect_revision: s.project!.summary.revision });
    await refresh();
  }
  const validation = s.project?.validation, counts = validation?.counts ?? {};
  const tabs: { id: 'Activity' | 'Validate' | 'Diff' | 'Sources'; icon: IconName; badge?: string }[] = [
    { id: 'Activity', icon: 'agent' },
    { id: 'Validate', icon: validation && !validation.ok ? 'error' : counts.warning ? 'warning' : 'validate-ok', badge: validation ? String((counts.error ?? 0) + (counts.warning ?? 0) || '') : '' },
    { id: 'Diff', icon: 'diff' },
    { id: 'Sources', icon: 'sources' },
  ];
  const latest = s.project?.history.entries?.[0];
  return <aside className="agent-panel panel" data-panel="agent" aria-labelledby="ph-agent"><Notch />
    <PanelHead silk="AGENT" title={t('agent')} id="ph-agent">{latest && <span className="mono">{t('lastCommit')} r{latest.revision}</span>}</PanelHead>
    {/* signal: 3-step pixel pulse along the trace to the Activity tab when another actor commits (W1) */}
    {s.change?.actor && s.change.actor !== 'gui' && <span key={s.change.revision} className="signal" aria-hidden="true"><i /><i /><i /></span>}
    <div className="agent-tabs" role="tablist">{tabs.map(({ id, icon, badge }) => <button id={`tab-${id}`} role="tab" aria-selected={s.tab === id} aria-controls={`panel-${id}`} key={id} className="atab" onClick={() => view({ tab: id })}>
      <Icon name={icon} /><span>{t(id)}</span>{badge ? <span className="badge mono">{badge}</span> : null}</button>)}</div>
    <section className={`agent-content agent-${s.tab.toLowerCase()}`} role="tabpanel" aria-labelledby={`tab-${s.tab}`} id={`panel-${s.tab}`}>
      {s.tab === 'Activity' && <ol className="activity-list">{s.project?.history.entries.map((entry: any) => {
        const frames = (entry.changed?.frames ?? []) as { frame: number; pixels_changed: number }[];
        const pixels = frames.reduce((n, f) => n + (f.pixels_changed ?? 0), 0);
        return <li key={entry.revision} className={`act ${picked === entry.revision ? 'sel' : ''} ${entry.revision === s.project!.summary.revision ? 'head' : ''}`}>
          <button className="activity-entry" onClick={() => { setPicked(entry.revision); void act(() => compare(Math.max(0, entry.revision - 1), entry.revision, 'Activity')); }}>
            <span className="act-head"><b className="rev mono">r{entry.revision}</b><span className={`actor ${isAgent(entry.actor) ? 'agent' : 'human'}`}><Icon name={isAgent(entry.actor) ? 'agent' : 'human'} />{entry.actor}</span><span className="when soft mono">{clock(entry.time)}</span></span>
            <span className="act-label">{entry.label ?? t(entry.kind === 'create' ? 'created' : 'commit')}</span>
            <span className="act-meta soft">{entry.ops.map((op: string, i: number) => <code className="op" key={i}>{op}</code>)}{frames.length > 0 && <span className="mono">{frameRange(frames.map(f => f.frame))}</span>}{pixels > 0 && <span className="mono">{pixels} px</span>}</span>
          </button>
          <button className="pad small restore" disabled={entry.revision >= s.project!.summary.revision} onClick={() => void act(() => restore(entry.revision))}><Icon name="undo" />{t('restore')}</button>
        </li>;
      })}</ol>}
      {s.tab === 'Validate' && <div className="tab-body">
        <div className="vsum"><span className={`vstate ${validation?.ok ? 'ok' : 'ng'}`}><Icon name={validation?.ok ? 'validate-ok' : 'error'} /><b>{validation?.ok ? t('validOk') : t('validNg')}</b></span>
          <span className="mono soft">{t('errors')} {counts.error ?? 0} · {t('warnings')} {counts.warning ?? 0} · {t('infos')} {counts.info ?? 0}</span>
          <button className="pad small" onClick={() => void act(async () => { const value = await rpc('validate.run'); if (s.project) view({ project: { ...s.project, validation: value.result } }); })}>{t('refresh')}</button></div>
        <ul className="validation-issues">{validation?.issues.map((issue: any, i: number) => {
          const level = issue.level ?? issue.severity ?? 'info', frame = issue.where?.frames?.[0] ?? issue.where?.frame;
          return <li key={i}><button className={`issue ${level}`} onClick={() => view({ frame: frame ?? s.frame, layer: issue.where?.layer ?? s.layer, selection: issue.where?.bbox ? { type: 'rect', ...issue.where.bbox } : s.selection })}>
            <Icon name={levelIcon[level] ?? 'info'} /><span className="issue-body"><span className="issue-head"><code className="mono">{issue.rule ?? issue.code}</code><span className="soft">{t(level as TextKey) ?? level}{frame !== undefined ? ` · f${frame}` : ''}</span></span><span>{issue.message}</span></span></button></li>;
        })}</ul>
        <details className="metrics"><summary>{t('metrics')}</summary><pre className="validation-metrics">{JSON.stringify(validation?.metrics, null, 2)}</pre></details>
        {s.delta && <details className="metrics"><summary>{t('lastDelta')}</summary><pre className="validation-delta">{JSON.stringify(s.delta, null, 2)}</pre></details>}
      </div>}
      {s.tab === 'Diff' && <div className="tab-body">
        <div className="diff-form"><label className="fld"><span className="lbl">{t('from')}</span><input className="field num" type="number" min="0" value={from} onChange={e => setFrom(Math.trunc(+e.target.value))} /></label>
          <label className="fld"><span className="lbl">{t('to')}</span><input className="field num" type="number" min="0" value={to} onChange={e => setTo(Math.trunc(+e.target.value))} /></label>
          <button className="pad" onClick={() => void act(() => compare(from, to))}><Icon name="diff" />{t('compare')}</button></div>
        <div className="diff-images">{s.diff?.images?.map((image: string, i: number) => <img className="diff-image checker" key={i} src={`data:image/png;base64,${image}`} alt={`${t('Diff')} ${i}`} />)}</div>
        {s.diff?.frames && <pre className="mono small-pre">{JSON.stringify(s.diff.frames, null, 2)}</pre>}
      </div>}
      {s.tab === 'Sources' && <div className="tab-body">
        <div className="row-actions"><button className="pad small" onClick={() => void act(async () => view({ sources: await rpc('sources.list') }))}>{t('refresh')}</button><button className="pad small" disabled={!s.underlay} onClick={() => view({ underlay: null })}>{t('clear')}</button></div>
        {(() => { const list = (s.sources?.result?.sources ?? s.sources?.sources ?? s.project?.sources.sources ?? []); return list.length ? <ul className="sources-list">{list.map((entry: any) => <li key={entry.id}><button className="source-entry" onClick={() => void act(async () => setSource(await rpc('sources.get', { id: entry.id })))}><Icon name="sources" /><b className="mono">{entry.id}</b><span>{entry.provider}</span><span className="soft">{entry.license}</span></button></li>)}</ul> : <p className="empty-note soft">{t('noSources')}</p>; })()}
        {source && <pre className="mono small-pre">{JSON.stringify(source, null, 2)}</pre>}
        {(source?.result ?? source)?.files?.map((file: any) => <figure key={file.path}><img className="source-image checker" src={fileUrl(file.path)} alt={t('source')} /><figcaption className="mono soft">{file.path}</figcaption><button className="pad small" onClick={() => view({ underlay: file.path })}>{t('underlay')}</button></figure>)}
      </div>}
    </section>
  </aside>;
}
