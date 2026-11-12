# REPO_RECREATION_REPORT — GitHub リポジトリの作り直し（PR-01）

- 実施日: 2026-11-13（JST）
- 担当: Claude Opus 5.5（リポジトリ作り直し担当。サブエージェントは使っていない）
- 入力: `docs/PUBLICATION_REVIEW.md`（総合判定「条件つき可」。必須は PR-01 の 1 件）。発注者は §4.4 の対処案 1（作り直して `main` だけを push）を採用した
- 範囲: 作り直しと検証まで。**visibility の変更（public 化）は行っていない。** 旧リポジトリは削除していない

---

## 0. 結果の要約

| 項目 | 結果 |
|---|---|
| PR-04（未コミットの編集 2 件） | 差分を読んで確かめ、コミットした（`1cb0f39`）。§1 |
| PR-02（コネクタを標準と現在形で書いた 4 行） | 4 行に「のちI-2002で標準から外した」を足した（`270e2de`）。§2 |
| 旧リポジトリ | `kokuren333/CyberSprite-pre-public-20261113` にリネーム。**private のまま存在**。以後触らない |
| 新リポジトリ | `kokuren333/CyberSprite` を **private**・空（自動生成なし）で作成 |
| PR-03（メールの非公開・露出する push の拒否） | **未実施。発注者の手作業（1 分）として残す**。§4 |
| push | `main` だけ（`270e2de`）。他の 41 ブランチとタグは push していない |
| 検証 | 5 項目すべて期待どおり。§6 |
| 資格情報 | Git Credential Manager からメモリ内でだけ取得。表示・保存・記録・コミットしていない |

---

## 1. PR-04 — 未コミットの編集 2 件

作業ツリーにあった `docs/review/CODEX_REVIEW_R1.md`（+260 行、§9 の追補）と `docs/review/CODEX_REVIEW_R2.md`（2026-11-13 の再検証で更新、+151 / −149 行）の差分を、追加行をすべて読んで確かめた。あわせて、メールの形、絶対パス、`/Users/`、`token`・`secret`・`password`・トークンの接頭辞、SNS の名前、`@` で始まる識別子を機械的に検索した。

| 確認 | 結果 |
|---|---|
| 秘密情報（トークン、鍵、パスワード） | 0。`token` の語は GUI の認証方式の説明だけ |
| 個人のメール | 0 |
| 実名 | 0 |
| 第三者のハンドル | 0。両文書とも「協力者の識別子・DM 原文・参照画像を転載していない」と明記している |
| ローカルの絶対パス | 0。出てくるのはリポジトリ相対の `_private/…`、`build/…` と、`$env:TEMP` の変数だけ |
| リポジトリ所有者名 `kokuren333` | 1 か所（R2 の Actions の実行の URL）。所有者名は `NOTICE` などにも既にあり、公開の情報である。ただし、その URL は旧リポジトリの実行を指すので、作り直しの後は辿れない（§7 の PR-07 に含める） |

判断: 捨てずにコミットした（`1cb0f39`）。どちらも、過去のレビューを上書きせず追補・再検証として残す書き方で、監査 A-21 の先行走査の結論とも一致する。

## 2. PR-02 — I-2002 の注記

`PUBLICATION_REVIEW.md` §2.1 が特定した 4 行に、1 句ずつ足した（`270e2de`）。修正報告が既に直した行（`FIX_ROUND_1_REPORT.md` 272、278 行の「I-2002で標準から外した」「のちI-2002で変更」）と表現をそろえた。

| ファイル・行 | 変更 |
|---|---|
| `docs/REVIEW_LOG.md` 14 | 「private connector標準」→「private connector標準（のちI-2002で標準から外した）」 |
| `docs/REVIEW_LOG.md` 23 | 「後続発注指示で標準化済み」→「…標準化済み（のちI-2002で標準から外した）」 |
| `docs/FIX_ROUND_1_REPORT.md` 287 | 「後続発注指示で標準」→「後続発注指示で標準（のちI-2002で標準から外した）」 |
| `docs/FIX_ROUND_1_REPORT.md` 573 | 「connectorは後続発注指示で標準化済み」→「…標準化済み（のちI-2002で標準から外した）」 |

差分は 2 ファイル 4 行の置き換えだけ。改行コードは変えていない。

## 3. リネームと新規作成

