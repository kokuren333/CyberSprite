# R1-E1: M11 プラットフォーム機構の報告

## 実装

- `core/platform.py`: 整数だけの完全snapshotモデル、RGBビット展開、固定整数Oklabの最近表現色、tick配分、2KB以内のguide。`platforms/`はデータの探索、単一継承、深い併合、null解除、JSON Pointer上書き、設定既定を扱う。master色表もsnapshotへ固定する。
- `data/platforms/`: 29定義。free、dmg、nds、HD4系統、汎用14役割、意味のある7組、motion。gray-4の既存RGB値は変えず、自作の慣用値で実機RGB規格ではないことを明記した。
- `ops/platform_ops.py`: set_platform、list_platforms、conform_palette、set_frame_ticks。既存set_celにlinked、move_celに必須scopeを追加。CLI/MCPは同じOpを使う。新規作成、タイル寸法、プレビュー、書き出し、取り込みの既定を接続した。
- `core/quality_platform.py`: Q-PLT-01/02/03/05/07/08とmetrics.platform。quality.pyの編集は色数の透明除外と新規モジュール呼出しの局所変更だけ。`.aseprite`予約メタデータでもsnapshotを保持する。
- SPEC §5.13、§9、§10、§13、§16.4、付録CとH-20の§3.6、AGENTS §6.1、srcのモジュール表、NOTICEを更新した。

## 受け入れ基準

- [x] SPECを先に改訂、M11/M12/M13を追加。
- [x] platformはschema_version=1の省略可能キーで、nameの直後。無しの旧正本はバイト不変。合成schema_version=0を使ってMIGRATIONS経路を試験。
- [x] 解決順、継承、循環、部分指定、JSON Pointer、設定既定、保存後の定義非依存。
- [x] 全6規則の手計算ベクタ、表現色の補正、24fps配分、リンクのerror/all/unlinkとframe/shared。
- [x] NDS/DMGの新規goldenを唯一の更新器から生成。
- [x] MCP SDKで作成→描画→validate→conform_palette→export、結果スキーマを検査。
- [x] 実CLIの作成→描画→補正予行→補正→検証→プレビュー→書き出し。最終PNGを自前デコーダとPillowで照合し、ファイルも開いて確認。
- [x] Ruff check/format、core/ops mypy（39ファイル）、schema drift、repository check。
- [x] 最終全体pytestは1455 passed / 2 skipped。スキップは既存のWindowsシンボリックリンク権限2件。

## 検証とgolden

最新のplatform個別試験 `uv run --extra mcp --extra gui pytest tests/test_platforms.py -q --tb=short` は **41 passed（22.31秒）**。取り込み既定値の履歴・冪等再送、JSON Pointerの途中の配列添字も含む。最終全体試験 `uv run --extra mcp --extra gui pytest -q --tb=short` は **1455 passed / 2 skipped（582.06秒）**、終了コード0。ログは `build/r1-e1-review/pytest-final.log`。スキップは `tests/mcp/test_paths.py:117` と `tests/unit/test_m5_exports.py:465` の既存Windowsシンボリックリンク権限制約である。最初の全体試験で検出したCLI終了コード表の `E_LINKED_CEL` 欠落は修正し、付録Cとの全件照合も最終全体試験に含めて通過した。

最終の静的検査は `uv run ruff check .`、`uv run ruff format --check .`（180ファイル）、`uv run mypy src/cybersprite/core src/cybersprite/ops`（39ファイル）、`uv run python tools/gen_schemas.py --check`、`uv run python tools/check_repository.py` がすべて成功。`uv build --wheel --out-dir build/r1-e1-dist` も成功し、wheel内の29定義がsourceとバイト同一で、platformモデルとNOTICEも含まれることを確認した。

既存goldenの変更は `frame_remapping/tx0.json, tx1.json`、`raster_ops/tx0.json, tx1.json`、`transactions/tx0.json, tx2.json, tx6.json, tx7.json` の8件。すべてvalidation.metrics_deltaのcolors_used/colors_per_frame/colors_per_frame_maxだけである。フレームの透明番号を1色と数えていた値を除いた。正本・PNG・画素配列・画素ハッシュには変更がない。読み取り専用の `tools/r1_e1_audit_goldens.py` で全差分を列挙し、`tools/update_goldens.py --case ...` でこの3ケースだけを更新した。

