# CyberSprite — Codex 独立実装レビュー R2

- 再検証日: **2026-11-13 JST**。対象HEAD: **`d2cf0e856219f4bf8f42ab0a47b916a9960cd841`**。開始時の作業ツリーはclean。
- 依頼どおり最初に `docs/REVIEW_REQUEST_2.md` と `docs/FIX_ROUND_1_REPORT.md` を読み、R1 §2の8件と§3〜6の実質論点を再検証した。SPECの関連節、REQUIREMENTS_NOTES、DECISIONS、進捗・総括の各R1報告への対応表、実装・既存テスト・skills、指定の非公開申し送り2冊と旧DS報告を照合した。
- 指定先には2026-11-12の先行R2（対象`13b44e5`）が既にあった。本書は**今回の実行結果で更新**した。先行R2の実測やAPI取得を今回実施したとは扱わない。先行文書と今回の生計測は `_private/review-r2-20261113/` / `build/review-r2-20261113-*` に保管した。
- 現HEADにはR1後の公開前修正も含む。`docs/PUBLICATION_FIX_REPORT.md` とI-2001〜2004を追加照合した。実装・仕様・既存テスト・ゴールデン・依存・lockは変更していない。当方の管理対象の変更は本書のみ。実行中に別途生じた`CODEX_REVIEW_R1.md`への追記は編集せず保持した。コミット・pushなし。
- 新規依存・外部pixelizer・重みの導入なし。他製品のソース、非公開参照画像、DM生データは開いていない。既存資料の文章・ログ・自作入力だけを使った。

## 1. 判定と検査範囲

**R1の正本破壊blockingは主な経路で解消した。ただし、既存出力の失敗時復元と資源予算に実害のある抜けが残る。** R1の8件は **解消5／部分解消3／未解消0／悪化0**。修正報告の「fixed 7 / partially 1」をそのまま承認しない。

先行Codex R2の5件は今回も全件再現し、番号を維持した（**blocking 0／major 4／minor 1**、§3）。新発見の5件という意味ではない。Fableの既知指摘との対応・判定差は§7。性能の未達だけでblockingにしていない。

環境: Windows 11 10.0.26200、CPython 3.12.10、NumPy 2.3.4、Pillow 13.0.0。既存仮想環境を`--no-sync`で使用。BLAS/OpenMP/MKLは1 thread。巨大割当やブラウザ停止は実行せず、割当前のスパイと要求量の整数計算で検査した。

| 今回実行した検査 | 結果 |
|---|---|
| `uv run --no-sync pytest -q --tb=short` | **2143 passed, 12 skipped in 1131.26s (0:18:51)**。詳細は`build/review-r2-20261113-pytest.log` |
| `cd gui; npm test` | **710 passed、contrast 102/102** |
| schema drift / grid7ベクタ / check_repository | すべて成功 |
| `tools/r1_a1_acceptance.py` | CLI/MCP/GUI最終path保護、locked dry-run、cwd外GUI root、すべて期待どおり |
| 先行R2の故障注入・mask・PixelOE・tick、実TS再生関数 | 5件すべて再現（§3） |
| 性能 | 履歴10/1000/10000行、独立フレーム4fixture、実stdio MCP、1024²密/4096²疎を各3回（§4） |
| e2e-07既存成果物 | 最終PNG8枚/GIF8フレームを独立復号しcoreと全画素一致。A: error0/warning73/info9、B: error0/warning4/info1、両方validate成功。3関門シート実在。見た目の合否はpending |

今回GUI build/Playwright、実外部3方式、GPU再生成、実ComfyUI、Linuxのローカル実行はしていない。先行R2・元実装報告の実行結果と区別する。通常環境の外部方式/GPU skipを「接続未実装」とも「今回の実runtime成功」とも扱わない。

## 2. R1 §2 の8件の再判定

以下のC番号は `CODEX_REVIEW_R1.md` の番号である。Fable側のR1番号とは区別する。

