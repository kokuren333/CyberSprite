# CyberSprite — Codex 独立実装レビュー R2

- 日付: 2026-11-12 JST。担当: Codex、工学・正確性の独立レビュー。
- 対象: `13b44e5c6eb731ac064bc0bdc1450243dc3e13bf`。開始時の作業ツリーは clean。`dc0fe4f` 以降に実装コードの変更はなく、文書・e2e-07 成果物が追加されている。
- 最初に `docs/REVIEW_REQUEST_2.md` と `docs/FIX_ROUND_1_REPORT.md` を読み、R1 §2 の8件、§3〜6の実質論点、R1の再現コードを照合した。SPEC、判断・進捗・各R1報告、実装・テスト・skills、指定の申し送り2冊、旧DS報告も確認した。
- 実装、仕様、既存テスト、ゴールデンは変更していない。再現には破棄用プロジェクトを使った。追加のスクリプト・生計測・CIログは `_private/review-r2/`、既存測定器の成果物は `build/` に置いた。コミット・pushはしていない。
- 他製品のソース、非公開参照画像、DM生データ、モデルの重みは開いていない。新しい依存は導入していない。外部pixelizerは既存の別環境を利用した。

## 1. 判定

**R1の正本破壊経路は解消した。ただし、書き出しの失敗時復元は全経路へ届いておらず、資源予算にも抜けが残る。修正報告の「Codex fixed 7 / partially 1」は、そのままでは承認しない。**

R1の8件は **解消5 / 部分解消3 / 未解消0 / 悪化0** と判定する。新規・残存指摘は **blocking 0 / major 4 / minor 1**。性能目標の未達だけで停止する判定ではない。大きな配列・再生列の実割当は避け、整数計算または割当前のスパイで境界を検査した。

### 実行した検査

環境はWindows 11 10.0.26200、Python 3.12.10、NumPy 2.3.4、Pillow 13.0.0。既存環境を `--no-sync` で使用した。

| 検査 | R2の結果 |
|---|---|
| `uv run --no-sync pytest -q --tb=short` | **2089 passed / 12 skipped、1021.34秒** |
| `cd gui; npm test` | **698 passed**、contrast **100/100** |
| `cd gui; npm run build` | 成功 |
| `cd gui; npm run test:e2e`（build後、全体pytest終了後） | **5 passed、1.2分** |
| 既存外部pixelizer環境での接続2ファイル | **20 passed、151.90秒** |
| schema drift / grid7ベクタ / check_repository | 全て成功 |
| A1のR1再現測定器 | CLI/MCP/GUI正本保護、locked dry-run、cwd外GUI rootが全て期待どおり |

12 skipはWindowsのsymlink権限5件、主環境に未導入の外部方式6件、明示opt-inのGPU1件。外部6件は別環境の実行結果と分ける。最初のブラウザ試行は全体pytest・外部runtime試験と同時実行し、**2 passed / 3 failed**（1000ms通知制約1件、canvas待ち/timeout2件）だった。上記の追試では同じテストを緩めず全5件成功した。最初の失敗を成功数に混ぜず、通常の再生の契約と負荷下のタイミングの不安定さを分ける。試験中の切断時にASGIのWebSocketDisconnectedログも観測したが、正本破壊や認証回避の再現ではない。

## 2. R1 §2 の8件の再判定

以下のC番号は `CODEX_REVIEW_R1.md` の番号である。Fable側のR1番号とは区別する。

