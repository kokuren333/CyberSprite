"""Original deterministic calibration seed, defined as index arrays, not art.

Run with PYTHONPATH=src python tests/pipeline/corpus/synthetic.py.
The JSON report is stdout only; no source/project files are modified.
"""

import json

import numpy as np

from cybersprite.pipeline.cleanup import cleanup_pixels
from cybersprite.pipeline.decisions import outline_and_dither
from cybersprite.pipeline.downsample import downsample
from cybersprite.pipeline.grid import detect_grid
from cybersprite.pipeline.metrics import compute_metrics, evaluate_gates
from cybersprite.pipeline.quantize import quantize

PALETTE = np.array([[0, 0, 0, 0], [0, 0, 0, 255], [255, 255, 255, 255],
                    [64, 64, 64, 255], [128, 128, 128, 255], [192, 192, 192, 255]], dtype=np.uint8)


def ground_truths():
    y, x = np.indices((8, 9), dtype=np.int64)
    checker = 1 + (x + y) % 2
    ramp = 1 + (x + 2 * y) % 5
    shapes = np.zeros((8, 9), dtype=np.uint8)
    shapes[1:7, 1:8] = 1
    shapes[2:6, 2:7] = 2
    shapes[3:5, 3:6] = 4
    # Two original algebraic boundary probes break periodic ambiguities.
    shapes[0, 0], shapes[-1, -1] = 3, 5
    return {"checker": checker.astype(np.uint8), "ramp": ramp.astype(np.uint8), "shapes": shapes}


def cases():
    for name, indices in ground_truths().items():
        truth = PALETTE[indices]
        for factor in range(2, 9):
            large = truth.repeat(factor, axis=0).repeat(factor, axis=1)
            for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
                # A one-pixel crop at the leading edge changes phase while
                # leaving >= half of the first source cell, as §11.3.2 requires.
                yield f"{name}-s{factor}-crop{dx}{dy}", large[dy:, dx:].copy(), truth.copy(), factor


def perturbed(image, variant):
    out = image.astype(np.int64)
    if variant == "integer-noise":
        y, x, c = np.indices(out[:, :, :3].shape, dtype=np.int64)
        out[:, :, :3] += ((x * 17 + y * 31 + c * 13 + 7) % 17) - 8
    else:
        original = out.copy()
        out[:, 1:, :3] = (3 * original[:, 1:, :3] + original[:, :-1, :3] + 2) // 4
    out = np.clip(out, 0, 255).astype(np.uint8)
    out[out[:, :, 3] == 0] = 0
    return out


def run_case(image, *, degraded=False, grid_settings=None):
    grid = detect_grid(image, **(grid_settings or {}))
    downs, down_report = downsample(image, grid, method="auto" if degraded else "center")
    indices, palette, quant_report = quantize(downs, mode="fixed" if degraded else "exact",
                                             source=PALETTE.tolist() if degraded else None, max_colors=255)
    indices, clean_report = cleanup_pixels(indices[0], palette, min_cluster=1)
    final, palette, choice_report = outline_and_dither(indices, palette)
    metrics = compute_metrics(downs, final, palette)
    gates = evaluate_gates(metrics, grid, grid_thresholds=(990, 1000), fidelity_thresholds=(0, 0),
                           cleanup={"min_cluster": 1})
    decoded = np.asarray(palette, dtype=np.uint8)[final[0]]
    return decoded, {"grid": grid, "downsample": down_report, "quantize": quant_report,
                     "cleanup": clean_report, "choices": choice_report, "metrics": metrics, **gates}


def calibration_report():
    records = []
    for name, image, truth, factor in cases():
        grid_settings = corpus_grid(name, factor)
        decoded, report = run_case(image, grid_settings=grid_settings)
        records.append({"name": name, "category": "a", "factor": factor,
                        "exact": bool(np.array_equal(decoded, truth)),
                        "grid_mode": report["grid"]["mode"],
                        "grid_score": report["grid"]["grid_score"],
                        "fidelity": report["metrics"]["fidelity"],
                        "pixel_sha256": report["metrics"]["pixel_sha256"][0]})
        if name.endswith("s4-crop00") or name.endswith("s7-crop11"):
            for variant in ("integer-noise", "edge-mix"):
                decoded, report = run_case(perturbed(image, variant), degraded=True, grid_settings=grid_settings)
                records.append({"name": f"{name}-{variant}", "category": "b-style",
                                "exact": bool(np.array_equal(decoded, truth)),
                                "grid_score": report["grid"]["grid_score"],
                                "fidelity": report["metrics"]["fidelity"]})
    return records


def corpus_grid(name, factor):
    if name.startswith("shapes-"):
        # Sparse flat regions do not identify a unique automatic period.
        # Exercise the specified-grid recovery path rather than alter §11.3.2.
        dx, dy = (int(c) for c in name[-2:])
        return {"mode": "fixed", "cell_w": factor, "cell_h": factor,
                "offset_x": (factor - dx) % factor, "offset_y": (factor - dy) % factor}
    return {"mode": "auto"}


if __name__ == "__main__":
    print(json.dumps(calibration_report(), sort_keys=True, indent=2))
