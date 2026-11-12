# IMPLEMENTATION_PROGRESS — 実装フェーズの進捗

オーケストレーター: Claude Opus 5.5（effort 高）。仕様の正本は `docs/SPEC.md`、判断は `docs/DECISIONS.md`。
新しい記録を下に足していく（追記式）。

## FIX-5: トランザクション／GUI遅延とCLI・再取り込み（2026-11-12）

- `fix5-perf` でフレーム解析の内容SHA-256キャッシュ、画素使用数・行検査・トリム・正準行JSONの上限付き再利用、検証済み正準bytesのsnapshot共有、gzip level=1、複製1回とその内部での正規化を実装した。汎用copy-on-writeは任意プラグインの可変編集を隔離するため見送った。
- GUIは実bytes一致時だけ解析モデルを再利用し、検証済みRGBAを差分と既定frame配信で共有する。同サイズ・同mtimeの外部変更、範囲描画、無効フレーム、読込失敗時の既存エラーコードを検査した。
- `op` のカンマ区切り配列を生成オプションと同じ変換器へ接続した。未作成プロジェクトへのimport自動作成とundo後の再取り込みを文書化し、不透明色のない既存パレットでは明示modeがなければextractを選ぶ。FIX-4領域は `ops/ingest.py` のこの最小変更だけで、`pipeline/` は未編集。
- `uv run pytest -q --tb=short`: **1370 passed, 2 skipped（263.52秒）**。skipは既存のWindowsシンボリックリンク権限2件。GUI読込エラー互換性の最後の変更は `uv run pytest tests/server/test_fix5_cache.py tests/server/test_server.py -q --tb=short` の **14 passed** でも追試した。
- 固定シード3本・実Op195回のキャッシュあり／なし報告JSON・デルタ比較、正準JSONの従来整形との一致、入力複製の独立性、gzip展開bytes・mtime・OS、リンク所有者変更時のz_index維持を確認した。既存ゴールデンは全件成功、更新・再生成は0件。
- Ruff check / format、core/opsのmypy（36ファイル）、7ファイルのstrict、schema drift、repository check、既存Python依存監査（mcp/gui込み）・JS原文監査が成功。`npm test` は **627 passed** とコントラスト86組成功、`npm run build` 成功、`npm run test:e2e` は **3 passed**。
- `tools/profile_transactions.py` と `python -X importtime` で前後を計測した。`tools.bench` の各3回の最終中央値はtransaction **205.148 ms**、GUI往復 **92.965 ms**（変更直前950.395 / 236.209 ms）。150 / 50 ms目標は未達。観測最小184.519 / 79.732 msと、残る全正本の読込・構造検査・JSON生成・同期保存の費用を [PERFORMANCE.md](PERFORMANCE.md) と [KNOWN_ISSUES.md](KNOWN_ISSUES.md) に記録した。Linuxとブラウザpointer-upからの表示完了時間は未計測。
- 実CLI子プロセス10呼出しでカンマ指定、作成不要import、undo、再import、validate、stored PNG exportを実行し、validation_ok/verified=trueと書出しファイルの復号画素一致を確認した。全5フレームの一覧と実PNGも確認した。警告・エラーは0、未使用色と空の初期レイヤーのinfo指摘は工学用fixtureの意図どおりとして保持した。成果物はgit管理外の `build/fix5-verified/`。
- 判断 **I-881〜I-887**。仕様変更は§10.12／§11.11の自動作成・undo後再取り込みの補足だけ。新規依存・外部参照・ビジュアル判断なし。mainへの統合はオーケストレーターが行う。

## 現在地（2026-11-12 12:55 JST）— **M0〜M10 完了。レビュー依頼 1 回目を作成済み**

| マイルストーン | 状態 | 備考 |
|---|---|---|
| M0 準備と実機参照 | **完了** | P-01〜P-11 実施。P-11 は実機 Aseprite と全ピクセル一致 |
| M1 コア基盤 | **完了** | |
| M2 Op とトランザクション | **完了** | |
| M3 CLI | **完了** | |
| M4 MCP サーバ | **完了** | Claude Code / Codex から実接続 |
| M5 形式 | **完了** | |
| M6 変換パイプライン | **完了**（生成画像コーパス (d) は未作成） | 整数倍 255/255、非整数倍の自動検出 62/68（FIX-4） |
| M7 タイルマップ | **完了** | |
| M8 GUI | **完了** | テーマ案 C、アイコン 41 個は `.csprite` から |
| M9 生成バックエンド | **完了**（実 GPU は未検証） | |
| M10 仕上げ | **完了** | 新しい Claude Code セッションが AGENTS.md と skills/ だけでシナリオ 1 を完走（e2e-06） |
| 修正 INT-1、FIX-2〜FIX-6 | **完了** | e2e 制作テストの指摘への対応 |

