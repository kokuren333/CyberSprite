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
uv run cybersprite -p sample.csprite gen run --backend diffusers --model local --prompt "説明" --width 512 --height 512 --seed 42 --params '{"num_inference_steps":30,"guidance_scale":7}'
```

`model` は設定の別名だけを受け付ける。バックエンドはローカルの pipeline ディレクトリを `AutoPipelineForText2Image.from_pretrained` で読み、単一ファイルは `StableDiffusionPipeline.from_single_file` で読む。単一ファイル方式は SD 系の対応形式に限る。いずれも `local_files_only=True` で、自動ダウンロードを要求しない。LoRA は別々に読み込んで有効化する。パラメータスキーマは `gen backends` の `params_schema` にあり、`num_inference_steps` と整数の `guidance_scale` に限定する。生成結果の PNG は CyberSprite 自前 writer を使う。

**依存監査の保留:** M9 では既存の `diffusers = []` extra を予約のまま維持した。PyPI wheel の LICENSE 原文を確認した Diffusers 0.35.2 と Transformers 4.57.1 自体は Apache-2.0 だが、推移依存 regex 2025.9.18 の原文には CNRI Python 1.6 の記載もあり、今回の依存許可リストにない。したがって `uv sync --extra diffusers` だけでは GPU スタックは導入されない。オーケストレーターが依存全体の監査と許可方針を解決してから extra の依存を有効にする。Torch/Diffusers の巨大 wheel や重みはこの環境に導入していない。API 接続は偽パイプラインで検証している。

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

実 ComfyUI / GPU 生成は未検証。このワークストリームは自作の偽 HTTP サーバーによる API 契約・来歴・拒否条件を検証する。実 GPU 確認は R1-F2、実 ComfyUI の追加確認はオーケストレーターへ引き継ぐ。

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

この実装では L-10 / L-12 の調査を行っていない。既定のモデル推奨例は置かない。

- L-10: SD1.5、SDXL base と使用する refiner、FLUX.1 [schnell]、Pixel Art XL の各モデルカード・同梱 LICENSE・利用条件の版。Pixel Art XL はアダプタ自体と、その指定ベースモデルを別々に確認する。
- L-10: PixArt-alpha と PixArt-Sigma の実際に採用するチェックポイントのモデルカードと LICENSE。系列名で同一条件だと決めない。
- L-10: 上記に追加するすべての LoRA と、そのカードが指定するベースモデル。ダウンロード元、正確な revision、実体ハッシュ、商用利用・再配布・利用制限を記録する。
- モデルカードの確認先候補（未閲覧。正式な配布元・対象 revision の確認から行う）: `stable-diffusion-v1-5/stable-diffusion-v1-5`、`stabilityai/stable-diffusion-xl-base-1.0`、`stabilityai/stable-diffusion-xl-refiner-1.0`、`black-forest-labs/FLUX.1-schnell`、`nerijs/pixel-art-xl`、`PixArt-alpha/PixArt-XL-2-1024-MS`、`PixArt-alpha/PixArt-Sigma-XL-2-1024-MS`。
- L-12: OpenAI の個人向け利用規約と、適用される法人向け契約・サービス条件の現行版、画像出力の帰属と制限。Codex の当該実行環境で使える画像生成ツールの仕様、モデル情報の公開範囲、保存先、来歴として取得できる情報も確認する。
- L-09: regex の CNRI Python 1.6 表記と許可方針の整合、Torch の実際に採用する wheel とバンドルされたライセンス、Diffusers/Transformers/LoRA 用の推移依存全体の原文監査。台帳の更新後に extra を有効にする。
