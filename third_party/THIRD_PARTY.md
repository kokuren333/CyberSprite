# 組み込み OSS 台帳

方針と手順は `docs/SPEC.md` §2 にある。この台帳は、**実際に依存に追加した、または同梱したもの**を §1 に記録する。利用者導入・評価のみの対象は §5 に分け、配布用の承認と混同しない。

- 追加する前に、そのリポジトリの **LICENSE の原文**を開いて確認する。検索結果や二次情報だけで決めない。
- 許可するライセンス: MIT / MIT-0 / BSD-2-Clause / BSD-3-Clause / 0BSD / Apache-2.0 / ISC / Zlib / HPND（MIT-CMU）/ PSF-2.0 / Unlicense / CC0-1.0（MIT-0 と 0BSD は I-012 で明記）。アセットは OFL-1.1 も可。
- GPL / LGPL / AGPL / MPL のコードは入れない。既存 I-010 / I-012 の限定例外は SPEC §2.1 に明記したが、発注者の事後承認待ちである。モデルの重みは入れない。
- 同梱するものは、ライセンス本文を `third_party/licenses/<名前>.txt` に置き、`NOTICE` に帰属表示を足す。

## 1. 依存・同梱の記録

| 名前 | 版 | ライセンス（SPDX） | 入手元 | 確認日 | 確認方法 | 組み込み形態 | 確認者 |
|---|---|---|---|---|---|---|---|
| numpy | 2.3.4 | BSD-3-Clause（wheel 同梱物は §3 L-04 の注記） | PyPI | 2026-11-12 | インストール済み dist-info の LICENSE 原文（`docs/M1_LICENSE_REVIEW.md`） | 必須依存 | Codex（M1）/ オーケストレーター |
| pydantic | 2.12.3 | MIT | PyPI | 2026-11-12 | インストール済み dist-info の LICENSE 原文（`docs/M1_LICENSE_REVIEW.md`） | 必須依存 | Codex（M1）/ オーケストレーター |
| pydantic-core | 2.41.4 | MIT | PyPI | 2026-11-12 | インストール済み dist-info の LICENSE 原文（`docs/M1_LICENSE_REVIEW.md`） | 必須依存（推移） | Codex（M1）/ オーケストレーター |
| annotated-types | 0.8.0 | MIT | PyPI | 2026-11-12 | インストール済み dist-info の LICENSE 原文（`docs/M1_LICENSE_REVIEW.md`） | 必須依存（推移） | Codex（M1）/ オーケストレーター |
| typing-inspection | 0.4.5 | MIT | PyPI | 2026-11-12 | インストール済み dist-info の LICENSE 原文（`docs/M1_LICENSE_REVIEW.md`） | 必須依存（推移） | Codex（M1）/ オーケストレーター |
| typing-extensions | 4.16.0 | PSF-2.0 | PyPI | 2026-11-12 | インストール済み dist-info の LICENSE 原文（`docs/M1_LICENSE_REVIEW.md`） | 必須依存（推移） | Codex（M1）/ オーケストレーター |
| click | 8.3.0 | BSD-3-Clause | PyPI | 2026-11-12 | インストール済み dist-info の LICENSE 原文（`docs/M1_LICENSE_REVIEW.md`） | 必須依存 | Codex（M1）/ オーケストレーター |
| colorama | 0.4.6 | BSD-3-Clause | PyPI | 2026-11-12 | インストール済み dist-info の LICENSE 原文（`docs/M1_LICENSE_REVIEW.md`） | 必須依存（推移、Windows のみ） | Codex（M1）/ オーケストレーター |
| pytest | 8.4.2 | MIT | PyPI | 2026-11-12 | インストール済み dist-info の LICENSE 原文（`docs/M1_LICENSE_REVIEW.md`） | 開発のみ | Codex（M1）/ オーケストレーター |
| ruff | 0.14.1 | MIT | PyPI | 2026-11-12 | インストール済み dist-info の LICENSE 原文（`docs/M1_LICENSE_REVIEW.md`） | 開発のみ | Codex（M1）/ オーケストレーター |
| mypy | 1.15.0 | MIT（一部 PSF-2.0） | PyPI | 2026-11-12 | インストール済み dist-info の LICENSE 原文（`docs/M1_LICENSE_REVIEW.md`） | 開発のみ | Codex（M1）/ オーケストレーター |
| mypy-extensions | 1.2.0 | MIT | PyPI | 2026-11-12 | インストール済み dist-info の LICENSE 原文（`docs/M1_LICENSE_REVIEW.md`） | 開発のみ（推移） | Codex（M1）/ オーケストレーター |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | PyPI | 2026-11-12 | インストール済み dist-info の LICENSE 原文（`docs/M1_LICENSE_REVIEW.md`） | 開発のみ | Codex（M1）/ オーケストレーター |
| iniconfig | 2.3.1 | MIT | PyPI | 2026-11-12 | インストール済み dist-info の LICENSE 原文（`docs/M1_LICENSE_REVIEW.md`） | 開発のみ（推移） | Codex（M1）/ オーケストレーター |
| pluggy | 1.7.0 | MIT | PyPI | 2026-11-12 | インストール済み dist-info の LICENSE 原文（`docs/M1_LICENSE_REVIEW.md`） | 開発・ビルドのみ（推移） | Codex（M1）/ オーケストレーター |
| Pygments | 2.21.0 | BSD-2-Clause | PyPI | 2026-11-12 | インストール済み dist-info の LICENSE 原文（`docs/M1_LICENSE_REVIEW.md`） | 開発のみ（推移） | Codex（M1）/ オーケストレーター |
| hatchling | 1.27.0 | MIT | PyPI | 2026-11-12 | インストール済み dist-info の LICENSE 原文（`docs/M1_LICENSE_REVIEW.md`） | ビルドのみ | Codex（M1）/ オーケストレーター |
| trove-classifiers | 2026.9.21.13 | Apache-2.0 | PyPI | 2026-11-12 | インストール済み dist-info の LICENSE 原文（`docs/M1_LICENSE_REVIEW.md`） | ビルドのみ（推移） | Codex（M1）/ オーケストレーター |
| pathspec | 0.12.1 / 1.1.1 | MPL-2.0 | PyPI | 2026-11-12 | インストール済み dist-info の LICENSE 原文（`docs/M1_LICENSE_REVIEW.md`） | ビルドのみ（推移）。配布物に入らない例外（I-010） | Codex（M1）/ オーケストレーター |
| pillow | 13.0.0 | MIT-CMU | PyPI | 2026-11-12 | dist-info の LICENSE 原文（M0 / M4） | 必須依存（formats / pipeline の読み込みのみ） | オーケストレーター |
| mcp | 2.3.0 | MIT | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| mcp-types | 2.3.0 | MIT | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| anyio | 4.16.0 | MIT | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| attrs | 26.1.0 | MIT | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| cffi | 2.1.1 | MIT-0 | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| idna | 3.20 | BSD-3-Clause | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| jsonschema | 4.26.0 | MIT | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| jsonschema-specifications | 2025.9.1 | MIT | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| opentelemetry-api | 1.45.2 | Apache-2.0 | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| pycparser | 3.12 | BSD-3-Clause | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| PyJWT | 2.15.1 | MIT | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| python-multipart | 0.0.33 | Apache-2.0 | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| referencing | 0.37.0 | MIT | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| rpds-py | 2026.9.1 | MIT | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| sse-starlette | 3.7.0 | BSD-3-Clause | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| starlette | 1.10.0 | BSD-3-Clause | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| truststore | 0.10.5 | MIT | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| uvicorn | 0.54.0 | BSD-3-Clause | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| pywin32 | 312 | PSF-2.0 / BSD-3-Clause（未使用の adodbapi は LGPL-2.1。I-012 の例外） | PyPI | 2026-11-12 | dist-info の LICENSE 原文（`docs/M4_IMPLEMENTATION_REPORT.md`） | 任意 extra `mcp`（推移を含む） | Codex（M4）/ オーケストレーター |
| aseprite（mattt/aseprite-py） | 0.1.0 | Apache-2.0 | https://pypi.org/project/aseprite/0.1.0/ | 2026-11-12 | M5 の wheel / dist-info LICENSE 原文（I-401）、M10 の再確認。R1-DOC でも実 LICENSE を再読 | 必須依存、`formats/aseprite_io.py` のアダプタ越し。製品 Aseprite のコードではない | Codex（M5 / M10 / R1-DOC） |
| websockets | 16.0 | BSD-3-Clause | https://pypi.org/project/websockets/16.0/ | 2026-11-12 | L-04、M8_SERVER_REPORT の dist-info `licenses/LICENSE` 原文。R1-DOC で再読 | 任意 extra `gui` | Codex（M8-S / R1-DOC） |
| h11 | 0.16.0 | MIT | https://pypi.org/project/h11/0.16.0/ | 2026-11-12 | M4 / M8-S の `licenses/LICENSE.txt` 原文。R1-DOC で再読 | `mcp` / `gui` の推移的依存 | Codex（M4 / M8-S / R1-DOC） |
| httpcore2 | 2.16.0 | BSD-3-Clause | https://pypi.org/project/httpcore2/2.16.0/ | 2026-11-12 | M4 の `licenses/LICENSE.md` 原文。R1-DOC で再読 | 任意 extra `mcp` の推移的依存 | Codex（M4 / R1-DOC） |
| httpx2 | 2.16.0 | BSD-3-Clause | https://pypi.org/project/httpx2/2.16.0/ | 2026-11-12 | M4 の `licenses/LICENSE.md` 原文。R1-DOC で再読 | 任意 extra `mcp` の推移的依存 | Codex（M4 / R1-DOC） |
| GUI の JS 依存（直接・推移・ビルド・試験） | 全46件の版は別表 | MIT / Apache-2.0 / BSD / ISC 等、各行は別表 | npm、`gui/package-lock.json` | 2026-11-12 | [版・SPDX・原文ファイル・SHA-256](../gui/THIRD_PARTY_JS.md)、[全原文](../gui/LICENSES_JS.txt)、I-657 / I-802 | bundle に入る実行時依存と、開発時のみの依存を別表で追跡。配布用本文は `third_party/licenses/gui-bundle.txt` | Codex（M8-S / M10）、R1-H / R1-INT |
| CyberSprite 組み込みパレット（`src/cybersprite/data/palettes/`） | — | Apache-2.0（自作）/ CC0-1.0（機器・汎用の灰色と白黒） | 自作 | 2026-11-12 | 自作（`docs/design/PALETTES.md`） | 同梱データ | Opus（デザイン） |

