# REVIEW_REQUEST_2 — 修正ラウンド1後のレビュー依頼準備（2回目）

- 作成: Codex / R1-DOC、2026-11-12 JST。オーケストレーターの総括用文書。
- 宛先: 上流工程 Fable 5.2、Codex独立レビュー担当。SPEC §16.5の観点に沿う。
- 対象: `dc0fe4f`（全R1作業統合）と本書を含む後続文書コミット。**実施時にオーケストレーターが対象SHAを固定する**。
- **実施保留**: 発注者の以前の判断どおり、修正ラウンド1後に一旦止めて仕様を締め直す。これは発注者がR2を決めたときに使う準備済み依頼で、R2を自動開始する指示ではない。
- 指摘の書式: `docs/REVIEW_2.md` に番号・重大度（blocker / major / minor / suggestion）・仕様の節・根拠（実行／読解／目視、手順・ファイル）・期待する状態。独立Codexは別文書へ記録し、対応をREVIEW_LOGへ集約する。

## 1. レビュー範囲とR1からの変更

全体は [FIX_ROUND_1_REPORT](FIX_ROUND_1_REPORT.md)、全40指摘の表は同§4、全198件のR1判断とDOC判断は同§5、現在の残件は [KNOWN_ISSUES](KNOWN_ISSUES.md)。古い工程報告の未統合・未検証を現在の状態と混同しない。

| 領域 | 主な変更 | 証拠 |
|---|---|---|
| 正本・資源保護 | 全exportの最終path、3面の保護、inputの復号前累積・描画仕事量・出力予算、import予行の配置検査 | A1/A2報告・進捗、tests/unit/test_r1_a1_exports.py、pipelineの予行／limits試験 |
| 保存・MCP・速度 | 追記履歴、1000取引索引、共通保存文脈、偽時計の境界期限、読取無lock、NumPy成分/LRU/lazy、全87ツール98,576bytes | PERFORMANCE、B1/B2進捗、M/INT報告、回帰と測定器 |
| 拡張・変換 | 共通plugin許可/API、6群＋platforms、外部3方式の実接続、生成16枚、版5閾値、格子7ベクタ、全5候補の中立実測 | C/D1/D2報告、PIXELIZE_BENCH、監査JSON |
| 制作工程・機種 | snapshot platform、代表機種、共有位置の明示、保護描画／色名／ramps、登録原画、crop/review、craft info、gb-2bpp | E1/E2/E3報告・schemas・golden27ケース、skills/workflows |
| 生成 | BYOW条件・hash・use/rights_note・Q-SRC04、登録workflow限定ComfyUI HTTP、外部CUDA監査(b)、RTX実生成 | F1/F2報告、GENERATION、fake HTTP／GPU opt-in試験 |
| GUI・文書 | Opusのplatform選択・条件バッジ・review見出し・authored craft、共有再生、3関門・pending、台帳／来歴／例外明記、CI OS固定 | R1-G/GUI進捗、docs/design/gui、THIRD_PARTY、PROVENANCE_LOG、H commit3962a41 |

名称platform／schema1維持／行index規約と共有位置の既定errorはFable §3を優先した。Codexのschema2・bank/slot/layout全面採用は行っていない。明示した延期と限定を含めて仕様適合を再確認してほしい。

## 2. テスト結果と証拠の区分

INT（D2前）はPython **2071 passed / 9 skipped（464.43秒）**、GUI698 tests／contrast100／Playwright5／build成功、core/ops50ファイルとstrict7成功、Python依存42・JS46。D2単体は別baseで1680 passed / 11 skipped、外部評価環境20 passed。加算していない。

R1-DOCの全統合版の最終検査は [総括 §7](FIX_ROUND_1_REPORT.md) の実行結果を使う。全src mypy再測定は **61件 / 20ファイル（115検査）**、core/ops必須基準とは別の既知残件。

<!-- CI_RESULT -->
**オーケストレーター追記待ち**: 最終pushのSHA・Actions URL・Windows/Ubuntu × Python3.12/3.13、GUI・wheel・独立復号の結果。e94bd7aのcore Ubuntu3.12/3.13・Windows3.12成功は確認済みとの申し送り。Windows3.13のMCP期限とGUI Ubuntu26.04のChromium失敗はB1/Hが修正、4475308のstrict committed_bytes注釈失敗はINTが修正。過去の成功を最終版の証明に読み替えない。

ローカルはWindows/Python3.12.10、BLAS/OpenMP/MKL1 thread。権限不足symlink5件、未導入外部方式6件、明示GPU1件は通常環境でskip。GPU・外部ツールの実試験は別環境の元報告で、DOCが再試験したものではない。

## 3. 数値と測定上の限界

約12作業を16GB／8論理CPUの同一Windows機で並行実行し、複数工程でメモリ圧迫を報告した。時間値は並行負荷下で、自己の試験と重ねなかった回も他process／OS負荷を固定していない。ラッパーの中断・期限切れは成功や拒否率に数えていない。各3生値・中央値・原fixtureは総括§3とPERFORMANCEにある。

