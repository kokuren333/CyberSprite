/* In-browser stand-in for the local CyberSprite server, used only by the demo build
 * (npm run build:demo → GitHub Pages). It answers the same JSON-RPC methods the GUI calls,
 * so every UI component runs unchanged (REVIEW_NOTES item 10). It is a small toy engine:
 * palette-indexed pixels, integer geometry from src/raster (the GUI's provisional rules),
 * snapshot undo/redo. It is NOT the core: validation is simplified, and anything that
 * needs files, the import pipeline or export answers E_DEMO_SERVER_ONLY with a hint. */
import { RpcError, type Notification, type RpcParams, type Transport } from '../api/client';
import { ellipse, floodFill, line, rect, regionMask, stamp, stroke, type Brush, type Point, type Region } from '../raster';
import type { OpSchema } from '../store';
import * as F from './fixture';

export const DEMO_PROJECT = 'demo/chip-robot.csprite';
export const DEMO_START_LAYER = 'L2';
const W = F.WIDTH, H = F.HEIGHT, TRANSPARENT = 0;

type Cel = { pixels: Uint8Array };
type LayerState = { id: string; name: string; visible: boolean; locked: boolean; opacity: number; cels: (Cel | null)[] };
type Snapshot = { layers: LayerState[]; durations: number[] };
type FrameChange = { frame: number; pixels_changed: number; bbox: { x: number; y: number; w: number; h: number } | null };
type Entry = { revision: number; actor: string; time: string; label: string; ops: string[]; kind: string; changed: { frames: FrameChange[] } };
type Call = { op: string; args: Record<string, any> };

const TAGS = [
  { id: 'T1', name: 'walk', from: 0, to: 3, direction: 'forward', repeat: 0 },
  { id: 'T2', name: 'hop', from: 1, to: 2, direction: 'pingpong', repeat: 0 },
];

function fail(code: string, message: string, hint: string, details: unknown = {}): RpcError {
  return new RpcError(-32000, message, { code, hint, details });
}
const SERVER_HINT = 'This page is the in-browser demo. Clone the repository and run `cybersprite gui`, or drive the CLI / MCP from an AI agent, to use this.';
const serverOnly = (what: string) => fail('E_DEMO_SERVER_ONLY', `${what} needs the local CyberSprite server.`, SERVER_HINT, { demo: true });

const int = (v: unknown, name: string, min = -Infinity, max = Infinity): number => {
  if (typeof v !== 'number' || !Number.isSafeInteger(v) || v < min || v > max)
    throw fail('E_INVALID_ARGUMENT', `${name} must be an integer${min > -Infinity ? ` in ${min}..${max}` : ''}.`, `Pass ${name} as a whole number.`, { argument: name, value: v });
  return v;
};

// ---- schemas shown in the Operation menu (defaults make "Apply" work out of the box) ----
const target = { layer: { type: 'string', default: DEMO_START_LAYER }, frame: { type: 'integer', minimum: 0, default: 0 } };
const colorArg = { color: { type: 'integer', minimum: 0, maximum: 15, default: 4 } };
const brushArg = { brush: { type: 'object', default: { size: 1, shape: 'square' } } };
const schema = (name: string, kind: string, description: string, properties: Record<string, unknown>): OpSchema =>
  ({ name, kind, idempotency: kind === 'query' ? 'pure' : 'none', description: `${description} (in-browser demo)`, inputSchema: { type: 'object', properties, required: Object.keys(properties) } });
