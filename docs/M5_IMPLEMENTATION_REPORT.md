# M5 形式 — 実装報告

対象ブランチは `m5-formats`。仕様変更なし。判断は I-401〜I-413。ビジュアルの設計・作品制作は担当していない。試験画像は幾何と色番号だけの自作入力である。

## 実装

| モジュール | 内容 |
|---|---|
| `formats/export_args.py` | 6 種の export と import_aseprite の厳密な pydantic 引数・結果モデル |
| `formats/common.py` | 検証ゲート、書式、フレーム列、実体パスの制約、書いたファイルの読み戻しと失敗時削除 |
| `formats/export.py` | 画像・シート・アニメーション・パレット・タイルセット・.aseprite の書き出し |
| `formats/sheet.py` | 項目列、5 配置、余白、トリム、重複共有、データ 3 形式 |
| `formats/animation.py` | 自前 GIF89a/LZW、自前 APNG writer/decoder、独立した Pillow GIF reader |
| `formats/palette_files.py` | GPL/PAL/HEX/PNG、パレット名、既存プリセット、プロジェクト／.aseprite 抽出 |
| `formats/aseprite_io.py` | 唯一の aseprite import、ネイティブモデル変換、型つきプロパティ、往復比較 |
| `formats/input_adapter.py` | `load_external(path, options)`。一時プロジェクトだけを返し、保存・来歴は作らない |
| `ops/export_ops.py` | export の E 登録と import_aseprite の ingest/C 登録。既存正本の更新経路は増やしていない |
| `core/sources.py` | 最小の来歴保存。M6 はここを拡張・再利用できる |
| `tools/m5_cases.py`、`tools/m5_acceptance.py` | 自作入力、実行確認と P-11 ファイルの再生成 |

既存の自前 PNG codec とコアレンダラを使用する。PNG/APNG/GIF を Pillow で書く経路はない。GIF の辞書幅変更・満杯時のリセットは固定シードの入力で独立したデコーダと照合する。

## aseprite パッケージの評価（R-01）

PyPI の `aseprite` **0.1.0** を採用・固定した。wheel の `aseprite-0.1.0.dist-info/licenses/LICENSE` とインストール後の同じファイルの原文を開き、**Apache-2.0、Copyright 2026 Mattt** を確認した。実行時の追加依存はない。台帳の更新は依頼どおりオーケストレーターに委ねる。

確認した LICENSE の SHA-256 は `95cfa5103d94d2075ca6bf0edc1becd545cf80e634a3a699ba13b9b8f838c973`。パッケージの唯一の Requires-Dist は任意の image extra の `pillow>=10.1` で、この extra は追加していない。

| 対応表の要素 | 評価・試験 |
|---|---|
| Z インデックス・セル拡張 | API にあり。Z は往復、拡張は捨てた要素の報告を試験 |
| タイルマップ／タイルセット | 32 bit、埋め込み画像、基準番号、8 反転、旧空タイル規約、タイル単位のユーザーデータを試験 |
| 型つきユーザーデータ | すべての規定型、混在 vector、入れ子、null、拡張マップを試験 |
| スライス・タグ | 複数キー、center/pivot の null、方向、repeat、独立した表示色と user_data.color を試験 |
| パレット名・プロファイル | 名前と凍結を往復。ICC の破棄、none/sRGB のマッピングに対応 |
| レイヤーフラグ・リンク | 階層、全 19 blend 値、編集ロック、表示、連続、折りたたみ、背景、移動ロックを試験。表現できない独立したリンク属性は展開 |
| 旧パレット・フレームパレット | 自作バイナリの旧 4/17 チャンク、フレームパレット統合を試験 |
| グリッド・ピクセル比 | API にあり。非対応の比を 1:1 にして報告 |
| 参照レイヤー・UUID・外部参照等 | 破棄した要素を列挙。外部のみのタイルセットは E_UNSUPPORTED |

