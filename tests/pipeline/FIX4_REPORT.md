# FIX-4 実装報告

作業ブランチは `fix4-pipeline`。Windows / Python 3.12.10で検証した。
非整数拡大のauto検出、誤格子の診断、背景推定、パレット抽出、引数契約、source履歴を修正した。

## 変更と受け入れ状況

| 項目 | 状態 | 実装・検証 |
|---|---|---|
| P1 非整数auto | 達成 | `pipeline/grid.py`。有理ピッチの全候補に境界整合・整数三次位相相関・補間の傾き変化を評価。完全整数境界の補正を維持。校正(c)-autoは62/68（91.18%）、整数(a)は255/255（100%）。スライム原入力と7変種は8/8で32×32 |
| P2 関門と警告 | 達成 | `pipeline/metrics.py`、`runner.py`、`ops/ingest.py`。セル数・境界整合・候補間の僅差・スナップ誤差を診断。warnをenvelopeとsourceに保存し、`core/quality.py`のQ-SRC-01へ接続。旧11×11相当の指定格子も無警告では通らない |
| P3 既定パレット | 達成 | 既存projectパレット優先の既定を維持。未変更のcs-circuit-16などへの暗黙の写像にW_DEFAULT_PALETTEとextract/事前設定のヒントを返す |
| P4 背景auto | 達成 | `pipeline/downsample.py`。Oklab許容距離で外周支持数を集計し、外周連結部分だけ除去。60%支持がなければW_BACKGROUND_KEPTをenvelopeにも返す |
| P5 色とスキーマ | 達成 | `pipeline/args.py`。全節をpydanticモデルで定義し、未知キー拒否とField説明を共有。background・固定パレット・outline・palette.protectでRGB/RGBA配列とhexを受理。import_imageのdescribeとconvertの引数生成に接続 |
| P6 抽出とアクセント | 達成 | `pipeline/quantize.py`。枠を割り当てる前に近似色を実在代表色へ統合。2〜4pxかつ全体の1/64以下で他色から十分離れる色を予約。明示protectは最近の実在色を予約し、後始末にも保護番号を渡す。決定性・色予算・入力内の実在色だけを使うことをテスト |
| P7 undo/redo | 達成 | `core/sources.py`とトランザクションの最小接続。配置・パイプライン指標を原子的に履歴保存・復元し、原画とsource IDは保持。旧履歴では有効配置をジャーナルから復元し、戻せない指標をundone_conversion_metricsと警告で明示。履歴の期限も正本側と揃える |
| P8 unused mapping | 達成 | `ops/palette.py`と共通結果型。削除番号はnull。実際に使用する番号の写像は従来どおり |
| P9 dry-run | 達成 | `.cybersprite/previews/dry/`へ全段階・結果・報告だけを書く。source記録・原画複製・配置・正本変更なし。実CLIでも確認 |
| P10 再校正・実入力 | 達成 | 547件を再計測しcalibration=4。元のgrid_score fail/warn=415/707、fidelity=466954543/233477271は維持。正解優先と負例分離の限界をCALIBRATIONに記録。スライムは実CLIで取り込み・検証・書き出し・PNG再復号・目視確認 |

仕様の変更は§11.3〜§11.5、§11.8、§11.9、§11.11の上記アルゴリズムと契約の補足。
判断は **I-851〜I-858**。共通トランザクション、Q-SRC、palette結果型、校正器とMCPシナリオ2の期待値は、依頼されたP2/P7/P8/再校正を成立させるための最小の範囲外接続である。

## 校正と限界

正本は[CALIBRATION.md](CALIBRATION.md)、全値は`calibration_metrics.json`。
(c)-autoは17原画を3.5・5.37・7.9・10.84倍にbicubic拡大し、JPEG q95/subsampling=0で圧縮する。
透明部分は近白色に合成してから拡大する。正解の列数・行数は検出器へ渡さない。

未検出または誤検出の6件は、sparse_fireflyの3.5・5.37倍とterrainの4倍率である。
疎な点や元画像の粗い周期には曖昧さが残るため、必要ならfixed/targetを使う。
生成風スライムは自作の合成入力であり、本物の生成バックエンドの分類(d)を満たしたとは扱わない。
Linux実行はこの環境では未実施で、既存方針I-007どおりCI側の確認が残る。

