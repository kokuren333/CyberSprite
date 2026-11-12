"""Fixed product budgets checked with Python integers before expensive work."""

from dataclasses import dataclass

from .errors import CyberSpriteError

SOURCE_SIDE = 8192
SOURCE_AREA = 67_108_864
FRAME_COUNT = 4096
TILES_PER_SET = 65_536
DECODED_BYTES = 256 * 1024 * 1024
OUTPUT_BYTES = 256 * 1024 * 1024
DRAW_POINTS = 65_536
OUTPUT_ITEMS = 65_536
WORK_PER_OP = 1_048_576
WORK_PER_TRANSACTION = 16_777_216


def check_limit(name: str, requested: int, limit: int, hint: str) -> None:
    if requested > limit:
        raise CyberSpriteError(
            "E_LIMIT_EXCEEDED",
            f"{name} requests {requested}; the limit is {limit}.",
            hint,
            {"limit_name": name, "requested": requested, "limit": limit},
        )


def output_bytes(width: int, height: int, count: int = 1) -> int:
    """Use RGBA-equivalent bytes even for indexed images; exclude codec scratch space."""
    requested = width * height * 4 * count
    check_limit(
        "output_bytes",
        requested,
        OUTPUT_BYTES,
        "Reduce scale, crop dimensions, frame count, sheet items, or layout padding.",
    )
    return requested


@dataclass
class DecodeBudget:
    frames: int = 0
    bytes: int = 0

    def reserve(self, width: int, height: int, frames: int = 1) -> None:
        source_dimensions(width, height)
        check_limit(
            "source_frames",
            self.frames + frames,
            FRAME_COUNT,
            "Import fewer files/frames or split the animation into separate imports.",
        )
        self.reserve_pixels(width, height, frames)
        self.frames += frames

    def reserve_pixels(self, width: int, height: int, count: int = 1) -> None:
        source_dimensions(width, height)
        requested = self.bytes + width * height * 4 * count
        check_limit(
            "decoded_bytes",
            requested,
            DECODED_BYTES,
            "Reduce source dimensions or import fewer frames/files at once.",
        )
        self.bytes = requested


def source_dimensions(width: int, height: int) -> None:
    check_limit(
        "source_width", width, SOURCE_SIDE, "Resize the source to at most 8192 pixels wide."
    )
    check_limit(
        "source_height", height, SOURCE_SIDE, "Resize the source to at most 8192 pixels high."
    )
    check_limit("source_area", width * height, SOURCE_AREA, "Reduce the source pixel area.")


def drawing_work(requested: int) -> None:
    check_limit(
        "drawing_work_per_op",
        requested,
        WORK_PER_OP,
        "Reduce shape dimensions, path length, vertex count, or brush size; split the work.",
    )


@dataclass
class DrawingBudget:
    units: int = 0

    def reserve(self, requested: int) -> None:
        drawing_work(requested)
        check_limit(
            "drawing_work_per_transaction",
            self.units + requested,
            WORK_PER_TRANSACTION,
            "Split these drawing operations into smaller transactions.",
        )
        self.units += requested
