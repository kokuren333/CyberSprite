# R1-A1: 書き出し保護・GUIポリシー・取り込み予行（2026-11-12）

## 実装

- `formats/common.py` の preflight で、全形式の展開後・実体解決後の出力先を検査する。正本、source、.cybersprite と大小文字別名、リンクを保護する。複数出力は全件検査してから書く。`formats/export.py` の6 exporterが同じ境界へ project root を渡す。
- `ops/__init__.py` は export の履歴同期を成功後へ移し、拒否時は外部変更の履歴も書かない。mutate/query の経路は変更していない。
- `server/app.py` は export_policy に root/allow-dir を束縛する。形式層の root 相対出力パスを応答アダプタへ正しく渡す。GUIの展開前の正本検査は export に使わず、共通境界へ集約した。
- `ops/ingest.py` は通常予行と本実行で capture、パイプライン、受理判定、prepared、transact/place を共用する。予行でもレイヤー存在・祖先のロック・フレーム拡張・正規化・構造検査を通す。原画一時コピーと報告は previews/dry のみ。source と履歴は保存しない。
- `pipeline_only` は dry_run 専用。GUI pipeline.preview は `pipeline_accepted` と `checked=[pipeline]` を返し、would_commit を返さない。`core/registry.py` の import_image 出力スキーマにも追加フィールドを宣言した。
- `core/quality.py` は明示されたメモリ内source_manifestを、manifest.jsonが未保存でも検査する。初回の予行でもsource指標・来歴警告を落とさず、本実行と検証デルタが一致する。
- 新規回帰: `tests/unit/test_r1_a1_exports.py`、`tests/pipeline/test_r1_a1_dry_run.py`、`tests/server/test_server.py`。既存の予行試験に必須の来歴を追加した。

## 受け入れ基準

- [x] レビュー R1-01 の CLI/MCP/GUI 3面を再現し、すべて E_PATH_NOT_ALLOWED。正本の先頭8bytesは `7b0a202022666f72`（JSON）のまま。正本・履歴bytes不変。
- [x] 直接名・テンプレート・大小文字・hardlink、source/history の予約領域を3面で検査。symlinkも同じ試験を持つ（Windowsの作成権限がなければskip）。
- [x] 画像・シート/tilesetのJSON・パレット・.aseprite・GIF/APNGで共通境界を検査。後続出力が不正なら先行出力/既存ファイルを変更しない。
- [x] GUIのcwd外rootと外部allow-dirへの実WebSocket export.run、および許可外拒否、返却パスを検査。
- [x] レビュー R1-08 のロックされたレイヤーで、予行・本実行とも E_LAYER_LOCKED。存在しないレイヤー、祖先ロック、フレーム不足/上限、構造違反、来歴欠落、初回作成、source再利用も検査。
- [x] SPEC §4.2、§6.2.2、§8.8、§10.1.3、§10.12、§14.6、付録Cを更新。新しいエラーコードは不要。
- [ ] 全体テストgreen。共有環境で32分以上実行して未完だったため停止し、未確認として残した。初回の既存GUI試験にもタイムアウトが残る（下記）。

## 検証