製品 Aseprite / LibreSprite のソース、素材、サンプルは参照していない。参照した外部資料は PyPI の aseprite 0.1.0 のメタデータ・README と、Apache-2.0 を確認した同パッケージの API モデル、reader/writer、userdata の実装である。コード片の転載なし。来歴ログへの追記はオーケストレーターへの引継事項。

## 利用面との接続

引数名は §8・§10.12 のまま。`ops.registry()` に 6 export と import を追加するので M3/M4 はスキーマを取得できる。`load_external(path, options)` は Project を返す。`.aseprite` の options では quantize を受け付け、ラスターは exact を使う。

CLI/MCP が root / allow-dir を持つ場合、Op の呼び出し全体を `formats.common.export_policy(root, allow_dirs)` で囲む。形式層の相対出力はこの root を基準にする。個々のパスをすでに検査している場合でも、このコンテキストを同じ設定にそろえる。既定は cwd の配下だけを許す。

M6 には `core.sources.load_sources` と `record_import` を引き継ぐ。後者は新規取り込み用の最小実装で、パイプライン報告・段階画像・既存ソースの再処理は M6 本体の担当である。

## 受け入れ確認

- [x] §5.9.2 の両方向の往復。自作ファイルだけを使用。
- [x] パッケージの独立した Normal レンダラとも、通常画像と全 8 反転タイルの合成画素を比較。
- [x] RGBA / グレースケール、量子化の必要／明示指定、既知の差の試験。
- [x] PNG indexed/rgba × stored/zlib、5 配置、トリム、共有、分割、3 JSON、GIF、APNG のゴールデン。
- [x] stored PNG / GIF のバイト比較。zlib PNG は画素ハッシュを固定。
- [x] すべての書き出しに verified。自己検査失敗時の削除、検証ゲートと強行、overwrite を試験。
- [x] 手動の小さなアニメーションから json-hash シート・GIF・APNG・.aseprite を書き出し、復号後の全フレームを画像で確認。
- [ ] Linux 実行。ローカル環境に Linux がないため I-007 のとおり CI に引き継ぐ。
- [ ] 実機 P-11。以下の 2 ファイルをオーケストレーターが開く。

P-11 ファイル:

- `tests/roundtrip/p11/layers.aseprite` — グループ、レイヤー、リンクセル、タグ、スライス、型つきユーザーデータ。
- `tests/roundtrip/p11/tile-flips.aseprite` — 埋め込みタイルセット、タイルマップ、全 8 反転、ユーザーデータ。

通し実行は `uv run python -m tools.m5_acceptance --out .pytest_cache/m5-acceptance` で再現できる。P-11 も再生成する場合だけ `--p11 tests/roundtrip/p11` を付ける。最終書き出しのファイルと報告は指定 out に残る。GIF の 35 ms → 40 ms は仕様どおりの W_GIF_DURATION_ROUNDED として残す。取り込み元の license=unknown による Q-SRC-02 も、import_aseprite が利用条件を推定しないため意図して残す。

検証結果（Windows / Python 3.12.10）:

- `uv run pytest -q --tb=short`: **694 passed, 1 skipped**。スキップは Windows の権限によってシンボリックリンクを作成できない試験。許可ディレクトリと範囲外拒否の試験自体は通過。
- `uv run pytest tests/roundtrip tests/unit/test_m5_exports.py -q --tb=short`: **71 passed, 1 skipped**。
- `uv run ruff check`、`uv run ruff format --check`、`uv run python tools/gen_schemas.py --check`、`uv run python tools/check_repository.py`、`git diff --check`: 成功。
- 実際の `csp op export_sheet` / `export_animation`（GIF、APNG）/ `export_aseprite` と Python の公開 Op 入口を実行し、validation_ok / verified がすべて true。新しい export サブコマンドの生成自体は M3 の担当。
- P-11 の両ファイル自体を再読込し、自作入力と正本の比較が一致。実機で開く確認は未実施。

実行環境指紋は `cybersprite 0.1.0 / zlib 1.3.1 / python 3.12`。
