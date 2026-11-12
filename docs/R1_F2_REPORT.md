# R1-F2 — Diffusers 依存監査と実GPU試行

2026-11-12、`fixr1-f2`。工学部分のみ。実GPU生成の受け入れ条件は未達。

## 実装

- `generate/backends.py`: ローカルfp16 safetensors variantの検出、生成用 `deterministic` パラメータ、Torchフラグ・CUBLAS環境変数の例外時復元とプロセス内の実行ロック、空extraに合う導入エラーのヒント。
- `tools/check_licenses.py`: regexのCNRI派生通知、tqdmのfiles:* MPL例外をメタデータより先に拒否。許可リストと既存例外は変更なし。
- `tools/audit_generation_stack.py`: 実環境の依存閉包、LICENSE原文/実ファイルSHA-256、ネイティブ一覧を保存する再監査用ツール。
- `tools/verify_generation_gpu.py`: 実CLIを子プロセスとして計測し、200ms間隔のnvidia-smi、PNGハッシュ、取り込み応答をリポジトリ外に保存する。試行中に判明したWindows venv launcherの子プロセス残留へ対処し、タイムアウトでは当該プロセスツリーを終了する。
- 既存偽パイプラインのfp16 variantとフラグ復元試験を拡張し、混在ライセンス固定ベクタと、既定スキップの `gpu` 試験を追加。生成契約試験の偽コマンド期限は180秒へ変更した。製品側の期限既定は変更なし。

## 受け入れ条件

- [x] 公式CUDA wheelと全33配布物の閉包を外部環境で監査し、選択肢(b)を確定。日本語監査表と利用者導入手順は `GENERATION.md`。
- [x] 主lockへの生成依存追加なし、ライセンス例外追加なし、重み/生成画像のコミットなし。
- [x] ローカルウェイトの探索とパス一覧、指定SDXL/LoRAの固定revision取得、ベースとLoRAの別承諾・実体ハッシュ記録。
- [ ] RTX 3080による実SDXL+LoRA画像の生成成功。
- [ ] 同一seedの3回実測・バイト比較、実生成物のai取り込み・validate・PNG書出しと復号、2〜3枚の見本。
- [ ] 最終全体試験の完走結果（後記に実行記録を記載）。

## 実測と制約

CPython 3.12.10、Windows 11、RTX 3080 / 20480MiB、driver 610.88。別環境は `<外部環境>/_genenv`。Torch 2.8.0+cu128、Diffusers 0.35.2、Transformers 4.57.1、Accelerate 1.11.0、Safetensors 0.6.2、Hub 0.36.0、PEFT 0.17.1。全推移依存は `GENERATION.md` の表とprivateのfreezeにある。

seed=42、1024×1024、30 steps、guidance=7、deterministic=true、Pixel Art XL LoRA有効の実CLIを試したが、**1800秒でタイムアウト、画像0枚**。ホストRAM16GBの空きは観測時約13〜270MiB。GPUへの到達を確認できず、停止箇所のスタックトレースはない。観測時のボード使用量は3MiB/GPU 0%。厳密なVRAMピークと生成時間の実測は得られていない。

これは生成時間1800秒という成功測定ではない。同一シード再現性と関門は未検証。速度改善は行っておらず、reviewの性能再現fixtureを使った前後3回測定の対象ではない。今回の互換修正を高速化として報告しない。

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

## 仕様変更・依存・ゴールデン

SPEC §12.4へfp16 variant、deterministicパラメータと復元、実体監査結果の保存を局所追記した。F1の登録項目・ComfyUIや共有Op/履歴/MCPは編集していない。

CyberSpriteへの新規依存は0。外部環境へ導入した配布物と、実際に開いたLICENSE原文の分類は `GENERATION.md` の全33行に記載。NVIDIA EULA、CNRI、MPL、LGPLを含むため配布用extraとして不合格。tokenizers wheelはLICENSE原文がなく、公式タグの原文を別に確認しただけでwheel原文確認済みとはしていない。第三者台帳は未編集。ゴールデン変更なし、更新器も実行していない。

