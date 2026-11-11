# src/

Python パッケージ `cybersprite` の置き場所。**まだコードはない**（仕様策定フェーズ）。実装は `docs/SPEC.md` §16.4 のマイルストーン M1 から始まる。

`src/` レイアウトにしているのは、インストールしていない状態のコードをテストが誤って読み込むのを防ぐためである。

| ディレクトリ | 役割 | 仕様の節 | 着手 |
|---|---|---|---|
| `cybersprite/core/` | モデル、正準 JSON、Op レジストリ、トランザクション、履歴、検証、レンダラ | §5、§6、§13 | M1〜M2 |
| `cybersprite/ops/` | Op の実装（描画、パレット、レイヤー、フレーム、タグ、スライス、タイル、キャンバス） | §6.4、§10 | M2、M7 |
| `cybersprite/formats/` | PNG / GIF / APNG / シート / パレットファイル / `.aseprite` アダプタ | §5.9、§8 | M1、M5 |
| `cybersprite/pipeline/` | 変換パイプライン | §11 | M6 |
| `cybersprite/generate/` | 生成バックエンド | §12 | M9 |
| `cybersprite/cli/` | CLI | §9 | M1、M3 |
| `cybersprite/mcp/` | MCP サーバ | §10 | M4 |
| `cybersprite/server/` | GUI 用ローカルサーバ。GUI のビルド成果物を `static/` に同梱する | §14.6 | M8 |
| `cybersprite/plugins/` | プラグインの読み込みと公開 API | §15 | M2〜 |
| `cybersprite/data/` | 規範データ（色変換表、Bayer 行列、組み込みパレット、パイプラインの既定値） | 付録 B、§11 | M1、M6 |

## 依存の向き（必ず守る）

- `core` が import してよいのは、標準ライブラリ、NumPy、pydantic だけ。Pillow と `aseprite` は `formats` と `pipeline` だけが使う。
- `cli`、`mcp`、`server` は、Op レジストリを通してだけプロジェクトを変える。
- `core`、`ops`、書き出し、パイプラインの組み込みステップでは、浮動小数、乱数、現在時刻を使わない。
