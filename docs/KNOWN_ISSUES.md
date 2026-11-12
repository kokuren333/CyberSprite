# 既知の不足と差異

2026-11-12、全作業統合済み `dc0fe4f` をR1-DOCで確認した状態。過去の工程別報告の未統合・未検証はその時点の記録で、現在の残件は以下を使う。制作の見た目の判定は、人間が決めるまで **pending**。全指摘の対応表は [FIX_ROUND_1_REPORT.md](FIX_ROUND_1_REPORT.md)。

| 項目 | 現状と次の対応 |
|---|---|
| 最終CI（R1-01） | 解消。`dc0fe4f` のGitHub Actions（run 43196622534）でWindows/Ubuntu × Python 3.12/3.13 のcore 4ジョブ（2093〜2094 passed）とGUI両OS（ubuntu-24.04含む、Playwright 5 passed）が全成功し、同じゴールデンに4環境が一致した。Ubuntu 26.04（ubuntu-latest）はPlaywrightのChromium未提供のためGUIジョブを24.04に固定している（R1-H）。Pythonの新版・新OSイメージでの再確認はpushごとのCIに委ねる |
| 全srcの型検査 | R1-DOCの `uv run mypy src/cybersprite` は **61件 / 20ファイル（115ファイル検査）**。CLI、formats、generate、pipeline、MCP、platformsの動的モデル・型の絞込み・未導入jsonschema stub等。core/opsの必須検査とstrict7ファイルは別の成功基準。新しいstub依存や診断を隠す設定は追加していない |
| 性能（R1-09） | B2の独立内容フレームで96×96・8層・45f編集2452.570ms（目標1000）、256×256・32f解析空validate2257.868ms（2000）、小規模CLI info1391.715ms（1000）。INTの後続同機比較ではDS編集1202.689msで未達、256²×32f解析空1261.025ms。別負荷の測定を連結した改善率にしない。旧64²同一フレーム編集205.148ms／GUI往復92.965msは150／50ms未達の補助値。[PERFORMANCE](PERFORMANCE.md)と[INT報告](R1_INT_REPORT.md)に各3生値・中央値・範囲を記録。ブラウザ描画とLinux性能は未測定 |
| メモリ・予算 | 256MiBのLRU／入力・出力予算はRSS上限ではない。4096²疎画像のpeak working set中央値はB2で264→328MiB。全面成分配列の疎領域最適化、完全Q-PIX点集合や追加craft／未参照タイル検査を含む実制作の最悪負荷は未計測。一般polygon/stroke/ellipse・太いブラシは予算内列挙で、完全な事前clipはない |
| 取り込み関門（R1-06） | 実生成16枚（ドット絵風13、非ピクセル対照3）を追加・原寸診断済み。版5既定AUTOは(d)8/13合格、(e)10/12拒否=**83.3% < 95%**、誤固定(f)3/34拒否、AUTO対照16/17合格。alignment下限308で(d)2/13へ悪化、小格子・残差の追加信号も正例と独立checker反例を拒否するため不採用。既定・閾値を維持。外部reconstructの関門は復元後で、入力格子の正しさを保証しない |
| 外部ピクセル化方式 | Fixer/PPA/PixelOEは接続・実試験済みだが**利用者導入のみ**。OpenCV/PyAVのFFmpeg、tqdm、Torch等の全バイナリ監査は未完。Xpriteは評価のみで製品未接続。PPAは初期倍率1（上流既定2）で3/323入力が高さ0。PixelOEはCPUのみでoracle寸法を検出率にしない。実アニメーション／写真の意匠、GPU、他OS・別版、ベンダー元アセット再現は未実施。[PIXELIZE_BENCH](PIXELIZE_BENCH.md) |
| GUI主要フォーム・パレット（R1-17） | 取り込み・書き出し専用フォーム、来歴入力・段階表示、種別ごとの予定寸法／ファイル名、パレットの色編集・追加・並替え・凍結は未実装。新規platform選択とモデル条件バッジはこの不足を解消しない。§14.8のW3/W5・専用操作の受入は**部分達成**。汎用JSON Opダイアログは利用可 |
| GUI設定（R1-30） | グリッド・市松・ショートカットの設定ダイアログ、config keymap読込、検証本文の日本語化は未対応。英語本文を恒久仕様と決めたわけではない。表示設定はlocalStorage、サーバprefsはプロセス内。内部段階の進捗フックはなく開始／完了通知のみ |
| GUI原画・条件表示 | guide underとGUIでの原画表示、platform定義編集はv1.x。バッジは操作結果に表示するが、sourceごとの来歴タブ用バッジはget_source契約未整備のため未実装 |
| offset links（H-12後半） | set_celのerror/all/unlinkとmove_celの必須scopeまで実装。画像だけ共有して位置を独立させるリンクはschema／形式／正準化／履歴／GUI横断の別工程（8〜15人日）としてM13-later/v1.xへ延期（I-1515） |
| analyze（H-10） | 設定保存、入力集合hash、raw範囲を含む統計契約の独立検証が必要なためM13-later/v1.xへ延期（I-1515）。ROM container解析・画像出力は追加していない |
| 実機出力・モード | gb-2bpp tile streamは実装・独立復号済み。gba-4bpp/rgb555-le、palette_out/map_outは延期し指定時E_UNSUPPORTED。VRAM/map/bank自動割付・走査線制約・全モードは未対応。Q-PLT-06はindexパターン予算でbank間slot最適配置ではない。NESのRGB表は利用者指定が必要 |
| その他の編集拡張 | apply --replace-last（H-18）はv1.x。inside outlineの一般冪等性は未実装。種集合除外を保つためinsideはN、outsideだけ指定条件でI（I-1463）。cropはcanvas内の正矩形のみ |
| プラグイン | importers実行は入力予算・来歴・配置の共通契約が未確定でv1.x（I-1201）。汎用exporterは単一ファイル、decoderなしは理由付きverified=false。一覧のAPI版未宣言はunchecked、初回使用時に検査。外部コードの任意副作用を取消すsandboxはなく、登録・保存・一時出力の範囲を復元する |
| MCP期限・一覧 | 行トレース・関数差替え・毎回全体走査は解消。協調境界の期限検査なので単一Op内部／native処理の強制中断はせず、応答が期限を超える場合がある。別process隔離なし。Windows別volumeをroot相対にできない場合はroot変更。標準87ツール98,576bytesだが複雑な入れ子の詳細は一覧で省略、CLI/schemaと実行時に完全契約を保持する |
| Diffusers利用者導入 | F2で全33配布物監査、(b)で空extra維持。regex CNRI、certifi/tqdm MPL、vendor LGPL、NVIDIA DLLは配布承認しない。RTX 3080/SDXL+LoRA実CLI3回は同PNG、中央値446.692秒、観測VRAM13342MiB。特定Windows/GPU/版のみで、他GPU/Linux/単一checkpoint実機は未試験。F2画像のCIコーパス化と並行スループット比較は未実施 |
| モデル条件 | F2の固定revision SDXL／Pixel Art XLは別々に確認・承諾済み。L-10/L-12の古いカード欄・検索抜粋は他モデル・将来版・現行規約の原文確認完了ではない。tokenizers wheelは原文欠落、公式タグ補足と区別。VAE/ControlNet/LoRAの登録だけで単体生成可能とは保証しない |
| ComfyUI（H-22） | 自作HTTPサーバーで段階1/2契約を検証、**実ComfyUIは未試験**。本体GPLを同梱しない。サーバ上の重みhash・条件は推測しない。期限切れでjobが残る場合も全体interruptは送らない。段階3のノード互換・他者workflow同梱は対象外 |
| コネクタ403 | 発注者指示（I-1807）で非公開コネクタは標準手順。2026-11-12、利用者PCのChromeでHTTP403、回避を試みずe2e-07は既存privateライブラリを利用（オーケストレーターの観測）。利用可を保証せず、人が保存した資料を使う代替を残す。本体・画像・題名・URLは公開しない |
| 参照画像入力・粒度 | imagegenへ文章と計測値だけの暫定方針（I-1808）。市販計測値を内蔵しない。48px以上turnaround-partsは未較正の目安（I-1803）。最終画像入力方針、32〜48px境界、256pxがframeかsheetか、M13公開範囲は発注者判断待ち |
| 既存ライセンス例外（R1-22） | pathspecのbuild-only MPL（I-010）とpywin32 312の未使用adodbapi LGPL（I-012）を§2.1に明記したが**発注者の事後承認待ち**。検査器の例外を承認済みと扱わず、新しい例外は追加していない |
| M0（I-005/I-006、R1-29） | 画面04、13〜23、26〜32、39〜41、44〜46は未撮影。棚卸し§4からSPEC §7への追加・よく使うキーの聞取りは未完。P-01〜P-11の挙動とP-11実機画素一致は確認済み。全画面棚卸し完了とは区別する |
| Windows symlink・任意試験 | 権限不足のsymlink5件、未導入外部方式6件、明示GPU1件は通常環境でskip。hardlink・実ジャンクション・通常の脱出拒否は検査。統合後の全件数は総括のR1-DOC検査欄を参照 |
| e2e-07・Discord・次工程 | e2e-07進行中、3関門・実書出ファイル・人間の合否は未確定。Discordツールはなく未送信。監督者向け投稿ファイルはe2e-tests/07-ds-turnaround/discord/に準備済みとの申し送りで、DOCは実在一覧を再確認していない。R1後は自動R2へ進まず、発注者が仕様を締め直すため一旦止める。REVIEW_REQUEST_2は再開時の準備文書 |

ジャーナルの無制限全量書換え、MCP行トレースの約5倍費用、生成(d)未作成、GPU全未検証、Linux CI全未実行、独立R1レビュー未実施、dry-run配置未検査は解消したため残件から除いた。履歴の区画roll・索引再構築の最悪時間、外部Command失敗時のWindows子残留／共有違反の全条件は未保証。
