# import-convert — 生成画像や既存画像を取り込む

## 1. 思想と原則

- 外から来た画像がキャンバスに入る経路は `import_image` だけである。量子化はこの 1 回だけで、以後は番号で編集する（`AGENTS.md` §3）。
- 原画像と来歴（提供元、プロンプト、ライセンス）は `source/SRC<n>/` に必ず残る。ライセンスが分からなければ `unknown` と書く。空欄にしない。
- パイプラインは決定的である。関門に落ちたら、**段階画像を見て**設定を変え、同じソースでやり直す。関門を黙って無効にしない。
- 関門に通っても、結果が正しいとは限らない。結果の大きさと段階画像を必ず見る。
- このパイプラインは失われた細部を作り出さない。取り込んだ後の手直しは前提である（§11.12）。

仕様: 変換パイプライン `docs/SPEC.md` §11（プリセット §11.10、関門と段階画像 §11.8、配置 §11.11）、来歴 §5.10、生成 §12。生成と来歴の書き方の実例は `docs/GENERATION.md`。

## 2. 手順

`csp` は `uv run --project <リポジトリ> csp`。MCP では `import_image`、`list_sources`、`get_source`。CLI の入出力は cwd 配下、MCP は `--root`（と `--allow-dir`）配下。

設計原画だけの登録は `add_source`（CLI: `source add <画像> --provenance '{"license":"unknown"}'`）。`use: "design"` として保存し、正本・パレットは変えない。`render_preview.guide: {source: "SRC1", mode: "side"}` は登録原画を横に並べる（file は登録パス、x/y は原画の切出し原点、scale 省略時はプレビューと同倍率）。under と GUI 表示は v1.x。

### 2.1 プリセットを選ぶ

| 入力 | プリセット |
|---|---|
| すでに 1 ピクセル = 1 ドットのドット絵 | `exact`（損失なし。色はそのまま） |
| 本物のドット絵を整数倍に拡大したもの | `upscaled` |
| 生成モデルの「ドット絵風」画像 | `ai`（既定） |
| 格子のない絵や写真 | `photo`（`grid.target_w` / `target_h` が必須） |

### 2.2 まず `convert` で試す（プロジェクトは変わらない）

`import_image` は予行（`--dry-run`）を受け付けない。設定を探るときは `convert` を使う。

```powershell
csp pipeline detect-grid in/slime.png                       # 検出した格子（cell_w、offset、columns×rows、候補）
csp convert in/slime.png work/try1.png --preset ai --stages work/stages1
```

結果の `accepted`、`gates`（関門ごとの `value`、`threshold`、`outcome`）、`stage_paths` を読み、段階画像を開く。

| 段階画像 | 見るもの |
|---|---|
| `stage1_grid.png` | 格子線がドットの境目に乗っているか。セルが大きすぎ・小さすぎないか |
| `stage2_downsampled.png` | 縮小後の形。背景が抜けているか |
| `stage3_quantized.png` | 色の割り当て。似た色がつぶれていないか |
| `stage4_cleaned.png` | 後始末で、目やハイライトなど必要な 1px が消えていないか |
| `stage5_final.png` | 最終結果 |

### 2.3 関門に落ちたとき・結果がおかしいとき

`--pipeline '<JSON>'` で設定を上書きする（上書きした項目は報告に残る）。よく効くもの:

| 症状 | 見る段階画像 | 上書きの例 |
|---|---|---|
| 格子の推定違い（結果が 3×3 など極端に小さい・大きい） | stage1 | `{"grid":{"mode":"target","target_w":32,"target_h":32}}` か `{"grid":{"mode":"fixed","cell_w":11,"cell_h":11,"offset_x":0,"offset_y":0}}` |
| 背景が残る | stage2 | `{"background":{"mode":"key","color":[246,244,238],"tolerance":20}}`（色は **RGB の整数配列**）、または `{"background":{"mode":"auto"}}` |
| `orphans` 不合格、ノイズが残る | stage3・4 | `{"palette":{"max_colors":8}}` で色を絞る、`{"downsample":{"method":"mode"}}` |
| 必要な 1px が消える | stage4 | `{"cleanup":{"protect":[<番号>]}}`、または `{"cleanup":{"min_cluster":1}}` |
| 既存プロジェクトに入れたら「No opaque palette color」 | — | 既存プロジェクトでは `palette.mode` が `project`（今のパレットに合わせる）。新しく色を取るなら `{"palette":{"mode":"extract"}}` |

