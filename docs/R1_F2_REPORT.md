# R1-F2 — Diffusers依存監査と実GPU検証

2026-11-12、`fixr1-f2`。RTX 3080で実SDXL+Pixel Art XL LoRA生成、同一seedの3回一致、ai取り込み・PNG検証まで完了した。依存監査は選択肢(b)で、配布用extraは空の予約名を維持する。詳細な33配布物の版・原文判定・導入手順・モデルrevisionは [GENERATION.md](GENERATION.md)。

## 実装（what implemented）

- `generate/backends.py`: ローカルfp16 safetensors variant検出、明示的なdeterministic設定、Torch/cuDNN/TF32/CUBLAS状態の例外時復元。highest/high/mediumの精度名を保持し、プロセス全体の状態の競合をRLockで防ぐ。空extraに合う未導入時のヒントへ修正。
- `tools/check_licenses.py`: regexのCNRI派生通知とtqdmのfiles:* MPL混在をメタデータより先に拒否する。許可リスト・既存例外は不変。
- `tools/audit_generation_stack.py`: 依存閉包、実LICENSE原文と実ファイルSHA-256、native一覧を外部JSONへ保存する。
- `tools/verify_generation_gpu.py`: 実CLI子プロセス、200ms間隔のnvidia-smi、PNGハッシュ、時間・取り込み結果を外部へ記録する。Windows launcherの子残留を避けるタイムアウト時のプロセスツリー終了も実装。
- fake pipeline回帰試験、状態復元の固定ベクタ、混在ライセンス試験、明示envでのみ動く`gpu`試験を追加。既存Command偽子プロセスの試験期限のみ30→180秒へ変更した。製品の既定期限は変更なし。

## 受け入れ条件（acceptance）

- [x] 外部環境の公式CUDA wheelと全33配布物を監査し、選択肢(b)を記録。主lockへ生成依存・例外を追加していない。
- [x] 既存重みのパスを探索し、指定公式SDXL/LoRAがないため固定revisionをHFキャッシュへ取得。個別承諾・実体ハッシュを記録。
- [x] RTX 3080で実CLI `gen run`、seed=42、1024×1024、30 steps、guidance=7、LoRA、deterministic=trueを3回実行し、同一PNGバイトを確認。
- [x] 実SRC1をaiプリセットで取り込み、全14関門合格。唯一のフレーム0の変更後プレビューを確認。
- [x] validateはok、error/warning=0。PNG書き出しはvalidation_ok/verified=true。最終ファイルを独立Pillowと独自デコーダで復号してRGBA一致、表示でも確認。
- [x] privateに原画像・段階画像・3つの小さな見本を保存。追加GPU試験の別画像は孤立画素1件の拒否例として保存し、関門を変更していない。
- [x] 最終状態の全体試験1427 passed / 3 skipped、必須静的検査も成功。

## 実機結果（before/after numbers）

Windows 11 / CPython 3.12.10 / RTX 3080 20480MiB / driver 610.88 / CUDA runtime 12.8。外部環境は`<外部環境>/_genenv`。Torch 2.8.0+cu128、Diffusers 0.35.2、Transformers 4.57.1、Accelerate 1.11.0、Safetensors 0.6.2、Hub 0.36.0、PEFT 0.17.1。

| 実CLI回 | 秒（起動・実体ハッシュ・ロード・推論・保存を含む） | 観測VRAMピークMiB |
|---|---:|---:|
| 1 | 540.420334100003 | 13342 |
| 2 | 446.6919937000057 | 13342 |
| 3 | 337.9346435000043 | 13342 |
| 中央値 | 446.6919937000057 | 13342 |

3回の原PNG SHA-256はすべて`1a7c4e608d08eaae66f1502d4a4a70261ef51552d76a6c43032fefe179cfa395`。厳密な決定的アルゴリズムとTF32無効を明示したこの機械上の結果で、他GPU/版へ一般化しない。200msのボード標本最大はallocatorの厳密ピークではない。実体ハッシュが要求ごとに4回走る現経路も時間に含み、純推論速度を表さない。下降する3値を最適化効果と扱わない。性能改善は主張せず、変更前後の並行性能3回ずつの比較値はない。

