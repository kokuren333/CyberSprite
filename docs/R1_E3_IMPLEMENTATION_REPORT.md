# R1-E3 実装報告（2026-11-12）

## 実装したもの

- `platforms/__init__.py`: 共通PluginManagerへ接続。factory前のAPI 1検査、enabled/disabled、整数JSON、ID整合、重複拒否、metadataだけの一覧を維持した。
- `core/review_sheet.py`、`ops/previews.py`: H-08の1枚PNG。実寸screen枠・背景別表示、整数拡大、シルエット、付録Bの明度、E2の登録済みguide、タグの再生列。番号と`panels`で内容・座標を返す。CLIは`preview --layout review`。実寸を維持できないscreen/生成予算の超過は生成前に拒否する。
- `core/craft.py`、`quality_platform.py`: fill/depth/flat/4近傍領域密度/暗い輪郭の比、ランプ別使用段数、part.*寸法比を全frameで測る。craftがあると`metrics.platform.craft.frames`を常に返す。Q-CRF-01はframe/metric別で、severity:errorでもinfoを保ち、関門にしない。
- `core/palette_units.py`: 非表示の層・未参照タイルも含むQ-PLT-04。行数・混在・slot0・元座標のtile/block格子を検査する。tilemapはタイルごとの配列で扱い、巨大な展開マップを先に確保しない。同じ違反でも各blockの矩形を保持する。Q-PLT-06はE1の指標へ反転予算と未参照タイルを接続した。同RGBAの別番号も厳密に保持し、非閉包frameだけは従来のnearest参考値を使う。
- `data/platforms/`: cgb、nes、sfc、md、gbaの5定義。代表的なspriteモードを明示し、NESにはRGB色表を同梱せず、利用者のmaster_palette/master_colorsを必須にした。
- `formats/native.py`、`plugin_export.py`: `export_native`と内蔵`gb-2bpp`をexportersの共通経路へ接続。独立decoderで実ファイルの各タイルをレンダラと照合する。画像層・tilemap層・tileset、リンクframe、slot0=color、非0透明番号の写像を整数だけで扱う。表現不能はallow_invalid/severity=offでも拒否し、既存出力を保持する。
- `core/models.py`、`pixels.py`、`ops/palette.py`、`drawing.py`: palette.ramps、厳密な@ramp:k、shift_ramp、outline.selective。共有セル・mask・undo・パレット番号の並替え・.aseprite予約メタデータの往復を維持した。空rampsは正準JSONに出さず、旧正本bytesを保つ。
- CLI/MCPは共通Opを利用する。登録数は89 Op、生成無効の標準MCPは87ツール。journal/history、MCPの実行器、quality.pyのcluster処理は変更していない。

## 受け入れ確認

- [x] task 0: 許可されたplatform factoryだけの読み込み、API不適合のfactory未呼出し、disabled優先、一覧の非import。
- [x] NDS/DMGのreview PNGを実CLIで作り、実ファイルを開いた。パネル、実寸と倍率、guideの同じ行での隣接、タグの有限往復列、空/過大入力を試験した。
- [x] Q-CRF-01: 手計算ベクタ（5×5中の3×3単色でfill=360、depth=2、flat=111、領域密度=11、暗輪郭=1000）、空画像、部品比300、指標ごとのデルタ、errorに昇格しないこと。
- [x] Q-PLT-04/06: object/layer/tile/block、3種類のslot0、行数超過、複数blockの矩形、反転で2種→1種となる2×2ベクタ。
- [x] 追加5機種の定数を公開技術資料と照合。NESに標準RGB表があるとは主張しない。代表モード以外の制約・実行時の割付は推測しない。
- [x] gb-2bpp: 手計算JSON、固定seed100タイル、層/セット/リンクframe、独立復号、色・alpha・行・寸法の拒否、壊れたdecoderと保護出力先、MCP SDKとCLI。
- [x] ramps: 厳密参照、範囲・素材衝突の拒否、1段移動・端固定・mask・リンク共有・undo、選択輪郭、正準JSONと.aseprite往復。
- [x] 延期項目をSPEC/I-1515に明記した。
- [x] 最終全体pytest: **1725 passed / 8 skipped（442.04秒）**。終了コード0。

## 検証

専用3ファイルは62 passed（24.35秒）。その後の同RGBA別番号ベクタも含む最終確認 `uv run pytest tests/unit/test_r1_e3.py tests/unit/test_r1_e3_native_ramps.py tests/mcp/test_r1_e3_contracts.py tests/test_platforms.py tests/test_goldens.py -q --tb=short` は **131 passed（36.36秒）**。追加のR1-E3試験63件を含む。既存platform/pluginも含む先行確認は118 passed（34.75秒）で、専用確認と重複する。実CLI実演は13呼び出しで成功した。

`uv run ruff check .`、`uv run ruff format --check .`（219ファイル）、`uv run mypy src/cybersprite/core src/cybersprite/ops`（45ファイル）、`uv run python tools/gen_schemas.py --check`、`uv run python tools/check_repository.py`、`git diff --check` は成功した。