| 指標 | 同条件前→後の中央値 | 限定・残件 |
|---|---:|---|
| B1、Codex §7 Hの10/1000/10000行編集 | 103.606/399.828/4448.854 → 82.190/83.319/73.059ms | 合成履歴・初期化済み索引。roll／再構築最悪値ではない |
| B1 MCP set_pixel / validate | 542.598/272.022 → 169.524/21.038ms | 32²×10独立f、初期化・stdio/HTTP通信を除く。直接set_pixel増加も元表に併記 |
| B2 DS96²・8層・45独立f編集 | 12600.196 → 2452.570ms | previewなし、目標1000未達 |
| B2 256²・32独立f cold validate | 13033.595 → 2257.868ms | 目標2000未達。cached267.214とは区別 |
| B2 小規模CLI info | 1932.556 → 1391.715ms | 起動〜終了、目標1000未達 |
| B2 4096²疎画像peak working set | 264 → 328MiB | 増加。256MiB LRUはRSS上限ではない |
| INT DS編集 / 256²cold validate | 1073.466/1348.378 → 1202.689/1261.025ms | 同じB2計測器で4475308対統合版。増減混在、platform/craftなし |
| INT MCP standard / minimal定義 | 113126/17652 → 98576/16043bytes | 全87/13ツール維持、各3回同値。速度や応答画像量の値ではない |
| 非pixel AUTO拒否 | 前後とも10/12=83.3% | **95%未達**。生成(d)8/13合格、強化候補は正例も落とす |
| F2 RTX生成（比較対象なし） | 446.6919937000057秒、観測VRAM13342MiB | 3回540.420334100003/446.6919937000057/337.9346435000043秒、PNG bytes一致。起動/hash/load/推論/保存込み、特定機のみ |

D2の同じ323入力×5方式、各3回は寸法一致builtin313/Fixer277/PPA163/Xprite321、PixelOE323は**oracle**。PPA初期倍率1は上流2と異なる。方式ごとに画素評価母数が違い、生成(d)に正解寸法はない。外部関門は復元後なので入力格子の正解率と順位付けしない。最終1672PNGを独立復号した記録はD2報告にある。

## 4. 特に再確認してほしい点（SPEC §16.5）

1. **(a) 仕様適合**: Fable32件／Codex8件の全対応表と延期理由。exportの全出力と全3面、入力／仕事量の事前拒否、dry-run配置、保存途中／封筒失敗のbytes復元。INTでE群に接続した保存・予算・source-only・再送・MCPpathに回帰がないか。
2. **(b) 決定性**: 最終CIの全matrix結果と同じgolden27ケース、固定ベクタ、独立復号。platform snapshot、透明色除外、Q-PIX完全点集合／64点表示の分離、cached／coldの報告同値。GPU同seed一致をコア水準Aへ一般化していないか。
3. **(c) クリーンルーム・ライセンス**: 台帳欠落5行、JS別表・L05/06、Pillow最低版＋lock、I-010/012承認待ち、D1/D2/F2利用者導入の区別。PROVENANCEの全転記、E3の一部403／検索抜粋による照合、参照画像・ゲーム題名の非公開規律。
4. **(d) 実際の制作**: 新セッションからAGENTS/skillsのみで、platform→原画→part→frame→3関門→最終exportを通す。**e2e-07の人間の合否はpending**。自動validateと美的判定の区別、道A/B、顔／シルエットの実寸確認、疑う3点を確認する。
5. **(e) GUI**: 共有有限再生・停止・durationとexport一致、platform選択とdefaults、バッジの原文併記、Opusのreview配置、contrast100組。R1-17/30の未実装を、platform画面追加で解消扱いにしていないか。
6. **(f) 文書**: 全40指摘の状態、H22件、設計分岐の採用理由・I番号、古い報告から現在への案内、CI/e2e差込み、performanceの代表性、ライセンスの未確認を承認済みと書いていないか。

追加の技術確認: Cの許可提供者だけの読込、plugin_api検査、importer延期。D2のrun_frames共通mesh・palette lock一度だけ・stdout非干渉・未導入hint、grid定義の再実装性。E3の表現不能nativeはallow_invalidでも拒否し独立decoderで実ファイル照合。F1は任意workflow引数を受けず登録hashに承諾を拘束し、**実ComfyUI未試験**を明記しているか。

## 5. e2e-07・参照・投稿の証拠

<!-- E2E07 -->
**追記待ち**: e2e-tests/07-ds-turnaround/ のREVIEW、設計／ブロッキング／仕上げ前シート3枚、全frame、最終PNG/native等のファイルhash・validation_ok/verified、警告ごとの理由、疑う3点、人間の合否。人間の返事まで見た目はpending。

オーケストレーターの提供事実: 2026-11-12、利用者PCのChromeから非公開参照コネクタがHTTP403を返した。回避を試みず既存private libraryを使用。コネクタ標準化の政策判断と実際の取得可能性を区別する。参照の画像・作品名・URLは公開資料に載せない。

