"""Assemble CyberSprite `render` outputs into review sheets (inspection only, no drawing).

Usage: python contact_sheet.py <renders dir containing x1/ and x4/> <out dir>
Writes:
  contact-x4.png   every icon at x4 on three theme-C backgrounds (panel, board, active pad)
  strip-x1.png     every icon at true size on the same backgrounds (what the GUI shows at 1x)
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import icon_grids  # noqa: E402

BGS = [("panel", (255, 255, 255)), ("board", (221, 243, 248)), ("active", (191, 239, 249))]


def main() -> None:
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    names = list(icon_grids.all_icons())
    cols = 8
    rows = (len(names) + cols - 1) // cols
    cw, ch = 64 * 3 + 4 * 4, 64 + 22
    sheet = Image.new("RGB", (cols * cw, rows * ch), (90, 110, 120))
    d = ImageDraw.Draw(sheet)
    for i, n in enumerate(names):
        im = Image.open(src / "x4" / f"{n}.png").convert("RGBA")
        assert im.size == (64, 64), (n, im.size)
        x0, y0 = (i % cols) * cw, (i // cols) * ch
        for j, (_, bg) in enumerate(BGS):
            tile = Image.new("RGBA", (64, 64), bg + (255,))
            tile.alpha_composite(im)
            sheet.paste(tile, (x0 + 4 + j * 68, y0 + 4))
        d.text((x0 + 6, y0 + 68), n, fill=(255, 255, 255))
    sheet.save(out / "contact-x4.png")

    # true-size strip, then the same strip magnified x3 (nearest) so it can be inspected
    strip = Image.new("RGB", (len(names) * 20 + 4, len(BGS) * 20 + 4), (90, 110, 120))
    for j, (_, bg) in enumerate(BGS):
        for i, n in enumerate(names):
            im = Image.open(src / "x1" / f"{n}.png").convert("RGBA")
            assert im.size == (16, 16), (n, im.size)
            tile = Image.new("RGBA", (20, 20), bg + (255,))
            tile.alpha_composite(im, (2, 2))
            strip.paste(tile, (2 + i * 20, 2 + j * 20))
    strip.save(out / "strip-x1.png")
    strip.resize((strip.width * 3, strip.height * 3), Image.NEAREST).save(
        out / "strip-x1-zoom3.png"
    )


if __name__ == "__main__":
    main()
