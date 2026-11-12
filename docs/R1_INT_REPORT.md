# R1-INT 統合報告（2026-11-12）

作業ブランチは `r1-merge`、起点は `4475308`。mainの参照更新・push・R1-D2の取り込みは行っていない。意匠は取り込んだOpusの実装を維持し、新しいビジュアル判断はしていない。

## 1. マージごとの記録

全7件を指定順に独立したmerge commitで記録した。各メッセージ末尾に指定のCo-Authored-By trailerがある。

| 順 | ブランチ・commit | 競合と解決 |
|---|---|---|
| 1 | `r1-int` / `b309d1f` | core/previews・quality・registry、ops/__init__・args・export_ops・ingest・previews・queriesを手動統合。B2の遅延登録・成分解析とB1の保存文脈・索引再送を保持し、E1の既定値とE2の保護描画・切出し・点差分・原画を接続した。DECISIONS/PROGRESSはunion。SPECの自動併合も後から精査した。 |
| 2 | `fixr1-e3` / `963bf83` | MCP ORDERはexport_nativeを保持。descriptionsはupdate_layer.backgroundとshift_ramp.directionの両方を保持。DECISIONSはunion。native、共通platform loader、craft、review、rampsと既存B/C経路の関連148件が成功。 |
| 3 | `fixr1-f1` / `9b2ece6` | SPECのMCP公開範囲はコンパクト契約と人間専用登録の両方を保持し、付録Cもunion。DECISIONS/PROGRESSはunion。Source.useとparams.useの生成用途を一致させた。生成・品質109件が成功。 |
| 4 | `fixr1-f2` / `c7ea7f3` | GENERATION/DECISIONS/PROGRESSは両側を保持。pytest markerはindependent_decoderとgpuを併記。src/READMEは統合済み機能の説明と空Diffusers extraの監査結論を併記。偽生成fixtureの120/180秒は後続F2の180秒を保持した。製品の期限は変更していない。関連40 passed / 1 skipped。 |
| 5 | `fixr1-g` / `e7ce53e` | DECISIONS/PROGRESS/PROVENANCE_LOGはunion。自動併合で重複したSPEC §3.6は後続の文書修正で一節に整理し、両側の規律を保持した。 |
| 6 | `fixr1-gui` / `076bcac` | DECISIONS/PROGRESSはunion。他は自動併合。プラットフォーム選択・バッジ・見出し・レビューシート配置・craft値をそのまま保持した。 |
| 7 | `fixr1-h` / `61ae19f` | 競合なし。ubuntu-24.04とWindowsのJS ledger checkを保持した。 |

判断番号の監査では、起点と全7ブランチのI番号の欠落・重複は0件。テーブル内に空行を挿入していない。既存の各工程の実測・未実施事項は履歴として保持した。

## 2. 統合修正

実装・回帰試験・schema更新は`03a2d00`、公開パス注釈・ローカル$defs・型・文書整合は`bdb954d`（いずれも`R1-INT:`）に記録した。最終の検証報告も同prefixで記録する。

- **遅延登録と既定値**: `AddSourceArgs/AddSourceResult`を`ops/ingest_args.py`へ移し、ingestの旧import名も再公開した。source_queryはqueriesのまま。platform既定値は_lazy_applyの実行時に適用し、正本未作成のsource読取には適用しない。summaryは品質検証せずplatform宣言だけを返す。
- **保存・再送**: new_projectのproject_lock/save_contextを保持。import_imageのplatform既定値はロック内で解決し、B1の索引再送を既定値再計算より先に実施する。add_sourceも共通保存文脈に入り、途中のmanifest保存失敗では書いた原画を復元する。独立のsource再送側車はE2のまま保持した。
- **資源予算**: 切り出し後のpreview寸法を出力予約に使う。add_source/guideは共通DecodeBudgetへ接続し、複数原画も同じ要求の累積保持量に数える。
- **品質デルタ**: B2の成分マスク・帰属キャッシュ・公開BFS64点を保持。実描画順を逆にたどり、不透明な上層が隠した下層を寄与から外す。完全な点集合は成分マスクから作り、64点以降の新規・解消も差分に含める。E2/B2の両テスト群が成功した。
- **MCPパス**: add_sourceのresult.filesを、Mのschema駆動の結果パス変換へ接続し、その戻り値をguide.fileへ渡せるようにした。領域木は汎用の再帰コピーより先に検査する。
- **用途**: 生成時はSource.useとparams.useを同じ値で保存し、後続の明示importでSource.useをcanvasへ更新する。ComfyUIの実HTTP回帰試験で確認した。
- **型検査**: Ramp/platform/region validatorとcommitted_bytesの注釈を補い、strict CIとcore/opsの両方を通す。後者のローカル変数をPathとして保持した。
- **文書整合**: 重複した§3.6を統合。F1時点のGPU未検証とF2の実機確認を区別し、§13.2のplatform規則一覧をE3と一致させた。