| R1指摘 | 判定 | R2で行った再現・根拠 |
|---|---|---|
| C-R1-01 正本を上書きするexport | **部分解消** | R1そのままのCLI直接名、MCP直接名、GUI `{name}.json` は全て `E_PATH_NOT_ALLOWED`、正本・履歴bytes不変。`tools/r1_a1_acceptance.py` 完走。既存の大小文字・hardlink・source/history・data_out保護試験もある。しかし期待修正に含めた「途中失敗・応答生成失敗で既存出力を復元」は残る（R2-01）。正本破壊blocking自体の再現ではない |
| C-R1-02 復号前のサイズ・累積上限 | **解消** | 8193×1 PNGの元再現を再実行し、`E_LIMIT_EXCEEDED`、`source_width=8193 / 8192`、revision/正本bytes不変。`test_resource_limits.py` はseek/convert前のスパイ、4097f、複数ファイル累積、native入力も検査する |
| C-R1-03 小さいJSONから巨大な仕事量・出力 | **部分解消** | 元の10^9角矩形は仕事量 `2000000000000000000 / 1048576`、4096²×64は `274877906944 / 268435456 bytes` で割当前に拒否。ところが新しい描画maskが取引予算に算入されない（R2-02）。追加の外部方式・GUIにも割当前の防御不足がある（R2-03/04） |
| C-R1-04 履歴全量の二度書換え | **解消** | §4で元の10/1000/10000行Hを再計測。追記・区画化・末尾読取・1000取引索引をコードと試験で確認。耐久復元・roll・再送の試験あり。索引欠損再構築やrollの最悪時間まで証明した判定ではない |
| C-R1-05 拡張点・API・無関係な提供者の読込 | **部分解消** | 自作entry pointで `allowed_read` だけを選択し、loaded/factoryとも `['allowed']`。API999の提供者は `E_PLUGIN`、factory未実行、既存登録不変。CLI/MCP共通登録、exporters/pipeline_steps/generators/validators/palettes/platformsの接続試験あり。importers実行は仕様・既知問題に明記してv1.xへ延期。隠蔽は解消したが当初の全群完成ではない |
| C-R1-06 GUIのroot/allow-dirを形式層が拒否 | **解消** | 元のcwd外TEMPをrootとする `Service(root).run_op('export_image',...)` が成功、`validation_ok / verified=true`。A1測定器でも再現。`server/app.py:111` が実policyを束縛し、実WebSocketの外部allow-dir/拒否試験もある |
| C-R1-07 有限ping-pongの片道repeat | **解消** | 実TS関数を抽出して再評価。0..2、repeat1/2/3はcoreと同じ `[0,1,2]` / `[0,1,2,1,0]` / `[0,1,2,1,0,1,2]`。共有64ベクタと有限停止・末端durationのブラウザ試験がある。大きなrepeatの資源問題は別にR2-04へ記録 |
| C-R1-08 dry-runが配置可能性を検査しない | **解消** | 元のlocked L1へのimportはdry-run・本実行とも `E_LAYER_LOCKED`。A1測定器で再現。`test_r1_a1_dry_run.py` はlayer/group、lock、frame延長、link、配置領域、bytes不変を検査。変換だけの `pipeline_only` を区別した契約も確認 |

主な再現コマンド（root、PowerShell）:

```powershell
uv run --no-sync python tools/r1_a1_acceptance.py
uv run --no-sync pytest -q tests/unit/test_r1_a1_exports.py tests/pipeline/test_r1_a1_dry_run.py tests/unit/test_resource_limits.py tests/test_plugins_r1.py tests/test_platforms.py
```

## 3. 新規・残存指摘

行番号は対象SHAのもの。以下のPythonブロックはPowerShellの `@'` と `'@ | uv run --no-sync python -` の間で実行する。故障注入は破棄用fixtureにだけ適用する。

### R2-01 — major: exportの復元がsurface・形式によって異なり、失敗した要求が既存出力を失わせる

**根拠:** `formats/plugin_export.py:95` は `staged.replace(path)` で直接確定するため、MCPのSaveContextに出力が記録されない。組み込み `export_native` もこの経路を使う。通常のPNGは `formats/common.py:280` の `history.atomic_write` を通り、MCPの応答失敗では復元される。一方CLI/GUI/直接Opの共通export経路（`ops/__init__.py:514`、`cli/__init__.py:458`、`server/app.py:111`）には出力群を包むsave contextがない。`write_verified` は復号失敗時に既存出力も削除する（`common.py:288`）。

**実測:** 同じ応答生成失敗の注入で、MCP `export_image` は旧10bytesを復元、`export_native` は旧10bytesが新64bytesへ置換されたまま、どちらも `E_INTERNAL`。CLIの2フレームPNGは2枚目でI/O故障を注入すると終了4、1枚目だけ上書き済みになる。

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from click.testing import CliRunner
from cybersprite import ops
from cybersprite.cli import cli
from cybersprite.core import history
from cybersprite.core.errors import CyberSpriteError
from cybersprite.mcp.server import MCPService

with TemporaryDirectory(dir=Path.cwd()) as t:
    r = Path(t); p = r / 'p'
    ops.execute('new_project', p, {'platform': 'dmg/sprite-16'}, preview='none')
    ops.execute('rect', p, dict(layer='L1', frame=0, x=0, y=0,
                              w=8, h=8, color=1), preview='none')
    for tool, extra, suffix in [('export_image', {'frames': [0]}, 'png'),
                                ('export_native', {'layer': 'L1'}, '2bpp')]:
        out = r / ('old.' + suffix); out.write_bytes(b'old output')
        svc = MCPService(root=r); pack = svc._pack
        def fail_success(value, root):
            if value['ok']:
                raise CyberSpriteError('E_INTERNAL', 'injected envelope failure', 'test only')
            return pack(value, root)
        with patch.object(svc, '_pack', fail_success):
            v = svc.call(tool, dict(project='p', out=out.name, **extra))
        print(tool, v.structured_content['error']['code'],
              out.read_bytes() == b'old output')  # True / False
    ops.execute('add_frame', p, {}, preview='none')
    outputs = [r / 'frame-0.png', r / 'frame-1.png']
    for f in outputs: f.write_bytes(b'old ' + f.name.encode())
    atomic = history._atomic_write
    def fail_second(path, data):
        if Path(path) == outputs[1]: raise OSError('injected second write failure')
        return atomic(path, data)
    with patch.object(history, '_atomic_write', fail_second):
        v = CliRunner().invoke(cli, ['-p', str(p), 'export', 'image',
                                    '--out', str(r / 'frame-{frame}.png')])
    print(v.exit_code, [f.read_bytes().startswith(b'old ') for f in outputs])
    # 4, [False, True]
