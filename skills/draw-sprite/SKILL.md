# draw-sprite — 新しいスプライトを描く

## 1. 思想と原則

- 何をどう描くかは自由である。この手順書が決めるのは、確かめ方と記録の仕方だけ。
- ピクセルはパレット番号でしか存在しない。色は**先に**パレットに置き、描くときは番号で指す（`AGENTS.md` §3）。編集で色を近似する経路はない。
- 1 つの意図ごとに 1 トランザクション。結果の検証デルタを読み、プレビューを見てから次へ進む。
- 方向性（作風、色調、頭身など）が決まっていなければ、3 案ほどを小さく作って利用者に選んでもらう。問い返せない自律タスクでは 1 つを選んで進め、選んだものとほかの案を報告に書く（`skills/README.md`）。

工程（段、担当、人間が見る関門）は `skills/workflows/` にある。大きさで選ぶ: 48 px 以上の 1 体は `turnaround-parts`、32 px 以下は `direct`、極小で制約の厳しいものは `silhouette-first`（`skills/README.md`）。この手順書は、その中で使う道具の手順である。

仕様: キャンバスとパレット `docs/SPEC.md` §5.3、描画アルゴリズム §6.4、トランザクション §6.2、プレビュー §6.7。

## 2. 手順

以下 `csp` は `uv run --project <リポジトリ> csp`。MCP ではツール名 = Op 名で、引数は同じ（`project` を足す）。

### 2.1 パレットを決める

```powershell
csp palette presets                                   # 同梱: cs-circuit-16 / cs-circuit-32 / bw-1bit / gray-4 / gray-8
csp new hero.csprite --size 32x32                     # 既定は cs-circuit-16（透明 0 番 + 16 色 = 17 項目）
csp new hero.csprite --size 32x32 --palette cs-circuit-32
csp new hero.csprite --size 32x32 --palette '["#00000000","#1a1c2cff","#5d275dff","#ffcd75ff"]'   # 自作（番号 0 が透明）
csp -p hero.csprite palette show
```

- 途中で色を足すときは `add_palette_colors`（結果の `indices` が新しい番号）。1 色を変えるなら `set_palette_color`。
  `csp -p hero.csprite op add_palette_colors 'colors=["#38b764ff"]'`
- 名前付きの色（`palette show` の `name`）は、後で番号を思い出すのに役立つ。

### 2.2 レイヤーを組む（必要なら）

```powershell
csp -p hero.csprite op add_layer name=body
csp -p hero.csprite op add_layer name=shadow position=bottom
csp -p hero.csprite op update_layer layer=L1 name=body          # 改名（表示・ロック・順序なども update_layer）
csp -p hero.csprite info --include layers
```

レイヤーは ID（`L1` …）、一意な名前、グループのパスのどれでも指せる。最初のレイヤーは `L1`（名前 `Layer 1`）。

### 2.3 描く

よく使う Op（契約は `csp ops describe <名前>`）:

| 目的 | Op |
|---|---|
| 格子をそのまま流し込む | `draw_rows`（`format: "sym"` で `.` = 透明、`0-9` / `a-z` / `A-Z` = 0–9 / 10–35 / 36–61 番。62 色まで。既定の `format` は `hex`（1 番号 = 16 進 2 桁）） |
| 図形 | `rect`（`filled`）、`ellipse`、`line`、`polygon`、`stroke`（点列をブラシでつなぐ）、`fill` |
| 輪郭 | `outline`（`placement: outside/inside`、`connectivity: 4/8`、`exclude_colors` で種色を除外。outside で輪郭色を除くと再適用は no_op） |
| 消す・動かす | `erase`、`clear_cel`、`transform_region`（例は `animate` §2.3） |
| 色の置き換え | `replace_color` |

色引数は `"@<palette.names の名前>"` も受ける。`draw_rows` の sym は `legend: {"b":"@body.base"}` のような文字対応表を指定できる（`.` は透明、legend 使用時は62色制限なし）。描画 Op の `mask: {only_on: [色], not_on: [色], region: 領域}` は描画前の対象セルで一度だけ判定する。プレビューは `--rect x,y,w,h` で部分を原座標のまま切り出せる。

