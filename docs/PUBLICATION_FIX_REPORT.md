# PUBLICATION_FIX_REPORT — 公開前仕上げ

- 実施日: 2026-11-12
- 担当: Claude Opus 5.5（統括。サブエージェントは使っていない）
- 起点: `75a7358`（`main` = `origin/main`）。作業はすべて通常のコミットで積んだ。**push、visibility の変更、履歴の書き換えはしていない**（別セッションの範囲）
- 入力: `docs/PUBLICATION_AUDIT.md`（A-0、A-6〜A-12）、`docs/REVIEW_2.md`（R2-01、R2-11、R2-12、R2-16、R2-25）、`docs/review/CODEX_REVIEW_R2.md`（C-R2-01 は R2-01 と同系）
- 発注者の確定判断: A-6 は履歴の noreply 化を次のセッションで行う。A-11 / R2-11 は参照取得ツールをローカルに残して公開せず、手動で参照を取り込む設計を入れる。低の 3 件（A-8、A-10、A-0）も直す

---

## 0. 一覧

| # | 項目 | 結果 | コミット |
|---|---|---|---|
| 1 | R2-01 CLI の `--out` が経路ガードを通らない | **解消** | `51d829c` |
| 2 | A-11 / R2-11 参照取得ツールを標準手順とする記述 | **解消**（追跡文書から外した。残りは §2.3） | `fc6c079`、`065a102` |
| 3 | 手動の参照の取り込み（新規） | **実装・試験済み**（CLI / MCP / GUI） | `8359c4f` |
| 4 | A-8 ローカルの絶対パス 5 ファイル | **解消**（現行のツリー。履歴は §9） | `52da128` |
| 5 | A-10 協力者のハンドル由来の名前 | **解消**（2 か所。現行のツリー。履歴は §9） | `6b91680` |
| 6 | R2-12 の残り（生成画像の権利、README、MCP のツール数） | **解消** | `fac34db`、`8359c4f` |
| 7 | デモ（`fixr1-demo`）の統合 | **統合済み**。Pages は有効化していない | `f042aa2` |
| 8 | A-0 チェックリスト正本との突き合わせ | **解消**（監査書に補遺 A） | `fcfd5a6` |
| — | 入力の Codex R2 レビューを追跡に入れた | — | `72150aa` |

決定記録: I-2001（R2-01）、I-2002（参照の入手）、I-2003（手動の参照の取り込み）、I-2004（生成画像の権利と sdist）、I-DEMO-1〜3（デモのブランチから）。

---

## 1. R2-01 — CLI の出力を export と同じ事前検査に通す

**対処。** `render` / `preview` / `diff` / `schema` / `convert` の出力先を、export の preflight と同じ関数 `formats.common.guard_output` に通した（`cli/output.py` の `protect_project_output` がこれを呼ぶ）。中身は export と同じで、

- cwd を root とする出力の許可範囲（I-602）。外は `E_PATH_NOT_ALLOWED`。
- `protect_project_output` の予約領域。選んだプロジェクトと、宛先の上にあるすべてのプロジェクトの `project.json`・`source/`・`.cybersprite/`。大文字小文字の別名、`..`、ハードリンク、シンボリックリンクを含む。違反は `E_PATH_NOT_ALLOWED`、`details.reason = "protected_project_file"`、終了コード 4。
- 複数のファイルを書くコマンド（`preview` の複数コマ、`schema all`、`convert` のフレーム・報告・段階画像）は、**全部の宛先を検査してから最初の 1 バイトを書く**。`convert` は `cli_api.convert(..., guard=...)` で、CLI から渡した検査を書き込みの前に呼ぶ。
- 保護されていない通常のファイルは、従来どおり上書きできる（export の `overwrite` は持ち込まない。手順書の `--out check.png` の使い方を壊さないため。I-2001）。

**全経路をそろえた。** MCP と GUI は、Op を通らないファイル出力を持たない（書き出しは export の Op、プレビューは `.cybersprite/previews/`）。GUI の、export 以外の Op の出力パス検査（`server/app.py` の `check_outputs`）が `project.json` の名前だけを見ていたので、同じ予約領域の検査を足した。