新規回帰は`tests/unit/test_r1_integration.py`の3件と`tests/mcp/test_r1_contract_integration.py`の3件。加えて既存ComfyUI試験へ用途一致・import後の用途を追加した。予算拒否、保存途中のI/O失敗、再送、正本未作成のsource読取、コンパクト宣言の有効な領域入力とnullable制約、完全なmask検証を試験する。

初回の圧縮は公開projectパス注釈も省いてしまい、既存のSDK契約1件が失敗した。テストを変えずに全パス注釈を復元し、説明を短くして予算内に収めた。型検査のPath変数も修正した。全体試験のもう1件はgolden追加後もREADMEが25件のままだったため、実数27件へ更新した。両方とも既存のテスト条件を維持した。

## 3. MCP定義サイズ

R1-Mと同じ`len(json.dumps([tool.model_dump(by_alias=True, exclude_none=True), ...]).encode())`で測定した。起点の78ツール99,478 bytesと、今回の87ツールは母数が違うため直接の前後比較にしない。

| profile | ツール数 | 統合直後3回（bytes） | 中央値 | 圧縮後3回（bytes） | 中央値 |
|---|---:|---|---:|---|---:|
| standard | 87 | 113126 / 113126 / 113126 | 113126 | 98576 / 98576 / 98576 | 98576 |
| minimal | 13 | 17652 / 17652 / 17652 | 17652 | 16043 / 16043 / 16043 | 16043 |

全ツールとパス注釈を保持し、extendedへの移動はしていない。一覧の説明だけを短くし、完全な説明はregistry契約に維持した。スカラーのnullable制約を同じ型の配列にまとめ、enumが既に決める型、内部領域注釈、discriminatorを一覧から除いた。大きな入れ子の投影で重複したoneOfは、全objectを拒否する不正な宣言になっていたため、有効な和へまとめた。同一のproperty形は定義自体のコストを含めて小さくなる場合だけローカル$defsへ共有し、オフライン解決と値制約を追加回帰試験で確かめた。完全なargumentSchema・実行時パス検査・Op parserは保持する。詳細は引き続きCLI/schemaから得られる。外部参照はない。

生値はgit管理外`build/r1-int-measurements/mcp-size.json`。圧縮前は`61ae19f`の自作contracts.pyを同じ87 Opに適用し、圧縮後と同じマシン・JSON直列化で各3回測定した。これは定義サイズの比較であり、通信・起動・実行速度の測定ではない。

## 3.1 Before/after numbers（実行時間）

`uv run python -m tools.r1_int_measure`が同じWindows/CPython 3.12.10/NumPy 2.3.4で起点4475308のsrcをbuild下へ凍結し、その後に統合版を各3回測る。新規依存や別環境は使わず、同じR1-B2の`benchmark_r1_b2`を両方へ適用する。BLAS/OpenMP/MKLは1 thread、設定先を隔離。測定の最終回は他の自分の試験を同時実行していないが、利用者の他プロセスは止めていない。先行の試験と重なった診断回は以下の表に使わない。

