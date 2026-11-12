import { createStore } from 'zustand/vanilla';
import { useStore } from 'zustand';
import { RpcClient, RpcError, type RpcParams } from '../api/client';
import type { Brush, Point, Region } from '../raster';
export type Tool = 'pencil' | 'eraser' | 'line' | 'rect' | 'ellipse' | 'fill' | 'eyedropper' | 'select' | 'move' | 'hand' | 'zoom';
export type Layer = { id: string; name: string; type: string; visible: boolean; locked: boolean; opacity: number; children?: Layer[]; cels?: any[] };
export type Tag = { id: string; name: string; from: number; to: number; direction: string; repeat: number };
export type ProjectData = { summary: { name: string; width: number; height: number; revision: number; platform?: { id: string; canvas: { w: number; h: number; fixed: boolean } | null } | null }; layers: Layer[]; frames: { duration_ms: number }[]; tags: Tag[]; palette: { colors: string[]; transparent_index: number }; validation: any; history: any; sources: any; slices: any[] };
export type OpSchema = { name: string; kind: string; inputSchema: any; idempotency: string; description: string };
export const flattenLayers = (layers: Layer[]): Layer[] => layers.flatMap(l => [l, ...flattenLayers(l.children ?? [])]);
export function reconcileView(data: ProjectData, layer: string, frame: number) {
  const all = flattenLayers(data.layers).filter(l => l.type === 'image');
  return { layer: all.some(l => l.id === layer) ? layer : all[0]?.id ?? '', frame: Math.max(0, Math.min(frame, data.frames.length - 1)) };
}
export function playbackFrames(tag: Tag | undefined, count: number): number[] {
  const ascending = Array.from({ length: tag ? tag.to - tag.from + 1 : count }, (_, i) => i + (tag?.from ?? 0));
  if (!tag || ascending.length <= 1) return ascending;
  if (tag?.direction === 'reverse' || tag?.direction === 'pingpong_reverse') ascending.reverse();
  const sequence: number[] = [];
  if (tag.direction.startsWith('pingpong')) {
    for (let leg = 0; leg < (tag.repeat || 2); leg++) {
      const pass = leg % 2 === 0 ? ascending : [...ascending].reverse();
      sequence.push(...(leg === 0 ? pass : pass.slice(1)));
    }
  } else {
    for (let pass = 0; pass < (tag.repeat || 1); pass++) sequence.push(...ascending);
  }
  // Match animation_sequence(loop=0) only for an infinitely looping preview.
  if (!tag.repeat && sequence.length > 2 && sequence.at(-1) === sequence[0]) sequence.pop();
  return sequence;
}
type State = {
  connected: boolean; projectPath: string; project: ProjectData | null; schemas: OpSchema[];
  tool: Tool; layer: string; frame: number; foreground: number; background: number; zoom: number;
  pan: Point; pointer: Point; selection: Region; brush: Brush; filled: boolean; pixelPerfect: boolean; connectivity: 4 | 8;
  onion: boolean; grid: boolean; playing: boolean; tag: string; tab: 'Activity' | 'Validate' | 'Diff' | 'Sources';
  status: string; error: string; delta: any; change: any; progress: any; sources: any; diff: any; underlay: string | null;
};
export const initialState: State = { connected: false, projectPath: '', project: null, schemas: [], tool: 'pencil', layer: '', frame: 0, foreground: 1, background: 0, zoom: 8, pan: [0, 0], pointer: [0, 0], selection: { type: 'all' }, brush: { size: 1, shape: 'square' }, filled: false, pixelPerfect: false, connectivity: 4, onion: false, grid: false, playing: false, tag: '', tab: 'Activity', status: '', error: '', delta: null, change: null, progress: null, sources: null, diff: null, underlay: null };
export const store = createStore<State>(() => initialState);
export const useEditor = () => useStore(store);
export const view = (patch: Partial<State>) => store.setState(patch);
let client: RpcClient;
let generation = 0;
export function attachClient(value: RpcClient) {
  client = value;
  client.onConnection(connected => {
    view({ connected });
    if (connected) void act(async () => {
      view({ schemas: await client.call('op.list') });
      const path = store.getState().projectPath;
      if (path) await client.call('project.open', { project: path });
      await refresh();
    });
  });
  client.subscribe(n => {
    if (n.method === 'project.changed') { view({ change: n.params }); void act(refresh); }
    if (n.method === 'job.progress') view({ progress: n.params });
  });
  client.connect();
}
export async function act(work: () => Promise<unknown>) {
  try { view({ error: '' }); return await work(); }
  catch (e) {
    const error = e as RpcError;
    view({ error: `${error.data?.code ?? ''} ${error.message} ${error.data?.hint ?? ''}`.trim() });
    if (error.data?.code === 'E_REVISION_CONFLICT') await refresh();
  }
}
export async function refresh() {
  const ticket = ++generation;
  const data = await client.call('project.get');
  if (ticket !== generation) return;
  const current = store.getState(), project = data.result as ProjectData;
  view({ projectPath: data.project, project, ...reconcileView(project, current.layer, current.frame) });
}
export const rpc = (method: string, args: RpcParams = {}) => client.call(method, args);
export async function openProject(project: string) { await rpc('project.open', { project }); view({ projectPath: project }); await refresh(); }
export async function closeProject() { await rpc('project.close'); generation++; view({ project: null, projectPath: '', playing: false }); }
export async function apply(op: string, args: RpcParams, project = store.getState().projectPath) {
  const state = store.getState();
  const drawing = ['set_pixel', 'set_pixels', 'stroke', 'line', 'rect', 'ellipse', 'fill', 'erase', 'transform_region'].includes(op);
  const schema = state.schemas.find(s => s.name === op);
  const result = await rpc('op.apply', { project, op, args: { ...(!drawing && op !== 'new_project' && schema?.kind === 'mutate' ? { expect_revision: state.project?.summary.revision } : {}), ...args, ...(['mutate', 'ingest'].includes(schema?.kind ?? '') ? { preview: 'inline' } : {}) } });
  // Read and expose the validation delta before fetching the authoritative preview.
  view({ delta: result.validation, status: `r${typeof result.revision === 'number' ? result.revision : result.revision?.after}` });
  if (op === 'new_project') view({ projectPath: project });
  await refresh();
  return result;
}
