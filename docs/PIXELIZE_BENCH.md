# ピクセル化の中立ベンチと関門較正（R1-D1）

2026-11-12、Windows / Python 3.12。製品の既定方式は変更していない。結果は自作の入力に限った比較であり、外部ツールの一般的な優劣や作画品質の判定ではない。

## 再現

`uv sync --extra mcp --extra gui` の後に `uv run python tools/pixelize_bench.py --no-generated --output build/pixelize-bench --xprite-root PATH`。ネットワークは使わない。`--smoke --limit 1 --no-generated` は3ケースの小試験。`--repeats` の既定は3。生成画像と段階画像はgit管理外のbuildに保存する。ライセンス監査に必要な取得はベンチ実行とは別に済ませた。

xpriteを測る場合は利用者がリポジトリ外へ `@xprite/pixelate@0.1.2` を導入し、パッケージのディレクトリを `--xprite-root PATH` で渡す。今回は公式npm tarballのLICENSEを開いてから外部一時領域へ展開した。Nodeの同一ワーカーを使い、最初のimportを含む実測3回の中央値を取る。JSON転送・起動・段階画像保存・共通の減色と後始末も時間に含むので、純粋な検出器の速度ではない。並行する他worktreeの負荷があり、速度の改善・退行は主張しない。

## 版とライセンス

[監査表](reference/PIXELIZE_LICENSE_AUDIT.md) と [原文のURL・ハッシュ](reference/pixelize_license_audit.json) を参照。FixerのPython参照版はOpenCV/SciPy、proper-pixel-art 2.0.0はav/OpenCV/tqdm、PixelOE 1.0.0はOpenCV/PyTorch等を要求する。3つとも配布用依存を追加せず利用者導入を検出する。今回の環境には導入していないため、実測の順位には含めない。xprite 0.1.2は評価のみ。未監査の環境マーカーや同梱バイナリを許可済みとは扱わない。

## 入力と指標

正解は `tests/pipeline/corpus/originals` の自作画像のみ。各原画のSHA-256と条件は小さな [マニフェスト](../tests/pipeline/pixelize_bench_manifest.json) に固定する。劣化画像はコミットしない。

| 系列 | 条件 |
|---|---|
| nearest | 整数nearest ×2〜×12 |
| fractional | ×5.5、bilinear、寸法は整数切捨て |
| offset | ×6から左右各2px・上下各1pxを切り出す |
| blur | ×6に整数の可分[1,2,1]/4カーネル、端を複製、各軸で四捨五入 |
| jpeg50 / jpeg75 | ×6、不透明matte (246,244,238)、Pillow JPEG q50/q75、subsampling=0 |
| noise | ×6、RGBに一様整数±8、alphaは保持、seed=1301 |
| jitter | ×6、色ごとRGBに一様整数±12、seed=1301の継続状態 |
| alpha_aa | ×6、alphaだけに同じ整数blur |

内蔵方式は `preset ai` のAUTO。外部方式のRGBAにも同じaiのパレット抽出・後始末を適用する（外部方式の格子を再検出しない）。PixelOEには正解寸法を渡す設計であり、導入した場合は必ず **oracle size** と明記する。生成画像には正解寸法がないのでPixelOEの比較は行わない。

寸法完全一致率は全入力を母数とする。誤寸法の結果を補間・位置合わせして画素精度を上げることはせず、画素指標はnull、表では評価できた件数も併記する。厳密RGBA一致、同じ透明区分内で画素一致を最大化する多対一色写像後の一致（同数は固定小数点Oklab距離、RGBA順）、元の色のOklab距離2500以下の一致、使用不透明色数の差、alpha>=128のmask IoUを記録する。RGBAの透明部分の隠れたRGB差も厳密一致には含める。JPEGのmatteは透明を復元しないためIoUには不利になる。

## 実測

自作原画17枚 × 19条件 × 2方式 = 646件。各3回。Python 3.12.10、NumPy 2.3.4、Pillow 13.0.0。3つの未導入アダプターは除外し、成功率の母数に架空の出力を加えていない。

