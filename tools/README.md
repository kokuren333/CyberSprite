# tools/

開発用スクリプトの置き場所。

| スクリプト | 内容 | 仕様の節 | 着手 |
|---|---|---|---|
| `check_licenses.py` | 依存と推移的依存のライセンスを調べ、許可リスト外があれば失敗する。`_private` / `_handoff` が追跡されていないことも検査する | §2.2、§3.4 | M1 |
| `gen_schemas.py` | pydantic のモデルから `schemas/` を生成する | §4.4 | M1 |
| `update_goldens.py` | ゴールデンファイルの期待値を更新する（差分は必ず目で見る） | §13.5 | M1 |
| `gen_color_tables.py` | 付録 B の色変換表を生成する（規範は生成された表そのもの） | 付録 B | M6 |
| `calibrate_pipeline.py` | 自作17作品から整数拡大・JPEG・補間・誤格子を作り、非ドット12枚と合わせて測定し、しきい値と較正表を保存する | §11.9 | M6 |
| `benchmark_pipeline.py` | 1024×1024入力から、段階画像の保存・再復号検査までの時間を3回測る | §13.8 | M6 |
| `int_acceptance.py` | CLI 子プロセスで16×16・4フレーム・タグ・検証・シート/GIF/APNG/.asepriteを書き出し、往復とコーパスPNGを再復号照合。`--out` は未使用のディレクトリを指定する | §13.6 | INT-1 |
| `m7_acceptance.py` | 実 CLI でタイルセット作成・8反転配置・リンク・共有タイル修正・PNG/タイルセット/.aseprite出力を実行する。全検証デルタと書出し自己検査、実PNGの再復号を確認し、`--out` の未使用ディレクトリへ画像と記録を残す（`uv run python -m tools.m7_acceptance --out build/m7-review`） | §10.10、§13.6 | M7 |
| `fix2_acceptance.py` | runner.csprite を一時ディレクトリへコピーして、実CLIのタグstrip・全フレームgrid・タグ循環onion・生RGB背景を確認する。正本のバイト不変と実PNGの再復号を検査し、画像とsession.jsonを残す（`uv run python -m tools.fix2_acceptance --out build/fix2-review`、出力先は未使用） | §6.7、§10.4 | FIX-2 |
| `m7_cases.py` | 自作の非対称L字工学ベクタと変換・番号付替えのゴールデン入力だけを作る。期待値は `update_goldens.py` で生成する | §13.5 | M7 |
| `smoke_pipeline.py` | 等倍・整数拡大・JPEGの3件を直接 Op で取り込み、配置後の PNG と段階画像を `.cybersprite/m6-review/` に残す | §11、§13.7 | M6 |
| `build_release.py` | npm ci、JSライセンス照合、CLIによるアイコン書き出し、GUIビルド、uv build、wheel内の静的ファイル・データ・ライセンス本文の照合 | §16.4 M10 | M10 |
| `verify_release.py` / `release_probe.py` | wheelをリポジトリ外の新規venvへextras付きで導入し、CLI・両版のMCP stdio・認証付きGUIを実起動。`uv run python tools/verify_release.py dist/cybersprite-0.1.0-py3-none-any.whl` | §16.4 M10 | M10 |
| `bench.py` | §13.8の全6目標。`uv run python -m tools.bench --out build/m10-bench.json`。マイクロ秒の反復値と環境を保存。プロセス起動はCLIだけに含める | §13.8 | M10 |
| `m10_acceptance.py` | GUI/CLI混在シナリオ4と実stdioの.asepriteシナリオ5を再生し、画像と記録を残す。`uv run python -m tools.m10_acceptance --out build/m10-review`（未使用先） | §13.6 | M10 |

実行は `uv run python tools/<スクリプト>.py`。較正は期待値の更新器ではなく測定器である。ゴールデンの更新は引き続き `update_goldens.py` だけを使い、PNG・画素・ハッシュの変更を確認する。
