# examples/

自作のサンプルプロジェクト。どれも Claude Opus 5.5 の制作サブエージェントが **CyberSprite の Op だけで**作った（e2e 制作テストの成果物。経緯は `e2e-tests/` の各 REPORT.md）。ライセンスは Apache-2.0（このリポジトリと同じ）。

- どのサンプルも `validate` が `ok: true`（エラー・警告 0）で、書き出しの自己検査（`verified: true`）を通っている。
- 派生データ（`.cybersprite/` の履歴とプレビュー）は含めていない。正本は各 `project.json` だけである。

| ディレクトリ | 内容 | 見どころ |
|---|---|---|
| `runner-walk/` | 32×32 の横向きキャラクター。歩行 8 フレーム＋待機 2 フレーム、タグ `walk`（forward）と `idle`（pingpong）、レイヤー 6 枚 | リンクセル（影と胴体の上下動）、フレームごとの表示時間、タグ別の GIF とシート（json-hash）。e2e-03 |
| `meadow-tileset/` | 16×16 タイル 16 枚のタイルセットと、12×8 タイルの草原マップ（タイルマップレイヤー 2 枚） | 縁と角を 1 方向だけ描き、反転フラグ（x / y / d）で使い回す。タイルセットの書き出しとデータ。e2e-04 |
| `slime-import/` | 生成画像風に劣化させた 347px の入力を、変換パイプラインで 32×32 のスライムにし、手で仕上げたもの | `source/SRC1/` の来歴（`manifest.json`：提供元・プロンプト・ライセンス）、段階画像、パイプライン報告。格子を `target` で指定した理由は e2e-05 の報告を参照 |

## 試し方

```
cd examples
uv run cybersprite -p runner-walk/runner.csprite info --include layers,tags
uv run cybersprite -p runner-walk/runner.csprite preview --frames tag:walk --layout strip
uv run cybersprite -p meadow-tileset/meadow.csprite export image --out meadow.png --scale 2
uv run cybersprite -p slime-import/slime.csprite source show SRC1
```

書き出しはカレントディレクトリの配下にだけ書ける（`docs/CLI.md`）。サンプルを編集して試すときは、ディレクトリごと別の場所にコピーしてから行う。