Discordツールは利用できず未投稿。オーケストレーターから、監督者用Discord-readyファイルを `e2e-tests/07-ds-turnaround/discord/` に準備済みとの申し送りがある。DOCでは実在一覧を再確認しておらず、リストと投稿結果は監督者が追記する。文書を作ったことを送信済みと扱わない。

## 6. 発注者の判断事項（Fable §6の1〜7）

| 項目 | 現在の選択・状態 | 発注者に確認してほしい範囲 |
|---|---|---|
| 1 市販タイトルの測定値を内蔵するか | **入れていない**。内蔵craftはauthoredのNDS ramp_steps[1,5]／DMG[1,3]だけ、他の作風／比率はnull（I-1863/1864） | measured値は利用者手元だけとする運用の確定。作品からの数値を普遍則にしない |
| 2 コネクタ継続 | **後続発注指示で標準化済み**（I-1807）。Fableの「手動保存を標準」推奨より発注指示を優先。実機403時は回避せず既存library | 未決として再承認を求めない。403時の代替と非公開・少量・再利用の運用を仕様締直しで確認 |
| 3 参照画像をimagegenに渡すか | **暫定: 渡さない**。文章と計測値だけ、作品／キャラ名も渡さない（I-1808、§3.6） | 最終方針は未決。発注者の明示変更までは現行を守る |
| 4 ライセンス例外2件 | §2.1へ明文化したが **事後承認待ち**。I-010 pathspec MPL build-only、I-012 pywin32 312未使用adodbapi LGPLのWindows任意mcpのみ | 2件の限定条件を承認するか。D1/D2/F2の非許可スタックへ拡張する判断ではない |
| 5 256px級の意味 | frameかsheetか **未決**。platformはscreen/asset/exportを別々に持つので技術的に区別可能 | 実制作要求の単位を定義する |
| 6 M11/M12/M13の1.0範囲 | M11/M12とM13一部実装。offset links/analyze/追加native/sidecarsはM13-later/v1.x（I-1515） | 1.0の受入範囲を締め直す。実装済みと公開スコープ確定は別 |
| 7 両レビューの相違 | schema1/platform・位置変更error＋move_cel・行index規約を採用。Codexのschema2・bank/slot完全layoutは採らず延期。Linuxと品質をFable同様重視 | 採用理由表を確認。重大度差を口実にCI／人間合否を省略しない |

追加: **48px境界**はI-1803の経験的な目安で、統計的に較正した閾値ではない。platform.workflow優先、48px以上turnaround-parts／32px以下direct／小色数16px silhouette-first。32〜48pxの扱いと大型題材の標準工程を仕様締直しで確定する。inside outlineのI限定、importers延期、95%関門未達・性能未達の扱いも併せて確認する。

発注者項目1〜8の対応は総括§4.2。第9項の原文は公開入力になく番号対応未確定なので、オーケストレーターが原文と照合して追記する。推測で項目を作っていない。

## 7. 再現・動かし方

PowerShell、リポジトリrootから実行する。uvは既存lockを使用。licenseのbuild範囲には既存hatchlingが必要。

```powershell
uv sync --locked --extra mcp --extra gui
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
uv run pytest -q --tb=short
uv run ruff check .
uv run ruff format --check .
uv run mypy src/cybersprite/core src/cybersprite/ops
uv run mypy --strict --follow-imports=silent src/cybersprite/core/models.py src/cybersprite/core/canonical.py src/cybersprite/core/errors.py src/cybersprite/core/hashing.py src/cybersprite/core/references.py src/cybersprite/ops/args.py src/cybersprite/ops/descriptions.py
uv run python tools/gen_schemas.py --check
uv run python tools/gen_grid_vectors.py --check
uv run python tools/check_repository.py
uv run python tools/check_licenses.py --include-dev --extra mcp --extra gui
uv pip install hatchling==1.27.0
uv run --no-sync python tools/check_licenses.py --include-build
node tools/check_js_licenses.mjs --check
```

JS検査は先にguiで `npm ci` を実行する。Windows台帳のバイト照合はWindowsで行い、Linuxでは `node tools/check_js_licenses.mjs` で実nativeを監査する（HのCIと同じ）。build用hatchlingの導入は既存I-010の例外範囲のみで、事後承認を代行しない。

```powershell
Push-Location gui
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:e2e
Pop-Location
uv run cybersprite --help
uv run cybersprite plugins list
uv run python tools/r1_int_acceptance.py build/review2-int
uv run python -m cybersprite.mcp --root .
```

実CLIの出力先は未使用ディレクトリを指定する。代表性能は `uv run python -m tools.bench --representative --out build/review2-bench.json`、履歴／MCPは `uv run python -m tools.bench_persistence --out build/review2-history.json`。元commitとの比較と測定条件はPERFORMANCEの手順に従う。外部pixelizer／GPUは本体extraでは導入されない。元報告の別環境・正確な版・個別条件承諾・保存先で手動確認する。

制作はAGENTS §6とskills/READMEから始める。機械検査・実ファイル検証と人間の判定を両方記録し、e2e-07の未完欄を自動採点で埋めない。
