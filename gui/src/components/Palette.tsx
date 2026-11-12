import { useText } from '../i18n';
import { useEditor, view } from '../store';
export function Palette() {
  const s = useEditor(), t = useText();
  return <section className="palette-panel" aria-label={t('palette')}><h2>{t('palette')}</h2>
    <p>{t('foreground')}: {s.foreground} / {t('background')}: {s.background}</p>
    <ol className="palette-list">{s.project?.palette.colors.map((color, index) => <li key={index}>
      <button className="palette-color" aria-pressed={s.foreground === index} title={`${index}: ${color}`} onClick={() => view({ foreground: index })} onContextMenu={e => { e.preventDefault(); view({ background: index }); }}>{index}: {color}</button>
    </li>)}</ol>
  </section>;
}