export const SCHEMAS: OpSchema[] = [
  schema('set_pixel', 'mutate', 'Set one pixel to a palette index.', { ...target, x: { type: 'integer', default: 4 }, y: { type: 'integer', default: 4 }, ...colorArg }),
  schema('set_pixels', 'mutate', 'Set many pixels to one palette index.', { ...target, pixels: { type: 'array', default: [[4, 4], [5, 4], [6, 4]] }, ...colorArg }),
  schema('stroke', 'mutate', 'Freehand stroke through points.', { ...target, points: { type: 'array', default: [[2, 20], [6, 16], [10, 20]] }, ...colorArg, ...brushArg, pixel_perfect: { type: 'boolean', default: false } }),
  schema('line', 'mutate', 'Straight line between two points.', { ...target, x0: { type: 'integer', default: 1 }, y0: { type: 'integer', default: 30 }, x1: { type: 'integer', default: 30 }, y1: { type: 'integer', default: 30 }, ...colorArg, ...brushArg }),
  schema('rect', 'mutate', 'Rectangle outline or filled rectangle.', { ...target, x: { type: 'integer', default: 2 }, y: { type: 'integer', default: 2 }, w: { type: 'integer', minimum: 1, default: 6 }, h: { type: 'integer', minimum: 1, default: 4 }, filled: { type: 'boolean', default: false }, ...colorArg, ...brushArg }),
  schema('ellipse', 'mutate', 'Ellipse inscribed in a box.', { ...target, x: { type: 'integer', default: 22 }, y: { type: 'integer', default: 2 }, w: { type: 'integer', minimum: 1, default: 7 }, h: { type: 'integer', minimum: 1, default: 7 }, filled: { type: 'boolean', default: true }, ...colorArg, ...brushArg }),
  schema('fill', 'mutate', 'Flood fill one layer from a seed pixel.', { ...target, x: { type: 'integer', default: 1 }, y: { type: 'integer', default: 1 }, ...colorArg, connectivity: { type: 'integer', enum: [4, 8], default: 4 } }),
  schema('transform_region', 'mutate', 'Move a region by an integer offset.', { ...target, region: { type: 'object', default: { type: 'all' } }, dx: { type: 'integer', default: 1 }, dy: { type: 'integer', default: 0 } }),
  schema('update_layer', 'mutate', 'Change layer visibility, lock, name or opacity.', { layer: { type: 'string', default: 'L3' }, visible: { type: 'boolean', default: true } }),
  schema('set_frame_duration', 'mutate', 'Set the duration of frames in milliseconds.', { frames: { type: 'array', default: [0] }, duration_ms: { type: 'integer', minimum: 1, maximum: 65535, default: 200 } }),
  schema('get_pixels', 'query', 'Read palette indices in a rectangle.', { layer: { type: 'string', default: '@composite' }, frame: { type: 'integer', default: 0 }, rect: { type: 'object', default: { x: 14, y: 14, w: 4, h: 4 } } }),
  schema('diff_preview', 'query', 'Compare two revisions frame by frame.', { from_revision: { type: 'integer', default: 0 }, to_revision: { type: 'integer', default: 1 }, inline: { type: 'boolean', default: true } }),
];
const MUTATIONS = new Set(SCHEMAS.filter(s => s.kind === 'mutate').map(s => s.name));
const QUERIES = new Set(SCHEMAS.filter(s => s.kind === 'query').map(s => s.name));

