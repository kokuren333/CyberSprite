# R1-C: プラグイン拡張点の接続（2026-11-12）

対象ブランチは `fixr1-c`。R1-04 / C-R1-05 の読み込み境界と拡張点を実装した。ビジュアル判断・外部コードの参照・依存追加は行っていない。

## 1. 実装

- `plugins/`: 設定付きの公開 PluginManager と `PipelineStep` / `IndexedImage` / `Validator` 契約。`core/plugin_loader.py` / `core/plugin_settings.py` が外側層に依存しないメタデータ列挙、共通許可表、API 検査、遅延読込、再利用・直列化を担う。相対 import も repository check で監査する。
- `core/registry.py` / CLI / MCP: Op 提供者の名前解決、登録の全件検査後の一括反映、CLI からの初回解決。MCP は許可 Op 名に対応する提供者だけを読む。
- `generate/registry.py`: 共通ローダーへ移行。設定・組み込みバックエンド・遅延の能力一覧を維持。
- `pipeline/args.py` / `plugin_steps.py` / `runner.py`: grid / downsample / quantize / cleanup と複合 reconstruct の実行、型・寸法・パレット境界検査、報告・来歴、非 A 警告。target＋auto は有効な PixelOE 登録を選べる。
- `core/quality.py` / `plugins/validators.py`: 有効な品質ルールを全体検証へ注入し、水準上書き・絞込・metrics・デルタに接続。文書コピーと失敗時の保存防止を検証。
- `plugins/palettes.py` / `formats/palette_files.py`: プリセット一覧・共通読取・新規プロジェクトへの使用、重複名拒否、ライセンスの表示。
- `formats/plugin_export.py` / `ops/export_ops.py`: `export_plugin` Op と `export plugin` CLI、形式名／拡張子の解決、共通検証・path preflight、一時ファイル、戻り値スキーマ検査、実 bytes の復号照合。decode がなければ理由つき verified=false。
- SPEC §7.12 / §9.3 / §11.4 / §11.13 / §15 / 付録 C と `PLUGIN_AUTHORING.md` を整合させた。

## 2. 受け入れ基準

| 項目 | 状態・証拠 |
|---|---|
| C-R1-05 の限定読込 | テストで allowed だけを import、unrelated は未読込 |
| API 999 の拒否 | メタデータによる事前拒否と、読込対象の属性検査の両方。factory は未呼出 |
| Op 登録失敗の破棄 | 重複 Op の後に空のレジストリを確認 |
| ops / generators | 共通ローダーとテストへ接続 |
| pipeline_steps | 5 step のテスト、convert と import_image、source manifest の記録まで通過 |
| validators | 水準上書き・指標差分・新規指摘・例外時の正本不変を確認 |
| palettes | ライセンス表示、読取、新規作成への使用を確認 |
| exporters | Op 経由と直接 API、拡張子解決、自己検査、未対応の理由、失敗時の以前の出力保持を確認 |
| importers | SPEC と I-1201 で v1.x に延期。メタデータ列挙のみ |
| platforms | メタデータ群を予約。解決は R1-E1 の担当 |
| plugins list | 名前・配布名・版・群・ライセンス・状態を本体未 import で確認 |
| 全体検査 | 最終版で1436 passed / 2 skipped。Ruff・format・mypy・schema・repository checkも成功 |

## 3. 検証

- 最終ソース `e2250be`、`OPENBLAS_NUM_THREADS=1` / `OMP_NUM_THREADS=1` の `uv run pytest -q --tb=short`: **1436 passed / 2 skipped（732.69秒）**。skip は MCP の symlink パス検査と export の symlink 検査で、どちらも Windows のシンボリックリンク作成権限がないため。Linux は未実行。
- `OPENBLAS_NUM_THREADS=1` / `OMP_NUM_THREADS=1` を設定した `uv run pytest tests/test_plugins_r1.py tests/test_repository_imports.py tests/unit/test_transactions.py tests/generate/test_generation.py -q --tb=short`: **61 passed（124.51秒）**。プラグイン24件、依存監査1件、不変条件・トランザクション15件、生成21件を含む。固定画素ベクタ、診断用格子、保護番号、規則 ID と builtin 提供者の衝突、実際に読み込んだ提供者の disabled 検査も確認した。
- 先行の通常設定全体試験は **1431 passed / 1 failed / 2 skipped（3480.70秒）**。失敗は `test_plugin_invariant_error_rollback` が E_INVARIANT を期待したのに E_PLUGIN を返した回帰。I-1212 の修正後、不変条件・トランザクション15件、関連61件、最終全体試験で成功した。
- 低層処理分離後の全体試験は **1435 passed / 1 failed / 2 skipped（910.59秒）**。設定場所の試験が参照する既存の `config.sys` を外していたためで、同じ sys モジュールの公開参照を保持して修正した。設定試験15件は単独で成功（2.07秒）。単独実行でも生成実行パッケージの mock が契約の import を妨げないよう、共通契約の初期化を mock より先に明示した。
- 初回の `uv run pytest tests/test_plugins_r1.py tests/generate/test_generation.py -q --tb=short`: 34 passed / 4 failed（419.42秒）。失敗は既存の外部コマンド用 Python 子プロセスの30秒期限超過と、残った stderr.log の Windows 共有違反。生成実行・期限処理は本工程で変更していない。最終の全体試験とは別の途中結果である。
- `uv run ruff check .` / `uv run ruff format --check .`: 成功。
- `uv run mypy src/cybersprite/core src/cybersprite/ops`: 成功（38ファイル）。
- `uv run python tools/gen_schemas.py --check` / `uv run python tools/check_repository.py`: 成功。
- 実 CLI の `uv run cybersprite plugins list` と `uv run cybersprite export plugin --help` を実行し、メタデータ封筒と新規 Op の引数表示を確認した。
- `uv run python tests/generate/fake_command.py` を実行し、`build/r1-c-verified/` の2枚の PNG を実 bytes から復号して8×6 RGBA・不透明アルファ・白い内部領域の画素値を確認した。
- ゴールデンの変更・更新は0件。スキーマ生成器の実行による正本スキーマの差分も0件。

