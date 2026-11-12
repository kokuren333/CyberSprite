# tools/

開発用スクリプトの置き場所。

| スクリプト（予定） | 内容 | 仕様の節 | 着手 |
|---|---|---|---|
| `check_licenses.py` | 依存と推移的依存のライセンスを調べ、許可リスト外があれば失敗する。`_private` / `_handoff` が追跡されていないことも検査する | §2.2、§3.4 | M1 |
| `gen_schemas.py` | pydantic のモデルから `schemas/` を生成する | §4.4 | M1 |
| `update_goldens.py` | ゴールデンファイルの期待値を更新する（差分は必ず目で見る） | §13.5 | M1 |
| `gen_color_tables.py` | 付録 B の色変換表を生成する（規範は生成された表そのもの） | 付録 B | M6 |
| `calibrate_pipeline.py` | 自作17作品から整数拡大・JPEG・補間・誤格子を作り、非ドット12枚と合わせて測定し、しきい値と較正表を保存する | §11.9 | M6 |
| `benchmark_pipeline.py` | 1024×1024入力から、段階画像の保存・再復号検査までの時間を3回測る | §13.8 | M6 |
| `smoke_pipeline.py` | 等倍・整数拡大・JPEGの3件を直接 Op で取り込み、配置後の PNG と段階画像を `.cybersprite/m6-review/` に残す | §11、§13.7 | M6 |

実行は `uv run python tools/<スクリプト>.py`。較正は期待値の更新器ではなく測定器である。ゴールデンの更新は引き続き `update_goldens.py` だけを使い、PNG・画素・ハッシュの変更を確認する。
