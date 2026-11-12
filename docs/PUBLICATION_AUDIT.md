# PUBLICATION_AUDIT — 公開前監査（private → public）

- 実施日: 2026-11-12
- 監査担当: Claude Opus 5.5（公開前監査）
- 対象: ローカル `main`（= `origin/main`、198 コミット。差分 0）。履歴の走査は、未 push のローカルブランチも含む `--all`（199 コミット、2,704 blob）で行った
- 範囲: 監査と報告のみ。visibility の変更、履歴の改変、ファイルの削除・書き換えはしていない
- 総括: **グリーンではない。** 秘密鍵・トークン・非公開ディレクトリ・ROM・他製品の資産は見つからなかった。一方で、公開前に発注者の判断が要る「中」が 2 件、通常のコミットで直せる「低」が 3 件ある（§0）

---

## 0. 判定の一覧

| # | 項目 | 判定 | 重大度 |
|---|---|---|---|
| A-0 | チェックリスト正本 `_handoff/PUBLICATION_AUDIT_CHECKLIST.md` | **問題あり**（ファイルが存在しない） | 低（手続） |
| A-1 | 追跡ファイルの全量棚卸し | OK | — |
| A-2 | `_private/`・`_handoff/` の混入（現行と全履歴） | OK | — |
| A-3 | 参照画像・他製品のスクリーンショット・ROM・重み・実行ファイル | OK | — |
| A-4 | 画像のメタデータ（PNG テキスト、JPEG の APP、GIF） | OK | — |
| A-5 | API キー・トークン・パスワード・秘密鍵（現行と全履歴） | OK | — |
| A-6 | **コミットの作者・コミッターのメールアドレス** | **問題あり** | **中** |
| A-7 | 本文中の個人メール | OK | — |
| A-8 | ローカル絶対パス（`C:\Users\<ユーザー名>`） | **問題あり** | 低 |
| A-9 | Discord の ID・Webhook・トークン | OK | — |
| A-10 | 外部の協力者との DM の原文転載 | OK（原文なし） / ハンドル由来のファイル名が 1 か所 | 低 |
| A-11 | **非公開の参照取得コネクタの記述** | **問題あり（要判断）** | **中** |
| A-12 | LICENSE | OK | — |
| A-13 | NOTICE と実物の一致 | OK | — |
| A-14 | THIRD_PARTY 台帳と実物の一致 | OK（承認待ちの例外 2 件は情報） | 情報 |
| A-15 | 組み込み OSS の帰属（PixelOE ほか） | OK | — |
| A-16 | 配布物（wheel）の中身 | OK | — |
| A-17 | クリーンルーム（Aseprite / LibreSprite 由来のコード・アイコン・文面） | OK | — |
| A-18 | 生成画像・作例の権利表記 | OK（`unknown` の明記あり） | 情報 |
| A-19 | CI ワークフローの公開時の安全性 | OK（改善案あり） | 情報 |
| A-20 | README / About の Pages デモ URL の実在確認 | **未実施（公開後タスク）** | — |
| A-21 | 未追跡ファイル（`docs/REVIEW_2.md`、`docs/review/CODEX_REVIEW_R2.md`） | OK（今回はコミットしていない） | — |

---

## 1. 手続

### A-0 チェックリスト正本の不在 — 問題あり（低）

- 証拠: `cat _handoff/PUBLICATION_AUDIT_CHECKLIST.md` → `No such file or directory`。`_handoff/` にも、`kokuren_future/` の 4 階層下までにも、該当のファイルはない（`find ... -iname "*AUDIT*"`）。
- 対処: 発注の文面（`_handoff/PROMPT_AUDIT.md`）の「重点」5 項目を展開して、本書の A-1〜A-21 を作った。正本ができたら、本書との差を確かめること。

---

## 2. 追跡ファイルの棚卸し

### A-1 全量の棚卸し — OK