**証拠。**
- 再現試験 `tests/unit/test_publication_r2_01.py`（25 件）。R2-01 の 4 つの再現（登録済み原画、ジャーナル、`source/manifest.json`、cwd の外）をそのまま含む。各ケースで、プロジェクトの全ファイルの SHA-256 が不変、同じ宛先への `export image` も同じコードと理由で拒否、その後に `set_pixel` が通る（履歴が壊れていない）ことを確かめる。
- 修正前のコードに対して同じ試験を走らせると **24 / 25 が失敗**した（`git stash` で `src/` だけ戻して実行）。残る 1 件は「通常の出力は従来どおり書ける」の試験で、修正前も通る。
- 既存の試験 3 本の期待値を変えた: `project.json` とハードリンクへの出力は `E_INVALID_ARGS`（2）から `E_PATH_NOT_ALLOWED`（4）へ（export とそろえた）。`tests/e2e/test_cli.py` と `tests/unit/test_fix2.py` は、tmp の出力先に合わせて cwd を tmp にした。
- 文書: `docs/CLI.md`（出力先の規則）。

---

## 2. A-11 / R2-11 — 参照取得ツールを公開の手順から外す

### 2.1 対処

監査 A-11 の 7 か所をすべて書き換えた。公開版の標準は「**人がブラウザなどで見て保存した画像を、手動で取り込む**」。エージェントは資料サイトから自分で取得せず、足りないものは利用者に頼む。

| 場所 | 変更 |
|---|---|
| `skills/workflows/references.md` §2.2 | ツールの所在・コマンド・接続の方法・取得の性質の記述を削除。標準を手動に。チェックリストの項目も差し替え |
| `docs/SPEC.md` §3.6「入手」 | 同上（I-2002） |
| `docs/DECISIONS.md` I-1807 | 「I-2002 で廃止」と明記し、ツールのパスを除いた。I-2002 に変更の理由を 1 行 |
| `docs/FIX_ROUND_1_REPORT.md:466` | I-1807 の写しを同じように一般化 |
| `skills/workflows/turnaround-parts.md:58` | 参照ライブラリと手動の取り込みへ |
| `docs/reference/PROVENANCE_LOG.md:78`（と 80） | 「非公開の参照取得ツール」と一般化。ブラウザの記述を除いた |
| `e2e-tests/07-ds-turnaround/RECORD.md:19` | 試験の事実（403、回避せず、既存のライブラリを読んだ）は残し、言い換えた旨を項の末尾に書いた |

監査の列挙の外で、「ツールが標準である」と現在形で書いていた箇所も直した: `docs/KNOWN_ISSUES.md:25`、`docs/IMPLEMENTATION_PROGRESS.md:44`、`docs/FIX_ROUND_1_REPORT.md`（46、272、278、567 行）、`docs/REVIEW_REQUEST_2.md:100`（追記の形）。監査書 A-11 の証拠の引用（ツールのパス、ブラウザの起動のしかた、取得の性質）も一般化した（`065a102`）。

旧 §2.2 の原文は、git の管理外の `_handoff/tools/REFERENCE_CONNECTOR_PROCEDURE.md` に移した（ローカルに残す、という発注者の判断に従う）。ツール本体（`_handoff/` の中）には触れていない。

### 2.2 証拠

```text
git grep -n -I -E 'sprite_ref|リモートデバッグ|実ブラウザ経由|_handoff/tools'
  → docs/REVIEW_2.md:244 の 1 行だけ（§2.3）
git grep -n 'コネクタ' -- skills docs/SPEC.md e2e-tests README.md AGENTS.md
  → 0 件
```

### 2.3 残したもの（判断が要る）

- **`docs/REVIEW_2.md:244`**（上流のレビュー R2-11 の根拠）が、旧手順書の中身（ツールのパスの一部、サブコマンドの数、ブラウザの起動のしかた、取得の性質）を引用している。他者のレビューの本文なので書き換えていない。外す場合は、履歴の書き換えと同時に `_handoff/publication_replace_text_optional.txt` の最後の行で置き換えられる（§9）。
- `docs/REVIEW_1.md` §3.5・§6、`docs/PUBLICATION_AUDIT.md` A-11 の分析の文、`docs/REVIEW_2.md` の他の行は、「ツールを標準にすることを勧めない」という批評として残した。手順は書いていない。
- 過去の記録の「非公開コネクタは HTTP 403 のため使わず」（`FIX_ROUND_1_REPORT.md:558`、`REVIEW_REQUEST_2.md:82・91`、`IMPLEMENTATION_PROGRESS.md:357`）は、観測の事実として残した。