### Pillow の版の方針（I-1941）

`pyproject.toml` の `pillow>=12` を維持する。開発・CI・受け入れ確認では `uv.lock` の **13.0.0** を使い、`uv sync --locked --extra mcp --extra gui` で再現する。ライブラリ利用者の依存解決には最低版を示し、読込専用の Pillow を他のアプリと共有できるようにする。監査済みの実体は上表の13.0.0であり、将来版の監査・決定性を承認した意味ではない。lock更新時は原文と同梱通知を再確認し、独立復号・取り込み・goldenを再検査する。PNG/GIF/APNG writerは自前で、入力復号の再現範囲はPillow版と環境指紋を含む SPEC §6.6 / §11.13 に従う。

表の欠落は R1-DOC で42件の実行時・開発・mcp/gui閉包と照合した。hatchling / trove-classifiers / pathspec はビルド用の既存記録である。L-04にあるsniffioは現在の閉包に含まれず、未採用の推移候補として扱う。

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
| L-02 | PixelOE 本体の LICENSE は Apache-2.0。R1-D1/D2で推移依存と実CPU環境を別監査 | 本体原文は確認済み。全同梱物は承認せず、利用者導入のみ（§5） | 2026-11-12 | オーケストレーター / Codex（R1-D1/D2） |
| L-03 | pixeldetector / PixelArt-Detector | 移植しない（既定の計画どおり、§11.3 を自前で実装） | 2026-11-12 | オーケストレーター（Opus 5.5） |
| L-04 | 原文で確認: NumPy（BSD-3-Clause。wheel は 0BSD・MIT・Zlib・CC0 の部品を含む。Windows / Linux の wheel は OpenBLAS（BSD-3-Clause）と gfortran ランタイム（GPL-3.0 + GCC ランタイム例外）を同梱）、Pillow（MIT-CMU）、pydantic / pydantic-core（MIT）、click（BSD-3-Clause）、`mcp` 2.3.0（MIT）、Starlette（BSD-3-Clause）、Uvicorn（BSD-3-Clause）、websockets（BSD-3-Clause）。推移的依存は PyPI の記載で確認: annotated-types（MIT）、typing-extensions（PSF-2.0）、typing-inspection（MIT）、anyio（MIT）、idna（BSD-3-Clause）、h11（MIT）、sniffio（MIT OR Apache-2.0）、colorama（BSD）。`mcp` の推移的依存（jsonschema、httpx2、opentelemetry-api ほか）は M4 で `tools/check_licenses.py` により全件確認する | **合格**（注: NumPy wheel 同梱の gfortran ランタイムは GCC ランタイム例外つきで、CyberSprite はそれを再配布しない。利用者が NumPy を導入する通常の形で問題ない） | 2026-11-12 | オーケストレーター（Opus 5.5） |
| L-05 | GUI に同梱する JS 依存 | **確認済み**。M8-Sで46件の原文・版・hashを別表へ記録（I-657）、M10で配布本文を収録（I-802）。R1-HはWindows CIを `--check` に変更、LinuxはOS固有配布物を別監査 | 2026-11-12 | Codex（M8-S / M10）、オーケストレーター（R1-H）、R1-DOC |
| L-06 | 同梱するフォント | **第三者フォントの同梱なし**。M8のシステムフォント指定（I-674、tokens.css）と、自作3×5字形（I-205 / I-1859）の記録を確認。R1-DOCで追跡対象woff/woff2/ttf/otf/bdfは0件、CSSの外部font-faceもなし。新たなフォントの採用承認ではない | 2026-11-12 | Opus（M8 / R1-GUI）、Codex（R1-DOC、配置の確認のみ） |
| L-07 | Lospec の利用規約（パレットの一括再配布） | 未確認のまま。同梱しない方針で回避（変更なし） | 2026-11-12 | オーケストレーター（Opus 5.5） |
| L-08 | Aseprite のファイル形式仕様ファイルの利用条件: 仕様はリポジトリの `docs/` にあり、リポジトリは EULA（「電子的な文書」を含む）の下にある。EULA の許諾・制限の条項（設置と利用、再配布の禁止、著作権表示）に、形式の実装を禁じる文言は見当たらない | 方針どおり（文面は写さず、事実だけを使う）。発注者への報告事項なし。商用展開の前に専門家の確認を勧める | 2026-11-12 | オーケストレーター（Opus 5.5） |
| L-09 | Diffusers（Apache-2.0）、stable-diffusion.cpp（MIT）、InvokeAI（Apache-2.0）: いずれも LICENSE 原文で確認 | **合格** | 2026-11-12 | オーケストレーター（Opus 5.5） |
| L-10 | Hugging Face のモデルカードの `license` 欄（API で取得）: SD 1.5 = creativeml-openrail-m、SDXL base / refiner 1.0 = openrail++、FLUX.1 [schnell] = apache-2.0（取得はアクセス承認制 `gated: auto`）、Pixel Art XL（LoRA）= creativeml-openrail-m、PixArt-α / Σ = openrail++ | 重みは同梱しない（方針どおり）。OpenRAIL 系は利用制限が付いて回るので、`docs/GENERATION.md` の例では FLUX.1 [schnell] を第一候補にし、OpenRAIL 系は利用者が承諾を記録したときだけ使う（§2.4 の承諾の仕組み）。LoRA とベースのライセンスは別々に記録する | 2026-11-12 | オーケストレーター（Opus 5.5） |
| L-11 | Oklab: 作者の解説ページに「コードはパブリックドメイン、MIT でも利用可」と明記 | **合格**。係数の出典を、係数を使う時点（M6）で `NOTICE` に書く | 2026-11-12 | オーケストレーター（Opus 5.5） |
| L-12 | OpenAI の利用規約: 入力の権利は利用者に残り、出力は利用者のもの（OpenAI の権利を、あるとすれば利用者に譲渡する。適用法の許す範囲で）。出力は他の利用者と同一・類似になりうる。規約ページは自動取得が拒否されたため、公式ページの検索結果と抜粋で確認した | 文書の記述（`docs/GENERATION.md`、来歴の `rights_note`）はこの理解で正しい。独占性がないこと、第三者の権利は別問題であることを手順書に書く。商用展開の前に、発注者が現行の規約を直接確認することを勧める | 2026-11-12 | オーケストレーター（Opus 5.5） |
| L-13 | GIF の LZW: 関連する特許は 2003〜2004 年に各国で失効済み（一般に知られた事実）。GIF89a の形式自体に利用制限はない | **合格** | 2026-11-12 | オーケストレーター（Opus 5.5） |