レビューの96×96・8層・45独立フレームと256×256・32独立フレームを対象とする。全フレーム同一の代替fixtureではない。coldはフレームLRUを毎回消去、cachedは同じプロセスの再利用、editは初回検証後の1画素編集（previewなし）。CLI infoは子プロセスの起動を含む。この2fixtureのplatformなしの統合影響を測り、新platform/craft検証・巨大な孤立点集合・GPU・実制作全体の時間やメモリ上限を代表しない。

単位ms。生値と中央値を分けて示す。

| fixture | 操作 | 起点3回 | 中央値 | 統合後3回 | 中央値 |
|---|---|---|---:|---|---:|
| ds_96_8_45 | validate_cold | 1183.494 / 1712.558 / 1308.838 | 1308.838 | 985.735 / 919.139 / 948.256 | 948.256 |
| ds_96_8_45 | edit | 1494.761 / 1018.426 / 1073.466 | 1073.466 | 1271.246 / 1174.689 / 1202.689 | 1202.689 |
| ds_96_8_45 | info_summary | 72.277 / 71.898 / 94.891 | 72.277 | 127.426 / 80.430 / 58.818 | 80.430 |
| ds_96_8_45 | cli_info | 1397.618 / 950.478 / 1176.142 | 1176.142 | 1387.768 / 1474.217 / 1208.876 | 1387.768 |
| ds_96_8_45 | validate_cached | 194.644 / 206.286 / 198.668 | 198.668 | 202.135 / 240.656 / 223.826 | 223.826 |
| validate_256_1_32 | validate_cold | 1348.378 / 1141.559 / 1553.246 | 1348.378 | 1312.068 / 1261.025 / 1164.405 | 1261.025 |
| validate_256_1_32 | edit | 1286.218 / 1130.690 / 939.897 | 1130.690 | 967.056 / 855.857 / 952.176 | 952.176 |
| validate_256_1_32 | info_summary | 53.160 / 37.062 / 30.519 | 37.062 | 99.464 / 50.135 / 64.017 | 64.017 |
| validate_256_1_32 | cli_info | 1292.861 / 1272.350 / 1341.890 | 1292.861 | 1278.321 / 1467.054 / 1386.347 | 1386.347 |
| validate_256_1_32 | validate_cached | 121.134 / 116.503 / 148.085 | 121.134 | 154.184 / 161.698 / 196.351 | 161.698 |

DSの編集中央値は1073.466→1202.689 ms、256²×32fのcold検証は1348.378→1261.025 ms。増減が混在し、起動・キャッシュ・空きメモリも変動するため、速度改善や目標達成を主張しない。raw JSONは`build/r1-int-measurements/before.json`と`after.json`にあり、各ソースのSHA-256、実import先、空き物理メモリも保持する。

## 4. スキーマとgolden

`uv run python tools/gen_schemas.py`でOp契約を再生成し、既存23ファイルと新規9ファイルの差分を確認した。追加9件はadd_source/conform_palette/export_native/export_plugin/list_platforms/move_cel/set_frame_ticks/set_platform/shift_ramp。既存差分はmask/region、preview guide/rect/review、platform既定値、set_cel.linked、ramps、generationのuse/rights_note、先行C/D1のpipeline契約を反映する。project/sources/sheetは統合済み成果物と一致した。

goldenの競合はなかった。今回更新器を実行したのは`m11_nds`と`m11_dmg`の各tx0.jsonだけで、E2のnew_pointsとQ-PAL-02のupdated_issuesを補った。E3側も同じ結果を既に持ち、その後のマージで追加差分は生じていない。更新コマンドは`uv run python tools/update_goldens.py --case m11_nds --case m11_dmg`。

起点からの全golden差分は次のとおり。既存ケースの変更はvalidationフィールドだけで、正本・PNG・画素・hashに変更はない。

