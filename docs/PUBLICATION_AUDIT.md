# PUBLICATION_AUDIT — 公開前監査（private → public）

本書は 2 回分の監査をまとめる。**正は第 2 回（§0〜§8）**。第 1 回（2026-11-12）の本文と補遺は、指摘番号 A-0〜A-21 の参照先として付録 1 にそのまま残した（見出しを 1 段下げただけ）。

- 第 2 回の実施日: 2026-11-13（JST）
- 監査担当: Claude Opus 5.5（公開前監査）
- チェックリスト正本: `_handoff/PUBLICATION_AUDIT_CHECKLIST.md`（git の管理外）。§1〜§5 の全項目を、本書の B-1〜B-26 に対応づけた。正本は非公開なので、項目は言い換えて書く
- 対象: ローカル `main` の `d2cf0e8`（213 コミット）。**履歴の書き換え（`git filter-repo`、2026-11-12 23:55 実行）の後の状態**。ローカルのブランチは 43 本で、全部を走査した（`--all` = 213 コミット、2,783 blob、過去に追跡したパス 1,698）
- 範囲: 監査と報告だけ。visibility の変更、履歴の改変、push、ファイルの削除・書き換えはしていない
- 並走: 監査の間、別の 2 セッションが同じ作業ツリーで動いていた。(1) 履歴の書き換えセッション。`.git/filter-repo/` はあるが、監査の終わりの時点で完了の印 `_handoff/history_rewrite.done` が無く、force-push も済んでいない（B-24）。(2) `docs/review/CODEX_REVIEW_R1.md` を未コミットで編集しているセッション（B-26）。本書のコミットには本書だけを入れた

---

## 0. 総括

**ローカルの履歴と現行のツリーは、公開してよい状態（グリーン）。GitHub 側はまだグリーンではない。**

- 書き換えた後のローカルでは、秘密情報・個人のメール・実名・ユーザー名・ホスト名・協力者のハンドルと DM の原文・ROM・他製品の資産が、現行のツリーと全履歴の両方で **0 件**。第 1 回の「中」の A-6（コミットのメール）は、ローカルでは解消した。
- 残る問題は 2 件。
  - **B-24（中）: GitHub の旧履歴。** GitHub の `main` は、まだ書き換え前の旧履歴（`13b44e5`。作者のメールは個人の Gmail）。書き換えた履歴を force-push しても、GitHub は旧コミットを SHA で引ける状態のまま保持する。しかも、追跡文書は旧 SHA を 61 個書いていて、それが道しるべになる。public にする前に、リポジトリを作り直すか、GitHub Support に旧コミットの消去を頼む必要がある。
  - **B-15（低）: 参照取得ツールの記述の残り。** 旧版の `skills/workflows/references.md`（全履歴の 2 コミット）に、ツールのサブコマンドの形と、取得の性質を述べた一文が残っている。任意の置き換えの一覧と文面が 1 文字（読点）違うため、当たらなかった。現行のツリーにも、ツールのファイル名とローカルの手順書のファイル名が 2 行ある。
- 情報（公開は止めない）: I-010 / I-012 の事後承認待ち（B-18）、`ci.yml` に `permissions` が無い（B-23）、未コミットの並走の編集（B-26）。
- 公開後のタスク: Pages の URL の実在確認（B-25）は **未実施（公開後タスク）**。

## 1. 判定の一覧

| # | 正本 | 項目 | 判定 | 重大度 | 第 1 回 |
|---|---|---|---|---|---|
| B-1 | §1 | 追跡ファイルの全量の棚卸し | OK | — | A-1 |
| B-2 | §1 | `_private/`・`_handoff/` が追跡されていない（`.gitignore` の効き、全履歴） | OK | — | A-2 |
| B-3 | §1 | 参照画像・他製品のスクリーンショット・DM 由来の媒体 | OK | — | A-3 |
| B-4 | §1 | ROM・市販ゲーム由来のファイル・重み・実行ファイル | OK | — | A-3 |
| B-5 | §1 | ビルド成果物・キャッシュ・セッションログ | OK | — | 補遺 A |
| B-6 | （追加） | 画像のメタデータ | OK | — | A-4 |
| B-7 | §2 | トークン・パスワード・API キー・秘密鍵（現行と全履歴） | OK | — | A-5 |
| B-8 | §2 | 資格情報のファイル | OK | — | 補遺 A |
| B-9 | §3 | コミットの作者・コミッターのメール（ローカル） | **OK（解消）** | — | A-6（中） |
| B-10 | §3 | 本文中の私用メール | OK | — | A-7 |
| B-11 | §3 | 発注者の実名（漢字・ローマ字） | OK | — | 補遺 A（未実施だった） |
| B-12 | §3 | ローカルの絶対パス・ユーザー名・マシン名 | **OK（解消）** | — | A-8（低） |
| B-13 | §3 | Discord のユーザー ID・チャンネル ID・サーバー ID・Webhook | OK | — | A-9 |
| B-14 | §3 | DM の原文の転載、協力者のハンドル | **OK（解消）** | — | A-10（低） |
| B-15 | §3・§4 の周辺 | 参照取得ツールの記述 | **問題あり** | **低** | A-11（中） |
| B-16 | §4 | LICENSE | OK | — | A-12 |
| B-17 | §4 | NOTICE と実物の一致 | OK | — | A-13 |
| B-18 | §4 | THIRD_PARTY 台帳と現行の依存の一致 | OK（承認待ち 2 件は情報） | 情報 | A-14 |
| B-19 | §4 | 組み込み OSS の帰属（PixelOE ほか） | OK | — | A-15 |
| B-20 | （追加） | 配布物（wheel と sdist）の中身 | OK | — | A-16 |
| B-21 | §4 | クリーンルーム（Aseprite / LibreSprite 由来のコード・アイコン・文面） | OK | — | A-17 |
| B-22 | （追加） | 生成画像・作例の権利表記 | OK | 情報 | A-18 |
| B-23 | （追加） | CI ワークフローの公開時の安全性 | OK（改善案あり） | 情報 | A-19 |
| B-24 | §5 の前提 | **GitHub 上の旧履歴（force-push の後も SHA で読める）** | **問題あり** | **中** | （新規） |
| B-25 | §5 | README の冒頭と About の Pages デモ URL、スマホでの確認 | **未実施（公開後タスク）** | — | A-20 |
| B-26 | （追加） | 並走セッションの未コミットの変更 | OK（情報） | 情報 | A-21 |

---

## 2. 追跡ファイル（正本 §1）

### B-1 全量の棚卸し — OK

