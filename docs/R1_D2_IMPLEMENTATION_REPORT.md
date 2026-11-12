# R1-D2 実装報告（2026-11-12）

3つの外部ピクセル化方式をR1-Cの同じentry point経路へ接続し、別環境で全候補を実測した。製品の既定方式と較正版5の閾値は維持した。95%の分類条件は未達のままである。

## 1. 実装

- `pipeline/external/steps.py` とpyprojectの `cybersprite.pipeline_steps`: `reconstruct.pixel_art_fixer` / `reconstruct.proper_pixel_art` / `reconstruct.pixeloe` の遅延factory。通常のenabled/disabledとAPI 1を使い、依存宣言・extra・MCP専用ツールは追加していない。
- `plugins/contracts.py` / `pipeline/plugin_steps.py`: 任意の `run_frames`、入力と同数の出力・指標の検査、共通寸法・共有パレットの検査、既知エラーのhint保持。PPAは全フレームを一度に渡し、D1の共通meshを維持する。
- `external/*` / `runner.py`: wrapper配布版と実ツール版を区別し、実効params・level_a=false・same-platformを報告とsourceへ保存。Fixerのstep_x/step_y/cols/rows/consensusをstage2へ公開。reconstructの関門は復元後を対象にし、`gate_scope` / `input_grid_evaluated=false` を明記する。
- PixelOEのCPU読込で任意のSlang backendを初期化しない。呼出スレッドだけに作用する一時finderを必ず除去し、Python loggerの状態も例外時に復元する。実CLIで観測したネイティブD3D12警告のstdout混入を回避し、MCPのプロセス全体のstdoutは差し替えない。
- `tools/pixelize_bench.py`: 全候補、3回の生時間・ハッシュ、再開、原寸生成診断、比較用comparison.pngと索引result.pngの分離。`demo_pixelizer_steps.py` は実CLI convert/importと実MCP Clientのimport/validate/export、Pillow復号とcore描画との照合。`pixelize_gate_tradeoffs.py` は閾値候補の追試。
- `tools/gen_grid_vectors.py` / `tests/vectors/grid/`: 新規7ベクタ。既存ファイルの上書きを拒否し、`--check` で照合する。単純な境界・位相・局所最大・補助信号を手計算で確認した。`src/cybersprite/mcp/contracts.py` は既存の長すぎる文字列行を分割しただけで、公開ツールは変えていない。
- `skills/import-convert/SKILL.md` と `PLUGIN_AUTHORING.md`: 実際の方式名、設定許可、各1例、共有フレーム契約、エラーと決定性の事実を追記した。既にA1で対応済みのdry-runを「未対応」としていた旧説明も現行仕様へ合わせた。

## 2. 受け入れ基準

| 項目 | 状態・証拠 |
|---|---|
| CLI / MCPから3方式を選択 | 成功。共通registryのみ。実CLI convert、import、MCP Client importを全方式で実行 |
| validate / export / decode | 6プロジェクト全てvalidate.ok=true、error=0、validation_ok=true / verified=true。PillowのRGBAとcore描画が一致し、方式ごとにCLI/MCP画素も一致 |
| 未導入時の導入案内・ライセンス注意 | 通常環境の回帰試験でE_PLUGINのhintをCLI/MCP末端まで保持 |
| PPAの複数フレーム | mockだけでなく、色の異なる実2フレームで共通mesh・共有色・共通出力寸法を確認 |
| 中立ベンチ | 323入力×5方式=1,615件。成功1,612件は各3回の画素ハッシュ一致。PPAのエラー3件は別途各3回再現 |
| 原寸生成(d) | 13枚＋非ピクセル対照3枚。4方式の60出力を確認。Xpriteの未検出4件は実行エラー、PixelOEのoracle比較16件は正解不明のため欠測 |
| 最終PNG自体の検証 | 合成1,612＋生成60=1,672ファイルをPillowで独立復号しRGBAハッシュ一致。索引画素もstage5と報告のCSPX1ハッシュへ照合 |
| R1-27 | Q・信号・局所最大の方向・補助信号・除算順序・min_peakの比較対象・確定値の所在を仕様化。7ベクタと手計算の試験9件 |
| 95%の関門 | 改善候補を検査したが正例を犠牲にするため閾値維持。未達をSPEC §11.9へ明記 |
| 最終全体試験 | 1680 passed / 11 skipped（374.22秒）。外部ツール環境は20 passed |

## 3. 検証