- `git ls-files | wc -l` → **1,669 件**。最上位の内訳: `tests/` 645、`e2e-tests/` 476、`src/` 172、`schemas/` 93、`docs/` 92、`tools/` 54、`assets/` 47、`gui/` 43、`examples/` 21、`skills/` 13、`third_party/` 3、その他（ルートの設定・文書）11。
- 拡張子: json 639、png 468、py 280、md 95、pixhash 63、gitkeep 19、ts 15、tsx 13、jpg 10、txt 9、gif 9、gpl 8、aseprite 8、css 6、mjs 5、jsonl 5、html 4、apng 2、ほか各 1。
- 注意して開いたもの:
  - `.aseprite` 8 件: `tests/roundtrip/p11/*.aseprite` は `tools/m5_acceptance --p11` で CyberSprite 自身が書いたもの（`docs/M5_IMPLEMENTATION_REPORT.md` §65〜68）。`e2e-tests/0{3,4,7}/**/*.aseprite` は E2E の書き出しと、その往復の入力。いずれも自作の絵で、Aseprite の同梱物ではない。
  - `.jpg` 10 件: スライムの合成入力とその変種（`tests/pipeline/corpus/slime/PROVENANCE.txt` に作り方・`provider: user`・Apache-2.0 を明記）。
  - `e2e-tests/06-fresh-session/session.log`: 新規セッションのエージェントの最終報告（日本語の要約）。秘密情報なし。ローカルパスは A-8。
  - `e2e-tests/07-ds-turnaround/discord/`: 発注者の Discord 投稿用に用意した自作の絵 4 点と `caption.txt`。ID・URL・他人の発言は含まない。
  - `tests/e2e/scenarios/*/calls.jsonl`、`transcript.json`: 試験用の呼び出し列。秘密情報なし。

### A-2 `_private/`・`_handoff/` の混入 — OK

- `.gitignore` の 3 行目・5 行目で除外（`git check-ignore -v _private _handoff` → 両方とも一致）。
- 現行: `git ls-files | grep -E '_private|_handoff'` → 0 件。
- 全履歴: `git log --all --no-renames --name-only` で過去に追跡したことのある 1,684 パスを列挙 → `_private/`・`_handoff/` で始まるパスは 0 件。
- 文書の中に `_private/...` や `_handoff/...` という**パスの名前**は出てくる（規則の説明や記録）。中身の転載はない。名前の扱いは A-10、A-11。

### A-3 参照画像・スクリーンショット・ROM・重み・実行ファイル — OK

- 追跡中の画像 488 件（png 468、jpg 10、gif 9、apng 2）の置き場所は、`tests/golden`、`tests/pipeline/corpus`、`e2e-tests/0{1..7}`、`examples/`、`docs/design/{gui,img,theme-options}` だけ。`docs/design/gui/*.png` は CyberSprite 自身の GUI の画面（`settings-ja.png` などを目視）。他製品の画面はない。
- 全履歴のパスに `shot`、`aseprite_ref`、`refs`、`e2e-ds`、`.ini`、`cli_help` を含むものは、`gui/scripts/screenshots.mjs`（自製品の GUI を撮る Playwright スクリプト）と `gui/src/theme/prefs.ts` だけ。
- 全履歴の 2,704 blob を、署名で走査した（GB のロゴ列 `CE ED 66 66 …`、GBA のロゴ列 `24 FF AE 51 …`、iNES `NES\x1A`、ZIP、7z、PE、ELF、safetensors のヘッダ）→ **0 件**。
- 重みの拡張子（`.safetensors .ckpt .gguf .pt .pth .onnx .bin`）は、全履歴のパスに 0 件。
- 1 MB を超える blob は 7 件で、すべて自作の作例・較正画像・ベンチ結果 JSON。
- e2e-07 の関門シート（`review/final_review.png`、`review/g1_design_stage1.png`）を目視: 自作のキャラクター「ゼンマイ」と、Codex imagegen の自作原画だけ。参照用の市販スプライトは写っていない。

### A-4 画像のメタデータ — OK

- PNG / APNG 470 件の `tEXt`・`zTXt`・`iTXt`・`eXIf`・`iCCP` を抽出 → **0 件**。
- JPEG 10 件: APP0（JFIF）だけ。Exif（APP1）、コメント（COM）なし。
- GIF 9 件: `NETSCAPE2.0`（ループ指定）だけ。2 件で検出した `21 FE` は LZW データ内の偶然の並びで、コメントの拡張ではない（中身を読んで確認）。
- `.aseprite` 8 件: `<ユーザー名>`・`Users`・`Aseprite` の文字列なし。

