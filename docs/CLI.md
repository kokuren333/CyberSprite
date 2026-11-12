# CLI

`uv run cybersprite`（短縮名 `uv run csp`）。フレーム番号は 0 始まり。確認入力は求めない。
仕様の正本は [SPEC.md §9](SPEC.md)。

全体オプションは `-p/--project <ディレクトリまたは project.json>`、`--format json|text`、
`--actor <名前>`、`--quiet`、`--version`、`--help`。
プロジェクト省略時はカレントディレクトリの `project.json` を使う。
`--actor`、環境変数 `CYBERSPRITE_ACTOR`、`cli` の順で実行者を決める。
`-p`、`--actor`、`--quiet` はサブコマンドの後にも置ける。
全体の `--format` はコマンドより前に置く。書き出し Op の `--format` はファイル形式を指す。

既定の標準出力は §10.3 の封筒形式の JSON 1 個（UTF-8）。診断文章は標準エラーへ出る。
`--format text` は短い要約、`--help` と `--version` は通常のテキスト表示。
`mcp serve --transport stdio` の稼働中は MCP 通信が標準出力を使う。

| 終了コード | 意味 |
|---|---|
| 0 | 成功 |
| 1 | 検証不合格。`validate --strict` は警告でも 1 |
| 2 | 引数、Op 名の誤り |
| 3 | 対象なし、状態不一致、生成・プラグインの状態エラー |
| 4 | 入出力、ロック、許可パス、壊れたプロジェクト、時間切れ |
| 5 | 内部エラー、不変条件違反 |
| 6 | 上限、未対応、量子化が必要、パレット閉包でない、新しすぎるスキーマ |

## コマンド

Op 対応コマンドのオプションは、登録済みの pydantic 引数モデルから作る。
`snake_case` は `--kebab-case`、真偽値は `--flag/--no-flag`。
配列は JSON またはカンマ区切り、オブジェクトは JSON を渡す。
`import image` と `convert` では `--sheet-cell 16x16`、
`--dither none|bayer2|bayer4|bayer8` も使える。後者は `pipeline.dither.type` の上書き。
厳密な型・選択肢は `ops describe <名前>`、利用できるオプションは各コマンドの `--help` で確認する。

| コマンド | 主な引数・オプション |
|---|---|
| `new <パス>` | `--size 16x16`（必須）、`--palette <プリセット・ファイル・JSON 配列>`、`--frames n`、`--duration ms`、`--name`、`--background <色>` |
| `info` | `--include summary,layers,frames,tags,slices,tilesets,palette,sources,validation,history` |
| `pixels` | `--layer <L>`、`--frame n`（省略時 0）、`--rect x,y,w,h`、`--as hex|sym`（旧名 `--pixel-format` も可） |
| `palette show` / `palette presets` | プロジェクトのパレット / 同梱プリセット一覧 |
| `validate` | `--frames all|0-3|tag:walk`、`--rules Q-PAL-01,...`、`--strict` |
| `render` | `--out <PNG>`（必須）、`--frame n`、`--scale n`、`--layers L1,L2`、`--bg <色>`、`--indexed`、`--flatten strict|nearest`、`--include-hidden`、`--compression zlib|stored`、`--apply-pixel-ratio` |
| `preview` | `--frame n` またはカンマ区切りのフレーム列、`--scale auto|n`、`--grid`、`--rulers`、`--onion p,n`、`--layers`、`--background`、`--out <PNG またはディレクトリ>` |
| `diff` | `--from <rev>`、`--to <rev>`、`--frame n`、`--out <PNG またはディレクトリ>` |
| `op <名前>` | `--args-file <JSON ファイル>`、`--args <JSON>`、`キー=値...` |
| `apply [<JSON ファイル>\|-]` | ファイル省略または `-` で標準入力の JSON。端末からの対話入力は拒否 |
| `undo` / `redo` / `history` | `--steps n` / `--steps n` / `--limit n` |
| `import image <ファイル...>` | `import_image` の引数モデルから生成（M6） |
| `import aseprite <ファイル>` | `--out <プロジェクト>`、ほかは `import_aseprite` から生成（M5） |
| `import palette <ファイルまたはプリセット>` | `--append` または `--mode replace|append`、`--on-shrink <方針の JSON>` |
| `export image|sheet|anim|aseprite|tileset|palette` | 各 `export_*` の全引数。`anim` は `export_animation`。`--input <外部ファイル>` も可（M5） |
| `convert <入力> <出力>` | `import_image` と同じ変換オプション、`--stages <ディレクトリ>`（M6） |
| `pipeline detect-grid <ファイル>` | 検出の診断（M6） |
| `source list` / `source show <ID>` | `list_sources` / `get_source` の引数（M6） |
| `gen backends` / `gen run` | `list_generators` / `generate_image` の引数（M9） |
| `gen accept-license <名前>` | モデルのライセンス承諾（M9） |
| `ops list` / `ops describe <名前>` | 登録された Op の一覧 / 契約 |
| `schema [project|sources|sheet|op <名前>|all]` | `--out <ディレクトリ>`。`all` は利用できるデータスキーマと全 Op の入力スキーマ |
| `plugins list` | インストール済み Op プラグインの許可状態・読込状態を表示。読み込みは行わない |
| `mcp serve` | `--root`、繰り返せる `--allow-dir`、`--transport stdio|http`、`--port`、`--profile standard|minimal`、`--enable-generation`、繰り返せる `--allow-plugin-op`、`--read-only`（M4） |
| `gui [<プロジェクト>]` | `--port n`、`--no-browser`（M8） |
| `doctor` | 版、実行環境指紋、任意依存、書込権限、設定ファイルの診断 |

