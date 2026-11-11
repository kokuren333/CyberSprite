# 組み込み OSS 台帳

方針と手順は `docs/SPEC.md` §2 にある。この台帳は、**実際に依存に追加した、または同梱したもの**を記録する。

- 追加する前に、そのリポジトリの **LICENSE の原文**を開いて確認する。検索結果や二次情報だけで決めない。
- 許可するライセンス: MIT / BSD-2-Clause / BSD-3-Clause / Apache-2.0 / ISC / Zlib / HPND（MIT-CMU）/ PSF-2.0 / Unlicense / CC0-1.0。アセットは OFL-1.1 も可。
- GPL / LGPL / AGPL / MPL のコードは入れない。モデルの重みは入れない。
- 同梱するものは、ライセンス本文を `third_party/licenses/<名前>.txt` に置き、`NOTICE` に帰属表示を足す。

## 1. 依存・同梱の記録

現時点（仕様策定フェーズ）では、依存も同梱もない。

| 名前 | 版 | ライセンス（SPDX） | 入手元 | 確認日 | 確認方法 | 組み込み形態 | 確認者 |
|---|---|---|---|---|---|---|---|
| （なし） | | | | | | | |

## 2. 上流工程での事前確認（2026-11-12、Fable 5.2）

依存に追加したわけではない。実装フェーズで追加するときに、もう一度確認する。

| 名前 | ライセンス | 確認方法 | 予定している形態 |
|---|---|---|---|
| `aseprite`（mattt/aseprite-py）0.1.0 | Apache-2.0 | PyPI のページと README の記載 | 必須依存（アダプタ越し） |
| PixelOE | Apache-2.0（Copyright 2024 KohakuBlueLeaf） | リポジトリの LICENSE 原文 | 任意の extra |
| `mcp`（MCP Python SDK）2.3.0 | MIT | PyPI のページの記載 | 任意の extra |
| Astropulse/pixeldetector | MIT（Copyright (c) 2023 Astropulse、追加制限なし） | リポジトリの LICENSE 原文 | 設計の参照のみ |
| dimtoneff/ComfyUI-PixelArt-Detector | MIT（Copyright (c) 2023 dimtoneff） | リポジトリの LICENSE 原文 | 設計の参照のみ |
| sedthh/pyxelate | MIT（Copyright (c) 2021 Richard Nagyfi） | リポジトリの LICENSE 原文 | 設計の参照のみ |

## 3. 実装着手前のチェックリスト

`docs/SPEC.md` §2.5 の L-01〜L-13 を M0 で実施し、結果をここに書く。

| # | 項目 | 結果 | 確認日 | 確認者 |
|---|---|---|---|---|
| L-01 | `aseprite` の LICENSE 原文、最新版、依存 | 未実施 | | |
| L-02 | PixelOE の LICENSE 原文と依存のライセンス | LICENSE は確認済み。依存は未実施 | 2026-11-12 | Fable 5.2 |
| L-03 | pixeldetector / PixelArt-Detector を移植する場合の該当ファイルの表示 | 移植しない計画。LICENSE は確認済み | 2026-11-12 | Fable 5.2 |
| L-04 | Pillow、NumPy、pydantic、click、`mcp`、Starlette、Uvicorn、websockets と推移的依存 | 未実施 | | |
| L-05 | GUI に同梱する JS 依存と推移的依存 | 未実施 | | |
| L-06 | 同梱するフォント | 未実施 | | |
| L-07 | Lospec の利用規約（パレットの一括再配布） | 未確認（規約ページを取得できず）。同梱しない方針 | 2026-11-12 | Fable 5.2 |
| L-08 | Aseprite のファイル形式仕様ファイル自体の利用条件 | 未実施 | | |
| L-09 | Diffusers、stable-diffusion.cpp、InvokeAI の LICENSE 原文 | 未実施 | | |
| L-10 | 生成に使う各モデルカードのライセンス | 未実施 | | |
| L-11 | Oklab の係数と参照実装の利用条件 | 未実施 | | |
| L-12 | OpenAI の利用規約の現行版、Codex の画像生成の仕様 | 未実施 | | |
| L-13 | GIF（LZW）に関する制約がないこと | 未実施 | | |
