# CyberSprite — Codex 独立実装レビュー R1

> **今回の依頼に対する現 HEAD の評価は末尾の [§9（2026-11-13 追補）](#current-review)を参照。** §1〜8 は `e94bd7a` に対する当初のレビューとして保存した。そこでの未実装項目・blocking 判定・旧行番号を、現在の実装への判定として読み替えない。

- レビュー日: 2026-11-12 JST
- 対象: `e94bd7a823c9b2c4b49cab86b55591528c74dff2`（作業開始時 HEAD、main）
- 担当: Codex、実装・正確性・性能の独立レビュー
- 変更範囲: 本文書のみ。実装・仕様・既存テスト・ゴールデン・申し送りは変更していない。コミットは作成していない。
- 入力: `docs/REVIEW_REQUEST_1.md`、`KNOWN_ISSUES.md`、`IMPLEMENTATION_PROGRESS.md`、`SPEC.md`、`REQUIREMENTS_NOTES.md`、`DECISIONS.md`、M1〜M10・INT/FIX の報告、`src/cybersprite/`、`gui/`、`skills/`、`tests/`、制作 e2e 報告。
- 必須申し送り: `_handoff/REVIEW_NOTES_FOR_FABLE.md`、DM 知見メモ（非公開）、`_private/e2e-ds/REPORT.md` を評価した。非公開画像・DM 生データ・ROM・他製品のソースコードは開いていない。本書にそれらを転載していない。
- `docs/review/FABLE_REVIEW_R1.md` は確認時点で存在しなかった。したがって他レビューとの一致・不一致は未比較であり、以下は独立の指摘である。

## 1. 判定

**現状のままのリリースには反対する。書き出しが正本を上書きする blocking が 1 件ある。** 新規指摘は blocking 1 / major 6 / minor 1。既知の性能未達を blocking に格上げした判定ではない。

整数描画、パレット番号の保持、正準 JSON、リンクの正規化、タイル反転、自己検査付き書き出しには、手計算ベクタ・ゴールデン・性質テストがある。再実行した既存テストも成功した。ただし、成功結果の `validation_ok=true / verified=true` は「出力先が正本ではない」ことを保証していなかった。正常系の豊富さに対して、最終出力先・入力サイズ・拡張機構・GUI 再生の境界テストが不足している。

DS 粒度の制作は現アーキテクチャで実行可能だが、完成品の美的品質が達成済みとは判定できない。試作の validate と往復一致はファイルの正確性の証拠であり、作者の自己評価 4/5 は利用者の選好の証拠にならない。サイズクラス／機種仕様は現在の SPEC にない追加要求として、§5〜§6 に実装案・費用を示す。

### 検査結果と限界

環境は Windows 11 10.0.26200、Intel Family 6 Model 140、Python 3.12.10、NumPy 2.3.4、Pillow 13.0.0。既存の仮想環境を `--no-sync` で使用し、新しい依存は導入していない。

| 再実行した検査 | 結果 |
|---|---|
| `uv run --no-sync pytest -q --tb=short` | **1411 passed / 2 skipped、301.45 秒** |
| `cd gui; npm test` | **627 passed**、コントラスト **86/86** |
| `cd gui; npm run test:e2e` | **3 passed、28.3 秒**（既存 Playwright シナリオ） |
| `uv run --no-sync python tools/gen_schemas.py --check` | 成功 |
| `uv run --no-sync python tools/check_repository.py` | 成功 |

2 skip は Windows のシンボリックリンク作成権限による既知のもの。Linux / Python 3.13、実 GPU、実モデル生成、実生成画像コーパスの較正は本レビューでも実行していない。配布 wheel の再ビルド・ライセンス原文の再監査も今回の再実行範囲外。GUI の色・構図の新規判断はしていない。

## 2. 新規指摘

行番号は上記 HEAD のもの。再現コマンドはプロジェクトルートの PowerShell 用で、すべて破棄用 fixture に対して実行する。以下の Python ブロックは `@'` と `'@ | uv run --no-sync python -` の間に置いて実行できる。

### R1-01 — blocking: 書き出しが `project.json` を破壊し、成功を返す

**根拠:** `src/cybersprite/formats/common.py:170` の `preflight` は許可ディレクトリ・重複・既存ファイルだけを検査し、`:182` の `write_verified` は直接 `path.write_bytes(data)` する。`ExportBase.overwrite` は既定で true（`formats/export_args.py:26`）。`formats/export.py:53` の `export_image` からこの経路に入る。CLI の preview/render 用保護はこの共通 export 経路に適用されていない。MCP も同じである。

GUI には `server/app.py:105` の保護があるが、`export_image` のファイル名展開（`formats/export.py:65`）**より前**に検査するため、`{name}.json` → `project.json` を拒否できない。MCP の rollback フックは `history.atomic_write` にしか掛からず、この直接書き込みを復元しない。

**再現（確認済み）:** 次の結果は CLI 終了コード 0、MCP/GUI の `ok=true`。各正本の先頭 8 byte は JSON から `b'\x89PNG\r\n\x1a\n'` に変わる。MCP では `validation_ok=true / verified=true` も返った。明示的な `overwrite=true` は不要。

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from click.testing import CliRunner
from cybersprite import ops
from cybersprite.cli import cli
from cybersprite.mcp.server import MCPService
from cybersprite.server.app import Service

with TemporaryDirectory(dir=Path.cwd()) as t:
    root = Path(t).resolve()
    for surface in ("cli", "mcp", "gui-template"):
        p = root / surface
        ops.execute("new_project", p, {"width": 2, "height": 2, "name": "project"})
        if surface == "cli":
            r = CliRunner().invoke(cli, ["-p", str(p), "export", "image",
                                        "--out", str(p / "project.json")])
            print(surface, r.exit_code)
        elif surface == "mcp":
            r = MCPService(root=root).call("export_image", {
                "project": str(p), "out": str(p / "project.json")})
            print(surface, r.structured_content["ok"])
        else:
            r = Service(root).run_op("export_image", p, {"out": str(p / "{name}.json")})
            print(surface, r["ok"])
        print((p / "project.json").read_bytes()[:8])
```

**期待する修正:** 最終展開・resolve 後の全出力先を形式層の共通境界で検査する。予約名 `project.json`、現在の正本の別名／hard link 等を拒否する。画像以外の `data_out`・パレット・`.aseprite` も同じ保護を通す。出力の検証成功と、正本の保存権限を混同しない。複数ファイル出力の途中失敗や応答生成失敗でも、正本・既存出力を壊さない保存手順を設ける。

**回帰条件:** CLI / MCP / GUI × 直接名・テンプレート・大小文字・リンク経路を検査し、失敗時の正本・履歴 bytes 不変を確認する。`verified` だけの assertion では足りない。SPEC §4.2、§6.1、§8.8、§10.1.3 に関係する。修正目安 **1〜2 人日**。

### R1-02 — major: 元画像のサイズ上限がなく、フレーム上限も全復号後にしか検査しない

**根拠:** `pipeline/decode.py:14` は `Image.open` 後、`:40` から全フレームを RGBA 配列へ変換して保持する。各辺 8192・面積 67,108,864 のチェックがない。`ops/ingest.py:198` の `decode_files` は全入力の復号・連結後に、初めて 4096 フレームを検査する。SPEC §5.11 の元画像上限を実装していない。

**再現（確認済み）:** 8193×1 の小さな PNG を既存の 2×2 プロジェクトへ `exact` で取り込むと、拒否されず `ok=true / accepted=true`、新規セル幅 8193 となる。キャンバス外保存は既存仕様だが、元画像の上限超過を許す根拠にはならない。

```python
from pathlib import Path
from tempfile import TemporaryDirectory
import numpy as np
from cybersprite import ops
from cybersprite.core.canonical import load_project
from cybersprite.formats.png import encode_png
with TemporaryDirectory() as t:
    r = Path(t); p = r / "p"; f = r / "wide.png"
    ops.execute("new_project", p, {"width": 2, "height": 2})
    f.write_bytes(encode_png(np.full((1, 8193, 4), 255, dtype=np.uint8)))
    v = ops.execute("import_image", p, {"files": str(f), "preset": "exact",
                    "provenance": {"license": "unknown"}}, preview="none")
    print(v["result"]["accepted"], load_project(p).layers[-1].cels[0].w)
```

**期待する修正:** ヘッダの寸法・フレーム数を復号前に検査し、複数ファイルの累積フレーム数も逐次検査する。上限違反は `E_LIMIT_EXCEEDED`。同時保持する復号画素数／bytes の予算も定義する。Pillow の一般的な警告は本製品の 8192 制限の代わりにならない。巨大入力そのものは今回作成していないが、配列化より前に制止できない経路はコードで確認した。目安 **1〜2 人日**。

### R1-03 — major: 小さな要求 JSON から、無制限の図形列挙・巨大な拡大配列を要求できる

**根拠:** `ops/args.py:115` 以降の座標は無制限の int、図形寸法は正数のみ。`core/raster.py:94` の直線は端点間を、`:118` の矩形は w×h を列挙し、`ops/drawing.py` で点リスト・stamp を作った後に `ops/common.py:88` でキャンバスへ切り取る。キャンバス 2×2 でも遠方や巨大な図形の仕事量を制限しない。

さらに `core/render.py:229` は倍率を検査済みでも最終出力の画素数を制限せず `np.repeat` と copy を行う。4096² × 64 倍の RGBA は **274,877,906,944 byte（256 GiB）**。これは割当前の算術値で、実際の巨大割当は行っていない。GUI の JSON サイズ制限や MCP の Python 期限は、ネイティブ配列の割当に対するメモリ上限ではない。

**安全な再現（引数の受理まで確認、巨大演算は実行しない）:**

```python
from cybersprite import ops
from cybersprite.core.projects import new_project
from cybersprite.core.render import _options
a = ops.registry().get("rect").parse({"layer": "L1", "frame": 0, "x": 0, "y": 0,
                                     "w": 10**9, "h": 10**9, "color": 1})
p = new_project(width=4096, height=4096)
o = _options(p, 0, {"scale": 64})
print(a.w, a.h, o.scale, 4096 * 4096 * 64 * 64 * 4)
```

**期待する修正:** 割当・列挙前の仕事量／出力 bytes 予算を共有する。完全にキャンバス外の図形を早期終了し、必要な範囲だけ整数規則を保って列挙する。複雑な polygon/stroke と 1000 Op の累積負荷も扱う。予算超過は具体的な requested/limit を添えて `E_LIMIT_EXCEEDED`。MCP だけでなく CLI / GUI でも有効にする。SPEC §5.11 に積の上限を追記する必要がある。目安 **2〜4 人日**。

### R1-04 — major: 履歴件数に比例して全ジャーナルを二度書き直し、編集が秒単位まで劣化する

**根拠:** `core/history.py:165` は全 journal を `read_bytes → splitlines → json.loads`、`transactions.py:217` は各編集でそれを読む。`:363` と `:382` は全件を直列化し直し、全ファイルを二度保存する。`save_files` のバックアップでも旧ファイルを読む。`:232` の retention は snapshot にだけ作用し、ジャーナルは小さくならない。GUI の scan と get_history も全件を読む。

**実測:** 16×16・1点変更・preview=none。実コミット 1 件から作った JSON journal 行を繰り返す合成負荷（1000/10000 回の実編集を行った測定ではない）。同一プロセス各 3 回。全体 pytest/GUI テストとは同時実行していない。

| 初期 journal 行数 | 初期 bytes | 編集時間 ms（3 回） | 中央値 ms |
|---:|---:|---|---:|
| 10 | 17,721 | 68.923 / 74.668 / 76.084 | 74.668 |
| 1000 | 1,773,893 | 439.506 / 338.066 / 332.868 | 338.066 |
| 10000 | 17,748,894 | 1440.351 / 2856.404 / 1985.643 | 1985.643 |

再現は §7 の H。将来の機種制約検証を足す前に、蓄積時間に比例する保存費を切り離すべきである。

**期待する修正:** セグメント化した追記 journal と、直近 1000 件の冪等キー索引、履歴ページ読み取りを設ける。既存の原子性・失敗時復元を保持する設計が必要で、単に末尾追記へ変えるだけでは足りない。正本保存と journal の確定位置を検証可能な状態として記録する。10/1000/10000 件の同一編集を回帰ベンチに追加する。目安 **3〜5 人日**。

### R1-05 — major: v1 とした拡張点の大半が未接続で、Op プラグインの API 版・読込範囲も検査しない

**根拠:** SPEC §15.1 は ops/importers/exporters/pipeline_steps/generators/validators/palettes の 7 群を v1 対応としている。実装で entry point を読むのは `core/registry.py:180`、`generate/registry.py`、CLI の ops 一覧だけ。残り 5 群の登録・実行経路は見つからなかった。CLI の通常実行は Op プラグインをロードしない。`plugins.enabled` は CLI の表示に使うが、通常の Op 呼び出しへ接続していない。

MCP は `mcp/server.py:293` で `--allow-plugin-op` が 1 つでもあれば、全 `cybersprite.ops` entry point をロードする。公開ツールの絞り込みはその後なので、非公開・無関係なパッケージの import/factory 実行は防げない。`core/registry.py:185` は `plugin_api` を検査しない。generator 側には同検査があり、契約が揃っていない。

**再現（確認済み。実プラグインのインストールは不要）:**

```python
import importlib.metadata
from unittest.mock import patch
from cybersprite.core.registry import Registry
loaded = []
class Entry:
    def __init__(self, name): self.name = name
    def load(self):
        loaded.append(self.name)
        def factory(): return []
        factory.plugin_api = 999
        return factory
with patch.object(importlib.metadata, "entry_points",
                  return_value=[Entry("allowed"), Entry("unrelated")]):
    Registry().load_plugins(enabled=True)
print(loaded)  # ['allowed', 'unrelated']; unsupported API 999 was accepted
```

未接続群は次でも追跡できる。

```powershell
rg -n 'entry_points|load_plugins|plugin_api' src/cybersprite
```

**期待する修正:** entry point メタデータの列挙と実ロードを分け、提供者の許可を確認した上で対象だけを遅延ロードする。factory 呼出前に API 版を検査し、失敗時の半端な Op 登録を戻す。CLI と MCP が同じ登録済み Op を実行するよう接続する。残りの拡張点も実装するか、Fable と SPEC の v1 範囲を整合させる。現在の `KNOWN_ISSUES.md` にはこの不足がない。「7 群 v1 対応済み」という前提で新しいハードウェア exporter を計画できない。

費用は Op のロード境界と契約試験 **2〜3 人日**、残り 5 群を共通登録方式へ載せる工学 **追加 5〜8 人日**。各形式の実装費は別。Python プラグインのサンドボックスを要求する指摘ではない。信頼済みコードの選択範囲・互換性検査の問題である。

### R1-06 — major: GUI が許可した `--root` / `--allow-dir` の書き出し先を形式層が拒否する

**根拠:** `server/app.py:88` の `Service.run_op` は PathPolicy で許可した絶対パスを `ops.execute` へ渡すが、`export_policy` を束縛しない。`formats/common.py:39` は未束縛時にサーバの cwd を root とする。MCP の `server.py` と CLI の `_run` には policy の束縛がある。

**再現（確認済み）:** cwd 外の TEMP を Service の root にすると、その直下の正当な出力が `E_PATH_NOT_ALLOWED` となる。GUI RPC `export.run` もこの関数を通る。

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from cybersprite import ops
from cybersprite.server.app import Service
with TemporaryDirectory() as t:
    root = Path(t); p = root / "p"
    ops.execute("new_project", p, {"width": 2, "height": 2})
    Service(root).run_op("export_image", p, {"out": str(root / "ok.png")})
    # CyberSpriteError: E_PATH_NOT_ALLOWED
```

**期待する修正:** GUI でも `with export_policy(self.policy.root, self.policy.allowed)` を設定する。許可ディレクトリ・拒否ディレクトリ・cwd 外の root を実 RPC で確認する。R1-01 の正本保護も同じ最終パス境界で適用する。SPEC §14.6「パスの制限は MCP と同じ」に不適合。目安 **0.5〜1 人日**。

### R1-07 — major: GUI の有限 ping-pong 再生が、タグの片道 repeat を往復回数として扱う

**根拠:** `gui/src/store/index.ts:15` の `playbackFrames` は repeat に関係なく往復から末端を除いた 1 周を作る。`components/Timeline.tsx:20` と `:30` はそれを repeat 周再生する。SPEC §5.7 の repeat は「片道を 1 回」と数え、`formats/common.py` の `animation_sequence` はその意味で実装されている。

**確認結果:** 0〜2、direction=pingpong。書き出し側を loop=1 で確認した結果と、現 GUI の関数＋タイマーから得る列は次のとおり。GUI 関数は実 TypeScript を transpile して評価した。該当タグを選択して再生するブラウザ操作自体は今回の追加再現としては実施していない。

| repeat | core の列 | GUI の列 |
|---:|---|---|
| 1 | 0,1,2 | 0,1,2,1 |
| 2 | 0,1,2,1,0 | 0,1,2,1,0,1,2,1 |
| 3 | 0,1,2,1,0,1,2 | 0,1,2,1 を 3 周 |

再現は §7 の P。既存 `gui/src/store/store.test.ts` は方向 4 種と単フレームを試すが、有限 repeat を試していない。既存 Playwright の有限 repeat 試験も reverse/repeat=1 であり、ping-pong は通していない。idle の無限ループだけでは見つからない。

**期待する修正:** Python/TS に共通の再生順ベクタを持ち、repeat=0/1/2/3、4 方向、1/2/3 フレーム、末端の表示時間まで固定する。可能ならサーバが確定した再生順を GUI へ返す。プレビューで確認した動きと書き出し結果が違うため、制作上も影響がある。目安 **1〜2 人日**。

### R1-08 — minor: import の `dry_run.would_commit=true` が配置可能性を意味しない

**根拠:** `ops/ingest.py:296` の dry-run 分岐は pipeline だけを実行し、accepted を would_commit に入れる。`:477` の `place` にある対象レイヤー・ロック・フレーム拡張可否などを検査しない。GUI `pipeline.preview` が変換だけを見せる用途は妥当だが、共通の `would_commit` という名前と §6.2.2 の期待には合わない。

**再現（確認済み）:**

```python
from pathlib import Path
from tempfile import TemporaryDirectory
import numpy as np
from cybersprite import ops
from cybersprite.formats.png import encode_png
with TemporaryDirectory() as t:
    r = Path(t); p = r / "p"; f = r / "in.png"
    f.write_bytes(encode_png(np.full((2, 2, 4), 255, dtype=np.uint8)))
    ops.execute("new_project", p, {"width": 2, "height": 2})
    ops.execute("update_layer", p, {"layer": "L1", "locked": True}, preview="none")
    args = {"files": str(f), "preset": "exact", "provenance": {"license": "unknown"},
            "target": {"mode": "layer", "layer": "L1"}}
    print(ops.execute("import_image", p, args, dry_run=True)["would_commit"])  # True
    ops.execute("import_image", p, args, preview="none")  # E_LAYER_LOCKED
```

**期待する修正:** 同じ prepared 結果を使って、メモリ上の配置・構造検査まで予行する。変換プレビューだけの契約を維持するなら、配置を検査したかを明示し、would_commit をコミット可否の保証として返さない。目安 **1〜2 人日**。

## 3. 正確性・決定性・テストの評価

- `core/render.py` の `source_over` / `mul255`、固定小数点 Oklab、ラスタライズで整数経路を確認した。描画に乱数・現在時刻を加えるコードは見つからなかった。時刻は `journal_clock.py`、float はユーザー properties と形式のメタデータ処理に分離されている。全入力についての形式的証明を行ったという意味ではない。
- 手計算の合成ベクタ、キャンバス端、非 0 透明番号、背景レイヤー、厳密閉包と nearest、正方形／非正方形タイルの 8 フラグを試すテストがある。特に非正方形の d を無視する契約は、欠陥扱いせず SPEC と照合した。
- `tests/unit/test_fix5_latency.py:22` は 3 固定シード × 65 実 Op で cache 有無の report/validation_delta を比較する。可変返却値による cache 汚染・外部変更の失効も試す。最適化の守りとして有効である。ただし全量比較側も同じ report 実装なので、独立した規範ベクタを代替するものではない。
- CLI/MCP のスキーマが同じレジストリから生成され、schema drift 検査が成功した点はよい。スキーマの一致はファイルの副作用や、GUI 独自の再生・設定コンテキストまで保証しない。R1-01/06/07 がその具体例である。
- GUI の起動ごとのトークン、HTTP の Host/Origin、WebSocket の厳密 Origin＋トークン照合を確認した。欠落・偽トークン・異なる Origin の拒否試験（`tests/server/test_server.py:87` 以降）も全体検査に含めて成功しており、認証回避は今回見つかっていない。PathPolicy は resolve/commonpath と派生ディレクトリ検査を行い、実 junction の脱出拒否試験もある。ただしリンク作成権限による 2 skip と、最終出力先の R1-01 は別に残る。
- ゴールデンは変更していない。R1-01〜08 の失敗例を足し、Linux/Windows × Python 3.12/3.13 で同じ期待を通す必要がある。大入力の試験は、OOM を起こす試験ではなく、復号・列挙・割当の前に拒否されたことを監視する試験にする。

既知不足の再掲を新規バグ件数に含めないが、Linux 未実行のまま水準 A/B の環境横断一致を「証明済み」とは扱えない。`KNOWN_ISSUES.md` の GPU・コーパス (d)・mypy の不足も本レビューで解消していない。§16.3 の両 OS 条件と「M0〜M10 完了」という進捗表現は、受け入れ済み／実装済みを分ける方が正確である。

## 4. 性能の再測定

### 4.1 既存のベンチをそのまま再実行

```powershell
uv run --no-sync python -m tools.bench --out "$env:TEMP/cybersprite-codex-r1-bench.json"
```

各 3 回。テストと同時実行していないが、OS と他アプリの負荷を固定してはいない。import・fixture 作成を含むかは `docs/PERFORMANCE.md` と同じ境界である。

| 項目 | 今回の中央値 ms | 今回の最大 ms | 目標 ms |
|---|---:|---:|---:|
| インストール済み CLI --version | 247.173 | 271.247 | 400 |
| 64²・10 層・32 フレーム、一画素編集＋preview | 341.249 | 373.994 | 150 |
| 256² RGBA render | 26.374 | 41.218 | 50 |
| 256²・32 フレーム validate | 241.933 | 534.680 | 2000 |
| GUI 128² Op＋RGBA 往復 | 93.217 | 531.666 | 50 |
| 1024² 組み込み変換、段階保存・検査込み | 618.491 | 702.882 | 5000 |

パイプラインの既報の 5 秒以内は同じ fixture で再現した。写真・多数色・実生成画像一般の時間をこの値から保証しない。transaction/GUI の 2 項目の未達も再現した。報告済みの中央値との差だけを性能退行とは判定しない。

80²・4 フレームの空プロジェクトで `info --include layers` を別プロセスから各 3 回実行すると、インストール済み CLI は **1366.609 / 1720.897 / 1430.541 ms**、`uv run --no-sync` 経由は **1601.477 / 1543.708 / 1534.350 ms**。DS 報告の約 4.7 秒という同じ値は再現していない。軽い --version の測定だけでは実作業の起動時間を代表できない。MCP 常駐と Op の適切なまとめ送りは有効だが、履歴の費用は常駐化だけで消えない。

### 4.2 大きなキャンバス

別 Python 子プロセスで render → report を各 1 回実行。時間はその関数だけ、peak working set は import・fixture を含むプロセス最大値。再現は §7 の L。

| fixture（1 層・1 フレーム） | render ms | validate ms | peak working set MiB |
|---|---:|---:|---:|
| 1024²、全画素が番号 1 の独立セル | 653.298 | 6213.787 | 262 |
| 4096²、1×1 の非透明セルが 1 個 | 35.695 | 2674.836 | 264 |

4096² 密画像・多層・多数フレームは実測していない。疎な 4096² の render 値を密画像の性能と読み替えてはならない。`quality.clusters` は全画素を Python のリストにし、全非透明座標を保持した後、さらに tuple へ複製する（`quality.py:63,129`）。1024² の validate が 6 秒を超える結果と整合する。4096² 密画像での費用はさらに増えると推定するが、外挿した数値を実測として載せない。

§13.8 は大キャンバスの目標を定めていないので、この測定だけを仕様違反の blocking とはしない。任意粒度を実用範囲として掲げる前に、クラスタの個数・面積・先頭座標・報告用最大 64 点を集計し、全座標を常時保持しない実装へ改める価値が高い。固定ベクタと cache 無効時との同値性を保つ改善で **2〜4 人日**が目安。

## 5. DS 試作 §6 の摩擦を現在の HEAD で評価

以下は追加機能と使い勝手の評価であり、現 SPEC どおりの挙動を数値バグとして数えていない。費用は実装＋意味のある回帰検査・文書を含む、非ビジュアル工学の概算人日。GUI のデザイン作業は別である。

| DS 報告の項目 | 現状・具体策 | 目安 |
|---|---|---:|
| 1. linked `set_cel` で全員の位置が変わる | `ops/frames.py` の共有変更と `changed.linked_frames/link_groups` を確認。§5.6.3 どおりだが、呼吸アニメの罠は残る。新規 `move_cel(dx,dy,scope=frame/shared)` を設け、frame は明示的に detach して移動する。既存 set_cel の意味は維持し、共有変更時の具体的警告と全対象フレームを返す。既定を突然 E_LINKED に変える案は互換性変更になる | 1〜2 |
| 2. 原点が分からない・相対移動なし | **原点の取得は解消済み**。`ops/queries.py` の `get_info(include=[layers])` は各 cel の x/y/w/h/link を返す。独立の include=cels は不要。相対移動は上記 move_cel で追加する。`transform_region` はキャンバス外画素を捨てるため、その代用にはしない | 上記に含む |
| 3. クリッピング・形×色選択なし | 残存。共通 draw 引数に `only_on`（番号配列）または region を足し、書込前画像のマスクを一度作る。region に ellipse/polygon と and/or/subtract を追加するなら、式の深さ・ノード数を制限する。色選択は最初に番号へ厳密解決する。GUI の選択表示と同じ規範ベクタを共有する | only_on 1〜2、複合 region 追加 2〜4 |
| 4. outline を繰り返すと太る | §6.4.11 とクラス N の意図どおり。既存の region は**出力マスク**であり、種集合の除外ではない。`seed_exclude_colors` 等を追加し、輪郭色を種に含めない集合から計算すれば再適用を制御できる。既定 N を無断で I に変えない | 1〜2 |
| 5. strip がない | **解消済み**。`render_preview.layout=strip/grid`、CLI も対応。DS 報告より新しい FIX-2 が main に入っている | 0 |
| 6. frames=all の誤解を招くエラー | FIX-2 後は共通フレーム解決を使用し、単一出力なら strip が使える。現在の説明も複数枚はディレクトリと示す。過去の文言だけを未修正バグとして再掲しない | 0 |
| 7. preview の矩形切出しなし | 残存。preview 引数へ rect/crop を追加し、オニオン・格子・定規に元座標オフセットを伝える。PNG を出してから外部で crop する手順を不要にする | 1〜2 |
| 8. Q-PIX-02 の差が点ごとでない | identity は rule/frames/layer（`quality.py:521`）であり、現在のデルタでは同じ issue の点の更新は new/resolved に出ない。SPEC の現契約には適合。`updated_issues` または points_added/removed を追加し、既存の identity を保つ。layer 推定も追加済みだが、複数寄与なら null が正当 | 1〜2 |
| 9. CLI 1 回約 4.7 秒 | §4 の現実測を参照。--no-sync と常駐 MCP、関連する数 Op の一括化を推奨。新規 subprocess ごとの import 費と、履歴全体の費用を分けて改善する | R1-04 と別途計測 |
| 10. undo→再 apply の差替え | 現行の安全な回避策はある。replace-last は undo と再編集の二段操作にせず、分岐・冪等キー・revision を含む単一トランザクションとして設計する。優先度は低い | 2〜3 |
| 11. 名前で色を使えない | 保存場所 `palette.names`、名前付け Op、get_palette の表示は**既にある**。不足は名前による解決と sym の別名表。`@body.shade` のような明示書式を追加し、重複名は曖昧エラーにする。内部では必ず番号へ解決する | 1〜2 |
| 12. その他 | `info --include layers --include frames` は後者だけになる。現 CLI は `--include layers,frames` / JSON 配列を案内すべき。update_layer.background の汎用説明は boolean 用に上書きする。タグ/スライスの表示色がパレット外なのは現仕様に適合。`skills/animate` の「frames=2,6 は失敗」は FIX-5/I-886 後には古い | 説明整理 0.5〜1 |

最低限の制作改善は move_cel、only_on、preview crop、色名の解決、手順書の更新で **5〜9 人日程度**。より大きい複合 region・履歴差替え・セルモデルの分離は別段階にする。試作で行った unlink→位置変更→同位置を再 link する回避策は妥当だが、パーツ数とフレーム数が増えるほどデータと Op 数が増える。

**第5世代風のパーツアニメ:** 現在の link は画像だけでなく位置・不透明度も共有するため、共有画像をフレームごとの位置で再利用するインスタンスモデルではない。小規模なら上記 move_cel の detach で作れる。本格対応では画像資源とセルインスタンスの変換を分離するスキーマ変更が必要で、Aseprite の読込・書出し・正規化・履歴・GUI を含め **8〜15 人日**。任意角回転やサブピクセル補間まで含めない。既存の整数・パレット規律を維持する。

## 6. 申し送りの実装案

### 6.1 汎用プロファイルを正本に固定する

現状は自由寸法の canvas と `ValidationSettings` があり、サイズクラス／機種制約の正式なモデルはない。`extensions` へ適当な dict を置くだけでは、既定値・検証・CLI/GUI の契約が分散する。

**提案:** `Project.profile` を既定 null の正式キーとして追加し、schema_version を 2 に上げる。§5.12 どおり 1→2 移行を実装し、既存作品は profile=null でピクセル不変にする。`canonical.MIGRATIONS`、`Project`、正準キー順、project schema、`.aseprite` の予約メタデータ保存、全 Op の describe/get_info を一緒に更新する。

プロファイルはプリセット名だけでなく、解決した**内容の snapshot** をプロジェクト内に保存する。ユーザー設定を更新しても既存作品が暗黙に変わらないようにする。内容 hash は digest フィールドを除いた正準 payload から計算する。外部定義はデータだけとし、eval・コマンド・Python モジュール名を受け付けない。

| 概念 | 持たせる情報・駆動対象 |
|---|---|
| ID / 版 / 出典 | カスタム定義も同じ方式。ローカル定義を明示的に解決し内容を固定する |
| アセット用途 | sprite / tileset / map / sheet 等。画面解像度と単体スプライト寸法を分ける。160×144 の画面向けだから単体アセットも160×144にする、という既定にしない |
| 粒度と推奨値 | 任意整数の推奨・許容寸法、タイル格子、palette budget、preview/export の既定倍率。既存の明示引数を優先する |
| 検証 | 色数・アルファ・タイルサイズ・タグ規約等の制約と severity。推奨作法は info、物理的な出力不能条件は error とする |
| 機種向け表現 | palette bank、local slot→global palette index 対応、タイル／object／map の配置、出力形式の版 |
| ワークフロー | skills に渡すガイド ID。大アセットの分割、三面図、実寸比較など。スクリプトを実行する欄にはしない |

**設定の優先順:** 明示的な Op 引数 → 正本内 profile の snapshot → 新規作成時だけ使うユーザー既定。環境の default profile がロード時の描画・検証を変えてはならない。`new --profile` は新規作成オプションとして追加する。MCP の `--profile standard/minimal` と同じ意味にしてはならない。

**追加 Op 案:** `list_asset_profiles` / `get_asset_profile`（読取）、`set_asset_profile`（snapshot の固定、変更デルタを返す）、`set_hardware_layout`（bank/object/map の割当）、`export_hardware`（形式と mapping を明示して出力）。既存の `new_project` に profile 入力を足し、`get_info` に解決値・出典・違反を返す。CLI/MCP/GUI は共通レジストリを通す。

プロファイルはユーザーが定義でき、主要機種のリストに閉じない。ただし「あらゆる粒度」は既存の面積・色数・整数倍率上限を無効にする意味にはしない。上限を拡大するなら R1-02/03 と大キャンバス検証を先に扱う。

### 6.2 ハードウェア制約を色数 1 個で表現しない

現コアの global palette は維持できる。機種側の local palette slot と global index の対応を別に持ち、書き出し時に厳密に変換する。取り込み後の再量子化で帳尻を合わせない。表現できない色や割当は、明示的な palette edit / remap が終わるまで拒否する。

タイルは現在 pixels/user_data、tile reference は番号＋x/y/d だけであり、ハードウェアの palette bank・object 属性・VRAM 配置を表す正式な構造ではない。機種対応はエクスポータの追加だけでは完了しない。

検証には、少なくとも次のデータと規則が要る。

- tile/object ごとの bank と local slot の閉包、各 bank の色数・透明規則、許されるアルファと色表現。
- タイル寸法・総数・重複統合後の配置量、map 寸法、object 寸法・個数・走査線使用数。後二者は単なる合成画像からは分からないので、明示的な object/layout を入力にする。
- バイナリ出力の bitplane 順・endianness・map 属性・番号割当。2bpp/4bpp の encoder と**独立した decoder**、手計算ベクタ、書出し後のファイル読戻しを用意する。
- 構造不変条件 S は解除不可。機種制約は新しい Q 規則として正確な資源 ID と違反量を返す。`export_hardware` は、通常 PNG の allow_invalid と同じ感覚で出力不能な bit 値を書かない。

申し送りの「16×16・3色」「DMG 4階調」「DS 80/96」「256シート・24fps」は要求例／観測材料であり、すべて同じ種類の制約ではない。可視色と透明枠、画面と単体アセット、作品上の慣習と機種の物理上限を区別する。正式な機種プリセットの数値は、採用する機種・モードの一次仕様を確認して別途固定する必要がある。本レビューでは外部資料による機種仕様の確定をしていない。

24fps は現在の整数 duration_ms では各フレーム等長にできない。必要なら n 番目の時間を `((n+1)*1000//24)-(n*1000//24)` として 41/42ms を配分し、周期の総時間を保つ。Q-ANI-03 の扱いを profile で説明し、GIF の丸め警告は維持する。タグ名 idle/attack/hurt/death/skill/power 等は制作ガイド／任意の規約であり、全作品へ必須にしない。

### 6.3 工程と費用

| 段階 | 成果と受け入れ条件 | 概算人日 |
|---|---|---:|
| A: 粒度 profile | schema 2・移行・内容固定、設定優先順、new/set/get、CLI/MCP 契約、get_info/skills 接続。旧作品の JSON 移行と全画素不変 | 4〜6 |
| B: 制作摩擦 | §5 の最低限改善。linked 移動・クリップ・crop・色名を実 DS シナリオで確認 | 5〜9 |
| C: 最初の機種・モード | bank/layout、制約検証、2bpp 等 1 系統の writer/独立 reader、手計算ベクタ・実ファイル確認 | 6〜10 |
| D: GUI 工学 | profile 選択、実寸／拡大比較、違反資源への移動。見た目の設計・審査は担当モデルの別作業 | 2〜4 ＋デザイン |

A+C は **10〜16 人日**が目安。R1-05 の共通プラグイン機構を先に完成させるなら、その費用は別に必要。最初の専用 exporter を組み込み Op として作れば、その工程を依存先から外せる。残りすべての機種や任意角パーツアニメまで含む見積もりではない。共通化の効果と機種固有の割当仕様によって後続費は変わる。R1-01〜03 の安全な入出力境界を最優先にする。

### 6.4 DM 知見と制作分担

申し送りで確定した **Codex imagegen が通常三面図 → ピクセルアートライク三面図を作り、Opus が解釈して最終ドットを打つ**工程は、現在の `skills/` の標準手順にまだ明記されていない。`draw-sprite` / `import-convert` / `animate` と README の入口を揃える必要がある。M9 の実 GPU がなくても、外部原画を provenance 付きで source に取り込む既存経路でこの分担は実施できる。

原画をキャンバスに置く場合は import_image のみを使う。原画は原画として source に保存し、誰が何を生成したか・prompt・license（不明なら unknown）を残す。通常三面図とピクセル風三面図の 2 種、選択した案、目標 profile、パーツ対応表を制作申し送りとして固定する。手順書更新と小さな再現 e2e の準備は **1〜2 人日**が目安で、作品の美的完成を保証する日数ではない。

制作評価では実寸・整数拡大・シルエット・顔の切出し・フレーム比較を利用者が見られるようにする。顔や目の寸法比は、作者が指定した landmark/bbox がある場合の**任意の計測・比較**には使えるが、輪郭や顔を認識するモデルが現コアにあるわけではない。特定の比率を全キャラクターの hard error にする設計は避ける。客観規則の合格と人間の採用判断を別々に記録する。

大きい作品は三面図→パーツ→フレーム→シートの段階で検証し、小さい作品は色の役割と実寸可読性を早く確認する。形・階調の固定雛形を強制するのではなく、利用者に方向を選んでもらう既存の 3 案手順へ接続する。

「既存作品のタイル資料から統計を抽出する」案は、一般のタイルダンプ画像を測定して任意 profile へ添える最初の実装なら **2〜4 人日**程度。専用 ROM パーサ、未知形式からの意味推定、顔パーツの自動識別まで含めない。まず自作・利用者提供の測定用資料で、色数・連結成分・占有率などの再現可能な統計を出す。既存製品のアセットを本体・ゴールデンに追加しない。サンプル数と測定対象を示し、少数の参照から得た作法を機種仕様に昇格させない。

## 7. 補助再現コード

### H: ジャーナル肥大時の同一編集

実コミット由来の行を複製する負荷用 fixture。undo の正確性を検証する fixture ではない。出力値は OS 負荷で変動する。

```python
import json, tempfile, time, statistics
from pathlib import Path
from cybersprite import ops
from cybersprite.core import history
with tempfile.TemporaryDirectory() as t:
    p = Path(t) / "p"
    ops.execute("new_project", p, {"width": 16, "height": 16})
    args = {"layer": "L1", "frame": 0, "x": 1, "y": 1, "color": 1}
    ops.execute("set_pixel", p, args, preview="none")
    sample = history.read_journal(p)[-1]
    for count in (10, 1000, 10000):
        data = history.journal_bytes([dict(sample, revision=i+1) for i in range(count)])
        (history.paths(p) / "journal.jsonl").write_bytes(data)
        ms = []
        for i in range(3):
            start = time.perf_counter()
            ops.execute("set_pixel", p, {**args, "color": 2 if i % 2 == 0 else 1},
                        preview="none")
            ms.append(round((time.perf_counter() - start) * 1000, 3))
        print(count, len(data), ms, statistics.median(ms))
```

### P: GUI と core の有限再生列

GUI の実関数だけを抽出して実行する。新しいツール・依存の導入はしない。Timeline の cycle 制御と同じ回数で連結する。

```powershell
Push-Location gui
@'
const fs = require('node:fs'), ts = require('typescript');
const input = fs.readFileSync('src/store/index.ts', 'utf8');
const tree = ts.createSourceFile('index.ts', input, ts.ScriptTarget.Latest, true);
const node = tree.statements.find(s => ts.isFunctionDeclaration(s) && s.name.text === 'playbackFrames');
const js = ts.transpileModule(node.getText(tree).replace('export ', ''), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS }
}).outputText;
const fn = new Function(js + ';return playbackFrames')();
for (const repeat of [1, 2, 3]) {
  const cycle = fn({from: 0, to: 2, direction: 'pingpong', repeat}, 3);
  console.log(repeat, Array.from({length: repeat}, () => cycle).flat());
}
'@ | node
Pop-Location
@'
from cybersprite.core.projects import new_project
from cybersprite.core.models import Tag
from cybersprite.formats.common import animation_sequence
p = new_project(width=1, height=1, frames=3)
for n in (1, 2, 3):
    p.tags = [Tag(id="T1", name="test", **{"from": 0, "to": 2},
                  direction="pingpong", repeat=n)]
    print(n, animation_sequence(p, tag="T1", loop=1))
'@ | uv run --no-sync python -
```

### L: 大キャンバス測定（Windows）

下の Python を上記と同じ here-string で実行する。子プロセスごとに peak を分離する。4096² 密画像を割り当てるコードではない。

```python
import subprocess, sys
code = r'''
import ctypes, json, sys, time
from ctypes import wintypes
from cybersprite.core.projects import new_project
from cybersprite.core.models import ImageCel
from cybersprite.core.render import render
from cybersprite.core.quality import report
class Counters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
        (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize",
        "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
        "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
n = int(sys.argv[1]); dense = sys.argv[2] == "dense"
p = new_project(width=n, height=n)
p.layers[0].cels = [ImageCel(frame=0, x=0, y=0, w=n if dense else 1,
    h=n if dense else 1, pixels=["01" * n] * n if dense else ["01"])]
start = time.perf_counter(); render(p); rt = time.perf_counter() - start
start = time.perf_counter(); q = report(p); qt = time.perf_counter() - start
c = Counters(); c.cb = ctypes.sizeof(c)
h = ctypes.windll.kernel32.GetCurrentProcess; h.restype = wintypes.HANDLE
f = ctypes.windll.psapi.GetProcessMemoryInfo
f.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
assert f(h(), ctypes.byref(c), c.cb)
print(json.dumps(dict(size=n, dense=dense, render_ms=rt*1000, validate_ms=qt*1000,
    peak_working_set_mib=c.PeakWorkingSetSize//1024//1024, ok=q["ok"])))
'''
for n, mode in ((1024, "dense"), (4096, "sparse")):
    result = subprocess.run([sys.executable, "-c", code, str(n), mode],
                            capture_output=True, text=True, timeout=55, check=True)
    print(result.stdout.strip())
```

## 8. 修正後レビューで必要な証拠

1. R1-01 の全経路で正本を保護し、失敗時 bytes 不変を確認する。新しい入力・仕事量予算が割当前に作用することを確認する。
2. R1-05 の v1 対応範囲を SPEC と実装で一致させる。GUI の policy と有限再生列を共通契約へ揃える。
3. Windows/Linux の CI 結果、全ゴールデン一致、履歴肥大時ベンチを添える。既知の性能未達と実生成画像較正の未了は、修正済みと混同しない。
4. DS 再試験では標準の三面図工程、linked パーツの移動、陰影クリップ、顔の実寸比較、最終全フレームと実書出しを確認する。利用者の採用判断を作者の自己評価で代替しない。

<a id="current-review"></a>

## 9. 依頼再受領時の現 HEAD 追補（2026-11-13 JST）

### 9.1 対象と判定の読み方

今回の依頼開始時点では R1 本書、Codex R2、上流の `docs/REVIEW_1.md`・`docs/REVIEW_2.md`、公開前修正が既に存在した。過去のレビューを上書きせず、現在の `main` **`d2cf0e8`** に対する再検証をここに残す。`REVIEW_REQUEST_1.md` の「1411 tests」「Linux 未実行」「プロファイル未実装」は依頼作成当時の状態である。現在の不足の入口は `KNOWN_ISSUES.md` と後続レビューだが、それらの解消申告だけで判定していない。

作業途中に別作業の **`b7a44f1`** が加わった。`git diff d2cf0e8 b7a44f1` は `docs/PUBLICATION_AUDIT.md` だけで、`src`・`gui`・`skills`・`tests`・SPEC の差分がないことを確認した。本追補の再現対象の実装は同じである。

完了直前には別担当の `CODEX_REVIEW_R2.md` 更新も作業ツリーに現れた。当方は同ファイルを編集していない。§9.2 の参照・追試は更新前の `d2cf0e8` にある R2 本文に基づくため、下の抽出コマンドも同コミットに固定した。新しい R2 文書の測定値を今回の値へ混ぜていない。

指定された申し送り 2 冊、旧 DS 制作報告 §6、SPEC、要件メモ、判断・進捗・工程報告、実装・テスト・skills を照合した。非公開の申し送りは設計要求として評価し、協力者の識別子・DM 原文・参照画像を本書へ追加していない。外部サイト、他製品のソース、モデルの重みは参照していない。新規依存・実装変更・コミット・push はない。

**当初の正本破壊 blocking を現在の不具合として再掲しない。一方、失敗時の出力復元と資源予算の残存を理由に、製品完成の承認は留保する。** 本追補で再現を確認した現存項目は **blocking 0 / major 5 / minor 2**。このうち major 4・minor 1 は既存 Codex R2 の追試であり、新規件数に足さない。新規は参照再登録の復旧不能（minor 1）と汎用 exporter の累積予算漏れ（major 1）。これは全レビュー台帳の残件総数ではない。

### 9.2 既存指摘の追試結果（重複登録しない）

当初の blocking の確認には `uv run --no-sync python tools/r1_a1_acceptance.py` も再実行した。CLI 直接名・MCP 直接名・GUI の `{name}` 展開の 3 経路とも `E_PATH_NOT_ALLOWED`、`canonical_and_history_unchanged=true`。locked layer への import は dry-run と本実行の両方で `E_LAYER_LOCKED`、cwd 外 root の GUI export は `validation_ok / verified=true` となった。この範囲は解消を維持する。

以下の C-R2 は [Codex R2](CODEX_REVIEW_R2.md) §3 の番号である。再現コマンドの全文も同書にある。現在の行番号は今回の HEAD で確認したもの。巨大配列は実際には割り当てず、既存の無割当スパイで要求寸法を調べた。

| 既存 ID・重大度 | 現 HEAD の根拠と実測 | 修正の単位・概算 |
|---|---|---|
| **C-R2-01 / major** 出力復元 | `formats/plugin_export.py:95` の `staged.replace(path)` が SaveContext を通らない。MCP の成功封筒生成を故障注入すると、PNG は旧 bytes を復元するが、`export_native` は `E_INTERNAL` を返して新 bytes を残す。CLI で連番 PNG の 2 枚目に I/O 故障を入れると終了 4、旧 bytes を保持したのは `[False, True]`。正本上書きの再現ではない | 本体の最終置換を共通保存境界に通す。CLI・GUI・直接 Op も出力群と結果検証まで同じ保存スコープで包む。第三者コードの任意副作用の取消しとは別。**1〜2 人日** |
| **C-R2-02 / major** mask の取引予算漏れ | `ops/drawing.py:49` の `_work` は mask 付き `set_pixel` も 1 と数え、`:172` 以降で canvas 全体を走査する。1024²・`mask.only_on=[0]` の 17 Op が成功し、最低 **17,825,792 px** の走査が取引上限 **16,777,216** を超える。SPEC §5.11 の mask 面積予約に不適合 | region の各ノード、only_on/not_on、対象タイル群の走査を DrawingBudget に予約する。拒否は割当前・コミット前。境界の直下／直上、空 mask、1000 Op を確認。**1〜2 人日** |
| **C-R2-03 / major** PixelOE の中間積 | `pipeline/external/pixeloe.py:29–31` が target と pixel_size を個別に検査し、`:50` 付近の interpolate が積を検査しない。1024²・pixel_size=16 は **16384²** の RGBA float tensor を要求することをスパイで再確認。単一 tensor だけで **4,294,967,296 bytes**、追加 scratch は別 | adapter が外部処理に入る前に中間 bytes を整数で検査する。入力／最終出力の 256 MiB 制限を RSS 保証と解釈する修正では足りない。未導入依存をロードする前の検査も可能。**0.5〜1 人日** |
| **C-R2-04 / major** GUI repeat 全展開 | `gui/src/store/index.ts:15–26` と `Timeline.tsx`。実 TS 関数を抽出・transpile し、2f・pingpong・repeat=65535 で **65,536 要素**を得た。合法な最大 4096f の forward では **268,431,360 要素**になる（後者は算術のみ）。サーバの出力列上限はブラウザ内の同期展開を止めない | 再生カーソルを方向・片道番号・残り回数で管理するか、展開前に上限を検査する。有限停止と末端 duration の共有ベクタは保持する。**1〜2 人日** |
| **C-R2-05 / minor** tick の部分選択 | `ops/platform_ops.py:152–158` が選択フレームだけで位相を作り直す。motion・6f・ticks=1 の一括は **[41,42,42,41,42,42] = 250 ms**。各コマを分割設定すると **[41,41,41,41,41,41] = 246 ms**。validate の tick_deviations は **0**。SPEC §5.13 のタグ先頭からの累積配分と不一致 | 実行と検証で同じ位相規則を共有する。非選択コマの tick 数の扱いを決め、飛び飛び選択・重複タグ・分割呼出しのベクタを固定する。**1〜2 人日** |

追試は既存文書のコードをそのまま抽出して実行した。PowerShell、root からの再現コマンドは次のとおり（故障注入先は TemporaryDirectory 内の自作 fixture のみ）。

```powershell
@'
import re, subprocess
review = subprocess.check_output([
    'git', 'show', 'd2cf0e8:docs/review/CODEX_REVIEW_R2.md'
]).decode('utf-8')
for item in ('R2-01', 'R2-02', 'R2-03', 'R2-05'):
    section = review.split('### ' + item + ' ', 1)[1].split('\n### ', 1)[0]
    code = re.search(r'```python\n(.*?)\n```', section, re.S).group(1)
    print(item, flush=True)
    exec(compile(code, item, 'exec'), {})
'@ | uv run --no-sync python -
```

GUI の再現は同書 C-R2-04 の `node` コマンドである。試験が通っても、この 5 件が解消したとはしない。

### 9.3 新規 R1-A01 — minor: 欠落・破損した参照を再登録しても復旧しない

**根拠:** `ops/references.py:172–191` の重複判定は manifest に記録された SHA-256 だけを見る。同じ digest があれば `duplicate=true` を返し、保存先の存在・実 bytes の hash を検査しない。保存済みファイルを削除してから元画像を再登録しても `ok=true / duplicate=true`、ファイルは欠落したまま。破損 bytes の場合も修復されない。どちらも validate に **Q-SRC-05** が残ることを再現した。

`.cybersprite/` の掃除による参照消失自体は公開前報告 §3.4 に申告済みである。今回の新規部分は、利用者が原本を持って再添付する通常の復旧手段でも直せないこと。作品ピクセルの破壊や登録先からの脱出は確認していないため minor とする。

**再現コマンド（PowerShell、root）:**

```powershell
@'
from pathlib import Path
from tempfile import TemporaryDirectory
import numpy as np
from cybersprite import ops
from cybersprite.formats.png import encode_png

with TemporaryDirectory() as d:
    r = Path(d); p = r / 'p'; f = r / 'reference.png'
    f.write_bytes(encode_png(np.full((2, 2, 4), 255, dtype=np.uint8)))
    ops.execute('new_project', p, {'width': 2, 'height': 2}, preview='none')
    a = {'file': str(f), 'rights_note': 'self-authored review fixture'}
    first = ops.execute('register_reference', p, a)['result']
    target = p / first['files'][0]
    target.unlink()
    second = ops.execute('register_reference', p, a)
    print(second['ok'], second['result']['duplicate'], target.exists())
    # True True False
    target.write_bytes(b'corrupted')
    third = ops.execute('register_reference', p, a)
    print(third['ok'], third['result']['duplicate'], target.read_bytes() == f.read_bytes())
    # True True False
    print([i['rule'] for i in ops.execute('validate', p)['result']['issues']])
    # Includes Q-SRC-05
'@ | uv run --no-sync python -
```

**期待:** 重複の早期 return 前に `sources.file_matches` 等で実体を照合する。不一致なら、今回受け取った digest 一致の bytes を既存 ID の場所へ保存トランザクションで復元するか、少なくとも具体的な復旧方法つきの失敗を返す。ID や最初の登録者を勝手に更新しない。正常重複の bytes 不変、欠落／破損の修復、dry_run 不変、修復途中の I/O 失敗時の復元を確認する。schema 変更は必須ではない。**0.5〜1 人日**。

### 9.4 新規 R1-A02 — major: 汎用 exporter の比較画像に累積予算がない

**根拠:** `formats/plugin_export.py:70` は `verification_frames` のない exporter に対して、`expected = [render(document, f) for f in range(len(document.frames))]` と全 RGBA を保持する。個々の render の出力検査はあるが、同時保持する全フレームの積を検査しない。`:81` の decoder 有無の確認より前なので、decoder を持たず `verified=false` を返す exporter でも不要な比較画像をすべて作る。writer の任意副作用ではなく、本体の事前処理の問題である。SPEC §5.11 の「同時保持する項目群」の予算に不適合。

**安全な再現:** 下では入力・実 renderer・品質 gate は実物のまま、予算を 16 KiB に縮め、自作の無害な exporter を差し込む。各 4096 bytes は合法だが 5 枚合計 **20480 > 16384** の比較画像を本体が作り、出力が成功する。既定値のままでも 4096²・5f は **335,544,320 > 268,435,456 bytes** になる。別の無割当スパイで既定予算の 4096²・5f が全 5 回の render 呼出しと writer まで到達することも確認した。巨大 RGBA の実割当はしていない。

```powershell
@'
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from cybersprite.core import limits
from cybersprite.core.models import Model
from cybersprite.core.projects import new_project
from cybersprite.formats import common, plugin_export
from cybersprite.formats.export_args import PluginExportArgs
seen = []; real_render = plugin_export.render
def record(p, frame):
    rgba = real_render(p, frame); seen.append(rgba.nbytes); return rgba
def writer(p, renderer, out, options):
    out.write_bytes(b'fixture')
    return dict(files=[], fingerprint='fixture', warnings=[],
                validation_ok=True, verified=False)
plugin = SimpleNamespace(name='fixture', extension='.tiny', options_model=Model, write=writer)
p = new_project(width=32, height=32, frames=5)
with TemporaryDirectory() as d, common.export_policy(d), \
     patch.object(limits, 'OUTPUT_BYTES', 16384), \
     patch.object(plugin_export, 'resolve_exporter', return_value=plugin), \
     patch.object(plugin_export, 'render', record):
    result = plugin_export.export_plugin(p, PluginExportArgs(out='result.tiny', format='fixture'))
    print(seen, sum(seen), limits.OUTPUT_BYTES, (Path(d) / 'result.tiny').exists(),
          result['validation_ok'])
    # [4096, 4096, 4096, 4096, 4096] 20480 16384 True True
'@ | uv run --no-sync python -
```

**期待:** decoder がない場合は比較画像を作らない。通常の全フレーム比較は、リスト生成前に `output_bytes(width, height, count)` 相当で累積量を検査するか、decoder との逐次比較を契約化する。`verification_frames` の独自経路も、組込 native と共通の予算責任を明記する。decoder 有／無・予算直下／直上を検査し、拒否時に writer が未実行であることを確認する。Python plugin 全体の sandbox を求める指摘ではない。**0.5〜1.5 人日**。

### 9.5 正確性・契約・セキュリティの評価

- **整数と決定性:** `raster`、合成、固定小数点 Oklab は整数の規範処理を保持している。ランダムな試験は固定 seed で、描画本体の乱数ではない。時刻は来歴・履歴の記録経路に分離されている。外部 PixelOE の浮動小数は明示された adapter 境界であり、内蔵ラスタ処理への混入として数えない。
- **テストの有効な点:** `tests/unit/test_raster.py` の手計算・固定 seed 性質テスト、`tests/vectors/raster/` の Python/TS 共通ベクタ、`test_render.py` の palette 閉包と低 index の同距離 tie-break、`test_m7_tiles.py` の非対称形 8 反転・非正方形 d 規則、roundtrip のリンク／タイル／metadata を確認した。ゴールデンを変更して成功させる操作はしていない。
- **境界の不足:** 正常な PNG の verified だけでは native 最終保存の応答失敗を覆えず、小さい repeat の共有ベクタでは巨大な再生列を覆えず、mask 1 回の単発上限では取引全体を覆えない。C-R2-01〜04 はこれらの層間の欠落である。
- **契約:** schema drift 検査は成功した。これは CLI/MCP/保存モデルが共通定義へ追従する証拠だが、全組合せの意味的一致の証明ではない。C-R2-05 が実例。旧 R1 で提案した schema 2 は現 SPEC §5.13.1 の D-41 により不要となっており、現在は省略可 `platform` を schema 1 に追加する契約に従って評価した。
- **GUI 認証・パス:** loopback、Host/Origin 一致、token の compare_digest、WebSocket の両必須条件、HTTP cookie、typed path の resolve を確認した。実サーバ試験には token 不正／欠落・異 origin・許可外出力・cwd 外 root のケースがある。認証回避は今回見つけていない。token 認証を、認証済み要求のメモリ上限と同一視しない。
- **プラグイン:** API 版・許可した提供者・失敗時登録復元の共通境界が入っている。importers 実行は現 SPEC に v1.x と明記され、当初の「7 群すべて v1」の主張は残していない。Python plugin は信頼済み外部コードであり、sandbox 完成とは判定しない。native/plugin 最終置換の問題は C-R2-01 に集約する。

### 9.6 必須申し送りの現在の実装可能性と残費用

**汎用粒度／機種プロファイルの芯は実装済みで、初期案を一から作る段階ではない。** `core/models.py:Project.platform`、`core/platform.py` の型、`platforms/__init__.py` のデータ定義・継承解決、`ops/platform_ops.py` のレジストリ Op、`quality_platform.py` の Q-PLT、`core/craft.py` の情報指標、CLI/MCP/GUI が接続されている。

| 要求 | 現状・必要な具体作業 | 残費用の目安 |
|---|---|---:|
| 任意粒度と画面／単体アセットの分離 | `system.screen` と `asset.canvas`、defaults、validation、workflow を分離。`new_project` / `set_platform` / `list_platforms` / `conform_palette` / `set_frame_ticks` が既存 Op。解決済み snapshot と master_colors を正本に保存し、既存作品を外部定義変更で変えない | 芯の再実装 **0**。追加の単純なデータプリセットは **0.5〜1 人日／件**、数値の一次資料確認は別 |
| 機種の物理制約と binary 出力 | RGB bits／master、alpha、palette 行・slot0、tile/object/block 単位、tile flip・数・map 寸法の検査がある。gb-2bpp stream は実装済み。VRAM／bank／map／scanline の自動割付と追加形式は未完成 | 最初の追加 1 モードは **5〜10 人日**。後述の明示 layout モデル、独立 decoder・ベクタを含み、全機種分ではない |
| リンク位置の罠（DS §6-1） | `set_cel` の既定 `linked=error`、all/unlink、必須 scope の `move_cel` で黙った全員移動を防ぐ。画像だけ共有して位置を独立させる offset links は未実装 | 安全策 **0**。共有画像／位置インスタンス分離は schema・正準化・履歴・形式・GUI 横断 **8〜15 人日** |
| 相対移動と原点（§6-2） | move_cel dx/dy、get_info の cels がある | **0** |
| 陰影 clip／図形選択（§6-3） | mask.only_on/not_on と ellipse/polygon・複合 region がある。取り込み後の近似色を増やす経路ではなく palette index で選ぶ | 機能追加 **0**。予算の直しは C-R2-02 の **1〜2 人日** |
| outline（§6-4） | selective／exclude_colors で外周の条件付き冪等性を扱う。inside の一般冪等性は未完成と記録されている | 現契約を実装漏れとして数えない。inside の意味と種集合を拡張するなら **1〜3 人日** |
| strip／crop／色名（§6-5、7、11） | strip/grid/review、rect crop、`@name` / `@ramp:k` が実装されている | **0** |
| 24fps とタグ規約 | 有理数 tick と motion の任意タグガイドがある。256px が sheet 寸法か frame 寸法かは申し送りだけでは確定しない。固定 canvas 値へ断定していない | 部分設定の修正 C-R2-05 **1〜2 人日**。寸法解釈の決定は発注者事項 |
| 実資料の統計と顔の比率 | 人が渡した参照を登録できる。craft は計測と情報であり、顔の可読性・人間の採用を機械判定しない。専用 analyze は延期 | 画像／既知 tile dump から色数・成分・占有率を抽出する初版 **2〜4 人日**。顔の自動意味認識・ROM 解析は含まない |

**次のスキーマ変更をするなら:** pixel index 正本を保ったまま、明示的な hardware layout に tile/object→bank、slot→global index、map 属性、VRAM 割当を持たせる。`set_hardware_layout` のような mutate Op と `get_info` 表示を追加し、構造参照・slot 閉包・重複配置の検証、資源上限の Q ルール、native export の解除不可な表現可能性検査を分ける。互換性を壊す追加は §5.12 の schema 移行、正準キー順、undo snapshot、`.aseprite` metadata 保持、CLI/MCP の生成スキーマまで一緒に更新する。encoder だけを足して「機種対応済み」としない。

費用は工学実装＋回帰確認の概算であり、独立した行の共通部分を重複加算しない。機種の数値・モードは今回外部一次資料で再監査していないため、表の期間にハード仕様の確定作業は含めない。

**制作分担と知見:** skills/README と turnaround-parts は「通常三面図 → ピクセル風三面図の生成を Codex imagegen、解釈・打点・見た目の判断を Opus」とし、3 関門、人間判定 pending、改善前後の並置と疑う箇所 3 点を定めている。これは必須申し送りへの実装回答として成立する。ただし `turnaround-parts.md` には `add_source` 等を「まだ無ければ」とする実装前の説明が残り、新 Op を動く例で工程へ組み込む改訂は必要（上流 R2-08）。機能があることだけで、初見の制作担当が使いこなせるとは判定しない。48px は未較正の工程目安で、普遍的な成功境界とはしない。極小の顔の可読性、大きい題材の部品分割、色の役割、背景抜きの混色は工程・計測対象として扱い、ゲーム名や既存絵の画素を品質の固定雛形にしない。

申し送り後半の「既定の制作担当は Opus、imagegen は例外」という再配分と今回の独立 Codex レビューは矛盾しない。今回、制作やビジュアル採点・他エージェントへの委任は行っていない。GPU／ComfyUI／外部方式については既存報告と接続境界を照合し、今回実 GPU・実 ComfyUI を動かしたとは主張しない。PixelOE の資源修正を除き、新しい生成方式を無断で追加する提案にはしていない。

### 9.7 他レビューとの照合

指定された `docs/review/FABLE_REVIEW_R1.md` は現 HEAD に存在しない。実際の上流レビューは `docs/REVIEW_1.md` と `docs/REVIEW_2.md` にある。後者は既存 Codex R2 の 5 件を採用済みなので、同じ問題に新番号を振って独立発見の件数を増やさない。

- 本追補 C-R2-01 は上流 **R2-06**。公開前報告の「**R2-01 解消**」は CLI render/preview 等の予約領域保護を指し、**C-R2-01 の出力復元の解消ではない**。混同すると、今回再現した残件を閉じてしまう。
- C-R2-02/03/04/05 はそれぞれ上流 **R2-05/07/20/19** と同根。同じ root cause として管理する。
- **重大度の相違:** GUI repeat は上流 R2-20 が「通常の制作で踏む値ではない」として minor、Codex は major。本追補は、受理した保存データから同期処理でブラウザ停止規模の要求を作れ、サーバ予算も効かない点を重視して major を維持する。停止そのものの実験をしたという意味ではない。
- 上流は importers を「延期を仕様へ明記したので R1 解消」、Codex R2 は「当初の全群完成ではないので部分解消」と評価した。完成範囲の評価軸の差であり、現状のコードや延期の有無で争っているわけではない。
- 上流の制作物の見た目の講評は本追補では独立採点していない。利用者の採用待ちを維持する。特定の目の比率や形の禁止を、工学上のハードエラーとして追加しない。

### 9.8 今回の検査記録と性能の扱い

Windows の既存環境を `uv run --no-sync` で使い、依存を同期・追加していない。以下は今回の実行結果であり、§1〜8 や Codex R2 の成功件数の転記ではない。

| 検査 | 今回の結果 |
|---|---|
| `uv run --no-sync pytest -q --tb=short` | **2143 passed / 12 skipped、1134.18 秒（18分54秒）**、終了 0 |
| `cd gui; npm test -- --run` | **710 passed**、contrast **102/102**。余分な `--run` に npm の非推奨警告が出たが終了 0 |
| `cd gui; npm run build` | icons・TypeScript・Vite 成功 |
| build 後の `cd gui; npm run test:e2e` | **6 passed、1.5 分**。新しい手動参照添付も実ブラウザで成功 |
| `uv run --no-sync python tools/gen_schemas.py --check` | 成功 |
| `uv run --no-sync python tools/check_repository.py` | 成功 |
| `uv run --no-sync python tools/r1_a1_acceptance.py` | 成功。正本保護 3 経路・locked import の両モード・cwd 外 GUI root を確認 |
| §9.2 の既存 5 件・§9.3〜4 の新規 2 件 | 上記の実測どおり再現 |

ブラウザ試験中、ページ切替時の WebSocket 送信に `WebSocketDisconnected` の ASGI ログも出た。6 件の試験は成功し、今回のログだけでデータ破壊や認証回避とは判定しない。この切断ログは既存 Codex R2 にも観測記録がある。Linux、Python 3.13、実 GPU、実 ComfyUI、外部 pixelizer の別導入環境、配布 wheel とライセンス原文全件は今回再実行していない。4 環境の CI 成功は既存報告の証拠と、今回の Windows での検査を区別する。

12 skip は Windows の symlink 権限 5 件、未導入外部 pixelizer 6 件、明示 opt-in の GPU 1 件。新規の再現コードは既存テストへ追加しておらず、全体テスト成功と新規の境界不具合の再現が両立する。修正作業では再現を回帰テストへ移す必要がある。

**性能の実測条件:** 各 3 回、既存の測定器を使用した。全体 pytest・GUI 検査・ほかの測定が並行し、B2 の呼出し直前の空き物理メモリは **約 180〜816 MiB** まで変動した。OS・他アプリ・CPU 周波数を固定していない。以下を「静かな再計測」「修正による回帰／改善率」「全環境の上限」として使わない。現条件で DS の編集が秒単位になる事実と、公表値が得られた条件を区別する。

再現コマンド（root、出力 JSON は OS の一時領域）:

```powershell
uv run --no-sync python -m tools.benchmark_r1_b2 --case small_32_3_4 --case ds_96_8_45 --case validate_256_1_32 --out "$env:TEMP/cybersprite-review-r1-b2.json"
uv run --no-sync python -m tools.benchmark_r1_large --out "$env:TEMP/cybersprite-review-r1-large.json"
uv run --no-sync python tools/benchmark_pipeline.py
```

B2 はフレームごとに内容が異なる独立セルを使い、編集は毎回 `no_op=false` を assert する。cold 検証はメモリ上のモデルに対する全品質検査（フレーム解析 LRU を毎回空にする）で、読込時間は含まない。編集は正本読込・履歴・保存を含み preview=none。CLI は実行ファイルの起動〜info終了で uv の同期は含まない。**単位 ms、括弧内が中央値。**

| fixture | 1px 編集の 3 回 | cold 検証の 3 回 | CLI info の 3 回 |
|---|---|---|---|
| 32²・3層・4f | 166.180 / 289.032 / 381.424（289.032） | 78.003 / 20.975 / 12.924（20.975） | 7016.266 / 5808.337 / 5126.698（5808.337） |
| 96²・8層・45f | 5044.100 / 4092.543 / 3758.663（4092.543） | 3976.060 / 3534.530 / 3600.364（3600.364） | 3240.245 / 5132.413 / 3522.065（3522.065） |
| 256²・1層・32f | 3006.087 / 2453.080 / 2012.685（2453.080） | 3731.898 / 3708.486 / 3983.445（3731.898） | 3992.350 / 3951.463 / 2753.717（3951.463） |

解析再利用の検証中央値は順に **3.512 / 753.811 / 272.555 ms**。cold と取り違えない。`docs/PERFORMANCE.md` 冒頭の別条件での 96² 編集 1379.0 ms・256² cold 検証 1174.9 ms を、今回の値で誤計測と断定する根拠はない。一方、その静かな条件の目標達成を、メモリ圧迫時や任意の制作へ一般化することもできない。

**4096² とメモリ:** 大画像用測定器は新しい子プロセスで render→validate し、全 6 試行で validate `ok=true`。1024² は密、4096² は **1×1 セル 1 個の疎画像**、いずれも 1 層 1f。

| fixture | render ms・3 回（中央値） | validate ms・3 回（中央値） | peak working set bytes・3 回 |
|---|---|---|---|
| 1024²・密 | 930.914 / 785.860 / 754.762（785.860） | 1846.595 / 1084.498 / 1138.277（1138.277） | 218890240 / 221278208 / 221446144 |
| 4096²・疎 | 82.642 / 47.415 / 45.301（47.415） | 1425.223 / 1526.217 / 1444.676（1444.676） | 277872640 / 345309184 / 282169344 |

出力予算 256 MiB は RSS 上限ではなく、今回もピークはそれを超える。密な 4096²、多層・多フレーム・完全な点集合出力や craft を重ねた最悪負荷まで実測した結果ではない。preview 64 倍や PixelOE の 4 GiB 要求の実割当は行っていない。

**パイプライン:** `benchmark_pipeline.py` の自作 hero をタイル状に繰返し、16 倍に拡大した 1024²→64²、upscaled・段階 PNG 保存までを計測。**1632 / 2084 / 2241 ms**、全 3 回 `accepted / verified=true`、5 秒目標内。同じ工程の再現であり、写真・実生成三面図・外部方式の一般精度や速度ではない。較正版 5 の (e)10/12 拒否、(f)3/34 拒否、(d)8/13 合格と 95% 未達は [CALIBRATION](../../tests/pipeline/CALIBRATION.md) に明記されており、この速度測定で精度の残件を閉じない。

**履歴肥大:** `tools.bench_persistence` の元の H も再実行したが、各件数で色を 2/1/2 と固定するため、前の件数の最後の色が 2 なら次の先頭が no_op になりうる。性能改善の主表には使わず、§7 H を下のように、全試行で実変更を assert する形で再実行した。測定器自体は変更していない。

| 初期合成 journal 行数 | 初期 bytes | 実変更 3 回 ms | 中央値 ms | no_op |
|---:|---:|---|---:|---|
| 10 | 4391 | 90.2101 / 130.2625 / 84.1471 | 90.2101 | 全て false |
| 1000 | 440893 | 118.4967 / 91.6764 / 82.1526 | 91.6764 | 全て false |
| 10000 | 4418894 | 156.0078 / 132.7863 / 176.2924 | 156.0078 | 全て false |

これは実コミット 1 行を複製した合成負荷であり、1 万回の正当な編集・undo を積んだ耐久試験ではない。追記 journal・索引・区画化の実装と整合する結果だが、roll や索引欠損の再構築の最悪時間は未確定。大量 Op の点数／取引上限はあるものの、C-R2-02 が示すとおり走査仕事量の網羅は未完成である。

```powershell
@'
from pathlib import Path
from tempfile import TemporaryDirectory
from statistics import median
from time import perf_counter_ns
from cybersprite import ops
from cybersprite.core import history
with TemporaryDirectory() as d:
    p = Path(d) / 'p'
    ops.execute('new_project', p, {'width': 16, 'height': 16}, preview='none')
    a = {'layer': 'L1', 'frame': 0, 'x': 1, 'y': 1, 'color': 1}
    ops.execute('set_pixel', p, a, preview='none')
    sample = history.read_journal(p)[-1]; previous = 1
    for count in (10, 1000, 10000):
        data = history.journal_bytes([dict(sample, revision=i+1) for i in range(count)])
        (history.paths(p) / 'journal.jsonl').write_bytes(data)
        values = []
        for i in range(3):
            previous = 3 - previous
            start = perf_counter_ns()
            v = ops.execute('set_pixel', p, {**a, 'color': previous}, preview='none')
            values.append(round((perf_counter_ns() - start) / 1000000, 4))
            assert v['ok'] and not v['no_op']
        print(count, len(data), values, median(values), flush=True)
'@ | uv run --no-sync python -
```

初回 `python tools/bench_persistence.py` は `ModuleNotFoundError: tools` で終了したため、パッケージ入口の `python -m tools.bench_persistence` に直して実行した。この起動ミスを製品の性能値に含めていない。
