# R1-E2 実装報告（2026-11-12）

## 実装範囲

- H-13: 描画 Op の `mask.only_on/not_on/region`、ellipse/polygon 領域、and/or/not 領域を追加。判定は対象の共有画像ごとに描画前の画素から一度だけ構築し、既存の `linked_frames` を維持する。
- H-14: `outline.exclude_colors` を種集合 A に適用。outside で輪郭色自身を除外すると再適用は `no_op`。既定 N を維持する。inside の例外は下記に明記する。
- H-15: `render_preview.rect` と CLI `--rect x,y,w,h` を追加。onion・格子・定規の座標位相を保持し、frames/strip/grid に対応する。
- H-16 前半: `@name` の厳密なパレット番号解決、重複時 `E_AMBIGUOUS_REF`、未知名の候補、sym `legend` を追加。
- H-17 / R1-19: 完全な Q-PIX 点集合を非直列化属性で保持し、差分層で正確な集合差を計算する。`new_points/resolved_points` は各64点と総数を返し、`updated_issues` は既存の同一性を保って件数・水準・本文の変化を返す。画素への寄与が一意なレイヤーを推定し、不透明な上層に隠れる下層を寄与から除く。
- H-11: ingest Op `add_source`、`Source.use`、side guide を追加。source 登録と preview は正本・パレット・revision を変えない。Pillow は formats 層に限定し、ヘッダー寸法検査と登録 hash の照合を行う。
- CLI/MCP は共通 Op を使用。MCP のパス制約、guide.file の戻りパス再利用、引数スキーマ、直接・optional mask・apply_ops の再帰領域制限を契約テストで確認する。関連する skills の引数事実だけを追記した。

主な追加ファイルは `core/validation_diff.py`、`formats/design_sources.py`、`tests/unit/test_r1_e2.py`、`tests/mcp/test_r1_e2_contracts.py`、`tools/r1_e2_acceptance.py`。主な変更先は `core/raster.py`、`core/pixels.py`、`core/previews.py`、`ops/args.py`、`ops/drawing.py`、`ops/ingest.py`、`ops/previews.py`。

## 受け入れ・検証

- [x] H-13: 形状と領域の画素一致、結合・上限、only_on/not_on、描画前固定、共有セルの結果。
- [x] H-14: outside の再適用 `no_op`、引数省略時 N。inside の限定は I-1463。
- [x] H-15: crop と全体 preview の切り出し一致、onion/grid/rulers、strip/grid、CLI 引数。
- [x] H-16: 名前・曖昧性・候補・sym legend。
- [x] H-17 / R1-19: 64点超の正確な集合差、既存 issue の悪化・水準変更、レイヤー寄与。
- [x] H-11: 来歴、source のみの登録、guide、正本バイト不変、復号前寸法制限。
- [x] CLI/MCP の一貫した引数・パス制約と実演。
- [x] 最終コードの全体テスト完了。
- 新規の単体・CLI・MCP 契約は53件。focused 実行は **51 passed**、その後の追加境界確認は **7 passed**（重複あり）。
- Ruff check、Ruff format check、core/ops mypy（37ファイル）、schema drift、repository check: 成功。
- 全体 `uv run pytest -q --tb=short`: **1464 passed / 2 skipped（807.93秒）**。skip は既存の Windows シンボリックリンク作成権限による2件。追加53件を含め成功した。
- CLI 実演 `uv run python tools/r1_e2_acceptance.py build/r1-e2-finalcheck` は12呼び出しで成功。保護描画による3段階の陰影、outside outline の2回実行（2回目 `no_op`）、crop、source 登録、side guide、validate、RGBA PNG 書き出しと復号照合を確認した。
- validation は error 0 / warning 0 / info 1。残る Q-PAL-02 は未使用の既定色5〜16で、工学用ベクタに必要な色だけを描いた結果として保持する。`validation_ok` / `verified` は true。crop・guide・export の実ファイルを開いて確認した。

実行コマンド:

```text
uv run pytest -q --tb=short tests/unit/test_r1_e2.py tests/mcp/test_r1_e2_contracts.py
uv run pytest -q --tb=short tests/mcp/test_r1_e2_contracts.py tests/unit/test_r1_e2.py::test_mask_intersection_empty_and_transform
uv run pytest -q --tb=short
uv run ruff check .
uv run ruff format --check .
uv run mypy src/cybersprite/core src/cybersprite/ops
uv run python tools/gen_schemas.py --check
uv run python tools/check_repository.py
uv run python tools/r1_e2_acceptance.py build/r1-e2-finalcheck
```

I-1473 の revision 進行後の再送、I-1474 の MCP パス往復、I-1475 の300段の領域木とバッチ、共有セルの保護付き移動も最終全体実行で成功した。

## ゴールデンの差分

唯一の更新器 `tools/update_goldens.py` で10個の応答 JSON を更新し、各差分を確認した。既存 PNG、正本、画素配列、画素 hash の変更はない。

| ケース | 変更した応答 | 理由 |
|---|---|---|
| frame_remapping | tx0 / tx1 / tx3 | Q-PIX の追加・解消点とフレームの対応を返す。tx3 は解消0/2、新規1/3。 |
| transactions | tx0 / tx2 / tx3 / tx6 / tx7 | Q-PIX 点差分、未使用パレット件数の2→1または1→2、同数でも未使用番号が変わる本文差分。 |
| raster_ops | tx0 | 未使用パレット件数2→1と本文の更新。 |
| m7_renumber | tx2 | 未使用タイル番号が変わる既存指摘の本文差分。件数は1→1。 |

