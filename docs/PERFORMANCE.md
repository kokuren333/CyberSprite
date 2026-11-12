# 性能測定

## M3: CLI 起動（2026-11-12）

- Windows 11（10.0.26200）、CPython 3.12.10、uv の仮想環境。
- `uv run python tools/measure_cli_startup.py`。インストール済みの
  `.venv/Scripts/cybersprite.EXE` を各 7 回起動し、親プロセスの単調時計で起動から終了まで測定した。
  uv 自体の起動・同期時間は含めない。整数 ms への切り捨て。
- 独立した `python -X importtime -m cybersprite --version/--help` で import も検査した。
  **NumPy、pydantic、Pillow、aseprite の import は両方とも 0 件**。

| コマンド | 7 回の測定（ms） | 中央値 | 最大値 | 400 ms の目標 |
|---|---|---|---|---|
| `cybersprite --version` | 218, 266, 253, 246, 222, 257, 244 | 246 ms | 266 ms | 達成 |
| `cybersprite --help` | 234, 254, 269, 274, 267, 290, 240 | 267 ms | 290 ms | 達成 |

全体テスト終了後の測定値。同じコードでも、全体テストなどが動いていた回は
version が 438〜780 ms（中央値 505 ms）、help が 428〜527 ms（中央値 484 ms）だった。
負荷・ファイル I/O 競合の影響と推定するが、原因を個別に計測したものではない。
負荷のある環境で常に 400 ms 以下になる保証はしない。

切り分け用の 7 回測定では、何もしない Python が中央値 56 ms、
`python -m cybersprite --version` が 202 ms、実行ファイル版が 214 ms。
そのときの importtime は `cybersprite.cli` の累積 102,700 μs
（うち Click の累積 67,011 μs）。最上位ヘルプはスキーマ生成やレジストリ初期化を行わない。

Linux の実測は未実施（I-007）。他の性能目標は担当マイルストーンで追記する。