- `git ls-files | wc -l` → **1,697 件**（第 1 回から +28）。最上位: `tests/` 647、`e2e-tests/` 476、`src/` 173、`docs/` 106、`schemas/` 94、`tools/` 54、`gui/` 52、`assets/` 47、`examples/` 21、`skills/` 13、`third_party/` 3、`.github/` 2、ルート 9（`.gitattributes`、`.gitignore`、`AGENTS.md`、`CLAUDE.md`、`LICENSE`、`NOTICE`、`README.md`、`pyproject.toml`、`uv.lock`）。
- 拡張子: json 640、png 477、py 283、md 100、pixhash 63、ts 21、gitkeep 19、tsx 15、jpg 10、txt 9、gif 9、gpl 8、aseprite 8、mjs 6、css 6、jsonl 5、html 4、yml 2、apng 2、ほか各 1。
- 第 1 回から増えた 27 ファイル（`git diff --name-only --diff-filter=A 169d9f1 main`）を 1 件ずつ分類した: Pages デモ（`.github/workflows/pages.yml`、`gui/src/demo/*`、`gui/src/components/DemoNotice.tsx`、`gui/scripts/demo-check.mjs`、`docs/DEMO_REPORT.md`、`docs/design/demo/*.png` 7 枚）、手動の参照の取り込み（`src/cybersprite/ops/references.py`、`gui/src/api/reference*.ts`、`gui/src/components/ReferenceAttach.tsx`、スキーマ 1、試験 2、`docs/design/gui/reference-*.png` 2 枚）、文書（`docs/REVIEW_2.md`、`docs/review/CODEX_REVIEW_R2.md`、`docs/PUBLICATION_FIX_REPORT.md`）。削除は 0 件。
- 画像を目視した: `docs/design/demo/desktop-ja-1-open.png`（CyberSprite 自身のデモ画面と、自作のロボット「Chip」）、`docs/design/gui/reference-listed-en.png`（自製品のソースのタブ。参照の見本は赤一色の試験画像）。
- `CLAUDE.md` の中身は `@AGENTS.md` の 1 行だけ。

### B-2 `_private/`・`_handoff/` — OK

- `.gitignore` の 3 行目と 5 行目で除外している。
- 現行: `git ls-files _private _handoff` → 0 件。
- 全履歴: `git log --all --no-renames --pretty=format: --name-only | sort -u` → 1,698 パス。`_private`・`_handoff` を含むものは 0 件。
- 文書の中に、パスの**名前**としての `_private/…`、`_handoff/…` は出てくる（規則の説明と記録）。中身の転載は無い（B-14、B-15）。

### B-3 参照画像・スクリーンショット・DM 由来の媒体 — OK

- 全履歴のパスで `shot`、`refs/`、`aseprite_ref`、`screenshot` を検索 → `gui/scripts/screenshots.mjs`（自製品の GUI を撮るスクリプト）だけ。
- 作品名と資料サイトの名前（DM で共有された作品のキャラクター名、シリーズ名、2 つの資料サイトの名前とドメイン）を、全履歴の 2,783 blob で検索 → **0 件**。

### B-4 ROM・市販ゲーム由来のファイル・重み・実行ファイル — OK

- 全履歴の 2,783 blob を署名で走査した: GB のロゴ列 `CE ED 66 66 CC 0D 00 0B`、GBA / NDS のロゴ列 `24 FF AE 51 69 9A A2 21`、iNES `NES\x1A`、ZIP、7z、PE（`MZ`）、ELF、safetensors のヘッダ → **0 件**。
- 全履歴のパスで ROM・アーカイブ・実行ファイル・重みの拡張子（`.gb .gbc .gba .nds .nes .sfc .smc .zip .7z .rar .exe .dll .bin .iso .safetensors .ckpt .gguf .pt .pth .onnx`）→ 0 件。
- 1 MB を超える blob は 7 件で、第 1 回と同じもの（自作の作例、較正画像、ベンチ結果の JSON）。

### B-5 ビルド成果物・キャッシュ・セッションログ — OK

- 追跡中のファイル名で `__pycache__`、`.pyc`、`dist/`、`node_modules`、`demo-dist`、`test-results`、`playwright-report`、`.cache`、`.DS_Store`、`Thumbs.db` → 0 件。
- `.jsonl` 5 件は `tests/e2e/scenarios/scenario{1..5}/calls.jsonl`（試験の呼び出し列。中身は `new_project` などのツール呼び出しで、セッションログではない）。
- `.log` 1 件は `e2e-tests/06-fresh-session/session.log`（3,165 バイト）。新規セッションのエージェントの最終報告の要約で、秘密情報もパスも無い。同じ試験の `mcp.json` と `task.txt` のパスは `<repo>` に置き換え済み。

### B-6 画像のメタデータ — OK

- 現行の PNG / APNG 479 件: `tEXt`、`zTXt`、`iTXt`、`eXIf`、`iCCP`、`tIME` のチャンク → 0 件。
- JPEG 10 件: APP0（JFIF）以外のマーカー（APP1〜APP15、COM）→ 0 件。
- GIF 9 件: ブロックを順に読んだ。コメントの拡張 0 件、`NETSCAPE2.0` 以外のアプリケーション拡張 0 件。
- `.aseprite` 8 件: ユーザー名、`Users`、メールのローカル部、親フォルダの名前 → 0 件。

---

## 3. 秘密情報（正本 §2）

走査の方法: 現行のツリーは `git ls-tree -r HEAD` の 1,433 blob、全履歴は `git rev-list --all --objects` の 2,783 blob を `git cat-file --batch` で読み、同じ正規表現をかけた。コミットのメッセージ（`git log --all --format=%B`、948 行）、作者名とコミッター名、過去のパス名も別に走査した。スクリプトはリポジトリの外の一時ディレクトリに置き、コミットしていない（消すべき文字列そのものを含むため）。

### B-7 トークン・パスワード・API キー・秘密鍵 — OK

| 型 | 現行 | 全履歴 |
|---|---|---|
| OpenAI / Anthropic（`sk-…`、`sk-proj-…`、`sk-ant-…`） | 0 | 0 |
| GitHub（`ghp_ gho_ ghu_ ghs_ ghr_`、`github_pat_`） | 0 | 0 |
| AWS（`AKIA…`、`ASIA…`）、Google（`AIza…`）、Slack（`xox?-`）、Hugging Face（`hf_…`） | 0 | 0 |
| 秘密鍵（`-----BEGIN … PRIVATE KEY`）、JWT | 0 | 0 |
| Discord のボットトークンの形、Webhook、招待 URL | 0 | 0 |
| `password / secret / api_key / access_token / auth_token` への 8 文字以上の文字列の代入 | 0 | 0 |

- コミットのメッセージでの当たりは、`mask-protected` が `sk-` に当たった誤検出 1 件だけ。

### B-8 資格情報のファイル — OK

- 追跡中のファイル名で `credential`、`secret`、`.npmrc`、`.pypirc`、`.netrc`、`id_rsa`、`id_ed25519`、`.pem`、`.key`、`.p12`、`.pfx`、`.env`、`settings.local`、`config.json`、`token` → `gui/src/theme/tokens.css`（デザイントークン）と `gui/tsconfig.json` だけ。
- `.gitignore` が `.env`、`.env.*`、`*.local.json`、`.claude/settings.local.json` を除外している。

---

## 4. 個人情報・環境情報（正本 §3）

### B-9 コミットの作者・コミッターのメール — OK（ローカルでは A-6 を解消）