最終の `uv run pytest -q --tb=short` は **1680 passed / 11 skipped、374.22秒**。BLAS/OpenMPのスレッド数は1。skipは通常環境に意図して入れていない外部3方式の直接・登録経路6件と、Windowsのsymlink作成権限5件である。

`uv run ruff check .`、`uv run ruff format --check .`（217ファイル）、`uv run mypy src/cybersprite/core src/cybersprite/ops`（42ファイル）、`uv run python tools/gen_schemas.py --check`、`uv run python tools/check_repository.py`、`uv run python tools/gen_grid_vectors.py --check` は全て成功。別環境の `uv pip check --python ../_pixenv/Scripts/python.exe` も60 distributionの依存整合を確認した。

- 別環境: `../_pixenv/Scripts/python.exe -m pytest tests/pipeline/test_external.py tests/pipeline/test_pixelizer_steps.py -q --tb=short` は **20 passed、26.29秒**。Windowsネイティブstdout対策と例外時・他スレッドへの非干渉も含む。
- 通常環境で関連試験25 passed / 6 skipped、およびbenchmarkの再開を含む6 passedを先行確認した。skipは未導入3パッケージの直接・登録経路であり、理由に導入案内を含む。最終の全体結果とは別の途中結果である。
- 実デモ: `tools/demo_pixelizer_steps.py --input tests/pipeline/corpus/generated/character_seed.png --output build/r1-d2-demo-complete`。原寸画像を縮小せず、CLI convert/import、MCP Client import、validate、exportを実行。Fixer 28×28、PPA 28×30、PixelOE 32×32（動作確認用の明示指定、oracle=false）。3方式の実書出PNGを開いた。意匠の採否は判断していない。
- CLIのJSONを厳密に解析してstdout混入がないことを確認し、sourceのmethod/version/params/level_aと生成原画の来歴も読み戻した。未知の生成モデルは型付きSourceModelの識別子・hashを捏造せず、paramsに元のunknown表記を残した。
- 7つのgrid JSONは新規ベクタであり、既存の547較正ベクタとD1の測定記録は保持した。goldenは `tools/update_goldens.py --case m11_dmg --case m11_nds` だけで応答JSON 2件を更新し、変更前後の全diffを確認した。E1の新規ケースがE2の `updated_issues` / `new_points` / `new_points_count` を含んでいなかった統合差分である。DMGでは未使用色3→2、NDSでは2→1、両方で新規点(0,0)の1件が加わるだけ。canonical・PNG・画素の変更は0件。更新後のgolden試験は27 passed、2.96秒。

デモの警告は意図して残した。`W_PLUGIN_DETERMINISM` とそれに伴う `Q-SRC-01` は外部のsame-platform宣言のため、`Q-SRC-02` は生成原画の利用条件がunknownのためである。各projectのwarningは2件。infoの `Q-LYR-03` は既存の空の初期Layer 1、PPA/PixelOEの `Q-PAL-02` は後始末後の未使用抽出色であり、既存構造・palette lockを保つため残した。エラーは0件。

## 4. 判断記録

**I-1331〜I-1346**。接続方法、batch契約、エラー/実効params/来歴、ベクタと仕様、oracle表示、母数、閾値、隔離評価環境、PPA設定、最終ファイル検証、既定維持、生成診断回数、loggerとCPU import境界、粗い格子の独立反例、統合golden応答を記録した。

## 5. SPEC変更

§11.3の未定義記号・信号・整数演算・順位・例外、§11.9の未達と候補実験、§11.10の確定値/所在、§11.13の登録済み3方式・実効params・oracle・CPU境界・関門範囲、§15.2.1の任意batchと既知エラー保持を最小更新した。§11.4/11.7は既存のdownsample拡張と同梱reconstructの違いを明確にした。製品の既定方式・数値閾値・正本schemaは変更していない。

## 6. 依存とライセンス

製品の新規依存は **0**。pyprojectはentry pointだけの追加、uv.lockとthird_party台帳は未変更。今回の明示指示による評価用の `../_pixenv` にeditable CyberSpriteと外部ツールを導入した。これは許可外・未監査の推移依存を配布可能とする判断ではない。

