# コントラスト検査（テーマ 3 案）

`tools/contrast_check.py` が各案の `style.css` の CSS 変数を読み、WCAG 2.x の相対輝度でコントラスト比を計算した結果である。基準は SPEC §14.3.3: 本文 7:1、補助の文字 4.5:1、意味のある文字以外の要素 3:1。「基準」が `—` の行は装飾（意味を持たない配線など）で、参考として値だけを載せる。

再生成: `python docs/design/theme-options/tools/contrast_check.py`

## Option A

必須 25 組のうち不合格 0 組。最も余裕が小さい組: active border vs its own fill（3.16 / 基準 3）。

| 用途 | 前景 | 背景 | 比 | 基準 | 判定 |
|---|---|---|---:|---:|---|
| body text on panels | `--cs-ink` #0B2A3A | `--cs-panel` #FFFFFF | 14.93 | 7:1 | OK |
| menu / context bar text on the board | `--cs-ink` #0B2A3A | `--cs-board` #F4FAFC | 14.17 | 7:1 | OK |
| button and input text on pads | `--cs-ink` #0B2A3A | `--cs-pad` #E6F7FB | 13.55 | 7:1 | OK |
| text on pressed / selected pads | `--cs-ink` #0B2A3A | `--pad-on-bg` #D2F1F8 | 12.57 | 7:1 | OK |
| selected activity row / selected layer | `--cs-ink` #0B2A3A | `--act-sel-bg` #EAF8FC | 13.74 | 7:1 | OK |
| panel header text, silk labels | `--cs-ink` #0B2A3A | `--ph-bg` #FFFFFF | 14.93 | 7:1 | OK |
| inverted: tooltip, FG tag, current frame number | `--cs-panel` #FFFFFF | `--cs-ink` #0B2A3A | 14.93 | 7:1 | OK |
| secondary text on panels | `--cs-ink-soft` #4A6878 | `--cs-panel` #FFFFFF | 5.93 | 4.5:1 | OK |
| secondary text on the board | `--cs-ink-soft` #4A6878 | `--cs-board` #F4FAFC | 5.62 | 4.5:1 | OK |
| secondary text on pads / tag band | `--cs-ink-soft` #4A6878 | `--cs-pad` #E6F7FB | 5.38 | 4.5:1 | OK |
| secondary text in the selected row | `--cs-ink-soft` #4A6878 | `--act-sel-bg` #EAF8FC | 5.46 | 4.5:1 | OK |
| header meta text | `--cs-ink-soft` #4A6878 | `--ph-bg` #FFFFFF | 5.93 | 4.5:1 | OK |
| silk-screen label (pixel font) | `--silk` #4A6878 | `--ph-bg` #FFFFFF | 5.93 | 4.5:1 | OK |
| icon line (all icons are ink-outlined) | `--cs-ink` #0B2A3A | `--cs-panel` #FFFFFF | 14.93 | 3:1 | OK |
| icon line inside pads | `--cs-ink` #0B2A3A | `--cs-pad` #E6F7FB | 13.55 | 3:1 | OK |
| icon line inside the active tool | `--cs-ink` #0B2A3A | `--pad-on-bg` #D2F1F8 | 12.57 | 3:1 | OK |
| active tool / active tab / selection frame / energised border | `--cs-trace-deep` #0A8FB3 | `--cs-panel` #FFFFFF | 3.75 | 3:1 | OK |
| pressed pad border next to idle pads | `--cs-trace-deep` #0A8FB3 | `--cs-pad` #E6F7FB | 3.41 | 3:1 | OK |
| active border vs its own fill | `--cs-trace-deep` #0A8FB3 | `--pad-on-bg` #D2F1F8 | 3.16 | 3:1 | OK |
| selected-row bar | `--cs-trace-deep` #0A8FB3 | `--act-sel-bg` #EAF8FC | 3.46 | 3:1 | OK |
| energised panel border on the board | `--cs-trace-deep` #0A8FB3 | `--cs-board` #F4FAFC | 3.56 | 3:1 | OK |
| empty-cel dot, checkbox frame, slider frame | `--cs-ink-soft` #4A6878 | `--cs-panel` #FFFFFF | 5.93 | 3:1 | OK |
| cels in the current-frame column | `--cs-ink` #0B2A3A | `--cur-col` #EAF8FC | 13.74 | 3:1 | OK |
| agent marker (icon fill, diff box) | `--cs-agent` #7C5CFF | `--cs-panel` #FFFFFF | 4.35 | 3:1 | OK |
| error icon fill | `--cs-error` #E5484D | `--cs-panel` #FFFFFF | 3.91 | 3:1 | OK |
| warning icon fill (decorative: the ink outline carries the shape) | `--cs-warn` #E8A317 | `--cs-panel` #FFFFFF | 2.17 | — | 参考 |
| bright trace on panels (decorative wiring) | `--cs-trace` #19C3E6 | `--cs-panel` #FFFFFF | 2.10 | — | 参考 |
| bright trace on the board (decorative wiring) | `--cs-trace` #19C3E6 | `--cs-board` #F4FAFC | 1.99 | — | 参考 |
| soft separators (decorative) | `--cs-trace-soft` #BFEFF9 | `--cs-panel` #FFFFFF | 1.24 | — | 参考 |