```

**期待:** 既存出力を置換する組み込み・plugin/nativeの最終書込を同じ記録境界へ通す。全surfaceで複数出力を一つの復元可能な要求として包む。実ファイル検査と封筒生成が終わるまで旧bytesを保持する。decoder故障、2枚目故障、封筒故障、期限切れを各surfaceで試す。第三者pluginの任意副作用のsandboxを要求するものではなく、本体が行う最終置換の問題。関係: SPEC §6.1、§8.8、§10.1.3、C-R1-01の期待修正。目安1〜2人日。

### R2-02 — major: 描画mask・複合regionの走査が累積仕事量に入らない

`ops/drawing.py:49` の `_work` はset_pixelを常に1と数え、図形もgeometryだけを数える。その後 `:172` でcanvas画像とmaskを作る。`raster.py:453` は各maskの面積を単発検査するだけで、DrawingBudgetへ予約しない。複合regionの各ノードや `only_on/not_on` の走査も累積に入らない。SPEC §5.11「マスク系の描画は走査するキャンバス／タイル面積を予約」と一致しない。

**既定値のまま再現:** 1024²、mask付き17 Opは最低17,825,792画素を走査するが、16,777,216の取引上限を超えて成功、17画素をcommitする。

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from cybersprite import ops
with TemporaryDirectory() as t:
    p = Path(t) / 'p'
    ops.execute('new_project', p, dict(width=1024, height=1024), preview='none')
    calls = [dict(op='set_pixel', args=dict(layer='L1', frame=0, x=i, y=0,
                 color=1, mask={'only_on': [0]})) for i in range(17)]
    v = ops.execute('apply_ops', p, {'ops': calls}, preview='none')
    print(v['ok'], 17 * 1024 * 1024)  # True, 17825792
```

**期待:** geometry・maskの面積・regionのノード別走査・タイル群を事前に保守的に合算し、同じDrawingBudgetへ予約する。予算直下/直上、空mask、複合region、1000 Opで検査し、拒否時の全bytes不変を確かめる。C-R1-03の残存。目安1〜2人日。

### R2-03 — major: 組み込みPixelOE adapterの中間拡大を、小さな入力・引数から巨大化できる

`pipeline/external/pixeloe.py:29–31` はtargetを入力以下、pixel_sizeを16以下と検査するが、その積を検査しない。`:50` はRGBA float tensorを `(target_h*pixel_size, target_w*pixel_size)` へ拡大する。1024²の4MiB入力から、合法なtarget=1024²、pixel_size=16で、**16384²×4×4 = 4,294,967,296bytes**のfloat配列を要求できる。以後の作業配列は別。MCPの協調期限ではこのnative割当を止められない。

これは依存の同梱可否やLevel Aを要求する指摘ではない。利用者が有効にした本体adapterの要求量を、呼出前に制御できない問題である。SPEC §5.11がRSS全体を保証しないことも承知しており、中間tensor用の明示的な予算・上限が必要と判断する。

**安全な再現（実4GiB割当なし）:** tensor操作を無割当スパイに替え、interpolate到達とsizeを確認した。

```python
from contextlib import nullcontext
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
from cybersprite.pipeline.external import pixeloe, _common as common
class Tensor:
    def permute(self, *a): return self
    def unsqueeze(self, *a): return self
    def float(self): return self
    def __truediv__(self, v): return self
class Stop(Exception): pass
def interpolate(tensor, **kw):
    print(kw)  # {'size': (16384, 16384), 'mode': 'nearest'}
    raise Stop()
torch = NS(get_num_threads=lambda: 1,
    are_deterministic_algorithms_enabled=lambda: False,
    is_deterministic_algorithms_warn_only_enabled=lambda: False,
    set_num_threads=lambda v: None, use_deterministic_algorithms=lambda *a, **kw: None,
    random=NS(fork_rng=lambda **kw: nullcontext(),
              default_generator=NS(manual_seed=lambda v: None)),
    no_grad=lambda: nullcontext(), from_numpy=lambda a: Tensor())
def load(name, *a):
    return torch if name == 'torch' else NS(interpolate=interpolate) if name == 'torch.nn.functional' else NS()
with patch.object(common, 'load', load):
    try:
        pixeloe.run(np.zeros((1024, 1024, 4), dtype=np.uint8),
                    dict(target_w=1024, target_h=1024, pixel_size=16))
    except Stop: pass
```

**期待:** float化・拡大前に整数でtensor bytesを計算して拒否する。3方式それぞれのadapterが作る拡大とフレーム群の同時保持を点検し、上限とhintを定義する。runtime未導入の環境でも割当前スパイで回帰検査できる。目安0.5〜1.5人日。

### R2-04 — major: GUIは合法な大きいrepeatを全展開し、再生操作でタブを停止させうる