---

## 3. 秘密情報

走査の方法: 現行のツリーは `git grep`、全履歴は `git rev-list --all --objects` で得た 2,704 blob を `git cat-file --batch` で読み、同じ正規表現をかけた（スクリプトはリポジトリの外の一時ディレクトリに置いた）。

### A-5 API キー・トークン・パスワード・秘密鍵 — OK

- 検索した型: `sk-…`（OpenAI）、`sk-ant-…`、`ghp_/gho_/ghu_/ghs_/ghr_/github_pat_`、`AKIA…`、`AIza…`、`xox[abpr]-`、`hf_…`、`-----BEGIN … PRIVATE KEY`、Discord のボットトークンの形、`password|secret|api_key = "…"` の代入。
- 現行・全履歴とも **0 件**。代入の形で当たったのは試験用の固定値（`token="test-token"`、`"playwright-fixture-token"`、`"local-test-token"`）だけ。
- 環境変数の名前（`GH_TOKEN`、`GITHUB_TOKEN`）は、`docs/UPSTREAM_PROGRESS.md:12` と `docs/UPSTREAM_REPORT.md:46` で「未設定」と書いているだけで、値はない。
- `.gitignore` で `.env`、`.env.*`、`*.local.json`、`.claude/settings.local.json` を除外済み。

### A-6 コミットの作者・コミッターのメール — **問題あり（中）**

- 証拠: `git log --all --format='%an <%ae>|%cn <%ce>' | sort | uniq -c` → **199 コミットすべてが、作者・コミッターとも発注者の個人の Gmail アドレス**（本書ではアドレスを伏せる）。うち 198 件は push 済みの `origin/main`。
- 影響: public にすると、誰でもコミットの `.patch`、API、`git log` で読める。本文の走査（A-7）では出てこない経路である。
- 対処案（どれを選ぶかは発注者の判断。監査では何もしていない）:
  1. **受け入れる。** 今後のコミットだけ GitHub の noreply アドレス（`<ID>+kokuren333@users.noreply.github.com`）にする。GitHub の設定「Keep my email addresses private」と「Block command line pushes that expose my email」を有効にする。
  2. **公開前に履歴を書き換える。** `git filter-repo --mailmap` で作者・コミッターを noreply に置き換え、force-push する。全コミットの SHA が変わるので、文書に書いた SHA（CI の記録、`REVIEW_REQUEST_2` など）と、未 push のローカルブランチの付け替えが要る。破壊的な操作なので、発注者の明示の指示が要る。
  3. **新しいリポジトリに、履歴をまとめて 1 から入れる。** 履歴の価値（来歴、判断の記録）を捨てることになる。

### A-7 本文中の個人メール — OK

- 現行のツリーのメールアドレスは、`gui/LICENSES_JS.txt`、`third_party/licenses/gui-bundle.txt`、`uv.lock` の第三者の著作権表示（ライセンスの本文として必要なもの）と、コミットの帰属の `noreply@anthropic.com` だけ。それ以外は 0 件。
- 発注者の Gmail アドレス（ローカル部を含む）は、現行・全履歴の本文とも 0 件（`@gmail.com` の当たりは第三者の LICENSE 本文 2 blob だけ）。

### A-8 ローカル絶対パス — 問題あり（低）

- 現行のツリーで Windows のユーザー名を含むファイルが 5 件（全履歴では、その旧版を含めて 10 blob。ほかのファイルにはない）。

| ファイル | 行 | 内容 |
|---|---|---|
| `docs/GENERATION.md` | 161、289 | 生成の監査環境と `_private/gen-check/` の絶対パス |
| `docs/R1_F2_REPORT.md` | 25、71 | 同上 |
| `docs/UPSTREAM_REPORT.md` | 58、63 | `git -C "C:\Users\…\CyberSprite" push`、`gh repo create … --source "C:\Users\…"` |
| `e2e-tests/06-fresh-session/mcp.json` | 1 | MCP サーバーの `--project` と `--root` |
| `e2e-tests/06-fresh-session/task.txt` | 2、3 | 新規セッションへの指示文の中のパス |

