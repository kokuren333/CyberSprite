# gui/

M8-S の接続・状態管理と無装飾の仮画面。React / TypeScript / Vite / Zustand を使用する。

起動、開発用プロキシ、ビルド、検査、Opus 用コンポーネント/className 一覧は [docs/GUI.md](../docs/GUI.md)。

- `npm ci` → `npm test` → `npm run build`。成果物は `src/cybersprite/server/static/`。
- `npm run licenses` で全インストール済み依存の原文と台帳を確認する。再生成はリポジトリ root から `node tools/check_js_licenses.mjs`。
- `npx playwright install chromium` → `npm run test:e2e` で実 CLI とブラウザの W1/W2/W4 を確認する。

- 仕様: `docs/SPEC.md` §14（画面構成、テーマ「Circuit White」、ワークフロー、ショートカット、サーバとの通信）。
- GUI は、エージェントと同じ `project.json` を同じ Op で編集する薄い画面である。GUI 専用の編集経路を作らない。合成はサーバ（Python のコア）が行う。
- ビルド成果物は `src/cybersprite/server/static/` にコピーして wheel に同梱する。利用者は Node を必要としない。
- **デザインとビジュアルの判断は、必ず Opus 系が行う。**
- アイコン、フォント、文言はすべて自作。他製品の画面、アイコン、配色表を取り込まない（`docs/SPEC.md` §3）。