---

## 3. 手動の参照の取り込み（新規）

### 3.1 設計

発注者の指示「エージェント経由でも GUI 経由でも参照画像を手動で入れられる。GUI 経由の参照も結局はエージェントに渡る」を、Op 1 つで満たした。

- **Op `register_reference`**（ingest、冪等 I）。CLI（`source reference <画像>`）、MCP（同名のツール）、GUI（ソースのタブ、`op.apply`）が同じ Op を通る（原則 5）。
- **置き場所。** SPEC §3.6 は「参照の画像をプロジェクトの `source/` に入れない（プロジェクトは公開されうる）」と定めている。これと「来歴（`source/manifest.json`）に登録する」を両立させるため、**画素は git の管理外の `.cybersprite/references/<ID>/reference_0000.<拡張子>` に置き、manifest には ID・SHA-256・寸法・バイト数・`placed_by`・権利メモ・利用条件だけを書く**。`use: "reference"`、`origin: "manual"`、`provider: "user"`、`url: ""`。元のファイル名と URL は記録しない（題名が入りうるため）。
- **`placed_by` は利用面が決める。** GUI は常に `human-gui`、MCP（actor が `agent:`）は常に `agent`、CLI は既定 `human-cli` で `--placed-by agent` を受ける。別の利用面を名乗ると `E_INVALID_ARGS`。
- **権利メモは必須**（1〜2000 文字）。利用条件は既定 `unknown`。
- **入力。** `file`（パス。MCP では root / allow-dir の制限、`x-cybersprite-path: input`）か `data`（base64）のどちらか一方。上限 5 MiB（`reference_bytes`。ファイルは読む前に stat で検査、`data` は base64 の長さをスキーマで制限し、復号後も検査）。署名で PNG / GIF / JPEG / BMP / WebP を判別し、既存の復号予算（各辺 8192、面積）を通す。GUI の電文の上限 8 MiB に収まる。
- **同じバイト列**の参照がすでにあれば、何も書かずに同じ ID を `duplicate: true` で返す。
- **参照は計測専用。** `import_image` の `source` に参照を渡すと `E_INVALID_ARGS`。GUI は参照に「下絵に表示」のボタンを出さず「計測専用」と表示する。
- **エージェントへの見え方。** `list_sources` が参照について `origin`、`placed_by`、`rights_note`、`files` を返す。MCP では `files` を root 基準のパスに直す。
- **ハッシュ検証（R2-16 の最小対策）。** 配置していない登録済みソース（手動の参照と設計原画）も、`validate` が SHA-256 を照合する。不一致・欠落は新しい規則 **Q-SRC-05（warning）**。error にしないのは、参照は作品の一部ではなく、派生データ（`.cybersprite/`）の削除で書き出しを止めないため（I-2003）。配置済みの不一致は従来どおり Q-SRC-03（error）。
- **既存のデータは不変。** `origin` と `placed_by` は null のとき manifest に書かない（`canonical._ordered`）。`get_source` と `get_info` の出力にも出さない。既存の manifest のバイト列とゴールデンは変わらない。
- **GUI。** `gui/src/components/ReferenceAttach.tsx`（ファイルの選択とドロップ、権利メモ、利用条件、添付）。デモ版では無効（`demoNotAvailable` を表示）。i18n は en / ja に 10 キー。

### 3.2 証拠

