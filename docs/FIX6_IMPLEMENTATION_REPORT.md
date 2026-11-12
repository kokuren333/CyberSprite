# FIX-6 — マニュアル作成時に見つかった整合性修正

作業ブランチは `fix6-small`。仕様は `docs/SPEC.md`、判断記録は I-901〜I-904。

## 実装と受け入れ基準

| 対象 | 結果 |
|---|---|
| 独自シートの名前とID | `formats/sheet.py` の `items[].layer/tag/slice` を名前に統一し、`layer_id/tag_id/slice_id` を併記。対象なしは両方 `null`。上位の `tags[]/slices[]` にも `id` を追加し、同名対象を対応付けられる。レイヤー経路は従来の `layers[].path` に保持 |
| シートの回帰検査 | 8通りの分割設定と明示タグ指定を indexed/RGBA 両方で検査（18件）。入れ子・同名レイヤー、同名タグ・スライス、日本語名、未指定時の `null` と順序を確認 |
| 切捨て画素数の文書 | SPEC §6.4.1 を `changed.clipped_pixels` に訂正。実装の変更なし |
| Q-PAL-02 | `core/quality.py` で予約された透明番号を除外。`unused_palette` も同じ集合を数え、`colors_used` は実使用数を維持。透明番号0/2・キャッシュ有無・指摘文面・検証デルタ・透明だけの空プロジェクトを検査（5件） |
| 実uvのUTF-8試験 | `tests/e2e/test_cli_m3.py` を `uv run --no-sync` に変更。設定先を一時ディレクトリに隔離し、60秒の期限と失敗時のstdout/stderr表示を追加。再試行なし |

## 不安定な試験の原因

従来は `uv run` が環境同期を行うにもかかわらず、その全stderrが空であると仮定していた。
`pyproject.toml` のmtimeだけを1秒進めて実行すると、通常の `uv run --offline cybersprite --version` は終了0でもeditable再ビルド・再導入の通知をstderrへ出した。
同じ鮮度条件で先に実行した `uv run --no-sync cybersprite --version` のstderrは空だった。
実験後に元のmtimeを復元した。修正後も日本語JSONのUTF-8復号、成功/失敗の終了コード、空stderrの検査を維持する。

## ゴールデンの確認

`uv run --no-sync python tools/update_goldens.py --case m5_exports --case raster_ops --case transactions` のみで更新した。
既存15ファイルの差分と新規3ファイルをすべて確認した。

- 独自シート5種類は項目のnull ID欄とtags/slicesのIDが増え、対応する結果JSONのbytes/sha256だけが追従する。
- トランザクション5応答は `unused_palette` のbefore/afterから未使用の透明番号1個を除く。
- 新規 `sheet-split-native` は名前とIDの実値を固定する。PNGは既存 `sheet-array.png` とバイト単位で同一。画像とJSONのbytes/sha256を実ファイルから再計算して照合した。
- 既存PNG・画素配列・画素ハッシュ・正本は不変。互換JSON2形式も不変。
- `PYTHONHASHSEED=17/319` の別プロセスでM5全出力の結合SHA-256が一致した。

## 実CLIと最終ファイル

実CLIで2×1・2フレームを新規作成し、透明番号2のパレット、黒白の画素、日本語タグ・スライスを1トランザクションで適用した。
検証デルタを確認後、validate、全フレームgridプレビュー、独自シートPNG/JSONの書き出しを実行した。
`validation_ok=true` / `verified=true`、未使用色0、error/warningとも0。
全フレームプレビューと実PNGを開き、実ファイルの復号画素・各項目の画素ハッシュ・名前/ID対応を確認した。
git管理外の `build/fix6-review/` にPNG、JSON、トランザクション入力、成功4呼出しの `session.json` を残した。

情報指摘3件は意図どおり保持した。Q-ANI-05は同じ絵の独立セルを2枚作ったため、Q-PIX-02の2件は1画素ずつの黒白を各フレームへ置いたためである。

## チェック結果

| コマンド | 結果 |
|---|---|
| `uv sync --locked --extra mcp --extra gui` | 成功。既存lockの依存を導入 |
| `uv run pytest -q --tb=short` | **1411 passed / 2 skipped、283.87秒**。skipは既存のWindowsシンボリックリンク作成権限2件。実uv試験・全golden・MCPシナリオを含む |
| `uv run --no-sync pytest tests/unit/test_m5_exports.py tests/unit/test_quality.py tests/e2e/test_cli_m3.py::test_real_uv_stdout_utf8_and_errors -q --tb=short` | **100 passed / 1 skipped**。skipは同じシンボリックリンク権限の1件 |
| `uv run --no-sync ruff check` | 成功 |
| `uv run --no-sync ruff format --check` | 173ファイル成功 |
| `uv run --no-sync python tools/gen_schemas.py --check` | driftなし |
| `uv run --no-sync python tools/check_repository.py` | 成功 |
| `uv run --no-sync python tools/check_licenses.py --include-dev --extra mcp --extra gui` | 既存依存42件成功。台帳・ライセンス例外は未変更 |
| `uv run --no-sync mypy src/cybersprite/core src/cybersprite/ops` | 36ファイル成功 |
| CI指定7ファイルの `uv run --no-sync mypy --strict --follow-imports=silent …` | 7ファイル成功 |
| `git diff --check` | 成功 |

## 仕様・依存・残件

SPEC変更は付録D.1の名前/ID契約、§6.4.1の格納先、§13.2/13.4の未使用色の対象だけ。
判断は I-901〜I-904。新しい依存、第三者コード、外部参照、ビジュアル判断、関連TODOはない。
Linuxは既存I-007どおり未実行。GUIコードは未編集。mainへの統合はオーケストレーターが行う。
