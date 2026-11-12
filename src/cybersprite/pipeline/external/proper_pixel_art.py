"""proper-pixel-art 2.x image-only adapter, including shared-mesh frame lists."""

import numpy as np
from PIL import Image

from . import _common as common

INSTALL = (
    "Install proper-pixel-art==2.0.0 yourself after reviewing its dependency licenses. "
    "PyAV wheels bundle FFmpeg (potential GPL) and OpenCV wheels may bundle LGPL components. "
    "CyberSprite never imports the video module or calls the video API."
)


def available():
    return common.available("proper_pixel_art", INSTALL)


def describe():
    return common.describe("proper-pixel-art", "proper-pixel-art", "MIT")


def run(rgba, params):
    frames, single = common.inputs(rgba, params, ("pixel_width",), multiple=True)
    width = common.positive(params, "pixel_width") if "pixel_width" in params else None
    module = common.load("proper_pixel_art", INSTALL)
    image_api = common.load("proper_pixel_art.image", INSTALL)
    utils = common.load("proper_pixel_art.utils", INSTALL)
    cv = common.load("cv2", INSTALL)
    config = module.PixelateConfig(pixel_width=width, initial_upscale_factor=1)
    config.colors.method = "dominant"
    config.colors.dominant.merge_distance = 0
    with common.serial_cv(cv):
        detections = [module.pixelate(Image.fromarray(frame), config=config) for frame in frames]
        # Use the modal complete mesh; ties use the first frame. All frames vote.
        keys = [tuple(tuple(int(v) for v in axis) for axis in result.mesh) for result in detections]
        chosen = max(range(len(keys)), key=lambda i: (keys.count(keys[i]), -i))
        grid = detections[chosen]
        results = [
            common.output(
                image_api.downsample(
                    utils.scale_img(Image.fromarray(frame), grid.upscale_factor),
                    grid.mesh,
                    skip_quantization=True,
                    color_config=config.colors,
                )
            )
            for frame in frames
        ]
    palette = np.unique(np.concatenate([frame.reshape(-1, 4) for frame in results]), axis=0)
    return results[0] if single else results, {
        **describe(),
        "device": "cpu",
        "opencv_threads": 1,
        "thread_policy": "OpenCV single thread; NumPy/SciPy backend threads are user controlled",
        "seed": 0,
        "params": {
            "pixel_width": width,
            "initial_upscale_factor": 1,
            "color_method": "dominant",
            "merge_distance": 0,
        },
        "quantized": False,
        "grid_policy": "modal frame mesh; first frame breaks ties",
        "selected_frame": chosen,
        "grid": {
            "x_lines": list(keys[chosen][0]),
            "y_lines": list(keys[chosen][1]),
            "upscale_factor": int(grid.upscale_factor),
            "pixel_width": int(grid.pixel_width),
        },
        "shared_palette": palette.tolist(),
        "shared_palette_policy": "exact union; caller locks once",
    }
