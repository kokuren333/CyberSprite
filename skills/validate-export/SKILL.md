# validate-export — 検証、書き出し、書き出したファイルの確認

## 1. 思想と原則

- きれいなプレビューは、きれいな最終成果を保証しない。確かめるのは、**外へ出したファイルそのもの**である。
- 書き出しは必ず自己検査をする（書いたファイルを復号し直し、レンダラの出力とピクセル単位で照合する）。それでも、自分の目と数で確かめる。
- 警告は消すことが目的ではない。1 件ずつ「直した」か「意図どおりなので残す（理由）」を決めて報告する。

仕様: 完了条件 `docs/SPEC.md` §13.7、規則の一覧 §13.2、検証の設定 §13.3、書き出し §8（再生順 §8.6.1、共通事項 §8.8）。

## 2. 手順

`csp` は `uv run --project <リポジトリ> csp`。MCP ではツール名 = Op 名（`validate`、`export_image`、`export_sheet`、`export_animation`、`export_tileset`、`export_aseprite`、`export_palette`）。

### 2.1 検証を読む

```powershell
csp -p hero.csprite validate                       # 全体
csp -p hero.csprite validate --frames tag:walk     # 範囲を絞る
csp -p hero.csprite validate --strict              # 警告も不合格（終了コード 1）にしたいとき
```

- `result.ok`（エラー 0 件）と `counts` を見る。各 `issues[]` は `rule`、`level`、`message`、`where`（`frames`、`layer`、`points`）を持つ。
- 変更のたびに返る `validation` は**差分**（`new_issues`、`resolved_issues`、`metrics_delta`）。全体は `validate` で取る。
- よく出るもの:

| 規則 | 扱いの目安 |
|---|---|
| `Q-PIX-02`（小さなかたまり、info） | 座標を 1 点ずつ見る。迷子なら直す。目・光沢・1px のアクセントなら残す |
| `Q-PIX-01`（孤立ピクセルが上限超え、warning） | `orphan_pixels_max` を設定したときだけ出る |
| `Q-PAL-02`（未使用の色、info） | 共通パレットなら残してよい。不要なら `remap_palette`（`remove_unused`） |
| `Q-ANI-03`（10 ms の倍数でない表示時間） | GIF で丸められる。意図を確かめる |
| `Q-PIX-03`（セルがキャンバス外） | 取り込みや移動の位置を直す |
| `Q-SRC-01` / `Q-SRC-02`（関門破り / ライセンス不明のソース） | 報告に理由を書く |

- 規則のしきい値や水準は `set_validation` で変えられる（例: `--args '{"settings":{"min_cluster":1}}'`）。変えたら、その理由も報告に書く。

### 2.2 最後に全フレームを見る

最後の変更の**後**に、全フレームのプレビューか差分を見る。

```powershell
csp -p hero.csprite preview --frames all --layout strip --out final-strip.png
csp -p hero.csprite diff --from <書き出し前に確認したリビジョン> --out final-diff     # 前回確認からの変化だけ見るとき
```

### 2.3 書き出す（最後のコミットの後に）

**CLI の書き出し先は、コマンドを実行した場所（cwd）の配下だけ**（外なら `E_PATH_NOT_ALLOWED`）。`-p` はプロジェクトを選ぶだけで、出力の基準は変えない。MCP では `--root` / `--allow-dir` の配下。

```powershell
csp -p hero.csprite export image --out 'export/hero_{frame}.png' --frames all          # 複数フレームは {frame} などで名前を分ける
csp -p hero.csprite export image --out export/hero_x4.png --frames 0 --scale 4
csp -p hero.csprite export sheet --out export/walk.png --data-out export/walk.json --data-format json-hash --tag walk --layout horizontal
csp -p hero.csprite export anim --out export/walk_x4.gif --tag walk --scale 4         # .png なら APNG
csp -p hero.csprite export aseprite --out export/hero.aseprite
csp -p hero.csprite export tileset --tileset TS1 --out export/tiles.png --data-out export/tiles.json
csp -p hero.csprite export palette --out export/hero.gpl
```

- 結果の `validation_ok` と `verified` が **両方 true** であることを確かめる。`files[]` に `path`、`sha256`、`pixel_sha256`、大きさが出る。
- 検証にエラーがあると書き出しは拒否される。`allow_invalid` で押し通すのは、利用者が求めたときだけ。
- 既定の色は `indexed`（インデックス PNG）。RGBA が要るなら `--color-mode rgba`。拡大は整数の `--scale` だけ。

### 2.4 書き出したファイルを確かめる

1. **開いて見る。** PNG はそのまま画像として開く（拡大版があると見やすい）。シートは JSON の `rect` と並びが合っているか。
2. **アニメーションは再生順で見る。** 書き出した GIF / APNG を、作業用の別プロジェクトに取り込み直すと、フレーム列と表示時間を CyberSprite で見られる:
   ```powershell
   csp -p check.csprite import image export/walk_x4.gif --preset upscaled --provenance '{"kind":"imported","provider":"self-export","license":"<作品のライセンス>"}'
   csp -p check.csprite info --include frames                       # 表示時間
   csp -p check.csprite preview --frames all --layout strip --out check-strip.png
   ```
   タグの方向どおりに並んでいるか（例: 0–3 の pingpong は 0,1,2,3,2,1）。確認用のプロジェクトは納品物に含めない。
3. **`.aseprite` は読み戻す。** `csp import aseprite export/hero.aseprite --out check-ase.csprite` で、`dropped` が空、フレーム数・タグ・パレットが一致するか。
4. 数で確かめたいときは、Pillow などで読み取りだけを行う作業用スクリプトを書いてよい（e2e では、×N 版が ×1 の最近傍拡大と一致すること、パレット外の色がないことを照合した）。

### 2.5 完了の報告

`AGENTS.md` §6.3 / SPEC §13.7 の 5 条件を、報告に 1 つずつ書く。

1. `validate` が `ok: true`（リビジョン番号も）。
2. 警告（と気になる info）を 1 件ずつ「直した」か「残す（理由）」。
3. 最後の変更の後に全フレームを見た（何で見たか）。
4. 書き出しは最後のコミットの後で、`validation_ok` と `verified` が true（ファイル一覧）。
5. 書き出したファイルそのものをどう確かめたか。

## 3. 失敗チェックリスト

- [ ] 書き出し先が cwd の外で `E_PATH_NOT_ALLOWED` になっていないか（作業ディレクトリに移ってから実行する）。
- [ ] 複数フレームを 1 つのファイル名に書こうとして「Export filenames collide」になっていないか（`{frame}`、`{frame1}`、`{tag}` などを使う）。
- [ ] 書き出しの後に変更して、書き出しが古くなっていないか（最後のコミットの後に書き出し直す）。
- [ ] `verified` を見ずに終えていないか。
- [ ] プレビューだけを見て、書き出したファイルを開かずに終えていないか。
- [ ] アニメーションを再生順（タグの方向と繰り返し）で確かめたか。
- [ ] 警告を、理由を書かずに残していないか。`set_validation` で規則を黙らせて済ませていないか。
- [ ] 確認用に作ったプロジェクトや一時ファイルを、納品物に混ぜていないか。
