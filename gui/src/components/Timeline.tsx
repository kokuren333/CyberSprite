import { useEffect } from 'react';
import { useText } from '../i18n';
import { act, apply, flattenLayers, playbackFrames, store, useEditor, view } from '../store';
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
  return <section className="timeline" aria-label={t('timeline')}><h2>{t('timeline')}</h2>
    <div className="playback-controls"><select aria-label={t('timeline')} value={s.tag} onChange={e => view({ tag: e.target.value, playing: false })}><option value="">{t('all')}</option>{s.project?.tags.map(tag => <option value={tag.id} key={tag.id}>{tag.name}: {tag.from}–{tag.to} ({tag.direction}, {tag.repeat})</option>)}</select>
      <button onClick={() => view({ playing: !s.playing })}>{t(s.playing ? 'stop' : 'play')}</button>
      <button onClick={() => view({ frame: Math.max(0, s.frame - 1), playing: false })}>{t('previous')}</button><button onClick={() => view({ frame: Math.min((s.project?.frames.length ?? 1) - 1, s.frame + 1), playing: false })}>{t('next')}</button>
      <label><input type="checkbox" checked={s.onion} onChange={e => view({ onion: e.target.checked })} />{t('onion')}</label>
      <label><input type="checkbox" checked={s.grid} onChange={e => view({ grid: e.target.checked })} />{t('grid')}</label>
    </div>
    <table className="timeline-grid"><thead><tr><th>{t('layer')}</th>{s.project?.frames.map((frame, index) => <th key={index}><button onClick={() => view({ frame: index })}>{index}</button><input aria-label={`${t('duration')} ${index}`} type="number" min="1" max="65535" defaultValue={frame.duration_ms} key={`${index}:${frame.duration_ms}`} onBlur={e => { const duration_ms = Math.trunc(+e.target.value); if (duration_ms !== frame.duration_ms) void act(() => apply('set_frame_duration', { frames: [index], duration_ms })); }} /></th>)}</tr></thead>
      <tbody>{flattenLayers(s.project?.layers ?? []).map(layer => <tr key={layer.id}><th><button onClick={() => view({ layer: layer.id })}>{layer.name} ({layer.type})</button><label><input aria-label={`${layer.name} visible`} type="checkbox" checked={layer.visible} onChange={e => void act(() => apply('update_layer', { layer: layer.id, visible: e.target.checked }))} />visible</label><label><input aria-label={`${layer.name} locked`} type="checkbox" checked={layer.locked} onChange={e => void act(() => apply('update_layer', { layer: layer.id, locked: e.target.checked }))} />locked</label></th>{s.project?.frames.map((_, frame) => {
        const cel = layer.cels?.find(c => c.frame === frame), state = !cel ? 'empty' : 'link' in cel ? 'linked' : 'present';
        return <td key={frame}><button className={`timeline-cel cel-${state}`} aria-pressed={s.frame === frame && s.layer === layer.id} title={`${layer.name} / ${frame}: ${t(state)}`} onClick={() => view({ layer: layer.id, frame, playing: false })}>{t(state)}</button></td>;
      })}</tr>)}</tbody>
    </table>
  </section>;
}
