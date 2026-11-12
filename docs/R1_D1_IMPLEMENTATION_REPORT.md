# R1-D1 実装報告（2026-11-12）

R1-06に対し、外部ピクセル化の関数境界、ライセンス監査、生成入力、較正と中立ベンチを追加した。関門の95%要件は未達であり、版5にも `requirements_met: false` と明記した。runnerへの登録は依頼どおり行っていない。

## 1. 実装

- `pipeline/external/`: Fixer、proper-pixel-art、PixelOEの `run` / `available` / `describe`。入力と出力のRGBA検査、コピーによる入力保護、量子化無効、乱数・スレッド設定と復元。float実装は水準Aではない。Fixerは5項目の格子指標、properは共通meshと共有色の和集合を返す。PixelOEはCPUのoracle target sizeだけを使う。
- `pipeline_defaults.json` 版5、`args` / `grid` / `metrics` / `presets` / `runner`: 旧固定閾値4系統を外部化し、通常のpipeline設定で上書き可能にした。値は維持。変更は局所的で、Opや正本の保存経路は増やしていない。
- `tools/pixelize_bench.py` とNodeの評価ブリッジ: 自作原画17枚、9系列・19条件、再現可能なseed、共通減色・後始末、固定小数点Oklab指標、誤寸法とエラーの扱い、3回の時間と出力ハッシュを保存する。`pixelize_generated_bench.py` は生成原画の検出・復元だけを診断する。
- `tools/calibrate_pixelize_gates.py`: AUTOの最終判定、誤固定格子、AUTO対照を入力ごとの期限つきで測定する。時間切れは未測定。`--names` で明示的に再試行でき、`--summarize` で記録した判定を再集計できる。旧 `calibrate_pipeline.py` は版5以降はこちらへ委譲する。
- 生成コーパス16枚（13枚のドット絵風、3枚の非ピクセル対照、三面図3枚）、プロンプト・日付・切り出し・ハッシュ・unknownのモデル/出力条件を保存。PNG 11,603,213 bytes、縮小なし。

## 2. 受け入れ項目

| 項目 | 状態 |
|---|---|
| ライセンス監査表 | 4ツールとPython側44 distribution候補を記録。Python側43種類で原文を確認し、cuda-toolkitは原文が見つからず未確認。全同梱バイナリや全OSの承認ではない。非許可条件がある3ツールを依存宣言・vendorしていない |
| 3アダプターと試験 | 関数境界とモック試験を実装。実ライブラリ3系統は未導入で明示的skip。画像APIだけを使い、動画APIは呼ばない |
| corpus(d) | 16回の独立生成と来歴を追加。原画の見かけの倍率を正解とは扱わない |
| 中立ベンチ | 646件・各3回の実測済み（内蔵 / xprite）。未導入3系統の順位は付けない |
| 閾値外部化・AUTO再較正 | 版5で測定。生成(d)8/13合格、非ピクセル(e)10/12拒否、誤固定(f)3/34拒否、AUTO対照16/17合格。95%未達を隠さず記録 |
| 全体試験 | 1423 passed / 5 skipped |

## 3. 検証

- `uv run pytest -q --tb=short`: **1423 passed / 5 skipped、2315.04秒**。既存のWindows symlink権限2件と未導入の外部3ライブラリ。
- 最終の色写像（色ラベルの入替も含む）・期限集計・アダプターの対象試験: **13 passed / 3 skipped、4.50秒**。
- Ruff check / format、core+ops mypy（36ファイル）、schema drift、repository検査が成功。既存依存のlicense checkerはdev/mcp/guiの42件が成功。
- 中立ベンチ646件は各3回。出力の同一性646/646、保存済みPNGの画素ハッシュも照合した。実NGT診断の失敗や時間切れは成功率へ転用していない。

実CLI `convert --preset ai` で生成seed入力を56×56・25色（透明含む）へ変換し、`accepted=true` / `verified=true`。境界整合度213とsnap誤差832による警告2件は意図どおり残した。プレビューと実PNGを表示し、Pillowで独立復号した索引画素・出力ハッシュ・56×56寸法・4倍プレビューとの一致を確認した（実使用24色、パレット枠25）。PNG SHA-256は `4c6c88a4803416ee92b883bce49685b20d069ad6c7f2644110972adadb0604db`。結果と段階画像は `build/r1-d1-cli-final/`。正本を作成・変更する試験ではない。

既存の547測定ベクタ、255件の正例の完全一致、既存ゴールデンの画像や期待値を機械的に更新していない。ゴールデン変更は0件。

## 4. 判断記録

I-1301〜I-1309。依存の扱い、共有mesh、閾値維持、生成物の正解不明、色写像と欠測値、AUTOと誤固定の分離、期限と測定エラー、旧ベクタの保持、外部実装の実行条件を記録した。

## 5. SPEC変更

§2.3.2のPixelOEを利用者導入へ変更。§11.8に外部化した設定と意味、§11.9に(d)の正解不明とAUTO最終合否・欠測・版4参照の規則、§11.10に実際の415/707およびfidelity既定値、§11.13に登録前のアダプター契約と水準Aの範囲を追記した。

## 6. 新しい依存とライセンス

宣言・vendorした新規依存は0。`pyproject.toml` と第三者台帳は変更していない。FixerのPython参照版もOpenCV/SciPyを要求するためvendorしなかった。

