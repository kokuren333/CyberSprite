# M7 タイルマップ 実装報告

作業ブランチは `m7-tiles`。非ビジュアルの工学実装だけを担当した。

## 実装

`src/cybersprite/ops/tiles.py` に `add_tileset`、`set_tile_pixels`、`delete_tiles`、`move_tiles`、`set_tile`、`set_tiles`、`get_tiles`、`tileset_from_layer` を実装した。引数・結果・冪等性・破壊的注釈を既存レジストリへ登録し、CLIとMCPが同じ契約を使う。全体は77 Op。

セルの剰余を原点とする格子、範囲検査、リンク共有編集、空タイル0の保護、タイル削除・移動に伴う全レイヤー／全フレームの参照付替えを扱う。画像変換はフレーム・行・列順で切り、端を透明補完し、指定反転を使う厳密一致で重複統合する。位置・リンク・レイヤーID・ユーザーデータを保つ。背景レイヤーは先に `update_layer(background=false)` で通常画像にする具体的な案内を返す。

`ops/canvas.py` の全体変形は配置とD4フラグを合成し、タイル画像を変更しない。非正方形は90/270度だけを `E_UNSUPPORTED` とする。既存の整数拡大を回帰確認した。`ops/drawing.py` の `replace_color(tilesets=true)` は全セットの非0タイルを各1回置換し、参照レイヤーと祖先のロックを守る。

`formats/export.py` はM5のシート配置、番号と矩形／tile user_dataのJSON、書込後の復号検査を再利用する。一時プロジェクトの1フレームを使い、4096を超えるタイルも書き出せる。M5の `.aseprite` アダプタは既に必要な機構を備えていたため実装を重複させず、複数セット、8フラグ、base_index、match_flips、リンク、セット／タイル／セルのuser_data、非0透明番号の往復試験を12件追加した。

`core/quality.py` のQ-TIL-01は未使用番号・重複番号対を返し、Q-TIL-02は非正方形のdフラグと座標を検出する。検証デルタの同一性キーが重複しないよう、前者は全体1件、後者はフレーム・レイヤーごと1件へまとめた。

`ops/queries.py` のnewもGPLの色名を保持する。load_paletteの置換・追記を回帰試験で固定した。`core/transactions.py` はモデル変更と合成画素差を分け、RGBA差が0のフレームをchanged.framesへ含めない。名前・凍結・同色番号の変更・表示時間・見た目に影響しない重ね順も検査した。CLI.mdとパスエラーのhintはトリム矩形・全キャンバスのrect指定・I-602のcwd配下制約を説明する。

## 受け入れ基準

| 項目 | 結果 |
|---|---|
| §10.10全Op、引数／結果／冪等性／破壊的注釈 | 合格。移動は作業指示に従い仕様へ追加 |
| 非対称3×3 L字の8反転ゴールデン | 合格。手書き期待ピクセルでも全8通りを検査 |
| 非正方形+dは転置せずQ-TIL-02 | 合格。h/v/180の合成結果も一致 |
| tile編集波及、削除／移動の番号付替え | 合格。全範囲・全挿入位置の描画とuser_data保持を検査 |
| 反転一致付きtileset_from_layer | 合格。x/y/d個別・全フラグ、重複・端補完・リンク保持 |
| export_tilesetと自己検査 | 合格。全5配置、余白・倍率・空タイル・metadata・4097タイル |
| .aseprite往復 | 合格。12追加ケース、正本・実画素・再エンコードのバイト一致 |
| transform／scale／replace_colorのtile対応 | 合格。旧M2スタブを除去、非正方形90/270のみ仕様どおり拒否 |
| Q-TIL-01/02、S-09/S-10 | 合格。検出／非検出と指摘の解決、構造不変条件違反を検査 |
| MCPシナリオ3 | 合格。in-processと実stdio、正本・実出力PNGハッシュ一致 |
| 実CLIセッションとPNG確認 | 合格。下記手順、全export検証成功、警告0 |
| Ruff／pytest | 合格。1244 passed、既存Windows権限の2 skipped |
| Linux実行 | I-007により未実施。既存CIでの検査待ち |

