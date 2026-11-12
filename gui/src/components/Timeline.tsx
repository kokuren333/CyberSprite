import { useEffect, type ReactElement } from 'react';
import { useText } from '../i18n';
import { act, apply, flattenLayers, playbackFrames, store, useEditor, view, type Layer, type Tag } from '../store';
import { Icon, Notch, PanelHead } from './chrome';
/** Greedy lanes so overlapping tags never share a row of the tag band. */
function tagLanes(tags: Tag[]): Tag[][] {
  const lanes: Tag[][] = [];
  for (const tag of [...tags].sort((a, b) => a.from - b.from || a.to - b.to)) {
    const lane = lanes.find(l => l.at(-1)!.to < tag.from);
    if (lane) lane.push(tag); else lanes.push([tag]);
  }
  return lanes;
}
const topFirst = (ls: Layer[]): Layer[] => [...ls].reverse().map(l => l.children ? { ...l, children: topFirst(l.children) } : l);
const arrow = (direction: string) => direction === 'reverse' ? '←' : direction.startsWith('pingpong') ? '↔' : '→';
export function Timeline() {
  const s = useEditor(), t = useText();
  useEffect(() => {
    if (!s.playing || !s.project) return;
    const tag = s.project.tags.find(t => t.id === s.tag), sequence = playbackFrames(tag, s.project.frames.length);
    let cursor = 0, cycles = 0, timer: ReturnType<typeof setTimeout>;
    const step = () => {
      const current = store.getState().project;
      if (!current) return;
      const frame = sequence[cursor];
      if (frame >= current.frames.length) { view({ playing: false }); return; }
      view({ frame });
      timer = setTimeout(() => {
        cursor++;
        if (cursor >= sequence.length) { cursor = 0; cycles++; if (tag?.repeat && cycles >= tag.repeat) { view({ playing: false }); return; } }
        step();
      }, current.frames[frame].duration_ms);
    };
    step(); return () => clearTimeout(timer);
  }, [s.playing, s.tag, s.project?.frames.length]);
  const frames = s.project?.frames ?? [], last = Math.max(0, frames.length - 1), layers = flattenLayers(topFirst(s.project?.layers ?? []));
  const go = (frame: number) => view({ frame: Math.max(0, Math.min(last, frame)), playing: false });
  return <section className="timeline panel" data-panel="timeline" aria-labelledby="ph-timeline"><Notch />
    <PanelHead silk="TIMELINE" title={t('timeline')} id="ph-timeline">
      <span className="legend" aria-hidden="true"><span><i className="cel-glyph present" />{t('present')}</span><span><i className="cel-glyph linked" />{t('linked')}</span><span><i className="cel-glyph empty" />{t('empty')}</span></span>
    </PanelHead>
    <div className="playback-controls">
      <span className="transport">
        <button className="pad icon-only" aria-label={t('firstFrame')} data-tip={t('firstFrame')} onClick={() => go(0)}><Icon name="first" /></button>
        <button className="pad icon-only" aria-label={t('previous')} data-tip={`${t('previous')}  ←`} onClick={() => go(s.frame - 1)}><Icon name="step-prev" /></button>
        <button className={`pad icon-only ${s.playing ? 'on' : ''}`} aria-label={t(s.playing ? 'stop' : 'play')} data-tip={`${t(s.playing ? 'stop' : 'play')}  Enter`} onClick={() => view({ playing: !s.playing })}><Icon name={s.playing ? 'pause' : 'play'} /></button>
        <button className="pad icon-only" aria-label={t('next')} data-tip={`${t('next')}  →`} onClick={() => go(s.frame + 1)}><Icon name="step-next" /></button>
        <button className="pad icon-only" aria-label={t('lastFrame')} data-tip={t('lastFrame')} onClick={() => go(last)}><Icon name="last" /></button>
      </span>
      <span className="pad val mono frame-counter" aria-label={t('frame')}>{s.frame} / {last}</span>
      <span className="pad val mono" aria-label={t('duration')}>{frames[s.frame]?.duration_ms ?? 0} ms</span>
      <span className="vsep" aria-hidden="true" />
      <label className="fld"><Icon name="tag" /><span className="sr-only">{t('playRange')}</span>
        <select className="field" aria-label={t('timeline')} value={s.tag} onChange={e => view({ tag: e.target.value, playing: false })}><option value="">{t('all')}</option>{s.project?.tags.map(tag => <option value={tag.id} key={tag.id}>{tag.name}: {tag.from}–{tag.to} ({tag.direction}, {tag.repeat})</option>)}</select></label>
      <label className="pad toggle"><input type="checkbox" checked={s.onion} onChange={e => view({ onion: e.target.checked })} /><Icon name="onion" />{t('onion')}</label>
      <label className="pad toggle"><input type="checkbox" checked={s.grid} onChange={e => view({ grid: e.target.checked })} /><Icon name="grid" />{t('grid')}</label>
    </div>
    <div className="timeline-scroll">
      <table className="timeline-grid">
        <colgroup><col className="col-layer" />{frames.map((_, i) => <col key={i} className="col-frame" />)}<col /></colgroup>
        <thead>
          {tagLanes(s.project?.tags ?? []).map((lane, i) => {
            const cells: ReactElement[] = []; let at = 0;
            for (const tag of lane) {
              if (tag.from > at) cells.push(<td key={`gap${at}`} colSpan={tag.from - at} />);
              cells.push(<td key={tag.id} colSpan={tag.to - tag.from + 1} className="tag-cell"><button className={`tagspan ${s.tag === tag.id ? 'on' : ''}`} aria-pressed={s.tag === tag.id} data-tip={`${tag.name}: ${tag.from}–${tag.to}  ${tag.direction}${tag.repeat ? ` ×${tag.repeat}` : ` · ${t('loop')}`}`} onClick={() => view({ tag: s.tag === tag.id ? '' : tag.id, playing: false })}>
                <span className="tag-dir" aria-hidden="true">{arrow(tag.direction)}</span><b>{tag.name}</b><span className="sr-only">{tag.direction}{tag.repeat ? ` ×${tag.repeat}` : ` ${t('loop')}`}</span></button></td>);
              at = tag.to + 1;
            }
            if (at < frames.length) cells.push(<td key="tail" colSpan={frames.length - at} />);
            return <tr key={`lane${i}`} className="tag-row"><th scope="row" className="lane-head soft">{i === 0 ? t('tags') : ''}</th>{cells}</tr>;
          })}
          <tr className="frame-row"><th scope="col" className="lane-head soft">{t('layer')}</th>{frames.map((frame, index) => <th scope="col" key={index} className={index === s.frame ? 'cur' : ''}>
            <button className="frame-no mono" aria-current={index === s.frame ? 'true' : undefined} onClick={() => view({ frame: index })}>{index}</button>
            <input className="dur mono" aria-label={`${t('duration')} ${index}`} type="number" min="1" max="65535" defaultValue={frame.duration_ms} key={`${index}:${frame.duration_ms}`} onBlur={e => { const duration_ms = Math.trunc(+e.target.value); if (duration_ms !== frame.duration_ms) void act(() => apply('set_frame_duration', { frames: [index], duration_ms })); }} />
          </th>)}<th className="fill-col" aria-hidden="true" /></tr>
        </thead>
        <tbody>{layers.map(layer => <tr key={layer.id} className={`${s.layer === layer.id ? 'sel' : ''} ${layer.visible ? '' : 'hidden-layer'}`}><th scope="row" className="layer-head"><div className="lh">
          <label className="icon-toggle" data-tip={layer.visible ? t('hideLayer') : t('showLayer')}><input aria-label={`${layer.name} visible`} type="checkbox" checked={layer.visible} onChange={e => void act(() => apply('update_layer', { layer: layer.id, visible: e.target.checked }))} /><Icon name={layer.visible ? 'eye' : 'eye-off'} /></label>
          <label className="icon-toggle" data-tip={layer.locked ? t('unlockLayer') : t('lockLayer')}><input aria-label={`${layer.name} locked`} type="checkbox" checked={layer.locked} onChange={e => void act(() => apply('update_layer', { layer: layer.id, locked: e.target.checked }))} /><Icon name={layer.locked ? 'lock' : 'unlock'} /></label>
          <button className="layer-name" aria-pressed={s.layer === layer.id} onClick={() => view({ layer: layer.id })}><Icon name={layer.type === 'group' ? 'folder' : layer.type === 'tilemap' ? 'tile' : 'layer'} /><span className="lname">{layer.name}</span><span className="ltype soft">{layer.type}</span></button>
          <span className="lop mono soft" aria-label={t('opacity')}>{Math.round((layer.opacity ?? 255) * 100 / 255)}</span>
        </div></th>{frames.map((_, frame) => {
          const cel = layer.cels?.find(c => c.frame === frame), state = !cel ? 'empty' : 'link' in cel ? 'linked' : 'present';
          return <td key={frame} className={`${frame === s.frame ? 'cur' : ''} ${state === 'linked' ? 'link-left' : ''}`}>
            <button className={`timeline-cel cel-${state}`} aria-pressed={s.frame === frame && s.layer === layer.id} title={`${layer.name} / ${frame}: ${t(state)}`} onClick={() => view({ layer: layer.id, frame, playing: false })}>
              <i className="cel-glyph" aria-hidden="true" /><span className="sr-only">{t(state)}</span></button></td>;
        })}<td className="fill-col" aria-hidden="true" /></tr>)}</tbody>
      </table>
    </div>
  </section>;
}
