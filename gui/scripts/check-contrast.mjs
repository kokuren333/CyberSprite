// Contrast check for the GUI theme (SPEC §14.3.3, §14.8-4).
// Parses gui/src/theme/tokens.css for the normal and high-contrast themes, resolves var()
// chains, and checks every foreground/background pair the stylesheet actually uses:
//   body text >= 7:1, secondary text >= 4.5:1, meaningful non-text >= 3:1 (WCAG 2.x ratio).
// Pairs marked `decor` are reported for reference only (decorative wiring, separators).
// It also fails when app.css references a CSS variable that tokens.css does not define.
// Usage: node scripts/check-contrast.mjs [--verbose]
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const theme = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'theme');
const tokensCss = readFileSync(join(theme, 'tokens.css'), 'utf8');
const appCss = readFileSync(join(theme, 'app.css'), 'utf8');
const verbose = process.argv.includes('--verbose');

function block(marker) {
  const at = tokensCss.indexOf(`/* @theme ${marker}`);
  if (at < 0) throw new Error(`tokens.css: missing "/* @theme ${marker}" block`);
  const open = tokensCss.indexOf('{', at), close = tokensCss.indexOf('}', open);
  const vars = {};
  for (const m of tokensCss.slice(open + 1, close).matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) vars[m[1]] = m[2].trim();
  return vars;
}
const normal = block('normal');
const themes = { normal, 'high-contrast': { ...normal, ...block('high-contrast') } };