| 実体 | 版 | 原文確認 |
|---|---|---|
| Pixel Art Fixer Python | ef376e57e1c272633ca2dbf5f29ec3fcf6596465、source SHAはruntime JSON | MIT。D1が取得した当該commitのLICENSE原文を再読してから導入 |
| proper-pixel-art | 2.0.0 | MIT。公式LICENSE原文と配布物の実LICENSEを確認 |
| PixelOE | 1.0.0 | Apache-2.0。公式LICENSE原文と配布物の実LICENSEを確認 |
| torch / torchvision CPU | 2.9.0+cpu / 0.24.0+cpu | BSD-3-Clauseの原文・同梱通知を公式CPU wheelから導入前に開いた。全バイナリツリーの配布承認ではない |
| Xprite評価用 | 0.1.2、Node 24.15.0 | MIT原文を再確認し、D1のリポジトリ外導入を再利用。全WASMツリーの配布承認ではない |

全60 Python distributionの実体版・原文ファイル名・SHA-256、CPU wheelのSHA-256、Xpriteと実効条件は [pixelize_runtime_versions.json](reference/pixelize_runtime_versions.json)。D1監査の原文156ファイルも導入前に再読した。av/OpenCVのFFmpeg通知、tqdmのMPL条件、SlangpyのLLVM例外/OFL等、torch/SciPy等の同梱通知は製品依存への採用を承認していない。CPUアダプターはSlangを初期化せず、モデルの重みも取得していない。

## 7. 既知の不足・意匠判断

- 関門の95%条件は未達。内蔵AUTOは(d)8/13合格、(e)10/12拒否、D1の(f)3/34拒否のまま。生成データを増やしたことと分類条件の達成を区別した。
- PPAはD1の初期倍率1であり上流既定2とは異なる。glyphsの3入力では高さ0のRGBAが返る。空画像を正本へ配置するfallbackは作っていない。
- PixelOEはCPUのみ。CPUモジュールは任意Slang選択を使わず初期化する。GPU利用や他のSlang経路は別プロセスで扱う。生成(d)にはoracle寸法がなく、PixelOEの数値順位を付けない。
- 実アニメーション・写真の正解や見た目の比較、GPU、Linux、全同梱バイナリの監査は未実施。Opusの意匠判断を要する見た目の採否は残す。
- この分岐に未統合のR1-A2による入力・作業量予算は別工程である。外部実装の中間処理（特にPixelOEのtarget×pixel_size）も統合時の予算確認対象に含める。本工程の動作確認を全パラメーターでの資源上限保証とはしない。

KNOWN_ISSUESへの転記案（同ファイルはこの工程で編集していない）:

| 項目 | 既知の制限 |
|---|---|
| 生成画像の取り込み関門 | 実生成16枚を追加・原寸診断済み。版5の既定AUTOは(d)8/13合格、(e)10/12拒否、(f)3/34拒否で95%条件未達。alignment下限308は(d)を2/13へ下げ、小格子＋残差の追加信号は小型正例8件を追加拒否するため不採用。既定・閾値は維持。外部reconstructの合格は復元後の関門であり入力格子の正しさを保証しない |

## 8. 参照したもの

AGENTS、SPEC、DECISIONS、IMPLEMENTATION_PROGRESS、src/README、両R1レビュー、D1/C報告、PLUGIN_AUTHORING、既存実装と試験を参照した。外部コードを転用していない。GPL/プロプライエタリ製品の実装・アイコン・サンプル・スクリーンショットは参照・使用していない。

以下はオーケストレーターがPROVENANCE_LOGへ転記できる。

