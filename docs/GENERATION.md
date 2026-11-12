# 画像生成と取り込み

生成は `source/SRC<n>/` に原画像と来歴を保存する。キャンバスに配置するには、同じプロジェクトに `import image --source SRC<n>` を別途実行する。生成によって `project.json` とリビジョンは変わらない。プロジェクトの正本がまだなくても生成できる。

## 設定と承諾

通常の設定先は Windows の `%APPDATA%/cybersprite/config.toml`、その他は `$XDG_CONFIG_HOME/cybersprite/config.toml`（未指定なら `~/.config/cybersprite/config.toml`）。`CYBERSPRITE_CONFIG_DIR` を指定すると、そのディレクトリ直下の `config.toml` と `models.json` を使う。テストや分離した環境のための起動時設定であり、CLI/MCP のツール引数から設定先は変更できない。

モデルは利用者自身が取得する。設定例の `example/base` は識別子の例であり、推奨モデルやライセンス確認済みモデルではない。`license` は実際に読んだモデルカードに合わせて記入する。重みもアダプタもリポジトリ・wheel に含めない。

```toml
[generators.command.local]
program = "C:/tools/generator.exe"
args = ["--model", "C:/models/local-model.gguf", "--prompt", "{prompt}",
        "--negative", "{negative_prompt}", "--width", "{width}", "--height", "{height}",
        "--seed", "{seed}", "--count", "{count}", "--out", "{out}"]
license = "生成物の利用条件。実際の規約と版を記入"
timeout_seconds = 600

[generators.command.local.model]
id = "example/base"
local_path = "C:/models/local-model.gguf"
license = "モデルカードのライセンス名を記入"
source_url = "モデルカードの入手先を記入"

# コマンド側で使用するアダプタは、引数に加えてここにも記録する。
# [[generators.command.local.model.adapters]]
# id = "example/adapter"
# local_path = "C:/models/adapter.safetensors"
# license = "アダプタ自身のライセンス名を記入"
```

モデルの `local_path` が相対パスなら設定ディレクトリ基準。実体がない設定では生成を始めない。ファイルは通常の SHA-256、ディレクトリは `CSMODEL1\n` に続けて相対パスの昇順で「UTF-8 相対パス、NUL、ファイル SHA-256 の32バイト」を連結した SHA-256 で識別する。ディレクトリには実行時に書き換わるログや出力を入れない。

```text
uv run cybersprite gen backends
uv run cybersprite gen accept-license command:local
uv run cybersprite -p sample.csprite gen run --backend command:local --prompt "説明" --width 64 --height 64 --seed 42 --idempotency-key sample-1
uv run cybersprite -p sample.csprite import image --source SRC1 --preset ai
```

`gen accept-license` の代わりに `gen run --accept-model-license` でも、設定済みモデルと全アダプタの承諾を記録できる。Diffusers のモデルは設定の別名を `gen accept-license <別名>` に渡す。名前・ライセンス・実体ハッシュが一致する承諾が `models.json` にある場合だけ生成する。ベースとアダプタを別々の行に保存し、どちらかの実体やライセンスが変われば再承諾が必要。エラーの `message` と `details.models` に承諾が必要な名称・ライセンス・ハッシュを示す。MCP ではサーバ起動前に CLI で承諾する。

同じ `idempotency_key` と引数を再実行すると、保存済み source を返す。異なる引数で同じキーを再使用すると拒否する。キーは source 来歴の `params._generation` に保存され、正本の履歴とは独立する。元画像が失われた・変更された場合も再実行を拒否し、復元を促す。

## 外部コマンド

バックエンド名は `command:<設定名>`。コマンド・引数・タイムアウトは利用者の設定だけで定義する。`params` は空のオブジェクトだけを受け付け、コマンドや追加オプションをツール引数から注入できない。置換名は `{prompt}`、`{negative_prompt}`、`{width}`、`{height}`、`{seed}`、`{out}`、`{count}` のみ。要素ごとに置換し、シェルを介さず引数配列で起動する。

`{out}` は一時出力ディレクトリの `output.png` の絶対パス。複数生成するコマンドは、そのディレクトリ以下にちょうど `count` 枚を書き出す。PNG/JPEG/WebP/BMP をファイルパスの昇順で収集する。枚数・寸法・復号・出力先の実体パスを確認し、成功した画像だけを source に複製する。画像ごとの来歴にはコマンドに渡した共通シードを記録する。コマンド側で画像ごとに派生シードを使う場合は、その意味をコマンド定義の管理者が把握する。

