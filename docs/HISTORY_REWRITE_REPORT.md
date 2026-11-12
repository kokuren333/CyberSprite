# HISTORY_REWRITE_REPORT — 公開前の履歴の書き換え（A-6）

- 実施日: 2026-11-12 23:45 〜 2026-11-13（JST）
- 担当: Claude Opus 5.5（履歴の書き換え担当。サブエージェントは使っていない）
- 発注者の判断: 監査 A-6 の推奨案（公開前に、コミットのメールを noreply にする履歴の書き換え）を採用
- 入力: `docs/PUBLICATION_FIX_REPORT.md` §9（引き継ぎ）、`_handoff/publication_replace_text_required.txt`（必須）、`_handoff/publication_replace_text_optional.txt`（任意。A-11）。どちらも git の管理外

---

## 0. 結果の要約

| 項目 | 結果 |
|---|---|
| 前提（`_handoff/publication_fix.done`、`main` がクリーン、全テスト通過） | 満たしていた（`afeaba1`、2143 passed / 12 skipped） |
| バックアップ | `%USERPROFILE%\Desktop\CyberSprite_pre-rewrite_2026-11-12_afeaba1.bundle`（リポジトリの外。`git bundle verify` 成功） |
| 使った noreply アドレス | `50736503+kokuren333@users.noreply.github.com`（数値 ID は GitHub の API で取得） |
| 全コミットの作者・コミッター | 書き換えの後 214 件、本書の前のコミットまで含めてすべて noreply（個人のアドレスは 0） |
| 置き換えの対象の文字列（全履歴と現行ツリー） | 書き換えの前は 103 か所 → 書き換えの後は **0** |
| コミット数 | 全 42 ブランチの各コミット数が、書き換えの前と一致（全体で 213 → 213） |
| 内容の不変 | 213 組すべてで、変わったファイルが「旧版に置き換えを当てたもの」と一致（不一致 0） |
| 全テスト（書き換えの後） | 2143 passed / 12 skipped（書き換えの前と同じ） |
| CI（force-push の前、一時ブランチ） | 6 ジョブすべて成功（Windows / Linux、Python 3.12 / 3.13、GUI） |
| push | `origin/main` を `13b44e5` → `b7a44f1` に force-push（`--force-with-lease`）。補遺のコミット `4354b7a` と本書も push |
| **残る問題** | **B-24（中）: GitHub は旧コミットを SHA で読める状態のまま**（§6）。B-15（低）: 読点の入った一文が旧版の 2 コミットに残る（§6） |

---

## 1. 前提の確認

| 確認 | 結果 |
|---|---|
| `_handoff/publication_fix.done` | あり |
| `git status --porcelain` | 0 行。`main` = `afeaba1` |
| `uv run pytest -q`（書き換えの前） | **2143 passed, 12 skipped**（586 秒）。`PUBLICATION_FIX_REPORT.md` §10 の数値と同じ。skip は GPU、シンボリックリンクの権限、利用者が導入する外部方式 |
| ワークツリー 22 本（`CyberSprite-wt/`） | すべてクリーン（変更 0） |
| リモート | `origin/main` = GitHub の `main` = `13b44e5`（`git ls-remote` で一致を確認） |

---

## 2. 安全確保（バックアップ）

- 場所: **`%USERPROFILE%\Desktop\CyberSprite_pre-rewrite_2026-11-12_afeaba1.bundle`**（25,150,290 バイト。デスクトップの直下。ユーザー名を追跡ファイルに書かないため、環境変数の形で書く）
- 作り方: `git bundle create <上のパス> --all`（ローカルの全ブランチ 42 本、`origin` の追跡ブランチ、HEAD を含む 67 の参照）
- 検証: `git bundle verify` → `is okay`、`The bundle records a complete history`。さらに、このバンドルから `git clone --mirror` で復元し、`main` = `afeaba1`、ブランチ 42 本、`git fsck` でエラー 0 を確かめた。
- 注意: このバンドルは**書き換えの前の履歴（個人のメール、ローカルのパス、ハンドル由来の名前）をそのまま含む**。どこにも上げないこと。不要になったら発注者が削除する。

戻す手順（必要なときだけ）: `git clone --mirror <バンドル> restore.git` で旧履歴のすべての参照が戻る。

---

## 3. noreply アドレスと設定