- `tests/unit/test_publication_references.py`（29 件）: 登録と来歴の内容、`source/` に画素が入らないこと、ファイル名が manifest に出ないこと、重複、既存の manifest のバイト不変、利用面ごとの `placed_by`（5 通り）と詐称の拒否（5 通り）、dry_run、不正な入力 7 通り、5 MiB の上限（読む前に拒否）、画素の上限、Q-SRC-05（参照の書き換えと設計原画の削除、復元で消えること、warning なので `ok` は true）、import の拒否、`render` と `export` から参照のファイルを守ること、CLI の登録と一覧、**実際の MCP クライアント**での登録（`placed_by: agent`、出力スキーマの検証、root 外のパスの拒否、詐称の拒否）、GUI のサービスでの登録（`human-gui`）。
- `tests/unit/test_quality.py`: 配置を外した原画の改変で Q-SRC-05 が出ること。
- GUI: `gui/src/api/reference.test.ts`（vitest 3 件: base64 の分割境界、引数の形、上限の一致）。Playwright `e2e/workflows.spec.ts` の新しい試験で、**ファイル選択から添付 → CLI の `source list` に `placed_by: human-gui` で載る → 保存されたバイトが元と一致 → 参照に下絵のボタンが無い**、を実ブラウザで確かめた。
- 画面: `docs/design/gui/reference-attach-en.png`、`docs/design/gui/reference-listed-en.png`（自製品の GUI。目視で、既存のパネルの部品と同じ見た目に収まっていることを確かめた）。
- CLI の手動確認（一時ディレクトリ）: 登録 → 重複 → `source list` / `source show` → manifest の中身 → `validate` が警告なし。

### 3.3 文書

`docs/SPEC.md` §3.6（添付の規則）、§5.10（`use` / `origin` / `placed_by`）、§5.11（`reference_bytes`）、§10.12（Op の契約）、§13.2 と付録（Q-SRC-05）。`skills/workflows/references.md` §2.2 は「見つけて保存する（人）→ 手動で取り込む（GUI / CLI / エージェント）→ エージェントが受け取る」の手順に書き換え、`turnaround-parts.md` からの参照も合わせた。`docs/CLI.md`、`docs/MCP.md`、`docs/GUI.md`。スキーマは `tools/gen_schemas.py` で再生成（`schemas/op.register_reference.schema.json`、`schemas/sources.schema.json`）。

### 3.4 自分で疑っている点

1. MCP の標準プロファイルのツール一覧が **99,949 バイト**で、試験の上限 100,000 バイトまで 51 バイトしかない。次にツールを足すと試験が落ちる。上限を上げるか、説明を短くする判断が要る。
2. `.cybersprite/` は「消しても正本は壊れない派生データ」という位置づけで、参照の実体をそこに置いた。消すと Q-SRC-05 が出るだけで書き出しは止まらないが、利用者が「派生データの掃除」で参照を失う可能性がある。
3. CLI の `placed_by` の既定は `human-cli` である。エージェントが CLI で `--placed-by agent` を付け忘れると、人が置いたと記録される。手順書には書いたが、機械では区別できない。

---

## 4. A-8 — ローカルの絶対パス

`docs/GENERATION.md`、`docs/R1_F2_REPORT.md`、`docs/UPSTREAM_REPORT.md`、`e2e-tests/06-fresh-session/mcp.json`、同 `task.txt` の絶対パスを `<repo>` と `<外部環境>` に置き換えた。e2e-06 は試験の記録なので、`RESULT.md` の冒頭に置き換えた旨を 1 行書いた。

証拠: `git grep -n -i <ユーザー名>` → 0 件（現行のツリー）。全履歴の blob を走査すると、旧版に 21 か所が残る（§9 で消す）。

## 5. A-10 — 協力者のハンドル

`docs/review/CODEX_REVIEW_R1.md` の 8 行目（非公開ファイルの名前）を「DM 知見メモ（非公開）」に、358 行目の見出しを「DM 知見と制作分担」にした。監査は 1 か所としていたが、REVIEW_2 R2-12 の指摘どおり見出しにも 1 か所あった。

証拠: `git grep -n -i <ハンドル>` → 0 件（現行のツリー）。全履歴では旧版に 2 か所（§9）。

## 6. R2-12 の残りと R2-25（公開面）

