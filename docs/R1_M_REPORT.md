# R1-M — 残りの minor 指摘への修正（2026-11-12）

対象ブランチ: `fixr1-m`。実装コミット: `dc50e96`。新規依存・外部実装の参照・ビジュアル判断はない。`core/quality.py` の内部は変更していない。

## 実装と受け入れ基準

| 指摘 | 実装・検証 | 状態 |
|---|---|---|
| R1-08 | MCP 公開入力のコンパクトな投影、共通の成功・失敗封筒。完全な検証スキーマは内部と CLI に保持。標準 99,478 bytes、minimal 17,247 bytes | 完了 |
| R1-12 | flatten の背景属性維持、merge の可視性・重なり順の保存。24 seed × 2 Op、背景・非表示・不透明度ありの合成比較 | 完了 |
| R1-23 | W_CLIPPED、警告の封筒への集約、互換別名、付録 C の 4 警告、検証失敗のヒント、範囲外座標の details、未宣言引数名 | 完了 |
| R1-24 | シート 3 形式と 80 Op のスキーマを生成。core の外で集約し、欠落・変更・残存ファイルを drift 検査 | 完了 |
| R1-25 | `format: path` による結果変換。通常の path／paths 文字列、レイヤー候補、プラグインの入れ子パスを試験 | 完了 |
| R1-28 | info の繰り返し include を順序付きで統合。background の boolean 説明、78/80 ツール、HTTP 8765、古い animate 注意を修正 | 完了 |
| R1-29 | P-01〜P-11 の確認済み記録を反映。更新器は明示ケースまたは二重の全件指定を要求し JSON 差分を出力。README は実在する 25 ケースに修正 | 指定範囲完了 |
| R1-31 | PNG／GIF／APNG／シート PNG を Pillow で復号しレンダラと比較。independent_decoder マーカーを Windows/Linux CI に明示 | 完了 |
| R1-32 | 未知の検証 ID 拒否、flatten(false) の定義、cleanup の層の判断、表 3 か所の修復、seed 3→8、GUI 生成 opt-in、初回取り込みの L1 再利用 | 完了 |

主な変更先: `mcp/contracts.py`・`result_paths.py`・`paths.py`・`server.py`、`ops/structure.py`・`ingest.py`・`descriptions.py`、`core/raster.py`・`transactions.py`、`formats/common.py`・`export_args.py`・`sheet_models.py`、`schemas.py`、CLI／GUI サーバ、生成・更新・検証用 tools と回帰テスト。

## 検証

- 追加回帰・独立復号・シナリオ 2: **72 passed**。
- MCP パス・契約・CLI: **112 passed, 1 skipped**（Windows の symlink 権限）。
- 最終全体 `uv run pytest -q --tb=short`: **1735 passed, 5 skipped（1003.04秒）**。skip は Windows の symlink 作成権限による既存の5件。パス注釈と stdio シナリオの追試は **10 passed**、独立復号マーカーは **7 passed / 1733 deselected**、拡張したキャッシュ同値試験は **13 passed**。
- `uv run python tools/r1_m_acceptance.py` は実装コミット後にも成功。新規作成、背景消去、矩形、flatten、繰り返し include、validate、PNG/GIF/APNG/シートPNG、sheet schema を実 CLI で実行した。指摘0件、全出力 validation_ok/verified=true、Pillow の全フレーム比較に成功し、書き出したシート PNG 自体を開いて確認した。
- `uv run ruff check`、`uv run ruff format --check`、`uv run mypy src/cybersprite/core src/cybersprite/ops`（38 ファイル）、`uv run python tools/gen_schemas.py --check`、`uv run python tools/check_repository.py` は成功。
- Linux 実行はこの開発機では未実施。CI 定義は両 OS で実行する。ローカルの合格を Linux の合格と同一視しない。

## Before/after numbers

`tools/measure_mcp_contracts.py`。レビューと同じ `json.dumps(tools).encode("utf-8")`、同じ Windows / Python 3.12.10 / SDK 2.3.0、生成無効、78/13 ツール。変更前は `9c030ab` の src をリポジトリ内の一時ディレクトリへ展開し同じ環境で import。以下は各 3 回と中央値であり、速度の測定ではない。

