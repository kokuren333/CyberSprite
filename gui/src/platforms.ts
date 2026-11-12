/** Pure helpers for platform selection, platform issue grouping and model licence badges.
 * The server owns every value: list_platforms supplies the entries, term_badges the badge text. */
export type PlatformEntry = {
  id: string; title: string; origin: string; system: string | null; role: string | null;
  canvas: { w: number; h: number; fixed: boolean } | null;
};
export type PlatformGroup = { system: string; items: PlatformEntry[] };

/** Group by inherited system ID in code-point order; entries keep the server's ID order. */
export function groupPlatforms(entries: PlatformEntry[]): PlatformGroup[] {
  const groups = new Map<string, PlatformEntry[]>();
  for (const entry of entries) {
    const key = entry.system ?? '';
    (groups.get(key) ?? groups.set(key, []).get(key)!).push(entry);
  }
  return [...groups].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)).map(([system, items]) => ({ system, items }));
}

/** new_project arguments: "none" is exactly the pre-platform dialog; a platform drops the
 * explicit palette (so defaults.palette applies) and copies a declared canvas. */
export function newProjectArgs(base: Record<string, unknown>, entry: PlatformEntry | null): Record<string, unknown> {
  const plain: Record<string, unknown> = { ...base, width: 32, height: 32 };
  if (!entry) return { ...plain, platform: null };
  const rest = { ...plain };
  delete rest.palette;
  return { ...rest, platform: entry.id, ...(entry.canvas ? { width: entry.canvas.w, height: entry.canvas.h } : {}) };
}

/** Q-PLT-* and Q-CRF-01 belong to the platform heading; craft is always informational. */
export const isPlatformRule = (rule: string | undefined) => !!rule && (rule.startsWith('Q-PLT-') || rule === 'Q-CRF-01');
export const displayLevel = (rule: string | undefined, level: string) => (rule === 'Q-CRF-01' ? 'info' : level);

export type Terms = { id: string; license: string; commercial_use: string; badge: string; message: string };
export type TermsTone = 'ok' | 'restricted' | 'nc' | 'review';
/** Tone of a server badge string; unknown text is treated as needing review. */
export function termsTone(badge: string): TermsTone {
  if (badge === 'commercial OK') return 'ok';
  if (badge.startsWith('commercial OK with use restrictions')) return 'restricted';
  if (badge === 'non-commercial only') return 'nc';
  return 'review';
}
/** Every badge object inside an operation result (generate_image model_terms, list_generators
 * models[].badges), de-duplicated by id and badge in first-seen order. */
export function collectTerms(value: unknown): Terms[] {
  const found: Terms[] = [], seen = new Set<string>();
  const visit = (v: unknown) => {
    if (Array.isArray(v)) { v.forEach(visit); return; }
    if (!v || typeof v !== 'object') return;
    const o = v as Record<string, unknown>;
    if (typeof o.badge === 'string' && typeof o.id === 'string' && typeof o.license === 'string') {
      const key = `${o.id}\u0000${o.badge}`;
      if (!seen.has(key)) { seen.add(key); found.push(o as unknown as Terms); }
      return;
    }
    Object.values(o).forEach(visit);
  };
  visit(value);
  return found;
}
