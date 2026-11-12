import { useText, type TextKey } from '../i18n';
import { useEditor, view, type Tool } from '../store';
import { Icon, Notch, type IconName } from './chrome';
// [tool, shortcut, icon, group]; groups are separated by a silk line on the chip.
const tools: [Tool, string, IconName, number][] = [
  ['pencil', 'B', 'pencil', 0], ['eraser', 'E', 'eraser', 0], ['line', 'L', 'line', 0], ['rect', 'U', 'rect', 0], ['ellipse', 'Shift+U', 'ellipse', 0],
  ['fill', 'G', 'fill', 0], ['eyedropper', 'I', 'eyedropper', 0],
  ['select', 'M', 'select-rect', 1], ['move', 'V', 'move', 1],
  ['hand', 'Space', 'hand', 2], ['zoom', 'Z', 'zoom', 2],
];
export function Toolbar() {
  const s = useEditor(), t = useText();
  return <section className="toolbar panel" data-panel="tools" role="toolbar" aria-orientation="vertical" aria-label={t('tool')}><Notch />
    <span className="pins left" aria-hidden="true" /><span className="pins right" aria-hidden="true" />
    {tools.map(([tool, shortcut, icon, group], i) => {
      const name = t((tool === 'select' ? 'selectTool' : tool) as TextKey);
      return <button key={tool} className={`tool-button ${i > 0 && tools[i - 1][3] !== group ? 'group-start' : ''}`} aria-pressed={s.tool === tool}
        aria-label={name} aria-keyshortcuts={shortcut} data-tip={`${name}  ${shortcut}`} onClick={() => view({ tool })}>
        <Icon name={icon} scale={2} />
      </button>;
    })}
  </section>;
}
