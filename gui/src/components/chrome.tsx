import type { ReactNode } from 'react';
/** Presentation primitives for the "Solder Mask" theme. Pixel-exact: every shape is
 * drawn as 1×1 runs in an SVG with shape-rendering: crispEdges, or is an icon PNG
 * exported from assets/ui/icons/*.csprite by the CyberSprite CLI (npm run icons). */

export const ICONS = [
  'add', 'agent', 'diff', 'ellipse', 'eraser', 'error', 'eye', 'eye-off', 'eyedropper', 'fill',
  'first', 'folder', 'grid', 'hand', 'human', 'info', 'last', 'layer', 'line', 'link',
  'lock', 'move', 'onion', 'pause', 'pencil', 'play', 'rect', 'redo', 'remove', 'select-rect',
  'settings', 'sources', 'step-next', 'step-prev', 'tag', 'tile', 'undo', 'unlock', 'validate-ok', 'warning', 'zoom',
] as const;
export type IconName = typeof ICONS[number];

/** 16×16 icon at an integer scale (1 = 16 px, 2 = 32 px). Decorative unless `label`. */
export function Icon({ name, scale = 1, label }: { name: IconName; scale?: 1 | 2; label?: string }) {
  return <img className={`ico ico-x${scale}`} src={`${import.meta.env.BASE_URL}icons/${name}.png`} width={16 * scale} height={16 * scale}
    alt={label ?? ''} aria-hidden={label ? undefined : true} draggable={false} />;
}

/** Run-length path of a pixel set ("M x y h w v1 h-w z" per horizontal run). */
function runs(pixels: Iterable<[number, number]>): string {
  const rows = new Map<number, number[]>();
  for (const [x, y] of pixels) (rows.get(y) ?? rows.set(y, []).get(y)!).push(x);
  let d = '';
  for (const [y, xs] of [...rows].sort((a, b) => a[0] - b[0])) {
    xs.sort((a, b) => a - b);
    for (let i = 0; i < xs.length;) {
      let j = i; while (j + 1 < xs.length && xs[j + 1] === xs[j] + 1) j++;
      d += `M${xs[i]} ${y}h${j - i + 1}v1h-${j - i + 1}z`; i = j + 1;
    }
  }
  return d;
}