M0の実機確認P-01は転置→X→Yの仕様と一致済みであり、反転順について `docs/KNOWN_ISSUES.md` へ追記する必要はない。

## 検証コマンドと結果

| コマンド | 結果 |
|---|---|
| `uv sync --extra mcp` | 既存ロックから環境構築。依存・ロック変更なし |
| `uv run pytest -q --tb=short` | 1244 passed, 2 skipped、256.17秒 |
| `uv run pytest tests/unit/test_m7_tiles.py -q --tb=short` | 69 passed |
| `uv run pytest tests/e2e/test_scenario3.py tests/unit/test_quality.py -q --tb=short` | 30 passed |
| `uv run pytest tests/unit/test_m7_tiles.py tests/unit/test_quality.py tests/test_goldens.py -q --tb=short` | 最終型整理後122 passed |
| `uv run ruff check .` / `uv run ruff format --check .` | 合格、138 Pythonファイル |
| `uv run python tools/gen_schemas.py --check` | 合格 |
| `uv run python tools/check_repository.py` | 合格、禁止追跡パスなし・core依存方向正常 |
| `uv run python tools/check_licenses.py --include-dev --extra mcp` | 合格。既存I-012の個別例外を維持 |
| `uv run mypy --no-error-summary` | 既存78件、新規0件。全体の型検査は既存課題として未合格 |
| `git diff --check` | 合格 |

決定性に関わる追加ゴールデンは `m7_eight_flips`、`m7_rectangular_flips`、`m7_from_layer`、`m7_renumber` の4ケース・95ファイル。`tools/update_goldens.py` だけで生成し、PNG・画素配列・正本・応答を確認した。PYTHONHASHSEED=17/319の別プロセスで全95出力のSHA-256が一致した。既存frame_remappingの期待値変更は、2応答からフレーム5のpixels_changed=0を除いたものだけで、他フィールドと画像は不変。

シナリオ3の期待値は `uv run python -m tests.e2e.replay --case scenario3` が同じ唯一の更新器へ委譲して作った。タイル出力の実RGBAハッシュは `9d7c69b2bc4729010e282c9f144408b99e2a2762d4950c446dc496166331efd0`。

## CLI実行と確認用ファイル

```powershell
uv run python -m tools.m7_acceptance --out build/m7-review-final
```

14回のCLI子プロセス呼出しで、新規作成、セット作成、タイル追加、マップ追加、8反転配置、リンク、修正前PNG、共有タイル修正、validate、全フレームpreview、画像／tileset／.aseprite書出し、修正後PNGを作る。各変更の検証デルタを読み、全exportで `validation_ok=true` と `verified=true` を確認する。実PNGをPillowで復号しコアのRGBAと比較し、.asepriteを再読込して正本の同値性も照合する。

修正前後PNG、全フレームプレビュー、実タイルセットPNGを開き、8配置と修正波及を工学的に確認した。意匠の判断はしていない。実セッションは警告0、空の初期画像レイヤー等のinfoだけを保持する。両フレームの実出力PNGハッシュは `4484e9ea2251bebe9ec651a8a17291097ad1dcf313b59efd15988d845c391daf`。画像・transcript.json・hashes.jsonはgit管理外のbuild配下に残す。

## 判断・仕様・依存・残件

判断はI-501〜I-511。仕様変更は §5.8.2 のmatch_flipsのv1変換利用、§10.10 のmove_tiles追加とadd_tileset.if_exists列挙、§10.3.1 のchanged.framesを合成画素差に限定する明確化。

新規依存はない。third_party台帳は編集していない。外部資料・コード・他製品素材・画面は一切参照しておらず、PROVENANCE_LOGへの外部参照追記対象はない。参照したのはこのリポジトリの仕様・判断・既存実装・既存テストだけ。

残件はLinux CI、既存mypy78件、オーケストレーターの独立確認とmain統合。M7の機能TODO・ビジュアル判断のTODOはない。