- `https://api.github.com/users/kokuren333` から数値 ID **50736503** を得た。アドレスは **`50736503+kokuren333@users.noreply.github.com`**。
  - 指示は `gh api` だったが、この PC には `gh` が無い。同じ公開の API を直接読んだ。資格情報マネージャーの認証情報は、PowerShell からの取り出しには失敗したが、この API は認証なしで読める。push と CI の照会では、git の資格情報マネージャーを使った（トークンは表示も保存もしていない）。
- このリポジトリのローカル設定: `git config --local user.email 50736503+kokuren333@users.noreply.github.com`、`user.name kokuren333`。**グローバル設定は変えていない**（グローバルは個人のアドレスのまま。ほかのリポジトリでは個人のアドレスが使われる）。
- 作者名 `kokuren333` は GitHub のハンドルで、メール由来ではないので、そのまま残した。

---

## 4. 書き換え

### 4.1 道具と引数

- `git-filter-repo`（`pip install --user git-filter-repo`、版 `a40bce548d2c`。リポジトリの外に導入。リポジトリの依存には入れていない）
- 実行（2026-11-12 23:55 JST）:

```text
python -m git_filter_repo --force \
  --mailmap <mailmap> \
  --replace-text <必須の一覧と任意の一覧を、この順に連結したもの> \
  --prune-empty never --prune-degenerate never
```

- mailmap は 1 行（旧の個人アドレス → noreply、名前は `kokuren333`）。
- `--prune-empty never` と `--prune-degenerate never` は、置き換えで中身が同じになったコミットが消えて、コミット数が変わるのを防ぐため。
- `--force` は、ワークツリーが複数あるため（filter-repo の安全確認が止める）。先に `git clone --mirror` の複製で同じ引数を試し、結果（§5 の各数値）が一致することを確かめてから、本体にかけた。
- 置き換えは、一覧の上から順に当たる（filter-repo は文字列の置き換えを一覧の順に適用する）。一覧は「長いもの・具体的なものが先」に並んでいて、複製で、短い形が先に当たって長い形が残る事故が無いことを確かめた（§5.2 の 0 件）。

### 4.2 一覧の扱い

- **必須**（A-8 のパス 4 行、A-10 の名前 3 行）: すべて当てた。
- **任意**（A-11 の 6 行）: 指示どおり当てた。このうち最後の行は `docs/REVIEW_2.md` の 1 行（上流のレビューの本文）を言い換えるもので、現行のツリーでも、この 1 行だけが変わった（§5.4）。
- **実名**: 発注者の実名を、この PC のアカウントの登録情報から特定し、漢字（空白なし、半角空白、全角空白）、姓だけ、ローマ字（姓名の順と名姓の順、ヘボン式と訓令式、大文字・小文字を区別しない）で、現行のツリーと全履歴の blob とコミットのメッセージを検索した。**書き換えの前から 0 件**だったので、一覧には足していない。実名そのものは、本書にもどの追跡ファイルにも書いていない。あわせて、この PC に登録されている別の個人アドレスとそのローカル部も検索し、0 件だった。

### 4.3 書き換えの後のローカルの整理

- `filter-repo` は `origin` のリモートを外し、`origin` の追跡ブランチを消す。**force-push までは `git fetch` をしない**（旧コミットが追跡ブランチで戻り、`git log --all` に旧メールが出るため）。`origin` は push の直前に付け直した。
- 22 本のワークツリーは、インデックスが旧版のままだった。各ワークツリーの差分が「置き換えの対象のファイルだけ」であることを確かめてから、`git reset --hard` で書き換えたブランチに合わせた（全部クリーンになった）。

---

## 5. 検証

### 5.1 メール

| 検査 | 書き換えの前 | 書き換えの後 |
|---|---|---|
| `git log --all --format='%ae\|%ce'` | 213 件すべて個人の Gmail | **213 件すべて noreply**（その後の並走のコミット `b7a44f1` と補遺の `4354b7a` を含めて、本書の前で 214 件 + 1 件、すべて noreply） |
| `git log --all --format='%an\|%cn'` | 213 件すべて `kokuren333` | 同じ |
| 旧アドレス（全体とローカル部）を全履歴の blob とコミットのメッセージで検索 | blob 0 / メッセージの本文 0（ヘッダーにだけあった） | **0** |
| 現行のツリー | 0 | **0** |