| 方式 / 系列 | 全件 / エラー | 寸法一致 | RGBA一致 | 色写像後一致 | Oklab一致 | mask IoU | 画素評価件数 | pitch誤差 | 色数差 | 中央値ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| builtin / alpha_aa | 17 / 0 | 100.0% | 96.7% | 96.8% | 98.8% | 0.987 | 17 | 0.000 | -1.059 | 901.222 |
| builtin / blur | 17 / 0 | 100.0% | 96.7% | 96.8% | 98.8% | 0.987 | 17 | 0.000 | -1.059 | 1074.612 |
| builtin / fractional | 17 / 0 | 52.9% | 73.9% | 94.8% | 80.0% | 0.984 | 9 | 3.095 | 1.706 | 1383.741 |
| builtin / jitter | 17 / 0 | 100.0% | 29.5% | 97.7% | 90.8% | 0.987 | 17 | 0.000 | -1.000 | 439.896 |
| builtin / jpeg50 | 17 / 0 | 94.1% | 1.6% | 63.6% | 62.0% | 0.686 | 16 | 0.118 | 2.588 | 1373.511 |
| builtin / jpeg75 | 17 / 0 | 100.0% | 11.3% | 66.2% | 66.1% | 0.705 | 17 | 0.000 | 1.588 | 1058.241 |
| builtin / nearest | 187 / 0 | 100.0% | 96.7% | 96.8% | 98.8% | 0.987 | 187 | 0.000 | -1.059 | 419.015 |
| builtin / noise | 17 / 0 | 94.1% | 31.4% | 88.4% | 89.6% | 0.875 | 16 | 0.000 | 5.412 | 1218.608 |
| builtin / offset | 17 / 0 | 100.0% | 96.7% | 96.8% | 98.8% | 0.987 | 17 | 0.000 | -1.059 | 379.082 |
| xprite / alpha_aa | 17 / 0 | 100.0% | 96.7% | 96.8% | 98.8% | 0.987 | 17 | 0.000 | -1.059 | 1902.329 |
| xprite / blur | 17 / 0 | 100.0% | 94.6% | 96.6% | 97.2% | 0.987 | 17 | 0.003 | -0.588 | 1612.570 |
| xprite / fractional | 17 / 0 | 94.1% | 73.3% | 92.2% | 86.7% | 0.971 | 16 | 0.091 | 1.588 | 2446.744 |
| xprite / jitter | 17 / 0 | 100.0% | 29.5% | 97.7% | 90.8% | 0.987 | 17 | 0.000 | -1.000 | 1456.584 |
| xprite / jpeg50 | 17 / 0 | 100.0% | 1.6% | 66.8% | 68.0% | 0.705 | 17 | 0.003 | -0.353 | 3228.635 |
| xprite / jpeg75 | 17 / 0 | 100.0% | 12.7% | 67.1% | 69.1% | 0.705 | 17 | 0.004 | -0.471 | 2873.072 |
| xprite / nearest | 187 / 0 | 100.0% | 96.7% | 96.8% | 98.8% | 0.987 | 187 | 0.000 | -1.059 | 1998.931 |
| xprite / noise | 17 / 0 | 100.0% | 36.2% | 96.5% | 98.6% | 0.987 | 17 | 0.003 | -1.000 | 1924.468 |
| xprite / offset | 17 / 0 | 94.1% | 97.7% | 97.8% | 98.7% | 0.986 | 16 | 0.008 | -1.059 | 2064.110 |

[各入力の3回の生時間・ハッシュ・全指標](reference/pixelize_bench_results.json)。pitch誤差は検出器が報告した軸の周期と既知倍率の平均絶対差であり、切り出し後の画像全幅から倍率を逆算しない。未検出はnull。Nodeは分析と復元で検出を2度呼ぶため、速度の比較は検出器単体の順位ではない。

nearestのRGBA画素一致率96.7%はaiの減色・後始末を適用した後の値で、upscaledの無損失条件や検出器単体の精度ではない。保存済みPNGを復号し、画素ハッシュを照合してから最良の多対一色写像と周期誤差を再集計した。入力・出力・実測時間は変更していない。
同一入力3回の出力一致: 646/646件。

## 実生成コーパス

内蔵の再現は `tools/calibrate_pixelize_gates.py --repeats 1`、xpriteの原画診断は `uv run python tools/pixelize_generated_bench.py --xprite-root PATH --output build/pixelize-generated`。初回120秒で未完だった三面図3枚とhillsは、同じ入力を `--names` と `--timeout 600` で明示的に再試行し、最終判定を取得した。初回の時間切れもJSONに保持した。