| ケース | 既存変更ファイル | 理由 |
|---|---|---|
| frame_remapping | expected/tx0.json、tx1.json | 透明番号を色数から除外、Q-PIX新規点を追加 |
| frame_remapping | expected/tx3.json | フレームの並替えに伴うQ-PIX追加・解消点 |
| raster_ops | expected/tx0.json | 透明除外と未使用色の件数・本文のupdated_issues |
| raster_ops | expected/tx1.json | 透明除外による色数指標 |
| transactions | expected/tx0.json、tx2.json、tx6.json、tx7.json | 透明除外、Q-PIXの点差分、未使用色の件数・本文更新 |
| transactions | expected/tx3.json | 件数が同じでも未使用番号が変わる本文更新 |
| m7_renumber | expected/tx2.json | 未使用タイル番号が変わる本文更新 |
| m11_nds / m11_dmg | 各case.jsonとexpected 8ファイル | 新規platform工学ベクタ。expectedはafter.project.json、canonical.project.json、tx0.project.json、tx0.json、f0.pixels.json、f0.pixhash、f0.stored.png、f0.warnings.json。原点1画素とsnapshot・検証結果を固定 |

Opus GUI工程由来のm11のproject期待値各3ファイルは、preset_version=2とauthored ramp_stepsの追加を保持した。これもPNG/画素/hash不変。全29パス（新規2ケース各9パスと既存11応答）の分類を確認した。

## 5. 検証結果

最終コード`bdb954d`の`uv run pytest -q --tb=short`は **2071 passed / 9 skipped（464.43秒）**、終了コード0。BLAS/OpenMP/MKLを1 threadにしたWindows実行。ログは`build/r1-int-pytest-verified.log`。skipはWindowsのsymlink権限5件、未導入の任意コンバータ3件、明示env専用GPU試験1件。

初回完走は2068 passed / 9 skipped / 2 failed（442.99秒）。公開projectパス注釈とgolden README件数を根本で直し、既存テストを変更せず最終全体で成功した。その前に、追加のsource-only境界を確かめるため予備全体実行を中断しており、成功件数に含めない。最後の追加MCP回帰を含むfocused実行は17 passed（16.18秒）。

- `uv sync --extra mcp --extra gui`: 成功、既存lockのみ。
- Ruff check / format: 成功。
- core/ops mypy: 成功（50ファイル）。CIのstrict list: 成功（7ファイル）。
- schema drift / repository check: 成功。
- `uv run python tools/check_licenses.py --include-dev --extra mcp --extra gui`: 成功（42配布物）。
- GUI: npm ci、698 tests、100コントラスト対、build、Playwright 5 testsが成功。
- JS台帳: guiから`node ../tools/check_js_licenses.mjs --check`、46 installed packagesが成功。指定の`node tools/...`はリポジトリroot基準のパスなので、guiからは`../tools/...`を使用した。

Playwright終了時にWindowsのProactorがConnectionResetErrorを記録したが、5件のassertと終了コードは成功。製品UI・試験条件を緩める変更はしていない。

### 受け入れ基準

| 条件 | 状態 |
|---|---|
| 指定順の7 merge、各trailer、main非変更・pushなし | 合格 |
| E1/E2/E3とB1/B2/A2/M/Cの共通契約を保持 | 関連回帰と実CLIで合格 |
| source-only、用途一致、予算・保存復元の追加回帰 | 合格 |
| standardの全ツールを保持して100,000 bytes以下 | 合格、87 tools / 98,576 bytes |
| 全Python試験 | 合格、2071 passed / 9 skipped |
| Ruff / format / mypy両範囲 / schemas / repository / licenses | 合格 |
| GUI npm ci / test / build / e2e / JS台帳 | 合格 |
| golden全差分の確認と専用更新器の使用 | 合格 |
| 実CLI・実ファイル確認 | 17呼出し合格。最終commit後の同じ手順の証跡はbuild/r1-int-smoke-final/ |
| Linux、GPU・実ComfyUIの再試験、R1-D2 | 指定範囲外、未実施 |

## 6. 実CLIと実ファイル

