# M6 実装報告（2026-11-12）

Windows の検証を完了した。作業ブランチは `m6-pipeline`。更新された main（`c89bc0b`）へリベース済み。CLI パッケージと第三者台帳は変更していない。

## 実装

| ファイル・モジュール | 内容 |
|---|---|
| `core/color.py`、`core/pixels.py`、`ops/palette.py` | 固定小数点 Oklab をコアへ移し、nearest 平坦化・最近色3候補・縮小パレットの remap_nearest・明るさと色相の並べ替えに接続。`pipeline/oklab.py` は互換再公開 |
| `core/sources.py` | 既存の Source/Sources モデルによるマニフェスト、source 内パス制限、ID検索、原子的保存 |
| `ops/ingest.py` | import_image（ingest）、list_sources/get_source（query）。原画複製、ハッシュ・寸法・容量・ライセンス・固定可能な時刻、再変換、シート・複数ファイル・アニメーション、関門、配置 |
| `core/registry.py`、`core/transactions.py`、`core/quality.py` | 準備済み ingest を内部トランザクションへ通し、新規正本・履歴・配置来歴をまとめて保存。保存前後のマニフェストを別々に検証し、Q-SRC が正しいデルタへ出る。失敗後も元画像と診断を保持 |
| `ops/drawing.py` | cleanup_pixels の M2 スタブを共通処理へ置換。リンク実体を一度だけ編集し、領域制限・protect・位置報告を返す |
| `pipeline/runner.py` | プリセットと上書き、ステップ1〜6、報告、全フレームの段階画像、結果PNG、関門。自前 stored PNG を再復号して照合 |
| `pipeline/grid.py` ほか | 疎な境界をすべて説明する整数格子の優先。純度、均等セルの center 縮小、色ごとの量子化、孤立点計数を整数配列で計算 |
| `pipeline/cli_api.py` | M3 指定の convert / detect_grid。PNG・報告・任意の段階ディレクトリ、複数フレームの連番出力。JSON辞書または CyberSpriteError |
| `tools/calibrate_pipeline.py`、`data/pipeline_defaults.json` | 実画像471件の較正。測定値・既定値が変わる再較正では版を上げる |
| `tools/benchmark_pipeline.py`、`tools/smoke_pipeline.py` | 性能測定と、実際に画像を開いて確認できる手動実行の再現手順 |

Q-SRC-01〜03 は M2 の既存判定を実際のマニフェストと接続した。関門の override と unknown 利用条件は配置コミットから警告になり、配置済み原画の追記改ざん・削除は error になる。失敗した配置だけで override の来歴を足さない。

## M5 と M3 の統合 API

M5 の最小マニフェスト実装との統合には、次の `core/sources.py` API を使える。

```text
read_manifest(root) -> Sources
save_manifest(root, manifest) -> None
manifest_path(root) -> Path
manifest_bytes(manifest) -> bytes
find_source(manifest, source_id) -> Source
source_path(root, relative) -> Path
```

M3 から呼ぶ関数は以下。失敗はすべてプロジェクトの CyberSpriteError へ適合させる。

```text
pipeline.cli_api.convert(input_path, output_path, **options) -> dict
pipeline.cli_api.detect_grid(path, **options) -> dict
```

convert の options は preset、pipeline、on_gate_fail、stages、および grid/downsample/background/palette/cleanup/dither/outline/gates の各節。出力は PNG と `<出力>.report.json`。段階画像は stages 指定時に残す。複数フレームは先頭が指定した出力名、後続が `_f0001.png` 等。

## 受け入れ基準

- [x] (a) 17作品 × 整数倍率2〜16 = **255/255、100%完全一致**。全件 auto。別途、元画像17件の exact も統合テストに含む。比較は RGBA。
- [x] (b) JPEG q60〜95を136件、(c) 非整数bilinearを34件、(e) 非ドット12件、(f) 誤格子34件で計測。表の正本は [CALIBRATION.md](../tests/pipeline/CALIBRATION.md)、全値は calibration_metrics.json。
- [x] §11.9 の規則で ai の grid_score=415/707、ai/photo の fidelity=466954543/233477271を採用。負例各95%拒否を満たす区間がないことを明記して、正解の全合格を優先した。exact/upscaled の無損失設定は維持。
- [x] 組み込みステップを同じ入力で再実行し、別Pythonプロセス・PYTHONHASHSEED=1/451でも報告と stored PNG がバイト一致。上書き辞書のキー順にも依存しない。
- [x] 取り込み・拒否・override・再試行・履歴・失敗時ロールバック・既存レイヤー・シート・複数ファイル・Q-SRC・非ゼロ透明番号・容量上限のテスト。
- [x] シナリオ2相当の直接Opテスト。拒否→ソースIDで設定変更→合格→cleanup→validate→書出しPNGの復号一致。
- [x] Ruff と pytest が成功。自前PNGの自己検査と、実ファイルの目視を実施。
- [ ] Linux 実行。この開発機には環境がない（I-007）。CIの両OS設定は既存のまま。
- [ ] 生成画像(d)による較正と本来のシナリオ2。M9待ちであり、現在のシナリオでは元からある非ドット画像を代用。

