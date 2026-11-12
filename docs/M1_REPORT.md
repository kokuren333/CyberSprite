# M1 コア基盤の実装報告

M1 の非ビジュアル実装を `m1-core` に作成した。ライセンスの衝突が未承諾のため、マイルストーンの完了・main 統合は宣言していない。

## 1. 実装

- `pyproject.toml` / `uv.lock`：src 配置、Python 3.12 以上、hatchling 指定、console scripts 2 名、空の extras、固定依存。
- `core/models.py` / `canonical.py`：全モデル、既定値、ユーザーデータ、ID カウンタ、参照・色解決、正準 JSON、版移行フック。
- `core/validation.py` / `normalize.py`：S-01〜S-14 の具体的な場所・修正ヒント、リンク所有権の正規化、透明外周の切詰め、空セル除去。既存正本の保存経路は作っていない。
- `core/render.py` / `hashing.py`：整数 source-over、グループ不透明度、安定 Z 順、背景・表示指定・crop・scale・pixel ratio、タイル反転、閉包、nearest、CSPX1。
- `formats/png.py`：indexed / RGBA、stored / zlib、PLTE / tRNS、単一 IDAT、CRC、Adler32、限定 reader、実行環境指紋。
- `cli`：new、info、render、validate、schema、doctor、UTF-8 / LF の JSON 封筒、終了コード、遅延 import。
- `schemas` / `tools` / `tests`：pydantic 由来スキーマ、差分検査、runtime / dev / build のライセンス閉包検査、追跡パス・core import 検査、ゴールデン更新、合成ベクタ、性質テスト、CLI 通しテスト。
- `.github/workflows/ci.yml`：Windows / Ubuntu × Python 3.12 / 3.13。Ruff、型検査、テスト、スキーマ差分、ライセンス、クリーンルーム検査。

## 2. 受け入れ基準

| 基準 | 状態 |
|---|---|
| 合成・正本ゴールデン | Windows 3.12 で 17 ケース一致 |
| 正準往復・付録 A | 性質テスト一致、仕様の例と UTF-8 バイト一致 |
| スキーマ生成・差分検査 | 2 スキーマ生成済み、検査成功 |
| core の import 制限 | AST 検査成功。標準ライブラリ・NumPy・pydantic のみ |
| Ruff / pytest | 成功。下記参照 |
| CLI の実使用 | 新規プロジェクトと付録 A の両方で成功。console script のインストール確認は依存判断待ち |
| Linux / Python 3.13 | CI を設定。ローカル Linux はなく、結果は未取得 |
| ライセンス | 本体 runtime + dev のメタデータ閉包検査は成功。build の pathspec と NumPy wheel 同梱物の条件は未承諾。台帳転記は担当外 |
| 通常の uv sync / wheel build | 未承諾の build 依存を導入するため保留。uv lock は生成・確認済み |

## 3. 検証

確認用環境で `PYTHONPATH=<作業ツリー>/src` を指定し、依存を再同期しない `uv run --no-sync` を使用した。

- `uv run --no-sync pytest -q`：168 passed。
- `uv run --no-sync ruff check` / `ruff format --check`：成功。
- `uv run --no-sync mypy`：17 ソースファイルで成功。
- `uv run --no-sync python tools/gen_schemas.py --check`：成功。
- `uv run --no-sync python tools/check_licenses.py --include-dev`：16 配布物で成功。
- `uv run --no-sync python tools/check_repository.py`：成功。
- `uv run --no-sync python tools/check_licenses.py --include-build`：pathspec の MPL-2.0 を正しく拒否して終了 1。
- ゴールデンは `tools/update_goldens.py` で初回生成。付録 A のカウンタを原例に合わせた意図的な訂正も同ツールで更新し、変更 1 件を確認した。期待 JSON の数値・正規化された位置・ID 列を読み、付録 A の両フレーム・背景・不透明度組合せの PNG を開いて確認した。

手動 CLI は `uv run --no-sync python -m cybersprite ...` で実施。新規 4×3・2 フレームは revision=0、info のサイズ・フレーム数が一致、render は 4×3 PNG、validate の構造エラー・警告とも 0。付録 A は revision=5、8×8・2 フレーム・リンク 1、indexed render と validate が成功。各 render の `validation_ok` / `verified` は true。Windows の System.Drawing でも実 PNG を独立して読み、8×8 と目の位置 (2,3) の RGBA=(255,255,255,255) を確認した。

`--version` は subprocess の起動時間を含む 10 回の実測で中央値 150 ms、最大 248 ms。目標 400 ms 未満。Click のみ import し、NumPy / pydantic を読み込まないこともテストした。指紋は `cybersprite 0.1.0 / zlib 1.3.1 / python 3.12`。

## 4. 判断記録

I-101〜I-114。既定パレット、strict モデル、制御文字、M6 までの RGB 距離、飽和、描画用パレット、crop と背景、nearest 候補、構造検証だけの報告、新規作成の境界、終了コード、ゴールデンの形、依存審査、JSON の型。

## 5. 仕様の変更

§6.5.3 に丸めによる RGB=256 の飽和を 1 行追記。§6.5.5 に描画用パレットを明記し、nearest から透明番号を除くことと候補なしのエラーを明記した。どれも固定ベクタ・単体テストで検証する。ライセンス方針は変更していない。

## 6. 新規依存

名前・版・SPDX・原文確認先は `M1_LICENSE_REVIEW.md` の一覧を参照。`third_party/THIRD_PARTY.md` は指示どおり変更していない。pathspec の例外も自動承認していない。

## 7. 残件

- pathspec（MPL-2.0）と NumPy wheel 同梱物の扱い、台帳更新はオーケストレーター・発注者の判断待ち。回答を得た後で通常の uv sync、wheel / console scripts、Linux CI を確認する。
- 最近色の整数 RGB 距離は今回指定された仮実装。M6 で固定小数点 Oklab に置き換える TODO を共通関数に記載した。
- `new --background` は明示的な E_UNSUPPORTED。品質ルール・指標、装飾プレビュー、Op・トランザクション・履歴は M2 以降。
- ビジュアル・デザイン判断は行っていない。fixture は数値の組合せと仕様付録 A のみ。

## 8. 参照

今回の AGENTS / SPEC / DECISIONS / src README と、依存の LICENSE 原文のみ。外部製品・ライブラリの実装ソース、他製品の文言・画像は参照していない。LICENSE 確認は `docs/reference/PROVENANCE_LOG.md` に記録した。
