# src/

Python パッケージ `cybersprite` の置き場所。M1〜M11 のヘッドレス基盤、Op・トランザクション、CLI、MCP、形式、変換、タイルマップ、GUI、source 専用生成、platform機構を統合済み（84 Op、生成を無効にした標準MCPは82ツール）。Diffusers extra の依存追加は監査保留。M10の配布手順は `tools/build_release.py`。

`src/` レイアウトにしているのは、インストールしていない状態のコードをテストが誤って読み込むのを防ぐためである。

| ディレクトリ | 役割 | 仕様の節 | 着手 |
|---|---|---|---|
| `cybersprite/core/` | M1 の型・正準化・構造検証・レンダラに加え、`registry` 契約と登録、`transactions` 唯一の既存正本保存経路、`history` ロック・原子的保存・履歴、`journal_clock` 時刻の隔離、`quality` 品質検証とデルタ、`previews` 装飾画像の整数配列 | §5、§6、§13 | M1、M2 |
| `cybersprite/ops/` | `args` 引数モデルと `descriptions` の Field 説明、`ingest` が来歴・変換・配置、`export_ops` が形式登録、`common` 参照・リンク共有編集、`drawing` ラスタ関数の接続、`frames` フレーム／セル、`palette` パレット、`structure` レイヤー／タグ／スライス／メタデータ、`canvas` キャンバス、`queries` 読取と初期構築、`previews` PNG 保存。`__init__` の `registry()` と `execute()` が利用面の共通入口 | §6.4、§10 | M2、M7 |
| `cybersprite/formats/` | `png` 自前 PNG codec、`animation` 自前 GIF/LZW と APNG、`sheet` 配置と JSON 3 形式、`export` 共通の自己検査付き書出し、`export_args` 利用面共通の引数、`palette_files` パレット codec、`aseprite_io` 唯一のパッケージ依存境界、`input_adapter` 一時取り込み。`common.export_policy` が利用面の root/allow-dir を共有する | §5.9、§6.6、§8 | M1、M2、M5 |
| `cybersprite/pipeline/` | `runner` が6段階変換・関門・報告を実行。`decode` は復号と共通シート分割、`cli_api` は convert/detect_grid、その他は整数の純粋ステップ | §11 | M6 |
| `cybersprite/generate/` | `contracts` のバックエンド契約、`registry` の遅延プラグイン、`backends` の command/Diffusers API 接続、`licenses` の実体ハッシュと承諾、`service` の source 専用保存と再実行 | §12 | M9 |
| `cybersprite/cli/` | 全コマンド。`generated` が登録済み Op の引数から Click オプションを遅延生成し、`output` が JSON・要約・エラー封筒と正本への出力保護を担当する。GUIと生成の入口も統合済み。使い方は `docs/CLI.md` | §9 | M1〜M9 |
| `cybersprite/config.py` | ユーザーの config.toml の場所解決と厳密なスキーマ、生成コマンドの置換名検査、モデル実体の設定。`CYBERSPRITE_CONFIG_DIR` で設定ディレクトリを分離できる | §9.6、§12 | M3、M9 |
| `cybersprite/platforms/` | データだけの定義の探索・単一継承・JSON Pointer上書き。`core/platform.py`が純粋snapshotと整数色距離・tick配分、`core/quality_platform.py`がQ-PLT検証を担当。保存後は定義を読み直さない | §5.13、§10、§13 | M11 |
| `cybersprite/mcp/` | `server` が Op 実行と利用範囲、`contracts` がプロファイルとスキーマ、`paths` が入力・出力の実体パス制限、`execution` が期限とロールバックを担当。export_policy は同じ root/allow-dir を共有 | §10 | M4 |
| `cybersprite/server/` | GUI 用ローカルサーバ。GUI のビルド成果物を `static/` に同梱する | §14.6 | M8 |
| `cybersprite/plugins/` | プラグインの読み込みと公開 API | §15 | M2〜 |
| `cybersprite/data/` | 規範データ（色変換表、Bayer 行列、組み込みパレット、パイプラインの既定値） | 付録 B、§11 | M1、M6 |

## 依存の向き（必ず守る）

R1-C の `core/plugin_loader.py` と `core/plugin_settings.py` は、標準ライブラリと pydantic だけのメタデータ・許可表の低層処理である。公開の設定付き窓口は `plugins.PluginManager`。core は外側の plugins / formats / pipeline を import しない。`tools/check_repository.py` は相対 import も解決してこの境界を監査する。

FIX-5では `core/quality` の内容ハッシュ付きフレーム解析、`validation` の画素行検査、
`normalize` のトリム、`canonical` の正準行JSONを上限つきのプロセス内キャッシュで再利用する。
`report(use_cache=False)` で品質報告を全量再計算でき、実Op列による同値性試験を持つ。
`transactions` は読込・正規化後の構造検査を保ち、検証済みbytesを履歴snapshotと共有する。
GUIサーバは正本bytesを毎回読み、完全一致時だけ解析モデルを再利用する。

- `core` が import してよいのは、標準ライブラリ、NumPy、pydantic だけ。Pillow と `aseprite` は `formats` と `pipeline` だけが使う。
- `cli`、`mcp`、`server` は、Op レジストリを通してだけプロジェクトを変える。
- `core`、`ops`、書き出し、パイプラインの組み込みステップでは、浮動小数、乱数、現在時刻を使わない。

