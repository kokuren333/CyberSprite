# MCP サーバ

現状: M1〜M9を統合済み。`mcp==2.3.0` は optional extra として固定され、I-012 の既存承認方針に従うライセンス監査を通る。過去の依存採用保留は解消済み。標準プロファイルは77ツール（生成2 Opを有効にすると79）、minimal は仕様の13 Opを公開する。

`uv sync --extra mcp` で任意依存を導入する。CLI の `cybersprite mcp serve` または次の直接起動が使える。

```powershell
uv run --extra mcp python -m cybersprite.mcp --root C:/sprites
```

Claude Code への登録例（`C:/repos/CyberSprite` は実際のリポジトリへ置き換える）:

```powershell
claude mcp add --transport stdio cybersprite -- uv --directory C:/repos/CyberSprite run --extra mcp python -m cybersprite.mcp --root C:/sprites
```

Codex は `~/.codex/config.toml` に次を追加する。[公式の MCP 設定説明](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)も参照。

```toml
[mcp_servers.cybersprite]
command = "uv"
args = ["--directory", "C:/repos/CyberSprite", "run", "--extra", "mcp", "python", "-m", "cybersprite.mcp", "--root", "C:/sprites"]
tool_timeout_sec = 310
```

生成を有効にする場合はクライアント側の `tool_timeout_sec` も1810秒以上にする。

`python -m cybersprite.mcp` と `cybersprite mcp serve` は同じサーバを起動する。HTTP は `--transport http --port 8765` で起動し、接続先は `http://127.0.0.1:8765/mcp`。待受はループバック限定、HTTP セッションはステートレス。

`standard` は import_image/list_sources/get_source/cleanup_pixels と各 export を含む登録済みの組み込みツールを仕様書の掲載順に公開する。`--profile minimal` は13種類の小さな集合（未実装の Op は除く）を公開し、個別編集を `apply_ops` にまとめる。`--read-only` は query だけに制限する。生成は `--enable-generation`、プラグインは `--allow-plugin-op 名前` による明示指定が必要で、バッチ内でも同じ制限を適用する。

相対パスは入出力とも `--root` 基準。別の場所が必要なら `--allow-dir C:/inputs` を追加する。シンボリックリンク・ジャンクションの実体を検査し、結果のパスも root 基準の `/` 区切りで返す。allow-dir が root の外なら `../inputs/...` のようになる。

呼出例:

```json
{"name":"new_project","arguments":{"project":"hero.csprite","width":16,"height":16}}
{"name":"apply_ops","arguments":{"project":"hero.csprite","expect_revision":0,"idempotency_key":"first-line","preview":"inline","ops":[{"op":"line","args":{"layer":"L1","frame":0,"x0":2,"y0":2,"x1":10,"y1":2,"color":1}}]}}
{"name":"validate","arguments":{"project":"hero.csprite"}}
```

返り値は `structuredContent` と先頭の JSON テキストで同じ封筒を返す。インライン PNG は後続の画像ブロック。失敗は `isError: true` と具体的な `error.code`・`hint` を持つ。テキストは UTF-8 で256 KiBまで。

既定期限は60秒、取り込み300秒、生成1800秒。Python の実行境界と保存境界で期限を検査し、期限超過・封筒の容量超過時にはコアの保存経路で変更を復元する。復元までプロジェクトロックを保持し、処理中のスレッドを放置して応答しない。ネイティブ処理がブロックした場合は Python へ戻るまで応答が遅れる。この制約はプラグインでも同じ。

追加 Op のパス引数は `Field(json_schema_extra={"x-cybersprite-path":"input"})` または `"output"` で宣言する。配列・入れ子も再帰検査する。M2 と既知の後続組み込み Op には MCP アダプタが互換メタデータを補完する。任意の実行ツールを公開してはならない。

検査:

```powershell
uv run --extra mcp pytest tests/mcp tests/e2e/test_scenario1.py tests/e2e/test_scenario2.py -q
uv run --extra mcp python tools/check_licenses.py --extra mcp
```

シナリオ1・2の期待値更新は `uv run --extra mcp python -m tests.e2e.replay --case scenario1 --case scenario2`。書込みは `tools/update_goldens.py` を通る。変更した正本とハッシュを確認してからコミットする。fixture は幾何形状による工学用テストベクタであり、作例として公開する前の見た目の判断は Opus が担当する。


import_image の `files`（単体文字列・配列）と `pipeline.palette.source` のファイル参照にも root/allow-dir 制限を適用する。
拒否された入力は source に保持され、正本がまだなくても list_sources/get_source で確認できる。minimal では個別の cleanup_pixels は apply_ops 内から呼び出す。
書き出し先と返却される `result.files[].path` はともにサーバ root 基準。許可範囲外の出力はファイル作成前に拒否する。

シナリオ2は既存の自作非ドット画像による代用で、生成コーパス(d)は未入手。JSONLは拒否→設定変更→合格→手直し→書出しを実際のSDK Client（in-process/stdio両方）で実行する。シナリオ3はタイル、5は自作.asepriteのimport→編集→export→読戻し同値性を検査する。1〜5にskip/xfailはない。

M10の新規venv試験は、2025-06-18では `initialize` / `notifications/initialized` の後に `tools/list`、2026-07-28では `server/discover` と各要求の `params._meta` にprotocolVersion/clientCapabilities/clientInfoを付けた `tools/list` を実行する。2026版は初期化ハンドシェイクを使わない。moduleとCLI両入口を `tools/verify_release.py <wheel>` で確認できる。