GitHub の REST API を使った（`gh` は未導入のまま。winget での導入は不要だった）。資格情報は `git credential fill`（protocol=https / host=github.com）で Git Credential Manager から取り、スクリプトのメモリ内でだけ使った。スクリプトはリポジトリの外の一時ディレクトリに置き、トークンを出力しない作りにした。トークンのスコープは `repo`、`workflow`、`gist`。

**リネームの前の旧リポジトリ**（控え）:

| 照会 | 結果 |
|---|---|
| visibility | private |
| ブランチ | `main` だけ（先端 `ae3937b`） |
| 旧の先端 `13b44e5` | 200（読める。B-24 のとおり） |
| `afeaba1` | 422（もともと push されていない） |
| Actions の実行履歴 | 18 件 |

**操作:**

| 手順 | API | 結果 |
|---|---|---|
| リネーム | `PATCH /repos/kokuren333/CyberSprite`（name） | 200。`kokuren333/CyberSprite-pre-public-20261113`、private |
| 新規作成 | `POST /user/repos`（private、`auto_init: false`） | 201。`kokuren333/CyberSprite`、private、size 0 |
| 空であることの確認 | `GET …/commits` | 409「Git Repository is empty.」 |

## 4. PR-03 — 試行の結果（未実施）

| 設定 | 試行 | 結果 |
|---|---|---|
| メールアドレスを非公開にする | `PATCH /user/email/visibility` | 404。この API には `user` スコープが要り、手元のトークンには無い |
| メールを露出するコマンドラインの push を拒否する | — | 公開の API が無い。画面の操作だけ |

ブラウザを操作する手段もこのセッションには無いため、**発注者の手作業（1 分）** として残す。

> GitHub → Settings → Emails で、「Keep my email addresses private」と「Block command line pushes that expose my email」を有効にする。

今回 push した 220 コミットは、作者・コミッターとも noreply だけである（§6）。この設定が無くても、今回の初期 push の安全性には影響しない。設定は、今後の push（別の PC や、グローバルの `user.email` が個人のアドレスのままの作業ツリーからのコミット）のための防護である。

## 5. push

- `origin` の URL を `https://github.com/kokuren333/CyberSprite.git`（新リポジトリ）に設定し直した。リネームで旧リポジトリへの転送が作られるが、同名の新リポジトリを作った時点でその転送は新リポジトリに置き換わる。push の前に `git ls-remote origin` が 0 行（空）であることを確かめ、旧リポジトリに向いていないことを確認した。
- push の前のローカル: 作業ツリーはクリーン、`main` は 220 コミット、`git log main --format='%ae%n%ce'` は noreply の 1 種類だけ（440 件）、タグ 0。
- `git push origin refs/heads/main:refs/heads/main` だけを行った。`--all`、`--mirror`、`--tags`、force は使っていない。
- push の後の `git ls-remote origin`: `HEAD` と `refs/heads/main` の 2 行だけ（どちらも `270e2de`）。

## 6. 検証

| 確認 | 方法 | 結果 |
|---|---|---|
| **コミット数の一致** | API で `main` の全コミットをページ送りで取得し、ローカルの `git rev-list main` と比べた | **220 = 220**。SHA の集合も完全に一致 |
| 同上（clone） | 新しい一時ディレクトリに clone し直した | `git rev-list --all --count` = **220**。ブランチは `main` だけ |
| **旧 SHA が取得できない** | `GET /repos/kokuren333/CyberSprite/git/commits/<完全な SHA>` | `13b44e5`: **404**、`afeaba1`: **404** |
| 同上（commits API） | `GET …/commits/<SHA>`（完全形・短縮形） | 両方とも 422（No commit found）。旧リポジトリでも未 push の `afeaba1` は 422 を返していたので、これは「無い」の応答である |
| 同上（clone） | clone の中で `git cat-file -t 13b44e5c…` | オブジェクト無し |
| **Actions の実行履歴** | `GET …/actions/runs` | **旧リポジトリから引き継いだ実行は 0 件**（作成直後の空のリポジトリ）。push の後にある実行は、今回の push が起動した CI の 1 件（`270e2de`）だけで、ローカル `main` に無い SHA を指す実行は **0 件**。結果は下の表 |
| **全コミットのメール** | API の全 220 コミットの author / committer、clone の `git log --all --format='%ae\|%ce'` | どちらも **`50736503+kokuren333@users.noreply.github.com` の 1 種類だけ**（220 / 220） |
| **旧リポジトリの存在** | `GET /repos/kokuren333/CyberSprite-pre-public-20261113` | 200、**private**。実行履歴 18 件もそのまま（触っていない） |
| その他 | タグ、リリース、イベント | タグ 0、リリース 0。イベントの API は 0 件（旧 SHA の force-push の記録は新リポジトリには無い） |
| visibility | `GET /repos/kokuren333/CyberSprite` | **private のまま** |

