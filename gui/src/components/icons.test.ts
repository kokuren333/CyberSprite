import { readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
// Every icon the GUI references must have a CyberSprite source project (SPEC §14.8-5),
// and every source must be listed, so `npm run icons` and the UI never drift apart.
describe('UI icons', () => {
  const sources = readdirSync(resolve(__dirname, '../../../assets/ui/icons')).filter(n => n.endsWith('.csprite')).map(n => n.slice(0, -8)).sort();
  const listed = [...readFileSync(resolve(__dirname, 'chrome.tsx'), 'utf8').match(/export const ICONS = \[([\s\S]*?)\] as const/)![1].matchAll(/'([a-z-]+)'/g)].map(m => m[1]).sort();
  it('lists exactly the .csprite icon sources', () => expect(listed).toEqual(sources));
  it('only uses listed names in components', () => {
    const dir = resolve(__dirname);
    for (const file of readdirSync(dir).filter(f => f.endsWith('.tsx')).concat(['../App.tsx'])) {
      for (const m of readFileSync(resolve(dir, file), 'utf8').matchAll(/<Icon name="([a-z-]+)"/g)) expect(sources, `${file}: ${m[1]}`).toContain(m[1]);
    }
  });
});