function resolve(vars, value, seen = []) {
  const m = /^var\((--[\w-]+)\)$/.exec(value);
  if (!m) {
    if (!/^#[0-9a-fA-F]{6}$/.test(value)) throw new Error(`Colour must be #RRGGBB or var(): ${seen.at(-1) ?? ''} = ${value}`);
    return value.toUpperCase();
  }
  if (seen.includes(m[1])) throw new Error(`var() cycle: ${[...seen, m[1]].join(' -> ')}`);
  if (!(m[1] in vars)) throw new Error(`Undefined token ${m[1]}`);
  return resolve(vars, vars[m[1]], [...seen, m[1]]);
}
const lum = hex => {
  const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255).map(c => c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };

const BODY = 7, SECONDARY = 4.5, NONTEXT = 3, DECOR = 0;
// [use, foreground token, background token, minimum]
const pairs = [
  ['body text on panels', '--ui-text', '--cs-panel', BODY],
  ['body text on the board (dialog footers, code blocks)', '--ui-text', '--cs-board', BODY],
  ['button / tab / op-chip text on pads', '--ui-text', '--cs-pad', BODY],
  ['button text on hovered pads', '--ui-text', '--ui-pad-hover', BODY],
  ['text on pressed pads, active tool, checked toggles', '--ui-text', '--ui-pad-on-bg', BODY],
  ['selected activity row / selected layer', '--ui-text', '--ui-sel-bg', BODY],
  ['demo strip (build:demo): notice text and link', '--ui-text', '--ui-sel-bg', BODY],
  ['current frame column', '--ui-text', '--ui-cur-col', BODY],
  ['error issue row', '--ui-text', '--ui-error-bg', BODY],
  ['warning issue row', '--ui-text', '--ui-warn-bg', BODY],
  ['idle panel header (silk label, title)', '--ui-ph-text', '--ui-ph-bg', BODY],
  ['active panel header (silk label, title)', '--ui-ph-text-on', '--ui-ph-bg-on', BODY],
  ['inverted: tooltip, badge, FG tag, HEAD, current frame number', '--ui-text-inverse', '--ui-inverse-bg', BODY],
  ['secondary text on panels', '--ui-text-soft', '--cs-panel', SECONDARY],
  ['secondary text on the board', '--ui-text-soft', '--cs-board', SECONDARY],
  ['secondary text on pads', '--ui-text-soft', '--cs-pad', SECONDARY],
  ['secondary text in selected rows', '--ui-text-soft', '--ui-sel-bg', SECONDARY],
  ['secondary text in the current frame column', '--ui-text-soft', '--ui-cur-col', SECONDARY],
  ['secondary text in issue rows (error)', '--ui-text-soft', '--ui-error-bg', SECONDARY],
  ['secondary text in issue rows (warning)', '--ui-text-soft', '--ui-warn-bg', SECONDARY],
  ['idle header meta text', '--ui-ph-meta', '--ui-ph-bg', SECONDARY],
  ['active header meta text', '--ui-ph-meta-on', '--ui-ph-bg-on', SECONDARY],
  ['icon outlines, cel glyphs, checkbox core', '--ui-text', '--cs-panel', NONTEXT],
  ['icon outlines inside pads', '--ui-text', '--cs-pad', NONTEXT],
  ['icon outlines in the active tool', '--ui-text', '--ui-pad-on-bg', NONTEXT],
  ['cel glyphs in the current frame column', '--ui-text', '--ui-cur-col', NONTEXT],
  ['empty-cel dot', '--ui-text-soft', '--cs-panel', NONTEXT],
  ['active tool / tab / pressed pad border on panels', '--ui-on-line', '--cs-panel', NONTEXT],
  ['pressed pad border next to idle pads', '--ui-on-line', '--cs-pad', NONTEXT],
  ['pressed pad border against its own fill', '--ui-on-line', '--ui-pad-on-bg', NONTEXT],
  ['selected-row bar', '--ui-on-line', '--ui-sel-bg', NONTEXT],
  ['active panel border on the board', '--ui-panel-line-on', '--cs-board', NONTEXT],
  ['active panel border against the panel', '--ui-panel-line-on', '--cs-panel', NONTEXT],
  ['input and checkbox frames', '--ui-field-line', '--cs-panel', NONTEXT],
  ['palette swatch frames', '--ui-swatch-line', '--cs-panel', NONTEXT],
  ['keyboard focus ring on panels', '--ui-focus', '--cs-panel', NONTEXT],
  ['keyboard focus ring on pads', '--ui-focus', '--cs-pad', NONTEXT],
  ['keyboard focus ring on pressed pads', '--ui-focus', '--ui-pad-on-bg', NONTEXT],
  ['marquee on the canvas (light checker)', '--ui-selection-line', '--cs-checker-a', NONTEXT],
  ['marquee on the canvas (dark checker)', '--ui-selection-line', '--cs-checker-b', NONTEXT],
  ['changed-pixels box (light checker)', '--ui-change-line', '--cs-checker-a', NONTEXT],
  ['changed-pixels box (dark checker)', '--ui-change-line', '--cs-checker-b', NONTEXT],
  ['changed-pixels box on the canvas surround', '--ui-change-line', '--cs-canvas-surround', NONTEXT],
  ['error marker (icon fill, issue bar)', '--cs-error', '--cs-panel', NONTEXT],
  ['warning bar (decorative: the warning icon carries the shape)', '--cs-warn', '--cs-panel', DECOR],
  ['idle panel border (decorative wiring)', '--ui-panel-line', '--cs-board', DECOR],
  ['idle pad edge (decorative; pads are labelled by text or ink icons)', '--ui-pad-line', '--cs-panel', DECOR],
  ['separators (decorative)', '--ui-sep', '--cs-panel', DECOR],
  ['canvas edge on the surround (decorative)', '--ui-canvas-edge', '--cs-canvas-surround', DECOR],
  ['pixel grid on the checker (aid)', '--ui-grid-line', '--cs-checker-a', DECOR],
];

let failures = 0, checked = 0;
for (const [name, vars] of Object.entries(themes)) {
  const rows = pairs.map(([use, fg, bg, min]) => {
    const a = resolve(vars, `var(${fg})`), b = resolve(vars, `var(${bg})`), r = ratio(a, b);
    const ok = min === DECOR || r + 1e-9 >= min;
    if (min) checked++;
    if (!ok) failures++;
    return { use, fg: `${fg} ${a}`, bg: `${bg} ${b}`, ratio: r.toFixed(2), min: min || '-', result: min === DECOR ? 'ref' : ok ? 'OK' : 'FAIL' };
  });
  const required = rows.filter(r => r.result !== 'ref');
  const worst = required.reduce((w, r) => (+r.ratio / +r.min < +w.ratio / +w.min ? r : w));
  console.log(`theme ${name}: ${required.length - required.filter(r => r.result === 'FAIL').length}/${required.length} required pairs pass; tightest: ${worst.use} ${worst.ratio} (min ${worst.min})`);
  for (const r of rows) if (verbose || r.result === 'FAIL') console.log(`  ${r.result.padEnd(4)} ${r.ratio.padStart(5)} >= ${String(r.min).padEnd(3)} ${r.use}  [${r.fg} on ${r.bg}]`);
}

// every variable used by the stylesheet must exist in the tokens
const defined = new Set([...tokensCss.matchAll(/(--[\w-]+)\s*:/g)].map(m => m[1]).concat(['--scale', '--checker']));
const used = new Set([...appCss.matchAll(/var\((--[\w-]+)/g)].map(m => m[1]));
const missing = [...used].filter(v => !defined.has(v));
if (missing.length) { failures += missing.length; console.log(`undefined variables in app.css: ${missing.join(', ')}`); }

// canvas surround and checker must stay low-chroma (SPEC §14.3.3)
for (const [name, vars] of Object.entries(themes)) for (const token of ['--cs-canvas-surround', '--cs-checker-a', '--cs-checker-b']) {
  const hex = resolve(vars, `var(${token})`), c = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));
  const chroma = (Math.max(...c) - Math.min(...c)) / 255;
  if (chroma > 0.1) { failures++; console.log(`FAIL ${name} ${token} ${hex} chroma ${chroma.toFixed(2)} > 0.10`); }
}

if (failures) { console.error(`contrast check failed: ${failures} problem(s)`); process.exit(1); }
console.log(`contrast check passed (${checked} required pairs across ${Object.keys(themes).length} themes)`);