**最終の検査結果（main、Windows 11 / Python 3.12.10）**: pytest 1411 passed / 2 skipped（シンボリックリンク作成権限による skip）、GUI vitest 627 passed、コントラスト検査 86 組合格、Ruff / format / スキーマ差分 / クリーンルーム / ライセンス（実行時・開発・mcp・gui extra）すべて合格。通しシナリオ 1〜5 合格。**Linux は未実行**（I-007）。

## 次セッションへの引き継ぎ

**完了範囲**: 仕様 §16.4 の M0〜M10 すべて。作業ツリーに未コミットの変更はない（`_handoff/`・`_private/` は git 管理外）。

**次の作業（優先順）**
1. **GitHub リポジトリの作成と push**（発注者の操作が要る。`docs/UPSTREAM_REPORT.md` §3 の手順 A か B）。push すると CI（Windows / Ubuntu × Python 3.12 / 3.13）が初めて走り、**Linux での決定性（ゴールデンのバイト一致）が初めて検証される**。落ちたら最優先で直す。
2. **レビューループ**（§16.5）: `docs/REVIEW_REQUEST_1.md` を Fable 5.2 に渡し、`docs/REVIEW_1.md` を受けて `docs/REVIEW_LOG.md` に対応を書く。最大 3 回。
3. `docs/KNOWN_ISSUES.md` の残件: 性能 2 項目（1 トランザクション 205 ms / 目標 150 ms、GUI 往復 93 ms / 目標 50 ms）、mypy 47 件、GUI の専用メニュー、生成画像コーパス (d) と実 GPU での生成、M0 の未撮影画面と発注者のよく使うキー。

**注意点**
- サブエージェントの起動: Codex は `_handoff/codex/run_codex.sh <TASK> <worktree>`（共通ブリーフ `_handoff/codex/COMMON.md` ＋タスク別の指示を連結し、`codex exec -m gpt-6.1-sol -c model_reasoning_effort=high` で実行）。1 タスク 1 worktree・1 ブランチで、オーケストレーターが検証してから `main` に統合した。`docs/DECISIONS.md` と本ファイルの衝突は行の和集合で解消できる（`_handoff/tools/union_merge.py`）。
- Opus のサブエージェント（Agent ツール）は、この環境では `REPORT.md` という名前のファイルを書けないことがある。その場合は最終メッセージで本文を受け取り、オーケストレーターが保存した。
- CLI の書き出し先はカレントディレクトリの配下に限られる（I-602）。プロジェクトの中から実行すると外へ書けない。
- 全体テストは約 5 分かかる。高負荷時に `uv run` の再ビルド通知が stderr に混ざる問題は FIX-6 で修正済み。

## 体制とサブエージェントの起動方法

| 役割 | モデル | 起動方法 |
|---|---|---|
| 非ビジュアルの工学（実装・テスト） | Codex（GPT）6.1 sol / effort 高 | `codex exec -m gpt-6.1-sol -c model_reasoning_effort=high`。指示は共通ブリーフ＋マイルストーン別の指示（`_handoff/codex/`、git 管理外）。各マイルストーンを専用の git worktree とブランチで実行し、オーケストレーターが検証してから `main` に統合する |
| デザイン・ビジュアル、e2e 制作テスト | Claude Opus 5.5 / effort 中 | Agent ツール（model: opus、effort: medium） |

## M0: 準備と実機参照 — 完了（2026-11-12）

| 作業 | 結果 |
|---|---|
| (1) ライセンスのチェックリスト L-01〜L-13 | L-01・L-03・L-04・L-07・L-08・L-09・L-11・L-13 を実施。L-02 は LICENSE のみ確認（依存は M6）。L-05・L-06 は M8、L-10・L-12 は M9 で実施（`third_party/THIRD_PARTY.md` §3） |
| (2) Aseprite 実機参照 | v1.3.18.6（Steam 版）を GUI とバッチモードで参照。GUI は代表的な約 20 画面を撮影（`_private/aseprite_ref/shots/`、git 管理外）。挙動確認 P-01〜P-10 は自作ファイルで全件実施。棚卸しメモ `docs/reference/ASEPRITE_INVENTORY.md` |
| (3) §7 の対応表 | 棚卸しで見つかった表にない機能の区分を決めた（ASEPRITE_INVENTORY §4、I-005）。表への行の追加は M8 着手時 |
| (4) 挙動確認の仕様への反映 | P-01・P-03・P-06・P-07・P-08 は仮定どおり。P-02・P-05・P-09 は既知の差として §5.9.3 に追記（I-002）。P-04 で付録 D.2 を確定（I-003）。P-10 は規則を維持し差を注記（I-004）。P-11 は M5 後 |
| (5) 名称の確認 | PyPI に `cybersprite` はない。GitHub に活動の目立たない同名リポジトリが 2 件。商標は簡易確認のみ（THIRD_PARTY §4） |
| (6) GitHub リポジトリ | 発注者の指示により対象外（`gh` 未導入。push は試みない） |

