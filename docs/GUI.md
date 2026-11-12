# GUI の起動と構成

M8-S の GUI は接続・状態・Op 呼出しを確かめるための無装飾の仮画面である。見た目は Opus の後続作業で決める。テーマ C のトークンだけを原文どおり `gui/src/theme/tokens.css` に移した。

```powershell
uv sync --locked --extra gui
cd gui
npm ci
npm run build
cd ..
uv run cybersprite gui example.csprite --root . --no-browser
```

表示された URL は `#` より後も含めて開く。既定は OS が選ぶ空きポート。固定したければ `--port 8765`、追加の許可領域には `--allow-dir` を使う。`project`、入出力、プレビュー、元画像の実体パスを MCP と共通の規則で制限する。`--root` の既定は起動時のカレントディレクトリ。

すべての編集はコミット時点で保存される。Ctrl+S は保存済みのリビジョンを表示する。描画はポインタを離すと 1 Op を送る。キャンバスにフォーカスして矢印で座標、Enter で 1 ピクセルを指定する操作もある。通常の HTML ボタン、入力、ダイアログはキーボードで操作できる。

## 開発

```powershell
uv run cybersprite gui example.csprite --port 8765 --no-browser
# 別の端末。サーバの URL のフラグメントを localhost ではなく下記 URL に付ける。
cd gui
$env:CYBERSPRITE_SERVER = 'http://127.0.0.1:8765'
npm run dev
# http://127.0.0.1:5173/#<サーバが表示したトークン>
```

Vite は 127.0.0.1 だけで待ち受け、`/ws`、`/auth`、`/files` をプロキシする。プロキシではバックエンド自身の Origin/Host に変換する。この開発サーバは信頼できるローカル作業専用で、配布物には含めない。

`npm run build` は `src/cybersprite/server/static/` に出力する。`.gitkeep` 以外のビルド結果は git 管理外。M10 の wheel ビルドは **先に** `npm ci && npm run build` を実行し、その後 `uv build` を呼ぶこと。Node は配布後の実行には不要。

## 接続とデータ

`server.serve` がソケットを先に bind して空きポートを確定し、ランダムなトークンを URL フラグメントで渡す。`/` はデータを持たない初期ページ。`POST /auth` が厳密な Origin と Bearer トークンを検査して HttpOnly / SameSite=Strict Cookie を設定する。静的ファイルと `/files/` は Cookie 必須。WebSocket `/ws` は `['cybersprite', token]` のサブプロトコルと厳密な Origin/Host が必要。トークンを URL クエリやアクセスログへ出さない。

JSON-RPC 2.0 の名前付き引数を使う。通常要求、通知、バッチを扱い、プロトコルエラーは標準の負の整数コード、業務エラーは `-32000` と `error.data = {code,message,hint,details}` を返す。

| メソッド | 引数・結果の要点 |
|---|---|
| `project.open/close/get` | `open: {project}`。get は get_info の封筒。各接続が開くプロジェクトを持つ |
| `op.list` | レジストリの全 Op と生成された入出力スキーマ |
| `op.apply` | apply_ops と同じ `{ops,label,...}`。単独呼出しは `{op,args,project?}` も可。new_project と query もこの入口 |
| `render.frame` | `{frame}` または `{frames:[...]}`, optional `region:{x,y,w,h}`。最大17枚。`encoding:rgba8-base64` と行順 RGBA8 の `frames:[{frame,width,height,rgba}]` |
| `history.list/undo/redo` | 登録 Op の引数。undo は追加で `{to_revision}` を受け、現在の undo 経路から steps を算出して Op に渡す。経路外は具体的なエラー |
| `validate.run` | validate の引数と封筒 |
| `pipeline.preview` | import_image の引数、dry_run を強制。段階画像と関門は登録 Op の結果をそのまま表示 |
| `import.commit`, `export.run` | import_image / export_* の薄い呼出し。export は `{op:export_image,...}` 等 |
| `sources.list/get` | list_sources / get_source。未登録時は get_info の sources を利用 |
| `prefs.get/set` | language(auto/ja/en)、zoom(1〜64)、grid/onion(bool)。サーバ存続中の表示設定だけ |

`project.changed` は `{project,revision,actor,changed}`。250 ms ごとに mtime+size を見て、変化時だけ正本を読み、リビジョンを比較する。複数コミットを観測した場合はジャーナルの各行を通知する。`job.progress` は長い処理の開始0%と完了100%。処理内の段階別進捗は後続 Op がフックを提供してから拡張する。

サーバは同じ `ops.execute(..., actor='gui')` を呼ぶ。合成は core の render のみ。フロントは RGBA を整数倍で表示し、描きかけだけ共通ラスタ規則で仮描画する。Zustand の tool/layer/frame/colors/selection は表示状態で、Op の対象はポインタ押下時に固定して明示する。構造変更は expect_revision を付け、描画には付けない。再接続時は構造を再取得し、途切れた変更要求を自動再送しない。

## 確認と後続作業

```powershell
uv run pytest tests/server -q
uv run python tools/check_licenses.py --extra gui
cd gui
npm test
npm run licenses
npm run build
npx playwright install chromium
npm run test:e2e
```

JS の全インストール済み直接・推移依存は `THIRD_PARTY_JS.md`、原文は `LICENSES_JS.txt`。`node tools/check_js_licenses.mjs` で再生成し差分を読む。`--check` は記録との一致も検査する。ネイティブ依存は OS ごとにインストール集合が違うため、CI は Windows/Linux 各々で原文を検査する。esbuild/Rollup のネイティブ専用パッケージに LICENSE がない場合、**同じ版**の親パッケージが同梱する原文を読む。許可表外・不明・原文なしは拒否する。

M5/M6 がこのブランチに未統合なので W3/W5 の実ファイルを伴う通し確認は統合後に行う。現時点でも登録 Op を追加すればスキーマとダイアログへ自動反映する。サーバ試験では仮の登録 Op によって予行・配置・書出しの転送、actor、dry_run、job.progress を検査している。合成・検証・描画・履歴・CLI 反映には実装済みの本物の Op を使う。

Opus の変更箇所は次のとおり。CSS の配色・レイアウト、アイコン、市松模様、スライス/タイル格子、強調の見た目、アクセシビリティの意匠検査は後続作業。

| コンポーネント | 主な className |
|---|---|
| App | app-shell, menu-bar, file-menu, edit-menu, op-menu, workspace, status-bar, global-error, job-progress |
| ContextBar | context-bar |
| Palette | palette-panel, palette-list, palette-color |
| Toolbar | toolbar, tool-button |
| Canvas | canvas-region, document-tabs, canvas-controls, canvas-viewport, sprite-canvas, canvas-sample |
| Timeline | timeline, playback-controls, timeline-grid, timeline-cel, cel-empty/present/linked |
| AgentPanel | agent-panel, agent-tabs, agent-content, agent-activity/validate/diff/sources, activity-list, activity-entry, validation-issues, validation-metrics, validation-delta, diff-image, sources-list, source-image |
| SchemaDialog | schema-dialog, op-schema, export-plan, dialog-error, operation-result, stage-image |

ショートカット設定の読み込み・永続 prefs、取り込みの専用項目 UI、書き出し種別ごとの予定寸法の詳細計算は後続拡張。現在は生成スキーマと JSON 入力で全引数を明示できる。GUI だけに保存・変換・書出しの処理を増やさないこと。
