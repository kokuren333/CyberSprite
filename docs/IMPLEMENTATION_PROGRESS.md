# IMPLEMENTATION_PROGRESS — 実装フェーズの進捗

オーケストレーター: Claude Opus 5.5（effort 高）。仕様の正本は `docs/SPEC.md`、判断は `docs/DECISIONS.md`。
新しい記録を下に足していく（追記式）。

## 現在地（2026-11-12 09:50 JST）

| マイルストーン | 状態 | 備考 |
|---|---|---|
| M0 準備と実機参照 | **完了** | 下記 |
| M1 コア基盤 | **完了**（main に統合） | Windows で 168 テスト。Linux は CI 設定のみ（I-007） |
| M2 Op とトランザクション | **完了**（main に統合） | 59 Op、22 品質規則、履歴・取り消し、プレビュー・差分。ラスタライズは先行ブランチ `m2-raster` で作成 |
| M3 CLI | int-m356 に統合・Windows 検証完了 | INT-1 報告参照 |
| M4 MCP サーバ | int-m356 に統合・Windows 検証完了 | 依存の保留は既存 I-012 で解消 |
| M5 形式 | int-m356 に統合・Windows 検証完了 | CLI/MCP と実書出しを接続 |
| M6 変換パイプライン | int-m356 に統合・Windows 検証完了 | 取り込み・来歴・配置・較正を統合。(a)255/255完全一致。生成(d)とLinux実行は未了 |
| M7 タイルマップ | 未着手（M5 の後） | 指示書は準備済み |
| M8 GUI | テーマ 3 案を作成し案 C を選定（I-011） | 実装は M7 の後 |
| M9 / M10 | 未着手 | |

main のテスト: 622 passed（M2 統合時点、Windows / Python 3.12）。M6 ブランチの検証結果は下記。

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

### e2e で見つかった問題（未対応のもの）

| 出所 | 問題 | 担当 |
|---|---|---|
| e2e-01 #5 | `ops describe` の説明が定型文で、引数（例: `draw_rows` の `format: sym`）の意味が分からない | M3 後の修正 |
| e2e-01 #6 | `op` に `--label` がない（単発 Op の履歴ラベルが空） | M3 後の修正 |
| e2e-01 #7 | 図形系 Op（`ellipse` など）の result に `pixels_written` がない | M3 後の修正 |
| e2e-01 #8 | undo / redo の結果にプレビューがない | M3 後の修正 |
| e2e-01 #10 | Q-PIX-02 の `where.layer` が null（どのレイヤーか分からない） | M3 後の修正 |
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
