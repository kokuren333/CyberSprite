# gui/

GUI フロントエンド（TypeScript + React + Vite）の置き場所。**まだコードはない。** 着手は `docs/SPEC.md` §16.4 の M8。

- 仕様: `docs/SPEC.md` §14（画面構成、テーマ「Circuit White」、ワークフロー、ショートカット、サーバとの通信）。
- GUI は、エージェントと同じ `project.json` を同じ Op で編集する薄い画面である。GUI 専用の編集経路を作らない。合成はサーバ（Python のコア）が行う。
- ビルド成果物は `src/cybersprite/server/static/` にコピーして wheel に同梱する。利用者は Node を必要としない。
- **デザインとビジュアルの判断は、必ず Opus 系が行う。**
- アイコン、フォント、文言はすべて自作。他製品の画面、アイコン、配色表を取り込まない（`docs/SPEC.md` §3）。
