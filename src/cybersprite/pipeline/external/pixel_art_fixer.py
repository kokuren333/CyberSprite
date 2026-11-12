"""Pixel Art Fixer Python reference adapter (MIT); no vendored upstream code."""

import hashlib
from pathlib import Path

from . import _common as common

INSTALL = (
    "Install Retro-Diffusion/pixel-art-fixer's Python pixelfixer module yourself and expose "
    "its python/ directory on PYTHONPATH. Its OpenCV wheels may bundle LGPL FFmpeg; "
    "CyberSprite neither installs nor redistributes that dependency tree."
)


def available():
    return common.available("pixelfixer", INSTALL)


def describe():
    result = common.describe("pixel-art-fixer", "pixelfixer", "MIT")
    if result["version"] == "uninstalled" and available()[0]:
        module = common.load("pixelfixer", INSTALL)
        if not getattr(module, "__file__", None):
            result["version"] = "unknown (runtime has no source path)"
            return result
        fingerprint = hashlib.sha256()
        for path in sorted(Path(module.__file__).parent.rglob("*.py")):
            fingerprint.update(path.relative_to(Path(module.__file__).parent).as_posix().encode())
            fingerprint.update(b"\0" + path.read_bytes() + b"\0")
        result["version"] = "source-sha256:" + fingerprint.hexdigest()
    return result


def run(rgba, params):
    frames, _ = common.inputs(rgba, params, ())
    module = common.load("pixelfixer", INSTALL)
    reconstruct = common.load("pixelfixer.reconstruct", INSTALL).reconstruct
    cv = common.load("cv2", INSTALL)
    with common.serial_cv(cv):
        detected = module.detect(frames[0])
        required = ("step_x", "step_y", "cols", "rows", "consensus")
        if not all(key in detected for key in required):
            raise common.invalid(
                "Fixer detection is missing required grid metrics.", required=list(required)
            )
        result = reconstruct(
            frames[0], detected["step_x"], detected["step_y"], detected["cols"], detected["rows"]
        )
    return common.output(result), {
        **describe(),
        "device": "cpu",
        "opencv_threads": 1,
        "thread_policy": "OpenCV single thread; NumPy/SciPy backend threads are user controlled",
        "seed": 0,
        "params": {},
        "grid": {key: detected[key] for key in required},
        "quantized": False,
    }