## 未実施・引き継ぎ（Deferred / not done）

1. ホストRAMを確保して、実生成・3回のseed比較・ai関門・import/validate/export/decodeをやり直す。単にVRAM空きがあるだけではホストRAM不足を解消しない。
2. 停止原因の正確な箇所を診断する。RAM圧迫は観測事実だが、それだけが原因だと断定しない。
3. 2〜3枚の見本と実画像の確認・美的評価。画像自体が得られておらず、ビジュアル判断は行っていない。
4. 初回の契約試験ではWindows仮想環境の子コマンド期限超過後、stderr.logのWinError 32も出た。製品Command backendのプロセスツリー終了はF1/オーケストレーターの範囲として引き継ぐ。今回の手動GPUツール側の後始末は修正済み。
5. Linux実行、他GPU/他CUDA版、SDXL単一checkpointの実機確認は行っていない。

## 保持したローカル証拠

`<repo>/_private/gen-check/` に `dependency-audit.json`、`generation-freeze.txt`、`failed-attempt.json`、`local-weight-inventory.txt`、`settings/config.toml`、`settings/models.json`。画像はない。重みはHFキャッシュで、リポジトリ外に保持する。

## 参照・台帳への報告行

コードの移植なし。他製品のGPL/プロプライエタリなソース・素材・文言は参照していない。DiffusersのAPI確認ではApache-2.0原文を確認した0.35.2 wheelの `pipelines/pipeline_utils.py` と `pipeline_loading_utils.py` のdevice_map対応箇所だけを読んだ。device_mapの変更は実装していない。

オーケストレーター用PROVENANCE行（台帳への外部連携扱いの行はGENERATIONの監査表から転記可能。配布依存の追加ではない）:

- `2026-11-12 | R1-F2 | PyTorch公式cu128 Windows cp312 wheel 2.8.0、Diffusersスタック全33配布物のdist-info LICENSE/LICENCE/COPYING原文・native一覧 | 外部環境のみ、監査不合格(b)、原文ハッシュはprivate dependency-audit.json | Codex`
- `2026-11-12 | R1-F2 | https://pytorch.org/get-started/previous-versions/ 、https://docs.nvidia.com/cuda/archive/12.8.1/eula/index.html 、https://docs.nvidia.com/deeplearning/cudnn/backend/latest/reference/eula.html | CUDA wheel導入方法と同梱DLLの条件を確認、例外追加なし | Codex`
- `2026-11-12 | R1-F2 | https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/tree/462165984030d82259a11f4367a4eed129e94a7b 、https://huggingface.co/nerijs/pixel-art-xl/tree/8bf4a4d9ea283e00a51fafda8e0539f8248ea037 、https://huggingface.co/spaces/CompVis/stable-diffusion-license/blob/main/license.txt | カード/モデル条件、取得と個別承諾。重み非同梱 | Codex`
- `2026-11-12 | R1-F2 | https://github.com/huggingface/tokenizers/blob/v0.22.2/LICENSE 、Diffusers 0.35.2 Apache-2.0 wheel API箇所 | tokenizers不足原文の補足とdevice_map対応の確認。コード移植なし | Codex`

## 試験記録

- 初回 `uv run pytest tests/generate -q --tb=short`: 6 failed / 21 passed、661.82秒。5件は低空きRAM下の30秒子コマンド期限、1件は変更したエラー文の既存assertに対処した。期限超過後のWindows子プロセス残留も記録した。
- 最終の対象絞り込み試験: `uv run --no-sync pytest tests/generate/test_generation.py::test_diffusers_fake_pipeline tests/generate/test_generation.py::test_deterministic_generation_restores_flags_and_environment tests/generate/test_generation.py::test_availability_no_runtime_no_gpu_no_model tests/mcp/test_mcp_license_audit.py -q --tb=short` → **14 passed / 19.26秒**。
- Ruff check/formatは成功（176ファイル）。schema driftとrepository検査は成功。`uv run --no-sync mypy src/cybersprite/core src/cybersprite/ops` は36ファイルで診断0。全体試験の最終結果は実行完了後に追記する。
