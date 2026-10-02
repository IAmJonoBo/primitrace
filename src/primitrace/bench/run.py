"""The noise floor and the frozen baseline (milestone 0).

``noise_floor`` draws every ground-truth mark with both renderers and records, per metric, the
95th percentile of their disagreement. ``SAFETY`` times that is the smallest difference any gate
may claim.

``baseline`` traces every synthetic sample with each baseline arm and scores it against the
ground truth:

* ``potrace``: ``prep.prepare`` then stacked potrace layers (the current product);
* ``vtracer``: ``prep.prepare`` then vtracer in cutout spline mode.

The traces are drawn back in the ground truth's frame. The result, with the tool versions and
conventions it was measured under, is ``baseline.json``, which later milestones are compared
against item by item.
"""

from __future__ import annotations

import datetime as dt
import platform
import re
import resource
import statistics
import sys
import time
from collections.abc import Callable, Iterable

import numpy as np

from primitrace import prep, trace
from primitrace.bench import render as R
from primitrace.bench import shape, synthetic

SAFETY = 2.0  # a difference counts only above SAFETY × the noise floor
ARMS: dict[str, Callable[[prep.Prepared], str]] = {
    "potrace": lambda p: trace.layered_svg(p.rgba, p.palette),
    "vtracer": lambda p: trace.colour_svg(p.rgba),
}


def _inner(svg: str) -> str:
    """The content of an SVG's root element."""
    m = re.search(r"<svg\b[^>]*>(.*)</svg>", svg, flags=re.S)
    return m.group(1) if m else ""


def in_truth_frame(traced: str, p: prep.Prepared, source_px: int) -> str:
    """A trace drawn in the prepared frame, re-expressed in the ground truth's view box."""
    k = synthetic.VIEW / source_px
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {synthetic.VIEW} {synthetic.VIEW}" '
        f'width="{synthetic.VIEW}" height="{synthetic.VIEW}">'
        f'<g transform="scale({k:.10g}) {p.source_transform()}">{_inner(traced)}</g></svg>'
    )


def _metric_rows(s: shape.Score) -> dict[str, float]:
    rows = {"1-iou": 1 - s.iou, "hausdorff": s.hausdorff, "chamfer": s.chamfer}
    for d, v in s.ssim.items():
        rows[f"1-ssim@{d}"] = 1 - v
    if s.delta_e is not None:
        rows["delta_e"] = s.delta_e
    return rows


def noise_floor(marks: Iterable[synthetic.Mark], sizes: tuple[int, ...] = synthetic.SIZES) -> dict[str, object]:
    """Per metric, the p95 disagreement between the pinned and the independent renderer."""
    samples: dict[str, list[float]] = {}
    for m in marks:
        for size in sizes:
            s = shape.score(m.svg, m.svg, size, renderer=R.independent, truth_renderer=R.pinned,
                            optimise_candidate=False)  # fmt: skip
            for k, v in _metric_rows(s).items():
                samples.setdefault(k, []).append(v)
    floor = {k: round(float(np.percentile(v, 95)), 6) for k, v in sorted(samples.items())}
    return {"p95": floor, "safety": SAFETY, "samples": len(next(iter(samples.values()), []))}


def baseline(count: int, seed: int, arms: Iterable[str] = ("potrace", "vtracer"),
             progress: Callable[[str], None] | None = None) -> dict[str, object]:  # fmt: skip
    """Trace and score every synthetic sample with each arm."""
    items = []
    started = time.monotonic()
    for sample in synthetic.samples(count, seed):
        src = synthetic.raster(sample)
        row: dict[str, object] = {"id": sample.id, "size": sample.size, "degradation": sample.degradation,
                                  "palette": len(sample.mark.palette),
                                  "primitives": [p.kind for p in sample.mark.primitives]}  # fmt: skip
        truth_nodes = shape.complexity(shape.optimise(sample.mark.svg))[0]
        row["truth_nodes"] = truth_nodes
        p = prep.prepare(src)
        for arm in arms:
            t0 = time.monotonic()
            try:
                cand = in_truth_frame(ARMS[arm](p), p, sample.size)
                s = shape.score(cand, sample.mark.svg, sample.size)
                row[arm] = {**s.as_dict(), "node_ratio": round(s.nodes / max(1, truth_nodes), 3),
                            "seconds": round(time.monotonic() - t0, 3)}  # fmt: skip
            except Exception as exc:  # recorded, never hidden: a failing arm is a baseline fact
                row[arm] = {"error": f"{type(exc).__name__}: {exc}"}
        items.append(row)
        if progress:
            progress(sample.id)
    return {
        "items": items,
        "summary": summarise(items, arms),
        "seconds": round(time.monotonic() - started, 1),
        "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1 << 20), 1)
        if sys.platform == "darwin"
        else round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
    }


def summarise(items: list[dict], arms: Iterable[str]) -> dict[str, dict[str, float]]:
    out = {}
    for arm in arms:
        ok = [r[arm] for r in items if isinstance(r.get(arm), dict) and "error" not in r[arm]]
        if not ok:
            out[arm] = {"scored": 0}
            continue
        out[arm] = {
            "scored": len(ok),
            "errors": len(items) - len(ok),
            "median_iou": round(statistics.median(x["iou"] for x in ok), 5),
            "median_hausdorff": round(statistics.median(x["hausdorff"] for x in ok), 4),
            "p95_hausdorff": round(float(np.percentile([x["hausdorff"] for x in ok], 95)), 4),
            "median_chamfer": round(statistics.median(x["chamfer"] for x in ok), 4),
            "median_ssim16": round(statistics.median(x["ssim"]["16"] for x in ok), 4),
            "median_node_ratio": round(statistics.median(x["node_ratio"] for x in ok), 3),
            "median_seconds": round(statistics.median(x["seconds"] for x in ok), 3),
            "primitive_share": round(statistics.mean(x["primitive_share"] for x in ok), 4),
        }
    return out


def conventions() -> dict[str, object]:
    return {
        "view": synthetic.VIEW,
        "sizes": list(synthetic.SIZES),
        "degradations": list(synthetic.DEGRADATIONS),
        "oversample": shape.OVERSAMPLE,
        "resample_points_per_source_px": shape.RESAMPLE,
        "display_sizes": list(shape.DISPLAY_SIZES),
        "distance_unit": "source px",
        "nodes": "path segments + 1 per circle/ellipse/rect + 1 per polygon vertex, on pinned svgo output",
    }


def versions() -> dict[str, str]:
    from importlib.metadata import version

    return {
        "pinned_rasteriser": R.pinned_version(),
        "independent_renderer": R.independent_version(),
        "svgo": shape.svgo_version(),
        "potrace": trace.potrace_version(),
        "vtracer": version("vtracer"),
        "python": platform.python_version(),
        "numpy": np.__version__,
    }


def stamp() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