コマンドのモデル指定と `model` / `model.adapters` の記録を一致させる責任は設定の管理者にある。コマンド雛形の SHA-256 も `params.command_template_sha256` に記録する。タイムアウトは `E_TIMEOUT`、非ゼロ終了や出力不正は `E_GENERATION_FAILED`、実行ファイルがない場合は `E_BACKEND_UNAVAILABLE`。

## Diffusers 接続

### BYOW 登録（H-21）

重みは利用者が取得し、CyberSprite にはメタデータだけを登録する。`gen register-model` は人間用 CLI 専用で、MCP に登録ツールはない。既存名への上書きは拒否する。設定先は前述の `CYBERSPRITE_CONFIG_DIR` に従い、既存の設定とコメントを保って追記する。

```text
uv run cybersprite gen register-model C:/models/base.safetensors --name my-base --kind checkpoint --base-model unknown --license CreativeML-OpenRAIL-M --license-url https://example.invalid/base-license --commercial-use yes --source-url https://example.invalid/base --note "取得時の版を記入"
uv run cybersprite gen register-model C:/models/adapter.safetensors --name my-lora --kind lora --base-model my-base --license CC-BY-NC-4.0 --commercial-use no --source-url https://example.invalid/adapter
uv run cybersprite gen models
uv run cybersprite --format text gen models
```

URL は説明用の架空 URL。実際に確認した入手先・条件へ置き換える。`kind` は `diffusers-dir` / `checkpoint` / `lora` / `vae` / `controlnet`。表示名、ベースの登録名（不明なら `unknown`）、実体パス、入手先、ライセンスとその URL、商用利用可否（`yes` / `no` / `unknown`）、メモ、登録時 SHA-256、登録日時を保存する。ディレクトリには既存の I-703 のハッシュ方式を使う。モデル一覧は登録時のメタデータを読み、GPU ランタイムの起動や重み全体の再ハッシュを行わない。生成と承諾では実体を再ハッシュし、内容変更後の古い承諾を流用しない。

バッジは OpenRAIL 系が **commercial OK with use restrictions (not OSI)**、NC が **non-commercial only**、未知・独自条件が **needs review**。`commercial_use` の申告値も併記する。OpenRAIL の表示でも `unknown` なら確認が必要。LoRA 自身の条件だけで判断せず、参照するベースモデルの条件も表示・保存する。ベースは先に登録し、循環参照は作らない。旧設定で省略された条件は `unknown` として扱う。

登録された VAE / ControlNet / LoRA を単体で生成パイプラインとして使用できることを保証するものではない。既存 Diffusers バックエンドの読み込み方法・`adapters` 設定は維持する。GPU での対応方式は R1-F2 の確認対象である。

```toml
[generators.diffusers.models.local]
id = "example/base"
local_path = "C:/models/downloaded-pipeline"
license = "確認したモデルライセンス名を記入"
source_url = "確認したモデルカードのURLを記入"

# [[generators.diffusers.models.local.adapters]]
# id = "example/adapter"
# local_path = "C:/models/adapter.safetensors"
# license = "確認したアダプタライセンス名を記入"
```

```text
uv run cybersprite gen accept-license local
uv run cybersprite -p sample.csprite gen run --backend diffusers --model local --prompt "説明" --width 512 --height 512 --seed 42
```

`model` は設定の別名だけを受け付ける。バックエンドはローカルの pipeline ディレクトリを `AutoPipelineForText2Image.from_pretrained` で読み、単一ファイルは `StableDiffusionPipeline.from_single_file` で読む。単一ファイル方式は SD 系の対応形式に限る。いずれも `local_files_only=True` で、自動ダウンロードを要求しない。ディレクトリ内に fp16 safetensors があれば `variant="fp16", use_safetensors=True` を指定する。LoRA は別々に読み込んで有効化する。パラメータは `num_inference_steps`、整数の `guidance_scale`、真偽値の `deterministic`（既定 false）。最後の値は生成中だけ決定的アルゴリズムを要求し、cuDNN benchmark と TF32 を無効化する。未対応演算はエラーにし、元のフラグと環境変数は例外時も復元する。生成結果の PNG は CyberSprite 自前 writer を使う。

**R1-F2 の監査結論: 選択肢 (b)。** `diffusers = []` は空の予約名のまま維持する（I-1641）。`uv sync --extra diffusers` は GPU スタックを導入しない。利用者が下記の別環境へ自分で導入し、その Python から CyberSprite を起動する。`pyproject.toml` の生成依存と `uv.lock` は変更せず、許可リストへの例外も追加しない。Windows CUDA wheel の実体に許可外の NVIDIA ランタイムがあるため、regex だけを交換しても配布用 extra の監査合格にはならない。

