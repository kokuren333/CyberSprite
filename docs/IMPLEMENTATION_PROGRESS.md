# IMPLEMENTATION_PROGRESS — 実装フェーズの進捗

オーケストレーター: Claude Opus 5.5（effort 高）。仕様の正本は `docs/SPEC.md`、判断は `docs/DECISIONS.md`。
新しい記録を下に足していく（追記式）。

## 現在地（2026-11-12 11:05 JST）

| マイルストーン | 状態 | 備考 |
|---|---|---|
| M0 準備と実機参照 | **完了** | P-11 も合格（実機 Aseprite と全ピクセル一致） |
| M1 コア基盤 | **完了** | |
| M2 Op とトランザクション | **完了** | |
| M3 CLI | **完了** | `--version` 中央値 246 ms |
| M4 MCP サーバ | **完了** | Claude Code と Codex から実接続して描画まで確認（I-012 のライセンス判断、outputSchema の互換修正） |
| M5 形式 | **完了** | PNG / シート 3 形式 / GIF / APNG / パレット / `.aseprite` 往復、全書き出しに自己検査 |
| M6 変換パイプライン | **完了**（生成画像のコーパス (d) は M9 後） | 較正 (a) 255/255 完全一致。1024² 入力 0.7〜1.1 秒 |
| 結合 INT-1 | **完了** | M3/M5/M6 の結合、e2e-01 の指摘 5 件を修正 |
| M7 タイルマップ | 進行中（Codex、`m7-tiles`） | e2e-02 の小さな指摘 3 件も同梱 |
| M8 GUI | サーバ・土台は完了（main）。見た目の実装は進行中（Opus、`m8-ui`） | テーマ案 C を選定済み（I-011） |
| M9 生成バックエンド | 進行中（Codex、`m9-generate`） | |
| M10 仕上げ | 未着手 | |
| M0 準備と実機参照 | **完了** | 下記 |
| M1 コア基盤 | **完了**（main に統合） | Windows で 168 テスト。Linux は CI 設定のみ（I-007） |
| M2 Op とトランザクション | **完了**（main に統合） | 59 Op、22 品質規則、履歴・取り消し、プレビュー・差分。ラスタライズは先行ブランチ `m2-raster` で作成 |
| M3 CLI | int-m356 に統合・Windows 検証完了 | INT-1 報告参照 |
| M4 MCP サーバ | int-m356 に統合・Windows 検証完了 | 依存の保留は既存 I-012 で解消 |
| M5 形式 | int-m356 に統合・Windows 検証完了 | CLI/MCP と実書出しを接続 |
| M6 変換パイプライン | int-m356 に統合・Windows 検証完了 | 取り込み・来歴・配置・較正を統合。(a)255/255完全一致。生成(d)とLinux実行は未了 |
| M7 タイルマップ | m7-tiles 上で Windows 検証完了 | 77 Op、8反転ゴールデン、MCPシナリオ3。統合はオーケストレーターが行う |
| M8 GUI | テーマ 3 案を作成し案 C を選定（I-011） | 実装は M7 の後 |
| M9 / M10 | 未着手 | |

main のテスト（2026-11-12 11:00、Windows / Python 3.12）: Python 1160 passed / 2 skipped、GUI（vitest）625 passed。

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
