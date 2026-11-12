import { describe, expect, it } from 'vitest';
import { RpcError } from '../api/client';
import { DEMO_PROJECT, DemoBackend, DemoClient, SCHEMAS } from './backend';
const fixed = () => '2026-11-12T00:00:00.000Z';
const info = (b: DemoBackend) => (b.handle('project.get') as any).result;
const pixel = (b: DemoBackend, frame: number, x: number, y: number) =>
  (b.handle('op.apply', { op: 'get_pixels', args: { layer: '@composite', frame, rect: { x, y, w: 1, h: 1 } } }) as any).result.used[0].index;
const code = (fn: () => unknown) => { try { fn(); } catch (e) { return (e as RpcError).data?.code; } return 'no error'; };

describe('demo backend (in-browser stand-in for the server)', () => {
  it('opens the bundled sample with the agent-built history', () => {
    const b = new DemoBackend(fixed), p = info(b);
    expect(p.summary).toEqual({ name: 'chip-robot', width: 32, height: 32, revision: 3 });
    expect(p.frames.map((f: any) => f.duration_ms)).toEqual([160, 120, 160, 120]);
    expect(p.history.entries.map((e: any) => e.revision)).toEqual([3, 2, 1, 0]);
    expect(p.history.entries.every((e: any) => e.actor === 'agent:demo')).toBe(true);
    // board cel is linked across frames; sparks only on odd frames
    expect(p.layers[0].cels).toEqual([{ frame: 0 }, { frame: 1, link: 0 }, { frame: 2, link: 0 }, { frame: 3, link: 0 }]);
    expect(p.layers[2].cels.map((c: any) => c.frame)).toEqual([1, 3]);
    expect(p.validation.ok).toBe(true);
  });
  it('is deterministic: same ops give the same pixels', () => {
    const run = () => {
      const b = new DemoBackend(fixed);
      b.handle('op.apply', { op: 'stroke', args: { layer: 'L2', frame: 0, points: [[0, 0], [7, 3]], color: 11, brush: { size: 2, shape: 'circle' } } });
      b.handle('op.apply', { op: 'fill', args: { layer: 'L1', frame: 0, x: 0, y: 0, color: 3, connectivity: 4 } });
      return (b.handle('render.frame', { frames: [0, 1, 2, 3] }) as any).frames.map((f: any) => f.rgba);
    };
    expect(run()).toEqual(run());
  });
  it('draws with palette indices and renders RGBA8 rows', () => {
    const b = new DemoBackend(fixed);
    const r: any = b.handle('op.apply', { op: 'rect', args: { layer: 'L2', frame: 0, x: 0, y: 0, w: 3, h: 3, filled: true, color: 11 } });
    expect(r.revision).toEqual({ before: 3, after: 4 });
    expect(r.result.pixels_changed).toBe(9);
    expect(pixel(b, 0, 2, 2)).toBe(11);
    const frame = (b.handle('render.frame', { frame: 0 }) as any).frames[0];
    const raw = Uint8Array.from(atob(frame.rgba), c => c.charCodeAt(0));
    expect([frame.width, frame.height, raw.length]).toEqual([32, 32, 32 * 32 * 4]);
    expect([...raw.subarray(0, 4)]).toEqual([0xF2, 0x54, 0x5B, 0xFF]);
  });
  it('edits through a linked cel change every linked frame and say so', () => {
    const b = new DemoBackend(fixed);
    const r: any = b.handle('op.apply', { op: 'set_pixel', args: { layer: 'L1', frame: 2, x: 0, y: 0, color: 13 } });
    expect(r.result.linked_frames).toEqual([0, 1, 2, 3]);
    expect([0, 1, 2, 3].map(f => pixel(b, f, 0, 0))).toEqual([13, 13, 13, 13]);
  });
  it('undoes, redoes, restores to a revision and drops the redo branch on a new commit', () => {
    const b = new DemoBackend(fixed);
    b.handle('op.apply', { op: 'set_pixel', args: { layer: 'L2', frame: 0, x: 0, y: 0, color: 11 } });
    b.handle('history.undo');
    expect(pixel(b, 0, 0, 0)).toBe(6);
    b.handle('history.redo');
    expect(pixel(b, 0, 0, 0)).toBe(11);
    b.handle('history.undo', { to_revision: 1 });
    expect(info(b).layers[1].cels).toEqual([]);
    b.handle('op.apply', { op: 'set_pixel', args: { layer: 'L2', frame: 0, x: 1, y: 1, color: 4 } });
    expect(info(b).summary.revision).toBe(2);
    expect(code(() => b.handle('history.redo'))).toBe('E_NOTHING_TO_REDO');
    expect(code(() => b.handle('history.undo', { to_revision: 0, expect_revision: 7 }))).toBe('E_REVISION_CONFLICT');
  });
  it('rolls back a failed transaction and reports actionable errors', () => {
    const b = new DemoBackend(fixed);
    b.handle('op.apply', { op: 'update_layer', args: { layer: 'L2', locked: true } });
    const before = (b.handle('render.frame', { frame: 0 }) as any).frames[0].rgba;
    expect(code(() => b.handle('op.apply', { op: 'set_pixel', args: { layer: 'L2', frame: 0, x: 0, y: 0, color: 1 } }))).toBe('E_LAYER_LOCKED');
    expect(code(() => b.handle('op.apply', { op: 'set_pixel', args: { layer: 'L1', frame: 0, x: 0, y: 0, color: 99 } }))).toBe('E_COLOR_NOT_IN_PALETTE');
    expect(code(() => b.handle('op.apply', { op: 'set_pixel', args: { layer: 'L1', frame: 0, x: 0.5, y: 0, color: 1 } }))).toBe('E_INVALID_ARGUMENT');
    expect((b.handle('render.frame', { frame: 0 }) as any).frames[0].rgba).toBe(before);
    expect(info(b).summary.revision).toBe(4);
  });
  it('refuses server-only work with a hint instead of pretending', () => {
    const b = new DemoBackend(fixed);
    const cases: [string, Record<string, unknown>][] = [['export.run', { op: 'export_image' }], ['import.commit', {}], ['pipeline.preview', {}], ['op.apply', { op: 'new_project', args: {} }], ['op.apply', { op: 'export_image', args: {} }], ['project.open', { project: 'other.csprite' }], ['project.close', {}]];
    for (const [method, params] of cases) {
      let error: RpcError | undefined;
      try { b.handle(method, params); } catch (e) { error = e as RpcError; }
      expect(error?.data?.code, method).toBe('E_DEMO_SERVER_ONLY');
      expect(error?.data?.hint).toMatch(/clone the repository/i);
    }
    expect(SCHEMAS.some(s => s.name.startsWith('export_') || s.name === 'import_image' || s.name === 'new_project')).toBe(false);
    expect((b.handle('project.open', { project: DEMO_PROJECT }) as any).project).toBe(DEMO_PROJECT);
  });
  it('simulates agent commits through the same notification as the server', async () => {
    const client = new DemoClient(new DemoBackend(fixed)), seen: any[] = [];
    client.subscribe(n => seen.push(n));
    const r: any = await client.call('demo.agent_commit');
    await new Promise(resolve => setTimeout(resolve, 0));
    expect(r.revision.after).toBe(4);
    expect(seen).toHaveLength(1);
    expect(seen[0].method).toBe('project.changed');
    expect(seen[0].params.actor).toBe('agent:demo');
    expect(seen[0].params.changed.frames[0]).toMatchObject({ frame: 3, pixels_changed: 2 });
    await expect(client.call('export.run')).rejects.toBeInstanceOf(RpcError);
  });
  it('compares revisions for the Diff tab', () => {
    const b = new DemoBackend(fixed);
    const d: any = b.handle('op.apply', { op: 'diff_preview', args: { from_revision: 2, to_revision: 3 } });
    expect(d.result.frames.map((f: any) => f.frame)).toEqual([1, 3]);
    expect(d.result.frames[0].pixels_changed).toBe(10);
  });
});
