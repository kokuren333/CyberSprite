import { defineConfig } from 'vitest/config';
const target = process.env.CYBERSPRITE_SERVER ?? 'http://127.0.0.1:8765';
export default defineConfig({
  base: '/',
  build: { outDir: '../src/cybersprite/server/static', emptyOutDir: false },
  server: {
    host: '127.0.0.1', strictPort: true,
    proxy: {
      '/ws': { target, ws: true, changeOrigin: true, rewriteWsOrigin: true },
      '/auth': { target, changeOrigin: true, configure(proxy) {
        proxy.on('proxyReq', req => req.setHeader('Origin', target));
      } },
      '/files': { target, changeOrigin: true },
    },
  },
  test: { include: ['src/**/*.test.ts'], environment: 'node' },
});
