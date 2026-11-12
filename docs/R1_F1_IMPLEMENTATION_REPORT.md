# R1-F1 — 生成入力・BYOW・ComfyUI 実装報告

作業日: 2026-11-12。ブランチ `fixr1-f1`。実装コミット `568ff08`、生成試験の起動期限調整・検証記録 `321d9b4`。

## 1. 実装

- `config.py`、`generate/models.py`、`generate/licenses.py`: BYOW メタデータの登録、実体 SHA-256、登録日時、ベース参照と循環の検査、人間用 `gen register-model` / `gen models`。既存設定・コメントを保ち、重複名を拒否する。OpenRAIL・NC・未知条件のバッジはアダプタとベースの両方を表示する。承諾は実体ハッシュに結び付ける。
- `generate/contracts.py` / `service.py`、`ops/generation.py`: `use`（既定canvas）と `rights_note`、モデル条件のsnapshot、GUI用 `model_terms` と平文 `message`、`W_MODEL_TERMS`。生成はsource保存までで正本を変えず、配置は既存の `import_image` に委ねる。
- `core/source_terms.py` / `quality.py`: 配置済みモデル・アダプタ・ベースの商用条件がyesでない場合のQ-SRC-04。未知ベースと旧来歴の条件不明も報告する。未配置の参照原画には出さない。
- `generate/comfyui.py` / `registry.py`: 登録済みAPIワークフロー専用の標準ライブラリHTTPバックエンド。POST送信、履歴ポーリング、画像取得、期限と応答上限、明示bind、型・登録名・既存scalar入力の検査、workflowファイルの承諾、埋込み済みJSONとハッシュの保存・再送照合、`gen comfy-inspect`。
- `tests/generate/test_byow.py` / `test_comfyui.py`: 自作データと自作HTTPサーバーによる新規54件。既存command/Diffusersの呼出し署名は維持した。
- `tests/unit/test_quality.py`: 新しいsource規則を共通の検出・非検出試験にも追加し、配置済みunknown/yesと未配置を検査した。

連携先への格納契約: 用途は **`source.params.use`**、生成時の条件は **`source.params.model_registry`**（`adapters` と `bases` を含む）。ワークフローは **`source.params.workflow.path/sha256`**、登録元ハッシュは `workflow_file_sha256`、埋込み後は `workflow_sha256`。サーバー側の重みハッシュを推測していない。

## 2. 受け入れ基準

| 項目 | 状態 | 確認 |
|---|---|---|
| ダミーファイルのCLI登録・ハッシュ・バッジ | 合格 | 実CLI子プロセス、Unicode・引用符・既存設定・重複名・ディレクトリの固定ハッシュベクタ |
| use / rights_noteの来歴 | 合格 | design/canvas、GUI共通結果、source保存だけで正本なし |
| Q-SRC-04 | 合格 | モデル・アダプタ・ベース・未知ベースと全yes、実配置 |
| 偽ComfyUI経由の生成と来歴 | 合格 | 実HTTP、送信グラフと保存JSON、画像とworkflowの実ハッシュ、再送 |
| 未登録・任意JSON・未対応引数の拒否 | 合格 | 登録名・bind・入力型・HTTP失敗・期限・画像枚数/寸法/復号・応答上限 |
| 全体試験 | 再実行中 | 共通品質fixtureへのQ-SRC-04追加後、`uv run pytest -q --tb=short` を再実行中 |

## 3. 検証

- `uv run pytest tests/generate -q --tb=short`: **75 passed（334.57秒）**。旧経路21件、新規54件。
- 初回の生成試験は **66 passed / 2 failed（727.17秒）**。どちらも既存 `fake_command.py` のPython子プロセスが試験設定の30秒を超えた `TimeoutExpired`。このfixtureだけ120秒に広げて上記75件の成功を確認した。製品既定とTimeoutExpired注入試験は変えていない（I-1609）。この実行時間の差を性能改善の値として扱わない。
- `uv run pytest -q tests/generate/test_comfyui.py -k invalid_server_urls --tb=short`: **7 passed / 24 deselected（16.45秒）**。最終75件にも含む。
- 最初の全体試験: **1458 passed / 1 failed / 2 skipped（3537.21秒）**。新規Q-SRC-04がsourceなしの汎用品質fixtureへ自動列挙された1件だけが失敗した。既存Q-SRC-01〜03と同じsource用試験へ正例・負例を追加した（I-1610）。製品コードとgoldenは変更していない。
- 修正後 `uv run pytest -q tests/unit/test_quality.py --tb=short`: **34 passed（1.52秒）**。全体試験は再実行中。skip2件は既存のWindowsシンボリックリンク作成権限によるもの。
- `uv run ruff check .`、`uv run ruff format --check .`: 成功（178ファイル）。
- `uv run mypy src/cybersprite/core src/cybersprite/ops`: 成功（37ファイル）。
- `uv run python tools/gen_schemas.py --check`、`uv run python tools/check_repository.py`、`git diff --check`: 成功。golden更新・スキーマ生成物の変更は0件。
- 実CLI子プロセス7呼出しで登録→一覧→検査→生成→配置→validate→PNG書出しを実行した。`validation_ok` / `verified` はtrue。最終PNGを独立復号して元の8×6 RGBAテスト配列と完全一致し、元画像とworkflowのハッシュも再照合した。Q-SRC-04は試験workflowのcommercial_use=unknownを意図どおり警告したため保持した。
- 実ファイルと記録: git管理外 `build/r1-f1-manual/` の `export.png`、`summary.json`、source内の `workflow.json`。