- **生成画像の権利。** `NOTICE` に節「Images with unknown usage terms」を足した。対象（`tests/pipeline/corpus/generated/`、`e2e-tests/07-ds-turnaround/`）、Apache-2.0 の対象に含めないこと、来歴の置き場所、台帳 L-12 への参照。e2e-03 / 04 の往復プロジェクトの `unknown` は取り込みの既定値で、自作の絵であることも書いた。`README.md` のライセンスの節と英語の要約から案内した。
- **配布物を確かめた。** wheel にはもともと入っていない（監査 A-16）。**sdist には両方が入っていた**（1,750 項目、27 MB）。`pyproject.toml` の sdist に `exclude = ["/e2e-tests", "/tests/pipeline/corpus/generated"]` を足し、1,256 項目、5.4 MB になった（`uv build --sdist` で確認。I-2004）。
- **README の冒頭。** 「Linux CI は未実行」「M10 の整備中」を、実態（M0〜M10 実装済み、修正ラウンド 1 と 2 回目のレビュー済み、CI は Windows / Ubuntu × Python 3.12 / 3.13、GUI は Windows / Ubuntu 24.04、パッケージの配布は未）に直した。
- **`docs/MCP.md` のツール数。** 78 → **88**（生成を有効にすると 90。minimal 13、read-only 11）。`MCPService(...).tools()` で数えた。87 に今回の `register_reference` が足されている。
- **`docs/REVIEW_LOG.md:20`** の Fable の件数を総括（24 / 6 / 2）に合わせ、REVIEW_2 の判定（20 / 10 / 2）を併記した。
- R2-25 のうち SPEC の古い行（933、1028、1130、1148、2802、3321、3329 行）と §14.8 の注記は、REVIEW_2 §5.3 で上流（Fable）の「仕様の締め直し」に割り当てられているので、触っていない。

## 7. デモの統合

`fixr1-demo`（`bc25868`）を `--no-ff` で `main` に統合した（`f042aa2`）。競合は 3 ファイルで、最小限に解いた: `docs/DECISIONS.md` は `main` の行を保ち、I-DEMO-1〜3 を足した。`gui/src/i18n/en.json` / `ja.json` は `main` のキーを保ち、デモのキー 9 個を足した。`.github/workflows/pages.yml` は `workflow_dispatch` だけで、**有効化も実行もしていない**（公開後のフェーズ）。

証拠（統合直後）: vitest 707、コントラスト 102 組、`npm run build`、`npm run build:demo`、Playwright 5、`npm run check:demo`（デスクトップとスマホ、ja / en）がすべて成功。手動の参照の取り込みを足した後も、デモでは添付の欄が無効になり、`check:demo` は成功した。

## 8. A-0 — チェックリスト正本との突き合わせ

`docs/PUBLICATION_AUDIT.md` に「補遺 A」を書いた。正本の各項目を A-1〜A-21 に対応づけ、差は「あり 3、一部 2」。そのうち、

- ビルド成果物・キャッシュ・セッションログ、資格情報のファイル名、マシン名は、この場で確かめて問題なし（全履歴の差分にホスト名は 0 件）。
- 発注者の実名は、監査担当が知らないため検索できない → §9 の引き継ぎ。
- Pages の URL を README の**冒頭**と About に載せ、**スマホで**辿れるかを確かめる → 公開後のタスク。

正本は `_handoff/` にあり公開しないので、補遺では項目を言い換えて書いた（正本に含まれるユーザー名とハンドルを写さないため）。

---

## 9. 履歴の書き換えセッションへの引き継ぎ

### 9.1 `--replace-text` に渡すファイル

消すべき文字列そのものを、この追跡文書に書くと、書き換えの後もこの文書に残ってしまう。そこで、**`git filter-repo --replace-text` の形式のファイルを git の管理外に置いた**。

| ファイル（`_handoff/`、git の管理外） | 中身 | 扱い |
|---|---|---|
| `publication_replace_text_required.txt` | A-8 のパス 4 通り（`<外部環境>/_genenv`、`<repo>/_private/gen-check/`、`<repo>` のスラッシュ形とバックスラッシュ形）と、A-10 のファイル名 2 通りと見出し 1 つ。置き換え先は今回のコミットと同じ文字列 | **必須**（発注者の判断どおり） |
| `publication_replace_text_optional.txt` | 旧手順書のツールのパスとファイル名、ブラウザの起動のしかたの文、取得の性質の文、REVIEW_2:244 の該当句 | 任意（A-11 を履歴からも消すなら） |

