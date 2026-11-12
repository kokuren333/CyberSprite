# INT-1 統合報告

2026-11-12、Windows / CPython 3.12.10、作業ブランチ `int-m356`。

## 実装

- M6 の未完了マージを解消し `f56ed83`（`M6: merge conversion pipeline integration (m6-pipeline)`）でコミット。M5/M6 の全機能と M3 の actor 優先規則を保持した。
- `core/sources.py` は M6 の検証済み API を正本とし、M5 の record_import も同じ読み書きへ接続。.aseprite の SRC1 とラスターの SRC2 を同じプロジェクトで確認した。
- CLI と MCP に export_policy を接続。CLI は cwd、MCP はサーバ root/allow-dir が基準。MCP の出力パスの二重解釈を修正し、範囲外・追加許可・root直下の出力を検査した。
- CLI の import image/source list/source show/convert/pipeline detect-grid を M6 本体へ接続。source ID だけの再試行を許可し、シート分割を pipeline.decode.split_sheet へ共通化した。
- MCP の standard/minimal とバッチ経由の cleanup を確認。画像 files と pipeline.palette.source、.aseprite の quantize.source を再帰検査。union の兄弟メタデータも維持する。
- `ops/descriptions.py`、M5/M6 の Field 説明、共通引数から ops describe/Click/MCP の説明を生成。sym の全アルファベット、透明の `.`、hex の2桁を明示した。
- `op --label` を追加。描画の pixels_written、undo/redo のプレビュー、preview --frames/--onion/--out、pixels --as/--rect、validate --frames は既実装を保持し実 CLI で回帰確認した。
- Q-PIX-01/02 に一意な可視葉レイヤーの ID を追加。複数層の点や重ね合わせを含む合成指摘は null のままとし、その理由は I-606 に記録した。
- MCP JSONL シナリオ1の export を必須化し、シナリオ2を追加。実書出しを復号したハッシュを期待値に固定。src/README、CLI/MCP文書と tools/README を更新した。

## 受け入れ

- [x] 未解決競合なし、M5/M6 の登録を保持（69 Op）。
- [x] 旧未実装前提テストを修正し、全 export サブコマンド、.aseprite/image import、source、convert、detect-grid の実処理を検査。
- [x] export --input は実 load_external を経由し、成功JSON・終了コード・実PNG・一時正本/来歴なしを検査。
- [x] MCP の入力・出力制限と追加許可、minimal での apply_ops cleanup を確認。
- [x] シナリオ1・2を in-process と stdio の実SDK Clientで再生。書出し PNG/GIF を復号照合。
- [x] 制作試験01の説明・ラベル・描画件数・履歴プレビュー・レイヤー指摘・CLIオプションを確認。
- [x] 手動 CLI 14呼出しの通し確認、書出し後の再復号、全フレームの画像確認。
- [ ] Linux 実行。この端末に環境がなく I-007 の既存方針どおり CI 待ち。
- [ ] 生成コーパス(d)による本来のシナリオ2。M9 待ちのため、今回の JSONL は自作非ドット入力で代用する。

## 検査

| コマンド | 結果 |
|---|---|
| `uv run pytest -q --tb=short` | **1150 passed, 2 skipped、214.96秒** |
| `uv run ruff check` | 成功 |
| `uv run ruff format --check` | 成功（128ファイル） |
| `uv run python tools/gen_schemas.py --check` | 成功、ドリフトなし |
| `uv run python tools/check_repository.py` | 成功 |
| `uv run python tools/check_licenses.py --include-dev --extra mcp` | 成功（41配布パッケージ） |
| `uv run mypy` | 既存78件、新規0件。統合直後106件から28件減少 |
| `uv run --extra mcp pytest tests/test_goldens.py tests/mcp/test_paths.py tests/mcp/test_int_formats_pipeline.py -q --tb=short` | 32 passed, 1 skipped |
| `git diff --check` | 成功 |

2件の全体スキップは Windows の権限により実シンボリックリンクを作れない既存試験。ジャンクション・文字列パス・許可ディレクトリ等の検査は実行して成功した。

mypy は統合マージ `f56ed83` のソースを作業ディレクトリ内へ複製して比較した。基準は **106件/29ファイル**、今回の結果は **78件/24ファイル**。ファイル・メッセージ・エラー種別の差分では新規エラー **0件**。M6単体報告の68件には M3/M4/M5 の統合後エラーが含まれていないため、今回の基準値とは異なる。残件は既存のレイヤー型の絞込み、動的スキーマ、形式アダプタ、MCP保存フックなど。

## ゴールデンの確認

- `python -m tests.e2e.replay --case scenario1 --case scenario2` は既存の `tools/update_goldens.py` を通る。シナリオ1の既存正本と画素は不変、実シート/GIFの exports.json を追加。シナリオ2は正本・画素・実PNGの3期待値を新規作成した。
- `tools/update_goldens.py --case frame_remapping --case transactions` で7 JSONを更新。更新前後の差分を確認し、変更は Q-PIX の where.layer が null から L1 になる箇所だけ。画素・PNG・ハッシュは不変だった。
- シナリオ1の実シート、GIFを復号した4枚、シナリオ2の書出しと段階2/5を開いた。意匠・画風の評価は行わず、フレーム数・配置・欠落・ピクセル同一性を確認した。

## 手動 CLI

再現: `uv run python tools/int_acceptance.py --out build/int-acceptance-<未使用名>`。
正本がある出力先は上書きせず失敗する。

new 16×16 → 幾何描画 → 4フレーム → walk タグ → validate → 全フレーム preview → json-hashシート/GIF/APNG/.aseprite export → .aseprite import → 正本・全画素比較 → コーパスPNGの exact import/export を実行した。

- hero の validate は error=0/warning=0/info=0。全 export の validation_ok/verified は true。
- .aseprite 再取り込みは revision 以外の正本が完全一致し、全フレームの画素も一致。
- 実シートの CSPX1 RGBA hash は `5a01f502e323508fd6c33a413efdc91a269189ef49289fbc0c2d6ab8b4b25d91`。GIF/APNGの4フレームはシナリオ1の各期待値と一致。復号したPNGコンタクトシートも3形式で同じバイト列になった。
- コーパス hero_16x16.png の exact 取り込み・書出しは元RGBAと完全一致。
- 再取り込み・コーパスの Q-SRC-02（各1警告）は、利用条件を推定せず unknown と記録する仕様どおりなので残した。コーパスの Q-LYR-03（初期空レイヤー）と Q-PIX-02（元の小成分）は情報であり、無損失の exact 試験として意図的に保持した。関門 override は使っていない。
- 実ファイルとCLIログは git 管理外の `build/int-acceptance/` に保存。最終コミット後の再実行先は `build/int-acceptance-final/`（同じ14呼出しと照合）。

## 判断・仕様・依存・参照

- 判断: **I-601〜I-608**。
- INT-1 の仕様変更: §9.4.1 に単発 op の --label を追記。マージ元M6に含まれる §11 の変更は M6報告のとおり。
- **新規依存なし**。pyproject.toml/uv.lock/third_party の台帳は変更していない。ライセンス監査は既存 I-012 の承認を使用し、許可方針を変更していない。
- 参照: リポジトリの AGENTS、SPEC、DECISIONS、実装報告、既存ソース、テスト、自作コーパスのみ。外部サイト・外部OSS実装・他製品のソースや素材は参照していない。
- 新たなビジュアル判断の TODO はない。既存M6の診断用格子線の意匠確認は Opus に引き継がれている。
- _private / _handoff は開かず、変更・コミットしていない。main への再統合はオーケストレーターの担当。