`op`、`apply` および生成された変更コマンドには、`--dry-run`、`--expect-revision n`、
`--idempotency-key <キー>`、`--preview none|path|inline` を渡せる。
Op 引数はファイル → `--args` → `キー=値` の順で上書きする。
共通トランザクション設定の明示フラグは、その JSON 内の値より優先する。

`preview` / `diff` の `--out` は 1 枚ならファイル、複数枚ならディレクトリを指定する。
省略時はプロジェクト内の `.cybersprite/previews/` に保存する。
`project.json` を出力で上書きすることはできない。

後続マイルストーンの Op やモジュールがまだない場合もコマンドは存在し、
`E_UNSUPPORTED`・終了コード 6 と必要なマイルストーンのヒントを返す。
`mcp serve` の依存がなければ `cybersprite[mcp]` の導入を案内する。
M3 時点で `schema sheet` は M5 のスキーマ提供待ち。

## 例 1: 作成・描画・検証・確認

```powershell
uv run csp new demo.csprite --size 16x16 --palette gray-4
uv run csp -p demo.csprite op rect layer=L1 frame=0 x=2 y=2 w=12 h=12 color=1
uv run csp -p demo.csprite validate
uv run csp -p demo.csprite preview --frame 0 --grid --out preview.png
uv run csp -p demo.csprite pixels --layer L1 --frame 0 --as sym
```

描画結果の `validation` は検証デルタ。全体は `validate` で読み、プレビュー PNG 自体を開いて確認する。

## 例 2: トランザクションと履歴

`draw.json`（UTF-8）:

```json
{"label":"draw bar","ops":[{"op":"line","args":{"layer":"L1","frame":0,"x0":4,"y0":7,"x1":11,"y1":7,"color":2}}]}
```

```powershell
uv run csp -p demo.csprite apply draw.json
uv run csp -p demo.csprite undo
uv run csp -p demo.csprite history --limit 5
uv run csp -p demo.csprite diff --frame 0 --out diff.png
uv run csp -p demo.csprite render --frame 0 --out final.png --indexed
```

変更の後に検証とプレビューを確認し、最後に書き出した `final.png` を開く。

## 例 3: 契約と環境を調べる

```powershell
uv run csp ops describe line
uv run csp schema op line --out schemas-out
uv run csp doctor
uv run csp export sheet --help
```

## ユーザー設定

Windows は `%APPDATA%/cybersprite/config.toml`、それ以外は
`$XDG_CONFIG_HOME/cybersprite/config.toml`（未指定時 `~/.config/cybersprite/config.toml`）。
ファイルなしは既定設定。未知キー・型違い・不正 TOML は `E_INVALID_ARGS`。

```toml
[gui]
port = 8765
open_browser = true
language = "ja"

[plugins]
enabled = []

[generators.command.local]
program = "C:/tools/generate.exe"
args = ["--prompt", "{prompt}", "--output", "{out}"]
license = "unknown"
timeout_seconds = 600

[generators.diffusers.models.local]
id = "configured/model"
license = "unknown"
```

コマンドの雛形で使える置換は `{prompt}`、`{negative_prompt}`、`{width}`、`{height}`、
`{seed}`、`{out}`、`{count}` だけ。`program` やモデルの場所をツール引数から定義できない。
`doctor` は設定の場所と登録名を表示し、コマンド定義の本文は出力しない。
外部プログラムの実行、モデルの利用と `models.json` へのライセンス承諾記録は M9 が担当する。
