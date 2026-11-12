// Capture review screenshots of the running GUI (our own UI only).
// Usage: node scripts/screenshots.mjs "<server URL with #token>" <output dir> [chrome.exe]
// Start the server first, e.g. `uv run cybersprite gui <copy>.csprite --no-browser --port 8790`.
import { chromium } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

// Optional 4th argument: the opened project; an agent commit is made to show the W1 highlight.
const [url, outArg, chrome, project] = process.argv.slice(2);
if (!url || !outArg) throw new Error('Usage: node scripts/screenshots.mjs <url#token> <outdir> [chrome]');
const out = resolve(outArg);
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: chrome || undefined, headless: true });

async function shot(name, { language = 'en', contrast = 'normal', setup } = {}) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: language === 'ja' ? 'ja-JP' : 'en-US', reducedMotion: 'reduce' });
  await context.addInitScript(([language, contrast]) => {
    localStorage.setItem('cybersprite.gui.language', language);
    localStorage.setItem('cybersprite.gui.display', JSON.stringify({ contrast, motion: 'auto', text: 13, scale: 1 }));
  }, [language, contrast]);
  const page = await context.newPage();
  await page.goto(url);
  await page.getByTestId('sprite-canvas').waitFor();
  await page.waitForFunction(() => [...document.images].every(i => i.complete && i.naturalWidth > 0));
  for (let i = 0; i < 4; i++) await page.locator('.canvas-controls button').last().click();
  await page.locator('.activity-entry').nth(1).click();
  if (setup) await setup(page);
  await page.waitForTimeout(name === 'main-en' ? 150 : 400);
  await page.screenshot({ path: resolve(out, `${name}.png`) });
  await context.close();
}
await shot('main-en', { setup: async page => {
  await page.locator('.tool-button').nth(0).hover();
  if (!project) return;
  const before = await page.getByTestId('revision').textContent();
  execFileSync('uv', ['run', 'cybersprite', '-p', project, '--actor', 'agent:claude-code', 'op', 'line', '--label', 'Brighten wrench edge',
    '--args', JSON.stringify({ layer: 'details', frame: 0, x0: 26, y0: 14, x1: 28, y1: 14, color: Number(before.slice(1)) % 2 ? 4 : 5 })], { cwd: resolve('..') });
  await page.waitForFunction(b => document.querySelector('[data-testid=revision]')?.textContent !== b, before);
  await page.locator('.activity-entry').first().hover();
} });
await shot('main-high-contrast', { contrast: 'high', setup: async page => { await page.locator('.tool-button').nth(2).hover(); } });
await shot('main-ja', { language: 'ja', setup: async page => { await page.locator('.palette-color').nth(7).click(); await page.locator('#tab-Validate').click(); } });
await shot('settings-ja', { language: 'ja', setup: async page => { await page.locator('.menu-right .pad').click(); } });
await browser.close();
console.log(`screenshots written to ${out}`);
