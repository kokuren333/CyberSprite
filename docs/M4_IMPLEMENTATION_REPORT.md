# M4 実装報告

2026-11-12 / `m4-mcp` / Codex。**本体実装済み、依存採用の判断待ちのため M4 未完了。**

## 1. 実装

- `src/cybersprite/mcp/server.py`: `serve(**options)`、低水準 SDK Server、全59登録済み Op の公開、standard/minimal、read-only、生成・プラグインの制限、進捗、JSON と画像の封筒。stdio とループバック限定のステートレス Streamable HTTP。
- `contracts.py`: Op の pydantic 定義から入出力スキーマ・注釈を生成。共通引数、成功・失敗の oneOf、仕様書順の一覧。
- `paths.py`: schema metadata によるパス再帰検査。バッチ・配列・union・入れ子、実体パス、Windows の大小文字・ジャンクション、root 相対の結果。
- `execution.py`: ContextVar で限定したコア保存フック、外側のプロジェクトロック、期限検査、失敗時の正本・履歴・プレビューのバイト復元。Op 以外のモデル変更経路は追加していない。
- `__main__.py`: `python -m cybersprite.mcp`。M3 の CLI は変更していない。
- `tests/mcp/`: 契約、実 SDK Client、HTTP、パス脱出、ロールバック、容量、進捗、依存未導入時の skip。
- `tests/e2e/`: JSON Lines 再生、シナリオ1、正本バイト列と CSPX1 画素ハッシュ。期待値の書込みは既存 `tools/update_goldens.py` に委譲。
- `tools/check_licenses.py`: `--extra` と、集約メタデータに隠れる不許可の同梱原文の検出。許可一覧は変更していない。
- [MCP.md](MCP.md): Claude Code / Codex の登録、プロファイル、パス、呼出例。

## 2. 受け入れ状況

| 項目 | 状況 |
|---|---|
| 登録済み全ツールの inputSchema / outputSchema / annotations | 成功、59 Op |
| standard / minimal / read-only / generation / plugin gating | 成功。minimal は現在実装済みの9ツール |
| `..`、絶対外部パス、入力・出力の metadata、バッチ、union | 拒否・再帰検査のテスト成功 |
| Windows ジャンクション | 実物を作成して脱出を拒否 |
| シンボリックリンク | この端末の作成権限がないため1テスト skip |
| 成功・失敗の封筒、JSON テキスト先頭、画像、isError、容量 | 成功 |
| 期限超過時にコミットを残さない | 保存前・保存後・プレビュー中の期限超過で正本と履歴の全ファイルを照合済み |
| stdio 実 SDK Client でシナリオ1 | 非書出し7呼出しを完走 |
| Streamable HTTP 実 SDK Client | 別クライアントによる再接続・読取も成功 |
| SDK の固定・mcp extra・ライセンス検査合格 | **保留／不合格**。下記参照。pyproject と uv.lock は変更していない |
| M5 書出し2工程 | 定義済み。Op 未登録時に明示的に skip。統合時は自動で有効化 |

stdio の実行内容は `new_project`（r0）→ `apply_ops`（r1）→ `add_frame`（r2）→ `apply_ops`（r3）→ `add_tag`（r4）→ `validate`（r4、エラー・警告0）→ `render_preview`（r4、画像4枚）。16×16・4フレーム・walk タグを確認し、最終正本3652バイトと4フレームのハッシュが期待値に一致した。全フレームの最終プレビューも確認済み。fixture の幾何形状を作例として採用する美術判断は行っていない。

## 3. 検証

