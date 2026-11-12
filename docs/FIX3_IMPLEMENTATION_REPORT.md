# FIX-3 — タイル制作ワークフローの修正

ブランチは `fix3-tiles`。e2e-04 §5 のタイル関連指摘を修正した。変更は非ビジュアルの工学実装であり、GUI・テーマ・アイコン・作例のデザインは変更していない。

## 実装と受け入れ基準

| 項目 | 状態・実装 |
|---|---|
| 1. キャンバス格子での変換 | 完了。`ops/tiles.py` は `canvas.grid.x/y` または明示した `origin_x/origin_y` と要求タイル寸法で切る。透明外周のトリム、負座標、任意原点、反転8通り、リンク保持、変換前後のRGBA一致をテストした |
| 2. delete_tileset | 完了。C・破壊的・missing_ok対応。参照中は `E_IN_USE`（終了3）とレイヤーID/名前を返す。暗黙の連鎖削除なし。曖昧名、予行、undo、再送、バッチ失敗時の原子性を検証した |
| 3. タイル一覧プレビュー | 完了。`core/previews.py` の既存合成処理を共有し、`render_preview(tileset=...)` と変更後プレビューでデータ番号付き一覧・空0の市松を表示。PNGとinlineの一致、CLIと実MCP SDK、1024px上限を検証した |
| 4. 変更通知 | 完了。`core/transactions.py` が実際の参照番号から `changed.cels` と `changed.layers` を計算する。リンク先・非表示・遮蔽を含み、未使用タイルの追加はセル変更なし。RGBA差のあるフレームだけを `changed.frames` に残す。変更セットは `changed.tilesets` |
| 5. 変換結果の枚数 | 完了。`tiles` は空0以外の登録数、`tiles_total` は0を含む総数 |
| 6. 書出しデータ | 完了。`formats/export.py` のJSONへ name/tile_w/tile_h/base_index/size、各タイルへ display_index を追加。tileset は既存ID、index は0始まりの元データ番号を維持 |
| 7. 変形順の説明 | 完了。共通Op説明に flip → 時計回り回転、タイルフラグは転置 → x → y と明記 |
| 8. 小さな改善 | 完了。CLI.md に get_tiles の呼出しと矩形単位を記載。画素格子は灰160を25%整数合成し交点も1回だけ。文書格子は従来の強度。予約空タイル0は colors_used に加算しない |
| 9. 全体検査とCLI再現 | 完了。全体1335 passed / 2 skipped。meadowのコピーで18呼出しを完走し、原本の正本バイト不変と書出しPNGを確認した |

主要な変更先は `core/{previews,transactions,quality,errors}.py`、`ops/{tiles,previews,queries,args,descriptions,__init__}.py`、`formats/export.py`、`mcp/contracts.py`。CLI/MCP/スキーマは共通レジストリから生成し、別の変更経路は増やしていない。

## 検証

- 関連単体テスト: `uv run pytest tests/unit/test_fix3.py tests/unit/test_m7_tiles.py tests/unit/test_fix2.py -q --tb=short` — **128 passed**。
- 実MCP SDKの新規試験: `uv run pytest tests/mcp/test_mcp_contracts.py::test_tileset_preview_and_deletion_through_sdk -q --tb=short` — **1 passed**。
- 全体: `uv run pytest -q --tb=short` — **1335 passed / 2 skipped、481.01秒**。スキップは既存のWindowsシンボリックリンク権限2件。
- `uv run ruff check .`、`uv run ruff format --check .`（155ファイル）、`uv run python tools/gen_schemas.py --check`、`uv run python tools/check_repository.py`、`uv run python tools/check_licenses.py --include-dev --extra mcp --extra gui`、`git diff --check` はすべて成功。
- `uv run python tools/update_goldens.py --case frame_remapping --case raster_ops --case transactions --case m7_from_layer --case m7_renumber` だけで24期待ファイルを更新し、全差分を確認した。変更は応答の cels/tilesets/layers、枚数、書出しメタデータとその長さ・ハッシュ、格子修正による m7_from_layer の正本2ファイル。既存PNG・画素配列・画素ハッシュの差分はない。

## CLIと実ファイル

再現スクリプトは `tools/fix3_acceptance.py`。`uv run python tools/fix3_acceptance.py --out build/fix3-review-session` で、原本を一時コピーして操作し、画像・JSON・全応答を残した。同じCLI手順の最終コミット後の再実行先は `build/fix3-review-final/`。

1. 原本のvalidate、17タイルの番号付き一覧、×4格子、get_tiles。
2. 元のタイル15の4反転を画像レイヤーへ描き、トリム後のセルyが正であることを確認。
3. tileset_from_layer で空0と非空1枚へ統合し、セルy=0・RGBA完全一致・変換前後プレビューのバイト同一を確認。
4. 未使用タイルを追加し、合成差なしでもタイル一覧プレビューが返ることを確認。
5. 使用中セットの削除拒否→レイヤー削除→セット削除→missing_ok再実行。
6. validate とPNG・タイルPNG/JSON書出し。全書出しが validation_ok/verified=true。

最終検証は **error 0 / warning 0 / info 1**。警告はない。制作中の Q-LYR-03（新規の空レイヤー）と Q-TIL-01（意図的に追加した未使用・重複タイル）は、試験用レイヤーとセットの削除で解消した。最終に残る Q-PIX-02（小さいクラスタの情報指摘）は原本と同じであり、原作の画素を保つため変更していない。

原本 `project.json` のSHA-256は `4e35ef13b1dbdbf6bcb35ce793acda531ed3f63674440aef4008e5b115abe6e8`。出力された before/after-conversion.png はどちらも `2a0e15c12c95ca933a84589e2acbb24d549a0f5454b27fbcb890c90432173f8f`。実書出し final.png は192×128、SHA-256 `6fda966a488b75b431db4b13f33f70c5e5e68da36a887ef699282d8d2df0dc41`。一覧・格子・変換後・編集結果のプレビューと実書出しPNG2種を開き、番号0〜16、空0、反転配置、変換前後、格子を確認した。配色・デザインの評価はしていない。

## 判断・仕様・依存・引継ぎ

- 判断は **I-781〜I-787**。以前のI-503（切り出し原点）とI-511（結果枚数）の該当規則を置換した。
- SPEC変更は §6.7.1、§8.7、§10.1.2、§10.3.1、§10.4、§10.10、§13.4、付録C。新規引数と出力、削除契約、格子、色数を補足した。
- **新しい依存なし**。uv.lock・pyproject.toml・第三者台帳は変更していない。既存のdev/mcp/gui依存のライセンス監査は成功。
- 外部資料・他製品のソース・画像・文面は参照していない。読んだ資料はリポジトリ内のAGENTS、SPEC、DECISIONS、進捗、モジュールマップ、e2e-04報告と既存実装・テストだけ。
- Linux実行は既存I-007のとおりCI待ち。mainへの統合はオーケストレーターが行う。既存のWindowsシンボリックリンク権限による2スキップを保持する。
- 表示の最終的な見やすさはOpusによる確認事項。既存の装飾と指示された25%合成を使い、新しいビジュアル判断は行っていない。非常に多数のタイルは1024px上限で整数抽出されるため、細部や番号が判読しづらくなる既存合成プレビューと同じ制約がある。
