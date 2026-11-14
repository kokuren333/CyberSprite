# CyberSprite

AI エージェントが、ピクセル単位で正確にドット絵とドットアニメーションを作るための制作環境。
An agent-first pixel art and sprite animation environment. Pixel-perfect by construction.

> 🎮 **ブラウザで触れるデモ / Hands-on demo**: https://kokuren333.github.io/CyberSprite/ — インストール不要で GUI を試せます（デモ版は保存・書き出し等に制限があります）。実際の制作は、リポジトリをクローンしてローカル環境で。

> **現在の状態 / Status**: 1.0 より前の開発版です。CLI、MCP、ローカル GUI、画像変換、タイルマップ、アニメーション、`.aseprite` 入出力と、配布物の検証（M0〜M10）を実装し、修正ラウンド 1 と 2 回目のレビューを終えました。CI は Windows と Linux（Ubuntu）の Python 3.12 / 3.13、GUI は Windows と Ubuntu 24.04 で実行しています。PyPI などへの配布はまだです。既知の不足は [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md)。
> Pre-1.0 development version. Milestones M0–M10 are implemented and CI runs on Windows and Linux (Python 3.12 / 3.13; GUI on Windows and Ubuntu 24.04). Not yet published to a package registry. See the known issues before use. The source of truth is [`docs/SPEC.md`](docs/SPEC.md) (Japanese).

---

## これは何か

CyberSprite は、Claude Code や Codex などの AI エージェントから操作することを第一に設計した、ドット絵の制作環境です。人間用の GUI も、エージェントと同じデータを、同じ操作で編集します。

- **ヘッドレスのコア（Python）**: インデックスカラーのドキュメントモデル、決定的なレンダラ、検証。
- **CLI と MCP ツール**: 座標と番号を明示する有界な操作。無制限のスクリプト実行ツールはありません。
- **変換パイプライン**: 生成モデルの出力や既存の画像を、グリッド検出 → 縮小 → パレットロック → 後始末 → 検証の手順で、正しいドット絵に直します。
- **GUI**: 白と水色の回路基板をモチーフにしたテーマ「Circuit White」。エージェントの変更、検証デルタ、履歴とプレビューを表示し、同じ Op で編集できます。
- **書き出し**: PNG、GIF、APNG、スプライトシートと JSON、パレット、タイルセット、`.aseprite`。書き出したファイルを読み直して検証します。

## インストールと起動

Python 3.12 以上と uv を用意します。公開レジストリへの配布はまだ行っていません。配布用 wheel がある場合、リポジトリや Node.js は実行に不要です。

```powershell
uv tool install "dist/cybersprite-0.1.0-py3-none-any.whl[mcp,gui]"
cybersprite --version
```

ソースから使う場合は Node.js 24 / npm も必要です。

```powershell
uv sync --locked --extra mcp --extra gui
uv run python tools/build_release.py
uv run python tools/verify_release.py dist/cybersprite-0.1.0-py3-none-any.whl
```

`build_release.py` は `gui/` で `npm ci` → ライセンス照合 → CLI によるアイコン書き出しを含む `npm run build` → `uv build` の順に実行し、wheel のデータとライセンス本文を検査します。`uv build` 単独は GUI を作らないため、リリースにはこの手順を使ってください。検証器はリポジトリ外に新しい venv を作って wheel と extras を導入し、CLI・MCP・GUI を起動します。

## エージェントの最初の操作

MCP クライアントには、次のコマンドを stdio サーバとして登録します。root はプロジェクトと入出力を許可するディレクトリです。

```powershell
cybersprite mcp serve --root C:/sprites
# 同じサーバのモジュール起動
python -m cybersprite.mcp --root C:/sprites
```

`new_project` → `get_info` / `get_palette` → 描画 Op または `apply_ops` → `validate` → `render_preview` → 書き出し、の順で使います。各ツールのスキーマを読み、フレームは 0 始まり、色はパレット番号で指定します。`--profile minimal` はバッチを中心とする小さなツール集合です。詳しくは [`docs/MCP.md`](docs/MCP.md)。

同じ制作を CLI でも実行できます。ソース環境では各コマンドに `uv run` を付けます。