## Design forks decided

仕様の追記は §5.3.2 / §5.10 / §6.4.1 / §6.4.9 / §6.4.11 / §6.7.1 / §10.2.2 / §10.12 / §13.4 / 付録C。§16.4 の M11–M13 は R1-E1 に委ねた。

| 判断 | 選択と理由 | 根拠 |
|---|---|---|
| I-1461 | 領域木は深さ16・256ノード。and/or は1子以上、not は1子。形状の列挙前に外接辺8192・面積16777216を制限する。 | Fable §3.2.2、Codex §5 row 3 の資源量注意 |
| I-1462 | 保護条件は積、色配列内は和。空 only_on は空選択。transform_region は移動元に適用する。 | Fable §3.2.2 の描画前判定、既存の共有セル契約 |
| I-1463 | 輪郭色除外による I は outside のみ。inside は N。種集合除外を保つと inside の再適用は内側へ進み、一般の I と両立しない。 | Fable §3.2.2 の種集合 A の指定を優先、Codex §5 row 4 の既定 N 維持 |
| I-1464 | crop はキャンバス内の正の矩形だけ。範囲外は E_OUT_OF_CANVAS。自動倍率・配置寸法は crop を使う。 | Fable §3.2.2、Codex §5 row 7 |
| I-1465 | guide.file は登録パス。x/y は原画の切り出し原点。scale 省略時は preview 倍率。右側に2px間隔、1024px超過時は共通の整数サンプリング。 | Fable §3.4 の同倍率比較・原色隔離 |
| I-1466 | 色名は完全一致、重複は番号順の曖昧エラー、未知は最大8候補。 | Fable §3.2.2、Codex §5 row 11 |
| I-1467 | legend 指定時は全非透明文字を legend で解決し62色制限を外す。dot は透明専用、hex+legend は拒否。 | Fable §3.2.2 の記号対応表 |
| I-1468 | 公開64点サンプルと別に完全点集合を保持し、集合差を計算した後に64点へ制限する。 | Fable H-17、R1-B2 と責務を分離 |
| I-1469 | updated_issues と点差分は変化時だけ追加。同一性は rule/frames/layer のまま。 | Fable R1-19、Codex §5 row 8 |
| I-1470 | source 専用登録・dry-run・永続再送記録を配置用 journal と分離し、project revision を増やさない。 | Fable §3.4 のキャンバスに入れない経路 |
| I-1471 | Source.use は canvas が後方互換の既定。明示 import で canvas へ設定する。 | Fable §3.4 |
| I-1472 | 共有 pre-decode helper がこの分岐にないため formats 内で辺8192・面積67108864を検査。アニメ原画は先頭フレームを装飾に使い、hash を照合する。 | Fable §3.4、タスクの復号前制限 |
| I-1473 | add_source の再送キー照合を revision 照合より先に行う。登録後に描画 revision が進んでも同じ再送を成功させ、キーの引数相違を先に拒否する。 | Fable R1-21 の順序修正 |
| I-1474 | guide.file に登録実体と一致する絶対パスも許し、MCP の入力パス解決を適用する。返された files をそのまま guide に渡せる。 | Fable §3.4 の登録原画制限と MCP パス規則 |
| I-1475 | optional mask のスキーマに領域容器の標識を付け、JSON Schema の anyOf より先に region 木を制限する。事前 deepcopy も廃し、PathPolicy の新規容器構築を使う。apply_ops は子Opの型付き引数を先に検査する。 | Codex §5 row 3 の再帰上限、H-13 |

## Deferred / not done

- inside outline の一般的な冪等性は、種集合 A の除外契約とは両立しないため実装していない。上記 I-1463 に仕様上の限定を記録した。
- guide under と GUI 表示は指定どおり v1.x。ramps / shift_ramp、H-08 review sheet、H-06 craft metrics、platform defaults は範囲外。
- R1-E1 の platform 機構および別分岐の pre-decode helper との統合はオーケストレーターの工程。Linux は利用できず未実行。見た目の良否の判断は行っていない。

## Before/after numbers

性能最適化は本作業の目的に含めず、速度向上の主張・before/after 計測はない。MCP の deepcopy 削除は再帰例外の修正で、速度を根拠とした変更ではない。テストの実時間は競合した Windows 環境の機能検証時間であり、性能値として扱わない。

完全点集合と集合差の保持には点数に応じた追加メモリを使う。大規模 Q-PIX 入力での追加時間・メモリ量は未計測で、R1-B2 の quality 最適化との統合後に確認する事項として残す。

## 統合時の注意

- 実装コミットは `9546d6b`、`79413c1`、`58335c7`、登録一覧の契約テスト更新は `6dedadf`。platform を扱う R1-E1 の既定倍率と crop 寸法を統合する際は、preview の切り出し・guide の倍率テストを維持する。
- R1-B2 の quality 最適化では、`Issue.full_points/count` の非直列化属性をキャッシュ・複製後も保つ。公開64点だけから差分を計算すると、上限より後の変更を失う。
- MCP のパス処理を統合する際は add_source の返却 files と guide.file の往復を維持する。領域の検査は deepcopy / JSON Schema / apply_ops の汎用走査より前に行う。

## 依存・参照

追加依存なし。既存の NumPy、pydantic、Pillow、MCP、Click、pytest を使用した。外部資料・他製品のコード・素材・文言の参照なし。参照はリポジトリの AGENTS、SPEC、DECISIONS、進捗、モジュール表、指定の二つのレビュー、既存の実装・テスト・golden 更新器のみ。ライセンス台帳は変更していない。