再現は`uv run python tools/r1_int_acceptance.py <新しい出力先>`。17 CLI子プロセスでNDS/DMGを新規作成、mask.only_onを含む描画、outline exclude_colorsを2回（2回目no_op）、登録原画を含むreview、validate、RGBA PNG、DMG gb-2bppを実行する。PNGは自前decoder・Pillow・コアRGBAを照合し、nativeは独立decoderで12タイルへ復号する。レビューシートも実ファイルを開いて全3フレームの再生順と配置を確認する。

初回証跡はgit管理外`build/r1-int-smoke-1/`のcalls.json、summary.json、nds-review.png、dmg-review.png、nds-final.png、dmg-final.png、dmg.2bpp。最終commit後の出力先は`build/r1-int-smoke-final/`。同じ17呼出しを新規projectへ再実行し、calls.json/summary.jsonとpost-commit-proof.jsonに実ファイルのhash・commit・検証結果を保存する。

各プロジェクトのvalidateはerror=0、warning=4。各4件のQ-PLT-05は、(1)canvasが複数object構成、(2〜4)frame0/1/2の自作小矩形セルがタイル倍数・単独object寸法でないためである。工学ベクタの最小矩形を意図して保持し、severityを下げていない。未使用色・小クラスタ・tick差のinfoも工学入力の性質で、作品の美的評価の根拠にはしない。全exportはvalidation_ok/verified=true。

## 7. Design forks decided

| 判断 | 選択・理由 | 優先した根拠 |
|---|---|---|
| I-1901 | 既存のlazy/save/index replayへE1/E2を接続。summaryの全品質検証は復活させない | Fable H-02とR1-07/09/10、既存B1/B2契約 |
| I-1902 | vector成分を保持しつつ実描画順の遮蔽を採用。全点集合と公開64点は分離 | Fable H-17、E2とB2双方の独立した回帰 |
| I-1903 | source-onlyにも共通予算・保存文脈・結果パス注釈を適用 | Fable R1-13/H-11、Codex C-R1-02/03、B1/M境界 |
| I-1904 | 生成用途はSource.useとparams.useへ同値保存 | Fable H-11/H-21、E2/F1の互換読取 |
| I-1905 | 全ツール公開を保ち、一覧だけを正規化し、反復する形は有利な場合だけローカル$defsへ共有。完全な実行時契約は維持 | Fable R1-08、R1-Mの投影設計 |
| I-1906 | 重複§3.6を両側の規律を保って一節に整理。後続の取得判断を保持 | Fable H-20、Gに記録された後続の発注者判断 |

## 7.1 仕様変更

統合時のSPEC局所修正は§3.6の重複統合、§10.1.2のコンパクト一覧とローカル$defs、§12.3の用途の同値保存、§13.2の規則一覧。各ブランチから取り込んだ仕様変更は各工程の報告とmerge履歴に保持した。schema_version・核言語・ライセンス・palette lockは変更していない。

## 8. 依存・参照・Deferred / not done

新規依存0件。依存のLICENSEを新たに承認する対象はない。既存lockのmcp/gui extrasと既存package-lockだけを導入した。第三者台帳は編集していない。参照したのはリポジトリ内の仕様・両レビュー・既存各報告・自作コード・テスト・golden更新器・各ブランチの履歴だけで、外部文献・コード・画像は参照していない。取り込んだ各工程の外部参照記録はPROVENANCE_LOGと元の報告に保持した。

- mainへのfast-forwardとpushはオーケストレーターの工程。
- R1-D2は指示どおり待たず、未統合。
- Linux/CI実行、実GPU・実ComfyUIの再試験は本worktreeで実施していない。F2の実GPU結果は元の報告の証跡であり、今回の再測定と呼ばない。
- 新しい美的判断は行っていない。OpusのGUI/craft/レビュー配置を維持した。実制作物の人間の合否関門は、この幾何学ベクタの工学スモークとは別工程。
- 既存工程で延期したoffset links、analyze、追加native形式、importer、未完の専用GUIフォーム等は、今回の統合で完成したとは扱わない。
