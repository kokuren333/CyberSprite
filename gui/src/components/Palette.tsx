import { useText } from '../i18n';
import { useEditor, view } from '../store';
import { Notch, PanelHead } from './chrome';
const isClear = (color?: string) => !color || (color.length === 9 && color.endsWith('00'));
const hex = (color?: string) => (color ?? '').slice(1, 7).toUpperCase();
function Chip({ color, className = '' }: { color?: string; className?: string }) {
  return <span className={`chip ${className} ${isClear(color) ? 'checker' : ''}`} style={isClear(color) ? undefined : { background: color!.slice(0, 7) }} />;
}
export function Palette() {
  const s = useEditor(), t = useText(), colors = s.project?.palette.colors ?? [];
  const fg = colors[s.foreground], bg = colors[s.background];
  return <section className="palette-panel panel" data-panel="palette" aria-labelledby="ph-palette"><Notch />
    <PanelHead silk="PALETTE" title={t('palette')} id="ph-palette"><span className="mono">{colors.length} / 256</span></PanelHead>
    <div className="fgbg">
      <span className="fgbg-stack" aria-hidden="true"><Chip color={bg} className="bg" /><Chip color={fg} className="fg" /></span>
      <dl>
        <dt>{t('fgShort')}</dt><dd><b className="mono">#{s.foreground}</b> <span className="mono soft">{isClear(fg) ? t('transparent') : hex(fg)}</span></dd>
        <dt>{t('bgShort')}</dt><dd><b className="mono">#{s.background}</b> <span className="mono soft">{isClear(bg) ? t('transparent') : hex(bg)}</span></dd>
      </dl>
    </div>
    <ol className="palette-list" aria-label={t('palette')}>{colors.map((color, index) => {
      const role = s.foreground === index ? 'fg' : s.background === index ? 'bg' : '';
      return <li key={index} className={`sw-cell ${role}`}>
        <button className="palette-color" aria-pressed={s.foreground === index} title={`${index}: ${isClear(color) ? t('transparent') : hex(color)}`}
          aria-label={`${index} ${isClear(color) ? t('transparent') : hex(color)}${role ? ` (${t(role === 'fg' ? 'foreground' : 'background')})` : ''}`}
          onClick={() => view({ foreground: index })} onContextMenu={e => { e.preventDefault(); view({ background: index }); }}>
          <Chip color={color} />{role && <span className={`role-tag ${role}`} aria-hidden="true">{role.toUpperCase()}</span>}
        </button>
        <span className="idx mono" aria-hidden="true">{String(index).padStart(2, '0')}</span>
      </li>;
    })}</ol>
    <div className="panel-foot"><button className="pad small swap" aria-label={t('swapColors')} data-tip={`${t('swapColors')}  X`} onClick={() => view({ foreground: s.background, background: s.foreground })}>{t('swap')}</button><p className="panel-hint soft">{t('paletteHint')}</p></div>
  </section>;
}
