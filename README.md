# CyberSprite

AI エージェントが、ピクセル単位で正確にドット絵とドットアニメーションを作るための制作環境。
An agent-first pixel art and sprite animation environment. Pixel-perfect by construction.

> **現在の状態 / Status**: 仕様策定が完了し、実装はこれから始まる段階です。コードはまだありません。仕様書の正本は [`docs/SPEC.md`](docs/SPEC.md) です。
> Specification complete, implementation not started. There is no code yet. The source of truth is [`docs/SPEC.md`](docs/SPEC.md) (Japanese).

---

## これは何か

CyberSprite は、Claude Code や Codex などの AI エージェントから操作することを第一に設計した、ドット絵の制作環境です。人間用の GUI も用意しますが、GUI もエージェントと同じデータを、同じ操作で編集します。

- **ヘッドレスのコア（Python）**: インデックスカラーのドキュメントモデル、決定的なレンダラ、検証。
- **CLI と MCP ツール**: 座標と番号を明示する有界な操作。無制限のスクリプト実行ツールはありません。
- **変換パイプライン**: 生成モデルの出力や既存の画像を、グリッド検出 → 縮小 → パレットロック → 後始末 → 検証の手順で、正しいドット絵に直します。
- **GUI**: 白と水色の回路基板をモチーフにしたテーマ「Circuit White」。エージェントの変更を見守り、差分を確かめ、軽く手直しするための画面です。
- **`.aseprite` 互換**: 読み書きに対応します。

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
| `skills/` | エージェント向けの制作手順書 |
| `assets/` / `examples/` | 自作の UI アセットとサンプル |
| `third_party/` | 組み込み OSS の台帳とライセンス本文 |

各ディレクトリの役割と配置の理由は `docs/SPEC.md` §4.4 にあります。

## ライセンス方針

- CyberSprite は **Apache License 2.0** で公開します（[`LICENSE`](LICENSE)）。
- 組み込む OSS は、Apache-2.0 の成果物に組み込めるパーミッシブライセンス（MIT、BSD、Apache-2.0、ISC、Zlib、HPND など）のものに限ります。**GPL / LGPL / AGPL のコードは取り込みません。** 必須の依存にもしません。
- **画像生成モデルの重みは同梱しません。** 利用者が自分でダウンロードし、モデルのライセンスを確認・承諾したうえで使います。承諾とモデルの情報は、生成物の来歴に記録されます。
- 組み込み OSS の一覧は [`third_party/THIRD_PARTY.md`](third_party/THIRD_PARTY.md) にあります。

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

The specification (in Japanese) is in [`docs/SPEC.md`](docs/SPEC.md).