GPU スタック未導入、CUDA GPU なし、モデル実体なし、ライセンス未承諾は `gen backends` の理由として返す。通常の描画・変換・書き出しに生成用の依存や GPU は必要ない。

## 2 つの出口と権利メモ

`generate_image` / `gen run` は `use`（`canvas` が既定、または `design`）と `rights_note` を受ける。`design` は参照原画用、`canvas` は変換・配置用の用途を `params.use` に記録する。両方とも source 保存までで、キャンバスには直接入らない。配置は `import image --source SRC<n>` を別途実行する。

```text
uv run cybersprite -p sample.csprite gen run --backend diffusers --model local --prompt "説明" --width 512 --height 512 --seed 42 --use design --rights-note "確認すべき第三者の権利や規約の版"
```

生成時のモデル・アダプタ・ベースの条件は `params.model_registry` に保存する。結果の `model_terms` と `message`、封筒の `W_MODEL_TERMS` は CLI と GUI 共通のデータである。配置後にモデル・アダプタ・ベースの `commercial_use` が `yes` でなければ **Q-SRC-04（warning）**。旧来歴で商用利用条件が不明なモデルも警告する。未配置の参照原画には出さない。条件不明のまま配置できるが、公開や商用利用の前に利用者が条件を確認する。

**GUI 引き継ぎ TODO（Opus）:** 生成結果の `model_terms[].badge`、`commercial_use`、`message` を生成経路で表示する。参照原画の並列プレビューは別ワークストリーム。ここではビジュアル設計を行わない。

## ComfyUI 接続（H-22 段階 1・2）

