import { useText, type TextKey } from '../i18n';
import { useEditor, view } from '../store';
import { Icon, type IconName } from './chrome';
const toolIcon: Record<string, IconName> = { pencil: 'pencil', eraser: 'eraser', line: 'line', rect: 'rect', ellipse: 'ellipse', fill: 'fill', eyedropper: 'eyedropper', select: 'select-rect', move: 'move', hand: 'hand', zoom: 'zoom' };
export function ContextBar() {
  const s = useEditor(), t = useText();
  const size = (v: number) => view({ brush: { ...s.brush, size: Math.max(1, Math.min(64, Math.trunc(v) || 1)) }, pixelPerfect: false });
  return <section className="context-bar" aria-label={t('toolSettings')}>
    <span className="ctx-tool"><Icon name={toolIcon[s.tool]} /><b>{t((s.tool === 'select' ? 'selectTool' : s.tool) as TextKey)}</b></span>
    <span className="vsep" aria-hidden="true" />
    <span className="fld"><label className="lbl" htmlFor="ctx-brush">{t('brush')}</label>
      <button className="pad icon-only" aria-label={t('brushSmaller')} data-tip={`${t('brushSmaller')}  [`} onClick={() => size(s.brush.size - 1)}><Icon name="remove" /></button>
      <input id="ctx-brush" className="field num" aria-label={t('brush')} type="number" min="1" max="64" value={s.brush.size} onChange={e => size(+e.target.value)} />
      <span className="unit soft">px</span>
      <button className="pad icon-only" aria-label={t('brushLarger')} data-tip={`${t('brushLarger')}  ]`} onClick={() => size(s.brush.size + 1)}><Icon name="add" /></button>
    </span>
    <span className="fld"><span className="lbl" id="ctx-shape">{t('shape')}</span>
      <span className="seg" role="radiogroup" aria-labelledby="ctx-shape">{(['square', 'circle'] as const).map(shape =>
        <button key={shape} className={`pad ${s.brush.shape === shape ? 'on' : ''}`} role="radio" aria-checked={s.brush.shape === shape} onClick={() => view({ brush: { ...s.brush, shape } })}>
          <span className={`shape-dot ${shape}`} aria-hidden="true" />{t(shape)}</button>)}</span>
    </span>
    <span className="vsep" aria-hidden="true" />
    <label className="chk"><input type="checkbox" checked={s.filled} onChange={e => view({ filled: e.target.checked })} />{t('filled')}</label>
    <label className="chk"><input type="checkbox" disabled={s.brush.size !== 1} checked={s.pixelPerfect} onChange={e => view({ pixelPerfect: e.target.checked })} />{t('perfect')}</label>
    <span className="vsep" aria-hidden="true" />
    <span className="fld"><span className="lbl" id="ctx-conn">{t('connectivity')}</span>
      <span className="seg" role="radiogroup" aria-labelledby="ctx-conn">{([4, 8] as const).map(n =>
        <button key={n} className={`pad mono ${s.connectivity === n ? 'on' : ''}`} role="radio" aria-checked={s.connectivity === n} onClick={() => view({ connectivity: n })}>{n}</button>)}</span>
    </span>
    <span className="ctx-right">
      <span className="fld"><span className="lbl">{t('ink')}</span><span className="pad val mono">{t('fgShort')} #{s.foreground}</span></span>
    </span>
  </section>;
}
