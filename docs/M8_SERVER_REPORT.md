# M8-S 実装報告

対象ブランチ: `m8-server`。担当: Codex、非ビジュアル工学。M5/M6 未統合の基盤に対してレジストリを汎用的に接続した。

## 実装

- `src/cybersprite/server/`: CLI の `serve` フック、127.0.0.1 専用の bind 済みソケット、フラグメント認証、静的配信、MCP 共通のパス制限、§14.6 全メソッド、JSON-RPC 通知とバッチ、共有外部監視、RGBA8 の領域/複数フレーム配信。変更は必ず `ops.execute(..., actor='gui')`。
- `gui/src/api/`: RPC、通知、再接続、切断要求の再送禁止、root 相対ファイル URL。
- `gui/src/store/`: 正本から取得する構造と独立した表示状態、外部変更時の参照修復、明示 Op 引数、検証デルタ、競合処理、タグ方向の再生列。
- `gui/src/raster/`: 既存10分類すべてを TS で実装。仮描画に使用する線・矩形・楕円・ストローク・ブラシを含む。楕円は BigInt。
- `gui/src/components/`: 無装飾の HTML で全領域を露出。スキーマと JSON 入力による新規/開く/取り込み/書出し/任意 Op。タイムライン、実データの活動/検証/差分/来歴、元画像下絵。i18n は ja/en、OS 既定。テーマ C の既存トークンをそのまま配置。
- `tools/check_js_licenses.mjs`: 実インストール済み46パッケージと各 LICENSE 内のバンドル通知を検査。`gui/THIRD_PARTY_JS.md` と全文 `gui/LICENSES_JS.txt` を生成。許可表外・原文なしを拒否。
- ビルド成果物は `server/static/`（`.gitkeep` 以外 git 管理外）。Windows/Linux の GUI CI、Playwright の隔離サーバ、短い起動・構成文書は [GUI.md](GUI.md)。

## 受け入れ確認

| 項目 | 状態と証拠 |
|---|---|
| W1 外部作業の反映 | 成功。実 CLI コミットが1秒以内に revision/活動/キャンバスへ反映。サーバ試験と Playwright |
| W2 ポインタ解放時1 Op | 成功。ドラッグ中は revision 不変、解放後 line 1件と actor=gui。Ctrl+S は保存済み表示だけ |
| W3 取り込み予行/配置 | 配管成功。登録スキーマ→予行 dry_run→段階画像/結果表示→明示確認→配置。サーバ転送試験成功。M6 の実ファイル通し確認は統合待ち |
| W4 再生/オニオン/時間変更 | 成功。全方向の列は store 試験、reverse/repeat=1・オニオン要求・時間変更のコミットは Playwright |
| W5 書き出し | 配管成功。登録 export_* と全引数、予定設定、明示 force、結果表示。サーバ転送試験成功。M5 の実ファイル通し確認は統合待ち |
| GUI 専用の正本変更経路なし | 成功。実ジャーナルの actor/Op を検査。出力パスによる project.json 上書きも拒否 |
| 認証/Origin/パス | 成功。欠落・不正トークン、Origin 欠落/外部、Host、入れ子のバッチ引数、root 外を拒否 |
| 全ラスタベクタ | 618 / 618 成功、10分類すべて |
| JS ライセンス | 成功、46インストール済みパッケージとバンドル原文。npm audit も脆弱性0 |
| ビジュアル | 判断対象外。アイコン、CSS、コントラスト、動き、テーマの適用は Opus の担当 |

## 実行結果（Windows / Python 3.12 / Node 24）

| コマンド | 結果 |
|---|---|
| `uv run pytest -q --tb=short` | **768 passed, 2 skipped**, 145.43秒 |
| `uv run pytest tests/server -q --tb=short` | **11 passed** |
| `uv run ruff check` / `uv run ruff format --check` | 成功、104 Python files |
| `uv run python tools/gen_schemas.py --check` | 成功 |
| `uv run python tools/check_repository.py` | 成功 |
| `uv run python tools/check_licenses.py --extra gui` | 成功、GUI 閉包20件 |
| 同上 `--extra gui --extra mcp --include-dev` | 成功 |
| `npm test` | **625 passed**（618ラスタ + 7 store） |
| `npm run build` | TypeScript 型検査、Vite production build とも成功 |
| `npm run test:e2e` | **3 passed**（W1/W2、スキーマ新規、W4） |
| `npm run licenses` | 46件の原文と記録の一致を確認 |
| `npx playwright install chromium` | Chromium の取得・実行に成功。スキップなし |
| `uv run mypy` | **既存22ファイルの86エラー**。server の診断なし。動的 pydantic 型、既存 core/ops/MCP/CLI など。M8 外の修正は行わなかった |
| `uv run mypy src/cybersprite/server --follow-imports=silent` | 成功、2 source files |

