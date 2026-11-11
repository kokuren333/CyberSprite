# schemas/

規範となる JSON Schema の置き場所。**まだファイルはない。** M1 で、コード（pydantic のモデル）から生成する。

| ファイル（予定） | 内容 | 仕様の節 |
|---|---|---|
| `project.schema.json` | `project.json` | §5 |
| `sources.schema.json` | `source/manifest.json` | §5.10 |
| `ops/<Op 名>.schema.json` | 各 Op の引数 | §10 |
| `envelope.schema.json` | ツールの戻り値の封筒 | §10.3 |
| `sheet.schema.json` | スプライトシートのデータ（独自形式） | 付録 D |
| `pipeline_report.schema.json` | パイプライン報告 | §11.8 |

トップレベルに置くのは、これが Python の実装ではなく「言語に依存しない仕様」だからである。GUI（TypeScript）と将来の Rust 実装が同じものを参照する。CI で、コードから生成し直した結果との差分がないことを検査する。
