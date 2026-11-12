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
- [ ] 全体pytestの集計を反映（検査中）。

## 検証とgolden

途中のplatform個別試験は **33 passed（450.01秒）**。新規の取り込み試験を加えて再実行中。全体試験はMCP/GUI extraを有効にして実行している。最初のextra無しの全体実行はMCP未導入による収集失敗だったため、全体合格には数えない。

既存goldenの変更は `frame_remapping/tx0.json, tx1.json`、`raster_ops/tx0.json, tx1.json`、`transactions/tx0.json, tx2.json, tx6.json, tx7.json` の8件。すべてvalidation.metrics_deltaのcolors_used/colors_per_frame/colors_per_frame_maxだけである。フレームの透明番号を1色と数えていた値を除いた。正本・PNG・画素配列・画素ハッシュには変更がない。読み取り専用の `tools/r1_e1_audit_goldens.py` で全差分を列挙し、`tools/update_goldens.py --case ...` でこの3ケースだけを更新した。

新規 `m11_nds` / `m11_dmg` はnew_projectを実プリセットIDから構築し、原点1画素の工学ベクタを持つ。各8期待ファイル（正本、応答、PNG、画素、ハッシュ、警告）でsnapshotと最終レンダリングを固定する。

実CLIの記録は `build/r1-e1-review/accept-z79ycw3b/records.json`、最終PNGは同ディレクトリの `nds.csprite/final.png`。検証はerror=0、warning=2、info=2、exportはvalidation_ok/verified=true。PNGは80×80、SHA-256=`1a3a8b23ada189f5a9c823c13689c1917cdd2f45f7017d66a58052032448579d`。

警告2件は意図して残した工学ベクタの性質である。(1) Q-PLT-05: 80×80のcanvasは単一のNDS物体サイズではなく複数物体の合成を要する。(2) Q-PLT-05: 1画素だけのセルは8×8の倍数でも単一物体サイズでもない。infoは未使用パレット番号2（明示補正の対象色を残した）と、単独画素クラスタ（試験対象そのもの）。美的評価には使っていない。

## 判断記録とDesign forks decided

- I-1401: platformの名称とschema_version=1。Fable §3.1.3/§3.8を優先し、旧正本を自動移行しない。移行機構は合成fixtureで別に保証する。
- I-1402: 行はindex div row_size、共有位置変更の既定はerror、相対移動はscope必須のmove_cel。Fable §3.2.1/§3.8を優先し、警告の読み飛ばしを防ぐ。
- I-1403: M11〜M13の段階分けとR1-18の透明除外。Fable §3.9に従う。
- I-1404: JSON Pointer辞書、tickの検査方法とタグの位相。仕様の未定義部分を整数規則で補った。
- I-1405〜I-1410: master_colors固定、既定パレットの予算、全候補Oklab最小と同距離RGB順、plugin発見の接合点、重複IDの順序、予約メタデータでの往復。
- I-1411: H-20の参照規律を仕様化。I-1412: free本体はalpha:any、機種のbinary制約は各機種で明示する。
- I-1413: 定義内のパレット名は登録ID、独自色は配列とし、ファイルパスは明示引数だけから受ける。MCPのパス制限を定義データで迂回させない。
- I-1414: 同じ規則・フレーム・層に複数の違反があるとき、異なる色番号・最近色・スライス・タグをwhere.findingsに保持する。

## 仕様変更

新§5.13のデータ表・解決順・snapshot・tick、platform関連Op/CLI、6規則と指標、M11〜M13、E_LINKED_CEL、色数の透明除外、H-20を追加した。master_paletteの名前だけでは外部変更を遮断できないため、解決したRGB表master_colorsを追加した。

## 依存

新規依存なし。uv syncで既存lockのmcp/gui extraを導入しただけで、pyproject.toml・uv.lock・第三者台帳を変更していない。外部のコード片・モデル重み・画像は追加していない。

## Deferred / not done

- GUIの選択UI、IDのステータス表示、Q-PLTの表示整理はOpusのGUI工程へ。見た目の判断は行っていない。
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
