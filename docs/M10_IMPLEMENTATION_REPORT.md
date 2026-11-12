# M10 仕上げ — 工学部分の報告

2026-11-12、Windows 11 / Python 3.12.10、ブランチ `m10-finish`。担当は非ビジュアル工学。mainへの統合、`skills/` と `examples/`、FIX-3のtile opsは担当外として変更していない。

## 実装

| 対象 | 内容 |
|---|---|
| `pyproject.toml`、`tools/build_release.py` | git管理外のGUI静的成果物をwheel/sdistへ明示収録。npm ci→原文照合→CLIアイコン書出しを含むGUIビルド→uv build→zip内容検査。古いstatic成果物は検証済みの出力ディレクトリ内だけで削除する |
| `tools/verify_release.py`、`release_probe.py` | リポジトリ外の新規venv、wheel+extrasのみの導入、cwdとPYTHONPATHの分離。CLI・MCP両入口/両版・認証付きGUIの起動と実ファイル配信確認 |
| `tools/bench.py`、`gui_test_support.py` | §13.8の全6目標、整数μsの反復値と環境記録。GUIは実WebSocketで編集とRGBA取得の往復 |
| `core/quality.py`、`render.py`、`transactions.py`、`validation.py` | report内の直前1フレームだけの厳密再利用、同一合成入力の差分描画省略、探索順を維持したクラスタ比較、サロゲート/画素行検査の高速化 |
| `core` / `ops` の型整理 | core/opsの41診断を0へ。構造モデル・正準化・参照・Op引数等の7ファイルをstrict検査。layer/celの絞り込み、NoReturn、空コンテナの注釈、変数の型混在を整理。`ops/previews.py`の変更は注釈と変数名のみで、画像処理は変えていない |
| `tests/e2e/`、`tools/m10_acceptance.py` | シナリオ4と5のJSONL、期待正本・画素・実出力ハッシュ。シナリオ1〜3の依存不足skipも除去。4はGUI/CLI混在、5は.aseprite読戻し同値 |
| `NOTICE`、`third_party/licenses/gui-bundle.txt` | Oklabの出典/パブリックドメイン、asepriteの別導入とNOTICE有無、GUI実行時JSとVite由来runtimeの帰属。監査済み全JS原文を上位集合として収録 |
| `.github/workflows/ci.yml` | core/ops全体と7ファイルstrictの型検査、両OSのGUI付きリリースビルドと新規venv試験を必須化 |
| README / CLI・MCP・GUI周辺文書 | インストール、最初の制作、文書案内、現在のモジュール構成、既知の不足、性能、検査手順を更新 |

## 受け入れ基準

| 基準 | 状態・証拠 |
|---|---|
| wheelにGUIと規範データ | 合格。152エントリ。index、JS/CSS、41アイコン、全パレット・色表・pipeline defaultsを照合。要求データ53パス。スキーマは実行時生成でコピーを使わない |
| 新規環境のCLI | 合格。wheel+`[mcp,gui]`を外部venvへ導入。version、新規作成、rect編集、validate、全フレームpreview、PNG export、exact convert、schema all。実PNGをPillowで再復号しコアRGBAと一致 |
| 新規環境のMCP | 合格。`python -m cybersprite.mcp --help`、module / `cybersprite mcp serve`の両方で2025-06-18と2026-07-28のtools/list。4組とも77ツール。2026版はdiscoverと要求ごとの_metaを使用し、旧版へのフォールバックを許さない |
| 新規環境のGUI | 合格。`cybersprite gui release.csprite --no-browser`。未認証/appは403、tokenによるauth後にindex/JS/CSS/iconが200。配信bytesとインストール済み実ファイルを照合。Node/ソースのimportは使わない |
| §13.8の全目標 | 全件測定済み。4件達成、トランザクションとGUI往復は未達。原因と次の対策をPERFORMANCEへ記録 |
| シナリオ4 | 合格。実CLIと実GUI WebSocketの交互編集。通知revision 1/2/3/4、古いexpect_revisionによる構造変更拒否時の正本バイト不変、reload、再試行、最終PNGの画素一致 |
| シナリオ5 | 合格。自作P-11 layers.asepriteをimport→unlockとpixel編集を1transaction→validate→全3フレームpreview→.aseprite/sheet export。出力.asepriteを実際に再復号し、§5.9.2の正本同値と全フレームRGBAを照合 |
| シナリオ1〜5 | 10試験すべて実行。skip / xfailなし。シナリオ2は生成(d)がなく自作非ドット入力の代用を明記 |
| 検証デルタと最終実画像 | 合格。全出力validation_ok / verified=true。シナリオ4の実PNG、5の3フレーム最終previewと実sheetを開き、個数・位置・欠落を工学的に確認。意匠の評価なし |
| Windows / Linux | Windowsで合格。LinuxはI-007の既存判断によりCI設定のみ、実行結果未取得 |
| M10の独立エージェント/作例/レビュー | 担当外。AGENTSとskillsだけの新規セッション完走、作例§13.7、レビュー依頼とFableレビューはオーケストレーターが確認する |

## 検査結果