`gui/src/store/index.ts:15–26` の `playbackFrames` はrepeat回の列を配列へ全展開し、`Timeline.tsx:20` が再生開始時に同期実行する。`Tag.repeat` は65535まで、フレームは4096まで合法。forwardなら **268,431,360要素**になりうる。Python側 `formats/common.py:animation_sequence` に追加した展開前検査がGUI側にない。

**安全な実測:** 実TS関数をtranspileして2フレーム、pingpong/repeat65535を評価すると65,536要素を返す。同じタグのcore exportは展開前に `E_LIMIT_EXCEEDED(output_frames, requested=65536, limit=4096)`。数億要素の実割当・ブラウザ停止は試していない。

```powershell
@'
const fs = require('node:fs'), ts = require('./gui/node_modules/typescript');
const input = fs.readFileSync('gui/src/store/index.ts', 'utf8');
const tree = ts.createSourceFile('index.ts', input, ts.ScriptTarget.Latest, true);
const node = tree.statements.find(s => ts.isFunctionDeclaration(s) && s.name.text === 'playbackFrames');
const js = ts.transpileModule(node.getText(tree).replace('export ', ''), {
  compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS}
}).outputText;
const fn = new Function(js + ';return playbackFrames')();
console.log(fn({from:0,to:1,direction:'pingpong',repeat:65535},2).length); // 65536
'@ | node
```

**期待:** 再生カーソルを片道番号・方向・残り回数で進め、全列を保持しない。あるいは展開前に上限を検査して具体的に拒否する。共有ベクタに大きいrepeatと境界値を追加し、末端duration・有限停止は維持する。関係: §5.11、§14.6、C-R1-03/07。目安1〜2人日。

### R2-05 — minor: `set_frame_ticks` の部分選択が、タグ先頭からの累積位相を失う

`ops/platform_ops.py:152–158` は選択されたフレームだけで累積を0から作る。選択の前や隙間のコマを数えないため、同じtick設定が、全フレーム一括か分割呼出しかで違うdurationになる。§5.13の累積配分規則と異なる。検証側の±1ms許容により、このずれは指摘されない。

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from cybersprite import ops
from cybersprite.core.canonical import load_project
with TemporaryDirectory() as t:
    p = Path(t) / 'p'
    ops.execute('new_project', p, dict(platform='motion', width=1, height=1, frames=6), preview='none')
    print(ops.execute('set_frame_ticks', p, {'ticks': 1}, preview='none')['result'])
    # [41, 42, 42, 41, 42, 42]、合計250ms
    for i in range(6):
        ops.execute('set_frame_ticks', p, dict(frames=[i], ticks=1), preview='none')
    print([f.duration_ms for f in load_project(p).frames])  # [41,41,41,41,41,41]、246ms
    print(ops.execute('validate', p)['result']['metrics']['platform']['tick_deviations']) # 0
```

**期待:** タグ/タグ外区間の位相の規則を実行側と検証側で共通にする。非選択フレームのtick数の復元または明示tick情報の保持を設計し、部分・飛び飛び・重複タグ・分割呼出しのベクタを足す。単に検証の許容を狭める修正では足りない。目安1〜2人日。

## 4. 性能の再実測と公表値の訂正

**訂正のfixture・集計は正しい。一方、最終公表値と同じ速度・目標達成は今回の負荷条件で再現しなかった。** `_private/quiet-bench/b2-final.json` の3生値から全中央値を再計算し、PERFORMANCEと総括の転記が一致することを確認した。今回のB2 JSONの記録する3実装ファイルのhashもquiet測定と一致した。全フレーム同一内容の旧ベンチを代表値から外し、独立した内容のフレームを使う訂正は妥当である。

今回の計測は自己のpytest/外部runtime試験/ブラウザ試験を終えた後、各測定器を順次実行した。OS・常駐アプリ・他のレビュー作業の負荷は固定していない。B2直前の空き物理メモリは **233〜604MiB**で、quiet報告の約1.1GBより少ない。時間差をコード退行と断定せず、quietの達成値を通常負荷での保証にも使わない。BLAS/OpenMP/MKLは1 thread。各3回、単位は以下全てms。

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
uv run --no-sync python -m tools.bench_persistence --out _private/review-r2/history.json --real-edits 0
uv run --no-sync python -m tools.benchmark_r1_b2 --case small_32_3_4 --case ds_96_8_45 --case validate_256_1_32 --case wide_480_270_1_16 --out _private/review-r2/b2.json
uv run --no-sync python _private/review-r2/bench_mcp.py
uv run --no-sync python -m tools.benchmark_r1_large --out _private/review-r2/large.json
uv run --no-sync python -m tools.bench --out _private/review-r2/legacy.json
```

### 4.1 元のH: 10 / 1000 / 10000行

R1 §7 Hそのままの16²・実コミット行の複製。previewなし。後の件数の最初の呼出しは元コードどおりno-opを含む。今回1200連続実編集の再測定は省き、`--real-edits 0` とした。undoの正確性、索引消失時・区画roll時の最悪費用をこの合成fixtureから主張しない。