最終全体 `uv run pytest -q --tb=short` は **1725 passed / 8 skipped（442.04秒）**、終了コード0。skipはWindowsのsymlink権限5件と未導入の任意コンバータ3件。最終コード61b6350で全件を実行した。

全体の初回完走は1720 passed / 8 skipped / 1 failed（854.44秒）。失敗はtest_ops.pyの固定された登録名一覧に新しい2 Opがないことだけで、専用試験には両Opの成功・拒否・undo/decoder経路がある。一覧を補い、当該契約は1 passed（2.51秒）を確認した。最終成功ログは `build/r1-e3-validation/pytest-final-3.log`。初回ログは `pytest-final.log` に保持する。最初の全体実行は8%時点でnativeの追加ガードを含むコードへ切り替えるため中断し、BLAS/OpenMPスレッド数を1にして開始し直した。中断した実行を成功件数に含めない。

## 実ファイルの確認

`uv run python tools/r1_e3_acceptance.py build/r1-e3-acceptance` の記録は`calls.json`と`summary.json`。成果は自作の幾何学的ベクタで、作例や意匠の合格を示すものではない。

- `nds-review.png`: 646×762。256×192の枠に80×80のframeを実寸配置、4倍のキャンバス像、同倍率の小さい白黒guide、単色のシルエット、明度版、下段に0/1/2/1/0の5コマ。黒い矩形の内部に白い点があり、frameごとに横へ1pxずつ移動することを確認した。
- `dmg-review.png`: 266×268。160×144の枠に16×16のframeを配置、4倍像、guide、シルエット、明度版、同じ往復列。非透明領域の位置と、明度版に残る内部の点を確認した。
- `nds-final.png`（80×80）、`dmg-final.png`（16×16）は自前PNG decoderでコアRGBAと完全一致。両方のexportでvalidation_ok/verified=true。
- `dmg.2bpp`は192 bytes、3frame×4タイル。書出し経路で独立decoderとレンダラを照合し、実演でも12枚へ復号した。verified/validation_ok=true。

各実演のwarningは4件、いずれもQ-PLT-05として意図して残す。(1) NDSの80×80/DMGの16×16キャンバスは単一物体サイズではない。(2〜4) frame 0/1/2の6×7セルはタイル倍数でも単一物体サイズでもない。幾何学ベクタを小さいまま描き、その最小矩形を正準化した結果である。warningの水準を下げて隠していない。

## Goldenと仕様変更

唯一の更新器 `uv run python tools/update_goldens.py --case m11_nds --case m11_dmg` を使用した。更新前の再計算との差を読み、更新後のgit diffも確認した。

- `m11_nds/expected/tx0.json`: E2のnew_points（Q-PIX-02、L1、frame0、原点1点）と、未使用色Q-PAL-02の件数2→1・本文のupdated_issuesを追加。
- `m11_dmg/expected/tx0.json`: 同じ原点1点と、未使用色件数3→2のupdated_issuesを追加。

これは統合元に残っていたE2契約の期待値の遅れである。他の25 goldenケースは更新不要だった。既存の正本・PNG・画素配列・画素hashは全て不変。新規native vectorは外部アセットを使わず手計算した。

SPECは§5.3.2、§5.13.5、§6.7.1、新§8.9、関連MCP表、§15、M12/M13、付録Cを局所更新した。project schemaは追加Rampモデルだけを生成した。新しいerror codeは足さず、既存のE_INVALID_ARGS/E_LIMIT_EXCEEDED/E_VALIDATION_FAILED/E_UNSUPPORTEDを具体化した。AGENTSとskillsは引数の事実だけを補足した。

## Design forks decided

判断は **I-1501〜I-1517**。DECISIONSに各1行で記録した。

| 判断 | 選択と理由 | 優先した根拠 |
|---|---|---|
| 1501 | 共通PluginManager、API/許可の二重経路を解消 | 追加task 0、Fable §3.1.5 |
| 1502〜1503、1517 | 中立な番号付きパネル、Lの整数灰色、screen枠と実寸を守る事前拒否 | Fable §3.3.2 H-08 |
| 1504〜1505 | 測定の分母・端・4近傍・部品keyを整数で固定 | Fable §3.1.7 H-06 |
| 1506 | Q-CRFをmetric別に識別し、info固定 | Fable §3.1.7の「関門にしない」が既存集約より優先 |
| 1507〜1508 | 元座標の局所行と反転indexタイルを検査。bank再配置の最適化はしない | Fable §3.1.7/§3.1.10、Codex §6.2 |
| 1509〜1510 | 代表モードだけを内蔵、NESの色表は利用者指定 | Fable §3.1.9のRGB非一意性 |
| 1511 | exportersの区画照合hookと独立decoder | Fable §3.1.10、Codex §6.2 |
| 1512〜1514 | 素材間の番号重複を拒否、1段移動・輪郭のタイ・remap追従を明示 | Fable §3.2.2 H-16の未定義部分を補う |
| 1515 | offset links/analyze/追加形式/sidecarは後続へ | 今回の優先0〜6を検証した境界にする |
| 1516 | 統合元のE2応答2件だけを更新器で整合 | §13.5、E2の実装契約 |

