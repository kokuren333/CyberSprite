# e2e テスト #05 報告: 生成風ラスターの取り込みと手仕上げ

- 担当: Claude Opus 5.5（effort 中）／2026-11-12
- （サブエージェントの環境では REPORT.md を書き込めなかったため、本文はオーケストレーターが保存した。）

テストは完了し、絵は良い仕上がりになった。ただし `ai` プリセットの既定設定は、この入力に対して誤った格子で 11×11 の崩れた絵を作り、関門はそれを止めずにキャンバスに配置した。格子を `target` で指定し直すと、パイプラインは原画にかなり近い結果を出した。

## 成果物
- `slime.csprite/`（`source/SRC1/` に原画像・pipeline_report.json・段階画像 5 枚・result.png）
- `export/slime_x1.png`（32×32）、`export/slime_x4.png`（128×128）
- `source_input/slime_generated_like.jpg`（入力）、`slime_clean_32.png`（正解。取り込みには使っていない）、`PROVENANCE.txt`
- `convert/`（`convert` での比較結果と段階画像）、`work/`（入力の作成と検査のスクリプト、格子検出用の変種画像）

## 1. 作ったもの
- 題材: 緑のスライム。32×32、透明背景、透明＋8 色。
- 入力: 32×32 のスライムを自分で描き（`slime_clean_32.png`）、生成画像らしく劣化させた（347×347）: 近白の不透明背景 #F6F4EE に載せる → bicubic で ×10.84 の非整数拡大 → Gaussian blur 0.7 → 周期を持たない色ずれ ±6 と画素ごとのノイズ ±4 → JPEG q80（シード 20261112）。
- 来歴: provider `user`、Apache-2.0、生成器に送るはずだったプロンプトを記録した。
- 入力の作り直し: 最初の版は色ずれを 8px のタイル単位で入れており、JPEG の 8×8 ブロックと重なって格子検出を 8px に引っ張っていたので、周期のない色ずれに作り直した（最初の版は `work/variant_tile8drift_q80.jpg`）。
- キャンバスのピクセルは、すべて `import_image` と Op だけで入れた。

## 2. 手順
| rev | 内容 |
|---|---|
| 0 | `new slime.csprite --size 32x32`（既定パレット cs-circuit-16） |
| 1 | `import image … --preset ai --provenance <json>`。全関門を通過したが、結果は 11×11 の誤った格子（P1–P3） |
| 2 | `undo` |
| 3 | `import image --source SRC1 --preset ai --target '{"mode":"new_layer","name":"slime"}' --pipeline '{"grid":{"mode":"target","target_w":32,"target_h":32},"downsample":{"method":"center"},"background":{"mode":"key","color":[246,244,238],"tolerance":20},"palette":{"mode":"extract","max_colors":16},"cleanup":{"min_cluster":1}}'` → 合格して配置 |
| 4–5 | ノイズで分かれた近い色を統合（`replace_color` ×8） |
| 6 | `remap_palette remove_unused=true`（7 色） |
| 7 | `add_palette_colors ["#EF8A9A","#FFFFFF"]`（ピンクは入力画像の頬の中心から測った値） |
| 8–10 | 量子化で失われた頬 4px を描き戻し、目の光点 2px を白に、左下に照り返し 3px を追加 |
| 11 | 空の L1 レイヤーを削除 |

コミットは 11 リビジョン、変更 Op は 16 個（import 2 回を含む）、undo 1 回。`cleanup_pixels --dry-run` で目の光点が消されることを事前に確かめた。比較のため `detect-grid` 7 回、`convert` 17 回（うち 6 回は 16 進の背景色指定で失敗）。

## 3. 検証、書き出し、正解との比較
- validate: `ok: true`、エラー 0、警告 0、info 1（`Q-PIX-02` は目の光点で意図どおり）。Q-SRC 系の警告は出ていない（grid_score 895、override なし）。ただし rev1 の誤った取り込みのときも Q-SRC 系の警告は出なかった。
- 書き出し: 最後のコミットより後に実行し、×1 と ×4 で `validation_ok` と `verified` が true。×4 は ×1 の最近傍 4 倍と全ピクセル一致。