キャンバス周囲の色み（クロマ = RGB の最大 − 最小、0 が無彩色）: surround #DCE6EA = 0.05、市松 #FFFFFF = 0.00 / #E3E8EB = 0.03（参考: UI の `--cs-trace` は 0.80。低いほど絵の色判断を邪魔しない）。

## Option B

必須 31 組のうち不合格 0 組。最も余裕が小さい組: secondary text in the selected row（5.99 / 基準 4.5）。

| 用途 | 前景 | 背景 | 比 | 基準 | 判定 |
|---|---|---|---:|---:|---|
| body text on panels | `--cs-ink` #0B2A3A | `--cs-panel` #FFFFFF | 14.93 | 7:1 | OK |
| menu / context bar text on the board | `--cs-ink` #0B2A3A | `--cs-board` #FFFFFF | 14.93 | 7:1 | OK |
| button and input text on pads | `--cs-ink` #0B2A3A | `--cs-pad` #EDF8FB | 13.81 | 7:1 | OK |
| text on pressed / selected pads | `--cs-ink` #0B2A3A | `--pad-on-bg` #CFF0F8 | 12.42 | 7:1 | OK |
| selected activity row / selected layer | `--cs-ink` #0B2A3A | `--act-sel-bg` #E5F6FB | 13.44 | 7:1 | OK |
| panel header text, silk labels | `--cs-ink` #0B2A3A | `--ph-bg` #FFFFFF | 14.93 | 7:1 | OK |
| inverted: tooltip, FG tag, current frame number | `--cs-panel` #FFFFFF | `--cs-ink` #0B2A3A | 14.93 | 7:1 | OK |
| secondary text on panels | `--cs-ink-soft` #45606F | `--cs-panel` #FFFFFF | 6.65 | 4.5:1 | OK |
| secondary text on the board | `--cs-ink-soft` #45606F | `--cs-board` #FFFFFF | 6.65 | 4.5:1 | OK |
| secondary text on pads / tag band | `--cs-ink-soft` #45606F | `--cs-pad` #EDF8FB | 6.15 | 4.5:1 | OK |
| secondary text in the selected row | `--cs-ink-soft` #45606F | `--act-sel-bg` #E5F6FB | 5.99 | 4.5:1 | OK |
| header meta text | `--cs-ink-soft` #45606F | `--ph-bg` #FFFFFF | 6.65 | 4.5:1 | OK |
| silk-screen label (pixel font) | `--silk` #0B2A3A | `--ph-bg` #FFFFFF | 14.93 | 4.5:1 | OK |
| icon line (all icons are ink-outlined) | `--cs-ink` #0B2A3A | `--cs-panel` #FFFFFF | 14.93 | 3:1 | OK |
| icon line inside pads | `--cs-ink` #0B2A3A | `--cs-pad` #EDF8FB | 13.81 | 3:1 | OK |
| icon line inside the active tool | `--cs-ink` #0B2A3A | `--pad-on-bg` #CFF0F8 | 12.42 | 3:1 | OK |
| active tool / active tab / selection frame / energised border | `--cs-trace-deep` #077A99 | `--cs-panel` #FFFFFF | 4.94 | 3:1 | OK |
| pressed pad border next to idle pads | `--cs-trace-deep` #077A99 | `--cs-pad` #EDF8FB | 4.57 | 3:1 | OK |
| active border vs its own fill | `--cs-trace-deep` #077A99 | `--pad-on-bg` #CFF0F8 | 4.11 | 3:1 | OK |
| selected-row bar | `--cs-trace-deep` #077A99 | `--act-sel-bg` #E5F6FB | 4.45 | 3:1 | OK |
| energised panel border on the board | `--cs-trace-deep` #077A99 | `--cs-board` #FFFFFF | 4.94 | 3:1 | OK |
| empty-cel dot, checkbox frame, slider frame | `--cs-ink-soft` #45606F | `--cs-panel` #FFFFFF | 6.65 | 3:1 | OK |
| cels in the current-frame column | `--cs-ink` #0B2A3A | `--cur-col` #E9F7FB | 13.62 | 3:1 | OK |
| agent marker (icon fill, diff box) | `--cs-agent` #6B4CF0 | `--cs-panel` #FFFFFF | 5.36 | 3:1 | OK |
| error icon fill | `--cs-error` #D9434A | `--cs-panel` #FFFFFF | 4.33 | 3:1 | OK |
| warning icon fill (decorative: the ink outline carries the shape) | `--cs-warn` #E8A317 | `--cs-panel` #FFFFFF | 2.17 | — | 参考 |
| bright trace on panels (decorative wiring) | `--cs-trace` #19C3E6 | `--cs-panel` #FFFFFF | 2.10 | — | 参考 |
| bright trace on the board (decorative wiring) | `--cs-trace` #19C3E6 | `--cs-board` #FFFFFF | 2.10 | — | 参考 |
| soft separators (decorative) | `--cs-trace-soft` #CDEFF7 | `--cs-panel` #FFFFFF | 1.21 | — | 参考 |
| silk label + refdes printed on the board | `--cs-ink` #0B2A3A | `--cs-board` #FFFFFF | 14.93 | 7:1 | OK |
| refdes chip (U1, J1 ...) | `--cs-panel` #FFFFFF | `--cs-ink` #0B2A3A | 14.93 | 7:1 | OK |
| title-block field labels | `--cs-ink-soft` #45606F | `--cs-panel` #FFFFFF | 6.65 | 4.5:1 | OK |
| component outline / title block rules | `--cs-trace-deep` #077A99 | `--cs-panel` #FFFFFF | 4.94 | 3:1 | OK |
| dimension lines around the canvas | `--cs-ink-soft` #45606F | `--cs-canvas-surround` #E1E7EA | 5.33 | 3:1 | OK |
| dimension text | `--cs-ink` #0B2A3A | `--cs-canvas-surround` #E1E7EA | 11.96 | 7:1 | OK |
| drafting dot grid (decorative) | `--cs-grid` #B3E2EE | `--cs-board` #FFFFFF | 1.40 | — | 参考 |