- `git log --all --format='%ae|%ce' | sort | uniq -c` → **213 コミットすべてが、作者・コミッターとも GitHub の noreply アドレス**（`<数値 ID>+kokuren333@users.noreply.github.com`）。
- `git log --all --format='%an|%cn' | sort | uniq -c` → 213 件すべて `kokuren333`。
- ローカルの `user.email` も同じ noreply（`git config --local`）。今後のコミットも noreply で作られる（本書のコミットも）。
- これはローカルの話である。GitHub 側は B-24。

### B-10 本文中の私用メール — OK

- `@gmail.com` の当たりは、現行・全履歴とも、第三者の著作権表示（`gui/LICENSES_JS.txt` と `third_party/licenses/gui-bundle.txt`。同じ blob）と、第 1 回の本文の「当たりは第三者の LICENSE だけ」という説明文だけ。
- 発注者のメールのローカル部 → 現行・全履歴・コミットのメッセージで 0 件。

### B-11 発注者の実名 — OK

- 第 1 回では、実名が分からず検索できなかった項目。今回は、この PC のローカルアカウントの「フルネーム」欄から実名を得て、漢字の姓、漢字の姓名、ローマ字の姓（大文字小文字を無視）で検索した。
- 現行のツリー・全履歴の 2,783 blob・コミットのメッセージ・作者名 → **すべて 0 件**。wheel と sdist の中身も 0 件（B-20）。
- 実名そのものは本書に書かない。名だけの形は短すぎて誤検出が多いので、検索していない（姓と姓名で 0 件なので十分と判断した）。ローカルアカウントの欄が戸籍上の表記と違う可能性は残るので、気になる場合は発注者が別の表記でもう一度検索すること。

### B-12 ローカルの絶対パス・ユーザー名・マシン名 — OK（A-8 を解消）

- Windows のユーザー名、`C:\Users\…`・`C:/Users/…`（`<` で始まる置き換え済みのものを除く）、`/c/Users/`、この PC のホスト名 → 現行・全履歴・コミットのメッセージで **0 件**。
- 第 1 回で全履歴に 21 か所あったパスは、書き換えで消えた。
- 親フォルダの名前（GitHub のハンドルに由来する一般的な名前）は、付録 1 の第 1 回の本文に 2 か所ある。資格情報でも、個人の特定につながる情報でもないので、OK とする。

### B-13 Discord の ID 類 — OK

- `discord|channel|guild|server|user` の近く（40 文字以内）の 17〜20 桁の数字（snowflake）、Webhook、招待 URL → 現行・全履歴とも 0 件。
- `discord` の語は、投稿用ファイルの置き場所の説明（`e2e-tests/07-ds-turnaround/discord/`）と、第三者パッケージのメタデータ（`docs/reference/pixelize_license_audit.json` の `extra == "discord"`）だけ。投稿用フォルダの `caption.txt` は自作の絵の説明文で、ID・URL・他人の発言は無い。

### B-14 DM の原文、協力者のハンドル — OK（A-10 を解消）

- 方法: 非公開の DM 知見メモ（git の管理外）から、相手のハンドル（短い形と Discord のユーザー名の形）、相手の作品名・自作ツール名、DM の生データの置き場所の名前、特徴的な発言の断片 18 個、共有された作品のキャラクター名、資料サイトの名前を選び、現行・全履歴・コミットのメッセージを検索した。
- 結果: **すべて 0 件**。第 1 回で残っていたハンドル由来のファイル名と見出し（全履歴で 2 か所）は、書き換えで消えた。
- 文書が使うのは、番号つきの言い換え（「DM 知見 1〜7」）だけで、発言の主の名前は無い。

### B-15 参照取得ツールの記述 — 問題あり（低）

第 1 回の A-11（中）は、現行のツリーについては公開前仕上げで解消した（標準の手順から外し、手動の取り込みを入れた。`docs/PUBLICATION_FIX_REPORT.md` §2）。発注者は、ツールの記述を履歴からも消すことを「任意」とした。残りは次のとおり。

1. **全履歴: 旧版の `skills/workflows/references.md` に、ツールの使い方の記述が残る。** 書き換えでツールのファイル名は `<非公開ツール>` に置き換わったが、次が残っている。
   - 対象はコミット `835bff3` と `f931c6c`（どちらも 2026-11-12、R1-G）の版。`git log --all -S'<取得の性質の一文の語句>'` で特定した。
   - 残っている内容: 4 つのサブコマンド（検索、取得、作品単位の取得、一覧）の形と、「上流のレビューは、このツールを標準の手順にすることを勧めていない」に続く、取得の性質を述べた括弧書きの一文（第 1 回 A-11 の 3 点目と同じ内容）。
   - 原因: 任意の置き換えの一覧（`_handoff/publication_replace_text_optional.txt`）の 5 行目は、この一文を読点なしで書いていた。実物は途中に読点がある。
   - ツールの所在（パス）と、ブラウザの起動のしかた（リモートデバッグ）は、全履歴で 0 件（第 1 回の監査書の旧版の、検索の型に出てくるものを除く。下の 3）。
2. **現行のツリー: `docs/PUBLICATION_FIX_REPORT.md` の 2 行。** 66 行目に、ローカルの手順書のファイル名（`_handoff/tools/` の下）。71 行目に、検証の `git grep` の型として、ツールのファイル名。どちらも、ツールの中身や使い方ではない。
3. 参考: 第 1 回の監査書の旧版（`169d9f1`）も、証拠の `git grep` の型にツールのファイル名を含む。現行の版（`19eebd1` で一般化）にあるのは、分析の文（付録 1 の A-11。公開するとどう読まれるか、という評価）だけ。

- 影響: 秘密情報の漏れではない。ツールの中身はリポジトリに無い。読めるのは「発注者がそういうツールを持っていて、2026-11-12 に一時期、標準の手順にしていた」という事実と、取得の性質の一文である。旧版を開く読者は少ないが、public にすると誰でも読める。
- 対処案（発注者の判断。監査では何もしていない）:
   1. **受け入れる。** 現行のツリーでは手順から外してあり、旧版の一文も「上流のレビューは勧めていない」という批評の文脈にある。
   2. **force-push の前に、読点ありの形を一覧に足して、もう一度 `--replace-text` をかける。** B-24 でリポジトリを作り直すなら、その前に 1 行足すだけで済む。足す行は、一覧の 5 行目の左辺に読点を補った形で、右辺は 5 行目と同じ。サブコマンドの形まで消すには `--replace-text` の 1 行では足りない（複数行の置き換えになる）ので、そこは受け入れを勧める。
   3. 現行の 2 行は、通常のコミットで「ローカルの手順書」「ツールのファイル名」に言い換えられる（任意）。

---

## 5. ライセンス・権利（正本 §4）

### B-16 LICENSE — OK

- `md5sum LICENSE` → `3b83ef96387f14655fc854ddc3c6bd57`。Apache 財団の `LICENSE-2.0.txt` と同じ値（改変なし）。
- `pyproject.toml`: `license = "Apache-2.0"`、`license-files = ["LICENSE", "NOTICE", "third_party/licenses/*.txt"]`。