| 初期行数 | 初期bytes | 3生値 | 中央値 | R1元レビューの中央値 |
|---:|---:|---|---:|---:|
| 10 | 4,391 | 219.423 / 117.299 / 76.563 | 117.299 | 74.668 |
| 1000 | 440,893 | 43.356 / 123.227 / 88.647 | 88.647 | 338.066 |
| 10000 | 4,418,894 | 306.442 / 139.684 / 167.043 | 167.043 | 1985.643 |

履歴全量の読込・二重書換えは除去され、件数が1000倍でも元の秒単位の増加は再現しなかった。元行の成功封筒を除いたためbytesも減っており、単に同じ17MBを高速に書いた測定ではない。修正報告の73.059msという特定観測値そのものは再現しなかった。

### 4.2 独立フレームの代表値

fixtureはB2と同じ8px格子＋フレーム番号マーカー。各セルが独立で内容も異なる。編集は毎回新しいx=1/2/3を異なる番号へ変更し、`no_op=false`を確認、previewなし。読込・正規化・前後報告・履歴・保存込み。coldは各回frame LRU消去、cachedは同じ全報告を再利用可能な状態で計算。`report(p)`の検証自体にはファイル読込を含めず、CLI infoにはプロセスの起動〜終了を含める。

| fixture | 操作 | 3生値 | 中央値 |
|---|---|---|---:|
| 32²・3層・4f | validate cold | 45.317 / 12.246 / 15.028 | 15.028 |
| 同上 | edit | 81.201 / 99.526 / 163.377 | 99.526 |
| 同上 | info要約 | 23.986 / 2.865 / 2.656 | 2.865 |
| 同上 | CLI info | 2127.926 / 1720.392 / 1868.136 | 1868.136 |
| 同上 | validate cached | 3.282 / 2.999 / 2.403 | 2.999 |
| 96²・8層・45f | validate cold | 2802.023 / 2307.101 / 2477.182 | 2477.182 |
| 同上 | edit | 3030.089 / 2382.646 / 3124.044 | 3030.089 |
| 同上 | info要約 | 197.051 / 136.496 / 146.639 | 146.639 |
| 同上 | CLI info | 3367.346 / 4209.535 / 3602.312 | 3602.312 |
| 同上 | validate cached | 590.913 / 603.091 / 819.063 | 603.091 |
| 256²・1層・32f | validate cold | 3734.089 / 3559.807 / 3812.981 | 3734.089 |
| 同上 | edit | 2960.985 / 3048.938 / 2590.518 | 2960.985 |
| 同上 | info要約 | 125.187 / 94.177 / 93.485 | 94.177 |
| 同上 | CLI info | 5210.978 / 3251.112 / 2787.419 | 3251.112 |
| 同上 | validate cached | 344.152 / 875.389 / 664.678 | 664.678 |
| **480×270・1層・16f** | validate cold | 3086.238 / 2338.450 / 2963.918 | 2963.918 |
| 同上 | **edit** | **2303.499 / 1606.347 / 2122.992** | **2122.992** |
| 同上 | info要約 | 185.354 / 105.069 / 76.746 | 105.069 |
| 同上 | CLI info | 2931.319 / 3453.284 / 3447.324 | 3447.324 |
| 同上 | validate cached | 336.831 / 478.095 / 398.281 | 398.281 |

quiet公表値との照合:

| 目標・指標 | 最終公表の中央値 | R2中央値 | 判定 |
|---|---:|---:|---|
| DS edit ≤1000 | 1379.037 | 3030.089 | 両方未達 |
| 256²×32f cold validate ≤2000 | 1174.894 | 3734.089 | 公表観測では達成、今回未達。cachedで代用しない |
| 小規模CLI info ≤1000 | 1539.322 | 1868.136 | 両方未達 |
| 480×270×16f edit（固有目標なし） | 944.071 | 2122.992 | 条件依存。R1前B2の19,186msより短いが、無負荷での倍率保証ではない |

従って公表値を改竄・誤集計とは判定しない。「この修正で256²の検証は常に2秒以内」という受け取り方は支持できない。旧同一内容fixtureの百数十msを代表値にしない訂正は維持すべきである。

### 4.3 MCP: service内と実stdio往復を分ける

まずB1と同じ `MCPService.call` まで（通信なし、SDK初期化除外、32²×10の独立した密フレーム）を測った。

| 経路・操作 | 3生値 | 中央値 |
|---|---|---:|
| 直接 set_pixel | 222.902 / 167.275 / 113.611 | 167.275 |
| service set_pixel | 745.124 / 248.126 / 174.799 | 248.126 |
| 直接 validate | 15.014 / 5.811 / 5.751 | 5.811 |
| service validate | 37.167 / 21.364 / 23.440 | 23.440 |

