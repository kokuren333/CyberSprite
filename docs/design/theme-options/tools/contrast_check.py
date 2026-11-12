"""WCAG 2.x contrast check for the three theme mockups (SPEC 14.3.3).

    python docs/design/theme-options/tools/contrast_check.py

Reads the CSS custom properties actually shipped in option-*/style.css, resolves
var() chains, checks every colour pair the mockups use for text and for
meaningful non-text elements, and writes ../CONTRAST.md. Exit code 1 if any
required pair fails.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

# (foreground var, background var, where it is used, minimum ratio or None = informative)
TEXT = 7.0
SOFT = 4.5
UI = 3.0

COMMON = [
    ("--cs-ink", "--cs-panel", "body text on panels", TEXT),
    ("--cs-ink", "--cs-board", "menu / context bar text on the board", TEXT),
    ("--cs-ink", "--cs-pad", "button and input text on pads", TEXT),
    ("--cs-ink", "--pad-on-bg", "text on pressed / selected pads", TEXT),
    ("--cs-ink", "--act-sel-bg", "selected activity row / selected layer", TEXT),
    ("--cs-ink", "--ph-bg", "panel header text, silk labels", TEXT),
    ("--cs-panel", "--cs-ink", "inverted: tooltip, FG tag, current frame number", TEXT),
    ("--cs-ink-soft", "--cs-panel", "secondary text on panels", SOFT),
    ("--cs-ink-soft", "--cs-board", "secondary text on the board", SOFT),
    ("--cs-ink-soft", "--cs-pad", "secondary text on pads / tag band", SOFT),
    ("--cs-ink-soft", "--act-sel-bg", "secondary text in the selected row", SOFT),
    ("--cs-ink-soft", "--ph-bg", "header meta text", SOFT),
    ("--silk", "--ph-bg", "silk-screen label (pixel font)", SOFT),
    ("--cs-ink", "--cs-panel", "icon line (all icons are ink-outlined)", UI),
    ("--cs-ink", "--cs-pad", "icon line inside pads", UI),
    ("--cs-ink", "--pad-on-bg", "icon line inside the active tool", UI),
    ("--cs-trace-deep", "--cs-panel", "active tool / active tab / selection frame / energised border", UI),
    ("--cs-trace-deep", "--cs-pad", "pressed pad border next to idle pads", UI),
    ("--cs-trace-deep", "--pad-on-bg", "active border vs its own fill", UI),
    ("--cs-trace-deep", "--act-sel-bg", "selected-row bar", UI),
    ("--cs-trace-deep", "--cs-board", "energised panel border on the board", UI),
    ("--cs-ink-soft", "--cs-panel", "empty-cel dot, checkbox frame, slider frame", UI),
    ("--cs-ink", "--cur-col", "cels in the current-frame column", UI),
    ("--cs-agent", "--cs-panel", "agent marker (icon fill, diff box)", UI),
    ("--cs-error", "--cs-panel", "error icon fill", UI),
    ("--cs-warn", "--cs-panel", "warning icon fill (decorative: the ink outline carries the shape)", None),
    ("--cs-trace", "--cs-panel", "bright trace on panels (decorative wiring)", None),
    ("--cs-trace", "--cs-board", "bright trace on the board (decorative wiring)", None),
    ("--cs-trace-soft", "--cs-panel", "soft separators (decorative)", None),
]

EXTRA = {
    "a": [],
    "b": [
        ("--cs-ink", "--cs-board", "silk label + refdes printed on the board", TEXT),
        ("--cs-panel", "--cs-ink", "refdes chip (U1, J1 ...)", TEXT),
        ("--cs-ink-soft", "--cs-panel", "title-block field labels", SOFT),
        ("--cs-trace-deep", "--cs-panel", "component outline / title block rules", UI),
        ("--cs-ink-soft", "--cs-canvas-surround", "dimension lines around the canvas", UI),
        ("--cs-ink", "--cs-canvas-surround", "dimension text", TEXT),
        ("--cs-grid", "--cs-board", "drafting dot grid (decorative)", None),
    ],
    "c": [
        ("--cs-ink", "--cs-trace", "energised header: ink text on solid cyan", TEXT),
        ("--cs-ink", "--cs-trace-soft", "idle header text on soft cyan", TEXT),
        ("--cs-ink-soft", "--cs-trace-soft", "idle header meta text", SOFT),
        ("--cs-ink", "--cs-trace", "via ring on the energised header", UI),
        ("--cs-trace-deep", "--cs-trace-soft", "header rule / active tab vs header", UI),
        ("--cs-trace-deep", "--cs-board", "DIP pins of the tool chip", None),
        ("--cs-mask-trace", "--cs-board", "routed traces on the mask (decorative)", None),
        ("--cs-pad-shade", "--cs-panel", "pad bevel (decorative)", None),
    ],
}


def parse_vars(css: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for block in re.findall(r":root\s*\{(.*?)\}", css, re.S):
        for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", block):
            out[name] = value.strip()
    return out


def resolve(name: str, vars_: dict[str, str], depth=0) -> str:
    v = vars_[name]
    m = re.fullmatch(r"var\((--[\w-]+)\)", v)
    if m:
        return resolve(m.group(1), vars_, depth + 1)
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", v):
        raise ValueError(f"{name} -> {v} is not a plain colour")
    return v.upper()


def lum(hexc: str) -> float:
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hexc[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def ratio(a: str, b: str) -> float:
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def saturation(hexc: str) -> float:
    """Chroma: max - min of the RGB channels (0 = grey). HSL S overstates near-whites."""
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return max(r, g, b) - min(r, g, b)


def main() -> int:
    lines = [
        "# コントラスト検査（テーマ 3 案）",
        "",
        "`tools/contrast_check.py` が各案の `style.css` の CSS 変数を読み、WCAG 2.x の相対輝度でコントラスト比を計算した結果である。"
        "基準は SPEC §14.3.3: 本文 7:1、補助の文字 4.5:1、意味のある文字以外の要素 3:1。"
        "「基準」が `—` の行は装飾（意味を持たない配線など）で、参考として値だけを載せる。",
        "",
        "再生成: `python docs/design/theme-options/tools/contrast_check.py`",
        "",
    ]
    failures = 0
    summary = []
    for key in ("a", "b", "c"):
        css = (ROOT / f"option-{key}" / "style.css").read_text(encoding="utf-8")
        vars_ = parse_vars(css)
        pairs = COMMON + EXTRA[key]
        rows = []
        worst_req = None
        n_req = n_fail = 0
        for fg, bg, use, need in pairs:
            cf, cb = resolve(fg, vars_), resolve(bg, vars_)
            r = ratio(cf, cb)
            if need is None:
                verdict = "参考"
            elif r >= need:
                verdict = "OK"
                n_req += 1
            else:
                verdict = "**NG**"
                n_req += 1
                n_fail += 1
            if need is not None and (worst_req is None or r / need < worst_req[0]):
                worst_req = (r / need, use, r, need)
            rows.append(f"| {use} | `{fg}` {cf} | `{bg}` {cb} | {r:.2f} | {'—' if need is None else f'{need:g}:1'} | {verdict} |")
        failures += n_fail
        sur = resolve("--cs-canvas-surround", vars_)
        ca, cb_ = resolve("--cs-checker-a", vars_), resolve("--cs-checker-b", vars_)
        lines += [
            f"## Option {key.upper()}",
            "",
            f"必須 {n_req} 組のうち不合格 {n_fail} 組。最も余裕が小さい組: {worst_req[1]}（{worst_req[2]:.2f} / 基準 {worst_req[3]:g}）。",
            "",
            "| 用途 | 前景 | 背景 | 比 | 基準 | 判定 |",
            "|---|---|---|---:|---:|---|",
            *rows,
            "",
            f"キャンバス周囲の色み（クロマ = RGB の最大 − 最小、0 が無彩色）: surround {sur} = {saturation(sur):.2f}、"
            f"市松 {ca} = {saturation(ca):.2f} / {cb_} = {saturation(cb_):.2f}（参考: UI の `--cs-trace` は 0.80。低いほど絵の色判断を邪魔しない）。",
            "",
        ]
        summary.append((key, n_req, n_fail, worst_req))
    lines += ["## まとめ", "", "| 案 | 必須の組 | 不合格 | 最小余裕の組 |", "|---|---:|---:|---|"]
    for key, n_req, n_fail, w in summary:
        lines.append(f"| {key.upper()} | {n_req} | {n_fail} | {w[1]}（{w[2]:.2f} / {w[3]:g}） |")
    lines += [
        "",
        "### 注記",
        "",
        "- 明るい水色 `--cs-trace` は白地で 3:1 に届かない。どの案でも配線・区切りの装飾にだけ使い、文字、選択表示、フォーカスには使わない（選択・通電は `--cs-trace-deep` と形の変化で示す）。",
        "- 警告色 `--cs-warn`（はんだの金色）は白地で 3:1 に届かない。警告アイコンは濃紺の輪郭と「!」で形を作り、金色は塗りの補助に留める。",
        "- 状態は色だけで示さない: セルは形（点 / 塗り四角 / 白抜き四角＋連結線）、検証は記号（チェック / 三角）と文字、実行者はアイコン（ロボット / 人）と名前、選択は枠＋左の帯で示す。",
    ]
    (ROOT / "CONTRAST.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    for key, n_req, n_fail, w in summary:
        print(f"option {key}: {n_req} required pairs, {n_fail} failing; tightest {w[1]} {w[2]:.2f}/{w[3]:g}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