**M0 の未了（後続マイルストーンで実施）**: GUI の未撮影画面（04、13〜23、26〜32、39〜41、44〜46）、発注者がよく使うキーの聞き取り、P-11（M5 後）。

## 詰まり・注意

- **Linux 環境がない**（WSL も Docker もない）。CI の設定は Windows / Linux の両方を書くが、Linux での実行は GitHub リポジトリ作成後になる（I-007）。それまで「両 OS で通る」という完了条件は Windows のみで判定し、ここに明記する。

## M2: Op とトランザクション — Windows 検証完了（2026-11-12）

- 59 個の登録済み Op、履歴と原子的保存、予行・再送・ロック、22 個の品質規則と検証デルタ、プレビュー／差分、CLI の共通入口を実装した。
- `uv run pytest -q --tb=short`: **487 passed**。`uv run ruff check`、`uv run ruff format --check`、`uv run python tools/gen_schemas.py --check`、`uv run python tools/check_repository.py` は全て成功。
- CLI で新規作成 → 矩形 → 塗りつぶし → 直線 → undo → redo → validate → preview → render を実行。revision 5、検証 error/warning 0、書出し `validation_ok` / `verified` とも true。プレビュー PNG と最終 PNG 自体を開いて確認した。
- `frame_remapping`、`transactions`、`raster_ops` のゴールデンは専用更新ツールで生成し、正本・封筒・PNG を確認した。
- 判断 I-201〜I-210。追加依存・外部参照なし。距離とパレット並べ替えの暫定実装は M6、cleanup は M6、PNG パレット読込は M5、タイルマップの全体変形とタイル置換は M7。機能用プレビューの色と定規は Opus の確認対象。
- 詳細と CLI の実行内容は [M2_IMPLEMENTATION_REPORT.md](M2_IMPLEMENTATION_REPORT.md)。Linux は上記 I-007 のとおり未実行。

## e2e 制作テスト

| # | 題材 | 日付 | 実施 | 結果 | 記録 |
|---|---|---|---|---|---|
| 01 | キャラクター（32×32、2 フレームのまばたき、タグ） | 2026-11-12 | Opus 5.5 / 中 | validate ok（警告 0、情報 3 は個別に判断）。書き出し Op が未実装のため `render` で PNG を出力。使い心地 4/5 | `e2e-tests/01-character/REPORT.md` |
| 02 | UI 素材（GUI アイコン 40 個、原本 `assets/ui/icons/*.csprite`） | 2026-11-12 | Opus 5.5 / 中 | 全件 validate ok。`render` で ×1 / ×4 を出力し、設計データと全ピクセル一致。使い心地 4/5 | `e2e-tests/02-ui-icons/REPORT.md` |
| 03 | アニメーション（32×32 歩行 8 フレーム＋待機 2 フレーム、リンクセル、タグ 2 個） | 2026-11-12 | Opus 5.5 / 中 | validate ok（警告 0）。GIF ×2、APNG、タグ別シート（json-hash）、`.aseprite` を書き出し、全ファイルをフレーム単位で照合して一致。使い心地 4/5（減点はプレビュー周り） | `e2e-tests/03-walk-animation/REPORT.md` |
| 04 | タイルセット（16×16 タイル 16 枚、反転で縁と角を再利用、12×8 マップ） | 2026-11-12 | Opus 5.5 / 中 | validate ok。マップ・タイルセット・`.aseprite` を書き出し、自前の反転合成と全ピクセル一致。`tileset_from_layer` の格子原点のずれ（不具合）を発見。使い心地 4/5 | `e2e-tests/04-tileset/REPORT.md` |
| 05 | 取り込み変換（生成画像風に劣化させた 347px の入力 → 32×32 スライム、手仕上げ） | 2026-11-12 | Opus 5.5 / 中 | 最終 validate ok、正解と 1021/1024 一致。ただし `ai` の既定設定は非整数倍の拡大で格子を誤り、関門が通してしまう重大な問題を発見。使い心地 3/5 | `e2e-tests/05-import-convert/REPORT.md` |

### e2e で見つかった問題（未対応のもの）