`--dither none|bayer2|bayer4|bayer8` も使える。設定を変えたら、同じ入力で `convert` をやり直し、段階画像を見比べる。

### 2.4 取り込む

先に `new` で、意図した大きさのプロジェクトを作っておく（省くと、最初の取り込み結果の大きさでプロジェクトが作られる。後で別の大きさで入れ直すと、キャンバスからはみ出す）。

```powershell
csp new slime.csprite --size 32x32
csp -p slime.csprite import image in/slime.png --preset ai --pipeline '{"grid":{"mode":"target","target_w":32,"target_h":32},"palette":{"mode":"extract"}}' --target '{"mode":"new_layer","name":"slime","x":0,"y":0}' --provenance '{"kind":"generated","provider":"<道具の名前>","license":"unknown","prompt":"<実際に送った指示>","rights_note":"<分かっている権利の情報>"}'
```

- `provenance.kind` は `imported` か `generated`。`license` は必須。`prompt`、`model`、`seed`、`url` は分かるものだけ。推測で埋めない。
- 不合格でも `ok: true` が返る。**`result.accepted` を見る。** `false` なら何も配置されていない。`report_path` と段階画像を読み、設定を変えて同じソースでやり直す:
  ```powershell
  csp -p slime.csprite import image --source SRC1 --preset ai --pipeline '<変えた設定>'
  ```
- どうしても関門を破って入れるなら `--on-gate-fail accept` を明示する。来歴の `gates_overridden` に残り、`Q-SRC-01` が警告し続ける。報告に理由を書く。
- 複数フレーム: 同じ大きさのファイルを並べる（`files` に配列）、1 枚のシートなら `--sheet-cell 32x32`。全フレームで同じ格子を使う。
- 生成した画像は、その道具から一度ファイルに保存してから渡す。CyberSprite 内蔵の生成（`gen run`）は `docs/GENERATION.md`。

### 2.5 取り込んだ後

```powershell
csp -p slime.csprite source list
csp -p slime.csprite source show SRC1 --include-report
csp -p slime.csprite info --include summary,layers
csp -p slime.csprite preview --frames all --layout strip --out after-import.png
```

- 結果の大きさ（`gates` の `size`）、配置先のレイヤーとフレーム（`placed`）、セルの位置を確かめる。`fits_canvas` が `warn` ならはみ出している。
- 形の崩れ、フレーム間の揺れは、`draw-sprite` と `animate` の手順で番号を使って直す。
- 最後は `validate-export`。`Q-SRC-02`（ライセンス `unknown` のソースを配置）は警告として残る。報告に理由を書く。

## 3. 失敗チェックリスト

- [ ] 外部の画像を、パイプラインを通さずにピクセル列へ書き写していないか（経路は `import_image` だけ）。
- [ ] 来歴のライセンス欄を空にしていないか（分からなければ `unknown`）。プロンプトは実際に送ったものか。
- [ ] `ok: true` だけを見て、`accepted` を見落としていないか。
- [ ] 関門に通ったからといって、段階画像と結果の大きさを見ずに進めていないか（格子を 49px と誤検出して 3×3 で「合格」した例がある）。
- [ ] 関門に落ちたとき、段階画像を見ずに `on_gate_fail: accept` にしていないか。
- [ ] `background.color` を `#rrggbb` の文字列で渡して `Background key needs RGB or RGBA color.` になっていないか（`[r,g,b]` で渡す）。
- [ ] 試しの `import_image` を繰り返してソースとレイヤーを増やしていないか。設定探しは `convert` で行う。
- [ ] 取り込み先のキャンバスの大きさは意図どおりか（先に `new`）。
- [ ] 取り込んだアニメーションを、フレームを並べて見比べ、直したか。