## Deferred / not done

- H-12後半のoffset links: M13-later/v1.x。schema、形式、正準化、履歴、GUIを横断する8〜15人日規模の別工程であり、一部だけ実装して既存の共有位置契約を壊さない。
- H-10 analyze: M13-later/v1.x。ユーザー設定への統計保存、入力集合hashとraw範囲の契約まで含む独立した検証を残す。画像出力・ROM container解析は追加していない。
- gba-4bpp/rgb555-leとpalette_out/map_out: 延期。予約引数の指定はE_UNSUPPORTEDで書込み前に拒否する。gb-2bppはtile streamであり、palette bank/VRAM/map配置を含む完成ゲーム用パッケージではない。
- 機種のモード切替、実行時の走査線制限、物体サイズ対やVRAM割付は検査しない。Q-PLT-06はindexパターンの予算で、bankをまたぐ局所slotへの再配置最適化はしない。
- previewのラベル・中立背景・guide配置の意匠確認、実制作物のH-07関門と合否はOpus/発注者へ。今回の工学ベクタを作例の完成と評価していない。
- Linux実行と統合ブランチへのmergeはオーケストレーターへ。

## Before/after numbers・依存

速度向上の変更・主張はなく、レビューの性能fixtureのbefore/after測定は行っていない。上記は共有Windowsでの機能試験時間で、性能改善率の根拠ではない。追加craft/未参照タイル検査を含む実制作の時間・メモリ測定は、R1-B統合後に残る。

**新規依存なし。** 既存lockのmcp/gui extrasをuv syncで導入した。pyproject.toml/uv.lock/第三者台帳に変更はなく、新しいライセンス承認や検証が必要な配布物を追加していない。

## 参照資料（PROVENANCE_LOG追記用）

公開技術文書の事実だけを利用した。外部のソースコード・画像・色表・ゲーム素材は取り込んでいない。NESdev/SNESdevの一部は直接取得が403で、検索索引が返した当該技術文書の本文抜粋で照合した。製品のソースコードは参照していない。MDの参照文書の著者はCharles MacDonaldである。

| 日付 | 参照者 | 資料 | 得た事実 | 反映先 |
|---|---|---|---|---|
| 2026-11-12 | Codex / R1-E3 | https://raw.githubusercontent.com/gbdev/pandocs/master/src/Palettes.md | CGBの8行×4、RGB555、物体slot0透明 | cgb.json、SPEC §16.4 |
| 2026-11-12 | Codex / R1-E3 | https://raw.githubusercontent.com/gbdev/pandocs/master/src/Tile_Data.md | GB/CGBの8×8、2bpp、16bytes、行/bit面順 | native.py、native vector |
| 2026-11-12 | Codex / R1-E3 | https://raw.githubusercontent.com/gbdev/pandocs/master/src/OAM.md | 8×8/8×16物体とx/y反転 | cgb.json |
| 2026-11-12 | Codex / R1-E3 | https://mgba-emu.github.io/gbatek/ | GBAの240×160、RGB555、16行×16、12物体寸法と非変形反転 | gba.json、SPEC §16.4 |
| 2026-11-12 | Codex / R1-E3 | https://www.nesdev.org/wiki/PPU_programmer_reference | NES画面・2組の256タイル・2bpp・局所パレット | nes.json |
| 2026-11-12 | Codex / R1-E3 | https://www.nesdev.org/wiki/PPU_attribute_tables | NES背景の16×16パレット選択単位 | SPEC §16.4、Q-PLT-04 |
| 2026-11-12 | Codex / R1-E3 | https://www.nesdev.org/wiki/PPU_palettes | NESのRGB色表は一意でない | nes.json、I-1510 |
| 2026-11-12 | Codex / R1-E3 | https://snes.nesdev.org/wiki/Sprites | SFCの4bpp・8パレット・正方形物体寸法 | sfc.json |
| 2026-11-12 | Codex / R1-E3 | https://snes.nesdev.org/wiki/SNES_PPU_for_NES_developers | SFCのRGB555と通常224行 | sfc.json |
| 2026-11-12 | Codex / R1-E3 | https://snes.nesdev.org/wiki/Palettes | SFCの透明slot0と色表構成 | sfc.json |
| 2026-11-12 | Codex / R1-E3 | https://www.neperos.com/article/picoxo1fc33c8979 | Charles MacDonaldのVDP技術文書。MDの3bit RGB、4行×16、8×8/4bpp、物体1〜4セル、H40/224、反転 | md.json、SPEC §16.4 |

取得を試みたが採用根拠にしなかったもの: segaretro.orgのGenesis Reference Sheets PDF、chibiakumasのページ（403）。検索結果に含まれた他のコード・サンプルや画像は使っていない。

実装コミット: 09b2679、8559df0、09ef46d、61b6350。最終文書コミット後にもcalls.json中の5件のpreview/exportを再実行し、after-commit.jsonへ結果を保存して同じ実ファイルを確認する。