| 出所 | 問題 | 担当 |
|---|---|---|
| e2e-01 #5（**INT-1 で修正済み**） | `ops describe` の説明が定型文で、引数（例: `draw_rows` の `format: sym`）の意味が分からない | M3 後の修正 |
| e2e-01 #6（**INT-1 で修正済み**） | `op` に `--label` がない（単発 Op の履歴ラベルが空） | M3 後の修正 |
| e2e-01 #7（**INT-1 で修正済み**） | 図形系 Op（`ellipse` など）の result に `pixels_written` がない | M3 後の修正 |
| e2e-01 #8（**INT-1 で修正済み**） | undo / redo の結果にプレビューがない | M3 後の修正 |
| e2e-01 #10（**INT-1 で修正済み**） | Q-PIX-02 の `where.layer` が null（どのレイヤーか分からない） | M3 後の修正 |
| e2e-02 #2 | `new --palette <.gpl>` で色名が捨てられる | M7 で修正・load_palette置換/追記も回帰確認 |
| e2e-02 #3 | 名前だけの `set_palette` でも `changed.frames` にフレームが出る | M7 で全OpのRGBA差に統一して修正 |
| e2e-02 #6 | `docs/CLI.md` に `pixels --rect` の既定範囲の説明がない | M7 でトリム矩形・全キャンバス指定とcwd出力制約を追記 |
| e2e-03 #1〜7 | プレビューの frames 指定・横並べ・背景色・オニオンスキン、`info` のリンク表示、書き出し結果のデータファイルの項目、細かい点 | FIX-2（Codex、作業中） |
| e2e-04 #1〜9 | `tileset_from_layer` の格子原点、タイルセットの削除・プレビュー、`changed` の表し方、タイルセット JSON の項目ほか | FIX-3（Codex、作業中） |
| e2e-05 P1〜P9 | 非整数倍の格子検出、関門のすり抜け、背景の自動判定、色指定、パレット抽出、undo と来歴ほか | FIX-4（Codex、作業中） |
| e2e-01 #1〜4、#9 | 書き出し、`preview` / `pixels` / `validate` のオプション、`docs/CLI.md` | M3 / M5（作業中） |

## M6: 変換パイプライン — Windows 検証完了（2026-11-12）

- 来歴マニフェスト、取り込み・読み取り3 Op、共通cleanup、6ステップ・報告・段階PNG・関門、配置と履歴の原子的保存、M3指定の cli_api を実装。CLI パッケージは未変更。
- Oklab をコアへ集約し、距離とパレット並べ替えの暫定実装を置換。ゴールデンは専用更新器で3ケース9ファイルを更新し、JSON・ハッシュ・PNGを確認した。
- 実画像471件を較正版1で測定。17作品の倍率2〜16は auto で **255/255、100% RGBA完全一致**。JPEG・非整数補間・非ドット・誤格子も記録。負例95%拒否を満たす区間がないため、仕様どおり正解側の全合格を優先した。
- 全体 `uv run pytest -q --tb=short`: **924 passed、125.00秒**。最終のGIF表示時間修正後は取り込み境界・トランザクションの **23 passed** も確認。Ruff、スキーマ、コア依存境界、依存ライセンス監査が成功。mypy は既存68件（分岐元は70件）が残る。
- 手動で等倍・疎な4倍・JPEG q75を取り込み、全段階と配置PNGを開き、ファイルを再復号して画素一致を確認した。1024×1024変換は805/1133/656 msで、保存と再復号を含め5秒目標を達成。
- 判断 I-463〜I-473。仕様変更は §11.3.2 の整数境界補正、§11.8 の容量・凍結のoverride制限。追加依存なし。既存PillowのLICENSE原文確認とMIT-CMU識別子の監査修正を実施し、台帳は未編集。
- Linux、生成(d)、M4のJSONL e2e、M5のexport_imageとのシナリオ接続は統合後の確認事項。`tests/e2e/scenarios/` はリベース後もないため未作成。詳細は [M6_IMPLEMENTATION_REPORT.md](M6_IMPLEMENTATION_REPORT.md)、較正は [tests/pipeline/CALIBRATION.md](../tests/pipeline/CALIBRATION.md)、性能は [PERFORMANCE.md](PERFORMANCE.md)。


## INT-1: M3/M5/M6 と MCP の統合（2026-11-12）

