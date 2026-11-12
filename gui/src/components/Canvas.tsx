import { useEffect, useRef, useState } from 'react';
import { useText } from '../i18n';
import { fileUrl } from '../api/files';
import { act, apply, flattenLayers, rpc, store, useEditor, view } from '../store';
import { ellipse, line, rect, stamp, stroke, type Point } from '../raster';
import { Icon, Notch } from './chrome';
/** Crisp 1px outline (fillRect on integer device pixels; strokeRect would anti-alias). */
function box(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, width = 1) {
  ctx.fillRect(x, y, w, width); ctx.fillRect(x, y + h - width, w, width);
  ctx.fillRect(x, y, width, h); ctx.fillRect(x + w - width, y, width, h);
}
const token = (el: Element, name: string) => getComputedStyle(el).getPropertyValue(name).trim();

type Drag = { points: Point[]; state: ReturnType<typeof store.getState>; pan?: Point; scroll?: Point; tool: string };
function pixels(drag: Drag): Point[] {
  const { points, state: s, tool } = drag, a = points[0], b = points.at(-1)!;
  const box = [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.abs(a[0] - b[0]) + 1, Math.abs(a[1] - b[1]) + 1] as const;
  if (['select', 'move', 'hand', 'zoom', 'fill', 'eyedropper'].includes(tool)) return [];
  return stamp(tool === 'line' ? line(...a, ...b) : tool === 'rect' ? rect(...box, s.filled) : tool === 'ellipse' ? ellipse(...box, s.filled) : stroke(points, s.pixelPerfect, s.brush.size), s.brush);
}
export function Canvas() {
  const s = useEditor(), t = useText(), canvas = useRef<HTMLCanvasElement>(null), viewport = useRef<HTMLDivElement>(null);
  const drag = useRef<Drag | null>(null), base = useRef<HTMLCanvasElement | null>(null);
  const underlay = useRef<HTMLImageElement | null>(null);
  const [, repaint] = useState(0);
  const [sample, setSample] = useState<string>('');
  const space = useRef(false);
  useEffect(() => {
    underlay.current = null;
    if (!s.underlay) { repaint(n => n + 1); return; }
    let active = true;
    const image = new Image();
    image.onload = () => { if (active) { underlay.current = image; repaint(n => n + 1); } };
    image.src = fileUrl(s.underlay);
    return () => { active = false; };
  }, [s.underlay]);
  useEffect(() => {
    const down = (e: KeyboardEvent) => { if (e.code === 'Space' && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement)) { space.current = true; e.preventDefault(); } };
    const up = (e: KeyboardEvent) => { if (e.code === 'Space') space.current = false; };
    window.addEventListener('keydown', down); window.addEventListener('keyup', up);
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); };
  }, []);
  useEffect(() => {
    let live = true;
    if (!s.project) { base.current = null; return; }
    void act(async () => {
      const count = s.project!.frames.length;
      const frames = s.onion ? [s.frame - 1, s.frame + 1, s.frame].filter(f => f >= 0 && f < count) : [s.frame];
      const data = await rpc('render.frame', { frames });
      if (!live) return;
      const output = document.createElement('canvas');
      output.width = s.project!.summary.width; output.height = s.project!.summary.height;
      const ctx = output.getContext('2d')!;
      for (const frame of data.frames) {
        const raw = Uint8ClampedArray.from(atob(frame.rgba), c => c.charCodeAt(0));
        const source = document.createElement('canvas'); source.width = frame.width; source.height = frame.height;
        source.getContext('2d')!.putImageData(new ImageData(raw, frame.width, frame.height), 0, 0);
        ctx.globalAlpha = frame.frame === s.frame ? 1 : 0.25;
        ctx.drawImage(source, 0, 0);
      }
      base.current = output; repaint(n => n + 1);
    });
    return () => { live = false; };
  }, [s.projectPath, s.project?.summary.revision, s.frame, s.onion]);
  useEffect(() => {
    const output = canvas.current, image = base.current;
    if (!output || !image || !s.project) return;
    const ctx = output.getContext('2d')!;
    ctx.clearRect(0, 0, output.width, output.height); ctx.imageSmoothingEnabled = false;
    if (underlay.current) { ctx.globalAlpha = 0.25; ctx.drawImage(underlay.current, 0, 0, output.width, output.height); ctx.globalAlpha = 1; }
    ctx.drawImage(image, 0, 0, output.width, output.height);
    const drawing = drag.current;
    if (drawing) {
      const color = drawing.state.project!.palette.colors[drawing.tool === 'eraser' ? drawing.state.project!.palette.transparent_index : drawing.state.foreground];
      ctx.fillStyle = color;
      for (const [x, y] of pixels(drawing)) {
        if (drawing.tool === 'eraser') ctx.clearRect(x * s.zoom, y * s.zoom, s.zoom, s.zoom);
        else ctx.fillRect(x * s.zoom, y * s.zoom, s.zoom, s.zoom);
      }
    }
    // Overlays: pixel grid, marquee, and the 1-second changed-pixels highlight (W1).
    if (s.grid && s.zoom >= 3) {
      ctx.fillStyle = token(output, '--ui-grid-line');
      for (let x = 1; x < image.width; x++) ctx.fillRect(x * s.zoom, 0, 1, output.height);
      for (let y = 1; y < image.height; y++) ctx.fillRect(0, y * s.zoom, output.width, 1);
    }
    if (s.selection.type === 'rect') {
      const [x, y, w, h] = [s.selection.x! * s.zoom, s.selection.y! * s.zoom, s.selection.w! * s.zoom, s.selection.h! * s.zoom];
      ctx.fillStyle = '#FFFFFF'; box(ctx, x - 1, y - 1, w + 2, h + 2, 1); box(ctx, x + 1, y + 1, w - 2, h - 2, 1);
      ctx.fillStyle = token(output, '--ui-selection-line'); box(ctx, x, y, w, h, 1);
    }
    if (s.change) for (const f of s.change.changed?.frames ?? []) {
      if (f.frame !== s.frame || !f.bbox) continue;
      const [x, y, w, h] = [f.bbox.x * s.zoom, f.bbox.y * s.zoom, f.bbox.w * s.zoom, f.bbox.h * s.zoom];
      ctx.fillStyle = '#FFFFFF'; box(ctx, x - 3, y - 3, w + 6, h + 6, 1);
      ctx.fillStyle = token(output, '--ui-change-line'); box(ctx, x - 2, y - 2, w + 4, h + 4, 2);
    }
  });
  useEffect(() => { if (s.change) { const timer = setTimeout(() => view({ change: null }), 1000); return () => clearTimeout(timer); } }, [s.change]);
  if (!s.project) return <section className="canvas-region panel" data-panel="canvas" aria-label={t('canvas')}><Notch /><div className="document-tabs" /><div className="canvas-empty"><Icon name="folder" scale={2} /><p>{t('noProject')}</p></div></section>;
  function point(e: React.PointerEvent<HTMLCanvasElement>): Point {
    const bounds = e.currentTarget.getBoundingClientRect();
    // Bounds include the integer UI scale (CSS zoom); convert to canvas pixels, then to sprite pixels.
    const k = e.currentTarget.width / bounds.width;
    return [Math.floor((e.clientX - bounds.left) * k / s.zoom), Math.floor((e.clientY - bounds.top) * k / s.zoom)];
  }
  async function commit(drawing: Drag) {
    const { state: at, points, tool } = drawing, a = points[0], b = points.at(-1)!;
    const target = { layer: at.layer, frame: at.frame }, color = tool === 'eraser' ? at.project!.palette.transparent_index : at.foreground;
    if (tool === 'eyedropper') {
      const value = await rpc('op.apply', { op: 'get_pixels', args: { layer: '@composite', frame: at.frame, rect: { x: b[0], y: b[1], w: 1, h: 1 } } });
      view({ foreground: value.result.used[0].index }); return;
    }
    if (tool === 'hand' || tool === 'select') return;
    if (tool === 'zoom') { view({ zoom: Math.min(64, at.zoom + 1) }); return; }
    if (tool === 'move') { await apply('transform_region', { ...target, region: at.selection, dx: b[0] - a[0], dy: b[1] - a[1] }, at.projectPath); return; }
    if (tool === 'fill') { await apply('fill', { ...target, x: b[0], y: b[1], color, connectivity: at.connectivity }, at.projectPath); return; }
    if (tool === 'line') await apply('line', { ...target, x0: a[0], y0: a[1], x1: b[0], y1: b[1], color, brush: at.brush }, at.projectPath);
    else if (tool === 'rect' || tool === 'ellipse') await apply(tool, { ...target, x: Math.min(a[0], b[0]), y: Math.min(a[1], b[1]), w: Math.abs(b[0] - a[0]) + 1, h: Math.abs(b[1] - a[1]) + 1, filled: at.filled, color, brush: at.brush }, at.projectPath);
    else await apply('stroke', { ...target, points, color, brush: at.brush, pixel_perfect: at.pixelPerfect }, at.projectPath);
  }
  const checker = s.zoom * Math.max(1, Math.round(8 / s.zoom));
  const tool = s.tool === 'hand' ? 'grab' : s.tool === 'zoom' ? 'zoom-in' : 'crosshair';
  return <section className="canvas-region panel" data-panel="canvas" aria-label={t('canvas')}><Notch />
    <div className="document-tabs" role="tablist" aria-label={t('documents')}>
      <h2 className="dtab on" role="tab" aria-selected="true"><span className="dtab-name">{s.project.summary.name}.csprite</span><span className="dtab-rev mono">r{s.project.summary.revision}</span></h2>
      <div className="canvas-controls">
        <button className="pad icon-only" aria-label={t('zoomOut')} data-tip={t('zoomOut')} onClick={() => view({ zoom: Math.max(1, s.zoom - 1) })}><Icon name="remove" /></button>
        <output className="pad val mono" aria-label={t('zoomLevel')}>{s.zoom * 100}%</output>
        <button className="pad icon-only" aria-label={t('zoomIn')} data-tip={t('zoomIn')} onClick={() => view({ zoom: Math.min(64, s.zoom + 1) })}><Icon name="add" /></button>
      </div>
    </div>
    <div ref={viewport} className="canvas-viewport" style={{ cursor: tool }}>
      <canvas ref={canvas} className="sprite-canvas checker" style={{ backgroundSize: `${checker * 2}px ${checker * 2}px`, ['--checker' as string]: `${checker}px` }} data-testid="sprite-canvas" aria-label={t('canvas')} tabIndex={0} width={s.project.summary.width * s.zoom} height={s.project.summary.height * s.zoom}
        onWheel={e => view({ zoom: Math.max(1, Math.min(64, s.zoom + (e.deltaY < 0 ? 1 : -1))) })}
        onPointerDown={e => {
          if (e.button !== 0 && e.button !== 1) return;
          const p = point(e); e.currentTarget.setPointerCapture(e.pointerId);
          drag.current = { points: [p], state: store.getState(), tool: space.current || e.button === 1 ? 'hand' : e.altKey ? 'eyedropper' : s.tool, pan: [e.clientX, e.clientY], scroll: [viewport.current!.scrollLeft, viewport.current!.scrollTop] };
          repaint(n => n + 1);
        }}
        onPointerMove={e => {
          const p = point(e); view({ pointer: p });
          const d = drag.current;
          if (!d) return;
          d.points.push(p);
          if (d.tool === 'hand') { viewport.current!.scrollLeft = d.scroll![0] + d.pan![0] - e.clientX; viewport.current!.scrollTop = d.scroll![1] + d.pan![1] - e.clientY; view({ pan: [Math.trunc(viewport.current!.scrollLeft), Math.trunc(viewport.current!.scrollTop)] }); }
          if (d.tool === 'select') { const a = d.points[0]; view({ selection: { type: 'rect', x: Math.min(a[0], p[0]), y: Math.min(a[1], p[1]), w: Math.abs(a[0] - p[0]) + 1, h: Math.abs(a[1] - p[1]) + 1 } }); }
          repaint(n => n + 1);
        }}
        onPointerUp={e => {
          const d = drag.current; drag.current = null;
          if (d) { d.points.push(point(e)); void act(() => commit(d)); }
          repaint(n => n + 1);
        }}
        onPointerCancel={() => { drag.current = null; repaint(n => n + 1); }}
        onKeyDown={e => {
          if (e.key === 'Enter' && !e.ctrlKey) { e.stopPropagation(); void act(() => apply('set_pixel', { layer: s.layer, frame: s.frame, x: s.pointer[0], y: s.pointer[1], color: s.foreground })); }
          if (e.key.startsWith('Arrow')) { e.preventDefault(); e.stopPropagation(); view({ pointer: [Math.max(0, Math.min(s.project!.summary.width - 1, s.pointer[0] + (e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0))), Math.max(0, Math.min(s.project!.summary.height - 1, s.pointer[1] + (e.key === 'ArrowDown' ? 1 : e.key === 'ArrowUp' ? -1 : 0)))] }); }
          if (e.key === 'i') void act(async () => { const v = await rpc('op.apply', { op: 'get_pixels', args: { layer: '@composite', frame: s.frame, rect: { x: s.pointer[0], y: s.pointer[1], w: 1, h: 1 } } }); setSample(String(v.result.used[0].index)); });
        }} />
    </div>
    <div className="cv-foot"><span className="cv-chip mono">{t('frame')} <b>{s.frame}</b> · {t('layer')} <b>{flattenLayers(s.project.layers).find(l => l.id === s.layer)?.name}</b>{s.tag && <> · {t('tag')} <b>{s.project.tags.find(g => g.id === s.tag)?.name}</b></>}</span>
      <output className="canvas-sample cv-chip mono" hidden={!sample}>{t('sampled')} #{sample}</output></div>
  </section>;
}