最終PNGは128×128、33パレット/32使用色、16704bytes、SHA-256 `0045bc88751cf4ecbb587f5ea22b4ca8fa96542e2277a00f4115f4cd98871e45`、画素SHA-256 `b6ea18d4c632927ace3a776d47cdd08b39df5fc2990809d1bf72217113489d94`。警告0。info Q-LYR-03は自動作成された空L1の通知として意図どおり保持した。追加の生成試験は1 passed / 329.72秒、negative_promptなしの画像はorphans=1で取り込み拒否、他13関門pass。UNetのみのLoRAに対するtext encoder通知2件は2166キーの内容と一致し、隠していない。

初回1800秒タイムアウト（空きホストRAM約13〜270MiB）は成功時間と混同しない。後のCUDA FP16行列演算プローブと再試行生成は成功したが、初回の原因をRAMだけと断定しない。他アプリは強制終了していない。

## 設計分岐（Design forks decided）

| 判断 | 選択と理由 | 根拠 |
|---|---|---|
| I-1641 | (b)、空extraを維持。regex CNRI、certifi/tqdm MPL、vendor LGPL、NVIDIA DLLを例外承認しない | Fable §3.6-4、SPEC §2.1、既存I-014/I-708 |
| I-1642 | 公式cu128の具体的な旧版スタックを別環境で監査・試行。PEFTも含む | Fable §3.6-4、今回のスコープ |
| I-1643 | ローカルのfp16 variantを自動検出し、単一ファイル経路は既存契約を維持 | 指定のfp16取得物に無印の重みがないため。F1のモデル登録項目へ依存しない |
| I-1644 | 決定的アルゴリズムは明示の生成オプションとし、スコープ終了時に復元。プロセス内で直列化 | Fable実機検証とSPEC §6.6の生成非決定性境界 |
| I-1645 | SPDXメタデータと同梱原文の判定を区別し、混在通知を固定テスト化 | SPEC §2.2、classifierだけの誤承認防止 |
| I-1646 | GPU試験は明示envと外部保存先・事前承諾を要求 | Fable §3.6-4、CIにGPUなし、重み非同梱 |
| I-1647 | 偽コマンド試験だけ期限180秒、期限の意味は例外注入で検査 | 低空きRAM時に通常のPython/NumPy起動が30秒を超えたため |
| I-1648 | 同一プロセスのDiffusers生成をRLockで直列化 | プロセス全体のTorchフラグを並行呼出しが誤って復元しないため |
| I-1649 | 行列演算の精度名を保存・復元し、3状態で正常/例外の試験を固定 | PyTorch 2.8ではhigh/mediumがともにTF32有効へ対応し、真偽値だけではmediumを保てないため |

## 仕様変更・新規依存・ゴールデン

SPEC §12.4へfp16 variant、deterministicオプションと状態復元、監査記録を局所追記した。F1のモデル登録/ComfyUI、他のOp・履歴・MCPは変更していない。記録した判断は **I-1641〜I-1649**。

CyberSpriteへの新規依存は0。外部にだけ導入した全33配布物の名前・版・SPDX/混在判定・LICENSE確認方法はGENERATIONの表に記載。NVIDIA EULA、CNRI、MPL、vendor LGPLが許可外。tokenizers wheelは原文欠落、公式タグ原文の補足確認と区別した。`third_party/THIRD_PARTY.md`は未編集。ゴールデン差分0、更新器も実行していない。

## 未実施・引き継ぎ（deferred / not done）

1. Linux、他GPU/CUDA/モデル版、SDXL単一checkpoint実機は未検証。このWindows環境のみの結果。
2. 生成直列化の並行スループット/VRAMへの前後比較は未測定。プロセス全体フラグを守る正しさの変更で、性能改善を主張していない。
3. 実生成画像のCIコーパス化・関門再較正は範囲外。本作業では画像コミットは禁止されており、privateの合格/拒否例を引き渡す。
4. 最初のCommand偽子プロセス期限超過でWindows子残留によるstderr.log WinError 32を観測した。手動GPUツールの終了処理は対処済み。製品Commandバックエンド側はF1/オーケストレーターへ引き継ぐ。
5. デザイン・作画品質の判断はしていない。工学的な入出力、画素・ファイルの一致と関門結果だけを確認した。オーケストレーターによる見本の美的確認は別途必要。
6. 今回の外部導入は配布依存への承認ではない。別版を採用する場合は全推移依存とnativeを再監査する。

## ローカル証跡

