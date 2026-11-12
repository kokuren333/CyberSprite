import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e', workers: 1, timeout: 30000,
  use: { baseURL: 'http://127.0.0.1:8766', locale: 'en-US', headless: true },
  webServer: {
    command: 'uv run python tools/gui_smoke_server.py', cwd: '..',
    url: 'http://127.0.0.1:8766', reuseExistingServer: false, timeout: 30000,
  },
});