| コマンド | 結果 |
|---|---|
| `uv sync --locked --extra mcp --extra gui` | 既存lockから同期。依存追加・更新なし |
| `uv run pytest -q --tb=short` | **1339 passed / 2 skipped、413.44秒** |
| `uv run pytest tests/e2e/test_scenario1.py tests/e2e/test_scenario2.py tests/e2e/test_scenario3.py tests/e2e/test_scenario4.py tests/e2e/test_scenario5.py -q --tb=short` | **10 passed、76.38秒** |
| `uv run pytest tests/unit/test_m10_performance.py tests/unit/test_validation.py tests/test_goldens.py -q --tb=short` | **79 passed、5.59秒** |
| `uv run mypy` | core/ops **36ファイル、0件** |
| CIと同じ7ファイルの `mypy --strict --follow-imports=silent` | **7ファイル、0件** |
| `uv run mypy --no-error-summary src/cybersprite` | **47件 / 17ファイル**。既知の不足として記録し、CI必須範囲には未整備の残りを含めない |
| `uv run ruff check .` / `uv run ruff format --check .` | 合格、163 Pythonファイル |
| `tools/gen_schemas.py --check` / `tools/check_repository.py` / `git diff --check` | 合格。スキーマドリフト、禁止追跡パス、core依存違反なし |
| `tools/check_licenses.py --include-dev --extra mcp --extra gui` | 合格、42配布パッケージ。既存I-012を維持 |
| `uv pip install hatchling==1.27.0` → `uv run --no-sync python tools/check_licenses.py --include-build` | 合格、既存I-010のbuild-only pathspec例外を維持。新しい例外なし |
| `npm test`（gui） | **627 passed**、両テーマの必須コントラスト **86/86** |
| `npm run test:e2e`（gui） | **3 passed、28.4秒**、実Chromiumと実サーバ |
| `tools/build_release.py` | npm audit脆弱性0、46 JSパッケージの原文確認、41アイコンexport、tsc/vite build、sdist→wheel、payload照合が成功 |
| `tools/verify_release.py dist/cybersprite-0.1.0-py3-none-any.whl` | 新規venvのCLI/MCP/GUIが成功。検証結果は `build/release-verification.json` |

全体の2 skipは既存Windows権限のシンボリックリンク試験（`tests/mcp/test_paths.py`と`tests/unit/test_m5_exports.py`）。ジャンクションとその他のパス検査は実行した。

最終測定の中央値: CLI189.549ms、transaction1654.159ms、render19.751ms、validate508.282ms、GUI212.382ms、pipeline464.683ms。測定境界・全反復値・原因・次の対策は [PERFORMANCE.md](PERFORMANCE.md)。

## ゴールデンと実行確認

期待値は `uv run python -m tests.e2e.replay --case scenario4 --case scenario5` が既存の `tools/update_goldens.py` に委譲して作成した。新規7ファイルだけを追加し、既存ゴールデンは上書きしていない。4の正本は8×8の4×4領域と1行の番号変更、revision=4、L2削除済み。5は8×6・3フレーム・リンク共有・タグ・スライス・型付きユーザーデータを保持し、revision=1。出力.asepriteと合成sheetの各ハッシュを確認した。

`uv run python -m tools.m10_acceptance --out build/m10-review` で実ファイルを残して再実行した。シナリオ4は検証warning=0。5のwarningは **Q-SRC-02の1件**で、import_asepriteが元ファイルの利用条件を推定せずunknownと記録する契約どおりなので残した。5のinfoはQ-ANI-03、Q-LYR-03、Q-PAL-02、Q-PIX-02×2。元の表示時間35ms、空の補助層、未使用透明番号、元fixtureの小成分を往復試験の対象として保持した。

最適化の決定性は旧クラスタ探索との50固定シード配列比較、全量reportとの比較、合成入力の各変更の失効試験、全既存ゴールデンで固定した。最適化が期待値を変更する経路はない。

## 判断・仕様変更・依存・参照

- 判断: **I-801〜I-807**。
- **SPEC変更なし**。性能目標やライセンス方針を変更していない。
- **新規依存なし**。`uv.lock`とPython台帳は編集していない。既存React 19.2.0 / React DOM 19.2.0 / Scheduler 0.27.0 / Zustand 5.0.8のMIT原文、Vite 7.3.8のMITと同梱通知、監査済みJS全文を確認し配布用コピーを追加した。aseprite 0.1.0のApache-2.0原文とRECORDを開き、独立NOTICEなしを確認した。
- 外部参照: インストール済みMCP/mcp-types 2.3.0のMIT LICENSE、版定数・runner・inboundのAPI動作（プロトコル検証用、コード転用なし）。Oklabは既存のL-11/来歴記録を使用。他製品のソース・画像・文面・スクリーンショットは参照していない。新しい参照はPROVENANCE_LOGに1行記録済み。
- 残件: Linux、47件の型診断とstrict範囲拡大、性能2件、生成(d)、Diffusers監査、GUI汎用メニュー、M0未撮影などを [KNOWN_ISSUES.md](KNOWN_ISSUES.md) に集約した。新たな配色・アイコン・画風・GUI意匠の判断は行っていない。
- オーケストレーターへの注意: FIX-3のtile ops / tileset exportは未編集。`ops/previews.py`には型整理のみの小差分があるため、同ファイルのFIX-3統合時には両方を保持する。`skills/` / `examples/`は未編集。