- `int-m356` 上で M6 の5競合を解消し、`f56ed83` でマージ。共通 Source API、両側の登録、明示 actor 優先を保持した。
- `41a22da` で CLI/MCP の export_policy、M6 cli_api と source 再試行、パス制限と契約、制作試験01の説明・ラベル・レイヤー指摘を統合した。既存の描画件数・undo/redoプレビュー・CLIオプションも回帰確認。
- 最終 `uv run pytest -q --tb=short`: **1150 passed, 2 skipped、214.96秒**。スキップは Windows でシンボリックリンクを作る権限がない既存2件。
- Ruff check/format、schema drift、repository check、`check_licenses.py --include-dev --extra mcp`（既存 I-012、41配布パッケージ）、diff check は成功。mypy は統合直後106件から **78件、新規0件**へ減少。
- MCP JSONL シナリオ1・2を実 SDK Client の in-process/stdio で通し、実シート/GIF/PNGを復号照合。シナリオ2は非ドットの自作コーパスによる代用で、生成(d)は M9 待ち。
- CLI 14呼出しで new16×16→draw→4frames→walk→validate→sheet(json-hash)/GIF/APNG/.aseprite→再取り込み比較、および corpus PNG exact import/export。正本（revision除外）と画素が一致し、全 export の validation_ok/verified=true。最終コミット後の再実行先は `build/int-acceptance-final/`。
- シナリオの実書出しと全フレームを画像で確認した。意匠判断なし。unknown 来歴の Q-SRC-02 は仕様どおりの警告として保持し、理由を報告に記録した。
- 判断 I-601〜I-608。INT の仕様変更は §9.4.1 の op --label だけ。新規依存・外部参照なし。Linux は I-007 のとおり CI 待ち。main への再統合はオーケストレーターが行う。
- 詳細: [INT1_IMPLEMENTATION_REPORT.md](INT1_IMPLEMENTATION_REPORT.md)。
## M8-S: GUI サーバと接続基盤 — Windows 検証完了

- `m8-server` に loopback サーバ、フラグメント認証、MCP 共通パス制限、全 RPC、250 ms 外部監視、actor=gui の Op 接続、RGBA 配信、React/TS/Zustand の無装飾仮画面を実装した。画面のビジュアル判断は行っていない。
- `uv run pytest -q --tb=short`: **768 passed, 2 skipped**。Ruff、スキーマ、クリーンルーム、Python GUI ライセンス検査は成功。JS は **625 passed**（全618ラスタベクタを含む）、Playwright は **3 passed**、build と46件の JS 原文検査に成功。
- 実 CLI GUI を起動し、Google Chrome headless の初期スクリーンショットと、実キャンバス/revision を待ったスクリーンショットを開いた。判断 I-651〜I-660。仕様 §14.6 に認証初期ページの説明を補足した。
- M5/M6 未統合のため W3/W5 の実ファイル通し確認は統合後。Linux は I-007 により CI 設定のみ。全体 mypy は既存22ファイルの86エラーで、server の診断はない。Opus の restyle と Python 台帳/来歴ログへの反映は後続作業。
- 詳細、依存原文、受け入れ状況は [M8_SERVER_REPORT.md](M8_SERVER_REPORT.md)、起動方法と UI className 一覧は [GUI.md](GUI.md)。

## M7: タイルマップ — Windows 検証完了（2026-11-12）

- §10.10 の7 Op と、作業指示で必要な move_tiles を実装し、全体を77 Opにした。格子原点・リンク共有・空タイル不変・全参照再番号付け・反転一致付き画像変換を実装し、全体変形／色置換のM2スタブを除去した。
- M5の配置と自己検査をタイル書出しへ再利用し、4096フレーム上限をタイル数へ適用していた経路を1フレームの一時描画に修正した。既存.asepriteアダプタの複数セット・8フラグ・base_index・match_flips・リンク・user_data・非0透明番号を12件の往復試験で保証した。
- 正方形・非正方形の8反転、共有修正と再番号付け、画像変換の4ケース・95期待ファイルを唯一の更新器で生成し、手書き期待配列・PNG・正本・検証デルタを確認した。ハッシュシード17/319で全95ファイルが一致。既存ゴールデンは空の0差分フレームを2応答から除いた箇所だけを変更した。
- `uv run pytest -q --tb=short`: **1244 passed, 2 skipped、256.17秒**。スキップは既存のWindowsシンボリックリンク権限2件。最終の型注釈整理後も関連 **122 passed**。Ruff check/format・スキーマ・repository・ライセンス監査・diff checkは成功。mypyは**既存78件、新規0件**。
- MCPシナリオ3は実Clientのin-process/stdio両方で成功し、正本と実出力PNGのハッシュを固定した。CLIは14呼出しで作成→8反転配置→リンク→共有修正→検証→PNG/tileset/.aseprite出力と実ファイル再復号を完走した。全exportでvalidation_ok/verified=true、警告0、プレビューと実出力PNGを開いて確認した。最終コミット後の再実行先は `build/m7-review-final/`。
- e2e-02 #2/#3/#6 を修正。判断I-501〜I-511。仕様の補足はmatch_flipsのv1変換利用、add_tileset.if_exists、move_tiles、changed.framesのRGBA差限定。追加依存・外部参照・意匠判断なし。P-01の反転順は仕様に一致済みなのでKNOWN_ISSUESの追記は不要。
- LinuxはI-007のとおりCI待ち。mainへの統合とオーケストレーターによる独立実機確認は未実施。詳細は [M7_IMPLEMENTATION_REPORT.md](M7_IMPLEMENTATION_REPORT.md)。
## M9 生成バックエンド（2026-11-12、Codex）