評価用xprite 0.1.2（MIT）は公式npm tarballのLICENSE原文確認後、リポジトリ外の一時領域に配置してNode 24.15.0で実行した。npmの宣言runtime依存は0だが、これを全同梱WASM・ネイティブツリーの承認や製品への採用とは扱わない。候補のSPDX・版・URL・LICENSE原文のSHA-256・確認方法は `docs/reference/pixelize_license_audit.json`、判断は `docs/reference/PIXELIZE_LICENSE_AUDIT.md` にある。

## 7. 残る不足・意匠判断

- 95%の分類条件は未達。固定格子のsnap誤差を警告に留める既存契約も維持している。較正バージョン更新を性能合格とは扱わない。
- 外部ライブラリ3系統の実試験、GPU、実アニメーション・写真での比較、全OS/全バイナリの監査、Linuxでの実行は未実施。APIのモック試験を実ライブラリ試験として数えていない。
- properの共有meshは最頻の1フレームを使う方式で、上流の動画経路の同時最適化ではない。BLASのスレッド数は利用者設定のままであり、全バックエンド1スレッドを保証していない。
- registry/runnerへの外部接続、登録後の作業量制限・エラー封筒・来歴・段階画像の統合はR1-C後のR1-D2で行う。
- 生成物と段階画像の意匠・作画品質の採否は行っていない。Opusによる確認を残す。

## 8. 参照したもの・ログ用行

以下をオーケストレーターがPROVENANCE_LOGへ転記できる。GPL/プロプライエタリ製品の実装コード・画像・文言は参照していない。非許可パッケージはLICENSE/EULA文面だけを開いた。

| 日付 | 参照者 | 資料 | 得た事実 | 反映先 |
|---|---|---|---|---|
| 2026-11-12 | Codex / R1-D1 | Retro-Diffusion/pixel-art-fixer ef376e57e1c272633ca2dbf5f29ec3fcf6596465 のLICENSE、README、Pythonの公開APIとreconstruct（https://github.com/Retro-Diffusion/pixel-art-fixer） | MIT原文、detectの5指標とreconstructのRGBA契約、OpenCV/SciPy依存。コード転用なし | external/pixel_art_fixer.py、監査表、I-1301 |
| 2026-11-12 | Codex / R1-D1 | KennethJAllen/proper-pixel-art 2.0.0 のLICENSE、README、image/config API（https://github.com/KennethJAllen/proper-pixel-art） | MIT原文、画像APIとmesh、動画の遅延読込、依存av/OpenCV/tqdm。コード転用なし | external/proper_pixel_art.py、I-1302 |
| 2026-11-12 | Codex / R1-D1 | PixelOEの公式LICENSE/APIと1.0.0配布wheelのtorch/pixelize API（https://github.com/KohakuBlueleaf/PixelOE、https://pypi.org/project/pixeloe/1.0.0/） | Apache-2.0原文、CPU Torchのbackend・no_post_upscale・do_quant API、条件付きslangpy依存。コード転用なし | external/pixeloe.py、I-1309 |
| 2026-11-12 | Codex / R1-D1 | @xprite/pixelate 0.1.2の公式npm tarball、LICENSE、公開型定義（https://www.npmjs.com/package/@xprite/pixelate） | MIT原文、RGBAバッファの分析・復元API。外部一時領域での評価のみ | pixelize_bench.py、pixelize_xprite.mjs、実測表 |
| 2026-11-12 | Codex / R1-D1 | 44種類の導入候補のPyPIメタデータ・wheel LICENSE等（全URL/版/SHA-256は監査JSON） | OpenCV等のLGPL同梱表記、tqdmのMPL、CUDA EULA、未確認部分を識別。実装コードは開いていない | PIXELIZE_LICENSE_AUDIT.md、I-1301 |

## 9. Design forks decided

| 分岐 | 選択・理由 | 根拠 |
|---|---|---|
| optional extra / vendor / runtime検出 | 3系統ともruntime検出。非許可・未承認の推移依存を宣言しない | 今回のR1-D1 §1、SPEC §2、I-1301 |
| 複数フレームの共通格子 | 画像APIの最頻meshと共有色の厳密和集合。動画APIを呼ばず量子化は1回 | 今回のR1-D1 §2、SPEC §11.12、I-1302 |
| 閾値を厳しくして95%へ寄せるか | 現行値を維持し、未達の最終率を記録する | Fable R1-06、SPEC §11.9の正例優先、I-1303/I-1306 |
| 生成指示の倍率を正解にするか | 正解にしない。寸法と合否だけを記録 | Fable R1-06と今回のR1-D1 §4、I-1304 |
| タイムアウトを拒否に数えるか | 欠測とし、期限を変えた再試行の結果も保存する | Fable R1-06の最終判定による較正、I-1307 |

Fable §3やCodex §6と競合する新しい意匠・機種の設計判断は行っていない。

## 10. Deferred / not done

R1-D2の登録・統合は依頼による延期。実ライブラリ3系統の導入と比較は依存全体が許可条件を満たさず未実施。cuda-toolkitの原文と、Rust Fixer・Mac・全バイナリ内部のライセンスは未確認。xpriteの実生成原画16件は5件が出力され、7件が120秒のworker期限、3件が格子未検出、1件がI/Oエラーとなった。CyberSprite関門は未接続なのでaccepted=nullであり、11件を拒否には数えない。 改善に見せるための入力縮小・固定格子指定・関門上書きは行っていない。

## 11. Before/after numbers

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

ベンチの各系列の率・全646件の3回の生時間・中央値・出力ハッシュは `docs/PIXELIZE_BENCH.md` と `docs/reference/pixelize_bench_results.json`。自作原画への偏りと、JPEGの透明喪失、誤寸法の画素指標を欠測とした母数を明記した。速度の改善・退行や、未実行3系統の優劣を主張しない。
