# GUI の起動と構成

GUI はテーマ「Circuit White」の案 C「Solder Mask」（`docs/design/theme-options/SELECTION.md` の緩和策つき）で描く。画面の見本は `docs/design/gui/`（英語、高コントラスト、日本語、設定ダイアログ、プラットフォームの選択と検査、モデルの利用条件）。データ経路と Op の呼び方は下の「接続とデータ」のとおりで、見た目の層はそこに手を入れていない。

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

`npm run build` は `src/cybersprite/server/static/` に出力する。`.gitkeep` 以外のビルド結果は git 管理外。リリースはリポジトリ直下から `uv run python tools/build_release.py` で作る。npm ci・原文ライセンス照合・CLIアイコン出力を含むGUIビルド・uv build・wheel内容照合を順に実行する。Nodeは配布後の実行には不要。`tools/verify_release.py <wheel>` はリポジトリ外の新規venvで認証付きHTML/JS/CSS/アイコン配信を確認する。

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

## プラットフォームと利用条件（R1-GUI）

- 新規プロジェクトのダイアログは、開いた直後に `op.apply {op:"list_platforms"}` を 1 回呼ぶ（プロジェクトがまだ無くても使える query）。選択肢は継承を解いた `system` ごとの `<optgroup>` で、`ID — 題名 · 幅×高さ 固定/目安`（canvas が無ければ「大きさ自由」）。選ぶと引数 JSON を `platform`、canvas の幅と高さ、明示パレットなし（プラットフォームの既定パレットを使う）に置き換える。「なし」は従来の `{width:32,height:32,platform:null,...}`。引数はその後も手で直せる。値の組立ては `gui/src/platforms.ts` の純関数で、vitest で固定した。
- ステータスバーは `summary.platform` があるときだけ「プラットフォーム」と ID を出す（`data-testid="platform-id"`）。
- 検証タブは Q-PLT-* と Q-CRF-01 を「プラットフォームの検査」見出し（ID と件数つき）の下に分ける。Q-CRF-01 は常に情報として表示する。関門の判定はサーバの `ok` のままで、GUI は並べ替えるだけ。
- 生成モデルの利用条件は `components/Terms.tsx`。操作ダイアログの結果（`generate_image` の `model_terms`、`list_generators` の `models[].badges`）から、`id`・`license`・`badge` を持つ項目を集めて表示する。文言は 4 種（商用利用可 / 商用可（利用制限あり） / 非商用のみ / 要確認）を訳し、サーバの英語の `badge` と `commercial_use` も同じ行に残す。色だけに頼らず、アイコンと語で区別する。背景と帯は既存の検証行と同じトークンで、`check:contrast` に行を足した。
- 見本: `docs/design/gui/platform-main-en.png`、`platform-new-project-ja.png`、`model-terms-en.png`。

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

M5/M6のOpは統合済みで、スキーマとダイアログへ反映される。M10シナリオ4は実GUI WebSocketとCLIを交互に使い、project.changed・構造変更のE_REVISION_CONFLICT・再読込・最終書き出しを検査する。W3/W5の専用フォームとブラウザ操作の拡充はKNOWN_ISSUES参照。

## テーマ

| ファイル | 中身 |
|---|---|
| `gui/src/theme/tokens.css` | 全トークン。`--cs-*` は SPEC §14.3.1 の基本色、`--ui-*` は役割（本文、補助、見出し帯、押下中のパッド、選択行、フォーカス、キャンバスの重ね表示など）。`/* @theme normal */` と `/* @theme high-contrast */` の 2 ブロック。寸法（文字の大きさ、パネルの幅、行の高さ、面取りの形）もここ |
| `gui/src/theme/app.css` | 部品の見た目。色は必ず `var(--ui-*)` か `var(--cs-*)` で参照する |
| `gui/src/theme/prefs.ts` | 表示の設定。`<html>` の `data-contrast`、`data-text`、`data-scale`、`data-motion` に反映し、localStorage に保存する |
| `gui/src/components/chrome.tsx` | 意匠の部品。アイコン、シルク印刷のピクセルフォント（5×7）、IC の切り欠き、ビア、パネルの見出し帯。すべて 1×1 の矩形の連なりを `crispEdges` で描く |

意匠の約束:

- パネルは IC のパッケージ。左上に 45° の切り欠き、2px の配線色の枠、見出し帯にビアとシルク印刷のラベル（英語表示ではラベルが見出しを兼ね、日本語表示では隣に日本語の見出しを出す）。ツールバーは両側に DIP のピンを付ける。
- **アクティブなパネルだけ**見出し帯を水色で塗り、枠を濃い水色にして外側に 1px の薄い線（発光の代わり）を出す。アクティブは最後にポインタかフォーカスが入ったパネル。ほかの見出し帯は白。
- パッド（ボタン）は 1 段の面取り（`--chamfer`）。押下中は濃い水色の枠と淡い水色の面。フォーカスは内側 2px のインクの枠。
- ぼかし、発光のグラデーション、アンチエイリアスの曲線は使わない。グラデーションは市松模様と DIP ピンの、軸に沿った硬い境目だけ。キャンバスの重ね表示（グリッド、選択枠、変わったピクセルの枠）は `fillRect` の 1px 線で描く。
- 状態は形でも示す。押下中は枠、セルは塗り（あり）・中抜き（リンク）・点（空）、検証は合格チップ・三角・八角形のアイコンと文字、前景色と背景色は FG / BG の札、選択色は実線、背景色は破線。
- エージェントのコミットが届くと、エージェントパネルの見出しの配線を信号が 3 コマ（300 ms）で活動タブへ走り、キャンバスの変わった範囲を 1 秒間紫の枠で囲む。