| コマンド | 結果 |
|---|---|
| `uv run --no-sync pytest -q --tb=short` | 648 passed, 2 skipped、Windows / Python 3.12.10 |
| `uv run --no-sync pytest tests/mcp tests/e2e/test_scenario1.py -q --tb=short` | ライセンス検査テスト追加前に24 passed, 2 skipped |
| `uv run --no-sync pytest tests/mcp/test_paths.py tests/mcp/test_execution.py tests/mcp/test_mcp_license_audit.py -q --tb=short` | 最後のパス補正後、14 passed, 1 skipped |
| `uv run --no-sync pytest tests/mcp/test_mcp_license_audit.py tests/unit/test_tools.py -q --tb=short` | 25 passed |
| `uv sync --locked` 後の MCP 契約・シナリオ収集 | SDK に依存する5モジュールがエラーなく skip。検証後 SDK 2.3.0 を環境へ再導入 |
| `uv run --no-sync ruff check` / `ruff format --check` | 成功 |
| `uv run --no-sync python tools/gen_schemas.py --check` | 成功 |
| `uv run --no-sync python tools/check_repository.py` / `git diff --check` | 成功 |
| `uv run --no-sync python tools/check_licenses.py --extra mcp` | **失敗**。現在 mcp extra は空であり、既存 Pillow 13.0.0 の MIT-CMU で失敗 |
| `tools.check_licenses.audit(['mcp==2.3.0'])` | **失敗**。cffi の MIT-0 と pywin32 同梱の LGPL-2.1 を検出 |

`--no-sync` は、採用が未承認の SDK を git 管理外の `.venv` にのみ導入して検証したために必要。通常の `uv sync` では SDK が外れ、MCP 契約テストは skip する。ゴールデンは専用更新器で初回生成し、revision・セルの行データ・タグ・全ハッシュを確認した。

## 4. 判断と仕様変更

I-351〜I-358 を [DECISIONS.md](DECISIONS.md) に記録。`docs/SPEC.md` の変更なし。`third_party/THIRD_PARTY.md` と来歴台帳は依頼どおり変更していない。

## 5. 依存とライセンス

新しい**採用済みの依存はない**。検証環境では `mcp==2.3.0` を導入した。以下は Windows の SDK 依存閉包30 distribution。全件についてインストール済み `*.dist-info` の LICENSE / COPYING 原文を開き、複数ファイルを持つ cryptography・pywin32 では各原文も確認した。メタデータだけを根拠に許可していない。

| distribution | 版 | 原文による SPDX・所見 | 確認ファイル（dist-info 配下） |
|---|---|---|---|
| annotated-types | 0.8.0 | MIT | licenses/LICENSE |
| anyio | 4.16.0 | MIT | licenses/LICENSE |
| attrs | 26.1.0 | MIT | licenses/LICENSE |
| cffi | 2.1.1 | **MIT-0、許可一覧外** | licenses/LICENSE |
| click | 8.3.0 | BSD-3-Clause | licenses/LICENSE.txt |
| colorama | 0.4.6 | BSD-3-Clause | licenses/LICENSE.txt |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | licenses/LICENSE、LICENSE.APACHE、LICENSE.BSD |
| h11 | 0.16.0 | MIT | licenses/LICENSE.txt |
| httpcore2 | 2.16.0 | BSD-3-Clause | licenses/LICENSE.md |
| httpx2 | 2.16.0 | BSD-3-Clause | licenses/LICENSE.md |
| idna | 3.20 | BSD-3-Clause | licenses/LICENSE.md |
| jsonschema | 4.26.0 | MIT | licenses/COPYING |
| jsonschema-specifications | 2025.9.1 | MIT | licenses/COPYING |
| mcp | 2.3.0 | MIT | licenses/LICENSE |
| mcp-types | 2.3.0 | MIT | licenses/LICENSE |
| opentelemetry-api | 1.45.2 | Apache-2.0 | licenses/LICENSE |
| pycparser | 3.12 | BSD-3-Clause | licenses/LICENSE |
| pydantic | 2.12.3 | MIT | licenses/LICENSE |
| pydantic_core | 2.41.4 | MIT | licenses/LICENSE |
| PyJWT | 2.15.1 | MIT | licenses/LICENSE |
| python-multipart | 0.0.33 | Apache-2.0 | licenses/LICENSE.txt |
| pywin32 | 312 | 使用する win32 / com は BSD-3-Clause。ただし **未使用の adodbapi に LGPL-2.1 の原文を同梱**。集約 PSF 分類だけでは許可できない | licenses/win32/License.txt、com/License.txt、adodbapi/license.txt、ほか下記 |
| referencing | 0.37.0 | MIT | licenses/COPYING |
| rpds-py | 2026.9.1 | MIT | licenses/LICENSE |
| sse-starlette | 3.7.0 | BSD-3-Clause | licenses/LICENSE |
| starlette | 1.10.0 | BSD-3-Clause | licenses/LICENSE.md |
| truststore | 0.10.5 | MIT | licenses/LICENSE |
| typing_extensions | 4.16.0 | PSF-2.0 | licenses/LICENSE |
| typing-inspection | 0.4.5 | MIT | licenses/LICENSE |
| uvicorn | 0.54.0 | BSD-3-Clause | licenses/LICENSE.md |

