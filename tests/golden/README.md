# ゴールデンファイル（M1）

17 ケースの入力は自作の数値配置と仕様付録 A。各 `case.json` は正準往復、正規化、ID 発行、描画オプションを指定する。M2 の Op・トランザクションは扱わない。

`expected/` は `uv run python -m tools.update_goldens` だけで更新する。更新対象を絞る場合は `--case 名前`。変更サマリーを読み、JSON の期待ピクセルと正本の差分、実際の PNG を確認してからコミットする。テストから更新しない。

比較対象は CSPX1 ピクセルハッシュ、stored PNG の全バイト、期待ピクセル配列、警告・エラー、正準 JSON。PNG は限定 reader で再読して照合する。言語非依存の合成ベクタは `tests/vectors/compositing.json`。
