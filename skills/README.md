# skills/

エージェント（Claude Code、Codex）向けの、CyberSprite で絵を作るための手順書である。
最初に `AGENTS.md`（とくに §2 思想、§6 制作）を読み、次にこのページの「どの手順で作るか」で標準ワークフローを選び、クイックスタート、作業に合った手順書の順に読む。

## どの手順で作るか（標準ワークフロー）

題材の大きさとプラットフォームで、`skills/workflows/` の 1 冊を選ぶ。プラットフォームに `workflow` があれば、それに従う（`get_info` の `include: ["platform"]`、M11 で追加）。無ければ下の表で選ぶ。

| 題材 | 手順書 |
|---|---|
| 1 体のキャラクターで 48 px 以上（DS 級の 80×80 / 96×96、モダンな立ち絵） | [`workflows/turnaround-parts.md`](workflows/turnaround-parts.md)（三面図 → 部品） |
| 16×16 以下で色数がごく少ない（実機の制約に合わせた 3 色など） | [`workflows/silhouette-first.md`](workflows/silhouette-first.md) |
| 32 px 以下のキャラクター、UI アイコン、小物 | [`workflows/direct.md`](workflows/direct.md) |
| タイルセット、タイルマップ、タイルで組む背景 | [`workflows/tiles-first.md`](workflows/tiles-first.md) |
| 画面と同じ大きさの背景や一枚絵 | [`workflows/scene.md`](workflows/scene.md) |
| 既存のスプライトを参照して測る | [`workflows/references.md`](workflows/references.md)（どの手順の段 0 からも） |

- **分担**: 原案の生成（三面図など）は Codex の imagegen、原画の解釈・ドットを打つこと・見た目の判断は Opus（`docs/SPEC.md` §16.2）。Codex の呼び出し方は `workflows/turnaround-parts.md` §3.2。
- **人間が見る関門が 3 つある**（設計 / ブロッキング / 仕上げ前）。機械の検査が全部通っても「できた」とは言わない。見た目の判定は人間が決めるまで `pending`（`AGENTS.md` §6.3、`docs/SPEC.md` §13.7）。
- 制作テストや自律タスクの記録は [`templates/review-record.md`](templates/review-record.md) の形で残す。

## 手順書の一覧

| 手順書 | 使う場面 |
|---|---|
| [`draw-sprite/`](draw-sprite/SKILL.md) | 新しいスプライトを描く。パレットを決める、シルエットから描く、プレビューで直す、検証する |
| [`animate/`](animate/SKILL.md) | フレームを足す、リンクセル、タグ、オニオンスキンと横並びで動きを確かめる、表示時間 |
| [`tileset/`](tileset/SKILL.md) | タイルセットとタイルマップ。反転の使い回し、継ぎ目の確認、既存の絵からのタイル化と重複の統合 |
| [`import-convert/`](import-convert/SKILL.md) | 生成画像や既存画像を取り込む。プリセット、段階画像、関門に落ちたとき、来歴 |
| [`validate-export/`](validate-export/SKILL.md) | 検証の読み方、警告の扱い、書き出しと自己検査、書き出したファイルの確かめ方、レビューシート、完了条件と報告の規則 |

上の 5 冊は道具の使い方、`workflows/` の手順書は工程（段、担当、関門）である。工程の中から道具の手順書を引く。

## クイックスタート（新しいセッションの最小ループ）

16×16 のキャラクターを描き、4 フレームの歩行にして、シートと GIF を書き出すまで（`docs/SPEC.md` §13.6 のシナリオ 1）。各段の詳しい話は上の手順書にある。

### 0. 道具をつなぐ

どちらか一方でよい。両方とも同じ Op レジストリを通るので、結果は同じである。

- **MCP**: ツール名は Op 名そのもの（`new_project`、`apply_ops`、`render_preview`、`export_sheet` …）。登録の方法は `docs/MCP.md`。相対パスはサーバの `--root` が基準。
- **CLI**: リポジトリの中なら `uv run csp …`。外からは `uv run --project <リポジトリ> csp …`。出力は封筒形式の JSON 1 個。
  - `csp` と `cybersprite` は同じコマンドの別名。タスク文がどちらかを指定していれば、それに合わせる。
  - `--no-sync`（`uv run --project <リポジトリ> --no-sync csp …`）は、環境の同期を省く。環境がすでにできていれば付けても付けなくても結果は同じで、付けると速く、並行実行での衝突もない。環境がまだなければ、先に 1 回 `uv sync` する。

迷ったら、契約は道具そのものに聞く: `csp ops list`、`csp ops describe <Op 名>`、`csp <コマンド> --help`。

**CLI の書き出し先は、コマンドを実行した場所（cwd）の配下だけ。** 作業用ディレクトリに `cd` してから始めるのが楽である。

**プロジェクト（`hero.csprite`）はディレクトリである。** 中身は正本の `project.json`、派生物の `.cybersprite/`（プレビュー `previews/` など）、取り込んだ原画像と来歴の `source/`。`-p` にはこのディレクトリ（か `project.json`）を渡す。手で書き換えず、変更は必ず Op で行う。