## 4. 名称の確認（M0、2026-11-12）

| 対象 | 結果 |
|---|---|
| PyPI `cybersprite` / `cyber-sprite` | 登録なし（空き） |
| GitHub の同名リポジトリ | `mushymane/cybersprite`（2021 年以降更新なし、説明なし）、`CyberSprite/CyberSprite`（説明なし、スター 0）。いずれも活動の目立たないリポジトリで、名前の使用を妨げる性質のものではない |
| 商標 | 簡易確認のみ（公開検索で目立つ同名製品は見当たらない）。商用展開の前に専門家の確認を勧める |

## 5. 利用者導入・評価のみ（修正ラウンド 1）

次の対象は **CyberSprite の宣言依存でも同梱物でもない**。本体の許諾と、推移依存・同梱バイナリ全体の許諾を分けて記録する。実行できたことを配布承認とは扱わない。R1-DOC は既存の原文確認記録を整理したもので、新しい例外を承認していない。

| 対象・評価版 | ライセンス | 確認方法と証拠 | 宣言しない理由・利用形態 |
|---|---|---|---|
| Pixel Art Fixer Python、ef376e57e1c272633ca2dbf5f29ec3fcf6596465 | MIT | D1が固定commitのLICENSE原文、D2が同原文を再読。下記監査表・runtime JSONに原文hash | OpenCV/SciPyと同梱物の条件を全体承認していない。利用者導入を遅延検出。Rust版は未評価 |
| proper-pixel-art 2.0.0 | MIT | D1の公式LICENSEとwheel、D2の配布物原文再読。下記監査表・runtime JSON | av/OpenCVのFFmpeg通知、tqdmのMPL等。画像APIだけを利用し、動画APIを呼ばない。初期倍率はアダプタ設定1（上流既定2） |
| PixelOE 1.0.0 | Apache-2.0 | D1の公式LICENSEとwheel原文、D2の実LICENSE再読。下記監査表・runtime JSON | OpenCV/PyTorch/任意Slangの推移依存・バイナリを全体承認していない。空のpixeloe extraを維持し、CPU経路を利用者導入で検出 |
| @xprite/pixelate 0.1.2、49c62fccaaa776281c522089b1c8d30b3028cbd5 | MIT | D1が公式npm tarballのLICENSE原文、D2が再確認。宣言runtime依存0件 | 中立ベンチの評価のみで製品への接続はない。全WASM・nativeツリーの監査完了とは扱わない |
| D2のCPU torch / torchvision 2.9.0+cpu / 0.24.0+cpu | 本体BSD-3-Clause、同梱通知は別 | 公式CPU wheelの原文・通知と実体hashをD2が導入前に確認。全60配布物の実体版・原文名・hashをruntime JSONに記録 | 外部3方式の評価環境だけ。全バイナリの配布承認ではない |
| Diffusers 0.35.2 / torch 2.8.0+cu128 と生成スタック | Diffusers Apache-2.0、torch本体BSD-3-Clause。閉包にCNRI-Python / MPL / LGPL / NVIDIA EULA | R1-F2でWindows CUDA全33配布物のdist-info LICENSE/LICENCE/COPYING原文とnative一覧を監査。全版・判定・確認箇所は [GENERATION](../docs/GENERATION.md)「R1-F2: 実体の依存監査」。tokenizers 0.22.2はwheel原文欠落、公式タグ原文の補足と区別 | **監査結論(b)**。regexのCNRI、certifi/tqdmのMPL、setuptoolsのvendor LGPL、torch同梱NVIDIA DLLが許可リスト外。空diffusers extraと利用者の別環境導入を維持。RTX 3080での実生成成功は配布承認ではない（I-1641） |
| ComfyUI（実サーバーの版は未確認） | GPL-3.0（REVIEW_1 §3.7の記録。R1-DOCでは本体LICENSE原文を再確認していない） | R1-F1は公式公開HTTP API文書と文書索引だけを確認。本体・ノードのソースは未参照。自作HTTPサーバーで契約試験 | 本体を依存・同梱・再実装しない。利用者が起動した外部HTTPサーバーへ、登録済みworkflowだけを送信。実ComfyUIは未試験 |

D1の固定URL・原文156ファイル等の記録は [PIXELIZE_LICENSE_AUDIT.md](../docs/reference/PIXELIZE_LICENSE_AUDIT.md) / [監査JSON](../docs/reference/pixelize_license_audit.json)。D2の実60配布物・CPU wheel・Xpriteは [pixelize_runtime_versions.json](../docs/reference/pixelize_runtime_versions.json)。D1のcuda-toolkitはwheel内原文がなく **未確認**、torchvisionの候補wheelにはmacOS版が含まれるためWindows承認とは扱わない。F2の原文hash・native一覧の全証跡は同報告に記載された非公開保存先にあり、ここへ複製していない。重みのライセンスはコードの許可リストから独立し、SDXLとPixel Art XL LoRAの固定revisionごとに条件を記録・承諾している。