### 設定（右上の設定ボタン）

言語（日本語 / English）、コントラスト（OS に従う / 標準 / 高コントラスト）、本文の文字（12 / 13 / 14 px、既定 13）、表示倍率（1 / 2 / 3 倍。CSS の `zoom` による整数倍。キャンバスの座標計算は倍率を割り戻す）、動き（OS に従う / 減らす）。OS の `prefers-contrast: more` と `prefers-reduced-motion: reduce` に連動する。動きを減らすと、すべてのアニメーションと遷移を止め、信号の演出も出さない。

高コントラスト版は、線と文字をすべて `--cs-ink`、面をすべて白にし、アクティブな見出し帯は反転（インク地に白文字）、押下中と選択行は太い枠で示す。

## アイコン

原本は `assets/ui/icons/*.csprite`（1 アイコン 1 プロジェクト、16×16、`assets/ui/icons/README.md`）。`npm run icons` が各プロジェクトをリポジトリのルートから CLI で書き出す。

```powershell
uv run cybersprite -p assets/ui/icons/<名前>.csprite export image --out gui/public/icons/<名前>.png
```

- `npm run build` と `npm run dev` は先に `npm run icons` を実行する。出力 `gui/public/icons/` は git 管理外で、Vite が `static/icons/` に写す。
- 書き出しの結果の `ok`、`validation_ok`、`verified` と 16×16 を確かめ、1 つでも外れたらビルドを止める。
- GUI では `<Icon name="…" scale={1|2} />` で使う（`image-rendering: pixelated`、整数倍だけ）。ツールバーは 2 倍、ほかは 1 倍。名前の一覧 `ICONS`（`chrome.tsx`）と原本の一致は `src/components/icons.test.ts` が検査する。
- 足りないアイコンは、ほかの手段で描かず、`assets/ui/icons/tools/icon_grids.py` に設計データを足して `build_icons.py` で `.csprite` を作る（M8 で `settings` を追加）。

## コントラストの自動検査

```powershell
cd gui
npm run check:contrast        # --verbose で全組を表示
```

`scripts/check-contrast.mjs` が `tokens.css` の通常版と高コントラスト版を読み、`var()` をたどって色を求め、画面で実際に使う前景と背景の組を WCAG 2.x の比で検査する。基準は SPEC §14.3.3（本文 7:1、補助の文字 4.5:1、意味のある文字以外の要素 3:1）。装飾（配線、区切り線、パッドの縁、警告色の帯）は参考値として表示だけする。あわせて、`app.css` が未定義の変数を参照していないこと、キャンバスの周囲と市松模様の彩度が低いこと（クロマ 0.10 以下）も検査する。`npm test` は vitest のあとにこの検査を実行する。部品に新しい色の組を足したら、この表にも足すこと。

## スクリーンショットの撮り直し

```powershell
# 原本を壊さないよう、作業用の写しを開く
uv run cybersprite gui .gui-check/shots/mechanic.csprite --no-browser --port 8790
cd gui
node scripts/screenshots.mjs "<表示された URL（# 以降も含む）>" ../docs/design/gui "C:\Program Files\Google\Chrome\Application\chrome.exe" .gui-check/shots/mechanic.csprite
```

4 番目の引数を渡すと、撮影中にエージェントとして 1 コミットし、W1 の強調表示を写す（写しにだけ使うこと）。

## 部品と className

Playwright の試験はアクセシブルな名前（ツールの `aria-label`、`Play`、`Onion skin` のラベル、`Project path`、`Arguments (JSON)`、`Apply`）、`data-testid`（`sprite-canvas`、`revision`、`status`）と、下の className に依存する。見た目を変えるときも残すこと。

| コンポーネント | 主な className |
|---|---|
| App | app-shell（`data-active-panel`）, menu-bar, file-menu, edit-menu, op-menu, status-bar, global-error, job-progress |
| ContextBar | context-bar |
| Palette | palette-panel, palette-list, palette-color |
| Toolbar | toolbar, tool-button |
| Canvas | canvas-region, document-tabs, canvas-controls, canvas-viewport, sprite-canvas, canvas-sample |
| Timeline | timeline, playback-controls, timeline-grid（`tbody` の行 = レイヤー、`td` = セル）, timeline-cel, cel-empty/present/linked |
| AgentPanel | agent-panel, agent-tabs, agent-content, agent-activity/validate/diff/sources, activity-list, activity-entry, validation-issues, validation-metrics, validation-delta, diff-image, sources-list, source-image |
| SchemaDialog | schema-dialog, op-schema, export-plan, dialog-error, operation-result, stage-image |
| SettingsDialog / Tooltip | settings-dialog / tooltip（`data-tip` 属性を持つ要素に、ポインタとキーボードのフォーカスで出す） |

`get_info` はFIX-2で各リンクセルの `link` とレイヤーごとの `link_groups` を返すようになり、以前のリンク情報欠落は解消した。

ショートカット設定の読み込み・永続 prefs、取り込みの専用項目 UI、書き出し種別ごとの予定寸法の詳細計算は後続拡張。現在は生成スキーマと JSON 入力で全引数を明示できる。GUI だけに保存・変換・書出しの処理を増やさないこと。
