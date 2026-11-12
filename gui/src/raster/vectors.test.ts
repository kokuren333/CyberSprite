import { readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import * as r from './index';
const directory = resolve('../tests/vectors/raster');
for (const file of readdirSync(directory).filter(n => n.endsWith('.json')).sort()) {
  const group = JSON.parse(readFileSync(resolve(directory, file), 'utf8'));
  describe(group.kind, () => {
    for (const c of group.cases) it(c.name, () => {
      const a = c.input;
      let actual: unknown;
      switch (group.kind) {
        case 'line': actual = { points: r.line(a.x0, a.y0, a.x1, a.y1) }; break;
        case 'rect': actual = { points: r.rect(a.x, a.y, a.w, a.h, a.filled) }; break;
        case 'ellipse': {
          const points = new Set(r.ellipse(a.x, a.y, a.w, a.h, a.filled).map(p => p.join(',')));
          actual = { rows: Array.from({ length: a.h }, (_, y) => Array.from({ length: a.w }, (_, x) => points.has(`${x},${y}`) ? '#' : '.').join('')) }; break;
        }
        case 'polygon': actual = { points: r.polygon(a.points, a.closed, a.filled) }; break;
        case 'stroke': actual = { points: r.stroke(a.points, a.pixel_perfect) }; break;
        case 'brush': actual = { offsets: r.brushOffsets(a.brush.size, a.brush.shape), points: r.stamp(a.points, a.brush) }; break;
        case 'flood_fill': actual = { rows: r.maskRows(r.floodFill(a.image, a.x, a.y, a.connectivity)) }; break;
        case 'outline': actual = { rows: r.maskRows(r.outline(r.parseMask(a.opaque), a.placement, a.connectivity)) }; break;
        case 'region': actual = { rows: r.maskRows(r.regionMask(a.region, a.canvas_w, a.canvas_h, a.image)) }; break;
        case 'transform': actual = { pixels: r.transform(a.pixels, a.flip, a.rotate), rows: r.maskRows(r.transform(r.parseMask(a.mask), a.flip, a.rotate)) }; break;
        default: throw Error(`Unimplemented vector group ${group.kind}`);
      }
      expect(actual).toEqual(c.expected);
    });
  });
}