実装と Windows での検証を完了。配布用 Diffusers extra の依存追加は I-708 の監査保留があるため、M9 全体を完了扱いにはしない。

- `generate/` にバックエンド契約、設定と遅延プラグイン登録、command、Diffusers API 接続、モデルとアダプタの個別承諾、実体ハッシュ照合を実装した。`ops/generation.py` が list_generators/query と generate_image/ingest/G を登録し、全71 Op。
- 生成は source の原画像と来歴だけを保存し、正本・リビジョンを変更しない。source の冪等性キーで再実行を抑止し、既存 import_image で配置する。設定の分離は CYBERSPRITE_CONFIG_DIR（I-702）。
- `uv run --extra mcp --extra gui pytest -q`: **1180 passed、2 skipped**（298.94秒）。既存2件のスキップは Windows のシンボリックリンク作成権限。最終変更後の `uv run --extra mcp --extra gui pytest tests/generate -q`: **21 passed**（14.65秒）。
- `uv run --extra mcp --extra gui ruff check .`、`tools/check_repository.py`、`tools/check_licenses.py`、`git diff --check` が成功。新しい依存は追加しておらず、第三者台帳は編集していない。
- `uv build --wheel --out-dir .venv/m9-dist` の wheel 全105エントリを確認。重み拡張子・32 MiB 以上のファイルなし。追跡ファイルと package 配下の走査テストも追加した。
- `.venv/m9-smoke/settings/config.toml` を設定先にして、実 CLI の gen backends、gen run（偽コマンド、承諾フラグ、seed=42、冪等性キー）、import image --source SRC1 --preset exact、validate、preview、export image を実行。検証デルタは errors=0/warnings=0、最終 validate も error=0/warning=0。初期空レイヤーと透明番号未使用の info 2件は試験の構成どおり。
- 書き出し結果は validation_ok=true / verified=true。プレビューと最終PNGそのものを開いて確認し、復号した8×6の黒枠・白い内側の画素も検査した。最終PNG SHA-256 は `aca375c26bb02658ae0b4150357250b88a98cc242154c87f7f67e975dfbb503a`。試験出力は git 管理外の `.venv/m9-smoke/` に保持する。
- 仕様変更は §12.5 の command.model 設定と例の追記のみ。判断 I-701〜I-709。エージェント側生成・利用方法・正確な L-10/L-12 の確認先候補・残る依存監査は `docs/GENERATION.md` に記載。
- 未完: Diffusers extra の実依存追加と推移依存監査（regex の CNRI Python 1.6 表記が今回の許可リスト外）、GPU実機、Linux実行、L-10/L-12 のモデルカード・利用規約の確認。Torch/Diffusers の巨大wheel・重みは導入していない。ビジュアル判断を要する変更なし。M7 と gui/ は変更していない。

## FIX-2: アニメーション制作の使い勝手 — Windows検証完了（2026-11-12）

- `fix2-preview` でe2e-03 §5の全7指摘を修正した。共通フレーム指定、strip/grid、1024px上限、任意RGB背景、約50%の前後幽像と `onion.loop_tag`、infoのリンク元・リンク組、`changed.link_groups`、画像/データのexport結果分離、プレースホルダhelp、表示色、透明パレット警告を実装した。`generate/` と `gui/` は変更していない。
- 全体 `uv run pytest -q --tb=short`: **1300 passed / 2 skipped、253.54秒**。スキップは既存のWindowsシンボリックリンク権限の2件。Ruff check/format、schema drift、repository、ライセンス監査（dev/mcp/gui）、diff checkは成功。任意のmypyは既存記録と同じ78件が残る。
- 実CLIで原本runner.cspriteを一時ディレクトリへコピーし、tag:walkのstrip、全10フレームのgrid、フレーム0の前7/次1のonion、パレット外の白背景を生成した。実PNGを再復号して開き、原本とコピーの正本のバイト不変を確認した。validateはerror 0、warning 0、info 10。再現スクリプトは `tools/fix2_acceptance.py`、実画像と記録は `build/fix2-review/`。
- ゴールデンは唯一の更新器で生成し、応答JSONの新しい契約・透明パレット警告と新規パレット出力を確認した。既存画像・正本・画素ハッシュの変更なし。判断I-751〜I-761。仕様は§5.8.1、§6.7.1、§8.8、§10.2.2、§10.3.1、§10.4、付録Cを補足した。追加依存・外部参照なし。
- 実装コミットは `1547911` と `70fe2a9`。LinuxはI-007によりCI待ち、mainへの統合と表示の最終的な見やすさの評価はオーケストレーターの作業。極端に多数の合成では番号の判読に小さい範囲が必要。詳細は [FIX2_IMPLEMENTATION_REPORT.md](FIX2_IMPLEMENTATION_REPORT.md)。

