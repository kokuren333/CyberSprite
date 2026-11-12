# REVIEW_REQUEST_1 — 実装完了後のレビュー依頼（1 回目）

- 作成: オーケストレーター Claude Opus 5.5（effort 高）／2026-11-12 JST
- 宛先: 上流工程 Fable 5.2（`docs/SPEC.md` §16.5 のレビューループ、最大 3 回）
- 対象: ブランチ `main` の最新コミット（このファイルを含むコミット）
- 指摘の書き方: `docs/REVIEW_1.md` に、番号・重大度（`blocker` / `major` / `minor` / `suggestion`）・仕様の節・根拠（再現手順やファイル）・期待する状態（§16.5 の 2）。

## 1. できたこと

M0〜M10 をすべて実装し、`main` に統合した。詳細は `docs/IMPLEMENTATION_PROGRESS.md`（現在地の表）と各マイルストーンの報告（`docs/M*_REPORT.md` / `docs/M*_IMPLEMENTATION_REPORT.md`、`docs/INT1_…`、`docs/FIX*_…`）。

| 領域 | 内容 | 主な文書 |
|---|---|---|
| コア（M1・M2） | 正準 JSON の正本、構造不変条件 S-01〜S-14、整数だけのレンダラ、自前 PNG、Op レジストリ（現在 80 Op）、トランザクション（ロック・原子的保存・予行・冪等キー・no_op）、履歴と取り消し、品質規則 22 種と検証デルタ、プレビューと差分 | `src/README.md` |
| CLI（M3） | §9.3 の全コマンド。Op 定義から自動生成。終了コード、UTF-8、設定ファイル | `docs/CLI.md` |
| MCP（M4） | ステートレス、プロファイル、パスの制限、封筒、期限。Claude Code と Codex から実接続して描画まで確認 | `docs/MCP.md` |
| 形式（M5） | 画像、シート（配置 5 種・データ 3 形式）、GIF（自前 LZW）、APNG、パレット、`.aseprite` の往復、全書き出しの自己検査 | |
| パイプライン（M6・FIX-4） | 6 段階、固定小数点 Oklab、関門、来歴、較正（整数倍 255/255 完全一致、非整数倍の自動検出 62/68） | `tests/pipeline/CALIBRATION.md` |
| タイル（M7・FIX-3） | タイル Op 一式、反転 8 通り、`tileset_from_layer`、タイルセットの書き出しとプレビュー | |
| GUI（M8） | ローカルサーバ（JSON-RPC over WebSocket、トークンと Origin 検査）、React フロントエンド、テーマ「Circuit White」案 C（3 案から選定、I-011）、アイコン 41 個は CyberSprite 自身で描いた `.csprite` から書き出し、高コントラスト版、日英、コントラスト自動検査 | `docs/GUI.md`、`docs/design/` |
| 生成（M9） | バックエンドのインターフェース、`command` / `diffusers`、ライセンス承諾、来歴。GPU のない環境で理由を返す | `docs/GENERATION.md` |
| 仕上げ（M10） | GUI を同梱した wheel、新しい環境での導入確認、性能測定、通しシナリオ 1〜5、手順書 `skills/` 5 冊、作例 3 点、NOTICE と台帳 | `docs/PERFORMANCE.md`、`docs/KNOWN_ISSUES.md`、`skills/`、`examples/` |

## 2. 実機（Aseprite v1.3.18.6 Steam 版）との照合

- 挙動確認 P-01〜P-11 を実施（`docs/reference/ASEPRITE_INVENTORY.md` §2）。P-01（タイル反転の順）は仕様どおり。P-02・P-05・P-09 は既知の差として §5.9.3 に記録（I-002）。P-04 で付録 D.2 を確定（I-003）。P-10 は規則を維持（I-004）。
- **P-11: CyberSprite が書いた `.aseprite` を実機で開き、全フレームの描画が CyberSprite と全ピクセル一致**（タイル反転 8 通りを含む）。

## 3. テスト結果（Windows 11 / Python 3.12.10）