| 日付 | 参照者 | 資料 | 得た事実 | 反映先 |
|---|---|---|---|---|
| 2026-11-12 | Codex / R1-D2 | [Fixerの公式README](https://github.com/Retro-Diffusion/pixel-art-fixer)、D1の当該commit LICENSE | 自身のベンチの77%という公表値、MIT、Python版の同定 | PIXELIZE_BENCH、runtime JSON |
| 2026-11-12 | Codex / R1-D2 | [PPA公式repo](https://github.com/KennethJAllen/proper-pixel-art)、2.0.0の実LICENSE・config/image API | MIT、上流初期倍率2とD1設定1の相違、共通mesh画像API | 比較の条件表示、batch試験 |
| 2026-11-12 | Codex / R1-D2 | [PixelOE公式repo](https://github.com/KohakuBlueleaf/PixelOE)、1.0.0の実LICENSE・torch/pixelize/logger/slang auto API | Apache-2.0、backend=torchはSlang contextを返さない経路、stdout loggerと任意import | CPU loader、protocol回帰、I-1343/I-1344 |
| 2026-11-12 | Codex / R1-D2 | [Xprite公式ベンチ表](https://github.com/rhinoc/xprite-pixelate#benchmark)、0.1.2の実LICENSE | MIT、AI suiteの83.6/49.7/72.2%と入力条件の違い | PIXELIZE_BENCHの公表値比較 |
| 2026-11-12 | Codex / R1-D2 | 公式CPU torch/torchvision wheel、評価環境の実LICENSE、[Slangpy公式文書](https://slangpy.shader-slang.org/en/stable/changelog.html)・実LICENSE・init、[MicrosoftのSetSDKVersion文書](https://learn.microsoft.com/en-us/windows/win32/api/d3d12/nf-d3d12-id3d12sdkconfiguration-setsdkversion) | CPU wheelの版・原文・hash、任意GPU初期化のstdout混入。SlangpyのDLLは関連する文字列だけ調査しコードは転用しない | runtime JSON、CPUのみの初期化 |

## 9. Design forks decided

| 分岐 | 選択・理由 | 根拠 |
|---|---|---|
| 別経路か既存拡張か | 同梱entry point＋通常許可表、reconstructとして接続。量子化は後段一度だけ | Fable R1-04、Codex §6の拡張案、R1-C/I-1204、I-1331 |
| frameごとか共通処理か | 任意batchを追加しPPAを一括実行。共通meshとpaletteを維持 | SPEC §11.12、D1/I-1302、I-1332 |
| unknown寸法を正解にするか | PixelOE oracleは合成だけ。生成(d)は欠測、利用者指定はoracle=false | Fable R1-06、D1の正解不明方針、I-1335/I-1342 |
| 閾値を厳しくして(e)だけ達成するか | (a)〜(c)と(d)への悪化があるため現行維持、未達を記録 | Fable R1-06、SPEC §11.9の正例優先、I-1337 |
| PPAを測定途中で調整するか | D1の初期倍率1を維持し上流既定との差を明示 | 今回の既存アダプター接続範囲、I-1339 |
| 既定方式を変えるか | 内蔵維持。oracle、未接続Xprite、条件の異なるPPAから一般的な優劣を断定しない | 今回の既定変更条件、I-1341 |
| native stdoutを全体で差し替えるか | CPUで不要な任意GPU importを当該スレッドだけ除外。stdoutハンドルは不変 | CLI/MCPのJSON契約と今回の実デモ、I-1343/I-1344 |

## 10. Deferred / not done

95%分類条件を満たす一般的な追加信号は得られなかった。ベンダーの元アセットでのベンチ再現、PPA初期倍率2の別較正、実アニメーション/写真の意匠評価、GPU、Linux、全バイナリ配布監査は行っていない。今回の表はD1アダプター条件の比較であり、ベンダー既定条件の再現ではない。第三者台帳とPROVENANCE_LOGへの統合、mainへの統合はオーケストレーターへ引き継ぐ。

## 11. Before/after numbers

性能最適化は行っておらず、速度の改善は主張しない。合成の同じ323入力を各3回測定した時間・中央値は [全記録](reference/pixelize_bench_r1_d2_results.json) と [比較表](PIXELIZE_BENCH.md)。availability importとCLI起動は時間の範囲外、PNGと共通処理は範囲内。並行負荷・メモリ不足のためD1との時間差をコードの改善率にしない。計測後のprotocol修正はCPU importと診断出力の境界だけで、backend=torchの画素計算条件を変えていない。

品質の前後は、現行維持なので(e)の拒否10/12=83.3%、(d)の合格8/13=61.5%のまま。候補の追加判定は次のとおりで、いずれも製品へ採用していない。

| 条件 | (e)拒否 | (d)合格 | 小型正例57条件の追加拒否 |
|---|---:|---:|---:|
| 現行 | 10/12 | 8/13 | 0 |
| alignment下限308 | 12/12 | 2/13 | 0（生成正例6件を失う） |
| 短辺12未満 | 12/12 | 8/13 | 53 |
| 短辺12未満かつ残差100超 | 12/12 | 8/13 | 8 |
| 入力短辺96以上・検出短辺12未満・残差300超 | 12/12 | 8/13 | 57条件では0。ただし完全復元するchecker反例2件を拒否 |

(d)(e)はD1の保存済み最終判定へ追加条件を適用し、小型57入力と独立した自作checkerのblur 2入力は実際にpipelineを通して測定した。後者は8×8へ完全復元して合格するが、spanで制限しても追加拒否になる（残差1216/908）。擬似判定の値を製品の改善済み合否とは呼ばない。生値は [閾値実験](reference/pixelize_gate_tradeoffs_small.json) と [独立反例](reference/pixelize_gate_coarse_counterexample.json)。D1と共通の内蔵/Xpriteの出力画素は **646/646同一**であり、画像goldenの更新で差を消していない。
