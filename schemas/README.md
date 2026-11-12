# schemas/

コード（pydantic のモデル）から生成した規範 JSON Schema の置き場所。

| ファイル | 内容 | 仕様の節 |
|---|---|---|
| `project.schema.json` | `project.json` | §5 |
| `sources.schema.json` | `source/manifest.json` | §5.10 |
| `op.<Op 名>.schema.json` | 各組み込み Op の入力（project・共通引数を含む） | §10 |
| `sheet.schema.json` | 独自形式と互換 2 形式のシートデータ | 付録 D |

トップレベルに置くのは、これが Python の実装ではなく「言語に依存しない仕様」だからである。GUI（TypeScript）と将来の Rust 実装が同じものを参照する。CI で、コードから生成し直した結果との差分がないことを検査する。

生成は `uv run python tools/gen_schemas.py`、差分検査は同じコマンドの `--check`。
CLI の `csp schema project|sources|sheet|all` と `csp schema op <name>` も同じ定義を使う。