別に実子プロセス `python -m cybersprite.mcp --root TEMP` を、SDKの `Client(StdioServerParameters(...), mode='2026-07-28')` から呼んだ。fixtureは `tools.benchmark_r1_b2.fixture(w,h,1,frames)`。最初のvalidateを温めてから `await client.call_tool` の要求〜結果受信を計時した。編集引数はL1/frame0/(1,1)、color2/1/2、preview=path、全て実変更。起動・初回検証は測定外。補助スクリプトは `_private/review-r2/bench_mcp.py`、生値は `mcp-stdio.json`。

| 実stdio往復 | 3生値 | 中央値 |
|---|---|---:|
| 32²×10f set_pixel | 463.056 / 154.884 / 164.369 | 164.369 |
| 32²×10f validate | 43.543 / 25.396 / 29.727 | 29.727 |
| 480×270×16f set_pixel | 2154.232 / 1863.831 / 1446.269 | 1863.831 |
| 480×270×16f validate | 601.593 / 415.846 / 349.451 | 415.846 |

service内よりstdioの中央値が短く見えるが、順次の別試行・cache/OS負荷が違うため通信の負の追加費用や改善倍率とは解釈しない。stdio編集は2版の往復で、B2の毎回新規画素・previewなしと同一条件でもない。R1の「MCP往復」と、通信を除いた修正報告のsingle callを分けて記録した。

### 4.4 大キャンバスと旧補助fixture

R1 §7 Lと同じ、新規子プロセスごとのrender→reportを各3回。

| fixture | 操作 | 3生値 | 中央値 |
|---|---|---|---:|
| 1024²・密・1層1f | render | 646.378 / 414.748 / 486.194 | 486.194 |
| 同上 | validate | 932.135 / 716.989 / 1009.341 | 932.135 |
| 4096²・1×1セル1個・1層1f | render | 55.328 / 44.799 / 79.725 | 55.328 |
| 同上 | validate | 1669.077 / 1749.495 / 1282.444 | 1669.077 |

peak working setは1024²で210.74 / 210.77 / 210.61MiB、4096²で321.71 / 248.35 / 328.76MiB。プロセスimportとfixtureも含む。4096²は**疎画像だけ**であり、密・多層・多数フレームへの外挿はしない。256MiB LRUはRSS上限ではないという修正報告の注意は正しい。

R1 §4.1と同じ `tools.bench` の補助値も再実行した。このfixtureの多数フレームは同一内容なので、上の独立フレームの表を置き換えない。

| 項目 | 3生値 | 中央値 | 目標 |
|---|---|---:|---:|
| インストール済CLI --version | 258.458 / 238.411 / 234.591 | 238.411 | 400 |
| 64²・10層・32f edit+preview | 601.027 / 493.605 / 457.854 | 493.605 | 150 |
| 256² render | 23.525 / 20.642 / 18.116 | 20.642 | 50 |
| 同一内容256²×32f validate | 167.516 / 138.998 / 169.731 | 167.516 | 2000 |
| GUI 128² Op＋RGBA往復 | 339.521 / 100.161 / 101.283 | 101.283 | 50 |
| 1024² upscaled変換・段階保存/検査込み | 534.050 / 576.210 / 518.395 | 534.050 | 5000 |

パイプライン5秒以内は同じ工程fixtureで再現。写真・実生成画像・3外部方式の一般速度を示す値ではない。CLI --versionは400ms以内だが実務のinfo起動を代表しない。64²編集/GUIの目標未達も再現した。GUI値はサーバOp＋render RPCであり、ブラウザpointer-upからpaintまでの実測ではない。

## 5. 新規実装の審査

### 5.1 粒度プロファイル・機種仕様

`platform` の解決済みsnapshot、ユーザー/ファイル/plugin/内蔵の優先順、継承・循環拒否、JSON Pointer、整数型、既定値の明示引数優先、旧正本のbytes保持を確認した。R1で提案したschema2ではなくschema1に省略可能な正式フィールドを足す分岐は、SPECとI-1401以降に理由があり、今回これを未解消バグとして再要求しない。検証は登録定義を再読込せずsnapshotだけで動く。

行index・slot0規約、未使用/非表示データ、tile/block/object/layer単位、反転を考慮したtile数は手計算ベクタがある。RGB表現は固定小数点距離、明示的な `conform_palette` だけがパレットを変更する。craftのseverity:errorをinfoに固定し、測定値を美的合格の関門にしない点も確認した。tickの部分選択だけはR2-05。

代表機種の数値はSPECの代表モードの範囲に照合した。DMG/NDS/CGB/NES/SFC/MD/GBAの全モード・VRAM割付・走査線上限を検証しているとは判定しない。NESは利用者RGB表なしで解決を拒否する。今回、実機仕様を外部一次資料から再確定する監査はしていない。

`gb-2bpp` は手計算bitplane、独立decoder、実ディスクbytesとの照合があり、行混在・禁止slot・色表現不能・部分alpha・opacityを `allow_invalid` やseverity無効でも拒否する。追加native形式・palette/map sidecar・offset links・analyzeは明示延期である。nativeの最終保存にはR2-01が残る。

