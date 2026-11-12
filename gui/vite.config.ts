import { defineConfig } from 'vitest/config';
const target = process.env.CYBERSPRITE_SERVER ?? 'http://127.0.0.1:8765';
// `--mode demo` (npm run build:demo / dev:demo): the GitHub Pages hands-on demo. Same UI code,
// in-browser backend (src/demo), relative base so it works from any sub-path or file://.
export default defineConfig(({ mode }) => mode === 'demo' ? {
  base: './',
  build: { outDir: 'demo-dist', emptyOutDir: true },
  server: { host: '127.0.0.1', port: 5174, strictPort: true },
} : {
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
