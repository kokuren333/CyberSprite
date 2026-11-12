# animate — フレーム、リンクセル、タグ、表示時間

## 1. 思想と原則

- 動きの設計（何フレームで、どう動かすか）は自由である。この手順書が決めるのは、動きの確かめ方である。
- 1 枚ずつのきれいさは、動きの正しさを保証しない。**並べて見る、重ねて見る、再生順で見る**の 3 つで確かめる。
- 変わらない部分はリンクセルで共有すると、直すときに 1 か所で済む。そのかわり、リンクセルを編集すると共有している全フレームが変わる。編集の前に影響範囲を確かめる。

仕様: フレームとセル `docs/SPEC.md` §5.4・§5.6（リンクセル §5.6.3）、タグ §5.7、プレビューとオニオンスキン §6.7.1、再生順と GIF §8.6。

## 2. 手順

`csp` は `uv run --project <リポジトリ> csp`。MCP ではツール名 = Op 名。フレーム番号は 0 始まり。

### 2.1 フレームを足す

```powershell
csp -p hero.csprite op add_frame count=3 cels=copy copy_from=0     # 独立した複製
csp -p hero.csprite op add_frame count=3 cels=link copy_from=0     # 全レイヤーをリンク
csp -p hero.csprite op add_frame count=1 cels=empty at=2           # 位置を指定して空のフレーム
```

`add_frame` の `cels` はプロジェクト全体に効く。レイヤーごとに分けたいときは、足した後で `link_cel` / `unlink_cel` を使う。

```powershell
csp -p hero.csprite op link_cel layer=shadow source_frame=0 frames=1-7     # 影は全フレームで共有
csp -p hero.csprite op unlink_cel layer=details frame=1                    # このフレームだけ描き変える
csp -p hero.csprite info --include layers                                  # 各レイヤーの link_groups を見る
```

フレーム指定は、整数、配列、`all`、範囲 `0-3`、`tag:<名前>` を受ける（Op の説明に「Frame selection」とあるもの）。`csp op … キー=値` で一覧を渡すときは `'frames=[2,6]'` と JSON 配列で書く（`frames=2,6` は `E_INVALID_ARGS`）。

### 2.2 リンクセルを編集する前に予行する

```powershell
csp -p hero.csprite op set_pixel layer=body frame=2 x=7 y=7 color=5 --dry-run
```

結果の `changed.linked_frames`（と `link_groups`）に、一緒に変わるフレームが出る。意図しないフレームが入っていたら、先に `unlink_cel` する。MCP では引数に `"dry_run": true`。

### 2.3 各フレームを描き分ける

- フレーム間で部分を動かすには `transform_region`（`dx`、`dy`、`target_frame` で別フレームへ写す、`action: "copy"`）。
- 関節の座標から手足を毎フレーム描くような作業は、Op の引数 JSON をスクリプトで作って `apply` に渡してよい（ピクセルを書くのは CyberSprite の Op だけ）。
- 1 回のトランザクションに複数フレームの変更を入れてよいが、意図は 1 つにする（例: 「左脚の歩幅を直す」）。

### 2.4 動きを確かめる（変更のたび）

```powershell
csp -p hero.csprite preview --frames tag:walk --layout strip --out walk-strip.png      # 番号つき横並び
csp -p hero.csprite preview --frames all --layout grid --out all-grid.png              # 多いフレームは一覧で
csp -p hero.csprite preview --frames tag:walk --onion '{"prev":1,"next":1,"loop_tag":"walk"}' --background '#ffffff' --out onion
```

- `layout: frames`（既定）は個別画像で 8 枚まで。それより多いときは `strip` か `grid`。
- オニオンスキンは前が赤系、後ろが青系。市松模様の上では見にくいので、`--background` に明るい単色を指定するとよい（パレット外の色でもよい。書き出しには入らない）。`loop_tag` を付けると、タグの端で前後が循環する（最初のフレームの前 = 最後のフレーム）。
- 見るもの: 接地している足が滑っていないか、上下動の幅、輪郭の太さの揺れ、色の取り違え。

MCP: `{"name":"render_preview","arguments":{"project":"hero.csprite","frames":"tag:walk","layout":"strip"}}`（画像が返る）。

### 2.5 表示時間とタグ

```powershell
csp -p hero.csprite op set_frame_duration frames=0-7 duration_ms=100
csp -p hero.csprite op set_frame_duration 'frames=[2,6]' duration_ms=120     # op の キー=値 では一覧は JSON 配列で書く
csp -p hero.csprite op add_tag name=walk from=0 to=7                        # 既定 forward、repeat 0
csp -p hero.csprite op add_tag name=idle from=8 to=9 direction=pingpong
csp -p hero.csprite op update_tag --args '{"tag":"idle","direction":"forward"}'   # 契約は ops describe update_tag
```

- 表示時間は整数ミリ秒。GIF は 10 ms 単位に丸められる（`Q-ANI-03` が知らせる）。
- `pingpong` は折り返し点を重ねない。`repeat 0` の `pingpong` は 1 往復で、ループ時に先頭と同じ末尾の 1 枚は落ちる（§8.6.1）。例: 8–9 の pingpong は GIF では [8, 9]。

### 2.6 再生順で確かめる

書き出した GIF / APNG を、タグの方向と繰り返しどおりの順で確かめる。手順は `validate-export` の §2.4。

## 3. 失敗チェックリスト

- [ ] リンクセルを編集する前に `--dry-run` で `linked_frames` を見たか。編集後も結果の `linked_frames` を読んだか。
- [ ] `add_frame cels=link` の後、描き分けたいレイヤーを `unlink_cel` し忘れていないか（全フレームが一緒に変わる）。
- [ ] フレーム番号を 1 始まりで数えていないか。タグの `from` / `to` は両端を含む。
- [ ] 1 枚ずつのプレビューだけで済ませていないか。横並びとオニオンスキンで、隣のフレームとの差を見たか。
- [ ] 手前と奥の手足で、付け根（腰・肩）の位置が 1px ずれていないか。歩幅が左右でそろっているか。
- [ ] 外接矩形の揺れが気になるなら、`set_validation` で `silhouette_jitter_max` を設定して `Q-ANI-04` に見張らせる。
- [ ] タグの色を指定するときは `#rrggbb`（パレット外でよい。表示用）。
- [ ] 最後の変更の後に、全フレームを見たか（`AGENTS.md` §6.3）。
- [ ] 書き出したアニメーションを、再生順で確かめたか。