## FIX-3: タイル制作ワークフロー — Windows検証完了（2026-11-12）

- `fix3-tiles` でe2e-04 §5のタイル関連指摘を修正した。変換格子のcanvas.grid原点と明示origin、delete_tileset（C・破壊的・missing_ok・E_IN_USE）、番号付きタイル一覧プレビューと編集結果表示、共有参照を含むchanged.cels/layers/tilesets、tiles/tiles_total、タイル書出しメタデータ、変形順の説明、get_tilesのCLI文書、25%画素格子、空0のcolors_used除外を実装した。
- 全体 `uv run pytest -q --tb=short`: **1335 passed / 2 skipped、481.01秒**。スキップは既存Windowsシンボリックリンク権限2件。Ruff check/format、schema drift、repository、ライセンス監査（dev/mcp/gui）、diff checkは成功。CLI/MCPは共通レジストリから生成し、実SDKでも一覧表示・参照中削除拒否・削除・missing_okを検証した。
- 唯一のゴールデン更新器で24期待ファイルを更新し、全差分を確認した。応答と書出しJSON、変換原点に伴う正本だけが変わり、既存PNG・画素配列・画素ハッシュの変更はない。
- `tools/fix3_acceptance.py` が原本meadowを一時コピーし、CLI18呼出しで一覧・×4格子・透明上端レイヤーの反転統合・タイル追加・delete_tileset・PNG/タイルPNG/JSON書出しを確認した。変換前後のRGBAとプレビューは完全一致し、原本の正本バイトは不変。最終error 0 / warning 0 / info 1（原本のQ-PIX-02を保持）、全exportでvalidation_ok/verified=true。プレビューと実書出しPNGを開いて確認した。最終コミット後の再実行先は `build/fix3-review-final/`。
- 判断I-781〜I-787。SPECは§6.7.1、§8.7、§10.1.2、§10.3.1、§10.4、§10.10、§13.4、付録Cを補足した。追加依存・外部参照なし。LinuxはI-007によりCI待ち、mainへの統合と表示の最終的な見やすさの評価はオーケストレーターへ引き継ぐ。詳細は [FIX3_IMPLEMENTATION_REPORT.md](FIX3_IMPLEMENTATION_REPORT.md)。
## M10: 仕上げの工学部分 — Windows検証完了（2026-11-12）

- `m10-finish`でGUI付きwheel/sdistのビルドとpayload/原文照合、新規の外部venvでのCLI/MCP/GUI実行、全6目標のbench、E2Eシナリオ4/5、NOTICEとJS原文の配布、README/KNOWN_ISSUESを整備した。skills/examplesとFIX-3のtile opsは未編集。
- 全体Python **1339 passed / 2 skipped**（413.44秒）、シナリオ1〜5 **10 passed**（skipなし）、GUI **627 passed** / コントラスト86組 / Playwright **3 passed**。Ruff・schema・repository・依存監査も成功。2 skipは既存Windowsシンボリックリンク権限。
- core/opsの型診断41件を0へ減らし、CI必須化（36ファイル）。7ファイルはstrictでも0。全srcには47件/17ファイルが残り、既知の不足へ記録した。
- 初回の重い構造検証・クラスタ処理を高速化し、全既存ゴールデンの出力を保持した。最終中央値はCLI189.549ms、transaction1654.159ms、render19.751ms、validate508.282ms、GUI212.382ms、pipeline464.683ms。transaction/GUIは未達で原因と対策をPERFORMANCEに記録。
- wheelにはGUI index/JS/CSS・41アイコン・全規範データとNOTICE/ライセンス本文を収録。新規venvでmodule/CLIのMCP両入口×2025-06-18/2026-07-28の77ツール、認証付きGUIの実bytes配信を確認した。
- 判断I-801〜I-807、SPEC変更・新規依存なし。LinuxはI-007により未実行。新規エージェント/作例/最大3回のレビューとmain統合はオーケストレーターの工程。詳細は [M10_IMPLEMENTATION_REPORT.md](M10_IMPLEMENTATION_REPORT.md)。

