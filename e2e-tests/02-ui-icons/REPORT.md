# e2e 制作テスト #02 — GUI アイコンセット（報告）

- 担当: Claude Opus 5.5（effort 中）／制作日: 2026-11-12
- 題材: SPEC §14.3.2 の GUI アイコン（16×16、原本は `assets/ui/icons/*.csprite`）。テーマは案 C「Solder Mask」
- （サブエージェントの実行環境がレポートファイルの書き込みを禁じていたため、本文はオーケストレーターが保存した。）

## 作ったもの
- `assets/ui/icons/<名前>.csprite` 40 個（16×16、1 フレーム、レイヤー `icon`、背景は透明）
  - ツールバー 11: pencil, eraser, line, rect, ellipse, fill, eyedropper, select-rect, move, hand, zoom
  - タイムライン 13: eye, eye-off, lock, unlock, link, play, pause, step-prev, step-next, first, last, onion, grid
  - コマンド 4: undo, redo, add, remove
  - 状態とエージェント 8: warning（三角）, error（八角形）, info（円）, agent（ロボットの頭）, human, diff（比較スライダー）, sources（来歴の画像）, validate-ok（IC チップに検査済みの印）
  - 構造 4: tag, layer, folder, tile
- 共通パレット `ui-icons.gpl`（11 色: 透明、ink #0B2A3A、trace-deep、trace、trace-soft、white、warn、error、agent、ink-soft、agent-soft）。全プロジェクトで番号を共通にし、色名もつけた。
- デザイン: テーマ担当の下書き（`docs/design/theme-options/tools/pixels.py`）を出発点にした。線の太さが 2px のもの（move、plus、warn、prev など）を 1px の輪郭に揃え、大きさを 14×14 の枠に揃えた。eye は虹彩・瞳・ハイライトに、zoom は 11px の円にして十字を中央に置いた。link、diff、sources、validate-ok、tag、layer は描き直した。意味は色ではなく形で伝える（警告・エラー・情報・OK は輪郭の形がそれぞれ違う）。
- ピクセルは CyberSprite の Op（`draw_rows` の `sym` 形式）だけで書いた。Pillow は一覧画像を並べることと、照合にだけ使った。

## 作業の記録
- `new` を 40 回。トランザクションは 83 回（描画 40、見直しによる描き直し 2、パレットの色名づけ 40、試し 1）。undo は 0 回。
- 見たもの: 全 40 個の ×4 の一覧（3 種類の下地: パネル白、基板、アクティブ）と実寸の帯。最後の変更の後にも作り直して見た。
- 書き出したファイルの確認: x1 と x4 の 80 枚の PNG を、設計データと 1 ピクセルずつ照らし合わせた。不一致は 0、α は 0 か 255 だけ。`render --indexed` の出力は P モード、16×16、透明 = 0、11 色。結果は `validation_ok: true`、`verified: true`。

## 検証の結果
- 40 個すべて `ok: true`（error 0、warning 0）。
- info `Q-PAL-02`（使っていないパレット番号）: 全アイコンで出る。共通パレットなので、意図どおりとして残した。
- info `Q-PIX-02`（小さすぎる塊）: pencil、line、move、eye、onion の 5 個で出る。座標を 1 つずつ確かめ、どれも意図したアクセントなので残した。

## ツールの問題（深刻な順）
1. `export image|sheet` がまだ使えない（M5 統合待ち）。`export sheet` は終了コード 6 で `E_UNSUPPORTED`。`export image --help` に将来の引数が出ない。回避として `render` で 1 枚ずつ書き出した。仕様の抜け: 複数のプロジェクトを 1 枚のシートにまとめる手段が仕様にない。
2. `new --palette <.gpl>` で、.gpl の色名が捨てられる（`palette show` で全色 `"name": null`）。回避として `set_palette`（`colors` と `names`）を 40 回当てた。
3. 名前だけを変えた `set_palette` でも、`changed` にフレームの変更（`pixels_changed: 0`）が出る。期待は `frames: []`。
4. CLI の 1 回の呼び出しが約 1 秒かかる（軽微）。40 プロジェクトのビルドに約 2 分。
5. `Q-PIX-02` が UI アイコンの意図した 1px のアクセントに出る（軽微、info）。手順書に「UI アイコンでは 1px のアクセントは普通。必要なら `set_validation` で min_cluster を下げる」とあるとよい。
6. `pixels --layer` の既定の範囲はセルの矩形（切り詰め後）になる。全面と比べるには `--rect` が要る。CLI.md の例に一言あると迷わない。

## よかった点
`draw_rows` の `sym` 形式で設計の格子をそのまま流し込めた。`apply -` の `label` で履歴が読みやすい。検証デルタに点の座標が出る。`render` の `verified` と `pixel_sha256`。描画系のエラーは 0 回。

## 評価
**4 / 5**。描く・検証する・確かめるの流れは快適で、同じ入力から同じ結果が出る。1 点引いたのは、シートへの書き出しがまだできないことと、.gpl の色名が落ちることのため。

## オーケストレーターの対応（2026-11-12）
- 1: 書き出しは M5 統合（作業中）で入る。複数プロジェクトのシートは作らず、アイコンごとに `export image` で書き出す方針にした（I-013、SPEC §14.3.2 を修正）。
- 2・3・6: 修正項目として `docs/IMPLEMENTATION_PROGRESS.md` に登録した。4 は `docs/PERFORMANCE.md` で追う。5 は手順書（M10）に書く。
