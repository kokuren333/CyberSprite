# FIX-2 — アニメーション制作の使い勝手修正

担当: Codex。ブランチ: `fix2-preview`。対象は e2e-03 §5 の工学的な修正。`generate/` と `gui/` は変更していない。

## 実装

| 対象 | 内容 |
|---|---|
| `core/previews.py`、`ops/args.py`、`ops/previews.py`、`ops/queries.py` | 共通フレーム指定、strip/grid、既存3×5数字のラベル、2px間隔、1024px上限、任意RGB背景、約50%の前後幽像、`onion.loop_tag` |
| `cli/generated.py`、`ops/descriptions.py` | 自動生成の `--layout`、共通フレーム指定、既存 `--onion p,n` の維持、表示色の説明 |
| `core/history.py` | strip/gridも直近100コミットのプレビュー保持対象に追加 |
| `ops/queries.py` | 葉レイヤーごとの `link_groups`、リンクセルごとの所有フレーム `link` |
| `core/registry.py`、`core/transactions.py`、`ops/common.py`、`ops/frames.py`、`ops/tiles.py` | 従来の `linked_frames` を保持して `changed.link_groups` を追加 |
| `formats/common.py`、`formats/export.py`、`formats/export_args.py` | 画像とデータの結果モデルを分離。データは `kind: data` とpath/bytes/sha256のみ。MCP outputSchemaも同じモデルから生成 |
| `formats/palette_files.py`、`formats/export.py` | GPL/PAL/HEXに実RGBを保存し、透明番号を `W_PALETTE_TRANSPARENT_ENTRY` で通知。HEX出力はRGB、RGBA入力は維持 |
| `formats/export_args.py` | 各exportサブコマンドの `--out` 説明に全プレースホルダと `{frame:02}` を追加。展開対象がexport imageであることも明記 |
| `ops/structure.py` | スライスの生RGB表示色にffを補い、正本のRGBA型と既存RGBA入力を維持 |
| `tests/unit/test_fix2.py`、`tests/unit/test_m5_exports.py`、`tools/golden_cases.py`、`tests/golden/` | 回帰試験、整数テストベクタ、画像/データの出力契約とパレット警告のゴールデン |
| `tools/fix2_acceptance.py` | 原本を一時ディレクトリへコピーして実CLIを実行し、実PNGを再復号し、原本とコピーの正本のバイト不変を検査する再現用スクリプト |

## 受け入れ基準

| 番号 | 状態 | 確認 |
|---|---|---|
| 1 共通framesと8枚制限 | 合格 | 整数・配列・all・範囲・タグ、解決後の制限検査とmessageの回避策 |
| 2 strip/grid | 合格 | 単一PNG、番号・2px間隔、auto・定規・巨大キャンバス・4096フレームの上限試験 |
| 3 任意RGB背景 | 合格 | パレット外のRGB、既存パレット番号・市松模様、正本・レンダラ不変 |
| 4 onionとタグ循環 | 合格 | 赤/青と約50%の整数期待値、元アルファ保持、前後の端の循環、範囲外拒否 |
| 5 linkと組一覧 | 合格 | 2組を同時編集した固定ベクタと実CLIのinfo |
| 6 files契約 | 合格 | JSON/テキストパレットの画像フィールド排除、PNGの画像情報保持、MCPスキーマによる拒否試験 |
| 7 小修正 | 合格 | 全export help、タグ/スライスの生RGB作成・更新、透明番号1の実RGBと警告、linked_frames互換 |
| 8 全体検査・実CLI | 合格（Windows） | 1300 passed / 2 skipped、下記の実ファイル確認も完了 |

## 検証

- `uv sync --locked --extra mcp --extra gui`: 既存ロックで同期。依存の追加・更新なし。
- `uv run pytest -q --tb=short`: **1300 passed / 2 skipped、253.54秒**。スキップは既存のWindowsシンボリックリンク権限の2件。
- `uv run pytest tests/unit/test_fix2.py tests/unit/test_m5_exports.py -q --tb=short`: 初期の関連確認は91 passed / 1 skipped。
- `uv run pytest tests/test_goldens.py tests/unit/test_fix2.py -q --tb=short`: 68 passed（スライスRGB入力の追加前）。
- `uv run pytest tests/mcp/test_mcp_contracts.py tests/mcp/test_output_schema_root.py tests/mcp/test_int_formats_pipeline.py -q --tb=short`: 14 passed。
- `uv run pytest tests/unit/test_fix2.py tests/unit/test_ops.py tests/unit/test_ops_edges.py -q --tb=short`: スライスRGB入力の追加後に225 passed。
- `uv run ruff check`、`uv run ruff format --check`、`uv run python tools/gen_schemas.py --check`、`uv run python tools/check_repository.py`、`git diff --check`: 成功。
- `uv run python tools/check_licenses.py --include-dev --extra mcp --extra gui`: 既存配布物の監査が成功。既存I-012の例外も維持。
- `uv run mypy`: 既存記録と同じ78件（24ファイル）が残る。型検査の既知の未解消分は今回の対象外。
- ゴールデンは `uv run python tools/update_goldens.py` だけで生成した。既存画像・画素ハッシュ・正本の差分はない。応答JSONのリンク組・files情報と新規のパレット出力を確認した。

## CLIセッションと実画像

実行: `uv run python -m tools.fix2_acceptance --out build/fix2-review`。

原本を同出力先内の一時ディレクトリへコピーし、6回のCLI呼び出しでvalidate・info・4つのpreviewを実行した。検証結果はerror 0、warning 0、info 10。コピーと原本の `project.json` はrevision 17のままバイト一致。原本SHA-256は `7911ed892057e5bda2fb6870404f0553c88e966fccd9d4d918765910189748f0`。

| 実ファイル | 大きさ | 確認内容 |
|---|---|---|
| `build/fix2-review/strip.png` | 782×103 | tag:walkの0〜7、番号と横一列 |
| `build/fix2-review/grid.png` | 902×697 | 全10フレーム、行優先、空きセル |
| `build/fix2-review/onion-loop.png` | 512×512 | フレーム0に前7/次1を指定した装飾 |
| `build/fix2-review/white.png` | 512×512 | パレット外の白背景 |

4枚とも書いたPNGそのものを再復号し、画像を開いて確認した。呼び出しと結果、各PNGのSHA-256は `build/fix2-review/session.json` にある。ビジュアルのデザイン判断は行っていない。

## 判断・仕様・依存・残件

- 判断は I-751〜I-761。仕様補足は§5.8.1、§6.7.1、§8.8、§10.2.2、§10.3.1、§10.4、付録C。§5.7のタグの表示色は既に正しかったため変更していない。
- 新規依存なし。ライセンス台帳の編集なし。外部資料・他製品のソース・文面・アセットの参照なし。参照はリポジトリ内の仕様・判断・モジュール説明・e2e-03報告だけ。
- LinuxはこのWindows環境では未実施。既存I-007とWindows/LinuxのCI設定を維持する。
- 極端に長いstrip等では番号・間隔だけでも1024pxを超えるため最終画像も整数間隔で縮小する。番号の判読には範囲を小さくする。通常の8〜10フレームでは数字は既存フォントのまま保持される。
- 新しい配色・フォント・GUIの判断はしていない。表示の最終的な見やすさの評価はOpusのレビュー対象。
- 実装コミットは `1547911`（プレビュー・リンク・書出し契約）と `70fe2a9`（スライスRGB入力）。mainへの統合はオーケストレーターが行う。
