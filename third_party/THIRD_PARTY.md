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
| L-01 | `aseprite`（mattt/aseprite-py）: リポジトリの LICENSE 原文は Apache-2.0。PyPI の最新版は 0.1.0、Python 3.12 以上。依存は extra `image` の Pillow（10.1 以上）だけ | **合格** | 2026-11-12 | オーケストレーター（Opus 5.5） |
| L-02 | PixelOE: LICENSE 原文は Apache-2.0（再確認）。依存（PyTorch ほか）のライセンスは、extra を作る時点（M6）で確認する | LICENSE は合格。依存は M6 で確認 | 2026-11-12 | オーケストレーター（Opus 5.5） |
| L-03 | pixeldetector / PixelArt-Detector | 移植しない（既定の計画どおり、§11.3 を自前で実装） | 2026-11-12 | オーケストレーター（Opus 5.5） |
| L-04 | 原文で確認: NumPy（BSD-3-Clause。wheel は 0BSD・MIT・Zlib・CC0 の部品を含む。Windows / Linux の wheel は OpenBLAS（BSD-3-Clause）と gfortran ランタイム（GPL-3.0 + GCC ランタイム例外）を同梱）、Pillow（MIT-CMU）、pydantic / pydantic-core（MIT）、click（BSD-3-Clause）、`mcp` 2.3.0（MIT）、Starlette（BSD-3-Clause）、Uvicorn（BSD-3-Clause）、websockets（BSD-3-Clause）。推移的依存は PyPI の記載で確認: annotated-types（MIT）、typing-extensions（PSF-2.0）、typing-inspection（MIT）、anyio（MIT）、idna（BSD-3-Clause）、h11（MIT）、sniffio（MIT OR Apache-2.0）、colorama（BSD）。`mcp` の推移的依存（jsonschema、httpx2、opentelemetry-api ほか）は M4 で `tools/check_licenses.py` により全件確認する | **合格**（注: NumPy wheel 同梱の gfortran ランタイムは GCC ランタイム例外つきで、CyberSprite はそれを再配布しない。利用者が NumPy を導入する通常の形で問題ない） | 2026-11-12 | オーケストレーター（Opus 5.5） |
| L-05 | GUI に同梱する JS 依存 | M8 で実施 | | |
| L-06 | 同梱するフォント | M8 で実施（既定は自作ビットマップフォントとシステムフォント） | | |
| L-07 | Lospec の利用規約（パレットの一括再配布） | 未確認のまま。同梱しない方針で回避（変更なし） | 2026-11-12 | オーケストレーター（Opus 5.5） |
| L-08 | Aseprite のファイル形式仕様ファイルの利用条件: 仕様はリポジトリの `docs/` にあり、リポジトリは EULA（「電子的な文書」を含む）の下にある。EULA の許諾・制限の条項（設置と利用、再配布の禁止、著作権表示）に、形式の実装を禁じる文言は見当たらない | 方針どおり（文面は写さず、事実だけを使う）。発注者への報告事項なし。商用展開の前に専門家の確認を勧める | 2026-11-12 | オーケストレーター（Opus 5.5） |
| L-09 | Diffusers（Apache-2.0）、stable-diffusion.cpp（MIT）、InvokeAI（Apache-2.0）: いずれも LICENSE 原文で確認 | **合格** | 2026-11-12 | オーケストレーター（Opus 5.5） |
| L-10 | 生成に使う各モデルカードのライセンス | M9 で実施（重みは同梱しない方針は変わらない） | | |
| L-11 | Oklab: 作者の解説ページに「コードはパブリックドメイン、MIT でも利用可」と明記 | **合格**。係数の出典を、係数を使う時点（M6）で `NOTICE` に書く | 2026-11-12 | オーケストレーター（Opus 5.5） |
| L-12 | OpenAI の利用規約の現行版、Codex の画像生成の仕様 | M9 で実施 | | |
| L-13 | GIF の LZW: 関連する特許は 2003〜2004 年に各国で失効済み（一般に知られた事実）。GIF89a の形式自体に利用制限はない | **合格** | 2026-11-12 | オーケストレーター（Opus 5.5） |

## 4. 名称の確認（M0、2026-11-12）

| 対象 | 結果 |
|---|---|
| PyPI `cybersprite` / `cyber-sprite` | 登録なし（空き） |
| GitHub の同名リポジトリ | `mushymane/cybersprite`（2021 年以降更新なし、説明なし）、`CyberSprite/CyberSprite`（説明なし、スター 0）。いずれも活動の目立たないリポジトリで、名前の使用を妨げる性質のものではない |
| 商標 | 簡易確認のみ（公開検索で目立つ同名製品は見当たらない）。商用展開の前に専門家の確認を勧める |
