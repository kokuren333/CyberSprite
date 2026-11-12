"""Measure the original-art corpus and derive §11.9 thresholds (no art generation)."""

import argparse
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from cybersprite.pipeline.cleanup import cleanup_pixels
from cybersprite.pipeline.decode import decode_raster
from cybersprite.pipeline.downsample import downsample
from cybersprite.pipeline.grid import detect_grid
from cybersprite.pipeline.metrics import compute_metrics
from cybersprite.pipeline.quantize import quantize

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/pipeline/corpus"


def measure(name, category, image, truth, grid_options, palette=None):
    grid = detect_grid(image, **grid_options)
    working = grid if grid["detected"] else detect_grid(image, mode="none")
    downs, _ = downsample(image, working, method="median", background={"mode": "keep"})
    indices, locked, _ = quantize(
        downs,
        mode="fixed" if palette else "extract",
        source=palette,
        max_colors=255 if palette else 32,
    )
    final, _ = cleanup_pixels(indices[0], locked, min_cluster=1)
    metrics = compute_metrics(downs, [final], locked)
    decoded = np.asarray(locked, dtype=np.uint8)[final]
    return {
        "name": name,
        "category": category,
        "grid_score": grid["grid_score"],
        "fidelity": metrics["fidelity"],
        "detected": grid["detected"],
        "exact": truth is not None and np.array_equal(decoded, truth),
        "grid": {k: grid[k] for k in ("mode", "cell_w", "cell_h", "offset_x", "offset_y")},
    }