16回の独立生成（ドット絵風13、非ピクセル対照3）。[全プロンプトと来歴](../tests/pipeline/corpus/generated/manifest.json)。モデルIDと出力条件を確認できないためlicenseはunknown。縮小していない。三面図の横幅を保持し、整数切り出しと可逆PNG圧縮だけで12MB以内にした。

| 入力 | 内蔵AUTO寸法 | 最終合否 | xprite寸法 | xprite分類 / 状態 |
|---|---|---|---|---|
| character_seed.png | [56, 56] | pass | [220, 223] | uncertain |
| item_lantern.png | [79, 79] | pass | [72, 76] | uncertain |
| tile_marsh.png | [79, 79] | pass | [104, 106] | uncertain |
| character_clock.png | [92, 92] | fail | — | error / pending |
| item_compass.png | [1004, 1004] | fail | — | error / pending |
| views_moss.png | [1254, 1004] | fail | — | error / pending |
| views_robot.png | [1254, 1004] | fail | — | error / pending |
| tile_roof.png | [39, 39] | pass | — | error / pending |
| item_shell.png | [63, 63] | pass | — | error / pending |
| character_diver.png | [58, 58] | pass | — | error / pending |
| tile_crystal.png | [19, 19] | pass | — | error / pending |
| views_beetle.png | [1254, 1004] | fail | [207, 163] | uncertain |
| item_flask.png | [146, 146] | pass | [49, 62] | uncertain |
| illustration_plant.png | [20, 21] | pass | — | error / pending |
| illustration_boat.png | [26, 26] | pass | — | error / pending |
| illustration_hills.png | [804, 804] | fail | — | error / pending |

[生成画像の検出値・合意指標・合否・出力ハッシュ](reference/pixelize_generated_results.json)。xpriteは原画に対する検出・復元だけの診断で、共通量子化・CyberSprite関門の接続はR1-D2に残す。処理が完了しない入力はunmeasuredとした。

外部ツールの `accepted: null` は未接続のCyberSprite関門を評価していないという意味で、合格ではない。外部の合意度・confidenceはCyberSpriteの千分率スコアと同じ尺度ではない。画像の採否や三面図の完成度は評価していない。

## 最終関門の再較正

`uv run python tools/calibrate_pixelize_gates.py --output build/pixelize-calibration` が(d)(e)のAUTO最終合否、(f)の誤固定格子と同一入力のAUTO対照を測る。`--code-root build/r1-d1-baseline/src` は変更前HEADをgit archiveしたsrcを読むための比較用入口。正本を書き換えず、全段階画像と最終のacceptedを記録する。

| 分類 | 件数 | 合格 | 拒否 | 測定エラー |
|---|---:|---:|---:|---:|
| d | 13 | 8 | 5 | 0 |
| d-nonpixel-control | 3 | 2 | 1 | 0 |
| e | 12 | 2 | 10 | 0 |
| f | 34 | 31 | 3 | 0 |
| f-auto-control | 17 | 16 | 1 | 0 |

(e)は再試行で完了したnoise_white_128も含めて10/12拒否（83.3%）。Fable R1-06の83%を再現し、95%には届かない。(f)は3/34拒否（8.8%）、AUTO対照は16/17合格。誤固定格子に対するsnap誤差は仕様どおり警告に留まるため、この関門だけで誤指定を排除できない。閾値を変更していないので、改善を主張しない。

[全測定値・個別関門・再試行](reference/pixelize_calibration_v5.json)。計測途中に修正したNone集計の問題は、保存済みの個別判定を `--summarize` で再集計した。時間切れによる拒否の水増しは行っていない。

値は版5の `src/cybersprite/data/pipeline_defaults.json` に確定して置いた。grid_score=[415,707]、fidelity=[466954543,233477271]、grid_cell_count=[12,96]、boundary_alignment=[80,250]、snap_fidelity=[3000,500]、grid.candidate_agreement=950。今回は現行値を維持した。95%の要件を達成したことにはしない。警告は合格に含め、上書きして受理するオプションは使っていない。

## 判断と限界