新規 `m11_nds` / `m11_dmg` はnew_projectを実プリセットIDから構築し、原点1画素の工学ベクタを持つ。各8期待ファイル（正本、応答、PNG、画素、ハッシュ、警告）でsnapshotと最終レンダリングを固定する。

最後のコード変更後にも実CLIを再実行した。記録は `build/r1-e1-review/accept-2b7st7ed/records.json`、最終PNGは同ディレクトリの `nds.csprite/final.png`。検証はerror=0、warning=2、info=2、exportはvalidation_ok/verified=true。PNGは80×80、SHA-256=`1a3a8b23ada189f5a9c823c13689c1917cdd2f45f7017d66a58052032448579d`。前回とバイト同一で、実ファイルを再度開いて確認した。

警告2件は意図して残した工学ベクタの性質である。(1) Q-PLT-05: 80×80のcanvasは単一のNDS物体サイズではなく複数物体の合成を要する。(2) Q-PLT-05: 1画素だけのセルは8×8の倍数でも単一物体サイズでもない。infoは未使用パレット番号2（明示補正の対象色を残した）と、単独画素クラスタ（試験対象そのもの）。美的評価には使っていない。

## 判断記録とDesign forks decided

- I-1401: platformの名称とschema_version=1。Fable §3.1.3/§3.8を優先し、旧正本を自動移行しない。移行機構は合成fixtureで別に保証する。
- I-1402: 行はindex div row_size、共有位置変更の既定はerror、相対移動はscope必須のmove_cel。Fable §3.2.1/§3.8を優先し、警告の読み飛ばしを防ぐ。
- I-1403: M11〜M13の段階分けとR1-18の透明除外。Fable §3.9に従う。
- I-1404: JSON Pointer辞書、tickの検査方法とタグの位相。Fable §3.1.4/§3.1.5の未定義部分を整数規則で補った。
- I-1405: master_colorsも保存する。Fable §3.1.3/§3.1.5のsnapshot原則とCodex §6.1に従い、外部色表の更新で検証結果が変わる経路を除いた。
- I-1406: 色予算で制限するのは既定パレットだけ。Fable §3.1.4/§3.1.6に従い明示引数を優先し、DMG背景の4階調と物体の3不透明色を区別した。
- I-1407: 表現可能な全候補から付録Bの固定整数Oklab距離最小を選び、同距離はRGB辞書順。Fable §3.1.6の単一量子化とconform_paletteの最近色要件に従い、独立したチャンネル丸めとの差をRGB555ベクタで固定した。
- I-1408: plugin発見を1関数に隔離。Fable §3.1.5のentry pointと今回のR1-C接合指示に従い、JSON定義を返す最小契約を採用した。
- I-1409: 利用者定義の同IDはパス辞書順の後勝ち、plugin間の同IDはE_PLUGIN。Fable §3.1.5で未定義の同順位だけを補い、走査順への依存を除いた。
- I-1410: 予約メタデータでもsnapshotを往復する。Codex §6.1の既存形式との互換境界に従い、platformなしのデータは変更しない。
- I-1411: Fable §3.5/§3.9のH-20を仕様化。I-1412: Fable §3.1.2の「レトロからモダン」を満たすためfree本体はalpha:anyとし、binary制約は各機種で明示する。
- I-1413: 定義内のパレット名は登録ID、独自色は配列とし、ファイルパスは明示引数だけから受ける。Codex §6.1のデータ定義という境界を維持し、MCPのパス制限を迂回させない。
- I-1414: 同じ規則・フレーム・層に複数の違反があるとき、異なる色番号・最近色・スライス・タグをwhere.findingsに保持する。Codex §6.2の資源IDを正確に報告する要件に従う。
- I-1415: system.tileにもコアと同じ1〜256の寸法上限を適用し、既定値と指標計算による上限の迂回を防ぐ。Codex §6.1の既存上限維持に従う。
- I-1416: 取り込みの既定値はロック内で決定して履歴にも保存する。Fable §3.1.5/§3.1.6のsnapshotと既定値来歴を満たすため、冪等再送では現在のplatformを再解釈せず当初の来歴を返す。
- I-1417: Fable §3.2.1で追加するE_LINKED_CELは、編集拒否としてCLI終了コード3。未指定の終了コードを補い、付録Cの全件照合にも追加した。

