# 外部ピクセル化ツールの監査（R1-D1）

2026-11-12。配布用依存は追加しない。これはWindows / Python 3.12の導入候補の監査であり、全OSのバイナリを許可する証明ではない。ライセンス原文だけをwheelからRange取得で開き、ハッシュとURLを [JSON](pixelize_license_audit.json) に記録した。GPL製品のコードは開いていない。

| ツール | 版 | 原文 | 判断 |
|---|---|---|---|
| Pixel Art Fixer | ef376e57e1c272633ca2dbf5f29ec3fcf6596465 | [MIT](https://github.com/Retro-Diffusion/pixel-art-fixer/blob/ef376e57e1c272633ca2dbf5f29ec3fcf6596465/LICENSE) | Python参照版もOpenCV/SciPyを要求するためvendorしない。利用者導入を検出 |
| proper-pixel-art | 2.0.0 | [MIT](https://github.com/KennethJAllen/proper-pixel-art/blob/4de0dda5ba066491b5b5fac3500365db4dfd665e/LICENSE) | av/OpenCV/tqdmがあるため依存宣言しない。動画APIは使用しない |
| PixelOE | 1.0.0 | [Apache-2.0](https://github.com/KohakuBlueleaf/PixelOE/blob/7ce444b36d3876a151d845d4493240e904454d89/LICENSE) | OpenCV/PyTorchのバイナリ全体を許可できないためextraに追加しない |
| @xprite/pixelate | 0.1.2 / 49c62fccaaa776281c522089b1c8d30b3028cbd5 | [MIT](https://github.com/rhinoc/xprite-pixelate/blob/49c62fccaaa776281c522089b1c8d30b3028cbd5/LICENSE) | npm tarballのLICENSE原文確認。宣言されたruntime依存なし。リポジトリ外の一時領域で評価のみ |

PixelOEの参照時点のリポジトリmainは1.0.1で、配布wheelは1.0.0。APIの確認は配布wheelを基準にする。FixerのRust実装・依存ツリーは今回利用・同梱しない。PyAV/OpenCVのラッパーの許可と同梱FFmpegの許可は別である。

| 推移依存（導入候補） | 版 | 原文から確認した表記・制約 | 検証 |
|---|---|---|---|
| av | 19.0.2 | BSD-3-Clause (wrapper only; bundled FFmpeg not cleared) | [wheel](https://files.pythonhosted.org/packages/32/5a/743a83666ded197df8b9957e2800bef9a39d52b23be2ca211bbd14b5fb22/av-19.0.2-cp312-abi3-win_amd64.whl) のLICENSE等 2件を開いた。各SHA-256はJSON |
| colorama | 0.4.6 | BSD-3-Clause | [wheel](https://files.pythonhosted.org/packages/d1/d6/3965ed04c63042e047cb6a3e6ed1a63a35087b6a609aa3a15ed8ac56c221/colorama-0.4.6-py2.py3-none-any.whl) のLICENSE等 1件を開いた。各SHA-256はJSON |
| filelock | 4.2.10 | MIT | [wheel](https://files.pythonhosted.org/packages/ef/90/5d0096a325aa0f83ba7a3968bfb485b67e32c947bdf9cd0fcb4b485be718/filelock-4.2.10-py3-none-any.whl) のLICENSE等 1件を開いた。各SHA-256はJSON |
| fsspec | 2026.9.0 | BSD-3-Clause | [wheel](https://files.pythonhosted.org/packages/6c/c0/a98505f18594f1bce828bb159cec0fcf9860562f1a2c85913409fc8f3d9e/fsspec-2026.9.0-py3-none-any.whl) のLICENSE等 1件を開いた。各SHA-256はJSON |
| jinja2 | 3.1.6 | BSD-3-Clause | [wheel](https://files.pythonhosted.org/packages/62/a1/3d680cbfd5f4b8f15abc1d571870c5fc3e594bb582bc3b64ea099db13e56/jinja2-3.1.6-py3-none-any.whl) のLICENSE等 1件を開いた。各SHA-256はJSON |
| kornia | 0.9.0 | Apache-2.0 | [wheel](https://files.pythonhosted.org/packages/c5/ee/6bffb3fc85446de03fa7e397954ba4dd1bc5edab92b4b8be3ce09c9ccd1b/kornia-0.9.0-py3-none-any.whl) のLICENSE等 1件を開いた。各SHA-256はJSON |
| kornia-rs | 0.2.0 | Apache-2.0 (bundled dependencies require separate review) | [wheel](https://files.pythonhosted.org/packages/4d/14/a1863c42b142fa7018105e7ef028b700a04c86a7a221d67e83fe2697ff31/kornia_rs-0.2.0-cp312-cp312-win_amd64.whl) のLICENSE等 1件を開いた。各SHA-256はJSON |
| markupsafe | 3.0.4 | BSD-3-Clause | [wheel](https://files.pythonhosted.org/packages/3f/bf/62495e180b7000aaf30000fff849e933f74264638057176cf46852500adc/markupsafe-3.0.4-cp312-cp312-win_amd64.whl) のLICENSE等 1件を開いた。各SHA-256はJSON |
| mpmath | 1.3.0 | BSD-3-Clause | [wheel](https://files.pythonhosted.org/packages/43/e3/7d92a15f894aa0c9c4b49b8ee9ac9850d6e63b03c9c32c0367a13ae62209/mpmath-1.3.0-py3-none-any.whl) のLICENSE等 1件を開いた。各SHA-256はJSON |
| networkx | 3.7 | BSD-3-Clause | [wheel](https://files.pythonhosted.org/packages/7e/cd/fe58041e9011f307c490e3e17dd48cc516448f7c698a3f2d9d9d65d7e6a8/networkx-3.7-py3-none-any.whl) のLICENSE等 1件を開いた。各SHA-256はJSON |
| numpy | 2.5.4 | BSD-3-Clause AND bundled notices | [wheel](https://files.pythonhosted.org/packages/12/33/fefe62073dc8acfd0f2b9ed7c003af2f50aa61555e113e6db02b8f79f145/numpy-2.5.4-cp312-cp312-win_amd64.whl) のLICENSE等 20件を開いた。各SHA-256はJSON |
| opencv-python | 5.0.0.93 | Apache-2.0 AND bundled notices (LGPL FFmpeg risk) | [wheel](https://files.pythonhosted.org/packages/21/f0/9fa6e85cb10c8eb36a0222d27e50fe381b86ce49a55446bf39f491727564/opencv_python-5.0.0.93-cp37-abi3-win_amd64.whl) のLICENSE等 4件を開いた。各SHA-256はJSON |
| opencv-python-headless | 5.0.0.93 | Apache-2.0 AND bundled notices (LGPL FFmpeg risk) | [wheel](https://files.pythonhosted.org/packages/b8/88/763b967f7efd7226b82c9fae16d560cba049b1f0c036647e65c610fd636e/opencv_python_headless-5.0.0.93-cp37-abi3-win_amd64.whl) のLICENSE等 4件を開いた。各SHA-256はJSON |
| pillow | 13.0.0 | MIT-CMU AND bundled notices | [wheel](https://files.pythonhosted.org/packages/ff/cd/73a79ecdc822076002eb24b5e1e4a530b0bb5310fcb6d239abbec877110b/pillow-13.0.0-cp312-cp312-win_amd64.whl) のLICENSE等 1件を開いた。各SHA-256はJSON |
| pixeloe | 1.0.0 | Apache-2.0 | [wheel](https://files.pythonhosted.org/packages/20/4d/fdb0ccfdf93ee25aa4d5c1006b317d354e1ddec813048ba0e17387323a76/pixeloe-1.0.0-py3-none-any.whl) のLICENSE等 1件を開いた。各SHA-256はJSON |
| proper-pixel-art | 2.0.0 | MIT | [wheel](https://files.pythonhosted.org/packages/6d/1b/2307a29a960df0c70c54fb04031edc2ecaf5503ad7db2f25e335c8faa974/proper_pixel_art-2.0.0-py3-none-any.whl) のLICENSE等 1件を開いた。各SHA-256はJSON |
| pyyaml | 6.0.3 | MIT | [wheel](https://files.pythonhosted.org/packages/86/bf/899e81e4cce32febab4fb42bb97dcdf66bc135272882d1987881a4b519e9/pyyaml-6.0.3-cp312-cp312-win_amd64.whl) のLICENSE等 1件を開いた。各SHA-256はJSON |
| scipy | 1.18.1 | BSD-3-Clause AND bundled notices | [wheel](https://files.pythonhosted.org/packages/39/e7/979fd14e75008623df31ba70d6bb144700f68feadcea042021c06a05bf82/scipy-1.18.1-cp312-cp312-win_amd64.whl) のLICENSE等 5件を開いた。各SHA-256はJSON |
| setuptools | 84.2.1 | MIT AND bundled notices | [wheel](https://files.pythonhosted.org/packages/ef/55/6dc6d6bb953bdfc52519a0059592c52b6e3b8ad51cf8256dffceb55b0610/setuptools-84.2.1-py3-none-any.whl) のLICENSE等 15件を開いた。各SHA-256はJSON |
| sympy | 1.14.0 | BSD-3-Clause | [wheel](https://files.pythonhosted.org/packages/a2/09/77d55d46fd61b4a135c444fc97158ef34a095e5681d0a6c10b75bf356191/sympy-1.14.0-py3-none-any.whl) のLICENSE等 3件を開いた。各SHA-256はJSON |
| torch | 2.15.0 | BSD-3-Clause AND bundled notices (not cleared) | [wheel](https://files.pythonhosted.org/packages/74/0b/a57c0b58a64b7a197dc40fc464bb96c0de867f95a2b1cbb3ec9e54414fde/torch-2.15.0-cp312-cp312-win_amd64.whl) のLICENSE等 65件を開いた。各SHA-256はJSON |
| torchvision | 0.29.2 | BSD-3-Clause (macOS artifact; Windows binary not verified) | [wheel](https://files.pythonhosted.org/packages/60/ec/ce97c46e5322b588b95be388f2c21878d014ca20838478e7aab59edd128a/torchvision-0.29.2-py3-none-macosx_14_0_arm64.whl) のLICENSE等 1件を開いた。各SHA-256はJSON |
| tqdm | 4.70.1 | MPL-2.0 AND MIT | [wheel](https://files.pythonhosted.org/packages/a7/03/921a3d3c75785aca9ebfbfcabfbc3a1be12e2ab5265deb026d55a5a3f83e/tqdm-4.70.1-py3-none-any.whl) のLICENSE等 1件を開いた。各SHA-256はJSON |
| typing-extensions | 4.16.0 | PSF-2.0 | [wheel](https://files.pythonhosted.org/packages/49/d3/b8441a820a491ddfc024b0b0cf0393375b75ea13866d9c66727e54c2fc80/typing_extensions-4.16.0-py3-none-any.whl) のLICENSE等 1件を開いた。各SHA-256はJSON |

| slangpy | 0.43.1 | Apache-2.0 WITH LLVM-exception、OFL-1.1フォント等（未承認） | [Windows wheel](https://files.pythonhosted.org/packages/a7/af/81eaf29a574e27c143da02653fc82cdeb97ab1047bba61b76c772d223bbf/slangpy-0.43.1-cp312-cp312-win_amd64.whl) の原文3件。JSONにSHA-256 |

slangpyの環境マーカー（Windows AMD64表記）はuvのWindowsターゲット解決には現れなかったため、0.43.1のWindows cp312 wheelを別に取得しLICENSE等3件を開いた。runtime依存はtyping_extensionsとnumpyで、torch連携extraは対象外。Linuxの既定ターゲットではslangpyが要求するglibc 2.34 wheelと合わず解決できなかった。LinuxのCUDA/NVIDIA追加依存とバイナリ内部の全推移ライセンスは未承認なので、PixelOEのツリー全体をcleanとは扱わない。torchvisionは今回取得できたmacOS wheelのLICENSEを確認しただけでWindows wheelを確認したものではない。

この監査は依存追加の承認ではない。`third_party/THIRD_PARTY.md` はオーケストレーターが維持するため編集していない。

追加で確認した制約: NumPy/SciPyの候補wheelの通知にはGCC runtime例外付きGPLやlibquadmathのLGPL、setuptoolsの同梱autocommand 2.2.2にはLGPL-3.0がある。既存のCyberSprite依存の版・監査例外を変更する判断ではなく、今回の外部ツールの新しい解決ツリーを許可できない根拠として記録する。

## Linux側の追加依存（宣言・導入しない）

CPython 3.12 / manylinux_2_34で43 distributionまで解決した。Windowsの25件と合わせて44種類（coloramaはWindowsのみ）。追加19件も実際のwheelのライセンス文面を取得して開いたが、cuda-toolkitのwheelにはLICENSE原文が見当たらず未確認である。取得したartifactのarchitectureはJSONに残す。aarch64やWindows版の原文確認をx86_64バイナリ全体の承認と読み替えない。

| 追加候補 | 版 | SPDX / 未承認の理由 | 原文 |
|---|---|---|---|
| cuda-bindings | 13.5.0 | Apache-2.0 | [wheel](https://files.pythonhosted.org/packages/e5/ea/87bd4fa1e1e70d3895b4e46606902fa7974111a81002dbd0418b68fb5b74/cuda_bindings-13.5.0-cp312-cp312-win_amd64.whl) のLICENSE等1件 |
| cuda-pathfinder | 1.8.6 | Apache-2.0 | [wheel](https://files.pythonhosted.org/packages/6a/9e/08555797c979322def080814686417ea93f66d38f5c48ebab6867a85a21e/cuda_pathfinder-1.8.6-py3-none-any.whl) のLICENSE等1件 |
| cuda-toolkit | 13.2.2 | UNVERIFIED: no actual license text present in wheel | [wheel](https://files.pythonhosted.org/packages/3d/62/854e4a141f5e87e5425513bad2a742a6260acfe06ef148001b5362148f31/cuda_toolkit-13.2.2-py2.py3-none-any.whl) のLICENSE等0件 |
| nvidia-cublas | 13.4.1.3 | LicenseRef-NVIDIA (not allowlisted; see actual wheel EULA) | [wheel](https://files.pythonhosted.org/packages/d0/a0/5cd9d4b08a8320f7ca150ee0d66c97e98092922e338336cb4b62da7500c3/nvidia_cublas-13.4.1.3-py3-none-manylinux_2_27_aarch64.whl) のLICENSE等1件 |
| nvidia-cuda-cccl | 13.3.5.0.6 | Apache-2.0 WITH LLVM-exception AND LicenseRef-NVIDIA（同梱EULA原文確認） | [wheel](https://files.pythonhosted.org/packages/81/dc/9a056ef9bd05c55ddaed3afce160702e4ce8303b9ec1b38066044c18dcd2/nvidia_cuda_cccl-13.3.5.0.6-py3-none-manylinux2014_aarch64.manylinux_2_17_aarch64.whl) のLICENSE等2件 |
| nvidia-cuda-cupti | 13.2.86 | LicenseRef-NVIDIA (not allowlisted; see actual wheel EULA) | [wheel](https://files.pythonhosted.org/packages/e1/ab/52414925ea803a5f86b994ae97d951e5943ed27a6f1da4a5c4ac09e308af/nvidia_cuda_cupti-13.2.86-py3-none-manylinux_2_25_aarch64.whl) のLICENSE等1件 |
| nvidia-cuda-nvrtc | 13.2.86 | LicenseRef-NVIDIA (not allowlisted; see actual wheel EULA) | [wheel](https://files.pythonhosted.org/packages/1e/39/c58835ec8392a91b8d7bad83760eafc3085f64788b722ec2b44a27b3ca3e/nvidia_cuda_nvrtc-13.2.86-py3-none-manylinux2010_x86_64.manylinux_2_12_x86_64.whl) のLICENSE等1件 |
| nvidia-cuda-runtime | 13.2.86 | LicenseRef-NVIDIA (not allowlisted; see actual wheel EULA) | [wheel](https://files.pythonhosted.org/packages/89/d4/fa981071e3d9f29158ca16c69ee617831cd6df4dd47024149c16eec717f8/nvidia_cuda_runtime-13.2.86-py3-none-manylinux2014_aarch64.manylinux_2_17_aarch64.whl) のLICENSE等1件 |
| nvidia-cudnn-cu13 | 9.26.0.51 | LicenseRef-NVIDIA (not allowlisted; see actual wheel EULA) | [wheel](https://files.pythonhosted.org/packages/c5/1c/01e1dd3dec6ffe0baaff7e722b8946d867353d05a01301f128f1730fde0b/nvidia_cudnn_cu13-9.26.0.51-py3-none-manylinux_2_27_aarch64.whl) のLICENSE等1件 |
| nvidia-cufft | 12.2.0.57 | LicenseRef-NVIDIA (not allowlisted; see actual wheel EULA) | [wheel](https://files.pythonhosted.org/packages/07/8d/f650e6d527f9d22b5ded906c000eaebb037721c06d4ecd906df62f300979/nvidia_cufft-12.2.0.57-py3-none-manylinux2014_aarch64.manylinux_2_17_aarch64.whl) のLICENSE等1件 |
| nvidia-cufile | 1.17.1.22 | LicenseRef-NVIDIA (not allowlisted; see actual wheel EULA) | [wheel](https://files.pythonhosted.org/packages/fe/fd/4b4157512a131a51e1514d40d0199b1c5b7b10c6856db274ff22e5fe15be/nvidia_cufile-1.17.1.22-py3-none-manylinux_2_27_aarch64.whl) のLICENSE等1件 |
| nvidia-cusolver | 12.2.0.11 | LicenseRef-NVIDIA (not allowlisted; see actual wheel EULA) | [wheel](https://files.pythonhosted.org/packages/60/df/9e6b603f1d64040ce3e076e9bce1b78e2d588d0aabc9783f351cecd861ab/nvidia_cusolver-12.2.0.11-py3-none-manylinux_2_27_aarch64.whl) のLICENSE等1件 |
| nvidia-cusparse | 12.7.10.12 | LicenseRef-NVIDIA (not allowlisted; see actual wheel EULA) | [wheel](https://files.pythonhosted.org/packages/60/35/abbd278fb6d039fcfb5175efa10a21007a11878bec59920d84854b47d766/nvidia_cusparse-12.7.10.12-py3-none-manylinux2014_aarch64.manylinux_2_17_aarch64.whl) のLICENSE等1件 |
| nvidia-cusparselt-cu13 | 0.8.1 | LicenseRef-NVIDIA (not allowlisted; see actual wheel EULA) | [wheel](https://files.pythonhosted.org/packages/46/e1/cdc1797eadf82d3a9a575a19b33fdc871a97edbec42c00b5b5e914f4aff4/nvidia_cusparselt_cu13-0.8.1-py3-none-manylinux2014_aarch64.whl) のLICENSE等1件 |
| nvidia-nccl-cu13 | 2.30.7 | BSD-3-Clause（NCCLの原文確認、同梱ツリー全体は未承認） | [wheel](https://files.pythonhosted.org/packages/d1/21/a73174c6157101bdf1ffc22b517f76ff0082613989dd9bc8f43e8034caac/nvidia_nccl_cu13-2.30.7-py3-none-manylinux_2_18_aarch64.whl) のLICENSE等1件 |
| nvidia-nvjitlink | 13.5.37 | LicenseRef-NVIDIA (not allowlisted; see actual wheel EULA) | [wheel](https://files.pythonhosted.org/packages/cc/1f/2321702b8d60b4b4dd18b957f61612dbac9cb1c07e940cf6582106b7c8b8/nvidia_nvjitlink-13.5.37-py3-none-manylinux2010_x86_64.manylinux_2_12_x86_64.whl) のLICENSE等1件 |
| nvidia-nvshmem-cu13 | 3.7.2 | LicenseRef-NVIDIA (not allowlisted; see actual wheel EULA) | [wheel](https://files.pythonhosted.org/packages/81/11/1767ef120299972822a43aceffbc81ac813aad2089d817e36e4e12aa4c9c/nvidia_nvshmem_cu13-3.7.2-py3-none-manylinux2014_aarch64.manylinux_2_17_aarch64.whl) のLICENSE等1件 |
| nvidia-nvtx | 13.2.86 | Apache-2.0（NVTXの原文確認） | [wheel](https://files.pythonhosted.org/packages/49/ee/16bde09927e7ffacd50b117cd7d1dc764d145f03249fc41fdf6dfba3301f/nvidia_nvtx-13.2.86-py3-none-manylinux1_x86_64.manylinux_2_5_x86_64.whl) のLICENSE等1件 |
| triton | 3.9.0 | MIT AND bundled notices (not cleared) | [wheel](https://files.pythonhosted.org/packages/4a/0e/a2176f4ddc2a0c77796d7834cd9bb088cdba4d89e080716b36970dce4ad0/triton-3.9.0-cp311-cp311-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl) のLICENSE等1件 |

このLinuxメタデータ解決にはCUDAの非許可条件が含まれるため、PixelOEの標準extraを空のままにする判断を変えない。Rust FixerのcrateツリーとMacの導入ツリーは対象外。NVIDIAのモデルの重み・GPU runtime・GPLコードはダウンロードも導入もしていない（wheelのLICENSE部分だけをRange取得した）。