キャンバス周囲の色み（クロマ = RGB の最大 − 最小、0 が無彩色）: surround #E1E7EA = 0.04、市松 #FFFFFF = 0.00 / #E4E9EC = 0.03（参考: UI の `--cs-trace` は 0.80。低いほど絵の色判断を邪魔しない）。

## Option C

必須 30 組のうち不合格 0 組。最も余裕が小さい組: energised header: ink text on solid cyan（7.10 / 基準 7）。

| 用途 | 前景 | 背景 | 比 | 基準 | 判定 |
|---|---|---|---:|---:|---|
| body text on panels | `--cs-ink` #0B2A3A | `--cs-panel` #FFFFFF | 14.93 | 7:1 | OK |
| menu / context bar text on the board | `--cs-ink` #0B2A3A | `--cs-board` #DDF3F8 | 12.98 | 7:1 | OK |
| button and input text on pads | `--cs-ink` #0B2A3A | `--cs-pad` #EAF8FB | 13.73 | 7:1 | OK |
| text on pressed / selected pads | `--cs-ink` #0B2A3A | `--pad-on-bg` #CDEFF7 | 12.29 | 7:1 | OK |
| selected activity row / selected layer | `--cs-ink` #0B2A3A | `--act-sel-bg` #E6F7FB | 13.55 | 7:1 | OK |
| panel header text, silk labels | `--cs-ink` #0B2A3A | `--ph-bg` #FFFFFF | 14.93 | 7:1 | OK |
| inverted: tooltip, FG tag, current frame number | `--cs-panel` #FFFFFF | `--cs-ink` #0B2A3A | 14.93 | 7:1 | OK |
| secondary text on panels | `--cs-ink-soft` #43606E | `--cs-panel` #FFFFFF | 6.69 | 4.5:1 | OK |
| secondary text on the board | `--cs-ink-soft` #43606E | `--cs-board` #DDF3F8 | 5.82 | 4.5:1 | OK |
| secondary text on pads / tag band | `--cs-ink-soft` #43606E | `--cs-pad` #EAF8FB | 6.16 | 4.5:1 | OK |
| secondary text in the selected row | `--cs-ink-soft` #43606E | `--act-sel-bg` #E6F7FB | 6.08 | 4.5:1 | OK |
| header meta text | `--cs-ink-soft` #43606E | `--ph-bg` #FFFFFF | 6.69 | 4.5:1 | OK |
| silk-screen label (pixel font) | `--silk` #0B2A3A | `--ph-bg` #FFFFFF | 14.93 | 4.5:1 | OK |
| icon line (all icons are ink-outlined) | `--cs-ink` #0B2A3A | `--cs-panel` #FFFFFF | 14.93 | 3:1 | OK |
| icon line inside pads | `--cs-ink` #0B2A3A | `--cs-pad` #EAF8FB | 13.73 | 3:1 | OK |
| icon line inside the active tool | `--cs-ink` #0B2A3A | `--pad-on-bg` #CDEFF7 | 12.29 | 3:1 | OK |
| active tool / active tab / selection frame / energised border | `--cs-trace-deep` #0A86A8 | `--cs-panel` #FFFFFF | 4.21 | 3:1 | OK |
| pressed pad border next to idle pads | `--cs-trace-deep` #0A86A8 | `--cs-pad` #EAF8FB | 3.87 | 3:1 | OK |
| active border vs its own fill | `--cs-trace-deep` #0A86A8 | `--pad-on-bg` #CDEFF7 | 3.47 | 3:1 | OK |
| selected-row bar | `--cs-trace-deep` #0A86A8 | `--act-sel-bg` #E6F7FB | 3.82 | 3:1 | OK |
| energised panel border on the board | `--cs-trace-deep` #0A86A8 | `--cs-board` #DDF3F8 | 3.66 | 3:1 | OK |
| empty-cel dot, checkbox frame, slider frame | `--cs-ink-soft` #43606E | `--cs-panel` #FFFFFF | 6.69 | 3:1 | OK |
| cels in the current-frame column | `--cs-ink` #0B2A3A | `--cur-col` #E9F8FB | 13.71 | 3:1 | OK |
| agent marker (icon fill, diff box) | `--cs-agent` #7C5CFF | `--cs-panel` #FFFFFF | 4.35 | 3:1 | OK |
| error icon fill | `--cs-error` #E5484D | `--cs-panel` #FFFFFF | 3.91 | 3:1 | OK |
| warning icon fill (decorative: the ink outline carries the shape) | `--cs-warn` #E8A317 | `--cs-panel` #FFFFFF | 2.17 | — | 参考 |
| bright trace on panels (decorative wiring) | `--cs-trace` #19C3E6 | `--cs-panel` #FFFFFF | 2.10 | — | 参考 |
| bright trace on the board (decorative wiring) | `--cs-trace` #19C3E6 | `--cs-board` #DDF3F8 | 1.83 | — | 参考 |
| soft separators (decorative) | `--cs-trace-soft` #BFEFF9 | `--cs-panel` #FFFFFF | 1.24 | — | 参考 |
| energised header: ink text on solid cyan | `--cs-ink` #0B2A3A | `--cs-trace` #19C3E6 | 7.10 | 7:1 | OK |
| idle header text on soft cyan | `--cs-ink` #0B2A3A | `--cs-trace-soft` #BFEFF9 | 12.04 | 7:1 | OK |
| idle header meta text | `--cs-ink-soft` #43606E | `--cs-trace-soft` #BFEFF9 | 5.40 | 4.5:1 | OK |
| via ring on the energised header | `--cs-ink` #0B2A3A | `--cs-trace` #19C3E6 | 7.10 | 3:1 | OK |
| header rule / active tab vs header | `--cs-trace-deep` #0A86A8 | `--cs-trace-soft` #BFEFF9 | 3.39 | 3:1 | OK |
| DIP pins of the tool chip | `--cs-trace-deep` #0A86A8 | `--cs-board` #DDF3F8 | 3.66 | — | 参考 |
| routed traces on the mask (decorative) | `--cs-mask-trace` #93D2E3 | `--cs-board` #DDF3F8 | 1.45 | — | 参考 |
| pad bevel (decorative) | `--cs-pad-shade` #B9DDE6 | `--cs-panel` #FFFFFF | 1.44 | — | 参考 |

