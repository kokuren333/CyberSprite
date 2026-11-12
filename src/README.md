# src/

Python パッケージ `cybersprite` の置き場所。M1 のヘッドレス基盤を実装済み。

`src/` レイアウトにしているのは、インストールしていない状態のコードをテストが誤って読み込むのを防ぐためである。

| ディレクトリ | 役割 | 仕様の節 | 着手 |
|---|---|---|---|
| `cybersprite/core/` | `models` 型と ID、`canonical` 正準 JSON と読み込み、`pixels` 行符号化・色解決、`references` 参照解決、`normalize` 純粋なセル正規化、`validation` S-01〜S-14、`render` 整数合成、`hashing` CSPX1、`schemas` スキーマ生成、`projects` 新規作成のみ、`errors` 共通エラー | §5、§6、§13 | M1 |
| `cybersprite/ops/` | Op の実装（描画、パレット、レイヤー、フレーム、タグ、スライス、タイル、キャンバス） | §6.4、§10 | M2、M7 |
| `cybersprite/formats/` | `png` 自前 PNG writer・限定 reader・実行環境指紋。ほかの形式は M5 | §6.6、§8 | M1、M5 |
| `cybersprite/pipeline/` | 変換パイプライン | §11 | M6 |
| `cybersprite/generate/` | 生成バックエンド | §12 | M9 |
| `cybersprite/cli/` | 遅延 import の Click CLI。`new`、`info`、`render`、`validate`、`schema`、`doctor`。Op レジストリ・履歴は M2、CLI 拡充は M3 | §9 | M1、M3 |
| `cybersprite/mcp/` | MCP サーバ | §10 | M4 |
| `cybersprite/server/` | GUI 用ローカルサーバ。GUI のビルド成果物を `static/` に同梱する | §14.6 | M8 |
| `cybersprite/plugins/` | プラグインの読み込みと公開 API | §15 | M2〜 |
| `cybersprite/data/` | 規範データ（色変換表、Bayer 行列、組み込みパレット、パイプラインの既定値） | 付録 B、§11 | M1、M6 |

## 依存の向き（必ず守る）

- `core` が import してよいのは、標準ライブラリ、NumPy、pydantic だけ。Pillow と `aseprite` は `formats` と `pipeline` だけが使う。
- `cli`、`mcp`、`server` は、Op レジストリを通してだけプロジェクトを変える。
- `core`、`ops`、書き出し、パイプラインの組み込みステップでは、浮動小数、乱数、現在時刻を使わない。

M2 のコミット処理は `normalize_cels` → `require_valid` → `dumps_project` を再利用する。M1 の `create_project` は排他作成のみで、既存正本を上書きする API はない。`render` / `render_indexed` は ndarray を返し、警告と描画用パレットが必要なら `render_result` / `indexed_result` を使う。