## 4. 判断記録

`docs/DECISIONS.md` **I-1601〜I-1610**。

## 5. 仕様変更

SPEC §2.4 / §9.6 / §10.1.2 / §12 / §13.2 / 付録Cを局所更新し、§12.7を追加した。ローカル実体限定のI-703を本文に合わせ、BYOW・2出口・権利メモ・Q-SRC-04・ComfyUI段階1/2を明記した。`docs/GENERATION.md` と `src/README.md` も更新した。

## 6. 依存とライセンス

新規依存 **0件**。pyproject / uv.lock / 第三者台帳の変更なし。新しい依存の原文ライセンス確認対象もない。重み・製品コード・外部ワークフロー・他製品アセットを同梱していない。

## 7. 既知の不足・ビジュアル判断

- GUIには利用条件バッジ・commercial_use・平文をデータとして返す。具体的な表示と参照原画の並列プレビューはOpus向けTODO。ビジュアル判断は行っていない。
- 登録したVAE/ControlNet/LoRAを単体生成パイプラインとして実行できることは保証しない。GPUの読み込み方式・依存監査はR1-F2の範囲。

## 8. 参照したもの

リポジトリの仕様・判断・両R1レビュー、および [ComfyUI公式公開HTTPルート文書](https://docs.comfy.org/development/comfyui-server/comms_routes) と [公式文書索引](https://docs.comfy.org/llms.txt)。公開API事実だけを利用し、GPL製品のソース・ノード実装・外部ワークフローは開いていない。コード転用なし。PROVENANCE_LOGへ記録済み。

## 9. Design forks decided

| 判断 | 選択と理由 | 根拠 |
|---|---|---|
| I-1601 | 既存TOMLを保持して追記、重複名拒否、登録済みベースかunknownと循環拒否。既存設定とBYOWを共存させる | Fable §3.6 H-21 |
| I-1602 | useと条件はparamsへ固定。旧source schemaを維持し、設定変更で過去の条件を変えない | Fable §3.6 H-21 |
| I-1603 | バッジと申告値を併記し、アダプタとベース両方を読む。不明ベースも要確認とし、LoRA単体で判断しない | Fable §3.6 H-21、発注者BYOW補足 |
| I-1604 | modelを登録workflow名、paramsを対応付け済みキーに限定。要求を黙って無視せず、任意グラフ送信を塞ぐ | Fable §3.7 H-22 |
| I-1605 | 元ファイルと埋込み後のハッシュを分離し、承諾は元ファイル、再送は保存JSONにも拘束。重みハッシュとの誤認を避ける | Fable §3.7 H-22 |
| I-1606 | 1POSTがcount枚を返す方式、HTTP/全体期限、応答上限、直接接続。期限切れの全体interruptを送らず他者のジョブを止めない | Fable §3.7 H-22の未規定細部 |
| I-1607 | 正負接続が分かるときだけinspectが提案し、曖昧さを候補として残す。人間の確認を置換しない | Fable §3.7 H-22 |
| I-1608 | ローカル実体限定とrights_noteを仕様へ合わせ、GPU作業を分離。既存の安全な入力経路とAPIを維持する | Fable §3.6 H-21、R1-14 |
| I-1609 | 生成試験の子プロセスfixture期限だけ120秒。起動速度の変動を正しさの条件にしない | R1共通の全試験要件、実測TimeoutExpired |
| I-1610 | Q-SRC-04を共通のsource用検出・非検出fixtureへ追加。sourceなしの汎用fixtureでは検出できないため | SPEC §13.2/§13.6、全体試験の診断 |

Codex §6は本件の生成入力に対する別案を示していないため、対応する設計はFable §3.6/§3.7と発注者の具体指示に従った。

## 10. Deferred / not done

- 実ComfyUIサーバーでの確認と、実GPUでの生成は未実行。前者はオーケストレーターへ、後者とGPU依存監査はR1-F2へ引き継ぐ。
- Linuxはローカル実行環境がなく未実行（I-007）。Windows上で可搬なパス・標準ライブラリHTTP・自作fixtureを検証した。
- ノードグラフの再実装、ComfyUI本体・ノード・他者ワークフローの同梱はH-22段階3として対象外。
- main統合とGUIの見た目はオーケストレーターの工程。

## 11. Before/after numbers

性能改善の対象ではなく、新規生成経路のため比較対象なし。既存性能の改善・目標達成を主張しない。試験の実行秒数は上記の検証記録であり、レビューの性能再現条件・3回中央値による前後測定ではない。実GPUや実ComfyUIの性能を表すものでもない。