// ---- helpers ----
function clone(layers: LayerState[]): LayerState[] {
  const copies = new Map<Cel, Cel>(); // keep linked cels linked in the copy
  const copy = (cel: Cel | null) => { if (!cel) return null; let c = copies.get(cel); if (!c) copies.set(cel, c = { pixels: cel.pixels.slice() }); return c; };
  return layers.map(l => ({ ...l, cels: l.cels.map(copy) }));
}
const rgba = (hex: string) => [1, 3, 5, 7].map(i => parseInt(hex.slice(i, i + 2), 16));
const COLORS = F.PALETTE.map(rgba);
function base64(bytes: Uint8Array | Uint8ClampedArray): string {
  let text = '';
  for (let i = 0; i < bytes.length; i += 0x8000) text += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(text);
}
/** Integer source-over of the visible layers, bottom first. */
export function composite(layers: LayerState[], frame: number): Uint8ClampedArray {
  const out = new Uint8ClampedArray(W * H * 4);
  for (const layer of layers) {
    const cel = layer.cels[frame];
    if (!layer.visible || !cel) continue;
    for (let i = 0; i < W * H; i++) {
      const v = cel.pixels[i];
      if (v === TRANSPARENT) continue;
      const [r, g, b, ca] = COLORS[v], a = Math.trunc((ca * layer.opacity + 127) / 255), o = i * 4;
      if (a === 0) continue;
      const da = out[o + 3], rest = Math.trunc((da * (255 - a) + 127) / 255), oa = a + rest;
      for (const [k, c] of [[0, r], [1, g], [2, b]] as const) out[o + k] = Math.trunc((c * a + out[o + k] * rest + (oa >> 1)) / oa);
      out[o + 3] = oa;
    }
  }
  return out;
}
function compare(a: Uint8ClampedArray, b: Uint8ClampedArray, frame: number): FrameChange {
  let n = 0, x0 = W, y0 = H, x1 = -1, y1 = -1;
  for (let i = 0; i < W * H; i++) {
    const o = i * 4;
    if (a[o] === b[o] && a[o + 1] === b[o + 1] && a[o + 2] === b[o + 2] && a[o + 3] === b[o + 3]) continue;
    const x = i % W, y = (i - x) / W;
    n++; x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
  }
  return { frame, pixels_changed: n, bbox: n ? { x: x0, y: y0, w: x1 - x0 + 1, h: y1 - y0 + 1 } : null };
}
/** Changed pixels at full strength, unchanged ones faded; ×4 nearest-neighbour PNG (browser only). */
function diffImage(after: Uint8ClampedArray, before: Uint8ClampedArray): string | null {
  if (typeof document === 'undefined') return null;
  const scale = 4, data = new Uint8ClampedArray(after);
  for (let i = 0; i < W * H; i++) {
    const o = i * 4, same = [0, 1, 2, 3].every(k => after[o + k] === before[o + k]);
    if (same) data[o + 3] = Math.trunc(data[o + 3] / 4);
  }
  const small = document.createElement('canvas'); small.width = W; small.height = H;
  small.getContext('2d')!.putImageData(new ImageData(data, W, H), 0, 0);
  const big = document.createElement('canvas'); big.width = W * scale; big.height = H * scale;
  const ctx = big.getContext('2d')!; ctx.imageSmoothingEnabled = false; ctx.drawImage(small, 0, 0, big.width, big.height);
  return big.toDataURL('image/png').split(',')[1];
}

/** Scripted commits that play the role of an AI agent editing the same project (W1). */
const AGENT_SCRIPT: { label: string; calls: (b: DemoBackend) => Call[] }[] = [
  { label: 'Agent: blink the antenna LED red on frame 3', calls: () => [{ op: 'set_pixels', args: { layer: 'L2', frame: 3, pixels: [[15, 8], [16, 8]], color: 11 } }] },
  { label: 'Agent: paint the chest panel deep cyan on every frame', calls: b => [0, 1, 2, 3].map(frame => ({ op: 'set_pixels', args: { layer: 'L2', frame, color: 5, pixels: b.find('L2', frame, 8).filter(([x, y]) => y > 18 && x > 9 && x < 22) } })) },
  { label: 'Agent: add a spark on frame 0', calls: () => [{ op: 'set_pixels', args: { layer: 'L3', frame: 0, color: 13, pixels: [[25, 3], [24, 4], [26, 4], [25, 5]] } }, { op: 'set_pixel', args: { layer: 'L3', frame: 0, x: 25, y: 4, color: 2 } }] },
];

export class DemoBackend {
  layers: LayerState[] = [];
  durations: number[] = [];
  private history: { entry: Entry; snap: Snapshot }[] = [];
  private head = 0;
  private agentStep = 0;
  readonly outbox: Notification[] = [];
  constructor(private now: () => string = () => new Date().toISOString()) { this.reset(); }

  get revision() { return this.head; }
  reset() {
    this.layers = [
      { id: 'L1', name: 'board', visible: true, locked: false, opacity: 255, cels: [null, null, null, null] },
      { id: 'L2', name: 'chip', visible: true, locked: false, opacity: 255, cels: [null, null, null, null] },
      { id: 'L3', name: 'sparks', visible: true, locked: false, opacity: 255, cels: [null, null, null, null] },
    ];
    this.durations = [160, 120, 160, 120];
    this.history = []; this.head = 0; this.agentStep = 0;
    this.record({ revision: 0, actor: 'agent:demo', label: 'new_project 32×32, 4 frames, 16-colour palette', ops: ['new_project'], kind: 'create', changed: { frames: [] } });
    // The sample is built as agent commits so the Activity tab has something to show.
    this.transaction('Agent: draw the circuit-board background (one cel, linked to all frames)', 'agent:demo', [], () => {
      const board: Cel = { pixels: F.background() };
      this.layers[0].cels = [board, board, board, board];
      return ['set_pixels', 'link_cels'];
    });
    this.transaction('Agent: draw Chip, a 4-frame walk cycle', 'agent:demo', [], () => {
      this.layers[1].cels = [0, 1, 2, 3].map(f => ({ pixels: F.robot(f) }));
      return ['set_pixels'];
    });
    this.transaction('Agent: add sparks on odd frames', 'agent:demo', [], () => {
      this.layers[2].cels = [0, 1, 2, 3].map(f => { const g = F.sparks(f); return g ? { pixels: g } : null; });
      return ['set_pixels'];
    });
    this.outbox.length = 0;
  }
  /** Pixels of one cel holding a palette index (used by the agent script). */
  find(layer: string, frame: number, index: number): Point[] {
    const cel = this.layer(layer).cels[frame], out: Point[] = [];
    cel?.pixels.forEach((v, i) => { if (v === index) out.push([i % W, Math.trunc(i / W)]); });
    return out;
  }