### 5.2 置き換えの対象（全履歴の blob とコミットのメッセージ、全ブランチ）

一覧の左辺（13 行）そのものを、全履歴の blob（2,788 → 2,783 個）とメッセージで数えた。行どうしが部分文字列の関係にあるので、合計は重複を含む。

| 対象 | 書き換えの前 | 書き換えの後 |
|---|---|---|
| A-8 ユーザー名を含むパス（4 行。重複を除いた実数は 21 か所: スラッシュ形 17〔うち `_private/gen-check/` 6、外部環境 6〕、バックスラッシュ形 4） | 33（重複込み） | **0** |
| A-10 ハンドル由来の名前（3 行。実数 2 か所: ファイル名と見出し） | 3（重複込み） | **0** |
| A-11 任意の 6 行 | 67（重複込み） | **0** |
| **合計** | **103** | **0** |
| 現行のツリー（`HEAD`） | 0 | **0** |

参考（対象ではないが確かめたもの）: ユーザー名そのもの（大文字・小文字を区別しない）は書き換えの前 21 → 後 **0**。ハンドル由来の語は 2 → **0**。親フォルダの名前（ユーザー名を含まない、ハンドルを含むだけのもの）は、監査書の検索の記録として 8 か所残る（GitHub のハンドルは公開情報なので、そのまま）。ツールの名前だけ（拡張子なし）は、監査書と仕上げの報告の検索の型として 3 か所残る（B-15 の 2・3）。

### 5.3 コミット数と内容の不変

- 全体: `git rev-list --all --count` 213 → **213**。
- ブランチごと: 42 本すべてで `git rev-list --count <ブランチ>` が書き換えの前と一致。
- 内容: `.git/filter-repo/commit-map` の 213 組すべてについて、旧コミットと新コミットの木を `git diff-tree -r` で比べた。違いのあるファイルは延べ 654 件で、**すべてが「旧版の blob に一覧の置き換えを当てたもの」とバイト単位で一致**（不一致 0）。
- メタデータ: 作者名・コミッター名・作者日時・コミット日時・親の数・メッセージを 213 組で比べた。違いは 1 件だけで、メッセージ中の短縮 SHA を filter-repo が新しい SHA に直したもの（`75a7358` の旧コミット。中身の文は同じ）。

### 5.4 最終のツリー

- 書き換えの前の `main`（`afeaba1`）と後の `main`（`d2cf0e8`）の木の比較: **`docs/REVIEW_2.md` の 1 行だけ**（任意の一覧の最後の行による言い換え）。それ以外のファイルは全部同じ。
- ほかのブランチの先端の差分も、置き換えの対象を含むファイル（`docs/UPSTREAM_REPORT.md`、`docs/review/CODEX_REVIEW_R1.md`、`e2e-tests/06-fresh-session/` の 2 つ、`docs/GENERATION.md`、`docs/R1_F2_REPORT.md`、`docs/DECISIONS.md`、`docs/FIX_ROUND_1_REPORT.md`、`skills/workflows/references.md`）だけ。

### 5.5 テストと CI

| 検査 | 結果 |
|---|---|
| `uv run pytest -q`（書き換えの前、`afeaba1`） | 2143 passed, 12 skipped（586 秒） |
| `uv run pytest -q`（書き換えの後、`d2cf0e8`） | **2143 passed, 12 skipped**（1,146 秒。並走セッションと CPU を分け合ったため遅い） |
| CI（GitHub Actions、一時ブランチ `rewrite-ci-check` = `b7a44f1`） | **6 ジョブすべて成功**: core（ubuntu-latest / windows-latest × Python 3.12 / 3.13）、gui（ubuntu-24.04、windows-latest）。run `43246345965`。確認の後、一時ブランチは削除した |

---

## 6. push の結果と、残る問題

### 6.1 push

| 操作 | 結果 |
|---|---|
| `git push origin main:refs/heads/rewrite-ci-check` | CI のための一時ブランチ。CI が成功した後に `git push origin --delete rewrite-ci-check` |
| `git push --force-with-lease=main:13b44e5… origin main:main` | **`+ 13b44e5...b7a44f1 main -> main (forced update)`**（GitHub の `main` が旧の `13b44e5` のときだけ上書きする条件つき） |
| 補遺のコミット（`4354b7a`、`docs/PUBLICATION_AUDIT.md` の補遺 B） | push 済み（fast-forward） |
| 本書のコミット | push 済み（本書のコミット自体も noreply） |
| `git ls-remote origin` | `refs/heads/main` と `HEAD` だけ。ほかのブランチ、タグ、PR の参照は無い |

