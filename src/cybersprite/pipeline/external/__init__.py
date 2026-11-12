"""Optional pixelizers registered through lazy, bundled pipeline entry points.

Inputs are nonempty uint8 H x W x 4 arrays; proper_pixel_art also accepts
a same-sized frame list. Outputs are RGBA arrays (or a matching frame list),
never project mutations. Quantization and palette locking belong to the caller.
No adapter installs packages, downloads files, or opens video paths.
"""