  // ---- JSON-RPC surface (same names and envelopes as src/cybersprite/server) ----
  handle(method: string, p: RpcParams = {}): unknown {
    switch (method) {
      case 'op.list': return SCHEMAS;
      case 'project.get': return { project: DEMO_PROJECT, result: this.info() };
      case 'project.open':
        if (p.project && p.project !== DEMO_PROJECT) throw serverOnly('Opening a project from disk');
        return { project: DEMO_PROJECT };
      case 'project.close': throw fail('E_DEMO_SERVER_ONLY', 'The demo keeps its bundled sample open.', 'Use the demo bar to reset the sample. ' + SERVER_HINT, { demo: true });
      case 'op.apply': {
        const op = String(p.op ?? ''), args = (p.args ?? {}) as Record<string, any>;
        if (Array.isArray(p.ops)) throw serverOnly('Batch apply_ops');
        if (QUERIES.has(op)) return { ok: true, op, result: this.query(op, args) };
        if (!MUTATIONS.has(op)) throw serverOnly(`Op "${op}"`);
        return this.apply([{ op, args }], typeof p.label === 'string' ? p.label : op, 'gui');
      }
      case 'render.frame': {
        const frames = (Array.isArray(p.frames) ? p.frames : [p.frame ?? 0]).map(f => int(f, 'frame', 0, this.durations.length - 1));
        return { encoding: 'rgba8-base64', frames: frames.map(frame => ({ frame, width: W, height: H, rgba: base64(composite(this.layers, frame)) })) };
      }
      case 'history.list': return this.info().history;
      case 'history.undo': case 'history.redo': return this.travel(method === 'history.undo', p);
      case 'validate.run': return { ok: true, result: this.validation() };
      case 'sources.list': return { sources: [] };
      case 'sources.get': throw fail('E_NOT_FOUND', 'The demo sample has no sources.', SERVER_HINT);
      case 'prefs.get': return {};
      case 'prefs.set': return { ok: true };
      case 'pipeline.preview': case 'import.commit': throw serverOnly('Importing an image (the conversion pipeline)');
      case 'export.run': throw serverOnly('Exporting files');
      case 'demo.agent_commit': {
        const step = AGENT_SCRIPT[this.agentStep++ % AGENT_SCRIPT.length];
        return this.apply(step.calls(this), step.label, 'agent:demo');
      }
      case 'demo.reset': this.reset(); return { ok: true, revision: this.head };
      default: throw fail('E_METHOD_NOT_FOUND', `Unknown method ${method}.`, SERVER_HINT);
    }
  }

  info() {
    const layers = this.layers.map(l => ({
      id: l.id, name: l.name, type: 'image', visible: l.visible, locked: l.locked, opacity: l.opacity,
      cels: l.cels.flatMap((cel, frame) => {
        if (!cel) return [];
        const owner = l.cels.indexOf(cel);
        return [owner === frame ? { frame } : { frame, link: owner }];
      }),
    }));
    const entries = this.history.slice(0, this.head + 1).map(h => h.entry).reverse();
    return {
      summary: { name: 'chip-robot', width: W, height: H, revision: this.head }, layers,
      frames: this.durations.map(duration_ms => ({ duration_ms })), tags: TAGS,
      palette: { colors: F.PALETTE, transparent_index: TRANSPARENT },
      validation: this.validation(), history: { entries, head: this.head }, sources: { sources: [] }, slices: [],
    };
  }