- 静止画の既定は内蔵AUTOのまま。既知の整数拡大にはupscaled、正しい格子を利用者が知る場合はfixed/targetを使う。
- アニメーションは共通格子・共有パレットを使う内蔵経路を既定に残す。proper-pixel-artのアダプターは動画APIを呼ばず、全フレームのmeshの最頻値を共有する設計だが、実ライブラリでの検証と順位付けは未完。
- 写真・イラストは明示targetを使う。PixelOEは選択候補として残すが、実測していないため今回の結果だけで推奨の既定へ昇格させない。
- Fixerの77%とxprite側の49.7%という依頼文中の数字は、別のベンチでの報告値であり、原画・判定条件が同一とは確認していない。今回は第三者のベンチ画像を使わず、Fixerも未実行なのでどちらかの追認・反証にはならない。
- 自作原画への偏り、疎な絵・単色の格子同定不能、生成画像に正解がないこと、サンプル数、CPU・OS負荷、外部のfloat実装の環境差が限界。関門合格は見た目の品質や生成物の採用を保証しない。
- registry/runnerへの外部アダプター接続は依頼どおりR1-D2に残す。Linuxの実行、全OSの推移バイナリ監査、実ライブラリ3系統のテスト、実アニメーションと写真の比較は未完。

## 変更前後の実CLI計測

同一端末・同じ非ピクセル12枚を、変更前commit `0fd9e26` のsrcと変更後のsrcで各3回、実際の `python -m cybersprite convert INPUT OUTPUT --preset ai --stages STAGES` に通した。両方とも10/12拒否（83.3%）、2/12合格で、各入力の3回の判定は一致した。

実行環境はWindows / CPython 3.12.10 / NumPy 2.3.4 / Pillow 13.0.0。PYTHONPATHと設定先を版ごとに分離し、同一の画像・引数・段階保存条件で測った。起動・読み込み・段階画像保存を含む。並行worktreeの負荷と空きメモリは一定でなく、下表の時間差をコードの高速化・退行に帰属させない。速度の改善は主張しない。

| 入力 | 変更前3回 ms | 前中央値 | 変更後3回 ms | 後中央値 |
|---|---|---:|---|---:|
| aa_circles_256.png | 29241.544, 19725.323, 20773.493 | 20773.493 | 9353.898, 13013.910, 10250.185 | 10250.185 |
| aa_vector_scene_384x256.png | 23113.680, 25012.298, 23469.432 | 23469.432 | 9834.888, 10169.482, 13440.041 | 10169.482 |
| bokeh_blur_256.png | 79595.887, 73186.316, 79310.078 | 79310.078 | 58000.233, 60281.856, 58323.582 | 58323.582 |
| brush_strokes_320.png | 49471.674, 47215.508, 48188.254 | 48188.254 | 33701.435, 42092.781, 31755.557 | 33701.435 |
| checker_rotated_aa_256.png | 28540.693, 24629.263, 22455.415 | 24629.263 | 8597.862, 9019.190, 10473.085 | 9019.190 |
| gradient_linear_256x192.png | 14111.276, 12719.748, 16255.327 | 14111.276 | 8758.879, 9372.414, 10030.291 | 9372.414 |
| gradient_radial_alpha_320x240.png | 14657.314, 17048.769, 15451.827 | 15451.827 | 9966.215, 7100.468, 8182.356 | 8182.356 |
| landscape_photo_512x320.png | 13648.361, 12828.611, 12940.826 | 12940.826 | 7902.862, 6357.774, 6245.889 | 6357.774 |
| noise_fbm_256.png | 17513.300, 16332.521, 19756.368 | 17513.300 | 8384.954, 8494.558, 7948.399 | 8384.954 |
| noise_white_128.png | 126636.362, 115205.667, 112560.125 | 115205.667 | 101092.036, 102601.394, 84262.964 | 101092.036 |
| sphere_soft_256.png | 7939.509, 6065.221, 5909.029 | 6065.221 | 8131.879, 5983.191, 7184.846 | 7184.846 |
| text_aa_384x128.png | 7578.660, 10574.108, 9732.845 | 9732.845 | 8860.206, 10017.940, 8487.818 | 8860.206 |

[丸めていない生値と入力SHA-256](reference/pixelize_cli_before_after.json)。品質の改善を主張する数値でもない。閾値は現行値を維持した。