## FIX-6: マニュアル作成時の整合性修正（2026-11-12）

- `fix6-small` で独自シートの `items[].layer/tag/slice` を名前に統一し、対応する `_id` と `tags[]/slices[]` のIDを追加した。同名・入れ子・日本語名、分割8通りと明示tag指定、nullをindexed/RGBA両方で検査した。互換JSON2形式は不変。
- Q-PAL-02とunused_paletteから透明番号を除外し、番号0/2、キャッシュ有無、検証デルタ、透明だけの空プロジェクトを固定ベクタで検査した。SPEC §6.4.1の切捨て画素数の格納先はchanged.clipped_pixelsへ訂正した。
- 実uv試験の空stderr仮定は環境同期のeditable再ビルド通知で破れる。pyprojectのmtime変更だけで再現し、`uv run --no-sync`、設定先隔離、期限・失敗時診断に修正した。再試行なし。
- `uv run pytest -q --tb=short`: **1411 passed / 2 skipped（283.87秒）**。skipは既存Windowsシンボリックリンク権限2件。Ruff check/format、schema drift、repository、dev/mcp/gui依存監査42件、core/opsのmypy36ファイルとstrict7ファイルが成功。
- 唯一の更新器で既存15・新規3のgolden期待値を生成して全差分を確認した。既存PNG・画素配列・画素ハッシュ・正本は不変。新しい独自分割PNGは既存互換配列PNGとバイト同一。M5全出力はハッシュシード17/319でも一致した。
- 実CLIで2×1・2フレーム・透明番号2・日本語タグ/スライスを作成し、検証デルタ・全フレームプレビュー・書出しPNG/JSONを確認した。validation_ok/verified=true、error/warning=0、未使用色0。情報3件は独立同一セルと1画素クラスタの工学ベクタによる意図どおりの指摘として保持。git管理外の `build/fix6-review/` に実ファイルと記録を残した。
- 判断I-901〜I-904。SPEC変更は付録D.1と§6.4.1、§13.2/13.4。新規依存・外部参照・ビジュアル判断なし。LinuxはI-007のとおり未実行、main統合はオーケストレーターが行う。詳細は [FIX6_IMPLEMENTATION_REPORT.md](FIX6_IMPLEMENTATION_REPORT.md)。

## R1-F2: Diffusers依存監査とGPU生成検証（2026-11-12）

- 外部CUDA環境の全33配布物の原文・nativeを監査し、NVIDIA DLL、CNRI、MPL、vendor LGPLが許可外のため選択肢(b)で空extraを維持した。主lock・許可例外・第三者台帳の追加なし。監査表・導入手順は `GENERATION.md`。
- ローカルfp16 variant、生成中だけの決定性設定・例外時復元・3精度状態の保持・プロセス内ロック、混在ライセンス固定ベクタ、外部保存の監査/GPU計測ツール、既定skipのgpu試験を追加。
- 対象回帰 **22 passed / 1 skipped / 10.38秒**、明示した実GPU試験 **1 passed / 329.72秒**。最終全体 `uv run pytest -q --tb=short` は **1427 passed / 3 skipped / 364.90秒**（GPU1件・既存Windows権限2件のskip）。Ruff check/format、core/ops mypy36ファイル、schema/repository、主環境依存42件は成功。
- RTX 3080でSDXL+Pixel Art XL LoRAを実CLIから3回生成。seed42、1024×1024、30 steps、guidance7、deterministic=trueでPNGバイト一致。全体時間540.420334100003 / 446.6919937000057 / 337.9346435000043秒、中央値446.6919937000057秒、観測VRAMピークはいずれも13342MiB。起動・ハッシュ・ロード・保存込みであり、性能改善の前後比較ではない。直列化の並行性能比較は未測定。
- SRC1はai全14関門pass、128×128/33パレットで配置。変更後プレビューと実書き出しPNGを表示し、validate ok/error0/warning0、validation_ok/verified=true、Pillowと独自デコーダのRGBA一致を確認した。追加GPU画像は孤立画素1件で拒否し、段階画像確認後も関門を変更しなかった。privateへ合格PNG・途中段階・拒否例を保存し、画像・重みはコミットしていない。
- 初回1800秒タイムアウトとRAM圧迫も記録。判断 **I-1641〜I-1649**、SPEC §12.4局所追記、ゴールデン変更なし。実装 `d7d3a5f` / `799c69b`。Linux/他GPU/別版、CIコーパス化、美的評価は未実施。原文参照・台帳用行・残件は [R1_F2_REPORT.md](R1_F2_REPORT.md)。
