# tests/

テストの置き場所。仕様は `docs/SPEC.md` §13。全体検査は `uv sync --locked --extra mcp --extra gui` の後に `uv run pytest -q --tb=short` を使う。

| ディレクトリ | 内容 | 仕様の節 |
|---|---|---|
| `unit/` | 単体テスト | — |
| `golden/` | ゴールデンファイル（入力プロジェクトと期待出力） | §13.5 |
| `vectors/` | 言語に依存しないテストベクタ（ラスタライズ、合成、色距離、ディザ行列）。GUI の TypeScript 実装も同じものを使う | §13.5、付録 B |
| `roundtrip/` | `.aseprite` などの往復テスト | §5.9.2 |
| `pipeline/` | 変換パイプラインのテスト、較正コーパス（`corpus/`）、`CALIBRATION.md` | §11.9 |
| `mcp/` | MCP ツールの契約テスト、パス制限のテスト | §10 |
| `e2e/` | ツール呼び出しの列を再生する通しテスト | §13.6 |

## 規則

- テスト用の画像とファイルは、**自分たちで作ったもの**だけを使う。他製品のサンプルやテスト資産を入れない。CC0 の素材は出典を記録すれば可。
- ゴールデンファイルの期待値は `tools/update_goldens.py` でだけ更新し、差分を必ず目で見る。
- CI は Windows と Linux の両方で走らせる。全環境で同じ期待値に一致することが、決定性の証明になる。

## 通しシナリオ

`e2e/scenarios/scenario1`〜`scenario5` に呼出JSONL、説明、期待正本と実書き出しの画素ハッシュを置く。1〜3と5は実MCP Clientのin-process / stdio、4は実GUIサーバのWebSocketとCLI子プロセスを交互に使う。5は自作P-11ファイルを使い、`.aseprite`を再復号して§5.9.2の正本同値と全フレームの合成画素を検査する。依存不足を理由にこれらをskipしない。

```powershell
uv run pytest tests/e2e/test_scenario1.py tests/e2e/test_scenario2.py tests/e2e/test_scenario3.py tests/e2e/test_scenario4.py tests/e2e/test_scenario5.py -q
uv run python -m tests.e2e.replay --case scenario4 --case scenario5
```

後者の期待値書込も `tools/update_goldens.py` に委譲する。失敗を消す目的で上書きせず、実画像・差分・画素配列を確認する。実ファイルを残す確認は `tools/m10_acceptance.py`。シナリオ2の生成(d)代替と、Windowsの権限による別の2試験のskipはKNOWN_ISSUES参照。