- 影響: Windows のユーザー名と、デスクトップ上のフォルダ構成が分かる。資格情報は含まない。
- 対処案: 通常のコミットで `<repo>`、`<外部環境>` のような置き換えにする。`e2e-tests/06` は試験の記録なので、置き換えたことを `RESULT.md` か冒頭に 1 行書く。履歴に残る旧版は、低の重大度なので書き換えまでは勧めない（A-6 で履歴を書き換えるなら、`--replace-text` で同時に消せる）。
- 誤検出の除外: `%APPDATA%` や `Path.home()` の一般的な記述、試験の `monkeypatch.setenv("APPDATA", …)` は問題なし。PNG・JPEG・GIF・`.aseprite` の中にもユーザー名はない（`git grep -a`）。

### A-9 Discord の ID 類 — OK

- Webhook の URL、ボットトークンの形、`discord|channel|guild|user` の近くの 17〜20 桁の数字（snowflake）→ 現行・全履歴とも 0 件。
- `discord` の語は、投稿用ファイルの置き場所の説明と、第三者パッケージのメタデータ（`docs/reference/pixelize_license_audit.json` の `extra == "discord"`）だけ。

### A-10 外部の協力者との DM の原文転載 — OK（注記 1 件、低）

- 方法: 非公開の要約 `_handoff/<相手のハンドル>_DM_INSIGHTS.md`（リポジトリ外）から特徴的な語句を 39 個選び、現行・全履歴の全 blob（画像と第三者 LICENSE を除く）で検索した。語句の例: 本人の発言の断片、ハンドル（`<Discord のハンドル>`）、本人の作品名、自作エミュレータ名、共有された作品のキャラクター名、生データのディレクトリ名、`.gba`、`.nds`。
- 結果: **原文の引用・ハンドル・本人の作品名は 0 件。** 文書が使うのは「DM 知見 1〜7」という番号つきの言い換えだけ（`docs/REVIEW_1.md`、`skills/workflows/*.md`、`docs/FIX_ROUND_1_REPORT.md:284`）。発言の主の名前は書いていない。
- 注記（低）: `docs/review/CODEX_REVIEW_R1.md:8` に、非公開ファイルの名前 `_handoff/<相手のハンドル>_DM_INSIGHTS.md` がそのまま出ている。第三者の Discord ハンドルに由来する名前で、DM の存在と相手が分かる。対処案: 「DM 知見メモ（非公開）」に言い換える通常のコミット。履歴の旧版は残る（A-6 で書き換えるなら同時に消せる）。
- 参考: 発注者自身の過去の試作の名前「モクリ」は `docs/REVIEW_1.md` と `e2e-tests/07-ds-turnaround/RECORD.md` に出るが、発注者の作品の名前で、DM の転載ではない。

### A-11 非公開の参照取得コネクタの記述 — **問題あり（要判断、中）**

- 証拠: `git grep -n -E 'sprite_ref|参照取得コネクタ|自動の取得を断|リモートデバッグ'` → 9 か所。中心は `skills/workflows/references.md` §2.2（28〜41 行）。
  - 発注者の私物のツール（`<非公開ツール>`）を**標準の手順**とし、`search` / `fetch <ページの URL>` / `game <機種> <作品>` のコマンド例を載せている。
  - 「利用者の Chrome をリモートデバッグ付きで起動しておく必要がある」と書いている。
  - 41 行目に「サイトが自動の取得を断っているのを実ブラウザ経由で通す作り」と明記している。
  - 同じ方針が `docs/SPEC.md:400`、`docs/DECISIONS.md:354`（I-1807）、`docs/FIX_ROUND_1_REPORT.md:466`、`skills/workflows/turnaround-parts.md:58`、`docs/reference/PROVENANCE_LOG.md:78`、`e2e-tests/07-ds-turnaround/RECORD.md:19` にある。
