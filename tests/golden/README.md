# ゴールデンファイル（M1）

25 ケースの入力は自作の数値配置と仕様付録 A。各 `case.json` は正準往復、正規化、ID 発行、描画、Op・トランザクション、形式の試験を指定する。

`expected/` は `uv run python -m tools.update_goldens --case 名前` だけで更新する。全件を意図して更新する場合は `--all --confirm-all` の両方が必要。指定なし・存在しない名前はエラーになる。変更サマリーと JSON 差分を読み、期待ピクセルと正本、実際の PNG を確認してからコミットする。テストから更新しない。

比較対象は CSPX1 ピクセルハッシュ、stored PNG の全バイト、期待ピクセル配列、警告・エラー、正準 JSON。PNG は限定 reader で再読して照合する。言語非依存の合成ベクタは `tests/vectors/compositing.json`。
