/* Bundled sample for the in-browser demo. Original artwork drawn for CyberSprite
 * (a small circuit-board robot, "Chip"), written as character grids so it stays reviewable.
 * Pixels are palette indices only (AGENTS.md §3-1). */
export const WIDTH = 32, HEIGHT = 32;
export const PALETTE = [
  '#00000000', // 0 transparent
  '#1B2A3AFF', // 1 ink (outline)
  '#FFFFFFFF', // 2 white
  '#BFEFFFFF', // 3 light cyan
  '#3FC7E8FF', // 4 cyan
  '#138FB5FF', // 5 deep cyan
  '#E6F4F8FF', // 6 board
  '#A9DCEBFF', // 7 trace
  '#C9D3DAFF', // 8 solder
  '#7D8C99FF', // 9 grey
  '#3BD16FFF', // 10 LED green
  '#F2545BFF', // 11 LED red
  '#F5B841FF', // 12 amber
  '#8C6BE8FF', // 13 violet
  '#FFB3C7FF', // 14 pink
  '#D9A441FF', // 15 pad gold
];
/** Character → palette index. 'L' is the antenna LED (per frame). Space and '.' are transparent. */
const KEY: Record<string, number> = { '.': 0, ' ': 0, k: 1, w: 2, l: 3, c: 4, d: 5, s: 8, g: 9, y: 12, p: 14 };
const BODY = [
  '       kk       ',
  '      kLLk      ',
  '       kk       ',
  '  kkkkkkkkkkkk  ',
  ' kllllllllllllk ',
  ' klwwwwwwwwwwlk ',
  ' klwkkwwwwkkwlk ',
  ' klwkkwwwwkkwlk ',
  ' klwpwwwwwwpwlk ',
  ' klwwwkkkkwwwlk ',
  ' kcllllllllllck ',
  '  kkkkkkkkkkkk  ',
  '   kcccccccck   ',
  ' skkcdssssdckks ',
  ' skkcdsyysdckks ',
  '   kcccccccck   ',
];
const LEGS: Record<'stand' | 'left' | 'right', string[]> = {
  stand: ['   kkkk  kkkk   ', '   kddk  kddk   ', '  kkkkk  kkkkk  '],
  left: ['   kkkk  kkkk   ', '   kkkk  kddk   ', '         kkkkk  '],
  right: ['   kkkk  kkkk   ', '   kddk  kkkk   ', '  kkkkk         '],
};
export type Grid = Uint8Array;
const blank = () => new Uint8Array(WIDTH * HEIGHT);
function paint(grid: Grid, rows: string[], ox: number, oy: number, led: number) {
  rows.forEach((row, y) => [...row].forEach((ch, x) => {
    const v = ch === 'L' ? led : KEY[ch];
    if (v === undefined) throw Error(`fixture: unknown glyph ${ch}`);
    if (v) grid[(oy + y) * WIDTH + ox + x] = v;
  }));
}
export function background(): Grid {
  const g = blank().fill(6);
  const put = (x: number, y: number, v: number) => { g[y * WIDTH + x] = v; };
  for (let x = 0; x < WIDTH; x++) put(x, 29, 7);
  for (let y = 0; y < 29; y++) put(3, y, 7);
  for (let y = 6; y < 29; y++) put(28, y, 7);
  for (let x = 20; x < 28; x++) put(x, 6, 7);
  for (let x = 4; x < 15; x++) put(x, 2, 7);
  for (const [cx, cy] of [[3, 29], [28, 29], [28, 6], [20, 6], [3, 2]]) {
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      const x = cx + dx, y = cy + dy;
      if (x >= 0 && y >= 0 && x < WIDTH && y < HEIGHT) put(x, y, dx || dy ? 15 : 9);
    }
  }
  return g;
}
export function robot(frame: number): Grid {
  const g = blank(), up = frame % 2 === 1 ? 1 : 0, led = frame === 1 || frame === 2 ? 12 : 10;
  paint(g, BODY, 8, 8 - up, led);
  paint(g, frame === 1 ? LEGS.left : frame === 3 ? LEGS.right : LEGS.stand, 8, 24 - up, led);
  for (let x = 10; x < 22; x++) g[28 * WIDTH + x] = 7; // contact shadow on the board
  return g;
}
export function sparks(frame: number): Grid | null {
  if (frame % 2 === 0) return null;
  const g = blank(), spots = frame === 1 ? [[24, 4], [6, 10]] : [[26, 12], [6, 4]];
  for (const [x, y] of spots) {
    g[y * WIDTH + x] = 2;
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) g[(y + dy) * WIDTH + x + dx] = 13;
  }
  return g;
}