  validation() {
    const opaque = this.durations.map((_, f) => { const c = composite(this.layers, f); let n = 0; for (let i = 3; i < c.length; i += 4) if (c[i]) n++; return n; });
    const used = new Set<number>();
    for (const l of this.layers) for (const cel of l.cels) cel?.pixels.forEach(v => { if (v !== TRANSPARENT) used.add(v); });
    const issues: any[] = [{ level: 'info', rule: 'DEMO_SIMULATED', message: 'In-browser demo: this is a simplified check. The real validate runs in the Python core.' }];
    opaque.forEach((n, frame) => { if (!n) issues.push({ level: 'warning', rule: 'EMPTY_FRAME', message: `Frame ${frame} has no visible pixels.`, where: { frame } }); });
    const hidden = this.layers.filter(l => !l.visible);
    if (hidden.length) issues.push({ level: 'info', rule: 'HIDDEN_LAYER', message: `Hidden layers are not exported: ${hidden.map(l => l.name).join(', ')}.`, where: { layer: hidden[0].id } });
    const counts = { error: 0, warning: 0, info: 0 } as Record<string, number>;
    for (const i of issues) counts[i.level]++;
    return { ok: counts.error === 0, counts, issues, metrics: { colors_used: used.size, palette_size: F.PALETTE.length, frames: this.durations.length, layers: this.layers.length, opaque_pixels: opaque } };
  }

  // ---- transactions ----
  private snapshot(): Snapshot { return { layers: clone(this.layers), durations: [...this.durations] }; }
  private restore(s: Snapshot) { this.layers = clone(s.layers); this.durations = [...s.durations]; }
  private record(e: Omit<Entry, 'time'>) { this.history.push({ entry: { ...e, time: this.now() }, snap: this.snapshot() }); this.head = this.history.length - 1; }
  /** Run mutate(), commit one revision, or roll back on error. Returns the per-frame change. */
  private transaction(label: string, actor: string, ops: string[], mutate: () => string[] | void) {
    const before = this.snapshot(), old = this.durations.map((_, f) => composite(before.layers, f));
    try {
      const names = mutate() ?? ops;
      const frames = this.durations.map((_, f) => compare(old[f] ?? new Uint8ClampedArray(W * H * 4), composite(this.layers, f), f)).filter(c => c.pixels_changed);
      this.history.length = this.head + 1; // a new commit drops the redo branch
      this.record({ revision: this.head + 1, actor, label, ops: names, kind: 'commit', changed: { frames } });
      return frames;
    } catch (e) { this.restore(before); throw e; }
  }
  apply(calls: Call[], label: string, actor: string) {
    const before = this.head, linked = new Set<number>();
    const frames = this.transaction(label, actor, calls.map(c => c.op), () => { for (const c of calls) this.mutate(c, linked); });
    const validation = this.validation();
    if (actor !== 'gui') this.outbox.push({ method: 'project.changed', params: { project: DEMO_PROJECT, revision: this.head, actor, changed: { frames } } });
    return { ok: true, op: calls.length === 1 ? calls[0].op : 'apply_ops', revision: { before, after: this.head }, result: { pixels_changed: frames.reduce((n, f) => n + f.pixels_changed, 0), linked_frames: [...linked].sort((a, b) => a - b) }, changed: { frames }, validation: { ok: validation.ok, counts: validation.counts, delta: { added: [], resolved: [] } } };
  }
  private travel(undo: boolean, p: RpcParams) {
    if (p.expect_revision !== undefined && p.expect_revision !== this.head)
      throw fail('E_REVISION_CONFLICT', `Expected revision ${p.expect_revision}, project is at ${this.head}.`, 'Reload the project state, then retry.');
    const last = this.history.length - 1;
    const to = p.to_revision !== undefined ? int(p.to_revision, 'to_revision', 0, last) : this.head + (undo ? -int(p.steps ?? 1, 'steps', 1) : int(p.steps ?? 1, 'steps', 1));
    if (to < 0) throw fail('E_NOTHING_TO_UNDO', 'Nothing to undo.', 'The bundled sample starts at revision 0.');
    if (to > last) throw fail('E_NOTHING_TO_REDO', 'Nothing to redo.', 'Redo is only available right after an undo.');
    if (undo ? to > this.head : to < this.head) throw fail('E_INVALID_ARGUMENT', `Revision ${to} is not on the ${undo ? 'undo' : 'redo'} path.`, 'Pick a revision from the Activity list.');
    const before = this.head;
    this.restore(this.history[to].snap); this.head = to;
    return { ok: true, revision: { before, after: to } };
  }