def records():
    for path in sorted((CORPUS / "originals").glob("*.png")):
        truth = decode_raster(path)[0][0]
        colors = sorted(
            {tuple(int(c) for c in pixel) for pixel in truth.reshape(-1, 4) if pixel[3] == 255}
        )
        palette = [(0, 0, 0, 0)] + colors
        for factor in range(2, 17):
            image = truth.repeat(factor, 0).repeat(factor, 1)
            yield measure(f"{path.stem}/x{factor}", "a", image, truth, {"mode": "auto"}, palette)
        image = truth.repeat(4, 0).repeat(4, 1)
        fixed = {"mode": "fixed", "cell_w": 4, "cell_h": 4}
        for quality in range(60, 96, 5):
            stream = io.BytesIO()
            Image.fromarray(image).convert("RGB").save(
                stream,
                format="JPEG",
                quality=quality,
                subsampling=0,
                optimize=False,
                progressive=False,
            )
            with Image.open(io.BytesIO(stream.getvalue())) as jpeg:
                degraded = np.array(jpeg.convert("RGBA"), dtype=np.uint8)
            yield measure(f"{path.stem}/q{quality}", "b", degraded, truth, fixed, palette)
        for numerator in (5, 7):
            h, w = truth.shape[:2]
            interpolated = np.array(
                Image.fromarray(truth).resize(
                    (w * numerator // 2, h * numerator // 2), resample=Image.Resampling.BILINEAR
                ),
                dtype=np.uint8,
            )
            yield measure(
                f"{path.stem}/s{numerator}-2",
                "c",
                interpolated,
                truth,
                {"mode": "target", "target_w": w, "target_h": h},
                palette,
            )
        for wrong in (5, 7):
            yield measure(
                f"{path.stem}/wrong{wrong}",
                "f",
                image,
                truth,
                {"mode": "fixed", "cell_w": wrong, "cell_h": wrong},
                palette,
            )
    for path in sorted((CORPUS / "non_pixel").glob("*.png")):
        image = decode_raster(path)[0][0]
        yield measure(path.stem, "e", image, None, {"mode": "fixed", "cell_w": 4, "cell_h": 4})


def thresholds(rows, metric, higher_good):
    good = [r[metric] for r in rows if r["category"] in "abc"]
    # Require 95% rejection separately for each negative category.
    limits = []
    for category in "ef":
        bad = sorted(r[metric] for r in rows if r["category"] == category)
        allowed = len(bad) * 5 // 100
        limits.append(bad[-allowed - 1] + 1 if higher_good else bad[allowed] - 1)
    if higher_good:
        lo, hi = max(limits), min(good)
        fail = (lo + hi) // 2 if lo <= hi else hi
        reference = min(r[metric] for r in rows if r["category"] == "a")
    else:
        lo, hi = max(good), min(limits)
        fail = (lo + hi) // 2 if lo <= hi else lo
        reference = max(r[metric] for r in rows if r["category"] == "a")
    return {
        "thresholds": [fail, (fail + reference) // 2],
        "separable": lo <= hi,
        "interval": [lo, hi],
    }


def next_version(defaults, previous, rows, grid, fidelity):
    version = defaults["calibration"]["version"]
    if version == 0:
        return 1
    unchanged = (
        previous is not None
        and previous.get("records") == rows
        and defaults["calibration"].get("pillow") == Image.__version__
        and defaults["presets"]["ai"]["gates"]
        == {"grid_score": grid["thresholds"], "fidelity": fidelity["thresholds"]}
        and defaults["presets"]["photo"]["gates"]["fidelity"] == fidelity["thresholds"]
    )
    return version if unchanged else version + 1


def calibrate():
    rows = list(records())
    assert all(r["exact"] for r in rows if r["category"] == "a")
    grid = thresholds(rows, "grid_score", True)
    fidelity = thresholds(rows, "fidelity", False)
    defaults_path = ROOT / "src/cybersprite/data/pipeline_defaults.json"
    defaults = json.loads(defaults_path.read_bytes())
    measurements_path = ROOT / "tests/pipeline/calibration_metrics.json"
    previous = json.loads(measurements_path.read_bytes()) if measurements_path.exists() else None
    version = next_version(defaults, previous, rows, grid, fidelity)
    defaults["calibration"] = {
        "version": version,
        "status": "original-corpus-pending-generated-d",
        "pillow": Image.__version__,
        "cases": len(rows),
        "pending": ["d"],
    }
    defaults["presets"]["ai"]["gates"] = {
        "grid_score": grid["thresholds"],
        "fidelity": fidelity["thresholds"],
    }
    defaults["presets"]["photo"]["gates"]["fidelity"] = fidelity["thresholds"]
    defaults_path.write_text(
        json.dumps(defaults, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    measured = {
        "calibration": defaults["calibration"],
        "grid_score": grid,
        "fidelity": fidelity,
        "records": rows,
    }
    (ROOT / "tests/pipeline/calibration_metrics.json").write_text(
        json.dumps(measured, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    lines = [
        f"# パイプライン較正（M6、版 {version}）",
        "",
        "正本はこの文書。測定値は `calibration_metrics.json`、"
        "再実行は `uv run python tools/calibrate_pipeline.py`。",
        "規範色表・整数パイプラインは共通で、JPEG と補間入力の作成だけに Pillow を使う。",
        "",
        "| 分類 | 件数 | 完全一致 | grid_score 範囲 | fidelity 範囲 |",
        "|---|---:|---:|---|---|",
    ]
    for category in "abcef":
        group = [r for r in rows if r["category"] == category]
        lines.append(
            f"| ({category}) | {len(group)} | {sum(r['exact'] for r in group)}/{len(group)} | "
            f"{min(r['grid_score'] for r in group)}〜{max(r['grid_score'] for r in group)} | "
            f"{min(r['fidelity'] for r in group)}〜{max(r['fidelity'] for r in group)} |"
        )
    lines += [
        "",
        "(a) は17作品の整数倍 ×2〜×16。全255件を auto で検出し RGBA で完全一致。",
        "単色場には境界情報がないので fixed を指定する。"
        "今回の flat_field 作品には鳥と単独点があり検出できた。",
        "(b) は ×4 を JPEG q60〜95（5刻み、subsampling=0）で圧縮。"
        "JPEG はアルファを保持しないため、透明作品の完全復元は期待できない。",
        "(c) は5/2・7/2倍の bilinear 補間。正解の列数・行数を target で指定した。",
        "(b)(c)(f) のパレットは正解の色。後始末は min_cluster=1、背景 keep、縮小 median。",
        "(e) は12枚を4×4セルで測定し32色抽出。(f) は倍率4の入力へセル幅5・7を故意に指定。",
        "(d) は M9 の生成バックエンド待ち。較正の完了を主張せず、到着後に版を上げて再測定する。",
        "",
        "## しきい値の選択",
        "",
        f"grid_score の可能区間は {grid['interval']}、採用 fail/warn は {grid['thresholds']}。",
        f"fidelity の可能区間は {fidelity['interval']}、"
        f"採用 fail/warn は {fidelity['thresholds']}。",
        "(e) と (f) 各95%拒否と (a)〜(c) 全合格を同時に満たす区間がない指標は、"
        "§11.9 の規則に従い正解格子の全合格を優先した。",
        "fidelity は格子の正しさを測らず、疎な誤格子でも純度が高くなるため、"
        "これらの数値だけで非ドット画像や誤格子を95%拒否できるとは言えない。",
        "ai/photo に較正値を適用。exact/upscaled の無損失 fidelity=0 と"
        " upscaled の厳密純度990/1000は、整数拡大の用途に限定して維持した。",
        "",
        "## 各画像の測定",
        "",
        "| 分類 | ケース | grid_score | fidelity | 完全一致 |",
        "|---|---|---:|---:|---|",
    ]
    lines += [
        f"| {r['category']} | {r['name']} | {r['grid_score']} | "
        f"{r['fidelity']} | {'yes' if r['exact'] else 'no'} |"
        for r in rows
    ]
    (ROOT / "tests/pipeline/CALIBRATION.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({k: v for k, v in measured.items() if k != "records"}))


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    calibrate()