### B-17 NOTICE と実物の一致 — OK

| NOTICE の記載 | 実物（`gui/package-lock.json` ほか） | 一致 |
|---|---|---|
| React 19.2.0 / React DOM 19.2.0 / Scheduler 0.27.0、MIT | 19.2.0 / 19.2.0 / 0.27.0、MIT、本番依存 | ○ |
| Zustand 5.0.8、MIT | 5.0.8、MIT、本番依存 | ○ |
| Vite 7.3.8（module-preload ランタイム） | 7.3.8、MIT、開発依存 | ○ |
| 原文は `third_party/licenses/gui-bundle.txt` | `cmp gui/LICENSES_JS.txt third_party/licenses/gui-bundle.txt` → 同一 | ○ |
| aseprite 0.1.0、Apache-2.0、同梱しない | 実行時依存。`check_licenses.py` で Apache-2.0 | ○ |
| 生成画像（`unknown`）を Apache-2.0 の対象に含めない。wheel と sdist から除外 | B-20 で確かめた（wheel・sdist とも 0 件） | ○ |
| Oklab の係数、機種名の商標の注記 | `PROVENANCE_LOG` L-11、機種プリセットの説明 | ○ |
| Aseprite / Igara Studio と無関係、他製品のコード・アイコン・絵・文書を含まない | B-21 | ○ |

- 著作権者の表示は `kokuren (kokuren333)`（GitHub のハンドル）で、実名ではない。

### B-18 THIRD_PARTY 台帳 — OK（情報 2 件）

- `uv run --no-sync python tools/check_licenses.py` → 実行時依存 10 件すべて `OK`。`--include-dev --extra mcp --extra gui` → `OK` 以外の行は 0（範囲の注記の 1 行だけ）。
- `node tools/check_js_licenses.mjs --check` → `Approved 46 installed JS packages; opened and checked license grants.`
- 情報: 限定例外 I-010（pathspec の MPL-2.0。ビルド時だけ）と I-012（pywin32 に同梱の未使用の adodbapi の LGPL-2.1）が、台帳の冒頭で「発注者の事後承認待ち」のまま。第 1 回と同じで、公開は止めない。

### B-19 組み込み OSS の帰属（PixelOE ほか） — OK

- PixelOE は、利用者が自分で入れた `pixeloe` を読むアダプタ（`src/cybersprite/pipeline/external/`）と、空の extra `pixeloe = []` だけ。コードの写しも同梱も無い（`git grep -i pixeloe -- src pyproject.toml`）。台帳 §2 の「Apache-2.0（Copyright 2024 KohakuBlueLeaf）」と、L-02 の「利用者導入のみ（§5）」の扱いに一致する。同梱しないので、NOTICE への帰属は要らない。
- pixel-art-fixer、proper-pixel-art も同じ形。pixeldetector などは設計の参照のみ（L-03）。第 1 回から変わっていない。

### B-20 配布物（wheel と sdist） — OK

- `uv build --wheel --sdist --out-dir <一時ディレクトリ>`。作業ツリーは変わらない。
- wheel: 224 項目。`dist-info/licenses/` に `LICENSE`、`NOTICE`、`third_party/licenses/gui-bundle.txt` がある。`_private`、`_handoff`、`e2e-tests`、`tests/`、生成コーパスは無い。全項目の中身で、ユーザー名・メールのローカル部・ハンドル・ホスト名・実名（漢字・ローマ字）は 0 件。
- sdist: 1,249 項目。`_private`、`_handoff`、`e2e-tests`、`tests/pipeline/corpus/generated`、`.venv`、`node_modules` は 0 件（I-2004 の除外が効いている）。中身の当たりは、`docs/PUBLICATION_AUDIT.md` の親フォルダの名前（B-12 の注記）だけ。

### B-21 クリーンルーム — OK

- `uv run --no-sync python tools/check_repository.py` → `Clean-room paths and core imports: OK`。
- `git grep -i -E 'igara|capello|dacap|libresprite|aseprite\.org|github\.com/aseprite'` を `src gui assets schemas skills tests tools` に（第三者 LICENSE の束を除いて）→ 0 件。
- `src/` と `gui/src/` に `Copyright` の表示 → 0 件（他者の著作権ヘッダの写しは無い）。
- 第 1 回から増えた GUI のファイル（デモ、参照の添付）は、独自の部品と独自の文言。新しいアイコンやアセットは足されていない。
- 他製品のスクリーンショットは、全履歴のパスと画像の目視で無し（B-3）。

### B-22 生成画像の権利 — OK（情報）

- `tests/pipeline/corpus/generated/` と `e2e-tests/07-ds-turnaround/` の生成画像は、NOTICE の節「Images with unknown usage terms」で Apache-2.0 の対象外とし、来歴の場所と台帳 L-12 を示している。配布物には入らない（B-20）。

### B-23 CI ワークフロー — OK（改善案）

- `ci.yml`: `on: [push, pull_request]`。`secrets.*` の参照なし、`pull_request_target` なし、self-hosted ランナーなし。fork の PR に秘密が渡る経路は無い。改善案（任意）: 先頭に `permissions: contents: read`（第 1 回と同じ）。
- `pages.yml`（新規）: `on: workflow_dispatch` だけで、push では動かない。`permissions` は `contents: read`、`pages: write`、`id-token: write` で、Pages の配備に要る最小。秘密は使わない。

---

## 6. GitHub 側（正本 §5 の前提）

### B-24 GitHub 上の旧履歴 — 問題あり（中）

- 証拠:
  - `git ls-remote https://github.com/kokuren333/CyberSprite.git`（読み取りだけ）→ `refs/heads/main` と `HEAD` が `13b44e5` の 2 行だけ。`refs/pull/*` もタグも無い。
  - `13b44e5` はローカルには無い（`git cat-file -t` → 無効なオブジェクト）。`.git/filter-repo/commit-map` では、書き換え前の「docs: record quiet final performance re-measurement for round 1」（書き換え後の `1cb7387`）に当たる。つまり GitHub に載っているのは、**書き換え前の旧履歴**（作者のメールは個人の Gmail。A-8 のパスと A-10 のハンドルを含む旧 blob もある）。
  - ローカルの `git remote -v` は空（`git filter-repo` が `origin` を外した）。書き換えのセッションは、監査の終わりの時点で完了の印を残していない。
  - 追跡文書の中の、バッククォートで囲んだ 7〜12 桁の 16 進は 67 個。そのうち **61 個が書き換え前の SHA**（commit-map の旧側にだけある）。書き換え後の SHA に当たるのは 1 個だけ。例: `docs/PUBLICATION_FIX_REPORT.md` §0 のコミット、`docs/REVIEW_REQUEST_2.md`、CI の記録。