ComfyUI は利用者が別に起動する。GPL-3.0 の本体・ノード実装・他者のワークフローは CyberSprite に同梱しない。参照したのは [公式 HTTP ルート文書](https://docs.comfy.org/development/comfyui-server/comms_routes) の公開 API であり、製品のソースコードは開いていない。標準ライブラリで送信・履歴ポーリング・画像取得を行う。API形式のワークフロー JSON を利用者が保存し、次のコマンドで対応付け候補を確認する。

```text
uv run cybersprite gen comfy-inspect C:/work/my_api.json
uv run cybersprite --format text gen comfy-inspect C:/work/my_api.json
```

`CLIPTextEncode`、`KSampler`、`EmptyLatentImage`、`CheckpointLoaderSimple`、`LoraLoader` の入力から候補を提示する。正負のテキストは KSampler の接続で区別できるときだけ提案し、曖昧なら `candidates` に残す。設定への書き込みと実行は行わない。人間がノード・接続・モデル・全入力を確認してから、設定へ登録する。下のノード番号は例であり、同梱ワークフローではない。

```toml
[generators.comfyui]
url = "http://127.0.0.1:8188"
timeout_seconds = 600
request_timeout_seconds = 10
poll_interval_ms = 500

[generators.comfyui.workflows.my-workflow]
file = "C:/work/my_api.json"
license = "実際に使用する checkpoint / LoRA / workflow の条件を記入"
commercial_use = "unknown"

[generators.comfyui.workflows.my-workflow.bind]
prompt = ["6", "inputs", "text"]
negative_prompt = ["7", "inputs", "text"]
seed = ["3", "inputs", "seed"]
width = ["5", "inputs", "width"]
height = ["5", "inputs", "height"]
steps = ["3", "inputs", "steps"]
cfg = ["3", "inputs", "cfg"]
checkpoint = ["4", "inputs", "ckpt_name"]
lora = ["10", "inputs", "lora_name"]
```

`file` の相対パスは設定ディレクトリ基準。`license` と `commercial_use` は必須。prompt / seed / width / height の対応付けは生成時に必須で、負プロンプトは空文字なら未対応付けでもよい。`params` の steps / cfg（整数）/ checkpoint / lora は指定されたキーの対応付けが必須。同じ入力への二重対応付け、ノード間の接続への上書き、未宣言の引数は拒否する。`count` と一致する枚数を生成するようワークフローのバッチ数と画像出力を設定する。

```text
uv run cybersprite gen backends
uv run cybersprite gen accept-license comfyui:my-workflow
uv run cybersprite -p sample.csprite gen run --backend comfyui --model my-workflow --prompt "説明" --negative-prompt blur --width 512 --height 512 --seed 42 --params '{"steps":20,"cfg":7}' --use canvas
uv run cybersprite -p sample.csprite import image --source SRC1 --preset ai
```

承諾は登録ワークフローファイルのハッシュと条件に結び付く。JSON の値や空白を変えた場合も再承諾が必要。値を埋めた完全な `workflow.json` を各 `source/SRC<n>/` に保存し、埋込み後と登録元の両ハッシュ、URL、seed、使用パラメータ、条件を記録する。再送時は画像と保存ワークフローの両方を照合する。サーバ上の重みは取得できないため、ワークフローハッシュを重みハッシュと取り違えない。商用条件の申告とライセンス確認は設定の管理者が行う。

カスタムノードはサーバ上で任意コードを動かせる。ツール引数から送れるのは登録名と明示的に対応付けた値だけで、任意ワークフロー JSON・サーバ URL・ノード種類・設定ファイルは受け付けない。設定先へ直接接続し、環境の HTTP プロキシと HTTP リダイレクトは使わない。JSON は8 MiB、画像応答は64 MiBまで。サーバ停止は `availability` の理由へ、タイムアウトは `E_TIMEOUT`、ワークフローや画像の失敗は `E_GENERATION_FAILED` へ返す。期限切れになってもサーバ上のジョブは残る場合がある。別の利用者の生成を止めないため全体への割込みを自動送信せず、再実行前にキューを確認する。

R1-F1 は自作の偽 HTTP サーバーによる API 契約・来歴・拒否条件を検証した。実 GPU 生成は後続の R1-F2 で確認済み（下記）。実 ComfyUI の追加確認はオーケストレーターへ引き継ぐ。

### R1-F2: 実体の依存監査（2026-11-12）

監査環境はリポジトリ外の `<外部環境>/_genenv`、CPython 3.12.10 / Windows 11。Torch は [PyTorch 公式 CUDA 12.8 index](https://download.pytorch.org/whl/cu128) の Windows cp312 wheel。`nvidia-smi` は RTX 3080 / 20480 MiB、driver 610.88 / CUDA UMD 13.3。CUDA 12.8 のFP16行列演算と下記の実SDXL生成を確認した。これは今回固定した監査・試行用スタックであり、最新版の推奨を意味しない。

`tools/audit_generation_stack.py` は `tools/check_licenses.py` と同じ依存閉包・SPDX判定で全33配布物を列挙し、各 dist-info の LICENSE/LICENCE/COPYING 原文、SHA-256、同梱ネイティブファイル一覧を JSON に保存する。以下はその原文と同梱物を読んだ結果。「可」は確認したライセンスが許可リストに合う意味で、スタック全体の配布許可を意味しない。機械判定だけで native notices の確認を置換しない。

| 配布物 | 版 | 原文からの分類 | 結果・確認箇所 |
|---|---|---|---|
| accelerate | 1.11.0 | Apache-2.0 | 可、dist-info/LICENSE |
| certifi | 2026.10.23 | MPL-2.0 | 不可、dist-info/licenses/LICENSE の Mozilla 証明書束 |
| charset-normalizer | 3.5.2 | MIT | 可、dist-info/licenses/LICENSE |
| colorama | 0.4.6 | BSD-3-Clause | 可、dist-info/licenses/LICENSE.txt |
| diffusers | 0.35.2 | Apache-2.0 | 可、dist-info/LICENSE |
| filelock | 4.2.4 | MIT | 可、dist-info/licenses/LICENSE |
| fsspec | 2026.9.0 | BSD-3-Clause | 可、dist-info/licenses/LICENSE |
| huggingface-hub | 0.36.0 | Apache-2.0 | 可、dist-info/LICENSE |
| idna | 3.20 | BSD-3-Clause | 可、dist-info/licenses/LICENSE.md |
| importlib-metadata | 10.2.0 | Apache-2.0 | 可、dist-info/licenses/LICENSE |
| Jinja2 | 3.1.6 | BSD-3-Clause | 可、dist-info/licenses/LICENSE.txt |
| lazy-importer | 0.1.0 | Apache-2.0 | 可、dist-info/licenses/LICENSE |
| MarkupSafe | 3.0.3 | BSD-3-Clause | 可、dist-info/licenses/LICENSE.txt |
| mpmath | 1.3.0 | BSD-3-Clause | 可、dist-info/LICENSE |
| networkx | 3.7 | BSD-3-Clause | 可、dist-info/licenses/LICENSE.txt |
| numpy | 2.3.4 | BSD-3-Clause、本体以外の通知を含む | 既存必須依存と同じ版。dist-info/LICENSE.txt を確認。今回の追加依存ではない |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | 可、LICENSE / LICENSE.APACHE / LICENSE.BSD |
| peft | 0.17.1 | Apache-2.0 | 可、dist-info/licenses/LICENSE。LoRA の実行に必要 |
| pillow | 13.0.0 | MIT-CMU（HPND） | 既存必須依存、dist-info/licenses/LICENSE |
| psutil | 7.2.2 | BSD-3-Clause | 可、dist-info/LICENSE |
| PyYAML | 6.0.3 | MIT | 可、dist-info/licenses/LICENSE |
| regex | 2026.11.9 | Apache-2.0 AND CNRI-Python | 不可、LICENSE.txt 冒頭の CPython 派生部分。checker に混在通知の固定テストを追加 |
| requests | 2.34.2 | Apache-2.0 | 可、dist-info/licenses/LICENSE |
| safetensors | 0.6.2 | Apache-2.0 | 可、dist-info/licenses/LICENSE |
| setuptools | 78.1.0 | MIT、同梱物に LGPL-3.0 | 不可、19件の原文に vendor の LGPL が含まれる。torch の Windows 実行時依存なので build-only 扱いにしない |
| sympy | 1.14.0 | BSD-3-Clause | 可、dist-info/licenses/LICENSE |
| tokenizers | 0.22.2 | Apache-2.0（メタデータ） | wheel に LICENSE 原文なし。公式 v0.22.2 タグの LICENSE は Apache-2.0 と確認したが、wheel 原文確認済みとは扱わない |
| torch | 2.8.0+cu128 | 本体 BSD-3-Clause、native に NVIDIA EULA | 不可、dist-info/LICENSE と実際の torch/lib/*.dll。集合通知に LGPL-2.1/3.0 本文もあるが、通知の存在だけで全成分のリンクを断定しない |
| tqdm | 4.70.1 | MIT AND MPL-2.0 | 不可、LICENCE の files:* 例外。checker へ混在通知の固定テストを追加 |
| transformers | 4.57.1 | Apache-2.0 | 可、dist-info/licenses/LICENSE |
| typing-extensions | 4.16.0 | PSF-2.0 | 可、dist-info/licenses/LICENSE |
| urllib3 | 2.8.0 | MIT | 可、dist-info/licenses/LICENSE.txt |
| zipp | 4.1.2 | MIT | 可、dist-info/licenses/LICENSE |

Torch wheel は `cudart64_12.dll`、`cublas64_12.dll`、`cublasLt64_12.dll`、`cudnn64_9.dll` と cuDNN 分割DLL、`cufft64_11.dll`、`curand64_10.dll`、`cusolver64_11.dll`、`cusparse64_12.dll`、`nvrtc64_120_0.dll` 等を実際に含む。BSD の package classifier をこれらの許可根拠にしない。[CUDA EULA](https://docs.nvidia.com/cuda/eula/index.html) と [cuDNN EULA](https://docs.nvidia.com/deeplearning/cudnn/backend/latest/reference/eula.html) は今回の許可リストにない。`triton` はこの Windows 閉包には入らなかった。Linux wheel や別版の監査結果へ一般化しない。全33配布物の原文とファイル名は監査 JSON に保持し、第三者台帳はオーケストレーターへ報告して更新を依頼する。

tokenizers の補足原文は [公式 v0.22.2 LICENSE](https://github.com/huggingface/tokenizers/blob/v0.22.2/LICENSE)。モデルについては下記の特定 revision のカードと LICENSE を別に確認した。コードの許可リスト判定を重みに適用したり、重みの条件をコード依存の例外へ流用したりしない。

### 利用者が別環境へ導入する手順

次は今回の検証用の版を再現する PowerShell 例。ネットワークと十分な空き領域が必要。まず LICENSE とモデル条件を自分で確認する。外部環境のパッケージは CyberSprite の配布依存ではない。

```powershell
uv venv --python 3.12 C:/work/cybersprite-genenv
$genPython = "C:/work/cybersprite-genenv/Scripts/python.exe"
uv pip install --python $genPython torch==2.8.0+cu128 --index-url https://download.pytorch.org/whl/cu128
uv pip install --python $genPython torch==2.8.0+cu128 diffusers==0.35.2 transformers==4.57.1 accelerate==1.11.0 safetensors==0.6.2 huggingface_hub==0.36.0 peft==0.17.1 --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match
# CyberSprite リポジトリを開発用に接続する場合。通常は入手済み wheel を指定してもよい。
uv pip install --python $genPython -e .
& $genPython -m cybersprite gen backends
```

2行目以降も同じ `$genPython` を使う。通常の `uv run` はリポジトリの `.venv` に戻るため、外部スタックを見つけられない。将来の推移依存の更新まで再現するには、監査 JSON の全版と `uv pip freeze --python $genPython` の記録を使う。主 lock に外部スタックを混ぜない。

取得は利用者の操作として HF キャッシュに保存する。今回の SDXL は `462165984030d82259a11f4367a4eed129e94a7b` の `model_index.json`、scheduler、2 tokenizer、2 text encoder、UNet、VAE の config と fp16 safetensors だけを使用した。Pixel Art XL は `8bf4a4d9ea283e00a51fafda8e0539f8248ea037` の `pixel-art-xl.safetensors`。`snapshot_download` の `revision` と `allow_patterns` を固定すれば不要な fp32/ONNX 重みを避けられる。配置先は `~/.cache/huggingface/hub` など、リポジトリ外とする。

設定例の `local_path` にそれぞれの実体パスを入れ、ベースのライセンスを `CreativeML Open RAIL++-M (2023-07-26)`、LoRA を `CreativeML Open RAIL-M (2022-08-22)` と別々に記録する。SDXL は [固定 revision の LICENSE.md](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/462165984030d82259a11f4367a4eed129e94a7b/LICENSE.md)、LoRA は [固定 revision のカード](https://huggingface.co/nerijs/pixel-art-xl/blob/8bf4a4d9ea283e00a51fafda8e0539f8248ea037/README.md) の宣言と [OpenRAIL-M 原文](https://huggingface.co/spaces/CompVis/stable-diffusion-license/blob/main/license.txt) を確認した。LoRA リポジトリに独立した LICENSE ファイルはない。

```toml
[generators.diffusers.models.sdxl-pixel]
id = "stabilityai/stable-diffusion-xl-base-1.0"
local_path = "C:/models/sdxl-fp16"
license = "CreativeML Open RAIL++-M (2023-07-26)"
source_url = "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/tree/462165984030d82259a11f4367a4eed129e94a7b"
[[generators.diffusers.models.sdxl-pixel.adapters]]
id = "nerijs/pixel-art-xl"
local_path = "C:/models/pixel-art-xl.safetensors"
license = "CreativeML Open RAIL-M (2022-08-22)"
source_url = "https://huggingface.co/nerijs/pixel-art-xl/tree/8bf4a4d9ea283e00a51fafda8e0539f8248ea037"
```

要求をUTF-8の `C:/work/generation-request.json` に保存する。Windows PowerShell 5.1でインラインJSONの引用符が落ちることを確認したため、ここでは `gen run` と同じ登録Opを要求ファイルから呼ぶ。

```json
{
  "backend": "diffusers",
  "model": "sdxl-pixel",
  "prompt": "pixel art, a small wooden chest, simple, flat colors, plain white background",
  "negative_prompt": "3d render, realistic, text, watermark",
  "width": 1024,
  "height": 1024,
  "seed": 42,
  "params": {"num_inference_steps": 30, "guidance_scale": 7, "deterministic": true}
}
```

```powershell
& $genPython -m cybersprite gen accept-license sdxl-pixel
& $genPython -m cybersprite -p C:/work/check.csprite op generate_image --args-file C:/work/generation-request.json
& $genPython -m cybersprite -p C:/work/check.csprite import image --source SRC1 --preset ai
& $genPython -m cybersprite -p C:/work/check.csprite validate
```

関門に落ちたら保存された段階画像と報告を先に見る。`preset ai` への入力が実生成画像であることは、関門の合格や美的な完成を保証しない。`deterministic=true` でも他の GPU・Torch/CUDA版・モデル・スケジューラで同じバイトになる保証はない。

GPU試験は既定でスキップする。承諾済みの設定とリポジトリ外の保存先を用意し、`CYBERSPRITE_RUN_GPU=1`、`CYBERSPRITE_GPU_CHECK_DIR`、必要なら `CYBERSPRITE_GPU_MODEL` を設定して外部環境の `python -m pytest tests/generate/test_gpu.py -q` を実行する。試験自身はダウンロードもライセンス承諾もしない。`python -m tools.verify_generation_gpu --out <リポジトリ外> --runs 3 --import-source` は実CLI子プロセスの時間、200 ms間隔の nvidia-smi ボード使用量、原PNGのハッシュ、取り込み応答を保存する。時間にはPython起動・モデルの実体ハッシュ・読込・推論・PNG保存を含み、純粋な推論時間とは区別する。Torchフラグはプロセス全体の状態なので、同一プロセスのDiffusers実行をロックして復元の競合を防ぐ。

### 実GPU検証の結果と測定範囲

2026-11-12、RTX 3080 / 20480 MiB、driver 610.88、上表の外部環境で、実CLI `gen accept-license sdxl-pixel` が成功した。SDXLのディレクトリ識別SHA-256は `686a5b6be3d889b77314461d3c4e457189d01dc0fd5fc86e8cb37d542b97bcf7`、LoRAファイルは `4234637cb80c998f41e348e6a6cb6bc20d8d038b2b0f256b6129b3b5e353eef7`。それぞれ別の承諾として `models.json` に保存された。

実CLI `cybersprite gen run` を3回、新規のsourceとして実行した。上記要求のseed=42、1024×1024、30 steps、guidance=7、`deterministic=true`、SDXL fp16とPixel Art XL LoRAを使用した。idempotency keyは使わず毎回推論した。

| 回 | CLI全体の時間（秒） | 観測VRAMピーク（MiB、200 ms間隔） |
|---|---:|---:|
| 1 | 540.420334100003 | 13342 |
| 2 | 446.6919937000057 | 13342 |
| 3 | 337.9346435000043 | 13342 |
| 中央値 | 446.6919937000057 | 13342 |

3枚とも原PNGのSHA-256が `1a7c4e608d08eaae66f1502d4a4a70261ef51552d76a6c43032fefe179cfa395` で一致した。これはこの機械・このモデルと版・この要求の再現確認であり、他GPUや別版の保証ではない。Torch決定的アルゴリズムは厳密モード、cuDNN benchmark/TF32は無効、行列演算精度highest、CUBLAS_WORKSPACE_CONFIG=:4096:8とし、終了時に元へ戻す。

時間はPython起動、承諾照合等のモデル実体ハッシュ、ロード、推論、PNG保存を含む。診断用スタックでは実体ハッシュ読込待ちも観測した（モデルとLoRAの組を1要求あたり4回ハッシュする現在の経路）。純粋な推論時間や速度改善の測定ではない。回ごとの減少はキャッシュ・同時負荷の差を分離しておらず、最適化の効果とは扱わない。VRAM値はボード全体の標本最大で、Torch allocatorの厳密なピークではない。同一プロセスの直列化について、変更前後3回ずつの並行性能比較は未実施。

SRC1の実CLI `import image --source SRC1 --preset ai` は変更なしの全14関門を通過し、revision 0→1でL2/frame 0へ配置した。論理128×128、パレット33（透明予約を含む）、使用32色。grid_score=996、grid_cell_count=128、boundary_alignment=767、snap_fidelity=81、off_palette=0、orphans=0、fidelity=8486958で、設定の上書き・関門無効化はない。生成だけではproject.jsonが作成されないことも確認した。

変更後の唯一のフレーム0のプレビューを確認し、独立 `validate` は `ok=true`、error=0、warning=0。infoのQ-LYR-03は自動作成された空のL1に対する通知で、そのまま残した。実CLIのPNG書き出しは `validation_ok=true` / `verified=true`。最終ファイルは128×128、indexed P、16704 bytes、SHA-256 `0045bc88751cf4ecbb587f5ea22b4ca8fa96542e2277a00f4115f4cd98871e45`、画素SHA-256 `b6ea18d4c632927ace3a776d47cdd08b39df5fc2990809d1bf72217113489d94`。Pillow 13.0.0と独自PNGデコーダのRGBA配列が一致し、書き出したファイルそのものも表示して確認した。美的評価は行っていない。

明示有効化した `tests/generate/test_gpu.py` も実CLIで **1 passed / 329.72秒**。同じseedと正promptだがnegative_promptなしの別画像で、生成子プロセスは328.83690509999724秒だった。この追加画像のai取り込みはorphans=1の関門で拒否（他13関門はpass）となった。stage5を表示して確認し、関門を変更せず、未配置の拒否例として保存した。LoRA読込時の2つのtext encoder通知は、このLoRAの2166 tensor keyがすべてlora_unet_でtext encoderを含まないことと一致する。通知を隠す変更はしていない。

初回はホストRAM16GB、空き約13〜270MiBの状況で1800秒タイムアウトし、画像が得られなかった。これは失敗期限であり生成時間ではない。後のTorch単体プローブはimport 63.6655秒、CUDA 12.8のFP16行列演算に成功した。再試行では上記の実画像を得たが、初回停止の原因をRAMだけとは断定しない。他アプリを強制終了する操作は行っていない。

記録は `<repo>/_private/gen-check/` に保持した。`dependency-audit.json`、`generation-freeze.txt`、`failed-attempt.json`、`torch-probe.json`、`local-weight-inventory.txt`、`settings/config.toml`、`settings/models.json`、`retry/summary.json`、CLI標準出力/エラーログ、`export-proof.json` が証跡。`retry/sdxl-pixel.csprite/source/` に原画像と全段階、`gpu-test/` に追加試験を保存した。`examples/chest-seed42.png` は合格した最終PNG、`chest-seed42-stage2.png` はその途中段階、`chest-no-negative-rejected-stage5.png` は追加画像の拒否例。最後の2つを合格済み成果物と混同しない。

初回探索ではNoobAI XL、animagine XL派生、音声用Qwen/HTDemucs、ComfyUIの各種重みがあったが、指定SDXL baseとPixel Art XLはなかった。パス一覧のみを保存し、指定の公式モデルをHFキャッシュへ取得した。後追いの一覧には今回の取得物と試験ダミーも含む。重み・生成画像はリポジトリにもコミットにも入れていない。他製品のコード・素材は開いていない。

## エージェント自身の画像生成ツール

エージェントが自分のツールで生成した画像は、そのツールからファイルとして保存し、`import_image` に来歴を付けて渡す。CyberSprite が別製品の画像生成 API を代行して呼ぶ経路ではない。

```text
uv run cybersprite -p sample.csprite op import_image --args-file import.json
```

`import.json` の例:

```json
{
  "files": "C:/work/generated.png",
  "preset": "ai",
  "provenance": {
    "kind": "generated",
    "provider": "codex-imagegen",
    "license": "unknown",
    "prompt": "実際に送った指示",
    "negative_prompt": "",
    "model": null,
    "url": "",
    "rights_note": "利用規約の版と出力条件は別途確認する",
    "seed": null,
    "params": {}
  }
}
```

ツールが明示したモデル ID・シード・設定値があれば記録する。非公開の ID や不明なハッシュは推測しない。ライセンスは空欄にせず、不明なら `unknown` とする。規約の版が確認できれば `license` に記入し、気づいた第三者の権利に関する情報は `rights_note` に書く。

関門で拒否された場合も source と段階画像・報告は残る。段階画像を確認してから設定を見直し、同じ source ID で再取り込みする。配置後は検証デルタとプレビューを読み、最後に書き出したファイルそのものを確認する。

## MCP と拡張

`--enable-generation` を付けたサーバだけが `list_generators` と `generate_image` を公開する。`--read-only` では生成を公開しない。生成は `G` クラスで `openWorldHint: true`。`apply_ops` の中で生成を実行することはできない。

`cybersprite.generators` の entry point で追加できる。factory は `plugin_api = 1` を持ち、引数なしで §12.3 のバックエンドを返す。`params_schema` は pydantic モデル。設定の `[plugins].enabled` に登録した名前だけを選択でき、一覧取得ではプラグイン本体を import しない。一覧では未読込の理由を返す。プラグインもローカル実体のモデル・アダプタの承諾と、返却ファイル・モデル情報の照合を通す。

## オーケストレーターへの未確認事項

M9では L-10 / L-12 の調査を行っていなかった。R1-F2では上記のSDXL baseとPixel Art XLの特定revisionのカード・利用条件を確認した。他モデル・refiner・L-12は未確認であり、一般のモデル推奨一覧は置かない。

- L-10: SD1.5、使用するSDXL refiner、FLUX.1 [schnell]等の各モデルカード・同梱LICENSE・利用条件の版。上記2モデルでも別revisionへ変える場合は再確認する。
- L-10: PixArt-alpha と PixArt-Sigma の実際に採用するチェックポイントのモデルカードと LICENSE。系列名で同一条件だと決めない。
- L-10: 上記に追加するすべての LoRA と、そのカードが指定するベースモデル。ダウンロード元、正確な revision、実体ハッシュ、商用利用・再配布・利用制限を記録する。
- モデルカードの確認先候補（未閲覧。正式な配布元・対象 revision の確認から行う）: `stable-diffusion-v1-5/stable-diffusion-v1-5`、`stabilityai/stable-diffusion-xl-refiner-1.0`、`black-forest-labs/FLUX.1-schnell`、`PixArt-alpha/PixArt-XL-2-1024-MS`、`PixArt-alpha/PixArt-Sigma-XL-2-1024-MS`。
- L-12: OpenAI の個人向け利用規約と、適用される法人向け契約・サービス条件の現行版、画像出力の帰属と制限。Codex の当該実行環境で使える画像生成ツールの仕様、モデル情報の公開範囲、保存先、来歴として取得できる情報も確認する。
- L-09: R1-F2のWindows CUDAスタック監査は不合格と確定し、空extraを維持する。将来、別版・別構成を配布依存へ採用するなら、再度実体を監査して別の判断を記録する。今回の利用者導入を配布用extraの承認と解釈しない。
