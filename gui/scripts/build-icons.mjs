// Export every UI icon source (assets/ui/icons/*.csprite) to a PNG with the
// CyberSprite CLI (SPEC §14.3.2 / §14.8-5). Icons are never drawn by other means.
// Output: gui/public/icons/<name>.png (git-ignored build output, copied by Vite).
// The CLI only writes under its working directory, so it runs from the repo root.
import { execFile } from 'node:child_process';
import { mkdirSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

const run = promisify(execFile);
const gui = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const root = resolve(gui, '..');
const source = join(root, 'assets', 'ui', 'icons');
const outRel = 'gui/public/icons';
const out = join(root, outRel);
const names = readdirSync(source).filter(n => n.endsWith('.csprite')).map(n => n.slice(0, -'.csprite'.length)).sort();
if (names.length === 0) throw new Error(`No icon projects in ${source}`);

rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });

async function exportIcon(name, sync) {
  const args = ['run', ...(sync ? [] : ['--no-sync']), 'cybersprite', '-p', `assets/ui/icons/${name}.csprite`,
    'export', 'image', '--out', `${outRel}/${name}.png`];
  let stdout;
  try {
    ({ stdout } = await run('uv', args, { cwd: root, windowsHide: true, maxBuffer: 1 << 20 }));
  } catch (e) {
    throw new Error(`Icon export failed for ${name}: ${e.stderr || e.stdout || e.message}\n` +
      `Hint: run "uv run cybersprite -p assets/ui/icons/${name}.csprite validate" from the repo root.`);
  }
  const envelope = JSON.parse(stdout);
  const file = envelope.result?.files?.[0];
  if (!envelope.ok || !envelope.result.validation_ok || !envelope.result.verified || file?.width !== 16 || file?.height !== 16)
    throw new Error(`Icon ${name} did not export as a verified 16x16 PNG: ${stdout}`);
}

// First export syncs the environment once; the rest run in parallel without re-syncing.
await exportIcon(names[0], true);
const queue = names.slice(1);
await Promise.all(Array.from({ length: 6 }, async () => {
  for (let name = queue.shift(); name; name = queue.shift()) await exportIcon(name, false);
}));
writeFileSync(join(out, 'manifest.json'), JSON.stringify(names) + '\n');
console.log(`icons: exported ${names.length} icons to ${outRel}/`);
