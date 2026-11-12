// Drive the built Pages demo (gui/demo-dist) in Chromium at desktop and phone sizes,
// check that drawing / playback / agent simulation / server-only refusal work, and save
// screenshots. Usage (from gui/): npm run build:demo && node scripts/demo-check.mjs [outDir]
// Serves demo-dist from a throwaway static server on 127.0.0.1 (no network access needed).
import { createServer } from 'node:http';
import { mkdirSync, readFileSync, statSync } from 'node:fs';
import { extname, join, normalize, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium, devices } from '@playwright/test';

const gui = resolve(fileURLToPath(import.meta.url), '../..');
const root = join(gui, 'demo-dist');
const out = resolve(process.argv[2] ?? join(gui, 'test-results', 'demo')); // git-ignored; docs/design/demo/ holds a picked subset
mkdirSync(out, { recursive: true });
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.json': 'application/json' };
const server = createServer((req, res) => {
  const pathname = new URL(req.url, 'http://x').pathname;
  if (!pathname.startsWith('/CyberSprite/')) { res.writeHead(404); res.end(); return; }
  const path = normalize(decodeURIComponent(pathname.slice('/CyberSprite/'.length))).replace(/^([/\\])+/, '');
  if (path.startsWith('..')) { res.writeHead(403); res.end(); return; }
  let file = join(root, path || 'index.html');
  try { if (statSync(file).isDirectory()) file = join(file, 'index.html'); res.writeHead(200, { 'content-type': types[extname(file)] ?? 'application/octet-stream' }); res.end(readFileSync(file)); }
  catch { res.writeHead(404); res.end(); }
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
// Serve under a sub-path, like https://<user>.github.io/<repo>/, to prove the relative base.
const url = `http://127.0.0.1:${server.address().port}/CyberSprite/`;
const browser = await chromium.launch();
const failures = [];
const check = (ok, what) => { console.log(`${ok ? 'ok  ' : 'FAIL'} ${what}`); if (!ok) failures.push(what); };

async function session(name, options, mobile) {
  const context = await browser.newContext({ ...options, locale: name.endsWith('en') ? 'en-US' : 'ja-JP' });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto(url);
  await page.getByTestId('revision').filter({ hasText: 'r3' }).waitFor();
  check(await page.locator('.demo-notice').isVisible(), `${name}: demo notice visible`);
  const canvas = page.getByTestId('sprite-canvas');
  await page.waitForTimeout(300);
  const box = await canvas.boundingBox();
  check(box && box.width >= 150, `${name}: canvas shown (${box?.width}px)`);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  check(overflow <= 0, `${name}: no horizontal page overflow (${overflow})`);
  await page.screenshot({ path: join(out, `${name}-1-open.png`) });

  // draw: pick red, pencil stroke across the board (touch on the phone)
  if (mobile) await page.getByRole('tab', { name: /パレット|Palette/ }).click();
  await page.locator('.palette-color').nth(11).click();
  await page.locator('.tool-button').first().click();
  const at = (fx, fy) => [box.x + box.width * fx, box.y + box.height * fy];
  if (mobile) {
    const cdp = await context.newCDPSession(page);
    const touch = (type, points) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: points.map(([x, y]) => ({ x, y })) });
    await touch('touchStart', [at(0.08, 0.1)]);
    for (let i = 1; i <= 8; i++) await touch('touchMove', [at(0.08 + i * 0.03, 0.1 + i * 0.02)]);
    await touch('touchEnd', []);
  } else {
    await page.mouse.move(...at(0.08, 0.1)); await page.mouse.down();
    for (let i = 1; i <= 8; i++) await page.mouse.move(...at(0.08 + i * 0.03, 0.1 + i * 0.02));
    await page.mouse.up();
  }
  check(await page.getByTestId('revision').filter({ hasText: 'r4' }).waitFor({ timeout: 3000 }).then(() => true, () => false), `${name}: ${mobile ? 'touch' : 'mouse'} stroke committed (r4)`);
  // fill tool on the board behind the robot
  await page.locator('.tool-button').nth(5).click();
  await page.locator('.palette-color').nth(3).click();
  if (mobile) await page.getByRole('tab', { name: /タイムライン|Timeline/ }).click();
  await page.locator('.layer-name', { hasText: 'board' }).click();
  await canvas.click({ position: { x: Math.round(box.width * 0.03), y: Math.round(box.height * 0.5) } });
  check(await page.getByTestId('revision').filter({ hasText: 'r5' }).waitFor({ timeout: 3000 }).then(() => true, () => false), `${name}: fill committed on the linked board cel (r5)`);
  await page.locator('.timeline-grid tbody tr').nth(1).locator('th .layer-name').click(); // back to chip layer

  // agent simulation → Activity entry + signal
  await page.locator('.demo-actions .pad').first().click();
  check(await page.getByTestId('revision').filter({ hasText: 'r6' }).waitFor({ timeout: 3000 }).then(() => true, () => false), `${name}: simulated agent commit (r6)`);
  if (mobile) { await page.waitForTimeout(150); await page.screenshot({ path: join(out, `${name}-2-drawn.png`) }); await page.getByRole('tab', { name: /エージェント|Agent/ }).click(); }
  check(await page.locator('.activity-entry').first().textContent().then(t => /agent:demo/.test(t)), `${name}: Activity lists the agent commit`);
  await page.waitForTimeout(100);
  await page.screenshot({ path: join(out, `${name}-${mobile ? 3 : 2}-${mobile ? 'agent' : 'drawn'}.png`) });

  // undo / redo via the Edit menu
  await page.locator('.edit-menu summary').click();
  await page.locator('.edit-menu .menu-pop button').first().click();
  check(await page.getByTestId('revision').filter({ hasText: 'r5' }).waitFor({ timeout: 3000 }).then(() => true, () => false), `${name}: undo → r5`);

  // playback: frame counter advances
  if (mobile) await page.getByRole('tab', { name: /タイムライン|Timeline/ }).click();
  await page.locator('.transport .pad').nth(2).click();
  const seen = new Set();
  for (let i = 0; i < 8; i++) { await page.waitForTimeout(90); seen.add(await page.locator('.frame-counter').textContent()); }
  const counter = [...seen].join(', ');
  await page.screenshot({ path: join(out, `${name}-${mobile ? 4 : 3}-playing.png`) });
  await page.locator('.transport .pad').nth(2).click();
  check(seen.size > 1, `${name}: playback running (${counter})`);

  // server-only: Export dialog explains it is unavailable
  await page.locator('.file-menu summary').click();
  await page.locator('.file-menu .menu-pop button').nth(3).click();
  const note = await page.locator('dialog .note').textContent();
  check(/サーバ|server/i.test(note ?? ''), `${name}: export shows server-only note`);
  await page.screenshot({ path: join(out, `${name}-${mobile ? 5 : 4}-export-off.png`) });
  await page.locator('dialog .dlg-actions .pad').first().click();
  // zoom in via the canvas controls
  await page.getByRole('button', { name: /拡大$|Zoom in/ }).click();
  check(errors.length === 0, `${name}: no console errors ${errors.join(' | ')}`);
  await context.close();
}

try {
  await session('desktop-ja', { viewport: { width: 1440, height: 900 } }, false);
  await session('desktop-en', { viewport: { width: 1280, height: 720 } }, false);
  await session('phone-ja', { ...devices['Pixel 7'] }, true);
  await session('phone-en', { ...devices['iPhone 13'], defaultBrowserType: undefined }, true);
} finally { await browser.close(); server.close(); }
console.log(failures.length ? `\n${failures.length} check(s) failed` : '\nall demo checks passed');
process.exit(failures.length ? 1 : 0);
