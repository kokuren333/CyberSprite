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

## M6 の統合 API

- `core/color.py` が付録 B の正本。`pipeline/oklab.py` は互換再公開であり、コアから pipeline への依存はない。
- `core/sources.py`: `read_manifest(root) -> Sources`、`save_manifest(root, manifest)`、`manifest_path(root)`、`manifest_bytes(manifest) -> bytes`、`find_source(manifest, id) -> Source`、`source_path(root, relative) -> Path`。M5 側の最小マニフェスト実装との統合時はこのモデル/APIへ揃える。
- `pipeline/runner.py`: `run_pipeline(images, directory, source_id="SRC1", preset="ai", overrides=None, project=None, position=(0,0)) -> (index_frames, rgba_palette, report)`。画像は RGBA uint8 のフレーム列。プロジェクトの正本は変更せず、段階画像・result.png・報告を保存する。
- `ops/ingest.py` の公開 Op は `import_image`（ingest）、`list_sources` / `get_source`（query）。配置は登録済み ingest の内部呼出しを `core/transactions.py` が1トランザクションで処理する。新規正本と配置の保存も1回にまとめる。原画像と拒否報告は配置失敗後も残す。
- `pipeline/cli_api.py` の `convert(input_path, output_path, **options)` と `detect_grid(path, **options)` は M3 用。`convert` は `preset`、`pipeline`（または各設定節）、`on_gate_fail`、`stages` を受ける。結果は JSON 化可能な辞書、失敗は `CyberSpriteError`。CLI パッケージは M6 では編集しない。

較正の正本は [tests/pipeline/CALIBRATION.md](../tests/pipeline/CALIBRATION.md)。MCP のシナリオ2は M4 統合前のため直接 Op の pytest で同じ流れを検査し、生成(d)の入力は M9 待ちとしている。