```powershell
csp -p hero.csprite apply body.json                   # {"label":"…","ops":[{"op":…,"args":{…}}, …]}
csp -p hero.csprite op rect layer=body frame=0 x=4 y=4 w=8 h=8 color=7 filled=true --label "torso"
csp -p hero.csprite op stroke layer=body frame=0 color=1 --args '{"points":[[2,10],[8,14]],"brush":{"size":1,"shape":"square"}}'
```

- `draw_rows` の `.`（透明）は、既定で**既存のピクセルを透明で上書きする**（矩形全体を書き換える）。重ね描きで下のピクセルを残したいときは `"skip_transparent": true`。矩形の外は変わらないので、前の絵が矩形からはみ出していたら、その分は `erase` か `clear_cel` で消す。
- 配列やオブジェクトを含む引数は `--args '<JSON>'` か `--args-file`。`apply -` は標準入力から読む。
- `label` を付けると履歴（`csp history`）が読みやすい。
- やり直しは `csp undo`（`--steps n`）。undo も新しいリビジョンとして積まれる。

### 2.4 結果を読み、見る（毎回）

1. 封筒の `validation.new_issues` を読む。`Q-PIX-02` などは座標（`where.points`）つきで出る。
2. `changed.frames` の `pixels_changed` と `bbox` が意図と合っているか。
3. プレビューを開いて見る。封筒の `preview.paths`、または明示的に:
   ```powershell
   csp -p hero.csprite preview --frame 0 --grid --rulers --out check.png     # 座標を合わせたいとき
   csp -p hero.csprite preview --frame 0 --background '#ffffff' --out onwhite.png
   csp -p hero.csprite diff --out diffs                                       # 直前のリビジョンとの差（変化はマゼンタ）
   ```
4. 数で確かめたいときは `csp -p hero.csprite pixels --layer body --frame 0 --rect 0,0,32,32 --as sym`（`--rect` を省くと透明な外周を除いた範囲になる）。

### 2.5 仕上げ

`validate` で全体を見て、`validate-export` の手順で書き出して確かめる。

## 3. 失敗チェックリスト

- [ ] 色を `#rrggbb` で指定して `E_COLOR_NOT_IN_PALETTE` になっていないか。エラーの `details.nearest` は候補にすぎない。番号で指すか、`add_palette_colors` で足してから使う。
- [ ] `draw_rows` の行の長さがそろっているか（矩形でないと拒否される）。`sym` の番号は 0–9、a–z（10–35）、A–Z（36–61）。`format: "sym"` を書き忘れていないか（既定は `hex`）。
- [ ] 重ね描きのつもりの `draw_rows` で、`.` の部分が下の絵を消していないか（`skip_transparent` を付けたか）。
- [ ] フレーム番号を 1 始まりで数えていないか（0 始まり）。
- [ ] 下のレイヤーの色と同化して消えた部分はないか（例: 頬紅が髪と同じ明るさで見えない）。合成のプレビューで確かめる。
- [ ] `Q-PIX-02`（小さなかたまり）を、座標を見ずに一括で消していないか。目のハイライトや 1px のアクセントは正しい表現でありうる。1 点ずつ見て、迷子のピクセルだけ直す。UI アイコンのように 1px が普通の題材では、`set_validation` で `min_cluster` を下げてもよい（`--args '{"settings":{"min_cluster":1}}'`）。
- [ ] `Q-PAL-02`（未使用の色）は、共通パレットなら意図どおりとして残してよい。報告に理由を書く。
- [ ] 描画の後、プレビューを開かずに次の変更へ進んでいないか。
- [ ] `pixels --layer` の結果を全面だと思い込んでいないか（既定は切り詰めたセルの矩形）。
- [ ] 外部の画像をピクセル列に書き写していないか。外から来た絵は `import-convert` の経路で入れる。
- [ ] 48 px 以上の題材を、原画なしで、楕円の積み重ねで作っていないか（`skills/workflows/turnaround-parts.md` §5）。