- Python: 1387 passed / 2 skipped（skip は開発機にシンボリックリンク作成権限がない 2 件）。FIX-6 の統合後の数は `IMPLEMENTATION_PROGRESS.md` を参照。
- GUI: vitest 627 passed（TS のラスタライズがテストベクタ 618 件と 100% 一致）、Playwright 3 passed、コントラスト検査 86 組合格。
- 通しシナリオ 1〜5（MCP の JSONL 再生）すべて合格、skip / xfail なし。
- Ruff、スキーマ差分検査、クリーンルーム検査、ライセンス検査（実行時・開発・ビルド・`mcp` / `gui` extra）合格。
- **Linux では一度も実行していない**（開発機に WSL / Docker がなく、GitHub リポジトリも未作成。I-007）。決定性（水準 A）の複数環境での証明は、CI を初めて走らせるまで未了である。

## 4. e2e 制作テスト（Opus 5.5 の制作サブエージェント）

| # | 題材 | 結果 |
|---|---|---|
| 01 | キャラクター（32×32、まばたき） | 4/5 |
| 02 | GUI アイコン 40 個 | 4/5 |
| 03 | 歩行アニメーション（8＋2 フレーム） | 4/5 |
| 04 | タイルセットとマップ | 4/5 |
| 05 | 生成画像風の入力の取り込み変換 | 3/5（パイプラインの重大な問題を発見 → FIX-4 で修正） |
| 06 | **新しい Claude Code セッションが AGENTS.md と skills/ だけでシナリオ 1 を完走**（M10 の受け入れ基準） | 完走。手順書の不足 10 点を反映済み |

見つかった問題はすべて修正タスク（INT-1、FIX-2〜FIX-6）で対応した。記録は各 `e2e-tests/*/REPORT.md` と `IMPLEMENTATION_PROGRESS.md`。

## 5. 既知の不足（`docs/KNOWN_ISSUES.md` の要約）

1. Linux CI 未実行（上記）。
2. 性能目標 2 項目が未達: 64×64・10 層・32 フレームの 1 トランザクション 205 ms（目標 150 ms）、GUI の 128×128 往復 93 ms（目標 50 ms）。FIX-5 で 950→205 ms、236→93 ms に改善。残りは正本全体の読込・構造検査・JSON 生成・同期保存。
3. M0 の GUI 画面の一部が未撮影（I-006）。発注者がよく使うキーの聞き取りが未了。
4. 生成画像の較正コーパス (d) が未作成。`diffusers` は extra に依存を固定していない（I-014）。実 GPU・実モデルでの生成は未検証。
5. GUI のメニューの多くが汎用の Op ダイアログを開く。取り込み・書き出しの専用フォームは簡素。
6. mypy のエラーが src 全体で 47 件残る（core / ops は CI で検査し 0 件）。

## 6. レビューで特に見てほしい点（§16.5 の観点に沿って）

- (a) 仕様への適合: 実装中に仕様を補足・修正した箇所は `docs/DECISIONS.md` の I-001〜I-9xx（各行に節番号）。特に I-002（実機との差の扱い）、I-010 / I-012 / I-014（ライセンスの判断）、I-011（テーマの選定）、I-013（アイコンの書き出し）、FIX-4 の §11.3 の格子検出の変更。
- (b) 決定性: 水準 A / B のテストが Windows でしか走っていないこと。
- (c) クリーンルームと台帳: `third_party/THIRD_PARTY.md`、`docs/reference/PROVENANCE_LOG.md`、`NOTICE`、`gui/THIRD_PARTY_JS.md`。
- (d) エージェントからの使いやすさ: e2e-06 の結果と `skills/`。
- (e) GUI のテーマの制約（§14.3.3）: `docs/design/gui/*.png`、`npm run check:contrast`。
- (f) 文書。

## 7. 動かし方

```
cd CyberSprite
uv sync --extra mcp --extra gui
uv run pytest                                   # Python 全体
cd gui && npm ci && npm test && npx playwright test && cd ..
uv run cybersprite --help                       # CLI
uv run python -m cybersprite.mcp --root <dir>   # MCP（stdio）
uv run cybersprite gui examples/runner-walk/runner.csprite   # GUI（ブラウザが開く）
uv run python tools/build_release.py            # GUI を同梱した wheel を作る
```

制作の手順は `AGENTS.md` §6 と `skills/README.md` から読む。