- 秘密情報の漏れではない（ツールの中身はリポジトリにない）。しかし public にすると、「資料サイトが断っている自動取得を、実ブラウザ経由で通す手順を標準にしているプロジェクト」と公に読める。サイトの規約、プロジェクトの評判、クリーンルームの説明の一貫性に関わる。上流のレビュー（`docs/REVIEW_1.md` §3.5、§6 の 2）も、このツールを標準にすることを勧めていない。
- 対処案（発注者の判断。I-1807 は発注者の指示なので、監査では変えない）:
  1. 公開版の `references.md` §2.2 は「人がブラウザで見て保存したものを入れる」を標準にし、コネクタの節（コマンド例、リモートデバッグ、断りを通す旨）は `_private/` か `_handoff/` の非公開の手順書へ移す。`SPEC.md:400` と `turnaround-parts.md:58` の文言も合わせる。DECISIONS には変更の理由を 1 行書く。
  2. 現状のまま公開する（リスクを受け入れる）。その場合も、41 行目の「断っているのを通す」の一文は、公開の文書に残す必要が薄い。

---

## 4. ライセンス整合

### A-12 LICENSE — OK

- `LICENSE` は Apache License 2.0 の全文。MD5 `3b83ef96387f14655fc854ddc3c6bd57` は、Apache 財団が配る `LICENSE-2.0.txt` の既知の値と一致（改変なし）。
- `pyproject.toml`: `license = "Apache-2.0"`、`license-files = ["LICENSE", "NOTICE", "third_party/licenses/*.txt"]`。

### A-13 NOTICE と実物の一致 — OK

| NOTICE の記載 | 実物 | 一致 |
|---|---|---|
| React 19.2.0 / React DOM 19.2.0 / Scheduler 0.27.0、MIT | `gui/package-lock.json`: 19.2.0 / 19.2.0 / 0.27.0、MIT、本番依存 | ○ |
| Zustand 5.0.8、MIT | 5.0.8、MIT、本番依存 | ○ |
| Vite 7.3.8（ビルド時の module-preload ランタイム） | 7.3.8、MIT、開発依存 | ○ |
| 原文は `third_party/licenses/gui-bundle.txt` | `cmp gui/LICENSES_JS.txt third_party/licenses/gui-bundle.txt` → 同一 | ○ |
| 一覧は `gui/THIRD_PARTY_JS.md` | 存在する | ○ |
| aseprite 0.1.0、Apache-2.0、Copyright 2026 Mattt <https://mat.tt>、NOTICE なし | `.venv` の `aseprite-0.1.0.dist-info/licenses/LICENSE` 末尾の表示が同文。dist-info に NOTICE なし | ○ |
| Oklab の係数（Björn Ottosson、パブリックドメイン / MIT） | `PROVENANCE_LOG` L-11 の記録と一致 | ○ |
| Aseprite / Igara Studio と無関係、他製品のコード・アイコン・絵・文書を含まない | A-17 の結果と一致 | ○ |
| 機種名は技術的な互換の説明で、任天堂ほかの保証を意味しない | 機種プリセットの説明と一致 | ○ |

### A-14 THIRD_PARTY 台帳 — OK（情報 2 件）

- `tools/check_licenses.py` → 実行時依存 10 件すべて `OK`（annotated-types、aseprite、click、colorama、numpy、pillow、pydantic、pydantic_core、typing_extensions、typing-inspection）。台帳 §1 の版・SPDX と一致。
- `node tools/check_js_licenses.mjs --check` → `Approved 46 installed JS packages; opened and checked license grants.`（台帳の「全 46 件」と一致）。
- `pyproject.toml` の固定版（numpy 2.3.4、pydantic 2.12.3、click 8.3.0、aseprite 0.1.0、mcp 2.3.0、starlette 1.10.0、uvicorn 0.54.0、websockets 16.0、jsonschema 4.26.0）は台帳 §1 の版と一致。
- 情報: 限定例外 **I-010**（pathspec の MPL-2.0。ビルド時だけで、配布物には入らない）と **I-012**（pywin32 に同梱される未使用の adodbapi の LGPL-2.1、MIT-0 / 0BSD の明記）が、台帳の冒頭で「発注者の事後承認待ち」のまま。公開の可否には影響しないが、公開と同時か前に承認を済ませると、台帳の表記がすっきりする。

### A-15 組み込み OSS の帰属（PixelOE ほか） — OK

