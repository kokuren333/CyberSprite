"""Shared validation and integer array helpers; no project dependencies."""

import numpy as np


class PipelineError(ValueError):
    """A pure-step error, adaptable to the future Op error boundary."""

    def __init__(self, code, message, hint, **details):
        super().__init__(f"{code}: {message} Hint: {hint}")
        self.code, self.message, self.hint, self.details = code, message, hint, details


def require(condition, message, hint="Check the pipeline settings and input array."):
    if not condition:
        raise PipelineError("E_INVALID_ARGS", message, hint)


def integer(value, name, low, high=None):
    require(isinstance(value, (int, np.integer)) and not isinstance(value, bool),
            f"{name} must be an integer.")
    require(value >= low and (high is None or value <= high), f"{name} is out of range.")
    return int(value)


def rgba_frames(images):
    if isinstance(images, np.ndarray) and images.ndim == 3:
        images = [images]
    result = list(images)
    require(bool(result), "At least one RGBA frame is required.")
    for im in result:
        require(isinstance(im, np.ndarray) and im.dtype == np.uint8 and
                im.ndim == 3 and im.shape[2] == 4 and min(im.shape[:2]) > 0,
                "Frames must be nonempty H x W x 4 uint8 arrays.")
    require(all(im.shape == result[0].shape for im in result), "Frame dimensions must match.")
    return result


def lower_median(pixels):
    return np.sort(pixels, axis=0)[(len(pixels) - 1) // 2].copy()


def interior(image):
    h, w = image.shape[:2]
    dx, dy = (max(1, w // 5) if w >= 4 else 0), (max(1, h // 5) if h >= 4 else 0)
    return image[dy:h - dy, dx:w - dx]


def neighbors(x, y, w, h, connectivity=8):
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if (dx or dy) and (connectivity == 8 or abs(dx) + abs(dy) == 1):
                xx, yy = x + dx, y + dy
                if 0 <= xx < w and 0 <= yy < h:
                    yield xx, yy
