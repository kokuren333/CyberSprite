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