- 行は「長いもの・具体的なものが先」に並べた（`<repo>` の置き換えが `-wt/_genenv` の前に効かないように）。filter-repo が上から順に当てることを、実行前に小さな複製で確かめること。
- 全履歴の blob（2,744 個）を走査した結果、置き換えの対象は次の数だけ残っている: ユーザー名を含むパス 21 か所（`_private/gen-check/` 6、`-wt/_genenv` 6、バックスラッシュ形 4、スラッシュ形 2、ほか 3）、ハンドル由来の名前 2 か所。書き換えの後に同じ走査を行い、0 になることを確かめる。

### 9.2 書き換え時のほかの注意

1. **メール（A-6）。** `--mailmap` で作者・コミッターを noreply にする。今回のコミット（本書を含めて 11 件、統合のコミットを含む）も同じ個人アドレスで作られているので、対象に含まれる。
2. **実名（補遺 A）。** 発注者が自分の実名で、現行のツリーと全履歴を検索する。
3. **SHA が変わる。** 文書に書いた SHA（本書の §0、DECISIONS、`REVIEW_REQUEST_2.md`、CI の記録など）は古くなる。本書の SHA は、書き換えの前の `main` を指す。
4. **ローカルのブランチ。** 統合済みの `fixr1-*` などのブランチと、未 push の作業は、書き換えの前に整理する。`fixr1-demo` は `main` に統合済み。
5. **push。** 今回のコミットは未 push。書き換えた結果を force-push する前に、CI を一度回す。

### 9.3 公開後のタスク（変わらず）

Pages の有効化、URL を README の冒頭と About へ、スマホでの確認（監査 A-20、補遺 A）。I-010 / I-012 の事後承認（A-14）。

---

## 10. 検証（CI 相当、ローカル Windows）

| 検査 | 結果 |
|---|---|
| `uv run pytest`（作業前の基準） | 2089 passed / 12 skipped |
| `uv run pytest`（最終） | **2143 passed / 12 skipped**（基準から +54。新しい試験 25 + 29 と既存の追加分。skip は基準と同じ 12 件: GPU、シンボリックリンクの権限、利用者導入の外部方式） |
| `uv run pytest -m independent_decoder` | 7 passed |
| `ruff check`、`ruff format --check` | 成功（262 ファイル） |
| `mypy src/cybersprite/core src/cybersprite/ops`、strict の 7 ファイル | 成功 |
| `tools/gen_schemas.py --check` | 成功 |
| `tools/check_licenses.py --include-dev --extra mcp --extra gui` | 成功 |
| `tools/check_repository.py` | `Clean-room paths and core imports: OK` |
| `node tools/check_js_licenses.mjs --check` | 46 パッケージ承認 |
| GUI `npm test`（vitest + コントラスト） | 710 passed、102 組 |
| GUI `npm run build`、`npm run build:demo` | 成功 |
| GUI `npm run test:e2e`（Playwright） | 6 passed（新しい参照の試験を含む） |
| GUI `npm run check:demo` | 成功 |
| 新しい Op の MCP 接続 | 実際の MCP クライアント（in-process）で `register_reference` と `list_sources` を呼んだ（§3.2）。`tools/build_release.py` → `tools/verify_release.py dist/cybersprite-0.1.0-py3-none-any.whl` で、リポジトリ外の新しい venv から MCP を stdio で起動し、module と CLI の 2 つの入口 × プロトコル 2025-06-18 / 2026-07-28 の 4 通りすべてで **88 ツール**を確認。CLI と GUI の起動も成功。wheel は 224 項目で、`ops/references.py` を含み、`e2e-tests` と生成コーパスは含まない |
| Linux | 未確認（push していないため CI は走っていない） |

最初の全体試験で 4 件が落ち、どれも今回の変更による想定どおりの差だったので、試験を直した: MCP のツール一覧が上限を 19 バイト超えた（Op の説明を短くした。§3.4 の 1）、cwd の外へ書く CLI の試験（R2-01 の新しい規則）、Op の一覧の試験（新しい Op）、規則ごとの品質の試験（Q-SRC-05 は専用の試験で確かめる）。

## 11. 道具への意見

- 品質の指摘は、同じ場所の同じ規則が 1 件にまとめられる。Q-SRC-05 は場所（ソースの ID）を `where` に持てないので、2 件の不一致が 1 つの文にまとまる。ソースの指摘に `where.source` があると、エージェントが読みやすい。
- GUI のソースのタブは、`get_source` の結果を生の JSON で見せている。参照が増えると読みにくい。