pywin32 の残りの原文は `licenses/com/win32comext/mapi/src/MAPIStubLibrary/LICENSE`（MIT）、`licenses/pythonwin/License.txt`（BSD-3-Clause）、`licenses/pythonwin/Scintilla/License.txt`（Scintilla 固有の許諾文、正確な SPDX 同定は保留）、`licenses/pythonwin/pywin/idle/LICENSE.txt`（PSF 系歴史的許諾文）。LGPL の原文確認を超えて adodbapi のソースは開いていない。

回避候補として導入した cffi 2.0.0 はメタデータが MIT だが LICENSE 原文は MIT No Attribution だったため採用しなかった。既存の Pillow 13.0.0 も原文・License-Expression とも MIT-CMU で、現在の一覧にはない。許可一覧の緩和や LGPL 同梱物の例外は設定していない。

## 6. 残件・制約

- 依存採用方針の判断後に `mcp==2.3.0` の extra・lockfile を追加し、オーケストレーターが台帳を整備してライセンス検査を再実行する必要がある。
- M5 統合後にシートと GIF の実書出しを確認する。再生ハーネスは `validation_ok` / `verified` と、実ファイルを復号した画素ハッシュを検査する。
- 期限は Python の実行境界と保存境界で検知する。ネイティブ呼出しがブロックすると復帰まで応答が遅れる。任意のネイティブ処理の強制中断を保証するプロセス隔離は未実装。
- Windows 別ボリュームのパスは root 相対で結果を表せない場合に、root の変更を促す E_PATH_NOT_ALLOWED を返す。
- Linux はこの端末にないため未実行。シンボリックリンクの実テストは権限がある CI で実行が必要。ジャンクションは実施済み。
- Claude Code / Codex 自体からの接続は未実施。今回のタスクで指定された実 SDK Client の stdio 接続は実施済み。
- fixture を公開作例として扱う場合の見た目の判断は Opus に委ねる。デザイン・アイコン・GUI の判断はしていない。

## 7. 参照

- リポジトリの AGENTS / SPEC / DECISIONS / IMPLEMENTATION_PROGRESS / src/README と既存のコア・Op・検査・ゴールデン更新器。
- インストール済み MCP SDK 2.3.0 の `server/lowlevel/server.py`、`server/context.py`、`server/session.py`、`server/runner.py`、stdio・HTTP transport、Client / session、および mcp-types のモデル原文。コード片は転記していない。
- [SDK 2.3.0 の PyPI 情報](https://pypi.org/project/mcp/2.3.0/)と[公式仕様改訂の説明](https://blog.modelcontextprotocol.io/posts/2026-07-28/)。
- OpenAI Docs スキルに従って確認した[公式 Codex MCP 設定](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)、ローカルの `codex --help` と `claude mcp add --help`。
- 他製品の GPL / プロプライエタリなソース、アイコン、作例、テスト素材は参照していない。来歴ログへの転記はオーケストレーターに依頼する。
