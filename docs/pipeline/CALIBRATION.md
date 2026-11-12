# パイプライン較正（M6-P 合成シード）

状態: `calibration.version = 0`、暫定。実画像を含む §11.9 全体の較正は未実施。M6-P の範囲は、整数の純粋関数と自作の合成コーパスである。仕様の変更はない。

## 再実行

Python 3.12、既存の NumPy / Pillow / pytest を使用する。PowerShell では先に `$env:PYTHONPATH="src"` を指定する。

```text
python -m pytest tests/pipeline -q
python tools/gen_color_tables.py
python tests/pipeline/corpus/synthetic.py
```

最後のコマンドは全ケースの指標・完全一致・画素ハッシュを JSON として標準出力へ出す。入出力ファイルやプロジェクトは変更しない。テストでは同じ処理を 2 回実行して、画素のバイト列と報告を比較する。別プロセスの `PYTHONHASHSEED=1,451` でも比較する。

## コーパスと結果

正解は `tests/pipeline/corpus/synthetic.py` の整数インデックス配列。チェッカー、灰色ランプ、入れ子の矩形をプログラムで定義した。配色や作品の見た目の判断は行っていない。倍率は 2〜8、位相は左・上の各 0 または 1 ピクセル切り落としの 4 通り。先頭セルを半分以上残すため、§11.3.2 の端セル保持規則に合う。透明部分も比較対象とする。

| 分類 | 内容 | 件数 | グリッド | 完全一致 | grid_score | fidelity |
|---|---|---:|---|---|---|---|
| (a) | チェッカー | 28 | auto | 28/28 | 1000 | 0 |
| (a) | ランプ | 28 | auto | 28/28 | 1000 | 0 |
| (a) | 疎な矩形 | 28 | fixed（正解の倍率・位相） | 28/28 | 1000 | 0 |
| (b) 相当 | 決定的な整数ノイズ（RGB 各 ±8） | 6 | 元のケースと同じ | 6/6 | 1000 | 7,820,066〜17,327,846 |
| (b) 相当 | 左隣との 3:1 整数混合 | 6 | 元のケースと同じ | 6/6 | 1000 | 0 |

(a) は **84/84、100% 完全一致**。疎な矩形の 28 ケースは自動検出の成功数に含めない。自動検出だけでは 56/84 が完全一致する。矩形の広い単色領域は周期を一意に示さず、仕様の peak 最大化は太い格子を選びうる。例えば倍率 4、切り落としなしの矩形では cell=20、grid_score=666 となり、upscaled の関門で拒否される。これは回帰テストで固定し、fixed での指定し直しを検証した。自動検出の仕様を変更して隠してはいない。

劣化ケースは画質の合否を要求せず、スコアのみを観測する。JPEG の実圧縮ではなく整数の近似的なノイズであり、(b) の正式な較正資料の代用にはしない。今回は微小ノイズを purity_tolerance=16 が許容し、混合した境界が内側から除外されるため grid_score がすべて 1000 となる。スコアが実画像を分離できることは、この結果だけでは証明されない。劣化ケースの割り当て先は正解パレット、(a) は exact。後始末は min_cluster=1、輪郭は keep、ディザは none。

## 暫定しきい値

規範データは `src/cybersprite/data/pipeline_defaults.json`。§11.10 をそのまま採用し、未較正の fidelity に数値は捏造しない。

| プリセット | grid_score（fail 未満 / warn 未満） | fidelity（fail 超 / warn 超） |
|---|---|---|
| exact | 判定しない | 0 / 0 |
| upscaled | 990 / 1000 | 0 / 0 |
| ai | 800 / 900 | 未較正（null、判定しない） |
| photo | 判定しない | 未較正（null、判定しない） |

共通値は min_cell=2、max_cell=64、harmonic_tolerance=850、min_peak=1500、purity_tolerance=16。セル純度が 990 以上なら downsample.auto は center、その他は mode。target は明示的に渡された PixelOE コールバックがあればそれを使い、なければ kcentroid。

## 後続の確定手順

Opus 担当の実作品と、正式な JPEG、非整数補間、生成画像、非ドット画像、誤指定格子を追加し、(a)〜(f) 各 10 枚以上、計 60 枚以上をそろえる。倍率 9〜16 も追加する。正解格子と期待出力を付け、(a)〜(c) 全件と (d) の 95% 以上を通し、(e)(f) の 95% 以上を落とす範囲の中央を fail とする。範囲がなければ (a)〜(c) 全合格を優先して理由を残す。warn は fail と (a) の最小値の中間、fidelity も同様に求める。確定時に calibration の版を上げ、全結果の表とゴールデン差分を確認する。

## 統合用 API

`pipeline/oklab.py` は標準ライブラリと NumPy のみに依存し、import 時にも Pillow を読まない。core からの色解決に再利用できる。LIN、M1i、M2i、Bayer の SHA-256 は読み込み時に検証する。色ベクタの LCG 定義と生成方法は `tests/vectors/color/README.md`。

各ステップは `(出力, 報告辞書)` を返し、量子化・輪郭処理は `(出力フレーム列, パレット, 報告辞書)`。グリッド検出は辞書を返す。RGBA は H×W×4 uint8、正本のインデックスは H×W uint8、パレットは RGBA 整数タプル列。複数フレームには共通のグリッドとパレットを使う。グリッドの `x_cells` / `y_cells` は半開区間で、系統 A のセル寸法の比較には分子・分母を使う。

固定パレットの名前・ファイルは呼び出し側で解決して `source` に渡す。関門は `compute_metrics` と `evaluate_gates` で純粋計算する。palette.frozen や palette_max は後者に渡す。256 色を超えてインデックス化できない場合は E_LIMIT_EXCEEDED に `gate=palette_budget` と必要色数を入れるため、統合層で失敗関門へ変換できる。`stage_report` と `build_pipeline_report` は渡された環境情報・プラグイン情報・画像参照から報告辞書だけを組み立てる。配置、manifest、import_image、段階 PNG の保存は M6 本体の担当。

`decode.py` のみ Pillow を使用する。CMYK・16bit 相当の入力モード・ICC を落としたことを警告し、復号済みの RGBA フレームと表示時間を返す。復号処理は Pillow の対応コーデックに依存し、組み込み整数ステップの比較対象は復号後の同一配列である。PixelOE の版・デバイス記録と結果保存は呼び出し側の責任。

Windows / Python 3.12.10 で実行済み。Linux はこの開発機にないため未実行（I-007）。Ruff はシステム Python に未導入で、依存を追加せず pytest と AST 制約検査を使用した。
