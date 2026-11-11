# UPSTREAM_PROGRESS — 上流工程（Fable 5.2）進捗ログ

追記式。新しい行を下に足す。時刻は JST。

## 2026-11-12 再走セッション（フル権限）

- [x] 開始時点の状態確認: `docs/UPSTREAM_PROGRESS.md` なし / `.git` なし / `.gitignore` なし。
  前任セッションの下書きが入っていたはずの `_handoff/fable_upstream.log` は bat の再実行で上書き済み（`START` 行のみ）。
  → **下書きは失われているため、成果物はすべて本セッションで新規作成する。**
- [x] 正本ブリーフ `_handoff/CONTEXT_FOR_FABLE.md` 全文読了。
- [x] 同梱資料読了: `round2-report.md`（主根拠）/ `round2-key-findings.md` / `round1-report.md`（第3章途中で途切れ。ファイル自体がそこで終わっている）/ `round1-sources.md`。
- [x] 環境確認: git 2.54 あり（user.name=kokuren333 設定済み）。`gh` CLI は未インストール、`GH_TOKEN`/`GITHUB_TOKEN` も未設定。Python 3.12.10 / uv あり。
- [x] `git init -b main` 実行（ローカルリポジトリ作成）。
- [x] ライセンス再確認（LICENSE 原文を取得して確認、2026-11-12）:
  - Astropulse/pixeldetector = MIT（Copyright (c) 2023 Astropulse、追加制限なし）→ round2 の「矛盾」は LICENSE 原文レベルでは解消。
  - KohakuBlueleaf/PixelOE = Apache-2.0（Copyright 2024 KohakuBlueLeaf）。
  - dimtoneff/ComfyUI-PixelArt-Detector = MIT（Copyright (c) 2023 dimtoneff）。
  - sedthh/pyxelate = MIT（Copyright (c) 2021 Richard Nagyfi）。
  - mattt/aseprite-py（PyPI `aseprite` 0.1.0）= Apache-2.0、Python>=3.12、公開フォーマット仕様ベース。
  - MCP 仕様の現行版 = 2026-07-28（ステートレス）。Python SDK `mcp` 2.3.0 = MIT。
  - Lospec の利用規約ページは取得できず（404）→ 未確認のまま台帳に残す。
- [x] `.gitignore` 作成（`_handoff/` と `_private/` を除外）。`LICENSE`（Apache-2.0 本文、apache.org から取得、SHA-256 cfc7749b…523d30）配置。
- [x] `docs/SPEC.md` 作成（第 0〜17 章 ＋ 付録 A〜E）。
- [x] `docs/REQUIREMENTS_NOTES.md` 作成（ソフト別の採用・不採用、D-01〜D-40 の理由）。
- [x] 雛形作成: `README.md` / `NOTICE` / `AGENTS.md` / `CLAUDE.md` / `third_party/THIRD_PARTY.md` / `docs/DECISIONS.md` / `docs/reference/{PROVENANCE_LOG,ASEPRITE_INVENTORY}.md` / 骨格ディレクトリ（各 README と `.gitkeep`）。
- [x] SPEC の整合性を機械的に確認: 節参照（§）の切れ 0 件、エラーコードの未定義 0 件、決定記録 D-01〜D-40 の対応、MCP ツール 78 個、撮影画面 47 件、挙動確認 11 件。
- [x] GitHub リポジトリ作成の試行: **不可。** `gh` 未インストール、トークン未設定、`git ls-remote` はリポジトリなし。`origin` の URL だけ設定済み。理由と再開手順は `docs/UPSTREAM_REPORT.md` §3。
- [x] Aseprite 実機参照: **未実施（ヘッドレスのため）。** 手順書を `docs/SPEC.md` §3.5 に残し、M0 の必須タスクにした。
- [x] `docs/UPSTREAM_REPORT.md` 作成。
- [x] ローカル git に初期コミット（ブランチ `main`）。
- [x] Aseprite 公開ドキュメント（docs 目次、tilemap / layers / animation / selecting / exporting / drawing / sprite-sheet / color の各ページ、ase-file-specs.md）から機能の事実を確認（文面はコピーしていない）。