| 段階 | 透明/不透明の不一致 | 構造一致 | 結果 |
|---|---:|---:|---|
| 既定の ai（格子は自動検出） | — | 比較不能 | 11×11 に崩れた |
| target 32 ＋ 背景 auto ＋ 12 色 | 589 | — | 背景が抜けなかった |
| target ＋ 背景 key ＋ kcentroid ＋ 8 色 | 0 | 1006/1024 | |
| **採用設定（手仕上げの前）** | **0** | **1018/1024** | 違うのは頬 4px と目の光点 2px だけ |
| **手仕上げの後（最終）** | **0** | **1021/1024** | 残る 3px は意図して足した照り返し |

## 4. ツールの問題（重い順）
- **P1 [不具合・重大]** `ai` の自動格子検出が、非整数倍の拡大画像で正しい格子を見つけない。`pipeline detect-grid source_input/slime_generated_like.jpg` → `"cell_w": 32, "columns": 11, "grid_score": 773`。上位 5 候補に正しい N=32 が入らない。§11.3 の式で再計算すると正しい N の peak は 1085〜1148 で min_peak 1500 に届かない。ノイズのない最近傍 ×10.84 でも 8×8 になる（粗い N=8 が peak 13542、正しい N=32 は 11161 で harmonic_tolerance 85% に届かない）。CALIBRATION.md の (c) は正解を `target` で指定して測ったもので、自動検出で非整数倍を扱う経路は較正されていない。期待: 正しい N を選ぶか、選べないなら `grid_detected` を fail にして `target` を案内する。
- **P2 [不具合・重大]** 誤った格子の結果が全関門を通り、キャンバスに配置される（grid_score 773 は pass、fidelity と size `[[11,11]]` も pass、`accepted: true`）。検証の警告は 0 件。期待: 少なくとも warn（セル数が極端に少ない、格子が画像サイズを割り切らない等）。
- **P3 [設計・中]** `new` → `import --preset ai` と進むと、既存プロジェクトの既定 `palette.mode: project` により cs-circuit-16 に写像される。警告なし。
- **P4 [中]** `background.mode: "auto"` がノイズや JPEG の入った背景を抜かない（外周の色を完全一致で数えている）。警告は report の中にしかなく、envelope の warnings は空。
- **P5 [中]** `background.color` が `"#F6F4EE"` を受け付けない（`[246,244,238]` なら通る）。`ops describe import_image` の `pipeline` の中身が説明されていない。
- **P6 [品質・中]** `extract` がノイズで分かれた近い色に枠を使い、少数の目立つ色（頬 4px、目の白 2px）を落とす。近い色をまとめる手段も、アクセント色を保護する手段もない。
- **P7 [不具合・小]** 取り込みを undo しても来歴が戻らない（manifest の `placements` と `grid_scores` に取り消した取り込みが残る）。
- **P8 [小]** `remap_palette remove_unused` の mapping が、削除した番号を 0（透明）として返す。
- **P9 [小]** `import image --dry-run` が E_INVALID_ARGS。hint で `convert --stages` を案内してほしい。
- **P10 [小・仕様どおり]** `ai` の既定 `min_cluster` 2 が 1px のアクセントを消す。手順書に注意書きがあるとよい。

## 5. パイプラインの品質評価
- 既定のままでは使えない。格子を誤り、それを関門が止めない。
- 格子を `target`、背景を `key` で指定すれば結果は優秀（輪郭 100% 一致、構造 1018/1024）。ぼけた入力では downsample の `center` が kcentroid より良かった。
- 色の抽出は人手の後処理が前提。段階画像（特に stage1 の格子の重ね描き）で誤りに一目で気づけた。`convert --stages` でプロジェクトに触れずに設定を比べられるのも良い。

## 6. 使い心地: 3 / 5
Op、検証デルタ、書き出しの確認は快適。取り込みの入口にある格子の自動検出と背景の自動判定がどちらも黙って失敗し、関門が結果を通すので、段階画像を見ない利用者には誤った絵が合格として残る。

## 7. オーケストレーターの対応（2026-11-12）
P1〜P9 を修正タスク FIX-4（Codex）に回した。P10 は手順書（`skills/import-convert`）に書く。
