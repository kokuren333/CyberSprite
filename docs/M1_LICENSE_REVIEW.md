# M1 依存ライセンスの確認

2026-11-12、Codex / M1。確認方法は `.venv/Lib/site-packages/<配布名>.dist-info/` 内の LICENSE（`licenses/` 配下を含む）の原文を開く方法。外部実装のソースコードは参照していない。下表はオーケストレーターが `third_party/THIRD_PARTY.md` へ転記するための報告であり、同台帳自体は今回変更していない。

| 配布名 | 版 | 本体の SPDX | 形態・原文確認 |
|---|---|---|---|
| numpy | 2.3.4 | BSD-3-Clause | runtime。LICENSE.txt の本体と同梱物の記載を確認。下記の未承諾事項あり |
| pydantic | 2.12.3 | MIT | runtime。licenses/LICENSE |
| pydantic_core | 2.41.4 | MIT | runtime 推移。licenses/LICENSE |
| annotated-types | 0.8.0 | MIT | runtime 推移。licenses/LICENSE |
| typing-inspection | 0.4.5 | MIT | runtime 推移。licenses/LICENSE |
| typing_extensions | 4.16.0 | PSF-2.0 | runtime 推移。licenses/LICENSE |
| click | 8.3.0 | BSD-3-Clause | runtime。licenses/LICENSE.txt |
| colorama | 0.4.6 | BSD-3-Clause | Windows runtime 推移。licenses/LICENSE.txt |
| pytest | 8.4.2 | MIT | dev。LICENSE |
| ruff | 0.14.1 | MIT | dev。licenses/LICENSE（同梱由来の帰属記載も含む） |
| mypy | 1.15.0 | MIT（Python 由来部分 PSF-2.0） | dev。LICENSE |
| mypy_extensions | 1.2.0 | MIT | dev 推移。licenses/LICENSE |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | dev。licenses/LICENSE、LICENSE.APACHE、LICENSE.BSD |
| iniconfig | 2.3.1 | MIT | dev 推移。licenses/LICENSE |
| pluggy | 1.7.0 | MIT | dev/build 推移。licenses/LICENSE |
| Pygments | 2.21.0 | BSD-2-Clause | dev 推移。licenses/LICENSE |
| hatchling | 1.27.0 | MIT | 指定 build backend。licenses/LICENSE |
| trove-classifiers | 2026.9.21.13 | Apache-2.0 | build 推移。licenses/LICENSE |
| pathspec | 0.12.1（審査環境） | MPL-2.0 | build 推移。LICENSE 原文確認。許可していない |

許可リストのままでは完了できない事項:

- hatchling の必須 build 依存 pathspec は MPL-2.0。審査時の 1.1.1 と 0.12.1 の両方が同じライセンスだった。mypy は pathspec に依存しない 1.15.0 に固定したが、指定 build backend 側の衝突は残る。
- NumPy の公式 Windows wheel の LICENSE.txt は、OpenBLAS（BSD-3-Clause）、LAPACK（BSD-3-Clause-Open-MPI）、GCC runtime（GPL-3.0-or-later WITH GCC-exception-3.1）を同梱すると記載する。本体 BSD のメタデータ検査と、wheel の同梱物審査は別の範囲である。
- 発注者へライセンス例外の判断を依頼した。無回答を承諾とは扱わず、例外表は空のまま。`uv sync`・wheel build は保留した。動作確認は LICENSE 確認用の既存環境に対する `uv run --no-sync` で行った。

`tools/check_licenses.py` の既定範囲は指定どおり runtime の配布メタデータ閉包。`--include-dev` で dev も確認できる。`--include-build` は審査環境の pathspec を MPL-2.0 として拒否する。未知のライセンスは常に失敗する。ネイティブライブラリの同梱物をメタデータだけで承認したとは扱わない。
