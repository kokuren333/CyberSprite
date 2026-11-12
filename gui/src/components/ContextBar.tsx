import { useText } from '../i18n';
import { useEditor, view } from '../store';
export function ContextBar() {
  const s = useEditor(), t = useText();
  return <section className="context-bar" aria-label={t('tool')}>
    <label>{t('brush')}<input aria-label={t('brush')} type="number" min="1" max="64" value={s.brush.size} onChange={e => view({ brush: { ...s.brush, size: Math.max(1, Math.min(64, Math.trunc(+e.target.value))) }, pixelPerfect: false })} /></label>
    <label>{t('shape')}<select value={s.brush.shape} onChange={e => view({ brush: { ...s.brush, shape: e.target.value as 'square' | 'circle' } })}><option value="square">{t('square')}</option><option value="circle">{t('circle')}</option></select></label>
    <label><input type="checkbox" checked={s.filled} onChange={e => view({ filled: e.target.checked })} />{t('filled')}</label>
    <label><input type="checkbox" disabled={s.brush.size !== 1} checked={s.pixelPerfect} onChange={e => view({ pixelPerfect: e.target.checked })} />{t('perfect')}</label>
    <label>{t('connectivity')}<select value={s.connectivity} onChange={e => view({ connectivity: +e.target.value as 4 | 8 })}><option>4</option><option>8</option></select></label>
  </section>;
}