`<repo>/_private/gen-check/` に依存原文・freeze・失敗記録・モデル探索パス・個別承諾設定・Torch probe・成功3回の`retry/summary.json`とCLIログ・生成project/source/stage画像・`export-proof.json`を保存。`examples/chest-seed42.png`が合格した最終PNG、`chest-seed42-stage2.png`が中間段階、`chest-no-negative-rejected-stage5.png`が未配置の拒否例。重みはHFキャッシュだけに保持する。

## 参照・台帳への報告行

コードの移植なし。他製品のGPL/プロプライエタリなソース・素材・文言は参照していない。DiffusersのAPI確認ではApache-2.0原文を確認した0.35.2 wheelの `pipelines/pipeline_utils.py` と `pipeline_loading_utils.py` のdevice_map対応箇所だけを読んだ。device_mapの変更は実装していない。

オーケストレーター用PROVENANCE行（台帳への外部連携扱いの行はGENERATIONの監査表から転記可能。配布依存の追加ではない）:

- `2026-11-12 | R1-F2 | PyTorch公式cu128 Windows cp312 wheel 2.8.0、Diffusersスタック全33配布物のdist-info LICENSE/LICENCE/COPYING原文・native一覧 | 外部環境のみ、監査不合格(b)、原文ハッシュはprivate dependency-audit.json | Codex`
- `2026-11-12 | R1-F2 | https://pytorch.org/get-started/previous-versions/ 、https://docs.nvidia.com/cuda/archive/12.8.1/eula/index.html 、https://docs.nvidia.com/deeplearning/cudnn/backend/latest/reference/eula.html | CUDA wheel導入方法と同梱DLLの条件を確認、例外追加なし | Codex`
- `2026-11-12 | R1-F2 | https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/tree/462165984030d82259a11f4367a4eed129e94a7b 、https://huggingface.co/nerijs/pixel-art-xl/tree/8bf4a4d9ea283e00a51fafda8e0539f8248ea037 、https://huggingface.co/spaces/CompVis/stable-diffusion-license/blob/main/license.txt | カード/モデル条件、取得と個別承諾。重み非同梱 | Codex`
- `2026-11-12 | R1-F2 | https://github.com/huggingface/tokenizers/blob/v0.22.2/LICENSE 、Diffusers 0.35.2 Apache-2.0 wheel API箇所 | tokenizers不足原文の補足とdevice_map対応の確認。コード移植なし | Codex`
- `2026-11-12 | R1-F2 | https://docs.pytorch.org/docs/2.8/generated/torch.set_float32_matmul_precision.html 、https://docs.pytorch.org/docs/2.8/generated/torch.get_float32_matmul_precision.html | highest/high/mediumとTF32の対応、復元APIを確認。コード移植なし | Codex`

## 試験記録

- 初回generate組: 6 failed / 21 passed / 661.82秒。5件は低空きRAM時の30秒起動期限、1件は未導入ヒントの既存assert。試験用期限と文面を修正し再検証した。
- 最終対象回帰: **22 passed / 1 skipped / 10.38秒**（復元3精度状態×環境2×正常/例外、fp16、未導入、ライセンス、既定GPU skip）。
- 明示GPU: 外部Pythonで`python -m pytest tests/generate/test_gpu.py -q --tb=short` → **1 passed / 329.72秒**。
- 最終全体 `uv run pytest -q --tb=short`: **1427 passed / 3 skipped / 364.90秒**。skipは明示GPU試験1件と既存Windowsシンボリックリンク権限2件。精度名復元の強化後の全コードを含む。途中全体1419 passed / 3 skipped / 2723.82秒は参考記録で、速度改善比較には使わない。
- `uv run ruff check .` / `uv run ruff format --check .`: 成功、176ファイル。
- `uv run mypy src/cybersprite/core src/cybersprite/ops`: 成功、36ファイル、診断0。
- `uv run python tools/gen_schemas.py --check` / `uv run python tools/check_repository.py`: 成功。
- `uv run python tools/check_licenses.py --include-dev --extra mcp --extra gui`: 成功、42配布物。主環境の監査であり、外部GPUスタックの不合格を上書きしない。
- ログはGit管理外の`build/r1-f2/*-latest.txt`、実GPU試験は`gpu-test-final.txt`。WindowsのみでLinuxは未実行。

## コミット

- `d7d3a5f` — dependency audit and local fp16 support.
- `799c69b` — exact matmul precision restoration.
- 最終の文書・実測記録は`R1-F2: record successful GPU generation and final verification`にまとめる。main統合はオーケストレーターが行う。
