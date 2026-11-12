# プラグインの実装契約（API 1）

プラグインは利用者が信頼して導入する Python パッケージであり、サンドボックスではない。仕様の正本は SPEC §15。外部コード・依存を本体へ同梱するときは通常のライセンス原文確認が必要になる。

## 登録と設定

`pyproject.toml` の例:

```toml
[project.entry-points."cybersprite.pipeline_steps"]
"downsample.example" = "my_package.steps:make_step"
```

利用者の `config.toml` に `[plugins] enabled = ["downsample.example"]` を書く。`disabled` に同じ名前があれば拒否が優先する。同梱する optional extra のアダプタも本体の entry point に登録し、依存の import は factory 内まで遅らせる。

entry point の対象はオブジェクト、または引数なし factory とする。**factory 自身**（クラスならクラス属性）に整数 `plugin_api = 1` を付ける。戻り値だけへの宣言では呼出前の互換検査ができない。読込・登録・実行の失敗は `E_PLUGIN`。factory は副作用を残さないように実装する。ローダーが戻すのは内部登録だけであり、第三者コードの任意の外部副作用は取り消せない。

一覧は distribution の名前・版・`License-Expression` → `License` → license classifier の順の表示を使い、コードを実行しない。任意の配布メタデータ `CyberSprite-Plugin-API: 1` は事前の互換判定に使える。未記載は未検査であり、実行時の検査は省略しない。distribution は導入後に固定し、変更したらプロセスを再起動する。

## 変換ステップ

```python
from cybersprite.plugins.contracts import PipelineStep

def run(image, params):
    grid = params["grid"]
    output = image[::2, ::2].copy()  # Minimal test example; not valid for arbitrary grids.
    return output, {"output_rows": int(output.shape[0])}

def make_step():
    return PipelineStep("downsample", "example", run, level_a=True)

make_step.plugin_api = 1
```

設定は `{"downsample": {"method": "example", "params": {}}}`。組み込み方式が優先する。登録名は `step.method` を推奨し、`method` だけも受理する。1 entry point は 1 実装。`run` はフレームごとに呼ばれ、引数と画像には独立コピーを渡す。複数フレームは同じ出力寸法・パレットに揃える。

| step | 入出力 | 追加の params |
|---|---|---|
| `grid` | RGBA → RGBA。後段で組み込みの格子検出を行う | grid 節の設定 |
| `downsample` | RGBA → RGBA。検出した rows/columns に一致させる | `grid`（確定したセル境界）。背景除去と二値アルファ化は共通処理 |
| `reconstruct` | RGBA → RGBA。grid＋downsample を置換 | `grid`。任意寸法を返せる。単一の量子化は後段で行う |
| `quantize` | RGBA → `IndexedImage` | `project_palette`、`transparent_index`、`dither_type`、`strength` |
| `cleanup` | `IndexedImage` → `IndexedImage`。寸法とパレットは変更不可 | `transparent_index`。`protect` はパレットの保護色も番号へ解決して合成した実効値 |

RGBA は `numpy.uint8[H,W,4]`。`IndexedImage` は `pixels: numpy.uint8[H,W]` と、整数 RGBA タプルの `palette`。配列の暗黙のキャスト・色の近似はしない。量子化方式は既存 `palette` 節の `method` で選ぶ（`quantize` 節も同義）。量子化は既存パレットの接頭辞・透明番号を維持し、`mode="project"` では完全一致させる。

metrics と params は JSON 化可能な値にする。プラグイン内部は浮動小数を使えるが、同じ環境と入力から同じ結果を返す必要がある。`level_a=True` は Windows/Linux などを跨いだ同一画素の宣言である。False では報告の determinism が `same-platform` となり `W_PLUGIN_DETERMINISM` が付く。登録名・distribution・版・引数・宣言は pipeline_report と source manifest の report に保存される。

## その他の群

公開の設定付きローダーは `cybersprite.plugins.PluginManager`。core は独立した標準ライブラリ／pydantic の低層ローダーと許可データ型だけに依存し、形式・変換・拡張実装を import しない。Python API から手動登録した Op と entry point 由来の Op は区別し、後者の設定許可を検査する。両方とも同じトランザクション・不変条件を通る。

- `ops`: factory は `core.registry.Op` の列を返す。entry point 名は提供者、Op 名は提供者名そのものまたは `<提供者>_<操作>`。CLI は名前で初回解決する。MCP は Op 名を `--allow-plugin-op` に列挙し、その名前に対応する最長の提供者接頭辞だけを読む。トランザクションは既存の共通経路を使う。
- `generators`: factory は SPEC §12.3 のバックエンドを返し、その `name` は entry point 名に一致する。能力・モデル一覧だけでは import しない。
- `validators`: オブジェクトまたは factory が `Validator(rule, default_severity, check)` かその列を返す。`rule="Q-<entry-point名>-nn"`、severity は error/warning/info/off。`check(document, frame_range)` は issue 辞書の列と metrics 辞書を返す。issue は `message` と任意の `where={frames,layer,bbox,points}`。コピーした文書を渡す。通常の severity 上書き、フィルタ、デルタに含まれる。
- `palettes`: factory は `{name, colors, license?, names?}` の列を返す。colors は 1〜256 個の `#rrggbbaa`、names は文字列の番号から色名。衝突する名前を拒否する。既存プリセットの読取入口と CLI の `palette presets` から使える。
- `exporters`: オブジェクトまたは factory は `name`, `extension`, pydantic の `options_model`, `write(document, renderer, out, options)` を提供する。`export_plugin` Op／`export plugin --format <name> --out <path>` が共通検証と path preflight を実行する。format 省略時は有効な exporter の extension を照合する。v1 は単一ファイル。writer は渡された一時 out だけへ書く。任意の `decode(bytes)` は全フレームの RGBA 配列の列を返す。自己検査は実ファイルから読んだ bytes を復号し、コア描画と照合する。decode がなければ `verified=false` と理由を返す。失敗時は以前の出力を保持する。
- `importers`: メタデータ列挙だけ。v1.x で入力予算・ラスターと構造形式の来歴／配置契約を確定して接続する。
- `platforms`: API 1のfactoryが`ID -> JSON定義`の辞書を返す。有効設定とAPI検査は他群と同じ。定義は整数・文字列・真偽・nullだけで構成し、キーと定義内idを一致させる。同名の内蔵定義を上書きでき、プラグイン間の同IDはE_PLUGIN。保存したsnapshotの検証では再読込しない。

exporter の `write` は `formats.export_args.ExportResult`（またはその辞書）を返す。wrapper は戻り値のスキーマを検査し、warnings を引き継ぐ。ファイルのメタデータ・validation_ok・verified は共通層が独立して求め、writer の自己申告で上書きしない。

実機形式は`native=true`で`export_native`から選べる。省略可能な`verification_frames(document, renderer, options)`は照合用の厳密RGBA区画列を返し、この場合decode(bytes)が必須。内蔵gb-2bppは8×8タイル列を独立復号してレンダラ区画へ照合する。bank/VRAM配置・palette_out/map_outはこの版の対象外。

validator の規則 ID は組み込みと他の登録済み規則を含めて一意にする。同じ ID の置換は許さず、衝突した登録を `E_PLUGIN` で破棄する。downsample は `params.grid` の実際のセル数に合わせる。自動格子が未検出の場合も診断用 none 格子で画像と不合格の報告を残す（関門は合格に変更しない）。

テストの最小実装は `tests/test_plugins_r1.py`。外部の製品や素材を使わず、fake entry point で読み込み範囲・API 版・失敗時の登録破棄・各実行経路を検査している。