## 実CLIとファイル確認

再現コマンドは `uv run python tests/pipeline/acceptance_fix4.py`。
成果はgit管理外の `.venv/fix4-review/run-*/` に保存する。
入力はe2eからコピーしたコーパスを使い、e2eディレクトリは変更していない。

既定 `new --size 32x32` → `import image --preset ai` の検出は次のとおり。

| 指標 | 結果 |
|---|---:|
| 列数・行数 | 32×32 |
| セル純度grid_score | 895 |
| 元のpeak | 1148 |
| normalized_score | 6336 |
| 境界整合度 | 240 |
| スナップRGB平均二乗誤差 | 334 |

関門は境界整合のみwarn、残り13件はpass。W_DEFAULT_PALETTEもenvelopeに出る。
既定の背景keepとprojectパレットを自動変更する仕様にはしていない。

| 設定 | RGBA完全一致 | 正解パレット最近色による一致 | 透明/不透明不一致 |
|---|---:|---:|---:|
| ai既定・既存の既定パレット | 0/1024 | 370/1024 | 589 |
| auto背景＋extract、その他ai既定 | 589/1024 | 955/1024 | 24 |
| auto背景＋center＋extract 8色・merge_distance=3000＋cleanup.min_cluster=1 | 588/1024 | 1021/1024 | 1 |

最近色比較は評価専用であり、正解色を取り込みに使っていない。JPEGの色誤差があるため、RGBA完全一致と形・色分類の一致を区別する。
cleanup.min_cluster=2の既定は維持しており、細部を保持したい入力では1またはprotectを明示する。
これは絵の仕上げ判断を行ったという意味ではなく、正解データとの比較結果である。

段階画像5枚と実出力PNGを開いて確認した。全書き出しでvalidation_ok/verified=true、実ファイルの再復号と正本レンダラの画素も一致した。
境界整合の警告はしきい値250に対して実測240なので意図して残す。
既定パレットの警告は既定を維持する判断I-852によって残す。Q-SRC-01もこの警告来歴を反映する。
意匠の変更・ビジュアル判断は行っていない。

## 検証

| コマンド・確認 | 結果 |
|---|---|
| `uv run --extra mcp --extra gui pytest -q --tb=short` | **1336 passed / 2 skipped、283.73秒**。スキップは既存のWindowsシンボリックリンク権限2件 |
| 最終の型注釈・既定値factory整理後の `pytest tests/pipeline/test_fix4.py tests/pipeline/test_grid.py -q --tb=short` | **22 passed** |
| source履歴・トランザクションの回帰 | **32 passed** |
| MCPシナリオ2、in-process/stdio | **2 passed** |
| Ruff check/format、schema drift、repository、diff check | 成功 |
| `tools/check_licenses.py --include-dev --extra mcp --extra gui` | 成功。追加依存なし |
| 任意のmypy | 変更前を同じ環境で検査すると87件、変更後86件。パスと行番号を正規化した差分で**新規0件**。既存エラーは未解消 |
| PYTHONHASHSEED=7/319 | 非整数スライム変換の全段階PNG・result.png・reportがバイト一致 |

通常ゴールデンは `tools/update_goldens.py` で0変更。
MCPシナリオ2は既存の `uv run python -m tests.e2e.replay --case scenario2` 入口から同じ更新器を呼び、3ファイルだけ更新した。
30色から6色への近似色統合、正本の画素配列、レンダリング前後、実出力ハッシュを確認してから更新している。

## 依存・参照・残件

新規依存はない。`pyproject.toml`、`uv.lock`、第三者台帳は変更していない。
参照したのは仕様・既存の自作コードとテスト・e2e報告・自作入力の来歴のみ。
他製品のコード・文書・素材、外部OSS実装、外部Web資料は参照していない。
新しい意匠判断のTODOはない。元のP10（1pxアクセントとcleanup既定の注意）の制作手順書への反映はオーケストレーター側の担当。