- 影響: force-push で `main` を書き換えた履歴にしても、GitHub は旧コミットを参照の無いコミットとして持ち続ける。SHA が分かれば、`/commit/<SHA>` と `/commit/<SHA>.patch` で中身と作者のメールを読める。GitHub の文書「Removing sensitive data from a repository」も、消すには GitHub Support への依頼が要る、としている。public にすると、追跡文書の 61 個の旧 SHA が、そのまま旧コミットへの道しるべになる。この状態では、A-6 の書き換えの目的（メールを公開しない）が GitHub 側で達成されない。
- 対処案（発注者の判断。監査では何もしていない）:
   1. **（推奨）GitHub のリポジトリを作り直す。** 今の private リポジトリを削除する（または別名にして private のまま残す）。同じ名前で空のリポジトリを作り、書き換えた履歴を push する。今は fork も PR もタグも無い（`ls-remote` に `refs/pull` が無い）ので、失うのは CI の実行記録と設定くらいである。旧オブジェクトが新しいリポジトリに入らないことが確実になる。作り直した後、public にする前に、旧 SHA（例: `13b44e5`）の `/commit/` が 404 になることを確かめる。
   2. force-push した後、public にする前に、GitHub Support に旧コミットのキャッシュと、参照の無いコミットの消去を頼む。終わるまで public にしない。
   3. 受け入れる（旧 SHA を知る人は旧コミットを読める）。推奨しない。
- 付随（低）: 追跡文書の 61 個の旧 SHA は、書き換えた履歴では無効なリンクになる。直すなら、`.git/filter-repo/commit-map` で新しい SHA に置き換えられる（通常のコミット）。案 1 を取るなら、旧 SHA はどこも指さない文字列になるので、急がない。
- ローカルの注意: 書き換え前のバックアップ（`git bundle`）が、リポジトリの外（デスクトップの直下）にある。旧履歴（個人のメール）を含むので、どこにも上げないこと。

### B-25 README の冒頭と About の Pages デモ URL — 未実施（公開後タスク）

- Pages はまだ無効なので、URL の実在確認はしていない。
- 現状の事実: `README.md` に `https?://` の URL は 0 件で、`demo` はコマンド例のファイル名だけ。`.github/workflows/pages.yml` は `main` にあるが、`workflow_dispatch` だけで、まだ実行していない。
- 公開後にすること（正本 §5）: 発注者の指示で Pages を有効にし、ワークフローの配備結果で実際の URL を確かめる（想定は `https://kokuren333.github.io/CyberSprite/`）→ **README の冒頭**（状態の行の近く）と **About の Website 欄**の両方に載せる → スマホの表示で、両方からリンクを辿れることを確かめる。

### B-26 並走セッションの未コミットの変更 — OK（情報）

- 監査の間の `git status --short` → ` M docs/review/CODEX_REVIEW_R1.md`（別のセッションが §9「2026-11-13 追補」を足している途中）。本書のコミットには入れていない。
- その時点の中身を、B-10〜B-15 と同じ語（ユーザー名、メール、ハンドル、親フォルダ、ホスト名、実名、`C:\Users`、ツールのファイル名、資料サイト、作品名、`discord`）で検索 → 0 件。コミットされた後の最終の版は、同じ検索をもう一度すること。

---

## 7. 対処の順番（提案）

1. **B-24（中）**: GitHub 側の旧履歴の扱いを決める。推奨は、リポジトリを作り直して、書き換えた履歴だけを push すること。これが済むまで public にしない。
2. **B-15（低）**: 旧版の `references.md` の一文を消すかを決める。消すなら、1 の push の前に `--replace-text` を 1 行足してかけ直す（全 SHA がもう一度変わり、本書の SHA も変わる）。
3. 任意: 追跡文書の旧 SHA 61 個の置き換え（B-24 の付随）、`PUBLICATION_FIX_REPORT.md` の 2 行の言い換え（B-15 の 3）、`ci.yml` の `permissions`（B-23）、I-010 / I-012 の承認（B-18）。
4. 並走セッションの `CODEX_REVIEW_R1.md` の追補がコミットされたら、B-26 の検索をもう一度する。
5. 公開の後: B-25。

## 8. 再現の手順（要約）

```text
git ls-files | wc -l                                                 # 1697
git log --all --no-renames --pretty=format: --name-only | sort -u    # 1698 パス、_private/_handoff は 0
git log --all --format='%ae|%ce' | sort | uniq -c                    # 213 件すべて noreply（B-9）
git log --all --format='%an|%cn' | sort | uniq -c                    # 213 件すべて kokuren333
git rev-list --all --objects | git cat-file --batch …                # 2783 blob を正規表現と署名で走査（B-3〜B-15）
git ls-tree -r HEAD | git cat-file --batch …                         # 1433 blob（現行）
git log --all --format=%B                                            # コミットのメッセージ（948 行）
git log --all --oneline -S'<取得の性質の一文の語句>'                 # B-15
git ls-remote https://github.com/kokuren333/CyberSprite.git          # B-24（main = 13b44e5、旧履歴）
grep 13b44e5 .git/filter-repo/commit-map                             # B-24（旧 → 新の対応）
uv run --no-sync python tools/check_licenses.py [--include-dev --extra mcp --extra gui]   # B-18
node tools/check_js_licenses.mjs --check                             # B-18
uv run --no-sync python tools/check_repository.py                    # B-21
uv build --wheel --sdist --out-dir <一時ディレクトリ>                 # B-20
md5sum LICENSE                                                       # B-16
```

走査に使った一時スクリプトは、リポジトリの外に置き、コミットしていない。

---

## 付録 1. 第 1 回監査（2026-11-12）の本文と補遺（保存）

以下は第 1 回の本文をそのまま残したもの（見出しを 1 段下げた）。SHA には、書き換えの**前**の履歴を指すものがある（B-24 の付随）。判定は第 2 回（§0〜§8）を正とする。

## PUBLICATION_AUDIT — 公開前監査（private → public）

- 実施日: 2026-11-12
- 監査担当: Claude Opus 5.5（公開前監査）
- 対象: ローカル `main`（= `origin/main`、198 コミット。差分 0）。履歴の走査は、未 push のローカルブランチも含む `--all`（199 コミット、2,704 blob）で行った
- 範囲: 監査と報告のみ。visibility の変更、履歴の改変、ファイルの削除・書き換えはしていない
- 総括: **グリーンではない。** 秘密鍵・トークン・非公開ディレクトリ・ROM・他製品の資産は見つからなかった。一方で、公開前に発注者の判断が要る「中」が 2 件、通常のコミットで直せる「低」が 3 件ある（§0）

---

### 0. 判定の一覧

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

### 1. 手続

#### A-0 チェックリスト正本の不在 — 問題あり（低）

- 証拠: `cat _handoff/PUBLICATION_AUDIT_CHECKLIST.md` → `No such file or directory`。`_handoff/` にも、`kokuren_future/` の 4 階層下までにも、該当のファイルはない（`find ... -iname "*AUDIT*"`）。
- 対処: 発注の文面（`_handoff/PROMPT_AUDIT.md`）の「重点」5 項目を展開して、本書の A-1〜A-21 を作った。正本ができたら、本書との差を確かめること。

---

### 2. 追跡ファイルの棚卸し

#### A-1 全量の棚卸し — OK

