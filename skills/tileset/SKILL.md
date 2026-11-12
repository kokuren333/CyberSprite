# tileset — タイルセットとタイルマップ

## 1. 思想と原則

- どんなタイルを何枚作るかは自由である。この手順書が決めるのは、継ぎ目と使い回しの確かめ方である。
- タイルを 1 枚直すと、そのタイルを置いた全箇所が変わる。これは利点であり、確かめるべき範囲でもある。
- タイル単体のきれいさは、並べたときのきれいさを保証しない。**並べて**見る。

仕様: タイルセット `docs/SPEC.md` §5.8.2、タイルマップセル §5.6.2、描画と反転の順 §6.5.4、タイル Op §10.10、書き出し §8.7。

## 2. 手順

`csp` は `uv run --project <リポジトリ> csp`。MCP ではツール名 = Op 名。

### 2.1 タイルセットとタイルマップレイヤーを作る

```powershell
csp new meadow.csprite --size 192x128 --palette '<自作パレットの JSON 配列>'
csp -p meadow.csprite op add_tileset name=ground tile_w=16 tile_h=16        # → result.id = "TS1"
csp -p meadow.csprite op add_layer name=map type=tilemap tileset=TS1
```

- タイル番号 0 は空タイル（全透明、変更不可）。データ上の番号は 0 始まり。`base_index`（既定 1）は GUI の表示だけに使う。

### 2.2 タイルを描く

```json
{"label":"grass and path edge","ops":[
 {"op":"set_tile_pixels","args":{"tileset":"TS1","tile":"new","format":"sym","rows":["…16 行…"]}},
 {"op":"set_tile_pixels","args":{"tileset":"TS1","tile":"new","format":"sym","rows":["…"]}}]}
```

- `tile: "new"` で末尾に追加（結果の `tile` が番号）。既存の番号を渡すと置き換え。行は常に `tile_h` 行 × `tile_w` 列。
- 縁や角は 1 方向だけ描き、反転フラグで使い回すと枚数が減り、継ぎ目もそろう。

### 2.3 並べる

```powershell
csp -p meadow.csprite apply place.json
```

```json
{"op":"set_tiles","args":{"layer":"map","frame":0,"col":0,"row":0,"rows":[
  "6 6 6 6", "1 1 2 1", "1 3 1 1", "6y 6y 6y 6y"]}}
```

- 1 行は空白区切りのタイル参照。反転フラグは番号の後ろに `x`（左右）、`y`（上下）、`d`（対角 = 転置）。
- 描画では **d → x → y** の順に適用される（§6.5.4）。例えば「上の縁」タイルを右の縁に使うなら `xd`、左なら `d`、下なら `y`（e2e #04 の実績）。
- 1 か所だけ置くなら `set_tile`（`flip` は `x`、`y`、`d` の順で書く）。
- 読み戻しは `csp -p meadow.csprite op get_tiles layer=map frame=0`。
- 注意: 画像の範囲を変形する `transform_region` は **反転 → 回転** の順（§6.4.10）で、タイルの d→x→y とは別物である。取り違えない。

### 2.4 継ぎ目を確かめる

```powershell
csp -p meadow.csprite preview --frame 0 --scale 3 --out map_x3.png
csp -p meadow.csprite preview --frame 0 --grid --scale 4 --out map_grid.png   # 格子つき（絵が白っぽく見えることがある）
```

- 全体と拡大の両方を見る。中央タイルの 2×2、縁の上下・左右のペア、外角と内角の 4 向き、`d` / `xd` の縦の並びを、一時レイヤーや空き地に並べて見ると速い（見終えたら消す）。
- タイルセットそのものを 1 枚で見るプレビューは**未提供**（予定）。当面は `export tileset` で書き出した画像を開いて見る（§2.6）。

### 2.5 タイルを直す

```powershell
csp -p meadow.csprite op set_tile_pixels tileset=TS1 tile=9 format=sym --args '{"rows":[…]}'
csp -p meadow.csprite diff --out diffs       # 置いた全箇所が強調される
```

結果の `changed.frames[].pixels_changed` は「直したピクセル数 × 置いた箇所数」になるはずである（e2e #04 では 11 × 14 = 154）。

### 2.6 描いた絵からタイルを作る（任意）

```powershell
csp -p meadow.csprite op tileset_from_layer layer=ground tile_w=16 tile_h=16 name=ground --args '{"match_flips":{"x":true,"y":true,"d":true}}'
csp -p meadow.csprite info --include layers       # 変換後のセルの x, y を確認
csp -p meadow.csprite op get_tiles layer=ground frame=0
```

- 同じ絵は 1 枚に統合され、`match_flips` を許すと反転した同じ絵も統合される。
- **既知の問題（修正作業中）:** 現状では、レイヤーの上端や左端に透明な行・列があると、詰めた後のセルの位置が格子の原点になり、タイルが 1px などずれる（`info --include layers` でセルの `x`, `y` がタイルの倍数でなくなる）。変換の前にレイヤーの絵がタイル格子の (0, 0) から始まることを確かめ、変換後にセルの位置とプレビューを確かめる。ずれたら `undo` する。
- 不要なタイルは `delete_tiles`（使用中なら `on_used: "clear"` を明示）、並べ替えは `move_tiles`。タイルセットそのものを消す Op は**まだない**（追加予定。現状は `undo` でしか消せない）。

### 2.7 書き出す

```powershell
csp -p meadow.csprite export tileset --tileset TS1 --out export/tiles.png --data-out export/tiles.json
csp -p meadow.csprite export image --out export/meadow_x1.png
csp -p meadow.csprite export aseprite --out export/meadow.aseprite
```

その後は `validate-export` の手順で確かめる。

## 3. 失敗チェックリスト

- [ ] 反転の順を取り違えていないか（タイルは d → x → y、`transform_region` は反転 → 回転）。迷ったら小さなマップに 4 向きを並べて見る。
- [ ] 正方形でないタイルに `d` を付けていないか（転置されず、`Q-TIL-02` が警告する）。
- [ ] タイル 1 枚の修正が、意図した全箇所に波及したか（`pixels_changed` と `diff`）。
- [ ] `tileset_from_layer` の後、セルの位置がずれていないか（上記の既知の問題）。
- [ ] 試しに作ったタイルセットが残っていないか（`.aseprite` にも残る。`info --include tilesets`）。
- [ ] `Q-TIL-01`（未使用・同じ絵のタイル）を読んだか。残すなら理由を報告に書く。
- [ ] 継ぎ目を、拡大と等倍の両方で、並べて見たか。
- [ ] タイルセット JSON の `index` を表示番号（`base_index`）と取り違えていないか。`index` はデータ上の番号（0 始まり、0 は空タイルで既定では書き出されない）で、`base_index` を変えても変わらない。