| R1指摘 | 判定 | R2で行った再現・根拠 |
|---|---|---|
| C-R1-01 正本を上書きするexport | **部分解消** | R1そのままのCLI直接名、MCP直接名、GUI `{name}.json` は全て `E_PATH_NOT_ALLOWED`、正本・履歴bytes不変。`tools/r1_a1_acceptance.py` 完走。既存の大小文字・hardlink・source/history・data_out保護試験もある。しかし期待修正に含めた「途中失敗・応答生成失敗で既存出力を復元」は残る（R2-01）。正本破壊blocking自体の再現ではない |
| C-R1-02 復号前のサイズ・累積上限 | **解消** | 8193×1 PNGの元再現を再実行し、`E_LIMIT_EXCEEDED`、`source_width=8193 / 8192`、revision/正本bytes不変。`test_resource_limits.py` はseek/convert前のスパイ、4097f、複数ファイル累積、native入力も検査する |
| C-R1-03 小さいJSONから巨大な仕事量・出力 | **部分解消** | 元の10^9角矩形は仕事量 `2000000000000000000 / 1048576`、4096²×64は `274877906944 / 268435456 bytes` で割当前に拒否。ところが新しい描画maskが取引予算に算入されない（R2-02）。追加の外部方式・GUIにも割当前の防御不足がある（R2-03/04） |
| C-R1-04 履歴全量の二度書換え | **解消** | 今回も§4で元の10/1000/10000行Hを再計測。追記・区画化・末尾読取・1000取引索引をコードと試験で確認。耐久復元・roll・再送の試験あり。索引欠損再構築やrollの最悪時間まで証明した判定ではない |
| C-R1-05 拡張点・API・無関係な提供者の読込 | **部分解消** | 自作entry pointで `allowed_read` だけを選択し、loadedは `['allowed']` で許可Opが登録された。API999の提供者は `E_PLUGIN`、factory未実行、既存登録不変。CLI/MCP共通登録、exporters/pipeline_steps/generators/validators/palettes/platformsの接続試験あり。importers実行は仕様・既知問題に明記してv1.xへ延期。隠蔽は解消したが当初の全群完成ではない |
| C-R1-06 GUIのroot/allow-dirを形式層が拒否 | **解消** | 元のcwd外TEMPをrootとする `Service(root).run_op('export_image',...)` が成功、`validation_ok / verified=true`。A1測定器でも再現。`server/app.py:111` が実policyを束縛し、実WebSocketの外部allow-dir/拒否試験もある |
| C-R1-07 有限ping-pongの片道repeat | **解消** | 実TS関数を抽出して再評価。0..2、repeat1/2/3はcoreと同じ `[0,1,2]` / `[0,1,2,1,0]` / `[0,1,2,1,0,1,2]`。共有64ベクタと有限停止・末端durationのブラウザ試験がある。大きなrepeatの資源問題は別にR2-04へ記録 |
| C-R1-08 dry-runが配置可能性を検査しない | **解消** | 元のlocked L1へのimportはdry-run・本実行とも `E_LAYER_LOCKED`。A1測定器で再現。`test_r1_a1_dry_run.py` はlayer/group、lock、frame延長、link、配置領域、bytes不変を検査。変換だけの `pipeline_only` を区別した契約も確認 |

主な再現コマンド（root、PowerShell）:

```powershell
uv run --no-sync python tools/r1_a1_acceptance.py
uv run --no-sync pytest -q tests/unit/test_r1_a1_exports.py tests/pipeline/test_r1_a1_dry_run.py tests/unit/test_resource_limits.py tests/test_plugins_r1.py tests/test_platforms.py
```


## 3. 新規・残存指摘

行番号は今回の対象SHAのもの。再現コードは今回すべて実行した。以下のPythonブロックはPowerShellの `@'` と `'@ | uv run --no-sync python -` の間で実行する。故障注入は破棄用fixtureにだけ適用する。

### R2-01 — major: exportの復元がsurface・形式によって異なり、失敗した要求が既存出力を失わせる