- PixelOE: `src/cybersprite/pipeline/external/pixeloe.py` は、利用者が自分で入れた `pixeloe==1.0.0` を実行時に読み込むアダプタだけ。`pyproject.toml` の extra `pixeloe = []` は空。コードの写し・同梱はない（`git grep -i pixeloe -- src` はアダプタと呼び出し側だけ）。したがって NOTICE への帰属は不要で、台帳 §5（利用者導入のみ）の扱いと一致する。台帳 §2 の表記「Apache-2.0（Copyright 2024 KohakuBlueLeaf）」は、`PROVENANCE_LOG` の原文確認の記録と一致。
- pixel-art-fixer、proper-pixel-art も同じ形（アダプタだけ、§5）。アダプタの導入案内に、推移依存の LGPL / GPL の可能性を明示している（`pixel_art_fixer.py:10`、`proper_pixel_art.py:10`）。
- pixeldetector、ComfyUI-PixelArt-Detector、pyxelate は「設計の参照のみ」（移植しない。L-03）。
- 組み込みパレット（`src/cybersprite/data/palettes/`）は自作（Apache-2.0 / CC0-1.0）と台帳に記録済み。Lospec のパレットは同梱しない（L-07）。
- フォント: 第三者フォントの同梱なし（L-06）。

### A-16 配布物（wheel）の中身 — OK

- `uv build --wheel --out-dir <一時ディレクトリ>` → `cybersprite-0.1.0-py3-none-any.whl`（227 項目）。
- `dist-info/licenses/` に `LICENSE`、`NOTICE`、`third_party/licenses/gui-bundle.txt` が入っている。
- wheel の中に `_private`、`_handoff`、`e2e-tests`、`tests/` はない。全項目に `<ユーザー名>`・`<メールのローカル部>`・`<相手のハンドル>`・`kokuren_future` の文字列なし。
- ビルドは作業ツリーを変えていない（`git status` は監査前と同じ 2 件の未追跡だけ）。

---

## 5. クリーンルーム

### A-17 Aseprite / LibreSprite 由来のコード・アイコン・文面 — OK

- `tools/check_repository.py` → `Clean-room paths and core imports: OK`。
- `git grep -i -E 'igara|capello|dacap|libresprite|aseprite\.org|github\.com/aseprite'` を `src gui assets schemas skills tests tools` にかけた → 0 件（第三者 LICENSE の束を除く）。
- 他者の `Copyright` 表示は、NOTICE・台帳・報告書の帰属の記録だけ。`src/` に第三者の著作権ヘッダはない。
- `aseprite` の語の出どころは、`.aseprite` 形式の読み書き（`formats/aseprite_io.py` は PyPI の mattt/aseprite-py、Apache-2.0 のアダプタ）と、Op・CLI の名前（`import_aseprite` / `export_aseprite`）。製品のコードではない。
- アイコン: `assets/ui/icons/*.csprite` 40 件は CyberSprite のプロジェクト形式の自作ドット絵と、それを描く生成スクリプト（`assets/ui/icons/tools/`）。
- GUI の文言: `gui/src/i18n/en.json` の 151 項目を読んだ。言い回しは独自（例: 「Commercial OK with use restrictions」「Display settings are kept in this browser only.」）。
- `docs/reference/ASEPRITE_INVENTORY.md`: 自分の言葉での機能の棚卸し（規則を冒頭に明記）。スクリーンショットはリポジトリになく、`_private/aseprite_ref/shots/` にだけある（A-2 で履歴にも入っていないことを確認）。メニューの第 1 階層の分類（ファイル・編集・スプライト・レイヤー・フレーム・選択・表示・ヘルプ）は、ドット絵エディタで一般的な語で、CyberSprite の GUI の第 1 階層にも同じ並び（＋エージェント）がある。文面の写しではないので OK とする。気になる場合は、並び順を変えるかどうかを GUI 担当（Opus）に諮る程度の話である。
- 他人の絵の参照: `docs/reference/PROVENANCE_LOG.md` の該当行（DS 世代の市販スプライト 4 点）は、作品名を書かず、統計値だけを残している。画像は `_private/e2e-ds/refs/` にだけあり、履歴に入ったことはない。

### A-18 生成画像・作例の権利表記 — OK（情報）

