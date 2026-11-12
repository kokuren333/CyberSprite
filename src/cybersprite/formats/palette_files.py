"""Original palette codecs; raster decoding is a lazy formats-only Pillow dependency."""

import io
import json
from importlib.resources import files
from pathlib import Path

import numpy as np

from cybersprite.core.errors import CyberSpriteError, invalid
from cybersprite.core.pixels import rgba


def presets():
    return json.loads(files("cybersprite").joinpath("data/palettes/index.json").read_text("utf-8"))


def raw_color(value):
    return "#" + "".join(f"{v:02x}" for v in rgba(value))


def _limit(colors):
    if len(colors) > 256:
        raise CyberSpriteError(
            "E_LIMIT_EXCEEDED",
            "Palette contains more than 256 colors.",
            "Reduce the source palette to at most 256 colors.",
            {"limit": 256, "requested": len(colors)},
        )
    if not colors:
        raise invalid("Palette must contain at least one color.")


def decode_palette(data, format):
    names = {}
    if format == "png":
        from PIL import Image

        with Image.open(io.BytesIO(data)) as image:
            colors = list(
                dict.fromkeys(
                    "#" + bytes(c).hex()
                    for c in np.asarray(image.convert("RGBA"), dtype=np.uint8).reshape(-1, 4)
                )
            )
        _limit(colors)
        return colors, names
    if format not in ("gpl", "pal", "hex"):
        raise invalid("Palette format must be gpl, pal, hex, or png.")
    try:
        lines = data.decode("utf-8-sig").splitlines()
        colors = []
        if format == "hex":
            colors = [
                raw_color(line.strip() if line.strip().startswith("#") else "#" + line.strip())
                for line in lines
                if line.strip() and not line.strip().startswith(";")
            ]
        else:
            count = None
            if format == "pal":
                if len(lines) < 3 or lines[:2] != ["JASC-PAL", "0100"]:
                    raise ValueError("Expected JASC-PAL 0100 header.")
                count, lines = int(lines[2]), lines[3:]
            else:
                if not lines or lines[0] != "GIMP Palette":
                    raise ValueError("Expected GIMP Palette header.")
                lines = lines[1:]
            for line in lines:
                line = line.strip()
                if not line or line.startswith(("#", "Name:", "Columns:")):
                    continue
                parts = line.split(maxsplit=3)
                rgb = [int(v) for v in parts[:3]]
                if len(rgb) != 3 or any(not 0 <= v <= 255 for v in rgb):
                    raise ValueError("RGB components must be 0..255.")
                if format == "gpl" and len(parts) == 4:
                    names[str(len(colors))] = parts[3]
                colors.append("#" + bytes(rgb).hex() + "ff")
            if count is not None and count != len(colors):
                raise ValueError("Declared color count does not match the file.")
    except (ValueError, IndexError, UnicodeError) as error:
        raise invalid("Invalid palette text file.", reason=str(error)) from error
    _limit(colors)
    return colors, names


def encode_palette(colors, names, format, name="Palette"):
    from .png import encode_png

    _limit(colors)
    if format == "png":
        # RGBA keeps the transparent entry's stored RGB intact, independently of rendering.
        pixels = np.array([[rgba(c) for c in colors]], dtype=np.uint8)
        return encode_png(pixels, compression="stored")
    if format == "hex":
        return ("\n".join(c.lower() for c in colors) + "\n").encode("utf-8")
    if format not in ("gpl", "pal"):
        raise invalid("Palette format must be gpl, pal, hex, or png.")
    header = (
        ["GIMP Palette", "Name: " + name.replace("\n", " ").replace("\r", " ")]
        if format == "gpl"
        else ["JASC-PAL", "0100", str(len(colors))]
    )
    for index, color in enumerate(colors):
        line = " ".join(str(v) for v in rgba(color)[:3])
        if format == "gpl" and str(index) in names:
            label = names[str(index)]
            if not label or label != label.strip() or any(c in label for c in "\r\n"):
                raise invalid(
                    "GPL color names must be nonempty single lines without edge whitespace.",
                    index=index,
                )
            line += "\t" + label
        header.append(line)
    return ("\n".join(header) + "\n").encode("utf-8")


def read_palette_with_names(source):
    preset = source in [item["name"] for item in presets()]
    try:
        if preset:
            data = files("cybersprite").joinpath(f"data/palettes/{source}.gpl").read_bytes()
            format = "gpl"
        else:
            path = Path(source)
            if path.is_dir() or path.name == "project.json":
                from cybersprite.core.canonical import load_project

                palette = load_project(path).palette
                return list(palette.colors), dict(palette.names)
            if path.suffix.lower() in (".aseprite", ".ase"):
                from .aseprite_io import read_aseprite

                palette = read_aseprite(path)[0].palette
                return list(palette.colors), dict(palette.names)
            format = path.suffix.lower().removeprefix(".")
            if format not in ("gpl", "pal", "hex", "png"):
                raise CyberSpriteError(
                    "E_UNSUPPORTED",
                    "Unsupported palette file format.",
                    "Use gpl, pal, hex, png, aseprite, or a project directory.",
                )
            data = path.read_bytes()
        colors, names = decode_palette(data, format)
    except OSError as error:
        raise CyberSpriteError(
            "E_IO", f"Cannot read palette: {error}", "Check the palette path and read permissions."
        ) from error
    if preset:
        colors.insert(0, "#00000000")
        names = {str(int(k) + 1): v for k, v in names.items()}
    _limit(colors)
    return colors, names


def read_palette(source):
    return read_palette_with_names(source)[0]
