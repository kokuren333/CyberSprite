# M3: CLI 実装報告

ブランチ `m3-cli`。Windows で検証。Linux は I-007 により CI 実行待ち。

## 実装

- `src/cybersprite/cli/__init__.py`: §9.3 の全コマンド、標準入力からの apply、共通オプション、サービスとパイプラインの遅延呼び出し、全スキーマの参照。
- `cli/generated.py`: pydantic 引数モデルからオプション・ヘルプを生成。登録された export/import/source Op へ自動追従。矩形・onion・sheet-cell・dither の CLI 表記を Op 引数へ変換する。
- `cli/output.py`: CliRunner と実 CLI 共通の JSON エラー処理、短い text 要約、正本への出力保護。ハードリンク・シンボリックリンク経由も検査する。
- `src/cybersprite/config.py`: config.toml の場所解決、未知キー禁止のスキーマ、コマンド置換名検査、生成引数からのコマンド・設定注入の拒否。doctor は登録名だけを表示する。
- `core/errors.py`: 付録 C 全コードの単一の終了コード表。未知の実装エラーは 5。
- `core/transactions.py` と `ops/__init__.py`: 明示 actor が環境変数で上書きされる M2 の不具合を修正。省略時の環境変数は引き続き有効。
- `tests/e2e/test_cli_m3.py` と `tests/unit/test_cli_config.py`: 全コマンドの成功・失敗、Op の結果モデルとの適合、後続 Op の仮登録、モジュールの受け渡し、全公開エラー、設定、出力保護、起動の import 検査、実 uv プロセスでの UTF-8 を検査する。
- `tests/e2e/test_cli.py`: new/info の結果参照を正規の `result.summary` に合わせた。
- `tools/measure_cli_startup.py`: インストール済み CLI の反復計測と importtime 監査。
- 操作の文書は [CLI.md](CLI.md)、性能の結果は [PERFORMANCE.md](PERFORMANCE.md)。

## 受け入れ基準

- [x] §9.3 の全コマンドが存在する。
- [x] 全コマンドに成功・失敗の JSON と終了コードの検査がある。後続機能の成功は仮の登録 Op / モジュールで入口を検査し、未提供時の E_UNSUPPORTED も検査した。
- [x] export の各引数は登録モデルから生成し、CLI を編集せず追加フィールドを使える。import_image の仮登録でも確認した。
- [x] --version / --help は NumPy、pydantic、Pillow、aseprite を import しない。
- [x] 実行ファイルで version 中央値 204 ms、最大 212 ms。help 中央値 291 ms、最大 377 ms。測定時の 7 回はすべて 400 ms 以下。負荷時の遅延は PERFORMANCE に併記した。
- [x] 実シェルで 16×16 の new → op → apply → undo → history → validate → preview → pixels --as sym → render を実行し、返り値と実画像を確認した。
- [ ] Linux の実行（開発機になく、既存方針 I-007 に従い CI 待ち）。

## 検査結果

最終検査の結果はこの節に追記する。

## 実セッション

`build/m3-cli-session-final/`（git 管理外）に入力 JSON、成功封筒・終了コード・stderr のログ、
プレビューと最終 PNG を保存した。後続の確認用には同じコマンドを CLI.md の例で再現できる。

| 操作 | 結果 |
|---|---|
| `new --size 16x16 --palette gray-4` | revision 0、日本語の名前を UTF-8 で取得 |
| `op rect layer=L1 frame=0 x=2 y=2 w=12 h=12 color=1` | revision 1、44 ピクセルの矩形、検証デルタ error/warning 0 |
| `apply draw.json`（line） | revision 2、8 ピクセルの線、検証デルタ error/warning 0 |
| `undo` | revision 3、線を取り消し。検証デルタ error/warning 0 |
| `history` | 作成・2 回の描画・undo の履歴を確認 |
| `validate` | ok=true、error=0、warning=0、info=1 |
| `preview --frame 0 --grid --out preview.png` | 最終変更より後の全フレーム（1 フレーム）を開いて確認 |
| `pixels --layer L1 --frame 0 --as sym` | インデックス 0/1 の矩形を確認 |
| `render --frame 0 --out final.png --indexed` | validation_ok=true、verified=true。実ファイルを再復号して 16×16・使用番号 0/1 を照合し、画像を開いた |

残した指摘は Q-PAL-02（info、未使用パレット色）の 1 件。描画 API の動作を確認する試験であり、
パレット削減は試験目的ではないため意図的に残した。警告は 0 件。
図形は診断用であり、デザイン・作例の評価は行っていない。

## 後続マイルストーンへの受け渡し

- **M4**: `cybersprite.mcp.server.serve(**options)` を同期呼び出しする。渡すキーは root（Path）、allow_dir（Path のリスト）、transport、port、profile、enable_generation、allow_plugin_op（文字列のリスト）、read_only。ImportError は終了コード 6 と `cybersprite[mcp]` の導入ヒント。稼働中の stdio は MCP プロトコルの所有とする。
- **M5**: `cybersprite.ops.registry()` に export_image/sheet/animation/aseprite/tileset/palette と import_aseprite を登録すれば CLI がそのまま使う。export --input は `cybersprite.formats.input_adapter.load_external(Path, options_dict)` が **メモリ上の Project** を返す契約。CLI は登録 Op の parse/apply/result 検証を使い、プロジェクトや来歴を作らない。sheet スキーマは `cybersprite.formats.sheet.sheet_schema() -> dict`、または既存の generate_schemas の sheet キーで受け渡せる。
- **M6**: import_image/list_sources/get_source の登録に追従する。単独変換は `cybersprite.pipeline.convert(input=..., output=..., **options) -> result_dict`、診断は `detect_grid(Path) -> result_dict`。convert の変換オプションは登録済み import_image から files/target/provenance/source を除いて生成する。--stages は CLI 固有で追加する。--sheet-cell と --dither は構造化した sheet/pipeline として渡す。
- **M8**: `cybersprite.server.serve(project=Path|None, port=int, no_browser=bool)`。
- **M9**: `cybersprite.generate` を選択時に import する。登録済み Op があればそれを実行する。なければ list_generators()、generate_image(project=..., actor=..., **options)、accept_license(project=..., actor=..., name=...) を探す。コマンド定義・任意モデル ID の注入は CLI で拒否する。実行とモデル承諾記録は M9 が担当する。
- **共有 actor の注意**: 利用面が actor を渡した場合、コアはそれを再上書きしない。MCP/GUI は環境変数があればそれを使い、なければクライアント名/gui を決めて渡す。`ops/__init__.py` の変更は import os と execute の引数既定・解決の 3 行のみなので、M5 の登録処理と統合時に両方を保持する。

後続機能の実体はこのブランチでは未提供。対応コマンドは必要なマイルストーンを示して終了 6。
schema sheet の提供、実 MCP/GUI サーバとの接続、変換・生成の実処理は各担当で統合確認する。
新たなビジュアル判断が必要な TODO はない。

## 判断・仕様・依存・参照

- 判断: I-301〜I-312（DECISIONS.md）。
- SPEC.md の変更: なし。
- 新しい依存: なし。既存 Click/pydantic 等を再利用したため、新規 LICENSE 確認・台帳追記の対象なし。
- 外部参照: なし。読んだものはリポジトリの AGENTS.md、SPEC.md、DECISIONS.md、IMPLEMENTATION_PROGRESS.md、src/README.md と既存の実装・テスト。
- GPL / プロプライエタリ製品のソース・文面・アセットは参照していない。_private / _handoff は開かず、変更・コミットしていない。