- `git ls-files | wc -l` → **1,669 件**。最上位の内訳: `tests/` 645、`e2e-tests/` 476、`src/` 172、`schemas/` 93、`docs/` 92、`tools/` 54、`assets/` 47、`gui/` 43、`examples/` 21、`skills/` 13、`third_party/` 3、その他（ルートの設定・文書）11。
- 拡張子: json 639、png 468、py 280、md 95、pixhash 63、gitkeep 19、ts 15、tsx 13、jpg 10、txt 9、gif 9、gpl 8、aseprite 8、css 6、mjs 5、jsonl 5、html 4、apng 2、ほか各 1。
- 注意して開いたもの:
  - `.aseprite` 8 件: `tests/roundtrip/p11/*.aseprite` は `tools/m5_acceptance --p11` で CyberSprite 自身が書いたもの（`docs/M5_IMPLEMENTATION_REPORT.md` §65〜68）。`e2e-tests/0{3,4,7}/**/*.aseprite` は E2E の書き出しと、その往復の入力。いずれも自作の絵で、Aseprite の同梱物ではない。
  - `.jpg` 10 件: スライムの合成入力とその変種（`tests/pipeline/corpus/slime/PROVENANCE.txt` に作り方・`provider: user`・Apache-2.0 を明記）。
  - `e2e-tests/06-fresh-session/session.log`: 新規セッションのエージェントの最終報告（日本語の要約）。秘密情報なし。ローカルパスは A-8。
  - `e2e-tests/07-ds-turnaround/discord/`: 発注者の Discord 投稿用に用意した自作の絵 4 点と `caption.txt`。ID・URL・他人の発言は含まない。
  - `tests/e2e/scenarios/*/calls.jsonl`、`transcript.json`: 試験用の呼び出し列。秘密情報なし。

#### A-2 `_private/`・`_handoff/` の混入 — OK

- `.gitignore` の 3 行目・5 行目で除外（`git check-ignore -v _private _handoff` → 両方とも一致）。
- 現行: `git ls-files | grep -E '_private|_handoff'` → 0 件。
- 全履歴: `git log --all --no-renames --name-only` で過去に追跡したことのある 1,684 パスを列挙 → `_private/`・`_handoff/` で始まるパスは 0 件。
- 文書の中に `_private/...` や `_handoff/...` という**パスの名前**は出てくる（規則の説明や記録）。中身の転載はない。名前の扱いは A-10、A-11。

#### A-3 参照画像・スクリーンショット・ROM・重み・実行ファイル — OK

- 追跡中の画像 488 件（png 468、jpg 10、gif 9、apng 2）の置き場所は、`tests/golden`、`tests/pipeline/corpus`、`e2e-tests/0{1..7}`、`examples/`、`docs/design/{gui,img,theme-options}` だけ。`docs/design/gui/*.png` は CyberSprite 自身の GUI の画面（`settings-ja.png` などを目視）。他製品の画面はない。
- 全履歴のパスに `shot`、`aseprite_ref`、`refs`、`e2e-ds`、`.ini`、`cli_help` を含むものは、`gui/scripts/screenshots.mjs`（自製品の GUI を撮る Playwright スクリプト）と `gui/src/theme/prefs.ts` だけ。
- 全履歴の 2,704 blob を、署名で走査した（GB のロゴ列 `CE ED 66 66 …`、GBA のロゴ列 `24 FF AE 51 …`、iNES `NES\x1A`、ZIP、7z、PE、ELF、safetensors のヘッダ）→ **0 件**。
- 重みの拡張子（`.safetensors .ckpt .gguf .pt .pth .onnx .bin`）は、全履歴のパスに 0 件。
- 1 MB を超える blob は 7 件で、すべて自作の作例・較正画像・ベンチ結果 JSON。
- e2e-07 の関門シート（`review/final_review.png`、`review/g1_design_stage1.png`）を目視: 自作のキャラクター「ゼンマイ」と、Codex imagegen の自作原画だけ。参照用の市販スプライトは写っていない。

#### A-4 画像のメタデータ — OK

- PNG / APNG 470 件の `tEXt`・`zTXt`・`iTXt`・`eXIf`・`iCCP` を抽出 → **0 件**。
- JPEG 10 件: APP0（JFIF）だけ。Exif（APP1）、コメント（COM）なし。
- GIF 9 件: `NETSCAPE2.0`（ループ指定）だけ。2 件で検出した `21 FE` は LZW データ内の偶然の並びで、コメントの拡張ではない（中身を読んで確認）。
- `.aseprite` 8 件: `<ユーザー名>`・`Users`・`Aseprite` の文字列なし。

---

### 3. 秘密情報

走査の方法: 現行のツリーは `git grep`、全履歴は `git rev-list --all --objects` で得た 2,704 blob を `git cat-file --batch` で読み、同じ正規表現をかけた（スクリプトはリポジトリの外の一時ディレクトリに置いた）。

#### A-5 API キー・トークン・パスワード・秘密鍵 — OK

- 検索した型: `sk-…`（OpenAI）、`sk-ant-…`、`ghp_/gho_/ghu_/ghs_/ghr_/github_pat_`、`AKIA…`、`AIza…`、`xox[abpr]-`、`hf_…`、`-----BEGIN … PRIVATE KEY`、Discord のボットトークンの形、`password|secret|api_key = "…"` の代入。
- 現行・全履歴とも **0 件**。代入の形で当たったのは試験用の固定値（`token="test-token"`、`"playwright-fixture-token"`、`"local-test-token"`）だけ。
- 環境変数の名前（`GH_TOKEN`、`GITHUB_TOKEN`）は、`docs/UPSTREAM_PROGRESS.md:12` と `docs/UPSTREAM_REPORT.md:46` で「未設定」と書いているだけで、値はない。
- `.gitignore` で `.env`、`.env.*`、`*.local.json`、`.claude/settings.local.json` を除外済み。

#### A-6 コミットの作者・コミッターのメール — **問題あり（中）**

- 証拠: `git log --all --format='%an <%ae>|%cn <%ce>' | sort | uniq -c` → **199 コミットすべてが、作者・コミッターとも発注者の個人の Gmail アドレス**（本書ではアドレスを伏せる）。うち 198 件は push 済みの `origin/main`。
- 影響: public にすると、誰でもコミットの `.patch`、API、`git log` で読める。本文の走査（A-7）では出てこない経路である。
- 対処案（どれを選ぶかは発注者の判断。監査では何もしていない）:
  1. **受け入れる。** 今後のコミットだけ GitHub の noreply アドレス（`<ID>+kokuren333@users.noreply.github.com`）にする。GitHub の設定「Keep my email addresses private」と「Block command line pushes that expose my email」を有効にする。
  2. **公開前に履歴を書き換える。** `git filter-repo --mailmap` で作者・コミッターを noreply に置き換え、force-push する。全コミットの SHA が変わるので、文書に書いた SHA（CI の記録、`REVIEW_REQUEST_2` など）と、未 push のローカルブランチの付け替えが要る。破壊的な操作なので、発注者の明示の指示が要る。
  3. **新しいリポジトリに、履歴をまとめて 1 から入れる。** 履歴の価値（来歴、判断の記録）を捨てることになる。

