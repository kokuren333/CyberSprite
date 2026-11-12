# e2e テスト #01 — キャラクター「サーキット・メカニック」

作成: Opus 5.5（effort 中、制作サブエージェント） / 2026-11-12 / CyberSprite 0.1.0（`3279f4d`）
（サブエージェントの実行環境がレポートファイルの書き込みを禁じていたため、本文はオーケストレーターが保存した。）

## 1. 作ったもの
- 32×32、既定パレット `cs-circuit-16`（`new` を `--palette` なしで作成）。ゴーグルを額に上げたオレンジ髪の整備士の少女。青いつなぎ、黄色のベルト、胸に回路バッジ、右手（画面右）にスパナ。
- 光源は左上。髪の左にハイライト（11）、右端に影（14）を 1 列。つなぎの左縁にシアン 7 のリムライト。レンズは 8→7→6 の段階。
- レイヤー（下から）: `shadow`（L2、接地影、`ellipse`）/ `body`（L1、輪郭とベース色）/ `details`（L3、目・口・バッジ・スパナ）。
- フレーム 0 = 通常（1600 ms）、フレーム 1 = まばたき（140 ms）。`shadow` と `body` はリンクしたまま。`details` だけ `unlink_cel` して目を閉じた。
- タグ `idle`（T1）: 0〜1、forward、repeat 0。使った色は透明を除いて 12 色。

## 2. 作業ログの要約
- コミットされたリビジョン 16。内訳: 通常のトランザクション 14（`apply` 6、`op` 8、Op 計 17）、undo 1、redo 1（タグを戻して再適用。正しく復元）、dry-run 1（リンクセル編集で `linked_frames: [0,1]` を事前確認）。
- 流れ: レイヤー構成 → `draw_rows`（sym）で body を一括 → 髪の右影を 2 列→1 列 → 影 → 顔 → 頬紅（髪と同化したので消去）→ バッジ → スパナ → `add_frame cels=link` → unlink + 閉じ目 → 表示時間 → タグ → undo/redo → 孤立点 (9,8) を修正 → 全フレームのプレビュー → 書き出し → 書き出しファイルの検査。

## 3. 検証
最終 `validate`（rev 16）: ok: true、error 0、warning 0、info 3。
- Q-PAL-02 未使用 [9,10,15,16]: このキャラクターに要らない色なので、意図どおり残す。
- Q-PIX-02（フレーム 0 で 10 点 / フレーム 1 で 8 点）: 1 点ずつ確認した。(9,8) のストラップ端の迷子ピクセルは色 2 に直した（リンクで両フレームに反映）。レンズの光と影 (12,7)(18,7)(13,8)(19,8)、前髪のハイライト (11,9)、瞳 (12,12)(18,12)、スパナの光沢 (26,15)、バッジ (17,19)、ベルトの陰 (19,21) は意図したものなので残す。

## 4. 書き出し
書き出し Op が未実装（M5 で実装中）のため、`render` で各フレームを書いた。GIF とシートは作れていない。
- `export/mechanic_f{0,1}.png`（×1）、`export/mechanic_f{0,1}_x8.png`（×8）、`export/mechanic_f0_indexed.png`（`--indexed`）。すべて validation_ok と verified が true。
- Pillow（読み取りのみ）で確認した: パレット外の色なし。フレーム 0 と 1 の差は目の 6 ピクセルだけ。×8 は ×1 の最近傍 ×8 とバイト一致。インデックス PNG の RGBA 化は ×1 と一致。×8 とフレーム 1 の ×1 は目でも確認した。
- アニメーションの書き出しが無いので、再生しての確認はしていない。

## 5. ツールの問題（重い順）
1. 書き出し Op（export_image / sheet / animation）が未実装。CLI に `export` も無い。
2. `preview --frames 0,1 --out …` → `E_INVALID_ARGS "No such option: --frames (Possible options: --frame, --rulers)"`。仕様 §9.3 の `--onion` と `--out` も無い。複数フレームを 1 枚で見られない。
3. `pixels --as sym` → `"No such option: --as"`。実装は `--pixel-format`。仕様の `--rect` も無い。
4. `docs/CLI.md` が存在しない。
5. `ops describe` の説明が定型文だけで、`draw_rows` の `format: sym` の意味が分からない（SPEC を grep する必要があった）。
6. `op` に `--label` が無く、単発の Op は履歴の label が None。
7. `ellipse`（影レイヤーに 40 px 書いた）の `changed.pixels_changed` が 18。合成結果の差なので仕様どおりだが、`ellipse` の result に `pixels_written` が無い。
8. undo / redo の envelope の preview が空（`paths: []`）。
9. `validate` に `--frames` が無い（仕様にはある）。
10. Q-PIX-02 の `where.layer` が null で、どのレイヤーの点か分からない。

良かった点: sym 形式の `draw_rows` で下地を 1 回で描けた。dry-run の `linked_frames` で事前に安全確認ができた。孤立点が座標つきで出る。`render` の verified と sha256。オプションを取り違えたとき、エラーが正しい候補を示してくれた。

## 6. 使い心地: 4 / 5
中核のループ（描画、リンク、タグ、undo、検証）は正確で読みやすい。減点の理由は、書き出しと複数フレームのプレビューが無いこと、そして CLI と仕様の食い違い。

## 7. 納品物
`mechanic.csprite/`（history と previews を含む。約 220 KB）、`export/` の PNG 5 枚、REPORT.md。

## 8. オーケストレーターの対応（2026-11-12）
- 1・2・3・4・9 は M3（CLI の完成）と M5（書き出し）の範囲で、並行作業中。統合後に再確認する。
- 5・6・7・8・10 は追加の修正項目として `docs/IMPLEMENTATION_PROGRESS.md` の「e2e で見つかった問題」に登録した。
