# 較正コーパス（`docs/SPEC.md` §11.9）

変換パイプラインのしきい値を決めるための画像。ここにある画像は**すべて CyberSprite プロジェクトのオリジナル**で、第三者の著作物は含まない。ライセンスはリポジトリと同じ Apache-2.0。

## 分類と置き場所

| 分類 | 内容 | 置き場所 |
|---|---|---|
| (a) 正解 | 本物のドット絵（インデックスカラー、等倍） | `originals/<name>.png` と `<name>.json` |
| (a) 合成 | 数式で作ったチェッカー・ランプ・矩形 | `synthetic.py` |
| (e) | ドット絵でない画像（グラデーション、アンチエイリアスの図形、ノイズ、写真風の風景、文字） | `non_pixel/<name>.png` |

- `originals/` の PNG は等倍の正解そのもの。拡大した (a) の入力、JPEG をかけた (b)、非整数倍に補間した (c)、格子を故意に間違えた (f) は、テストの中でここからプログラムで作る（ファイルとしては置かない）。
- `originals/<name>.json` は `{name, category, width, height, palette, transparent_index, opaque_colors, tags, notes, license, author}`。`palette` は `"#rrggbbaa"` の列で、PNG のパレット番号と同じ順。透明を使う画像は番号 0 が `"#00000000"`、使わない画像は `transparent_index: null`。`tags` は難しさの種類（`hard-grid`、`single-pixel-detail`、`low-contrast` など）。
- 絵は `make_originals.py` の中に文字の格子（1 文字 = 1 ピクセル）として書いてある。差分で絵の変更を読める。

## 作り直し方

リポジトリのルートで実行する。

```text
python tests/pipeline/corpus/originals/make_originals.py
python tests/pipeline/corpus/non_pixel/make_non_pixel.py
```

- どちらも決定的で、同じ Pillow / zlib なら同じバイト列になる（乱数は固定シード）。
- `make_originals.py` は書き出した PNG を読み直し、全ピクセルを照合する。パレットに使われない色や重複した色があれば止まる。
- `make_non_pixel.py` はテスト入力を作るだけなので浮動小数を使う。パイプラインのコードではない。`text_aa_384x128` は Pillow 同梱の既定フォントに依存するため、Pillow の版が変わると画素が変わりうる。