### 5.2 外部pixelizer3種と中立ベンチ

既存 `../CyberSprite-wt/_pixenv` を使い、現HEADのsrcを `PYTHONPATH` で指定して `tests/pipeline/test_external.py tests/pipeline/test_pixelizer_steps.py` を実行、**20 passed、151.90秒**。Fixer、PPA、PixelOEの実runtime経路を含む。本体環境への追加導入は0件。

選択提供者だけのロード、未導入hint、実効版・paramsの来歴、PPAの複数フレーム共通mesh、量子化1回、CPU/stdout境界を確認した。ただし資源境界はR2-03。

`pixelize_bench_r1_d2_results.json` を独立に再集計した結果:

| 方式 | 入力 | 寸法一致 | エラー | 同入力3回の画素一致 |
|---|---:|---:|---:|---:|
| builtin | 323 | 313 | 0 | 323 |
| Fixer Python | 323 | 277 | 0 | 323 |
| proper-pixel-art | 323 | 163 | 3 | 320 |
| PixelOE | 323 | 323 | 0 | 323 |
| Xprite（評価のみ） | 323 | 321 | 0 | 323 |

5方式で `(source, recipe, input_sha256)` の集合が一致した。**PixelOEの323件は全件oracle**。PPAは初期倍率1であり、エラー3件は拒否成功へ数えられていない。画素精度は誤寸法の出力を除外した条件付き指標で、全入力の精度と混同できない。公開値の転記・集計は合っている。

この比較の「中立」は同じ入力・共通の後処理という範囲に留まる。17原画は既存較正用、187/323がnearest系列、PPAは上流既定と違い、PixelOEだけ正解寸法を得る。生成画像に正解寸法はなく、外部の関門は復元後。したがって方式の一般的な順位、写真・実アニメーション・設計三面図での優劣、既定維持の優越性をこの総合率から導けない。報告もその限定を明記しており、PixelOEの100%を検出性能とした誤公表は見つからなかった。AUTOの10/12=83.3%は95%未達のままであり、解消に数えない。

### 5.3 任意重み登録とComfyUI

BYOWはローカルファイル/ディレクトリのhash、base/adapterの条件合成、循環・欠落base拒否、hash変更時の再承諾、未知条件の表示、Q-SRC-04、過去sourceのsnapshotを確認した。`register-model` をMCP Opへ公開せず、設定変更と生成要求を分離している。LoRA/VAE/ControlNetを登録できることは、そのファイル単体でDiffusers生成できる意味ではない。この制限は文書に明記されている。

ComfyUIは登録済みAPI graphのhashに承諾を結び、結線ではなくscalar入力だけをbindし、任意workflow JSON/未登録alias/未知paramsを拒否する。自作HTTPでPOST/poll/view、redirect拒否、応答bytes・時間、画像数/寸法、完成graph保存、再送hash確認が検査される。remote filenameをローカルpathへ使っていない。**実ComfyUIサーバーは今回も未試験**で、実custom node互換性やサーバ上の重みhash/条件を保証する証拠はない。GPUの同seed一致も特定機・特定スタックの記録の範囲で、コアの水準Aへ一般化しない。

### 5.4 Linux CIと決定性