```powershell
cybersprite new demo.csprite --size 16x16 --palette gray-4
cybersprite -p demo.csprite op rect layer=L1 frame=0 x=2 y=2 w=12 h=12 color=1
cybersprite -p demo.csprite validate
cybersprite -p demo.csprite preview --frames all --layout strip --out preview.png
cybersprite -p demo.csprite export image --out final.png --compression stored
cybersprite gui demo.csprite --no-browser
```

変更の検証デルタを読み、プレビューと最終ファイルを開いて確かめます。書き出し結果の `validation_ok` と `verified` はともに true が必要です。GUI は表示された URL の `#` 以降も含めて開きます。CLI と GUI の交互編集は変更通知で反映され、構造操作の競合時は再読込が必要です。出力先は起動時の cwd 配下に置きます。

## 文書の案内

| 文書 | 内容 |
|---|---|
| [`AGENTS.md`](AGENTS.md) | 開発と制作の原則、クリーンルーム、確認のループ |
| [`docs/CLI.md`](docs/CLI.md) / [`docs/MCP.md`](docs/MCP.md) | コマンド、引数、接続、パス制限 |
| [`docs/GUI.md`](docs/GUI.md) | GUI の起動、認証、RPC、開発 |
| [`docs/GENERATION.md`](docs/GENERATION.md) | 外部生成コマンド、モデル承諾、来歴。生成した画像は取り込みが別途必要 |
| [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) / [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md) | 実測値と未対応項目 |
| [`docs/SPEC.md`](docs/SPEC.md) / [`docs/DECISIONS.md`](docs/DECISIONS.md) | 正本の仕様と実装上の判断 |
| [`tools/README.md`](tools/README.md) / [`tests/README.md`](tests/README.md) | 検査、較正、唯一のゴールデン更新手順 |

制作手順は `skills/`、自作の作例は `examples/` にあります。複数の手順を組み合わせたワークフローは `skills/workflows/` にあり、生成 → 変換 → 修正 → アニメーションを1体のスプライトで通す `koitan_workflow` などを含みます。生成モデルの依存は既定では導入しません。`diffusers` extra は監査保留で空の予約名です（I-014）。

## ピクセルパーフェクトの保証

設計の根幹は次の 7 つです（詳細は `docs/SPEC.md` §1.2）。

1. **インデックスカラーが正本。** ピクセルはパレット番号でしか存在できません。パレットにない色は構造上入り込めません。
2. **パレットロック。** 量子化は取り込み時に 1 回だけ。以後の編集はパレット内の色だけを受け付けます。
3. **整数幾何のみ。** 座標も拡大も整数。拡大はニアレストネイバーだけです。
4. **決定論的レンダリング。** 同じプロジェクトから同じピクセルが得られます。CI でゴールデンファイルと照合します。
5. **全トランザクションの後に検証。** 変更のたびに検証が走り、結果の差分が返ります。
6. **差分とプレビューのループ。** 変更のたびにプレビュー画像と、前の状態とのピクセル差分が得られます。
7. **来歴の分離。** 生成・取り込みした元画像は、提供元・プロンプト・ライセンスとともに `source/` に隔離します。キャンバスに入るのは変換パイプラインの出力だけです。

## リポジトリの構成

| パス | 内容 |
|---|---|
| `docs/SPEC.md` | 仕様書の正本 |
| `docs/REQUIREMENTS_NOTES.md` | 他のソフトウェアから得た設計判断の記録（何を採り、何を採らなかったか） |
| `docs/UPSTREAM_REPORT.md` | 要件定義フェーズの完了報告 |
| `AGENTS.md` | 開発と制作のコンテキスト（エージェント向け） |
| `src/cybersprite/` | Python パッケージ（コア、Op、形式、パイプライン、生成、CLI、MCP、GUI サーバ） |
| `gui/` | GUI フロントエンド（TypeScript） |
| `schemas/` / `tests/` | JSON Schema、テスト、ゴールデンファイル、言語非依存のテストベクタ |
| `skills/` | エージェント向けの制作手順書とワークフロー（`skills/workflows/`） |
| `assets/` / `examples/` | 自作の UI アセットとサンプル |
| `third_party/` | 組み込み OSS の台帳とライセンス本文 |