- `tests/pipeline/corpus/generated/`（imagegen の 16 枚）は、`README.md` と `manifest.json` に全プロンプト・日付・SHA-256 を記録し、モデル ID と出力ライセンスを `unknown` と明記している。既存のキャラクターや第三者の画像は入力していない、とある。
- e2e-07 の原画（`zenmai*.csprite/source/`）も Codex imagegen の自作原画。
- 情報: OpenAI の規約上、出力の権利は利用者側にある（台帳 L-12）。公開を妨げない。

### A-19 CI ワークフロー — OK（改善案）

- 追跡中のワークフローは `.github/workflows/ci.yml` だけ。`on: [push, pull_request]`、`secrets.*` の参照なし、`pull_request_target` なし、self-hosted ランナーなし。fork からの PR に秘密が渡る経路はない。
- 改善案（任意）: 先頭に `permissions: contents: read` を書き、`GITHUB_TOKEN` の権限を最小にする。

---

## 6. 公開後のタスク

### A-20 README / About の Pages デモ URL — 未実施（公開後タスク）

- Pages はまだ無効なので、URL の実在確認はしていない。
- 現状の事実: `README.md` に URL は 0 件（`grep -o 'https\?://…' README.md` → なし。`demo` はコマンド例のファイル名だけ）。Pages のデモ（`.github/workflows/pages.yml`、`gui/src/demo/`、`docs/DEMO_REPORT.md`）は、**未 push のローカルブランチ `fixr1-demo`（コミット `bc25868`）にだけ**あり、`main` / `origin/main` には入っていない。
- 公開後にすること: (1) デモを `main` に統合して Pages を有効にする、(2) README と About に URL を載せる、(3) その URL を実際に開いて表示を確かめる。

### A-21 未追跡ファイル — OK

- `docs/REVIEW_2.md`（238 行）と `docs/review/CODEX_REVIEW_R2.md`（409 行）は未追跡で、今回のコミットには含めていない。
- 先回りして同じ語で走査した: `<ユーザー名>`、`gmail`、`<メールのローカル部>`、`<相手のハンドル>`、`tk_`、`token`、`api key`、`discord`、`C:\Users`、作品名 → 当たりは Python の `from …` と `ROM` の大文字小文字を無視した誤検出だけ。コミットしても A-5〜A-10 の観点では問題ない。

---

## 7. 対処の順番（提案）

1. **A-6（中）**: メールの扱いを決める（受け入れて今後だけ noreply にする / 公開前に履歴を書き換える / 新しいリポジトリにする）。履歴を書き換えるなら、A-8 と A-10 の旧版も `--replace-text` で同時に消せる。
2. **A-11（中）**: 参照取得コネクタの記述を公開版に残すかを決める。残さないなら、公開前に通常のコミットで `references.md` §2.2 ほかを書き換える。
3. **A-8、A-10（低）**: 絶対パス 5 ファイルと、ハンドル由来のファイル名 1 か所を、通常のコミットで言い換える。
4. **A-0（低）**: チェックリストの正本を置き、本書との差を確かめる。
5. 情報（A-14 の I-010 / I-012、A-19 の `permissions`）は、公開と前後して片づければよい。

## 8. 再現の手順（要約）

```text
git ls-files | wc -l                                       # 1669
git log --all --no-renames --pretty=format: --name-only | sort -u   # 1684 パス、_private/_handoff は 0
git log --all --format='%an <%ae>|%cn <%ce>' | sort | uniq -c       # A-6
git grep -n -i <ユーザー名>                                       # A-8
git grep -I -n -E '<鍵・トークンの正規表現>'              # A-5（現行）
git rev-list --all --objects | git cat-file --batch …      # A-3、A-5、A-10（全履歴の blob を走査）
python tools/check_licenses.py                             # A-14
node tools/check_js_licenses.mjs --check                   # A-14
python tools/check_repository.py                           # A-17
uv build --wheel --out-dir <一時ディレクトリ>              # A-16
```

走査に使った一時スクリプトは、リポジトリの外（一時ディレクトリ）に置き、コミットしていない。

---

## 補遺 A（2026-11-12、公開前仕上げ）: チェックリスト正本との突き合わせ（A-0 の解消）

