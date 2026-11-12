import { useText } from '../i18n';
import { useEditor, view, type Tool } from '../store';
const tools: [Tool, string][] = [['pencil', 'B'], ['eraser', 'E'], ['line', 'L'], ['rect', 'U'], ['ellipse', 'Shift+U'], ['fill', 'G'], ['eyedropper', 'I'], ['select', 'M'], ['move', 'V'], ['hand', 'Space'], ['zoom', 'Z']];
export function Toolbar() {
  const s = useEditor(), t = useText();
  return <section className="toolbar" role="toolbar" aria-label={t('tool')}>{tools.map(([tool, shortcut]) => <button key={tool} className="tool-button" aria-pressed={s.tool === tool} title={`${t(tool === 'select' ? 'selectTool' : tool)} (${shortcut})`} onClick={() => view({ tool })}>{t(tool === 'select' ? 'selectTool' : tool)}</button>)}</section>;
}