- `uv run --no-sync pytest tests/pipeline/test_r1_a1_dry_run.py tests/unit/test_r1_a1_exports.py -q --tb=short`: **46 passed / 3 skipped（832.94秒）**。skipはWindowsでsymlinkを作成する権限がない3面。hardlinkは全件実行した。
- 最後のsource_manifest修正後、同ファイルの `test_dry_run_places_once_in_memory_without_lock_or_source` / `test_source_reuse_dry_run_preserves_source_and_history` / `test_transparent_only_baseline_uses_same_palette_override` を再実行: **3 passed（23.41秒）**。初回の予行/本実行の検証デルタも完全一致を確認した。46件に含まれる3件の再確認であり、別の49件ではない。
- `uv run --no-sync ruff check .`、`ruff format --check .`: 成功（176ファイル）。
- `uv run --no-sync mypy src/cybersprite/core src/cybersprite/ops`: 成功（36ファイル）。
- `uv run --no-sync python tools/gen_schemas.py --check`、`tools/check_repository.py`: 成功。
- GUIを含む初回 `uv run --no-sync pytest tests/pipeline/test_r1_a1_dry_run.py tests/server/test_server.py -q --tb=short`: **26 passed / 3 failed / 1 error（322.43秒）**。新規GUI RPC 6件は成功した。既存 `test_http_token_origin_host_and_static` の起動待ち5秒、`test_rpc_read_render_prefs_and_lifecycle` / `test_mutations_actor_undo_redo_and_notifications` / `test_shared_watch_and_undo_to_revision` の応答待ち3秒でタイムアウトした。待ち時間は変更していない。
- 全体 `uv run pytest -q --tb=short`: 2026-11-12 14:18 JSTに開始し、32分以上経過しても未完だったため、自分のpytestプロセスとその子だけを停止した。完走・最終件数・全体greenは確認できていない。実行環境は物理メモリ約15.8 GiB、空き約0.41→0.33 GiBだった。上記タイムアウトと遅延の観測を記録するもので、負荷だけが原因だと断定したり、未実行部分に回帰がないと保証したりはしない。

手動再現: `uv run --no-sync python tools/r1_a1_acceptance.py`。3面の保護、GUI cwd外root、dry_run/本実行のロック拒否を確認した。実出力PNGを独立して再復号し、2×2の画素寸法を確認した。記録と実ファイルはgit管理外の `build/r1-a1-review/`。

ゴールデンの変更なし。新規依存なし。既存の `uv.lock` に従って環境を同期した。第三者台帳は未編集。外部資料、他製品のソース・素材・文言は参照していない。参照したものは本リポジトリのAGENTS、SPEC、DECISIONS、実装進捗、module map、両レビューと既存コード/テストのみ。

## Design forks decided

| 判断 | 選択と理由 | 根拠 |
|---|---|---|
| I-1001 | formats preflightに集約。case-sensitive環境でも予約領域のcase別名を拒否し、OS間で揃える。canonicalに加えsource/historyのhardlinkも保護する | Fable §1 R1-03、Codex §2 R1-01 |
| I-1002 | 拒否されるexportの履歴同期を行わない。外部編集済みの場合もbytes不変を保証する | Fable §1 R1-03 |
| I-1003 | GUIに同じexport_policyを束縛し、出力の返却パスもroot基準に揃える | Fable §1 R1-15、Codex §2 R1-06 |
| I-1004 | 通常予行は配置まで実行し、GUI変換専用経路は別名の判定を返す。通常予行も来歴検証を要求する | Fable §1 R1-26、Codex §2 R1-08 |
| I-1005 | 原画の一時コピーを予行領域にだけ置き、メモリ内来歴の実体検証に使う。既存冪等キーの予行は新しいコミットを主張しない | §6.2.2と上記R1-08の整合 |
| I-1006 | 明示されたメモリ内manifestを初回にも使い、予行の検証デルタを本実行に揃える | Fable R1-26、Codex R1-08、SPEC §6.2.2/13.4 |

Fable §3 / Codex §6には本作業の3件を上書きする設計分岐はない。判断記録はすべて `docs/DECISIONS.md` に1件1行で記録した。

## Deferred / not done

- **全体greenの確認と既存GUIタイムアウトの解消/再確認は未完。** 共有環境の空きメモリが0.33〜0.41 GiBの状態で全体実行が32分以上未完だったため停止した。負荷の低い環境で、上記4件と全体コマンドを再実行する必要がある。実装済みと受け入れ完了を区別する。
- Linuxでの実行はこのWindows環境では不可。既存CI/統合工程で確認する。
- OSが許可しないsymlink作成の試験はskipし、hardlinkと実体パスの検査を実行する。
- 入力上限・仕事量予算、GUI再生、journal/MCPの永続化方式は指定どおり対象外。
- デザイン・アート・GUIのビジュアル判断を要する変更なし。main統合はオーケストレーターが行う。

## Before/after numbers

性能改善を目的とした変更や改善の主張はないため、該当なし。上記の試験時間は性能比較値ではない。
