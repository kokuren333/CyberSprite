/** True only in `vite build --mode demo` (npm run build:demo). Vite replaces the
 * expression with a literal, so the normal build drops every demo-only branch. */
export const DEMO: boolean = import.meta.env.MODE === 'demo';
/** Optional link shown in the demo notice (set by the Pages workflow). */
export const REPO_URL: string = import.meta.env.VITE_DEMO_REPO_URL ?? '';
