"""Original readers for GPL (palette text), JASC PAL and line-based HEX files."""

import json
from importlib.resources import files
from pathlib import Path

from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.pixels import rgba


def presets():
    return json.loads(files("cybersprite").joinpath("data/palettes/index.json").read_text("utf-8"))


def raw_color(value):
    return "#" + "".join(f"{v:02x}" for v in rgba(value))


def read_palette(source):
    names = [item["name"] for item in presets()]
    preset = source in names
    try:
        if preset:
            text = files("cybersprite").joinpath(f"data/palettes/{source}.gpl").read_text("utf-8")
            suffix = ".gpl"
        else:
            path = Path(source)
            suffix = path.suffix.lower()
            if suffix not in (".gpl", ".pal", ".hex"):
                raise CyberSpriteError(
                    "E_UNSUPPORTED",
                    "This palette format is available in M5.",
                    "Use a built-in preset or .gpl, .pal, .hex text palette.",
                )
            text = path.read_text("utf-8-sig")
    except OSError as error:
        raise CyberSpriteError(
            "E_IO", f"Cannot read palette: {error}", "Check the palette path and read permissions."
        ) from error
    lines = text.splitlines()
    colors = []
    try:
        if suffix == ".hex":
            colors = [
                raw_color(line.strip() if line.strip().startswith("#") else "#" + line.strip())
                for line in lines
                if line.strip() and not line.strip().startswith(";")
            ]
        else:
            if suffix == ".pal":
                if len(lines) < 3 or lines[:2] != ["JASC-PAL", "0100"]:
                    raise ValueError("Expected JASC-PAL 0100 header.")
                count = int(lines[2])
                lines = lines[3:]
            else:
                if not lines or lines[0] != "GIMP Palette":
                    raise ValueError("Expected GIMP Palette header.")
                count = None
                lines = lines[1:]
            for line in lines:
                line = line.strip()
                if not line or line.startswith(("#", "Name:", "Columns:")):
                    continue
                values = [int(v) for v in line.split()[:3]]
                if len(values) != 3 or any(not 0 <= v <= 255 for v in values):
                    raise ValueError("RGB components must be 0..255.")
                colors.append("#" + "".join(f"{v:02x}" for v in values) + "ff")
            if count is not None and count != len(colors):
                raise ValueError("Declared color count does not match the file.")
    except (ValueError, IndexError) as error:
        raise invalid("Invalid palette text file.", source=source, reason=str(error)) from error
    if preset:
        colors.insert(0, "#00000000")
    if not 1 <= len(colors) <= 256:
        raise invalid("Palette must contain 1..256 colors.", count=len(colors))
    return colors