  // ---- ops ----
  private layer(id: unknown): LayerState {
    const l = this.layers.find(x => x.id === id || x.name === id);
    if (!l) throw fail('E_NOT_FOUND', `Layer ${String(id)} does not exist.`, `Use one of: ${this.layers.map(x => `${x.id} (${x.name})`).join(', ')}.`);
    return l;
  }
  private mutate({ op, args }: Call, linked: Set<number>) {
    if (op === 'update_layer') {
      const l = this.layer(args.layer);
      if (typeof args.visible === 'boolean') l.visible = args.visible;
      if (typeof args.locked === 'boolean') l.locked = args.locked;
      if (typeof args.name === 'string' && args.name) l.name = args.name;
      if (args.opacity !== undefined) l.opacity = int(args.opacity, 'opacity', 0, 255);
      return;
    }
    if (op === 'set_frame_duration') {
      const ms = int(args.duration_ms, 'duration_ms', 1, 65535);
      for (const f of (args.frames ?? [])) this.durations[int(f, 'frame', 0, this.durations.length - 1)] = ms;
      return;
    }
    const l = this.layer(args.layer), frame = int(args.frame, 'frame', 0, this.durations.length - 1);
    if (l.locked) throw fail('E_LAYER_LOCKED', `Layer ${l.name} is locked.`, 'Unlock it with the lock icon in the timeline, then draw again.', { layer: l.id });
    let cel = l.cels[frame];
    if (!cel) cel = l.cels[frame] = { pixels: new Uint8Array(W * H) };
    l.cels.forEach((c, f) => { if (c === cel && f !== frame) linked.add(f); });
    if (linked.size) linked.add(frame);
    const px = cel.pixels;
    const color = () => {
      const c = int(args.color, 'color', 0, Number.MAX_SAFE_INTEGER);
      if (c >= F.PALETTE.length) throw fail('E_COLOR_NOT_IN_PALETTE', `Palette index ${c} does not exist (palette has ${F.PALETTE.length} colours).`, 'Pick a colour from the palette panel; the palette is locked in the demo.');
      return c;
    };
    const brush = (args.brush ?? { size: 1, shape: 'square' }) as Brush;
    const put = (points: Point[], c: number) => { for (const [x, y] of points) if (x >= 0 && y >= 0 && x < W && y < H) px[y * W + x] = c; };
    const n = (k: string) => int(args[k], k);
    switch (op) {
      case 'set_pixel': put([[n('x'), n('y')]], color()); break;
      case 'set_pixels': put((args.pixels ?? []).map(([x, y]: Point) => [int(x, 'x'), int(y, 'y')] as Point), color()); break;
      case 'stroke': {
        const points = (args.points ?? []).map(([x, y]: Point) => [int(x, 'x'), int(y, 'y')] as Point);
        if (!points.length) throw fail('E_INVALID_ARGUMENT', 'stroke needs at least one point.', 'Pass points as [[x, y], ...].');
        put(stamp(stroke(points, !!args.pixel_perfect && brush.size === 1, brush.size), brush), color()); break;
      }
      case 'line': put(stamp(line(n('x0'), n('y0'), n('x1'), n('y1')), brush), color()); break;
      case 'rect': case 'ellipse': {
        const w = int(args.w, 'w', 1, 4096), h = int(args.h, 'h', 1, 4096);
        put(stamp((op === 'rect' ? rect : ellipse)(n('x'), n('y'), w, h, !!args.filled), brush), color()); break;
      }
      case 'fill': {
        const x = int(args.x, 'x', 0, W - 1), y = int(args.y, 'y', 0, H - 1), c = color();
        const grid = Array.from({ length: H }, (_, j) => Array.from(px.subarray(j * W, (j + 1) * W)));
        floodFill(grid, x, y, args.connectivity === 8 ? 8 : 4).forEach((row, j) => row.forEach((on, i) => { if (on) px[j * W + i] = c; }));
        break;
      }
      case 'transform_region': {
        const dx = n('dx'), dy = n('dy'), region = (args.region ?? { type: 'all' }) as Region;
        const grid = Array.from({ length: H }, (_, j) => Array.from(px.subarray(j * W, (j + 1) * W)));
        const mask = regionMask(region, W, H, grid), moved: [number, number, number][] = [];
        mask.forEach((row, j) => row.forEach((on, i) => { if (on) { moved.push([i + dx, j + dy, px[j * W + i]]); px[j * W + i] = TRANSPARENT; } }));
        for (const [x, y, v] of moved) if (x >= 0 && y >= 0 && x < W && y < H && v !== TRANSPARENT) px[y * W + x] = v;
        break;
      }
      default: throw serverOnly(`Op "${op}"`);
    }
  }
  private query(op: string, args: Record<string, any>) {
    if (op === 'get_pixels') {
      const frame = int(args.frame ?? 0, 'frame', 0, this.durations.length - 1), r = args.rect ?? { x: 0, y: 0, w: W, h: H };
      const x0 = int(r.x, 'rect.x', 0, W - 1), y0 = int(r.y, 'rect.y', 0, H - 1), w = int(r.w, 'rect.w', 1, W - x0), h = int(r.h, 'rect.h', 1, H - y0);
      const sources = args.layer === '@composite' || args.layer === undefined ? [...this.layers].reverse().filter(l => l.visible) : [this.layer(args.layer)];
      const rows: number[][] = [], count = new Map<number, number>();
      for (let y = y0; y < y0 + h; y++) {
        const row: number[] = [];
        for (let x = x0; x < x0 + w; x++) {
          let v = TRANSPARENT;
          for (const l of sources) { const p = l.cels[frame]?.pixels[y * W + x] ?? TRANSPARENT; if (p !== TRANSPARENT) { v = p; break; } }
          row.push(v); count.set(v, (count.get(v) ?? 0) + 1);
        }
        rows.push(row);
      }
      return { rect: { x: x0, y: y0, w, h }, indices: rows, used: [...count].sort((a, b) => b[1] - a[1] || a[0] - b[0]).map(([index, pixels]) => ({ index, pixels, color: F.PALETTE[index] })) };
    }
    // diff_preview
    const last = this.head, a = int(args.from_revision ?? 0, 'from_revision', 0, last), b = int(args.to_revision ?? last, 'to_revision', 0, last);
    const sa = this.history[a].snap, sb = this.history[b].snap;
    const frames: FrameChange[] = [], images: string[] = [];
    for (let f = 0; f < sb.durations.length; f++) {
      const before = composite(sa.layers, f), after = composite(sb.layers, f), change = compare(before, after, f);
      if (!change.pixels_changed) continue;
      frames.push(change);
      if (args.inline !== false) { const img = diffImage(after, before); if (img) images.push(img); }
    }
    return { from_revision: a, to_revision: b, frames, images };
  }
}

/** Transport over DemoBackend: same contract as RpcClient, answered asynchronously. */
export class DemoClient implements Transport {
  readonly backend: DemoBackend;
  private listeners = new Set<(n: Notification) => void>();
  private connections = new Set<(connected: boolean) => void>();
  constructor(backend = new DemoBackend()) { this.backend = backend; }
  subscribe(callback: (n: Notification) => void) { this.listeners.add(callback); return () => { this.listeners.delete(callback); }; }
  onConnection(callback: (v: boolean) => void) { this.connections.add(callback); return () => { this.connections.delete(callback); }; }
  connect() { setTimeout(() => this.connections.forEach(fn => fn(true)), 0); }
  call<T = any>(method: string, params: RpcParams = {}): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      try {
        // Round-trip through JSON like the wire does, so the UI never shares state with the engine.
        resolve(JSON.parse(JSON.stringify(this.backend.handle(method, params))));
        const queued = this.backend.outbox.splice(0);
        if (queued.length) setTimeout(() => queued.forEach(n => this.listeners.forEach(fn => fn(n))), 0);
      } catch (e) { reject(e); }
    });
  }
  close() { this.connections.forEach(fn => fn(false)); }
}