**公開の対象は `main` だけ**とした。ローカルの `fixr1-*`、`m*`、`r1-*` などのブランチ（統合済みの作業用）は書き換えたが、push していない（GitHub にも元から無い）。

### 6.2 B-24（中）: GitHub 上の旧コミット — 未解消

force-push の後に GitHub の API で確かめた:

- `GET /repos/kokuren333/CyberSprite/commits/13b44e5…`（旧の先端）→ **HTTP 200**。作者のメールのドメインは `gmail.com`（旧のまま）。
- つまり、**SHA を知っていれば、旧コミットとその作者のメール、旧 blob（ローカルのパス、ハンドル由来の名前）を読める**。いまは private なので見られるのは権限のある人だけだが、public にすると誰でも読める。追跡文書には旧 SHA が多数残っていて、それが手がかりになる（監査 B-24 の付随）。
- **public にする前に、発注者が次のどちらかを決める必要がある**（監査 B-24 の対処案）:
  1. （推奨）GitHub のリポジトリを作り直す。いまのリポジトリを削除するか別名にして private のまま残し、同じ名前で空のリポジトリを作り、書き換えた `main` を push する。作り直した後、旧 SHA の `/commit/` が 404 になることを確かめる。
  2. GitHub Support に、参照の無い旧コミットとキャッシュの消去を頼む。終わるまで public にしない。
- 書き換え担当は、リポジトリの削除と作り直しをしていない（外に向けた取り消せない操作で、指示の範囲に無いため）。

### 6.3 B-15（低）: 読点の入った一文

- 並走の監査（第 2 回）が見つけた。任意の一覧の 5 行目は、ある一文を読点なしで書いていたが、旧版の `skills/workflows/references.md`（2 コミット）では途中に読点がある。そのため当たらず、全履歴に 2 か所残る（ツールのパスやファイル名ではなく、取得の性質を述べた一文）。
- この 1 行を当てる置き換えのファイルを `_handoff/publication_replace_text_optional_b15.txt`（git の管理外）に用意した。
- **今回はかけ直していない。** 理由: (1) かけ直すと、その 2 コミットより後の全 SHA がもう一度変わり、書き換えの後に並走セッションが書いた文書（第 2 回の監査書、編集中の `CODEX_REVIEW_R1.md` の追補）の SHA が無効になる。(2) filter-repo は最後に作業ツリーを `reset --hard` する。並走セッションの未コミットの編集（`docs/review/CODEX_REVIEW_R1.md`）を消してしまう。(3) B-24 の対処案 1 を取るなら、その push の前に 1 回かければ済む。

---

## 7. 並走していたセッション

- 書き換えの後、別の監査セッションが `main` に `b7a44f1`（第 2 回の監査、`docs/PUBLICATION_AUDIT.md` だけ）をコミットした。新しいローカル設定のため noreply で作られている。対象の文字列・メール・実名で走査し 0 件であることを確かめてから、そのまま force-push に含めた。
- 別のセッションが `docs/review/CODEX_REVIEW_R1.md` を未コミットで編集している。本書と補遺のコミットには入れていない。ワークツリーの `reset` もしていない。コミットされたら、同じ走査をもう一度すること（監査 B-26）。

---

## 8. 発注者に残すこと

1. **B-24 の判断（public にする前に必須）**: リポジトリを作り直すか、GitHub Support に頼むか。作り直すなら、その前に B-15 の 1 行でかけ直すかも決める。
2. 文書の旧 SHA: 書き換えの前の SHA は失効した。旧 → 新の対応はローカルの `.git/filter-repo/commit-map`（公開しない）。直すなら通常のコミットで置き換える（B-24 で作り直すなら急がない）。
3. バックアップのバンドル（§2）は旧の個人情報を含む。保管か削除を決める。
4. ローカルの作業ブランチとワークツリー（`CyberSprite-wt/` の 22 本）は書き換えた状態で残した。不要なら削除してよい。
5. グローバルの `user.email` は個人のアドレスのまま。ほかの公開リポジトリでも noreply にするなら、別途設定する。