#### A-7 本文中の個人メール — OK

- 現行のツリーのメールアドレスは、`gui/LICENSES_JS.txt`、`third_party/licenses/gui-bundle.txt`、`uv.lock` の第三者の著作権表示（ライセンスの本文として必要なもの）と、コミットの帰属の `noreply@anthropic.com` だけ。それ以外は 0 件。
- 発注者の Gmail アドレス（ローカル部を含む）は、現行・全履歴の本文とも 0 件（`@gmail.com` の当たりは第三者の LICENSE 本文 2 blob だけ）。

#### A-8 ローカル絶対パス — 問題あり（低）

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

#### A-9 Discord の ID 類 — OK

- Webhook の URL、ボットトークンの形、`discord|channel|guild|user` の近くの 17〜20 桁の数字（snowflake）→ 現行・全履歴とも 0 件。
- `discord` の語は、投稿用ファイルの置き場所の説明と、第三者パッケージのメタデータ（`docs/reference/pixelize_license_audit.json` の `extra == "discord"`）だけ。

#### A-10 外部の協力者との DM の原文転載 — OK（注記 1 件、低）

- 方法: 非公開の要約 `_handoff/<相手のハンドル>_DM_INSIGHTS.md`（リポジトリ外）から特徴的な語句を 39 個選び、現行・全履歴の全 blob（画像と第三者 LICENSE を除く）で検索した。語句の例: 本人の発言の断片、ハンドル（`<Discord のハンドル>`）、本人の作品名、自作エミュレータ名、共有された作品のキャラクター名、生データのディレクトリ名、`.gba`、`.nds`。
- 結果: **原文の引用・ハンドル・本人の作品名は 0 件。** 文書が使うのは「DM 知見 1〜7」という番号つきの言い換えだけ（`docs/REVIEW_1.md`、`skills/workflows/*.md`、`docs/FIX_ROUND_1_REPORT.md:284`）。発言の主の名前は書いていない。
- 注記（低）: `docs/review/CODEX_REVIEW_R1.md:8` に、非公開ファイルの名前 `_handoff/<相手のハンドル>_DM_INSIGHTS.md` がそのまま出ている。第三者の Discord ハンドルに由来する名前で、DM の存在と相手が分かる。対処案: 「DM 知見メモ（非公開）」に言い換える通常のコミット。履歴の旧版は残る（A-6 で書き換えるなら同時に消せる）。
- 参考: 発注者自身の過去の試作の名前「モクリ」は `docs/REVIEW_1.md` と `e2e-tests/07-ds-turnaround/RECORD.md` に出るが、発注者の作品の名前で、DM の転載ではない。

#### A-11 非公開の参照取得コネクタの記述 — **問題あり（要判断、中）**

- 証拠: ツール名・接続の方法・取得の性質を表す語で `git grep` → 9 か所。中心は `skills/workflows/references.md` §2.2（28〜41 行）。（2026-11-12 公開前仕上げで、本項の引用を一般化した。原文の記述は I-2002 で追跡文書から外した）
  - 発注者の私物のツール（`_handoff/` の中）を**標準の手順**とし、検索・取得・一覧のコマンド例を載せている。
  - ツールを使うための、利用者のブラウザの起動のしかたを書いている。
  - 41 行目に、資料サイトが自動の取得を断っていることと、ツールがそれを利用者のブラウザ経由で取得する作りであることを明記している。
  - 同じ方針が `docs/SPEC.md:400`、`docs/DECISIONS.md:354`（I-1807）、`docs/FIX_ROUND_1_REPORT.md:466`、`skills/workflows/turnaround-parts.md:58`、`docs/reference/PROVENANCE_LOG.md:78`、`e2e-tests/07-ds-turnaround/RECORD.md:19` にある。
- 秘密情報の漏れではない（ツールの中身はリポジトリにない）。しかし public にすると、「資料サイトが断っている自動取得を、実ブラウザ経由で通す手順を標準にしているプロジェクト」と公に読める。サイトの規約、プロジェクトの評判、クリーンルームの説明の一貫性に関わる。上流のレビュー（`docs/REVIEW_1.md` §3.5、§6 の 2）も、このツールを標準にすることを勧めていない。
- 対処案（発注者の判断。I-1807 は発注者の指示なので、監査では変えない）:
  1. 公開版の `references.md` §2.2 は「人がブラウザで見て保存したものを入れる」を標準にし、コネクタの節（コマンド例、リモートデバッグ、断りを通す旨）は `_private/` か `_handoff/` の非公開の手順書へ移す。`SPEC.md:400` と `turnaround-parts.md:58` の文言も合わせる。DECISIONS には変更の理由を 1 行書く。
  2. 現状のまま公開する（リスクを受け入れる）。その場合も、41 行目の「断っているのを通す」の一文は、公開の文書に残す必要が薄い。

---

### 4. ライセンス整合

#### A-12 LICENSE — OK

- `LICENSE` は Apache License 2.0 の全文。MD5 `3b83ef96387f14655fc854ddc3c6bd57` は、Apache 財団が配る `LICENSE-2.0.txt` の既知の値と一致（改変なし）。
- `pyproject.toml`: `license = "Apache-2.0"`、`license-files = ["LICENSE", "NOTICE", "third_party/licenses/*.txt"]`。

#### A-13 NOTICE と実物の一致 — OK

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

#### A-14 THIRD_PARTY 台帳 — OK（情報 2 件）

- `tools/check_licenses.py` → 実行時依存 10 件すべて `OK`（annotated-types、aseprite、click、colorama、numpy、pillow、pydantic、pydantic_core、typing_extensions、typing-inspection）。台帳 §1 の版・SPDX と一致。
- `node tools/check_js_licenses.mjs --check` → `Approved 46 installed JS packages; opened and checked license grants.`（台帳の「全 46 件」と一致）。
- `pyproject.toml` の固定版（numpy 2.3.4、pydantic 2.12.3、click 8.3.0、aseprite 0.1.0、mcp 2.3.0、starlette 1.10.0、uvicorn 0.54.0、websockets 16.0、jsonschema 4.26.0）は台帳 §1 の版と一致。
- 情報: 限定例外 **I-010**（pathspec の MPL-2.0。ビルド時だけで、配布物には入らない）と **I-012**（pywin32 に同梱される未使用の adodbapi の LGPL-2.1、MIT-0 / 0BSD の明記）が、台帳の冒頭で「発注者の事後承認待ち」のまま。公開の可否には影響しないが、公開と同時か前に承認を済ませると、台帳の表記がすっきりする。

#### A-15 組み込み OSS の帰属（PixelOE ほか） — OK