監査の後に、チェックリストの正本（`_handoff/PUBLICATION_AUDIT_CHECKLIST.md`、git の管理外）が同期された。正本の各項目を本書の A-1〜A-21 と突き合わせた。正本は非公開のため、本節では項目を言い換えて書く。

| 正本の項目（言い換え） | 本書 | 差 | この補遺での確認 |
|---|---|---|---|
| §1 追跡ファイルの全量の目視分類 | A-1 | なし | — |
| §1 `_private/`・`_handoff/` が追跡されていない（`.gitignore` の効きも） | A-2 | なし | — |
| §1 参照画像・他製品のスクリーンショット・DM 由来の媒体が追跡されていない | A-3、A-10 | なし | — |
| §1 ROM・市販ゲーム由来のファイルがない | A-3 | なし | — |
| §1 ビルド成果物・キャッシュ・セッションログ（`.jsonl`）が追跡されていない | A-1（拡張子の内訳だけ） | **あり**（明示の検査がない） | `git ls-files` に `__pycache__`、`.pyc`、`dist/`、`node_modules`、各種キャッシュ、`server/static/assets`、`demo-dist`、`test-results` は 0 件。`.jsonl` は `tests/e2e/scenarios/*/calls.jsonl` の 5 件で、試験の呼び出し列（セッションログではない）。セッションの記録は `e2e-tests/06-fresh-session/session.log` の 1 件だけで、中身はエージェントの最終報告（A-1 で確認済み）→ OK |
| §2 トークン・パスワード・API キーの走査（現行と全履歴） | A-5 | なし | — |
| §2 PC の資格情報ファイル（`config.json` など）が含まれていない | A-5（`.gitignore` の確認だけ） | **あり**（ファイル名の検査がない） | 追跡ファイルの名前を `credential`、`secret`、`.npmrc`、`.pypirc`、`.netrc`、`id_rsa`、`.pem`、`.key`、`.env`、`settings.local`、`config.json`、`token` で検索 → 当たりは `gui/src/theme/tokens.css`（デザイントークン）と `gui/tsconfig.json` だけ → OK |
| §3 実名・私用メール・Discord の ID | A-6、A-7、A-9 | **一部**（実名の検索がない） | 監査担当は発注者の実名を知らないため、検索できない。履歴を書き換えるセッションで、発注者が自分の実名で `git grep` と全履歴の走査をすること（`docs/PUBLICATION_FIX_REPORT.md` の引き継ぎ） |
| §3 ローカルパスとマシン名 | A-8 | **一部**（マシン名の検索がない） | この PC のホスト名で、現行のツリーと全履歴の差分（`git log --all -p`）を検索 → 0 件。パスは公開前仕上げで直した（A-8） |
| §3 DM の原文の転載がない | A-10 | なし | — |
| §4 LICENSE・NOTICE・台帳と現行の依存の一致 | A-12〜A-14 | なし | — |
| §4 取り込んだ OSS の帰属 | A-15 | なし | — |
| §4 クリーンルーム | A-17 | なし | — |
| §5 全部グリーンを発注者に報告する | §0 | なし | 公開前仕上げの結果は `docs/PUBLICATION_FIX_REPORT.md` |
| §5 visibility の切り替えと、切り替え後の公開ページの目視 | A-20（公開後） | なし | 範囲外（別のセッション） |
| §5 Pages のワークフローは、公開後に発注者の指示で有効化する | A-20 | なし | デモは `main` に統合した（`fixr1-demo`）。ワークフローは `workflow_dispatch` だけで、有効化していない |
| §5 Pages の URL を **README の冒頭** と About の両方に載せ、**スマホで**リンクを辿れるか確かめる | A-20（README と About） | **あり**（「冒頭」とスマホでの確認がない） | 公開後のタスクに足す: URL は README の冒頭（状態の行の近く）に置き、About の Website 欄にも入れ、スマホの表示でリンクが辿れることを確かめる |

正本にあって本書に無かったのは、上の **差あり 3 件と一部 2 件**で、どれもこの補遺で確認するか、引き継ぎに入れた。逆に、本書にあって正本に無い項目（A-4 画像のメタデータ、A-6 コミットのメール、A-16 配布物、A-18 生成画像の権利、A-19 CI、A-21 未追跡）は、本書の側の追加である。A-0 は解消とする。