### 1. 作る → 描く

```powershell
cd C:/work/hero                                   # 書き出しもこの下に出す
uv run --project <repo> csp new hero.csprite --size 16x16      # 既定パレット cs-circuit-16
uv run --project <repo> csp -p hero.csprite palette show       # 番号と色名を見る
```

既定パレット `cs-circuit-16` は、透明（0 番）＋ 16 色 = **17 項目**（1–16 番が色）。番号は必ず `palette show`（MCP は `get_palette`）で確かめる。

描画は 1 つの意図ごとに 1 トランザクション（`apply`）。`draw_rows` の `sym` 形式を使うと、格子をそのまま流し込める。1 文字 = 1 番号で、`.` = 透明、`0–9` = 0–9 番、`a–z` = 10–35 番、`A–Z` = 36–61 番（既定パレットの 10–16 番は `a`–`g`）。`.` は既定で**透明で上書きする**。既存のピクセルを残したいところは `"skip_transparent": true` を付ける。

```json
{"label":"body base","ops":[
 {"op":"draw_rows","args":{"layer":"L1","frame":0,"x":5,"y":2,"format":"sym","rows":[
  "..111.", ".17771", ".17171", "..111."]}}]}
```

```powershell
uv run --project <repo> csp -p hero.csprite apply body.json
```

MCP では `{"name":"apply_ops","arguments":{"project":"hero.csprite","label":"body base","ops":[…]}}`。

### 2. 結果を読む → 見る

- 返ってきた封筒の `validation`（検証デルタ）と `changed` を読む。`new_issues` に座標が出る。
- プレビューを**開いて見る**: 封筒の `preview.paths`（CLI はプロジェクト内の `.cybersprite/previews/`）、または `csp -p hero.csprite preview --frame 0 --grid --out p0.png`。MCP では `render_preview`（画像が返る）。

### 3. 動かす

```powershell
uv run --project <repo> csp -p hero.csprite op add_frame count=3 cels=copy copy_from=0
# 各フレームを描き分ける（apply）。詳しくは animate
uv run --project <repo> csp -p hero.csprite op add_tag name=walk from=0 to=3
uv run --project <repo> csp -p hero.csprite preview --frames tag:walk --layout strip --out walk-strip.png
```

### 4. 検証 → 書き出し → 書き出したファイルを確かめる

```powershell
uv run --project <repo> csp -p hero.csprite validate
uv run --project <repo> csp -p hero.csprite export sheet --out export/walk.png --data-out export/walk.json --tag walk --layout horizontal
uv run --project <repo> csp -p hero.csprite export anim --out export/walk_x4.gif --tag walk --scale 4
```

- `validate` は `ok: true`。警告は 1 件ずつ「直した」か「意図どおり（理由）」を報告に書く。
- 書き出しの結果は `validation_ok: true` と `verified: true`。
- `--data-format` を省くとシートの JSON は独自形式（`cybersprite`）になる。ゲームエンジンなどの既存の読み込み機能に渡すなら `json-hash` か `json-array`。違いは `validate-export` の §2.3。
- 書き出した PNG を開いて見る。GIF は取り込み直して再生順を見る（`validate-export` の §2.4）。

ここまでやって、`AGENTS.md` §6.3 の機械の検査がそろう。残りは人間が見る関門である。このクイックスタートは `direct` の手順にあたる。レビューシート（`validate-export` §2.5）を出し、見た目の判定は `pending` のまま報告する。

## 方向性を決める場面

新しいアセットの作風、色調、構図など方向性の判断が要るときは、3 案ほどを小さく作って（小さなキャンバスや 1 フレームで十分）、プレビューを順位を付けずに並べて利用者に選んでもらう（推す案があれば理由は 1 行まで）。決まった後の細部は自分で決めて進める。

**利用者に問い返せない自律タスク**（題材だけが指定されている、途中で質問できない、など）では、待たずに 1 つの方向を選んで最後まで進める。最終報告に、選んだ方向と、考えたほかの案を 1〜2 行ずつ書く（利用者が後から選び直せるように）。

## 書き方の規則（手順書を足す・直すとき）

道具の手順書は `skills/<名前>/SKILL.md`、工程の手順書は `skills/workflows/<workflow の値>.md` に、次の 3 部構成で書く（工程の手順書は、2 の前に段・担当・関門の表を置く）。

1. **思想と原則** — なぜそうするのか。数行。
2. **手順** — 使うツールと順序。具体的な呼び出し例を付ける。例は実際のツールで動かして確かめてから書く。
3. **失敗チェックリスト** — 実際に起きた失敗から足していく。

**ハーネスは、あえて緩くする。** 手順書が定めるのは、品質保証（事前の確認、事後の確認、検証のループ、人間が見る関門）と再現性である。何をどう描くかを縛る禁止事項や固定の雛形は置かない。測った事実（作法の数値）は「照合する物差し」として渡してよい。規則として書かない。仕様は写さず、`docs/SPEC.md` の節へリンクする。

情報の優先順位は、指示 ＞ 仕様書 ＞ 原則 ＞ 過去事例（`AGENTS.md` §1）。
