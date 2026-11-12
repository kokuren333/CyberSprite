"""Offline neutral pixelizer benchmark on original art and recorded generated inputs.

No third-party sprites, network access, package installation, or golden updates.
All stochastic degradation is confined to this engineering tool, never the pipeline.
"""

import argparse
import atexit
import hashlib
import importlib
import io
import json
import platform
import random
import statistics
import subprocess
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

from cybersprite.core.color import rgb_to_oklab_fixed_numpy
from cybersprite.pipeline.decode import decode_raster
from cybersprite.pipeline.runner import run_pipeline

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/pipeline/corpus"
_XPRITE_CLIENT = None


class XpriteClient:
    """One evaluation worker; amortize Node import without excluding image work."""

    def __init__(self, root):
        self.root = root
        self._start()
        atexit.register(self.close)

    def _start(self):
        self.process = subprocess.Popen(
            ["node", str(ROOT / "tools/pixelize_xprite.mjs"), str(self.root), "--worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self.reader = ThreadPoolExecutor(max_workers=1)
        self.closed = False

    def run(self, payload):
        if self.closed or self.process.poll() is not None:
            self.close()
            self._start()
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()
        try:
            line = self.reader.submit(self.process.stdout.readline).result(timeout=120)
        except TimeoutError as error:
            self.close()
            raise TimeoutError("Xprite worker exceeded its 120-second deadline.") from error
        if not line:
            raise RuntimeError(self.process.stderr.read())
        return json.loads(line)

    def close(self):
        if self.closed:
            return
        if self.process.poll() is None:
            self.process.kill()
        self.process.communicate()
        self.reader.shutdown(wait=True)
        self.closed = True


FAMILIES = (
    "nearest",
    "fractional",
    "offset",
    "blur",
    "jpeg50",
    "jpeg75",
    "noise",
    "jitter",
    "alpha_aa",
)


def read_rgba(path):
    return decode_raster(path)[0][0]


def digest(image):
    return hashlib.sha256(image.tobytes()).hexdigest()


def blur(image):
    """Separable [1,2,1] integer kernel, replicated boundary, round half up."""
    value = image.astype(np.int64)
    for axis in (0, 1):
        pad = [(0, 0)] * 3
        pad[axis] = (1, 1)
        padded = np.pad(value, pad, mode="edge")
        a, b, c = [slice(None)] * 3, [slice(None)] * 3, [slice(None)] * 3
        a[axis], b[axis], c[axis] = slice(0, -2), slice(1, -1), slice(2, None)
        value = (padded[tuple(a)] + 2 * padded[tuple(b)] + padded[tuple(c)] + 2) // 4
    return value.astype(np.uint8)


def cases(truth, *, smoke=False):
    h, w = truth.shape[:2]
    for factor in (2,) if smoke else range(2, 13):
        yield (
            f"nearest-x{factor}",
            "nearest",
            truth.repeat(factor, 0).repeat(factor, 1),
            [factor, 1],
        )
    expanded = truth.repeat(6, 0).repeat(6, 1)
    fractional = np.array(
        Image.fromarray(truth).resize((w * 11 // 2, h * 11 // 2), Image.Resampling.BILINEAR)
    )
    yield "fractional-11-2-bilinear", "fractional", fractional, [11, 2]
    if smoke:
        yield "blur-x6", "blur", blur(expanded), [6, 1]
        return
    yield "offset-x6-crop-2-1", "offset", expanded[1:-1, 2:-2].copy(), [6, 1]
    yield "blur-x6", "blur", blur(expanded), [6, 1]
    for quality in (50, 75):
        # JPEG cannot carry alpha; composite on the same explicit matte for all methods.
        rgb = expanded.copy()
        rgb[rgb[:, :, 3] < 128] = (246, 244, 238, 255)
        data = io.BytesIO()
        Image.fromarray(rgb[:, :, :3]).save(
            data, format="JPEG", quality=quality, subsampling=0, optimize=False, progressive=False
        )
        with Image.open(io.BytesIO(data.getvalue())) as decoded:
            degraded = np.array(decoded.convert("RGBA"))
        yield f"jpeg-q{quality}-x6", f"jpeg{quality}", degraded, [6, 1]
    rng = random.Random(1301)
    noise = np.fromiter(
        (rng.randrange(-8, 9) for _ in range(expanded.size)), dtype=np.int16
    ).reshape(expanded.shape)
    noisy = np.clip(expanded.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    noisy[:, :, 3] = expanded[:, :, 3]
    yield "noise-uniform-8-seed1301-x6", "noise", noisy, [6, 1]
    jittered = expanded.copy()
    for color in np.unique(expanded.reshape(-1, 4), axis=0):
        if color[3]:
            replacement = np.clip(
                color[:3].astype(np.int16) + [rng.randrange(-12, 13) for _ in range(3)], 0, 255
            )
            jittered[np.all(expanded == color, axis=2), :3] = replacement
    yield "palette-jitter-12-seed1301-x6", "jitter", jittered, [6, 1]
    softened = expanded.copy()
    softened[:, :, 3] = blur(expanded)[:, :, 3]
    yield "alpha-aa-kernel121-x6", "alpha_aa", softened, [6, 1]


def compare(result, truth, expected_step, input_shape):
    """No spatial resize/alignment of a wrong-sized result; report those metrics as null.

    Palette mapping maximizes spatial agreement, independently for each output color
    within its opacity class. Ties use fixed-point Oklab distance, then RGBA order.
    Raw exact RGBA accuracy is also reported so palette mapping cannot hide color changes.
    """
    h, w = truth.shape[:2]
    rh, rw = result.shape[:2]

    def colors(a):
        return np.unique(a[a[:, :, 3] >= 128], axis=0)

    color_delta = len(colors(result)) - len(colors(truth))
    num, den = expected_step
    step_error = (
        abs(input_shape[1] * den - rw * num) / (rw * den)
        + abs(input_shape[0] * den - rh * num) / (rh * den)
    ) / 2
    metrics = {
        "size_exact": (rh, rw) == (h, w),
        "grid_step_error": step_error,
        "color_count_delta": color_delta,
        "exact_rgba": None,
        "mapped_exact_rgba": None,
        "oklab_match": None,
        "mask_iou": None,
    }
    if (rh, rw) != (h, w):
        return metrics
    a, b = result[:, :, 3] >= 128, truth[:, :, 3] >= 128
    union = int(np.count_nonzero(a | b))
    metrics["mask_iou"] = int(np.count_nonzero(a & b)) / union if union else 1
    metrics["exact_rgba"] = float(np.all(result == truth, axis=2).mean())
    source, inverse = np.unique(result.reshape(-1, 4), axis=0, return_inverse=True)
    target, truth_inverse = np.unique(truth.reshape(-1, 4), axis=0, return_inverse=True)
    overlap = np.bincount(
        inverse * len(target) + truth_inverse, minlength=len(source) * len(target)
    ).reshape(len(source), len(target))
    labs = rgb_to_oklab_fixed_numpy(target[:, :3])
    source_labs = rgb_to_oklab_fixed_numpy(source[:, :3])
    mapped = source.copy()
    for i, color in enumerate(source):
        valid = (target[:, 3] >= 128) == (color[3] >= 128)
        if np.any(valid):
            candidates = np.flatnonzero(valid)
            support = overlap[i, candidates]
            candidates = candidates[support == support.max()]
            dist = ((labs[candidates] - source_labs[i]) ** 2).sum(axis=1)
            mapped[i] = target[candidates[int(np.argmin(dist))]]
    mapped = mapped[inverse].reshape(truth.shape)
    metrics["mapped_exact_rgba"] = float(np.all(mapped == truth, axis=2).mean())
    delta = rgb_to_oklab_fixed_numpy(result[:, :, :3]) - rgb_to_oklab_fixed_numpy(truth[:, :, :3])
    close = (delta * delta).sum(axis=2) <= 2500**2
    metrics["oklab_match"] = float(((close & a & b) | (~a & ~b)).mean())
    return metrics


def detected_step_error(grid, expected_step):
    """Use reported pitches, so a cropped extent is not mistaken for pitch error."""
    if not grid:
        return None
    if "step_x" in grid:
        steps = [grid["step_x"], grid["step_y"]]
    elif "cellWidth" in grid:
        steps = [grid["cellWidth"], grid["cellHeight"]]
    elif grid.get("x") and grid.get("y"):
        steps = [grid[axis]["numerator"] / grid[axis]["denominator"] for axis in ("x", "y")]
    elif "pixel_width" in grid:
        steps = [grid["pixel_width"] / grid["upscale_factor"]] * 2
    else:
        return None
    expected = expected_step[0] / expected_step[1]
    return statistics.mean(abs(step - expected) for step in steps)


def method(name, image, target, directory, xprite_root=None):
    raw, detail = raw_method(name, image, target, directory, xprite_root)
    if name == "builtin":
        return raw, detail
    frames, palette, lock_report = run_pipeline(
        raw, directory / "palette-lock", preset="ai", overrides={"grid": {"mode": "none"}}
    )
    detail["downstream"] = "CyberSprite ai palette/cleanup; raw source grid gates not available"
    detail["lock_accepted"] = lock_report["accepted"]
    return np.asarray(palette, dtype=np.uint8)[frames[0]], detail


def raw_method(name, image, target, directory, xprite_root=None):
    if name == "builtin":
        frames, palette, report = run_pipeline(image, directory, preset="ai")
        return np.asarray(palette, dtype=np.uint8)[frames[0]], {
            "accepted": report["accepted"],
            "grid": report["grid"],
            "gates": report["gates"],
        }
    if name == "xprite":
        payload = {
            "width": image.shape[1],
            "height": image.shape[0],
            "data": image.reshape(-1).tolist(),
        }
        if _XPRITE_CLIENT is not None:
            data = _XPRITE_CLIENT.run(payload)
        else:
            data = _xprite_once(payload, xprite_root)
        return np.asarray(data["data"], dtype=np.uint8).reshape(
            data["height"], data["width"], 4
        ), data["metrics"]
    adapter = importlib.import_module("cybersprite.pipeline.external." + name)
    params = {"target_w": target[0], "target_h": target[1]} if name == "pixeloe" else {}
    return adapter.run(image, params)


def _xprite_once(payload, xprite_root):
    process = subprocess.run(
        ["node", str(ROOT / "tools/pixelize_xprite.mjs"), str(xprite_root)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=120,
    )
    if process.returncode:
        raise RuntimeError(process.stderr.strip())
    return json.loads(process.stdout)


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["method"], row["family"])].append(row)
    result = []
    for (name, family), group in sorted(groups.items()):
        values = {
            "method": name,
            "family": family,
            "n": len(group),
            "errors": sum("error" in row for row in group),
        }
        for key in (
            "size_exact",
            "grid_step_error",
            "exact_rgba",
            "mapped_exact_rgba",
            "oklab_match",
            "color_count_delta",
            "mask_iou",
        ):
            defined = [
                r["metrics"][key] for r in group if r.get("metrics", {}).get(key) is not None
            ]
            values[key] = (
                sum(r.get("metrics", {}).get("size_exact", False) for r in group) / len(group)
                if key == "size_exact"
                else statistics.mean(defined)
                if defined
                else None
            )
            values[key + "_n"] = len(defined)
        timings = [r["median_ms"] for r in group if "median_ms" in r]
        values["median_ms"] = statistics.median(timings) if timings else None
        result.append(values)
    return result


def benchmark(output, *, limit=None, smoke=False, repeats=3, xprite_root=None, generated=True):
    global _XPRITE_CLIENT
    output.mkdir(parents=True, exist_ok=True)
    methods = ["builtin"]
    skipped = {}
    for name in ("pixel_art_fixer", "proper_pixel_art", "pixeloe"):
        ok, reason = importlib.import_module("cybersprite.pipeline.external." + name).available()
        if ok:
            methods.append(name)
        else:
            skipped[name] = reason
    if xprite_root:
        methods.append("xprite")
        _XPRITE_CLIENT = XpriteClient(xprite_root)
    else:
        skipped["xprite"] = (
            "Evaluation-only package not supplied via --xprite-root (no runtime network)."
        )
    rows = []
    paths = sorted((CORPUS / "originals").glob("*.png"))
    for path in paths[:limit] if limit else paths:
        truth = read_rgba(path)
        for recipe, family, image, step in cases(truth, smoke=smoke):
            for name in methods:
                directory = output / path.stem / recipe / name
                row = {
                    "source": path.name,
                    "recipe": recipe,
                    "family": family,
                    "method": name,
                    "truth_sha256": digest(truth),
                    "input_sha256": digest(image),
                    "oracle_size": name == "pixeloe",
                }
                elapsed, hashes = [], []
                try:
                    for _ in range(repeats):
                        start = time.perf_counter_ns()
                        result, detail = method(
                            name, image, (truth.shape[1], truth.shape[0]), directory, xprite_root
                        )
                        elapsed.append((time.perf_counter_ns() - start) / 1_000_000)
                        hashes.append(digest(result))
                    row.update(
                        {
                            "runs_ms": elapsed,
                            "median_ms": statistics.median(elapsed),
                            "repeat_identical": len(set(hashes)) == 1,
                            "output_sha256": hashes[-1],
                            "repeat_pixel_sha256": hashes,
                            "size": [result.shape[1], result.shape[0]],
                            "metrics": compare(result, truth, step, image.shape),
                            "accepted": detail.get("accepted"),
                            "grid": detail.get("grid"),
                        }
                    )
                    row["expected_step"] = step
                    row["metrics"]["grid_step_error"] = detected_step_error(
                        detail.get("grid"), step
                    )
                    if name != "builtin":
                        from cybersprite.formats.png import encode_png

                        directory.mkdir(parents=True, exist_ok=True)
                        (directory / "result.png").write_bytes(encode_png(result))
                except Exception as error:
                    row["error"] = f"{type(error).__name__}: {error}"
                rows.append(row)
            print(path.stem, recipe, flush=True)
    generated_rows = []
    if generated and (CORPUS / "generated/manifest.json").exists():
        manifest = json.loads((CORPUS / "generated/manifest.json").read_text(encoding="utf-8"))
        for entry in manifest["images"]:
            image = read_rgba(CORPUS / "generated" / entry["file"])
            for name in methods:
                if name == "pixeloe":
                    generated_rows.append(
                        {
                            "source": entry["file"],
                            "method": name,
                            "skipped": "No ground-truth target size for generated input.",
                        }
                    )
                    continue
                try:
                    result, detail = method(
                        name, image, None, output / "generated" / entry["id"] / name, xprite_root
                    )
                    generated_rows.append(
                        {
                            "source": entry["file"],
                            "category": entry["category"],
                            "method": name,
                            "size": [result.shape[1], result.shape[0]],
                            "grid": detail.get("grid"),
                            "accepted": detail.get("accepted"),
                            "gates": detail.get("gates"),
                            "output_sha256": digest(result),
                        }
                    )
                except Exception as error:
                    generated_rows.append(
                        {"source": entry["file"], "method": name, "error": str(error)}
                    )
    report = {
        "version": 1,
        "seed": 1301,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pillow": Image.__version__,
        "repeats": repeats,
        "methods": methods,
        "skipped": skipped,
        "records": rows,
        "summary": summarize(rows),
        "generated": generated_rows,
    }
    (output / "results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    if _XPRITE_CLIENT is not None:
        _XPRITE_CLIENT.close()
        _XPRITE_CLIENT = None
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/pixelize-bench")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--xprite-root",
        type=Path,
        help="User-installed @xprite/pixelate package root (evaluation only).",
    )
    parser.add_argument("--no-generated", action="store_true")
    args = parser.parse_args()
    if args.repeats < 1 or args.limit is not None and args.limit < 1:
        parser.error("repeats and limit must be positive")
    report = benchmark(
        args.output,
        limit=args.limit,
        smoke=args.smoke,
        repeats=args.repeats,
        xprite_root=args.xprite_root,
        generated=not args.no_generated,
    )
    print(
        json.dumps(
            {
                "records": len(report["records"]),
                "summary": report["summary"],
                "skipped": report["skipped"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
