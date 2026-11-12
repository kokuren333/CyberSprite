# GUI アイコン（原本）

GUI のアイコンの原本。1 アイコン = 1 つの CyberSprite プロジェクト（`<名前>.csprite/`、16×16、1 フレーム、レイヤー `icon`、背景は透明）。
SPEC §14.3.2「自分たちの道具で自分たちの UI を作る」に従い、ピクセルは CyberSprite の Op（`draw_rows`）だけで描いた。テーマは案 C「Solder Mask」。

## パレット（`ui-icons.gpl`、全アイコン共通）

| 番号 | 名前 | 色 | 使い方 |
|---|---|---|---|
| 0 | transparent | — | 透明インデックス |
| 1 | ink | `#0B2A3A` | 輪郭線（1px）。どの下地でもこれで形が読める |
| 2 | trace-deep | `#0A86A8` | 濃い水色。補助の線、情報アイコンの面 |
| 3 | trace | `#19C3E6` | 水色。ツールの主な面 |
| 4 | trace-soft | `#BFEFF9` | 薄い水色。副の面 |
| 5 | white | `#FFFFFF` | 白い面、記号の抜き |
| 6 | warn | `#E8A317` | 警告（はんだの金色）。状態アイコンにだけ使う |
| 7 | error | `#E5484D` | エラー。状態アイコンにだけ使う |
| 8 | agent | `#7C5CFF` | エージェントの印 |
| 9 | ink-soft | `#43606E` | 小さな陰（鉛筆の芯など） |
| 10 | agent-soft | `#D9D0FF` | エージェントの面 |

色を足すときは、全プロジェクトに同じ番号で足す（番号が共通なのでシートにまとめても色がずれない）。

## 描き方の約束

- 輪郭は ink の 1px。内容は 14×14（座標 1〜14）に収める。
- 斜めは 45° か 2:1 の段。アンチエイリアスなし。
- 意味は形で伝える（警告 = 三角、エラー = 八角形、情報 = 円、検証 OK = チップ）。色だけに頼らない。
- 他製品のアイコンを見て写さない（AGENTS.md §4）。

## 名前

ファイル名は英小文字のケバブケース（`select-rect`、`eye-off`、`step-prev` など）。GUI からはこの名前で引く。
一覧は `tools/icon_grids.py` の `all_icons()`（ツールバー 11、タイムライン 13、コマンド 4、状態とエージェント 8、構造 4、GUI の部品 1 の計 41）。

## 作り直す・直す

- 原本は `.csprite`。小さな修正は、そのプロジェクトに Op を当てればよい（`cybersprite -p assets/ui/icons/pencil.csprite op set_pixel ...`）。
- 最初の描画は `tools/icon_grids.py`（設計データ）を `tools/build_icons.py` が CLI 経由で書き込んだもの。設計データを直して
  `python assets/ui/icons/tools/build_icons.py --renders <確認用ディレクトリ>` を実行すると、差のあるアイコンだけ `draw_rows` 1 トランザクションで描き直し、`validate` と `render`（×1、×4）まで行う。
  `.csprite` を直接直した場合は、設計データとずれるので、次に `build_icons.py` を流す前に設計データへ反映する。
- 確認用の一覧画像: `python assets/ui/icons/tools/contact_sheet.py <確認用ディレクトリ> <出力先>`（render の出力を並べるだけ。描画はしない）。

## GUI への組み込み

GUI のビルド（`cd gui && npm run build`）の前段 `npm run icons` が、全アイコンを 1 つずつ CLI の `export image` で PNG に書き出して組み込む（SPEC §14.3.2。複数プロジェクトを 1 枚にまとめる書き出しは v1 にはない [I-013]）。

```powershell
uv run cybersprite -p assets/ui/icons/<名前>.csprite export image --out gui/public/icons/<名前>.png
```

出力は git 管理外。詳細は `docs/GUI.md` の「アイコン」。M8 で GUI の設定ボタン用に `settings`（スライダー）を追加した（計 41）。