各ディレクトリの役割と配置の理由は `docs/SPEC.md` §4.4 にあります。

## ライセンス方針

- CyberSprite は **Apache License 2.0** で公開します（[`LICENSE`](LICENSE)）。
- 組み込む OSS は、Apache-2.0 の成果物に組み込めるパーミッシブライセンス（MIT、BSD、Apache-2.0、ISC、Zlib、HPND など）のものに限ります。**GPL / LGPL / AGPL のコードは取り込みません。** 必須の依存にもしません。
- **画像生成モデルの重みは同梱しません。** 利用者が自分でダウンロードし、モデルのライセンスを確認・承諾したうえで使います。承諾とモデルの情報は、生成物の来歴に記録されます。
- 組み込み OSS の一覧は [`third_party/THIRD_PARTY.md`](third_party/THIRD_PARTY.md) にあります。
- リポジトリには、画像生成器で作った、利用条件が `unknown` の試験用画像があります（`tests/pipeline/corpus/generated/` と `e2e-tests/07-ds-turnaround/`）。これらは Apache-2.0 の対象に含めず、wheel と sdist にも入れません。詳細は [`NOTICE`](NOTICE)。

## クリーンルーム開発

CyberSprite は、Aseprite の機能と操作体系を参考にしていますが、**Aseprite、LibreSprite、その他の製品のソースコード、アイコン、画像アセット、文書の文面を一切写していません。** 参照するのは、公開されているファイル形式仕様・CLI 文書などから読み取れる機能の事実だけです。名前、アイコン、画面の文言はすべて独自です。工程の詳細は `docs/SPEC.md` §3、参照の記録は [`docs/reference/PROVENANCE_LOG.md`](docs/reference/PROVENANCE_LOG.md) にあります。

CyberSprite は Aseprite および Igara Studio とは無関係の、独立したプロジェクトです。

## 開発体制

要件定義と仕様書は Fable 5.2、実装の統括は Claude Opus 5.5、デザインとビジュアルは Claude Opus 5.5、決定的な実装とテストは Codex が担当します（`docs/SPEC.md` §16）。コントリビューションの受け付け方は、最初のリリースまでに定めます。

---

## English summary

CyberSprite is an open-source (Apache-2.0) pixel art and sprite animation environment designed to be operated by AI agents first, with a thin human GUI on top of the same data and the same operations.

- **Indexed colour is the source of truth.** A pixel is a palette index; an off-palette colour cannot exist.
- **Deterministic core.** Integer-only geometry and compositing; the same project produces the same pixels on every platform.
- **Bounded agent surface.** A CLI and MCP tools with explicit coordinates, idempotency classes, and a validation delta after every transaction. No arbitrary script execution.
- **Conversion pipeline.** Generated or imported rasters go through grid detection, downsampling, palette lock, cleanup and validation before they may touch the canvas. Provenance is recorded.
- **Clean-room.** Aseprite is referenced for features only, through its public documentation. No code, icons, assets or documentation text from Aseprite, LibreSprite or any other product is used. CyberSprite is not affiliated with Aseprite or Igara Studio.
- **No bundled model weights.** Only permissively licensed code is incorporated; no GPL/LGPL/AGPL code.
- **Generated test images with unknown usage terms** (`tests/pipeline/corpus/generated/`, `e2e-tests/07-ds-turnaround/`) are not offered under Apache-2.0 and are not in the wheel or sdist; see [`NOTICE`](NOTICE).

The specification (in Japanese) is in [`docs/SPEC.md`](docs/SPEC.md).

Install a supplied wheel with `uv tool install "path/to/cybersprite-0.1.0-py3-none-any.whl[mcp,gui]"`.
Run `cybersprite mcp serve --root <workspace>` for agents or `cybersprite gui <project> --no-browser`
for the local GUI. The wheel includes the GUI; Node is needed only when building from source.
Use `uv run python tools/build_release.py` for releases and `tools/verify_release.py <wheel>`
to test a fresh installation. Every export is decoded again and checked against the core renderer.