**根拠:** `formats/plugin_export.py:95` は `staged.replace(path)` で直接確定するため、MCPのSaveContextに出力が記録されない。組み込み `export_native` もこの経路を使う。通常のPNGは `formats/common.py:300` の `history.atomic_write` を通り、MCPの応答失敗では復元される。一方CLI/GUI/直接Opの共通export経路（`ops/__init__.py:535`、`cli/__init__.py:459`、`server/app.py:111`）には出力群を包むsave contextがない。`write_verified` は復号失敗時に既存出力も削除する（`common.py:308`）。

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


## 4. 性能の再実測・公表値の訂正

**訂正の中央値とfixtureの区別は正しい。今回の速度は以下の新しい観測値で判断する。** `_private/quiet-bench/b2-final.json` の全3生値から中央値を再計算し、PERFORMANCE・総括の公表値と一致した。旧ベンチの同一内容フレームを、独立した内容の代表フレームと区別した訂正は妥当である。

性能計測は当方の全体pytest・GUI試験・故障注入終了後、下記の順で直列実行。他アプリ・OS負荷は固定していない。新旧の単一値の差をコードの退行／改善倍率と断定しない。単位ms、各3回。生値JSONには空き物理メモリ・ソースhash等も記録する。

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
uv run --no-sync python -m tools.bench_persistence --real-edits 0 --out build/review-r2-20261113-history.json
uv run --no-sync python -m tools.benchmark_r1_b2 --case small_32_3_4 --case ds_96_8_45 --case validate_256_1_32 --case wide_480_270_1_16 --out build/review-r2-20261113-b2.json
uv run --no-sync python -m tools.benchmark_r1_large --out build/review-r2-20261113-large.json
```

### 4.1 R1と同じ合成ジャーナルH

16²、実コミット由来行を複製し、1px変更、previewなし。1000/10000回の実編集ではない。後の件数で最初の呼出しがno-opになる元fixtureも維持した。1000キー索引初期化済み、roll/索引再構築最悪値を測っていない。1200実編集の別ベンチは今回省略し、元B1の結果を代用していない。

| 初期行数 | bytes | 3生値ms | 中央値ms |
|---:|---:|---|---:|
| 10 | 4391 | 133.865 / 89.251 / 138.516 | 133.865 |
| 1000 | 440893 | 31.654 / 123.766 / 118.319 | 118.319 |
| 10000 | 4418894 | 46.596 / 129.293 / 122.291 | 122.291 |


### 4.2 独立した密フレーム・実務CLI

B2既存測定器を変更せず使用。編集は毎回別座標の実変更でno_op=false、previewなし。coldは各回LRUを消去、cachedは全規則・指標の評価を維持。CLIはインストール済exeの起動〜終了。fixture作成・import・初期履歴作成は測定外。

| fixture | 操作 | 3生値ms | 中央値ms |
|---|---|---|---:|
| small_32_3_4 | validate_cold | 42.450 / 11.412 / 29.891 | 29.891 |
| small_32_3_4 | edit | 126.522 / 199.875 / 186.447 | 186.447 |
| small_32_3_4 | info_summary | 31.698 / 3.213 / 3.666 | 3.666 |
| small_32_3_4 | cli_info | 3349.396 / 1429.206 / 1296.597 | 1429.206 |
| small_32_3_4 | validate_cached | 2.497 / 2.285 / 2.273 | 2.285 |
| ds_96_8_45 | validate_cold | 1874.807 / 1701.263 / 1670.524 | 1701.263 |
| ds_96_8_45 | edit | 2830.110 / 1704.698 / 1960.515 | 1960.515 |
| ds_96_8_45 | info_summary | 87.199 / 82.882 / 78.411 | 82.882 |
| ds_96_8_45 | cli_info | 1423.812 / 1404.710 / 1645.010 | 1423.812 |
| ds_96_8_45 | validate_cached | 361.848 / 307.690 / 455.127 | 361.848 |
| validate_256_1_32 | validate_cold | 2361.019 / 1589.599 / 1665.533 | 1665.533 |
| validate_256_1_32 | edit | 1428.463 / 1219.898 / 1117.142 | 1219.898 |
| validate_256_1_32 | info_summary | 60.653 / 45.383 / 39.979 | 45.383 |
| validate_256_1_32 | cli_info | 1488.975 / 1257.215 / 1439.247 | 1439.247 |
| validate_256_1_32 | validate_cached | 181.703 / 164.693 / 184.027 | 181.703 |
| wide_480_270_1_16 | validate_cold | 1729.940 / 2052.270 / 2101.661 | 2052.270 |
| wide_480_270_1_16 | edit | 1383.231 / 1295.295 / 1470.093 | 1383.231 |
| wide_480_270_1_16 | info_summary | 44.386 / 37.120 / 40.728 | 40.728 |
| wide_480_270_1_16 | cli_info | 1412.021 / 1509.151 / 1247.449 | 1412.021 |
| wide_480_270_1_16 | validate_cached | 168.756 / 179.489 / 232.684 | 179.489 |


静かな再計測の公表値はDS編集1379.037ms、256²×32f cold検証1174.894ms、小規模CLI1539.322ms、480×270×16f編集944.071ms。DS目標1000、256²検証2000、小規模CLI1000との照合では、cached値をcold目標の代わりにしない。

今回のds_96_8_45/editは中央値1960.515ms、目標1000msとの中央値比較は**未達**（3回中3回は目標超過）。

今回のvalidate_256_1_32/validate_coldは中央値1665.533ms、目標2000msとの中央値比較は**達成**（3回中1回は目標超過）。

今回のsmall_32_3_4/cli_infoは中央値1429.206ms、目標1000msとの中央値比較は**未達**（3回中3回は目標超過）。

B2計時直前の空き物理メモリは698〜937MiB。静かな公表測定の約1.1GBと同じ負荷条件ではない。


### 4.3 MCPのservice内呼出しと実stdio往復

前半はB1既存測定器の`MCPService.call`まで。32²×10独立フレーム、引数/path検査・保存・preview=path・SDK封筒化を含み、初期化と通信を除く。

| 経路 | 3生値ms | 中央値ms |
|---|---|---:|
| direct_set_pixel_32_10 | 140.207 / 125.553 / 151.416 | 140.207 |
| mcp_set_pixel_32_10 | 388.416 / 145.565 / 173.933 | 173.933 |
| direct_validate_32_10 | 12.550 / 4.769 / 4.717 | 4.769 |
| mcp_validate_32_10 | 29.501 / 19.384 / 14.553 | 19.384 |


後半は実子プロセス`python -m cybersprite.mcp --root TEMP`とSDK `Client(StdioServerParameters(...), mode='2026-07-28')`の要求送信〜結果受信。B2の`fixture(w,h,1,frames)`、初回validateで温め、L1/frame0/(1,1)の色2/1/2、preview=path、全件no_op=falseをassert。起動・握手・温めは除外。再現補助: `_private/review-r2-20261113/bench_suite.py`（末尾は先行R2の`bench_mcp.py`と同じ条件）、生値`build/review-r2-20261113-mcp-stdio.json`。B2の毎回新座標/previewなしとは条件が違う。

| 実stdio往復 | 操作 | 3生値ms | 中央値ms |
|---|---|---|---:|
| small_32_10 | set_pixel | 365.003 / 172.398 / 144.943 | 172.398 |
| small_32_10 | validate | 28.978 / 21.366 / 14.428 | 21.366 |
| wide_480_270_16 | set_pixel | 1633.188 / 1115.897 / 1101.366 | 1115.897 |
| wide_480_270_16 | validate | 246.133 / 239.263 / 300.961 | 246.133 |


別試行のservice内値とstdio値の差を「通信の純追加費用」にしない。通信を除外した修正報告のsingle callを、MCP往復の公表値へ読み替えることもできない。定義サイズは元測定器と同じ`model_dump(by_alias=True, exclude_none=True)`＋既定`json.dumps`で、現standard **88ツール99,949bytes**、minimal **13ツール16,043bytes**を確認。R1の87ツール98,576bytesからはregister_referenceが増えており、母数を揃えず速度や縮小率へ換算しない。100KB目安の達成はFable R2-03が指摘する引数説明・入れ子の不足を解消しない。

### 4.4 大キャンバス

R1 §7 Lと同じ、新規子プロセスごとのrender→report。1024²は密な単色セル、4096²は1×1セル1個の疎画像。peak working setはimport・fixtureを含む。密な4096²・多層・多数フレームへの外挿はしない。

| fixture | render 3生値ms | validate 3生値ms | peak working set 3値MiB |
|---|---|---|---|
| dense | 416.424 / 347.528 / 320.974 | 524.181 / 562.460 / 585.096 | 210.742 / 210.773 / 210.836 |
| sparse | 36.622 / 34.859 / 30.603 | 770.129 / 652.088 / 581.655 | 328.785 / 328.824 / 328.867 |

256MiB LRU／入出力予算はプロセスのRSS上限ではない。コア品質検証・予算内処理の最悪時間や任意の画像での応答期限をこの測定から保証しない。


## 5. 新規実装の正確性・境界

### 5.1 粒度プロファイル・機種仕様

schema1の省略可能な`platform`と解決済snapshotを採用した分岐を、SPEC §5.13／I-1401以降に照合した。R1のschema2・bank/slot全面モデル案を現契約へ強要しない。定義の優先順位、継承/循環拒否、JSON Pointer、整数、明示引数優先、snapshot独立性、旧正本のbytes保持は`tests/test_platforms.py`、行index/slot0、反転を考慮したtile数、native/rampsは`test_r1_e3*.py`に手計算ベクタがある。

制約検査と明示的な`conform_palette`を分離し、通常編集はpaletteを近似しない。craftは情報であり人間の合否を決めない。`gb-2bpp`の独立decoder・bitplane・実ファイル検査、表現不能色/部分alpha等のallow_invalid非迂回を確認した。tick部分選択の位相はC-R2-05。

内蔵機種は代表モードであり、全VRAM割付・bank/map/走査線・全モードの受入を意味しない。追加native/sidecars/offset links/analyzeは明示延期。今回実機仕様を外部一次資料から再監査したとは扱わない。R1で求めた基盤の実装可能性は実装で確認できたが、全機種対応の完成宣言は支持しない。

### 5.2 3方式と中立ベンチ

Fixer/PPA/PixelOEは本体adapter→許可済entry point→共通StepRunner→1回のpalette lockへ接続されている。PPAはrun_framesとmodal mesh（同点は最初のframe）、PixelOEはCPU/明示target。未導入hint、返却型/フレーム数/寸法/閉包、stdout、選択した提供者だけのload、API不一致時のfactory拒否を既存試験とコードで照合した。外部runtimeの実試験は今回の通常環境ではskipで、元D2の実接続試験を再実行したとは書かない。PixelOE中間tensorはC-R2-03。

保存済JSON全1,615件を独立に再集計した。

| 方式 | 入力 | 寸法一致 | エラー | 成功時3反復hash一致 | 誤寸法でもaccepted |
|---|---:|---:|---:|---:|---:|
| builtin | 323 | 313 | 0 | 323 | 7 |
| Fixer | 323 | 277 | 0 | 323 | 44 |
| PPA | 323 | 163 | 3 | 320 | 144 |
| PixelOE | 323 | 323 | 0 | 323 | 0 |
| Xprite（評価専用） | 323 | 321 | 0 | 323 | 2 |

5方式の`(source,recipe,input_sha256)`集合は一致。PixelOEは全323件oracleで、検出率ではない。PPA初期倍率1、エラー3件を拒否成功に算入していない点も公表と一致する。ただし17原画は較正と共通、187/323はnearest系列、画素指標は寸法一致出力に条件付けられている。この「中立」は同一入力・後処理の統制という範囲であり、一般的な順位や写真/実アニメの優劣は導けない。

**Fable R2-02（major）へ合流:** 自作gradientと偽Fixer adapterでも、`accepted=true / gate_scope=reconstructed-output / input_grid_evaluated=false`、grid_detectedとgrid_score=1000がpassになった。実runtimeの検出精度の再測定ではなく共通関門の境界再現である。入力格子を測っていない事実を文書化するだけでは、passを読む利用者への保証は改善しない。未評価表示または入力純度での関門を要する。既定AUTOの非pixel拒否10/12=83.3%も95%未達のまま。

### 5.3 任意重み登録・ComfyUI

登録メタデータ、ローカルfile/dir hash、base/adapter条件合成、欠落/循環base、内容変更で再承諾、Q-SRC-04、生成物のdesign/import両出口は`test_byow.py`・`test_generation.py`で検査される。登録コマンド/任意workflow/サーバURLをMCPへ公開しない設計を確認した。

**Fable R2-09（major）へ合流:** 登録LoRAを選び、偽factoryでロード直前に止めると、`generate/backends.py:295`以降はkind/baseを使わずLoRAのlocal_pathを`StableDiffusionPipeline.from_single_file`へ渡す。登録baseのpathではない。登録できることと、そのLoRAを選んで生成できることは別で、後者は未完。自己作成のダミーbytesで再現し、実重みは使っていない。baseロード＋選択adapter適用か、未対応kindの早期E_UNSUPPORTEDと具体的hintが必要。再現補助`_private/review-r2-20261113/extra_boundaries.py`。

ComfyUIは登録API graphのhashに承諾を結び、scalar bindのみ許し、未知引数/任意graph/redirect/巨大応答を拒否する。POST/poll/view、枚数/寸法、完成graph保存、再送時hashは自作HTTP試験で検査される。remote filenameをローカルpathにしない。**実ComfyUIは未試験（Fable R2-10、major）**。本レビューでも段階1/2の実サーバ受入を完了にはしない。サーバ上の重み条件やhashは推測しない。期限後jobが残りうる仕様も維持する。

### 5.4 Linux CI

現環境はgit remote/ghなし。今回GitHubのrun URLを再取得できず、直接APIに加え、接続済みGitHubツールのrepository取得とworkflow jobs取得も試したが、APIと接続ツールはいずれも**404 Not Found**だった。先行R2の「APIで独立取得した」という記録を今回の取得成功へ流用しない。

保存済みLinuxジョブログ2本は今回読み、checkoutが`dc0fe4f7b76cfa67b4ac440e94f755497c63c0db`、同じgoldenを含むpytestと独立復号markerが成功していることを確認した。

| 保存ログ | 確認結果 |
|---|---|
| `_private/review-r2/ci-131109114147.log`、Ubuntu/Python3.12 | 2093 passed / 8 skipped、174.13秒。独立復号7 passed |
| `_private/review-r2/ci-131109113986.log`、Ubuntu/Python3.13 | 2093 passed / 8 skipped、153.78秒。独立復号7 passed |

原run: https://github.com/kokuren333/CyberSprite/actions/runs/43196622534 。R1コードでLinux未検証だった論点には解消の証拠がある。一方、公開前修正を含む**現HEADのLinux成功は今回独立確認できていない**。CI設定はWindows/Ubuntu×3.12/3.13とGUI Windows/Ubuntu24.04を維持するが、設定の存在を結果に代用しない。GPU/外部方式の同環境一致をコア水準Aへ一般化しない。

### 5.5 契約・堅牢性

CLI/MCP/projectスキーマは同一レジストリと生成物に照合し、schema driftなし。これは一覧の説明不足や副作用の正しさを保証する検査ではない。保存途中・封筒失敗・再送・revision競合・cached/uncached報告の同値、透明番号・リンク・tile反転・canvas端の既存ベクタを全体試験で再確認した。故障時の形式差はC-R2-01として残る。

GUIのloopback起動/token、Host/Origin、WebSocket認証、path policyとgeneration opt-inはserver試験を含めて検査した。認証回避は今回得ていない。権限不足でskipしたsymlink試験は成功へ数えない。プラグインは信頼したPythonの実行であり、許可した第三者コードの全副作用まで取消すsandboxはない。API/許可提供者の検査とその限界を分ける。MCPの協調期限もnative割当や単一Opの強制停止にはならず、C-R2-02/03の代わりにならない。

## 6. R1の実質論点・制作摩擦の照合

| 論点（R1 §3〜6 / 旧DS §6） | R2の判定・残る作業 |
|---|---|
| 整数・決定性・palette閉包・tile反転・link | 手計算/seeded性質/ゴールデン、cached対uncachedの報告同値を全体試験で再確認。今回再現したtick問題以外に画素計算の反例は得ていない。全機種・全入力の保証とはしない |
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
| 三面図→部品→フレーム→関門 | 5workflow、登録原画、3関門、自己採点しない/pendingの記録を確認。e2e-07の3シートは実在。最終PNG8枚をPillowで独立復号してcoreと全一致、GIF8フレームも全一致（.aseprite往復は先行R2の確認記録）。Aのvalidateはerror0/warning73/info9、Bもok |
| 人間の合否・美的品質 | **未了（pending）**。R1より工程が増えたことと、人が採用する品質に達したことを分ける。本レビューは新たなビジュアル採点をしない |
| profile/機種機構の実装可能性 | 基盤は実装済み。残るoffset linksは画像資源と位置インスタンスの分離、schema/正準化/形式/undo/GUI横断が必要でR1の8〜15人日規模を維持。追加nativeは既存exporter拡張点へ載るが、bank/map/VRAM等の明示モデルと独立decoderが必要。形式を足すだけで全機種対応とはしない |


## 7. Fableとの対応・優先順位・限界

指定の`docs/review/FABLE_REVIEW_R2.md`は存在しないが、**完成済みの`docs/REVIEW_2.md`**がFable 5.2のレビューとして存在するため照合した。先行Codexの番号を維持し、Fable側の同番号と混同しない。

| 本書 | Fable | 判定差／今回の確認 |
|---|---|---|
| C-R2-01 出力失敗時復元 | R2-06 | ともにmajor。native・複数出力の不完全復元を再現 |
| C-R2-02 mask予算 | R2-05 | ともにmajor。17mask Opの超過成功を再現 |
| C-R2-03 PixelOE中間tensor | R2-07 | ともにmajor。割当前スパイで再現 |
| C-R2-04 repeat全展開 | R2-20 | 本書major／Fable minor。合法な小さいmetadataで同期全展開しGUIが停止しうるためmajorを維持 |
| C-R2-05 tick位相 | R2-19 | ともにminor。分割と一括の差・検証見逃しを再現 |
| C-R1-05 plugins | R1-04再判定 | Fable解消、本書部分解消。許可/API/接続の修正には一致。importers延期を元要求の完成へ数えるかという判定基準の差 |
| 外部関門 / LoRA / 実ComfyUI | R2-02/09/10 | §5で既知majorへ合流。先行Codexより、要求の受入不足を明示した。重複の独立新規番号は作らない |
| CLI出力の経路保護 | R2-01 | 後続I-2001で修正済み。PUBLICATION_FIX_REPORT・test_publication_r2_01.pyと全体試験を照合。これを出力復元C-R2-01の修正と取り違えない |

C-R2-01〜03を先に直し、取引・形式・surface横断の失敗時bytes保持と割当前拒否で受け入れる。続いてC-R2-04/05。目安は各指摘の末尾（概算、合計5〜10人日程度）。Fableの機能受入残件は別に見積もる。仕様締め直しが必要な部分をテスト成功だけで済みにしない。

新しい見た目の採点・制作はしていない。e2e-07は機械検査・独立復号・3シート実在を確認した範囲で、**人間の判定pending**。I-010/I-012の事後承認、95%関門、専用GUIフォーム/設定、M13延期、全src型検査残件を解消へ変更しない。実GPU、実ComfyUI、全実機モード、現HEADのLinux CIを今回検証済みとは宣言しない。

参照・来歴: 今回新たな外部実装/アセットを参照せず、ローカルの仕様・実装・報告・ログと自作fixtureで検証した。GitHubへの取得試行は404で内容を得ていない。非公開資料のゲーム名・画像・URL・DM本文は本書へ転載していない。

完了前にHEADが`b7a44f14a6ae112fbd23c5121319f332fd90a331`へ進んだことを検出した。開始時SHAとの差分は`docs/PUBLICATION_AUDIT.md`のみ。`git diff --exit-code d2cf0e8 HEAD -- src gui skills tests pyproject.toml uv.lock`で検査対象の実装・試験・依存が不変であることを確認した。別作業の監査文書コミットとR1追補には変更を加えていない。