キャンバス周囲の色み（クロマ = RGB の最大 − 最小、0 が無彩色）: surround #D5DEE2 = 0.05、市松 #FFFFFF = 0.00 / #E1E7EA = 0.04（参考: UI の `--cs-trace` は 0.80。低いほど絵の色判断を邪魔しない）。

## まとめ

| 案 | 必須の組 | 不合格 | 最小余裕の組 |
|---|---:|---:|---|
| A | 25 | 0 | active border vs its own fill（3.16 / 3） |
| B | 31 | 0 | secondary text in the selected row（5.99 / 4.5） |
| C | 30 | 0 | energised header: ink text on solid cyan（7.10 / 7） |

### 注記

- 明るい水色 `--cs-trace` は白地で 3:1 に届かない。どの案でも配線・区切りの装飾にだけ使い、文字、選択表示、フォーカスには使わない（選択・通電は `--cs-trace-deep` と形の変化で示す）。
- 警告色 `--cs-warn`（はんだの金色）は白地で 3:1 に届かない。警告アイコンは濃紺の輪郭と「!」で形を作り、金色は塗りの補助に留める。
- 状態は色だけで示さない: セルは形（点 / 塗り四角 / 白抜き四角＋連結線）、検証は記号（チェック / 三角）と文字、実行者はアイコン（ロボット / 人）と名前、選択は枠＋左の帯で示す。