| profile | before 3 runs (bytes) | median | after 3 runs (bytes) | median |
|---|---|---:|---|---:|
| standard | 377768 / 377768 / 377768 | 377768 | 99478 / 99478 / 99478 | 99478 |
| minimal | 76556 / 76556 / 76556 | 76556 | 17247 / 17247 / 17247 | 17247 |

空白を除いた JSON は standard 347840→90838、minimal 70716→15755 bytes。全ツールを含む定義の値で、パケットの外枠・画像・実行時応答・起動時間は含まない。レビュー時の 377112 との差は、先行修正を含む現在の main 由来の定義差による。

## 仕様の変更

§8.8（警告の正本と互換別名）、§10.1.1（HTTP 既定ポート）、§10.1.2（コンパクト宣言・完全な実行時検証・パス注釈）、§10.8（flatten／merge の可視性・背景・strict 拒否）、§11.11（初回 L1 再利用）、§13.3（未知の規則 ID）、§14.6（GUI 生成 opt-in）、§17.2（P-01〜P-11）、付録 C（4 警告）を局所修正した。核言語・ライセンス・パレット規律の変更はない。

## 判断記録

| 日付 | 番号 | 節 | 決めたこと | 理由 | 決めた主体 |
|---|---|---|---|---|---|
| 2026-11-12 | I-1701 | §10.1.2、R1-08 | MCP一覧は共通封筒とコンパクトな入力投影にする。入れ子は説明・titleを除いた160 bytes以下とBrush/OpCallの形を掲載し、それ以外は型だけ掲載する。完全な引数・結果・パス検証には省略前の定義を使う | 78ツールを外部参照なしで100000 bytes以下にし、クライアントが外部スキーマを取得できない場合も動かす。完全な形はops describe/schema opで取得できる | Codex / R1-M |
| 2026-11-12 | I-1702 | §10.1.3、R1-25 | 応答のファイルパスは型モデルと明示した応答位置のformat:pathだけで変換する。projectはsurface root基準、プレビュー等はproject基準、exportはsurface root基準にする | 同じpathキーを持つレイヤー経路・任意メタデータを壊さず、完全なスキーマによる入出力検査を維持する | Codex / R1-M |
| 2026-11-12 | I-1703 | §10.8、R1-12、R1-32 | flatten(false)は全ての非表示の祖先・子も表示した合成を焼き込む。背景は保持する。mergeは連続する兄弟の可視合成を保存し、結果の可視性は入力の論理和とする。strictで属性と画素を両立できなければ拒否する | 非表示背景と透明な穴など、背景保持とRGBA保存が両立しない状態を黙って変えない。非連続結合は未選択層との順序を保存できない | Codex / R1-M |
| 2026-11-12 | I-1704 | §8.8、付録C、R1-23 | 警告は封筒warningsを正本とし、exportのresult.warningsは同内容の互換別名として残す。切捨て画素があればW_CLIPPEDと件数を返す | 既存の結果フィールドの利用者を壊さず、CLI/MCP/GUIで同じ場所から警告を読めるようにする | Codex / R1-M |
| 2026-11-12 | I-1705 | §4.4、§9.3、付録D、R1-24 | project/sourcesの生成器はcoreに保持し、sheetと80 Opの集約はcybersprite.schemasに置く。シートは独自と互換2形式の和とし、古いschemaファイルもdriftとする | coreからformats/opsへの依存を作らず、CLIとコミット済み成果物を同じ登録定義から得る | Codex / R1-M |
| 2026-11-12 | I-1706 | §9.3、§10.1.1、R1-28 | infoの反復includeは既存の配列変換後に最初の出現順で重複排除する。HTTP既定は8765に統一する | カンマ・JSON配列の既存文法を保ち、既存MCP文書とpython -mの値を採用する | Codex / R1-M |
| 2026-11-12 | I-1707 | §13.5、R1-29 | ゴールデン更新は実在する明示case名、または--allと--confirm-allの同時指定だけにする。JSON差分と全形式のバイト数・hash差を出す。README件数は現worktreeのcase.json実数25とする | HEAD版を一時fixtureで動かし、引数なしで全件を選ぶことを再現した。レビュー記載26を機械的に転記しない | Codex / R1-M |
| 2026-11-12 | I-1708 | §4.2、§13.3、R1-32 | set_validationのseverityキーは品質規則の既定表のIDだけを受ける。ops/drawingからpipeline/cleanupへの依存は、既存の整数だけの純粋な清掃関数を共有する層の判断として維持する | タイプミスを無視せず候補を返す。Opsは形式・変換を調停する層であり、coreへPillow等を入れずアルゴリズムの二重実装を避ける | Codex / R1-M |
| 2026-11-12 | I-1709 | §14.6、R1-32 | GUIのGクラスOpは--enable-generationを明示したServiceだけが実行できる。一覧取得は読み取りとして許す | MCPと同じ明示有効化を実行前に適用し、見た目の変更なしでバックエンド実行を制御する | Codex / R1-M |
| 2026-11-12 | I-1710 | §11.11、R1-32 | 初回import_imageは自動作成したL1を配置先として再利用する。既存プロジェクトのnew_layerは従来どおり新規発行する | 空のLayer 1と未使用IDを残さず、既存作品のレイヤーを削除・再利用しない。初回undo後にプロジェクトを残す契約は維持する | Codex / R1-M |
| 2026-11-12 | I-1711 | §13.5、§13.6、R1-31、R1-32 | 合成保存を24 seed×2 Opで検査し、既存のキャッシュ同値試験を3→8 seedにする。独立復号はPillowで全組み込みラスター形式を検査し両OSのCIへ明示する | 自前codec同士で対称な誤りを見逃す可能性を減らし、許されないstrict合成の拒否も含めて決定的な入力で固定する | Codex / R1-M |

