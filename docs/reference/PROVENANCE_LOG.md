# PROVENANCE_LOG — 参照ログ

クリーンルーム工程（`docs/SPEC.md` §3）の記録。何を見て、何の事実を得て、どこに反映したかを 1 件 1 行で残す。
ここに書くのは事実の要約だけである。参照元の文面を写さない。スクリーンショットは載せない（`_private/` に置く）。

Aseprite の実機（Steam 版）は上流工程では参照せず、実装フェーズのM0（2026-11-12）で参照した。

| 日付 | 参照者 | 資料 | 何の事実を得たか | 反映先 |
|---|---|---|---|---|
| 2026-11-12 | Codex / M6 | インストール済み `pillow-13.0.0.dist-info/licenses/LICENSE` の Pillow 本体の許諾原文 | 本体は MIT-CMU と明記されており、仕様 §2.1 の既存許可 HPND（MIT-CMU）に対応する。実装ソースは参照していない | tools/check_licenses.py、I-473、M6_IMPLEMENTATION_REPORT.md |
| 2026-11-12 | Codex / M1 | 指定パッケージおよび推移的依存のインストール済み dist-info 内 LICENSE 原文（NumPy 2.3.4、pydantic 2.12.3、click 8.3.0、pytest 8.4.2、Ruff 0.14.1、mypy 1.15.0、hatchling 1.27.0 等。詳細は M1_LICENSE_REVIEW.md） | 本体の許諾と、pathspec の MPL-2.0・NumPy wheel の同梱ネイティブライブラリの追加条件を確認した。製品・ライブラリの実装ソースは参照していない | pyproject.toml、tools/check_licenses.py、M1_LICENSE_REVIEW.md、I-113 |
| 2026-11-11 | 調査担当（第 2 弾調査） | Aseprite ファイル形式仕様 https://github.com/aseprite/aseprite/blob/main/docs/ase-file-specs.md | ヘッダ、色深度、チャンクの種類（レイヤー、セル、タグ、パレット、スライス、タイルセット、ユーザーデータ） | SPEC §5.9 |
| 2026-11-11 | 調査担当（第 2 弾調査） | Aseprite CLI 文書 https://aseprite.org/docs/cli/ | CLI でできることの範囲（一括処理、シート、分割、範囲指定、一覧） | SPEC §9.5 |
| 2026-11-11 | 調査担当（第 2 弾調査） | Pixelorama README | ライセンス（MIT）、機能の範囲（タイムライン、タグ、オニオンスキン、タイルマップ、インデックスモード、CLI 書き出し） | NOTES §2.2 |
| 2026-11-12 | Fable 5.2 | Aseprite ファイル形式仕様（同上） | 各チャンクの項目と値の意味（レイヤーのフラグと種類、ブレンドモードの番号、セルの種類、Z インデックスの並べ替え規則、タグの方向と繰り返し、パレット、ユーザーデータの型、スライス、タイルセットのフラグ、タイルの反転マスク） | SPEC §5.5〜§5.9、§6.5.2 |
| 2026-11-12 | Fable 5.2 | Aseprite 利用者向け文書の目次 https://www.aseprite.org/docs/ | 文書の話題の一覧（機能の棚卸しの見出しとして） | SPEC §7 |
| 2026-11-12 | Fable 5.2 | 同 tilemap のページ | タイルマップレイヤー、タイルセット、空タイルは番号 0、ピクセル編集とタイル配置の 2 つの編集、手動・自動・スタックの 3 モード | SPEC §5.8.2、§7.9 |
| 2026-11-12 | Fable 5.2 | 同 layers のページ | レイヤーの種類（通常、背景、グループ、タイルマップ）、背景レイヤーの性質、表示・ロック・連続、相互変換 | SPEC §5.5、§7.4 |
| 2026-11-12 | Fable 5.2 | 同 animation のページ | フレームの追加・複製・削除・逆順、リンクセル、タグ、オニオンスキン、再生 | SPEC §7.5 |
| 2026-11-12 | Fable 5.2 | 同 selecting のページ | 選択のモード（置換・追加・除外・交差）、全選択・解除・反転 | SPEC §7.7 |
| 2026-11-12 | Fable 5.2 | 同 exporting のページ | 書き出しの選択肢（拡大、レイヤー、フレーム、再生方向、ピクセル比の適用、連番） | SPEC §7.11、§8.3 |
| 2026-11-12 | Fable 5.2 | 同 drawing のページ | 描画ツールの種類と、慣例的なキー（鉛筆、直線、矩形、楕円、消しゴム、スポイト、選択、移動、ズーム） | SPEC §7.6、§14.5 |
| 2026-11-12 | Fable 5.2 | 同 sprite-sheet、color のページ | シートの読み込みの項目（オフセット、大きさ、余白）、色に関する性質（カラーモード、プロファイル、透明色） | SPEC §7.2、§7.11 |
| 2026-11-12 | Fable 5.2 | mattt/aseprite-py（PyPI、README） | ライセンス（Apache-2.0）、対応する要素、描画は Normal のみ、Python 3.12 以上 | SPEC §2.3、§5.9 |
| 2026-11-12 | Fable 5.2 | diivi/aseprite-mcp README | ツールの分類と名前の一覧、プレビューと差分の返し方、スクリプト実行ツールの警告 | SPEC §10、NOTES §2.5 |
| 2026-11-12 | Fable 5.2 | KohakuBlueleaf/PixelOE（README、LICENSE） | ライセンス（Apache-2.0）、API と依存（PyTorch） | SPEC §2.3、§11.4 |
| 2026-11-12 | Fable 5.2 | Astropulse/pixeldetector、dimtoneff/ComfyUI-PixelArt-Detector、sedthh/pyxelate（LICENSE 原文） | いずれも MIT、追加制限なし | SPEC §2.3、§17.2 |
| 2026-11-12 | Fable 5.2 | MCP 仕様 2026-07-28（概要、tools）、`mcp` SDK（PyPI） | ステートレス、ツール定義の項目、結果の形、エラーの扱い。SDK は MIT、2.3.0 | SPEC §10 |
| 2026-11-12 | オーケストレーター（Opus 5.5） | Aseprite 実機 v1.3.18.6 Steam 版（GUI） | 起動画面、新規作成、メイン画面の配置、メニュー第 1 階層 8 種、属性ダイアログ（スプライト・レイヤー・フレーム）、拡大縮小、キャンバスの大きさ、色の置換、書き出し、シート書き出し（1 タブ目）、環境設定（1 タブ目）の項目 | ASEPRITE_INVENTORY §1 |
| 2026-11-12 | オーケストレーター（Opus 5.5） | Aseprite 実機 v1.3.18.6（`--help` の出力） | コマンドラインでできることの分類 | ASEPRITE_INVENTORY §1-47、§4 |
| 2026-11-12 | オーケストレーター（Opus 5.5） | Aseprite 実機 v1.3.18.6（バッチモードで自作ファイルの挙動を確認） | P-01〜P-10 の事実（タイル反転の順、グループの不透明度、リンクセル、シート JSON の形、インデックスでの不透明度、タグの再生順、空セル、Z インデックス、背景レイヤーの透明インデックス、GIF の遅延の丸め） | ASEPRITE_INVENTORY §2、SPEC §5.9.3、§6.5.4、§8.6.3、付録 D.2 |
| 2026-11-12 | オーケストレーター（Opus 5.5） | Aseprite リポジトリの EULA.txt 冒頭、docs/ase-file-specs.md の見出し | 文書は EULA の「電子的な文書」に含まれうる。冒頭に形式の実装を禁じる条項は見当たらない（L-08） | THIRD_PARTY §3 |
| 2026-11-12 | オーケストレーター（Opus 5.5） | Björn Ottosson「A perceptual color space for image processing」（bottosson.github.io/posts/oklab/） | コードはパブリックドメイン、または MIT でも利用可と明記（L-11） | THIRD_PARTY §3、NOTICE（M6 で係数を使う時点） |
| 2026-11-12 | オーケストレーター（Opus 5.5） | LICENSE 原文: mattt/aseprite-py、KohakuBlueLeaf/PixelOE、modelcontextprotocol/python-sdk、encode/starlette、encode/uvicorn、python-websockets/websockets、huggingface/diffusers、leejet/stable-diffusion.cpp、invoke-ai/InvokeAI。インストール済み dist-info の LICENSE: numpy、pillow、pydantic、pydantic_core、click。PyPI の JSON: 上記と推移的依存 | ライセンスの種類と版（L-01、L-02、L-04、L-09） | THIRD_PARTY §1、§3 |
| 2026-11-12 | オーケストレーター（Opus 5.5） | PyPI（`cybersprite`、`cyber-sprite`）、GitHub リポジトリ検索 | PyPI に同名なし。GitHub に同名の空に近いリポジトリが 2 件（説明なし、スター 0） | THIRD_PARTY §3、IMPLEMENTATION_PROGRESS |
| 2026-11-12 | オーケストレーター（Opus 5.5） | Aseprite 実機 v1.3.18.6（バッチモード） | P-11: CyberSprite が書いた `.aseprite` を開けること、描画結果が CyberSprite と全ピクセル一致すること | ASEPRITE_INVENTORY §2 |
| 2026-11-12 | Codex / M9 | PyPI JSON（diffusers 0.35.2、torch 2.9.0）と PyPI wheel 内 dist-info の LICENSE（diffusers 0.35.2、transformers 4.57.1、regex 2025.9.18）。Hugging Face 公式 Diffusers 文書（api/loaders/single_file、using-diffusers/loading_adapters） | 任意依存の候補と原文ライセンスを確認。regex に CNRI Python 1.6 表記があるため依存追加を保留。API の local_files_only、from_single_file、LoRA 読込・有効化を確認（コード転用なし） | DECISIONS I-708、GENERATION、generate/backends.py |
| 2026-11-12 | オーケストレーター（Opus 5.5） | Hugging Face API（モデルカードの cardData）: SD 1.5、SDXL base / refiner、FLUX.1 [schnell]、Pixel Art XL、PixArt-α / Σ | 各モデルのライセンス欄の値（L-10） | THIRD_PARTY §3 |
| 2026-11-12 | オーケストレーター（Opus 5.5） | OpenAI 利用規約（openai.com/terms の検索結果の抜粋） | 出力の帰属と、出力が一意でないこと（L-12） | THIRD_PARTY §3 |
| 2026-11-12 | Codex / M10 | インストール済みaseprite 0.1.0のLICENSE/RECORD、MCP/mcp-types 2.3.0のMIT LICENSEとserver runner・inbound・版定数、React/React DOM/Scheduler/ZustandのMIT LICENSE、既存gui/LICENSES_JS.txtとJS台帳 | 配布NOTICEと原文収録、独立NOTICEの有無、両MCP版のstdio確認方法。コード片の転用・新規依存なし。Oklabは既存L-11の確認記録を使用 | NOTICE、third_party/licenses/gui-bundle.txt、tools/release_probe.py、DECISIONS I-802/I-807 |
| 2026-11-12 | Codex / R1-F1 | ComfyUI公式公開HTTP API文書 https://docs.comfy.org/development/comfyui-server/comms_routes と文書索引 https://docs.comfy.org/llms.txt | prompt送信、個別history、view、system_statsのHTTPルートというAPI事実だけを確認。製品ソース・ノード実装・外部ワークフローは未参照、コード転用・依存追加なし。テスト用グラフとHTTPサーバーは自作 | SPEC §12.7、GENERATION、DECISIONS I-1604〜I-1607 |
| 2026-11-12 | Opus 5.5（DS 粒度の特別テストの制作担当。R1-G がさかのぼって記録） | DS 世代の市販スプライト 4 点（人物 3、生き物 1）。`_private/e2e-ds/refs/` に置き、計測だけに使った。題名は記録しない | 外接矩形（人物 36〜48×60〜66、生き物 62×40）、不透明の色数（人物 14〜15、生き物 11）、輪郭の外周の 40〜64% が最も暗い色で残りは素材の最も暗い色、素材ごとの陰影 3 段（肌と白は 2 段）、ディザはほぼ無し、部分アニメーションはユニークなコマ 7 枚ほどの並べ替えと上下動 | `_private/e2e-ds/REPORT.md`（非公開）、`skills/workflows/turnaround-parts.md` §5、I-1809 |
| 2026-11-12 | Fable 5.2（レビュー 1 回目。R1-G がさかのぼって記録） | 同じ 4 点（計測のみ） | 頭の幅に対する目の幅（生き物で約 0.34）と目の 3 層の構造、占有率（16〜24%）、輪郭からの最大の深さ（10〜17 px）、3×3 が 1 色の画素の割合、同色の領域の密度、横方向の同色の連なりの平均 | `docs/REVIEW_1.md` §2.2、`skills/workflows/turnaround-parts.md` §5、I-1809 |
| 2026-11-12 | Codex / R1-D1 | Retro-Diffusion/pixel-art-fixer ef376e57e1c272633ca2dbf5f29ec3fcf6596465 のLICENSE、README、Pythonの公開APIとreconstruct（https://github.com/Retro-Diffusion/pixel-art-fixer） | MIT原文、detectの5指標とreconstructのRGBA契約、OpenCV/SciPy依存。コード転用なし | external/pixel_art_fixer.py、監査表、I-1301 |
| 2026-11-12 | Codex / R1-D1 | KennethJAllen/proper-pixel-art 2.0.0 のLICENSE、README、image/config API（https://github.com/KennethJAllen/proper-pixel-art） | MIT原文、画像APIとmesh、動画の遅延読込、依存av/OpenCV/tqdm。コード転用なし | external/proper_pixel_art.py、I-1302 |
| 2026-11-12 | Codex / R1-D1 | PixelOEの公式LICENSE/APIと1.0.0配布wheelのtorch/pixelize API（https://github.com/KohakuBlueleaf/PixelOE、https://pypi.org/project/pixeloe/1.0.0/） | Apache-2.0原文、CPU Torchのbackend・no_post_upscale・do_quant API、条件付きslangpy依存。コード転用なし | external/pixeloe.py、I-1309 |
| 2026-11-12 | Codex / R1-D1 | @xprite/pixelate 0.1.2の公式npm tarball、LICENSE、公開型定義（https://www.npmjs.com/package/@xprite/pixelate） | MIT原文、RGBAバッファの分析・復元API。外部一時領域での評価のみ | pixelize_bench.py、pixelize_xprite.mjs、実測表 |
| 2026-11-12 | Codex / R1-D1 | 44種類の導入候補のPyPIメタデータ・wheel LICENSE等（全URL/版/SHA-256は監査JSON） | OpenCV等のLGPL同梱表記、tqdmのMPL、CUDA EULA、未確認部分を識別。実装コードは開いていない | PIXELIZE_LICENSE_AUDIT.md、I-1301 |
| 2026-11-12 | Codex / R1-D2 | [Fixerの公式README](https://github.com/Retro-Diffusion/pixel-art-fixer)、D1の当該commit LICENSE | 自身のベンチの77%という公表値、MIT、Python版の同定 | PIXELIZE_BENCH、runtime JSON |
| 2026-11-12 | Codex / R1-D2 | [PPA公式repo](https://github.com/KennethJAllen/proper-pixel-art)、2.0.0の実LICENSE・config/image API | MIT、上流初期倍率2とD1設定1の相違、共通mesh画像API | 比較の条件表示、batch試験 |
| 2026-11-12 | Codex / R1-D2 | [PixelOE公式repo](https://github.com/KohakuBlueleaf/PixelOE)、1.0.0の実LICENSE・torch/pixelize/logger/slang auto API | Apache-2.0、backend=torchはSlang contextを返さない経路、stdout loggerと任意import | CPU loader、protocol回帰、I-1343/I-1344 |
| 2026-11-12 | Codex / R1-D2 | [Xprite公式ベンチ表](https://github.com/rhinoc/xprite-pixelate#benchmark)、0.1.2の実LICENSE | MIT、AI suiteの83.6/49.7/72.2%と入力条件の違い | PIXELIZE_BENCHの公表値比較 |
| 2026-11-12 | Codex / R1-D2 | 公式CPU torch/torchvision wheel、評価環境の実LICENSE、[Slangpy公式文書](https://slangpy.shader-slang.org/en/stable/changelog.html)・実LICENSE・init、[MicrosoftのSetSDKVersion文書](https://learn.microsoft.com/en-us/windows/win32/api/d3d12/nf-d3d12-id3d12sdkconfiguration-setsdkversion) | CPU wheelの版・原文・hash、任意GPU初期化のstdout混入。SlangpyのDLLは関連する文字列だけ調査しコードは転用しない | runtime JSON、CPUのみの初期化 |
| 2026-11-12 | Codex / R1-E1 | https://raw.githubusercontent.com/gbdev/pandocs/master/src/Tile_Data.md | DMGの8×8、2bpp、透明色番号の意味を照合 | SPEC §5.13、data/platforms/dmg.json |
| 2026-11-12 | Codex / R1-E1 | https://raw.githubusercontent.com/gbdev/pandocs/master/src/OAM.md | DMG物体8×8/8×16、反転属性を照合 | SPEC §5.13、data/platforms/dmg.json |
| 2026-11-12 | Codex / R1-E1 | https://raw.githubusercontent.com/gbdev/pandocs/master/src/Palettes.md | DMG背景1行・物体2行と4階調を照合。RGB値は自作慣用値 | SPEC §5.13、gray-4説明 |
| 2026-11-12 | Codex / R1-E1 | https://raw.githubusercontent.com/gbdev/pandocs/master/src/Tile_Maps.md | DMGマップ32×32、表示160×144を照合 | SPEC §5.13、data/platforms/dmg.json |
| 2026-11-12 | Codex / R1-E1 | https://raw.githubusercontent.com/gbdev/pandocs/master/src/Specifications.md | DMG概要の照合用に閲覧 | SPEC §5.13 |
| 2026-11-12 | Codex / R1-E1 | https://problemkaputt.de/gbatek.htm | NDS表示256×192、標準4bpp物体のパレット、RGB555、GBA系2D物体仕様を照合 | SPEC §5.13、data/platforms/nds.json |
| 2026-11-12 | Codex / R1-E1 | https://mgba-emu.github.io/gbatek/ | 同じGBATEKの公開ミラー。原サイト再取得タイムアウト時に12物体寸法と2D仕様の継承、標準16行×16を再照合 | SPEC §5.13、data/platforms/nds.json |
| 2026-11-12 | Codex / R1-E3 | https://raw.githubusercontent.com/gbdev/pandocs/master/src/Palettes.md | CGBの8行×4、RGB555、物体slot0透明 | cgb.json、SPEC §16.4 |
| 2026-11-12 | Codex / R1-E3 | https://raw.githubusercontent.com/gbdev/pandocs/master/src/Tile_Data.md | GB/CGBの8×8、2bpp、16bytes、行/bit面順 | native.py、native vector |
| 2026-11-12 | Codex / R1-E3 | https://raw.githubusercontent.com/gbdev/pandocs/master/src/OAM.md | 8×8/8×16物体とx/y反転 | cgb.json |
| 2026-11-12 | Codex / R1-E3 | https://mgba-emu.github.io/gbatek/ | GBAの240×160、RGB555、16行×16、12物体寸法と非変形反転 | gba.json、SPEC §16.4 |
| 2026-11-12 | Codex / R1-E3 | https://www.nesdev.org/wiki/PPU_programmer_reference | NES画面・2組の256タイル・2bpp・局所パレット | nes.json |
| 2026-11-12 | Codex / R1-E3 | https://www.nesdev.org/wiki/PPU_attribute_tables | NES背景の16×16パレット選択単位 | SPEC §16.4、Q-PLT-04 |
| 2026-11-12 | Codex / R1-E3 | https://www.nesdev.org/wiki/PPU_palettes | NESのRGB色表は一意でない | nes.json、I-1510 |
| 2026-11-12 | Codex / R1-E3 | https://snes.nesdev.org/wiki/Sprites | SFCの4bpp・8パレット・正方形物体寸法 | sfc.json |
| 2026-11-12 | Codex / R1-E3 | https://snes.nesdev.org/wiki/SNES_PPU_for_NES_developers | SFCのRGB555と通常224行 | sfc.json |
| 2026-11-12 | Codex / R1-E3 | https://snes.nesdev.org/wiki/Palettes | SFCの透明slot0と色表構成 | sfc.json |
| 2026-11-12 | Codex / R1-E3 | https://www.neperos.com/article/picoxo1fc33c8979 | Charles MacDonaldのVDP技術文書。MDの3bit RGB、4行×16、8×8/4bpp、物体1〜4セル、H40/224、反転 | md.json、SPEC §16.4 |
| 2026-11-12 | Codex / R1-F2 | PyTorch公式cu128 Windows cp312 wheel 2.8.0、Diffusersスタック全33配布物のdist-info LICENSE/LICENCE/COPYING原文・native一覧 | 外部環境のみ、監査不合格(b)、原文ハッシュはprivate dependency-audit.json | GENERATION、R1_F2_REPORT、I-1641〜I-1649 |
| 2026-11-12 | Codex / R1-F2 | https://pytorch.org/get-started/previous-versions/ 、https://docs.nvidia.com/cuda/archive/12.8.1/eula/index.html 、https://docs.nvidia.com/deeplearning/cudnn/backend/latest/reference/eula.html | CUDA wheel導入方法と同梱DLLの条件を確認、例外追加なし | GENERATION、R1_F2_REPORT、I-1641〜I-1649 |
| 2026-11-12 | Codex / R1-F2 | https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/tree/462165984030d82259a11f4367a4eed129e94a7b 、https://huggingface.co/nerijs/pixel-art-xl/tree/8bf4a4d9ea283e00a51fafda8e0539f8248ea037 、https://huggingface.co/spaces/CompVis/stable-diffusion-license/blob/main/license.txt | カード/モデル条件、取得と個別承諾。重み非同梱 | GENERATION、R1_F2_REPORT、I-1641〜I-1649 |
| 2026-11-12 | Codex / R1-F2 | https://github.com/huggingface/tokenizers/blob/v0.22.2/LICENSE 、Diffusers 0.35.2 Apache-2.0 wheel API箇所 | tokenizers不足原文の補足とdevice_map対応の確認。コード移植なし | GENERATION、R1_F2_REPORT、I-1641〜I-1649 |
| 2026-11-12 | Codex / R1-F2 | https://docs.pytorch.org/docs/2.8/generated/torch.set_float32_matmul_precision.html 、https://docs.pytorch.org/docs/2.8/generated/torch.get_float32_matmul_precision.html | highest/high/mediumとTF32の対応、復元APIを確認。コード移植なし | GENERATION、R1_F2_REPORT、I-1641〜I-1649 |
| 2026-11-12 | Codex / R1-DOC | 実行環境のaseprite 0.1.0、websockets 16.0、h11 0.16.0、httpcore2/httpx2 2.16.0のdist-info LICENSE原文、既存M4/M5/M8-S/M10の確認記録 | 欠落5行を原文と照合。Apache-2.0 / BSD-3-Clause / MITの許諾を再読し、依存追加なし。L-05はJS46件の原文記録、L-06はシステムフォント指定・自作字形の記録と追跡フォント0件を確認 | THIRD_PARTY §1/§3、I-1941〜I-1943 |
| 2026-11-12 | オーケストレーター（R1-DOCへの申し送り） | 非公開参照取得コネクタの実行観測（利用者PCのChrome） | HTTP 403。回避を試みず、e2e-07では既存の非公開参照ライブラリを利用。画像・作品名・URLは公開側に転載しない | KNOWN_ISSUES、FIX_ROUND_1_REPORT、REVIEW_REQUEST_2 |
| 2026-11-12 | Codex / R1-DOC（R1-E3記録の補記） | R1_E3_IMPLEMENTATION_REPORTの公開技術資料の取得記録 | NESdev/SNESdevの一部は直接403で、同文書の検索索引本文抜粋で照合。segaretroのPDFとchibiakumasは403で採用根拠にせず。製品ソース・画像は利用していない | E3の上記11行の確認方法の限定、THIRD_PARTY §5 |
| 2026-11-12 | Opus 5.5（E2E-07 DS 級の作り直し） | 参照ライブラリの DS 世代の市販スプライト 4 点（人物 3、生き物 1。`_private/e2e-ds/refs/`、計測のみ。コネクタはこの日 HTTP 403 のため代わりの方法） | 外接矩形（人物 36〜48×60〜66、生き物 62×40）、不透明色数 11〜15、外周に占める最も暗い色 0.40〜0.64、輪郭からの最大深さ 9〜16 px、横の同色連なり平均 1.6〜3.1、生き物の目は 1 個あたり幅 6 px 前後で「暗い縁 → 最も明るい地 → 暗い瞳」、影は下面に沿う 4〜5 行の帯（形の影）、アニメーションは 45 コマ中ユニーク 7 で形が変わる | `e2e-tests/07-ds-turnaround/RECORD.md` §2 |
