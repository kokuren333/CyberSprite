# 固定小数点 Oklab v1

`oklab_fixed_v1.json` は付録 B の言語非依存ベクタ。灰色 256 色、原色・補色 6 色、LCG の 1000 色をこの順に収録する（重複を除去しない）。LCG は初期値 `0x43535052`、`state = (1664525 * state + 1013904223) mod 2^32`。更新後のビット 24〜31、16〜23、8〜15 を RGB とする。

生成元は `tools/gen_color_tables.py`。行列・線形化表は四捨五入（`floor(x + 1/2)`）、立方根の参照計算は整数二分探索。実行時実装の Newton 法とは独立している。JSON は UTF-8、LF、空白なし、末尾改行あり。SHA-256 は `3d9223a18fd170a223118b015e6cf2d58be0c284cc2adad2306d86c6bca84a26`。

通常は `python tools/gen_color_tables.py` で照合する。初回生成は `--write`。既存ベクタの変更はゴールデン更新のレビュー工程で差分を確認し、失敗したテストに合わせた機械的な更新は行わない。係数の出典は `docs/SPEC.md` 付録 B と `NOTICE` にある。
