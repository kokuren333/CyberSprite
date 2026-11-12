# direct — そのまま描く（小さなスプライト、アイコン）

**使う場面**: 1 コマが 32 px 以下のキャラクター、UI アイコン、小物。極小で制約の厳しいもの（[`silhouette-first.md`](silhouette-first.md)）と、48 px 以上の大きなもの（[`turnaround-parts.md`](turnaround-parts.md)）を除く。プラットフォームの `workflow` が `direct` のとき。

## 1. 思想と原則

- この大きさでは、1 px がそのまま意味の単位になる（目は 2 px）。図形と行データで足り、原画なしでも成り立つことが多い。e2e の 16×16 アイコンと 32×32 のキャラクターは、この手順で実用の水準に届いた（`docs/REVIEW_1.md` §2.1）。
- それでも、見た目の合格は人間が決める。関門は 2 つにまとめてよい。

## 2. 段と関門

| 段 | 担当 | すること | 関門 |
|---|---|---|---|
| 0 | Opus | 大きさ、パレット、方向性を決める。方向性が決まっていなければ 3 案ほど小さく作る | **(1) 設計** |
| 1 | Opus | 描く（[`draw-sprite`](../draw-sprite/SKILL.md)）。動きがあれば [`animate`](../animate/SKILL.md) | **(2)+(3) まとめて 1 回** |
| 2 | Opus | 検証、書き出し、書き出したファイルの確認（[`validate-export`](../validate-export/SKILL.md)） | |

- 関門 (2) ブロッキングと (3) 仕上げ前は、1 回にまとめてよい（`docs/SPEC.md` §13.7）。まとめたことを制作記録に書く。
- 原画が欲しければ、Codex imagegen に頼んでよい（[`turnaround-parts.md`](turnaround-parts.md) §3.2）。
- アイコンのように 1 枚ずつが小さく数が多いものは、全部を 1 枚に並べたシート（`preview --layout grid` の ×1 と整数倍）を関門で見せる。

## 3. 手順

[`draw-sprite`](../draw-sprite/SKILL.md) と `skills/README.md` のクイックスタートのとおり。関門のシートは [`validate-export`](../validate-export/SKILL.md) §2.5。

## 4. 失敗チェックリスト

- [ ] 拡大だけを見て、×1 で読めるかを確かめずに終えていないか。
- [ ] 関門のシートを出さずに完了を報告していないか。
- [ ] 見た目の合格を自分で宣言していないか。判定は `pending` のままか。
- [ ] 実際には 48 px 以上で、`turnaround-parts` を使うべき題材ではないか。
