# M2 実装報告

対象ブランチ: `m2-ops`。対象は非ビジュアルの工学実装であり、デザインの採否は判断していない。

## 実装内容

- `core/registry.py`: 59 個の Op の共通契約。引数・結果モデル、種別、冪等性、破壊性、英語説明、入力・出力スキーマ、MCP annotations。プラグインは明示的な opt-in とし、定義元を保持する。
- `core/transactions.py`、`history.py`、`journal_clock.py`: 複製上での適用、リビジョン照合、直近 1000 件の冪等キー、正規化、不変条件、no_op、予行、検証デルタ、排他ロック、Windows の置換再試行、保存途中のロールバック、履歴、undo/redo、外部変更検知。gzip の時刻と OS ヘッダーは固定する。
- `ops/`: 描画、フレーム／セル、パレット、レイヤー、タグ／スライス、キャンバス、メタデータ、読取。幾何は既存の `core/raster.py` を呼び、再実装していない。共有セルの編集と、持ち主の削除・移動時の引継ぎを共通化した。
- `core/quality.py`: 22 個の Q 規則、指標、設定、指摘の順序と 64 点上限、同一性による検証デルタ。最適化キャッシュは導入せず全量再計算する。
- `core/previews.py` と `ops/previews.py`: 自前 PNG writer による市松、グリッド、定規、オニオン、最大 4 枚の変更プレビュー、インライン上限、100 リビジョン保持、前／後／マゼンタ強調の差分と最大 256 点の番号一覧。
- `formats/palette_files.py`: 配置済みの組み込みプリセットと GPL/PAL/HEX テキスト。プリセットだけ透明番号 0 を前置する。
- CLI: `op`、`apply`、`undo`、`redo`、`history`、`ops list/describe`、`preview`、`diff`、`pixels`、`palette show/presets`。`new` は登録済み入口を呼び、`validate` と `render.validation_ok` は品質検証まで含む。

## 受け入れ条件

| 条件 | 結果 |
|---|---|
| §10.4〜§10.9、§10.11 の全 Op のテスト | 正常系と未知引数、主要な意味上のエラー、登録済み cleanup stub を検査 |
| ラスタベクタとゴールデン | 既存 10 分類を維持し、`raster_ops` にベクタのダイジェストと描画結果を追加 |
| 正本のフレーム付け替え | `frame_remapping` に挿入・削除・移動・反転と各段階の正本を固定 |
| トランザクション | `transactions` の各封筒・正本に加え、ファイル同一性、再送、予行、競合、ロック、undo/redo、外部変更を検査 |
| §13.6 の性質 | クラス I の再適用、各変更の undo、シード固定の 40 操作列、不変条件、正準往復、デルタの全量比較を検査 |
| 品質規則 | 全 22 規則に検出・非検出ケース。水準、絞り込み、指標、背景の透明番号も検査 |
| 依存方向・整数処理 | クリーンルーム検査と AST 検査。core に Pillow/formats の import はない。時刻はジャーナル／ロック用 helper に隔離 |
| Windows | pytest、Ruff、スキーマ差分、クリーンルーム検査を実行 |
| Linux | ローカル環境なし。既存 CI 設定での実行待ち（I-007）。この作業では push しない |

## 実行確認

最終検査: `uv run pytest -q --tb=short` は **487 passed**（98.52 秒）。`uv run ruff check`、`uv run ruff format --check`（57 ファイル）、`uv run python tools/gen_schemas.py --check`、`uv run python tools/check_repository.py`、`git diff --check` は成功した。

次の CLI 操作を実行し、全て終了コード 0、`ok: true` を確認した。実行ログと試験プロジェクトは git 管理外の `.cybersprite/` にある。

```text
uv run cybersprite new .cybersprite/m2-smoke.csprite --size 16x16
uv run cybersprite -p .cybersprite/m2-smoke.csprite op rect layer=L1 frame=0 x=3 y=3 w=10 h=10 color=1
uv run cybersprite -p .cybersprite/m2-smoke.csprite op fill layer=L1 frame=0 x=5 y=5 color=2
uv run cybersprite -p .cybersprite/m2-smoke.csprite op line layer=L1 frame=0 x0=0 y0=0 x1=15 y1=15 color=3
uv run cybersprite -p .cybersprite/m2-smoke.csprite undo
uv run cybersprite -p .cybersprite/m2-smoke.csprite redo
uv run cybersprite -p .cybersprite/m2-smoke.csprite validate
uv run cybersprite -p .cybersprite/m2-smoke.csprite preview --grid --rulers
uv run cybersprite -p .cybersprite/m2-smoke.csprite render --out .cybersprite/m2-smoke-final.png --compression stored
```

矩形は 36、塗りつぶしは 64、直線は 16 ピクセルを書き換えた。revision は `0 → 1 → 2 → 3 → 4 → 5`。undo は revision 2、redo は revision 3 の内容を新しい版として復元した。検証は error 0 / warning 0 / info 1（Q-PAL-02、プリセットの未使用 13 色は試験上そのまま残した）。書き出しは `validation_ok: true`、`verified: true`。

最後のプレビュー `r000005_f0.png`（274×274、グリッド・定規付き）と、装飾なしの `m2-smoke-final.png`（16×16）そのものを開いて確認した。新規ゴールデンの PNG、フレーム付け替え後の正本、no_op／再送／途中失敗の封筒も確認した。

## 判断と仕様追記

判断番号は I-201〜I-210。仕様への追記は次の 3 件である。

1. §6.3: ジャーナルの `result` に再送用の成功封筒を保存する。
2. §6.7.1: 元キャンバスまたは定規を含む画像が 1024 を超える場合、インライン用プレビューだけ整数間隔で画素を抽出する。
3. §6.7.1 と付録 C: 正本保存後にプレビューを作れない場合は成功と `W_PREVIEW_UNAVAILABLE` を返す。返却結果のジャーナル保存に失敗した場合は正本・履歴・生成済みプレビューをロールバックする。

## 後続工程への申し送り

- `cleanup_pixels` は M6、`replace_color(tilesets=true)` とタイルマップの `transform_sprite` は M7 の明示的な `E_UNSUPPORTED`。PNG パレット読込は M5。
- 付録 B の規範データがまだないため、M1 の距離の仮実装を継続した。パレットの明るさ・色相の並べ替えも暫定の整数方式であり、M6 の規範表導入時に差し替える（I-206）。
- 品質検証は全量計算であり、大きなプロジェクトの性能最適化は未実施。
- プレビューの灰色、市松、グリッド、定規、赤／青オニオン、マゼンタ強調は機能確認用の単純な値である。数値は I-205 と `core/previews.py` にあり、Opus の確認対象とする。作品・ブランドのデザインは行っていない。
- M4 は `ops.execute()` と `registry().get(name).describe()` を利用できる。PNG base64 は `result.images` から MCP の画像コンテンツへ変換する。パスの許可範囲、256 KB 制限、トランスポート上の封筒は M4 の担当である。
- 新規依存はない。既存の uv ロックに従って NumPy / pydantic / Click と開発ツールを使った。外部コード・外部文書・他製品の素材は参照していない。台帳は編集していない。