M2 のコミット処理は `normalize_cels` → `require_valid` → `dumps_project` を再利用する。M1 の `create_project` は排他作成のみで、既存正本を上書きする API はない。`render` / `render_indexed` は ndarray を返し、警告と描画用パレットが必要なら `render_result` / `indexed_result` を使う。

`ops.execute(name, project, args, actor="cli", **transaction_options)` は成功の封筒を返す。失敗は `CyberSpriteError` として返し、バッチ内の失敗には `op_index` が付く。MCP と GUI はこの入口を使い、プロジェクトを直接保存しない。`registry().get(name).describe()` が入力・出力スキーマと annotations を生成する。Op のスキーマは現時点では実行時生成であり、`schemas/` に別の正本を置かない。R1-B2では全契約の登録を維持したまま適用関数を遅延importする。`ingest_args.py` は取り込み契約だけを持ち、変換実行部を読み込まない。`get_info` はhistoryを要求しない限り履歴同期を遅延し、summaryは品質検証・validation_okを含めない。

`core.validation.validation_report` は M1 互換の構造検証である。品質を含む報告は `core.quality.report`、利用面からは登録済み `validate` を使う。品質デルタは全体を検査し、`core.quality.validation_delta` が同一性と指標の比較を担当する。R1-B2では内容ハッシュをキーとする256 MiBのフレームLRUで、前後の報告と後続トランザクションの描画・閉包・成分解析を再利用する。`core/components.py` は同色8近傍の成分をNumPy整数配列で集計し、報告する最大64点だけ従来BFS順に列挙する。永続キャッシュはない（I-1142、I-1143）。

プレビューの PNG エンコードは `ops/previews.py` から自前 writer を呼ぶ。`core` には formats の import を持ち込まない。`inline` の画像は `result.images` の PNG base64 配列として運び、M4 が MCP 画像コンテンツへ変換できる。

## M6 の統合 API

- `core/color.py` が付録 B の正本。`pipeline/oklab.py` は互換再公開であり、コアから pipeline への依存はない。
- `core/sources.py`: `read_manifest(root) -> Sources`、`save_manifest(root, manifest)`、`manifest_path(root)`、`manifest_bytes(manifest) -> bytes`、`find_source(manifest, id) -> Source`、`source_path(root, relative) -> Path`。M5 の `record_import` もこのモデル/APIを使い、.aseprite とラスターで同じマニフェストと ID を共有する。
- `pipeline/runner.py`: `run_pipeline(images, directory, source_id="SRC1", preset="ai", overrides=None, project=None, position=(0,0)) -> (index_frames, rgba_palette, report)`。画像は RGBA uint8 のフレーム列。プロジェクトの正本は変更せず、段階画像・result.png・報告を保存する。
- `ops/ingest.py` の公開 Op は `import_image`（ingest）、`list_sources` / `get_source`（query）。配置は登録済み ingest の内部呼出しを `core/transactions.py` が1トランザクションで処理する。新規正本と配置の保存も1回にまとめる。原画像と拒否報告は配置失敗後も残す。
- `pipeline/cli_api.py` の `convert(input_path, output_path, **options)` と `detect_grid(path, **options)` は M3 用。`convert` は `preset`、`pipeline`（または各設定節）、`on_gate_fail`、`stages` を受ける。結果は JSON 化可能な辞書、失敗は `CyberSpriteError`。CLI はこの API を呼び、入出力引数は input_path/output_path として渡す。

較正の正本は [tests/pipeline/CALIBRATION.md](../tests/pipeline/CALIBRATION.md)。MCPのシナリオ1〜3と5はin-process/stdioのJSONL、シナリオ4は実GUI/CLIの交互編集を検査する。生成(d)の入力は未入手で、シナリオ2の代替入力を明記している。

## M7 のタイル操作

`ops/tiles.py` がタイルセット作成、画素編集、削除・移動の全参照付替え、配置・読取、画像レイヤーからの重複統合を担当する。登録契約は既存と同じ `ops/args.py`・`ops/descriptions.py` にある。`ops/canvas.py` の全体変形はタイル画像を保持して配置と反転フラグを合成する。非正方形の90/270度だけは具体的な `E_UNSUPPORTED` を返す。

FIX-3で変換格子の既定原点を canvas.grid.x/y に修正し、未参照セットだけを消す delete_tileset を追加した。`core/previews.py` のタイル一覧も `ops/previews.py` からPNGへ運び、変更セットのプレビューを返す。`core/transactions.py` の changed.cels は、共有タイルの実参照・リンク先を含むデータ差を合成RGBA差から独立して返す。

`formats/export.py` は M5 の配置・自己検査付き writer を再利用し、1フレームの一時プロジェクトで65536枚までのタイルを列挙できる。`.aseprite` は M5 の `aseprite_io.py` をそのまま使い、複数セット・8反転・リンク・base_index・match_flips・タイルの user_data・非0透明番号を M7 の往復試験で保証する。MCP のシナリオ3は実 in-process/stdio Client の両方で同じ JSONL を再生する。