- PixelOE: `src/cybersprite/pipeline/external/pixeloe.py` は、利用者が自分で入れた `pixeloe==1.0.0` を実行時に読み込むアダプタだけ。`pyproject.toml` の extra `pixeloe = []` は空。コードの写し・同梱はない（`git grep -i pixeloe -- src` はアダプタと呼び出し側だけ）。したがって NOTICE への帰属は不要で、台帳 §5（利用者導入のみ）の扱いと一致する。台帳 §2 の表記「Apache-2.0（Copyright 2024 KohakuBlueLeaf）」は、`PROVENANCE_LOG` の原文確認の記録と一致。
- pixel-art-fixer、proper-pixel-art も同じ形（アダプタだけ、§5）。アダプタの導入案内に、推移依存の LGPL / GPL の可能性を明示している（`pixel_art_fixer.py:10`、`proper_pixel_art.py:10`）。
- pixeldetector、ComfyUI-PixelArt-Detector、pyxelate は「設計の参照のみ」（移植しない。L-03）。
- 組み込みパレット（`src/cybersprite/data/palettes/`）は自作（Apache-2.0 / CC0-1.0）と台帳に記録済み。Lospec のパレットは同梱しない（L-07）。
- フォント: 第三者フォントの同梱なし（L-06）。

#### A-16 配布物（wheel）の中身 — OK

- `uv build --wheel --out-dir <一時ディレクトリ>` → `cybersprite-0.1.0-py3-none-any.whl`（227 項目）。
- `dist-info/licenses/` に `LICENSE`、`NOTICE`、`third_party/licenses/gui-bundle.txt` が入っている。
- wheel の中に `_private`、`_handoff`、`e2e-tests`、`tests/` はない。全項目に `<ユーザー名>`・`<メールのローカル部>`・`<相手のハンドル>`・`kokuren_future` の文字列なし。
- ビルドは作業ツリーを変えていない（`git status` は監査前と同じ 2 件の未追跡だけ）。

---

### 5. クリーンルーム

#### A-17 Aseprite / LibreSprite 由来のコード・アイコン・文面 — OK

- `tools/check_repository.py` → `Clean-room paths and core imports: OK`。
- `git grep -i -E 'igara|capello|dacap|libresprite|aseprite\.org|github\.com/aseprite'` を `src gui assets schemas skills tests tools` にかけた → 0 件（第三者 LICENSE の束を除く）。
- 他者の `Copyright` 表示は、NOTICE・台帳・報告書の帰属の記録だけ。`src/` に第三者の著作権ヘッダはない。
- `aseprite` の語の出どころは、`.aseprite` 形式の読み書き（`formats/aseprite_io.py` は PyPI の mattt/aseprite-py、Apache-2.0 のアダプタ）と、Op・CLI の名前（`import_aseprite` / `export_aseprite`）。製品のコードではない。
- アイコン: `assets/ui/icons/*.csprite` 40 件は CyberSprite のプロジェクト形式の自作ドット絵と、それを描く生成スクリプト（`assets/ui/icons/tools/`）。
- GUI の文言: `gui/src/i18n/en.json` の 151 項目を読んだ。言い回しは独自（例: 「Commercial OK with use restrictions」「Display settings are kept in this browser only.」）。
- `docs/reference/ASEPRITE_INVENTORY.md`: 自分の言葉での機能の棚卸し（規則を冒頭に明記）。スクリーンショットはリポジトリになく、`_private/aseprite_ref/shots/` にだけある（A-2 で履歴にも入っていないことを確認）。メニューの第 1 階層の分類（ファイル・編集・スプライト・レイヤー・フレーム・選択・表示・ヘルプ）は、ドット絵エディタで一般的な語で、CyberSprite の GUI の第 1 階層にも同じ並び（＋エージェント）がある。文面の写しではないので OK とする。気になる場合は、並び順を変えるかどうかを GUI 担当（Opus）に諮る程度の話である。
- 他人の絵の参照: `docs/reference/PROVENANCE_LOG.md` の該当行（DS 世代の市販スプライト 4 点）は、作品名を書かず、統計値だけを残している。画像は `_private/e2e-ds/refs/` にだけあり、履歴に入ったことはない。

#### A-18 生成画像・作例の権利表記 — OK（情報）

- `tests/pipeline/corpus/generated/`（imagegen の 16 枚）は、`README.md` と `manifest.json` に全プロンプト・日付・SHA-256 を記録し、モデル ID と出力ライセンスを `unknown` と明記している。既存のキャラクターや第三者の画像は入力していない、とある。
- e2e-07 の原画（`zenmai*.csprite/source/`）も Codex imagegen の自作原画。
- 情報: OpenAI の規約上、出力の権利は利用者側にある（台帳 L-12）。公開を妨げない。

#### A-19 CI ワークフロー — OK（改善案）

- 追跡中のワークフローは `.github/workflows/ci.yml` だけ。`on: [push, pull_request]`、`secrets.*` の参照なし、`pull_request_target` なし、self-hosted ランナーなし。fork からの PR に秘密が渡る経路はない。
- 改善案（任意）: 先頭に `permissions: contents: read` を書き、`GITHUB_TOKEN` の権限を最小にする。

---

### 6. 公開後のタスク

#### A-20 README / About の Pages デモ URL — 未実施（公開後タスク）

- Pages はまだ無効なので、URL の実在確認はしていない。
- 現状の事実: `README.md` に URL は 0 件（`grep -o 'https\?://…' README.md` → なし。`demo` はコマンド例のファイル名だけ）。Pages のデモ（`.github/workflows/pages.yml`、`gui/src/demo/`、`docs/DEMO_REPORT.md`）は、**未 push のローカルブランチ `fixr1-demo`（コミット `bc25868`）にだけ**あり、`main` / `origin/main` には入っていない。
- 公開後にすること: (1) デモを `main` に統合して Pages を有効にする、(2) README と About に URL を載せる、(3) その URL を実際に開いて表示を確かめる。

#### A-21 未追跡ファイル — OK

- `docs/REVIEW_2.md`（238 行）と `docs/review/CODEX_REVIEW_R2.md`（409 行）は未追跡で、今回のコミットには含めていない。
- 先回りして同じ語で走査した: `<ユーザー名>`、`gmail`、`<メールのローカル部>`、`<相手のハンドル>`、`tk_`、`token`、`api key`、`discord`、`C:\Users`、作品名 → 当たりは Python の `from …` と `ROM` の大文字小文字を無視した誤検出だけ。コミットしても A-5〜A-10 の観点では問題ない。

---

### 7. 対処の順番（提案）

1. **A-6（中）**: メールの扱いを決める（受け入れて今後だけ noreply にする / 公開前に履歴を書き換える / 新しいリポジトリにする）。履歴を書き換えるなら、A-8 と A-10 の旧版も `--replace-text` で同時に消せる。
2. **A-11（中）**: 参照取得コネクタの記述を公開版に残すかを決める。残さないなら、公開前に通常のコミットで `references.md` §2.2 ほかを書き換える。
3. **A-8、A-10（低）**: 絶対パス 5 ファイルと、ハンドル由来のファイル名 1 か所を、通常のコミットで言い換える。
4. **A-0（低）**: チェックリストの正本を置き、本書との差を確かめる。
5. 情報（A-14 の I-010 / I-012、A-19 の `permissions`）は、公開と前後して片づければよい。

### 8. 再現の手順（要約）

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

### 補遺 A（2026-11-12、公開前仕上げ）: チェックリスト正本との突き合わせ（A-0 の解消）

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
