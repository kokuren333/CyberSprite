/** Provisional geometry only. The server remains authoritative. SPEC 6.4. */
export type Point = [number, number];
export type Brush = { size: number; shape: 'square' | 'circle' };
type Mask = boolean[][];
const equal = (a: Point, b: Point) => a[0] === b[0] && a[1] === b[1];
const sorted = (p: Point[]) => p.sort((a, b) => a[1] - b[1] || a[0] - b[0]);
const unique = (p: Point[]) => [...new Map(p.map(v => [v.join(','), v])).values()];
function integer(n: number) { if (!Number.isSafeInteger(n)) throw Error('Use safe integer coordinates.'); return n; }
function dimensions(w: number, h: number) { if (integer(w) < 1 || integer(h) < 1) throw Error('Use positive dimensions.'); }
export function line(x0: number, y0: number, x1: number, y1: number): Point[] {
  [x0, y0, x1, y1].forEach(integer);
  if (y0 > y1 || (y0 === y1 && x0 > x1)) [x0, y0, x1, y1] = [x1, y1, x0, y0];
  const dx = Math.abs(x1 - x0), dy = y1 - y0, sx = x1 >= x0 ? 1 : -1;
  let err = dx - dy, x = x0, y = y0;
  const result: Point[] = [];
  for (;;) {
    result.push([x, y]);
    if (x === x1 && y === y1) return result;
    const e2 = 2 * err;
    if (e2 > -dy) { err -= dy; x += sx; }
    if (e2 < dx) { err += dx; y++; }
  }
}
export function rect(x: number, y: number, w: number, h: number, filled = false): Point[] {
  dimensions(w, h); integer(x); integer(y);
  const result: Point[] = [];
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++)
    if (filled || !i || !j || i === w - 1 || j === h - 1) result.push([x + i, y + j]);
  return result;
}
export function ellipse(x: number, y: number, w: number, h: number, filled = false): Point[] {
  dimensions(w, h); integer(x); integer(y);
  const W = BigInt(w), H = BigInt(h);
  const inside = (i: number, j: number) => i >= 0 && i < w && j >= 0 && j < h &&
    (BigInt(2 * i + 1) - W) ** 2n * H ** 2n + (BigInt(2 * j + 1) - H) ** 2n * W ** 2n <= W ** 2n * H ** 2n;
  const result: Point[] = [];
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++)
    if (inside(i, j) && (filled || neighbours(4).some(([dx, dy]) => !inside(i + dx, j + dy)))) result.push([x + i, y + j]);
  return result;
}
export function polygon(points: Point[], closed = true, filled = false): Point[] {
  if (points.length < 2 || (filled && !closed)) throw Error('Use at least two vertices and close filled polygons.');
  const edges = points.slice(1).map((p, i) => [points[i], p]);
  if (closed) edges.push([points.at(-1)!, points[0]]);
  const result = edges.flatMap(([a, b]) => line(...a, ...b));
  if (filled) for (let y = Math.min(...points.map(p => p[1])); y <= Math.max(...points.map(p => p[1])); y++)
    for (let x = Math.min(...points.map(p => p[0])); x <= Math.max(...points.map(p => p[0])); x++) {
      let odd = false;
      for (let [a, b] of edges) {
        if (a[1] > b[1]) [a, b] = [b, a];
        if (a[1] <= y && y < b[1] && BigInt(x - a[0]) * BigInt(b[1] - a[1]) < BigInt(y - a[1]) * BigInt(b[0] - a[0])) odd = !odd;
      }
      if (odd) result.push([x, y]);
    }
  return sorted(unique(result));
}
export function stroke(points: Point[], pixelPerfect = false, brushSize = 1): Point[] {
  if (!points.length || (pixelPerfect && brushSize !== 1)) throw Error('Use points and brush size 1 for pixel-perfect strokes.');
  const path: Point[] = [points[0]];
  for (let i = 1; i < points.length; i++) {
    const segment = line(...points[i - 1], ...points[i]);
    if (!equal(segment[0], points[i - 1])) segment.reverse();
    path.push(...segment.slice(1));
  }
  if (!pixelPerfect || path.length < 3) return path;
  const result = [path[0]];
  let i = 1;
  while (i < path.length - 1) {
    const p = result.at(-1)!, c = path[i], n = path[i + 1];
    if ((p[0] === c[0] || p[1] === c[1]) && (n[0] === c[0] || n[1] === c[1]) && p[0] !== n[0] && p[1] !== n[1]) { result.push(n); i += 2; }
    else { result.push(c); i++; }
  }
  if (i === path.length - 1) result.push(path[i]);
  return result;
}
export function brushOffsets(size = 1, shape = 'square'): Point[] {
  if (integer(size) < 1 || size > 64 || !['square', 'circle'].includes(shape)) throw Error('Use brush size 1–64 and square/circle.');
  const offset = -Math.floor(size / 2);
  return shape === 'circle' ? ellipse(offset, offset, size, size, true) : rect(offset, offset, size, size, true);
}
export function stamp(points: Point[], brush: Brush = { size: 1, shape: 'square' }): Point[] {
  const offsets = brushOffsets(brush.size, brush.shape);
  return unique(points.flatMap(([x, y]) => offsets.map(([dx, dy]): Point => [x + dx, y + dy])));
}
export function neighbours(connectivity: number): Point[] {
  if (connectivity === 4) return [[0, -1], [-1, 0], [1, 0], [0, 1]];
  if (connectivity === 8) return [[-1, -1], [0, -1], [1, -1], [-1, 0], [1, 0], [-1, 1], [0, 1], [1, 1]];
  throw Error('Use connectivity 4 or 8.');
}
export function floodFill(image: number[][], x: number, y: number, connectivity = 4): Mask {
  const h = image.length, w = image[0].length, offsets = neighbours(connectivity);
  if (x < 0 || y < 0 || x >= w || y >= h) throw Error('Seed is outside canvas.');
  const mask = Array.from({ length: h }, () => Array<boolean>(w).fill(false)), queue: Point[] = [[x, y]];
  mask[y][x] = true;
  for (let i = 0; i < queue.length; i++) for (const [dx, dy] of offsets) {
    const [px, py] = queue[i], nx = px + dx, ny = py + dy;
    if (nx >= 0 && ny >= 0 && nx < w && ny < h && !mask[ny][nx] && image[ny][nx] === image[y][x]) { mask[ny][nx] = true; queue.push([nx, ny]); }
  }
  return mask;
}
export function outline(opaque: Mask, placement = 'outside', connectivity = 4): Mask {
  const offsets = neighbours(connectivity);
  return opaque.map((row, y) => row.map((value, x) => value === (placement === 'inside') && offsets.some(([dx, dy]) => Boolean(opaque[y + dy]?.[x + dx]) !== (placement === 'inside'))));
}
export type Region = { type: string; x?: number; y?: number; w?: number; h?: number; rows?: string[]; color?: number; connectivity?: number };
export function regionMask(region: Region, w: number, h: number, image: number[][]): Mask {
  const { type, x = 0, y = 0 } = region;
  if (type === 'wand') return floodFill(image, x, y, region.connectivity);
  return Array.from({ length: h }, (_, j) => Array.from({ length: w }, (_, i) => {
    if (type === 'all') return true;
    if (type === 'color') return image[j][i] === region.color;
    if (type === 'rect') return i >= x && j >= y && i < x + region.w! && j < y + region.h!;
    if (type === 'mask') return region.rows?.[j - y]?.[i - x] === '#';
    throw Error('Unknown region type.');
  }));
}
export function transform<T>(input: T[][], flip: string | null = null, rotate = 0): T[][] {
  let result = input.map(row => [...row]);
  if (flip === 'h') result = result.map(row => row.reverse());
  if (flip === 'v') result.reverse();
  for (let r = 0; r < rotate; r += 90) result = result[0].map((_, x) => result.map(row => row[x]).reverse());
  return result;
}
export const maskRows = (mask: Mask) => mask.map(row => row.map(v => v ? '#' : '.').join(''));
export const parseMask = (rows: string[]) => rows.map(row => [...row].map(v => v === '#'));