## Design forks decided

- **コンパクト宣言と完全な検証の分離（I-1701）**: R1-08 §1に従う。外部 `$ref` は採らず、複雑な入れ子の詳細を一覧から省略する。したがって一覧だけで全ての入れ子を構成できるとは約束しない。完全な契約は CLI／schemas と実行時に保持する。
- **背景保持と透明な穴の競合（I-1703）**: R1-12／R1-32 §1に従う。strict は両立不能なら E_NOT_PALETTE_CLOSED。visible_only=false は全てを可視として焼き込み、merge は現在の可視合成を保存する。Fable §3に本件を上書きする指定はない。
- **非連続 merge（I-1703）**: 間の未選択層との順序を保証できないため E_INVALID_ARGS。仕様を先に限定し、静かな見た目の変更を避ける。
- **警告の互換性（I-1704）**: R1-23 §1に従い封筒を正本にし、旧 result フィールドは削除しない。
- **ポートと確認指定（I-1706／1707）**: R1-28／29 §1に従う。8765 は既存文書と python -m に合わせ、全件更新は対話で待たず二重フラグで明示する。
- **清掃の層・初回レイヤー（I-1708／1710）**: R1-32 §1に従う。純粋な整数関数の既存共有を記録し、初回だけ空の L1 を再利用する。

## ゴールデンの差分

`uv run python -m tests.e2e.replay --case scenario2` が共通 `tools/update_goldens.py` を呼ぶ経路だけを使用。変更は scenario2 の expected/project.json **1 ファイル**。空の初期レイヤーを削除し、配置レイヤーの ID を L2→L1、layer counter を 2→1 に変更した。対応する calls.jsonl も新しい配置先を指定する。PNG、画素配列、画素ハッシュ、exports.json、transcript.json は無変更。通常の tests/golden の 25 ケースは更新していない。

## Deferred / not done

- Linux の実行結果と他ワークストリーム統合後の CI はオーケストレーターの確認対象。
- R1-29 の背景記述にある M0 の未撮影 GUI 画面と I-005 が予告した棚卸し全体の追加は、この作業の P-01〜P-11／更新器の指定範囲外として残す。新たなビジュアル判断は行っていない。
- R1-17／R1-30 の GUI 見た目、および R1-22 のライセンス台帳は指示どおり対象外。
- 依存の追加はなく、新しい LICENSE 確認・台帳編集もない。参照したものは既存の仕様、2件のレビュー、判断／進捗、M0/M10 の記録、既存リポジトリ内コード・テストだけ。外部サイトや他製品のソース・アセットは参照していない。