報告のrunをGitHub APIから独立取得した。[Actions run 43196622534](https://github.com/kokuren333/CyberSprite/actions/runs/43196622534) は `dc0fe4f7b76cfa67b4ac440e94f755497c63c0db` に対して全6ジョブsuccess。Linuxの2ジョブログもダウンロードし、checkout SHAと末尾結果を照合した。

| OS / Python | 本体試験 | 独立復号marker |
|---|---|---|
| Ubuntu 26.04 / 3.12（job 131109114147） | 2093 passed / 8 skipped、174.13秒 | 7 passed |
| Ubuntu 26.04 / 3.13（job 131109113986） | 2093 passed / 8 skipped、153.78秒 | 7 passed |
| Windows / 3.12、3.13 | APIで各success。保存済みジョブログにも2094 passed / 7 skipped | CIに同じmarkerの明示実行あり |
| GUI Windows / Ubuntu 24.04 | APIで各success | wheel・独立導入までのステップあり |

対象HEADの [run 43201142512](https://github.com/kokuren333/CyberSprite/actions/runs/43201142512) もcompleted/successを確認した。LinuxのテストをこのWindows端末で実行したという意味ではない。同じ期待ゴールデンを4環境で検査するCIが通っているため、R1の「Linux未検証」は解消。ただし任意の全入力・外部pixelizer・GPU・全OSに対する数学的な決定性の証明ではない。

## 6. R1の実質論点・制作摩擦の照合

| 論点（R1 §3〜6 / 旧DS §6） | R2の判定・残る作業 |
|---|---|
| 整数・決定性・palette閉包・tile反転・link | 手計算/seeded性質/ゴールデン、cached対uncachedの全報告同値を確認。今回見つけたtick問題以外に画素計算の反例は得ていない。全機種・全入力の保証とはしない |
| 正本保護・巨大入力・GUI認証/パス | 正本最終pathとヘッダ拒否は解消。GUIのloopback/token/same-origin、typed path検査、generation opt-inの試験あり。保存と資源の残存はR2-01〜04 |
| linked set_cel / 相対移動 | 既定error＋all/unlink、必須scope付きmove_celが実装され、元の無言の全員移動は解消。R1の「旧意味維持」案との差はFable優先の明示決定。画像だけ共有するoffset linksは別工程のまま |
| セル原点 / strip / frames=all | layersに原点、strip/grid、一貫したフレーム解決は維持。旧報告の不足を再指摘しない |
| 陰影clip / 複合region | mask.only_on/not_on/region、ellipse/polygon、and/or/notが実装。深さ16/256ノード検査と形の固定ベクタあり。ただし累積予算はR2-02 |
| outlineの再適用 | outsideは種除外などの条件下でI。inside一般I化は延期。ランプの全最暗色を除外しないと再適用で広がる摩擦はe2eにも記録済み |
| preview切出し | rect、原座標のgrid/ruler/onion、strip/gridが実装。design guideの縮小・切出しは残り、大原画が予算で拒否される。画像を外部で縮小・再登録する摩擦は解消していない |
| Q-PIXの点差分・帰属 | 完全集合で差を出してから64点へ切り、updated_issuesとcountを返す。64点超・遮蔽・複数寄与の検査あり。帰属nullは複数寄与なら妥当 |
| CLI速度 / 代表性能 | §4。冷起動・履歴・frame再利用・stdio往復を分けた。全目標達成の宣言にはしない |
| undo→再apply差替え | replace-lastは未実装・明示延期。単一トランザクションとして設計するR1案は今も有効、工学2〜3人日程度 |
| 色名・ramps / sym legend | @name、@ramp:k、legendが番号へ厳密解決。閉包と既存paletteを維持する試験あり |
| include / background説明 / 古いskills | 複数include・boolean説明・フレーム指定の記述が更新済み。タグ/スライス表示色がパレット外なのは現仕様どおり |
| 三面図→部品→フレーム→関門 | 5workflow、登録原画、3関門、自己採点しない/pendingの記録を確認。e2e-07の3シートは実在。最終PNG8枚をPillowで独立復号してcoreと全一致、GIF8フレームも全一致、.aseprite往復equivalent=true/dropped=[]。Aのvalidateはerror0/warning73/info9、Bもok |
| 人間の合否・美的品質 | **未了（pending）**。R1より工程が増えたことと、人が採用する品質に達したことを分ける。本レビューは新たなビジュアル採点をしない |
| profile/機種機構の実装可能性 | 基盤は実装済み。残るoffset linksは画像資源と位置インスタンスの分離、schema/正準化/形式/undo/GUI横断が必要でR1の8〜15人日規模を維持。追加nativeは既存exporter拡張点へ載るが、bank/map/VRAM等の明示モデルと独立decoderが必要。形式を足すだけで全機種対応とはしない |

## 7. Fableレビューとの対応と限界

2026-11-12 21:30 JSTの照合時点で、指定の `docs/review/FABLE_REVIEW_R2.md` は存在しない。別担当が作成中の `docs/REVIEW_2.md` はあり、冒頭に未完成と明記され、§1/2/4は未挿入だった。これをFableの確定した全指摘一覧とは扱わない。本書のR2-xxは独立Codexの番号であり、横断台帳ではC-R2-xxとして区別できる。

その下書き§5.1のベンチ解釈とは、nearest系列の比重、較正用原画との重複、PPA倍率1、PixelOE oracle、生成画像に正解がない点で一致する。本書は数値の転記・同じ入力集合・反復一致が正しいことを確認したのであり、比較の一般化を承認していない。「中立」という名称を同じ入力・同じ後処理の統制条件の範囲で認める点と、独立した評価集合として不十分とする点を両立させる。

Fable下書きの制作・新しいワークフロー設計の議論は本書で重複して採点しない。人間の判定pendingを維持する点は一致する。schema1/platform・行index規約・共有位置の既定errorの採用は、R1で提案が異なったが現SPECに従って検査した。今回の工学上の追加は、特にnative/pluginの最終置換とsurface間復元、mask取引予算、拡大tensor、巨大repeat、部分tickの境界である。他方の完成版が後から出た場合、同じ番号だけで同一指摘と判断せず、再現条件を照合すべきである。

このレビューは実ComfyUI、今回のGPU再生成、追加の実機一次資料監査、実アニメーション全方式の新規比較を行っていない。配布依存のLICENSE原文全件を再監査したものでもない。既存のI-010/I-012の事後承認待ち、GUI専用forms・palette・設定、取り込み95%未達、M13延期を、テスト成功で完了へ変更しない。

最終の `git diff --exit-code -- src gui skills tests pyproject.toml uv.lock` は成功した。当方が追加した管理対象の成果物は本書だけである。作業中に出現した未追跡の `docs/REVIEW_2.md` は別担当の下書きで、編集していない。
