# src/

Python パッケージ `cybersprite` の置き場所。M1 のヘッドレス基盤と M2 の Op・トランザクションを実装済み。

`src/` レイアウトにしているのは、インストールしていない状態のコードをテストが誤って読み込むのを防ぐためである。

| ディレクトリ | 役割 | 仕様の節 | 着手 |
|---|---|---|---|
| `cybersprite/core/` | M1 の型・正準化・構造検証・レンダラに加え、`registry` 契約と登録、`transactions` 唯一の既存正本保存経路、`history` ロック・原子的保存・履歴、`journal_clock` 時刻の隔離、`quality` 品質検証とデルタ、`previews` 装飾画像の整数配列 | §5、§6、§13 | M1、M2 |
| `cybersprite/ops/` | `args` 引数モデル、`common` 参照・リンク共有編集、`drawing` ラスタ関数の接続、`frames` フレーム／セル、`palette` パレット、`structure` レイヤー／タグ／スライス／メタデータ、`canvas` キャンバス、`queries` 読取と初期構築、`previews` PNG 保存。`__init__` の `registry()` と `execute()` が利用面の共通入口 | §6.4、§10 | M2、M7 |
| `cybersprite/formats/` | `png` 自前 PNG writer・限定 reader・実行環境指紋、`palette_files` 組み込みプリセット・GPL/PAL/HEX テキスト読込。ほかの形式は M5 | §6.6、§8 | M1、M2、M5 |
| `cybersprite/pipeline/` | 変換パイプライン | §11 | M6 |
| `cybersprite/generate/` | 生成バックエンド | §12 | M9 |
| `cybersprite/cli/` | 遅延 import の Click CLI。既存コマンドに `op`、`apply`、`undo`、`redo`、`history`、`ops list/describe`、`preview`、`diff`、`pixels`、`palette show/presets` を追加。`validate` は品質規則まで検査。CLI の仕上げは M3 | §9 | M1〜M3 |
| `cybersprite/mcp/` | MCP サーバ | §10 | M4 |
| `cybersprite/server/` | GUI 用ローカルサーバ。GUI のビルド成果物を `static/` に同梱する | §14.6 | M8 |
| `cybersprite/plugins/` | プラグインの読み込みと公開 API | §15 | M2〜 |
| `cybersprite/data/` | 規範データ（色変換表、Bayer 行列、組み込みパレット、パイプラインの既定値） | 付録 B、§11 | M1、M6 |

## 依存の向き（必ず守る）

- `core` が import してよいのは、標準ライブラリ、NumPy、pydantic だけ。Pillow と `aseprite` は `formats` と `pipeline` だけが使う。
- `cli`、`mcp`、`server` は、Op レジストリを通してだけプロジェクトを変える。
- `core`、`ops`、書き出し、パイプラインの組み込みステップでは、浮動小数、乱数、現在時刻を使わない。

M2 のコミット処理は `normalize_cels` → `require_valid` → `dumps_project` を再利用する。M1 の `create_project` は排他作成のみで、既存正本を上書きする API はない。`render` / `render_indexed` は ndarray を返し、警告と描画用パレットが必要なら `render_result` / `indexed_result` を使う。

`ops.execute(name, project, args, actor="cli", **transaction_options)` は成功の封筒を返す。失敗は `CyberSpriteError` として返し、バッチ内の失敗には `op_index` が付く。MCP と GUI はこの入口を使い、プロジェクトを直接保存しない。`registry().get(name).describe()` が入力・出力スキーマと annotations を生成する。Op のスキーマは現時点では実行時生成であり、`schemas/` に別の正本を置かない。

`core.validation.validation_report` は M1 互換の構造検証である。品質を含む報告は `core.quality.report`、利用面からは登録済み `validate` を使う。品質デルタはキャッシュなしの全量計算で、`core.quality.validation_delta` が同一性と指標の比較を担当する。

プレビューの PNG エンコードは `ops/previews.py` から自前 writer を呼ぶ。`core` には formats の import を持ち込まない。`inline` の画像は `result.images` の PNG base64 配列として運び、M4 が MCP 画像コンテンツへ変換できる。