## 仕様変更

新§5.13のデータ表・解決順・snapshot・tick、platform関連Op/CLI、6規則と指標、M11〜M13、E_LINKED_CEL、色数の透明除外、H-20を追加した。master_paletteの名前だけでは外部変更を遮断できないため、解決したRGB表master_colorsを追加した。

## 依存

新規依存なし。uv syncで既存lockのmcp/gui extraを導入しただけで、pyproject.toml・uv.lock・第三者台帳を変更していない。外部のコード片・モデル重み・画像は追加していない。

## Deferred / not done

- GUIの選択UI、IDのステータス表示、Q-PLTの表示整理はOpusのGUI工程へ。見た目の判断は行っていない。
- 内蔵craftはauthoredの枠を持ち、造形に関わる数値は設定していない。作法数値の採用はOpusの判断とM12/M13の測定工程へ。
- Q-PLT-04/06、実機出力、残るcgb/nes/sfc/md/gba、ずれ付きリンク、作法の測定とQ-CRF、レビューシート、生成拡張はM12/M13。
- R1-C統合時にplugin_definitionsを共通プラグイン基盤へ接続する。現在のentry point契約はID→JSON定義の辞書、またはそれを返す関数。
- 過去DS資料の遡及来歴ログは、非公開資料に触れない本作業では実施していない。オーケストレーターの記録が必要。
- Linux実行とmain統合はこのWindows worktreeの外の工程。

## Before/after numbers

性能の最適化を行っておらず、速度向上の主張はない。上記秒数は試験時間であり、レビューの性能fixtureのbefore/after測定ではない。

## 参照資料（PROVENANCE_LOG追記用）

公開技術文書の事実だけを照合し、文面・コード・画像は転用していない。以下はオーケストレーターが台帳へ移せる行である。

| 日付 | 参照者 | 資料 | 得た事実 | 反映先 |
|---|---|---|---|---|
| 2026-11-12 | Codex / R1-E1 | https://raw.githubusercontent.com/gbdev/pandocs/master/src/Tile_Data.md | DMGの8×8、2bpp、透明色番号の意味を照合 | SPEC §5.13、data/platforms/dmg.json |
| 2026-11-12 | Codex / R1-E1 | https://raw.githubusercontent.com/gbdev/pandocs/master/src/OAM.md | DMG物体8×8/8×16、反転属性を照合 | SPEC §5.13、data/platforms/dmg.json |
| 2026-11-12 | Codex / R1-E1 | https://raw.githubusercontent.com/gbdev/pandocs/master/src/Palettes.md | DMG背景1行・物体2行と4階調を照合。RGB値は自作慣用値 | SPEC §5.13、gray-4説明 |
| 2026-11-12 | Codex / R1-E1 | https://raw.githubusercontent.com/gbdev/pandocs/master/src/Tile_Maps.md | DMGマップ32×32、表示160×144を照合 | SPEC §5.13、data/platforms/dmg.json |
| 2026-11-12 | Codex / R1-E1 | https://raw.githubusercontent.com/gbdev/pandocs/master/src/Specifications.md | DMG概要の照合用に閲覧 | SPEC §5.13 |
| 2026-11-12 | Codex / R1-E1 | https://problemkaputt.de/gbatek.htm | NDS表示256×192、標準4bpp物体のパレット、RGB555、GBA系2D物体仕様を照合 | SPEC §5.13、data/platforms/nds.json |
| 2026-11-12 | Codex / R1-E1 | https://mgba-emu.github.io/gbatek/ | 同じGBATEKの公開ミラー。原サイト再取得タイムアウト時に12物体寸法と2D仕様の継承、標準16行×16を再照合 | SPEC §5.13、data/platforms/nds.json |