## 4. Design forks decided

| 判断 | 選択・理由 | 根拠 |
|---|---|---|
| I-1201 | importers を v1.x へ延期。入力予算・ラスター／構造形式の配置と来歴の共通契約が未確定であり、未接続を対応済みとしない | Fable R1-04、今回の明示的な延期許可 |
| I-1202 / I-1203 | 設定許可に加えて提供者の名前規約で Op を逆引きし、最長接頭辞の提供者だけを読む。disabled 優先 | Codex C-R1-05。import 前に任意 factory の内容を調べることはできないため |
| I-1204 | reconstruct は grid＋downsample を置換し、quantize は後段の一度だけ。step.method を推奨 | 今回の R1-D 接続要求、SPEC の一度だけの量子化。Fable は複合 step の細部を指定していない |
| I-1205 | uint8 RGBA／IndexedImage の境界と level_a 宣言を使う | SPEC §1.2 / §6.6 / §15、今回の R1-C 契約要求 |
| I-1206 / I-1207 | core への注入可能な品質ルール、共通 palette reader への接続 | Fable R1-04。後続の機種規則・色表の前提を用意する |
| I-1208 | 単一ファイル exporter と全フレーム RGBA の自己検査。decode がない形式は false と理由 | Fable R1-04 / §3.1.10 H-05、SPEC §15.3 |
| I-1209 | platforms をメタデータ群だけ予約。API 表示は任意の配布ヘッダーを使い、未宣言は unchecked | Fable §3.1.5 H-01。コードを実行しない一覧で runtime 属性を互換と断定しない |
| I-1210 | validator の組み込み規則 ID も予約し、衝突を E_PLUGIN で破棄 | Fable R1-04、SPEC §13.4。rule ID を使う検証集約・デルタの同一性を保つ |
| I-1211 | 公開 Manager は plugins、許可型・場所・metadata の低層処理は core 内で共有。相対 import も監査 | SPEC §4.2。core から外側の層への依存を作らず、単独 Registry でも同じ許可表を使う |
| I-1212 | 手動登録 Op を provider 文字列だけで entry point とみなさず、実読込済み提供者に許可検査を適用 | 全体試験で見つかった不変条件 rollback の回帰を修正。MCP の公開許可と entry point の設定許可は維持 |
| I-1213 | Op の entry point 名 builtin を import 前に拒否し、metadata で incompatible と表示 | Codex C-R1-05 / SPEC §10.1.2。外部パッケージによる組み込み提供者の偽装と許可外 Op 公開を防ぐ |

判断記録は **I-1201〜I-1213**。SPEC の変更は上記の契約・延期・警告コード・規則 ID の一意性・依存方向・提供者の区別と、その関連表の整合だけ。自動格子未検出時の診断用 none 格子は既存の I-467 に従ってプラグイン経路にも保持した。

## 5. Deferred / not done

- importer の実行は v1.x。platform の解決と実機 exporter、R1-D の実コンバータは担当工程で実装する。
- 汎用 exporter は単一ファイルのみ。複数の palette/map ファイルや、全フレーム RGBA 以外の比較契約は本工程には含めていない。
- 一覧の runtime API は import せずには確定できない。配布ヘッダーがなければ api=unchecked、初回使用で必ず検査する。
- 拡張子だけで exporter を探す場合は有効な exporter 群の能力を読む。名前を指定すればその1件だけを読む。
- 第三者 Python コードの任意の副作用を取り消すサンドボックスは作っていない。取り消すのは登録・トランザクション・一時出力の範囲。
- Linux は利用できず未実行。デザイン判断・ビジュアル TODO はない。

## 6. Before/after numbers / 依存 / 参照

性能改善は本工程の対象ではなく、前後性能の数値・改善率は主張しない。新規依存・コード片・外部アセットの追加は0件で、新たなライセンス原文確認の対象はない。ロック済みの既存環境を uv で同期した。

途中の期限超過の切分けで測った1プロセスでは、ops の import が44.748秒、registry() の構築が4.451秒だった。その後の `metadata.entry_points(group="cybersprite.ops")` の3回は0.043 / 0.019 / 0.084秒。前後比較でもレビューの性能 fixture でもなく、起動待ちとメタデータ読込を分けた診断値だけである。

参照したのは、このリポジトリの AGENTS、SPEC、DECISIONS、IMPLEMENTATION_PROGRESS、src/README、REVIEW_1、CODEX_REVIEW_R1 と既存実装・テスト。外部資料・他製品のコードや文言は参照していない。
