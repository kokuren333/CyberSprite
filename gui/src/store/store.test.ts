import { describe, expect, it } from 'vitest';
import { initialState, playbackFrames, reconcileView, store, view, type ProjectData, type Tag } from './index';
describe('view state', () => {
  it('keeps tool and selection changes outside project data', () => {
    const project = { layers: [], frames: [{}] } as unknown as ProjectData;
    store.setState({ ...initialState, project }, true);
    view({ tool: 'line', foreground: 3, selection: { type: 'rect', x: 1, y: 2, w: 3, h: 4 } });
    expect(store.getState().project).toBe(project);
    expect(project).toEqual({ layers: [], frames: [{}] });
  });
  it('repairs references after an external structural commit', () => {
    expect(reconcileView({ layers: [{ id: 'L2', type: 'image' }], frames: [{}] } as ProjectData, 'L1', 10)).toEqual({ layer: 'L2', frame: 0 });
  });
  for (const [direction, expected] of [['forward', [2, 3, 4]], ['reverse', [4, 3, 2]], ['pingpong', [2, 3, 4, 3]], ['pingpong_reverse', [4, 3, 2, 3]]] as const)
    it(`plays ${direction}`, () => expect(playbackFrames({ from: 2, to: 4, direction } as Tag, 10)).toEqual(expected));
  it('plays a single-frame pingpong once per cycle', () => expect(playbackFrames({ from: 1, to: 1, direction: 'pingpong' } as Tag, 2)).toEqual([1]));
});