**新リポジトリの CI（push が起動した実行、`270e2de`）:**

| ジョブ | 結果 | 所要（開始〜終了、UTC） |
|---|---|---|
| core (ubuntu-latest, 3.12) | success | 16:11:49〜16:15:46 |
| core (ubuntu-latest, 3.13) | success | 16:11:49〜16:15:51 |
| core (windows-latest, 3.12) | success | 16:11:49〜16:22:26 |
| core (windows-latest, 3.13) | success | 16:11:49〜16:22:36 |
| gui (ubuntu-24.04) | success | 16:11:49〜16:13:29 |
| gui (windows-latest) | success | 16:11:50〜16:16:20 |

**6 ジョブすべて成功**（実行全体の結論 success、2026-11-12 16:11:46〜16:22:37 UTC = 2026-11-13 01:11〜01:22 JST）。本書のコミットの push でもう 1 回実行される（内容は文書だけ）。

作り直しで失ったものは、旧リポジトリの CI の実行履歴 18 件とキャッシュだけである（`PUBLICATION_REVIEW.md` §4.3 の見込みどおり）。旧リポジトリにはそのまま残っている。

## 7. 公開後のタスク（今回は行っていない）

| ID | 内容 | 提案 |
|---|---|---|
| **visibility** | public への切り替え | 今回の範囲外。PR-03 の設定の後で、発注者が行う。切り替えの後は、チェックリスト正本の §5（公開ページの目視）へ |
| **PR-03** | メールの非公開・露出する push の拒否 | §4 の手作業。**public 化と次の push より前**に済ませるのを勧める |
| **PR-07** | 追跡文書に残る書き換え前の SHA（約 65 種）。作り直しで、新リポジトリではどこも指さない文字列になった。`docs/review/CODEX_REVIEW_R2.md` の旧リポジトリの Actions の実行の URL も、同じく辿れない | 急がない。直すなら、対応表で置き換える通常のコミットか、注記。対応表そのものは公開しない（旧 SHA の一覧になる） |
| **PR-08** | バックアップのバンドル（デスクトップ直下、約 25 MB、旧履歴 213 コミット、メールは個人のアドレス）と、`.git/filter-repo/commit-map` | 公開と公開後の確認が済むまで消さない。その後、削除するか、同期も共有もされない場所へ移す。添付や共有に使わない |
| 旧リポジトリ | `CyberSprite-pre-public-20261113`（private、旧履歴と個人のメールを含む実行履歴 18 件） | 誤って public にしないこと。不要になったら発注者の判断で削除してよい（バンドルと同じ性質の控え） |
| PR-05、PR-06 | 公開の後でよい minor（`PUBLICATION_REVIEW.md` §1.3、§2.3） | 変更なし |

## 8. 自分で疑っている箇所

1. **旧 SHA の 404 は API の応答で確かめたもので、ブラウザの `/commit/` のページでは見ていない。** private の間は、ページの確認に認証付きのブラウザが要る。public 化の直後に、未ログインで `/commit/13b44e5` を開いて 404 を確かめるのを勧める。
2. **GitHub のフォークのネットワークやキャッシュとの関係。** 新リポジトリは旧リポジトリと独立に作ったので、オブジェクトの共有は無いはずだが、それを GitHub の内部まで確かめる手段は無い。上の 404 と、clone に旧オブジェクトが無いことで判断した。
3. **Actions の「0 件」の解釈。** 新リポジトリには push の時点で CI の実行が 1 件でき、本書の push でもう 1 件増える。「旧履歴に由来する実行が 0 件」の意味で確かめた。push の前の時点の実行一覧は、作成直後の空のリポジトリだったため照会していない（空のリポジトリでは実行が起動しえない）。
