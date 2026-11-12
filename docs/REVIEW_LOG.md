# REVIEW_LOG — レビューへの対応記録

2026-11-12、修正ラウンド1。設計回答はFable §3 → Codex §6 → SPEC、今回の具体的な発注指示が優先する。

## 相違と採用理由（発注者確認用）

| 論点 | Fable | Codex | 今回の対応・理由 |
|---|---|---|---|
| Linuxでの決定性 | R1-01 blocker | 識別するが新規指摘に数えない | 過去Linux core成功、最終CI待ち。重要度を下げずpartially |
| 制作品質 | R1-02 blocker | 未達とするが新規指摘に数えない | 3関門・原画・pendingを実装、e2e-07人間合否待ちでpartially |
| schemaの版 | 1のまま省略可、移行は合成fixture | 2へ上げ1→2移行 | Fable優先、schema1・platform snapshot（I-1401） |
| 共有位置の編集 | 既定error＋明示all/unlinkとmove_cel | 既存意味＋警告とmove_cel | Fable統合案を採用、事故を事前拒否（I-1402） |
| 機種のパレット | 行index規約を先行 | bank/slot/global対応とlayout | 行index規約とgb-2bppまで、完全layout／追加形式は延期（I-1402/1507/1515） |
| connectorの標準化 | 手動保存標準を推奨 | 別の確定案なし | 後続発注指示I-1807が優先、private connector標準（のちI-2002で標準から外した）。403時は回避せず既存library |

## 指摘ごとの直す／直さない

重複台帳の状態ずれを避け、全32 Fable・全8 Codex指摘の状態、対応先、延期理由は [FIX_ROUND_1_REPORT §4](FIX_ROUND_1_REPORT.md) を本ログの対応表として参照する（I-1945）。設計分岐とI番号は同§5、現在の未完はKNOWN_ISSUES。fixedは指定修正済み、partiallyは条件残、deferredは理由付き延期、not addressedは未着手を表す。

- Fable: fixed24 / partially6 / deferred2 / not addressed0（FIX_ROUND_1_REPORT §4 の総括に合わせた。2026-11-12 公開前仕上げで R2-25 の指摘を反映。REVIEW_2 の判定では解消 20・部分 10・未解消 2）。
- Codex: fixed7 / partially1 / deferred0 / not addressed0。
- 延期した実装はR1-17/30（専用GUI／設定）、importers、H-10 analyze、H-12後半offset links、追加native/sidecarsなど。関門95%と性能目標は下げず未達を記録。
- I-010/I-012事後承認、最終CI、e2e-07人間判定は待ち。connectorは未決ではなく後続発注指示で標準化済み（のちI-2002で標準から外した）。

## 次回

R1後は発注者が仕様を締め直すため一旦停止し、自動R2は行わない。REVIEW_REQUEST_2は実施決定時の準備文書。最終CIとe2e-07は総括・依頼の指定placeholderへオーケストレーターが差し込む。
