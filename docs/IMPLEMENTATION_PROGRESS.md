# IMPLEMENTATION_PROGRESS — 実装フェーズの進捗

オーケストレーター: Claude Opus 5.5（effort 高）。仕様の正本は `docs/SPEC.md`、判断は `docs/DECISIONS.md`。
新しい記録を下に足していく（追記式）。

## 現在地（2026-11-12 09:50 JST）

| マイルストーン | 状態 | 備考 |
|---|---|---|
| M0 準備と実機参照 | **完了** | 下記 |
| M1 コア基盤 | **完了**（main に統合） | Windows で 168 テスト。Linux は CI 設定のみ（I-007） |
| M2 Op とトランザクション | **完了**（main に統合） | 59 Op、22 品質規則、履歴・取り消し、プレビュー・差分。ラスタライズは先行ブランチ `m2-raster` で作成 |
| M3 CLI | 進行中（Codex、`m3-cli`） | |
| M4 MCP サーバ | 進行中（Codex、`m4-mcp`） | |
| M5 形式 | 進行中（Codex、`m5-formats`） | |
| M6 変換パイプライン | 進行中（Codex、`m6-pipeline`） | 純粋アルゴリズムと固定小数点 Oklab は先行ブランチで完了・統合済み。較正コーパスの原画は Opus が作成 |
| M7 タイルマップ | 未着手（M5 の後） | 指示書は準備済み |
| M8 GUI | テーマ 3 案を作成し案 C を選定（I-011） | 実装は M7 の後 |
| M9 / M10 | 未着手 | |

main のテスト: 622 passed（M2 統合時点、Windows / Python 3.12）。

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