Python の既存スキップは M5 の export_sheet/export_animation 未登録と、Windows の symlink 作成権限。Linux はローカルに環境がなく未実行（既存 I-007）。CI を Windows/Linux に設定した。

実際に `uv run cybersprite gui .gui-check/manual.csprite --port 8767 --no-browser --root .` を起動した。指定の Google Chrome 実行ファイルを `--headless=new --screenshot=...` で開き、初期画像を確認した。初期キャプチャは WS 応答前だったため、同じ Google Chrome を headless 起動し、実キャンバスと revision 1 を待った画像も取得・開いて、線、パレット、履歴、3フレームのセル状態、検証状態のデータ到達を確認した。画像は git 管理外の `.gui-check/gui-chrome.png` と `.gui-check/gui-chrome-loaded.png`。ビジュアル品質の評価はしていない。

## 判断と仕様

判断は **I-651〜I-660**。仕様変更は §14.6 の認証初期ページと Origin を付けない静的取得の説明だけ。フラグメントは HTTP に送られないことへの実装可能な補足で、データ API の保護は緩めていない。config の port 既定を0にし、空きポートの仕様に合わせた。

## 新しい Python GUI 依存の原文確認

直接依存4件と、その閉包で必要な以下の原文を site-packages の `*.dist-info/(licenses/)?LICENSE*` / COPYING から開いた。追加した実行時コード片はない。Python 台帳 `third_party/THIRD_PARTY.md` は指示どおり編集していないため、以下をオーケストレーターが反映する。

| 名前 | 版 | SPDX | 位置（dist-info 以下） |
|---|---|---|---|
| Starlette（直接） | 1.10.0 | BSD-3-Clause | licenses/LICENSE.md |
| Uvicorn（直接） | 0.54.0 | BSD-3-Clause | licenses/LICENSE.md |
| websockets（直接） | 16.0 | BSD-3-Clause | licenses/LICENSE |
| jsonschema（直接） | 4.26.0 | MIT | licenses/COPYING |
| anyio | 4.16.0 | MIT | licenses/LICENSE |
| attrs | 26.1.0 | MIT | licenses/LICENSE |
| h11 | 0.16.0 | MIT | licenses/LICENSE.txt |
| idna | 3.20 | BSD-3-Clause | licenses/LICENSE.md |
| jsonschema-specifications | 2025.9.1 | MIT | licenses/COPYING |
| referencing | 0.37.0 | MIT | licenses/COPYING |
| rpds-py | 2026.9.1 | MIT | licenses/LICENSE |
| typing-extensions | 4.16.0 | PSF-2.0 | licenses/LICENSE |
| click（既存必須依存とも共通） | 8.3.0 | BSD-3-Clause | licenses/LICENSE.txt |
| colorama（Windows） | 0.4.6 | BSD-3-Clause | licenses/LICENSE.txt |

jsonschema は新しい独自バリデータを持たず MCP の共通 PathPolicy の union 分岐をそのまま利用するために GUI extra へ明記した。残りの NumPy/pydantic/Pillow 等は既存必須依存。JS の直接依存は React/React DOM 19.2.0、Zustand 5.0.8、Vite 7.3.8、TypeScript 5.9.3、Vitest 5.1.0、Playwright 1.56.1、および固定した型パッケージ。各版・SPDX・原文ハッシュは [THIRD_PARTY_JS.md](../gui/THIRD_PARTY_JS.md)、全文は [LICENSES_JS.txt](../gui/LICENSES_JS.txt)。インストールされない他 OS の optional native は lockfile に SPDX を記録し、対象 OS の CI で原文を確認する。

## 引継ぎ

- Opus 用のコンポーネント/className 一覧は [GUI.md](GUI.md) 末尾。スクリーン構成のスタイル、テーマ適用、アイコン、グリッド等の意匠、コントラスト/フォーカス/動きの検証は TODO。
- M5/M6 統合後に W3/W5 の実アセットで受け入れを再実施する。現在の schema JSON 入力を専用ウィザードへ置き換えても、サーバの別編集経路を作らないこと。
- prefs はプロセス内のみ。設定キーの永続化・config keymap、書出し種別ごとの予定寸法の詳細表示は後続拡張。長い処理は開始/完了を通知し、段階別の進捗フックは未提供。
- 外部参照は依存パッケージの実 LICENSE と package metadata のみ。stackback の LICENSE 原文を探したが配布物になく、upstream の LICENSE URL も404だったため、その依存を含む旧 Vitest を採用しなかった。最終 Vitest 5.1.0 は stackback に依存しない。第三者の製品コード・画像・文面は参照していない。来歴ログと Python 台帳の反映はオーケストレーターへ依頼する。