// 5×7 pixel font for silk-screen labels (original glyphs, docs/design/theme-options/tools/pixels.py).
const FONT: Record<string, string[]> = {
  A: [' ### ', '#   #', '#   #', '#####', '#   #', '#   #', '#   #'], B: ['#### ', '#   #', '#   #', '#### ', '#   #', '#   #', '#### '],
  C: [' ### ', '#   #', '#    ', '#    ', '#    ', '#   #', ' ### '], D: ['#### ', '#   #', '#   #', '#   #', '#   #', '#   #', '#### '],
  E: ['#####', '#    ', '#    ', '#### ', '#    ', '#    ', '#####'], F: ['#####', '#    ', '#    ', '#### ', '#    ', '#    ', '#    '],
  G: [' ### ', '#   #', '#    ', '# ###', '#   #', '#   #', ' ####'], H: ['#   #', '#   #', '#   #', '#####', '#   #', '#   #', '#   #'],
  I: ['###', ' # ', ' # ', ' # ', ' # ', ' # ', '###'], J: ['  ###', '   # ', '   # ', '   # ', '#  # ', '#  # ', ' ##  '],
  K: ['#   #', '#  # ', '# #  ', '##   ', '# #  ', '#  # ', '#   #'], L: ['#    ', '#    ', '#    ', '#    ', '#    ', '#    ', '#####'],
  M: ['#   #', '## ##', '# # #', '# # #', '#   #', '#   #', '#   #'], N: ['#   #', '##  #', '# # #', '# # #', '#  ##', '#   #', '#   #'],
  O: [' ### ', '#   #', '#   #', '#   #', '#   #', '#   #', ' ### '], P: ['#### ', '#   #', '#   #', '#### ', '#    ', '#    ', '#    '],
  Q: [' ### ', '#   #', '#   #', '#   #', '# # #', '#  # ', ' ## #'], R: ['#### ', '#   #', '#   #', '#### ', '# #  ', '#  # ', '#   #'],
  S: [' ####', '#    ', '#    ', ' ### ', '    #', '    #', '#### '], T: ['#####', '  #  ', '  #  ', '  #  ', '  #  ', '  #  ', '  #  '],
  U: ['#   #', '#   #', '#   #', '#   #', '#   #', '#   #', ' ### '], V: ['#   #', '#   #', '#   #', '#   #', '#   #', ' # # ', '  #  '],
  W: ['#   #', '#   #', '#   #', '# # #', '# # #', '# # #', ' # # '], X: ['#   #', '#   #', ' # # ', '  #  ', ' # # ', '#   #', '#   #'],
  Y: ['#   #', '#   #', ' # # ', '  #  ', '  #  ', '  #  ', '  #  '], Z: ['#####', '    #', '   # ', '  #  ', ' #   ', '#    ', '#####'],
  '0': [' ### ', '#   #', '#  ##', '# # #', '##  #', '#   #', ' ### '], '1': [' # ', '## ', ' # ', ' # ', ' # ', ' # ', '###'],
  '2': [' ### ', '#   #', '    #', '   # ', '  #  ', ' #   ', '#####'], '3': ['#### ', '    #', '    #', ' ### ', '    #', '    #', '#### '],
  '4': ['   # ', '  ## ', ' # # ', '#  # ', '#####', '   # ', '   # '], '5': ['#####', '#    ', '#### ', '    #', '    #', '#   #', ' ### '],
  '6': [' ### ', '#    ', '#    ', '#### ', '#   #', '#   #', ' ### '], '7': ['#####', '    #', '   # ', '  #  ', ' #   ', ' #   ', ' #   '],
  '8': [' ### ', '#   #', '#   #', ' ### ', '#   #', '#   #', ' ### '], '9': [' ### ', '#   #', '#   #', ' ####', '    #', '    #', ' ### '],
  '-': ['   ', '   ', '   ', '###', '   ', '   ', '   '], ':': [' ', '#', ' ', ' ', ' ', '#', ' '], '.': [' ', ' ', ' ', ' ', ' ', ' ', '#'],
  '/': ['    #', '   # ', '   # ', '  #  ', ' #   ', ' #   ', '#    '], ' ': ['  ', '  ', '  ', '  ', '  ', '  ', '  '],
};
const silkCache = new Map<string, { d: string; w: number }>();
function silkPath(text: string) {
  let hit = silkCache.get(text);
  if (hit) return hit;
  const px: [number, number][] = []; let x = 0;
  for (const ch of text.toUpperCase()) {
    const glyph = FONT[ch] ?? FONT[' '];
    glyph.forEach((row, y) => [...row].forEach((c, i) => { if (c === '#') px.push([x + i, y]); }));
    x += glyph[0].length + 1;
  }
  hit = { d: runs(px), w: Math.max(x - 1, 1) }; silkCache.set(text, hit); return hit;
}
/** Silk-screen label in the pixel font. Decorative: the localized text is rendered next to it. */
export function Silk({ text }: { text: string }) {
  const { d, w } = silkPath(text);
  return <svg className="silk" width={w} height={7} viewBox={`0 0 ${w} 7`} aria-hidden="true"><path fill="currentColor" d={d} /></svg>;
}

function notchPaths(n: number, bw: number) {
  const out: [number, number][] = [], halo: [number, number][] = [], line: [number, number][] = [];
  for (let y = 0; y <= n; y++) for (let x = 0; x <= n; x++) {
    const d = x - 1 + y - 1;
    if (d < n - 2) out.push([x, y]); else if (d === n - 2) halo.push([x, y]); else if (d <= n - 2 + bw) line.push([x, y]);
  }
  return { out: runs(out), halo: runs(halo), line: runs(line) };
}
const NOTCH = notchPaths(10, 2);
/** IC-package notch: a 45° pixel cut on the top-left corner of a panel. */
export function Notch() {
  return <svg className="notch" width={11} height={11} aria-hidden="true">
    <path className="notch-out" d={NOTCH.out} /><path className="notch-halo" d={NOTCH.halo} /><path className="notch-line" d={NOTCH.line} />
  </svg>;
}
const VIA = { ring: runs([[1, 0], [2, 0], [3, 0], [0, 1], [4, 1], [0, 2], [4, 2], [0, 3], [4, 3], [1, 4], [2, 4], [3, 4]]), hole: runs([[1, 1], [2, 1], [3, 1], [1, 2], [2, 2], [3, 2], [1, 3], [2, 3], [3, 3]]) };
/** 5×5 via (pad with a drilled hole) placed at trace ends. */
export function Via() {
  return <svg className="via" width={5} height={5} aria-hidden="true"><path className="via-hole" d={VIA.hole} /><path className="via-ring" d={VIA.ring} /></svg>;
}
/** Panel header strip: via + silk label + localized name (+ optional meta on the right). */
export function PanelHead({ silk, title, children, id }: { silk: string; title: string; children?: ReactNode; id?: string }) {
  return <header className="ph"><Via /><h2 className="ph-title" id={id}><Silk text={silk} /><span className="ph-name">{title}</span></h2>
    {children && <div className="ph-meta">{children}</div>}</header>;
}
