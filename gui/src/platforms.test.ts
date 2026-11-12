import { describe, expect, it } from 'vitest';
import { collectTerms, displayLevel, groupPlatforms, isPlatformRule, newProjectArgs, termsTone, type PlatformEntry } from './platforms';
const entry = (id: string, system: string | null, canvas: PlatformEntry['canvas'] = null): PlatformEntry => ({ id, title: id, origin: 'builtin', system, role: null, canvas });
describe('platform selection', () => {
  it('groups by system in code-point order and keeps entry order', () => {
    const groups = groupPlatforms([entry('dmg', 'dmg'), entry('free', 'free'), entry('dmg/sprite-16', 'dmg'), entry('odd', null)]);
    expect(groups.map(g => g.system)).toEqual(['', 'dmg', 'free']);
    expect(groups[1].items.map(i => i.id)).toEqual(['dmg', 'dmg/sprite-16']);
  });
  it('none keeps the pre-platform arguments; a platform fills its canvas and palette default', () => {
    const base = { palette: 'cs-circuit-16', frames: 1 };
    expect(newProjectArgs(base, null)).toEqual({ palette: 'cs-circuit-16', frames: 1, width: 32, height: 32, platform: null });
    expect(newProjectArgs(base, entry('nds/sprite-80', 'nds', { w: 80, h: 80, fixed: true }))).toEqual({ frames: 1, width: 80, height: 80, platform: 'nds/sprite-80' });
    expect(newProjectArgs(base, entry('nds', 'nds'))).toEqual({ frames: 1, width: 32, height: 32, platform: 'nds' });
  });
  it('puts Q-PLT and Q-CRF-01 under the platform heading, craft always as info', () => {
    expect(['Q-PLT-05', 'Q-CRF-01', 'Q-PAL-01', undefined].map(isPlatformRule)).toEqual([true, true, false, false]);
    expect(displayLevel('Q-CRF-01', 'error')).toBe('info');
    expect(displayLevel('Q-PLT-05', 'warning')).toBe('warning');
  });
});
describe('licence badges', () => {
  it('maps server badge text to tones and treats unknown text as review', () => {
    expect(['commercial OK', 'commercial OK with use restrictions (not OSI)', 'non-commercial only', 'needs review', 'other'].map(termsTone))
      .toEqual(['ok', 'restricted', 'nc', 'review', 'review']);
  });
  it('collects badges from generation results and model listings once', () => {
    const terms = { id: 'm', license: 'MIT', commercial_use: 'yes', badge: 'commercial OK', message: 'm: commercial OK' };
    const result = { result: { model_terms: [terms], backends: [{ models: [{ id: 'm', license: 'MIT', badges: [terms, { ...terms, id: 'b', badge: 'needs review' }] }] }] } };
    expect(collectTerms(result).map(t => `${t.id}:${t.badge}`)).toEqual(['m:commercial OK', 'b:needs review']);
  });
});
