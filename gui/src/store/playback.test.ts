import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { playbackFrames, type Tag } from './index';

type PlaybackCase = {
  name: string;
  input: { tag: Tag; durations_ms: number[]; loop: number; cycles: number };
  expected: { sequence: number[]; durations_ms: number[]; observed_sequence: number[]; observed_durations_ms: number[] };
};
const vectors: { cases: PlaybackCase[] } = JSON.parse(readFileSync(resolve('../tests/vectors/playback/sequences.json'), 'utf8'));
describe('shared core playback vectors', () => {
  for (const c of vectors.cases) it(c.name, () => {
    const sequence = playbackFrames(c.input.tag, c.input.durations_ms.length);
    expect(sequence).toEqual(c.expected.sequence);
    expect(sequence.map(frame => c.input.durations_ms[frame])).toEqual(c.expected.durations_ms);
    const observed = Array.from({ length: c.input.cycles }, () => sequence).flat();
    expect(observed).toEqual(c.expected.observed_sequence);
    expect(observed.map(frame => c.input.durations_ms[frame])).toEqual(c.expected.observed_durations_ms);
  });
  it('loops all project frames when no tag is selected', () => expect(playbackFrames(undefined, 4)).toEqual([0, 1, 2, 3]));
  it('returns no steps for an empty project', () => expect(playbackFrames(undefined, 0)).toEqual([]));
});
