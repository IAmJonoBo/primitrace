"""Scoring a candidate SVG against a ground-truth SVG.

Conventions (recorded in ``baseline.json`` and asserted by tests):

* **Frame.** Both SVGs share the ground truth's view box and are drawn by the same renderer.
  Distances are reported in **source pixels** (the raster the candidate was traced from).
* **Contours** are sub-pixel iso-contours (alpha 0.5) of the ink drawn at ``OVERSAMPLE`` pixels per
  source pixel, then resampled at ``RESAMPLE`` points per source pixel of arclength, both for the
  candidate and the truth, so Hausdorff and Chamfer do not depend on vertex density.
* **SSIM** of the alpha-premultiplied luminance at each display size in ``DISPLAY_SIZES`` (logos are
  mostly seen small).
* **Complexity** is counted on the pinned svgo's output (``tools/svgo``): ``nodes`` = path segments
  plus one per native primitive element (circle, ellipse, rect) plus one per polygon vertex;
  ``primitives`` = native elements; ``primitive_share`` = primitives / (primitives + paths).
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import asdict, dataclass

import numpy as np

from primitrace.bench import render as R

OVERSAMPLE = 8  # render pixels per source pixel when extracting contours
RESAMPLE = 4  # contour points per source pixel of arclength, for Hausdorff and Chamfer
DISPLAY_SIZES = (16, 32, 64, 256)
ALPHA_INK = 0.5

# The pinned svgo: tools/svgo in a checkout, or wherever PRIMITRACE_SVGO_DIR points.
SVGO_DIR = os.environ.get(
    "PRIMITRACE_SVGO_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "..", "tools", "svgo")
)
_ARGS = {"m": 2, "l": 2, "h": 1, "v": 1, "c": 6, "s": 4, "q": 4, "t": 2, "a": 7, "z": 0}


@dataclass(frozen=True)
class Score:
    iou: float
    hausdorff: float  # source px
    chamfer: float  # source px (mean symmetric nearest-point distance)
    ssim: dict[int, float]  # display size -> SSIM
    delta_e: float | None  # mean CIELAB ΔE over shared ink (None when one side has no ink)
    nodes: int
    primitives: int
    paths: int
    primitive_share: float

    def as_dict(self) -> dict[str, object]:
        d = asdict(self)
        d["ssim"] = {str(k): v for k, v in self.ssim.items()}
        return d


def svgo_bin() -> str:
    return os.path.normpath(os.path.join(SVGO_DIR, "node_modules", ".bin", "svgo"))


def svgo_version() -> str:
    return subprocess.run([svgo_bin(), "--version"], check=True, capture_output=True, text=True).stdout.strip()


def optimise(svg: str) -> str:
    """``svg`` through the pinned svgo with the committed config (tools/svgo/svgo.config.mjs)."""
    config = os.path.normpath(os.path.join(SVGO_DIR, "svgo.config.mjs"))
    return subprocess.run(
        [svgo_bin(), "--config", config, "-i", "-", "-o", "-"],
        input=svg,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    ).stdout


def path_segments(d: str) -> int:
    """Drawing segments in path data, counting implicit repeats (``l1 2 3 4`` is two)."""
    segments = 0
    for cmd, args in re.findall(r"([MmLlHhVvCcSsQqTtAaZz])([^MmLlHhVvCcSsQqTtAaZz]*)", d):
        per = _ARGS[cmd.lower()]
        if per == 0:
            continue
        numbers = re.findall(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", args)
        if cmd.lower() == "a":  # arc flags may be written without separators ("a5 5 0 1 0 10 0" or "0110")
            numbers = _arc_numbers(args)
        n = max(1, len(numbers) // per)
        segments += n - 1 if cmd.lower() == "m" else n  # a moveto's own point is not a segment
    return segments


def _arc_numbers(args: str) -> list[str]:
    out: list[str] = []
    tokens = re.findall(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", args)
    for tok in tokens:
        slot = len(out) % 7
        if slot in (3, 4) and len(tok) > 1 and set(tok) <= {"0", "1"}:  # packed flags
            out.extend(tok[:2])
            if len(tok) > 2:
                out.append(tok[2:])
        else:
            out.append(tok)
    return out


def complexity(svg: str) -> tuple[int, int, int]:
    """(nodes, native primitives, paths) of an already-optimised SVG."""
    paths = re.findall(r'<path\b[^>]*\bd="([^"]*)"', svg)
    nodes = sum(path_segments(d) for d in paths)
    natives = re.findall(r"<(circle|ellipse|rect)\b", svg)
    nodes += len(natives)
    polygons = re.findall(r'<poly(?:gon|line)\b[^>]*\bpoints="([^"]*)"', svg)
    for pts in polygons:
        nodes += len(re.findall(r"-?(?:\d+\.?\d*|\.\d+)", pts)) // 2
    primitives = len(natives) + len(polygons)
    return nodes, primitives, len(paths)


def _alpha(svg: str, side: int, renderer=R.pinned) -> np.ndarray:
    return renderer(svg, side, side)[..., 3].astype(np.float32) / 255


def contours(alpha: np.ndarray, per_source_px: float) -> list[np.ndarray]:
    """Iso-contours (alpha 0.5) in source px, each resampled at ``RESAMPLE`` points per source px."""
    from skimage import measure

    out = []
    padded = np.pad(alpha, 1)  # close contours that touch the border
    for c in measure.find_contours(padded, ALPHA_INK):
        pts = (c[:, ::-1] - 1) / per_source_px  # (x, y), source px
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        length = float(seg.sum())
        if length <= 0:
            continue
        s = np.concatenate([[0.0], np.cumsum(seg)])
        n = max(8, int(round(length * RESAMPLE)))
        t = np.linspace(0, length, n, endpoint=False)
        out.append(np.stack([np.interp(t, s, pts[:, 0]), np.interp(t, s, pts[:, 1])], axis=1))
    return out


def distances(a: list[np.ndarray], b: list[np.ndarray]) -> tuple[float, float]:
    """(Hausdorff, Chamfer) between two contour sets; (inf, inf) when exactly one set is empty."""
    from scipy.spatial import cKDTree

    if not a and not b:
        return 0.0, 0.0
    if not a or not b:
        return float("inf"), float("inf")
    pa, pb = np.concatenate(a), np.concatenate(b)
    da, _ = cKDTree(pb).query(pa)
    db, _ = cKDTree(pa).query(pb)
    return float(max(da.max(), db.max())), float((da.mean() + db.mean()) / 2)


def ssim(a: np.ndarray, b: np.ndarray) -> float:
    from skimage.metrics import structural_similarity

    return float(structural_similarity(a, b, data_range=1.0))


def _premultiplied_luma(rgba: np.ndarray) -> np.ndarray:
    rgb = rgba[..., :3].astype(np.float32) / 255
    alpha = rgba[..., 3:4].astype(np.float32) / 255
    return ((rgb * alpha) @ np.array([0.2126, 0.7152, 0.0722], np.float32)).astype(np.float32)


def _delta_e(a: np.ndarray, b: np.ndarray) -> float | None:
    import cv2

    both = (a[..., 3] >= 128) & (b[..., 3] >= 128)
    if not both.any():
        return None
    scale = np.array([100 / 255, 1, 1], np.float32)
    la = cv2.cvtColor(np.ascontiguousarray(a[..., :3]), cv2.COLOR_RGB2LAB).astype(np.float32)[both] * scale
    lb = cv2.cvtColor(np.ascontiguousarray(b[..., :3]), cv2.COLOR_RGB2LAB).astype(np.float32)[both] * scale
    return float(np.mean(np.linalg.norm(la - lb, axis=1)))


def score(candidate: str, truth: str, source_px: int, *, renderer=R.pinned, truth_renderer=None,
          optimise_candidate: bool = True) -> Score:  # fmt: skip
    """Score ``candidate`` against ``truth``; both are drawn in the truth's frame.

    ``source_px`` is the side of the raster the candidate came from (distances are in its pixels).
    ``truth_renderer`` defaults to ``renderer``; the noise floor passes two different ones.
    """
    truth_renderer = truth_renderer or renderer
    cand = optimise(candidate) if optimise_candidate else candidate
    side = source_px * OVERSAMPLE
    ca, ta = renderer(cand, side, side), truth_renderer(truth, side, side)
    ink_c, ink_t = ca[..., 3] >= 128, ta[..., 3] >= 128
    union = (ink_c | ink_t).sum()
    iou = float((ink_c & ink_t).sum() / union) if union else 1.0
    h, c = distances(
        contours(ca[..., 3].astype(np.float32) / 255, OVERSAMPLE),
        contours(ta[..., 3].astype(np.float32) / 255, OVERSAMPLE),
    )
    sims = {}
    for d in DISPLAY_SIZES:
        sims[d] = round(
            ssim(_premultiplied_luma(renderer(cand, d, d)), _premultiplied_luma(truth_renderer(truth, d, d))), 4
        )
    nodes, prims, paths = complexity(cand)
    share = prims / (prims + paths) if (prims + paths) else 0.0
    de = _delta_e(ca, ta)
    return Score(round(iou, 5), round(h, 4), round(c, 4), sims, None if de is None else round(de, 3),
                 nodes, prims, paths, round(share, 4))  # fmt: skip