## 検証結果

| コマンド | 結果 |
|---|---|
| `uv run pytest -q --tb=short` | **924 passed、125.00秒**（ライセンス表記追加・リベース後の全体実行） |
| `uv run pytest tests/unit/test_transactions.py -q --tb=short` | 15 passed（ロックの型整理後。dry_run はロックを構築しないことも確認） |
| `uv run pytest tests/pipeline/test_calibration.py tests/pipeline/test_ingest_edges.py -q --tb=short` | 9 passed（較正版の更新規則・保存失敗・override・再試行を含む） |
| `uv run pytest tests/unit/test_tools.py -q --tb=short` | 24 passed（MIT-CMU 表記を追加後） |
| `uv run pytest tests/pipeline/test_ingest_edges.py tests/unit/test_transactions.py -q --tb=short` | 23 passed（最終のGIF配置開始位置と空フレーム表示時間の修正後） |
| `uv run ruff check` / `uv run ruff format --check` | 成功 |
| `uv run python tools/gen_schemas.py --check` | 成功 |
| `uv run python tools/check_repository.py` / `git diff --check` | 成功 |
| `uv run python tools/check_licenses.py --include-dev` | 既存17配布パッケージを許可と判定 |
| `uv run mypy` | **68件の既存エラーが残る**。分岐元3279f4dを別の一時ディレクトリで検査すると70件。動的pydanticスキーマ、レイヤー型の絞込み、既存パイプラインの型注釈など。新規モジュールを含む今回のエラー増加はない |

ゴールデンは `tools/update_goldens.py --case opacity_cel --case opacity_group --case opacity_layer` のみで更新した。各ケースの f2 について、画素JSON・ハッシュ・stored PNGの計9ファイル。全4画素の最近色が番号1（赤）から番号2（青）へ変わり、PNGも開いて確認した。RGB距離では同距離だった合成色に、付録Bの知覚距離を使った結果である。他のゴールデンは変更していない。

性能は [PERFORMANCE.md](PERFORMANCE.md)。1024×1024 → 64×64 の全組み込み変換を **805 / 1133 / 656 ms** で処理した。復号・段階画像・報告・最終PNG・再復号検査を含み、起動と入力生成は含まない。

## 手動実行と確認

`uv run python tools/smoke_pipeline.py` で3プロジェクトを作り、各5枚の段階画像と配置後PNGを実際に開いた。最後のPNGは読み直してレンダラおよびパイプライン結果と画素照合した。

- hero_16x16 の exact: 段階2〜5と配置後で色面・透明部分・単独点が保持される。既定の清掃を無効にした意図どおり。
- sparse_firefly_32x32 の4倍: auto が4×4を検出。非常に疎な本体と離れた点が残り、配置後は32×32。Q-PIX-02 は情報のみで、元作品の意図された単独点なので清掃しない。
- button_32x16 の4倍JPEG q75: fixed 4×4、ai、min_cluster=1。段階2からJPEG由来の境界周辺の色のばらつきが残り、後始末無効なので残る。背景は不透明のまま。配置後32×16、検証error/warningとも0。

確認ファイルは git 管理外の `.cybersprite/m6-review/`。格子なしのstage1は線を重ねず、検出格子の線は既存の診断用マゼンタを再利用した。線の見せ方の最終判断は Opus に委ねる。

## 判断・仕様変更・依存・参照

判断は **I-463〜I-473**。仕様変更は §11.3.2 の完全な整数境界を説明する補正と、§11.8 の構造上限・凍結を override で破れない旨の2点。

**追加依存はない**。既存 Pillow 13.0.0 の監査で、MIT-CMU の識別子を検査器が拒否する問題を発見した。`.venv/Lib/site-packages/pillow-13.0.0.dist-info/licenses/LICENSE` の本体の許諾原文を開き、仕様の既存許可 HPND（MIT-CMU）に対応することを確認して検査器を修正した。ライセンス方針や依存版は変更せず、`third_party/THIRD_PARTY.md` も編集していない。参照ログに1行記録した。

参照した外部資料はこの LICENSE のみ。実装アルゴリズムは仕様と既存の自作コードから構成し、他製品のソース・素材・文書・スクリーンショット、外部OSS実装は参照していない。

## 統合時の残件

- M5 のソースマニフェスト実装は上記APIと照合し、重複をまとめる。
- M4 のMCP e2eを通す。リベース後にも `tests/e2e/scenarios/` がないため、JSONLは作らず直接Opテストを残した。JSONLへ移す操作列は、`test_scenario2_reject_retry_cleanup_export` の import（fidelity=0で拒否）→source再試行（fidelity=null）→cleanup→validate→export_image。M9の(d)入手後に入力も置換する。
- export_image が未登録のこのブランチでは、シナリオ末尾は既存レンダラ・自前PNG writerを直接検査する。M5統合後は登録済みexport_imageへ接続する。
- PixelOE は任意依存で導入していない。指定時は既存の E_PLUGIN を返す。
- Linux、生成(d)、既存mypyエラーの解消、診断用格子線の視覚仕様の確認が残る。
